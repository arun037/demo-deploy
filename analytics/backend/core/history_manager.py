
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from backend.core.logger import logger

class HistoryManager:
    """
    Manages user query history with frequency tracking.
    Stores data in a JSON file.
    """
    
    def __init__(self, storage_file: str = "backend/data/query_history.json"):
        self.storage_file = storage_file
        self._ensure_storage()
        
    def _ensure_storage(self):
        """Ensure the storage file and directory exist"""
        directory = os.path.dirname(self.storage_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        if not os.path.exists(self.storage_file):
            self._save_history([])
            
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from JSON file"""
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []
            
    def _save_history(self, history: List[Dict[str, Any]]):
        """Save history to JSON file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            
    def add_query(self, query_text: str, query_type: str = 'normal'):
        """
        Add a query to history.
        If it exists (case-insensitive), increment count and update timestamp.
        If new, add to list.
        """
        if not query_text or not query_text.strip():
            return
            
        clean_query = query_text.strip()
        history = self._load_history()
        
        # Check if exists (normalization: lowercase for matching)
        found = False
        for item in history:
            if item['query'].lower() == clean_query.lower():
                item['count'] = item.get('count', 1) + 1
                item['last_run'] = datetime.now().isoformat()
                # Update formatting to the most recent casing used
                item['query'] = clean_query 
                # Update type if provided (prioritize 'refined' if it ever becomes refined?) -> No, just overwrite with latest usage type
                if query_type:
                    item['type'] = query_type
                found = True
                break
        
        if not found:
            history.append({
                'query': clean_query,
                'count': 1,
                'last_run': datetime.now().isoformat(),
                'first_run': datetime.now().isoformat(),
                'type': query_type or 'normal'
            })
            
        self._save_history(history)
        
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get history sorted by count (descending) then last_run (descending).
        """
        history = self._load_history()
        
        # Sort: Primary = count (desc), Secondary = last_run (desc)
        history.sort(key=lambda x: (x.get('count', 1), x.get('last_run', '')), reverse=True)
        
        return history[:limit]
