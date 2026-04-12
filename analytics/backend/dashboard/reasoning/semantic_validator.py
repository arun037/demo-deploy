"""
Semantic Validation Layer - Ensures SQL matches title/description semantics

This validator catches:
1. Duplicate insights (same SQL, different titles)
2. Semantic mismatches (title says "rate" but SQL is just count)
3. Format errors (currency labeled as percentage)
4. Missing business logic (status codes without labels)
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from backend.core.logger import logger


class SemanticValidator:
    """Validates that insight plans make semantic sense"""
    
    def __init__(self):
        self.seen_queries = {}  # Track queries to detect duplicates
        
    def validate_insight_plan(self, insight_plan: Dict) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate semantic correctness of an insight plan
        
        Returns: (is_valid, error_message, warnings)
        """
        warnings = []
        
        # Check 1: Semantic correctness (title vs SQL)
        is_valid, error = self._check_semantic_match(insight_plan)
        if not is_valid:
            return False, error, warnings
        
        # Check 2: Format correctness
        is_valid, error = self._check_format_correctness(insight_plan)
        if not is_valid:
            return False, error, warnings
        
        # Check 3: Duplicate detection
        is_duplicate, original_id = self._check_duplicate(insight_plan)
        if is_duplicate:
            return False, f"Duplicate of '{original_id}' - same SQL query", warnings
        
        # Check 4: Status code warnings
        if self._has_unlabeled_status_codes(insight_plan):
            warnings.append("Uses numeric status codes without labels - consider adding CASE statement")
        
        return True, None, warnings
    
    def _check_semantic_match(self, plan: Dict) -> Tuple[bool, Optional[str]]:
        """Check if SQL matches the semantic intent of title/description"""
        title = plan.get("title", "").lower()
        description = plan.get("description", "").lower()
        sql = plan.get("sql", "").upper()
        
        # Rule 1: "rate", "percentage", "ratio" should have division or multiplication by 100
        if any(word in title or word in description for word in ["rate", "percentage", "ratio", "%"]):
            # Exception: if it's explicitly about "growth rate" and uses time series, it's okay
            if "growth" not in title and "trend" not in title:
                if "/" not in sql and "* 100" not in sql and "/ COUNT" not in sql:
                    return False, f"Title/description suggests rate/percentage but SQL appears to be just a count or sum. Expected division or ratio calculation."
        
        # Rule 2: "average" or "avg" should use AVG()
        if "average" in title or "avg" in title:
            if "AVG(" not in sql and "AVG (" not in sql:
                return False, f"Title suggests average but SQL doesn't use AVG() function"
        
        # Rule 3: "total" with aggregation should use SUM() or COUNT()
        if "total" in title:
            if "SUM(" not in sql and "COUNT(" not in sql:
                # Could be okay if it's a trend (GROUP BY with COUNT/SUM)
                if "GROUP BY" not in sql:
                    return False, f"Title suggests total but SQL doesn't use SUM() or COUNT()"
        
        # Rule 4: "distribution" or "breakdown" should have GROUP BY
        category = plan.get("category", "")
        if category == "distribution":
            if "GROUP BY" not in sql:
                return False, f"Distribution insight must have GROUP BY clause"
        
        return True, None
    
    def _check_format_correctness(self, plan: Dict) -> Tuple[bool, Optional[str]]:
        """Check if format matches the metric type"""
        title = plan.get("title", "").lower()
        description = plan.get("description", "").lower()
        format_type = plan.get("format", "")
        
        # Rule 1: Revenue, investment, value, amount should be currency
        if any(word in title or word in description for word in ["revenue", "investment", "value", "amount", "price", "cost", "mrr", "arr"]):
            if format_type == "percentage":
                return False, f"Financial metric has 'percentage' format - should be 'currency'"
        
        # Rule 2: Rate, percentage should be percentage format
        if any(word in title for word in ["rate", "percentage", "%"]):
            if "growth" not in title:  # Growth rate can be number
                if format_type not in ["percentage", "number"]:
                    return False, f"Rate/percentage metric should have 'percentage' or 'number' format"
        
        return True, None
    
    def _check_duplicate(self, plan: Dict) -> Tuple[bool, Optional[str]]:
        """Check if this SQL query is a duplicate of an existing one"""
        sql = plan.get("sql", "")
        insight_id = plan.get("id", "")
        
        # Normalize SQL for comparison (remove whitespace, lowercase)
        normalized_sql = re.sub(r'\s+', ' ', sql.upper().strip())
        
        if normalized_sql in self.seen_queries:
            original_id = self.seen_queries[normalized_sql]
            return True, original_id
        
        # Store this query
        self.seen_queries[normalized_sql] = insight_id
        return False, None
    
    def _has_unlabeled_status_codes(self, plan: Dict) -> bool:
        """Check if query uses status codes without CASE labels"""
        sql = plan.get("sql", "").upper()
        
        # Check if selecting a status column
        if "STATUS AS CATEGORY" in sql or "SELECT STATUS" in sql:
            # Check if there's a CASE statement
            if "CASE" not in sql:
                return True
        
        return False
    
    def reset(self):
        """Reset duplicate tracking (call between dashboard generations)"""
        self.seen_queries = {}


class BusinessMetricEnhancer:
    """Enhances insights with business logic and proper labeling"""
    
    # Status code mappings for common tables
    STATUS_MAPPINGS = {
        "contracts": {
            "3": "Active",
            "4": "Completed",
            "7": "Pending",
            "68": "On Hold",
            "71": "Cancelled",
            "261": "Suspended",
            "263": "Terminated",
            "266": "Expired",
            "276": "Paused"
        },
        "customers": {
            "3": "Active",
            "4": "Completed",
            "261": "Suspended",
            "263": "Terminated",
            "276": "Paused"
        },
        "concepts": {
            "3": "Active",
            "4": "Completed",
            "71": "Cancelled"
        }
    }
    
    def enhance_insight_plan(self, plan: Dict, table_name: str) -> Dict:
        """Add business logic enhancements to insight plan"""
        
        # Enhancement 1: Add status code labels if needed
        if self._should_add_status_labels(plan, table_name):
            plan = self._add_status_labels(plan, table_name)
        
        # Enhancement 2: Add axis labels for charts
        if plan.get("category") in ["trend", "distribution"]:
            plan = self._add_axis_labels(plan)
        
        return plan
    
    def _should_add_status_labels(self, plan: Dict, table_name: str) -> bool:
        """Check if we should add status labels"""
        sql = plan.get("sql", "").upper()
        
        # Check if selecting status and table has known mappings
        if "STATUS" in sql and "AS CATEGORY" in sql:
            # Extract base table name (remove database prefix)
            base_table = table_name.split(".")[-1] if "." in table_name else table_name
            return base_table in self.STATUS_MAPPINGS
        
        return False
    
    def _add_status_labels(self, plan: Dict, table_name: str) -> Dict:
        """Add CASE statement for status code labels"""
        base_table = table_name.split(".")[-1] if "." in table_name else table_name
        mappings = self.STATUS_MAPPINGS.get(base_table, {})
        
        if not mappings:
            return plan
        
        sql = plan.get("sql", "")
        
        # Build CASE statement
        case_parts = []
        for code, label in mappings.items():
            case_parts.append(f"WHEN {code} THEN '{label}'")
        
        case_statement = f"""CASE status
    {chr(10).join('    ' + part for part in case_parts)}
    ELSE CONCAT('Status ', status)
END"""
        
        # Replace "status as category" with CASE statement
        sql = re.sub(
            r'status\s+as\s+category',
            f"{case_statement} as category",
            sql,
            flags=re.IGNORECASE
        )
        
        plan["sql"] = sql
        logger.info(f"Enhanced '{plan.get('id')}' with status code labels")
        
        return plan
    
    def _add_axis_labels(self, plan: Dict) -> Dict:
        """Add explicit x_axis and y_axis labels for charts"""
        category = plan.get("category")
        title = plan.get("title", "")
        
        if category == "trend":
            plan["x_axis"] = "Time Period"
            plan["y_axis"] = self._extract_metric_name(title)
        elif category == "distribution":
            plan["x_axis"] = self._extract_category_name(title)
            plan["y_axis"] = "Count"
        
        return plan
    
    def _extract_metric_name(self, title: str) -> str:
        """Extract metric name from title for y-axis"""
        # Remove common prefixes
        title = title.replace("Monthly ", "").replace("Trend", "").replace("Growth", "").strip()
        
        # Common patterns
        if "volume" in title.lower():
            return "Volume"
        elif "rate" in title.lower():
            return "Rate (%)"
        elif "revenue" in title.lower() or "investment" in title.lower():
            return "Amount ($)"
        elif "count" in title.lower():
            return "Count"
        else:
            return "Value"
    
    def _extract_category_name(self, title: str) -> str:
        """Extract category name from title for x-axis"""
        # Remove "Distribution by" or "Breakdown by"
        title = title.replace("Distribution by ", "").replace("Breakdown by ", "").strip()
        
        if "status" in title.lower():
            return "Status"
        elif "source" in title.lower():
            return "Source"
        elif "channel" in title.lower():
            return "Channel"
        elif "category" in title.lower():
            return "Category"
        else:
            return "Category"


# Standard business metric templates
BUSINESS_METRIC_TEMPLATES = {
    "lead_conversion_rate": {
        "title": "Lead Conversion Rate",
        "description": "Percentage of leads that successfully converted",
        "sql_template": """SELECT ROUND((COUNT(CASE WHEN {status_col} = '{success_value}' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) as total
FROM {table}
WHERE {date_col} IS NOT NULL""",
        "format": "percentage",
        "category": "kpi",
        "icon": "trending-up"
    },
    "churn_rate": {
        "title": "Customer Churn Rate",
        "description": "Percentage of customers who churned or cancelled",
        "sql_template": """SELECT ROUND((COUNT(CASE WHEN status IN ({churned_statuses}) THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) as total
FROM {table}
WHERE {date_col} IS NOT NULL""",
        "format": "percentage",
        "category": "kpi",
        "icon": "alert-triangle"
    },
    "average_contract_value": {
        "title": "Average Contract Value",
        "description": "Average revenue per active contract",
        "sql_template": """SELECT ROUND(AVG({value_col}), 2) as total
FROM {table}
WHERE status = 3 AND is_deleted = 0""",
        "format": "currency",
        "category": "kpi",
        "icon": "dollar-sign"
    },
    "monthly_recurring_revenue": {
        "title": "Monthly Recurring Revenue (MRR)",
        "description": "Total recurring revenue from active contracts",
        "sql_template": """SELECT ROUND(SUM({monthly_col}), 2) as total
FROM {table}
WHERE status = 3 AND is_deleted = 0""",
        "format": "currency",
        "category": "kpi",
        "icon": "dollar-sign"
    }
}
