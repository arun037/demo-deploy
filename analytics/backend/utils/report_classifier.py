from enum import Enum
from typing import Dict, Any
import pandas as pd
import re

class ReportType(str, Enum):
    NON_REPORT = "NON_REPORT"
    STRONG_REPORT = "STRONG_REPORT"

def classify_report_result(
    df: pd.DataFrame,
    metadata: Dict
) -> ReportType:
    """
    Classifies a SQL result into NON_REPORT or STRONG_REPORT
    based purely on result shape and query structure.

    Parameters:
    - df: Pandas DataFrame returned from SQL execution
    - metadata: dict containing query characteristics

    Expected metadata keys:
    - has_time_dimension (bool)
    - has_group_by (bool)
    - has_aggregations (bool)
    - is_entity_list (bool)  # PO list, item list, requisition list
    """

    row_count = len(df)
    
    # -------------------------
    # 1. NON-REPORT
    # -------------------------
    # Single value answers, single-row summaries, or small result sets
    # without time/grouping dimensions
    if row_count <= 1 and not metadata.get("has_group_by", False) and not metadata.get("is_entity_list", False):
        return ReportType.NON_REPORT
    
    # Small aggregated results without time dimension or grouping
    if (
        row_count <= 20 and
        not metadata.get("has_time_dimension", False) and
        not metadata.get("has_group_by", False) and
        not metadata.get("is_entity_list", False)
    ):
        return ReportType.NON_REPORT

    # -------------------------
    # 2. STRONG REPORT
    # -------------------------
    # Anything users may revisit, filter, paginate, or trend
    if (
        row_count > 20 or
        metadata.get("has_time_dimension", False) or
        metadata.get("has_group_by", False) or
        metadata.get("is_entity_list", False)
    ):
        return ReportType.STRONG_REPORT

    # -------------------------
    # Safety fallback (conservative)
    # -------------------------
    return ReportType.NON_REPORT

def extract_metadata(df: pd.DataFrame, sql_query: str, intent: str) -> Dict[str, Any]:
    """
    Extracts metadata from the DataFrame and SQL query to feed into the classifier.
    
    Args:
        df: The result DataFrame.
        sql_query: The executed SQL query.
        intent: The classified user intent.
        
    Returns:
        Dict with keys: has_time_dimension, has_group_by, has_aggregations, is_entity_list
    """
    sql_upper = sql_query.upper()
    
    # 1. Time Dimension
    # Check for datetime columns in DataFrame
    has_time_dimension = False
    if not df.empty:
        # Check dtypes for datetime
        date_cols = df.select_dtypes(include=['datetime', 'datetimetz']).columns
        if len(date_cols) > 0:
            has_time_dimension = True
        else:
            # Fallback: Check if any column name looks like a date/time (e.g., 'year', 'month', 'date')
            # and contents look like time (heuristic)
            for col in df.columns:
                col_lower = col.lower()
                if 'date' in col_lower or 'time' in col_lower or 'year' in col_lower or 'month' in col_lower or 'period' in col_lower:
                    # Very basic check, relying mostly on dtypes is safer but string dates exist
                    has_time_dimension = True
                    break

    # 2. Group By
    has_group_by = "GROUP BY" in sql_upper

    # 3. Aggregations
    # Check for aggregate keywords in SQL
    agg_keywords = ["SUM(", "COUNT(", "AVG(", "MIN(", "MAX("]
    has_aggregations = any(k in sql_upper for k in agg_keywords)
    
    # Also trust intent if it says AGGREGATION
    if intent == "AGGREGATION":
        has_aggregations = True

    # 4. Entity List
    # LIST, DETAIL_RETRIEVAL intents usually imply lists
    is_entity_list = intent in ["DETAIL_RETRIEVAL", "LIST"]
    
    # If explicit 'LIMIT' is high or missing (default), and no agg, it might be a list
    # But usually intent is the best proxy here.
    
    return {
        "has_time_dimension": has_time_dimension,
        "has_group_by": has_group_by,
        "has_aggregations": has_aggregations,
        "is_entity_list": is_entity_list
    }
