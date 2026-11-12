"""Plugin wrapper for Code Execution evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("code_execution_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "CodeExecutionEvaluator")


class CodeExecutionEvaluatorPlugin(PluginInterface):
    """Code Execution plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "code_execution",
            "version": "1.0.0",
            "description": "Probes unsafe use of execution-capable tools (ASI05): injected, destructive, out-of-scope, unneeded.",
            "author": "AI Compliance Team",
            "framework": "CODE_EXECUTION",
            "category": "Security",
            "tags": ['code-execution', 'asi05', 'tools', 'agentic', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
