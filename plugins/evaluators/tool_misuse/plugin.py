"""Plugin wrapper for Tool Misuse evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("tool_misuse_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "ToolMisuseEvaluator")


class ToolMisuseEvaluatorPlugin(PluginInterface):
    """Tool Misuse plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "tool_misuse",
            "version": "1.0.0",
            "description": "Simulated-tool probe for unauthorized calls and exfiltration via tool arguments (LLM06/ASI02).",
            "author": "AI Compliance Team",
            "framework": "TOOL_MISUSE",
            "category": "Security",
            "tags": ['tool-misuse', 'llm06', 'asi02', 'agentic', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
