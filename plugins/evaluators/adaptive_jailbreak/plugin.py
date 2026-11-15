"""Plugin wrapper for Adaptive Jailbreak (PAIR) evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("adaptive_jailbreak_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "AdaptiveJailbreakEvaluator")


class AdaptiveJailbreakEvaluatorPlugin(PluginInterface):
    """Adaptive Jailbreak plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "adaptive_jailbreak",
            "version": "1.0.0",
            "description": "Attacker-LLM PAIR probing: iterative jailbreak refinement with judge-scored success (OWASP LLM01).",
            "author": "AI Compliance Team",
            "framework": "ADAPTIVE_JAILBREAK",
            "category": "Security",
            "tags": ['adaptive', 'pair', 'jailbreak', 'llm01', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
