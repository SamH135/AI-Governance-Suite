"""
Configuration management for API providers.
Ported from framework/api/config.py with saved API key integration

Note: Provider configurations can be extended to read from the database (provider_configs table)
for fully dynamic management. The current hardcoded configs serve as a fallback and contain
minimal information (env keys, default models, API URLs). For dynamic provider management,
use the database-based approach in the gateway's models_service.
"""

import os
import aiohttp
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Centralized configuration management for API providers with saved API key integration."""

    def __init__(self):
        # Default configurations can be extended or loaded from a file/env
        # Note: default_model is deprecated - use dynamic discovery or specify model_id manually
        self.providers_config: Dict[str, Dict[str, Any]] = {
            "openai": {
                "env_key": "OPENAI_API_KEY",
                "default_model": None,
                "api_url": "https://api.openai.com/v1/chat/completions"
            },
            "anthropic": {
                "env_key": "ANTHROPIC_API_KEY",
                "default_model": None,
                "api_url": "https://api.anthropic.com/v1/messages"
            },
            "huggingface": {
                "env_key": "HF_TOKEN",
                "default_model": None,
                "api_url": None
            },
            "google": {
                "env_key": "GOOGLE_API_KEY",
                "default_model": None,
                "api_url": None
            },
            "local": {
                "env_key": None,
                "default_model": "local-mock-model",
                "api_url": None
            }
        }
        
        # Configuration for accessing saved API keys
        self.gateway_url = os.getenv('GATEWAY_URL', 'http://gateway:8000')
        self.api_token = None
        self.user_id = None
        
        logger.info("ConfigManager initialized with default provider configurations and saved API key support.")

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get raw configuration for a specific provider."""
        return self.providers_config.get(provider_name)

    def set_auth(self, api_token: str, user_id: int):
        """Set authentication credentials for accessing saved API keys."""
        self.api_token = api_token
        self.user_id = user_id
        logger.info(f"ConfigManager authentication set for user {user_id}")

    def get_api_key(self, provider_name: str) -> Optional[str]:
        """
        Get API key for a provider.
        Priority: 1) Saved API key from gateway, 2) Environment variable
        """
        # First try to get from saved API keys if authenticated
        if self.api_token and self.user_id:
            try:
                # Try to get the current event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, can't use asyncio.run()
                    # For now, skip saved keys and fall back to environment
                    logger.info(f"Async context detected, skipping saved keys for '{provider_name}'")
                except RuntimeError:
                    # No running loop, we can use asyncio.run()
                    saved_key = asyncio.run(self._get_saved_api_key(provider_name))
                    if saved_key:
                        logger.info(f"Using saved API key for provider '{provider_name}'")
                        return saved_key
            except Exception as e:
                logger.warning(f"Failed to retrieve saved API key for '{provider_name}': {e}")
        
        # Fall back to environment variable
        config = self.get_provider_config(provider_name)
        if config and config.get("env_key"):
            api_key = os.environ.get(config["env_key"])
            if api_key:
                logger.info(f"Using environment API key for provider '{provider_name}'")
                return api_key
            else:
                logger.warning(
                    f"API key environment variable {config['env_key']} for provider '{provider_name}' not set."
                )
        
        return None

    async def aget_api_key(self, provider_name: str) -> Optional[str]:
        """
        Async version of get_api_key for use in async contexts.
        Priority: 1) Saved API key from gateway, 2) Environment variable
        """
        # First try to get from saved API keys if authenticated
        if self.api_token and self.user_id:
            try:
                saved_key = await self._get_saved_api_key(provider_name)
                if saved_key:
                    logger.info(f"Using saved API key for provider '{provider_name}'")
                    return saved_key
            except Exception as e:
                logger.warning(f"Failed to retrieve saved API key for '{provider_name}': {e}")
        
        # Fall back to environment variable
        config = self.get_provider_config(provider_name)
        if config and config.get("env_key"):
            api_key = os.environ.get(config["env_key"])
            if api_key:
                logger.info(f"Using environment API key for provider '{provider_name}'")
                return api_key
            else:
                logger.warning(
                    f"API key environment variable {config['env_key']} for provider '{provider_name}' not set."
                )
        
        return None

    async def _get_saved_api_key(self, provider_name: str) -> Optional[str]:
        """Retrieve saved API key from gateway."""
        try:
            async with aiohttp.ClientSession() as session:
                # Get all API keys for the user
                headers = {'Authorization': f'Bearer {self.api_token}'}
                url = f"{self.gateway_url}/api-keys"
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get API keys from gateway: HTTP {response.status}")
                        return None
                    
                    api_keys = await response.json()
                    
                    # Find a key for the specified provider
                    for key_info in api_keys:
                        if (key_info.get('provider') == provider_name and 
                            key_info.get('status') == 'active'):
                            key_id = key_info.get('key_id')
                            if key_id:
                                # Get the actual key value
                                value_url = f"{self.gateway_url}/api-keys/{key_id}/value"
                                async with session.get(value_url, headers=headers) as value_response:
                                    if value_response.status == 200:
                                        result = await value_response.json()
                                        return result.get('key_value')
                    
                    logger.info(f"No active saved API key found for provider '{provider_name}'")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving saved API key for '{provider_name}': {e}")
            return None

    def get_default_model(self, provider_name: str) -> Optional[str]:
        """Get the default model ID for a provider."""
        config = self.get_provider_config(provider_name)
        return config.get("default_model") if config else None

    def get_api_url(self, provider_name: str) -> Optional[str]:
        """Get the API URL for a provider."""
        config = self.get_provider_config(provider_name)
        return config.get("api_url") if config else None