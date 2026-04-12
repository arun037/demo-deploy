import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.core.logger import logger


class DataProfiler:
    """
    Intelligent data profiler that analyzes DataFrames for the LLM planner.
    Provides: schema, quality scores, target recommendations, and top correlations.
    """

    @staticmethod
    def sanitize(obj: Any) -> Any:
        """Recursively converts NaN/Infinity to None for JSON safety."""
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            f = float(obj)
            return None if (np.isnan(f) or np.isinf(f)) else f
        elif isinstance(obj, dict):
            return {k: DataProfiler.sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DataProfiler.sanitize(v) for v in obj]
        elif isinstance(obj, np.ndarray):
            return DataProfiler.sanitize(obj.tolist())
        return obj

    @staticmethod
    def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates comprehensive intelligent profile:
        - Schema (Columns, Types)
        - Missing Data Analysis
        - Cardinality + Value Distributions
        - Correlations (Numeric) with Top Pairs
        - Descriptive Stats (Mean, Median, Skew)
        - Data Quality Score (0-100)
        - Target Column Recommendations
        """
        if df.empty:
            return {"error": "Empty DataFrame"}

        profile = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": {}
        }

        # ====== COLUMN-LEVEL PROFILING ======
        quality_penalties = 0
        total_checks = 0
        constant_cols = []
        id_like_cols = []
        target_candidates_classification = []
        target_candidates_regression = []

        for col in df.columns:
            col_data = df[col]
            col_type = str(col_data.dtype)
            nunique = int(col_data.nunique())
            missing_pct = round(col_data.isnull().mean() * 100, 2)

            col_profile = {
                "type": col_type,
                "missing_count": int(col_data.isnull().sum()),
                "missing_pct": missing_pct,
                "unique_count": nunique,
                "sample_values": col_data.dropna().unique()[:5].tolist()
            }

            # Quality checks
            total_checks += 3  # missing, constant, type consistency
            if missing_pct > 50:
                quality_penalties += 2
            elif missing_pct > 20:
                quality_penalties += 1

            if nunique == 1:
                constant_cols.append(col)
                quality_penalties += 1

            # ID-like detection (unique ratio > 95% and numeric)
            if nunique > len(df) * 0.95 and pd.api.types.is_numeric_dtype(col_data):
                id_like_cols.append(col)

            # Target recommendations
            if missing_pct < 30:
                if nunique >= 2 and nunique <= 20 and not col.lower().endswith('_id') and col.lower() not in ('id',):
                    target_candidates_classification.append({
                        "column": col,
                        "n_classes": nunique,
                        "reason": f"{nunique} distinct values  suitable for classification"
                    })
                elif pd.api.types.is_numeric_dtype(col_data) and nunique > 20 and col.lower() not in ('id',) and not col.lower().endswith('_id'):
                    skew_val = float(col_data.skew()) if not col_data.isnull().all() else 0
                    target_candidates_regression.append({
                        "column": col,
                        "skew": round(skew_val, 2),
                        "reason": f"Continuous numeric ({nunique} values)  suitable for regression"
                    })

            # Numeric specific stats
            if pd.api.types.is_numeric_dtype(col_data):
                non_null = col_data.dropna()
                if not non_null.empty:
                    col_profile.update({
                        "mean": round(float(non_null.mean()), 2),
                        "median": round(float(non_null.median()), 2),
                        "std": round(float(non_null.std()), 2),
                        "min": float(non_null.min()),
                        "max": float(non_null.max()),
                        "skew": round(float(non_null.skew()), 2)
                    })

            # Categorical specific
            elif pd.api.types.is_object_dtype(col_data) or hasattr(col_data, 'cat'):
                if nunique < 50:
                    col_profile["value_counts"] = col_data.value_counts().head(10).to_dict()

            # Datetime specific
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                non_null = col_data.dropna()
                if not non_null.empty:
                    col_profile.update({
                        "min_date": str(non_null.min()),
                        "max_date": str(non_null.max()),
                        "date_range_days": (non_null.max() - non_null.min()).days
                    })

            profile["columns"][col] = col_profile

        # ====== CORRELATIONS ======
        numeric_df = df.select_dtypes(include=[np.number])
        top_correlations = []
        if not numeric_df.empty and len(numeric_df.columns) > 1:
            try:
                corr = numeric_df.corr()
                # Extract top correlation pairs (exclude self-correlation)
                pairs_seen = set()
                for i, c1 in enumerate(corr.columns):
                    for j, c2 in enumerate(corr.columns):
                        if i >= j:
                            continue
                        pair_key = tuple(sorted([c1, c2]))
                        if pair_key not in pairs_seen:
                            val = corr.iloc[i, j]
                            if not np.isnan(val) and abs(val) > 0.3:
                                top_correlations.append({
                                    "feature_1": c1,
                                    "feature_2": c2,
                                    "correlation": round(float(val), 3)
                                })
                                pairs_seen.add(pair_key)

                top_correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
                top_correlations = top_correlations[:10]
            except:
                pass

        profile["top_correlations"] = top_correlations

        # ====== DATA QUALITY SCORE ======
        max_penalties = max(total_checks * 2, 1)
        quality_score = max(0, round(100 - (quality_penalties / max_penalties * 100)))
        profile["data_quality"] = {
            "score": quality_score,
            "constant_columns": constant_cols,
            "id_like_columns": id_like_cols,
            "total_missing_pct": round(df.isnull().mean().mean() * 100, 2)
        }

        # ====== TARGET RECOMMENDATIONS ======
        profile["target_recommendations"] = {
            "classification": sorted(target_candidates_classification, key=lambda x: x["n_classes"])[:5],
            "regression": sorted(target_candidates_regression, key=lambda x: abs(x.get("skew", 0)))[:5]
        }

        return DataProfiler.sanitize(profile)

    @staticmethod
    def scan_catalog_lightweight(tables_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Scans all provided tables to create a lightweight catalog for discovery.
        """
        catalog = {}
        for table_name, df in tables_data.items():
            if df.empty:
                continue

            catalog[table_name] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": []
            }

            for col in df.columns:
                catalog[table_name]["columns"].append({
                    "name": col,
                    "type": str(df[col].dtype),
                    "nunique": int(df[col].nunique()),
                    "missing_pct": round(df[col].isnull().mean() * 100, 1),
                    "sample": df[col].dropna().unique()[:3].tolist()
                })
        return DataProfiler.sanitize(catalog)
