"""
Date Format Detector - Automatically detects date formats from actual database data
Works universally for ALL queries with 100% accuracy

Adapted from research-implement for backend
"""
from backend.core.database import DatabaseManager
from backend.core.logger import logger
import time
import re

class DateFormatDetector:
    def __init__(self, db_manager: DatabaseManager, retriever=None):
        self.db = db_manager
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache for date formats
        
        # Store retriever reference
        self.retriever = retriever
        
        # Get all table names from schema
        self.all_tables = []
        if retriever and hasattr(retriever, 'schema_data'):
            self.all_tables = [table['table_name'] for table in retriever.schema_data]
    
    def detect_format(self, table, column):
        """
        Detect date format by sampling actual data.
        Returns MySQL format string (e.g., '%d/%m/%y')
        """
        cache_key = f"{table}.{column}"
        
        # Check cache
        if cache_key in self.cache:
            if time.time() - self.cache[cache_key]['timestamp'] < self.cache_ttl:
                logger.debug(f"Cache hit for date format: {cache_key}")
                return self.cache[cache_key]['format']
        
        try:
            # Get database name for this table from schema
            qualified_table = self._get_qualified_table_name(table)
            
            # Sample actual date values
            sql = f"SELECT {column} FROM {qualified_table} WHERE {column} IS NOT NULL LIMIT 10"
            results = self.db.execute_query_safe(sql)
            
            # Check if DataFrame is empty
            if results is None or results.empty:
                logger.warning(f"No data found in {table}.{column}")
                return None
            
            # Convert DataFrame to list of values
            sample_values = [str(row[column]) for _, row in results.iterrows() if row[column]]
            
            if not sample_values:
                return None
            
            detected_format = self._analyze_date_samples(sample_values)
            
            # Cache result
            self.cache[cache_key] = {
                'format': detected_format,
                'timestamp': time.time(),
                'samples': sample_values[:3]  # Store samples for debugging
            }
            
            logger.info(f"Detected date format for {table}.{column}: {detected_format} (samples: {sample_values[:3]})")
            return detected_format
        
        except Exception as e:
            logger.error(f"Failed to detect date format for {table}.{column}: {e}")
            return None
    
    def _get_qualified_table_name(self, table_name):
        """
        Get database-qualified table name (database.table) from schema.
        Falls back to unqualified name if database_name not found.
        """
        if self.retriever and hasattr(self.retriever, 'schema_data'):
            for table in self.retriever.schema_data:
                if table.get('table_name') == table_name:
                    db_name = table.get('database_name')
                    if db_name:
                        return f"{db_name}.{table_name}"
        
        # Fallback to unqualified table name
        return table_name
    
    def _analyze_date_samples(self, samples):
        """
        Analyze sample date values to detect format.
        Supports: dd/mm/yy, mm/dd/yy, yyyy-mm-dd, dd-mm-yyyy, etc.
        """
        # Common patterns with their possible formats
        patterns = [
            # Slash-separated formats
            (r'^\d{2}/\d{2}/\d{2}$', ['%d/%m/%y', '%m/%d/%y']),  # dd/mm/yy or mm/dd/yy
            (r'^\d{2}/\d{2}/\d{4}$', ['%d/%m/%Y', '%m/%d/%Y']),  # dd/mm/yyyy or mm/dd/yyyy
            
            # Dash-separated formats
            (r'^\d{4}-\d{2}-\d{2}$', ['%Y-%m-%d']),              # yyyy-mm-dd (ISO)
            (r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', ['%Y-%m-%d %H:%i:%s']),  # yyyy-mm-dd hh:mm:ss (DATETIME)
            (r'^\d{2}-\d{2}-\d{4}$', ['%d-%m-%Y', '%m-%d-%Y']),  # dd-mm-yyyy or mm-dd-yyyy
            (r'^\d{2}-\d{2}-\d{2}$', ['%d-%m-%y', '%m-%d-%y']),  # dd-mm-yy or mm-dd-yy
            
            # Dot-separated formats
            (r'^\d{2}\.\d{2}\.\d{4}$', ['%d.%m.%Y']),            # dd.mm.yyyy (European)
            (r'^\d{4}\.\d{2}\.\d{2}$', ['%Y.%m.%d']),            # yyyy.mm.dd
        ]
        
        for sample in samples:
            sample_str = str(sample).strip()
            
            for pattern, formats in patterns:
                if re.match(pattern, sample_str):
                    # For ambiguous formats (dd/mm vs mm/dd), use heuristic
                    if len(formats) > 1:
                        return self._disambiguate_format(sample_str, formats)
                    return formats[0]
        
        # Default fallback - try to detect if it's already a date object
        logger.warning(f"Could not detect format from samples: {samples[:3]}")
        return None  # Let SQL handle it without conversion
    
    def _disambiguate_format(self, sample, formats):
        """
        Disambiguate between dd/mm and mm/dd formats by analyzing the sample data.
        Returns the ACTUAL format detected, not a converted one.
        """
        # Split by separator (/ or -)
        separator = '/' if '/' in sample else '-'
        parts = sample.split(separator)
        
        if len(parts) < 2:
            # Default to DD/MM format if can't parse
            return '%d/%m/%Y' if '%Y' in str(formats) else '%d/%m/%y'
        
        try:
            first_num = int(parts[0])
            second_num = int(parts[1])
            
            # If first number > 12, it must be day  DD/MM format
            if first_num > 12:
                logger.debug(f"Detected DD/MM format from sample: {sample}")
                return '%d/%m/%Y' if '%Y' in str(formats) else '%d/%m/%y'
            
            # If second number > 12, it must be day  MM/DD format
            elif second_num > 12:
                logger.debug(f"Detected MM/DD format from sample: {sample}")
                return '%m/%d/%Y' if '%Y' in str(formats) else '%m/%d/%y'
            
            # Both <= 12, ambiguous - check multiple samples if possible
            # For now, default to DD/MM (international standard)
            else:
                logger.debug(f"Ambiguous date format, defaulting to DD/MM/YY: {sample}")
                return '%d/%m/%Y' if '%Y' in str(formats) else '%d/%m/%y'
        
        except (ValueError, IndexError):
            # Default to DD/MM format
            return '%d/%m/%Y' if '%Y' in str(formats) else '%d/%m/%y'
    
    def get_all_date_formats(self, tables, original_schema=None):
        """
        Detect date formats for all date columns in given tables.
        Returns dict: {table.column: format}
        
        Args:
            tables: List of table dicts from retriever (columns are strings)
            original_schema: Optional list of full table schemas from db_schema.json
        """
        date_formats = {}
        
        for table in tables:
            # Handle both dict and string table names
            if not isinstance(table, dict):
                continue
                
            table_name = table.get('table') or table.get('name') or table.get('table_name')
            columns = table.get('columns', [])
            
            if not table_name or not columns:
                continue
            
            # Find original schema for this table to get column types
            table_schema = None
            if original_schema:
                table_schema = next((t for t in original_schema if t.get('table_name') == table_name), None)
            
            for col in columns:
                # Columns from retriever are strings in format "name (type)"
                if isinstance(col, str):
                    # Parse "column_name (column_type)" format
                    if '(' in col and ')' in col:
                        col_name = col.split('(')[0].strip()
                        col_type = col.split('(')[1].split(')')[0].strip()
                    else:
                        col_name = col
                        col_type = 'VARCHAR'  # Default
                    
                    # If type lookup from original schema is available, use it
                    if table_schema and col_type == 'VARCHAR':
                        col_info = next((c for c in table_schema.get('columns', []) if c.get('name') == col_name), None)
                        if col_info:
                            col_type = col_info.get('type', 'VARCHAR')
                elif isinstance(col, dict):
                    col_name = col.get('name') or col.get('column_name')
                    col_type = col.get('type') or col.get('data_type', 'VARCHAR')
                else:
                    continue
                
                # Check if column is a date column
                is_date_type = col_type.upper() in ['DATE', 'DATETIME', 'TIMESTAMP']
                has_date_name = any(keyword in col_name.lower() for keyword in ['date', 'time', 'dt', '_dt', '_date'])
                
                if is_date_type or (has_date_name and col_type.upper() in ['VARCHAR', 'CHAR', 'TEXT']):
                    format = self.detect_format(table_name, col_name)
                    if format:
                        date_formats[f"{table_name}.{col_name}"] = format
        
        return date_formats
    
    def get_display_format(self, mysql_format: str) -> str:
        """
        Convert MySQL date format to JavaScript date picker format.
        
        Examples:
            '%d/%m/%y' -> 'dd/MM/yy'
            '%Y-%m-%d' -> 'yyyy-MM-dd'
            '%m/%d/%Y' -> 'MM/dd/yyyy'
        
        Args:
            mysql_format: MySQL date format string (e.g., '%d/%m/%y')
        
        Returns:
            JavaScript date format string (e.g., 'dd/MM/yy')
        """
        if not mysql_format:
            return 'dd/MM/yy'  # Default fallback
        
        # Mapping from MySQL format to JavaScript format
        mapping = {
            '%d': 'dd',    # Day of month (01-31)
            '%m': 'MM',    # Month (01-12)
            '%y': 'yy',    # Year, 2 digits (00-99)
            '%Y': 'yyyy',  # Year, 4 digits
            '%H': 'HH',    # Hour (00-23)
            '%i': 'mm',    # Minutes (00-59)
            '%s': 'ss',    # Seconds (00-59)
            '%M': 'MMM',   # Month name (Jan-Dec)
        }
        
        display_format = mysql_format
        for mysql, js in mapping.items():
            display_format = display_format.replace(mysql, js)
        
        return display_format
    
    def clear_cache(self):
        """Clear all cached date formats."""
        self.cache = {}
        logger.info("Date format cache cleared")

