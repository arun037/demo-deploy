import numpy as np
import joblib
import pandas as pd
from typing import Dict, Any, Tuple, List
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold
from sklearn.ensemble import (
    RandomForestRegressor, RandomForestClassifier,
    GradientBoostingRegressor, GradientBoostingClassifier,
    ExtraTreesRegressor, ExtraTreesClassifier
)
from sklearn.linear_model import Ridge, LogisticRegression, ElasticNet, SGDClassifier
from sklearn.svm import LinearSVR
from sklearn.metrics import (
    r2_score, accuracy_score, f1_score, mean_absolute_error,
    mean_squared_error, precision_score, recall_score,
    classification_report, roc_auc_score
)
from backend.core.logger import logger

# Optional: XGBoost / LightGBM (graceful fallback)
try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class DataAnalyzer:
    """
    Pre-training data analysis engine.
    Analyzes the data BEFORE choosing algorithms to make intelligent decisions.
    """

    @staticmethod
    def analyze(X: np.ndarray, y: np.ndarray, task_type: str) -> Dict[str, Any]:
        """
        Performs pre-training analysis to guide algorithm selection.
        Returns a report with data characteristics.
        """
        n_samples, n_features = X.shape
        analysis = {
            "n_samples": n_samples,
            "n_features": n_features,
            "feature_to_sample_ratio": n_features / max(n_samples, 1),
            "is_high_dimensional": n_features > n_samples * 0.5,
            "is_small_dataset": n_samples < 500,
            "is_large_dataset": n_samples > 10000,
        }

        # Sparsity analysis
        zero_ratio = np.sum(X == 0) / X.size if X.size > 0 else 0
        analysis["sparsity"] = zero_ratio
        analysis["is_sparse"] = zero_ratio > 0.5

        # Feature variance analysis
        try:
            variances = np.var(X, axis=0)
            analysis["low_variance_features"] = int(np.sum(variances < 0.01))
            analysis["high_variance_ratio"] = float(np.max(variances) / (np.min(variances) + 1e-10))
        except:
            analysis["low_variance_features"] = 0
            analysis["high_variance_ratio"] = 1.0

        # Target analysis
        if task_type == "classification":
            unique_classes = np.unique(y)
            class_counts = np.bincount(y.astype(int)) if np.issubdtype(y.dtype, np.integer) else np.array([np.sum(y == c) for c in unique_classes])
            analysis["n_classes"] = len(unique_classes)
            analysis["is_binary"] = len(unique_classes) == 2
            analysis["is_multiclass"] = len(unique_classes) > 2

            # Imbalance detection
            if len(class_counts) > 1:
                majority = np.max(class_counts)
                minority = np.min(class_counts)
                analysis["imbalance_ratio"] = float(majority / max(minority, 1))
                analysis["is_imbalanced"] = analysis["imbalance_ratio"] > 3.0
            else:
                analysis["imbalance_ratio"] = 1.0
                analysis["is_imbalanced"] = False
        else:
            # Regression target analysis
            analysis["target_skew"] = float(pd.Series(y).skew()) if len(y) > 2 else 0.0
            analysis["is_skewed_target"] = abs(analysis.get("target_skew", 0)) > 1.0
            analysis["target_range"] = float(np.max(y) - np.min(y)) if len(y) > 0 else 0.0

        # Correlation check (linear relationship strength)
        try:
            if n_features > 0 and n_features < 500:
                correlations = np.array([abs(np.corrcoef(X[:, i], y)[0, 1]) for i in range(min(n_features, 50)) if np.std(X[:, i]) > 0])
                correlations = correlations[~np.isnan(correlations)]
                if len(correlations) > 0:
                    analysis["max_linear_corr"] = float(np.max(correlations))
                    analysis["mean_linear_corr"] = float(np.mean(correlations))
                    analysis["has_strong_linear"] = analysis["max_linear_corr"] > 0.5
                else:
                    analysis["has_strong_linear"] = False
            else:
                analysis["has_strong_linear"] = False
        except:
            analysis["has_strong_linear"] = False

        return analysis


class AlgorithmSelector:
    """
    Intelligent algorithm selector based on data analysis.
    No hardcoded choices  everything is data-driven.
    """

    @staticmethod
    def select_models(analysis: Dict[str, Any], task_type: str) -> List[Tuple[str, Any, Dict]]:
        """
        Returns a ranked list of (name, model, hyperparams) based on data characteristics.
        Each model is configured with appropriate hyperparameters for the data.
        """
        models = []
        n_samples = analysis["n_samples"]
        n_features = analysis["n_features"]
        is_small = analysis["is_small_dataset"]
        is_large = analysis["is_large_dataset"]
        is_sparse = analysis.get("is_sparse", False)
        has_linear = analysis.get("has_strong_linear", False)

        # Dynamic estimator count based on dataset size
        n_estimators = 100 if is_small else (200 if not is_large else 300)

        if task_type == "regression":
            # 1. If strong linear correlations exist, linear models are competitive
            if has_linear:
                models.append(("Ridge Regression", Ridge(alpha=1.0), {}))
                models.append(("ElasticNet", ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=2000), {}))

            # 2. Tree-based (always good baselines)
            models.append(("Random Forest", RandomForestRegressor(
                n_estimators=n_estimators, max_depth=None if is_small else 20,
                min_samples_leaf=2, random_state=42, n_jobs=-1
            ), {}))

            # 3. Gradient Boosting (strong for structured data)
            models.append(("Gradient Boosting", GradientBoostingRegressor(
                n_estimators=n_estimators, learning_rate=0.1,
                max_depth=5, subsample=0.8, random_state=42
            ), {}))

            # 4. XGBoost (if available  typically best)
            if HAS_XGBOOST:
                models.append(("XGBoost", XGBRegressor(
                    n_estimators=n_estimators, learning_rate=0.1,
                    max_depth=6, subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbosity=0, n_jobs=-1
                ), {}))

            # 5. LightGBM (fastest for large data)
            if HAS_LIGHTGBM and not is_small:
                models.append(("LightGBM", LGBMRegressor(
                    n_estimators=n_estimators, learning_rate=0.1,
                    max_depth=-1, num_leaves=31, subsample=0.8,
                    random_state=42, verbose=-1, n_jobs=-1
                ), {}))

            # 6. Extra Trees (good for noisy data, high variance features)
            if analysis.get("high_variance_ratio", 1) > 100:
                models.append(("Extra Trees", ExtraTreesRegressor(
                    n_estimators=n_estimators, random_state=42, n_jobs=-1
                ), {}))

        else:  # Classification
            is_binary = analysis.get("is_binary", True)
            is_imbalanced = analysis.get("is_imbalanced", False)
            n_classes = analysis.get("n_classes", 2)

            # Class weight handling for imbalanced data
            class_weight = "balanced" if is_imbalanced else None

            # 1. Logistic Regression (interpretable baseline, good if linear)
            if has_linear or is_small:
                models.append(("Logistic Regression", LogisticRegression(
                    max_iter=2000, class_weight=class_weight,
                    solver='lbfgs' if n_classes <= 10 else 'saga',
                    multi_class='auto', random_state=42
                ), {}))

            # 2. Random Forest (robust baseline)
            models.append(("Random Forest", RandomForestClassifier(
                n_estimators=n_estimators, max_depth=None if is_small else 20,
                min_samples_leaf=2, class_weight=class_weight,
                random_state=42, n_jobs=-1
            ), {}))

            # 3. Gradient Boosting
            models.append(("Gradient Boosting", GradientBoostingClassifier(
                n_estimators=n_estimators, learning_rate=0.1,
                max_depth=5, subsample=0.8, random_state=42
            ), {}))

            # 4. XGBoost
            if HAS_XGBOOST:
                xgb_params = {
                    "n_estimators": n_estimators, "learning_rate": 0.1,
                    "max_depth": 6, "subsample": 0.8, "colsample_bytree": 0.8,
                    "random_state": 42, "verbosity": 0, "n_jobs": -1,
                    "eval_metric": "logloss"
                }
                if is_imbalanced and is_binary:
                    imbalance_ratio = analysis.get("imbalance_ratio", 1.0)
                    xgb_params["scale_pos_weight"] = imbalance_ratio
                models.append(("XGBoost", XGBClassifier(**xgb_params), {}))

            # 5. LightGBM
            if HAS_LIGHTGBM and not is_small:
                lgbm_params = {
                    "n_estimators": n_estimators, "learning_rate": 0.1,
                    "max_depth": -1, "num_leaves": 31, "subsample": 0.8,
                    "random_state": 42, "verbose": -1, "n_jobs": -1,
                    "class_weight": class_weight
                }
                if is_imbalanced and is_binary:
                    lgbm_params["is_unbalance"] = True
                models.append(("LightGBM", LGBMClassifier(**lgbm_params), {}))

            # 6. Extra Trees (good for noisy data)
            if n_features > 20:
                models.append(("Extra Trees", ExtraTreesClassifier(
                    n_estimators=n_estimators, class_weight=class_weight,
                    random_state=42, n_jobs=-1
                ), {}))

        logger.info(f"AlgorithmSelector: Selected {len(models)} candidate models for {task_type} "
                     f"(samples={n_samples}, features={n_features}, "
                     f"linear={has_linear}, sparse={is_sparse})")
        return models


class ModelTrainer:
    """
    Intelligent AutoML engine.
    1. Analyzes data characteristics FIRST
    2. Selects appropriate algorithms based on analysis
    3. Trains all candidates with cross-validation
    4. Returns comprehensive metrics and the best model
    """

    def __init__(self, task_type: str = 'regression'):
        self.task_type = task_type
        self.best_model = None
        self.best_score = -np.inf
        self.metrics = {}
        self.data_analysis = {}

    def train_auto(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Full intelligent training pipeline:
        1. Analyze data
        2. Select algorithms
        3. Train & evaluate all candidates
        4. Pick the best
        """
        # === PHASE 1: PRE-TRAINING DATA ANALYSIS ===
        self.data_analysis = DataAnalyzer.analyze(X, y, self.task_type)
        logger.info(f"DataAnalyzer report: {self.data_analysis}")

        # Guard: single class
        if self.task_type == 'classification' and self.data_analysis.get("n_classes", 0) < 2:
            return {"error": "Target has only one class. Training skipped."}

        # === PHASE 2: INTELLIGENT TRAIN/TEST SPLIT ===
        test_size = 0.2
        if self.task_type == 'classification':
            # Stratified split preserves class distribution
            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42, stratify=y
                )
            except ValueError:
                # Fallback if stratify fails (too few samples in a class)
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42
                )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )

        # === PHASE 3: ALGORITHM SELECTION (DATA-DRIVEN) ===
        candidates = AlgorithmSelector.select_models(self.data_analysis, self.task_type)

        if not candidates:
            return {"error": "No suitable algorithms found for this data."}

        # === PHASE 4: CROSS-VALIDATED TRAINING ===
        n_cv = min(5, max(2, len(y_train) // 50))  # Dynamic CV folds

        if self.task_type == 'classification':
            cv_strategy = StratifiedKFold(n_splits=n_cv, shuffle=True, random_state=42)
            scoring = 'f1_weighted'  # Better than accuracy for imbalanced data
        else:
            cv_strategy = KFold(n_splits=n_cv, shuffle=True, random_state=42)
            scoring = 'r2'

        results = {}
        best_name = None

        for name, model, _ in candidates:
            try:
                cv_scores = cross_val_score(model, X_train, y_train, cv=cv_strategy, scoring=scoring, n_jobs=-1)
                mean_score = cv_scores.mean()
                std_score = cv_scores.std()
                results[name] = {
                    "mean": round(float(mean_score), 4),
                    "std": round(float(std_score), 4)
                }

                logger.info(f"  {name}: {mean_score:.4f}  {std_score:.4f}")

                if mean_score > self.best_score:
                    self.best_score = mean_score
                    self.best_model = model
                    best_name = name
            except Exception as e:
                logger.warning(f"  {name} failed: {e}")
                results[name] = {"mean": 0.0, "std": 0.0, "error": str(e)}

        if self.best_model is None:
            return {"error": "All model candidates failed during training."}

        # === PHASE 5: RETRAIN BEST ON FULL TRAINING SET ===
        self.best_model.fit(X_train, y_train)

        # === PHASE 6: COMPREHENSIVE EVALUATION ===
        y_pred = self.best_model.predict(X_test)

        eval_metrics = {}
        if self.task_type == 'regression':
            eval_metrics['r2'] = round(float(r2_score(y_test, y_pred)), 4)
            eval_metrics['mae'] = round(float(mean_absolute_error(y_test, y_pred)), 4)
            eval_metrics['rmse'] = round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4)
        else:
            eval_metrics['accuracy'] = round(float(accuracy_score(y_test, y_pred)), 4)
            eval_metrics['f1'] = round(float(f1_score(y_test, y_pred, average='weighted', zero_division=0)), 4)
            eval_metrics['precision'] = round(float(precision_score(y_test, y_pred, average='weighted', zero_division=0)), 4)
            eval_metrics['recall'] = round(float(recall_score(y_test, y_pred, average='weighted', zero_division=0)), 4)

            # Per-class report
            try:
                report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
                eval_metrics['per_class'] = {
                    str(k): {
                        "precision": round(v["precision"], 3),
                        "recall": round(v["recall"], 3),
                        "f1": round(v["f1-score"], 3),
                        "support": int(v["support"])
                    }
                    for k, v in report.items()
                    if k not in ['accuracy', 'macro avg', 'weighted avg']
                }
            except:
                pass

        # Store test_set on the instance (not in dict  numpy arrays can't be JSON-serialized)
        self._test_set = (X_test, y_test)

        return {
            "best_model_name": best_name,
            "validation_scores": results,
            "test_metrics": eval_metrics,
            "task_type": self.task_type,
            "data_analysis": {
                k: v for k, v in self.data_analysis.items()
                if not isinstance(v, np.ndarray)
            },
            "algorithms_tried": len(candidates),
            "cv_folds": n_cv,
            "cv_scoring": scoring
        }

    def save_model(self, filepath: str):
        if self.best_model:
            joblib.dump(self.best_model, filepath)

    def load_model(self, filepath: str):
        self.best_model = joblib.load(filepath)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.best_model.predict(X)
