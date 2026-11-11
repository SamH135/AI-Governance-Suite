"""Plugin wrapper for Tool Poisoning evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("tool_poisoning_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "ToolPoisoningEvaluator")


class ToolPoisoningEvaluatorPlugin(PluginInterface):
    """Tool Poisoning plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "tool_poisoning",
            "version": "1.0.0",
            "description": "Malicious instructions embedded in simulated tool manifests and shadowed names (ASI04, MCP poisoning).",
            "author": "AI Compliance Team",
            "framework": "TOOL_POISONING",
            "category": "Security",
            "tags": ['tool-poisoning', 'asi04', 'mcp', 'agentic', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
