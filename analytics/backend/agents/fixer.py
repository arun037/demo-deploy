from backend.core.llm_client import LLMClient
from backend.config import Config

class Fixer:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def fix_sql(self, original_query, plan, schema_context, error_message, previous_sql):
        system_prompt = f"""You are a Database Expert fixing invalid SQL queries.

Context:
- Schema: {schema_context}
- Original Plan: {plan}
- User Question: {original_query}

Failed SQL:
{previous_sql}

Error Message:
{error_message}

CRITICAL ERROR ANALYSIS:
1. If error is "Unknown column 'X'", check the schema's "AVAILABLE COLUMNS" section
2. The column 'X' does NOT exist - do not retry with the same column name
3. Look for similar columns in the schema (e.g., if CONTRACT_DATE missing, look for other date columns)
4. If no similar column exists in that table, use a different table or approach

FIXING STRATEGY:
- For "Unknown column" errors: Find the correct column name from schema or use alternative table
- PRESERVE TABLE QUALIFICATION: Use `database.table` as shown in SCHEMA. Do not assume default database.
- For syntax errors: Fix the SQL syntax
- For join errors: Verify foreign key relationships in schema
- For "Illegal mix of collations" (Error 1267): Add `COLLATE utf8mb4_unicode_ci` to the string comparison.
  - Fix: `ON t1.col COLLATE utf8mb4_unicode_ci = t2.col COLLATE utf8mb4_unicode_ci`
- STRING MATCHING RULES:
  - NEVER change a user's search string to match an example value in the schema. Use their exact string.
  - ALWAYS use case-insensitive, space-tolerant regex for names/text searches: `(LOWER(col) = LOWER('User String') OR REGEXP_REPLACE(LOWER(col), '[^a-z0-9]', '') REGEXP 'userstring' OR LOWER(col) LIKE '%user string%')`
- KEEP IT SIMPLE: Maximum 60 lines of SQL

Goal:
Output the CORRECTED SQL query ONLY.
"""
        from backend.core.logger import logger
        
        logger.info("=" * 60)
        logger.info("FIXER INPUT:")
        logger.info(f"User Query: {original_query}")
        logger.info(f"Failed SQL: {previous_sql[:500]}...")
        logger.info(f"Error Message: {error_message}")
        
        response = self.llm.call_agent(system_prompt, "Fix the SQL code.", model=Config.FIXER_MODEL, timeout=120, agent_name="Fixer")
        
        if "<think>" in response:
            think_content = response.split("</think>")[0].split("<think>")[1] if "<think>" in response else ""
            logger.info(f"FIXER THINKING: {think_content[:300]}...")
        
        cleaned_sql = self._clean_sql(response)
        logger.info(f"FIXER OUTPUT (Corrected SQL): {cleaned_sql[:500]}...")
        logger.info("=" * 60)
        
        # Helper to clean markdown just in case (same as Synthesizer)
        return cleaned_sql
        
    def _clean_sql(self, text):
        # Remove <think>...</think> blocks if present
        if "<think>" in text and "</think>" in text:
            text = text.split("</think>")[-1].strip()
        
        # Remove markdown code blocks
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
