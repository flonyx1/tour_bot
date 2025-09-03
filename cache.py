# cache.py
import time
from typing import Dict, Any, Optional
from cachetools import TTLCache

class CacheManager:
    def __init__(self):
        self.rate_limit_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute TTL
        self.user_activity_cache = TTLCache(maxsize=5000, ttl=300)  # 5 minutes TTL
        
    def check_rate_limit(self, key: str, limit: int, period: int) -> bool:
        current_time = time.time()
        user_data = self.rate_limit_cache.get(key, [])
        
        # Clean old timestamps
        user_data = [t for t in user_data if current_time - t < period]
        
        if len(user_data) >= limit:
            return False
            
        user_data.append(current_time)
        self.rate_limit_cache[key] = user_data
        return True
        
    def get_user_activity(self, user_id: int) -> Dict[str, Any]:
        return self.user_activity_cache.get(user_id, {})
        
    def set_user_activity(self, user_id: int, activity_data: Dict[str, Any]):
        self.user_activity_cache[user_id] = activity_data
        
    def clear_user_activity(self, user_id: int):
        if user_id in self.user_activity_cache:
            del self.user_activity_cache[user_id]