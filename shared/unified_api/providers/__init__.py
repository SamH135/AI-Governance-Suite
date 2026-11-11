"""
Provider implementations package for the microservices Unified API system.
Uses auto-discovery pattern - no hardcoded imports required.
Just drop any BaseModelProvider subclass in this directory and it will be auto-discovered.
"""

# No explicit imports needed - the ProviderRegistry will auto-discover all providers
# that inherit from BaseModelProvider in this directory using pkgutil.iter_modules()

__all__ = []  # Will be populated dynamically by auto-discovery