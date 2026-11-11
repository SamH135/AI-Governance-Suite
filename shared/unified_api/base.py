"""
Base classes and data models for the Unified API system.
Ported from framework/api/base.py
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator, Union, Generator
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """Types of model usage patterns."""
    TEST_SUBJECT = "test_subject"  # Models being tested
    EVALUATOR = "evaluator"      # Models evaluating other models
    RAG = "rag"                  # RAG-enhanced models
    UTILITY = "utility"          # General utility usage

@dataclass
class ModelInfo:
    """Information about a model available from a provider."""
    model_id: str
    name: str
    description: str
    context_window: Optional[int] = None
    max_tokens: Optional[int] = None
    input_price_per_1k: Optional[float] = None
    output_price_per_1k: Optional[float] = None
    capabilities: List[str] = field(default_factory=list)
    deprecated: bool = False
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelConfig:
    """Universal configuration for any model."""
    provider: str  # e.g., "openai", "anthropic", "huggingface"
    model_id: str  # e.g., "gpt-4", "claude-3", "meta-llama/Llama-2-7b"
    api_key: Optional[str] = None
    api_url: Optional[str] = None  # For custom endpoints
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    # Provider-specific options
    provider_options: Dict[str, Any] = field(default_factory=dict)

    # Usage type for logging/metrics
    usage_type: ModelType = ModelType.UTILITY

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class APIErrorDetail:
    message: str
    code: Optional[str] = None
    type: Optional[str] = None
    details: Optional[Dict[str, Any]] = field(default_factory=dict)

@dataclass
class ModelRequest:
    """Standard request format for all models."""
    prompt: str
    system_prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None  # For chat models
    context: Optional[List[str]] = None  # For RAG

    # Override config parameters
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # Additional parameters
    kwargs: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelResponse:
    """Standard response format from all models."""
    content: str
    model_id: str
    provider: str
    usage: Optional[Dict[str, int]] = None  # tokens used, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[APIErrorDetail] = None
    latency: Optional[float] = None

class BaseModelProvider(ABC):
    """Base class for all model providers."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self._setup()

    @abstractmethod
    def _setup(self) -> None:
        """Provider-specific setup (authentication, client initialization, etc.)."""
        pass

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Synchronous generation."""
        pass

    @abstractmethod
    async def agenerate(self, request: ModelRequest) -> ModelResponse:
        """Asynchronous generation."""
        pass

    @abstractmethod
    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        """Streaming generation."""
        pass

    @abstractmethod
    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """Async streaming generation."""
        pass

    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """Get the canonical name of this provider."""
        pass

    @staticmethod
    @abstractmethod
    def validate_config(config: ModelConfig) -> None:
        """Validate provider-specific configuration."""
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models from this provider."""
        pass

    def _log_usage(self, request: ModelRequest, response: ModelResponse) -> None:
        """Log usage metrics."""
        logger.info(
            f"Model usage: {self.config.provider}:{self.config.model_id}",
            extra={
                "provider": self.config.provider,
                "model_id": self.config.model_id,
                "usage_type": self.config.usage_type.value,
                "usage": response.usage,
                "latency": response.latency
            }
        )