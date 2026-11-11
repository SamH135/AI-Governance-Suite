"""Plugin wrapper for Excessive Agency evaluator."""

from typing import Dict, Any, Type
import importlib.util
from pathlib import Path
import structlog

from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("excessive_agency_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
AgencyEvaluator = getattr(_eval_mod, "AgencyEvaluator")

logger = structlog.get_logger()

class ExcessiveAgencyPlugin(PluginInterface):
    """Excessive Agency plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "excessive_agency",
            "version": "2.0.0",
            "description": "Evaluates AI outputs for excessive agency, capability claims, and self-awareness using pattern matching and Claude LLM risk assessment.",
            "author": "AI Compliance Team",
            "framework": "EXCESSIVE_AGENCY",
            "category": "Safety & Governance",
            "tags": ["agency", "safety", "boundaries", "capabilities", "self-awareness", "claude-default"],
            "dependencies": [],
            "supported_models": ["claude-3-5-sonnet", "claude-3-haiku-20240307", "claude-3-sonnet-20240229", "gpt-4"],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        return AgencyEvaluator

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return isinstance(config, dict)

    def on_load(self) -> None:
        logger.info("Excessive Agency plugin loaded successfully")

    def on_unload(self) -> None:
        logger.info("Excessive Agency plugin unloaded")
