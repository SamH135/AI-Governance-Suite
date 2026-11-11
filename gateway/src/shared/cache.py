"""Redis cache connection utilities."""

import redis.asyncio as redis
from .config import get_settings

# Global Redis client
_redis_client = None

async def initialize_redis_client():
    """Initialize the Redis client."""
    global _redis_client
    settings = get_settings()
    
    _redis_client = redis.from_url(settings.REDIS_URL)
    await _redis_client.ping()
    return _redis_client

def get_redis_client() -> redis.Redis:
    """Get the Redis client."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call initialize_redis_client() first.")
    return _redis_client

async def close_redis_client():
    """Close the Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None