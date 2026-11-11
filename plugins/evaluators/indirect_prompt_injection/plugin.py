"""Plugin wrapper for Indirect Prompt Injection evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("indirect_prompt_injection_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "IndirectPromptInjectionEvaluator")


class IndirectPromptInjectionEvaluatorPlugin(PluginInterface):
    """Indirect Prompt Injection plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "indirect_prompt_injection",
            "version": "1.0.0",
            "description": "Attack payloads via retrieved docs, tool results, and emails; checks execution, exfil renders, and tool abuse (LLM01/ASI01).",
            "author": "AI Compliance Team",
            "framework": "INDIRECT_PROMPT_INJECTION",
            "category": "Security",
            "tags": ['indirect-prompt-injection', 'llm01', 'asi01', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
