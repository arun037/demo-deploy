from backend.core.database import DatabaseManager
from backend.core.logger import logger
import pandas as pd

class Validator:
    """SQL validation using MySQL EXPLAIN and Pattern Checks"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def validate(self, sql):
        """
        Validate SQL syntax (Pre-execution)
        Returns: (is_valid, error_message)
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query"
        return self.db.validate_sql(sql)

    def validate_results(self, results_df: pd.DataFrame, user_query: str, sql_query: str):
        """
        Validate execution results (Post-execution)
        Checks for duplication, empty results that differ from expectations, etc.
        Returns: (is_valid, issue_description, suggested_fix)
        """
        # Check for suspicious patterns (All NULLs)
        suspicious = self._check_suspicious_patterns(results_df, sql_query)
        if suspicious:
            return False, suspicious, None

        # Check for excessive duplicates
        duplicate_issue = self._check_duplicate_patterns(results_df, user_query, sql_query)
        if duplicate_issue:
            return False, duplicate_issue[0], duplicate_issue[1]
            
        return True, None, None

    def _check_duplicate_patterns(self, results_df, user_query, sql_query):
        """
        Check for excessive duplicate rows that suggest missing GROUP BY.
        Returns (issue_description, suggested_fix) or None
        """
        if results_df.empty or len(results_df) < 10:
            return None
        
        # Check for high duplicate rate
        total_rows = len(results_df)
        duplicates = results_df.duplicated()
        duplicate_count = duplicates.sum()
        duplicate_rate = duplicate_count / total_rows if total_rows > 0 else 0
        
        # Detect aggregation intent using a broad regex:
        # Matches any "by <noun>" phrase (e.g., "by department", "by vendor", "by category")
        # plus the original fixed list for backwards compatibility.
        import re
        query_lower = user_query.lower()
        
        # Regex: 'by' followed by one or two words (catches 'by department', 'by product type')
        has_by_grouping = bool(re.search(r'\bby\s+[a-z]+(?:\s+[a-z]+)?\b', query_lower))
        
        fixed_phrases = [
            "group by", "list all", "all items", "each item",
            "per item", "variance by", "breakdown", "split by",
            "aggregate", "summarize", "summarise"
        ]
        suggests_aggregation = has_by_grouping or any(phrase in query_lower for phrase in fixed_phrases)
        
        # Check if SQL has GROUP BY
        has_group_by = "GROUP BY" in sql_query.upper()
        
        # Condition: High duplicate rate + Aggregation Intent + No Group By
        if duplicate_rate > 0.3 and suggests_aggregation and not has_group_by:
            grouping_col = self._identify_grouping_column(results_df, user_query)
            
            issue = f"High duplicate rate detected ({duplicate_rate:.1%}). Query returns {total_rows} rows with many duplicates. "
            issue += f"User query suggests aggregation, but query doesn't use GROUP BY. "
            issue += f"Consider grouping by {grouping_col} to show unique items with aggregated metrics."
            
            fix = self._suggest_aggregation_fix(sql_query, grouping_col, user_query)
            return (issue, fix)
        
        return None

    def _identify_grouping_column(self, results_df, user_query):
        """Identify the column that should be used for GROUP BY."""
        query_lower = user_query.lower()
        
        # Explicit mentions
        if "by items" in query_lower or "by item" in query_lower:
            for col in results_df.columns:
                if 'item' in col.lower() and 'id' in col.lower():
                    return col
        
        if "by vendor" in query_lower:
            for col in results_df.columns:
                if 'vendor' in col.lower() and 'id' in col.lower():
                    return col

        # Default: first ID column
        for col in results_df.columns:
            if 'id' in col.lower():
                return col
        
        return results_df.columns[0] if len(results_df.columns) > 0 else "id"

    def _suggest_aggregation_fix(self, sql_query, grouping_col, user_query):
        suggestion = f"""
Consider modifying the query to use GROUP BY for aggregation:

1. Add GROUP BY {grouping_col}
2. Use aggregate functions for metrics:
   - MIN(), MAX(), AVG() for numeric columns
   - COUNT() for counting
   - SUM() for totals
"""
        return suggestion

    def _check_suspicious_patterns(self, results_df, sql_query):
        """Check for suspicious patterns in results."""
        # Check for all NULL results
        if not results_df.empty:
            # Check if all values in key columns are NULL
            non_id_cols = [col for col in results_df.columns if 'id' not in col.lower()]
            if non_id_cols:
                null_counts = results_df[non_id_cols].isnull().sum()
                if null_counts.sum() == len(results_df) * len(non_id_cols):
                    return "All result values are NULL - possible join or column mismatch"
            
            # Check for NULL values in key ID columns (data quality issue)
            id_cols = [col for col in results_df.columns if 'id' in col.lower()]
            for col in id_cols:
                null_count = results_df[col].isnull().sum()
                if null_count > 0:
                    null_rate = null_count / len(results_df)
                    if null_rate > 0.1:  # More than 10% NULLs
                        return f"High NULL rate ({null_rate:.1%}) in {col} column. Consider filtering WHERE {col} IS NOT NULL to exclude invalid data."
        
        return None
