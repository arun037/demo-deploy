from typing import Dict, List, Any, Tuple
from backend.core.logger import logger

class TypeAnalyzer:
    def __init__(self):
        pass

    def analyze_column_types(self, relevant_tables: List[Dict]) -> Dict[Tuple[str, str], Dict]:
        """
        Analyze column types and return type information for comparisons.
        Returns dict mapping (table, column) -> type info
        """
        type_map = {}
        
        for table in relevant_tables:
            table_name = table['table']
            columns = table.get('columns', [])
            
            # Columns might be strings (from schema text) or dicts. 
            # In embedding_retriever, they are usually just names or creating schema context strings.
            # We need to parse the schema context or rely on available metadata.
            # Assuming 'columns' is a list of strings "name (type)" or just names if metadata is limited.
            # The user doc implies we have column definitions.
            
            for col_def in columns:
                col_name, col_type = self._parse_column_definition(col_def)
                if col_name and col_type:
                    type_map[(table_name, col_name)] = {
                        'type': col_type,
                        'needs_cast': self._needs_casting(col_type),
                        'cast_type': self._suggest_cast_type(col_type),
                        'table': table_name,
                        'column': col_name
                    }
        
        return type_map

    def detect_type_mismatch(self, col1_info: Dict, col2_info: Dict) -> Tuple[bool, bool, str]:
        """
        Detect if two columns have type mismatch that needs casting.
        Returns (has_mismatch, needs_cast, cast_suggestion)
        """
        type1 = col1_info.get('type', '').upper()
        type2 = col2_info.get('type', '').upper()
        
        # Check for text vs decimal mismatch
        is_text1 = 'TEXT' in type1 or 'VARCHAR' in type1
        is_decimal1 = 'DECIMAL' in type1 or 'FLOAT' in type1 or 'DOUBLE' in type1 or 'NUMERIC' in type1
        
        is_text2 = 'TEXT' in type2 or 'VARCHAR' in type2
        is_decimal2 = 'DECIMAL' in type2 or 'FLOAT' in type2 or 'DOUBLE' in type2 or 'NUMERIC' in type2
        
        if (is_text1 and is_decimal2) or (is_text2 and is_decimal1):
            if is_text1:
                return True, True, f"CAST({col1_info.get('table', 't1')}.{col1_info.get('column', 'c1')} AS DECIMAL(20,8))"
            else:
                return True, True, f"CAST({col2_info.get('table', 't2')}.{col2_info.get('column', 'c2')} AS DECIMAL(20,8))"
        
        return False, False, None

    def _parse_column_definition(self, col_def: str) -> Tuple[str, str]:
        """Parse 'name (type)' string"""
        if isinstance(col_def, str):
            if '(' in col_def and ')' in col_def:
                parts = col_def.split('(')
                name = parts[0].strip()
                type_str = parts[1].split(')')[0].strip()
                return name, type_str
            return col_def.strip(), "UNKNOWN"
        return None, None

    def _needs_casting(self, col_type: str) -> bool:
        return 'TEXT' in col_type.upper() or 'VARCHAR' in col_type.upper()

    def _suggest_cast_type(self, col_type: str) -> str:
        if 'TEXT' in col_type.upper():
            return 'DECIMAL(20,8)'
        return None
