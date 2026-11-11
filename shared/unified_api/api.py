"""
Main UnifiedModelAPI class.
Ported from framework/api/__init__.py with auto-discovery.
"""

import logging
from typing import Dict, Type, Optional, Union, List, Any
import inspect

from .base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, ModelType, APIErrorDetail
from .registry import ProviderRegistry
from .config import ConfigManager

logger = logging.getLogger(__name__)

class UnifiedModelAPI:
    """Central interface for all model interactions."""

    def __init__(self):
        self.registry = ProviderRegistry()
        self.config_manager = ConfigManager()
        self._provider_cache: Dict[str, BaseModelProvider] = {}

        # Auto-discover and register providers
        self._discover_providers()

    def _discover_providers(self) -> None:
        """Auto-discover and register available providers using the framework's plugin system."""
        try:
            from . import providers  # providers is the subdirectory
            self.registry.auto_discover(providers)
            logger.info(f"Auto-discovered providers: {self.registry.list_providers()}")
        except ImportError as e:
            logger.warning(f"Failed to import providers package for auto-discovery: {e}")
            logger.warning("No providers directory found - all providers must be manually registered")

    def get_provider(self, config: Union[ModelConfig, Dict[str, Any]]) -> BaseModelProvider:
        """Get or create a provider instance."""
        if isinstance(config, dict):
            # If it's a dict, create ModelConfig from it
            provider_name_in_dict = config.get("provider")
            if not provider_name_in_dict:
                raise ValueError("Provider name must be specified in config dict.")

            # Resolve the provider name using flexible resolution
            resolved_provider_name = self.registry.resolve_provider_name(provider_name_in_dict)
            
            # Get defaults from ConfigManager for this provider
            cm_config = self.config_manager.get_provider_config(resolved_provider_name) or {}

            # Prioritize values from input dict, then ConfigManager, then ModelConfig defaults
            final_config_params = {
                "api_key": config.get("api_key") or self.config_manager.get_api_key(resolved_provider_name),
                "api_url": config.get("api_url") or self.config_manager.get_api_url(resolved_provider_name),
                "model_id": config.get("model_id") or self.config_manager.get_default_model(resolved_provider_name),
                **cm_config,  # Other defaults from config manager
                **config  # Overwrite with anything explicitly passed in the dict
            }
            # Use the resolved provider name instead of the original
            final_config_params["provider"] = resolved_provider_name
            config_obj = ModelConfig(**final_config_params)
        elif isinstance(config, ModelConfig):
            config_obj = config
            # Resolve the provider name using flexible resolution
            resolved_provider_name = self.registry.resolve_provider_name(config_obj.provider)
            config_obj.provider = resolved_provider_name
            
            # Ensure API key and URL are populated if not already set in ModelConfig
            if not config_obj.api_key:
                config_obj.api_key = self.config_manager.get_api_key(config_obj.provider)
            if not config_obj.api_url:
                config_obj.api_url = self.config_manager.get_api_url(config_obj.provider)
        else:
            raise TypeError("config must be a ModelConfig instance or a dictionary.")

        # Fill in missing model_id if needed
        if not config_obj.model_id:
            default_model = self.config_manager.get_default_model(config_obj.provider)
            if default_model:
                config_obj.model_id = default_model
            else:
                raise ValueError(f"model_id not specified and no default found for provider {config_obj.provider}")

        cache_key = f"{config_obj.provider}:{config_obj.model_id}:{config_obj.usage_type.value}"

        if cache_key in self._provider_cache:
            provider = self._provider_cache[cache_key]
            provider.config = config_obj  # Update config in case parameters changed
            return provider

        provider_class = self.registry.get_provider(config_obj.provider)
        provider_class.validate_config(config_obj)  # Validate before instantiation
        provider = provider_class(config_obj)

        self._provider_cache[cache_key] = provider
        return provider

    def generate(
            self,
            prompt: str,
            config: Union[ModelConfig, Dict[str, Any]],
            system_prompt: Optional[str] = None,
            messages: Optional[List[Dict[str, str]]] = None,
            context: Optional[List[str]] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
            **kwargs
    ) -> ModelResponse:
        """Generate a response using the specified model configuration."""
        provider = self.get_provider(config)
        request = ModelRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
            context=context,
            temperature=temperature,
            max_tokens=max_tokens,
            kwargs=kwargs
        )
        try:
            response = provider.generate(request)
            provider._log_usage(request, response)
            return response
        except Exception as e:
            logger.error(f"Error generating response via provider {provider.config.provider}: {e}")
            return ModelResponse(
                content="",
                model_id=provider.config.model_id,
                provider=provider.config.provider,
                error=APIErrorDetail(message=str(e), type="unified_api_error")
            )

    async def agenerate(
            self,
            prompt: str,
            config: Union[ModelConfig, Dict[str, Any]],
            system_prompt: Optional[str] = None,
            messages: Optional[List[Dict[str, str]]] = None,
            context: Optional[List[str]] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
            **kwargs
    ) -> ModelResponse:
        """Asynchronous generation."""
        provider = self.get_provider(config)
        request = ModelRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            messages=messages,
            context=context,
            temperature=temperature,
            max_tokens=max_tokens,
            kwargs=kwargs
        )
        try:
            response = await provider.agenerate(request)
            provider._log_usage(request, response)
            return response
        except Exception as e:
            logger.error(f"Error generating async response via provider {provider.config.provider}: {e}")
            return ModelResponse(
                content="",
                model_id=provider.config.model_id,
                provider=provider.config.provider,
                error=APIErrorDetail(message=str(e), type="unified_api_error")
            )

    def list_providers(self) -> List[str]:
        """List available (registered) providers."""
        return self.registry.list_providers()

    def get_provider_info(self, provider_name: str) -> Dict[str, Any]:
        """Get information about a specific provider class."""
        try:
            resolved_name = self.registry.resolve_provider_name(provider_name)
            provider_class = self.registry.get_provider(resolved_name)
            return {
                "name": provider_class.get_provider_name(),
                "class": provider_class.__name__,
                "module": provider_class.__module__,
                "doc": inspect.getdoc(provider_class),
                "resolved_from": provider_name if provider_name != resolved_name else None
            }
        except ValueError as e:
            raise ValueError(f"Provider '{provider_name}' not found: {e}")

    def get_providers_with_aliases(self) -> Dict[str, List[str]]:
        """Get all providers with their known aliases."""
        return self.registry.list_providers_with_aliases()
    
    def set_auth(self, api_token: str, user_id: int):
        """Set authentication credentials for accessing saved API keys."""
        self.config_manager.set_auth(api_token, user_id)
        logger.info(f"UnifiedModelAPI authentication set for user {user_id}")


# Singleton instance of the API manager
_api_instance: Optional[UnifiedModelAPI] = None

def get_unified_api() -> UnifiedModelAPI:
    """Get the singleton instance of the UnifiedModelAPI."""
    global _api_instance
    if _api_instance is None:
        _api_instance = UnifiedModelAPI()
    return _api_instance

def set_unified_api_auth(api_token: str, user_id: int):
    """Set authentication credentials for the unified API to access saved API keys."""
    api = get_unified_api()
    api.set_auth(api_token, user_id)