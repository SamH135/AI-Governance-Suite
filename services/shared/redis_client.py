"""Shared Redis client utilities."""

import os
import json
from typing import Optional, Any
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

class RedisClient:
    def __init__(self):
        self.redis = None
        
    async def initialize(self, redis_url: str = None):
        """Initialize Redis connection."""
        if not redis_url:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            
        try:
            self.redis = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
            )
            
            # Test connection
            await self.redis.ping()
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise
            
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
            
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return await self.redis.get(key)
        
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set a value in Redis."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return await self.redis.set(key, value, ex=ttl)
        
    async def delete(self, key: str) -> int:
        """Delete a key from Redis."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return await self.redis.delete(key)
        
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return bool(await self.redis.exists(key))
        
    async def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a JSON value in Redis."""
        json_str = json.dumps(value, default=str)
        return await self.set(key, json_str, ttl)
        
    async def get_json(self, key: str) -> Optional[Any]:
        """Get a JSON value from Redis."""
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from Redis", key=key)
            return None
            
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a value in Redis."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return await self.redis.incrby(key, amount)
        
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        return await self.redis.expire(key, ttl)
        
    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a Redis channel."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        if isinstance(message, (dict, list)):
            message = json.dumps(message, default=str)
        return await self.redis.publish(channel, message)
        
    async def subscribe(self, *channels: str):
        """Subscribe to Redis channels."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

# Global Redis client instance
redis_client = RedisClient()