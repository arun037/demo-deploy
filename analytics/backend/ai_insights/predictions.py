import pandas as pd
import numpy as np
from typing import Dict, Any
from backend.ai_insights.model_registry import ModelRegistry

class PredictionService:
    """
    Loads trained models and runs inference using ModelRegistry.
    """
    def __init__(self):
        self.registry = ModelRegistry()

    def predict(self, job_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs prediction for a specific job/model.
        """
        try:
            model, preprocessor, metadata = self.registry.load_model(job_id)
        except Exception as e:
             return {"error": f"Model load failed: {str(e)}", "status": "failed"}

        # Convert single input to DataFrame
        df_input = pd.DataFrame([input_data])
        
        # Feature Engineering is now fully handled by the preprocessor's transform method
        # which has been updated to robustly handle type conversions.
        X = df_input.copy()

        try:
            X_transformed = preprocessor.transform(X)
            prediction = model.predict(X_transformed)
            
            return {
                "prediction": float(prediction[0]),
                "status": "success",
                "model_version": metadata.get("created_at")
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
