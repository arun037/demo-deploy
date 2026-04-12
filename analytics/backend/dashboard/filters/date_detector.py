"""
Date Column Detector - AI-Powered Date Detection

Uses LLM to analyze SQL queries and detect date columns.
"""

import json
import re
from typing import Dict, Any, Optional
from backend.core.logger import logger


class DateColumnDetector:
    """AI-powered date column detection in SQL queries"""
    
    def __init__(self, llm_client, schema_json):
        self.llm = llm_client
        self.schema_json = schema_json
        
        # Build quick lookup for date columns
        self.date_columns_cache = self._build_date_columns_cache()
    
    def _build_date_columns_cache(self) -> Dict[str, list]:
        """Build cache of date columns per table from schema"""
        cache = {}
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            date_cols = []
            
            for col in table.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "").lower()
                col_desc = col.get("description", "").lower()
                
                # Detect date columns by name, type, or description
                if any(keyword in col_name.lower() for keyword in ['date', 'time', 'created', 'updated', 'modified']):
                    date_cols.append({
                        "name": col_name,
                        "type": col_type,
                        "format": self._guess_format(col_type)
                    })
                elif 'date' in col_type or 'time' in col_type:
                    date_cols.append({
                        "name": col_name,
                        "type": col_type,
                        "format": self._guess_format(col_type)
                    })
            
            if date_cols:
                # Store with unqualified name
                cache[table_name] = date_cols
                
                # Also store with database-qualified name
                if database_name:
                    qualified_name = f"{database_name}.{table_name}"
                    cache[qualified_name] = date_cols
        
        return cache
    
    def _guess_format(self, col_type: str) -> str:
        """Guess MySQL date format based on column type"""
        col_type = col_type.lower()
        
        if 'date' in col_type and 'time' not in col_type:
            return "%Y-%m-%d"
        elif 'datetime' in col_type or 'timestamp' in col_type:
            return "%Y-%m-%d %H:%i:%s"
        elif 'varchar' in col_type or 'char' in col_type:
            # Common format in this schema
            return "%d/%m/%y"
        else:
            return "%Y-%m-%d"
    
    def detect(self, sql: str, insight_id: str) -> Optional[Dict[str, Any]]:
        """
        Detect date column in SQL query
        
        Returns:
        {
            "table": "crmc_po_hdr",
            "date_column": "PO_Date",
            "date_format": "%d/%m/%y",
            "needs_conversion": true
        }
        """
        try:
            # Extract table name from SQL
            table_name = self._extract_table_name(sql)
            
            if not table_name:
                logger.warning(f"Could not extract table name from SQL: {sql[:100]}")
                return None
            
            # Check cache first
            if table_name in self.date_columns_cache:
                date_cols = self.date_columns_cache[table_name]
                
                if date_cols:
                    # Use first date column found
                    primary_date = date_cols[0]
                    
                    return {
                        "table": table_name,
                        "date_column": primary_date["name"],
                        "date_format": primary_date["format"],
                        "needs_conversion": "varchar" in primary_date["type"].lower() or "char" in primary_date["type"].lower()
                    }
            
            logger.warning(f"No date columns found for table: {table_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting date column: {e}")
            return None
    
    def _extract_table_name(self, sql: str) -> Optional[str]:
        """Extract main table name from SQL query (handles database.table format)"""
        sql_upper = sql.upper()
        
        # Pattern: FROM database.table_name OR FROM table_name
        match = re.search(r'FROM\s+(?:([a-zA-Z0-9_]+)\.)?([a-zA-Z0-9_]+)', sql_upper)
        if match:
            database = match.group(1)
            table = match.group(2)
            if database:
                # Return database-qualified name
                return f"{database.lower()}.{table.lower()}"
            return table.lower()
        
        # Pattern: UPDATE database.table_name OR UPDATE table_name
        match = re.search(r'UPDATE\s+(?:([a-zA-Z0-9_]+)\.)?([a-zA-Z0-9_]+)', sql_upper)
        if match:
            database = match.group(1)
            table = match.group(2)
            if database:
                return f"{database.lower()}.{table.lower()}"
            return table.lower()
        
        return None
    
    def get_date_columns_for_table(self, table_name: str) -> list:
        """Get all date columns for a specific table"""
        return self.date_columns_cache.get(table_name, [])
