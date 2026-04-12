from typing import List, Dict, Any
from backend.core.logger import logger
import json
import os
import re
from collections import deque

class SchemaAnalyzer:
    def __init__(self, schema_path=None):
        from backend.config import Config
        self.schema_path = schema_path if schema_path else Config.SCHEMA_FILE
        self.schema_data = self._load_schema()
        self.graph = self._build_graph()

    def _load_schema(self):
        try:
            if os.path.exists(self.schema_path):
                with open(self.schema_path, 'r') as f:
                    data = json.load(f)
                return data
            else:
                logger.warning(f"SchemaAnalyzer: Schema file not found at {self.schema_path}")
                return []
        except Exception as e:
            logger.error(f"SchemaAnalyzer: Failed to load schema: {e}")
            return []

    def _build_graph(self):
        """
        Build an undirected graph of tables based on explicit foreign keys.
        Graph structure: { table_name: { neighbor_table: [(my_col, their_col), ...] } }
        Supports multiple FK connections between the same pair of tables.
        """
        graph = {}
        for table in self.schema_data:
            t_name = table['table_name']
            if t_name not in graph:
                graph[t_name] = {}
                
            for fk in table.get('foreign_keys', []):
                refs = fk.get('references', '')
                # Parse "franchises.sites_info(site_id)" or "sites_info(site_id)"
                match = re.search(r'(?:[^.]+?\.)?([^.]+?)\s*\(([^)]+)\)', refs)
                if match:
                    target_table = match.group(1).strip()
                    target_col = match.group(2).strip()
                    source_col = fk.get('column', '')
                    
                    # Forward edge
                    if target_table not in graph[t_name]:
                        graph[t_name][target_table] = []
                    graph[t_name][target_table].append((source_col, target_col))
                    
                    # Backward edge (undirected)
                    if target_table not in graph:
                        graph[target_table] = {}
                    if t_name not in graph[target_table]:
                        graph[target_table][t_name] = []
                    graph[target_table][t_name].append((target_col, source_col))
                    
        return graph

    def _pick_best_connection(self, connections):
        """
        Intelligently pick the best FK connection from a list of options.
        Uses generic heuristics  NO hardcoded column names.
        
        Priority order:
        1. source_col == target_col (exact name match = strongest signal)
        2. source_col contains target_col or vice versa (partial match)
        3. First connection in list (fallback)
        """
        if len(connections) == 1:
            return connections[0]
        
        # Priority 1: Exact column name match (e.g., site_id == site_id, fbo_id == fbo_id)
        for conn in connections:
            source_col, target_col = conn
            if source_col == target_col:
                return conn
        
        # Priority 2: One column name contains the other
        for conn in connections:
            source_col, target_col = conn
            if source_col in target_col or target_col in source_col:
                return conn
        
        # Fallback: first connection
        return connections[0]

    def _find_path(self, start_table, end_table):
        """
        Find shortest path between two tables using BFS.
        Returns list of tuples: (from_table, from_col, to_table, to_col)
        Uses _pick_best_connection for intelligent FK selection.
        """
        if start_table not in self.graph or end_table not in self.graph:
            return None
            
        queue = deque([(start_table, [])])
        visited = set([start_table])
        
        while queue:
            current, path = queue.popleft()
            if current == end_table:
                return path
                
            for neighbor, connections in self.graph[current].items():
                if neighbor not in visited:
                    visited.add(neighbor)
                    
                    # Intelligently pick the best connection
                    from_col, to_col = self._pick_best_connection(connections)
                    
                    new_path = list(path)
                    new_path.append((current, from_col, neighbor, to_col))
                    queue.append((neighbor, new_path))
                    
        return None

    def analyze_schema_relationships(self, relevant_tables: List[Dict]) -> List[Dict]:
        """
        Analyze relationships between tables using explicit pathfinding.
        If tables aren't directly connected, it finds the bridge tables.
        Also includes ALL direct FK connections for the retrieved tables.
        """
        if not relevant_tables or len(relevant_tables) < 2:
            return []
            
        table_names = [t['table'] for t in relevant_tables]
        relationships = []
        covered_pairs = set()
        
        # Connect all subsequent tables to the primary table via BFS
        base_table = table_names[0]
        
        for i in range(1, len(table_names)):
            target = table_names[i]
            path = self._find_path(base_table, target)
            
            if path:
                for (from_tbl, from_col, to_tbl, to_col) in path:
                    pair_key = tuple(sorted([from_tbl, to_tbl]))
                    if pair_key not in covered_pairs:
                        covered_pairs.add(pair_key)
                        relationships.append({
                            'from_table': from_tbl,
                            'from_column': from_col,
                            'to_table': to_tbl,
                            'to_column': to_col
                        })
        
        # Also include ALL direct FK connections between retrieved tables
        # (even ones not in the BFS path) so LLM has full picture
        for t_name in table_names:
            if t_name in self.graph:
                for neighbor, connections in self.graph[t_name].items():
                    if neighbor in table_names:
                        for conn in connections:
                            source_col, target_col = conn
                            # Avoid exact duplicates AND reverse duplicates
                            # (A.x=B.y is the same relationship as B.y=A.x)
                            already_exists = any(
                                (r['from_table'] == t_name and r['from_column'] == source_col and
                                 r['to_table'] == neighbor and r['to_column'] == target_col) or
                                (r['from_table'] == neighbor and r['from_column'] == target_col and
                                 r['to_table'] == t_name and r['to_column'] == source_col)
                                for r in relationships
                            )
                            if not already_exists:
                                relationships.append({
                                    'from_table': t_name,
                                    'from_column': source_col,
                                    'to_table': neighbor,
                                    'to_column': target_col
                                })
        
        logger.info(f"SchemaAnalyzer found {len(relationships)} relationships: {relationships}")
        return relationships

    def enhance_schema_context(self, schema_context: str, relationships: List[Dict]) -> str:
        """
        Add explicit JOIN paths and cardinalities to the schema context fed to the LLM.
        Outputs ALL FK connections so the LLM can see every possible join path.
        """
        if not relationships:
            return schema_context
            
        hints = "\n=== EXPLICIT JOIN PATHS (MANDATORY) ===\n"
        hints += "CRITICAL: You MUST use the exact columns specified below for joining these tables.\n"
        hints += "DO NOT assume the join uses '.id' unless explicitly specified here.\n"
        hints += "The FIRST path listed for each table pair is the RECOMMENDED one.\n\n"
        
        for rel in relationships:
            if 'from_column' in rel and 'to_column' in rel:
                cardinality = self._detect_cardinality(rel, relationships)
                # Form explicit ON clause
                join_str = f"JOIN {rel['to_table']} ON {rel['from_table']}.{rel['from_column']} = {rel['to_table']}.{rel['to_column']}"
                hints += f"- {join_str} (cardinality: {cardinality})\n"
                
                if cardinality == "1:N":
                    hints += f"  [WARN] WARNING: {rel['to_table']} to {rel['from_table']} has a 1:N cardinality. Use GROUP BY to prevent row duplication.\n"
                    
                # Add generic warnings to prevent joining on internal auto-increment primary keys
                if rel['from_column'] != 'id' and rel['to_column'] != 'id':
                    hints += f"  [WARN] CRITICAL: The join target is `{rel['to_column']}`. Do NOT join on `{rel['to_table']}.id`. The `.id` column is an internal auto-increment PK and will produce wrong results.\n"
        
        return schema_context + "\n" + hints

    def _detect_cardinality(self, relationship, all_relationships):
        """Detect cardinality explicitly from db_schema.json foreign keys definition."""
        from_table = relationship['from_table']
        to_table = relationship['to_table']
        from_col = relationship['from_column']

        # Check if from_table has an FK to to_table
        from_table_data = next((t for t in self.schema_data if t['table_name'] == from_table), None)
        if from_table_data:
            for fk in from_table_data.get('foreign_keys', []):
                if fk.get('column') == from_col and to_table in fk.get('references', ''):
                    # Table with the FK is usually the Many (N) side
                    return fk.get('cardinality', 'N:1')
                    
        # Check reverse direction
        to_table_data = next((t for t in self.schema_data if t['table_name'] == to_table), None)
        if to_table_data:
            for fk in to_table_data.get('foreign_keys', []):
                if fk.get('column') == relationship['to_column'] and from_table in fk.get('references', ''):
                    # We are the referenced table, so we are the 1 side
                    # Let's check what the schema says, and reverse it if necessary
                    raw_card = fk.get('cardinality', 'N:1')
                    if raw_card == 'N:1': return '1:N'
                    if raw_card == '1:N': return 'N:1'
                    return raw_card

        # Default fallback
        return "1:N"
