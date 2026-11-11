"""Model provider endpoints for compliance service."""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
import structlog

from shared.unified_api import get_unified_api, ModelConfig

logger = structlog.get_logger()
router = APIRouter()

@router.get("/models")
async def get_available_models():
    """Get available model providers and configuration options from unified API."""
    try:
        unified_api = get_unified_api()
        
        # Get available providers from unified API
        providers = unified_api.list_providers()
        providers_with_aliases = unified_api.get_providers_with_aliases()
        model_info = []

        for provider_name in providers:
            try:
                provider_info = unified_api.get_provider_info(provider_name)

                # Create model configuration schema based on provider
                config_schema = {
                    "provider": provider_name,
                    "model_id": {
                        "type": "string",
                        "description": f"Model ID for {provider_name}",
                        "required": True,
                        "examples": {
                            "anthropic": ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229"],
                            "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"],
                            "google": ["gemini-pro", "gemini-pro-vision"],
                            "huggingface": ["meta-llama/Llama-2-7b-chat-hf", "microsoft/DialoGPT-medium"],
                            "local": ["local-mock-model"]
                        }.get(provider_name, [f"{provider_name}-model"])
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key (if required)",
                        "sensitive": True,
                        "required": provider_name not in ["huggingface", "local"]
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature",
                        "default": 0.7,
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "default": 1000,
                        "minimum": 1
                    }
                }

                # Add the canonical provider
                model_info.append({
                    "id": provider_name,
                    "name": provider_info.get("name", provider_name),
                    "provider": provider_name,
                    "configuration_options": config_schema
                })

                # Add aliases for this provider
                aliases = providers_with_aliases.get(provider_name, [])
                for alias in aliases:
                    model_info.append({
                        "id": alias,
                        "name": provider_info.get("name", provider_name),
                        "provider": provider_name,  # Keep the canonical provider name
                        "configuration_options": config_schema
                    })

            except Exception as e:
                logger.warning(f"Failed to get info for provider {provider_name}: {e}")
                continue

        return {
            "success": True,
            "data": model_info,
            "message": f"Retrieved {len(model_info)} model configurations from {len(providers)} providers"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving models: {str(e)}"
        )

@router.post("/models/test")
async def test_model_configuration(model_config: Dict[str, Any]):
    """Test a model configuration to verify it works."""
    try:
        unified_api = get_unified_api()
        
        # Create ModelConfig from the provided configuration
        config = ModelConfig(**model_config)
        
        # Test with a simple prompt
        test_prompt = "Hello, this is a test message. Please respond briefly."
        
        response = await unified_api.agenerate(
            prompt=test_prompt,
            config=config
        )
        
        if response.error:
            return {
                "success": False,
                "data": {"error": response.error.message, "error_type": response.error.type},
                "message": "Model configuration test failed"
            }
        
        return {
            "success": True,
            "data": {
                "test_prompt": test_prompt,
                "response": response.content[:200] + "..." if len(response.content) > 200 else response.content,
                "provider": response.provider,
                "model_id": response.model_id,
                "usage": response.usage
            },
            "message": "Model configuration test successful"
        }
        
    except Exception as e:
        logger.error(f"Error testing model configuration: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Error testing model configuration: {str(e)}"
        )