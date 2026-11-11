"""EnhancedEvaluatorFactory combining Registry and PluginManager."""

from typing import Dict, Any, List, Optional, Type
import structlog
import asyncio

from ...framework.core.registry import Registry
from ...framework.core.base import BaseEvaluator
from .plugin_manager import plugin_manager

logger = structlog.get_logger()

class EnhancedEvaluatorFactory:
    """Factory handling built-in and plugin compliance evaluators."""

    @classmethod
    async def reload_plugins(cls):
        """Reload all active evaluator plugins."""
        plugins = await plugin_manager.discover_plugins()
        for p in plugins:
            await plugin_manager.load_plugin(p)
            evaluator_cls = plugin_manager.get_evaluator_class(p)
            if evaluator_cls:
                try:
                    Registry.register_evaluator(evaluator_cls)
                    logger.info("Registered plugin evaluator in core registry", plugin=p)
                except Exception as e:
                    logger.warning("Could not register plugin evaluator", plugin=p, error=str(e))

    @classmethod
    def get_evaluator(cls, framework: str) -> BaseEvaluator:
        """Retrieve evaluator instance by framework name."""
        # Ensure built-ins discovered
        Registry.discover_evaluators()
        return Registry.get_evaluator(framework)

    @classmethod
    def get_framework_statistics(cls) -> Dict[str, Any]:
        """Get summary statistics of registered evaluators."""
        Registry.discover_evaluators()
        evaluators = Registry.list_evaluators()
        return {
            "total_registered": len(evaluators),
            "frameworks": evaluators
        }

enhanced_evaluator_factory = EnhancedEvaluatorFactory()
