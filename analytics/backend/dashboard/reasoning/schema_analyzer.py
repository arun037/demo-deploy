"""
Schema Analyzer - Deep Schema Structure Analysis

Analyzes database schema to understand:
- Business domain
- Fact vs dimension tables
- Relationships and foreign keys
- Time dimensions
- Metrics and dimensions
- Cardinalities
"""

from typing import Dict, List, Any
from backend.core.logger import logger


class SchemaAnalyzer:
    """Analyzes database schema structure and relationships"""
    
    def __init__(self, schema_json: List[Dict], llm_client=None):
        self.schema_json = schema_json
        self.llm = llm_client
        self.analysis = {}
        
        # Load business context
        try:
            import os
            import json
            context_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "business_context.json")
            if os.path.exists(context_path):
                with open(context_path, "r") as f:
                    self.business_context = json.load(f)
            else:
                self.business_context = {}
        except Exception as e:
            logger.error(f"Failed to load business_context.json: {e}")
            self.business_context = {}
    
    def analyze_schema(self) -> Dict[str, Any]:
        """
        Comprehensive schema analysis
        
        Returns:
            Dictionary containing:
            - business_domain: Inferred business domain
            - fact_tables: Tables with metrics and FKs
            - dimension_tables: Reference/lookup tables
            - relationships: FK relationships
            - time_dimensions: Date/time columns per table
            - metrics: Numeric columns for aggregation
            - dimensions: Categorical columns for grouping
            - cardinalities: Estimated row counts
        """
        logger.info(" Starting comprehensive schema analysis...")
        
        self.analysis = {
            "business_domain": self._infer_business_domain(),
            "fact_tables": self._identify_fact_tables(),
            "dimension_tables": self._identify_dimension_tables(),
            "relationships": self._map_relationships(),
            "time_dimensions": self._find_time_columns(),
            "metrics": self._identify_metrics(),
            "dimensions": self._identify_dimensions(),
            "table_purposes": self._extract_table_purposes()
        }
        
        logger.info(f"S Business Domain: {self.analysis['business_domain']}")
        logger.info(f"S Found {len(self.analysis['fact_tables'])} fact tables")
        logger.info(f"S Found {len(self.analysis['time_dimensions'])} tables with time dimensions")
        
        return self.analysis
    
    def _infer_business_domain(self) -> str:
        """Use LLM or context to infer business domain from schema"""
        # Prioritize business context if available
        if hasattr(self, 'business_context') and self.business_context.get('business_name'):
            return self.business_context.get('business_name')
            
        if not self.llm:
            return "Unknown"
        
        # Extract table names and purposes
        table_info = []
        for table in self.schema_json[:10]:  # Sample first 10 tables
            table_info.append({
                "table": table.get("table_name", ""),
                "purpose": table.get("purpose", ""),
                "columns": [c.get("name", "") for c in table.get("columns", [])[:5]]
            })
        
        prompt = f"""Analyze this database schema and identify the business domain in 2-4 words.

Tables:
{table_info}

Examples:
- "E-commerce Platform"
- "Franchise Management"
- "Healthcare Records"
- "Supply Chain Management"

Output ONLY the business domain name, nothing else."""

        try:
            response = self.llm.call_agent(
                system_prompt="You are a database analyst identifying business domains.",
                user_query=prompt,
                temperature=0.1,
                timeout=30,
                agent_name="Dashboard-SchemaAnalyzer",
                log_file="logs/dashboard_usage.csv"
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"Could not infer business domain: {e}")
            return "Business Intelligence"
    
    def _identify_fact_tables(self) -> List[str]:
        """
        Identify fact tables (tables with metrics and foreign keys)
        
        Fact tables typically have:
        - Numeric columns (metrics)
        - Foreign keys (relationships)
        - Date columns (time dimension)
        """
        fact_tables = []
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            columns = table.get("columns", [])
            foreign_keys = table.get("foreign_keys", [])
            
            # Count numeric columns
            numeric_count = sum(1 for col in columns 
                              if any(t in col.get("type", "").lower() 
                                   for t in ["int", "decimal", "float", "double", "numeric"]))
            
            # Has foreign keys and numeric columns
            if len(foreign_keys) > 0 and numeric_count > 2:
                fact_tables.append(table_name)
        
        return fact_tables
    
    def _identify_dimension_tables(self) -> List[str]:
        """
        Identify dimension tables (reference/lookup tables)
        
        Dimension tables typically have:
        - Mostly text/categorical columns
        - Few or no foreign keys
        - Descriptive information
        """
        dimension_tables = []
        fact_tables = set(self._identify_fact_tables())
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            if table_name not in fact_tables:
                dimension_tables.append(table_name)
        
        return dimension_tables
    
    def _map_relationships(self) -> List[Dict]:
        """Map foreign key relationships between tables"""
        relationships = []
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            foreign_keys = table.get("foreign_keys", [])
            
            for fk in foreign_keys:
                relationships.append({
                    "from_table": f"{database_name}.{table_name}",
                    "from_column": fk.get("column", ""),
                    "to_table": fk.get("references", ""),
                    "relationship_type": "many-to-one"
                })
        
        return relationships
    
    def _find_time_columns(self) -> Dict[str, List[str]]:
        """Find date/time columns for each table"""
        time_dimensions = {}
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            full_table_name = f"{database_name}.{table_name}"
            columns = table.get("columns", [])
            
            date_columns = []
            for col in columns:
                col_name = col.get("name", "").lower()
                col_type = col.get("type", "").lower()
                
                # Check if it's a date/time column
                if any(keyword in col_name for keyword in ["date", "time", "created", "updated", "modified"]) or \
                   any(keyword in col_type for keyword in ["date", "time", "timestamp"]):
                    date_columns.append(col.get("name", ""))
            
            if date_columns:
                time_dimensions[full_table_name] = date_columns
        
        return time_dimensions
    
    def _identify_metrics(self) -> Dict[str, List[str]]:
        """Identify numeric columns suitable for aggregation"""
        metrics = {}
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            full_table_name = f"{database_name}.{table_name}"
            columns = table.get("columns", [])
            
            metric_columns = []
            for col in columns:
                col_name = col.get("name", "").lower()
                col_type = col.get("type", "").lower()
                
                # Numeric types
                is_numeric = any(t in col_type for t in ["int", "decimal", "float", "double", "numeric"])
                
                # Exclude ID columns
                is_id = col_name.endswith("_id") or col_name == "id"
                
                if is_numeric and not is_id:
                    metric_columns.append(col.get("name", ""))
            
            if metric_columns:
                metrics[full_table_name] = metric_columns
        
        return metrics
    
    def _identify_dimensions(self) -> Dict[str, List[str]]:
        """Identify categorical columns suitable for grouping"""
        dimensions = {}
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            full_table_name = f"{database_name}.{table_name}"
            columns = table.get("columns", [])
            
            dimension_columns = []
            for col in columns:
                col_name = col.get("name", "").lower()
                col_type = col.get("type", "").lower()
                
                # Text/categorical types
                is_categorical = any(t in col_type for t in ["varchar", "char", "text", "enum"])
                
                # Exclude very long text fields
                is_long_text = "text" in col_type or "blob" in col_type
                
                # Exclude ID columns
                is_id = col_name.endswith("_id") or col_name == "id"
                
                if is_categorical and not is_long_text and not is_id:
                    dimension_columns.append(col.get("name", ""))
            
            if dimension_columns:
                dimensions[full_table_name] = dimension_columns[:10]  # Limit to 10
        
        return dimensions
    
    def _extract_table_purposes(self) -> Dict[str, str]:
        """Extract purpose/description for each table"""
        purposes = {}
        
        for table in self.schema_json:
            table_name = table.get("table_name", "")
            database_name = table.get("database_name", "")
            full_table_name = f"{database_name}.{table_name}"
            purpose = table.get("purpose", "")
            
            purposes[full_table_name] = purpose
        
        return purposes
