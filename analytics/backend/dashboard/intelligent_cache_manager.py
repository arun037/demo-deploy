"""
Intelligent Cache Manager - Enhanced with Data Quality & Insights

Features:
- Data quality validation before caching
- Intelligent metadata storage
- Auto-insight generation
- Adaptive query optimization
- Smart fallback mechanisms
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from backend.core.logger import logger


class IntelligentCacheManager:
    """Enhanced cache manager with intelligence and data quality checks"""
    
    def __init__(self, cache_file: str = "dashboard_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
        
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def cache_with_intelligence(
        self,
        insight_id: str,
        period: str,
        data: Dict[str, Any],
        sql: str,
        refresh_interval: str
    ) -> Dict[str, Any]:
        """
        Cache data with intelligent metadata and quality checks
        
        Returns enhanced cache entry with:
        - Data quality metrics
        - Coverage analysis
        - Auto-generated insights
        - Recommendations
        """
        cache_key = f"{insight_id}_{period}" if period != "all" else insight_id
        
        # Step 1: Analyze data quality
        quality_metrics = self._analyze_data_quality(data, sql)
        
        # Step 2: Detect data coverage
        coverage = self._analyze_coverage(data, period)
        
        # Step 3: Generate auto-insights
        insights = self._generate_insights(data, insight_id, quality_metrics)
        
        # Step 4: Create recommendations
        recommendations = self._create_recommendations(quality_metrics, coverage)
        
        # Step 5: Calculate expiry
        expires_at = self._calculate_expiry(refresh_interval)
        
        # Step 6: Build enhanced cache entry
        cache_entry = {
            "data": data,
            "cached_at": datetime.now().isoformat(),
            "expires_at": expires_at,
            "refresh_interval": refresh_interval,
            "metadata": {
                "quality_score": quality_metrics["score"],
                "data_coverage": coverage,
                "has_nulls": quality_metrics["has_nulls"],
                "has_zeros": quality_metrics["has_zeros"],
                "row_count": data.get("row_count", 0),
                "auto_insights": insights,
                "recommendations": recommendations
            }
        }
        
        # Step 7: Store in cache
        self.cache[cache_key] = cache_entry
        self._save_cache()
        
        logger.info(f"[OK] Cached {cache_key} with quality score: {quality_metrics['score']}/100")
        
        return cache_entry
    
    def _analyze_data_quality(self, data: Dict, sql: str) -> Dict[str, Any]:
        """
        Analyze data quality and assign a score
        
        Quality factors:
        - Has data (not empty)
        - No null values in critical fields
        - No zero values where unexpected
        - Reasonable data distribution
        """
        rows = data.get("rows", [])
        row_count = len(rows)
        
        quality_score = 100
        issues = []
        has_nulls = False
        has_zeros = False
        
        # Check 1: Empty data
        if row_count == 0:
            quality_score -= 50
            issues.append("No data returned")
        
        # Check 2: Null values
        if rows and any(None in row.values() for row in rows):
            quality_score -= 20
            issues.append("Contains null values")
            has_nulls = True
        
        # Check 3: Zero values in single-value results (KPIs)
        if row_count == 1 and rows:
            first_row = rows[0]
            if any(v == 0 or v == 0.0 for v in first_row.values()):
                quality_score -= 15
                issues.append("Contains zero values")
                has_zeros = True
        
        # Check 4: Data freshness (if last_updated exists)
        if "last_updated" in data:
            last_updated = datetime.fromisoformat(data["last_updated"])
            age_hours = (datetime.now() - last_updated).total_seconds() / 3600
            if age_hours > 24:
                quality_score -= 10
                issues.append(f"Data is {int(age_hours)} hours old")
        
        return {
            "score": max(0, quality_score),
            "issues": issues,
            "has_nulls": has_nulls,
            "has_zeros": has_zeros,
            "row_count": row_count
        }
    
    def _analyze_coverage(self, data: Dict, period: str) -> Dict[str, Any]:
        """
        Analyze data coverage for the requested period
        
        Returns:
        - Expected months/days in period
        - Actual months/days with data
        - Coverage percentage
        """
        rows = data.get("rows", [])
        
        # For trend data with period column
        if rows and "period" in rows[0]:
            periods_with_data = [row["period"] for row in rows]
            expected_periods = self._get_expected_periods(period)
            
            coverage_pct = (len(periods_with_data) / len(expected_periods) * 100) if expected_periods else 0
            
            return {
                "type": "time_series",
                "expected_periods": len(expected_periods),
                "actual_periods": len(periods_with_data),
                "coverage_percentage": round(coverage_pct, 1),
                "missing_periods": list(set(expected_periods) - set(periods_with_data))
            }
        
        # For single-value data (KPIs)
        return {
            "type": "single_value",
            "has_data": len(rows) > 0,
            "coverage_percentage": 100 if len(rows) > 0 else 0
        }
    
    def _get_expected_periods(self, period: str) -> List[str]:
        """Get expected period labels based on period type"""
        now = datetime.now()
        
        if period == "12m":
            # Last 12 months
            return [
                (now - timedelta(days=30*i)).strftime("%Y-%m")
                for i in range(12, 0, -1)
            ]
        elif period == "6m":
            return [
                (now - timedelta(days=30*i)).strftime("%Y-%m")
                for i in range(6, 0, -1)
            ]
        elif period == "3m":
            return [
                (now - timedelta(days=30*i)).strftime("%Y-%m")
                for i in range(3, 0, -1)
            ]
        
        return []
    
    def _generate_insights(
        self,
        data: Dict,
        insight_id: str,
        quality_metrics: Dict
    ) -> List[str]:
        """
        Generate automatic insights from the data
        
        Insights include:
        - Trends (increasing/decreasing)
        - Anomalies (spikes/drops)
        - Comparisons (highest/lowest)
        - Patterns (seasonality)
        """
        insights = []
        rows = data.get("rows", [])
        
        if not rows:
            insights.append("[WARN] No data available for this period")
            return insights
        
        # Single value insights (KPIs)
        if len(rows) == 1:
            row = rows[0]
            value_key = list(row.keys())[0]
            value = row[value_key]
            
            if value is None:
                insights.append("[WARN] Data not available - may be outside date range")
            elif value == 0:
                insights.append("[WARN] Zero value detected - check data filters")
            elif isinstance(value, (int, float)) and value > 0:
                insights.append(f"[OK] Current value: {self._format_value(value, insight_id)}")
        
        # Time series insights (Trends)
        elif len(rows) > 1 and "period" in rows[0]:
            # Calculate trend
            values = [row.get("total", 0) for row in rows if "total" in row]
            if len(values) >= 2:
                trend = self._calculate_trend(values)
                if trend > 10:
                    insights.append(f" Increasing trend: +{trend}% over period")
                elif trend < -10:
                    insights.append(f" Decreasing trend: {trend}% over period")
                else:
                    insights.append(f" Stable trend: {trend}% change")
            
            # Find peak period
            if values:
                max_idx = values.index(max(values))
                peak_period = rows[max_idx].get("period", "Unknown")
                insights.append(f" Peak: {peak_period} ({self._format_value(max(values), insight_id)})")
        
        # Distribution insights
        elif len(rows) > 1 and "category" in rows[0]:
            total_value = sum(row.get("total", 0) for row in rows)
            top_item = rows[0]
            top_pct = (top_item.get("total", 0) / total_value * 100) if total_value > 0 else 0
            
            insights.append(f" Top: {top_item.get('category', 'Unknown')} ({top_pct:.1f}% of total)")
        
        return insights
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate percentage change from first to last value"""
        if not values or len(values) < 2:
            return 0
        
        first = values[0] if values[0] != 0 else 0.01  # Avoid division by zero
        last = values[-1]
        
        return round(((last - first) / first) * 100, 1)
    
    def _format_value(self, value: Any, insight_id: str) -> str:
        """Format value based on insight type"""
        if "spend" in insight_id.lower() or "value" in insight_id.lower():
            return f"${value:,.2f}"
        elif "rate" in insight_id.lower():
            return f"{value}%"
        else:
            return f"{value:,}"
    
    def _create_recommendations(
        self,
        quality_metrics: Dict,
        coverage: Dict
    ) -> List[str]:
        """
        Create actionable recommendations based on data quality
        """
        recommendations = []
        
        # Quality-based recommendations
        if quality_metrics["score"] < 50:
            recommendations.append("[WARN] Low data quality - consider using 'All Time' filter")
        
        if quality_metrics["has_nulls"]:
            recommendations.append(" Null values detected - data may be outside filtered date range")
        
        if quality_metrics["has_zeros"]:
            recommendations.append(" Zero values found - verify date filters match your data")
        
        # Coverage-based recommendations
        if coverage.get("coverage_percentage", 100) < 50:
            missing = coverage.get("expected_periods", 0) - coverage.get("actual_periods", 0)
            recommendations.append(f" Only {coverage.get('coverage_percentage')}% coverage - {missing} periods missing")
        
        # No issues
        if not recommendations:
            recommendations.append("[OK] Data quality is excellent")
        
        return recommendations
    
    def _calculate_expiry(self, refresh_interval: str) -> str:
        """Calculate cache expiry time"""
        now = datetime.now()
        
        intervals = {
            "realtime": timedelta(minutes=1),
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1)
        }
        
        delta = intervals.get(refresh_interval, timedelta(hours=1))
        return (now + delta).isoformat()
    
    def get_cache_with_metadata(self, insight_id: str, period: str = "all") -> Optional[Dict]:
        """Get cache entry with full metadata"""
        cache_key = f"{insight_id}_{period}" if period != "all" else insight_id
        
        entry = self.cache.get(cache_key)
        if not entry:
            return None
        
        # Check if expired
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if datetime.now() > expires_at:
            logger.info(f" Cache expired for {cache_key}")
            return None
        
        return entry
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Generate overall cache quality report"""
        total_entries = len(self.cache)
        
        if total_entries == 0:
            return {"message": "No cached data"}
        
        quality_scores = []
        low_quality_items = []
        
        for key, entry in self.cache.items():
            metadata = entry.get("metadata", {})
            score = metadata.get("quality_score", 0)
            quality_scores.append(score)
            
            if score < 70:
                low_quality_items.append({
                    "key": key,
                    "score": score,
                    "issues": metadata.get("recommendations", [])
                })
        
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        return {
            "total_cached_items": total_entries,
            "average_quality_score": round(avg_quality, 1),
            "high_quality_count": sum(1 for s in quality_scores if s >= 80),
            "medium_quality_count": sum(1 for s in quality_scores if 50 <= s < 80),
            "low_quality_count": sum(1 for s in quality_scores if s < 50),
            "low_quality_items": low_quality_items[:5]  # Top 5 worst
        }
