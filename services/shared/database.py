"""Shared database utilities and models."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

logger = structlog.get_logger()

class Base(DeclarativeBase):
    pass

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session = None
        
    async def initialize(self, database_url: str = None):
        """Initialize database connection."""
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
            
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
            
        # Convert postgresql:// to postgresql+asyncpg://
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
        self.engine = create_async_engine(
            database_url,
            echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
            pool_size=20,
            max_overflow=0,
            pool_pre_ping=True,
        )
        
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info("Database connection initialized")
        
    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")
            
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        if not self.async_session:
            raise RuntimeError("Database not initialized")

        async with self.async_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_session_gen(self) -> AsyncGenerator[AsyncSession, None]:
        """Session dependency for FastAPI Depends — needs an async generator."""
        async with self.get_session() as session:
            yield session

# Global database manager instance
db_manager = DatabaseManager()