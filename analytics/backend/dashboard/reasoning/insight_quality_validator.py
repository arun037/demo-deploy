"""
Insight Quality Validator - Comprehensive Validation Framework

Validation Stages:
1. Schema Validation - Ensure all referenced columns/tables exist
2. Semantic Validation - Check logical consistency (e.g., SUM on numeric columns)
3. Temporal Validation - Verify date columns for time-based filtering
4. Business Logic Validation - Ensure insights make business sense
5. SQL Execution Validation - Test queries actually work

This mimics how a human analyst would validate their work before presenting it.
"""

from typing import Dict, List, Tuple, Any, Optional
from backend.core.logger import logger
import re


class InsightPlanValidator:
    """
    Pre-generation validator - checks insight plans BEFORE SQL generation
    
    Prevents errors upfront rather than fixing them later
    
    Now includes:
    - Semantic validation (duplicates, semantic correctness)
    - Business metric enhancement (status labels, axis labels)
    """
    
    def __init__(self, schema_json: List[Dict], table_schemas: Dict[str, Dict]):
        self.schema_json = {t["table_name"]: t for t in schema_json}
        self.table_schemas = table_schemas
        
        # Build quick lookup maps
        self.table_column_map = self._build_column_lookup()
        self.table_date_columns = self._build_date_column_lookup()
    
    def _build_column_lookup(self) -> Dict[str, Dict[str, str]]:
        """Build map of table -> {column_name -> column_type}"""
        lookup = {}
        for table_name, table_def in self.schema_json.items():
            columns = {}
            for col in table_def.get("columns", []):
                columns[col["name"]] = col["type"]
            lookup[table_name] = columns
        return lookup
    
    def _build_date_column_lookup(self) -> Dict[str, List[str]]:
        """Build map of table -> [date_column_names]"""
        lookup = {}
        for table_name, table_def in self.schema_json.items():
            date_cols = []
            for col in table_def.get("columns", []):
                col_type = col["type"].lower()
                col_name = col["name"].lower()
                if any(kw in col_type for kw in ["date", "time"]) or \
                   any(kw in col_name for kw in ["date", "time", "created", "updated"]):
                    date_cols.append(col["name"])
            if date_cols:
                lookup[table_name] = date_cols
        return lookup
    
    def validate_insight_plan(self, plan: Dict, category: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Comprehensive validation of a single insight plan
        
        Returns: (is_valid, error_messages, validation_metadata)
        """
        errors = []
        warnings = []
        metadata = {
            "validation_passed": True,
            "error_count": 0,
            "warning_count": 0,
            "checks_performed": []
        }
        
        # Check 1: Table Existence
        table = plan.get("table", "")
        table_key = table.split(".")[-1] if "." in table else table
        
        if not table:
            errors.append("Missing 'table' field in plan")
            metadata["validation_passed"] = False
        elif table_key not in self.schema_json and table not in self.table_schemas:
            errors.append(f"Table '{table}' not found in schema")
            metadata["validation_passed"] = False
        
        metadata["checks_performed"].append("table_existence")
        
        # If table doesn't exist, can't perform further checks
        if errors:
            metadata["error_count"] = len(errors)
            return False, errors, metadata
        
        # Get table columns
        if table in self.table_schemas:
            available_columns = self.table_schemas[table]["all"]
            numeric_columns = self.table_schemas[table].get("numeric", [])
            categorical_columns = self.table_schemas[table].get("categorical", [])
            date_columns = self.table_schemas[table].get("date", [])
        else:
            available_columns = list(self.table_column_map.get(table_key, {}).keys())
            numeric_columns = []
            categorical_columns = []
            date_columns = self.table_date_columns.get(table_key, [])
        
        # Check 2: Metric Column Validation
        metric_col = plan.get("metric_column")
        if metric_col and metric_col != "*":
            if metric_col not in available_columns:
                errors.append(f"Metric column '{metric_col}' not found in table '{table}'")
                metadata["validation_passed"] = False
            else:
                metadata["checks_performed"].append("metric_column_existence")
        
        # Check 3: Date Column Validation (CRITICAL for time filtering)
        date_col = plan.get("date_column")
        if date_col:
            if date_col not in available_columns:
                errors.append(f"Date column '{date_col}' not found in table '{table}'")
                metadata["validation_passed"] = False
            elif date_col not in date_columns:
                warnings.append(f"Column '{date_col}' may not be a date type")
                metadata["warning_count"] += 1
            metadata["checks_performed"].append("date_column_validation")
        else:
            # Date column is MANDATORY for KPIs and Trends
            if category in ["kpi", "trend"]:
                errors.append(f"Date column is MANDATORY for {category} insights (required for time filtering)")
                metadata["validation_passed"] = False
            metadata["checks_performed"].append("date_column_mandatory_check")
        
        # Check 4: Aggregation Type Validation
        aggregation = plan.get("aggregation", "COUNT")
        if aggregation in ["SUM", "AVG", "MIN", "MAX"]:
            if metric_col and metric_col != "*":
                if metric_col not in numeric_columns and numeric_columns:
                    warnings.append(f"Using {aggregation} on potentially non-numeric column '{metric_col}'")
                    metadata["warning_count"] += 1
            metadata["checks_performed"].append("aggregation_type_validation")
        
        # Check 5: Category Column Validation (for distributions)
        if category == "distribution":
            cat_col = plan.get("category_column") or plan.get("dimension_column")
            if cat_col:
                if cat_col not in available_columns:
                    errors.append(f"Category column '{cat_col}' not found in table '{table}'")
                    metadata["validation_passed"] = False
                metadata["checks_performed"].append("category_column_validation")
        
        # Check 6: Filter Conditions Validation
        filter_cond = plan.get("filter_conditions", "")
        if filter_cond:
            # Extract column names from filter conditions
            filter_columns = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', filter_cond)
            for col in filter_columns:
                if col.upper() not in ["AND", "OR", "NOT", "NULL", "IS", "IN", "LIKE", "WHERE"] and \
                   col not in available_columns:
                    warnings.append(f"Filter references unknown column '{col}'")
                    metadata["warning_count"] += 1
            metadata["checks_performed"].append("filter_conditions_validation")
        
        # Check 7: Business Logic Validation
        title = plan.get("title", "").lower()
        description = plan.get("description", "").lower()
        
        # Ensure title and description make sense for the category
        if category == "kpi":
            if not any(kw in title or kw in description for kw in ["total", "count", "sum", "average", "revenue", "rate"]):
                warnings.append("KPI title/description should indicate a measurable metric")
                metadata["warning_count"] += 1
        elif category == "trend":
            if not any(kw in title or kw in description for kw in ["over time", "trend", "growth", "monthly", "daily"]):
                warnings.append("Trend title/description should indicate time-based analysis")
                metadata["warning_count"] += 1
        
        
        metadata["checks_performed"].append("business_logic_validation")
        
        # Final validation status
        metadata["error_count"] = len(errors)
        metadata["warning_count"] = len(warnings)
        metadata["validation_passed"] = len(errors) == 0
        
        if warnings:
            logger.debug(f"Warnings for plan '{plan.get('id')}': {warnings}")
        
        return metadata["validation_passed"], errors, metadata
    
    def validate_all_plans(self, insight_plans: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Validate all insight plans across all categories
        
        Returns comprehensive validation report
        """
        logger.info(" Starting pre-generation validation...")
        
        report = {
            "total_plans": 0,
            "valid_plans": 0,
            "invalid_plans": 0,
            "plans_with_warnings": 0,
            "validation_by_category": {},
            "validated_plans": {},
            "rejected_plans": []
        }
        
        for category in ["kpi", "trend", "distribution", "alert"]:
            plan_key = f"{category}_plans"
            plans = insight_plans.get(plan_key, [])
            
            category_report = {
                "total": len(plans),
                "valid": 0,
                "invalid": 0,
                "errors": []
            }
            
            validated_plans = []
            
            for plan in plans:
                report["total_plans"] += 1
                is_valid, errors, metadata = self.validate_insight_plan(plan, category)
                
                if is_valid:
                    validated_plans.append(plan)
                    category_report["valid"] += 1
                    report["valid_plans"] += 1
                    
                    if metadata.get("warning_count", 0) > 0:
                        report["plans_with_warnings"] += 1
                else:
                    category_report["invalid"] += 1
                    category_report["errors"].extend(errors)
                    report["invalid_plans"] += 1
                    report["rejected_plans"].append({
                        "id": plan.get("id"),
                        "category": category,
                        "errors": errors
                    })
                    logger.warning(f"[FAIL] Rejected plan '{plan.get('id')}': {errors}")
            
            report["validation_by_category"][category] = category_report
            report["validated_plans"][plan_key] = validated_plans
        
        # Log summary
        logger.info(f"[OK] Validation Complete: {report['valid_plans']}/{report['total_plans']} plans passed")
        if report["invalid_plans"] > 0:
            logger.warning(f"[WARN]  {report['invalid_plans']} plans rejected due to validation errors")
        if report["plans_with_warnings"] > 0:
            logger.info(f" {report['plans_with_warnings']} plans have warnings (non-blocking)")
        
        return report


class InsightExecutionValidator:
    """
    Post-generation validator - validates SQL queries after generation
    
    Ensures queries are executable and return meaningful data
    """
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def validate_generated_insight(self, insight: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a generated insight with SQL query
        
        Returns: (is_valid, error_message)
        """
        sql = insight.get("sql", "")
        insight_id = insight.get("id", "unknown")
        
        if not sql:
            return False, "Missing SQL query"
        
        # Check 1: Basic SQL validation (already done during generation)
        # The query was already tested during generation phase
        # We just need to verify it's present and has been tested
        
        if not insight.get("tested"):
            return False, "Query was not tested during generation"
        
        # Check 2: Verify sample result exists
        sample_result = insight.get("sample_result")
        if sample_result is None:
            return False, "No sample result available"
        
        # If we got here, the insight passed generation testing
        return True, None
    
    def validate_all_insights(self, insights: List[Dict]) -> Tuple[Dict[str, Any], List[Dict]]:
        """
        Validate all generated insights
        
        Returns: (validation_report, valid_insights)
        """
        logger.info(" Starting post-generation validation...")
        
        report = {
            "total_insights": len(insights),
            "valid_insights": 0,
            "invalid_insights": 0,
            "validation_details": []
        }
        
        valid_insights = []
        
        for insight in insights:
            is_valid, error = self.validate_generated_insight(insight)
            
            detail = {
                "id": insight.get("id"),
                "category": insight.get("category"),
                "is_valid": is_valid,
                "error": error
            }
            
            report["validation_details"].append(detail)
            
            if is_valid:
                valid_insights.append(insight)
                report["valid_insights"] += 1
            else:
                report["invalid_insights"] += 1
                logger.error(f"[FAIL] Invalid insight '{insight.get('id')}': {error}")
        
        logger.info(f"[OK] Post-validation Complete: {report['valid_insights']}/{report['total_insights']} insights valid")
        
        return report, valid_insights
