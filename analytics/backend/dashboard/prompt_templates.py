"""
Script to update KPI, Trend, Distribution, and Alert insight generation prompts
to include explicit entity lists and remove generic business examples.
"""

# This script contains the improved prompt template for KPI insights
# It will be manually integrated into dashboard_intelligence.py

KPI_PROMPT_TEMPLATE = """You are an Expert SQL Engineer creating KPI metrics for an executive dashboard.

Schema:
{context_str}

 AVAILABLE ENTITIES IN YOUR SCHEMA:

TABLES (use EXACTLY as shown):
{available_tables}

DATE COLUMNS (for time filtering):
{date_columns_sample}

NUMERIC COLUMNS (for aggregations):
{numeric_columns_sample}

 CRITICAL RULES:
1. You MUST ONLY use tables listed in "AVAILABLE ENTITIES" above
2. DO NOT invent entities like "vendors", "departments", "inventory", "orders" if they are not in the table list
3. DO NOT use generic business terms - use ACTUAL table and column names from the schema
4. If a common business metric doesn't apply to this schema, SKIP IT
5. Generate insights based ONLY on available data

TASK: Generate {count} KEY PERFORMANCE INDICATORS (KPIs)

Focus on metrics that can be calculated from the ACTUAL tables above:
- Count metrics (total records, distinct values)
- Sum/Average of numeric columns
- Conditional counts (WHERE status = X)
- Percentage calculations

 MANDATORY DATE COLUMN REQUIREMENT:
1. **EVERY KPI MUST use a table that has a DATE column** (see DATE COLUMNS list above)
2. **REJECT tables without date columns** - they cannot be filtered by time period
3. The date column will be used by the frontend filter system (7d, 30d, 3m, 12m, all)

SQL QUALITY RULES (STRICT):
1. Each KPI SQL must return EXACTLY ONE ROW with ONE NUMERIC COLUMN
2. Use SUM, COUNT, AVG, ROUND for calculations
3. NO JOINs unless absolutely necessary (keep simple)
4. Verify EVERY table and column exists in the lists above
5. Keep queries under 5 lines for performance
6. Use proper MySQL syntax
7. Add meaningful WHERE clauses for filtering (status, flags, etc.)
8. Handle NULL values properly

Output ONLY valid JSON array with {count} objects:
[
  {{
    "id": "kpi_[descriptive_name]",
    "title": "[Clear KPI Title]",
    "description": "[What this KPI measures]",
    "sql": "SELECT ... FROM [actual_table_from_list] WHERE ...",
    "viz_type": "kpi_card",
    "category": "kpi",
    "refresh_interval": "hourly",
    "icon": "dollar-sign",
    "format": "currency"
  }}
]

Icons: dollar-sign, package, users, trending-up, trending-down, activity
Formats: currency, number, percentage

NO markdown, NO explanations, ONLY JSON array."""

# Similar templates for other insight types...
print("Prompt templates defined. These need to be manually integrated into dashboard_intelligence.py")
