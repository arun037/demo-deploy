"""
Query Cache Manager

Intelligent caching system with TTL and refresh intervals.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class QueryCacheManager:
    """Manages query result caching with TTL"""
    
    def __init__(self, cache_file: str = "dashboard_cache.json"):
        self.cache_file = cache_file
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(os.path.dirname(self.base_dir), cache_file)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file"""
        if not os.path.exists(self.cache_path):
            return {}
        
        try:
            with open(self.cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return {}
    
    def _save_cache(self) -> bool:
        """Save cache to file"""
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving cache: {e}")
            return False
    
    def get(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Get cached data for insight"""
        if insight_id not in self.cache:
            return None
        
        entry = self.cache[insight_id]
        
        # Check if expired
        if self._is_expired(entry):
            del self.cache[insight_id]
            self._save_cache()
            return None
        
        return entry.get("data")
    
    def put(self, insight_id: str, data: Dict[str, Any], refresh_interval: str) -> bool:
        """Cache data for insight with TTL"""
        ttl = self._get_ttl(refresh_interval)
        
        self.cache[insight_id] = {
            "data": data,
            "cached_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat(),
            "refresh_interval": refresh_interval
        }
        
        return self._save_cache()
    
    def delete(self, insight_id: str) -> bool:
        """Delete cache entry for a specific insight"""
        if insight_id in self.cache:
            del self.cache[insight_id]
            return self._save_cache()
        return True
    
    def clear(self) -> bool:
        """Clear all cache"""
        self.cache = {}
        return self._save_cache()
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        try:
            expires_at = datetime.fromisoformat(entry.get("expires_at", ""))
            return datetime.now() > expires_at
        except:
            return True
    
    def _get_ttl(self, refresh_interval: str) -> int:
        """Get TTL in seconds based on refresh interval"""
        ttl_map = {
            "realtime": 60,      # 1 minute
            "hourly": 3600,      # 1 hour
            "daily": 86400       # 24 hours
        }
        return ttl_map.get(refresh_interval, 3600)
