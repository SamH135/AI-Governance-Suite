"""Plugin wrapper for System Prompt Leakage evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("system_prompt_leakage_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "SystemPromptLeakageEvaluator")


class SystemPromptLeakageEvaluatorPlugin(PluginInterface):
    """System Prompt Leakage plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "system_prompt_leakage",
            "version": "1.0.0",
            "description": "Probe evaluator: attempts to extract the target's system prompt via direct, encoded, and multi-turn techniques (OWASP LLM07).",
            "author": "AI Compliance Team",
            "framework": "SYSTEM_PROMPT_LEAKAGE",
            "category": "Security",
            "tags": ['system-prompt-leakage', 'llm07', 'extraction', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
