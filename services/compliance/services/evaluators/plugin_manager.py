"""Plugin manager interface and dynamic plugin loader."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Type, List, Optional
import structlog

from .base_evaluator import BaseEvaluator
from ....shared.evaluator_plugin_system import PluginManager as SharedPluginManager, plugin_manager as shared_plugin_manager

logger = structlog.get_logger()

class PluginInterface(ABC):
    """Abstract base class for all evaluator plugins."""

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata dictionary."""
        pass

    @abstractmethod
    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        """Return the evaluator class implemented by this plugin."""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration dictionary."""
        return True

    def on_load(self) -> None:
        """Lifecycle hook called when plugin is loaded."""
        pass

    def on_unload(self) -> None:
        """Lifecycle hook called when plugin is unloaded."""
        pass

class PluginMetadata:
    """Plugin metadata wrapper."""
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "unknown")
        self.version = data.get("version", "1.0.0")
        self.description = data.get("description", "")
        self.author = data.get("author", "Unknown")
        self.framework = data.get("framework", self.name.upper())
        self.category = data.get("category", "custom")
        self.tags = data.get("tags", [])
        self.dependencies = data.get("dependencies", [])
        self.supported_models = data.get("supported_models", [])
        self.min_platform_version = data.get("min_platform_version", "1.0.0")
        self.enabled = data.get("enabled", True)
        self.config_schema = data.get("config_schema", {})

class PluginManagerWrapper:
    """Compliance plugin manager wrapping shared plugin system."""

    def __init__(self):
        self.shared_manager = shared_plugin_manager
        self.loaded_plugins: Dict[str, PluginInterface] = {}
        self.plugins_dir = self.shared_manager.plugin_directory

    async def discover_plugins(self) -> List[str]:
        """Discover available plugin packages in plugins directory."""
        import os
        from pathlib import Path
        
        plugins = []
        plugins_root = Path("plugins/evaluators")
        if plugins_root.exists():
            for item in plugins_root.iterdir():
                if item.is_dir() and (item / "plugin.py").exists():
                    plugins.append(item.name)
        return plugins

    def get_loaded_plugins(self) -> List[str]:
        return list(self.loaded_plugins.keys())

    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        if plugin_name in self.loaded_plugins:
            return PluginMetadata(self.loaded_plugins[plugin_name].get_metadata())
        return None

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        return self.shared_manager.plugin_configs.get(plugin_name, {})

    def get_evaluator_class(self, plugin_name: str) -> Optional[Type[BaseEvaluator]]:
        if plugin_name in self.loaded_plugins:
            return self.loaded_plugins[plugin_name].get_evaluator_class()
        return None

    async def load_plugin(self, plugin_name: str) -> bool:
        """Dynamically load a plugin module by name."""
        import importlib.util
        from pathlib import Path
        
        plugin_file = Path("plugins/evaluators") / plugin_name / "plugin.py"
        if not plugin_file.exists():
            logger.error("Plugin file not found", path=str(plugin_file))
            return False
            
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", plugin_file)
            if not spec or not spec.loader:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find PluginInterface subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, PluginInterface) and attr != PluginInterface:
                    instance = attr()
                    instance.on_load()
                    self.loaded_plugins[plugin_name] = instance
                    logger.info("Loaded evaluator plugin", name=plugin_name)
                    return True
            return False
        except Exception as e:
            logger.error("Failed to load plugin", plugin=plugin_name, error=str(e))
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name in self.loaded_plugins:
            self.loaded_plugins[plugin_name].on_unload()
            del self.loaded_plugins[plugin_name]
            return True
        return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        await self.unload_plugin(plugin_name)
        return await self.load_plugin(plugin_name)

    async def enable_plugin(self, plugin_name: str) -> bool:
        return await self.load_plugin(plugin_name)

    async def disable_plugin(self, plugin_name: str) -> bool:
        return await self.unload_plugin(plugin_name)

# Export singleton
plugin_manager = PluginManagerWrapper()
