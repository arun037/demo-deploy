"""
Data Explorer - Exploratory Data Analysis

Runs queries against the actual database to understand:
- Row counts per table
- Date ranges for time dimensions
- Sample values for categorical columns
- Metric ranges (min/max)
- Null percentages
- Data quality assessment
"""

from typing import Dict, List, Any
from backend.core.logger import logger


class DataExplorer:
    """Explores actual data in database to inform dashboard generation"""
    
    def __init__(self, db_manager, schema_analysis: Dict):
        self.db = db_manager
        self.schema_analysis = schema_analysis
        self.exploration = {}
    
    def exploration(self) -> Dict[str, Any]:
        """
        Run exploratory queries to understand actual data
        """
        return {}

    def _quote_table(self, table_name: str) -> str:
        """Correctly quote table name with backticks"""
        if "." in table_name:
            parts = table_name.split(".")
            # Quote each part
            return ".".join([f"`{p}`" for p in parts])
        return f"`{table_name}`"
    
    def explore_data(self) -> Dict[str, Any]:
        """
        Run exploratory queries to understand actual data
        
        Returns:
            Dictionary containing:
            - row_counts: Number of rows per table
            - date_ranges: MIN/MAX dates for time columns
            - sample_values: Sample categorical values
            - metric_ranges: MIN/MAX for numeric columns
            - data_quality: Quality assessment
        """
        logger.info(" Starting data exploration...")
        
        self.exploration = {
            "row_counts": self._get_row_counts(),
            "date_ranges": self._get_date_ranges(),
            "sample_values": self._sample_categorical_columns(),
            "metric_ranges": self._get_metric_ranges(),
            "data_quality": self._assess_data_quality()
        }
        
        logger.info(f"S Explored {len(self.exploration['row_counts'])} tables")
        logger.info(f"S Found {len(self.exploration['date_ranges'])} tables with date data")
        
        return self.exploration
    
    def _get_row_counts(self) -> Dict[str, int]:
        """Get row count for each table"""
        row_counts = {}
        
        for table in self.schema_analysis.get("time_dimensions", {}).keys():
            try:
                table_sql = self._quote_table(table)
                sql = f"SELECT COUNT(*) as count FROM {table_sql}"
                result = self.db.execute_query_safe(sql)
                
                # result is a DataFrame
                if result is not None and not result.empty:
                    row_counts[table] = int(result.iloc[0]['count'])
                else:
                    row_counts[table] = 0
                    
            except Exception as e:
                logger.warning(f"Could not get row count for {table}: {e}")
                row_counts[table] = 0
        
        return row_counts
    
    def _get_date_ranges(self) -> Dict[str, Dict]:
        """Get MIN/MAX dates for each time dimension"""
        date_ranges = {}
        time_dimensions = self.schema_analysis.get("time_dimensions", {})
        
        for table, date_columns in time_dimensions.items():
            date_ranges[table] = {}
            
            for date_col in date_columns[:2]:  # Check first 2 date columns
                try:
                    table_sql = self._quote_table(table)
                    sql = f"""
                    SELECT 
                        MIN(`{date_col}`) as min_date,
                        MAX(`{date_col}`) as max_date,
                        COUNT(DISTINCT `{date_col}`) as distinct_dates
                    FROM {table_sql}
                    WHERE `{date_col}` IS NOT NULL
                    """
                    
                    result = self.db.execute_query_safe(sql)
                    
                    # result is a DataFrame
                    if result is not None and not result.empty:
                        date_ranges[table][date_col] = {
                            "min": str(result.iloc[0]['min_date']) if result.iloc[0]['min_date'] else "",
                            "max": str(result.iloc[0]['max_date']) if result.iloc[0]['max_date'] else "",
                            "distinct_count": int(result.iloc[0]['distinct_dates']) if result.iloc[0]['distinct_dates'] else 0
                        }
                        
                except Exception as e:
                    logger.warning(f"Could not get date range for {table}.{date_col}: {e}")
        
        return date_ranges
    
    def _sample_categorical_columns(self) -> Dict[str, Dict]:
        """Get sample values for categorical columns"""
        samples = {}
        dimensions = self.schema_analysis.get("dimensions", {})
        
        for table, dim_columns in list(dimensions.items())[:5]:  # Sample first 5 tables
            samples[table] = {}
            
            for dim_col in dim_columns[:3]:  # Sample first 3 columns per table
                try:
                    table_sql = self._quote_table(table)
                    # Use backticks to handle reserved keywords like 'group'
                    sql = f"""
                    SELECT DISTINCT `{dim_col}` as value
                    FROM {table_sql}
                    WHERE `{dim_col}` IS NOT NULL
                    LIMIT 10
                    """
                    
                    result = self.db.execute_query_safe(sql)
                    
                    # result is a DataFrame
                    if result is not None and not result.empty:
                        samples[table][dim_col] = result['value'].tolist()
                        
                except Exception as e:
                    logger.debug(f"Could not sample {table}.{dim_col}: {e}")
        
        return samples
    
    def _get_metric_ranges(self) -> Dict[str, Dict]:
        """Get MIN/MAX for numeric columns"""
        metric_ranges = {}
        metrics = self.schema_analysis.get("metrics", {})
        
        for table, metric_columns in list(metrics.items())[:5]:  # Sample first 5 tables
            metric_ranges[table] = {}
            
            for metric_col in metric_columns[:3]:  # Sample first 3 metrics per table
                try:
                    table_sql = self._quote_table(table)
                    sql = f"""
                    SELECT 
                        MIN(`{metric_col}`) as min_value,
                        MAX(`{metric_col}`) as max_value,
                        AVG(`{metric_col}`) as avg_value
                    FROM {table_sql}
                    WHERE `{metric_col}` IS NOT NULL
                    """
                    
                    result = self.db.execute_query_safe(sql)
                    
                    # result is a DataFrame
                    if result is not None and not result.empty:
                        metric_ranges[table][metric_col] = {
                            "min": float(result.iloc[0]['min_value']) if result.iloc[0]['min_value'] is not None else 0,
                            "max": float(result.iloc[0]['max_value']) if result.iloc[0]['max_value'] is not None else 0,
                            "avg": float(result.iloc[0]['avg_value']) if result.iloc[0]['avg_value'] is not None else 0
                        }
                        
                except Exception as e:
                    logger.debug(f"Could not get range for {table}.{metric_col}: {e}")
        
        return metric_ranges
    
    def _assess_data_quality(self) -> Dict[str, Any]:
        """Assess data quality across tables"""
        quality = {
            "empty_tables": [],
            "tables_without_dates": [],
            "tables_with_data": [],
            "recommended_tables": []
        }
        
        row_counts = self.exploration.get("row_counts", {})
        date_ranges = self.exploration.get("date_ranges", {})
        
        for table, count in row_counts.items():
            if count == 0:
                quality["empty_tables"].append(table)
            elif count > 100:  # Sufficient data
                quality["tables_with_data"].append(table)
                
                # Has date data?
                if table in date_ranges and date_ranges[table]:
                    quality["recommended_tables"].append({
                        "table": table,
                        "row_count": count,
                        "date_columns": list(date_ranges[table].keys())
                    })
                else:
                    quality["tables_without_dates"].append(table)
        
        logger.info(f" Data Quality: {len(quality['tables_with_data'])} tables with data, "
                   f"{len(quality['empty_tables'])} empty tables")
        
        return quality
