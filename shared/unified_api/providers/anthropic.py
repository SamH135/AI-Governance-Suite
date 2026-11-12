"""Anthropic provider implementation for microservices."""

import os
import time
import logging
import asyncio
import json
from typing import Dict, Any, Generator, AsyncGenerator, List, Optional

import requests

from ..base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, APIErrorDetail, ModelInfo

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseModelProvider):
    """Provider for Anthropic's Claude models with improved session management and detailed logging."""

    DEFAULT_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, config: ModelConfig):
        self.session = None
        self.api_key = None
        self.api_url = None
        self.last_request_time = 0
        self.min_request_interval = 0.5
        self._config_hash = None  # Track config changes
        super().__init__(config)

    def _setup(self) -> None:
        """Initialize Anthropic client with improved error handling."""
        # Check if we need to reinitialize due to config changes
        current_hash = hash(f"{self.config.provider}{self.config.model_id}{self.config.api_key}")
        if self._config_hash == current_hash and self.session:
            logger.debug("Using existing session - config unchanged")
            return

        logger.info(f"Setting up AnthropicProvider for model: {self.config.model_id}")

        # Get and validate API key
        self.api_key = self._get_and_validate_api_key()
        self.api_url = self.config.api_url or self.DEFAULT_API_URL

        # Create new session
        self._create_session()

        # Update config tracking
        self._config_hash = current_hash

        logger.info(f"✅ AnthropicProvider setup complete for {self.config.model_id}")

    def _get_and_validate_api_key(self) -> str:
        """Get API key from config and validate format."""
        api_key = self.config.api_key

        if not api_key:
            raise Exception(
                "Anthropic API key not found. Please provide api_key in the request."
            )

        api_key = api_key.strip()

        # Basic validation - ensure it looks like an API key
        if not api_key.startswith('sk-'):
            raise Exception(
                "Invalid Anthropic API key format. Key should start with 'sk-'"
            )

        if len(api_key) < 20:
            raise Exception(
                "Invalid Anthropic API key format. Key appears to be too short."
            )

        # Accept multiple Anthropic key formats
        if api_key.startswith('sk-ant-'):
            logger.debug("✅ Standard Anthropic API key format detected")
        elif api_key.startswith('sk-a'):
            logger.debug("✅ Anthropic API key format detected (sk-a prefix)")
        else:
            # Still allow it but log a warning
            logger.warning(f"⚠️ Unusual API key format: {api_key[:6]}... - attempting to use anyway")

        logger.debug(f"✅ API key validated: {api_key[:10]}...{api_key[-4:]}")
        return api_key

    def _create_session(self) -> None:
        """Create a new requests session with proper headers."""
        if self.session:
            self.session.close()

        self.session = requests.Session()
        self.session.headers.update({
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key
        })

        # Configure retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    @classmethod
    def get_provider_name(cls) -> str:
        return "anthropic"

    @classmethod
    def validate_config(cls, config: ModelConfig) -> None:
        """Validate Anthropic-specific configuration."""
        if not config.model_id:
            raise ValueError("model_id is required for AnthropicProvider.")

    async def list_models(self) -> List[ModelInfo]:
        """List available models from Anthropic API.
        
        Note: Anthropic does not provide a public models endpoint.
        Users must specify model_id manually. See Anthropic documentation for current models:
        https://docs.anthropic.com/en/docs/about-claude/models
        """
        raise Exception(
            "Anthropic does not provide a public models API endpoint. "
            "Please specify the model_id manually in your request. "
            "For available models, see: https://docs.anthropic.com/en/docs/about-claude/models"
        )

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _prepare_payload(self, request: ModelRequest) -> Dict[str, Any]:
        """Prepare the JSON payload for the Anthropic API."""
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens or self.config.max_tokens,
            "temperature": request.temperature if request.temperature is not None else self.config.temperature,
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        if request.tools:
            payload["tools"] = [{
                "name": t.get("name"),
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            } for t in request.tools]

        # Add any additional kwargs
        if hasattr(request, 'kwargs') and request.kwargs:
            payload.update(request.kwargs)

        return payload

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response from Claude with detailed logging."""
        if not self.session:
            self._setup()

        self._apply_rate_limit()
        start_time = time.time()

        payload = self._prepare_payload(request)
        error_detail: Optional[APIErrorDetail] = None
        response_content: str = ""
        usage_data: Optional[Dict[str, int]] = None
        api_response = None
        response_data = None
        tool_calls = None

        try:
            logger.debug(f"Making request to {self.api_url}")

            api_response = self.session.post(
                self.api_url,
                json=payload,
                timeout=self.config.timeout
            )

            # Try to parse response data for logging
            try:
                response_data = api_response.json()
            except:
                response_data = {"raw_response": api_response.text}

            # Handle specific error codes
            if api_response.status_code == 401:
                error_detail = APIErrorDetail(
                    message="Authentication failed. Check API key.",
                    type="authentication_error",
                    code="401"
                )
                raise Exception(error_detail.message)
            elif api_response.status_code == 429:
                raise Exception("Anthropic API rate limit exceeded")

            api_response.raise_for_status()

            # Parse response
            if response_data.get("type") == "error":
                err_data = response_data.get("error", {})
                error_detail = APIErrorDetail(
                    message=err_data.get("message", "Unknown API error"),
                    type=err_data.get("type", "api_error"),
                    code=str(api_response.status_code)
                )
            elif response_data.get("content") and isinstance(response_data["content"], list):
                texts, calls = [], []
                for block in response_data["content"]:
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        calls.append({"name": block.get("name"), "arguments": block.get("input", {})})
                response_content = "".join(texts)
                tool_calls = calls or None
                usage_data = response_data.get("usage")
            else:
                error_detail = APIErrorDetail(
                    message="Unexpected response structure from Anthropic API",
                    type="response_parsing_error"
                )

        except requests.exceptions.Timeout:
            error_detail = APIErrorDetail(
                message=f"Request timeout after {self.config.timeout}s",
                type="timeout_error",
                code="TIMEOUT"
            )
            raise Exception(error_detail.message)
        except requests.exceptions.RequestException as e:
            error_detail = APIErrorDetail(
                message=f"Request failed: {str(e)}",
                type="request_error"
            )
            raise Exception(error_detail.message) from e
        except Exception as e:
            error_detail = APIErrorDetail(
                message=f"Unexpected error: {str(e)}",
                type="unexpected_error"
            )
            logger.exception("Unexpected error in Anthropic provider")

        latency = time.time() - start_time

        return ModelResponse(
            content=response_content,
            model_id=self.config.model_id,
            provider=self.get_provider_name(),
            tool_calls=tool_calls,
            usage=usage_data,
            metadata={"latency_seconds": latency},
            error=error_detail,
            latency=latency
        )

    async def agenerate(self, request: ModelRequest) -> ModelResponse:
        """Async version using asyncio.to_thread."""
        try:
            return await asyncio.to_thread(self.generate, request)
        except Exception as e:
            logger.error(f"Async generate error: {e}")
            return ModelResponse(
                content="",
                model_id=self.config.model_id,
                provider=self.get_provider_name(),
                error=APIErrorDetail(
                    message=f"Async execution error: {str(e)}",
                    type="async_error"
                )
            )

    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        """Streaming generation using Anthropic's streaming API."""
        self._setup()

        try:
            payload = {
                "model": self.config.model_id,
                "max_tokens": request.max_tokens or self.config.max_tokens,
                "messages": [{"role": "user", "content": request.prompt}],
                "stream": True
            }

            if request.temperature is not None:
                payload["temperature"] = request.temperature
            elif self.config.temperature is not None:
                payload["temperature"] = self.config.temperature

            response = self.session.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=30
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            if 'type' in data and data['type'] == 'content_block_delta':
                                if 'delta' in data and 'text' in data['delta']:
                                    yield data['delta']['text']
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            yield f"ERROR: {str(e)}"

    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """Async streaming generation using Anthropic's streaming API."""
        self._setup()

        try:
            import aiohttp

            payload = {
                "model": self.config.model_id,
                "max_tokens": request.max_tokens or self.config.max_tokens,
                "messages": [{"role": "user", "content": request.prompt}],
                "stream": True
            }

            if request.temperature is not None:
                payload["temperature"] = request.temperature
            elif self.config.temperature is not None:
                payload["temperature"] = self.config.temperature

            headers = {
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "x-api-key": self.api_key
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()

                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if 'type' in data and data['type'] == 'content_block_delta':
                                        if 'delta' in data and 'text' in data['delta']:
                                            yield data['delta']['text']
                                except json.JSONDecodeError:
                                    continue

        except Exception as e:
            logger.error(f"Anthropic async streaming error: {e}")
            yield f"ERROR: {str(e)}"

    def __del__(self):
        """Cleanup session on deletion."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass