from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4
from collections import Counter
import json
import os
import re
from backend.core.logger import logger
from backend.core.llm_client import LLMClient
from backend.config import Config

class Report:
    def __init__(
        self,
        title: str,
        base_sql: str,
        base_params: Dict[str, Any],
        detailed_summary: str,
        columns: List[str],
        created_by: str,
        classification: str,
        query: str = "",
        filter_schema: Optional[Dict[str, Any]] = None,
        chart_config: Optional[List[Dict[str, Any]]] = None,
        charts: Optional[List[Dict[str, Any]]] = None,  # NEW: Store full charts with data
        org_id: str = "default",
        row_count: Optional[int] = None,  # Store initial row count for display
        rows: Optional[List[Dict[str, Any]]] = None  # For backward compatibility only
    ):
        self.report_id = str(uuid4())
        self.title = title
        self.base_sql = base_sql
        self.base_params = base_params
        self.default_params = base_params.copy()  # Store original params for "Clear Filters"
        self.detailed_summary = detailed_summary
        self.columns = columns
        self.rows = rows  # Optional - only for legacy reports
        self.classification = classification
        self.created_by = created_by
        self.org_id = org_id
        self.created_at = datetime.utcnow().isoformat()
        self.row_count = row_count  # Store initial row count for display
        self.query = query
        self.filter_schema = filter_schema or infer_filter_schema(columns, base_sql)
        self.chart_config = chart_config or []  # Chart intent for regeneration
        self.charts = charts or []  # NEW: Full charts with data_override for direct use
        self.last_regenerated_at = None

    def to_dict(self):
        result = {
            "id": self.report_id,
            "title": self.title,
            "base_sql": self.base_sql,
            "base_params": self.base_params,
            "default_params": self.default_params,  # For filter reset
            "detailed_summary": self.detailed_summary,
            "columns": self.columns,
            "classification": self.classification,
            "created_by": self.created_by,
            "org_id": self.org_id,
            "createdAt": self.created_at,
            "query": self.query,
            "type": "comprehensive",
            "entity": "general",
            "filterSchema": self.filter_schema,
            "chart_config": self.chart_config,  # Chart intent for regeneration
            "charts": self.charts,  # NEW: Full charts with data for direct use
            "rowCount": self.row_count,  # Include row count for display
            "lastRegeneratedAt": self.last_regenerated_at
        }
        
        # Legacy support: include data if present (for old reports)
        if self.rows is not None:
            result["data"] = self.rows
            result["rowCount"] = len(self.rows)
            # Also include old field names for backward compatibility
            result["summary"] = self.detailed_summary
            # Use saved charts if available, otherwise fall back to chart_config
            if not result["charts"]:
                result["charts"] = self.chart_config
        
        return result

def infer_filter_schema(columns: List[str], sql: str, date_detector=None) -> Dict[str, Any]:
    """
    Infer filterable columns from column names and SQL.
    Returns a schema dict for frontend to render filters.
    
    Args:
        columns: List of column names
        sql: SQL query string
        date_detector: Optional DateFormatDetector instance for format detection
    """
    schema = {}
    
    # Extract table name from SQL for date format detection
    table_name = None
    table_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
    if table_match:
        table_name = table_match.group(1)
    
    # 1. Parse SQL WHERE clause for intelligent defaults
    # Extract WHERE clause
    where_match = re.search(r'WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    existing_conditions = {}
    
    if where_match:
        where_clause = where_match.group(1).strip()
        # Find simple conditions: col op val (matches = 'val' or LIKE '%val%')
        condition_pattern = r'([\w\.]+[\w\(\)]*)\s*(=|LIKE|>|<|>=|<=|IN)\s*(?:\'([^\']*)\'|([\d\.]+))'
        matches = re.finditer(condition_pattern, where_clause, re.IGNORECASE)
        
        for match in matches:
            col_expr = match.group(1)
            # Clean column name (remove table alias, UPPER, etc)
            clean_col = col_expr
            if '.' in clean_col:
                clean_col = clean_col.split('.')[-1]
            if '(' in clean_col:
                clean_col = clean_col.split('(')[-1].strip(')')
            
            val = match.group(3) or match.group(4)
            existing_conditions[clean_col.lower()] = val

    # 2. Mandatory Date Filter (check all columns)
    date_patterns = ['date', 'created_at', 'updated_at', 'po_date', 'accounting_dt', 'dttm', 'time', 'timestamp', 'year', 'month', 'period', 'day', 'last_update', 'published_at']
    for col in columns:
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in date_patterns) or col_lower.endswith('_at') or col_lower.endswith('_date'):
            # Detect date format if detector is available
            db_format = None
            display_format = 'dd/MM/yy'  # Default
            
            if date_detector and table_name:
                try:
                    db_format = date_detector.detect_format(table_name, col)
                    if db_format:
                        display_format = date_detector.get_display_format(db_format)
                        logger.info(f"Detected date format for {table_name}.{col}: {db_format} -> {display_format}")
                except Exception as e:
                    logger.warning(f"Failed to detect date format for {table_name}.{col}: {e}")
            
            schema[col] = {
                "type": "date",
                "column": col,
                "mandatory": True,
                "db_format": db_format,           # e.g., '%d/%m/%y' for SQL
                "display_format": display_format  # e.g., 'dd/MM/yy' for frontend
            }
    
    # 3. Enum/Category Filters (Status, Vendor, etc.)
    enum_patterns = ['status', 'vendor', 'department', 'location', 'category', 'buyer', 'type', 'group', 'uom', 'item_name', 'source', 'platform']
    for col in columns:
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in enum_patterns):
            # If detected in SQL, mark as active with default value
            active_val = existing_conditions.get(col_lower)
            schema[col] = {
                "type": "enum", 
                "column": col,
                "default": active_val if active_val else None
            }

    # 4. Numeric Range Filters (Price, Qty)
    numeric_patterns = ['price', 'cost', 'amount', 'quantity', 'qty', 'count', 'total', 'sum', 'number', 'score', 'rate', 'percent', 'balance', 'budget', 'leads', 'revenue', 'profit', 'days']
    for col in columns:
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in numeric_patterns) and col not in schema:
            schema[col] = {"type": "numeric", "column": col}
            
    # 5. Text Search (Description, Name)
    text_patterns = ['description', 'title', 'note', 'comment', 'name', 'details', 'summary']
    for col in columns:
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in text_patterns) and col not in schema:
            schema[col] = {"type": "text", "column": col}

    return schema

def _ensure_us_date_format(date_str: str) -> str:
    """
    Ensure date string is in US format (MM/DD/YYYY).
    Handles YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY formats.
    """
    if not date_str:
        return date_str
    
    date_str = str(date_str).strip()
    
    # Already in MM/DD/YYYY format
    if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
        parts = date_str.split('/')
        mm, dd, yyyy = parts[0], parts[1], parts[2]
        # Validate it's proper MM/DD (not DD/MM)
        if int(mm) <= 12 and int(dd) <= 31:
            return date_str
    
    # YYYY-MM-DD format (ISO)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        parts = date_str.split('-')
        yyyy, mm, dd = parts[0], parts[1], parts[2]
        return f"{mm}/{dd}/{yyyy}"
    
    # DD/MM/YYYY format - convert to MM/DD/YYYY
    if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
        parts = date_str.split('/')
        dd, mm, yyyy = parts[0], parts[1], parts[2]
        # Check if this is actually DD/MM by looking for day > 12
        if int(dd) > 12:
            return f"{mm}/{dd}/{yyyy}"
        elif int(mm) > 12:
            # Was already MM/DD
            return date_str
    
    # Default - assume already correct
    return date_str

def _escape_sql_string(value: str) -> str:
    """
    Escape special characters in SQL string literals (MySQL-specific).
    
    [WARN] SECURITY NOTE: This is a temporary mitigation, not a complete solution.
    TODO: Replace with parameterized queries for production-grade security.
    
    Args:
        value: Raw string value from user input
        
    Returns:
        Escaped string safe for SQL interpolation
    """
    if not isinstance(value, str):
        value = str(value)
    
    # SQL standard: escape single quotes by doubling them
    value = value.replace("'", "''")
    
    # MySQL-specific: escape backslashes
    value = value.replace("\\", "\\\\")
    
    return value


def _escape_like_pattern(value: str) -> str:
    """
    Escape LIKE pattern wildcards (%, _) for literal matching.
    
    [WARN] SECURITY NOTE: This prevents wildcard injection in LIKE queries.
    
    Args:
        value: Raw string value from user input
        
    Returns:
        Escaped string with wildcards escaped
    """
    if not isinstance(value, str):
        value = str(value)
    
    # First escape SQL string literals
    value = _escape_sql_string(value)
    
    # Then escape LIKE wildcards using backslash
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    
    return value


def _validate_column_identifier(column: str, allowed_columns: list) -> str:
    """
    Validate column identifier against allow-list.
    
    [WARN] SECURITY NOTE: Prevents identifier injection.
    
    Args:
        column: Column name from schema
        allowed_columns: List of allowed column names
        
    Returns:
        Validated column name
        
    Raises:
        ValueError: If column is not in allow-list
    """
    # Strip table prefix if present (e.g., "t.vendor_name"  "vendor_name")
    clean_column = column.split('.')[-1]
    
    # Validate against allow-list
    if clean_column not in allowed_columns:
        raise ValueError(f"Column '{clean_column}' not in schema allow-list")
    
    # Additional validation: only alphanumeric and underscore
    if not re.match(r'^[a-zA-Z0-9_]+$', clean_column):
        raise ValueError(f"Invalid column identifier: '{clean_column}'")
    
    return clean_column

def apply_filters(
    base_sql: str,
    base_params: Dict[str, Any],
    filters: Dict[str, Any],
    schema: Dict[str, Any],
    date_detector=None # Optional dependency for smart date parsing
) -> tuple[str, Dict[str, Any]]:
    """
    Applies filters by wrapping the base SQL in a subquery.
    This safely handles aliases, aggregates, and complex logic in the base query.
    
    [WARN] SECURITY WARNING: This function uses string interpolation with escaping.
    TODO: Refactor to use parameterized queries for production security.
    
    Known limitations:
    - Database-specific escaping (MySQL)
    - Vulnerable to identifier injection if schema is compromised
    - LIKE patterns have edge cases
    
    SQL Structure: SELECT * FROM ( <base_sql> ) AS base_view WHERE <filters>
    """
    clean_sql = base_sql.strip().rstrip(';')
    updated_params = base_params.copy()
    new_conditions = []
    
    # Build allow-list of columns from schema
    allowed_columns = [s["column"].split('.')[-1] for s in schema.values()]
    
    for filter_key, filter_value in filters.items():
        if filter_key not in schema:
            continue
            
        filter_def = schema[filter_key]
        raw_column = filter_def["column"]
        # For the wrapper, the column name is just the alias/name from the inner query.
        # We strip any table prefixes (e.g. t.col -> col) because the outer query sees the inner result columns.
        
        filter_type = filter_def["type"]
        
        # 1. Date Range
        if filter_type == "date" and isinstance(filter_value, dict):
            start, end = filter_value.get('start'), filter_value.get('end')
            
            # Validate column identifier
            try:
                column = _validate_column_identifier(raw_column, allowed_columns)
            except ValueError as e:
                logger.warning(f"Invalid column in date filter: {e}")
                continue
            
            # Conversion logic (STR_TO_DATE)
            # We try to detect if we need to convert the inner column to a date
            col_expr = column
            if start or end:
                if date_detector:
                     # Heuristic: try to detect format from the base SQL
                     table_match = re.search(r'FROM\s+(\w+)', clean_sql, re.IGNORECASE)
                     if table_match:
                        table_name = table_match.group(1)
                        db_fmt = date_detector.detect_format(table_name, column)
                        if db_fmt:
                            col_expr = f"STR_TO_DATE({column}, '{db_fmt}')"

                if start:
                    start_date = _escape_sql_string(_ensure_us_date_format(start))
                    new_conditions.append(f"{col_expr} >= STR_TO_DATE('{start_date}', '%m/%d/%Y')")
                if end:
                    end_date = _escape_sql_string(_ensure_us_date_format(end))
                    new_conditions.append(f"{col_expr} <= STR_TO_DATE('{end_date}', '%m/%d/%Y')")

        # 2. Numeric Range
        elif filter_type == "numeric" and isinstance(filter_value, dict):
            # Validate column identifier
            try:
                column = _validate_column_identifier(raw_column, allowed_columns)
            except ValueError as e:
                logger.warning(f"Invalid column in numeric filter: {e}")
                continue
            
            min_val, max_val = filter_value.get('min'), filter_value.get('max')
            
            if min_val:
                try:
                    min_val_safe = float(min_val)
                    new_conditions.append(f"{column} >= {min_val_safe}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric filter min value: {min_val}")
            
            if max_val:
                try:
                    max_val_safe = float(max_val)
                    new_conditions.append(f"{column} <= {max_val_safe}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric filter max value: {max_val}")

        # 3. Enum/Text Filters
        elif filter_type in ["enum", "text"]:
            # Validate column identifier
            try:
                column = _validate_column_identifier(raw_column, allowed_columns)
            except ValueError as e:
                logger.warning(f"Invalid column in text/enum filter: {e}")
                continue
            
            val_list = filter_value if isinstance(filter_value, list) else [filter_value]
            if not val_list or not val_list[0]: 
                continue
            
            # Escape all values - use LIKE escaping for pattern matching
            escaped_vals = [_escape_like_pattern(str(v)) for v in val_list if v]
            
            if not escaped_vals:
                continue
            
            if len(escaped_vals) > 1:
                # Multiple values - use IN clause (no wildcards needed)
                # Use basic string escaping for IN clause
                in_vals = [_escape_sql_string(str(v)) for v in val_list if v]
                formatted_vals = ", ".join([f"'{v}'" for v in in_vals])
                new_conditions.append(f"{column} IN ({formatted_vals})")
            else:
                # Single value - use LIKE for partial matching
                clean_val = escaped_vals[0]
                # Use ESCAPE clause to handle backslash escaping
                new_conditions.append(f"UPPER({column}) LIKE UPPER('%{clean_val}%') ESCAPE '\\\\'")

    # Construct Wrapper
    if not new_conditions:
        return base_sql, updated_params
        
    where_clause = " AND ".join(new_conditions)
    # Using a subquery wrapper to ensure safe filtering on aliases
    wrapped_sql = f"SELECT * FROM (\n{clean_sql}\n) AS base_view \nWHERE {where_clause}"
            
    return wrapped_sql, updated_params

def generate_detailed_summary(
    question: str,
    params: Dict[str, Any],
    result_rows: List[Dict[str, Any]],
    llm_client: LLMClient = None
) -> str:
    row_count = len(result_rows)

    if row_count == 0:
        return (
            f"No records matched the requested criteria. "
            f"This may indicate no activity for the selected period or filters."
        )
    
    # If no LLM client is provided, fall back to static template
    if not llm_client:
        return (
            f"This report answers the question: '{question}'. "
            f"The analysis is based on {row_count:,} records. "
            f"The data is grouped and calculated according to the requested breakdown."
        )

    # --- Pre-compute key stats for LLM prompt ---
    key_stats = {}
    if result_rows:
        # Identify numeric columns
        numeric_cols = []
        for col_name in result_rows[0].keys():
            # Check if at least one value in the first few rows is numeric
            if any(isinstance(row.get(col_name), (int, float)) for row in result_rows[:5]):
                numeric_cols.append(col_name)

        for col in numeric_cols:
            values = [row[col] for row in result_rows if isinstance(row.get(col), (int, float))]
            if values:
                key_stats[col] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "sum": sum(values)
                }
        
        # Identify categorical columns (non-numeric, with limited unique values)
        categorical_cols = []
        for col_name in result_rows[0].keys():
            if col_name not in numeric_cols:
                unique_values = set(str(row.get(col_name)) for row in result_rows if row.get(col_name) is not None)
                if 1 < len(unique_values) <= min(len(result_rows), 20): # Max 20 unique values or less than row_count
                    categorical_cols.append(col_name)
        
        for col in categorical_cols:
            counts = Counter(str(row.get(col)) for row in result_rows if row.get(col) is not None)
            if counts:
                most_common = counts.most_common(3)
                least_common = counts.most_common()[:-4:-1] # Get 3 least common
                key_stats[col] = {
                    "most_common": most_common,
                    "least_common": least_common
                }

    # Prepare data summary for LLM (limit to top 20 rows to avoid token limits)
    preview_rows = result_rows[:20]
    preview_str = json.dumps(preview_rows, default=str, indent=2)
    
    # Format key stats for the prompt
    stats_str = ""
    if key_stats:
        stats_str = "\n\nKEY DATA STATISTICS:\n"
        for col, stats in key_stats.items():
            stats_str += f"- **{col}**:\n"
            if "min" in stats: # Numeric stats
                stats_str += f"  - Range: {stats['min']:.2f} to {stats['max']:.2f}\n"
                stats_str += f"  - Average: {stats['avg']:.2f}\n"
                stats_str += f"  - Total Sum: {stats['sum']:.2f}\n"
            if "most_common" in stats: # Categorical stats
                stats_str += "  - Most Common: " + ", ".join([f"'{val}' ({count})" for val, count in stats['most_common']]) + "\n"
                stats_str += "  - Least Common: " + ", ".join([f"'{val}' ({count})" for val, count in stats['least_common']]) + "\n"

    system_prompt = f"""You are an expert business analyst writing a sharp, scannable report summary.

USER QUESTION: {question}
TOTAL RECORDS: {row_count:,}
APPLIED FILTERS: {params}
{stats_str}

RAW DATA PREVIEW (Top {min(20, len(preview_rows))} rows):
{preview_str}

-----------------------------------------
OUTPUT FORMAT  follow this EXACTLY, no extra sections:

**Answer**
(1-2 sentences. Directly answer the user's question with a hard number. No "the data shows".)

**Highlights**
- **Best**: [name/group] with [exact value]  [X]% above the average of [avg value]
- **Lowest**: [name/group] with [exact value]  [X]% below the average
- **Outlier / Trend**: (any notable pattern, concentration or gap  must cite a number)
- **Comparison**: (compare the top 2 entries OR this period vs expectation  with % difference)

**Watch Out**
- (1 specific red flag or anomaly that deserves action  must name the entity and value)

-----------------------------------------
NON-NEGOTIABLE RULES:
- Every single bullet MUST contain at least one specific number or percentage from KEY DATA STATISTICS or the raw preview.
- Use the exact values from KEY DATA STATISTICS for Best/Lowest  do NOT estimate.
- No emojis anywhere in the output.
- Write for a business manager, not a data scientist.
- Do NOT add any section not listed above. Do NOT write markdown tables.
"""

    try:
        response = llm_client.call_agent(
            system_prompt, 
            "Generate a professional executive synthesis.", 
            model=Config.RESPONSE_MODEL, 
            temperature=0.1
        )
         # Clean any thinking blocks
        if "<think>" in response:
            response = response.split("</think>")[-1]
            
        return response.strip()
    except Exception as e:
        logger.error(f"LLM Summary Generation Failed: {e}")
        return f"Analysis of {row_count:,} records related to: **{question}**."

REPORTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports_definitions.json")

def generate_report_name(
    original_question: str,
    columns: List[str],
    row_count: int,
    classification: str,
    llm_client: LLMClient = None
) -> str:
    """
    Generate a meaningful report name using LLM based on the query and data.
    Falls back to original question if LLM is not available.
    """
    if not llm_client:
        # Fallback: Use original question or create a simple name
        return original_question[:80] if len(original_question) <= 80 else original_question[:77] + "..."
    
    try:
        # Prepare context for name generation
        column_summary = ", ".join(columns[:10])  # First 10 columns
        if len(columns) > 10:
            column_summary += f" and {len(columns) - 10} more columns"
        
        system_prompt = f"""You are an expert at creating concise, descriptive report titles.

User Question: {original_question}
Report Type: {classification}
Data Columns: {column_summary}
Row Count: {row_count:,}

Create a professional, concise report title (maximum 60 characters) that:
1. Clearly describes what the report shows
2. Is specific and meaningful (not generic)
3. Uses business-friendly language
4. Avoids technical jargon when possible
5. Captures the essence of the data/analysis

Examples:
- "Top Vendors by Spend - Q4 2024"
- "Inventory Requests by Status - Current Month"
- "Purchase Orders Pending Receipt"
- "Requisition Analysis by Department"

Output ONLY the title, nothing else."""
        
        response = llm_client.call_agent(
            system_prompt,
            "Generate a concise report title.",
            model=Config.RESPONSE_MODEL,
            temperature=0.1
        )
        
        # Clean response
        if "<think>" in response:
            response = response.split("</think>")[-1]
        
        title = response.strip()
        # Remove quotes if present
        title = title.strip('"').strip("'")
        # Limit length
        if len(title) > 60:
            title = title[:57] + "..."
        
        return title if title else original_question[:80]
        
    except Exception as e:
        logger.error(f"Failed to generate report name: {e}")
        # Fallback to original question
        return original_question[:80] if len(original_question) <= 80 else original_question[:77] + "..."

def extract_chart_intent(charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract chart intent (type, x/y fields) without data points.
    Used to store chart configuration for regeneration.
    """
    chart_intents = []
    
    for chart in charts or []:
        if not chart:
            continue
            
        intent = {
            "type": chart.get("type") or chart.get("chart_type") or "bar_chart",
            "title": chart.get("title") or "Chart",
            "description": chart.get("description", "")
        }
        
        # 1. Prefer Explicit Intent (Correct)
        intent["x_intent"] = chart.get("x_key") or chart.get("x_intent") or chart.get("labels_key")
        intent["y_intent"] = chart.get("y_key") or chart.get("y_intent") or chart.get("values_key")
        
        # Persist Enhanced Styling & Logic
        intent["enhanced"] = chart.get("enhanced", False)
        intent["category_focus"] = chart.get("category_focus")
        intent["subtitle"] = chart.get("subtitle")
        intent["category_insights"] = chart.get("category_insights")
        intent["transformation"] = chart.get("transformation")
        intent["format"] = chart.get("format")
        intent["x_axis_title"] = chart.get("x_axis_title")
        intent["y_axis_title"] = chart.get("y_axis_title")
        intent["value"] = chart.get("value")  # For KPI cards

        # 2. Fallback to inferring from Data (Legacy/Chart.js)
        # Only do this if we didn't find explicit intent
        if not intent["x_intent"] and "data" in chart:
            data_config = chart["data"]
            # Try to find labels key (x-axis)
            if "labels" in data_config:
                intent["x_intent"] = "labels"  # Will need to infer from data
            
            # Try to find dataset keys (y-axis)
            if not intent["y_intent"] and "datasets" in data_config and len(data_config["datasets"]) > 0:
                dataset = data_config["datasets"][0]
                intent["y_intent"] = dataset.get("label", "value")
        
        chart_intents.append(intent)
    
    return chart_intents

def save_report(
    query_context: Dict[str, Any],
    sql_context: Dict[str, Any],
    result_cache: Dict[str, Any],
    user_id: str,
    llm_client: LLMClient = None,
    charts: List[Dict[str, Any]] = None,
    custom_title: Optional[str] = None,
    org_id: str = "default",
    date_detector=None  # NEW: DateFormatDetector for format detection
) -> Dict[str, str]:
    """
    Saves a report using SQL definition (no data storage).
    
    Args:
        custom_title: Optional custom title provided by user. If None, generates one using LLM.
        org_id: Organization ID for multi-tenancy support.
        date_detector: Optional DateFormatDetector for detecting date formats in columns.
    """
    
    # Generate detailed executive summary
    detailed_summary = generate_detailed_summary(
        question=query_context["original_question"],
        params=sql_context.get("base_params", {}),
        result_rows=result_cache["rows"],
        llm_client=llm_client
    )

    # Generate or use custom title
    if custom_title and custom_title.strip():
        report_title = custom_title.strip()
    else:
        report_title = generate_report_name(
            original_question=query_context["original_question"],
            columns=result_cache.get("columns", []),
            row_count=len(result_cache.get("rows", [])),
            classification=query_context.get("classification", "NON_REPORT"),
            llm_client=llm_client
        )
    
    # Extract chart intent (type + field mappings, no data) for regeneration
    chart_config = extract_chart_intent(charts)
    
    # Save FULL charts with data_override for direct use (when no filters applied)
    # This preserves the exact charts generated in Chat
    # Sanitize charts to remove NaN/Infinity values before saving
    saved_charts = []
    if charts:
        for chart in charts:
            # For simple charts, data_override might be null. 
            # We must freeze the exact chat data points so it doesn't regenerate differently on open.
            override_data = chart.get("data_override")
            if not override_data and "rows" in result_cache:
                override_data = result_cache["rows"]
                
            # Create a copy of the chart, preserving data_override if present
            saved_chart = {
                "chart_type": chart.get("chart_type") or chart.get("type") or "bar_chart",
                "title": chart.get("title", "Chart"),
                "subtitle": chart.get("subtitle"),
                "description": chart.get("description", ""),
                "x_key": chart.get("x_key"),
                "y_key": chart.get("y_key"),
                "x_axis_title": chart.get("x_axis_title"),
                "y_axis_title": chart.get("y_axis_title"),
                "format": chart.get("format"),
                "value": chart.get("value"),  # For KPI cards
                "enhanced": chart.get("enhanced", False),
                "category_focus": chart.get("category_focus"),
                "category_insights": chart.get("category_insights"),
                "data_override": sanitize_for_json(override_data),  # Sanitize data_override
                "is_advanced": chart.get("is_advanced", False)
            }
            saved_charts.append(saved_chart)
    
    # Generate filter schema with date format detection
    filter_schema = infer_filter_schema(
        columns=result_cache["columns"],
        sql=sql_context["base_sql"],
        date_detector=date_detector  # Pass detector for format detection
    )

    # Create report WITHOUT storing data rows
    report = Report(
        title=report_title,
        base_sql=sql_context["base_sql"],
        base_params=sql_context.get("base_params", {}),
        detailed_summary=detailed_summary,
        columns=result_cache["columns"],
        created_by=user_id,
        classification=query_context["classification"],
        query=query_context["original_question"],
        chart_config=chart_config,  # For regeneration when filters applied
        charts=saved_charts,  # Full charts for direct use when no filters
        org_id=org_id,
        row_count=len(result_cache.get("rows", [])),  # Store initial row count
        filter_schema=filter_schema  # Use generated schema with date formats
        # Note: rows parameter NOT passed - new reports don't store data
    )

    # Persist to simple JSON file
    try:
        existing_reports = []
        if os.path.exists(REPORTS_FILE):
             with open(REPORTS_FILE, 'r') as f:
                 try:
                     existing_reports = json.load(f)
                 except: 
                     existing_reports = []
        
        existing_reports.insert(0, report.to_dict())
        
        with open(REPORTS_FILE, 'w') as f:
            json.dump(existing_reports, f, indent=2, default=str)
        
        logger.info(f"Saved report {report.report_id} without data storage (SQL-definition model)")
            
        return {
            "status": "success",
            "report_id": report.report_id,
            "title": report.title,
            "message": "Report saved successfully"
        }
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

import math

def sanitize_for_json(obj):
    """
    Recursively replace NaN/Infinity with None for JSON compliance.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    return obj

def list_reports(limit: int = 50) -> List[Dict[str, Any]]:
    """
    List saved reports from the file store.
    """
    try:
        if not os.path.exists(REPORTS_FILE):
            return []
            
        with open(REPORTS_FILE, 'r') as f:
             reports = json.load(f)
             # Sanitize strictly to avoid Starlette serialization errors
             safe_reports = sanitize_for_json(reports[:limit])
             return safe_reports
    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        return []

def rename_report(report_id: str, new_title: str) -> Dict[str, Any]:
    """
    Rename a saved report.
    
    Args:
        report_id: The ID of the report to rename
        new_title: The new title for the report
        
    Returns:
        Dict with status and message
    """
    try:
        if not os.path.exists(REPORTS_FILE):
            return {"status": "error", "message": "No reports found"}
        
        with open(REPORTS_FILE, 'r') as f:
            reports = json.load(f)
        
        # Find the report
        report_index = None
        for idx, r in enumerate(reports):
            if r.get("id") == report_id:
                report_index = idx
                break
        
        if report_index is None:
            return {"status": "error", "message": "Report not found"}
        
        # Update the title
        reports[report_index]["title"] = new_title
        
        # Save back
        with open(REPORTS_FILE, 'w') as f:
            json.dump(reports, f, indent=2, default=str)
        
        return {
            "status": "success",
            "message": "Report renamed successfully",
            "report_id": report_id,
            "new_title": new_title
        }
        
    except Exception as e:
        logger.error(f"Failed to rename report: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def regenerate_report(
    report_id: str,
    filters: Dict[str, Any],
    user_id: str,
    llm_client: LLMClient,
    db_manager,
    date_detector=None,
    temporary: bool = False,
    insight_analyst = None
) -> Dict[str, Any]:
    """
    Regenerate a report with new filters.
    If temporary=True, the results are returned but not saved to the report file.
    """
    try:
        # ... (loading logic is same)
        if not os.path.exists(REPORTS_FILE):
            return {"status": "error", "message": "No reports found"}
            
        with open(REPORTS_FILE, 'r') as f:
            reports = json.load(f)
        
        # Find the report
        report_data = None
        report_index = None
        for idx, r in enumerate(reports):
            if r.get("id") == report_id:
                report_data = r
                report_index = idx
                break
        
        if not report_data:
            return {"status": "error", "message": "Report not found"}
        
        # Apply filters to SQL
        modified_sql, updated_params = apply_filters(
            base_sql=report_data["base_sql"],
            base_params=report_data.get("base_params", {}),
            filters=filters,
            schema=report_data.get("filterSchema", {}),
            date_detector=date_detector
        )
        
        logger.info(f"Regenerating report (temporary={temporary}) with SQL:\n{modified_sql}")
        
        # Execute SQL
        results_df = db_manager.execute_query_safe(modified_sql)
        new_rows = results_df.to_dict(orient='records')
        new_columns = results_df.columns.tolist()
        
        # Generate new summary
        new_summary = generate_detailed_summary(
            question=report_data.get("query", report_data["title"]),
            params=updated_params,
            result_rows=new_rows,
            llm_client=llm_client
        )
        
        # Regenerate charts using the EXACT same InsightAnalyst pipeline as Chat
        # (regenerate_report is always called when filters are applied, so always regenerate)
        new_charts = []
        if insight_analyst and not results_df.empty:
            logger.info(f"Filters applied - Using InsightAnalyst to regenerate charts (same as Chat) for {len(new_rows)} rows")
            try:
                user_query = report_data.get("query", report_data.get("title", "Report"))
                insight_config = insight_analyst.generate_insights(
                    user_query=user_query,
                    sql_query=modified_sql,
                    results_df=results_df,
                    schema_context="",
                    chat_history=None
                )
                if insight_config and insight_config.get("charts"):
                    new_charts = insight_config["charts"]
                    logger.info(f"InsightAnalyst generated {len(new_charts)} chart(s) successfully")
                else:
                    logger.warning("InsightAnalyst returned no charts, falling back to chart_config regeneration")
                    # Fallback to chart_config if InsightAnalyst fails
                    if report_data.get("chart_config"):
                        new_charts = regenerate_charts_from_data(
                            chart_intents=report_data["chart_config"],
                            data=new_rows,
                            columns=new_columns
                        )
            except Exception as e:
                logger.error(f"InsightAnalyst failed: {e}, falling back to chart_config regeneration", exc_info=True)
                # Fallback to chart_config regeneration
                if report_data.get("chart_config"):
                    new_charts = regenerate_charts_from_data(
                        chart_intents=report_data["chart_config"],
                        data=new_rows,
                        columns=new_columns
                    )
        elif report_data.get("chart_config"):
            # Fallback: use chart_config if InsightAnalyst not available
            logger.info(f"Using chart_config to regenerate charts for {len(new_rows)} rows")
            new_charts = regenerate_charts_from_data(
                chart_intents=report_data["chart_config"],
                data=new_rows,
                columns=new_columns
            )
        
        # Update report metadata (for legacy reports that store data)
        # Note: For temporary reports, we update the object in memory to return it,
        # but we do NOT save it to disk if temporary=True.
        if "data" in report_data:
            report_data["data"] = new_rows[:100]  # Store preview for legacy
            report_data["rowCount"] = len(new_rows)
        report_data["summary"] = new_summary
        report_data["detailed_summary"] = new_summary  # Update both fields
        report_data["lastRegeneratedAt"] = datetime.utcnow().isoformat()
        
        # Save back only if NOT temporary
        if not temporary:
             reports[report_index] = report_data
             with open(REPORTS_FILE, 'w') as f:
                 json.dump(reports, f, indent=2, default=str)
             logger.info(f"Saved regenerated report {report_id}")
        else:
             logger.info(f"Generated temporary view for report {report_id}")
        
        # Sanitize data and charts to remove NaN/Infinity values for JSON compliance
        sanitized_data = sanitize_for_json(new_rows)
        sanitized_charts = sanitize_for_json(new_charts)
        
        return {
            "status": "success",
            "data": sanitized_data,  # Return full data (not preview)
            "columns": new_columns,
            "rowCount": len(new_rows),
            "summary": new_summary,
            "charts": sanitized_charts,
            "cached_at": datetime.utcnow().isoformat()
        }

        
    except Exception as e:
        logger.error(f"Failed to regenerate report: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

def regenerate_charts_from_data(
    chart_intents: List[Dict[str, Any]],
    data: List[Dict[str, Any]],
    columns: List[str]
) -> List[Dict[str, Any]]:
    """
    Regenerates chart configurations compatible with the frontend InsightPanel (Recharts).
    Instead of generating Chart.js configs, we return a high-level config that the frontend
    uses to render dynamic charts.
    """
    charts = []
    
    if not data or len(data) == 0:
        logger.warning("No data provided for chart regeneration, returning empty charts")
        return charts
    
    for intent in chart_intents or []:
        try:
            # Determine chart type (default to bar if missing)
            chart_type = intent.get("type") or "bar_chart"
            if chart_type == "null" or chart_type is None:
                 # Simple heuristic: Time series -> Line, Categorical -> Bar
                 x_col = intent.get("x_intent", "").lower()
                 if "date" in x_col or "time" in x_col:
                     chart_type = "line_chart"
                 else:
                     chart_type = "bar_chart"
            
            # Normalize chart_type (remove _chart suffix if present for comparison)
            chart_type_normalized = chart_type.replace("_chart", "").lower()
            
            # Map intents to frontend keys
            chart_config = {
                "chart_type": chart_type_normalized,
                "title": intent.get("title", "Chart"),
                "subtitle": intent.get("subtitle"), # Restore subtitle
                "description": intent.get("description", ""),
                "x_key": intent.get("x_intent"),
                "y_key": intent.get("y_intent"),
                "x_axis_title": intent.get("x_axis_title"),
                "y_axis_title": intent.get("y_axis_title"),
                "value": intent.get("value"), # Restore KPI value
                "format": intent.get("format"), # Restore KPI format
                "enhanced": intent.get("enhanced", False), # Restore styling
                "category_focus": intent.get("category_focus"),
                "category_insights": intent.get("category_insights"),
                "data_override": None # Default: use full data
            }

            # Re-Apply Transformation Logic (Top N / Aggregation)
            transformation = intent.get("transformation")
            if transformation and data:
                try:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    method = transformation.get("method")
                    
                    if method == "top_n":
                        limit = transformation.get("limit", 15)
                        y_key = transformation.get("order_by") or intent.get("y_intent")
                        if y_key and y_key in df.columns:
                             # Re-apply Top N
                             df_sorted = df.nlargest(limit, y_key)
                             chart_config["data_override"] = df_sorted.to_dict(orient='records')
                             
                    elif method == "aggregation":
                         x_key = transformation.get("group_by") or intent.get("x_intent")
                         y_key = "count" # Usually aggregation is count
                         
                         if x_key and x_key in df.columns:
                             # Re-apply Group By Count
                             df_agg = df.groupby(x_key).size().reset_index(name='count')
                             
                             if transformation.get("limit"): # Top N after aggregation
                                 df_agg = df_agg.nlargest(transformation.get("limit"), 'count')
                                 
                             chart_config["data_override"] = df_agg.to_dict(orient='records')
                             chart_config["y_key"] = "count" # Ensure y_key matches aggregation

                except Exception as e:
                    logger.error(f"Failed to re-apply transformation: {e}")
            
            # Validate that required keys exist in data
            x_key = chart_config.get("x_key")
            y_key = chart_config.get("y_key")
            
            if not x_key or not y_key:
                # Try to infer from data if keys are missing
                if data and len(data) > 0:
                    sample_row = data[0]
                    if not x_key and columns:
                        # Use first non-numeric column as x_key
                        for col in columns:
                            if col in sample_row and not isinstance(sample_row[col], (int, float)):
                                chart_config["x_key"] = col
                                break
                    if not y_key and columns:
                        # Use first numeric column as y_key
                        for col in columns:
                            if col in sample_row and isinstance(sample_row[col], (int, float)):
                                chart_config["y_key"] = col
                                break
            
            charts.append(chart_config)
        except Exception as e:
            logger.error(f"Failed to regenerate chart: {e}", exc_info=True)
    
    return charts

def execute_report(
    report_id: str,
    params: Optional[Dict[str, Any]],
    db_manager,
    regenerate_charts: bool = True,
    insight_analyst = None
) -> Dict[str, Any]:
    """
    Execute a saved report's SQL query and return fresh data.
    Uses the same InsightAnalyst pipeline as Chat for chart generation.
    """
    try:
        if not os.path.exists(REPORTS_FILE):
            return {"status": "error", "message": "No reports found"}
        
        with open(REPORTS_FILE, 'r') as f:
            reports = json.load(f)
        
        report_data = None
        for r in reports:
            if r.get("id") == report_id:
                report_data = r
                break
        
        if not report_data:
            return {"status": "error", "message": "Report not found"}
        
        execution_params = params if params is not None else report_data.get("default_params", {})
        base_sql = report_data["base_sql"]
        
        logger.info(f"Executing report {report_id} with SQL: {base_sql[:200]}...")
        
        results_df = db_manager.execute_query_safe(base_sql)
        data_rows = results_df.to_dict(orient='records')
        columns = results_df.columns.tolist()
        
        charts = []
        if regenerate_charts:
            # Check if filters are applied (params differ from default)
            default_params = report_data.get("default_params", {})
            has_filters = params and params != default_params
            
            if has_filters:
                # Filters applied: Regenerate charts using InsightAnalyst (same as Chat)
                logger.info(f"Filters applied, regenerating charts using InsightAnalyst for {len(data_rows)} rows")
                if insight_analyst and not results_df.empty:
                    try:
                        user_query = report_data.get("query", report_data.get("title", "Report"))
                        insight_config = insight_analyst.generate_insights(
                            user_query=user_query,
                            sql_query=base_sql,
                            results_df=results_df,
                            schema_context="",
                            chat_history=None
                        )
                        if insight_config and insight_config.get("charts"):
                            charts = insight_config["charts"]
                            logger.info(f"InsightAnalyst generated {len(charts)} chart(s) successfully")
                        else:
                            logger.warning("InsightAnalyst returned no charts, falling back to chart_config regeneration")
                            if report_data.get("chart_config"):
                                charts = regenerate_charts_from_data(
                                    chart_intents=report_data["chart_config"],
                                    data=data_rows,
                                    columns=columns
                                )
                    except Exception as e:
                        logger.error(f"InsightAnalyst failed: {e}, falling back to chart_config regeneration", exc_info=True)
                        if report_data.get("chart_config"):
                            charts = regenerate_charts_from_data(
                                chart_intents=report_data["chart_config"],
                                data=data_rows,
                                columns=columns
                            )
                elif report_data.get("chart_config"):
                    charts = regenerate_charts_from_data(
                        chart_intents=report_data["chart_config"],
                        data=data_rows,
                        columns=columns
                    )
            else:
                # No filters: Use saved charts directly (from Chat)
                saved_charts = report_data.get("charts", [])
                if saved_charts:
                    logger.info(f"No filters applied, using {len(saved_charts)} saved chart(s) from Chat")
                    charts = saved_charts
                elif report_data.get("chart_config"):
                    # Fallback: regenerate from chart_config if no saved charts
                    logger.info(f"No saved charts, regenerating from chart_config for {len(data_rows)} rows")
                    charts = regenerate_charts_from_data(
                        chart_intents=report_data["chart_config"],
                        data=data_rows,
                        columns=columns
                    )
                else:
                    logger.warning(f"Report {report_id} has no saved charts and no chart_config")
        
        # Sanitize data and charts to remove NaN/Infinity values for JSON compliance
        sanitized_data = sanitize_for_json(data_rows)
        sanitized_charts = sanitize_for_json(charts)
        
        return {
            "status": "success",
            "data": sanitized_data,
            "columns": columns,
            "rowCount": len(data_rows),
            "charts": sanitized_charts,
            "executed_at": datetime.utcnow().isoformat(),
            "cached": False
        }
    except Exception as e:
        logger.error(f"Failed to execute report: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

def delete_report(report_id: str) -> Dict[str, Any]:
    """
    Delete a saved report from the file store.
    
    Args:
        report_id: The ID of the report to delete
        
    Returns:
        Dict with status and message
    """
    try:
        if not os.path.exists(REPORTS_FILE):
            return {"status": "error", "message": "No reports found"}
        
        with open(REPORTS_FILE, 'r') as f:
            reports = json.load(f)
        
        # Find and remove the report
        report_index = None
        for idx, r in enumerate(reports):
            if r.get("id") == report_id:
                report_index = idx
                break
        
        if report_index is None:
            return {"status": "error", "message": "Report not found"}
        
        # Remove the report
        deleted_report = reports.pop(report_index)
        
        # Save back
        with open(REPORTS_FILE, 'w') as f:
            json.dump(reports, f, indent=2, default=str)
        
        logger.info(f"Deleted report {report_id}: {deleted_report.get('title')}")
        
        return {
            "status": "success",
            "message": "Report deleted successfully",
            "report_id": report_id
        }
        
    except Exception as e:
        logger.error(f"Failed to delete report: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def save_filtered_version(
    report_id: str,
    filters: Dict[str, Any],
    new_title: str,
    user_id: str,
    db_manager,
    llm_client: LLMClient = None,
    date_detector=None
) -> Dict[str, Any]:
    """
    Save the currently filtered view of a report as a new standalone report.

    The filtered SQL (original base_sql wrapped with applied WHERE conditions)
    becomes the new report's base_sql, so it always returns this filtered slice.
    Chart config is inherited from the original; summary is regenerated against
    the filtered data.
    """
    try:
        # 1. Load original report
        if not os.path.exists(REPORTS_FILE):
            return {"status": "error", "message": "No reports found"}

        with open(REPORTS_FILE, "r") as f:
            reports = json.load(f)

        original = next((r for r in reports if r.get("id") == report_id), None)
        if not original:
            return {"status": "error", "message": "Original report not found"}

        # 2. Build filtered SQL
        filtered_sql, _ = apply_filters(
            base_sql=original["base_sql"],
            base_params=original.get("base_params", {}),
            filters=filters,
            schema=original.get("filterSchema", {}),
            date_detector=date_detector
        )

        # 3. Execute filtered SQL
        results_df = db_manager.execute_query_safe(filtered_sql)
        new_rows = results_df.to_dict(orient="records")
        new_columns = results_df.columns.tolist()

        # 4. Generate fresh summary against filtered data
        new_summary = generate_detailed_summary(
            question=original.get("query", original.get("title", "")),
            params=filters,
            result_rows=new_rows,
            llm_client=llm_client
        )

        # 5. Re-infer filter schema for the new SQL
        new_filter_schema = infer_filter_schema(
            columns=new_columns,
            sql=filtered_sql,
            date_detector=date_detector
        )

        # 6. Inherit chart config from original
        inherited_charts = original.get("chart_config", [])

        # 7. Build and persist new Report object
        new_report = Report(
            title=new_title.strip(),
            base_sql=filtered_sql,
            base_params={},          # Filters baked into SQL  no params needed
            detailed_summary=new_summary,
            columns=new_columns,
            created_by=user_id,
            classification=original.get("classification", "NON_REPORT"),
            query=original.get("query", original.get("title", "")),
            chart_config=inherited_charts,
            org_id=original.get("org_id", "default"),
            row_count=len(new_rows),
            filter_schema=new_filter_schema
        )

        reports.insert(0, new_report.to_dict())

        with open(REPORTS_FILE, "w") as f:
            json.dump(reports, f, indent=2, default=str)

        logger.info(f"Saved filtered version of {report_id} as new report {new_report.report_id}")

        return {
            "status": "success",
            "report_id": new_report.report_id,
            "title": new_report.title,
            "row_count": len(new_rows),
            "message": "Filtered report saved successfully"
        }

    except Exception as e:
        logger.error(f"Failed to save filtered version: {e}")
        return {"status": "error", "message": str(e)}
