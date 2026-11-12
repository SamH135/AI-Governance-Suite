"""Plugin wrapper for Model Extraction evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("model_extraction_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "ModelExtractionEvaluator")


class ModelExtractionEvaluatorPlugin(PluginInterface):
    """Model Extraction plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "model_extraction",
            "version": "1.0.0",
            "description": "Verbatim-continuation probes measuring training-data memorization/regurgitation.",
            "author": "AI Compliance Team",
            "framework": "MODEL_EXTRACTION",
            "category": "Privacy",
            "tags": ['extraction', 'memorization', 'regurgitation', 'privacy', 'probe'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
