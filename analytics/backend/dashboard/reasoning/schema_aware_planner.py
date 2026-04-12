"""
Schema-Aware Planner - Uses RAG to get actual schema columns

This planner retrieves actual table schemas using RAG before planning,
ensuring all column names are real and exist in the database.
"""

from typing import Dict, List, Any
import json
import os
from backend.core.logger import logger
from backend.config import Config


# Comprehensive Chart Selection Rules for LLM
CHART_SELECTION_RULES = """
 CHART TYPE SELECTION RULES - CRITICAL GUIDANCE:

For TRENDS (time-series data):
------------------------------------------------------------------------
- LINE CHART ("line"):
  S Best for: Continuous trends, growth/decline patterns, comparing multiple series
  S Use when: Tracking changes over time, showing progression
  F Avoid when: Data is very sparse or has many gaps
  Example: Monthly revenue trend, user growth over time

- AREA CHART ("area"):
  S Best for: Volume/magnitude over time, emphasizing total quantity
  S Use when: Showing accumulation, highlighting volume (SUM aggregations)
  F Avoid when: Multiple overlapping series (hard to read)
  Example: Total sales volume by month, cumulative revenue

- BAR CHART ("bar"):
  S Best for: Discrete time period comparisons, period-over-period analysis
  S Use when: Comparing specific months/quarters, showing rankings over time
  F Avoid when: Too many time periods (gets cluttered, use line instead)
  Example: Quarterly revenue comparison, monthly order counts

For DISTRIBUTIONS (categorical data):
------------------------------------------------------------------------
- PIE CHART ("pie"):
  S Best for: 2-5 categories, showing parts of a whole
  S Use when: Few categories, percentage breakdown is important
  F Avoid when: More than 5 categories (slices become too small)
  Example: Status breakdown (3 statuses), payment method distribution

- DONUT CHART ("donut"):
  S Best for: Same as pie, but with center space for displaying total
  S Use when: 2-6 categories AND you want to show total value in center
  F Avoid when: More than 6 categories
  Example: Customer type distribution with total count

- BAR CHART ("bar"):
  S Best for: 6-15 categories, ranking items, comparing magnitudes
  S Use when: Showing top N items, comparing many categories
  F Avoid when: Too few categories (pie is better) or too many (use treemap)
  Example: Top 10 vendors by spend, top products by sales

- TREEMAP ("treemap"):
  S Best for: 15+ categories, hierarchical data, showing proportions
  S Use when: Many items need to be shown, space efficiency is important
  F Avoid when: Few categories (overkill, use bar or pie)
  Example: All product categories, department breakdown with 20+ items

DECISION PROCESS (follow this for EVERY insight):
------------------------------------------------------------------------
1. Identify insight type: Is this time-series (trend) or categorical (distribution)?
2. Count expected data points/categories
3. Consider the business question: What comparison do users need to make?
4. Choose chart type that makes that comparison EASIEST
5. Justify your choice in the "reasoning" field

CRITICAL REQUIREMENTS:
------------------------------------------------------------------------
- You MUST include "chart_type" field in every trend and distribution insight
- You MUST provide "reasoning" explaining WHY you chose that chart type
- You MUST use diverse chart types across all insights (don't make everything "bar")
- You MUST consider the limit/cardinality when choosing distribution charts

EXAMPLES OF GOOD REASONING:
------------------------------------------------------------------------
S "Using area chart to emphasize revenue volume over time (SUM aggregation)"
S "Pie chart appropriate for 3 status categories, easy percentage comparison"
S "Bar chart for top 10 vendors - good for ranking and magnitude comparison"
S "Line chart shows growth trend clearly over 12 months"
F "Using bar chart" (too vague, doesn't explain why)
"""



class SchemaAwarePlanner:
    """Plans insights using actual schema columns from RAG"""
    
    def __init__(self, llm_client, rag_retriever, schema_analysis: Dict, data_exploration: Dict):
        self.llm = llm_client
        self.rag = rag_retriever
        self.schema_analysis = schema_analysis
        self.data_exploration = data_exploration
        self.table_schemas = {}
        
        # Load authoritative schema from JSON
        try:
            schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "db_schema.json")
            with open(schema_path, "r") as f:
                self.json_schema = {t["table_name"]: t for t in json.load(f)}
            logger.info(f"Loaded authoritative schema for {len(self.json_schema)} tables from JSON")
        except Exception as e:
            logger.error(f"Failed to load db_schema.json: {e}")
            self.json_schema = {}
            
        # Load business context
        try:
            context_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "business_context.json")
            if os.path.exists(context_path):
                with open(context_path, "r") as f:
                    self.business_context = json.load(f)
                logger.info(f"Loaded business context: {self.business_context.get('business_name', 'Unknown')}")
            else:
                self.business_context = {}
                logger.warning("business_context.json not found")
        except Exception as e:
            logger.error(f"Failed to load business_context.json: {e}")
            self.business_context = {}
    
    def plan_insights(self) -> Dict[str, Any]:
        """
        Plan insights using Adaptive Coverage Engine
        
        First checks for dashboard specifications in business_context.json.
        If found, uses those specifications. Otherwise, falls back to adaptive generation.
        
        Automatically scales strategy based on schema size:
        - Small (1-20): Comprehensive
        - Medium (21-100): Tiered
        - Large (101-500): Strategic Sampling
        - Enterprise (500+): Domain Partitioned
        """
        logger.info(" Starting ADAPTIVE insight planning...")
        
        # CHECK FOR DASHBOARD SPECIFICATIONS FIRST
        dashboard_specs = self.business_context.get("dashboard", {})
        if dashboard_specs and (dashboard_specs.get("kpi_cards") or dashboard_specs.get("trend_charts") or dashboard_specs.get("distribution_charts") or dashboard_specs.get("alert_cards")):
            logger.info("S Found dashboard specifications in business_context.json - using predefined cards")
            return self._plan_from_specifications(dashboard_specs)
        
        logger.info(" No dashboard specifications found - using adaptive generation")
        
        # Get tables with data
        tables_with_data = [
            table for table, count in self.data_exploration.get("row_counts", {}).items()
            if count > 0
        ]
        
        if not tables_with_data:
            # Fallback: use all tables with time dimensions
            tables_with_data = list(self.schema_analysis.get("time_dimensions", {}).keys())
        
        logger.info(f" Found {len(tables_with_data)} tables with data")
        
        # Initialize Adaptive Coverage Engine
        from .adaptive_coverage_engine import AdaptiveCoverageEngine
        coverage_engine = AdaptiveCoverageEngine(
            self.schema_analysis,
            self.data_exploration,
            self.json_schema
        )
        
        # Determine optimal strategy
        strategy = coverage_engine.determine_strategy(tables_with_data)
        logger.info(f" Strategy: {strategy['strategy_type'].upper()}")
        logger.info(f" Reasoning: {strategy['reasoning']}")
        
        # Execute strategy
        all_plans = {
            "kpi_plans": [],
            "trend_plans": [],
            "distribution_plans": [],
            "alert_plans": []
        }
        
        for batch in strategy["table_batches"]:
            logger.info(f" Processing batch: {batch['name']} ({len(batch['tables'])} tables)")
            
            # Retrieve schemas for this batch
            self._retrieve_table_schemas(batch["tables"])
            
            # Determine insight allocation for this batch
            if strategy["strategy_type"] == "comprehensive":
                allocation = strategy["insight_allocation"]
            elif strategy["strategy_type"] == "tiered":
                allocation = strategy["insight_allocation"].get(batch["name"], {})
            else:
                allocation = strategy["insight_allocation"].get("per_cluster") or strategy["insight_allocation"].get("per_domain")
            
            # Generate insights for this batch
            if allocation.get("kpi", 0) > 0:
                batch_kpis = self._plan_kpis_with_schema(target_count=allocation["kpi"])
                all_plans["kpi_plans"].extend(batch_kpis)
            
            if allocation.get("trend", 0) > 0:
                batch_trends = self._plan_trends_with_schema(target_count=allocation["trend"])
                all_plans["trend_plans"].extend(batch_trends)
            
            if allocation.get("distribution", 0) > 0:
                batch_dists = self._plan_distributions_with_schema(target_count=allocation["distribution"])
                all_plans["distribution_plans"].extend(batch_dists)
            
            if allocation.get("alert", 0) > 0:
                batch_alerts = self._plan_alerts_with_schema(target_count=allocation["alert"])
                all_plans["alert_plans"].extend(batch_alerts)
        
        all_plans["reasoning"] = strategy["reasoning"]
        all_plans["strategy"] = strategy["strategy_type"]
        
        logger.info(f"S Planned {len(all_plans['kpi_plans'])} KPIs, "
                   f"{len(all_plans['trend_plans'])} trends, "
                   f"{len(all_plans['distribution_plans'])} distributions, "
                   f"{len(all_plans['alert_plans'])} alerts")
        
        return all_plans
    
    def _plan_from_specifications(self, dashboard_specs: Dict) -> Dict[str, Any]:
        """
        Generate insight plans from dashboard specifications in business_context.json
        
        Args:
            dashboard_specs: Dashboard specifications from business_context.json
            
        Returns:
            Dictionary with kpi_plans, trend_plans, distribution_plans, alert_plans
        """
        logger.info(" Generating plans from dashboard specifications...")
        
        plans = {
            "kpi_plans": [],
            "trend_plans": [],
            "distribution_plans": [],
            "alert_plans": [],
            "strategy": "specification-based",
            "reasoning": "Using predefined dashboard specifications from business_context.json"
        }
        
        # Process KPI cards
        kpi_specs = dashboard_specs.get("kpi_cards", [])
        for kpi_spec in kpi_specs:
            plan = {
                "id": kpi_spec.get("id"),
                "title": kpi_spec.get("title"),
                "description": kpi_spec.get("description"),
                "table": kpi_spec.get("table"),
                "date_column": kpi_spec.get("date_column"),
                "metric_column": kpi_spec.get("metric_column"),
                "aggregation": kpi_spec.get("aggregation"),
                "filter_conditions": kpi_spec.get("filter_conditions", ""),
                "format": kpi_spec.get("format", "number"),
                "icon": kpi_spec.get("icon", "activity"),
                "color": kpi_spec.get("color"),
                "visual_config": kpi_spec.get("visual_config", {}),
                "chart_library": kpi_spec.get("chart_library", "recharts"),
                "requires_date_filter": kpi_spec.get("requires_date_filter", True),
                "sql_template": kpi_spec.get("sql_template", ""),
                "card_filters": kpi_spec.get("card_filters", [])
            }
            plans["kpi_plans"].append(plan)
        
        # Process Trend charts
        trend_specs = dashboard_specs.get("trend_charts", [])
        for trend_spec in trend_specs:
            plan = {
                "id": trend_spec.get("id"),
                "title": trend_spec.get("title"),
                "description": trend_spec.get("description"),
                "table": trend_spec.get("table"),
                "date_column": trend_spec.get("date_column"),
                "metric_column": trend_spec.get("metric_column"),
                "aggregation": trend_spec.get("aggregation"),
                "time_grouping": trend_spec.get("time_grouping", "monthly"),
                "filter_conditions": trend_spec.get("filter_conditions", ""),
                "format": trend_spec.get("format", "number"),
                "icon": trend_spec.get("icon", "trending-up"),
                "chart_type": trend_spec.get("chart_type", "line"),
                "color": trend_spec.get("color"),
                "visual_config": trend_spec.get("visual_config", {}),
                "chart_library": trend_spec.get("chart_library", "recharts"),
                "requires_date_filter": trend_spec.get("requires_date_filter", True),
                "sql_template": trend_spec.get("sql_template", ""),
                "group_by": trend_spec.get("group_by"),
                "card_filters": trend_spec.get("card_filters", [])
            }
            plans["trend_plans"].append(plan)
        
        # Process Distribution charts
        dist_specs = dashboard_specs.get("distribution_charts", [])
        for dist_spec in dist_specs:
            plan = {
                "id": dist_spec.get("id"),
                "title": dist_spec.get("title"),
                "description": dist_spec.get("description"),
                "table": dist_spec.get("table"),
                "date_column": dist_spec.get("date_column"),
                "category_column": dist_spec.get("category_column"),
                "category_join_table": dist_spec.get("category_join_table"),
                "category_join_column": dist_spec.get("category_join_column"),
                "category_join_conditions": dist_spec.get("category_join_conditions"),
                "category_display_column": dist_spec.get("category_display_column"),
                "metric_column": dist_spec.get("metric_column"),
                "aggregation": dist_spec.get("aggregation"),
                "limit": dist_spec.get("limit", 10),
                "filter_conditions": dist_spec.get("filter_conditions", ""),
                "format": dist_spec.get("format", "number"),
                "icon": dist_spec.get("icon", "bar-chart"),
                "chart_type": dist_spec.get("chart_type", "bar"),
                "color": dist_spec.get("color"),
                "visual_config": dist_spec.get("visual_config", {}),
                "chart_library": dist_spec.get("chart_library", "recharts"),
                "requires_date_filter": dist_spec.get("requires_date_filter", True),
                "sql_template": dist_spec.get("sql_template", ""),
                "card_filters": dist_spec.get("card_filters", [])
            }
            plans["distribution_plans"].append(plan)
        
        # Process Alert cards
        alert_specs = dashboard_specs.get("alert_cards", [])
        for alert_spec in alert_specs:
            plan = {
                "id": alert_spec.get("id"),
                "title": alert_spec.get("title"),
                "description": alert_spec.get("description"),
                "table": alert_spec.get("table"),
                "date_column": alert_spec.get("date_column"),
                "metric_column": alert_spec.get("metric_column"),
                "aggregation": alert_spec.get("aggregation"),
                "filter_conditions": alert_spec.get("filter_conditions", ""),
                "format": alert_spec.get("format", "number"),
                "icon": alert_spec.get("icon", "alert-circle"),
                "color": alert_spec.get("color"),
                "visual_config": alert_spec.get("visual_config", {}),
                "chart_type": alert_spec.get("chart_type"),
                "chart_library": alert_spec.get("chart_library", "recharts"),
                "requires_date_filter": alert_spec.get("requires_date_filter", False),
                "sql_template": alert_spec.get("sql_template", ""),
                "card_filters": alert_spec.get("card_filters", [])
            }
            plans["alert_plans"].append(plan)
        
        logger.info(f"S Generated {len(plans['kpi_plans'])} KPIs, "
                   f"{len(plans['trend_plans'])} trends, "
                   f"{len(plans['distribution_plans'])} distributions, "
                   f"{len(plans['alert_plans'])} alerts from specifications")
        
        return plans
    
    def _retrieve_table_schemas(self, tables: List[str]):
        """Populate table schemas for tables from JSON source"""
        for table in tables:
            # Use authoritative JSON schema if available
            # Handle potential DB prefix (e.g. franchises.sites_info -> sites_info)
            table_key = table
            if "." in table:
                table_key = table.split(".")[-1]
                
            if table_key in self.json_schema:
                table_def = self.json_schema[table_key]
                columns = {
                    "all": [c["name"] for c in table_def.get("columns", [])],
                    "date": [c["name"] for c in table_def.get("columns", []) if "date" in c["type"].lower() or "time" in c["type"].lower()],
                    "numeric": [c["name"] for c in table_def.get("columns", []) if any(t in c["type"].lower() for t in ["int", "float", "double", "decimal"])],
                    "categorical": [c["name"] for c in table_def.get("columns", []) if any(t in c["type"].lower() for t in ["char", "text", "string"])]
                }
                self.table_schemas[table] = columns
            else:
                # Fallback to analysis if not in JSON (should not happen for core tables)
                self.table_schemas[table] = self._parse_schema_columns("", table)
    
    def _parse_schema_columns(self, schema_text: str, table_name: str) -> Dict:
        """Parse columns from schema text"""
        columns = {
            "all": [],
            "date": [],
            "numeric": [],
            "categorical": []
        }
        
        # Extract from schema analysis
        time_dims = self.schema_analysis.get("time_dimensions", {})
        metrics = self.schema_analysis.get("metrics", {})
        dimensions = self.schema_analysis.get("dimensions", {})
        
        if table_name in time_dims:
            columns["date"] = time_dims[table_name]
            columns["all"].extend(time_dims[table_name])
        
        if table_name in metrics:
            columns["numeric"] = metrics[table_name]
            columns["all"].extend(metrics[table_name])
        
        if table_name in dimensions:
            columns["categorical"] = dimensions[table_name]
            columns["all"].extend(dimensions[table_name])
        
        return columns
    
    def _inject_business_metrics(self) -> List[Dict]:
        """
        Inject standard high-value business metrics
        
        These are metrics that should ALWAYS be included if the data supports them:
        - Lead Conversion Rate
        - Customer Churn Rate  
        - Monthly Recurring Revenue (MRR)
        - Average Contract Value
        """
        injected_metrics = []
        
        # Check if we have leads table with status
        leads_table = None
        for table in ["franchise_new.leads_all_business", "leads_all_business", "leads"]:
            if table in self.table_schemas:
                leads_table = table
                break
        
        if leads_table and "lead_status" in self.table_schemas.get(leads_table, {}).get("all", []):
            # Add Lead Conversion Rate
            date_col = self.table_schemas[leads_table].get("date", [None])[0]
            if date_col:
                injected_metrics.append({
                    "id": "lead_conversion_rate_actual",
                    "title": "Lead Conversion Rate",
                    "description": "Percentage of leads that successfully converted (SUCCESS status)",
                    "table": leads_table,
                    "metric_column": "lead_status",
                    "aggregation": "CUSTOM",
                    "date_column": date_col,
                    "custom_sql": f"SELECT ROUND((COUNT(CASE WHEN lead_status = 'SUCCESS' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) as total FROM {leads_table} WHERE {date_col} IS NOT NULL",
                    "format": "percentage",
                    "icon": "trending-up"
                })
        
        # Check if we have contracts table
        contracts_table = None
        for table in ["franchises.contracts", "contracts"]:
            if table in self.table_schemas:
                contracts_table = table
                break
        
        if contracts_table:
            schemas = self.table_schemas[contracts_table]
            date_col = schemas.get("date", [None])[0]
            
            # Add MRR if monthly_cap exists
            if "monthly_cap" in schemas.get("all", []) and date_col:
                injected_metrics.append({
                    "id": "monthly_recurring_revenue",
                    "title": "Monthly Recurring Revenue (MRR)",
                    "description": "Total monthly recurring revenue from active contracts",
                    "table": contracts_table,
                    "metric_column": "monthly_cap",
                    "aggregation": "SUM",
                    "date_column": date_col,
                    "filter_conditions": "status = 3 AND is_deleted = 0",
                    "format": "currency",
                    "icon": "dollar-sign"
                })
            
            # Add Average Contract Value if rate exists
            if "rate" in schemas.get("all", []) and date_col:
                injected_metrics.append({
                    "id": "average_contract_value",
                    "title": "Average Contract Value",
                    "description": "Average revenue per active contract",
                    "table": contracts_table,
                    "metric_column": "rate",
                    "aggregation": "AVG",
                    "date_column": date_col,
                    "filter_conditions": "status = 3 AND is_deleted = 0",
                    "format": "currency",
                    "icon": "credit-card"
                })
        
        # Check if we have customers table for churn
        customers_table = None
        for table in ["franchises.customers", "customers"]:
            if table in self.table_schemas:
                customers_table = table
                break
        
        if customers_table and "status" in self.table_schemas.get(customers_table, {}).get("all", []):
            date_col = self.table_schemas[customers_table].get("date", [None])[0]
            if date_col:
                # Add Customer Retention Rate
                injected_metrics.append({
                    "id": "customer_retention_rate",
                    "title": "Customer Retention Rate",
                    "description": "Percentage of customers who remain active",
                    "table": customers_table,
                    "metric_column": "active",
                    "aggregation": "CUSTOM",
                    "date_column": date_col,
                    "custom_sql": f"SELECT ROUND((COUNT(CASE WHEN active = 1 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) as total FROM {customers_table} WHERE {date_col} IS NOT NULL",
                    "format": "percentage",
                    "icon": "users"
                })
        
        logger.info(f" Injected {len(injected_metrics)} high-value business metrics")
        return injected_metrics
    
    def _plan_kpis_with_schema(self, target_count: int = 8) -> List[Dict]:
        """Plan KPIs using LLM reasoning + schema validation + business metric injection"""
        
        # STEP 1: Inject standard business metrics first
        injected_kpis = self._inject_business_metrics()
        
        # STEP 2: Calculate how many more KPIs we need from LLM
        # REQUEST BUFFER: Ask for 3 extra KPIs to handle validation failures
        base_needed = max(0, target_count - len(injected_kpis))
        remaining_count = base_needed + 3 if base_needed > 0 else 0
        
        if remaining_count == 0:
            logger.info(f"S Using {len(injected_kpis)} injected business metrics (no LLM planning needed)")
            return injected_kpis
        
        logger.info(f" Planning {remaining_count} additional KPIs via LLM (already have {len(injected_kpis)} injected)")
        
        # Context for LLM
        schema_summary = self._format_schema_for_llm()
        
        
        system_prompt = f"""You are an elite Business Intelligence expert creating a professional executive dashboard.
        
Your task: Analyze the complete schema and create EXACTLY {remaining_count} diverse, high-value KPI metrics.

IMPORTANT: We already have {len(injected_kpis)} standard business metrics. DO NOT duplicate these:
{chr(10).join(f"- {kpi['title']}" for kpi in injected_kpis)}
        
Requirements:
        - Each KPI must measure a different business aspect (no repetition)
        - Use meaningful column names with business context
        - Prefer columns with clear descriptions
        - Focus on: revenue, growth, efficiency, customer metrics, operational KPIs
        - Ensure each KPI has a clear business purpose"""
        
        user_prompt = f"""
        SCHEMA SUMMARY:
        {schema_summary}
        
        RULES:
        1. Plan EXACTLY {remaining_count} KPIs (we already have {len(injected_kpis)} injected).
        2. Focus on monetary values, counts, and averages.
        3. "symbol" should be one of: "$", "", "", "#", "%", "s" (seconds), "d" (days).
        4. "icon" must be one of: "dollar-sign", "users", "shopping-cart", "activity", "trending-up", "credit-card", "package", "bar-chart".
        5. "description" must be BUSINESS-VALUE focused, explaining WHY this metric matters to the business.
        6. DO NOT create conversion rates, churn rates, or MRR - we already have those.
        
        Return a JSON ARRAY of objects:
        [
            {{
                "id": "kpi_name",
                "title": "Human Readable Title",
                "description": "Business value explanation (e.g. 'Tracks customer acquisition efficiency')",
                "table": "database.table",
                "date_column": "col_name",
                "metric_column": "col_name",
                "aggregation": "SUM/COUNT/AVG",
                "symbol": "$",
                "icon": "activity",
                "x_axis_label": null,
                "y_axis_label": null,
                "reasoning": "Why this is important"
            }}
        ]
        """
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                agent_name="Dashboard-Planner-KPI",
                log_file="logs/dashboard_usage.csv"
            )
            llm_plans = self._parse_llm_json(response)
            
            # Validate plans against actual schema
            valid_llm_plans = []
            for plan in llm_plans:
                if self._validate_plan_columns(plan):
                    valid_llm_plans.append(plan)
            
             # Combine injected + LLM plans
            all_kpis = injected_kpis + valid_llm_plans
            logger.info(f"S Total KPIs Validated: {len(all_kpis)} ({len(injected_kpis)} injected + {len(valid_llm_plans)} viable from LLM)")
            
            # Return exactly the target count (or fewer if we don't have enough)
            return all_kpis[:target_count]
                
        except Exception as e:
            logger.warning(f"LLM KPI planning failed: {e}, using injected metrics only")
            return injected_kpis
    
    def _plan_trends_with_schema(self, target_count: int = 6) -> List[Dict]:
        """Plan trends using LLM reasoning + schema validation"""
        schema_summary = self._format_schema_for_llm()
        
        system_prompt = """You are an elite Data Scientist. Plan EXACTLY 6 meaningful time-series trends.
        
Requirement:
- Focus on growth, seasonality, and volume over time.
- Use valid date columns from the schema.
- Use diverse chart types (line, area, bar)."""
        
        user_prompt = f"""
        SCHEMA:
        {schema_summary}
        
        RULES:
        1. Plan EXACTLY 6 Trends.
        2. "chart_type" should be "line", "area", or "bar".
        3. "date_column" must be a valid date column.
        4. "description" must explain the BUSINESS INSIGHT this trend reveals.
        
        EXAMPLES:
        - BAD: "date_column": "join_date" (If column is named "joined_at")
        - GOOD: "date_column": "joined_at" (Exact match)
        
        Return JSON ARRAY:
        [
            {{
                "id": "trend_unique_id",
                "title": "Clear Business Title",
                "description": "Business insight (e.g. 'Shows seasonal demand patterns')",
                "table": "database.table",
                "date_column": "exact_date_column",
                "metric_column": "id",
                "aggregation": "COUNT",
                "time_grouping": "monthly",
                "time_period": "12_months",
                "chart_type": "area",
                "x_axis_label": "Month",
                "y_axis_label": "Total Leads",
                "reasoning": "Business value"
            }}
        ]
        
        CRITICAL RULE:
        - If the trend involves a breakout dimension, use NAME columns, not IDs.
        """
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                agent_name="Dashboard-Planner-Trend",
                log_file="logs/dashboard_usage.csv"
            )
            plans = self._parse_llm_json(response)
            
            valid_plans = []
            for plan in plans:
                if self._validate_plan_columns(plan):
                    valid_plans.append(plan)
            
            if valid_plans:
                return valid_plans
        except Exception as e:
            logger.warning(f"LLM Trend planning failed: {e}")
            
        return self._heuristic_trend_plan()

    def _plan_distributions_with_schema(self, target_count: int = 6) -> List[Dict]:
        """Plan distributions using LLM reasoning"""
        schema_summary = self._format_schema_for_llm()
        
        system_prompt = """You are an elite Data Scientist. Plan EXACTLY 6 diverse categorical distributions.
        
Requirement:
- Use different chart types (pie, donut, bar, treemap)
- Focus on high-value categorical columns (e.g., status, category, source, type)
- Do NOT repeat the same column/table combination
- Use EXACT column names from the schema"""
        
        user_prompt = f"""
        SCHEMA:
        {schema_summary}
        
        RULES:
        1. Plan EXACTLY 6 Distributions.
        2. "chart_type" should be "pie", "donut", "bar", or "treemap".
        3. "description" must explain what business question this distribution answers.
        4. **CRITICAL: ALWAYS use human-readable NAME/TITLE/STATUS columns for the category.**
           - Look for columns marked [NAME] or [CAT] in the schema.
           - NEVER use columns marked [ID] for the category.
           - If a table has both `site_id` [ID] and `site_name` [NAME], you MUST use `site_name`.
        5. "x_axis_label" and "y_axis_label" must be human-readable descriptions of the axes.
        
        EXAMPLES:
        - Use columns that represent meaningful business categories
        - Prefer text/name columns when available in the same table
        - ID and FK columns CAN be used - the SQL generation phase will automatically
          handle JOINs to get human-readable names from referenced tables
        - x_axis_label and y_axis_label should be human-readable descriptions

        Return JSON ARRAY:
        [
            {{
                "id": "dist_unique_id",
                "title": "Clear Business Title",
                "description": "Business question answered (e.g. 'Breakdown of revenue by region')",
                "table": "database.table",
                "category_column": "exact_column_name_NOT_ID",
                "metric_column": "id",
                "aggregation": "COUNT",
                "limit": 10,
                "chart_type": "donut",
                "x_axis_label": "Label for X Axis (Category)",
                "y_axis_label": "Label for Y Axis (Metric)",
                "reasoning": "Business value justification"
            }}
        ]
        """
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                agent_name="Dashboard-Planner-Distribution",
                log_file="logs/dashboard_usage.csv"
            )
            plans = self._parse_llm_json(response)
            
            valid_plans = []
            for plan in plans:
                # specific validation for distribution
                if not self._validate_plan_columns(plan):
                    continue
                
                # Check 1: Does column exist?
                if plan.get("category_column") not in self.table_schemas[plan["table"]]["all"]:
                    continue

                # Check 2: IS IT AN ID COLUMN? (We hate IDs for distribution)
                cat_col = plan.get("category_column", "").lower()
                is_id = cat_col.endswith("_id") or cat_col == "id" or cat_col.endswith("id")
                
                if is_id:
                    # AUTOMATIC FIX: Try to find a name column in the same table
                    table_schema = self.table_schemas[plan["table"]]
                    possible_names = [
                        c for c in table_schema["all"] 
                        if "name" in c.lower() or "title" in c.lower() or "label" in c.lower()
                    ]
                    
                    if possible_names:
                        # Swap it!
                        old_col = plan["category_column"]
                        new_col = possible_names[0] # Take first match
                        plan["category_column"] = new_col
                        plan["reasoning"] += f" (Auto-swapped {old_col} for {new_col} for better readability)"
                        logger.info(f" Auto-corrected distribution: Swapped {old_col} -> {new_col}")
                    else:
                        # If no name column, maybe reject it? 
                        # For now, let's keep it but log warning, unless strictly forbidden
                        logger.warning(f"[WARN] Distribution uses ID column {cat_col} and no name column found in {plan['table']}")

                valid_plans.append(plan)
            
            if valid_plans:
                return valid_plans
        except Exception as e:
            logger.warning(f"LLM Distribution planning failed: {e}")
            
        return self._heuristic_distribution_plan()

    def _plan_alerts_with_schema(self, target_count: int = 5) -> List[Dict]:
        """Plan alerts using LLM reasoning"""
        schema_summary = self._format_schema_for_llm()
        
        system_prompt = """You are an elite Business Analyst. Plan EXACTLY 5 critical business alerts.
        
Requirement:
- Focus on anomalies (drops in leads, high churn, low revenue)
- Use simple, robust SQL conditions
- Use EXACT column names from the schema
- Severity should match the business impact"""
        
        user_prompt = f"""
        SCHEMA:
        {schema_summary}
        
        RULES:
        1. Plan EXACTLY 5 Alerts.
        2. "severity" should be "high", "medium", or "low".
        3. Condition must be valid SQL WHERE clause fragment.
        4. "description" must explain the risk or opportunity being monitored.
        
        EXAMPLES:
        - BAD: "condition": "expiration_date < NOW()" (If column is named "end_date")
        - GOOD: "condition": "end_date < NOW()" (Exact match from schema)
        - BAD: "condition": "created_at > '2023-01-01'" (If column is named "creation_date")
        - GOOD: "condition": "creation_date > '2023-01-01'"
        
        Return JSON ARRAY:
        [
            {{
                "id": "alert_unique_id",
                "title": "Alert Title",
                "description": "Risk/Opportunity description",
                "table": "database.table",
                "condition": "column_name > 100",
                "aggregation": "COUNT",
                "severity": "high",
                "x_axis_label": null,
                "y_axis_label": null,
                "reasoning": "Why this matters"
            }}
        ]
        """
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_prompt,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                agent_name="Dashboard-Planner-Alert",
                log_file="logs/dashboard_usage.csv"
            )
            plans = self._parse_llm_json(response)
            # Basic validation
            valid_plans = [p for p in plans if p.get("table") in self.table_schemas]
            if valid_plans:
                return valid_plans
        except Exception as e:
            logger.warning(f"LLM Alert planning failed: {e}")
            
        return self._heuristic_alert_plan()

    def _format_schema_for_llm(self) -> str:
        """Format table schemas for LLM context using authoritative JSON"""
        lines = []
        lines.append("=" * 80)
        lines.append("REFERENCE DATABASE SCHEMA")
        lines.append("=" * 80)
        lines.append("")
        
        for table in self.table_schemas.keys():
            # Use JSON schema if available
            # Handle potential DB prefix (e.g. franchises.sites_info -> sites_info)
            table_key = table
            if "." in table:
                table_key = table.split(".")[-1]
            
            if hasattr(self, 'json_schema') and table_key in self.json_schema:
                t_def = self.json_schema[table_key]
                lines.append(f"TABLE: {table}")
                lines.append(f"PURPOSE: {t_def.get('purpose', 'No description')}")
                lines.append("-" * 40)
                
                # Columns
                lines.append("COLUMNS:")
                for col in t_def.get("columns", []):
                    desc = f" - {col.get('description')}" if col.get('description') else ""
                    # Mark column type to help LLM choose wisely
                    col_name_lower = col['name'].lower()
                    marker = ""
                    if col_name_lower == 'id' or col_name_lower.endswith('_id'):
                        marker = " [ID]"
                    elif any(kw in col_name_lower for kw in ['name', 'title', 'label']):
                        marker = " [NAME]"
                    elif any(kw in col_name_lower for kw in ['status', 'type', 'category', 'source']):
                        marker = " [CAT]"
                    lines.append(f"  - {col['name']} ({col['type']}){marker}{desc}")
                
                # Foreign Keys
                if t_def.get("foreign_keys"):
                    lines.append("RELATIONSHIPS:")
                    for fk in t_def.get("foreign_keys", []):
                        lines.append(f"  - {fk['column']} -> {fk['references']}")
                
                lines.append("")
            else:
                # Fallback to basic info if JSON missing (should not happen for core tables)
                schema = self.table_schemas[table]
                lines.append(f"TABLE: {table}")
                lines.append(f"  - Numeric: {', '.join(schema.get('numeric', [])[:5])}...")
                lines.append(f"  - Date: {', '.join(schema.get('date', []))}")
                
        lines.append("\n" + "=" * 80)
        lines.append("INSTRUCTIONS:")
        lines.append("- Use EXACT column names from the schema above.")
        lines.append("- Do NOT invent columns that are not listed.")
        lines.append("- Use foreign keys to join tables for richer insights.")
        lines.append("- Ensure KPIs are diverse and meaningful.")
        lines.append("- For distribution categories: PREFER columns marked [NAME] or [CAT] over columns marked [ID].")
        lines.append("=" * 80)
        
        lines.append("=" * 80)
        
        # Inject Business Context if available
        if hasattr(self, 'business_context') and self.business_context:
            bs = self.business_context
            lines.append("BUSINESS CONTEXT & RULES:")
            lines.append(f"Business Name: {bs.get('business_name', 'Unknown')}")
            lines.append(f"Description: {bs.get('description', '')}")
            lines.append("=" * 80)
        
        schema_str = "\n".join(lines)
        logger.debug(f"Generated Schema Context for LLM:\n{schema_str}")
        return schema_str

    def _parse_llm_json(self, response: str) -> List[Dict]:
        """Parse JSON response from LLM"""
        try:
            # Strip markdown code blocks if present
            clean_resp = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_resp)
        except:
            return []

    def _validate_plan_columns(self, plan: Dict) -> bool:
        """Ensure planned columns actually exist"""
        table = plan.get("table")
        if table not in self.table_schemas:
            return False
            
        schema = self.table_schemas[table]
        all_cols = schema["all"]
        
        # Check metric column
        if plan.get("metric_column") != "*" and plan.get("metric_column") not in all_cols:
            return False
            
        # Check date column
        if plan.get("date_column") and plan.get("date_column") not in all_cols:
            return False
            
        return True

    def _heuristic_kpi_plan(self) -> List[Dict]:
        """Original heuristic logic as fallback"""
        plans = []
        for table, schema in list(self.table_schemas.items())[:5]:
            if not schema["date"] or not schema["numeric"]:
                continue
            date_col = schema["date"][0]
            metric_col = schema["numeric"][0] if schema["numeric"] else "id"
            plan = {
                "id": f"kpi_{table.split('.')[-1]}_total",
                "title": f"Total {table.split('.')[-1].replace('_', ' ').title()}",
                "description": f"Total count of records in {table}",
                "table": table,
                "date_column": date_col,
                "metric_column": metric_col,
                "aggregation": "COUNT",
                "filter_conditions": f"{date_col} IS NOT NULL",
                "icon": "layers",
                "reasoning": f"Primary metric for {table}"
            }
            plans.append(plan)
        return plans

    def _heuristic_trend_plan(self) -> List[Dict]:
        """Fallback heuristic trends"""
        plans = []
        for table, schema in list(self.table_schemas.items())[:5]:
            if not schema["date"]:
                continue
            date_col = schema["date"][0]
            metric_col = schema["numeric"][0] if schema["numeric"] else "*"
            plan = {
                "id": f"trend_{table.split('.')[-1]}_monthly",
                "title": f"Monthly {table.split('.')[-1].replace('_', ' ').title()} Trend",
                "description": f"Monthly trend for {table}",
                "table": table,
                "date_column": date_col,
                "metric_column": metric_col,
                "aggregation": "COUNT",
                "time_grouping": "monthly",
                "time_period": "12_months",
                "x_axis_label": "Month",
                "y_axis_label": f"Total {table.split('.')[-1].replace('_', ' ').title()}",
                "reasoning": f"Shows growth pattern for {table}"
            }
            plans.append(plan)
        return plans

    def _heuristic_distribution_plan(self) -> List[Dict]:
        """Fallback heuristic distributions"""
        plans = []
        for table, schema in list(self.table_schemas.items())[:5]:
            if not schema["categorical"]:
                continue
            
            # Smart selection of category column (avoid IDs)
            cat_col = schema["categorical"][0]
            for col in schema["categorical"]:
                lower_col = col.lower()
                if any(x in lower_col for x in ["name", "title", "desc", "type", "status", "source", "region", "city"]):
                    cat_col = col
                    break
            
            plan = {
                "id": f"dist_{table.split('.')[-1]}_{cat_col}",
                "title": f"Top 10 by {cat_col.replace('_', ' ').title()}",
                "description": f"Distribution by {cat_col}",
                "table": table,
                "category_column": cat_col,
                "metric_column": "id",
                "aggregation": "COUNT",
                "limit": 10,
                "x_axis_label": cat_col.replace('_', ' ').title(),
                "y_axis_label": "Count",
                "reasoning": f"Shows distribution across {cat_col}"
            }
            plans.append(plan)
        return plans

    def _heuristic_alert_plan(self) -> List[Dict]:
        """Fallback heuristic alerts"""
        plans = []
        for table, schema in list(self.table_schemas.items())[:3]:
            if not schema["numeric"]:
                continue
            numeric_col = schema["numeric"][0]
            plan = {
                "id": f"alert_{table.split('.')[-1]}_low_{numeric_col}",
                "title": f"Low {numeric_col.replace('_', ' ').title()}",
                "description": f"Records with low {numeric_col}",
                "table": table,
                "condition": f"{numeric_col} < 10",
                "aggregation": "COUNT",
                "reasoning": f"Identifies low {numeric_col} records"
            }
            plans.append(plan)
        return plans
