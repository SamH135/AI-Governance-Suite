"""Plugin wrapper for Vector & Embedding Security evaluator."""

from typing import Dict, Any
import importlib.util
from pathlib import Path

from services.compliance.services.evaluators.plugin_manager import PluginInterface

_eval_path = Path(__file__).parent / "evaluator.py"
_spec = importlib.util.spec_from_file_location("vector_embedding_security_eval_mod", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
EvalCls = getattr(_eval_mod, "VectorEmbeddingSecurityEvaluator")


class VectorEmbeddingSecurityEvaluatorPlugin(PluginInterface):
    """Vector & Embedding Security plugin implementation."""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "vector_embedding_security",
            "version": "1.0.0",
            "description": "Fixture-simulated retrieval: poisoned chunks and cross-tenant canary docs (LLM08).",
            "author": "AI Compliance Team",
            "framework": "VECTOR_EMBEDDING_SECURITY",
            "category": "Security",
            "tags": ['vector-embedding', 'llm08', 'rag-poisoning', 'probe', 'security'],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }

    def get_evaluator_class(self):
        return EvalCls

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
