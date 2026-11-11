"""Plugin wrapper for Generic Compliance evaluator."""

from typing import Dict, Any, Type
import importlib.util
from pathlib import Path
import structlog

from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("generic_compliance_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
GenericComplianceEvaluator = getattr(_eval_mod, "GenericComplianceEvaluator")

logger = structlog.get_logger()

class GenericCompliancePlugin(PluginInterface):
    """Generic Compliance plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "generic_compliance",
            "version": "2.0.0",
            "description": "Evaluates responses for compliance using rule-based, LLM-enhanced (Claude default), and RAG-enabled analysis.",
            "author": "AI Compliance Team",
            "framework": "GENERIC_COMPLIANCE",
            "category": "Compliance",
            "tags": ["regulations", "ethics", "gdpr", "hipaa", "rag", "compliance", "claude-default"],
            "dependencies": [],
            "supported_models": ["claude-3-5-sonnet", "claude-3-haiku-20240307", "claude-3-sonnet-20240229", "gpt-4"],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        return GenericComplianceEvaluator

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return isinstance(config, dict)

    def on_load(self) -> None:
        logger.info("Generic Compliance plugin loaded successfully")

    def on_unload(self) -> None:
        logger.info("Generic Compliance plugin unloaded")
