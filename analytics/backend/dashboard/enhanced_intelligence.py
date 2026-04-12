import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from backend.core.logger import logger

class EnhancedDashboardIntelligence:
    """
    Enhanced intelligence for dashboard generation with smart table selection
    and template-based SQL generation.
    """
    
    def __init__(self, llm_client, rag_retriever, db_manager):
        self.llm = llm_client
        self.rag = rag_retriever
        self.db = db_manager
        
        # Define SQL patterns for common KPI types
        self.sql_templates = {
            "spend": {
                "sql": "SELECT COUNT(*) as count, SUM({amount_col}) as total FROM {table} WHERE {date_col} IS NOT NULL",
                "required_cols": ["amount", "date"],
                "keywords": ["spend", "amount", "cost", "price", "total"]
            },
            "requisitions": {
                "sql": "SELECT COUNT(*) as total FROM {table} WHERE {date_col} IS NOT NULL",
                "required_cols": ["id", "date"],
                "keywords": ["req", "requisition", "request"]
            },
            "fulfillment": {
                "sql": "SELECT CAST(SUM(CASE WHEN {status_col} IN ('Filled', 'Completed', 'Received') THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as rate FROM {table}",
                "required_cols": ["status"],
                "keywords": ["fulfill", "status", "complete"]
            },
            "inventory": {
                "sql": "SELECT COUNT(*) as total, SUM({qty_col}) as total_qty FROM {table}",
                "required_cols": ["qty"],
                "keywords": ["inventory", "stock", "quantity", "on_hand"]
            },
            "vendors": {
                "sql": "SELECT COUNT(DISTINCT {vendor_col}) as total FROM {table}",
                "required_cols": ["vendor"],
                "keywords": ["vendor", "supplier", "manufacturer"]
            }
        }

    def generate_smart_kpi(
        self,
        kpi_type: str,
        schema_json: List[Dict],
        previous_failures: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate KPI with intelligence and fallback strategies
        """
        # Step 1: Find best tables for this KPI
        candidate_tables = self._find_best_tables_for_kpi(kpi_type, schema_json)
        
        # Step 2: Filter out previously failed tables
        if previous_failures:
            candidate_tables = [
                t for t in candidate_tables
                if t["table_name"] not in previous_failures
            ]
        
        # Step 3: Rank tables by data quality indicators
        ranked_tables = self._rank_tables_by_quality(candidate_tables)
        
        # Step 4: Generate SQL with best table
        if ranked_tables:
            best_table = ranked_tables[0]
            kpi_config = self._generate_kpi_sql(kpi_type, best_table, schema_json)
            
            if kpi_config:
                # Step 5: Add fallback options
                kpi_config["fallback_tables"] = [t["table_name"] for t in ranked_tables[1:3]]
                kpi_config["data_quality_score"] = best_table.get("quality_score", 50)
                kpi_config["table_used"] = best_table["table_name"]
                return kpi_config
        
        return None

    def _find_best_tables_for_kpi(self, kpi_type: str, schema_json: List[Dict]) -> List[Dict]:
        """Find tables that match keywords for the KPI type"""
        template = self.sql_templates.get(kpi_type)
        if not template:
            return []
            
        candidates = []
        keywords = template["keywords"]
        
        for table in schema_json:
            table_name = table["table_name"].lower()
            columns = [c["name"].lower() for c in table["columns"]]
            
            # Score based on table name match
            score = 0
            if any(k in table_name for k in keywords):
                score += 50
                
            # Score based on column matches
            matched_cols = 0
            for k in keywords:
                if any(k in c for c in columns):
                    matched_cols += 1
            score += matched_cols * 10
            
            # Check for required columns
            # This is a simplified check - in reality we'd look for specific types too
            if score > 0:
                table["relevance_score"] = score
                candidates.append(table)
                
        return sorted(candidates, key=lambda x: x["relevance_score"], reverse=True)

    def _rank_tables_by_quality(self, tables: List[Dict]) -> List[Dict]:
        """Rank tables based on perceived data quality (dummy implementation for now)"""
        # In a real system, we'd check row counts, null rates, etc.
        # For now, we prefer tables that look like "fact" tables or "master" tables
        for table in tables:
            score = table.get("relevance_score", 0)
            name = table["table_name"].lower()
            
            if "_info" in name or "_master" in name:
                score += 10
            if "lumy" in name: # specific user preference/convention
                score += 5
                
            table["quality_score"] = score
            
        return sorted(tables, key=lambda x: x["quality_score"], reverse=True)

    def _generate_kpi_sql(self, kpi_type: str, table: Dict, schema: List[Dict]) -> Optional[Dict[str, Any]]:
        """Generate the actual SQL and config for the KPI"""
        template = self.sql_templates.get(kpi_type)
        if not template:
            return None
            
        table_name = table["table_name"]
        columns = {c["name"].lower(): c["name"] for c in table["columns"]}
        col_names = list(columns.keys())
        
        # Resolve column placeholders
        params = {"table": table_name}
        
        # Find date column
        date_col = next((c for c in col_names if "date" in c or "_dt" in c or "time" in c), None)
        if date_col:
            params["date_col"] = columns[date_col]
        else:
            # If no date column, we can't do time-based filtering efficiently
            # Better to return None or handle carefully. 
            # For now, we'll try to execute without date filter if template allows, 
            # but our templates enforce date checks usually to be "smart"
            pass

        # Specific logic per KPI type to find columns
        if kpi_type == "spend":
            amount_col = next((c for c in col_names if "amount" in c or "cost" in c or "total" in c), None)
            if amount_col and date_col:
                params["amount_col"] = columns[amount_col]
                sql = f"SELECT ROUND(SUM({params['amount_col']}), 2) as total FROM {table_name} WHERE {params['date_col']} >= '2024-01-01'" # Example default filter
                
                return {
                    "id": f"kpi_{kpi_type}",
                    "title": f"Total {kpi_type.title()}",
                    "sql": sql,
                    "viz_type": "kpi_card",
                    "format": "currency"
                }
                
        elif kpi_type == "requisitions":
             if date_col:
                sql = f"SELECT COUNT(*) as total FROM {table_name} WHERE {params['date_col']} >= '2024-01-01'"
                return {
                    "id": f"kpi_{kpi_type}",
                    "title": f"Total {kpi_type.title()}",
                    "sql": sql,
                    "viz_type": "kpi_card",
                    "format": "number"
                }

        elif kpi_type == "fulfillment":
            status_col = next((c for c in col_names if "status" in c), None)
            if status_col:
                col_real = columns[status_col]
                sql = f"SELECT ROUND(SUM(CASE WHEN {col_real} IN ('Filled', 'Completed', 'Received') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as rate FROM {table_name}"
                return {
                    "id": f"kpi_{kpi_type}",
                    "title": f"{kpi_type.title()} Rate",
                    "sql": sql,
                    "viz_type": "kpi_card",
                    "format": "percent"
                }
                
        elif kpi_type == "inventory":
            qty_col = next((c for c in col_names if "qty" in c or "quantity" in c), None)
            if qty_col:
                params["qty_col"] = columns[qty_col]
                sql = f"SELECT SUM({params['qty_col']}) as total FROM {table_name}"
                return {
                     "id": f"kpi_{kpi_type}",
                    "title": "Total Inventory Items",
                    "sql": sql,
                    "viz_type": "kpi_card",
                    "format": "number"
                }

        elif kpi_type == "vendors":
             vendor_col = next((c for c in col_names if "vendor" in c and "id" in c), None)
             if not vendor_col:
                 vendor_col = next((c for c in col_names if "vendor" in c), None)
                 
             if vendor_col:
                col_real = columns[vendor_col]
                sql = f"SELECT COUNT(DISTINCT {col_real}) as total FROM {table_name}"
                return {
                    "id": f"kpi_{kpi_type}",
                    "title": "Active Vendors",
                    "sql": sql,
                    "viz_type": "kpi_card",
                    "format": "number"
                }

        return None
