"""
Autonomous Query Generator
Generates supplementary SQL queries to enrich visualizations.
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from backend.core.llm_client import LLMClient
from backend.core.logger import logger
from backend.config import Config


class QueryAugmenter:
    """
    Generates additional SQL queries autonomously to provide richer visualizations.
    Example: If main query returns aggregated totals, generate time-series query for trends.
    """
    
    def __init__(self, llm_client: LLMClient, db_manager):
        self.llm = llm_client
        self.db = db_manager
    
    def should_augment(self, user_query: str, current_df: pd.DataFrame, analysis: Dict[str, Any]) -> bool:
        """
        Decide if supplementary queries would enhance visualization.
        
        Args:
            user_query: Original user query
            current_df: Current query results
            analysis: Data analysis from ChartSelector
        
        Returns:
            bool: True if augmentation recommended
        """
        # Don't augment if we already have rich data
        if len(current_df) > 20 and analysis.get('has_time_dimension'):
            logger.info("QueryAugmenter: Data already rich, no augmentation needed")
            return False
        
        # Don't augment single-value results (KPIs are fine as-is)
        if len(current_df) == 1:
            logger.info("QueryAugmenter: Single value result, no augmentation needed")
            return False
        
        # Augment if we have aggregated data but no time dimension
        if not analysis.get('has_time_dimension') and len(current_df) < 10:
            logger.info("QueryAugmenter: Aggregated data without time series - augmentation recommended")
            return True
        
        return False
    
    def generate_supplementary_queries(
        self, 
        user_query: str, 
        original_sql: str,
        current_df: pd.DataFrame,
        schema_context: str,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate supplementary SQL queries for richer visualizations.
        
        Returns:
            List of dicts with keys:
            - query_type: str (e.g., 'time_series', 'breakdown')
            - sql: str
            - purpose: str
        """
        supplementary_queries = []
        
        # Strategy 1: Add time-series if missing
        if not analysis.get('has_time_dimension'):
            time_series_sql = self._generate_time_series_query(
                user_query, original_sql, schema_context
            )
            if time_series_sql:
                supplementary_queries.append({
                    'query_type': 'time_series',
                    'sql': time_series_sql,
                    'purpose': 'Show trend over time'
                })
        
        # Strategy 2: Add categorical breakdown if we only have totals
        if len(current_df) == 1 and analysis.get('has_numeric_metrics'):
            breakdown_sql = self._generate_breakdown_query(
                user_query, original_sql, schema_context
            )
            if breakdown_sql:
                supplementary_queries.append({
                    'query_type': 'categorical_breakdown',
                    'sql': breakdown_sql,
                    'purpose': 'Show breakdown by category'
                })
        
        logger.info(f"QueryAugmenter: Generated {len(supplementary_queries)} supplementary queries")
        return supplementary_queries
    
    def _generate_time_series_query(
        self, 
        user_query: str, 
        original_sql: str, 
        schema_context: str
    ) -> Optional[str]:
        """
        Generate a time-series query based on the original query.
        Uses LLM to understand intent and create appropriate GROUP BY date query.
        """
        prompt = f"""You are a SQL expert. Generate a time-series query based on the user's request.

User Query: "{user_query}"
Original SQL: {original_sql}

Schema Context:
{schema_context[:2000]}

Task: Create a NEW SQL query that shows the SAME metric(s) but grouped by time period (month/week/day).

Rules:
1. Identify date columns in the schema (look for CREATED_DATE, ORDER_DATE, etc.)
2. Use DATE_TRUNC or similar to group by appropriate time period
3. Keep the same metric calculations (SUM, COUNT, etc.)
4. Order by date ascending
5. Limit to last 12 periods (months/weeks)

Output ONLY the SQL query, no explanations.
"""
        
        try:
            response = self.llm.call_agent(
                prompt, 
                user_query, 
                model=Config.INSIGHT_MODEL,
                timeout=30,
                agent_name="QueryAugmenter"
            )
            
            # Clean response
            sql = response.strip()
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            # Basic validation
            if "SELECT" in sql.upper() and "FROM" in sql.upper():
                logger.info("QueryAugmenter: Generated time-series query")
                return sql
            else:
                logger.warning("QueryAugmenter: Invalid time-series query generated")
                return None
                
        except Exception as e:
            logger.error(f"QueryAugmenter: Error generating time-series query: {e}")
            return None
    
    def _generate_breakdown_query(
        self, 
        user_query: str, 
        original_sql: str, 
        schema_context: str
    ) -> Optional[str]:
        """
        Generate a categorical breakdown query.
        Example: If query returns "Total Spend: $100K", generate "Spend by Vendor"
        """
        prompt = f"""You are a SQL expert. Generate a categorical breakdown query based on the user's request.

User Query: "{user_query}"
Original SQL: {original_sql}

Schema Context:
{schema_context[:2000]}

Task: Create a NEW SQL query that shows the SAME metric(s) but grouped by a meaningful category.

Rules:
1. Identify categorical columns (VENDOR_NAME, ITEM_CATEGORY, LOCATION, etc.)
2. Use GROUP BY to break down the metric
3. Keep the same metric calculations (SUM, COUNT, etc.)
4. Order by metric descending
5. Limit to top 10-15 categories

Output ONLY the SQL query, no explanations.
"""
        
        try:
            response = self.llm.call_agent(
                prompt, 
                user_query, 
                model=Config.INSIGHT_MODEL,
                timeout=30,
                agent_name="QueryAugmenter"
            )
            
            # Clean response
            sql = response.strip()
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            # Basic validation
            if "SELECT" in sql.upper() and "GROUP BY" in sql.upper():
                logger.info("QueryAugmenter: Generated breakdown query")
                return sql
            else:
                logger.warning("QueryAugmenter: Invalid breakdown query generated")
                return None
                
        except Exception as e:
            logger.error(f"QueryAugmenter: Error generating breakdown query: {e}")
            return None
    
    def execute_supplementary_queries(
        self, 
        queries: List[Dict[str, Any]]
    ) -> Dict[str, pd.DataFrame]:
        """
        Execute supplementary queries and return results.
        
        Returns:
            Dict mapping query_type to DataFrame
        """
        results = {}
        
        for query_spec in queries:
            query_type = query_spec['query_type']
            sql = query_spec['sql']
            
            try:
                logger.info(f"QueryAugmenter: Executing {query_type} query...")
                df = self.db.execute_query_safe(sql)
                
                if df is not None and not df.empty:
                    results[query_type] = df
                    logger.info(f"QueryAugmenter: {query_type} query returned {len(df)} rows")
                else:
                    logger.warning(f"QueryAugmenter: {query_type} query returned no data")
                    
            except Exception as e:
                logger.error(f"QueryAugmenter: Error executing {query_type} query: {e}")
        
        return results
