import os
import joblib
import json
import time
from typing import Dict, Any, Optional, Tuple
from backend.core.logger import logger
from backend.core.database import DatabaseManager
from sqlalchemy import text

class ModelRegistry:
    """
    Centralized manager for storing, loading, and versioning variables ML models.
    """
    
    ROOT_DIR = "models_storage"
    
    def __init__(self):
        os.makedirs(self.ROOT_DIR, exist_ok=True)
        # Simple LRU cache could be added here for frequently accessed models
        self._cache = {}
        try:
            self.db = DatabaseManager()
        except Exception as e:
            logger.error(f"ModelRegistry: Failed to connect to DB: {e}")
            self.db = None

    def save_model(self, job_id: str, model: Any, preprocessor: Any, metadata: Dict[str, Any]) -> str:
        """
        Saves model, preprocessor, and metadata to a dedicated directory AND database.
        Returns the path to the model directory.
        """
        model_dir = os.path.join(self.ROOT_DIR, job_id)
        os.makedirs(model_dir, exist_ok=True)
        
        # Paths
        model_path = os.path.join(model_dir, "model.joblib")
        preprocessor_path = os.path.join(model_dir, "preprocessor.joblib")
        metadata_path = os.path.join(model_dir, "metadata.json")
        
        # Save Artifacts
        joblib.dump(model, model_path)
        joblib.dump(preprocessor, preprocessor_path)
        
        # Enhance metadata
        metadata['created_at'] = time.time()
        metadata['job_id'] = job_id
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info(f"Model saved to {model_dir}")
        
        # Save to Database
        if self.db:
            try:
                task_name = metadata.get('plan', {}).get('task_name', 'Unknown Task')
                target = metadata.get('target', 'Unknown')
                train_results = metadata.get('metrics', {})
                algo = train_results.get('best_model_name', 'Unknown')
                test_metrics = train_results.get('test_metrics', {})
                accuracy = test_metrics.get('accuracy', test_metrics.get('r2', 0.0))
                inputs = json.dumps(metadata.get('input_features', []))
                
                sql = """
                INSERT INTO model_registry 
                (job_id, task_name, target_column, algorithm, accuracy, model_path, inputs, status, created_at)
                VALUES (:job_id, :task_name, :target, :algo, :acc, :path, :inputs, 'completed', NOW())
                ON DUPLICATE KEY UPDATE 
                    accuracy=:acc, status='completed', model_path=:path
                """
                
                with self.db.engine.connect() as conn:
                    conn.execute(text(sql), {
                        "job_id": job_id,
                        "task_name": task_name,
                        "target": target,
                        "algo": algo,
                        "acc": accuracy,
                        "path": model_dir,
                        "inputs": inputs
                    })
                    conn.commit()
                logger.info(f"Model metadata saved to DB for job {job_id}")
            except Exception as e:
                logger.error(f"ModelRegistry: Failed to save to DB: {e}")
        
        return model_dir

    def load_model(self, job_id: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Loads model code, preprocessor, and metadata.
        Returns: (model, preprocessor, metadata)
        """
        
        # Check cache first
        if job_id in self._cache:
             return self._cache[job_id]

        model_dir = os.path.join(self.ROOT_DIR, job_id)
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model {job_id} not found")
            
        model_path = os.path.join(model_dir, "model.joblib")
        preprocessor_path = os.path.join(model_dir, "preprocessor.joblib")
        metadata_path = os.path.join(model_dir, "metadata.json")
        
        if not (os.path.exists(model_path) and os.path.exists(preprocessor_path) and os.path.exists(metadata_path)):
             raise FileNotFoundError(f"Corrupt model artifact for {job_id}")

        model = joblib.load(model_path)
        preprocessor = joblib.load(preprocessor_path)
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            
        # Update cache (simple implementation, unbounded for now)
        self._cache[job_id] = (model, preprocessor, metadata)
        
        return model, preprocessor, metadata

    def list_models(self) -> list[Dict[str, Any]]:
        """
        Lists all available models and their metadata.
        Prioritizes Database, falls back to filesystem.
        """
        models = []
        
        # Try DB first
        if self.db:
            try:
                sql = "SELECT * FROM model_registry ORDER BY created_at DESC"
                with self.db.engine.connect() as conn:
                    result = conn.execute(text(sql))
                    rows = result.fetchall()
                    
                    if rows:
                        for row in rows:
                            # Convert row to dict-like structure compatible with frontend
                            # row keys: job_id, task_name, target_column, algorithm, accuracy, created_at, model_path, inputs, status
                            
                            # Retrieve column names relative to the row access
                            # SQLAlchemy rows are accessible by key (column name)
                            
                            model_meta = {
                                "job_id": row.job_id,
                                "task_name": row.task_name,
                                "target": row.target_column,
                                "best_model_name": row.algorithm,
                                "test_metrics": {"accuracy": row.accuracy}, # Simplified for list view
                                "created_at": row.created_at.timestamp() if row.created_at else 0,
                                "input_features": json.loads(row.inputs) if row.inputs else [],
                                "status": row.status
                            }
                            models.append(model_meta)
                        return models
            except Exception as e:
                logger.error(f"ModelRegistry: DB List failed: {e}")
        
        # Fallback to filesystem
        if not os.path.exists(self.ROOT_DIR):
            return []
            
        for job_id in os.listdir(self.ROOT_DIR):
            meta_path = os.path.join(self.ROOT_DIR, job_id, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    try:
                        models.append(json.load(f))
                    except:
                        pass
        return models
