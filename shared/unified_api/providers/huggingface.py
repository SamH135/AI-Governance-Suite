"""HuggingFace provider implementation for microservices."""

import os
import logging
import time
import asyncio
from typing import Dict, Any, Generator, AsyncGenerator, Optional, List

# Attempt to import transformers and torch
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM
    import torch
except ImportError:
    pipeline = None
    AutoTokenizer = None
    AutoModelForCausalLM = None
    AutoModelForSeq2SeqLM = None
    torch = None

from ..base import BaseModelProvider, ModelConfig, ModelRequest, ModelResponse, APIErrorDetail, ModelInfo

logger = logging.getLogger(__name__)


class HuggingFaceProvider(BaseModelProvider):
    """
    Provider for local Hugging Face transformer models using the `pipeline` API.
    """

    def __init__(self, config: ModelConfig):
        # Initialize instance attributes FIRST
        self.pipeline = None
        self.tokenizer = None
        self.task = None
        # THEN call super().__init__ which calls _setup() on the instance
        super().__init__(config)
        # DO NOT re-assign attributes to None here, as _setup() has populated them

    def _setup(self) -> None:
        """Load the model pipeline using transformers."""
        if not pipeline or not torch:
            raise Exception(
                "HuggingFaceProvider: 'transformers' and 'torch' libraries are required. Please install them.")

        model_id = self.config.model_id
        if not model_id:
            raise Exception("HuggingFaceProvider: 'model_id' must be specified in ModelConfig.")

        # API Key / Token for gated models
        token = self.config.api_key  # Removed environment variable fallback
        
        if not token:
            logger.info(f"No API key provided for HuggingFace model {model_id}. Using public access (may be limited for gated models).")
        else:
            logger.info(f"Using API key for HuggingFace model {model_id} (useful for gated models and higher rate limits).")

        # Device selection (GPU/CPU)
        device_option = self.config.provider_options.get("device", "auto") if self.config.provider_options else "auto"
        if device_option == "auto":
            device = 0 if torch.cuda.is_available() else -1
        elif device_option == "gpu":
            device = 0 if torch.cuda.is_available() else -1
            if device == -1:
                logger.warning("HuggingFaceProvider: GPU requested but not available, falling back to CPU.")
        elif device_option == "cpu":
            device = -1
        else:
            try:
                device = int(device_option)
            except ValueError:
                logger.warning(f"Invalid device option '{device_option}'. Defaulting to auto.")
                device = 0 if torch.cuda.is_available() else -1

        if device != -1 and not torch.cuda.is_available():
            logger.warning(f"HuggingFaceProvider: CUDA device {device} requested but CUDA not available. Using CPU.")
            device = -1

        # Quantization config
        quantization_config = self.config.provider_options.get("quantization_config") if self.config.provider_options else None
        model_kwargs = self.config.provider_options.get("model_kwargs", {}) if self.config.provider_options else {}
        if quantization_config and isinstance(quantization_config, dict):
            model_kwargs.update(quantization_config)

        # Determine the task for the pipeline
        explicit_task = self.config.provider_options.get("task") if self.config.provider_options else None
        if explicit_task:
            self.task = explicit_task
            logger.info(f"HuggingFaceProvider: Using explicitly set task '{self.task}' for model {model_id}.")
        else:
            # Existing inference logic
            if "t5" in model_id.lower() or "bart" in model_id.lower() or "pegasus" in model_id.lower():
                self.task = "text2text-generation"
            else:
                self.task = "text-generation"
            logger.info(f"HuggingFaceProvider: Task not specified, inferred as '{self.task}' for model {model_id}.")

        try:
            logger.info(f"HuggingFaceProvider: Loading model '{model_id}' for task '{self.task}' with device {device}.")

            # Load tokenizer separately for token counting
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
            except Exception as e:
                logger.warning(f"HuggingFaceProvider: Could not load tokenizer for {model_id}. Error: {e}")
                self.tokenizer = None

            # Pipeline instantiation
            self.pipeline = pipeline(
                task=self.task,
                model=model_id,
                tokenizer=self.tokenizer if self.tokenizer else model_id,
                device=device,
                token=token,
                model_kwargs=model_kwargs if model_kwargs else None,
                trust_remote_code=self.config.provider_options.get("trust_remote_code", False) if self.config.provider_options else False
            )
            if self.pipeline is None:
                logger.error(f"HuggingFaceProvider: Transformers 'pipeline()' function returned None for model {model_id} and task {self.task} during setup. This may be due to resource issues or model incompatibility.")
                raise Exception(f"HuggingFaceProvider: Pipeline creation failed as 'pipeline()' returned None for model {model_id}, task {self.task}.")
            logger.info(f"HuggingFaceProvider: Model '{model_id}' loaded successfully for task '{self.task}'.")

        except Exception as e:
            logger.error(f"HuggingFaceProvider: Failed to load model '{model_id}'. Error: {e}", exc_info=True)
            raise Exception(f"HuggingFaceProvider: Failed to load model '{model_id}'. Error: {str(e)}") from e

    @classmethod
    def get_provider_name(cls) -> str:
        return "huggingface"

    @classmethod
    def validate_config(cls, config: ModelConfig) -> None:
        if not config.model_id:
            raise ValueError("HuggingFaceProvider: 'model_id' is required in ModelConfig.")

    async def list_models(self) -> List[ModelInfo]:
        """List available models from HuggingFace.
        
        Note: This provider is for local model execution only. 
        For HuggingFace Hub model discovery, use the huggingface_hub library directly:
        
        from huggingface_hub import list_models
        models = list_models()
        
        Or specify model_id manually from https://huggingface.co/models
        """
        raise Exception(
            "HuggingFace local provider does not support model discovery. "
            "This provider runs models locally using transformers. "
            "Please specify the model_id manually from https://huggingface.co/models "
            "or use huggingface_hub.list_models() for discovery."
        )

    def _count_tokens(self, text: str) -> Optional[int]:
        if self.tokenizer and text:
            try:
                return len(self.tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"HuggingFaceProvider: Tokenizer failed to encode text for token counting: {e}")
        return None

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.pipeline:
            raise Exception(
                "HuggingFaceProvider: Pipeline not initialized. Call _setup() first or check for errors during init.")

        start_time = time.time()

        # Default pipeline arguments from ModelConfig and ModelRequest
        pipeline_args = {
            "max_length": request.max_tokens or self.config.max_tokens,
        }
        if request.temperature is not None:
            pipeline_args["temperature"] = request.temperature

        # Add any kwargs from the request
        if hasattr(request, 'kwargs') and request.kwargs:
            pipeline_args.update(request.kwargs)

        # Handle different tasks' input needs
        input_data = request.prompt
        if self.task == "text-generation":
            # text-generation often uses 'max_new_tokens' instead of 'max_length'
            if "max_length" in pipeline_args and (not self.config.provider_options or self.config.provider_options.get("use_max_new_tokens", True)):
                pipeline_args["max_new_tokens"] = pipeline_args.pop("max_length")

        # Remove None values from pipeline_args
        pipeline_args = {k: v for k, v in pipeline_args.items() if v is not None}

        logger.debug(
            f"HuggingFaceProvider: Calling pipeline for model {self.config.model_id} with args: {pipeline_args}")

        error_detail: Optional[APIErrorDetail] = None
        response_text: str = ""

        try:
            if pipeline_args:
                output = self.pipeline(input_data, **pipeline_args)
            else:
                output = self.pipeline(input_data)

            # Parse output based on pipeline task
            if isinstance(output, list) and output:
                first_result = output[0]
                if isinstance(first_result, dict):
                    if "generated_text" in first_result:
                        response_text = first_result["generated_text"]
                    elif "summary_text" in first_result:
                        response_text = first_result["summary_text"]
                    elif "translation_text" in first_result:
                        response_text = first_result["translation_text"]
                    else:
                        # Try to find any text-like key
                        for key, value in first_result.items():
                            if isinstance(value, str):
                                response_text = value
                                logger.warning(f"HuggingFaceProvider: Used generic key '{key}' for response text.")
                                break
                        if not response_text:
                            error_detail = APIErrorDetail(
                                message="HuggingFaceProvider: Could not determine output key in pipeline response.",
                                type="response_parsing_error",
                                details={"pipeline_output": output}
                            )
                elif isinstance(first_result, str):
                    response_text = first_result
                else:
                    error_detail = APIErrorDetail(
                        message=f"HuggingFaceProvider: Unexpected item type in pipeline output list: {type(first_result)}",
                        type="response_parsing_error",
                        details={"pipeline_output": output}
                    )
            elif isinstance(output, str):
                response_text = output
            else:
                error_detail = APIErrorDetail(
                    message=f"HuggingFaceProvider: Unexpected output format from pipeline: {type(output)}",
                    type="response_parsing_error",
                    details={"pipeline_output": output}
                )

            # Remove prompt from response if needed
            if (self.task == "text-generation" and
                    (not self.config.provider_options or self.config.provider_options.get("remove_prompt_from_response", True)) and
                    response_text.startswith(request.prompt)):
                response_text = response_text[len(request.prompt):].lstrip()

        except Exception as e:
            logger.error(f"HuggingFaceProvider: Error during pipeline execution for model {self.config.model_id}: {e}",
                         exc_info=True)
            error_detail = APIErrorDetail(
                message=str(e),
                type="pipeline_execution_error",
                details={"model_id": self.config.model_id, "task": self.task}
            )

        latency = time.time() - start_time

        # Token counting
        input_tokens = self._count_tokens(request.prompt)
        output_tokens = self._count_tokens(response_text)
        usage_data = {}
        if input_tokens is not None:
            usage_data["input_tokens"] = input_tokens
        if output_tokens is not None:
            usage_data["output_tokens"] = output_tokens

        return ModelResponse(
            content=response_text,
            model_id=self.config.model_id,
            provider=self.get_provider_name(),
            usage=usage_data if usage_data else None,
            metadata={"task": self.task, "latency_seconds": latency},
            error=error_detail,
            latency=latency
        )

    async def agenerate(self, request: ModelRequest) -> ModelResponse:
        logger.info("HuggingFaceProvider.agenerate is using asyncio.to_thread to run synchronous generate.")
        try:
            return await asyncio.to_thread(self.generate, request)
        except Exception as e:
            logger.error(f"HuggingFaceProvider.agenerate error: {e}", exc_info=True)
            err_detail = getattr(e, 'args_error_detail', None)
            if not isinstance(err_detail, APIErrorDetail):
                err_detail = APIErrorDetail(
                    message=f"Async execution error in HuggingFaceProvider: {str(e)}",
                    type="async_error"
                )
            return ModelResponse(
                content="",
                model_id=self.config.model_id,
                provider=self.get_provider_name(),
                error=err_detail
            )

    def stream(self, request: ModelRequest) -> Generator[str, None, None]:
        logger.warning("HuggingFaceProvider.stream is a basic implementation.")

        # Note: Streaming with local HuggingFace models often requires custom logic
        # with the model's generate() method and TextIteratorStreamer.
        # This basic implementation just runs full generation and yields chunks.
        response = self.generate(request)
        if response.error:
            yield f"ERROR: APIErrorDetail: {response.error.message}"  # Yield error message
        elif response.content:
            # Yield content in chunks to simulate streaming
            words = response.content.split(" ")
            for i, word in enumerate(words):
                if i < len(words) - 1:
                    yield word + " "
                else:
                    yield word
                time.sleep(0.01)  # Simulate stream delay
        else:
            yield ""

    async def astream(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        logger.warning("HuggingFaceProvider.astream is using asyncio.to_thread with self.stream.")
        # This will inherit the basic error reporting of self.stream
        try:
            stream_items = await asyncio.to_thread(list, self.stream(request))
            for item in stream_items:
                yield item
                await asyncio.sleep(0)  # Ensure other async tasks can run
        except Exception as e:
            logger.error(f"HuggingFaceProvider.astream error during threaded execution: {e}", exc_info=True)
            # Yielding a generic error message for async streaming issues
            yield f"ERROR: APIErrorDetail: Async streaming error: {str(e)}"