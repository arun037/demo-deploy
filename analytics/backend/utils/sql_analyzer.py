"""
SQL Analysis Utilities
Provides functions to analyze SQL queries for chart generation decisions.
"""

import re
from typing import List, Tuple, Optional


def is_aggregated_query(sql: str) -> bool:
    """
    Check if SQL query is aggregated (has GROUP BY or aggregate functions).
    
    Args:
        sql: SQL query string
        
    Returns:
        True if query is aggregated, False otherwise
    """
    sql_upper = sql.upper()
    
    # Check for GROUP BY clause
    has_group_by = "GROUP BY" in sql_upper
    
    # Check for aggregate functions
    aggregate_funcs = ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'GROUP_CONCAT(']
    has_aggregate_funcs = any(func in sql_upper for func in aggregate_funcs)
    
    return has_group_by or has_aggregate_funcs


def extract_group_by_columns(sql: str) -> List[str]:
    """
    Extract column names from GROUP BY clause.
    
    Args:
        sql: SQL query string
        
    Returns:
        List of column names in GROUP BY clause
    """
    # Find GROUP BY clause - stop at ORDER BY, HAVING, LIMIT, or end
    # Use non-greedy match and lookahead
    pattern = r'GROUP\s+BY\s+(.+?)(?:\s+ORDER\s+BY|\s+HAVING|\s+LIMIT|;|\s*$)'
    match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
    
    if not match:
        return []
    
    group_by_clause = match.group(1).strip()
    
    # Split by comma and clean up
    columns = []
    for col in group_by_clause.split(','):
        col = col.strip()
        # Remove table aliases (e.g., "t.column" -> "column")
        if '.' in col:
            col = col.split('.')[-1]
        # Remove any trailing whitespace or newlines
        col = col.split()[0] if col else ''
        if col:
            columns.append(col.lower())
    
    return columns


def is_metric_column(col_name: str) -> bool:
    """
    Determine if a column is a meaningful metric (not an ID or identifier).
    Uses generic pattern matching  no domain-specific hardcoding.
    
    Args:
        col_name: Column name to check
        
    Returns:
        True if column is a metric, False if it's an ID/identifier
    """
    col_lower = col_name.lower()
    
    # Generic identifier detection  works for any domain.
    # Pattern: ends with '_id', '_key', '_code', or is exactly 'id'.
    if col_lower == 'id':
        return False
    if col_lower.endswith('_id'):
        return False
    if col_lower.endswith('_key'):
        return False
    if col_lower.endswith('_code'):
        return False
    
    # Include actual metrics
    metric_keywords = [
        'count', 'total', 'sum', 'avg', 'average', 'mean',
        'leads', 'revenue', 'amount', 'price', 'cost', 'value',
        'quantity', 'qty', 'number', 'rate', 'percent', 'score',
        'days', 'hours', 'minutes', 'balance', 'budget', 'profit',
        'loss', 'margin', 'growth', 'change', 'delta'
    ]
    
    return any(keyword in col_lower for keyword in metric_keywords)


def is_date_column(col_name: str) -> bool:
    """
    Check if a column name suggests it contains date/time data.
    
    Args:
        col_name: Column name to check
        
    Returns:
        True if column appears to be a date/time column
    """
    col_lower = col_name.lower()
    date_keywords = [
        'date', 'time', 'timestamp', 'created_at', 'updated_at',
        'year', 'month', 'day', 'period', 'quarter', 'week',
        'last_update', 'create_date', 'start_date', 'end_date',
        'lead_date', 'activation_date', 'deactivate_date'
    ]
    
    return any(keyword in col_lower for keyword in date_keywords)


def should_create_time_series_chart(sql: str, date_columns: List[str]) -> Tuple[bool, str]:
    """
    Determine if data warrants a time series chart based on SQL analysis.
    
    Args:
        sql: SQL query string
        date_columns: List of date column names in the result
        
    Returns:
        Tuple of (should_create, reason)
    """
    # 1. Check if query is aggregated
    if not is_aggregated_query(sql):
        return False, "Query returns raw data without aggregation - time series not meaningful"
    
    # 2. Extract GROUP BY columns
    group_by_cols = extract_group_by_columns(sql)
    
    if not group_by_cols:
        return False, "No GROUP BY clause found despite aggregate functions"
    
    # 3. Check if grouping by a date/time column
    grouped_by_date = any(
        col in group_by_cols 
        for col in date_columns 
        if is_date_column(col)
    )
    
    if not grouped_by_date:
        return False, f"Grouping by {', '.join(group_by_cols)} (categorical, not temporal)"
    
    return True, "Query groups by date/time column - valid time series"


def get_valid_metric_columns(columns: List[str], exclude_ids: bool = True) -> List[str]:
    """
    Filter columns to only include valid metrics (exclude IDs if requested).
    
    Args:
        columns: List of column names
        exclude_ids: If True, exclude ID columns
        
    Returns:
        List of valid metric column names
    """
    if not exclude_ids:
        return columns
    
    return [col for col in columns if is_metric_column(col)]
