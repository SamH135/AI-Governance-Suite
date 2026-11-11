"""Plugin wrapper for Jailbreak Robustness evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("jailbreak_robustness_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "JailbreakRobustnessEvaluator")


class JailbreakRobustnessEvaluatorPlugin(PluginInterface):
    """Jailbreak Robustness plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "jailbreak_robustness",
            "version": "1.0.0",
            "description": "Two-sided probe: StrongREJECT-style jailbreak scoring plus benign-twin over-refusal measurement (OWASP LLM01).",
            "author": "AI Compliance Team",
            "framework": "JAILBREAK_ROBUSTNESS",
            "category": "Security",
            "tags": ['jailbreak', 'llm01', 'strongreject', 'over-refusal', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
