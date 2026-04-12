"""
Query Generator - Validated SQL Query Generation

Generates SQL queries from insight plans with:
- Syntax validation
- Execution testing
- Iterative refinement
- Date filter support
"""

from typing import Dict, Any
from backend.core.logger import logger
from backend.config import Config


class QueryGenerator:
    """Generates and validates SQL queries for insights"""
    
    def __init__(self, llm_client, db_manager):
        self.llm = llm_client
        self.db = db_manager
        
        import os
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Load business context
        try:
            context_path = os.path.join(base_dir, "business_context.json")
            if os.path.exists(context_path):
                with open(context_path, "r") as f:
                    self.business_context = json.load(f)
                logger.info(f"QueryGenerator: Loaded business context: {self.business_context.get('business_name', 'Unknown')}")
            else:
                self.business_context = {}
        except Exception as e:
            logger.error(f"QueryGenerator: Failed to load business_context.json: {e}")
            self.business_context = {}
        
        # Load db_schema.json for FK-aware SQL generation
        try:
            schema_path = os.path.join(base_dir, "db_schema.json")
            if os.path.exists(schema_path):
                with open(schema_path, "r") as f:
                    schema_list = json.load(f)
                # Convert list to dict keyed by table_name
                self.db_schema = {t["table_name"]: t for t in schema_list}
                logger.info(f"QueryGenerator: Loaded schema for {len(self.db_schema)} tables")
            else:
                self.db_schema = {}
                logger.warning("QueryGenerator: db_schema.json not found")
        except Exception as e:
            logger.error(f"QueryGenerator: Failed to load db_schema.json: {e}")
            self.db_schema = {}
    
    def generate_query(self, insight_plan: Dict, category: str, period: str = "30 DAY") -> Dict[str, Any]:
        """
        Generate SQL query from insight plan
        
        Args:
            insight_plan: Plan from InsightPlanner
            category: kpi, trend, distribution, or alert
            period: Time period for date filtering (e.g., "30 DAY", "12 MONTH")
        
        Returns:
            Dictionary with sql, tested status, and sample result
        """
        logger.debug(f"Generating query for {insight_plan.get('id', 'unknown')}")
        
        # Check if plan has sql_template (from dashboard specifications)
        sql_template = insight_plan.get("sql_template", "")
        requires_date_filter = insight_plan.get("requires_date_filter", True)
        
        if sql_template and "{period}" in sql_template:
            # Use template from specifications and inject period
            sql = sql_template.replace("{period}", period)
            logger.info(f" Using SQL template from dashboard specifications for {insight_plan.get('id')}")
        else:
            # Generate SQL from plan (fallback or general generation)
            sql = self._generate_sql_from_plan(insight_plan, category, period, requires_date_filter)
        
        if not sql:
            return None
        
        # Validate syntax
        is_valid, error = self.db.validate_sql(sql)
        if not is_valid:
            logger.warning(f"Initial SQL invalid: {error}")
            sql = self._fix_syntax_error(sql, error, insight_plan)
            
            # Re-validate
            is_valid, error = self.db.validate_sql(sql)
            if not is_valid:
                logger.error(f"Could not fix SQL: {error}")
                return None
        
        # Test execution
        try:
            df = self.db.execute_query_safe(sql)
            tested = True
            
            # Convert DataFrame to list of dicts for JSON serialization
            if df is not None and not df.empty:
                # Convert timestamps to strings for JSON serialization
                sample_result = df.head(5).astype(str).to_dict(orient='records')
            else:
                sample_result = []
                
        except Exception as e:
            logger.warning(f"Query execution failed: {e}")
            tested = False
            sample_result = None
        
        # Get chart type and library from plan (for sophisticated visualizations)
        chart_type = insight_plan.get("chart_type") or self._get_default_chart_type(category)
        chart_library = insight_plan.get("chart_library") or self._get_default_chart_library(chart_type)
        visual_config = insight_plan.get("visual_config", {})
        
        return {
            "id": insight_plan.get("id", ""),
            "title": insight_plan.get("title", ""),
            "description": insight_plan.get("description", ""),
            "sql": sql,
            # Store original template so api.py can re-apply period without double-injection
            "sql_template": insight_plan.get("sql_template", ""),
            "viz_type": self._get_viz_type(category, chart_type),
            "chart_type": chart_type,  # NEW: Explicit chart type for frontend
            "chart_library": chart_library,  # NEW: Which library to use (plotly/recharts)
            "visual_config": visual_config,  # NEW: Visual styling configuration
            "category": category,
            "refresh_interval": "hourly",
            "icon": insight_plan.get("icon") or self._get_icon(category),
            "format": insight_plan.get("format") or self._get_format(insight_plan),
            "color": insight_plan.get("color"),  # NEW: Custom color for KPI cards
            "show_trend": insight_plan.get("show_trend", False),  # NEW: Show trend indicator
            "tested": tested,
            "sample_result": sample_result,
            "x_axis_label": insight_plan.get("x_axis_label"),
            "y_axis_label": insight_plan.get("y_axis_label"),
            # ADD FILTER METADATA for time filtering
            "filter_metadata": {
                "date_column": insight_plan.get("date_column"),
                "table": insight_plan.get("table"),
                "supports_time_filter": bool(insight_plan.get("date_column") and requires_date_filter),
                "requires_date_filter": requires_date_filter,
                "date_filter_periods": {
                    "7d": "7 DAY",
                    "30d": "30 DAY",
                    "3m": "3 MONTH",
                    "6m": "6 MONTH",
                    "12m": "12 MONTH",
                    "all": "100 YEAR"
                }
            },
            "card_filters": insight_plan.get("card_filters", [])
        }
    
    def _generate_sql_from_plan(self, plan: Dict, category: str, period: str = "30 DAY", requires_date_filter: bool = True) -> str:
        """Generate SQL from insight plan"""
        
        if category == "kpi":
            return self._generate_kpi_sql(plan, period, requires_date_filter)
        elif category == "trend":
            return self._generate_trend_sql(plan, period, requires_date_filter)
        elif category == "distribution":
            return self._generate_distribution_sql(plan, period, requires_date_filter)
        elif category == "alert":
            return self._generate_alert_sql(plan, period, requires_date_filter)
        
        return None
    
    def _generate_kpi_sql(self, plan: Dict, period: str = "30 DAY", requires_date_filter: bool = True) -> str:
        """Generate KPI SQL with date filtering"""
        # Check if we have sql_template (from dashboard specifications)
        sql_template = plan.get("sql_template", "")
        if sql_template and "{period}" in sql_template:
            # Use template from specifications
            sql = sql_template.replace("{period}", period)
            logger.info(f" Using SQL template from dashboard specifications for {plan.get('id')}")
            return sql
        
        table = plan.get("table", "")
        metric_col = plan.get("metric_column", "")
        aggregation = plan.get("aggregation", "COUNT")
        filter_cond = plan.get("filter_conditions", "")
        date_col = plan.get("date_column", "")
        
        if aggregation == "COUNT":
            if metric_col == "*" or not metric_col:
                select_clause = "COUNT(*) as total"
            else:
                select_clause = f"COUNT(DISTINCT {metric_col}) as total"
        elif aggregation == "SUM":
            select_clause = f"ROUND(COALESCE(SUM({metric_col}), 0), 2) as total"
        elif aggregation == "AVG":
            select_clause = f"ROUND(COALESCE(AVG({metric_col}), 0), 2) as total"
        else:
            select_clause = f"COALESCE({aggregation}({metric_col}), 0) as total"
        
        # Build WHERE clause with date filter if required
        where_parts = []
        if filter_cond:
            where_parts.append(filter_cond)
        
        # Add date filter if required and date column exists
        if requires_date_filter and date_col:
            # Handle different date formats - use lead_date format for franchise_new.leads_all_business
            if "leads_all_business" in table:
                # lead_date is datetime, use direct comparison
                where_parts.append(f"lead_date >= DATE_SUB(CURDATE(), INTERVAL {period})")
            else:
                # For other tables, check if date column needs STR_TO_DATE
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
        
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        
        sql = f"SELECT {select_clause} FROM {table} {where_clause}"
        return sql.strip()
    
    def _generate_trend_sql(self, plan: Dict, period: str = "12 MONTH", requires_date_filter: bool = True) -> str:
        """Generate trend SQL with date filtering
        
        Handles:
        - Standard single-metric trends
        - Multi-series trends (multiple lines/bars)
        - Dual-axis charts (revenue vs leads)
        """
        # Check if we have sql_template (from dashboard specifications)
        sql_template = plan.get("sql_template", "")
        if sql_template and "{period}" in sql_template:
            # Use template from specifications
            sql = sql_template.replace("{period}", period)
            logger.info(f" Using SQL template from dashboard specifications for {plan.get('id')}")
            return sql
        
        table = plan.get("table", "")
        date_col = plan.get("date_column", "")
        metric_col = plan.get("metric_column", "")
        aggregation = plan.get("aggregation", "COUNT")
        time_grouping = plan.get("time_grouping", "monthly")
        filter_cond = plan.get("filter_conditions", "")
        group_by = plan.get("group_by")
        visual_config = plan.get("visual_config", {})
        chart_type = plan.get("chart_type", "line")
        
        # Date format based on grouping
        if time_grouping == "monthly":
            # Handle lead_date (datetime) vs other date formats
            if "leads_all_business" in table and date_col == "lead_date":
                date_format = f"DATE_FORMAT({date_col}, '%Y-%m')"
            else:
                date_format = f"DATE_FORMAT(COALESCE(STR_TO_DATE({date_col}, '%Y-%m-%d'), STR_TO_DATE({date_col}, '%d/%m/%y')), '%Y-%m')"
        elif time_grouping == "quarterly":
            if "leads_all_business" in table and date_col == "lead_date":
                date_format = f"CONCAT(YEAR({date_col}), '-Q', QUARTER({date_col}))"
            else:
                date_format = f"CONCAT(YEAR(COALESCE(STR_TO_DATE({date_col}, '%Y-%m-%d'), STR_TO_DATE({date_col}, '%d/%m/%y'))), '-Q', QUARTER(COALESCE(STR_TO_DATE({date_col}, '%Y-%m-%d'), STR_TO_DATE({date_col}, '%d/%m/%y'))))"
        else:
            if "leads_all_business" in table and date_col == "lead_date":
                date_format = f"DATE_FORMAT({date_col}, '%Y-%m')"
            else:
                date_format = f"DATE_FORMAT(COALESCE(STR_TO_DATE({date_col}, '%Y-%m-%d'), STR_TO_DATE({date_col}, '%d/%m/%y')), '%Y-%m')"
        
        if aggregation == "COUNT":
            if metric_col == "*" or not metric_col:
                select_metric = "COUNT(*) as total"
            else:
                select_metric = f"COUNT(DISTINCT {metric_col}) as total"
        elif aggregation == "SUM":
            select_metric = f"ROUND(COALESCE(SUM({metric_col}), 0), 2) as total"
        elif aggregation == "AVG":
            select_metric = f"ROUND(COALESCE(AVG({metric_col}), 0), 2) as total"
        else:
            select_metric = f"COALESCE({aggregation}({metric_col}), 0) as total"
        
        # Build WHERE clause
        where_parts = []
        if filter_cond:
            where_parts.append(filter_cond)
        
        # Add date filter if required
        if requires_date_filter and date_col:
            if "leads_all_business" in table and date_col == "lead_date":
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
            else:
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
        
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        
        # Handle multi-metric queries (e.g., revenue vs leads for dual-axis)
        if visual_config.get("dual_axis") or visual_config.get("primary_metric") and visual_config.get("secondary_metric"):
            # Dual-axis chart needs multiple metrics
            primary_metric = visual_config.get("primary_metric", "revenue")
            secondary_metric = visual_config.get("secondary_metric", "leads")
            
            if primary_metric == "revenue" and secondary_metric == "leads":
                # Special case: revenue vs leads
                select_clause = f"""{date_format} as period, 
    ROUND(COALESCE(SUM(rpl), 0), 2) as revenue, 
    COUNT(DISTINCT id) as leads"""
            else:
                # Generic dual metric
                select_clause = f"""{date_format} as period, 
    {select_metric} as {primary_metric},
    COUNT(DISTINCT id) as {secondary_metric}"""
        else:
            # Standard single metric
            select_clause = f"{date_format} as period{', ' + group_by if group_by else ''}, {select_metric}"
        
        # Build GROUP BY clause
        group_by_clause = "GROUP BY period"
        if group_by:
            # If there's an additional group_by (e.g., by site), add it
            group_by_clause = f"GROUP BY period, {group_by}"
        elif visual_config.get("dual_axis"):
            # For dual-axis, just group by period
            group_by_clause = "GROUP BY period"
        
        sql = f"""SELECT {select_clause}
FROM {table}
{where_clause}
{group_by_clause}
ORDER BY period ASC"""
        
        return sql.strip()
    
    def _generate_distribution_sql(self, plan: Dict, period: str = "30 DAY", requires_date_filter: bool = True) -> str:
        """Generate distribution SQL using LLM with full schema context.
        
        The LLM sees the table schema + FK-referenced tables and decides
        whether to JOIN and which columns to use for human-readable output.
        No hardcoded column lists  the AI decides based on context.
        
        Special handling for advanced chart types:
        - bubble_chart: Returns category, x_value, y_value, size_value
        - multi-metric: Returns multiple metrics for dual-axis or grouped charts
        """
        table = plan.get("table", "")
        category_col = plan.get("category_column", "")
        metric_col = plan.get("metric_column", "")
        aggregation = plan.get("aggregation", "COUNT")
        limit = plan.get("limit", 10)
        date_col = plan.get("date_column", "")
        filter_cond = plan.get("filter_conditions", "")
        category_join_table = plan.get("category_join_table")
        category_join_conditions = plan.get("category_join_conditions")
        category_display_column = plan.get("category_display_column")
        chart_type = plan.get("chart_type", "bar")
        visual_config = plan.get("visual_config", {})
        
        # Check if we have sql_template (from dashboard specifications)
        sql_template = plan.get("sql_template", "")
        if sql_template and "{period}" in sql_template:
            # Use template from specifications
            sql = sql_template.replace("{period}", period)
            logger.info(f" Using SQL template from dashboard specifications for {plan.get('id')}")
            return sql
        
        # Build schema context with FKs and related tables
        schema_context = self._build_schema_context(table)
        
        # Business context description
        biz_context = ""
        if self.business_context:
            biz_context = f"\nBUSINESS CONTEXT: {self.business_context.get('description', '')}"
        
        system_prompt = """You are a SQL expert. Write a single SELECT query for a distribution chart.
Output ONLY the raw SQL query. NO markdown, NO explanations, NO code blocks."""
        
        # Determine output columns based on chart type
        output_columns_instruction = ""
        if chart_type == "bubble_chart":
            # Bubble chart needs: category, x_value (leads), y_value (revenue), size_value (revenue)
            output_columns_instruction = f"""
CRITICAL: This is a BUBBLE CHART - return 4 columns:
1. "category" - the category name
2. "leads" - COUNT of leads (x-axis)
3. "revenue" - SUM of revenue (y-axis)  
4. "total" - same as revenue (size of bubble)
"""
        elif chart_type in ["multi_line", "grouped_bar"]:
            # Multi-series charts need category + multiple metric columns
            output_columns_instruction = f"""
CRITICAL: This is a MULTI-SERIES chart - return category plus multiple metric columns.
If group_by is specified, create one column per group value.
"""
        else:
            # Standard distribution: category + total
            output_columns_instruction = """
The query MUST return exactly 2 columns: "category" and "total"
"""
        
        user_prompt = f"""Write a SQL query for this distribution chart:

PLAN:
- Main Table: {table}
- Category Column: {category_col}
- Metric: {aggregation}({metric_col if metric_col and aggregation != 'COUNT' else '*'})
- Limit: {limit}
- Chart Type: {chart_type}
{output_columns_instruction}
SCHEMA CONTEXT (columns, types, and foreign keys):
{schema_context}
{biz_context}

RULES:
{output_columns_instruction}
1. If "{category_col}" is a foreign key (references another table), you MUST JOIN with that table
   and use a human-readable column (name, first_name+last_name, display_name, title, etc.) as "category"
2. If "{category_col}" is already a text/varchar column with meaningful values, use it directly
3. If "{category_col}" is a numeric ID with no FK, check if the schema has a related lookup table
4. Exclude NULL categories and rows where the category_col is 0 or empty
5. ORDER BY total DESC, LIMIT {limit}
6. Use fully qualified table names (database.table)
7. {"CRITICAL: Add date filter. Use: WHERE ... AND {date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})" if requires_date_filter and date_col else ""}
8. {"Add filter conditions: " + filter_cond if filter_cond else ""}

Output ONLY the SQL query, nothing else."""

        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                temperature=0.1,
                timeout=30,
                agent_name="Dashboard-DistSQL",
                log_file="logs/dashboard_usage.csv"
            )
            
            sql = self._clean_sql_response(response)
            
            # Ensure date filter is added if required but missing
            if requires_date_filter and date_col and date_col not in sql.upper():
                logger.warning(f"Date filter missing in LLM SQL, adding manually")
                # Try to add date filter before WHERE or at end
                if "WHERE" in sql.upper():
                    # Insert date filter after WHERE
                    sql_parts = sql.split("WHERE", 1)
                    if len(sql_parts) == 2:
                        sql = f"{sql_parts[0]}WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL {period}) AND {sql_parts[1]}"
                    else:
                        sql = sql.rstrip(";") + f" WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})"
                else:
                    sql = sql.rstrip(";") + f" WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})"
            
            if "SELECT" in sql.upper() and "category" in sql.lower():
                logger.info(f"[OK] LLM-generated distribution SQL for {plan.get('id', 'unknown')}")
                return sql
            else:
                logger.warning(f"LLM returned invalid distribution SQL, using fallback")
                return self._fallback_distribution_sql(plan, period, requires_date_filter)
                
        except Exception as e:
            logger.error(f"LLM distribution SQL generation failed: {e}")
            return self._fallback_distribution_sql(plan)
    
    def _fallback_distribution_sql(self, plan: Dict, period: str = "30 DAY", requires_date_filter: bool = True) -> str:
        """Simple fallback template if LLM fails"""
        table = plan.get("table", "")
        category_col = plan.get("category_column", "")
        metric_col = plan.get("metric_column", "")
        aggregation = plan.get("aggregation", "COUNT")
        limit = plan.get("limit", 10)
        date_col = plan.get("date_column", "")
        filter_cond = plan.get("filter_conditions", "")
        category_join_table = plan.get("category_join_table")
        category_display_column = plan.get("category_display_column")
        
        # Build WHERE clause
        where_parts = []
        if category_col:
            where_parts.append(f"{category_col} IS NOT NULL")
        if filter_cond:
            where_parts.append(filter_cond)
        if requires_date_filter and date_col:
            if "leads_all_business" in table and date_col == "lead_date":
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
            else:
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
        
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        
        # Handle JOIN if category_join_table is specified
        from_clause = f"FROM {table}"
        category_select = f"{category_col} as category"
        
        if category_join_table and category_display_column:
            # Use JOIN to get human-readable category name
            join_conditions = plan.get("category_join_conditions", f"{category_col} = {category_join_table}.id")
            from_clause = f"FROM {table} JOIN {category_join_table} ON {join_conditions}"
            category_select = f"{category_display_column} as category"
        
        if aggregation == "COUNT":
            if metric_col == "*" or not metric_col:
                select_metric = "COUNT(*) as total"
            else:
                select_metric = f"COUNT(DISTINCT {metric_col}) as total"
        elif aggregation == "SUM":
            select_metric = f"ROUND(COALESCE(SUM({metric_col}), 0), 2) as total"
        elif aggregation == "AVG":
            select_metric = f"ROUND(COALESCE(AVG({metric_col}), 0), 2) as total"
        else:
            select_metric = f"COALESCE({aggregation}({metric_col}), 0) as total"
        
        return f"""SELECT {category_select}, {select_metric}
{from_clause}
{where_clause}
GROUP BY category
ORDER BY total DESC
LIMIT {limit}""".strip()
    
    def _build_schema_context(self, table: str) -> str:
        """Build schema context for a table including FK-referenced tables.
        
        Gives the LLM everything it needs to decide JOINs:
        - Main table columns with types
        - Foreign key relationships
        - Referenced table columns (so LLM can pick name columns)
        """
        if not self.db_schema:
            return f"Table: {table} (no schema available)"
        
        # Get the bare table name (strip database prefix)
        bare_table = table.split(".")[-1] if "." in table else table
        db_prefix = table.split(".")[0] + "." if "." in table else ""
        
        table_def = self.db_schema.get(bare_table)
        if not table_def:
            return f"Table: {table} (not found in schema)"
        
        lines = []
        lines.append(f"=== MAIN TABLE: {table} ===")
        lines.append(f"Purpose: {table_def.get('purpose', 'N/A')}")
        lines.append("Columns:")
        for col in table_def.get("columns", []):
            lines.append(f"  - {col['name']} ({col['type']})  {col.get('description', '')}")
        
        # Foreign keys
        fks = table_def.get("foreign_keys", [])
        if fks:
            lines.append("Foreign Keys:")
            for fk in fks:
                lines.append(f"  - {fk['column']}  {fk['references']}")
        
        # Now load referenced tables so LLM can see their columns
        referenced_tables = set()
        for fk in fks:
            ref = fk.get("references", "")
            # Parse "franchises.sales_reps(id)"  "sales_reps"
            if "(" in ref:
                ref_table = ref.split("(")[0].split(".")[-1]
                referenced_tables.add(ref_table)
        
        for ref_table in referenced_tables:
            ref_def = self.db_schema.get(ref_table)
            if ref_def:
                lines.append(f"\n=== REFERENCED TABLE: {db_prefix}{ref_table} ===")
                lines.append(f"Purpose: {ref_def.get('purpose', 'N/A')}")
                lines.append("Columns:")
                for col in ref_def.get("columns", []):
                    lines.append(f"  - {col['name']} ({col['type']})  {col.get('description', '')}")
        
        return "\n".join(lines)
    
    def _generate_alert_sql(self, plan: Dict, period: str = "30 DAY", requires_date_filter: bool = True) -> str:
        """Generate alert SQL with optional date filtering"""
        # Check if we have sql_template (from dashboard specifications)
        sql_template = plan.get("sql_template", "")
        if sql_template and "{period}" in sql_template:
            # Use template from specifications
            sql = sql_template.replace("{period}", period)
            logger.info(f" Using SQL template from dashboard specifications for {plan.get('id')}")
            return sql
        
        table = plan.get("table", "")
        condition = plan.get("condition", "")
        filter_cond = plan.get("filter_conditions", "")
        date_col = plan.get("date_column", "")
        aggregation = plan.get("aggregation", "COUNT")
        metric_col = plan.get("metric_column", "")
        
        # Build WHERE clause
        where_parts = []
        if condition:
            where_parts.append(condition)
        elif filter_cond:
            where_parts.append(filter_cond)
        
        # Add date filter if required
        if requires_date_filter and date_col:
            if "leads_all_business" in table and date_col == "lead_date":
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
            else:
                where_parts.append(f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL {period})")
        
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        
        if aggregation == "COUNT":
            if metric_col == "*" or not metric_col:
                select_clause = "COUNT(*) as count"
            else:
                select_clause = f"COUNT(DISTINCT {metric_col}) as count"
        else:
            select_clause = f"COALESCE({aggregation}({metric_col}), 0) as count"
        
        sql = f"SELECT {select_clause} FROM {table} {where_clause}"
        return sql.strip()
    
    def _fix_syntax_error(self, sql: str, error: str, plan: Dict) -> str:
        """Use LLM to fix SQL syntax error"""
        prompt = f"""Fix this SQL query that has a syntax error.

ORIGINAL SQL:
{sql}

ERROR:
{error}

INSIGHT PLAN:
{plan}

Output ONLY the fixed SQL query. NO MARKDOWN. NO EXPLANATIONS."""

        try:
            response = self.llm.call_agent(
                system_prompt="You are a SQL expert fixing syntax errors.",
                user_query=prompt,
                temperature=0.1,
                timeout=30,
                agent_name="Dashboard-SQLFixer",
                log_file="logs/dashboard_usage.csv"
            )
            
            # Extract SQL from response
            fixed_sql = self._clean_sql_response(response)
            if "SELECT" in fixed_sql.upper():
                return fixed_sql
            else:
                return sql  # Return original if fix failed
                
        except Exception as e:
            logger.error(f"Error fixing SQL: {e}")
            return sql
            
    def _clean_sql_response(self, response: str) -> str:
        """Clean SQL response by removing markdown blocks"""
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if "```sql" in cleaned:
            cleaned = cleaned.replace("```sql", "")
        if "```" in cleaned:
            cleaned = cleaned.replace("```", "")
            
        return cleaned.strip()
    
    def _get_viz_type(self, category: str, chart_type: str = None) -> str:
        """Get visualization type for category"""
        # If chart_type is explicitly provided, use it
        if chart_type:
            # Map chart types to viz_type format
            type_mapping = {
                "line": "line_chart",
                "area": "area_chart",
                "bar": "bar_chart",
                "horizontal_bar": "bar_chart",
                "pie": "pie_chart",
                "treemap": "treemap",
                "heatmap": "heatmap",
                "funnel_chart": "funnel_chart",
                "waterfall_chart": "waterfall_chart",
                "bubble_chart": "bubble_chart",
                "gauge": "gauge",
                "multi_line": "multi_line",
                "grouped_bar": "grouped_bar"
            }
            return type_mapping.get(chart_type, f"{chart_type}_chart")
        
        # Default fallback
        viz_types = {
            "kpi": "kpi_card",
            "trend": "line_chart",
            "distribution": "bar_chart",
            "alert": "kpi_card"
        }
        return viz_types.get(category, "kpi_card")
    
    def _get_default_chart_type(self, category: str) -> str:
        """Get default chart type for category"""
        defaults = {
            "kpi": "kpi_card",
            "trend": "line",
            "distribution": "bar",
            "alert": "kpi_card"
        }
        return defaults.get(category, "bar")
    
    def _get_default_chart_library(self, chart_type: str) -> str:
        """Determine which chart library to use based on chart type"""
        plotly_types = ["treemap", "heatmap", "funnel_chart", "waterfall_chart", "bubble_chart", "gauge", "histogram", "candlestick"]
        if chart_type in plotly_types:
            return "plotly"
        return "recharts"
    
    def _get_icon(self, category: str) -> str:
        """Get icon for category"""
        icons = {
            "kpi": "dollar-sign",
            "trend": "trending-up",
            "distribution": "bar-chart",
            "alert": "alert-circle"
        }
        return icons.get(category, "activity")
    
    def _get_format(self, plan: Dict) -> str:
        """Get format from plan"""
        metric_col = plan.get("metric_column", "").lower()
        
        if any(word in metric_col for word in ["amount", "revenue", "cost", "price", "investment"]):
            return "currency"
        elif any(word in metric_col for word in ["rate", "percent", "ratio"]):
            return "percentage"
        else:
            return "number"
