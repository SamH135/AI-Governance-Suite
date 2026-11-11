"""OpenAI provider implementation for microservices."""

import os
import time
import logging
import asyncio
import json
from typing import Dict, Any, Generator, AsyncGenerator, List, Optional

# Attempt to import OpenAI library
try:
    from openai import OpenAI, AsyncOpenAI
    import openai
except ImportError:
    OpenAI = None
    AsyncOpenAI = None
    openai = None

from ..base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, APIErrorDetail, ModelInfo

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseModelProvider):
    """Provider for OpenAI's GPT models with proper error handling and session management."""

    DEFAULT_API_URL = "https://api.openai.com/v1"

    def __init__(self, config: ModelConfig):
        self.client = None
        self.async_client = None
        self.api_key = None
        self.api_url = None
        self.last_request_time = 0
        self.min_request_interval = 0.1  # OpenAI has higher rate limits
        self._config_hash = None  # Track config changes
        super().__init__(config)

    def _setup(self) -> None:
        """Initialize OpenAI client with improved error handling."""
        if not OpenAI:
            raise Exception("OpenAIProvider: 'openai' library is required. Please install it.")

        # Check if we need to reinitialize due to config changes
        current_hash = hash(f"{self.config.provider}{self.config.model_id}{self.config.api_key}")
        if self._config_hash == current_hash and self.client:
            logger.debug("Using existing OpenAI client - config unchanged")
            return

        logger.info(f"Setting up OpenAIProvider for model: {self.config.model_id}")

        # Get and validate API key
        self.api_key = self._get_and_validate_api_key()
        self.api_url = self.config.api_url or self.DEFAULT_API_URL

        # Create clients
        self._create_clients()

        # Update config tracking
        self._config_hash = current_hash

        logger.info(f"✅ OpenAIProvider setup complete for {self.config.model_id}")

    def _get_and_validate_api_key(self) -> str:
        """Get API key from config and validate format."""
        api_key = self.config.api_key

        if not api_key:
            raise Exception(
                "OpenAI API key is required. Please provide a valid API key."
            )

        if not api_key.startswith('sk-'):
            raise Exception(
                f"Invalid OpenAI API key format. Expected format: sk-..., got: {api_key[:10]}..."
            )

        return api_key

    def _create_clients(self) -> None:
        """Create OpenAI sync and async clients."""
        try:
            common_kwargs = {
                "api_key": self.api_key,
                "base_url": self.api_url,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries
            }

            self.client = OpenAI(**common_kwargs)
            self.async_client = AsyncOpenAI(**common_kwargs)
            
            logger.info(f"✅ OpenAI clients created for {self.api_url}")
        except Exception as e:
            logger.error(f"❌ Failed to create OpenAI clients: {e}")
            raise Exception(f"Failed to initialize OpenAI clients: {e}")

    @classmethod
    def get_provider_name(cls) -> str:
        return "openai"

    @classmethod
    def validate_config(cls, config: ModelConfig) -> None:
        """Validate OpenAI-specific configuration."""
        if not config.model_id:
            raise ValueError("model_id is required for OpenAIProvider.")

    async def list_models(self) -> List[ModelInfo]:
        """List available models from OpenAI API."""
        if not self.async_client:
            raise Exception("OpenAI client not initialized")
        
        try:
            response = await self.async_client.models.list()
            models = []
            
            for model in response.data:
                # Determine context window based on model ID
                context_window = self._get_model_context_window(model.id)
                max_tokens = self._get_model_max_tokens(model.id)
                
                models.append(ModelInfo(
                    model_id=model.id,
                    name=model.id,
                    description=f"OpenAI model: {model.id}",
                    context_window=context_window,
                    max_tokens=max_tokens,
                    capabilities=self._get_model_capabilities(model.id),
                    deprecated=False,
                    provider_metadata={"owned_by": model.owned_by}
                ))
            
            return models
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}")
            raise Exception(f"Failed to discover OpenAI models: {str(e)}")

    def _get_model_context_window(self, model_id: str) -> Optional[int]:
        """Get context window size for a model."""
        context_windows = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 128000,
            "gpt-4-turbo-preview": 128000,
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
        }
        return context_windows.get(model_id)

    def _get_model_max_tokens(self, model_id: str) -> Optional[int]:
        """Get max tokens for a model."""
        max_tokens_map = {
            "gpt-4": 4096,
            "gpt-4-32k": 4096,
            "gpt-4-turbo": 4096,
            "gpt-4-turbo-preview": 4096,
            "gpt-4o": 4096,
            "gpt-4o-mini": 4096,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 4096,
        }
        return max_tokens_map.get(model_id)

    def _get_model_capabilities(self, model_id: str) -> List[str]:
        """Get capabilities for a model."""
        capabilities = ["text-generation"]
        if "vision" in model_id or "gpt-4o" in model_id:
            capabilities.append("vision")
        if "turbo" in model_id or "gpt-4" in model_id:
            capabilities.append("function-calling")
        return capabilities

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _prepare_messages(self, request: ModelRequest) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI Chat Completions API."""
        messages = []

        # Add system message if provided
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })

        # Handle existing messages or create new user message
        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({
                "role": "user",
                "content": request.prompt
            })

        return messages

    def _prepare_payload(self, request: ModelRequest) -> Dict[str, Any]:
        """Prepare the payload for OpenAI API."""
        # Get effective temperature and max_tokens
        temperature = request.temperature if request.temperature is not None else self.config.temperature
        max_tokens = request.max_tokens if request.max_tokens is not None else self.config.max_tokens

        payload = {
            "model": self.config.model_id,
            "messages": self._prepare_messages(request),
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Add any provider-specific options
        if self.config.provider_options:
            payload.update(self.config.provider_options)

        logger.debug(f"OpenAI payload prepared: model={self.config.model_id}, messages={len(payload['messages'])}")
        return payload

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response using OpenAI API."""
        if not self.client:
            raise Exception("OpenAI client not initialized. Call _setup() first.")

        self._apply_rate_limit()

        payload = self._prepare_payload(request)
        start_time = time.time()

        response_content = ""
        usage_data = {}
        error_detail = None

        try:
            logger.debug(f"Making OpenAI API request to {self.config.model_id}")

            response = self.client.chat.completions.create(**payload)

            # Extract content
            if response.choices and response.choices[0].message:
                response_content = response.choices[0].message.content or ""
            else:
                error_detail = APIErrorDetail(
                    message="No content in OpenAI response",
                    type="response_parsing_error"
                )

            # Extract usage information
            if response.usage:
                usage_data = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            logger.debug(f"✅ OpenAI API request successful, tokens: {usage_data}")

        except Exception as e:
            if openai and hasattr(openai, 'AuthenticationError') and isinstance(e, openai.AuthenticationError):
                error_detail = APIErrorDetail(
                    message="OpenAI authentication failed. Check API key.",
                    type="authentication_error",
                    code="401"
                )
            elif openai and hasattr(openai, 'RateLimitError') and isinstance(e, openai.RateLimitError):
                error_detail = APIErrorDetail(
                    message="OpenAI API rate limit exceeded",
                    type="rate_limit_error",
                    code="429"
                )
            elif openai and hasattr(openai, 'APIConnectionError') and isinstance(e, openai.APIConnectionError):
                error_detail = APIErrorDetail(
                    message=f"OpenAI API connection failed: {str(e)}",
                    type="connection_error"
                )
            elif openai and hasattr(openai, 'APIStatusError') and isinstance(e, openai.APIStatusError):
                error_detail = APIErrorDetail(
                    message=f"OpenAI API error: {e.message if hasattr(e, 'message') else str(e)}",
                    type="api_error",
                    code=str(e.status_code) if hasattr(e, 'status_code') else None
                )
            else:
                error_detail = APIErrorDetail(
                    message=f"OpenAI error: {str(e)}",
                    type="unexpected_error"
                )
                logger.exception("Unexpected error in OpenAI provider")

        latency = time.time() - start_time

        return ModelResponse(
            content=response_content,
            model_id=self.config.model_id,
            provider=self.get_provider_name(),
            usage=usage_data,
            metadata={"latency_seconds": latency},
            error=error_detail,
            latency=latency
        )

    async def agenerate(self, request: ModelRequest) -> ModelResponse:
        """Async version using OpenAI async client."""
        if not self.async_client:
            raise Exception("OpenAI async client not initialized. Call _setup() first.")

        payload = self._prepare_payload(request)
        start_time = time.time()

        response_content = ""
        usage_data = {}
        error_detail = None

        try:
            logger.debug(f"Making async OpenAI API request to {self.config.model_id}")

            response = await self.async_client.chat.completions.create(**payload)

            # Extract content
            if response.choices and response.choices[0].message:
                response_content = response.choices[0].message.content or ""
            else:
                error_detail = APIErrorDetail(
                    message="No content in OpenAI response",
                    type="response_parsing_error"
                )

            # Extract usage information
            if response.usage:
                usage_data = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            logger.debug(f"✅ Async OpenAI API request successful, tokens: {usage_data}")

        except Exception as e:
            if openai and hasattr(openai, 'AuthenticationError') and isinstance(e, openai.AuthenticationError):
                error_detail = APIErrorDetail(
                    message="OpenAI authentication failed. Check API key.",
                    type="authentication_error",
                    code="401"
                )
            elif openai and hasattr(openai, 'RateLimitError') and isinstance(e, openai.RateLimitError):
                error_detail = APIErrorDetail(
                    message="OpenAI API rate limit exceeded",
                    type="rate_limit_error",
                    code="429"
                )
            elif openai and hasattr(openai, 'APIConnectionError') and isinstance(e, openai.APIConnectionError):
                error_detail = APIErrorDetail(
                    message=f"OpenAI API connection failed: {str(e)}",
                    type="connection_error"
                )
            elif openai and hasattr(openai, 'APIStatusError') and isinstance(e, openai.APIStatusError):
                error_detail = APIErrorDetail(
                    message=f"OpenAI API error: {e.message if hasattr(e, 'message') else str(e)}",
                    type="api_error",
                    code=str(e.status_code) if hasattr(e, 'status_code') else None
                )
            else:
                error_detail = APIErrorDetail(
                    message=f"Async OpenAI error: {str(e)}",
                    type="unexpected_error"
                )
                logger.exception("Unexpected error in async OpenAI provider")

        latency = time.time() - start_time

        return ModelResponse(
            content=response_content,
            model_id=self.config.model_id,
            provider=self.get_provider_name(),
            usage=usage_data,
            metadata={"latency_seconds": latency},
            error=error_detail,
            latency=latency
        )

    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        """Streaming generation for OpenAI."""
        if not self.client:
            raise Exception("OpenAI client not initialized. Call _setup() first.")

        payload = self._prepare_payload(request)
        payload["stream"] = True

        try:
            logger.debug(f"Starting OpenAI streaming for {self.config.model_id}")

            stream = self.client.chat.completions.create(**payload)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield f"ERROR: {str(e)}"

    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """Async streaming generation for OpenAI."""
        if not self.async_client:
            raise Exception("OpenAI async client not initialized. Call _setup() first.")

        payload = self._prepare_payload(request)
        payload["stream"] = True

        try:
            logger.debug(f"Starting async OpenAI streaming for {self.config.model_id}")

            stream = await self.async_client.chat.completions.create(**payload)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Async OpenAI streaming error: {e}")
            yield f"ERROR: {str(e)}"

    def __del__(self):
        """Cleanup clients on deletion."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        if self.async_client:
            try:
                asyncio.create_task(self.async_client.close())
            except Exception:
                pass