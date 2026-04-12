"""
Follow-Up Handler Agent

Handles follow-up queries by rewriting existing SQL instead of regenerating from scratch.
Ensures continuity, correctness, and faster reasoning for conversational queries.
"""

from typing import Dict, Any, Tuple
from backend.core.llm_client import LLMClient
from backend.core.logger import logger
from backend.config import Config


class FollowUpHandler:
    """
    Intelligent follow-up query handler that rewrites SQL based on user feedback.
    Implements conversational intelligence by preserving original intent and structure.
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def detect_followup_type(self, user_query: str, previous_context: Dict[str, Any]) -> str:
        """
        Infer user intent from follow-up query.
        
        Args:
            user_query: User's follow-up question/instruction
            previous_context: Context from previous query (responseMeta)
            
        Returns:
            Follow-up type: CLARIFICATION, NARROWING, EXPANDING, CORRECTION, FILTER_ADD, FILTER_REMOVE
        """
        query_lower = user_query.lower().strip()
        
        # Clarification patterns - user is asking about previous results
        clarification_keywords = ['did this', 'does this', 'is this', 'was this', 'are these', 'were these']
        if any(keyword in query_lower for keyword in clarification_keywords):
            logger.info(f"Follow-up type: CLARIFICATION")
            return "CLARIFICATION"
        
        # Narrowing patterns - user wants to filter/restrict results
        narrowing_keywords = ['only', 'just', 'specific', 'particular']
        if any(keyword in query_lower for keyword in narrowing_keywords):
            logger.info(f"Follow-up type: NARROWING")
            return "NARROWING"
        
        # Expanding patterns - user wants to broaden scope
        expanding_keywords = ['all', 'everything', 'every', 'entire', 'full', 'complete']
        if any(keyword in query_lower for keyword in expanding_keywords):
            logger.info(f"Follow-up type: EXPANDING")
            return "EXPANDING"
        
        # Correction patterns - user wants to exclude or change something
        correction_keywords = ['exclude', 'remove', 'without', 'except', 'not']
        if any(keyword in query_lower for keyword in correction_keywords):
            logger.info(f"Follow-up type: CORRECTION")
            return "CORRECTION"
        
        # Default to FILTER_ADD
        logger.info(f"Follow-up type: FILTER_ADD (default)")
        return "FILTER_ADD"
    
    def rewrite_sql(
        self, 
        original_sql: str, 
        user_instruction: str, 
        followup_type: str, 
        schema_context: str,
        previous_intent: str = "UNKNOWN"
    ) -> str:
        """
        Rewrite SQL query based on user feedback while preserving original intent.
        
        Args:
            original_sql: The original SQL query
            user_instruction: User's follow-up instruction
            followup_type: Type of follow-up (from detect_followup_type)
            schema_context: Database schema context
            previous_intent: Original query intent
            
        Returns:
            Modified SQL query
        """
        logger.info(f"Rewriting SQL for follow-up type: {followup_type}")
        
        system_prompt = f"""You are modifying an existing SQL query based on user feedback.
DO NOT REGENERATE - ONLY MODIFY THE EXISTING QUERY.

ORIGINAL QUERY:
{original_sql}

ORIGINAL INTENT: {previous_intent}
(The rewritten query MUST preserve this intent)

USER FOLLOW-UP: "{user_instruction}"
FOLLOW-UP TYPE: {followup_type}

SCHEMA CONTEXT:
{schema_context[:2000]}

TASK: Modify the SQL to incorporate the user's feedback while preserving the original intent.

MODIFICATION RULES:
1. DO NOT regenerate - MODIFY the existing query
2. For NARROWING: Add WHERE clause or tighten existing conditions
3. For EXPANDING: Remove/relax WHERE conditions
4. For CORRECTION: Replace filter values or add exclusion conditions
5. For CLARIFICATION: Return the original SQL unchanged
6. For FILTER_ADD: Add new WHERE/HAVING condition
7. For FILTER_REMOVE: Remove specific WHERE/HAVING condition
8. Maintain JOIN structure unless explicitly requested
9. Preserve column selections unless user asks to change
10. Keep GROUP BY, ORDER BY, aggregations intact unless directly affected by feedback

ALL TEXT STRING MATCHING — CANONICAL NORMALIZATION (MANDATORY):
When adding or modifying a filter on ANY text/string column:
- **NAME / LABEL columns** (e.g. generic_name_col, generic_title_col): ALWAYS use `LIKE` for partial matching — the user may only say part of the stored name. Use: `LOWER(column) LIKE LOWER('%<user_word>%')`. Never use exact `=` for name columns.
- **STATUS / ENUM columns** (e.g. generic_status_col, generic_type_col): Use exact canonical match. Lowercase and strip non-alphanumeric from the user word, then: `REGEXP_REPLACE(LOWER(column), '[^a-z0-9]', '') = '<canonicalized_word>'`
- For multiple status values: `REGEXP_REPLACE(LOWER(column), '[^a-z0-9]', '') IN ('<word1>', '<word2>', ...)`
- NEVER pass raw user text directly into `=` or `IN()` for name columns — always use LIKE with lowercase wrapping.

CRITICAL: Output ONLY the modified SQL query. No explanations, no markdown, just the SQL.
"""
        
        try:
            response = self.llm.call_agent(
                system_prompt,
                user_instruction,
                model=Config.SYNTHESIZER_MODEL,
                timeout=120,
                agent_name="FollowUpHandler"
            )
            
            # Clean response
            modified_sql = self._clean_sql(response)
            
            logger.info(f"SQL rewritten successfully (length: {len(modified_sql)} chars)")
            return modified_sql
            
        except Exception as e:
            logger.error(f"Error rewriting SQL: {e}")
            # Fallback: return original SQL
            logger.warning("Returning original SQL as fallback")
            return original_sql
    
    def validate_rewrite(
        self, 
        original_sql: str, 
        rewritten_sql: str, 
        previous_intent: str
    ) -> Tuple[bool, str]:
        """
        Validate that the rewritten SQL maintains original intent and is syntactically valid.
        
        Args:
            original_sql: Original SQL query
            rewritten_sql: Rewritten SQL query
            previous_intent: Original query intent
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation checks
        rewritten_upper = rewritten_sql.upper()
        
        # Check 1: Must contain SELECT and FROM
        if "SELECT" not in rewritten_upper or "FROM" not in rewritten_upper:
            return False, "Rewritten SQL must contain SELECT and FROM clauses"
        
        # Check 2: Should not drastically change structure
        original_has_group_by = "GROUP BY" in original_sql.upper()
        rewritten_has_group_by = "GROUP BY" in rewritten_upper
        
        # If original had GROUP BY, rewritten should too (mostly)
        if original_has_group_by and not rewritten_has_group_by:
            logger.warning("GROUP BY removed in rewrite - may change query intent")
            # Don't fail, but log warning
        
        # Check 3: Verify no dangerous operations introduced
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
        for keyword in dangerous_keywords:
            if keyword in rewritten_upper:
                return False, f"Dangerous operation detected: {keyword}"
        
        logger.info("SQL rewrite validation passed")
        return True, ""
    
    def _clean_sql(self, text: str) -> str:
        """
        Clean LLM response to extract pure SQL.
        
        Args:
            text: Raw LLM response
            
        Returns:
            Cleaned SQL query
        """
        # Remove thinking blocks
        if "<think>" in text and "</think>" in text:
            text = text.split("</think>")[-1].strip()
        elif "<think>" in text:
            text = text.split("<think>")[0].strip()
        
        # Remove markdown code blocks
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "select" in part.lower() and "from" in part.lower():
                    text = part
                    break
            
            # Remove language identifier
            if text.lower().startswith("sql"):
                text = text[3:]
        
        return text.strip()
