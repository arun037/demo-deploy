"""
Schema Graph Analyzer

Analyzes database schema structure using graph theory to identify
key tables, relationships, and star schema patterns.
"""

import json
from typing import Dict, List, Any
from collections import defaultdict


class SchemaGraphAnalyzer:
    """Analyzes schema using graph-based FK analysis"""
    
    def analyze(self, schema_json: List[Dict]) -> Dict[str, Any]:
        """
        Analyze schema and identify key tables
        
        Returns:
            - fact_tables: Tables with high FK centrality or aggregatable columns
            - dimension_tables: Reference/lookup tables
            - priority_tables: Top 20 tables for analysis
            - graph_metrics: Centrality scores
        """
        # Build FK graph
        fk_graph = self._build_fk_graph(schema_json)
        
        # Calculate centrality
        centrality = self._calculate_centrality(fk_graph, schema_json)
        
        # Identify fact vs dimension tables
        fact_tables = self._identify_fact_tables(schema_json, centrality)
        dimension_tables = self._identify_dimension_tables(schema_json, fact_tables)
        
        # Prioritize tables
        priority_tables = self._prioritize_tables(schema_json, centrality, fact_tables)
        
        return {
            "fact_tables": fact_tables,
            "dimension_tables": dimension_tables,
            "priority_tables": priority_tables[:20],
            "graph_metrics": centrality
        }
    
    def _build_fk_graph(self, schema_json: List[Dict]) -> Dict[str, List[str]]:
        """Build directed graph of foreign key relationships"""
        graph = defaultdict(list)
        
        for table in schema_json:
            table_name = table.get("table_name", "")
            foreign_keys = table.get("foreign_keys", [])
            
            for fk in foreign_keys:
                if isinstance(fk, dict) and "references" in fk:
                    referenced_table = fk["references"]
                    graph[table_name].append(referenced_table)
        
        return dict(graph)
    
    def _calculate_centrality(self, fk_graph: Dict, schema_json: List[Dict]) -> Dict[str, float]:
        """Calculate centrality scores for each table"""
        centrality = {}
        
        # Count incoming and outgoing edges
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        
        for source, targets in fk_graph.items():
            out_degree[source] += len(targets)
            for target in targets:
                in_degree[target] += 1
        
        # Calculate combined score
        for table in schema_json:
            table_name = table.get("table_name", "")
            
            # Fact tables typically have high out-degree (many FKs)
            # Dimension tables have high in-degree (referenced by many)
            out_score = out_degree.get(table_name, 0)
            in_score = in_degree.get(table_name, 0)
            
            # Boost score for numeric columns (likely aggregatable)
            numeric_cols = self._count_numeric_columns(table)
            
            # Combined score
            centrality[table_name] = (out_score * 2) + in_score + (numeric_cols * 0.5)
        
        return centrality
    
    def _count_numeric_columns(self, table: Dict) -> int:
        """Count numeric/aggregatable columns"""
        numeric_types = ['int', 'bigint', 'decimal', 'float', 'double', 'numeric']
        count = 0
        
        for col in table.get("columns", []):
            col_type = col.get("type", "").lower()
            col_name = col.get("name", "").lower()
            
            # Check type
            if any(t in col_type for t in numeric_types):
                # Exclude IDs
                if not col_name.endswith('_id') and col_name != 'id':
                    count += 1
        
        return count
    
    def _identify_fact_tables(self, schema_json: List[Dict], centrality: Dict) -> List[str]:
        """Identify fact tables using heuristics"""
        fact_tables = []
        
        for table in schema_json:
            table_name = table.get("table_name", "")
            purpose = table.get("purpose", "").lower()
            
            # Heuristic 1: High centrality score
            if centrality.get(table_name, 0) > 5:
                fact_tables.append(table_name)
                continue
            
            # Heuristic 2: Naming patterns
            fact_keywords = ['transaction', 'order', 'req', 'po_', 'invoice', 'demand', 'line']
            if any(kw in table_name.lower() for kw in fact_keywords):
                fact_tables.append(table_name)
                continue
            
            # Heuristic 3: Purpose indicates transactional data
            purpose_keywords = ['transaction', 'order', 'requisition', 'purchase', 'demand']
            if any(kw in purpose for kw in purpose_keywords):
                fact_tables.append(table_name)
        
        return fact_tables
    
    def _identify_dimension_tables(self, schema_json: List[Dict], fact_tables: List[str]) -> List[str]:
        """Identify dimension tables (reference/lookup tables)"""
        dimension_tables = []
        
        for table in schema_json:
            table_name = table.get("table_name", "")
            
            # Skip fact tables
            if table_name in fact_tables:
                continue
            
            purpose = table.get("purpose", "").lower()
            
            # Heuristic: Naming patterns
            dim_keywords = ['master', 'category', 'type', 'vendor', 'item', 'location', 'department']
            if any(kw in table_name.lower() for kw in dim_keywords):
                dimension_tables.append(table_name)
                continue
            
            # Heuristic: Purpose indicates reference data
            purpose_keywords = ['master', 'catalog', 'classification', 'reference', 'lookup']
            if any(kw in purpose for kw in purpose_keywords):
                dimension_tables.append(table_name)
        
        return dimension_tables
    
    def _prioritize_tables(self, schema_json: List[Dict], centrality: Dict, fact_tables: List[str]) -> List[str]:
        """Prioritize tables for analysis (top 20)"""
        # Sort by centrality score
        sorted_tables = sorted(
            schema_json,
            key=lambda t: centrality.get(t.get("table_name", ""), 0),
            reverse=True
        )
        
        # Ensure fact tables are prioritized
        priority = []
        
        # Add fact tables first
        for table in sorted_tables:
            table_name = table.get("table_name", "")
            if table_name in fact_tables:
                priority.append(table_name)
        
        # Add remaining high-centrality tables
        for table in sorted_tables:
            table_name = table.get("table_name", "")
            if table_name not in priority:
                priority.append(table_name)
        
        return priority
