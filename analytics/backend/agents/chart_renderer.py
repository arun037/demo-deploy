"""
Chart Renderer - Transforms ChartSpecifications into Frontend-Ready Configs

Handles:
- Multi-series data transformation (multi_line, multi_bar)
- Top-N filtering for large datasets
- Data formatting (currency, percentage, number)
- Standardized output format for UI
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from backend.agents.chart_planner import ChartSpecification
from backend.core.logger import logger


class ChartRenderer:
    """
    Renders ChartSpecification objects into frontend-ready chart configurations.
    
    Handles data transformations for multi-series charts and applies formatting.
    """
    
    def __init__(self):
        self.max_categories = 20  # INCREASED: Allow up to 20 bars/points
        logger.info("ChartRenderer initialized with strict safety limits")
        
    def _ensure_serializable_dates(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Ensure datetime columns are converted to string format YYYY-MM-DD"""
        df = df.copy()
        for col in columns:
            if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')
        return df
    
    def render_charts(
        self,
        specs: List[ChartSpecification],
        df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Render chart specifications into frontend configs.
        
        Args:
            specs: List of validated ChartSpecification objects
            df: Source data
            
        Returns:
            List of chart configuration dictionaries
        """
        rendered_charts = []
        
        for spec in specs:
            try:
                chart_config = self._render_single_chart(spec, df)
                if chart_config:
                    rendered_charts.append(chart_config)
                    logger.info(f"ChartRenderer: S Rendered '{spec.title}' ({spec.viz_type})")
            except Exception as e:
                logger.error(f"ChartRenderer: Error rendering '{spec.title}': {e}")
                continue
        
        return rendered_charts
    
    def _render_single_chart(
        self,
        spec: ChartSpecification,
        df: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """Render a single chart specification"""
        
        # Handle different viz types
        if spec.viz_type == 'kpi_card':
            return self._render_kpi_card(spec, df)
        elif spec.viz_type in ['multi_line', 'multi_bar']:
            return self._render_multi_series_chart(spec, df)
        else:
            return self._render_standard_chart(spec, df)
    
    def _render_kpi_card(
        self,
        spec: ChartSpecification,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Render KPI card (single value)"""
        
        # Get the value
        if len(df) == 1:
            value = df[spec.y_column].iloc[0]
        else:
            # Aggregate if multiple rows
            value = df[spec.y_column].sum()
        
        # Format value
        formatted_value = self._format_value(value, spec.format)
        
        return {
            'chart_type': 'kpi',
            'title': spec.title,
            'description': spec.description,
            'value': formatted_value,
            'raw_value': float(value) if pd.notna(value) else 0,
            'format': spec.format,
            'reasoning': spec.reasoning
        }
    
    def _render_standard_chart(
        self,
        spec: ChartSpecification,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Render standard chart (line, bar, pie)"""
        
        # Prepare data
        chart_df = df.copy()
        data_was_modified = False  # Track any sorting/filtering
        
        # 0. Ensure Dates are Strings for X-axis
        if spec.x_column:
             chart_df = self._ensure_serializable_dates(chart_df, [spec.x_column])
        
        # 1. AUTO-AGGREGATION: If raw data (rows == unique categories), aggregate first!
        if spec.x_column and pd.api.types.is_string_dtype(chart_df[spec.x_column]):
            unique_categories = chart_df[spec.x_column].nunique()
            if len(chart_df) > 50 and unique_categories == len(chart_df) and not pd.api.types.is_numeric_dtype(chart_df[spec.y_column]):
                 logger.info(f"ChartRenderer: Detected raw list data for {spec.x_column}, auto-aggregating by count")
                 chart_df = chart_df.groupby(spec.x_column).size().reset_index(name='count')
                 spec.y_column = 'count' # Update spec to reflect new metric
                 data_was_modified = True

        # 2. SORTING & LIMITING LOGIC
        # Apply strict visualization limits regardless of data type
        if spec.x_column:
            
            # Case A: Explicit Limit (Top 10, etc.) requested by Planner
            if hasattr(spec, 'limit') and spec.limit is not None:
                # FORCE CLAMP: Never show more than max_categories even if asked
                limit_n = min(spec.limit, self.max_categories)
                ascending = (spec.sort_order == 'asc')
                logger.info(f"ChartRenderer: Applying Limit: {limit_n} (Clamped from {spec.limit})")
                
                # Sort first
                if pd.api.types.is_numeric_dtype(chart_df[spec.y_column]):
                    chart_df = chart_df.sort_values(by=spec.y_column, ascending=ascending)
                
                # Take the N rows (head gives bottom N if ascending, top N if descending)
                # Note: If we clamp, we should ideally treat the rest as "Others", but for explicit limit 
                # usually we just want the top N.
                chart_df = chart_df.head(limit_n)
                
                # For display: always show bars in descending order (tallest first)
                if pd.api.types.is_numeric_dtype(chart_df[spec.y_column]):
                    chart_df = chart_df.sort_values(by=spec.y_column, ascending=False)
                
                data_was_modified = True
                
            # Case B: Safety Cap (No explicit limit, but too many categories)
            elif chart_df[spec.x_column].nunique() > self.max_categories:

                limit_n = self.max_categories
                logger.info(f"ChartRenderer: Applying Safety Cap: {limit_n} + Others")
                
                # Use "Others" logic ONLY for Safety Cap (Top N + Others)
                if pd.api.types.is_numeric_dtype(chart_df[spec.y_column]):
                    # 1. Identify Top N-1
                    top_n = limit_n - 1
                    top_df = chart_df.nlargest(top_n, spec.y_column)
                    
                    # 2. Identify Tail
                    tail_df = chart_df.drop(top_df.index)
                    
                    # 3. Aggregate Tail
                    agg_func = 'mean' if 'avg' in spec.y_column.lower() or 'average' in spec.y_column.lower() else 'sum'
                    others_value = tail_df[spec.y_column].agg(agg_func)
                    
                    # 4. Create Others Row
                    others_row = {spec.x_column: 'Others', spec.y_column: others_value}
                    for col in chart_df.columns:
                        if col not in others_row:
                            others_row[col] = 'Others' if chart_df[col].dtype == 'object' else 0
                            
                    # 5. Combine and sort descending for display
                    others_df = pd.DataFrame([others_row])
                    chart_df = pd.concat([top_df, others_df], ignore_index=True)
                    chart_df = chart_df.sort_values(by=spec.y_column, ascending=False)
                else:
                     # Fallback for non-numeric
                    top_cats = chart_df[spec.x_column].value_counts().head(limit_n).index
                    chart_df = chart_df[chart_df[spec.x_column].isin(top_cats)]
                
                data_was_modified = True
            
            # Case C: No limit needed, but still sort for good visualization
            elif pd.api.types.is_numeric_dtype(chart_df[spec.y_column]):
                ascending = (spec.sort_order == 'asc')
                chart_df = chart_df.sort_values(by=spec.y_column, ascending=False)  # Always display tallest first
                data_was_modified = True
        
        # Map viz_type to frontend chart_type
        chart_type_mapping = {
            'line_chart': 'line',
            'bar_chart': 'bar',
            'pie_chart': 'pie',
            'area_chart': 'area'
        }
        
        chart_type = chart_type_mapping.get(spec.viz_type, 'bar')
        
        return {
            'chart_type': chart_type,
            'title': spec.title,
            'description': spec.description,
            'x_key': spec.x_column,
            'y_key': spec.y_column,
            'format': spec.format,
            'reasoning': spec.reasoning,
            'data_override': chart_df.to_dict(orient='records') if data_was_modified else None
        }
    
    def _render_multi_series_chart(
        self,
        spec: ChartSpecification,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Render multi-series chart (multi_line, multi_bar).
        
        Transforms data into series format:
        {
            "labels": ["Jan", "Feb", "Mar"],
            "series": [
                {"name": "Product A", "data": [100, 120, 110]},
                {"name": "Product B", "data": [80, 90, 95]}
            ]
        }
        """
        
        if not spec.series_column:
            logger.warning(f"ChartRenderer: Multi-series chart '{spec.title}' missing series_column")
            return self._render_standard_chart(spec, df)
        
        # Validate columns
        if not all(col in df.columns for col in [spec.x_column, spec.y_column, spec.series_column]):
            logger.error(f"ChartRenderer: Missing required columns for multi-series chart")
            return None
        
        # Use pivot_table to transform data for frontend
        # From: [{x: 'A', series: 'S1', val: 10}, {x: 'A', series: 'S2', val: 20}]
        # To:   [{x: 'A', 'S1': 10, 'S2': 20}]
        try:
             # Ensure dates are strings BEFORE pivot to avoid Timestamp column names
            df = self._ensure_serializable_dates(df, [spec.x_column, spec.series_column])
            
            pivot_df = df.pivot_table(
                index=spec.x_column, 
                columns=spec.series_column, 
                values=spec.y_column, 
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            
            # Sort by total value if many categories
            if len(pivot_df) > self.max_categories:
                # Calculate row totals for sorting
                numeric_cols = [c for c in pivot_df.columns if c != spec.x_column]
                pivot_df['__total'] = pivot_df[numeric_cols].sum(axis=1)
                pivot_df = pivot_df.nlargest(self.max_categories, '__total').drop(columns=['__total'])
            
            # Sort columns alphabetically for consistent legend (after limiting rows)
            # This ensures 'Active' comes before 'Inactive' if that's the order, or 2020 before 2021
            final_cols = sorted([c for c in pivot_df.columns if c != spec.x_column])
            pivot_df = pivot_df[[spec.x_column] + final_cols]

            # Convert to records
            pivoted_data = pivot_df.to_dict(orient='records')
            
            # Map viz_type to frontend chart_type
            if spec.viz_type == 'multi_line':
                chart_type = 'multi_line'
                extra_props = {'series_by': spec.series_column}
            else:
                chart_type = 'grouped_bar'  # Map multi_bar to grouped_bar for frontend
                extra_props = {'group_by': spec.series_column}
            
            return {
                'chart_type': chart_type,
                'title': spec.title,
                'description': spec.description,
                'x_key': spec.x_column,
                'y_key': spec.y_column, # Primary metric
                'format': spec.format,
                'reasoning': spec.reasoning,
                'data_override': pivoted_data,
                **extra_props
            }
            
        except Exception as e:
            logger.error(f"ChartRenderer: Pivot failed for {spec.title}: {e}")
            return self._render_standard_chart(spec, df)
    
    def _format_value(self, value: Any, format_type: str) -> str:
        """Format value based on format type"""
        
        if pd.isna(value):
            return "N/A"
        
        try:
            num_value = float(value)
            
            if format_type == 'currency':
                return f"${num_value:,.2f}"
            elif format_type == 'percentage':
                return f"{num_value:.1f}%"
            else:  # number
                if num_value >= 1000:
                    return f"{num_value:,.0f}"
                else:
                    return f"{num_value:.2f}"
        except:
            return str(value)
