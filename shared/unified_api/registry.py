"""
Provider registry for managing model providers.
Ported from framework/api/registry.py with auto-discovery capabilities.
"""

import importlib
import inspect
import pkgutil
from typing import Dict, Type, Optional, List, Any
import logging

from .base import BaseModelProvider

logger = logging.getLogger(__name__)

class ProviderRegistry:
    """Manages registration and discovery of model providers."""

    def __init__(self):
        self._providers: Dict[str, Type[BaseModelProvider]] = {}
        
        # Provider alias mapping for exact matches
        self._provider_aliases: Dict[str, str] = {
            # Google variations
            "googleai": "google",
            "google-genai": "google", 
            "google_genai": "google",
            "genai": "google",
            
            # OpenAI variations
            "openai-gpt": "openai",
            "openai_gpt": "openai",
            "gpt": "openai",
            
            # Anthropic variations
            "anthropic-claude": "anthropic",
            "anthropic_claude": "anthropic",
            "claude": "anthropic",
            
            # HuggingFace variations
            "huggingface": "huggingface",
            "hf": "huggingface",
            "hugging_face": "huggingface",
            
            # Local variations
            "local-mock": "local",
            "local_mock": "local",
            "mock": "local",
            "test": "local",
        }

    def register_provider(self, provider_class: Type[BaseModelProvider]) -> None:
        """Register a provider class."""
        provider_name = provider_class.get_provider_name()
        if provider_name in self._providers:
            logger.warning(f"Provider '{provider_name}' is already registered. Overwriting.")
        self._providers[provider_name] = provider_class
        logger.info(f"Provider '{provider_name}' registered.")

    def resolve_provider_name(self, requested_name: str) -> str:
        """Resolve a provider name using alias mapping."""
        if not requested_name:
            raise ValueError("Provider name cannot be empty")
            
        # Normalize the requested name
        normalized_name = requested_name.lower().strip()
        
        # 1. Check exact match in registered providers
        if normalized_name in self._providers:
            return normalized_name
        
        # 2. Check alias mapping
        if normalized_name in self._provider_aliases:
            canonical_name = self._provider_aliases[normalized_name]
            if canonical_name in self._providers:
                return canonical_name
        
        # 3. Check substring matching for registered providers
        for provider_name in self._providers.keys():
            if normalized_name in provider_name or provider_name in normalized_name:
                return provider_name
        
        # 4. If no match found, raise error
        available_providers = list(self._providers.keys())
        available_aliases = list(self._provider_aliases.keys())
        raise ValueError(
            f"Provider '{requested_name}' not found. "
            f"Available providers: {available_providers}. "
            f"Available aliases: {available_aliases}"
        )

    def get_provider(self, provider_name: str) -> Type[BaseModelProvider]:
        """Get a provider class by name."""
        resolved_name = self.resolve_provider_name(provider_name)
        return self._providers[resolved_name]

    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def list_providers_with_aliases(self) -> Dict[str, List[str]]:
        """Get all providers with their known aliases."""
        result = {}
        for provider_name in self._providers.keys():
            aliases = [alias for alias, canonical in self._provider_aliases.items() 
                      if canonical == provider_name]
            result[provider_name] = aliases
        return result

    def auto_discover(self, providers_module) -> None:
        """
        Auto-discover and register providers from a module.
        This is the key method that enables plugin architecture.
        """
        try:
            for importer, modname, ispkg in pkgutil.iter_modules(providers_module.__path__):
                if modname.startswith('_'):
                    continue  # Skip private modules
                
                try:
                    module = importlib.import_module(f"{providers_module.__name__}.{modname}")
                    
                    # Look for provider classes in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BaseModelProvider) and 
                            obj != BaseModelProvider and 
                            hasattr(obj, 'get_provider_name')):
                            self.register_provider(obj)
                            
                except Exception as e:
                    logger.warning(f"Failed to import provider module {modname}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to auto-discover providers: {e}")