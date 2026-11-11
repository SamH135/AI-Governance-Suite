"""Plugin wrapper for Memory Poisoning evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("memory_poisoning_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "MemoryPoisoningEvaluator")


class MemoryPoisoningEvaluatorPlugin(PluginInterface):
    """Memory Poisoning plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "memory_poisoning",
            "version": "1.0.0",
            "description": "Planted instructions in working memory checked for execution on later tasks (ASI06).",
            "author": "AI Compliance Team",
            "framework": "MEMORY_POISONING",
            "category": "Security",
            "tags": ['memory-poisoning', 'asi06', 'context-poisoning', 'agentic', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
