"""Plugin wrapper for Multi-Turn Escalation evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("multi_turn_escalation_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "MultiTurnEscalationEvaluator")


class MultiTurnEscalationEvaluatorPlugin(PluginInterface):
    """Multi-Turn Escalation plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "multi_turn_escalation",
            "version": "1.0.0",
            "description": "Scripted Crescendo-style multi-turn jailbreaks with final-turn StrongREJECT scoring (LLM01).",
            "author": "AI Compliance Team",
            "framework": "MULTI_TURN_ESCALATION",
            "category": "Security",
            "tags": ['multi-turn', 'crescendo', 'jailbreak', 'llm01', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
