import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from pathlib import Path

# Load environment variables from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuration management for SQL Swarm backend"""
    
    # Database Configuration (Primary)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "franchises")  # Primary database for connection
    
    # Multi-Database Configuration
    # All databases on the same MySQL server - can query across databases using database.table syntax
    DATABASES = {
        'franchises': {
            'host': DB_HOST,
            'port': DB_PORT,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'database': 'franchises'
        },
        'franchise_new': {
            'host': DB_HOST,
            'port': DB_PORT,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'database': 'franchise_new'
        }
    }
    
    # OpenRouter API Configuration
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    
    # Novita AI Configuration
    USE_NOVITA = os.getenv("USE_NOVITA", "false").lower() == "true"
    NOVITA_API_KEY = os.getenv("NOVITA_API_KEY")
    NOVITA_BASE_URL = os.getenv("NOVITA_BASE_URL", "https://api.novita.ai/v3/openai")
    
    # Multi-Model Strategy for Speed + Accuracy
    USE_EMBEDDING_RETRIEVER = os.getenv("USE_EMBEDDING_RETRIEVER", "true").lower() == "true"
    
    # CRITICAL AGENTS - OpenRouter Configuration
    # Using Gemini 2.5 Flash for all agents as requested
    PLANNER_MODEL = os.getenv("PLANNER_MODEL", "anthropic/claude-sonnet-4.6")
    SYNTHESIZER_MODEL = os.getenv("SYNTHESIZER_MODEL", "anthropic/claude-sonnet-4.6")
    FIXER_MODEL = os.getenv("FIXER_MODEL", "google/gemini-2.5-flash")
    CLARIFICATION_MODEL = os.getenv("CLARIFICATION_MODEL", "anthropic/claude-sonnet-4.6")
    INSIGHT_MODEL = os.getenv("INSIGHT_MODEL", "google/gemini-2.5-flash")
    
    # SPEED-OPTIMIZED AGENTS
    RESPONSE_MODEL = os.getenv("RESPONSE_MODEL", "google/gemini-2.5-flash")
    VALIDATOR_MODEL = os.getenv("VALIDATOR_MODEL", "google/gemini-2.5-flash")
    
    # Specific Agent Overrides
    CHART_PLANNER_MODEL = os.getenv("CHART_PLANNER_MODEL", PLANNER_MODEL)
    # Dashboard uses Claude Sonnet 4.5
    DASHBOARD_MODEL = os.getenv("DASHBOARD_MODEL", "anthropic/claude-sonnet-4.5")
    ROUTER_MODEL = os.getenv("ROUTER_MODEL", "google/gemini-2.5-flash")
    QUERY_ENHANCER_MODEL = os.getenv("QUERY_ENHANCER_MODEL", "google/gemini-2.5-flash")
    
    # Embedding Model
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Chroma Cloud Configuration
    CHROMA_API_KEY = os.getenv("CHROMA_API_KEY_P")
    CHROMA_TENANT = os.getenv("CHROMA_TENANT_P")
    CHROMA_DB_NAME = os.getenv("CHROMA_DB_NAME_P")
    
    # Legacy fallback model
    MODEL_NAME = "google/gemini-2.5-flash"
    
    # Server Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_RELOAD = os.getenv("API_RELOAD").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS").split(",")
    
    # Timeouts
    PLANNER_TIMEOUT = int(os.getenv("PLANNER_TIMEOUT", "120"))
    SYNTHESIZER_TIMEOUT = int(os.getenv("SYNTHESIZER_TIMEOUT", "120"))
    FIXER_TIMEOUT = int(os.getenv("FIXER_TIMEOUT", "120"))
    RESPONSE_TIMEOUT = int(os.getenv("RESPONSE_TIMEOUT", "120"))
    
    # ChromaDB Configuration
    CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
    CHROMA_COLLECTION_NAME = "schema_new_des" # Upgraded to Column-Level Embeddings
    DASHBOARD_COLLECTION_NAME = "dashboard_schema_v5"
    
    # Schema file path
    SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "db_schema.json")
    BUSINESS_CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "business_context.json")
    
    # Clarification System Settings (EXACT MATCH with research-implement)
    ENABLE_CLARIFICATION = os.getenv("ENABLE_CLARIFICATION", "true").lower() == "true"
    MAX_CLARIFICATION_QUESTIONS = int(os.getenv("MAX_CLARIFICATION_QUESTIONS", "3"))
    CLARIFICATION_TIMEOUT = int(os.getenv("CLARIFICATION_TIMEOUT", "90"))
    

    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        
        if not cls.DB_HOST:
            missing.append("DB_HOST")
        if not cls.DB_USER:
            missing.append("DB_USER")
        if not cls.DB_NAME:
            missing.append("DB_NAME")
        
        # Require either Novita or OpenRouter API key
        if not cls.NOVITA_API_KEY and not cls.OPENROUTER_API_KEY:
            missing.append("NOVITA_API_KEY or OPENROUTER_API_KEY")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True
    
    @classmethod
    def get_db_url(cls):
        """Get database connection URL with properly encoded password"""
        # URL-encode the password to handle special characters like @, #, etc.
        encoded_password = quote_plus(cls.DB_PASSWORD) if cls.DB_PASSWORD else ""
        return f"mysql+pymysql://{cls.DB_USER}:{encoded_password}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
