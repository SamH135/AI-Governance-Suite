"""Configuration settings for the gateway service."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ai_compliance"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT
    JWT_SECRET: str  # required env var - no default (dev default was a known security issue)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Service URLs
    ANALYTICS_SERVICE_URL: str = "http://localhost:8005"
    COMPLIANCE_SERVICE_URL: str = "http://localhost:8001"
    PROMPTS_SERVICE_URL: str = "http://localhost:8002"
    DOCUMENTS_SERVICE_URL: str = "http://localhost:8003"
    TESTS_SERVICE_URL: str = "http://localhost:8004"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()