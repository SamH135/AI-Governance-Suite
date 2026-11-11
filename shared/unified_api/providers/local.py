"""Local/Mock provider implementation for microservices."""

import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, Generator
import logging

from ..base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, APIErrorDetail, ModelInfo
from .predetermined_responses import get_response, list_scenarios

logger = logging.getLogger(__name__)

class LocalProvider(BaseModelProvider):
    """Local provider for testing and development using pre-determined responses."""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        logger.info(f"LocalProvider initialized with model: {config.model_id}")
        logger.info(f"Available scenarios: {list_scenarios()}")

    def _setup(self) -> None:
        """No setup needed for local provider."""
        pass

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Synchronous generation using pre-determined responses."""
        try:
            full_prompt = (request.prompt or "") + (request.system_prompt or "")

            # Determine category based on prompt content
            category = "general"
            if any(term in full_prompt.lower() for term in ["compliance", "privacy", "gdpr", "hipaa", "regulation"]):
                category = "compliance"
            elif any(term in full_prompt.lower() for term in ["evaluate", "analyze", "assess"]):
                category = "evaluation"

            # Get pre-determined response
            response_data = get_response(request.prompt, category)

            # If evaluator expects JSON output, return structured JSON
            if "json" in full_prompt.lower() or "compliance_score" in full_prompt.lower():
                content = json.dumps({
                    "compliance_score": 85,
                    "compliance_status": "Compliant",
                    "violations": [],
                    "violated_regulations": [],
                    "violations_count": 0,
                    "explanation": f"Pre-determined response evaluation for: {request.prompt[:60]}...",
                    "summary": "Analysis completed using pre-determined response dataset",
                    "predetermined": True,
                    "source_response": response_data["response"][:200]
                })
            else:
                # Use pre-determined response
                content = response_data["response"]
                if request.system_prompt:
                    content = f"[SYSTEM: {request.system_prompt[:50]}...] " + content

            return ModelResponse(
                content=content,
                model_id=response_data.get("model_id", self.config.model_id),
                provider=response_data.get("provider", "local"),
                usage={"prompt_tokens": len(request.prompt.split()), "completion_tokens": len(content.split())},
                metadata={
                    "predetermined": True,
                    "scenario": category,
                    "original_model": response_data.get("model_id"),
                    "original_provider": response_data.get("provider")
                }
            )

        except Exception as e:
            logger.error(f"Local provider error: {e}")
            return ModelResponse(
                content="",
                model_id=self.config.model_id,
                provider="local",
                error=APIErrorDetail(message=str(e), type="local_provider_error")
            )

    async def agenerate(self, request: ModelRequest) -> ModelResponse:
        """Asynchronous generation for local provider."""
        # Simulate async delay
        await asyncio.sleep(0.1)
        return self.generate(request)

    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        """Streaming generation for local provider."""
        response = self.generate(request)
        words = response.content.split()
        for word in words:
            yield word + " "

    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """Async streaming generation for local provider."""
        response = await self.agenerate(request)
        words = response.content.split()
        for word in words:
            await asyncio.sleep(0.01)  # Simulate delay
            yield word + " "

    @classmethod
    def get_provider_name(cls) -> str:
        return "local"

    @staticmethod
    def validate_config(config: ModelConfig) -> None:
        """Local provider requires minimal validation."""
        if not config.model_id:
            raise ValueError("model_id is required for local provider")

    async def list_models(self) -> list:
        """List available local mock models."""
        return [
            ModelInfo(
                model_id="local-mock",
                name="Local Mock Model",
                description="Pre-determined response model for testing and development",
                context_window=4096,
                max_tokens=1000,
                capabilities=["text-generation", "evaluation", "compliance-analysis"],
                deprecated=False,
                provider_metadata={"scenarios": list_scenarios()}
            ),
            ModelInfo(
                model_id="local-mock-v2",
                name="Local Mock Model V2",
                description="Enhanced pre-determined response model with more scenarios",
                context_window=8192,
                max_tokens=2000,
                capabilities=["text-generation", "evaluation", "compliance-analysis", "rag"],
                deprecated=False,
                provider_metadata={"scenarios": list_scenarios()}
            )
        ]