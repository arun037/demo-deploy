"""
Insight Planner - Strategic Dashboard Planning

Uses LLM reasoning to plan which insights to generate based on:
- Schema analysis
- Data exploration results
- Business domain
- Data availability

Ensures all insights:
- Answer key business questions
- Have sufficient data
- Support date filtering
- Form coherent narrative
"""

from typing import Dict, List, Any
import json
from backend.core.logger import logger
from backend.config import Config


class InsightPlanner:
    """Strategic planning of dashboard insights using LLM reasoning"""
    
    def __init__(self, llm_client, schema_analysis: Dict, data_exploration: Dict):
        self.llm = llm_client
        self.schema_analysis = schema_analysis
        self.data_exploration = data_exploration
    
    def plan_insights(self) -> Dict[str, Any]:
        """
        Create strategic plan for dashboard insights
        
        Returns:
            Dictionary containing:
            - kpi_plans: List of planned KPI insights
            - trend_plans: List of planned trend insights
            - distribution_plans: List of planned distribution insights
            - alert_plans: List of planned alert insights
            - reasoning: Explanation of planning decisions
        """
        logger.info(" Starting strategic insight planning...")
        
        # Get recommended tables (have data + date columns)
        recommended_tables = self.data_exploration.get("data_quality", {}).get("recommended_tables", [])
        
        if not recommended_tables:
            logger.warning("[WARN]  No recommended tables found - using all tables with data")
            recommended_tables = [
                {"table": table, "row_count": count, "date_columns": []}
                for table, count in self.data_exploration.get("row_counts", {}).items()
                if count > 0
            ]
        
        logger.info(f" Planning insights for {len(recommended_tables)} recommended tables")
        
        # Plan each category
        plans = {
            "kpi_plans": self._plan_kpis(recommended_tables),
            "trend_plans": self._plan_trends(recommended_tables),
            "distribution_plans": self._plan_distributions(recommended_tables),
            "alert_plans": self._plan_alerts(recommended_tables),
            "reasoning": self._generate_reasoning_summary(recommended_tables)
        }
        
        logger.info(f"S Planned {len(plans['kpi_plans'])} KPIs, "
                   f"{len(plans['trend_plans'])} trends, "
                   f"{len(plans['distribution_plans'])} distributions, "
                   f"{len(plans['alert_plans'])} alerts")
        
        return plans
    
    def _plan_kpis(self, recommended_tables: List[Dict]) -> List[Dict]:
        """Plan KPI insights using LLM reasoning"""
        
        # Build context
        context = self._build_planning_context(recommended_tables)
        
        system_prompt = f"""You are a Business Intelligence Analyst planning KPI metrics for a dashboard.

BUSINESS DOMAIN: {self.schema_analysis.get('business_domain', 'Unknown')}

AVAILABLE TABLES (with data and date columns):
{json.dumps(recommended_tables, indent=2)}

SCHEMA ANALYSIS:
- Fact Tables: {', '.join(self.schema_analysis.get('fact_tables', []))}
- Metrics Available: {self._format_metrics()}
- Time Dimensions: {self._format_time_dimensions()}

TASK: Plan EXACTLY 8 KPI insights that:
1. Answer key business questions for this domain
2. Use tables with sufficient data (row_count > 100)
3. MUST use tables that have date columns for time filtering
4. Make semantic sense together
5. Cover different aspects of the business

CRITICAL RULES:
- You MUST return EXACTLY 8 KPIs, no more, no less
- If you can't find 8 distinct metrics, create variations (e.g., total vs average, count vs percentage)
- Every KPI MUST have a date_column for time-based filtering

Think step-by-step:
1. What are the key questions stakeholders ask in this business domain?
2. Which tables/metrics answer those questions?
3. Do those tables have date columns for filtering?
4. What's the best way to calculate each metric?

Output JSON array with EXACTLY 8 items using this structure:
[
  {{
    "id": "kpi_total_revenue",
    "title": "Total Revenue",
    "description": "Sum of all revenue from completed transactions",
    "table": "database.table_name",
    "date_column": "transaction_date",
    "metric_column": "amount",
    "aggregation": "SUM",
    "filter_conditions": "status = 'completed'",
    "reasoning": "Revenue is the primary business metric"
  }}
]

CRITICAL: 
- Output EXACTLY 8 KPI objects in the JSON array
- Every KPI MUST have a date_column for time-based filtering
- Output ONLY valid JSON array, no markdown, no explanations."""

        user_query = "Plan EXACTLY 8 strategic KPI insights for this business domain. Return a JSON array with exactly 8 items."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=120
            )
            
            # Parse JSON response
            plans = self._parse_json_response(response)
            return plans[:8]
            
        except Exception as e:
            logger.error(f"Error planning KPIs: {e}")
            return []
    
    def _plan_trends(self, recommended_tables: List[Dict]) -> List[Dict]:
        """Plan trend insights using LLM reasoning"""
        
        context = self._build_planning_context(recommended_tables)
        
        system_prompt = f"""You are a Business Intelligence Analyst planning trend analysis for a dashboard.

BUSINESS DOMAIN: {self.schema_analysis.get('business_domain', 'Unknown')}

AVAILABLE TABLES (with data and date columns):
{json.dumps(recommended_tables, indent=2)}

DATE RANGES:
{json.dumps(self.data_exploration.get('date_ranges', {}), indent=2)}

TASK: Plan 6 trend insights that:
1. Show how key metrics change over time
2. Use tables with date columns and sufficient data
3. Cover monthly/quarterly time periods
4. Reveal growth patterns and trends

Output JSON array:
[
  {{
    "id": "trend_monthly_revenue",
    "title": "Monthly Revenue Trend",
    "description": "Revenue by month over last 12 months",
    "table": "database.table_name",
    "date_column": "transaction_date",
    "metric_column": "amount",
    "aggregation": "SUM",
    "time_grouping": "monthly",
    "time_period": "12_months",
    "reasoning": "Shows revenue growth pattern"
  }}
]

Output ONLY valid JSON array."""

        user_query = "Plan 6 time-series trend insights."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=120
            )
            
            plans = self._parse_json_response(response)
            return plans[:6]
            
        except Exception as e:
            logger.error(f"Error planning trends: {e}")
            return []
    
    def _plan_distributions(self, recommended_tables: List[Dict]) -> List[Dict]:
        """Plan distribution insights using LLM reasoning"""
        
        system_prompt = f"""You are a Business Intelligence Analyst planning distribution analysis.

BUSINESS DOMAIN: {self.schema_analysis.get('business_domain', 'Unknown')}

AVAILABLE TABLES:
{json.dumps(recommended_tables, indent=2)}

CATEGORICAL DIMENSIONS:
{json.dumps(self.data_exploration.get('sample_values', {}), indent=2)}

TASK: Plan 6 distribution insights showing top 10 breakdowns.

Output JSON array:
[
  {{
    "id": "dist_top_categories",
    "title": "Top 10 Categories",
    "description": "Categories by transaction count",
    "table": "database.table_name",
    "category_column": "category_name",
    "metric_column": "id",
    "aggregation": "COUNT",
    "limit": 10,
    "reasoning": "Shows category distribution"
  }}
]

Output ONLY valid JSON array."""

        user_query = "Plan 6 distribution insights."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=120
            )
            
            plans = self._parse_json_response(response)
            return plans[:6]
            
        except Exception as e:
            logger.error(f"Error planning distributions: {e}")
            return []
    
    def _plan_alerts(self, recommended_tables: List[Dict]) -> List[Dict]:
        """Plan alert insights using LLM reasoning"""
        
        system_prompt = f"""You are a Business Intelligence Analyst planning alert/warning insights.

BUSINESS DOMAIN: {self.schema_analysis.get('business_domain', 'Unknown')}

AVAILABLE TABLES:
{json.dumps(recommended_tables, indent=2)}

TASK: Plan 6 alert insights identifying critical issues.

Output JSON array:
[
  {{
    "id": "alert_low_stock",
    "title": "Low Stock Items",
    "description": "Items with quantity below threshold",
    "table": "database.table_name",
    "condition": "quantity < 10",
    "aggregation": "COUNT",
    "reasoning": "Prevents stockouts"
  }}
]

Output ONLY valid JSON array."""

        user_query = "Plan 6 alert insights."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=120
            )
            
            plans = self._parse_json_response(response)
            return plans[:6]
            
        except Exception as e:
            logger.error(f"Error planning alerts: {e}")
            return []
    
    def _build_planning_context(self, recommended_tables: List[Dict]) -> str:
        """Build context string for planning"""
        context_parts = []
        
        context_parts.append(f"Business Domain: {self.schema_analysis.get('business_domain', 'Unknown')}")
        context_parts.append(f"Recommended Tables: {len(recommended_tables)}")
        
        for table_info in recommended_tables[:5]:
            context_parts.append(f"  - {table_info['table']}: {table_info['row_count']} rows, "
                                f"date columns: {', '.join(table_info.get('date_columns', []))}")
        
        return "\\n".join(context_parts)
    
    def _format_metrics(self) -> str:
        """Format metrics for display"""
        metrics = self.schema_analysis.get("metrics", {})
        return ", ".join([f"{table}: {', '.join(cols[:3])}" for table, cols in list(metrics.items())[:3]])
    
    def _format_time_dimensions(self) -> str:
        """Format time dimensions for display"""
        time_dims = self.schema_analysis.get("time_dimensions", {})
        return ", ".join([f"{table}: {', '.join(cols)}" for table, cols in list(time_dims.items())[:3]])
    
    def _generate_reasoning_summary(self, recommended_tables: List[Dict]) -> str:
        """Generate summary of planning reasoning"""
        return f"""Dashboard planning based on:
- Business Domain: {self.schema_analysis.get('business_domain', 'Unknown')}
- {len(recommended_tables)} tables with sufficient data and date columns
- Focus on tables: {', '.join([t['table'] for t in recommended_tables[:3]])}
- All insights designed to support date-based filtering"""
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        """Parse JSON response from LLM"""
        try:
            # Remove markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            response = response.strip()
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Response was: {response[:500]}")
            return []
