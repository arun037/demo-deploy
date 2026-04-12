from backend.core.llm_client import LLMClient
from backend.config import Config
from backend.utils.business_context_loader import BusinessContextLoader

class QueryArchitect:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
            
    def generate_sql(self, user_query, intent, schema_context, full_context=None):
        # Load business context
        business_context = BusinessContextLoader.load_context()
        
        # Build conversational context
        history_str = ""
        if full_context and full_context.get('conversation_history'):
            history_str = "\nCONVERSATIONAL CONTEXT (Full history, oldest to newest):\n"
            # Iterate ALL messages in the window — the window size (12 raw messages = ~3 full
            # exchanges even with clarification rounds) is controlled by enhanced_context_manager.
            for msg in full_context['conversation_history']:
                role = msg.get('role', 'unknown').upper()
                if role == 'USER':
                    # Pass full user query — these are short and contain the exact intent
                    content = msg.get('content', '')
                    history_str += f"- USER: {content}\n"
                else:
                    # Pass a short summary of the assistant reply + the full SQL used
                    content = msg.get('content', '')[:150]
                    history_str += f"- ASSISTANT: {content}\n"
                    # Inject the previously generated SQL — critical for filter consistency
                    prev_sql = (
                        msg.get('responseMeta', {}).get('generatedSql', '')
                        or msg.get('sqlData', {}).get('generatedSql', '')
                    )
                    if prev_sql:
                        history_str += f"  [SQL USED IN PREVIOUS ANSWER]:\n  {prev_sql}\n"
        
        from datetime import date
        today = date.today().strftime('%Y-%m-%d')

        # Build intent-specific SQL guidance
        intent_guidance = ""
        if intent == "RANKING":
            intent_guidance = """
INTENT: RANKING
- Use ROW_NUMBER() OVER (PARTITION BY <group_col> ORDER BY <metric_col> DESC) for per-group top-N.
- PARTITION BY the unique ID column of the group entity (e.g., entity_id, group_id), NOT a name column — names can have duplicates or case variations.
- The final ORDER BY MUST sort by the metric column first (DESC), then optionally by the group label.
- In the SELECT list, place the metric column immediately after the primary label. Never put it last.
- Only add a global LIMIT if the user explicitly asks for one. Do NOT add a default limit.
- JOIN STRATEGY for ranking queries:
  * Default to LEFT JOIN for all joined tables to prevent rows from dropping due to missing data (even dimension tables like site, concept or customer). 
  * Only use INNER JOIN if explicitly filtering out records that don't have a match in the joined table.
  * Put all filters on the LEFT-joined event table (date ranges, status filters) in the WHERE clause — this is correct and intentional; it restricts which events are counted.
  * Do NOT move event-table filters into the JOIN ON clause for ranking queries — that would count ALL events instead of only the filtered ones.
"""
        elif intent == "METRIC_TREND":
            intent_guidance = """
INTENT: METRIC_TREND
- ALWAYS GROUP BY a time period (DATE_FORMAT(col, '%Y-%m') for monthly, YEAR(col) for yearly)
- ORDER BY the time column ASC
- SELECT the time column + aggregated metric(s)
- Do NOT return individual rows  aggregate by period
"""
        elif intent == "AGGREGATION":
            intent_guidance = """
INTENT: AGGREGATION
- Use aggregate functions: COUNT(), SUM(), AVG()
- Use GROUP BY if breaking down by a dimension
- Keep output concise  totals, counts, or grouped summaries
"""
        elif intent == "COMPARISON":
            intent_guidance = """
INTENT: COMPARISON
- Show values side-by-side across dimensions (e.g., region A vs B)
- Use conditional aggregation (SUM(CASE WHEN ... END)) or subqueries if needed
- ORDER BY the comparison dimension
"""
        elif intent == "DETAIL_RETRIEVAL":
            intent_guidance = """
INTENT: DETAIL_RETRIEVAL
- Return individual rows, not aggregates
- Include all key descriptive columns (name, status, date, category)
- Do NOT add a LIMIT unless the user explicitly asks for one (e.g. "top 10", "first 50")
"""

        system_prompt = f"""You are an Elite Data Architect and SQL Engineer.
Your job is to write a single, perfect MySQL query based on the user's question.

Today's Date: {today}
("this year" = {today[:4]}, "last month" / "last 30 days" = relative to {today})

BUSINESS CONTEXT:
{business_context}

{intent_guidance}
AVAILABLE SCHEMA:
{schema_context}

{history_str}

RULES (follow all, in order of priority):

1. CONTEXT PRIORITY & COMPREHENSIVE COVERAGE (CRITICAL)
   - SCHEMA PRECEDENCE: The structure, column names, and relationships defined in AVAILABLE SCHEMA are absolute truth. If BUSINESS CONTEXT contradicts the schema, ignore the business context and strictly follow the schema.
   - COMPREHENSIVE COVERAGE: If the schema or business context indicates multiple ways a condition can be satisfied (e.g. status ranges, alternate flags), you must use OR conditions to capture all valid variations rather than picking only one.

2. MULTI-DATABASE PREFIXING
   Always use fully-qualified table names (`database.table`). The schema shows `DATABASE: <name>` per table.
   Example: `FROM my_database.my_table`.


2. JOIN STRATEGY — DEFAULT TO LEFT JOIN
   - Default to LEFT JOIN for all tables. Sparse/inconsistent data means INNER JOIN silently drops rows.
   - Use INNER JOIN ONLY when the explicit goal is to exclude rows with no match.
   - STAR SCHEMA: Always start FROM the most granular fact/event table (the one with the metric being counted or summed). JOIN dimension/lookup tables onto it — never the reverse.
   - Filter placement: date ranges and status filters on LEFT-joined tables go in the WHERE clause, NOT the JOIN ON condition.

3. DATE FILTERING & FILTER INHERITANCE (CRITICAL)
   - Never use exact `=` on DATETIME columns. Use `DATE(col) = 'YYYY-MM-DD'` or `BETWEEN`.
   - Relative dates — always compute from CURDATE(), never hardcode:
     * "today" → `CURDATE()`
     * "yesterday" → `DATE_SUB(CURDATE(), INTERVAL 1 DAY)`
     * "last 30 days" → `col >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)`
     * "last month" → `MONTH(col) = MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH)) AND YEAR(col) = YEAR(...)`
     * "this month" → `MONTH(col) = MONTH(CURDATE()) AND YEAR(col) = YEAR(CURDATE())`
   - FILTER INHERITANCE: If CONVERSATIONAL CONTEXT shows a previous SQL query, you MUST silently carry forward ALL of its active filters (date ranges, entity IDs, status flags, UTM sources, etc.) into your new query, UNLESS the user explicitly asks to drop or change them. Do not lose context!
4. STRING MATCHING & EXAMPLE VALUES (CRITICAL)
   - ALWAYS review the `[VALUES: ...]` block in the schema context to understand the *format* of the column data.
   - For string columns, the `[VALUES: ...]` list only shows a SAMPLE (max 10 values). There may be many more distinct values in the database.
   - NEVER alter, translate, or replace the user's explicit search string to match an example value you see in the schema. If the user asks for 'Franchise For Sale', search for exactly that string (or its canonical form). Do NOT assume they meant 'Business For Sale' just because that is the closest example in the schema.
   - If the schema shows a column naturally holds only specific, non-descriptive flags or codes (e.g. 'PPL', 'SUCCESS', 'WEB'), you MUST use exactly those representations.
   - FOR FREE-TEXT/NAME SEARCHING: Use a combination of LOWER exact match, canonical REGEXP, and LIKE.
     When the user asks for a specific name (e.g. 'Franchise For Sale', 'Bob Smith'):
     * NEVER use simple `col = 'Value'`.
     * ALWAYS use case-insensitive, space-tolerant matching:
       `(LOWER(col) = LOWER('User String') OR REGEXP_REPLACE(LOWER(col), '[^a-z0-9]', '') REGEXP 'userstring' OR LOWER(col) LIKE '%user string%')`
   - The regex replacement `REGEXP_REPLACE` strips punctuation and spaces, allowing 'Franchise For Sale' to match 'franchiseforsale' or 'Franchise-For-Sale'.

5. SELECT — HUMAN-READABLE OUTPUT (MANDATORY PRE_FLIGHT BEFORE WRITING ANY SQL)

   ══ STEP 1 — LIST every ID column you plan to SELECT or GROUP BY. ══
   For EACH one, inspect the AVAILABLE SCHEMA:
     (a) Read its column description — it will say which table and column it references.
     (b) Check the `foreign_keys` section of the current table for the exact join target.

   ══ STEP 2 — RESOLVE each ID to its human-readable name. ══
   - Go to the referenced table in the AVAILABLE SCHEMA.
   - Find the column in that table that holds the human-readable label.
     Look for columns described as the entity's name, title, display name, or label.
   - If the FK is multi-hop (e.g. table A → table B → table C where the name lives),
     follow the full chain through the schema until you reach the name column.

   ══ STEP 3 — WRITE the query with JOINs and name columns. ══
   - Add a LEFT JOIN for every lookup table identified in Step 2.
   - SELECT the name column. Use an alias that describes what it represents,
     derived from the referenced table's purpose — NOT from hardcoded words.
   - NEVER select an ID column without its resolved name column from the referenced table.

   ADDITIONAL RULES:
   - Always include at least 3–5 descriptive columns alongside core metrics.
   - Column order: (1) resolved name/label first, (2) ID if contextually useful, (3) metric(s), (4) supporting columns.
   - Only select a bare ID if the AVAILABLE SCHEMA has no FK or name column for it — this should be extremely rare.

6. 1:N JOINS — PREVENT ROW DUPLICATION
   If joining a 1:N table (multiple categories, tags, or options per parent), use `GROUP_CONCAT(child_col)` and `GROUP BY parent_id` to roll up into one row per parent. Never return duplicate parent rows.

7. TYPE MATCHING
   When comparing a text column to a decimal, use `CAST(text_col AS DECIMAL(20,8))`.

8. LIMITS
   Add a LIMIT only if the user explicitly asks for one (e.g. "top 10", "first 50"). Never add a default limit.

OUTPUT FORMAT:
First, you MUST write your Rule 5 Pre-Flight Checklist inside a <think>...</think> block.
After the </think> tag, output ONLY the raw SQL. No markdown fences (```sql), no explanations. Just the query.

YOUR TASK: Write the exact MySQL query to answer: "{user_query}"
"""
        from backend.core.logger import logger
        
        logger.info("=" * 60)
        logger.info("QUERY ARCHITECT INPUT:")
        logger.info(f"User Query: {user_query}")
        logger.info(f"Intent: {intent}")
        logger.info(f"Schema (first 300 chars): {schema_context[:300]}...")
        
        # We use SYNTHESIZER_MODEL config as it has the same settings previously used for SQL gen
        raw_response = self.llm.call_agent(
            system_prompt, 
            user_query, 
            model=Config.SYNTHESIZER_MODEL, 
            timeout=120, 
            agent_name="QueryArchitect"
        )
        
        if "<think>" in raw_response:
            if "</think>" in raw_response:
                think_content = raw_response.split("</think>")[0].split("<think>")[1]
                logger.info(f"ARCHITECT THINKING: {think_content[:300]}...")
                raw_response = raw_response.split("</think>")[-1]
            else:
                # Unclosed think tag means it hit token limit before writing SQL
                think_content = raw_response.split("<think>")[1]
                logger.warning(f"ARCHITECT hit token limit inside <think> block: {think_content[-100:]}")
                raw_response = "" # No SQL was generated
            
        sql = self._clean_sql(raw_response)
        logger.info(f"ARCHITECT OUTPUT (SQL): {sql[:500]}...")
        logger.info("=" * 60)
        return sql

        
    def _clean_sql(self, text):
        if not text:
            return ""
            
        # Remove <think>...</think> blocks if present
        if "<think>" in text:
            if "</think>" in text:
                text = text.split("</think>")[-1].strip()
            else:
                text = "" # It's all just thinking without actual output
                
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "select" in part.lower() and "from" in part.lower():
                     text = part
                     break
            if text.lower().startswith("sql"):
                text = text[3:]
            elif text.lower().startswith("mysql"):
                text = text[5:]
        
        return text.strip()