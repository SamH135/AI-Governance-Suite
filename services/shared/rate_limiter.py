"""Rate Limiting Service for API protection."""

import asyncio
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import structlog

from .redis_client import redis_client
from .exceptions import RateLimitExceededError

logger = structlog.get_logger()

class RateLimitType(Enum):
    """Types of rate limits."""
    PER_USER = "per_user"
    PER_IP = "per_ip"
    PER_API_KEY = "per_api_key"
    GLOBAL = "global"

class RateLimitWindow(Enum):
    """Rate limit time windows."""
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400

class RateLimiter:
    """Advanced rate limiting service with multiple strategies."""
    
    def __init__(self):
        self.initialized = False
        
        # Default rate limits
        self.default_limits = {
            # Per user limits
            "user_per_second": 10,
            "user_per_minute": 100,
            "user_per_hour": 1000,
            "user_per_day": 10000,
            
            # Per IP limits
            "ip_per_second": 20,
            "ip_per_minute": 200,
            "ip_per_hour": 2000,
            "ip_per_day": 20000,
            
            # Per API key limits
            "api_key_per_second": 50,
            "api_key_per_minute": 500,
            "api_key_per_hour": 5000,
            "api_key_per_day": 50000,
            
            # Global limits
            "global_per_second": 1000,
            "global_per_minute": 10000,
            "global_per_hour": 100000,
            "global_per_day": 1000000
        }
        
        # Custom limits for specific endpoints
        self.endpoint_limits = {
            "/api/tests/execute": {
                "user_per_minute": 10,
                "user_per_hour": 100
            },
            "/api/documents/generate": {
                "user_per_minute": 5,
                "user_per_hour": 50
            },
            "/api/prompts/optimize": {
                "user_per_minute": 3,
                "user_per_hour": 30
            },
            "/api/compliance/evaluate": {
                "user_per_minute": 20,
                "user_per_hour": 200
            }
        }
    
    async def initialize(self):
        """Initialize the rate limiter."""
        if self.initialized:
            return
            
        try:
            # Test Redis connection
            await redis_client.ping()
            
            self.initialized = True
            logger.info("Rate Limiter initialized successfully")
            
        except Exception as e:
            logger.error("Rate Limiter initialization failed", error=str(e))
            raise
    
    async def check_rate_limit(
        self,
        identifier: str,
        limit_type: RateLimitType,
        endpoint: Optional[str] = None,
        custom_limits: Optional[Dict[str, int]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limits.
        
        Returns:
            Tuple of (allowed: bool, limit_info: dict)
        """
        
        if not self.initialized:
            await self.initialize()
        
        try:
            current_time = int(time.time())
            
            # Get applicable limits
            limits = self._get_applicable_limits(limit_type, endpoint, custom_limits)
            
            # Check each time window
            for window_name, limit in limits.items():
                window_seconds = self._get_window_seconds(window_name)
                
                # Create Redis key
                key = f"rate_limit:{limit_type.value}:{identifier}:{window_name}:{current_time // window_seconds}"
                
                # Get current count
                current_count = await redis_client.get(key)
                current_count = int(current_count) if current_count else 0
                
                # Check if limit exceeded
                if current_count >= limit:
                    # Calculate reset time
                    reset_time = ((current_time // window_seconds) + 1) * window_seconds
                    
                    limit_info = {
                        "allowed": False,
                        "limit": limit,
                        "current": current_count,
                        "window": window_name,
                        "reset_time": reset_time,
                        "retry_after": reset_time - current_time
                    }
                    
                    logger.warning(
                        "Rate limit exceeded",
                        identifier=identifier,
                        limit_type=limit_type.value,
                        window=window_name,
                        current=current_count,
                        limit=limit
                    )
                    
                    return False, limit_info
            
            # All limits passed, increment counters
            await self._increment_counters(identifier, limit_type, limits, current_time)
            
            # Return success with current usage info
            limit_info = {
                "allowed": True,
                "limits": limits,
                "current_usage": await self._get_current_usage(identifier, limit_type, current_time)
            }
            
            return True, limit_info
            
        except Exception as e:
            logger.error("Rate limit check failed", identifier=identifier, error=str(e))
            # Fail open - allow request if rate limiting fails
            return True, {"allowed": True, "error": "rate_limit_check_failed"}
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        limit_type: RateLimitType,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current rate limit status for an identifier."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            current_time = int(time.time())
            limits = self._get_applicable_limits(limit_type, endpoint)
            
            status = {
                "identifier": identifier,
                "limit_type": limit_type.value,
                "endpoint": endpoint,
                "current_time": current_time,
                "windows": {}
            }
            
            for window_name, limit in limits.items():
                window_seconds = self._get_window_seconds(window_name)
                key = f"rate_limit:{limit_type.value}:{identifier}:{window_name}:{current_time // window_seconds}"
                
                current_count = await redis_client.get(key)
                current_count = int(current_count) if current_count else 0
                
                reset_time = ((current_time // window_seconds) + 1) * window_seconds
                
                status["windows"][window_name] = {
                    "limit": limit,
                    "current": current_count,
                    "remaining": max(0, limit - current_count),
                    "reset_time": reset_time,
                    "reset_in": reset_time - current_time
                }
            
            return status
            
        except Exception as e:
            logger.error("Failed to get rate limit status", identifier=identifier, error=str(e))
            return {"error": "failed_to_get_status"}
    
    async def reset_rate_limit(
        self,
        identifier: str,
        limit_type: RateLimitType,
        window: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reset rate limits for an identifier."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            current_time = int(time.time())
            
            if window:
                # Reset specific window
                windows_to_reset = [window]
            else:
                # Reset all windows
                windows_to_reset = ["per_second", "per_minute", "per_hour", "per_day"]
            
            reset_count = 0
            
            for window_name in windows_to_reset:
                window_seconds = self._get_window_seconds(window_name)
                key = f"rate_limit:{limit_type.value}:{identifier}:{window_name}:{current_time // window_seconds}"
                
                deleted = await redis_client.delete(key)
                if deleted:
                    reset_count += 1
            
            logger.info(
                "Rate limits reset",
                identifier=identifier,
                limit_type=limit_type.value,
                windows_reset=reset_count
            )
            
            return {
                "success": True,
                "identifier": identifier,
                "limit_type": limit_type.value,
                "windows_reset": reset_count
            }
            
        except Exception as e:
            logger.error("Failed to reset rate limits", identifier=identifier, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def set_custom_limit(
        self,
        identifier: str,
        limit_type: RateLimitType,
        window: str,
        limit: int,
        expires_in: Optional[int] = None
    ) -> Dict[str, Any]:
        """Set custom rate limit for specific identifier."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            custom_key = f"custom_limit:{limit_type.value}:{identifier}:{window}"
            
            if expires_in:
                await redis_client.setex(custom_key, expires_in, str(limit))
            else:
                await redis_client.set(custom_key, str(limit))
            
            logger.info(
                "Custom rate limit set",
                identifier=identifier,
                limit_type=limit_type.value,
                window=window,
                limit=limit
            )
            
            return {
                "success": True,
                "identifier": identifier,
                "limit_type": limit_type.value,
                "window": window,
                "limit": limit,
                "expires_in": expires_in
            }
            
        except Exception as e:
            logger.error("Failed to set custom limit", identifier=identifier, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def get_top_consumers(
        self,
        limit_type: RateLimitType,
        window: str = "per_hour",
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top consumers by request count."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            current_time = int(time.time())
            window_seconds = self._get_window_seconds(window)
            current_window = current_time // window_seconds
            
            # Get all keys for this window
            pattern = f"rate_limit:{limit_type.value}:*:{window}:{current_window}"
            keys = await redis_client.keys(pattern)
            
            consumers = []
            
            for key in keys:
                count = await redis_client.get(key)
                if count:
                    # Extract identifier from key
                    parts = key.split(":")
                    identifier = parts[2]
                    
                    consumers.append({
                        "identifier": identifier,
                        "count": int(count),
                        "window": window
                    })
            
            # Sort by count descending
            consumers.sort(key=lambda x: x["count"], reverse=True)
            
            return consumers[:top_n]
            
        except Exception as e:
            logger.error("Failed to get top consumers", limit_type=limit_type.value, error=str(e))
            return []
    
    def _get_applicable_limits(
        self,
        limit_type: RateLimitType,
        endpoint: Optional[str] = None,
        custom_limits: Optional[Dict[str, int]] = None
    ) -> Dict[str, int]:
        """Get applicable rate limits for the request."""
        
        limits = {}
        
        # Start with default limits
        prefix = limit_type.value.replace("per_", "")
        for window in ["per_second", "per_minute", "per_hour", "per_day"]:
            key = f"{prefix}_{window}"
            if key in self.default_limits:
                limits[window] = self.default_limits[key]
        
        # Apply endpoint-specific limits
        if endpoint and endpoint in self.endpoint_limits:
            endpoint_limits = self.endpoint_limits[endpoint]
            for window, limit in endpoint_limits.items():
                if window.startswith(prefix):
                    window_name = window.replace(f"{prefix}_", "")
                    limits[window_name] = limit
        
        # Apply custom limits
        if custom_limits:
            limits.update(custom_limits)
        
        return limits
    
    def _get_window_seconds(self, window_name: str) -> int:
        """Get window duration in seconds."""
        
        window_map = {
            "per_second": 1,
            "per_minute": 60,
            "per_hour": 3600,
            "per_day": 86400
        }
        
        return window_map.get(window_name, 60)
    
    async def _increment_counters(
        self,
        identifier: str,
        limit_type: RateLimitType,
        limits: Dict[str, int],
        current_time: int
    ):
        """Increment rate limit counters."""
        
        for window_name in limits.keys():
            window_seconds = self._get_window_seconds(window_name)
            key = f"rate_limit:{limit_type.value}:{identifier}:{window_name}:{current_time // window_seconds}"
            
            # Increment counter
            await redis_client.incr(key)
            
            # Set expiration
            await redis_client.expire(key, window_seconds * 2)  # Keep for 2 windows
    
    async def _get_current_usage(
        self,
        identifier: str,
        limit_type: RateLimitType,
        current_time: int
    ) -> Dict[str, int]:
        """Get current usage across all windows."""
        
        usage = {}
        
        for window_name in ["per_second", "per_minute", "per_hour", "per_day"]:
            window_seconds = self._get_window_seconds(window_name)
            key = f"rate_limit:{limit_type.value}:{identifier}:{window_name}:{current_time // window_seconds}"
            
            count = await redis_client.get(key)
            usage[window_name] = int(count) if count else 0
        
        return usage

# Decorator for rate limiting
def rate_limit(
    limit_type: RateLimitType,
    identifier_func: callable,
    endpoint: Optional[str] = None,
    custom_limits: Optional[Dict[str, int]] = None
):
    """Decorator for rate limiting endpoints."""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get identifier
            identifier = identifier_func(*args, **kwargs)
            
            # Check rate limit
            allowed, limit_info = await rate_limiter.check_rate_limit(
                identifier=identifier,
                limit_type=limit_type,
                endpoint=endpoint,
                custom_limits=custom_limits
            )
            
            if not allowed:
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {limit_type.value}",
                    limit_info
                )
            
            # Execute function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# Global instance
rate_limiter = RateLimiter()