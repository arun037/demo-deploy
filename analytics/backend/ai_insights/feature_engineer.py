import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, OrdinalEncoder
from sklearn.pipeline import Pipeline
from typing import List, Tuple, Dict, Any
from backend.core.logger import logger


class FeatureEngineer:
    """
    Intelligent feature engineering pipeline.
    Adapts strategy based on data characteristics:
    - Low cardinality categoricals  OneHot
    - High cardinality categoricals  Frequency Encoding
    - Datetime  Rich temporal features
    - Numeric  Outlier clipping + Standard Scaling
    """

    HIGH_CARDINALITY_THRESHOLD = 15  # Above this, use frequency encoding

    def __init__(self):
        self.preprocessor = None
        self.feature_names_out = []
        self.datetime_features = []
        self.freq_maps = {}  # For frequency encoding
        self._original_categorical = []
        self._original_numeric = []

    def fit_transform(self, df: pd.DataFrame, target_col: str) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        Analyzes features, builds an adaptive pipeline, and transforms data.
        Returns: X_transformed, y, metadata
        """
        # Drop missing targets
        df = df.dropna(subset=[target_col]).copy()
        if df.empty:
            raise ValueError(f"Target column '{target_col}' has no valid data after dropping nulls")

        # Separate Features and Target
        X = df.drop(columns=[target_col]).copy()
        y = df[target_col]

        # ============ COLUMN CLASSIFICATION ============
        numeric_features = X.select_dtypes(include=['int64', 'float64', 'int32', 'float32']).columns.tolist()
        datetime_features = X.select_dtypes(include=['datetime64', 'datetime', 'datetimetz']).columns.tolist()
        categorical_features = X.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()

        # Force all categoricals to string (prevent mixed-type errors)
        for col in categorical_features:
            X[col] = X[col].fillna('missing').astype(str)
            X[col] = X[col].replace({'nan': 'missing', 'None': 'missing', 'NaN': 'missing', '': 'missing'})

        self.datetime_features = datetime_features
        self._original_categorical = categorical_features.copy()
        self._original_numeric = numeric_features.copy()

        # ============ DATETIME FEATURE EXTRACTION ============
        derived_numeric = []
        for col in datetime_features:
            if col in X.columns:
                try:
                    X[f'{col}_year'] = X[col].dt.year.astype(float)
                    X[f'{col}_month'] = X[col].dt.month.astype(float)
                    X[f'{col}_dayofweek'] = X[col].dt.dayofweek.astype(float)
                    X[f'{col}_quarter'] = X[col].dt.quarter.astype(float)
                    X[f'{col}_is_weekend'] = (X[col].dt.dayofweek >= 5).astype(float)

                    # Days since epoch (captures recency)
                    epoch = pd.Timestamp('2020-01-01')
                    X[f'{col}_days_since'] = (X[col] - epoch).dt.days.astype(float)

                    new_cols = [f'{col}_year', f'{col}_month', f'{col}_dayofweek',
                                f'{col}_quarter', f'{col}_is_weekend', f'{col}_days_since']
                    derived_numeric.extend(new_cols)
                    X = X.drop(columns=[col])
                except Exception as e:
                    logger.warning(f"Failed to extract datetime features from {col}: {e}")
                    X = X.drop(columns=[col], errors='ignore')

        numeric_features = numeric_features + derived_numeric

        # ============ INTELLIGENT CATEGORICAL ENCODING ============
        low_card_cats = []
        high_card_cats = []
        freq_encoded_features = []

        for col in categorical_features:
            nunique = X[col].nunique()
            if nunique <= self.HIGH_CARDINALITY_THRESHOLD:
                low_card_cats.append(col)
            else:
                high_card_cats.append(col)
                # Frequency Encoding: Replace categories with their frequency
                freq_map = X[col].value_counts(normalize=True).to_dict()
                self.freq_maps[col] = freq_map
                X[f'{col}_freq'] = X[col].map(freq_map).fillna(0.0)
                freq_encoded_features.append(f'{col}_freq')
                X = X.drop(columns=[col])

        numeric_features = numeric_features + freq_encoded_features

        # ============ OUTLIER CLIPPING (Numeric) ============
        for col in numeric_features:
            if col in X.columns:
                try:
                    p1 = X[col].quantile(0.01)
                    p99 = X[col].quantile(0.99)
                    if p1 != p99:
                        X[col] = X[col].clip(lower=p1, upper=p99)
                except:
                    pass

        # ============ BUILD PREPROCESSING PIPELINE ============
        transformers = []

        # Valid numeric features (must exist in X)
        valid_numeric = [c for c in numeric_features if c in X.columns]
        if valid_numeric:
            numeric_transformer = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            transformers.append(('num', numeric_transformer, valid_numeric))

        # Low-cardinality categoricals  OneHot
        valid_low_card = [c for c in low_card_cats if c in X.columns]
        if valid_low_card:
            categorical_transformer = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
                ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False, max_categories=20))
            ])
            transformers.append(('cat', categorical_transformer, valid_low_card))

        if not transformers:
            raise ValueError("No valid features found after preprocessing")

        self.preprocessor = ColumnTransformer(
            transformers=transformers,
            remainder='drop'
        )

        # Fit and Transform
        X_processed = self.preprocessor.fit_transform(X)

        # Capture feature names
        try:
            if hasattr(self.preprocessor, 'get_feature_names_out'):
                self.feature_names_out = self.preprocessor.get_feature_names_out().tolist()
            else:
                self.feature_names_out = [f"feature_{i}" for i in range(X_processed.shape[1])]
        except Exception:
            self.feature_names_out = [f"feature_{i}" for i in range(X_processed.shape[1])]

        metadata = {
            "numeric_features": valid_numeric,
            "low_cardinality_categoricals": valid_low_card,
            "high_cardinality_categoricals": high_card_cats,
            "datetime_features_extracted": datetime_features,
            "freq_encoded_features": freq_encoded_features,
            "final_feature_count": X_processed.shape[1],
            "feature_names": self.feature_names_out,
            "encoding_strategy": {
                "low_card": "OneHotEncoder",
                "high_card": "FrequencyEncoding",
                "numeric": "MedianImputer + StandardScaler + OutlierClip",
                "datetime": "Year/Month/DOW/Quarter/IsWeekend/DaysSince"
            }
        }

        logger.info(f"FeatureEngineer: {len(valid_numeric)} numeric, "
                     f"{len(valid_low_card)} low-card cat, {len(high_card_cats)} high-card cat, "
                     f"{len(datetime_features)} datetime  {X_processed.shape[1]} final features")

        return X_processed, y.values, metadata

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transforms new data using the fitted pipeline.
        """
        X = df.copy()

        # Datetime extraction (must match training)
        if hasattr(self, 'datetime_features'):
            for col in self.datetime_features:
                if col in X.columns:
                    if not pd.api.types.is_datetime64_any_dtype(X[col]):
                        try:
                            X[col] = pd.to_datetime(X[col])
                        except:
                            continue

                    try:
                        epoch = pd.Timestamp('2020-01-01')
                        X[f'{col}_year'] = X[col].dt.year.astype(float)
                        X[f'{col}_month'] = X[col].dt.month.astype(float)
                        X[f'{col}_dayofweek'] = X[col].dt.dayofweek.astype(float)
                        X[f'{col}_quarter'] = X[col].dt.quarter.astype(float)
                        X[f'{col}_is_weekend'] = (X[col].dt.dayofweek >= 5).astype(float)
                        X[f'{col}_days_since'] = (X[col] - epoch).dt.days.astype(float)
                        X = X.drop(columns=[col])
                    except:
                        X = X.drop(columns=[col], errors='ignore')

        # High-cardinality frequency encoding (must match training)
        for col, freq_map in self.freq_maps.items():
            if col in X.columns:
                X[col] = X[col].astype(str)
                X[f'{col}_freq'] = X[col].map(freq_map).fillna(0.0)
                X = X.drop(columns=[col])

        # Force categoricals to string
        for col in self._original_categorical:
            if col in X.columns:
                X[col] = X[col].fillna('missing').astype(str)
                X[col] = X[col].replace({'nan': 'missing', 'None': 'missing', 'NaN': 'missing', '': 'missing'})

        return self.preprocessor.transform(X)
