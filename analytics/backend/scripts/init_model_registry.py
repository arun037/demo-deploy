import sys
import os

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.database import DatabaseManager
from backend.core.logger import logger
from sqlalchemy import text

def init_model_registry():
    """
    Creates the model_registry table if it doesn't exist.
    """
    logger.info("Initializing Model Registry Database...")
    
    db = DatabaseManager()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS model_registry (
        job_id VARCHAR(50) PRIMARY KEY,
        task_name VARCHAR(255),
        target_column VARCHAR(100),
        algorithm VARCHAR(100),
        accuracy FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        model_path VARCHAR(500),
        inputs TEXT,
        status VARCHAR(50) DEFAULT 'completed'
    );
    """
    
    try:
        with db.engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("[OK] Table `model_registry` created (or already exists).")
            
            # Verify
            result = conn.execute(text("SHOW TABLES LIKE 'model_registry'"))
            if result.fetchone():
                logger.info("Verification successful: Table found.")
            else:
                logger.error("Verification failed: Table NOT found.")
                
    except Exception as e:
        logger.error(f"Failed to initialize registry: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_model_registry()
