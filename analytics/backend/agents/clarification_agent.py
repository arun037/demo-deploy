"""
Clarification Agent - Intelligent conversational query clarification
Asks intelligent follow-up questions like a data analyst to ensure accurate results

Ported from research-implement with exact prompts and logic
"""
from backend.core.llm_client import LLMClient
from backend.config import Config
from backend.core.logger import logger
from backend.utils.business_context_loader import BusinessContextLoader
import json

class ClarificationAgent:
    def __init__(self, llm_client: LLMClient, data_sampler=None, date_format_detector=None):
        self.llm = llm_client
        self.data_sampler = data_sampler
        self.date_format_detector = date_format_detector
    
    def _extract_schema_elements(self, user_query, schema_context):
        """Extract schema-specific elements relevant to the query - 100% dynamic, no hardcoding."""
        import re
        
        elements = {
            'tables': [],
            'key_columns': {}
        }
        
        # Extract table names from schema context (supports both formats)
        # Format 1: TABLE: leads_all_business
        table_matches = re.findall(r'TABLE:\s*(\w+)', schema_context)
        if not table_matches:
            # Format 2: JSON style "table": "xxx"
            table_matches = re.findall(r'"table":\s*"(\w+)"', schema_context)
        if not table_matches:
            table_matches = re.findall(r'Table[:\s]+(\w+)', schema_context)
        elements['tables'] = list(dict.fromkeys(table_matches))  # Deduplicate preserving order
        
        # Extract key columns from schema for each table
        for table in elements['tables']:
            # Find the section for this table (between two TABLE: markers)
            pattern = rf'TABLE:\s*{re.escape(table)}(.*?)(?=TABLE:|$)'
            section_match = re.search(pattern, schema_context, re.DOTALL)
            
            if section_match:
                table_section = section_match.group(1)
                # Extract column names from "  - column_name (type)" format
                col_matches = re.findall(r'-\s+(\w+)\s*\(', table_section)
                if col_matches:
                    elements['key_columns'][table] = col_matches[:15]  # Include more columns
            else:
                # Fallback: try JSON-style parsing
                if f'"table": "{table}"' in schema_context:
                    table_section = schema_context.split(f'"table": "{table}"')[1].split('"table":')[0]
                    col_matches = re.findall(r'"(\w+)"\s*\([^)]+\)', table_section)
                    if col_matches:
                        elements['key_columns'][table] = col_matches[:15]
        
        return elements
    

    def analyze_query_conversational(self, user_query, schema_context, intent, chat_history=[], full_context=None):
        """
        Analyze user query and generate intelligent conversational follow-up questions.
        
        Args:
            user_query: Current user query
            schema_context: Database schema
            intent: Classified intent
            chat_history: Recent conversation messages
            full_context: Enhanced context with pipeline awareness (optional)
            
        Returns (needs_clarification, questions, context)
        """
        # Build UNIFIED Conversation & Context Block
        # Merges recent chat history with deep context (previous SQL, results, entities)
        conversation_context = ""
        
        if chat_history:
            conversation_context += "\n=== CONVERSATION HISTORY ===\n"
            for msg in chat_history[-2:]:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                conversation_context += f"{role.upper()}: {content[:200]}\n"
            
            # Add Deep Context from Pipeline (if available)
            if full_context:
                # 1. Follow-up Context (Critical for "show me by site", etc.)
                if full_context.get('has_previous_context') and full_context.get('previous_query'):
                    conversation_context += "\n--- PREVIOUS QUERY CONTEXT ---\n"
                    conversation_context += f"Last User Query: {full_context['previous_query']}\n"
                    
                    # Include redacted SQL snippet
                    prev_sql = full_context.get('previous_sql')
                    if prev_sql:
                        conversation_context += f"Last SQL (Snippet): {prev_sql[:300]}...\n"
                    
                    # Include result summary
                    prev_summary = full_context.get('previous_result_summary')
                    if prev_summary and prev_summary.get('row_count'):
                        conversation_context += f"Last Result: {prev_summary['row_count']} rows returned\n"
                        
                    # Include tables used
                    prev_tables = full_context.get('previous_tables', [])
                    if prev_tables:
                        conversation_context += f"Tables Used: {', '.join(prev_tables)}\n"

                # 2. Extracted Entities & Filters
                extracted = full_context.get('extracted_context', {})
                if extracted.get('time_scope') or extracted.get('filters') or extracted.get('entities'):
                    conversation_context += "\n--- KNOWN ENTITIES & FILTERS ---\n"
                    if extracted.get('time_scope'):
                        conversation_context += f"Time Period: {extracted['time_scope']}\n"
                    if extracted.get('filters'):
                        conversation_context += f"Active Filters: {', '.join(extracted['filters'])}\n"
                    if extracted.get('entities'):
                        conversation_context += f"Entities: {', '.join(extracted['entities'])}\n"
                
                # 3. Clarification History
                pipeline = full_context.get('pipeline_context', {})
                if pipeline.get('clarification_asked'):
                    conversation_context += "\n--- CLARIFICATION STATUS ---\n"
                    conversation_context += "[WARN] Clarification was already asked recently. Avoid repetitive questions.\n"

            conversation_context += "=== END CONVERSATION ===\n"
        # Extract schema elements (tables, columns)
        schema_elements = self._extract_schema_elements(user_query, schema_context)
        
        # Build schema elements context for LLM
        schema_elements_str = ""
        if schema_elements['tables']:
            schema_elements_str += f"\n=== SCHEMA ELEMENTS FOR THIS QUERY ===\n"
            schema_elements_str += f"Tables: {', '.join(schema_elements['tables'])}\n"
            
            if schema_elements['key_columns']:
                schema_elements_str += "\nKey Columns by Table:\n"
                for table, cols in schema_elements['key_columns'].items():
                    schema_elements_str += f"  {table}: {', '.join(cols[:5])}\n"
        
        # Optimize Schema Context for Speed (Prevent Timeouts)
        # Truncate if extremely large (approx 6-8k tokens)
        MAX_SCHEMA_CHARS = 25000
        optimized_schema_context = schema_context[:MAX_SCHEMA_CHARS] + "\n...(truncated for performance)..." if len(schema_context) > MAX_SCHEMA_CHARS else schema_context
        
        # Load business context
        business_context = BusinessContextLoader.load_context()
        
        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        
        system_prompt = f"""You are a Thoughtful Data Analyst having a conversation with a business user.

Today's Date: {today}

BUSINESS CONTEXT:
{business_context}

Database Schema (KEY COLUMNS include [VALUES: ...] for filter/categorical columns):
{optimized_schema_context}
{schema_elements_str}

{conversation_context}

User Query: "{user_query}"
Detected Intent: {intent}


 STEP 1  READ EXISTING CONTEXT FIRST

Before generating ANY questions, carefully read:
  - CONVERSATION HISTORY above
  - PREVIOUS QUERY CONTEXT above
  - KNOWN ENTITIES & FILTERS above
  - CLARIFICATION STATUS above

If the user or the context already answered something, NEVER ask about it again.
If CLARIFICATION STATUS says clarification was recently asked, be extra conservative.


 STEP 2  IDENTIFY GENUINE GAPS


Ask when:
  - A term or metric is ambiguous and different interpretations would produce DIFFERENT results
  - A time period or date range is missing and the data is clearly time-sensitive
  - A filter value is undefined and could include or exclude significant data

NEVER ask when:
  - The user already gave the information (check CONVERSATION HISTORY / KNOWN ENTITIES)
  - The answer is a database/SQL decision (e.g. which column to SELECT, how to JOIN)
  - The user explicitly stated a specific name, entity, or search string (e.g., "Franchise For Sale website", "Acme Corp"). DO NOT force them to clarify their explicit search string against a list of example schema values. If they say "Franchise For Sale", DO NOT ask "which site are you referring to?" with options from the schema. TRUST THEIR EXPLICIT STRING. Providing example values as clarification options for a string they already provided is strictly prohibited.


 STEP 3  TIME SCOPE RULE (CRITICAL)


If the schema contains any date/time columns AND the user did NOT explicitly specify a time
period (e.g. "last month", "Q1 2024", "last 30 days"), you MUST ask for the time range.
This rule overrides everything else  missing time period = always ask.

Exception: If KNOWN ENTITIES already shows a Time Period, skip this question.


 STEP 4  WRITE GREAT QUESTIONS WITH REAL OPTIONS


Rules for QUESTIONS:
  - Plain business language. No column names, no SQL terms, no technical jargon.
  - Max 3 questions total. Ask the most critical one first.

Rules for OPTIONS — read the context above FIRST, then derive:
  - Look at the [VALUES: ...] in the schema for that column. Those are your options.
  - Look at the ACTUAL DATA VALUES (sampled) section above. Those are your options.
  - Look at the date range info for time questions. Derive sensible periods from the actual
    min/max dates in the data — don't guess or invent periods.
  - Each option must produce a meaningfully DIFFERENT query result.
  - 2–4 options maximum. If only 2 make sense, use yes/no.
  - Every option must be something the user can simply click. It must be a real, concrete value.

NEVER put these in options — they are meaningless buttons:
  "Other" | "Custom" | "Specify" | "None of the above" | "All of the above"
  "N/A" | "Not sure" | "Depends" | "Something else" | "Please specify" | "All options"
  If you cannot find real concrete values from the schema/data, skip the question or use yes/no.

OUTPUT FORMAT (JSON):
{{
    "needs_clarification": true/false,
    "best_guess_assumptions": "Your smartest assumption if NOT asking questions. Leave empty if you ARE asking questions.",
    "questions": [
        {{
            "id": 1,
            "category": "metrics|granularity|status|time|scope|sorting|filters",
            "question": "Business-friendly question with no column names or SQL terms",
            "question_type": "multiple_choice|yes_no",
            "options": ["<derived from schema/data context>", "<derived from schema/data context>"],
            "importance": "critical|high|medium|low",
            "reasoning": "What different result would each answer produce?"
        }}
    ],
    "reasoning": "Why these clarifications are needed"
}}

IMPORTANCE LEVELS:
  critical  query would produce WRONG/misleading results without this
  high      missing time range, ambiguous key metric
  medium    would produce correct but not-ideal results
  low       nice-to-have output formatting
"""
        
        try:
            response = self.llm.call_agent(
                system_prompt, 
                "Analyze this query and generate intelligent follow-up questions.",
                model=Config.CLARIFICATION_MODEL,
                timeout=Config.CLARIFICATION_TIMEOUT,
                agent_name="ClarificationAgent"
            )
            
            # Parse JSON response
            analysis = self._parse_json_response(response)
            
            if analysis.get('needs_clarification', False):
                questions = analysis.get('questions', [])
                questions.sort(key=lambda q: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(q.get('importance', 'medium'), 2))
                
                # Sanitize options to remove vague 'please specify' / 'custom' wording
                questions = self._sanitize_question_options(questions)
                
                # POST-GENERATION FILTER: Remove questions already answered by the user's query
                questions = self._filter_redundant_questions(user_query, questions, full_context)
                
                if not questions:
                    logger.info("All clarification questions filtered as redundant — proceeding without clarification")
                    return False, [], {'schema_elements': schema_elements}
                
                context = {
                    'schema_elements': schema_elements,
                    'best_guess_assumptions': analysis.get('best_guess_assumptions', '')
                }
                return True, questions, context
            
            return False, [], {'schema_elements': schema_elements, 'best_guess_assumptions': analysis.get('best_guess_assumptions', '')}
        
        except Exception as e:
            logger.error(f"Conversational clarification failed: {e}")
            return False, [], {}
    
    def generate_next_question(self, user_query, schema_context, intent, answered_pairs, chat_history=[], full_context=None):
        """
        Generate the NEXT clarification question based on what's already been answered.
        
        This is the core of the sequential flow:
        - Takes previous Q&A pairs
        - Decides if another question is needed
        - If yes, returns exactly 1 new question
        - If no, returns needs_more=False
        
        Args:
            user_query: Original user query
            schema_context: Database schema
            intent: Classified intent
            answered_pairs: List of {"question": ..., "answer": ..., "category": ...}
            chat_history: Recent conversation messages
            full_context: Enhanced context
            
        Returns:
            (needs_more, question_or_none, context)
        """
        # Build what we already know from answers
        answered_summary = ""
        answered_categories = set()
        if answered_pairs:
            answered_summary = "\n=== ALREADY ANSWERED BY USER ===\n"
            for pair in answered_pairs:
                answered_summary += f"Q: {pair.get('question', '')}\n"
                answered_summary += f"A: {pair.get('answer', '')}\n"
                if pair.get('category'):
                    answered_categories.add(pair['category'])
            answered_summary += "=== END ANSWERED ===\n"
        
        # Build context
        conversation_context = ""
        if chat_history:
            conversation_context += "\n=== RECENT CONVERSATION ===\n"
            for msg in chat_history[-2:]:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                conversation_context += f"{role.upper()}: {content[:150]}\n"
            conversation_context += "=== END CONVERSATION ===\n"
        
        # Schema elements
        schema_elements = self._extract_schema_elements(user_query, schema_context)
        
        schema_elements_str = ""
        if schema_elements['tables']:
            schema_elements_str += f"\nTables: {', '.join(schema_elements['tables'])}\n"
            if schema_elements['key_columns']:
                for table, cols in schema_elements['key_columns'].items():
                    schema_elements_str += f"  {table}: {', '.join(cols[:5])}\n"
        
        MAX_SCHEMA_CHARS = 25000
        optimized_schema = schema_context[:MAX_SCHEMA_CHARS] if len(schema_context) > MAX_SCHEMA_CHARS else schema_context
        
        business_context = BusinessContextLoader.load_context()
        
        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        
        system_prompt = f"""You are an Expert Data Analyst having a follow-up conversation with a business user.

Today's Date: {today}

BUSINESS CONTEXT:
{business_context}

Database Schema (KEY COLUMNS include [VALUES: ...] for filter columns):
{optimized_schema}
{schema_elements_str}

{conversation_context}

User Query: "{user_query}"
Detected Intent: {intent}

{answered_summary}


 DECISION: Does ONE more question remain?


STEP 1  Check what's ALREADY KNOWN:
  - Read ALREADY ANSWERED  never re-ask covered categories
  - Read RECENT CONVERSATION  check if user answered indirectly
  - Resolved schema values [VALUES: ...] count as answered too

STEP 2  Apply TIME SCOPE RULE:
  - If the data has date columns AND no time period was mentioned by the user OR found in ALREADY ANSWERED  ask for it (importance: critical)
  - "this year" = {today[:4]}, "last month" = relative to {today}

STEP 3  Final gap check:
  - Is there exactly ONE remaining critical ambiguity?
  - If answered + schema already cover everything  return needs_more: false
  - If the user stated an explicit filter (e.g. 'expired')  do NOT ask about other statuses

PROHIBITED QUESTIONS:
  F Questions asking the user to pick a column or field name (e.g. "which date column?")
  F Questions about SQL structure or how to join/group data
  F Questions about a category already in ALREADY ANSWERED
  F Leading questions that suggest including more data than the user asked for
  F Questions forcing the user to clarify an explicit name/entity they already provided against schema example values. (e.g., if they say "Franchise For Sale", don't ask if they mean "Business For Sale").
  F Options that are vague or non-committal — NEVER use:
    "Custom", "Other", "Something else", "None of the above", "All of the above",
    "N/A", "Not applicable", "Depends", "Specify", "Not sure"
    Every option must be a specific, concrete choice the user can simply click.

GOOD QUESTION STYLE — plain business language, zero SQL/column names:
  BAD:  "Which date column should I filter on?"
  GOOD: "Should this be based on when each record was created, or when it was last updated?"

GOOD OPTIONS STYLE — derive entirely from the schema and data context above:
  - For categorical columns: read the [VALUES: ...] from the schema — use those exact values.
  - For date/time columns: read the date RANGE (min/max dates) from the sampled data —
    derive meaningful periods that fit the actual data, don't invent them.
  - For metric questions: look at what the data contains and offer the relevant aggregations.
  - 2–4 options that each produce a DIFFERENT result. If only 2 fit, use yes_no.
  - If you cannot find real concrete values from the context, skip the question entirely.
  NEVER use: "Other", "Custom", "Specify", "None of the above", "N/A", "Depends", "Not sure"

OUTPUT FORMAT (JSON):
{{
    "needs_more": true/false,
    "reasoning": "Concise reason why another question is or isn't needed",
    "question": {{
        "id": {len(answered_pairs) + 1},
        "category": "metrics|granularity|status|time|scope|filters",
        "question": "Business-friendly question with no column names or SQL terms",
        "question_type": "multiple_choice|yes_no",
        "options": ["<derived from schema/data context>", "<derived from schema/data context>"],
        "importance": "critical|high|medium",
        "reasoning": "What different result would each answer produce?"
    }}
}}

If needs_more is false, omit the "question" field entirely.
"""
        
        try:
            response = self.llm.call_agent(
                system_prompt,
                "Decide if another clarification question is needed.",
                model=Config.CLARIFICATION_MODEL,
                timeout=Config.CLARIFICATION_TIMEOUT,
                agent_name="ClarificationAgent"
            )
            
            analysis = self._parse_json_response(response)
            
            if analysis.get('needs_more', False) and analysis.get('question'):
                question = analysis['question']
                
                # Sanitize options before any other checks
                sanitized = self._sanitize_question_options([question])
                question = sanitized[0] if sanitized else question
                
                # Filter: skip if category already answered
                category = question.get('category', '').lower()
                if category in answered_categories:
                    logger.info(f"Skipping question (category '{category}' already answered)")
                    return False, None, {'sampled_data': sampled_data, 'schema_elements': schema_elements}
                
                # Filter: skip if query already specifies this
                filtered = self._filter_redundant_questions(user_query, [question], full_context)
                if not filtered:
                    logger.info(f"Next question filtered as redundant")
                    return False, None, {'schema_elements': schema_elements}
                
                return True, question, {'schema_elements': schema_elements}
            
            return False, None, {'schema_elements': schema_elements}
            
        except Exception as e:
            logger.error(f"generate_next_question failed: {e}")
            return False, None, {}
    
    
    def build_refined_query_conversational(self, original_query, clarifications, context):
        """Build refined query from conversational clarifications."""
        system_prompt = f"""You are a Query Refinement Expert.

Original User Query: "{original_query}"

User's Clarifications (from conversation):
{json.dumps(clarifications, indent=2)}

Additional Context:
{json.dumps(context, indent=2)}

Your job: Create a REFINED, PRECISE, UNAMBIGUOUS query that incorporates all clarifications.

REFINEMENT RULES:
1. Keep the original intent and tone
2. Add ALL specific details from clarifications
3. Include date ranges if specified
4. Include entity filters (organization, vendor, department, category) if specified
5. Include metric specifications if clarified
6. Include status filters if specified
7. Include thresholds if specified
8. Make it sound natural and clear

EXAMPLES:

Original: "Show me orders"
Clarifications: {{"entity": "Acme Corp", "date_range": "Jan 1-15, 2024", "status": "approved"}}
Refined: "Show me all approved orders for Acme Corp from January 1 to January 15, 2024"

Original: "Top 10 items"
Clarifications: {{"metric": "revenue", "time_period": "last month", "status": "active"}}
Refined: "Show me the top 10 active items by total revenue from last month"

Original: "Price variance"
Clarifications: {{"comparison": "master vs transaction", "threshold": "variance > $50", "entity": "all vendors"}}
Refined: "Show me all items where the price variance between master and transaction prices is greater than $50, across all vendors"

Output ONLY the refined query, nothing else.
"""
        
        try:
            refined = self.llm.call_agent(
                system_prompt,
                "Generate the refined query.",
                model=Config.CLARIFICATION_MODEL,
                temperature=0.1,
                timeout=30,
                agent_name="ClarificationAgent"
            )
            
            # Clean response
            if "<think>" in refined:
                refined = refined.split("</think>")[-1]
            
            return refined.strip()
        
        except Exception as e:
            logger.error(f"Query refinement failed: {e}")
            return original_query
    
    def _sanitize_question_options(self, questions):
        """
        Post-generation sanitizer: removes vague, open-ended, or assistant-like phrasing
        from answer options before they are shown to the user as buttons.
        
        Blocked patterns:
          - "please specify" / "specify"
          - "custom" / "other" / "something else"
          - Options that are questions themselves (end with ?)
          - Empty or very short options (< 2 chars)
        """
        import re
        
        # Phrases that make an option vague, open-ended, or meaningless as a clickable choice
        blocked_patterns = [
            # Escape hatches — open-ended / non-committal
            r'\bnone of the above\b',
            r'\ball of the above\b',
            r'\bnone\b',
            r'\bn/a\b',
            r'\bnot applicable\b',
            r'\bdepends\b',
            r'\bit depends\b',
            # Instruction-style or "specify yourself"
            r'\bplease specify\b',
            r'\bspecify\b',
            r'\bcustom\b',
            r'\bother\b',
            r'\bsomething else\b',
            r'\benter manually\b',
            r'\blet me specify\b',
            r'\btype here\b',
            r'\bfill in\b',
            r'\bmanually\b',
            r'\bnot sure\b',
            r'\buncertain\b',
        ]
        compiled = [re.compile(p, re.IGNORECASE) for p in blocked_patterns]
        
        sanitized_questions = []
        for q in questions:
            raw_options = q.get('options', [])
            cleaned_options = []
            for opt in raw_options:
                opt_str = str(opt).strip()
                # Drop empty or too-short options
                if len(opt_str) < 2:
                    continue
                # Drop options that end with '?' (they're questions, not choices)
                if opt_str.endswith('?'):
                    logger.info(f"[OptionSanitizer] Dropped question-style option: '{opt_str}'")
                    continue
                # Drop options containing blocked patterns
                if any(p.search(opt_str) for p in compiled):
                    logger.info(f"[OptionSanitizer] Dropped vague option: '{opt_str}'")
                    continue
                cleaned_options.append(opt_str)
            
            # Only keep the question if it still has at least 2 meaningful options
            if len(cleaned_options) >= 2:
                q['options'] = cleaned_options
                sanitized_questions.append(q)
            elif len(cleaned_options) == 1:
                # Still useful  keep it but mark as yes_no if only 1 option remains
                q['options'] = cleaned_options
                sanitized_questions.append(q)
            else:
                # All options were vague  convert to text_input
                logger.info(f"[OptionSanitizer] All options removed for question '{q.get('question', '')[:60]}'  converting to text_input")
                q['question_type'] = 'text_input'
                q['options'] = []
                sanitized_questions.append(q)
        
        return sanitized_questions
    
    def _filter_redundant_questions(self, user_query, questions, full_context=None):
        """
        Post-generation filter: remove questions whose answers are already known.

        Uses two layers:
          1. Basic: question text is literally contained in the user query (rare but catches obvious cases).
          2. Context-aware: checks full_context['extracted_context'] for already-known
             time_scope, entities, and filters and suppresses the matching question categories.
        """
        if not questions:
            return []

        filtered = []
        query_lower = user_query.lower()

        # -- Build a set of already-known categories from full_context --
        known_categories = set()  # e.g. {'time', 'filters', 'entities'}
        if full_context:
            extracted = full_context.get('extracted_context', {})

            # Time scope already known  suppress 'time' questions
            if extracted.get('time_scope'):
                known_categories.add('time')
                logger.info(f"[RedundancyFilter] time_scope already known: '{extracted['time_scope']}'  suppressing 'time' questions")

            # Active filters already known  suppress 'filters' / 'status' questions
            if extracted.get('filters'):
                known_categories.add('filters')
                known_categories.add('status')
                logger.info(f"[RedundancyFilter] filters already known: {extracted['filters']}  suppressing filter/status questions")

            # Entities already known  suppress 'scope' / 'granularity' questions
            if extracted.get('entities'):
                known_categories.add('entities')
                logger.info(f"[RedundancyFilter] entities already known: {extracted['entities']}  suppressing entity/scope questions")

            # If clarification was already recently asked, be extra conservative
            pipeline = full_context.get('pipeline_context', {})
            if pipeline.get('clarification_asked'):
                # Drop medium/low importance questions entirely to prevent over-clarifying
                questions = [q for q in questions if q.get('importance') in ('critical', 'high')]
                logger.info("[RedundancyFilter] Clarification recently asked  retaining critical/high importance only")

        for q in questions:
            category = q.get('category', '').lower()
            question_text = q.get('question', '').lower()

            # LAYER 0 Anti-Coercion Check
            # If the LLM asks "when you say 'X'" or quotes a phrase 'X' from the user's query,
            # it is trying to coerce an explicit user string into a schema example. We strictly forbid this.
            import re
            quotes = re.findall(r"['\"]([^'\"]+)['\"]", q.get('question', ''))
            is_coercive = False
            for quoted_text in quotes:
                qt_lower = quoted_text.lower().strip()
                if len(qt_lower) > 3 and qt_lower in query_lower:
                    logger.info(f"[RedundancyFilter] Dropped coercive mapping question for explicit entity '{qt_lower}': {q.get('question', '')[:80]}")
                    is_coercive = True
                    break
            
            # Also catch "when you say X" without quotes
            if not is_coercive and "when you say" in question_text:
                logger.info(f"[RedundancyFilter] Dropped 'when you say' coercive question: {q.get('question', '')[:80]}")
                continue
                
            if is_coercive:
                continue

            # Layer 1  literal containment check (very rare but catches perfect duplicates)
            if question_text and len(question_text) > 5 and question_text in query_lower:
                logger.info(f"[RedundancyFilter] Literal match  filtered: {q.get('question', '')[:80]}")
                continue

            # Layer 2  context-aware category suppression
            if category in known_categories:
                logger.info(f"[RedundancyFilter] Category '{category}' already known in context  filtered: {q.get('question', '')[:80]}")
                continue

            filtered.append(q)

        return filtered
    
    def _parse_json_response(self, response):
        """Parse JSON from LLM response."""
        # Remove thinking blocks
        if "<think>" in response:
            response = response.split("</think>")[-1]
        
        # Extract JSON
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        try:
            return json.loads(response.strip())
        except Exception as e:
            logger.error(f"Failed to parse clarification response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return {"needs_clarification": False, "questions": []}
