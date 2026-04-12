"""
Chart Type Selection Engine
Rule-based logic to intelligently select appropriate chart types based on data characteristics.
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from backend.core.logger import logger
from backend.utils.sql_analyzer import (
    is_aggregated_query,
    extract_group_by_columns,
    is_metric_column,
    is_date_column,
    should_create_time_series_chart,
    get_valid_metric_columns
)


class ChartSelector:
    """
    Intelligent chart type selector based on data analysis.
    Uses rule-based heuristics to recommend optimal chart types.
    """
    
    def __init__(self):
        self.chart_library = self._init_chart_library()
    
    def _init_chart_library(self) -> Dict[str, Dict[str, Any]]:
        """Define chart type catalog with requirements and best practices."""
        return {
            'kpi': {
                'requires': ['single_value'],
                'best_for': 'displaying key metrics or totals',
                'max_rows': 1,
                'priority': 10  # Highest priority for single values
            },
            'bar': {
                'requires': ['categorical_dimension', 'numeric_metric'],
                'best_for': 'comparing categories or discrete values',
                'max_categories': 20,
                'min_categories': 2,
                'priority': 8
            },
            'line': {
                'requires': ['time_dimension', 'numeric_metric'],
                'best_for': 'showing trends over time',
                'min_points': 3,
                'priority': 9
            },
            'pie': {
                'requires': ['categorical_dimension', 'numeric_metric'],
                'best_for': 'showing part-to-whole relationships',
                'max_categories': 8,
                'min_categories': 2,
                'priority': 6
            },
            'area': {
                'requires': ['time_dimension', 'numeric_metric'],
                'best_for': 'showing cumulative trends over time',
                'min_points': 3,
                'priority': 7
            },
            'scatter': {
                'requires': ['two_numeric_metrics'],
                'best_for': 'showing correlation between two variables',
                'min_points': 5,
                'priority': 5
            }
        }
    
    def analyze_data_pattern(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Deep analysis of DataFrame to identify patterns and characteristics.
        
        Returns:
            Dict with keys:
            - has_time_dimension: bool
            - has_categorical_dimension: bool
            - numeric_columns: List[str]
            - categorical_columns: List[str]
            - time_columns: List[str]
            - row_count: int
            - patterns: List[str] (e.g., ['time_series', 'categorical_breakdown'])
        """
        analysis = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'numeric_columns': [],
            'categorical_columns': [],
            'time_columns': [],
            'patterns': []
        }
        
        # Identify numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        # CRITICAL FIX: Filter out ID columns from metrics
        # IDs are identifiers, not meaningful metrics for visualization
        numeric_cols = [col for col in numeric_cols if is_metric_column(col)]
        logger.info(f"ChartSelector: Filtered numeric columns (excluding IDs): {numeric_cols}")
        
        analysis['numeric_columns'] = numeric_cols
        
        # Identify time/date columns
        date_cols = df.select_dtypes(include=['datetime']).columns.tolist()
        # Also check for date-like string columns
        for col in df.select_dtypes(include=['object']).columns:
            if any(keyword in col.lower() for keyword in ['date', 'time', 'year', 'month', 'day']):
                # Sample a few values to confirm
                sample = df[col].dropna().head(3)
                if len(sample) > 0:
                    # Simple heuristic: if column name suggests date, treat as time dimension
                    date_cols.append(col)

        # Enhanced Numeric Detection: Check for strings that act like numbers (e.g. "$1,200.50")
        for col in df.select_dtypes(include=['object']).columns:
            if col not in date_cols:
                # Sample non-null values
                sample = df[col].dropna().head(3)
                if not sample.empty:
                    # Check if sample looks like currency/number
                    is_dirty_numeric = all(
                        any(c in str(val) for c in ['$', ',']) and 
                        any(char.isdigit() for char in str(val)) 
                        for val in sample
                    )
                    
                    if is_dirty_numeric:
                        try:
                            logger.info(f"ChartSelector: detected dirty numeric column '{col}', cleaning...")
                            # Clean and convert in-place
                            # Remove $, commas, whitespace
                            cleaned = df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
                            df[col] = pd.to_numeric(cleaned, errors='coerce')
                            # Add to numeric_cols if successful
                            if pd.api.types.is_numeric_dtype(df[col]):
                                numeric_cols.append(col)
                                logger.info(f"ChartSelector: successfully converted '{col}' to numeric")
                        except Exception as e:
                            logger.warning(f"ChartSelector: failed to clean numeric column '{col}': {e}")
        
        analysis['time_columns'] = date_cols
        
        # Identify categorical columns (low cardinality)
        cat_cols = []
        for col in df.select_dtypes(include=['object', 'category']).columns:
            if col not in date_cols:  # Exclude time columns
                unique_count = df[col].nunique()
                if 2 <= unique_count < 500:  # Allow higher cardinality for "Top N" charts
                    cat_cols.append(col)
        
        analysis['categorical_columns'] = cat_cols
        
        logger.info(f"ChartSelector: Column analysis - Numeric: {numeric_cols}, Categorical: {cat_cols}, Time: {date_cols}")
        
        # Detect patterns
        if len(df) == 1 and len(numeric_cols) > 0:
            analysis['patterns'].append('single_value')
        
        # CRITICAL FIX: Only add time_series pattern if we have meaningful metrics
        # Don't create time series charts for raw data with just IDs and dates
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            # Only suggest time series if there are actual metrics (not just IDs)
            analysis['patterns'].append('time_series')
        
        # FIXED: Add categorical_breakdown pattern regardless of row count
        if len(cat_cols) > 0 and len(numeric_cols) > 0:
            analysis['patterns'].append('categorical_breakdown')
        
        if len(numeric_cols) >= 2:
            analysis['patterns'].append('multi_metric')
        
        # Set boolean flags
        analysis['has_time_dimension'] = len(date_cols) > 0
        analysis['has_categorical_dimension'] = len(cat_cols) > 0
        analysis['has_numeric_metrics'] = len(numeric_cols) > 0
        
        logger.info(f"ChartSelector: Detected patterns: {analysis['patterns']}")
        
        return analysis
    
    def select_chart_types(self, df: pd.DataFrame, user_query: str = "", sql: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Select appropriate chart types based on data analysis.
        
        Args:
            df: DataFrame to visualize
            user_query: Optional user query for context
            sql: Optional SQL query for aggregation analysis
        
        Returns:
            List of chart recommendations, each with:
            - chart_type: str
            - priority: int
            - reason: str
            - suggested_x: str (column name)
            - suggested_y: str (column name)
        """
        analysis = self.analyze_data_pattern(df)
        recommendations = []
        
        logger.info(f"ChartSelector: Analyzing data - {analysis['row_count']} rows, "
                   f"{len(analysis['numeric_columns'])} numeric cols, "
                   f"{len(analysis['categorical_columns'])} categorical cols, "
                   f"{len(analysis['time_columns'])} time cols")
        
        # Rule 1: Single value  KPI
        if 'single_value' in analysis['patterns']:
            for num_col in analysis['numeric_columns']:
                recommendations.append({
                    'chart_type': 'kpi',
                    'priority': 10,
                    'reason': 'Single row with numeric value - perfect for KPI display',
                    'suggested_x': None,
                    'suggested_y': num_col,
                    'value_column': num_col
                })
        
        # Rule 2: Time series  Line chart (WITH VALIDATION)
        if 'time_series' in analysis['patterns'] and analysis['row_count'] >= 3:
            # CRITICAL FIX: Validate if time series chart is appropriate
            should_create_ts = True
            reason_suffix = f'Time series data with {analysis["row_count"]} points'
            
            if sql:
                should_create_ts, ts_reason = should_create_time_series_chart(sql, analysis['time_columns'])
                if not should_create_ts:
                    logger.info(f"ChartSelector: Skipping time series chart - {ts_reason}")
                else:
                    logger.info(f"ChartSelector: Creating time series chart - {ts_reason}")
                    reason_suffix = ts_reason
            
            if should_create_ts and len(analysis['numeric_columns']) > 0:
                time_col = analysis['time_columns'][0]
                for num_col in analysis['numeric_columns'][:2]:  # Limit to 2 metrics
                    recommendations.append({
                        'chart_type': 'line',
                        'priority': 9,
                        'reason': reason_suffix,
                        'suggested_x': time_col,
                        'suggested_y': num_col
                    })
            elif not should_create_ts:
                # If time series not appropriate, log why
                logger.info(f"ChartSelector: Skipped time series - {ts_reason if sql else 'No SQL provided for validation'}")
        
        # Rule 3: Categorical breakdown  Bar chart
        if 'categorical_breakdown' in analysis['patterns']:
            cat_col = analysis['categorical_columns'][0]
            cat_count = df[cat_col].nunique()
            
            # IMPROVED: Handle large datasets by suggesting top N categories
            if cat_count > 20:
                logger.info(f"ChartSelector: {cat_count} categories detected, will recommend top 15 for visualization")
                # Still recommend bar chart, but note it needs top N filtering
                for num_col in analysis['numeric_columns'][:1]:  # Limit to 1 metric for large datasets
                    recommendations.append({
                        'chart_type': 'bar',
                        'priority': 8,
                        'reason': f'Top 15 categories from {cat_count} total (sorted by {num_col})',
                        'suggested_x': cat_col,
                        'suggested_y': num_col,
                        'needs_top_n': True,  # Flag for data preparation
                        'top_n_limit': 15
                    })
            elif 2 <= cat_count <= 20:
                for num_col in analysis['numeric_columns'][:2]:
                    recommendations.append({
                        'chart_type': 'bar',
                        'priority': 8,
                        'reason': f'Categorical comparison with {cat_count} categories',
                        'suggested_x': cat_col,
                        'suggested_y': num_col
                    })
                
                # Also suggest pie chart if categories are few
                if cat_count <= 8:
                    recommendations.append({
                        'chart_type': 'pie',
                        'priority': 6,
                        'reason': f'Part-to-whole relationship with {cat_count} categories',
                        'suggested_x': cat_col,
                        'suggested_y': analysis['numeric_columns'][0]
                    })
        
        # Rule 4: Multi-metric  Scatter plot (correlation)
        if 'multi_metric' in analysis['patterns'] and analysis['row_count'] >= 5:
            if len(analysis['numeric_columns']) >= 2:
                recommendations.append({
                    'chart_type': 'scatter',
                    'priority': 5,
                    'reason': 'Multiple numeric columns - explore correlation',
                    'suggested_x': analysis['numeric_columns'][0],
                    'suggested_y': analysis['numeric_columns'][1]
                })

        # Rule 5: Fallback for Categorical Counts (No numeric metrics)
        if not analysis['numeric_columns'] and analysis['categorical_columns']:
            # If we have categories but no numbers, visualize the count of items per category
            cat_col = analysis['categorical_columns'][0]
            cat_count = df[cat_col].nunique()
            
            if cat_count <= 20:
                recommendations.append({
                    'chart_type': 'bar',
                    'priority': 7, 
                    'reason': f'Count of items by {cat_col}',
                    'suggested_x': cat_col,
                    'suggested_y': 'count',
                    'is_aggregation': True
                })
            elif cat_count > 20:
                recommendations.append({
                    'chart_type': 'bar',
                    'priority': 7,
                    'reason': f'Top 15 {cat_col} by Count',
                    'suggested_x': cat_col,
                    'suggested_y': 'count',
                    'needs_top_n': True,
                    'is_aggregation': True,
                    'top_n_limit': 15
                })
        
        # Sort by priority (highest first)
        recommendations.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"ChartSelector: Generated {len(recommendations)} chart recommendations")
        for i, rec in enumerate(recommendations[:3]):  # Log top 3
            logger.info(f"  Recommendation {i+1}: {rec['chart_type']} (priority={rec['priority']}) - {rec['reason']}")
        
        return recommendations
    
    def validate_chart_config(self, chart_type: str, df: pd.DataFrame, x_key: str, y_key: str) -> Tuple[bool, str]:
        """
        Validate that a chart configuration is appropriate for the data.
        
        Returns:
            (is_valid, error_message)
        """
        if chart_type not in self.chart_library:
            return False, f"Unknown chart type: {chart_type}"
        
        chart_spec = self.chart_library[chart_type]
        
        # Check row count requirements
        if 'max_rows' in chart_spec and len(df) > chart_spec['max_rows']:
            return False, f"{chart_type} chart requires max {chart_spec['max_rows']} rows, got {len(df)}"
        
        if 'min_points' in chart_spec and len(df) < chart_spec['min_points']:
            return False, f"{chart_type} chart requires min {chart_spec['min_points']} points, got {len(df)}"
        
        # Check column existence
        if x_key and x_key not in df.columns:
            return False, f"X-axis column '{x_key}' not found in data"
        
        if y_key and y_key not in df.columns:
            return False, f"Y-axis column '{y_key}' not found in data"
        
        # Check data types
        if y_key and chart_type != 'kpi':
            if not pd.api.types.is_numeric_dtype(df[y_key]):
                return False, f"Y-axis column '{y_key}' must be numeric for {chart_type} chart"
        
        # Check cardinality for categorical charts
        if chart_type in ['bar', 'pie'] and x_key:
            unique_count = df[x_key].nunique()
            if 'max_categories' in chart_spec and unique_count > chart_spec['max_categories']:
                return False, f"{chart_type} chart supports max {chart_spec['max_categories']} categories, got {unique_count}"
            if 'min_categories' in chart_spec and unique_count < chart_spec['min_categories']:
                return False, f"{chart_type} chart requires min {chart_spec['min_categories']} categories, got {unique_count}"
        
        return True, ""
