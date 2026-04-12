"""
Intelligent Planner - LLM-Based Insight Generation

Uses LLM to generate meaningful, business-focused insights instead of
template-based logic. Understands business context and creates proper
KPIs, trends, distributions, and alerts.
"""

from typing import Dict, List, Any
import json
from backend.core.logger import logger


class IntelligentPlanner:
    """Uses LLM to plan meaningful dashboard insights"""
    
    def __init__(self, llm, rag_retriever):
        self.llm = llm
        self.rag = rag_retriever
    
    def plan_insights(self, schema_analysis: Dict, data_exploration: Dict) -> Dict[str, List]:
        """
        Use LLM to generate meaningful insight plans
        
        Returns:
            Dictionary with kpi_plans, trend_plans, distribution_plans, alert_plans
        """
        logger.info(" Starting LLM-based intelligent insight planning...")
        
        # Extract context for LLM
        business_domain = schema_analysis.get("business_domain", "Unknown")
        tables = self._format_tables_for_llm(schema_analysis)
        data_summary = self._format_data_summary(data_exploration)
        
        # Generate insights using LLM
        kpi_plans = self._plan_kpis_with_llm(business_domain, tables, data_summary, count=8)
        trend_plans = self._plan_trends_with_llm(business_domain, tables, data_summary, count=6)
        distribution_plans = self._plan_distributions_with_llm(business_domain, tables, data_summary, count=10)
        alert_plans = self._plan_alerts_with_llm(business_domain, tables, data_summary, count=5)
        
        logger.info(f"S Planned {len(kpi_plans)} KPIs, {len(trend_plans)} trends, "
                   f"{len(distribution_plans)} distributions, {len(alert_plans)} alerts")
        
        return {
            "kpi_plans": kpi_plans,
            "trend_plans": trend_plans,
            "distribution_plans": distribution_plans,
            "alert_plans": alert_plans
        }
    
    def _format_tables_for_llm(self, schema_analysis: Dict) -> str:
        """Format schema information for LLM prompt"""
        tables_info = []
        
        # Get all tables with their columns
        time_dims = schema_analysis.get("time_dimensions", {})
        metrics = schema_analysis.get("metrics", {})
        dimensions = schema_analysis.get("dimensions", {})
        
        all_tables = set(list(time_dims.keys()) + list(metrics.keys()) + list(dimensions.keys()))
        
        for table in all_tables:
            table_info = f"**{table}**\n"
            
            # Add date columns
            if table in time_dims and time_dims[table]:
                table_info += f"  - Date columns: {', '.join(time_dims[table])}\n"
            
            # Add metric columns
            if table in metrics and metrics[table]:
                table_info += f"  - Numeric columns: {', '.join(metrics[table][:5])}\n"
            
            # Add dimension columns
            if table in dimensions and dimensions[table]:
                table_info += f"  - Category columns: {', '.join(dimensions[table][:5])}\n"
            
            tables_info.append(table_info)
        
        return "\n".join(tables_info)
    
    def _format_data_summary(self, data_exploration: Dict) -> str:
        """Format data exploration results for LLM"""
        row_counts = data_exploration.get("row_counts", {})
        date_ranges = data_exploration.get("date_ranges", {})
        
        summary = []
        for table, count in list(row_counts.items())[:5]:
            summary.append(f"- {table}: {count:,} rows")
            if table in date_ranges:
                for col, info in date_ranges[table].items():
                    summary.append(f"  - {col}: {info.get('min', 'N/A')} to {info.get('max', 'N/A')}")
        
        return "\n".join(summary)
    
    def _plan_kpis_with_llm(self, business_domain: str, tables: str, data_summary: str, count: int) -> List[Dict]:
        """Use LLM to generate meaningful KPI plans"""
        
        prompt = f"""You are a business intelligence expert analyzing a {business_domain} database.

DATABASE SCHEMA:
{tables}

DATA SUMMARY:
{data_summary}

Generate {count} meaningful Key Performance Indicators (KPIs) that would be valuable for business users.

REQUIREMENTS:
1. Use business-friendly names (e.g., "Total Active Customers", "Monthly Revenue")
2. Focus on counts, sums, and averages that matter to the business
3. Use COUNT(*) for total counts, not COUNT(DISTINCT random_column)
4. Each KPI must have a date column for filtering
5. Provide clear descriptions of what each KPI measures

Return ONLY a JSON array with this exact structure:
[
  {{
    "id": "kpi_active_customers",
    "title": "Total Active Customers",
    "description": "Number of customers with active status",
    "table": "franchises.customers",
    "date_column": "activation_date",
    "aggregation": "COUNT",
    "metric_column": null,
    "filter_condition": "active = 1"
  }}
]

Generate {count} KPIs now:"""

        try:
            response = self.llm.send_message(prompt=prompt, temperature=0.1)
            
            # Extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                kpis = json.loads(json_str)
                logger.info(f"S LLM generated {len(kpis)} KPI plans")
                return kpis
            else:
                logger.warning("[WARN]  Could not parse LLM response for KPIs")
                return []
                
        except Exception as e:
            logger.error(f"[FAIL] Error generating KPIs with LLM: {e}")
            return []
    
    def _plan_trends_with_llm(self, business_domain: str, tables: str, data_summary: str, count: int) -> List[Dict]:
        """Use LLM to generate meaningful trend plans"""
        
        prompt = f"""You are a business intelligence expert analyzing a {business_domain} database.

DATABASE SCHEMA:
{tables}

DATA SUMMARY:
{data_summary}

Generate {count} time-series trends that show how key metrics change over time.

REQUIREMENTS:
1. Focus on growth metrics (new customers, new contracts, revenue)
2. Use monthly grouping (DATE_FORMAT with '%Y-%m')
3. Each trend must have a date column
4. Use business-friendly names
5. Show data for last 24 months

Return ONLY a JSON array with this exact structure:
[
  {{
    "id": "trend_new_customers_monthly",
    "title": "Monthly New Customers",
    "description": "Number of new customers acquired each month",
    "table": "franchises.customers",
    "date_column": "activation_date",
    "metric": "COUNT(*)",
    "grouping": "monthly",
    "period_months": 24
  }}
]

Generate {count} trends now:"""

        try:
            response = self.llm.send_message(prompt=prompt, temperature=0.1)
            
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_end:
                json_str = response[json_start:json_end]
                trends = json.loads(json_str)
                logger.info(f"S LLM generated {len(trends)} trend plans")
                return trends
            else:
                logger.warning("[WARN]  Could not parse LLM response for trends")
                return []
                
        except Exception as e:
            logger.error(f"[FAIL] Error generating trends with LLM: {e}")
            return []
    
    def _plan_distributions_with_llm(self, business_domain: str, tables: str, data_summary: str, count: int) -> List[Dict]:
        """Use LLM to generate meaningful distribution plans"""
        
        prompt = f"""You are a business intelligence expert analyzing a {business_domain} database.

DATABASE SCHEMA:
{tables}

DATA SUMMARY:
{data_summary}

Generate {count} distribution insights showing breakdowns by category.

REQUIREMENTS:
1. Show top 10 items for each distribution
2. Use business-meaningful categories
3. Focus on actionable breakdowns (by region, by product, by sales rep, etc.)
4. Use business-friendly names

Return ONLY a JSON array with this exact structure:
[
  {{
    "id": "dist_customers_by_state",
    "title": "Customers by State",
    "description": "Distribution of customers across states",
    "table": "franchises.customers",
    "category_column": "state",
    "metric": "COUNT(*)",
    "limit": 10
  }}
]

Generate {count} distributions now:"""

        try:
            response = self.llm.send_message(prompt=prompt, temperature=0.1)
            
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                distributions = json.loads(json_str)
                logger.info(f"S LLM generated {len(distributions)} distribution plans")
                return distributions
            else:
                logger.warning("[WARN]  Could not parse LLM response for distributions")
                return []
                
        except Exception as e:
            logger.error(f"[FAIL] Error generating distributions with LLM: {e}")
            return []
    
    def _plan_alerts_with_llm(self, business_domain: str, tables: str, data_summary: str, count: int) -> List[Dict]:
        """Use LLM to generate meaningful alert plans"""
        
        prompt = f"""You are a business intelligence expert analyzing a {business_domain} database.

DATABASE SCHEMA:
{tables}

DATA SUMMARY:
{data_summary}

Generate {count} alert conditions that indicate potential business issues.

REQUIREMENTS:
1. Focus on actionable alerts (contracts expiring, inactive customers, low performance)
2. Use COUNT(*) to count records matching alert condition
3. Include threshold and severity
4. Use business-friendly names

Return ONLY a JSON array with this exact structure:
[
  {{
    "id": "alert_contracts_expiring_soon",
    "title": "Contracts Expiring in 30 Days",
    "description": "Number of contracts expiring within the next 30 days",
    "table": "franchises.contracts",
    "condition": "end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)",
    "threshold": 10,
    "severity": "warning"
  }}
]

Generate {count} alerts now:"""

        try:
            response = self.llm.send_message(prompt=prompt, temperature=0.1)
            
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                alerts = json.loads(json_str)
                logger.info(f"S LLM generated {len(alerts)} alert plans")
                return alerts
            else:
                logger.warning("[WARN]  Could not parse LLM response for alerts")
                return []
                
        except Exception as e:
            logger.error(f"[FAIL] Error generating alerts with LLM: {e}")
            return []
