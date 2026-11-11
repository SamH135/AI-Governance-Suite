# services/compliance/services/evaluator_factory.py
"""Legacy factory for backward compatibility."""

from typing import Dict, Type, List
import structlog
import asyncio

from ..framework.core.base import BaseEvaluator
from ..framework.core.registry import Registry
from ...shared.exceptions import ValidationError

logger = structlog.get_logger()


class EvaluatorFactory:
    """Legacy factory class - delegates to Registry."""
    
    @classmethod
    def get_evaluator(cls, framework: str) -> BaseEvaluator:
        """Get an evaluator instance."""
        try:
            Registry.discover_evaluators()
            return Registry.get_evaluator(framework)
        except Exception as e:
            logger.error("Factory failed", framework=framework, error=str(e))
            raise ValidationError(f"Evaluator not found: {framework}")
    
    @classmethod
    def get_available_frameworks(cls) -> List[str]:
        """Get list of available frameworks."""
        Registry.discover_evaluators()
        return Registry.list_evaluators()
    
    @classmethod
    def register_evaluator(cls, framework: str, evaluator_class: Type[BaseEvaluator]):
        """Register a new evaluator."""
        Registry.register_evaluator(evaluator_class)
        logger.info("Registered evaluator via legacy factory", framework=framework)
    
    @classmethod
    def unregister_evaluator(cls, framework: str):
        """Unregister an evaluator."""
        # Registry doesn't have unregister, so we'll just log
        logger.info("Unregister requested via legacy factory", framework=framework)
