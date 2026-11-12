"""Plugin wrapper for Counterfactual Fairness evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("counterfactual_fairness_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "CounterfactualFairnessEvaluator")


class CounterfactualFairnessEvaluatorPlugin(PluginInterface):
    """Counterfactual Fairness plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "counterfactual_fairness",
            "version": "1.0.0",
            "description": "Demographic-swap matched pairs; scores decision consistency across protected attributes.",
            "author": "AI Compliance Team",
            "framework": "COUNTERFACTUAL_FAIRNESS",
            "category": "Fairness",
            "tags": ['fairness', 'bias', 'counterfactual', 'bbq', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
