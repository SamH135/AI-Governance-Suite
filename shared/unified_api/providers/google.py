"""Google provider implementation for microservices."""

import os
import time
import logging
import asyncio
import json
from typing import Dict, Any, Generator, AsyncGenerator, Optional, List

import requests
import aiohttp

from ..base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, APIErrorDetail, ModelInfo

logger = logging.getLogger(__name__)

class GoogleProvider(BaseModelProvider):
    """Google Gemini provider implementation using REST API."""

    DEFAULT_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, config: ModelConfig):
        self.session = None
        self.api_key = None
        self.api_url = None
        self.last_request_time = 0
        self.min_request_interval = 0.1
        self._config_hash = None
        super().__init__(config)

    @classmethod
    def get_provider_name(cls) -> str:
        return "google"

    def _setup(self) -> None:
        """Setup Google client."""
        # Check if we need to reinitialize due to config changes
        current_hash = hash(f"{self.config.provider}{self.config.model_id}{self.config.api_key}")
        if self._config_hash == current_hash and self.session:
            logger.debug("Using existing Google session - config unchanged")
            return

        logger.info(f"Setting up GoogleProvider for model: {self.config.model_id}")

        # Get and validate API key
        self.api_key = self._get_and_validate_api_key()
        self.api_url = self.config.api_url or self.DEFAULT_API_URL

        # Create new session
        self._create_session()

        # Update config tracking
        self._config_hash = current_hash

        logger.info(f"✅ GoogleProvider setup complete for {self.config.model_id}")

    def _get_and_validate_api_key(self) -> str:
        """Get API key from config and validate format."""
        api_key = self.config.api_key

        if not api_key:
            raise Exception("Google API key is required for Google provider")

        api_key = api_key.strip()

        logger.debug(f"✅ Google API key validated: {api_key[:10]}...{api_key[-4:]}")
        return api_key

    def _create_session(self) -> None:
        """Create a new requests session."""
        if self.session:
            self.session.close()

        self.session = requests.Session()

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

    @staticmethod
    def validate_config(config: ModelConfig) -> None:
        """Validate Google-specific configuration."""
        if not config.api_key:
            raise ValueError("api_key is required for Google provider")
        if not config.model_id:
            raise ValueError("model_id is required for Google provider")

    async def list_models(self) -> List[ModelInfo]:
        """List available models from Google API."""
        try:
            url = f"{self.DEFAULT_API_URL}"
            response = requests.get(url, headers={"x-goog-api-key": self.api_key}, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model in data.get("models", []):
                model_id = model.get("name", "").replace("models/", "")
                display_name = model.get("displayName", model_id)
                description = model.get("description", "")
                
                # Parse capabilities from supported generation methods
                capabilities = ["text-generation"]
                if "generateContent" in model.get("supportedGenerationMethods", []):
                    capabilities.append("vision")
                
                models.append(ModelInfo(
                    model_id=model_id,
                    name=display_name,
                    description=description,
                    context_window=self._get_model_context_window(model_id),
                    max_tokens=self._get_model_max_tokens(model_id),
                    capabilities=capabilities,
                    deprecated=False,
                    provider_metadata={"supported_methods": model.get("supportedGenerationMethods", [])}
                ))
            
            return models
        except Exception as e:
            logger.error(f"Failed to list Google models: {e}")
            return self._get_static_models()

    def _get_model_context_window(self, model_id: str) -> Optional[int]:
        """Get context window for Google model."""
        context_windows = {
            "gemini-1.5-pro": 1000000,
            "gemini-1.5-flash": 1000000,
            "gemini-1.0-pro": 91728,
            "gemini-pro": 91728,
        }
        return context_windows.get(model_id, 91728)

    def _get_model_max_tokens(self, model_id: str) -> Optional[int]:
        """Get max tokens for Google model."""
        max_tokens_map = {
            "gemini-1.5-pro": 8192,
            "gemini-1.5-flash": 8192,
            "gemini-1.0-pro": 8192,
            "gemini-pro": 2048,
        }
        return max_tokens_map.get(model_id, 8192)

    def _get_static_models(self) -> List[ModelInfo]:
        """Return static model list as fallback."""
        return [
            ModelInfo(
                model_id="gemini-1.5-pro",
                name="Gemini 1.5 Pro",
                description="Google's most capable multimodal model",
                context_window=1000000,
                max_tokens=8192,
                capabilities=["text-generation", "vision", "function-calling"],
                deprecated=False
            ),
            ModelInfo(
                model_id="gemini-1.5-flash",
                name="Gemini 1.5 Flash",
                description="Fast, efficient Gemini model",
                context_window=1000000,
                max_tokens=8192,
                capabilities=["text-generation", "vision"],
                deprecated=False
            ),
            ModelInfo(
                model_id="gemini-1.0-pro",
                name="Gemini 1.0 Pro",
                description="Original Gemini Pro model",
                context_window=91728,
                max_tokens=8192,
                capabilities=["text-generation", "vision"],
                deprecated=False
            )
        ]

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
        """Prepare the payload for Google Gemini API."""
        # Prepare content
        user_text = request.prompt
        if request.system_prompt:
            user_text = f"{request.system_prompt}\n\n{request.prompt}"

        contents = [{
            "role": "user",
            "parts": [{"text": user_text}]
        }]

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature if request.temperature is not None else self.config.temperature,
                "maxOutputTokens": request.max_tokens or self.config.max_tokens,
            }
        }

        # Add provider-specific options
        if self.config.provider_options:
            if 'top_p' in self.config.provider_options:
                payload["generationConfig"]["topP"] = self.config.provider_options['top_p']
            if 'top_k' in self.config.provider_options:
                payload["generationConfig"]["topK"] = self.config.provider_options['top_k']

        # Add safety settings to be more permissive for testing
        payload["safetySettings"] = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]

        return payload

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text using Google Gemini API."""
        if not self.session:
            self._setup()

        self._apply_rate_limit()
        start_time = time.time()

        payload = self._prepare_payload(request)
        url = f"{self.api_url}/{self.config.model_id}:generateContent"

        error_detail = None
        response_content = ""
        usage_data = None
        api_response = None
        response_data = None

        try:
            logger.debug(f"Making Google API request to {self.config.model_id}")

            api_response = self.session.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self.api_key},
                timeout=self.config.timeout
            )

            # Try to parse response data
            try:
                response_data = api_response.json()
            except:
                response_data = {"raw_response": api_response.text}

            # Handle specific error codes
            if api_response.status_code == 400:
                error_detail = APIErrorDetail(
                    message=f"Google API Bad Request: {response_data}",
                    type="bad_request_error",
                    code="400"
                )
                raise Exception(error_detail.message)
            elif api_response.status_code == 401:
                error_detail = APIErrorDetail(
                    message="Google API authentication failed. Check API key.",
                    type="authentication_error",
                    code="401"
                )
                raise Exception(error_detail.message)
            elif api_response.status_code == 429:
                raise Exception("Google API rate limit exceeded")

            api_response.raise_for_status()

            # Parse response
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    response_content = candidate["content"]["parts"][0]["text"]
                else:
                    response_content = str(candidate)
            else:
                error_detail = APIErrorDetail(
                    message="No candidates in Google API response",
                    type="response_parsing_error"
                )

            # Extract usage metadata
            if "usageMetadata" in response_data:
                usage_meta = response_data["usageMetadata"]
                usage_data = {
                    "input_tokens": usage_meta.get("promptTokenCount", 0),
                    "output_tokens": usage_meta.get("candidatesTokenCount", 0),
                    "total_tokens": usage_meta.get("totalTokenCount", 0)
                }

            logger.debug(f"✅ Google API request successful, tokens: {usage_data}")

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
            if not error_detail:
                error_detail = APIErrorDetail(
                    message=f"Google API error: {str(e)}",
                    type="google_api_error"
                )
            logger.exception("Error in Google provider")

        latency = time.time() - start_time

        return ModelResponse(
            content=response_content,
            model_id=self.config.model_id,
            provider="google",
            usage=usage_data,
            latency=latency,
            error=error_detail
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
                provider="google",
                error=APIErrorDetail(
                    message=f"Async execution error: {str(e)}",
                    type="async_error"
                )
            )

    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        """Streaming generation using Google's streaming API."""
        self._setup()

        try:
            url = f"{self.api_url}/{self.config.model_id}:streamGenerateContent"

            payload = {
                "contents": [{"parts": [{"text": request.prompt}]}],
                "generationConfig": {
                    "temperature": request.temperature or self.config.temperature,
                    "maxOutputTokens": request.max_tokens or self.config.max_tokens,
                }
            }

            response = self.session.post(url, json=payload, headers={"x-goog-api-key": self.api_key}, stream=True, timeout=30)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'candidates' in data and data['candidates']:
                            candidate = data['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                for part in candidate['content']['parts']:
                                    if 'text' in part:
                                        yield part['text']
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"Google streaming error: {e}")
            yield f"ERROR: {str(e)}"

    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """Async streaming generation using Google's streaming API."""
        self._setup()

        try:
            url = f"{self.api_url}/{self.config.model_id}:streamGenerateContent"

            payload = {
                "contents": [{"parts": [{"text": request.prompt}]}],
                "generationConfig": {
                    "temperature": request.temperature or self.config.temperature,
                    "maxOutputTokens": request.max_tokens or self.config.max_tokens,
                }
            }

            headers = {"x-goog-api-key": self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                if 'candidates' in data and data['candidates']:
                                    candidate = data['candidates'][0]
                                    if 'content' in candidate and 'parts' in candidate['content']:
                                        for part in candidate['content']['parts']:
                                            if 'text' in part:
                                                yield part['text']
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Google async streaming error: {e}")
            yield f"ERROR: {str(e)}"

    def __del__(self):
        """Cleanup session on deletion."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass