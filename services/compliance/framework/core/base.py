# framework/core/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Dict, Optional

# Import ModelConfig for type hinting
try:
    from shared.unified_api.base import ModelConfig
except ImportError:
    ModelConfig = Any


class EvaluatorCapability(Enum):
    """Defines the capabilities of an evaluator."""
    RULE_BASED = "rule_based"
    LLM_ENHANCED = "llm_enhanced"
    RAG_ENABLED = "rag_enabled"
    HYBRID = "hybrid"


class ModelRequirement(Enum):
    """Defines specific model requirements for an evaluator."""
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass
class LLMRequirements:
    """Defines the LLM requirements for an evaluator."""
    requirement_level: ModelRequirement = ModelRequirement.NONE
    suggested_providers: List[str] = field(default_factory=list)
    min_context_window: Optional[int] = None
    suggested_models: List[str] = field(default_factory=list)
    expected_response_format: str = "text"
    notes: Optional[str] = None


@dataclass
class RAGRequirements:
    """Defines the RAG requirements for an evaluator."""
    requirement_level: ModelRequirement = ModelRequirement.NONE
    vector_store_required: bool = False
    min_context_chunks: int = 3
    max_context_chunks: int = 10
    context_types: List[str] = field(default_factory=list)
    suggested_providers: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class EvaluatorMetadata:
    """Metadata structure for evaluators."""
    name: str
    description: str
    version: str
    category: str
    tags: List[str]
    output_format: str = "default"
    primary_output_key: str = "score"
    display_fields: List[Dict[str, Any]] = field(default_factory=list)
    risk_thresholds: Dict[str, Any] = field(
        default_factory=lambda: {"high": 50, "medium": 20, "low": 0}
    )
    capabilities: List[EvaluatorCapability] = field(default_factory=list)
    llm_requirements: LLMRequirements = field(default_factory=LLMRequirements)
    rag_requirements: RAGRequirements = field(default_factory=RAGRequirements)
    requires_test_subject_config: bool = False
    fallback_mode: str = "error"
    estimated_runtime: str = "fast"
    parallel_safe: bool = True


class BaseEvaluator(ABC):
    """Base evaluator with unified API support."""

    @classmethod
    @abstractmethod
    def get_metadata(cls) -> EvaluatorMetadata:
        """Return metadata describing this evaluator's capabilities and requirements."""
        pass

    @abstractmethod
    def evaluate(
            self,
            text: str,
            test_subject_config: Optional[ModelConfig] = None,
            evaluator_llm_config: Optional[ModelConfig] = None,
            rag_config: Optional[Dict[str, Any]] = None,
            vector_store: Optional[Any] = None,
            **kwargs
    ) -> Dict[str, Any]:
        """Evaluate text using configurable model resources."""
        pass

    @abstractmethod
    def interpret(self, results: Dict[str, Any]) -> str:
        """Generate human-readable interpretation of results."""
        pass

    @abstractmethod
    def summarize_category_results(self, category_results: List[Dict[str, Any]]) -> str:
        """Summarize results for a category of prompts."""
        pass
