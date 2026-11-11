"""
Shared Unified API module for AI-Governance-Suite microservices.
This ports the working framework/api/ logic to the microservices architecture.
"""

from .api import UnifiedModelAPI, get_unified_api, set_unified_api_auth
from .base import ModelConfig, ModelRequest, ModelResponse, ModelType, APIErrorDetail
from .registry import ProviderRegistry
from .config import ConfigManager

__all__ = [
    "UnifiedModelAPI",
    "get_unified_api", 
    "set_unified_api_auth",
    "ModelConfig",
    "ModelRequest",
    "ModelResponse",
    "ModelType",
    "APIErrorDetail",
    "ProviderRegistry",
    "ConfigManager"
]