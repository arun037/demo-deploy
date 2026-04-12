"""
Dynamic Query Generator - AI-Powered RAG Query Generation

Analyzes schema and generates optimized queries for each insight category.
"""

from typing import Dict, List
from backend.core.logger import logger
from backend.config import Config


class DynamicQueryGenerator:
    """Generates category-specific RAG queries using LLM analysis"""
    
    def __init__(self, llm_client, schema_analysis: Dict, json_schema: Dict):
        self.llm = llm_client
        self.schema_analysis = schema_analysis
        self.json_schema = json_schema
    
    def generate_category_queries(self) -> Dict[str, str]:
        """
        Generate optimized queries for all 4 categories
        
        Returns:
        {
            "kpi": "franchise contract revenue monthly cap lead conversion...",
            "trend": "contract start date lead created timestamp...",
            "distribution": "contract status lead status customer type...",
            "alert": "contract pending lead failed low inventory..."
        }
        """
        logger.info(" Generating AI-powered category queries...")
        
        # Build schema summary for LLM
        schema_summary = self._build_schema_summary()
        
        # Generate queries for all categories
        queries = {}
        for category in ["kpi", "trend", "distribution", "alert"]:
            queries[category] = self._generate_query_for_category(
                category, 
                schema_summary
            )
        
        logger.info(f"S Generated dynamic queries for {len(queries)} categories")
        return queries
    
    def _build_schema_summary(self) -> str:
        """Build concise schema summary for LLM"""
        summary_parts = []
        
        # Business domain
        domain = self.schema_analysis.get("business_domain", "Analytics")
        summary_parts.append(f"Business Domain: {domain}")
        
        # Key tables with purposes
        summary_parts.append("\nKey Tables:")
        for table_name, table_def in list(self.json_schema.items())[:20]:
            purpose = table_def.get("purpose", "")
            columns = [c["name"] for c in table_def.get("columns", [])[:10]]
            summary_parts.append(
                f"  - {table_name}: {purpose}\n"
                f"    Columns: {', '.join(columns)}"
            )
        
        # Metrics available
        metrics = self.schema_analysis.get("metrics", {})
        if metrics:
            summary_parts.append("\nMetric Columns:")
            for table, cols in list(metrics.items())[:10]:
                summary_parts.append(f"  - {table}: {', '.join(cols[:5])}")
        
        # Time dimensions
        time_dims = self.schema_analysis.get("time_dimensions", {})
        if time_dims:
            summary_parts.append("\nDate Columns:")
            for table, cols in list(time_dims.items())[:10]:
                summary_parts.append(f"  - {table}: {', '.join(cols)}")
        
        return "\n".join(summary_parts)
    
    def _generate_query_for_category(self, category: str, schema_summary: str) -> str:
        """Generate optimized query for specific category"""
        
        # Category-specific instructions
        category_instructions = {
            "kpi": """
Generate a search query to find tables for KEY PERFORMANCE INDICATORS (KPIs).

Focus on:
- Financial metrics (revenue, cost, spend, amount, value, price)
- Volume metrics (count, quantity, total, number)
- Efficiency metrics (rate, percentage, ratio, conversion)
- Business-specific KPIs based on the domain

Include domain-specific terminology from the schema.
""",
            "trend": """
Generate a search query to find tables for TIME-SERIES TRENDS.

Focus on:
- Tables with date/timestamp columns
- Time-based analysis (monthly, quarterly, yearly, growth)
- Temporal patterns (trends, changes over time, historical)
- Date column names from the schema

Include actual date column names you see in the schema.
""",
            "distribution": """
Generate a search query to find tables for CATEGORICAL DISTRIBUTIONS.

Focus on:
- Categorical columns (status, type, category, group, segment)
- Rankings and breakdowns (top performers, distribution by)
- Groupable dimensions
- Actual categorical column names from the schema

Include actual categorical column names you see.
""",
            "alert": """
Generate a search query to find tables for ALERTS and WARNINGS.

Focus on:
- Status indicators (pending, failed, overdue, critical)
- Threshold conditions (low stock, high value, expired)
- Problem detection (issues, errors, warnings)
- Business-specific alert conditions

Include domain-specific alert terminology.
"""
        }
        
        system_prompt = f"""You are a database expert analyzing a schema to generate optimized search queries.

SCHEMA SUMMARY:
{schema_summary}

TASK: {category_instructions[category]}

REQUIREMENTS:
1. Generate a SINGLE LINE of keywords (no sentences)
2. Include 15-25 relevant keywords/phrases
3. Use domain-specific terminology from the schema
4. Include actual column names when relevant
5. Prioritize business-specific terms over generic ones

EXAMPLES:

Good KPI query for franchise business:
"franchise contract revenue monthly cap rate lead conversion success customer retention active contracts total spend investment roi"

Good Trend query for sales data:
"order date created timestamp transaction date monthly quarterly sales growth revenue trend purchase history time series"

OUTPUT FORMAT: Just the keyword string, nothing else."""

        user_query = f"Generate optimized search query for {category.upper()} category based on this schema."
        
        try:
            response = self.llm.call_agent(
                system_prompt=system_prompt,
                user_query=user_query,
                model=Config.DASHBOARD_MODEL,
                temperature=0.1,
                timeout=30,
                agent_name="QueryGenerator",
                log_file="logs/dashboard_usage.csv"
            )
            
            # Clean response
            query = response.strip().strip('"').strip("'")
            logger.info(f"  {category}: {query[:80]}...")
            return query
            
        except Exception as e:
            logger.error(f"Failed to generate query for {category}: {e}")
            # Fallback to static query
            return self._get_fallback_query(category)
    
    def _get_fallback_query(self, category: str) -> str:
        """Fallback to static queries if LLM fails"""
        fallback_queries = {
            "kpi": "financial metrics totals counts aggregates summary statistics monetary amounts quantities revenue cost investment",
            "trend": "date fields time series monthly quarterly yearly temporal analysis growth changes trends over time",
            "distribution": "categories groups rankings top performers distributions breakdowns segments",
            "alert": "status pending low stock thresholds warnings critical items overdue issues problems"
        }
        return fallback_queries.get(category, "")
