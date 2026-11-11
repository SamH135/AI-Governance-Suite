"""Plugin wrapper for G-Eval metric evaluator."""

from typing import Dict, Any, Type
import importlib.util
from pathlib import Path
import structlog

from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("geval_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
GEvalEvaluator = getattr(_eval_mod, "GEvalEvaluator")

logger = structlog.get_logger()

class GEvalPlugin(PluginInterface):
    """G-Eval Metric plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "g_eval_metric",
            "version": "2.0.0",
            "description": "Production-quality G-Eval implementation with weighted scoring, CoT, rubrics, and Claude as default LLM judge.",
            "author": "AI Compliance Team",
            "framework": "G_EVAL",
            "category": "Quality Assessment",
            "tags": ["g-eval", "llm-judge", "chain-of-thought", "rubrics", "claude-default"],
            "dependencies": [],
            "supported_models": ["claude-3-5-sonnet", "claude-3-sonnet-20240229", "gpt-4"],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        return GEvalEvaluator

    def validate_config(self, config: Dict[str, Any]) -> bool:
        if not isinstance(config, dict):
            return False
        if "threshold" in config:
            val = config["threshold"]
            if not isinstance(val, (int, float)) or val < 0 or val > 1:
                return False
        return True

    def on_load(self) -> None:
        logger.info("G-Eval plugin loaded successfully")

    def on_unload(self) -> None:
        logger.info("G-Eval plugin unloaded")
