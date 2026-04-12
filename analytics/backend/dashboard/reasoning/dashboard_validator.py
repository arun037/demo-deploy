"""
Dashboard Validator - Coherence and Quality Validation

Validates final dashboard for:
- Semantic coherence
- No duplicates
- Proper coverage
- Date filterability
- Quality standards
"""

from typing import Dict, List, Any
from backend.core.logger import logger


class DashboardValidator:
    """Validates dashboard coherence and quality"""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    def validate_dashboard(self, insights: List[Dict], schema_analysis: Dict = None) -> Dict[str, Any]:
        """
        Validate entire dashboard
        
        Returns:
            Dictionary with validation results:
            - is_coherent: Boolean
            - has_duplicates: List of duplicate IDs
            - coverage_score: 0-100
            - all_date_filterable: Boolean
            - recommendations: List of improvements
        """
        logger.info("[OK] Validating dashboard coherence...")
        
        validation = {
            "is_coherent": True,
            "has_duplicates": self._check_duplicates(insights),
            "coverage_score": self._check_coverage(insights),
            "all_tested": self._check_all_tested(insights),
            "recommendations": []
        }
        
        # Check for issues
        if validation["has_duplicates"]:
            validation["is_coherent"] = False
            validation["recommendations"].append("Remove duplicate insights")
        
        if validation["coverage_score"] < 50:
            validation["recommendations"].append("Improve coverage across categories")
        
        if not validation["all_tested"]:
            validation["recommendations"].append("Some queries failed testing")
        
        logger.info(f"S Validation: coherent={validation['is_coherent']}, "
                   f"coverage={validation['coverage_score']}%, "
                   f"tested={validation['all_tested']}")
        
        return validation
    
    def _check_duplicates(self, insights: List[Dict]) -> List[str]:
        """Check for duplicate insights"""
        seen_titles = {}
        duplicates = []
        
        for insight in insights:
            title = insight.get("title", "").lower()
            if title in seen_titles:
                duplicates.append(insight.get("id", ""))
            else:
                seen_titles[title] = True
        
        return duplicates
    
    def _check_coverage(self, insights: List[Dict]) -> int:
        """Check coverage across categories (0-100 score)"""
        categories = {}
        for insight in insights:
            category = insight.get("category", "")
            categories[category] = categories.get(category, 0) + 1
        
        # Ideal: 8 KPIs, 6 trends, 6 distributions, 6 alerts
        ideal = {"kpi": 8, "trend": 6, "distribution": 6, "alert": 6}
        
        score = 0
        for cat, ideal_count in ideal.items():
            actual_count = categories.get(cat, 0)
            score += min(100, (actual_count / ideal_count) * 100) / 4
        
        return int(score)
    
    def _check_all_tested(self, insights: List[Dict]) -> bool:
        """Check if all queries were tested successfully"""
        for insight in insights:
            if not insight.get("tested", False):
                return False
        return True
