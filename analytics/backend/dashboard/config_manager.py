"""
Config Manager

Manages dashboard configuration persistence using JSON files.
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigManager:
    """Manages dashboard configuration persistence"""
    
    def __init__(self, config_file: str = "dashboard_config.json"):
        self.config_file = config_file
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(os.path.dirname(self.base_dir), config_file)
    
    def exists(self) -> bool:
        """Check if config file exists"""
        return os.path.exists(self.config_path)
    
    def load(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file"""
        if not self.exists():
            return None
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    def _make_json_serializable(self, obj):
        """Convert DataFrames and other non-serializable objects to JSON-compatible format"""
        # Handle pandas DataFrame
        if hasattr(obj, 'to_dict') and hasattr(obj, 'iloc'):
            return obj.to_dict('records')
        # Handle dict
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        # Handle list
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        # Handle objects with __dict__
        elif hasattr(obj, '__dict__'):
            return self._make_json_serializable(obj.__dict__)
        else:
            return obj
    
    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            # Convert any DataFrames to JSON-serializable format
            serializable_config = self._make_json_serializable(config)
            with open(self.config_path, 'w') as f:
                json.dump(serializable_config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def delete(self) -> bool:
        """Delete configuration file"""
        try:
            if self.exists():
                os.remove(self.config_path)
            return True
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False
    
    def get_schema_hash(self, schema_file: str) -> str:
        """Generate hash of schema file for change detection"""
        try:
            schema_path = os.path.join(os.path.dirname(self.base_dir), schema_file)
            with open(schema_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            print(f"Error hashing schema: {e}")
            return ""
