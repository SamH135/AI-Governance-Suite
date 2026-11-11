"""Advanced caching service with multiple strategies and cache warming."""

import asyncio
import json
import hashlib
import pickle
import time
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
import structlog

from .redis_client import redis_client
from .exceptions import ValidationError

logger = structlog.get_logger()

class CacheStrategy(Enum):
    """Cache strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    READ_THROUGH = "read_through"

class CacheLevel(Enum):
    """Cache levels."""
    L1_MEMORY = "l1_memory"  # In-memory cache
    L2_REDIS = "l2_redis"    # Redis cache
    L3_DATABASE = "l3_database"  # Database cache

class CachingService:
    """Advanced multi-level caching service."""
    
    def __init__(self):
        self.initialized = False
        
        # L1 Cache (in-memory)
        self.l1_cache = {}
        self.l1_access_times = {}
        self.l1_access_counts = {}
        self.l1_max_size = 1000
        
        # Cache configurations
        self.cache_configs = {}
        
        # Cache statistics
        self.stats = {
            "hits": {"l1": 0, "l2": 0, "l3": 0},
            "misses": {"l1": 0, "l2": 0, "l3": 0},
            "sets": {"l1": 0, "l2": 0, "l3": 0},
            "evictions": {"l1": 0, "l2": 0, "l3": 0}
        }
        
        # Cache warming tasks
        self.warming_tasks = {}
        
    async def initialize(self):
        """Initialize the caching service."""
        if self.initialized:
            return
            
        try:
            # Test Redis connection
            await redis_client.ping()
            
            # Setup default cache configurations
            await self._setup_default_configs()
            
            # Start background tasks
            asyncio.create_task(self._cache_maintenance_loop())
            asyncio.create_task(self._stats_collection_loop())
            
            self.initialized = True
            logger.info("Caching Service initialized successfully")
            
        except Exception as e:
            logger.error("Caching Service initialization failed", error=str(e))
            raise
    
    async def get(
        self,
        key: str,
        namespace: str = "default",
        levels: List[CacheLevel] = None
    ) -> Optional[Any]:
        """Get value from cache with multi-level lookup."""
        
        if not self.initialized:
            await self.initialize()
        
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        cache_key = self._build_cache_key(key, namespace)
        
        # Try each cache level
        for level in levels:
            try:
                if level == CacheLevel.L1_MEMORY:
                    value = await self._get_l1(cache_key)
                    if value is not None:
                        self.stats["hits"]["l1"] += 1
                        await self._update_access_stats(cache_key, level)
                        return value
                    else:
                        self.stats["misses"]["l1"] += 1
                
                elif level == CacheLevel.L2_REDIS:
                    value = await self._get_l2(cache_key)
                    if value is not None:
                        self.stats["hits"]["l2"] += 1
                        # Promote to L1 cache
                        await self._set_l1(cache_key, value)
                        await self._update_access_stats(cache_key, level)
                        return value
                    else:
                        self.stats["misses"]["l2"] += 1
                
            except Exception as e:
                logger.warning("Cache level failed", level=level.value, key=cache_key, error=str(e))
                continue
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default",
        levels: List[CacheLevel] = None,
        strategy: CacheStrategy = CacheStrategy.TTL
    ) -> bool:
        """Set value in cache across multiple levels."""
        
        if not self.initialized:
            await self.initialize()
        
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        cache_key = self._build_cache_key(key, namespace)
        success = True
        
        # Set in each cache level
        for level in levels:
            try:
                if level == CacheLevel.L1_MEMORY:
                    await self._set_l1(cache_key, value, ttl)
                    self.stats["sets"]["l1"] += 1
                
                elif level == CacheLevel.L2_REDIS:
                    await self._set_l2(cache_key, value, ttl)
                    self.stats["sets"]["l2"] += 1
                
            except Exception as e:
                logger.error("Cache set failed", level=level.value, key=cache_key, error=str(e))
                success = False
        
        return success
    
    async def delete(
        self,
        key: str,
        namespace: str = "default",
        levels: List[CacheLevel] = None
    ) -> bool:
        """Delete value from cache across multiple levels."""
        
        if not self.initialized:
            await self.initialize()
        
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        cache_key = self._build_cache_key(key, namespace)
        success = True
        
        # Delete from each cache level
        for level in levels:
            try:
                if level == CacheLevel.L1_MEMORY:
                    await self._delete_l1(cache_key)
                
                elif level == CacheLevel.L2_REDIS:
                    await self._delete_l2(cache_key)
                
            except Exception as e:
                logger.error("Cache delete failed", level=level.value, key=cache_key, error=str(e))
                success = False
        
        return success
    
    async def get_or_set(
        self,
        key: str,
        factory_func: Callable,
        ttl: Optional[int] = None,
        namespace: str = "default",
        levels: List[CacheLevel] = None
    ) -> Any:
        """Get value from cache or set it using factory function."""
        
        # Try to get from cache first
        value = await self.get(key, namespace, levels)
        
        if value is not None:
            return value
        
        # Generate value using factory function
        try:
            if asyncio.iscoroutinefunction(factory_func):
                value = await factory_func()
            else:
                value = factory_func()
            
            # Set in cache
            await self.set(key, value, ttl, namespace, levels)
            
            return value
            
        except Exception as e:
            logger.error("Factory function failed", key=key, error=str(e))
            raise
    
    async def invalidate_pattern(
        self,
        pattern: str,
        namespace: str = "default",
        levels: List[CacheLevel] = None
    ) -> int:
        """Invalidate all cache keys matching a pattern."""
        
        if not self.initialized:
            await self.initialize()
        
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        total_deleted = 0
        
        for level in levels:
            try:
                if level == CacheLevel.L1_MEMORY:
                    deleted = await self._invalidate_l1_pattern(pattern, namespace)
                    total_deleted += deleted
                
                elif level == CacheLevel.L2_REDIS:
                    deleted = await self._invalidate_l2_pattern(pattern, namespace)
                    total_deleted += deleted
                
            except Exception as e:
                logger.error("Pattern invalidation failed", 
                           level=level.value, pattern=pattern, error=str(e))
        
        logger.info("Cache pattern invalidated", pattern=pattern, deleted=total_deleted)
        return total_deleted
    
    async def warm_cache(
        self,
        key: str,
        factory_func: Callable,
        ttl: Optional[int] = None,
        namespace: str = "default",
        schedule_refresh: bool = True
    ) -> bool:
        """Warm cache with data."""
        
        try:
            # Generate value
            if asyncio.iscoroutinefunction(factory_func):
                value = await factory_func()
            else:
                value = factory_func()
            
            # Set in cache
            success = await self.set(key, value, ttl, namespace)
            
            # Schedule periodic refresh if requested
            if schedule_refresh and ttl:
                refresh_interval = max(ttl // 2, 60)  # Refresh at half TTL, minimum 1 minute
                
                async def refresh_task():
                    while True:
                        try:
                            await asyncio.sleep(refresh_interval)
                            
                            # Check if key still exists
                            current_value = await self.get(key, namespace)
                            if current_value is not None:
                                # Refresh the cache
                                if asyncio.iscoroutinefunction(factory_func):
                                    new_value = await factory_func()
                                else:
                                    new_value = factory_func()
                                
                                await self.set(key, new_value, ttl, namespace)
                                logger.debug("Cache warmed", key=key, namespace=namespace)
                            else:
                                # Key expired or deleted, stop refreshing
                                break
                                
                        except Exception as e:
                            logger.error("Cache warming failed", key=key, error=str(e))
                            break
                
                # Store task reference
                task_key = f"{namespace}:{key}"
                if task_key in self.warming_tasks:
                    self.warming_tasks[task_key].cancel()
                
                self.warming_tasks[task_key] = asyncio.create_task(refresh_task())
            
            return success
            
        except Exception as e:
            logger.error("Cache warming failed", key=key, error=str(e))
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        
        # Calculate hit rates
        hit_rates = {}
        for level in ["l1", "l2", "l3"]:
            hits = self.stats["hits"][level]
            misses = self.stats["misses"][level]
            total = hits + misses
            hit_rates[level] = (hits / total * 100) if total > 0 else 0
        
        # L1 cache info
        l1_info = {
            "size": len(self.l1_cache),
            "max_size": self.l1_max_size,
            "usage_percent": (len(self.l1_cache) / self.l1_max_size * 100)
        }
        
        # Redis info
        try:
            redis_info = await redis_client.info("memory")
            l2_info = {
                "used_memory": redis_info.get("used_memory", 0),
                "used_memory_human": redis_info.get("used_memory_human", "0B"),
                "connected_clients": redis_info.get("connected_clients", 0)
            }
        except:
            l2_info = {"error": "Unable to get Redis info"}
        
        return {
            "hit_rates": hit_rates,
            "stats": self.stats,
            "l1_cache": l1_info,
            "l2_cache": l2_info,
            "warming_tasks": len(self.warming_tasks),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def clear_cache(
        self,
        namespace: Optional[str] = None,
        levels: List[CacheLevel] = None
    ) -> Dict[str, int]:
        """Clear cache for namespace or all caches."""
        
        if not self.initialized:
            await self.initialize()
        
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        cleared = {"l1": 0, "l2": 0}
        
        for level in levels:
            try:
                if level == CacheLevel.L1_MEMORY:
                    if namespace:
                        cleared["l1"] = await self._clear_l1_namespace(namespace)
                    else:
                        cleared["l1"] = len(self.l1_cache)
                        self.l1_cache.clear()
                        self.l1_access_times.clear()
                        self.l1_access_counts.clear()
                
                elif level == CacheLevel.L2_REDIS:
                    if namespace:
                        cleared["l2"] = await self._clear_l2_namespace(namespace)
                    else:
                        # Clear all Redis keys with our prefix
                        pattern = "cache:*"
                        keys = await redis_client.keys(pattern)
                        if keys:
                            cleared["l2"] = await redis_client.delete(*keys)
                
            except Exception as e:
                logger.error("Cache clear failed", level=level.value, error=str(e))
        
        logger.info("Cache cleared", namespace=namespace, cleared=cleared)
        return cleared
    
    def cache_decorator(
        self,
        ttl: Optional[int] = None,
        namespace: str = "default",
        key_func: Optional[Callable] = None
    ):
        """Decorator for caching function results."""
        
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
                
                # Try to get from cache
                cached_result = await self.get(cache_key, namespace)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Cache result
                await self.set(cache_key, result, ttl, namespace)
                
                return result
            
            return wrapper
        return decorator
    
    # Private methods for L1 cache operations
    async def _get_l1(self, key: str) -> Optional[Any]:
        """Get from L1 (memory) cache."""
        
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            
            # Check TTL
            if entry.get("expires_at") and datetime.utcnow() > entry["expires_at"]:
                await self._delete_l1(key)
                return None
            
            return entry["value"]
        
        return None
    
    async def _set_l1(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in L1 (memory) cache."""
        
        # Check if we need to evict
        if len(self.l1_cache) >= self.l1_max_size:
            await self._evict_l1()
        
        expires_at = None
        if ttl:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        self.l1_cache[key] = {
            "value": value,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at
        }
        
        self.l1_access_times[key] = time.time()
        self.l1_access_counts[key] = 0
    
    async def _delete_l1(self, key: str):
        """Delete from L1 cache."""
        
        self.l1_cache.pop(key, None)
        self.l1_access_times.pop(key, None)
        self.l1_access_counts.pop(key, None)
    
    async def _evict_l1(self):
        """Evict entries from L1 cache using LRU strategy."""
        
        if not self.l1_cache:
            return
        
        # Find least recently used key
        lru_key = min(self.l1_access_times.keys(), key=lambda k: self.l1_access_times[k])
        
        await self._delete_l1(lru_key)
        self.stats["evictions"]["l1"] += 1
    
    # Private methods for L2 cache operations
    async def _get_l2(self, key: str) -> Optional[Any]:
        """Get from L2 (Redis) cache."""
        
        try:
            data = await redis_client.get(key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.warning("L2 cache get failed", key=key, error=str(e))
        
        return None
    
    async def _set_l2(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in L2 (Redis) cache."""
        
        try:
            data = pickle.dumps(value)
            if ttl:
                await redis_client.setex(key, ttl, data)
            else:
                await redis_client.set(key, data)
        except Exception as e:
            logger.error("L2 cache set failed", key=key, error=str(e))
            raise
    
    async def _delete_l2(self, key: str):
        """Delete from L2 cache."""
        
        try:
            await redis_client.delete(key)
        except Exception as e:
            logger.warning("L2 cache delete failed", key=key, error=str(e))
    
    # Helper methods
    def _build_cache_key(self, key: str, namespace: str) -> str:
        """Build cache key with namespace."""
        return f"cache:{namespace}:{key}"
    
    async def _update_access_stats(self, key: str, level: CacheLevel):
        """Update access statistics."""
        
        if level == CacheLevel.L1_MEMORY:
            self.l1_access_times[key] = time.time()
            self.l1_access_counts[key] = self.l1_access_counts.get(key, 0) + 1
    
    async def _invalidate_l1_pattern(self, pattern: str, namespace: str) -> int:
        """Invalidate L1 cache keys matching pattern."""
        
        prefix = f"cache:{namespace}:"
        full_pattern = f"{prefix}{pattern}"
        
        keys_to_delete = []
        for key in self.l1_cache.keys():
            if self._match_pattern(key, full_pattern):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            await self._delete_l1(key)
        
        return len(keys_to_delete)
    
    async def _invalidate_l2_pattern(self, pattern: str, namespace: str) -> int:
        """Invalidate L2 cache keys matching pattern."""
        
        prefix = f"cache:{namespace}:"
        full_pattern = f"{prefix}{pattern}"
        
        try:
            keys = await redis_client.keys(full_pattern)
            if keys:
                return await redis_client.delete(*keys)
        except Exception as e:
            logger.error("L2 pattern invalidation failed", pattern=full_pattern, error=str(e))
        
        return 0
    
    async def _clear_l1_namespace(self, namespace: str) -> int:
        """Clear L1 cache for specific namespace."""
        
        prefix = f"cache:{namespace}:"
        keys_to_delete = [key for key in self.l1_cache.keys() if key.startswith(prefix)]
        
        for key in keys_to_delete:
            await self._delete_l1(key)
        
        return len(keys_to_delete)
    
    async def _clear_l2_namespace(self, namespace: str) -> int:
        """Clear L2 cache for specific namespace."""
        
        pattern = f"cache:{namespace}:*"
        
        try:
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
        except Exception as e:
            logger.error("L2 namespace clear failed", namespace=namespace, error=str(e))
        
        return 0
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching with * wildcard."""
        
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    async def _setup_default_configs(self):
        """Setup default cache configurations."""
        
        self.cache_configs = {
            "user_sessions": {"ttl": 3600, "levels": [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]},
            "api_responses": {"ttl": 300, "levels": [CacheLevel.L2_REDIS]},
            "database_queries": {"ttl": 600, "levels": [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]},
            "static_content": {"ttl": 86400, "levels": [CacheLevel.L2_REDIS]},
            "analytics_data": {"ttl": 1800, "levels": [CacheLevel.L2_REDIS]}
        }
    
    async def _cache_maintenance_loop(self):
        """Background task for cache maintenance."""
        
        while True:
            try:
                # Clean expired L1 entries
                current_time = datetime.utcnow()
                expired_keys = []
                
                for key, entry in self.l1_cache.items():
                    if entry.get("expires_at") and current_time > entry["expires_at"]:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    await self._delete_l1(key)
                
                if expired_keys:
                    logger.debug("Cleaned expired L1 entries", count=len(expired_keys))
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error("Cache maintenance failed", error=str(e))
                await asyncio.sleep(60)
    
    async def _stats_collection_loop(self):
        """Background task for collecting cache statistics."""
        
        while True:
            try:
                # Reset stats periodically to prevent overflow
                await asyncio.sleep(3600)  # Every hour
                
                # Log current stats
                stats = await self.get_stats()
                logger.info("Cache statistics", stats=stats)
                
            except Exception as e:
                logger.error("Stats collection failed", error=str(e))
                await asyncio.sleep(3600)

# Global instance
caching_service = CachingService()