"""
Comparison Engine - Period-over-Period Comparisons

Calculates comparison metrics between current and previous periods.
"""

from typing import Dict, Any, Optional
from backend.core.logger import logger


class ComparisonEngine:
    """Calculates period-over-period comparisons"""
    
    def __init__(self, db_manager, sql_injector, period_calculator):
        self.db = db_manager
        self.injector = sql_injector
        self.calculator = period_calculator
    
    def compare(
        self, 
        sql: str, 
        date_info: Dict[str, Any], 
        current_period: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Execute query for current and previous period, return comparison
        
        Returns:
        {
            "current_value": 18859338,
            "previous_value": 16234567,
            "change_absolute": 2624771,
            "change_percent": 16.2,
            "trend": "up"
        }
        """
        try:
            # Execute for current period
            current_sql = self.injector.inject_filter(sql, date_info, current_period)
            current_result = self.db.execute_query_safe(current_sql)
            
            if current_result.empty:
                return None
            
            # Get first column, first row value
            current_value = float(current_result.iloc[0, 0]) if current_result.iloc[0, 0] is not None else 0
            
            # Calculate previous period
            previous_period = self.calculator.calculate_previous_period(current_period)
            
            # Execute for previous period
            previous_sql = self.injector.inject_filter(sql, date_info, previous_period)
            previous_result = self.db.execute_query_safe(previous_sql)
            
            if previous_result.empty:
                previous_value = 0
            else:
                previous_value = float(previous_result.iloc[0, 0]) if previous_result.iloc[0, 0] is not None else 0
            
            # Calculate metrics
            change_absolute = current_value - previous_value
            
            if previous_value != 0:
                change_percent = (change_absolute / previous_value) * 100
            else:
                change_percent = 100 if current_value > 0 else 0
            
            return {
                "current_value": current_value,
                "previous_value": previous_value,
                "change_absolute": change_absolute,
                "change_percent": round(change_percent, 1),
                "trend": "up" if change_absolute > 0 else "down" if change_absolute < 0 else "flat"
            }
            
        except Exception as e:
            logger.error(f"Error calculating comparison: {e}")
            return None
    
    def can_compare(self, insight: Dict[str, Any]) -> bool:
        """Check if insight supports comparison"""
        # Only KPI cards can be compared (single value)
        return insight.get("viz_type") == "kpi_card"
