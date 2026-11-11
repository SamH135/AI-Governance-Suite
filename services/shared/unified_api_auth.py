"""
Unified API Authentication Helper for Services

This module provides utilities to set up authentication for the unified AI API
so services can access saved API keys from the gateway.
"""

import logging
import os
import sys
from typing import Optional
from fastapi import Request, Depends, HTTPException

# Add shared directory to path
shared_path = os.path.join(os.path.dirname(__file__), '../../shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

try:
    from unified_api import set_unified_api_auth
    UNIFIED_API_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Unified API not available: {e}")
    UNIFIED_API_AVAILABLE = False
    def set_unified_api_auth(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

class UnifiedAPIAuthManager:
    """Manages authentication setup for unified API in services."""
    
    def __init__(self):
        self.current_user_id = None
        self.current_token = None
        
    def set_current_auth(self, api_token: str, user_id: int):
        """Set current authentication context."""
        if UNIFIED_API_AVAILABLE:
            self.current_user_id = user_id
            self.current_token = api_token
            set_unified_api_auth(api_token, user_id)
            logger.info(f"Unified API authentication set for user {user_id}")
        else:
            logger.warning("Unified API not available, skipping auth setup")
    
    def clear_auth(self):
        """Clear current authentication context."""
        self.current_user_id = None
        self.current_token = None
        logger.info("Unified API authentication cleared")

# Global instance
auth_manager = UnifiedAPIAuthManager()

def get_auth_manager() -> UnifiedAPIAuthManager:
    """Get the global auth manager instance."""
    return auth_manager

async def setup_unified_api_auth_from_request(request: Request):
    """
    Set up unified API authentication from FastAPI request.
    
    This should be called in route handlers that need to use the unified API
    with saved API keys.
    """
    try:
        # Extract auth token from request headers
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning("No valid authorization header found for unified API auth")
            return
        
        api_token = auth_header.replace('Bearer ', '')
        
        # For now, we'll need to get user_id from the request context
        # This would typically come from your auth system
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            # Try to extract from request context or JWT token
            # This is a simplified approach - in production you'd decode the JWT
            logger.warning("No user_id found in request state for unified API auth")
            return
        
        # Set up authentication
        auth_manager.set_current_auth(api_token, user_id)
        
    except Exception as e:
        logger.error(f"Failed to setup unified API auth from request: {e}")

def setup_unified_api_auth_from_credentials(api_token: str, user_id: int):
    """
    Set up unified API authentication from explicit credentials.
    
    Use this when you have direct access to auth credentials.
    """
    try:
        auth_manager.set_current_auth(api_token, user_id)
    except Exception as e:
        logger.error(f"Failed to setup unified API auth from credentials: {e}")

def get_current_user_context():
    """Get current user context for unified API."""
    return {
        'user_id': auth_manager.current_user_id,
        'token': auth_manager.current_token
    }

# Dependency for FastAPI routes
async def setup_unified_api_auth_dependency(request: Request):
    """FastAPI dependency to automatically set up unified API auth."""
    await setup_unified_api_auth_from_request(request)
    return auth_manager

# Context manager for temporary auth setup
class unified_api_auth_context:
    """Context manager for temporary unified API authentication setup."""
    
    def __init__(self, api_token: str, user_id: int):
        self.api_token = api_token
        self.user_id = user_id
        self.previous_user_id = None
        self.previous_token = None
    
    def __enter__(self):
        # Save current auth state
        self.previous_user_id = auth_manager.current_user_id
        self.previous_token = auth_manager.current_token
        
        # Set new auth
        setup_unified_api_auth_from_credentials(self.api_token, self.user_id)
        return auth_manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous auth state
        if self.previous_token and self.previous_user_id:
            auth_manager.set_current_auth(self.previous_token, self.previous_user_id)
        else:
            auth_manager.clear_auth()

# Utility functions for common patterns
def with_user_api_keys(func):
    """
    Decorator to ensure unified API is set up with user's saved API keys.
    
    The decorated function must have api_token and user_id parameters or
    access them from request context.
    """
    def wrapper(*args, **kwargs):
        # This is a simple decorator - you might want to make it more sophisticated
        # to automatically extract auth from FastAPI request context
        return func(*args, **kwargs)
    return wrapper

# Environment-based auth setup for services
def setup_service_auth():
    """
    Set up unified API auth using service environment variables.
    
    This is useful for services that run with a service account or
    have static authentication.
    """
    service_token = os.getenv('SERVICE_API_TOKEN')
    service_user_id = os.getenv('SERVICE_USER_ID')
    
    if service_token and service_user_id:
        try:
            user_id = int(service_user_id)
            setup_unified_api_auth_from_credentials(service_token, user_id)
            logger.info(f"Service unified API auth set up for user {user_id}")
        except ValueError:
            logger.error(f"Invalid SERVICE_USER_ID: {service_user_id}")
    else:
        logger.info("No service auth credentials found in environment")