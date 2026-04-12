"""
Data Sampler - Samples actual data values from database for intelligent clarification
Provides real options (department names, status values) and detects data patterns

Adapted from research-implement for backend
"""
from backend.core.database import DatabaseManager
from backend.core.logger import logger
import time

class DataSampler:
    def __init__(self, db_manager: DatabaseManager, retriever=None):
        self.db = db_manager
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache
        
        # Store retriever reference for accessing schema
        self.retriever = retriever
        
        # Get all table names from schema
        self.all_tables = []
        if retriever and hasattr(retriever, 'schema_data'):
            self.all_tables = [table['table_name'] for table in retriever.schema_data]
    
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
    
    # Column types that cannot meaningfully be sampled with GROUP BY
    _UNSAMPLEABLE_TYPES = {
        'TEXT', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT',
        'BLOB', 'LONGBLOB', 'MEDIUMBLOB', 'TINYBLOB',
        'JSON', 'BIT', 'BINARY', 'VARBINARY',
    }

    def sample_column_values(self, table, column, limit=10, col_type=None):
        """
        Sample distinct values from a column with counts and percentages.
        Returns list of {value, count, percentage}

        Args:
            table     : table name (unqualified)
            column    : column name
            limit     : max rows to return
            col_type  : declared SQL type of the column (e.g. 'VARCHAR', 'TEXT').
                        When provided, columns with unsampleable types are skipped
                        immediately without hitting the database.
        """
        # Type-safety guard: skip columns that can't be meaningfully GROUP-BY'd
        if col_type:
            base_type = col_type.upper().split('(')[0].strip()
            if base_type in self._UNSAMPLEABLE_TYPES:
                logger.debug(f"Skipping sample for {table}.{column} — unsampleable type: {col_type}")
                return []

        cache_key = f"{table}.{column}"
        
        # Check cache
        if cache_key in self.cache:
            if time.time() - self.cache[cache_key]['timestamp'] < self.cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return self.cache[cache_key]['data']
        
        try:
            # Get database-qualified table name
            qualified_table = self._get_qualified_table_name(table)
            
            # Sample data — lightweight query, no window function overhead
            sql = f"""
            SELECT 
                {column} as value,
                COUNT(*) as count
            FROM {qualified_table}
            WHERE {column} IS NOT NULL AND {column} != ''
            GROUP BY {column}
            ORDER BY count DESC
            LIMIT {limit}
            """
            
            result_df = self.db.execute_query_safe(sql)
            
            # Format results
            samples = []
            for _, row in result_df.iterrows():
                samples.append({
                    'value': row['value'],
                    'count': int(row['count']),
                })
            
            # Cache results
            self.cache[cache_key] = {
                'data': samples,
                'timestamp': time.time()
            }
            
            logger.debug(f"Sampled {len(samples)} values from {table}.{column}")
            return samples
        
        except Exception as e:
            logger.error(f"Failed to sample {table}.{column}: {e}")
            return []
    
    def detect_date_range(self, table, column):
        """
        Detect min/max dates in a column.
        Returns {min_date, max_date, total_records}
        """
        cache_key = f"{table}.{column}.daterange"
        
        # Check cache
        if cache_key in self.cache:
            if time.time() - self.cache[cache_key]['timestamp'] < self.cache_ttl:
                return self.cache[cache_key]['data']
        
        try:
            # Get database-qualified table name
            qualified_table = self._get_qualified_table_name(table)
            
            sql = f"""
            SELECT 
                MIN({column}) as min_date,
                MAX({column}) as max_date,
                COUNT(*) as total_records
            FROM {qualified_table}
            WHERE {column} IS NOT NULL
            """
            
            result_df = self.db.execute_query_safe(sql)
            
            if not result_df.empty:
                row = result_df.iloc[0]
                date_range = {
                    'min_date': str(row['min_date']),
                    'max_date': str(row['max_date']),
                    'total_records': int(row['total_records'])
                }
                
                # Cache results
                self.cache[cache_key] = {
                    'data': date_range,
                    'timestamp': time.time()
                }
                
                return date_range
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to detect date range for {table}.{column}: {e}")
            return None
    
    def get_column_stats(self, table, column):
        """
        Get basic statistics for a column.
        Returns {distinct_count, total_count, null_count, null_percentage}
        """
        cache_key = f"{table}.{column}.stats"
        
        # Check cache
        if cache_key in self.cache:
            if time.time() - self.cache[cache_key]['timestamp'] < self.cache_ttl:
                return self.cache[cache_key]['data']
        
        try:
            # Get database-qualified table name
            qualified_table = self._get_qualified_table_name(table)
            
            sql = f"""
            SELECT 
                COUNT(DISTINCT {column}) as distinct_count,
                COUNT(*) as total_count,
                SUM(CASE WHEN {column} IS NULL OR {column} = '' THEN 1 ELSE 0 END) as null_count
            FROM {qualified_table}
            """
            
            result_df = self.db.execute_query_safe(sql)
            
            if not result_df.empty:
                row = result_df.iloc[0]
                total = int(row['total_count'])
                null_count = int(row['null_count'])
                
                stats = {
                    'distinct_count': int(row['distinct_count']),
                    'total_count': total,
                    'null_count': null_count,
                    'null_percentage': round((null_count / total * 100) if total > 0 else 0, 1)
                }
                
                # Cache results
                self.cache[cache_key] = {
                    'data': stats,
                    'timestamp': time.time()
                }
                
                return stats
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to get stats for {table}.{column}: {e}")
            return None
    
    def should_ask_about_column(self, table, column):
        """
        Determine if we should ask clarification questions about this column.
        Returns (should_ask: bool, reason: str)
        """
        stats = self.get_column_stats(table, column)
        
        if not stats:
            return False, "No stats available"
        
        # Skip if column is mostly null
        if stats['null_percentage'] > 90:
            return False, f"Column is {stats['null_percentage']}% null"
        
        # Skip if only one distinct value
        if stats['distinct_count'] == 1:
            return False, "Only one distinct value"
        
        # Skip if no data
        if stats['total_count'] == 0:
            return False, "No data in column"
        
        return True, "Column has meaningful data"
    
    def format_sampled_data_for_prompt(self, table, columns):
        """
        Format sampled data for inclusion in LLM prompt.
        Returns formatted string with actual values and distributions.
        """
        formatted = f"\n=== SAMPLED DATA FROM {table} ===\n"
        
        for col in columns:
            col_name = col['name']
            col_type = col['type']
            
            # Sample categorical columns
            if col_type in ['VARCHAR', 'CHAR', 'TEXT', 'ENUM']:
                if any(keyword in col_name.lower() for keyword in ['status', 'type', 'dept', 'location', 'category']):
                    should_ask, reason = self.should_ask_about_column(table, col_name)
                    
                    if should_ask:
                        samples = self.sample_column_values(table, col_name, limit=5)
                        if samples:
                            formatted += f"\n{col_name} (top values):\n"
                            for sample in samples:
                                formatted += f"  - {sample['value']} ({sample['count']} records, {sample['percentage']}%)\n"
            
            # Detect date ranges
            elif col_type in ['DATE', 'DATETIME', 'TIMESTAMP']:
                date_range = self.detect_date_range(table, col_name)
                if date_range:
                    formatted += f"\n{col_name} range:\n"
                    formatted += f"  - From: {date_range['min_date']}\n"
                    formatted += f"  - To: {date_range['max_date']}\n"
                    formatted += f"  - Total records: {date_range['total_records']}\n"
        
        return formatted if len(formatted) > 50 else ""
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache = {}
        logger.info("Data sampler cache cleared")
