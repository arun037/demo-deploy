from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from backend.config import Config

from backend.core.logger import logger


class DatabaseManager:
    """Database connection and query execution manager"""
    
    def __init__(self):
        self.engine = None
        self.connect()
    
    def connect(self):
        """Establish database connection"""
        try:
            connection_string = Config.get_db_url()
            self.engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info(f"Connected to database: {Config.DB_NAME}")
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def verify_multi_database_access(self):
        """
        Verify user has access to all configured databases.
        MySQL allows cross-database queries from a single connection.
        """
        accessible_dbs = []
        inaccessible_dbs = []
        
        for db_name in Config.DATABASES.keys():
            try:
                with self.engine.connect() as conn:
                    # Try to use the database
                    conn.execute(text(f"USE `{db_name}`"))
                    # Verify we can query it
                    conn.execute(text("SELECT 1"))
                accessible_dbs.append(db_name)
                logger.info(f"S Multi-database access verified: {db_name}")
            except Exception as e:
                inaccessible_dbs.append(db_name)
                logger.warning(f"F Cannot access database '{db_name}': {e}")
        
        if accessible_dbs:
            logger.info(f"Multi-database support enabled for: {', '.join(accessible_dbs)}")
        
        if inaccessible_dbs:
            logger.warning(f"Limited access - cannot query: {', '.join(inaccessible_dbs)}")
        
        return accessible_dbs, inaccessible_dbs
    
    def get_table_names(self):
        """Get list of all table names"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SHOW TABLES"))
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get table names: {e}")
            return []
    
    def validate_sql(self, sql_query):
        """
        Validate SQL using EXPLAIN without executing
        Returns: (is_valid, error_message)
        """
        import re
        
        # Security check: block dangerous keywords using word boundaries
        # This prevents false positives like "last_update" being flagged as "UPDATE"
        forbidden_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'ALTER', 'CREATE']
        sql_upper = sql_query.upper()
        
        for keyword in forbidden_keywords:
            # Use word boundary regex to match only complete words
            # \b ensures we match "UPDATE" but not "last_UPDATE" or "UPDATE_date"
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return False, f"Security Error: {keyword} statements are not allowed"
        
        # Validate with EXPLAIN
        try:
            with self.engine.connect() as conn:
                explain_query = f"EXPLAIN {sql_query}"
                conn.execute(text(explain_query))
            return True, None
            
        except SQLAlchemyError as e:
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            return False, f"Syntax/Runtime Error: {error_msg}"
        except Exception as e:
            return False, f"Validation Error: {str(e)}"
    
    def execute_query_safe(self, sql_query):
        """
        Safely execute a SELECT query and return results as DataFrame
        """
        # Double-check it's a SELECT query
        # Double-check it's a SELECT query or CTE
        stripped_sql = sql_query.strip().upper()
        if not (stripped_sql.startswith('SELECT') or stripped_sql.startswith('WITH')):
            raise ValueError("Only SELECT queries are allowed (including CTEs). Prohibited: DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, TRUNCATE.")
        
        try:
            # Escape percentage signs for the driver/SQLAlchemy
            # This prevents errors like "TypeError: %d format: a real number is required"
            # when using DATE_FORMAT(..., '%d')
            safe_sql = sql_query.replace('%', '%%')
            
            # Log the actual query being run
            logger.info(f"DB Executing:\n{sql_query}")
            
            with self.engine.connect() as conn:
                df = pd.read_sql(safe_sql, conn)
            
            # Convert all missing values (NaN, NaT, etc.) to Python None
            # This prevents "ValueError: Out of range float values are not JSON compliant: nan"
            # because standard JSON serializers cannot handle NaN
            df = df.astype(object).where(pd.notnull(df), None)
            
            logger.info(f"Query executed successfully: {len(df)} rows returned")
            return df
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
