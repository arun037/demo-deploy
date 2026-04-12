"""
Dashboard Intelligence Agent - ENHANCED VERSION 3.0

Features:
- 20+ intelligent insights (6 KPI + 5 Trend + 5 Distribution + 4 Alert)
- Dynamic queries with fresh data
- Anomaly detection
- Predictive analytics
- Period comparisons
- Smart table selection with quality scoring
- Intelligent caching with metadata
- Adaptive learning from query success/failure
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from backend.core.logger import logger
from backend.config import Config
from .enhanced_intelligence import EnhancedDashboardIntelligence
from .intelligent_cache_manager import IntelligentCacheManager
from .reasoning.schema_analyzer import SchemaAnalyzer
from .reasoning.data_explorer import DataExplorer
from .reasoning.schema_aware_planner import SchemaAwarePlanner
from .reasoning.query_generator import QueryGenerator
from .reasoning.dashboard_validator import DashboardValidator


class DashboardIntelligence:
    """Production-Ready Dashboard Intelligence with Advanced Analytics"""
    
    def __init__(self, llm_client, rag_retriever, graph_analysis, db_manager):
        self.llm = llm_client
        self.rag = rag_retriever
        self.graph = graph_analysis
        self.db = db_manager
        
        # Initialize enhanced intelligence
        self.enhanced_intelligence = EnhancedDashboardIntelligence(
            llm_client, rag_retriever, db_manager
        )
        
        # Initialize intelligent cache manager
        self.cache_manager = IntelligentCacheManager()
        
        logger.info(" Enhanced Dashboard Intelligence initialized with smart features")
    
    
    def generate_dashboard(self, schema_json: List[Dict]) -> Dict[str, Any]:
        """
        Generate dashboard with adaptive intelligence and comprehensive validation
        
        Pipeline:
        1. Schema Analysis & Data Exploration
        2. Adaptive Strategic Planning (scales from 10 to 1000+ tables)
        3. Pre-Generation Validation (prevent errors upfront)
        4. Query Generation & Testing
        5. Post-Generation Validation (ensure quality)
        6. Dashboard Coherence Validation
        7. Iterative Refinement (fix issues if needed)
        """
        logger.info(" Starting ADAPTIVE INTELLIGENT dashboard generation...")
        logger.info("=" * 80)
        
        # Phase 1: Schema Analysis & Data Exploration
        logger.info(" Phase 1: Schema Analysis & Data Exploration")
        
        analyzer = SchemaAnalyzer(schema_json, self.llm)
        schema_analysis = analyzer.analyze_schema()
        
        explorer = DataExplorer(self.db, schema_analysis)
        data_exploration = explorer.explore_data()
        
        # NEW: Generate AI-powered dynamic queries for RAG retrieval
        logger.info(" Generating AI-powered category queries...")
        try:
            from .reasoning.dynamic_query_generator import DynamicQueryGenerator
            
            # Convert schema_json list to dict for query generator
            schema_dict = {t["table_name"]: t for t in schema_json}
            
            query_generator = DynamicQueryGenerator(
                self.llm,
                schema_analysis,
                schema_dict
            )
            dynamic_queries = query_generator.generate_category_queries()
            
            # Set dynamic queries in RAG retriever
            self.rag.set_dynamic_queries(dynamic_queries)
            logger.info("S RAG retriever configured with AI-generated queries")
            
        except Exception as e:
            logger.warning(f"[WARN] Failed to generate dynamic queries: {e}")
            logger.info(" Falling back to static queries")
        
        # Phase 2: Adaptive Strategic Planning
        logger.info(" Phase 2: Adaptive Strategic Planning")
        planner = SchemaAwarePlanner(self.llm, self.rag, schema_analysis, data_exploration)
        insight_plans = planner.plan_insights()  # Uses adaptive coverage engine
        
        logger.info(f" Strategy: {insight_plans.get('strategy', 'unknown').upper()}")
        logger.info(f" {insight_plans.get('reasoning', '')}")
        
        # Phase 3: Pre-Generation Validation
        logger.info("[OK] Phase 3: Pre-Generation Validation")
        from .reasoning.insight_quality_validator import InsightPlanValidator
        
        plan_validator = InsightPlanValidator(schema_json, planner.table_schemas)
        pre_validation_report = plan_validator.validate_all_plans(insight_plans)
        
        logger.info(f" Pre-validation: {pre_validation_report['valid_plans']}/{pre_validation_report['total_plans']} plans passed")
        
        if pre_validation_report['invalid_plans'] > 0:
            logger.warning(f"[WARN]  Rejected {pre_validation_report['invalid_plans']} invalid plans")
        
        # Use only validated plans
        validated_plans = pre_validation_report["validated_plans"]
        
        # Phase 4: Query Generation & Testing
        logger.info(" Phase 4: Query Generation & Execution Testing")
        generator = QueryGenerator(self.llm, self.db)
        
        generated_insights = []
        generation_failures = []
        
        for category in ["kpi", "trend", "distribution", "alert"]:
            plan_key = f"{category}_plans"
            category_plans = validated_plans.get(plan_key, [])
            
            logger.info(f"  Generating {len(category_plans)} {category} insights...")
            
            for plan in category_plans:
                try:
                    # Use default period of all for initial generation
                    # Frontend will apply actual period filter when fetching data
                    query_result = generator.generate_query(plan, category, period="all")
                    
                    if query_result and query_result.get("tested"):
                        generated_insights.append(query_result)
                    else:
                        generation_failures.append({
                            "id": plan.get("id"),
                            "category": category,
                            "reason": "Query generation or testing failed"
                        })
                except Exception as e:
                    logger.error(f"Error generating query for {plan.get('id')}: {e}")
                    generation_failures.append({
                        "id": plan.get("id"),
                        "category": category,
                        "reason": str(e)
                    })
        
        logger.info(f"S Generated {len(generated_insights)} insights")
        if generation_failures:
            logger.warning(f"[WARN]  {len(generation_failures)} generation failures")
        
        # Phase 5: Post-Generation Validation
        logger.info("[OK] Phase 5: Post-Generation Validation")
        from .reasoning.insight_quality_validator import InsightExecutionValidator
        
        execution_validator = InsightExecutionValidator(self.db)
        post_validation_report, validated_insights = execution_validator.validate_all_insights(generated_insights)
        
        # Phase 6: Dashboard Coherence Validation
        logger.info("[OK] Phase 6: Dashboard Coherence Validation")
        coherence_validator = DashboardValidator(self.llm)
        coherence_validation = coherence_validator.validate_dashboard(validated_insights, schema_analysis)
        
        # Phase 7: Iterative Refinement (if needed)
        coverage_score = coherence_validation.get("coverage_score", 100)
        if coverage_score < 70 and generation_failures:
            logger.warning(f"[WARN]  Coverage score low ({coverage_score}%), attempting refinement...")
            refined_insights = self._attempt_refinement(
                validated_insights,
                generation_failures[:5],  # Try to fix top 5 failures
                planner,
                generator
            )
            validated_insights.extend(refined_insights)
            logger.info(f"S Refinement added {len(refined_insights)} insights")
        
        # Final Summary
        logger.info("=" * 80)
        logger.info(f" DASHBOARD GENERATION COMPLETE")
        logger.info(f" Total Insights: {len(validated_insights)}")
        logger.info(f"[OK] All Tested: {all(i.get('tested') for i in validated_insights)}")
        logger.info(f" Coverage Score: {coverage_score}%")
        logger.info("=" * 80)
        
        # Load filter_definitions from business_context.json for frontend use
        filter_definitions = {}
        dashboard_title = f"{schema_analysis.get('business_domain', 'Analytics')} Dashboard"
        dashboard_description = "Real-time franchise performance intelligence"
        try:
            import os
            bc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "business_context.json")
            with open(bc_path, "r") as _f:
                _bc = json.load(_f)
            filter_definitions = _bc.get("dashboard", {}).get("filter_definitions", {})
            _dash = _bc.get("dashboard", {})
            if _bc.get("business_name"):
                dashboard_title = f"{_bc['business_name']} Analytics"
            if _dash.get("description"):
                dashboard_description = _dash["description"]
        except Exception:
            pass

        return {
            "title": dashboard_title,
            "description": dashboard_description,
            "insights": validated_insights,
            "filter_definitions": filter_definitions,
            "dashboard_metadata": {
                "title": dashboard_title,
                "description": dashboard_description,
                "generated_at": datetime.now().isoformat()
            },
            "generated_at": datetime.now().isoformat(),
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "schema_hash": self._hash_schema(schema_json),
                "generation_engine": "adaptive-intelligence-v3",
                "strategy": {
                    "type": insight_plans.get("strategy"),
                    "reasoning": insight_plans.get("reasoning")
                },
                "validation": {
                    "pre_generation": {
                        "total_plans": pre_validation_report["total_plans"],
                        "valid_plans": pre_validation_report["valid_plans"],
                        "rejected_plans": len(pre_validation_report["rejected_plans"])
                    },
                    "post_generation": {
                        "total_insights": post_validation_report["total_insights"],
                        "valid_insights": post_validation_report["valid_insights"],
                        "invalid_insights": post_validation_report["invalid_insights"]
                    },
                    "coherence": coherence_validation
                },
                "failures": {
                    "generation_failures": len(generation_failures),
                    "details": generation_failures
                },
                "data_quality": data_exploration.get("data_quality", {})
            }
        }
    
    def _attempt_refinement(self, existing_insights: List[Dict], failures: List[Dict],
                           planner, generator) -> List[Dict]:
        """
        Attempt to fix failed insights through iterative refinement
        
        Human-like behavior: If something doesn't work, try a different approach
        """
        logger.info(" Starting iterative refinement...")
        
        refined_insights = []
        
        for failure in failures:
            failure_id = failure.get("id")
            category = failure.get("category")
            
            logger.info(f"  Retrying: {failure_id}")
            
            # Strategy: Try with a different table or simpler aggregation
            try:
                # Get alternative plan (simplified version)
                alternative_plan = self._create_fallback_plan(failure, category, planner)
                
                if alternative_plan:
                    query_result = generator.generate_query(alternative_plan, category, period="all")
                    
                    if query_result and query_result.get("tested"):
                        refined_insights.append(query_result)
                        logger.info(f"  S Successfully refined {failure_id}")
                    else:
                        logger.warning(f"  F Refinement failed for {failure_id}")
            except Exception as e:
                logger.error(f"  F Refinement error for {failure_id}: {e}")
        
        return refined_insights
    
    def _create_fallback_plan(self, failure: Dict, category: str, planner) -> Optional[Dict]:
        """
        Create a simpler fallback plan for failed insight
        
        Uses conservative approach: COUNT(*) instead of complex aggregations
        """
        # Get a high-scoring table with date column
        tables_with_dates = planner.schema_analysis.get("time_dimensions", {})
        
        if not tables_with_dates:
            return None
        
        # Pick first available table with data
        for table in tables_with_dates.keys():
            date_cols = tables_with_dates[table]
            if date_cols:
                return {
                    "id": f"{failure.get('id')}_fallback",
                    "title": f"Total Records - {table.split('.')[-1].title()}",
                    "description": f"Total count of records in {table}",
                    "table": table,
                    "metric_column": "*",
                    "aggregation": "COUNT",
                    "date_column": date_cols[0],
                    "filter_conditions": f"{date_cols[0]} IS NOT NULL"
                }
        
        return None
    
    def _generate_kpi_insights(self, schema_json: List[Dict], count: int = 6) -> List[Dict]:
        """Generate 6 KPI insights with intelligent selection"""
        logger.info(f" Generating {count} KPI insights...")
        
        kpi_context = self.rag.retrieve_for_category("kpi", top_k=10)
        context_str = self._format_context(kpi_context, schema_json)
        
        system_prompt = f"""You are an Expert SQL Engineer creating KPI metrics for an executive dashboard.

Schema:
{context_str}

 CRITICAL: USE EXACT DATABASE-QUALIFIED TABLE NAMES FROM SCHEMA
- You MUST use database-qualified table names EXACTLY as shown in the "VALID TABLE NAMES" list above
- Format: database.table_name (e.g., franchises.contracts, franchise_new.sites_info)
- DO NOT use table names without database prefix (e.g., just 'contracts')
- DO NOT shorten, modify, or abbreviate table names
- Example: Use 'franchises.contracts' NOT 'contracts'
- Example: Use 'franchises.customers' NOT 'customers'
- Wrong table names will cause SQL errors and broken dashboards

TASK: Generate {count} KEY PERFORMANCE INDICATORS (KPIs)

Focus on BUSINESS-CRITICAL metrics:
1. Total monetary values (revenue, spend, cost)
2. Volume metrics (order count, requisition count)
3. Efficiency rates (fulfillment rate, on-time delivery)
4. Inventory health (active items, stock levels)
5. Vendor performance (vendor count, avg lead time)
6. Financial ratios (avg order value, cost per unit)

 MANDATORY DATE COLUMN REQUIREMENT:
1. **EVERY KPI MUST use a table that has a DATE column** (marked with [DATE_COLUMN] in schema)
2. Look for columns containing: 'date', 'Date', '_dt', '_DT', 'time', 'Time', 'created', 'updated'
3. **REJECT tables without date columns** - they cannot be filtered by time period
4. The date column will be used by the frontend filter system (7d, 30d, 3m, 12m, all)
5. Common date columns in this schema: PO_Date, Receipt_DT, Req_Date, INV_Request_Date, RECEIPT_DT

SQL QUALITY RULES (STRICT):
1. Each KPI SQL must return EXACTLY ONE ROW with ONE NUMERIC COLUMN
2. Use SUM, COUNT, AVG, ROUND for calculations
3. **HANDLE NULLS ROBUSTLY**: Use COALESCE(SUM(col), 0) to avoid returning NULL
4. Verify EVERY column exists in the schema provided above
5. Keep queries under 5 lines for performance
6. Use proper MySQL syntax. **HANDLE DATE FORMATS ROBUSTLY:**
   - If date format is like '15/01/24', use STR_TO_DATE(col, '%d/%m/%y')
   - If unsure, use COALESCE(STR_TO_DATE(col, '%d/%m/%y'), STR_TO_DATE(col, '%Y-%m-%d'))
7. Add meaningful WHERE clauses for filtering (status, flags, etc.)
8. **Test your column names against the schema** - wrong column = broken dashboard

EXAMPLES:

[OK] Total Aggregation with Date Column:
SELECT ROUND(SUM(numeric_column), 2) as total FROM table_with_date WHERE status = 'active'

[OK] Count Unique Items from Dated Table:
SELECT COUNT(DISTINCT id_column) as total FROM table_with_date_column

[OK] Efficiency Rate (Dated Table):
SELECT ROUND(AVG(CASE WHEN status = 'success' THEN 100 ELSE 0 END), 1) as rate FROM table_with_date

[OK] Conditional Count (Dated Table):
SELECT COUNT(DISTINCT id_column) as total FROM table_with_date WHERE status = 'active'

[OK] Average Value (Dated Table):
SELECT ROUND(AVG(numeric_column), 2) as avg_value FROM table_with_date WHERE amount > 0

Output ONLY valid JSON array with {count} objects:
[
  {{
    "id": "kpi_total_revenue",
    "title": "Total Revenue",
    "description": "Total revenue from all completed orders",
    "sql": "SELECT ROUND(SUM(total_amount), 2) as total FROM orders WHERE status = 'completed'",
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

        user_query = f"Generate {count} diverse KPI insights covering spend, volume, efficiency, inventory, vendors, and financial metrics. Prioritize queries with date columns for time-based filtering."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=180,
                agent_name="Dashboard-KPI",
                log_file="logs/dashboard_usage.csv"
            )
            
            insights = self._parse_json_response(response)
            logger.info(f"S Generated {len(insights)} KPI insights")
            return insights[:count]
            
        except Exception as e:
            logger.error(f"Error generating KPI insights: {e}")
            return []
    
    def _generate_trend_insights(self, schema_json: List[Dict], count: int = 5) -> List[Dict]:
        """Generate 5 trend insights with time-series analysis"""
        logger.info(f" Generating {count} trend insights...")
        
        trend_context = self.rag.retrieve_for_category("trend", top_k=8)
        context_str = self._format_context(trend_context, schema_json)
        
        system_prompt = f"""You are an Expert SQL Engineer creating trend analysis for a dashboard.

Schema:
{context_str}

 CRITICAL: USE EXACT DATABASE-QUALIFIED TABLE NAMES FROM SCHEMA
- You MUST use database-qualified table names EXACTLY as shown in the "VALID TABLE NAMES" list above
- Format: database.table_name (e.g., franchises.contracts, franchise_new.sites_info)
- DO NOT use table names without database prefix
- DO NOT shorten, modify, or abbreviate table names
- Example: Use 'franchises.contracts' NOT 'contracts'
- Example: Use 'franchises.customers' NOT 'customers'
- Wrong table names will cause SQL errors and broken dashboards

TASK: Generate {count} TREND INSIGHTS showing changes over time

Focus on TIME-SERIES patterns:
1. Monthly spending trends
2. Order volume over time
3. Fulfillment rate trends
4. Inventory movement patterns
5. Seasonal variations

CRITICAL RULES:
1. SQL must return TWO columns: period (date/text) and metric (number)
2. **HANDLE DATE FORMATS ROBUSTLY:**
   - Use COALESCE(STR_TO_DATE(date_col, '%d/%m/%y'), STR_TO_DATE(date_col, '%Y-%m-%d')) to parse dates.
   - Example: DATE_FORMAT(COALESCE(STR_TO_DATE(date_col, '%d/%m/%y'), STR_TO_DATE(date_col, '%Y-%m-%d')), '%Y-%m')
3. Use GROUP BY for time aggregations
4. **NEVER GROUP BY ID**: If grouping by a secondary dimension, USE THE NAME COLUMN (e.g., `site_name`, `vendor_name`). **NEVER use `site_id` or `vendor_id`**.
5. Limit to last 24 months for broader coverage
6. Order by period ASC
7. Keep queries under 10 lines

EXAMPLES:

[OK] Monthly Trend:
SELECT 
    DATE_FORMAT(STR_TO_DATE(date_column, '%Y-%m-%d'), '%Y-%m') as period,
    ROUND(SUM(numeric_column), 2) as total
FROM table_name
WHERE STR_TO_DATE(date_column, '%Y-%m-%d') >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY period
ORDER BY period

[OK] Rate Trend Over Time:
SELECT 
    DATE_FORMAT(STR_TO_DATE(date_column, '%Y-%m-%d'), '%Y-%m') as period,
    ROUND(AVG(CASE WHEN status = 'success' THEN 100 ELSE 0 END), 1) as rate
FROM table_name
WHERE STR_TO_DATE(date_column, '%Y-%m-%d') >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY period
ORDER BY period

Output ONLY valid JSON array with {count} objects:
[
  {{
    "id": "trend_monthly_revenue",
    "title": "Monthly Revenue Trend",
    "description": "Revenue by month over last 12 months",
    "sql": "SELECT DATE_FORMAT(...) as period, SUM(...) as total FROM ... WHERE ... GROUP BY period ORDER BY period",
    "viz_type": "line_chart",
    "category": "trend",
    "refresh_interval": "daily",
    "icon": "trending-up",
    "format": "currency"
  }}
]

viz_type: line_chart or bar_chart
format: currency, number, or percentage

NO markdown, ONLY JSON array."""

        user_query = f"Generate {count} trend insights showing monthly patterns, growth rates, and seasonal variations. Focus on tables with strong date columns."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=180
            )
            
            insights = self._parse_json_response(response)
            logger.info(f"S Generated {len(insights)} trend insights")
            return insights[:count]
            
        except Exception as e:
            logger.error(f"Error generating trend insights: {e}")
            return []
    
    def _generate_distribution_insights(self, schema_json: List[Dict], count: int = 5) -> List[Dict]:
        """Generate 5 distribution insights with rankings"""
        logger.info(f" Generating {count} distribution insights...")
        
        dist_context = self.rag.retrieve_for_category("distribution", top_k=8)
        context_str = self._format_context(dist_context, schema_json)
        
        system_prompt = f"""You are an Expert SQL Engineer creating distribution analysis for a dashboard.

Schema:
{context_str}

 CRITICAL: USE EXACT DATABASE-QUALIFIED TABLE NAMES FROM SCHEMA
- You MUST use database-qualified table names EXACTLY as shown in the "VALID TABLE NAMES" list above
- Format: database.table_name (e.g., franchises.contracts, franchise_new.sites_info)
- DO NOT use table names without database prefix
- DO NOT shorten, modify, or abbreviate table names
- Example: Use 'franchises.contracts' NOT 'contracts'
- Wrong table names will cause SQL errors and broken dashboards

TASK: Generate {count} DISTRIBUTION INSIGHTS showing breakdowns and rankings

Focus on CATEGORICAL breakdowns:
1. Top vendors by spend/orders
2. Top item categories by volume
3. Top departments by requisitions
4. Spend distribution by business unit
5. Order distribution by status

CRITICAL RULES:
1. SQL must return TWO columns: category (text) and value (number)
2. **Use HUMAN-READABLE NAME columns for the category (e.g., `vendor_name`, `product_title`, `site_name`).**
3. **NEVER use ID columns (e.g., `vendor_id`, `site_id`) for the category.** IDs are useless in charts.
4. Use GROUP BY for aggregations
5. Use ORDER BY DESC and LIMIT 10
6. Filter out NULL categories
7. Keep queries under 8 lines

EXAMPLES:

[OK] Top Categories:
SELECT 
    category_column as category,
    COUNT(DISTINCT id_column) as total
FROM table_name
WHERE category_column IS NOT NULL
GROUP BY category_column
ORDER BY total DESC
LIMIT 10

[OK] Value by Segment:
SELECT 
    segment_column as category,
    ROUND(SUM(numeric_column), 2) as total
FROM table_name
WHERE segment_column IS NOT NULL
GROUP BY segment_column
ORDER BY total DESC
LIMIT 10

Output ONLY valid JSON array with {count} objects:
[
  {{
    "id": "dist_top_vendors",
    "title": "Top 10 Vendors by Orders",
    "description": "Vendors with highest number of orders",
    "sql": "SELECT vendor_name as category, COUNT(*) as total FROM ... WHERE ... GROUP BY ... ORDER BY total DESC LIMIT 10",
    "viz_type": "bar_chart",
    "category": "distribution",
    "refresh_interval": "hourly",
    "icon": "bar-chart",
    "format": "number"
  }}
]

viz_type: bar_chart or pie_chart
format: currency or number

NO markdown, ONLY JSON array."""

        user_query = f"Generate {count} distribution insights showing top 10 breakdowns across vendors, categories, departments, and business units. Use diverse categorical dimensions."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=180,
                agent_name="Dashboard-Distribution",
                log_file="logs/dashboard_usage.csv"
            )
            
            insights = self._parse_json_response(response)
            logger.info(f"S Generated {len(insights)} distribution insights")
            return insights[:count]
            
        except Exception as e:
            logger.error(f"Error generating distribution insights: {e}")
            return []
    
    def _generate_alert_insights(self, schema_json: List[Dict], count: int = 4) -> List[Dict]:
        """Generate 4 alert insights with actionable warnings"""
        logger.info(f"[WARN]  Generating {count} alert insights...")
        
        alert_context = self.rag.retrieve_for_category("alert", top_k=6)
        context_str = self._format_context(alert_context, schema_json)
        
        system_prompt = f"""You are an Expert SQL Engineer creating alert/monitoring insights for a dashboard.

Schema:
{context_str}

 CRITICAL: USE EXACT DATABASE-QUALIFIED TABLE NAMES FROM SCHEMA
- You MUST use database-qualified table names EXACTLY as shown in the "VALID TABLE NAMES" list above
- Format: database.table_name (e.g., franchises.contracts, franchise_new.sites_info)
- DO NOT use table names without database prefix
- DO NOT shorten, modify, or abbreviate table names
- Example: Use 'franchises.contracts' NOT 'contracts'
- Wrong table names will cause SQL errors and broken dashboards

TASK: Generate {count} ALERT INSIGHTS highlighting issues needing attention

Focus on ACTIONABLE alerts:
1. Low stock items (quantity < threshold)
2. Unfulfilled requisitions (pending > X days)
3. Overdue purchase orders
4. High-value pending approvals

CRITICAL RULES:
1. For kpi_card: SQL returns ONE ROW with ONE NUMBER (count)
2. For table: SQL returns multiple rows with relevant columns (LIMIT 50)
3. **INCLUDE NAMES**: When listing items, include their NAME column (e.g., `item_name`, `po_number`), NOT just the ID.
4. Use WHERE clauses to filter for alert conditions
5. Keep queries simple (max 6 lines)
6. Make alerts actionable

EXAMPLES:

[OK] Threshold Alert (kpi_card):
SELECT COUNT(*) as count 
FROM table_name
WHERE numeric_column < 10

[OK] Critical Items List (table):
SELECT 
    id,
    name,
    date_col,
    status
FROM table_name
WHERE status IN ('Critical', 'Pending')
ORDER BY date_col ASC
LIMIT 50

Output ONLY valid JSON array with {count} objects:
[
  {{
    "id": "alert_low_stock",
    "title": "Low Stock Items",
    "description": "Items with available quantity below 10 units",
    "sql": "SELECT COUNT(*) as count FROM ... WHERE quantity < 10",
    "viz_type": "kpi_card",
    "category": "alert",
    "refresh_interval": "realtime",
    "icon": "alert-circle",
    "format": "number"
  }}
]

viz_type: kpi_card or table
format: number

NO markdown, ONLY JSON array."""

        user_query = f"Generate {count} alert insights for critical items: low stock, unfulfilled orders, overdue items, pending approvals. Make alerts actionable and specific."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=180,
                agent_name="Dashboard-Alert",
                log_file="logs/dashboard_usage.csv"
            )
            
            insights = self._parse_json_response(response)
            logger.info(f"S Generated {len(insights)} alert insights")
            return insights[:count]
            
        except Exception as e:
            logger.error(f"Error generating alert insights: {e}")
            return []
    
    def _format_context(self, context: List[Dict], schema_json: List[Dict]) -> str:
        """Format schema context for LLM with explicit database-qualified table names and date column marking"""
        # Extract all valid table names from context with database prefixes
        valid_tables = []
        for emb in context:
            if emb.get("table_name"):
                table_name = emb.get("table_name", "")
                database = emb.get("database", "")
                if database:
                    valid_tables.append(f"{database}.{table_name}")
                else:
                    valid_tables.append(table_name)
        
        # Start with explicit valid table names list
        context_str = " VALID TABLE NAMES (use EXACTLY as shown with database prefix):\n"
        for table in valid_tables:
            context_str += f"  - {table}\n"
        context_str += "\n"
        context_str += "[WARN] CRITICAL: You MUST use database-qualified table names in your SQL queries!\n"
        context_str += "   Example: SELECT * FROM franchises.contracts NOT SELECT * FROM contracts\n\n"
        
        # Common date column patterns for identification
        date_patterns = ['date', 'dt', 'time', 'created', 'updated', 'dispatch']
        
        for emb in context:
            table_name = emb.get("table_name", "")
            database = emb.get("database", "")
            qualified_table = f"{database}.{table_name}" if database else table_name
            
            table_info = next((t for t in schema_json if t.get("table_name") == table_name), None)
            
            if not table_info:
                continue
            
            context_str += f"\\nTable: {qualified_table}\\n"
            context_str += f"Database: {database}\\n"
            context_str += f"Purpose: {table_info.get('purpose', '')}\\n"
            context_str += "Columns:\\n"
            
            for col in table_info.get("columns", [])[:20]:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_desc = col.get("description", "")[:100]
                
                # Mark date columns explicitly
                is_date_col = any(pattern in col_name.lower() for pattern in date_patterns)
                date_marker = " [DATE_COLUMN]" if is_date_col else ""
                
                context_str += f"  - {col_name} ({col_type}){date_marker}: {col_desc}\\n"
            
            context_str += "\\n"
        
        return context_str
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        """Parse JSON from LLM response"""
        try:
            text = response.strip()
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    if "[" in part and "]" in part:
                        text = part
                        break
                if text.lower().startswith("json"):
                    text = text[4:]
            
            insights = json.loads(text.strip())
            
            if isinstance(insights, list):
                return insights
            elif isinstance(insights, dict):
                return [insights]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Response was: {response[:500]}")
            return []
    
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query using regex"""
        import re
        # Pattern to match table names after FROM and JOIN keywords
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(matches))  # Remove duplicates
    
    def _validate_insights(self, insights: List[Dict]) -> List[Dict]:
        """Validate SQL queries with table name verification"""
        validated = []
        
        for insight in insights:
            sql = insight.get("sql", "")
            insight_id = insight.get("id", "unknown")
            
            if not self._is_read_only(sql):
                logger.warning(f"Skipping non-read-only query: {insight_id}")
                continue
            
            # Extract and log table names for debugging
            table_names = self._extract_table_names(sql)
            if table_names:
                logger.info(f" Insight '{insight_id}' uses tables: {', '.join(table_names)}")
            
            is_valid, error_msg = self.db.validate_sql(sql)
            if not is_valid:
                logger.warning(f"Skipping invalid SQL: {insight_id}")
                logger.warning(f"Error: {error_msg}")
                if table_names:
                    logger.warning(f"Tables used: {', '.join(table_names)}")
                continue
            
            validated.append(insight)
        
        return validated
    
    def _is_read_only(self, sql: str) -> bool:
        """Check if SQL is read-only"""
        sql_upper = sql.upper()
        forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        return not any(kw in sql_upper for kw in forbidden)
    
    def _hash_schema(self, schema_json: List[Dict]) -> str:
        """Generate hash of schema"""
        import hashlib
        schema_str = json.dumps(schema_json, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()
