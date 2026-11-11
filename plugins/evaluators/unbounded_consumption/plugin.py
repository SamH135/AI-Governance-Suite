"""Plugin wrapper for Unbounded Consumption evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("unbounded_consumption_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "UnboundedConsumptionEvaluator")


class UnboundedConsumptionEvaluatorPlugin(PluginInterface):
    """Unbounded Consumption plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "unbounded_consumption",
            "version": "1.0.0",
            "description": "Deterministic probe: measures runaway generation via amplification, repetition loops, and output-cap hits (OWASP LLM10).",
            "author": "AI Compliance Team",
            "framework": "UNBOUNDED_CONSUMPTION",
            "category": "Security",
            "tags": ['unbounded-consumption', 'llm10', 'denial-of-wallet', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
