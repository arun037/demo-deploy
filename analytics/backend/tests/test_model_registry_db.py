import sys
import os
import shutil
import unittest
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.ai_insights.model_registry import ModelRegistry
from backend.core.database import DatabaseManager
from sqlalchemy import text

class TestModelRegistryDB(unittest.TestCase):
    def setUp(self):
        self.registry = ModelRegistry()
        self.job_id = "test_job_db_persistence"
        
        # Cleanup before test
        if os.path.exists(os.path.join(self.registry.ROOT_DIR, self.job_id)):
            shutil.rmtree(os.path.join(self.registry.ROOT_DIR, self.job_id))
            
        # Cleanup DB
        if self.registry.db:
            with self.registry.db.engine.connect() as conn:
                conn.execute(text("DELETE FROM model_registry WHERE job_id = :job_id"), {"job_id": self.job_id})
                conn.commit()

    def tearDown(self):
        # Cleanup after test
        if os.path.exists(os.path.join(self.registry.ROOT_DIR, self.job_id)):
            shutil.rmtree(os.path.join(self.registry.ROOT_DIR, self.job_id))
            
        # Cleanup DB
        if self.registry.db:
            with self.registry.db.engine.connect() as conn:
                conn.execute(text("DELETE FROM model_registry WHERE job_id = :job_id"), {"job_id": self.job_id})
                conn.commit()

    def test_save_and_list_model(self):
        # Mock objects
        model = "dummy_model"
        preprocessor = "dummy_preprocessor"
        metadata = {
            "task_name": "Test DB Persistence",
            "target": "test_target",
            "best_model_name": "RandomForest",
            "test_metrics": {"accuracy": 0.95},
            "input_features": ["col1", "col2"]
        }
        
        # Save
        self.registry.save_model(self.job_id, model, preprocessor, metadata)
        
        # Verify File System
        self.assertTrue(os.path.exists(os.path.join(self.registry.ROOT_DIR, self.job_id, "metadata.json")))
        
        # Verify DB List
        models = self.registry.list_models()
        found = False
        for m in models:
            if m['job_id'] == self.job_id:
                found = True
                self.assertEqual(m['task_name'], "Test DB Persistence")
                self.assertEqual(m['test_metrics']['accuracy'], 0.95)
                self.assertEqual(m['input_features'], ["col1", "col2"])
                break
        
        self.assertTrue(found, "Model not found in DB list")
        print("[OK] Model successfully saved to DB and listed.")

if __name__ == '__main__':
    unittest.main()
