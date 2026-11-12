"""Plugin wrapper for Multilingual Robustness evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("multilingual_robustness_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "MultilingualRobustnessEvaluator")


class MultilingualRobustnessEvaluatorPlugin(PluginInterface):
    """Multilingual Robustness plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "multilingual_robustness",
            "version": "1.0.0",
            "description": "Per-language attack success with benign twins; finds weak safety coverage in non-English languages.",
            "author": "AI Compliance Team",
            "framework": "MULTILINGUAL_ROBUSTNESS",
            "category": "Security",
            "tags": ['multilingual', 'jailbreak', 'llm01', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
