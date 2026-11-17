"""Plugin wrapper for Claim Grounding evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("claim_grounding_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "ClaimGroundingEvaluator")


class ClaimGroundingEvaluatorPlugin(PluginInterface):
    """Claim Grounding plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "claim_grounding",
            "version": "1.0.0",
            "description": "Tier-2 faithfulness check: local NLI model scores whether response claims are entailed by evidence documents.",
            "author": "AI Compliance Team",
            "framework": "CLAIM_GROUNDING",
            "category": "Quality",
            "tags": ['groundedness', 'faithfulness', 'nli', 'hallucination', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
