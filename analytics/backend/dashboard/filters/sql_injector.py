"""
SQL Filter Injector - Dynamic SQL Filter Injection

Intelligently injects date filters into SQL queries.
"""

import re
from typing import Dict, Any
from backend.core.logger import logger


class SQLFilterInjector:
    """Intelligently injects date filters into SQL queries"""
    
    def inject_filter(self, sql: str, date_info: Dict[str, Any], date_range: Dict[str, Any]) -> str:
        """
        Inject WHERE clause with date filter
        
        Handles:
        - Queries with no WHERE clause
        - Queries with existing WHERE clause
        - Queries with GROUP BY, ORDER BY, LIMIT
        - CTEs (WITH statements)
        """
        if not date_info or not date_range:
            return sql
        
        try:
            # Build filter clause
            filter_clause = self._build_filter_clause(date_info, date_range)
            
            # Inject into SQL
            filtered_sql = self._inject_clause(sql, filter_clause)
            
            logger.info(f"Injected filter: {filter_clause[:100]}")
            return filtered_sql
            
        except Exception as e:
            logger.error(f"Error injecting filter: {e}")
            return sql  # Return original if injection fails
    
    def _build_filter_clause(self, date_info: Dict[str, Any], date_range: Dict[str, Any]) -> str:
        """Build the WHERE filter clause"""
        date_col = date_info["date_column"]
        date_format = date_info["date_format"]
        needs_conversion = date_info["needs_conversion"]
        
        start_date = date_range["start"]
        end_date = date_range["end"]
        
        if needs_conversion:
            # Need STR_TO_DATE for varchar/char columns
            filter_clause = f"""STR_TO_DATE({date_col}, '{date_format}') >= '{start_date}' 
                              AND STR_TO_DATE({date_col}, '{date_format}') <= '{end_date}'"""
        else:
            # Direct comparison for DATE/DATETIME columns
            filter_clause = f"""{date_col} >= '{start_date}' 
                              AND {date_col} <= '{end_date}'"""
        
        return filter_clause.strip()
    
    def _inject_clause(self, sql: str, filter_clause: str) -> str:
        """Inject filter clause into SQL"""
        sql_upper = sql.upper()
        
        # Check if WHERE already exists
        if "WHERE" in sql_upper:
            # Add to existing WHERE with AND
            # Find WHERE position
            where_pos = sql_upper.find("WHERE")
            
            # Insert after WHERE
            before_where = sql[:where_pos + 5]  # Include "WHERE"
            after_where = sql[where_pos + 5:]
            
            # Inject with AND
            return f"{before_where} ({filter_clause}) AND {after_where}"
        else:
            # Add new WHERE clause
            # Find insertion point (before GROUP BY, ORDER BY, LIMIT, or end)
            insertion_point = self._find_insertion_point(sql)
            
            before = sql[:insertion_point].rstrip()
            after = sql[insertion_point:]
            
            return f"{before} WHERE {filter_clause} {after}"
    
    def _find_insertion_point(self, sql: str) -> int:
        """Find where to insert WHERE clause"""
        sql_upper = sql.upper()
        
        # Look for GROUP BY, ORDER BY, LIMIT
        keywords = ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"]
        
        earliest_pos = len(sql)
        
        for keyword in keywords:
            pos = sql_upper.find(keyword)
            if pos != -1 and pos < earliest_pos:
                earliest_pos = pos
        
        return earliest_pos
    
    def can_inject(self, sql: str) -> bool:
        """Check if SQL can have a filter injected"""
        sql_upper = sql.upper()
        
        # Can't inject into CTEs (WITH statements) - too complex
        if sql_upper.strip().startswith("WITH"):
            return False
        
        # Must be a SELECT query
        if not sql_upper.strip().startswith("SELECT"):
            return False
        
        return True
