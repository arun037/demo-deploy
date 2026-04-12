from backend.core.llm_client import LLMClient
from backend.core.logger import logger
from backend.config import Config
import re

class Router:
    """Fast intent classification using keyword matching"""
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client
    
    def classify_request_type(self, user_query, chat_history=[]):
        """
        Classify if the request is a DATA query (needs SQL) or CHAT (conversational).
        Uses LLM for context-aware decision.
        """
        try:
            # ── Fast pre-LLM guard ───────────────────────────────────────────
            # If the query starts with a clear data-retrieval imperative verb,
            # classify as DATA immediately without hitting the LLM.
            # This prevents misclassification when the router model times out
            # or when words like "Name" are misread as greetings.
            _q = user_query.strip().lower()
            _data_imperatives = (
                'name ', 'list ', 'show ', 'find ', 'get ', 'give me',
                'fetch ', 'display ', 'pull ', 'retrieve ', 'count ',
                'how many', 'what are', 'what is', "what's", 'which ', 'tell me the',
                'can i', 'could i', 'i need', 'i want', 'would you'
            )
            if any(_q.startswith(imp) for imp in _data_imperatives):
                logger.info(f"Router Gating (fast-path): '{user_query}' -> DATA (imperative keyword match)")
                return "DATA"
            # ────────────────────────────────────────────────────────────────
            # Load business context so the LLM knows what domain is in scope
            from backend.utils.business_context_loader import BusinessContextLoader
            business_context = BusinessContextLoader.load_context()
            
            # Build conversation context if available
            conversation_context = ""
            if chat_history and len(chat_history) > 0:
                conversation_context = "\n\nPREVIOUS CONVERSATION:\n"
                for msg in chat_history[-2:]:  # Last 2 messages for context
                    conversation_context += f"{msg['role'].upper()}: {msg['content']}\n"
                conversation_context += "\nNOTE: If the new query is related to the previous conversation and asks for data/metrics/analysis, classify as DATA.\n"
            
            prompt = f"""You are a query router for a business analytics assistant.
Classify the User Query as EXACTLY "DATA" or "CHAT".

BUSINESS CONTEXT (describes what data exists in this system's database):
{business_context}

- DATA: The user is asking about something that exists in the business database above.
- CHAT: The user is greeting, chatting, asking about capabilities, or asking about anything NOT covered by the business database above.

Use the business context above to make your decision. Do not rely on hardcoded rules.
{conversation_context}
User Query: "{user_query}"

Return ONLY "DATA" or "CHAT"."""

            
            response = self.llm.call_agent(prompt, "Classify Request", model=Config.ROUTER_MODEL, temperature=0.1, agent_name="Router")
            
            # Clean response
            cleaned = response.strip().upper().replace("'", "").replace('"', "").replace(".", "")
            
            # Log for debugging
            logger.info(f"Router Gating: '{user_query}' -> Raw: '{response}' -> Cleaned: '{cleaned}'")
            
            if "CHAT" in cleaned and "DATA" not in cleaned:
                return "CHAT"
            return "DATA" # Default to DATA for safety
            
        except Exception as e:
            logger.error(f"Router gating error: {e}")
            return "DATA" # Fail safe

    def classify_intent(self, user_query, chat_history=[]):
        """
        Classify user query intent using LLM with conversation awareness.
        Returns: Intent string (AGGREGATION, DETAIL_RETRIEVAL, FOLLOW_UP, META_QUESTION, etc.)
        """
        query_lower = user_query.lower().strip()
        
        # QUICK WIN #2: Meta-Question Detection
        # Detect questions about previous results/errors that don't need new SQL
        # NOTE: Keywords must be specific enough to NOT match legitimate data queries
        # e.g., 'how many', 'how much' are data queries - NOT meta-questions
        meta_keywords = [
            'why is', 'why did', 'why does', 'why are', 'why was',
            'how come', 'how did that', 'how is it', 'how did this',
            'explain', 'what does this mean', 'what is this', 'tell me about this',
            'what happened', 'what went wrong', 'what caused'
        ]
        
        if any(keyword in query_lower for keyword in meta_keywords):
            # Check if there's previous context to explain
            if chat_history and len(chat_history) > 0:
                # Check if last message was from assistant (has results/error to explain)
                last_msg = chat_history[-1]
                if last_msg.get('role') == 'assistant':
                    logger.info(f"Meta-question detected: '{user_query}' - referring to previous result/error")
                    return {"intent": "META_QUESTION", "is_follow_up": True}
        
        # Context-aware intent classification (no special FOLLOW_UP handling)
        # Context-aware intent classification (no special FOLLOW_UP handling)
        # All queries are classified by what they want to achieve, not how they relate to previous
        if chat_history and len(chat_history) > 0:
            # Build conversation context for better understanding
            conversation_str = ""
            for msg in chat_history[-5:]:  # Last 5 messages for context
                conversation_str += f"{msg['role'].upper()}: {msg['content']}\n"
                if msg.get('sql'):
                    conversation_str += f"  - SQL: {msg['sql'][:150]}...\n"
            
            context_aware_prompt = f"""
You are classifying a user query based on WHAT they want to achieve.

CONVERSATION CONTEXT:
{conversation_str}

CURRENT QUERY: "{user_query}"

Classify the intent based on what the user wants:

- AGGREGATION: Sum, count, average, total, group by, aggregate metrics
- DETAIL_RETRIEVAL: List specific records, show details, get individual items
- RANKING: Top N, bottom N, highest, lowest, sorted lists
- METRIC_TREND: Time-based analysis, trends over time, growth, changes
- COMPARISON: Compare across dimensions, A vs B, differences

IMPORTANT:
- Focus on WHAT the user wants, not HOW it relates to previous queries
- Even if refining a previous query, classify by the actual intent
- Use conversation context to understand ambiguous queries

Also determine if this query is a FOLLOW UP to the previous conversation (e.g. "what about X", "sort it by Y", "only for last month", short queries that rely on previous context).

Return ONLY a valid JSON object in this exact format:
{{"intent": "ONE_OF_THE_ABOVE", "is_follow_up": true_or_false}}
"""
            
            try:
                import json
                response = self.llm.call_agent(context_aware_prompt, "Classify Intent", 
                                              model=Config.ROUTER_MODEL, temperature=0.1, 
                                              agent_name="Router")
                
                # Extract JSON block if surrounded by markdown
                cleaned = response.strip()
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned:
                    cleaned = cleaned.split("```")[1].strip()
                    
                parsed = json.loads(cleaned)
                intent = parsed.get("intent", "DETAIL_RETRIEVAL")
                is_follow_up = parsed.get("is_follow_up", False)
                
                # Map to valid intents
                intent_upper = intent.upper()
                if "AGGREGATION" in intent_upper:
                    intent = "AGGREGATION"
                elif "DETAIL" in intent_upper or "RETRIEVAL" in intent_upper:
                    intent = "DETAIL_RETRIEVAL"
                elif "RANKING" in intent_upper or "TOP" in intent_upper:
                    intent = "RANKING"
                elif "TREND" in intent_upper or "METRIC" in intent_upper:
                    intent = "METRIC_TREND"
                elif "COMPARISON" in intent_upper or "COMPARE" in intent_upper:
                    intent = "COMPARISON"
                else:
                    intent = "DETAIL_RETRIEVAL"
                
                logger.info(f"Context-aware classification: intent={intent}, is_follow_up={is_follow_up}")
                return {"intent": intent, "is_follow_up": is_follow_up}
                
            except Exception as e:
                logger.error(f"Context-aware classification error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Pattern-based fallback classification (if no history or LLM failed)
        intent = "DETAIL_RETRIEVAL"
        if any(kw in query_lower for kw in ['top', 'bottom', 'highest', 'lowest', 'rank', 'best', 'worst']):
            intent = "RANKING"
        elif any(kw in query_lower for kw in ['trend', 'over time', 'growth', 'change', 'increase', 'decrease', 'monthly', 'quarterly', 'yearly', 'daily', 'weekly', 'historical', 'timeline']):
            intent = "METRIC_TREND"
        elif any(kw in query_lower for kw in ['compare', 'vs', 'versus', 'difference', 'between', 'contrast']):
            intent = "COMPARISON"
        else:
            # AGGREGATION - Count, sum, average
            aggregation_keywords = ['total', 'count', 'sum', 'average', 'avg', 'how many', 'number of']
            if any(keyword in query_lower for keyword in aggregation_keywords):
                intent = "AGGREGATION"
            else:
                # DETAIL_RETRIEVAL - List or show specific items
                detail_keywords = ['list', 'show', 'display', 'get', 'find', 'search', 'what are', 'which']
                if any(keyword in query_lower for keyword in detail_keywords):
                    intent = "DETAIL_RETRIEVAL"
                else:
                    # Default to aggregation
                    intent = "AGGREGATION"
                    
        return {"intent": intent, "is_follow_up": False}
