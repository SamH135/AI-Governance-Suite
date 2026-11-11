"""Database connection utilities."""

import asyncpg
from functools import lru_cache
from .config import get_settings

# Global database pool
_db_pool = None

async def initialize_db_pool():
    """Initialize the database connection pool."""
    global _db_pool
    settings = get_settings()
    
    _db_pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=5,
        max_size=20
    )
    return _db_pool

def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized. Call initialize_db_pool() first.")
    return _db_pool

async def close_db_pool():
    """Close the database connection pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None