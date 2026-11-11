"""
AI Model Configuration Service
Handles CRUD operations for AI model configurations and integration with Unified AI API
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field, validator
from enum import Enum

# Import Unified API components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../shared'))
from unified_api.api import get_unified_api
from unified_api.base import ModelConfig, ModelRequest, ModelType

logger = logging.getLogger(__name__)

class ProviderType(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"

class UsageType(str, Enum):
    TEST_SUBJECT = "test_subject"
    EVALUATOR = "evaluator"
    RAG = "rag"
    UTILITY = "utility"

class AIModelConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    provider: ProviderType
    model_id: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[str] = None  # For backward compatibility and testing
    api_key_id: Optional[str] = None  # Reference to managed API key
    api_url: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, gt=0)
    timeout: int = Field(default=30, gt=0)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, ge=0.0)
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    usage_type: UsageType = Field(default=UsageType.UTILITY)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)

    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return [tag.strip() for tag in v if tag.strip()]

class AIModelConfigResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    provider: str
    model_id: str
    api_key: Optional[str] = None  # Never return actual API key
    api_key_id: Optional[str] = None  # Reference to managed API key
    api_url: Optional[str]
    temperature: float
    max_tokens: int
    timeout: int
    max_retries: int
    retry_delay: float
    provider_options: Dict[str, Any]
    usage_type: str
    metadata: Dict[str, Any]
    tags: List[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]

    @validator('api_key', always=True)
    def mask_api_key(cls, v):
        # Never expose actual API keys, return masked version if exists
        return "***masked***" if v else None

class ModelTestRequest(BaseModel):
    prompt: str = Field(default="Hello, please respond with 'Test successful' to confirm the model is working.")
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class ModelTestResponse(BaseModel):
    success: bool
    response_content: Optional[str]
    response_time_ms: Optional[int]
    tokens_used: Optional[Dict[str, int]]
    error_message: Optional[str]
    test_metadata: Dict[str, Any]

class ModelsService:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.unified_api = get_unified_api()

    async def get_models(self, user_id: int) -> List[AIModelConfigResponse]:
        """Get all AI model configurations for a user"""
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT config_id, name, description, provider, model_id, 
                           CASE WHEN api_key IS NOT NULL OR api_key_id IS NOT NULL THEN 'has_key' ELSE NULL END as api_key,
                           api_key_id, api_url, temperature, max_tokens, timeout, max_retries, retry_delay,
                           provider_options, usage_type, metadata, tags, enabled,
                           created_at, updated_at, created_by
                    FROM ai_model_configs 
                    WHERE created_by = $1 
                    ORDER BY created_at DESC
                """
                rows = await conn.fetch(query, user_id)
                
                models = []
                for row in rows:
                    model_data = dict(row)
                    model_data['id'] = model_data.pop('config_id')
                    models.append(AIModelConfigResponse(**model_data))
                
                logger.info(f"Retrieved {len(models)} model configurations for user {user_id}")
                return models
                
        except Exception as e:
            logger.error(f"Failed to get model configurations for user {user_id}: {e}")
            raise

    async def get_model(self, config_id: int, user_id: int) -> Optional[AIModelConfigResponse]:
        """Get a specific AI model configuration"""
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT config_id, name, description, provider, model_id, 
                           CASE WHEN api_key IS NOT NULL OR api_key_id IS NOT NULL THEN 'has_key' ELSE NULL END as api_key,
                           api_key_id, api_url, temperature, max_tokens, timeout, max_retries, retry_delay,
                           provider_options, usage_type, metadata, tags, enabled,
                           created_at, updated_at, created_by
                    FROM ai_model_configs 
                    WHERE config_id = $1 AND created_by = $2
                """
                row = await conn.fetchrow(query, config_id, user_id)
                
                if not row:
                    return None
                
                model_data = dict(row)
                model_data['id'] = model_data.pop('config_id')
                return AIModelConfigResponse(**model_data)
                
        except Exception as e:
            logger.error(f"Failed to get model configuration {config_id} for user {user_id}: {e}")
            raise

    async def create_model(self, model_request: AIModelConfigRequest, user_id: int) -> AIModelConfigResponse:
        """Create a new AI model configuration"""
        try:
            async with self.db_pool.acquire() as conn:
                # Check for duplicate name
                existing = await conn.fetchrow(
                    "SELECT config_id FROM ai_model_configs WHERE name = $1 AND created_by = $2",
                    model_request.name, user_id
                )
                if existing:
                    raise ValueError(f"Model configuration with name '{model_request.name}' already exists")
                
                query = """
                    INSERT INTO ai_model_configs (
                        name, description, provider, model_id, api_key, api_url,
                        temperature, max_tokens, timeout, max_retries, retry_delay,
                        provider_options, usage_type, metadata, tags, enabled, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    RETURNING config_id, created_at, updated_at
                """
                
                row = await conn.fetchrow(
                    query,
                    model_request.name,
                    model_request.description,
                    model_request.provider.value,
                    model_request.model_id,
                    model_request.api_key,  # Store encrypted in production
                    model_request.api_url,
                    model_request.temperature,
                    model_request.max_tokens,
                    model_request.timeout,
                    model_request.max_retries,
                    model_request.retry_delay,
                    json.dumps(model_request.provider_options),
                    model_request.usage_type.value,
                    json.dumps(model_request.metadata),
                    model_request.tags,
                    model_request.enabled,
                    user_id
                )
                
                # Return the created model
                return AIModelConfigResponse(
                    id=row['config_id'],
                    name=model_request.name,
                    description=model_request.description,
                    provider=model_request.provider.value,
                    model_id=model_request.model_id,
                    api_key="***masked***" if model_request.api_key else None,
                    api_url=model_request.api_url,
                    temperature=model_request.temperature,
                    max_tokens=model_request.max_tokens,
                    timeout=model_request.timeout,
                    max_retries=model_request.max_retries,
                    retry_delay=model_request.retry_delay,
                    provider_options=model_request.provider_options,
                    usage_type=model_request.usage_type.value,
                    metadata=model_request.metadata,
                    tags=model_request.tags,
                    enabled=model_request.enabled,
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    created_by=user_id
                )
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create model configuration for user {user_id}: {e}")
            raise

    async def update_model(self, config_id: int, model_request: AIModelConfigRequest, user_id: int) -> Optional[AIModelConfigResponse]:
        """Update an AI model configuration"""
        try:
            async with self.db_pool.acquire() as conn:
                # Check if model exists and belongs to user
                existing = await conn.fetchrow(
                    "SELECT config_id FROM ai_model_configs WHERE config_id = $1 AND created_by = $2",
                    config_id, user_id
                )
                if not existing:
                    return None
                
                # Check for duplicate name (excluding current record)
                duplicate = await conn.fetchrow(
                    "SELECT config_id FROM ai_model_configs WHERE name = $1 AND created_by = $2 AND config_id != $3",
                    model_request.name, user_id, config_id
                )
                if duplicate:
                    raise ValueError(f"Model configuration with name '{model_request.name}' already exists")
                
                query = """
                    UPDATE ai_model_configs SET
                        name = $1, description = $2, provider = $3, model_id = $4,
                        api_key = $5, api_url = $6, temperature = $7, max_tokens = $8,
                        timeout = $9, max_retries = $10, retry_delay = $11,
                        provider_options = $12, usage_type = $13, metadata = $14,
                        tags = $15, enabled = $16, updated_at = CURRENT_TIMESTAMP
                    WHERE config_id = $17 AND created_by = $18
                    RETURNING updated_at
                """
                
                row = await conn.fetchrow(
                    query,
                    model_request.name,
                    model_request.description,
                    model_request.provider.value,
                    model_request.model_id,
                    model_request.api_key,  # Store encrypted in production
                    model_request.api_url,
                    model_request.temperature,
                    model_request.max_tokens,
                    model_request.timeout,
                    model_request.max_retries,
                    model_request.retry_delay,
                    json.dumps(model_request.provider_options),
                    model_request.usage_type.value,
                    json.dumps(model_request.metadata),
                    model_request.tags,
                    model_request.enabled,
                    config_id,
                    user_id
                )
                
                if not row:
                    return None
                
                # Return the updated model
                return await self.get_model(config_id, user_id)
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update model configuration {config_id} for user {user_id}: {e}")
            raise

    async def delete_model(self, config_id: int, user_id: int) -> bool:
        """Delete an AI model configuration"""
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM ai_model_configs WHERE config_id = $1 AND created_by = $2",
                    config_id, user_id
                )
                
                deleted_count = int(result.split()[-1])
                logger.info(f"Deleted model configuration {config_id} for user {user_id}: {deleted_count > 0}")
                return deleted_count > 0
                
        except Exception as e:
            logger.error(f"Failed to delete model configuration {config_id} for user {user_id}: {e}")
            raise

    async def test_model(self, config_or_request: Any, user_id: int) -> ModelTestResponse:
        """Test an AI model configuration"""
        start_time = datetime.now()
        
        try:
            # Handle both stored config ID and direct config data
            if isinstance(config_or_request, dict) and 'id' in config_or_request:
                # Testing existing stored configuration
                config_id = config_or_request['id']
                stored_config = await self.get_model(config_id, user_id)
                if not stored_config:
                    raise ValueError(f"Model configuration {config_id} not found")
                
                # Get actual API key for testing
                actual_api_key = None
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT api_key, api_key_id, provider FROM ai_model_configs WHERE config_id = $1 AND created_by = $2",
                        config_id, user_id
                    )
                    if row:
                        if row['api_key_id']:
                            # Try to retrieve from API key manager if available
                            try:
                                from api_key_manager import api_key_manager, APIKeyProvider
                                provider_enum = APIKeyProvider(row['provider'])
                                actual_api_key = await api_key_manager.get_api_key(user_id, provider_enum)
                                if not actual_api_key:
                                    raise ValueError(f"Managed API key {row['api_key_id']} not found or expired")
                            except ImportError:
                                logger.warning("API key manager not available, falling back to direct key storage")
                                actual_api_key = row['api_key']
                            except Exception as e:
                                logger.error(f"Failed to retrieve managed API key: {e}")
                                # Fall back to direct storage if available
                                actual_api_key = row['api_key']
                                if not actual_api_key:
                                    raise ValueError(f"Failed to retrieve API key for testing: {e}")
                        elif row['api_key']:
                            # Use directly stored API key
                            actual_api_key = row['api_key']
                        else:
                            raise ValueError("No API key configured for this model")
                
                # Create ModelConfig for Unified API
                model_config = ModelConfig(
                    provider=stored_config.provider,
                    model_id=stored_config.model_id,
                    api_key=actual_api_key,
                    api_url=stored_config.api_url,
                    temperature=stored_config.temperature,
                    max_tokens=stored_config.max_tokens,
                    timeout=stored_config.timeout,
                    max_retries=stored_config.max_retries,
                    retry_delay=stored_config.retry_delay,
                    provider_options=stored_config.provider_options,
                    usage_type=ModelType(stored_config.usage_type),
                    metadata=stored_config.metadata
                )
                test_request = ModelTestRequest()
                
            else:
                # Testing new configuration data
                if isinstance(config_or_request, dict):
                    config_data = config_or_request
                    test_request = ModelTestRequest()
                else:
                    # Assume it's a test request with embedded config
                    config_data = config_or_request
                    test_request = ModelTestRequest(
                        prompt=getattr(config_or_request, 'prompt', "Hello, please respond with 'Test successful' to confirm the model is working."),
                        system_prompt=getattr(config_or_request, 'system_prompt', None),
                        temperature=getattr(config_or_request, 'temperature', None),
                        max_tokens=getattr(config_or_request, 'max_tokens', None)
                    )
                
                # Create ModelConfig from request data
                model_config = ModelConfig(
                    provider=config_data.get('provider'),
                    model_id=config_data.get('model_id'),
                    api_key=config_data.get('api_key'),
                    api_url=config_data.get('api_url'),
                    temperature=config_data.get('temperature', 0.7),
                    max_tokens=config_data.get('max_tokens', 1000),
                    timeout=config_data.get('timeout', 30),
                    max_retries=config_data.get('max_retries', 3),
                    retry_delay=config_data.get('retry_delay', 1.0),
                    provider_options=config_data.get('provider_options', {}),
                    usage_type=ModelType(config_data.get('usage_type', 'utility')),
                    metadata=config_data.get('metadata', {})
                )
                config_id = None
            
            # Test the model using Unified API
            try:
                response = self.unified_api.generate(
                    prompt=test_request.prompt,
                    config=model_config,
                    system_prompt=test_request.system_prompt,
                    temperature=test_request.temperature,
                    max_tokens=test_request.max_tokens
                )
                
                end_time = datetime.now()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                success = response.error is None
                error_message = response.error.message if response.error else None
                
                test_result = ModelTestResponse(
                    success=success,
                    response_content=response.content if success else None,
                    response_time_ms=response_time_ms,
                    tokens_used=response.usage,
                    error_message=error_message,
                    test_metadata={
                        'model_id': response.model_id,
                        'provider': response.provider,
                        'latency': response.latency,
                        'test_timestamp': datetime.now().isoformat()
                    }
                )
                
                # Store test result if we have a config_id
                if config_id:
                    await self._store_test_result(config_id, test_request, test_result, user_id)
                
                logger.info(f"Model test completed for user {user_id}: success={success}")
                return test_result
                
            except Exception as api_error:
                end_time = datetime.now()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                test_result = ModelTestResponse(
                    success=False,
                    response_content=None,
                    response_time_ms=response_time_ms,
                    tokens_used=None,
                    error_message=str(api_error),
                    test_metadata={
                        'test_timestamp': datetime.now().isoformat(),
                        'error_type': type(api_error).__name__
                    }
                )
                
                # Store test result if we have a config_id
                if config_id:
                    await self._store_test_result(config_id, test_request, test_result, user_id)
                
                logger.error(f"Model test failed for user {user_id}: {api_error}")
                return test_result
                
        except Exception as e:
            logger.error(f"Failed to test model for user {user_id}: {e}")
            return ModelTestResponse(
                success=False,
                response_content=None,
                response_time_ms=None,
                tokens_used=None,
                error_message=str(e),
                test_metadata={'test_timestamp': datetime.now().isoformat()}
            )

    async def _store_test_result(self, config_id: int, test_request: ModelTestRequest, 
                                test_result: ModelTestResponse, user_id: int):
        """Store test result in database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ai_model_test_results (
                        config_id, test_prompt, response_content, response_time_ms,
                        tokens_used, error_message, success, test_metadata, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, 
                config_id, test_request.prompt, test_result.response_content,
                test_result.response_time_ms, json.dumps(test_result.tokens_used) if test_result.tokens_used else None,
                test_result.error_message, test_result.success, json.dumps(test_result.test_metadata), user_id)
        except Exception as e:
            logger.error(f"Failed to store test result: {e}")

    async def get_providers(self) -> List[Dict[str, Any]]:
        """Get available AI providers from Unified API"""
        try:
            providers = self.unified_api.list_providers()
            provider_info = []
            
            for provider_name in providers:
                try:
                    info = self.unified_api.get_provider_info(provider_name)
                    provider_info.append({
                        'name': provider_name,
                        'display_name': provider_name.title(),
                        'class': info.get('class'),
                        'description': info.get('doc', f'{provider_name.title()} AI provider')
                    })
                except Exception as e:
                    logger.warning(f"Failed to get info for provider {provider_name}: {e}")
                    provider_info.append({
                        'name': provider_name,
                        'display_name': provider_name.title(),
                        'description': f'{provider_name.title()} AI provider'
                    })
            
            logger.info(f"Retrieved {len(provider_info)} available providers")
            return provider_info
            
        except Exception as e:
            logger.error(f"Failed to get providers: {e}")
            # Return default providers as fallback
            return [
                {'name': 'openai', 'display_name': 'OpenAI', 'description': 'OpenAI GPT models'},
                {'name': 'google', 'display_name': 'Google', 'description': 'Google Gemini models'},
                {'name': 'anthropic', 'display_name': 'Anthropic', 'description': 'Anthropic Claude models'},
                {'name': 'local', 'display_name': 'Local', 'description': 'Local/self-hosted models'}
            ]