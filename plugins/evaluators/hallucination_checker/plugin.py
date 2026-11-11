"""Plugin wrapper for Hallucination Checker evaluator."""

from typing import Dict, Any, Type
import importlib.util
from pathlib import Path
import structlog

from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("hallucination_checker_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
PrivateHallucinationCheckerEvaluator = getattr(_eval_mod, "PrivateHallucinationCheckerEvaluator")

logger = structlog.get_logger()

class HallucinationCheckerPlugin(PluginInterface):
    """Hallucination Checker plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "hallucination_checker",
            "version": "2.0.0",
            "description": "Hallucination detection engine combining local claim extraction, NLI analysis, and Claude LLM verification.",
            "author": "AI Compliance Team",
            "framework": "HALLUCINATION_CHECKER",
            "category": "Quality & Accuracy",
            "tags": ["hallucination", "fact-checking", "nli", "claude-default"],
            "dependencies": [],
            "supported_models": ["claude-3-5-sonnet", "claude-3-sonnet-20240229", "gpt-4"],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        return PrivateHallucinationCheckerEvaluator

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return isinstance(config, dict)

    def on_load(self) -> None:
        logger.info("Hallucination Checker plugin loaded successfully")

    def on_unload(self) -> None:
        logger.info("Hallucination Checker plugin unloaded")
