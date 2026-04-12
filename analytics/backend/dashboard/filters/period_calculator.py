"""
Period Calculator - Date Range Calculations

Calculates date ranges for different time periods.
"""

from datetime import datetime, timedelta
from typing import Dict, Any


class PeriodCalculator:
    """Calculates date ranges for different time periods"""
    
    PERIODS = {
        "7d": {"days": 7, "label": "Last 7 Days"},
        "30d": {"days": 30, "label": "Last 30 Days"},
        "90d": {"days": 90, "label": "Last 90 Days"},
        "3m": {"months": 3, "label": "Last 3 Months"},
        "4m": {"months": 4, "label": "Last 4 Months"},
        "6m": {"months": 6, "label": "Last 6 Months"},
        "9m": {"months": 9, "label": "Last 9 Months"},
        "12m": {"months": 12, "label": "Last 12 Months"},
        "ytd": {"type": "ytd", "label": "Year to Date"},
        "qtd": {"type": "qtd", "label": "Quarter to Date"},
        "mtd": {"type": "mtd", "label": "Month to Date"},
        "all": {"type": "all", "label": "All Time"}
    }
    
    def calculate(self, period: str) -> Dict[str, Any]:
        """
        Calculate date range for a period
        
        Returns:
        {
            "start": "2025-12-22",
            "end": "2026-01-22",
            "label": "Last 30 Days",
            "days": 30
        }
        """
        now = datetime.now()
        
        if period not in self.PERIODS:
            period = "all"  # Default
        
        config = self.PERIODS[period]
        
        # Handle special periods
        if config.get("type") == "ytd":
            start = datetime(now.year, 1, 1)
            end = now
        elif config.get("type") == "qtd":
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            start = datetime(now.year, quarter_start_month, 1)
            end = now
        elif config.get("type") == "mtd":
            start = datetime(now.year, now.month, 1)
            end = now
        elif config.get("type") == "all":
            start = datetime(1970, 1, 1)  # Very old date
            end = now
        elif "days" in config:
            start = now - timedelta(days=config["days"])
            end = now
        elif "months" in config:
            # Approximate months as 30 days each
            start = now - timedelta(days=config["months"] * 30)
            end = now
        else:
            start = now - timedelta(days=30)
            end = now
        
        return {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "label": config["label"],
            "days": (end - start).days,
            "period_code": period
        }
    
    def calculate_previous_period(self, current_period: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate the previous period for comparison
        
        For "Last 30 Days", returns the 30 days before that
        """
        start = datetime.strptime(current_period["start"], "%Y-%m-%d")
        end = datetime.strptime(current_period["end"], "%Y-%m-%d")
        duration = (end - start).days
        
        # Previous period is same duration, ending when current starts
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=duration)
        
        return {
            "start": prev_start.strftime("%Y-%m-%d"),
            "end": prev_end.strftime("%Y-%m-%d"),
            "label": f"Previous {current_period['label']}",
            "days": duration,
            "period_code": "previous"
        }
    
    def get_all_periods(self):
        """Get list of all available periods"""
        return [
            {"code": code, "label": config["label"]}
            for code, config in self.PERIODS.items()
        ]
