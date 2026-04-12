import pandas as pd
import numpy as np
from typing import Dict, Any, List
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix
from backend.core.logger import logger


class ExplainabilityService:
    """
    Generates statistical explanations for models.
    Supports: feature importance (permutation), NxN confusion matrix with labels,
    target distributions, and lightweight driver analysis.
    """

    @staticmethod
    def calculate_feature_importance(model, X_test, y_test, feature_names: List[str]) -> List[Dict[str, Any]]:
        """
        Calculates permutation importance (unbiased, model-agnostic).
        Returns sorted list of {feature, importance, std}.
        """
        try:
            result = permutation_importance(
                model, X_test, y_test,
                n_repeats=10, random_state=42, n_jobs=-1
            )

            importances = result.importances_mean
            stds = result.importances_std

            feature_imp = []
            for i, imp in enumerate(importances):
                if i < len(feature_names):
                    # Clean feature name for display
                    clean_name = feature_names[i]
                    for prefix in ['num__', 'cat__', 'remainder__']:
                        clean_name = clean_name.replace(prefix, '')

                    feature_imp.append({
                        "feature": clean_name,
                        "importance": round(float(imp), 4),
                        "std": round(float(stds[i]), 4)
                    })

            # Sort by absolute importance descending
            feature_imp.sort(key=lambda x: abs(x["importance"]), reverse=True)

            # Return top 15 (more context for narrative)
            return feature_imp[:15]
        except Exception as e:
            logger.warning(f"Explainability Error (Importance): {e}")
            return []

    @staticmethod
    def calculate_distribution(df: pd.DataFrame, column: str, bins: int = 10) -> Dict[str, Any]:
        """
        Generates histogram data for the target variable.
        Handles numeric, datetime, and categorical types.
        """
        try:
            if column not in df.columns:
                return {}

            data = df[column].dropna()

            if pd.api.types.is_numeric_dtype(data) and not pd.api.types.is_datetime64_any_dtype(data):
                hist, bin_edges = np.histogram(data, bins=bins)
                return {
                    "type": "numeric",
                    "bins": [f"{round(bin_edges[i], 2)} - {round(bin_edges[i+1], 2)}" for i in range(len(hist))],
                    "counts": hist.tolist()
                }
            elif pd.api.types.is_datetime64_any_dtype(data):
                counts = data.dt.date.value_counts().sort_index().tail(bins)
                return {
                    "type": "datetime",
                    "bins": [d.strftime("%Y-%m-%d") for d in counts.index],
                    "counts": counts.values.tolist()
                }
            else:
                counts = data.value_counts().head(10)
                return {
                    "type": "categorical",
                    "bins": [str(b) for b in counts.index.tolist()],
                    "counts": counts.values.tolist()
                }
        except Exception as e:
            logger.warning(f"Explainability Error (Distribution): {e}")
            return {}

    @staticmethod
    def calculate_confusion_matrix(y_true, y_pred) -> Dict[str, Any]:
        """
        Generates NxN confusion matrix with class labels.
        Returns: {labels: [...], matrix: [[...], ...]}
        """
        try:
            labels = sorted(list(set(list(y_true) + list(y_pred))))
            cm = confusion_matrix(y_true, y_pred, labels=labels)
            return {
                "labels": [str(l) for l in labels],
                "matrix": cm.tolist()
            }
        except Exception as e:
            logger.warning(f"Explainability Error (Confusion Matrix): {e}")
            return {"labels": [], "matrix": []}

    @staticmethod
    def analyze_drivers(df: pd.DataFrame, target_col: str) -> List[Dict[str, Any]]:
        """
        Lightweight 'on-the-fly' driver analysis for Chat Explanations.
        """
        try:
            from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder

            df_clean = df.copy().dropna()
            if df_clean.empty or target_col not in df_clean.columns:
                return []

            le = LabelEncoder()
            for col in df_clean.columns:
                if df_clean[col].dtype == 'object' or df_clean[col].dtype.name == 'category':
                    df_clean[col] = df_clean[col].astype(str)
                    df_clean[col] = le.fit_transform(df_clean[col])

            X = df_clean.drop(columns=[target_col])
            y = df_clean[target_col]

            is_classification = y.dtype == 'object' or y.nunique() < 20
            model = (
                RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
                if is_classification
                else RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
            )
            model.fit(X, y)

            return ExplainabilityService.calculate_feature_importance(model, X, y, X.columns.tolist())

        except Exception as e:
            logger.warning(f"Explainability Error (Drivers): {e}")
            return []
