"""
AI Model Configuration Service
Handles CRUD operations for AI model configurations and integration with Unified AI API
"""

import logging
import json
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field, validator
from enum import Enum

logger = logging.getLogger(__name__)

# Import Simple API Key Service
from .simple_api_key_service import SimpleAPIKeyService, APIKeyProvider
API_KEY_MANAGER_AVAILABLE = True
logger.info("Using simple API key service for gateway")

# Import Unified API components

# Flag to track if unified API is available
UNIFIED_API_AVAILABLE = False

try:
    # Try multiple paths for the shared directory
    possible_paths = [
        '/app/shared',  # Docker mount path
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../shared')),  # Relative path
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../shared'))  # Alternative relative
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added shared path: {path}")
    
    from unified_api.api import get_unified_api
    from unified_api.base import ModelConfig, ModelRequest, ModelType
    UNIFIED_API_AVAILABLE = True
    logger.info("Successfully imported Unified API components")
except ImportError as e:
    logger.error(f"Failed to import unified API components: {e}")
    raise ImportError(f"Unified AI API is required but failed to import: {e}")

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
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
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
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
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
        
        # Initialize simple API key service
        self.api_key_service = SimpleAPIKeyService(db_pool)
        
        # Verify Unified API is working
        if not UNIFIED_API_AVAILABLE:
            raise RuntimeError("Unified AI API is not available")
        
        # Test that we can list providers
        providers = self.unified_api.list_providers()
        logger.info(f"Unified API initialized with providers: {providers}")

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
                    # Parse JSON strings back to dictionaries
                    if isinstance(model_data.get('provider_options'), str):
                        model_data['provider_options'] = json.loads(model_data['provider_options'])
                    if isinstance(model_data.get('metadata'), str):
                        model_data['metadata'] = json.loads(model_data['metadata'])
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
                # Parse JSON strings back to dictionaries
                if isinstance(model_data.get('provider_options'), str):
                    model_data['provider_options'] = json.loads(model_data['provider_options'])
                if isinstance(model_data.get('metadata'), str):
                    model_data['metadata'] = json.loads(model_data['metadata'])
                return AIModelConfigResponse(**model_data)
                
        except Exception as e:
            logger.error(f"Failed to get model configuration {config_id} for user {user_id}: {e}")
            raise

    async def create_model(self, model_request: AIModelConfigRequest, user_id: int) -> AIModelConfigResponse:
        """Create a new AI model configuration"""
        try:
            # Handle API key management
            api_key_id = None
            stored_api_key = None
            
            if model_request.api_key and API_KEY_MANAGER_AVAILABLE:
                # Use API key manager to store the key securely
                try:
                    provider_enum = APIKeyProvider(model_request.provider.value)
                    key_result = await self.api_key_service.create_user_api_key(
                        user_id=user_id,
                        provider=provider_enum.value,
                        key_value=model_request.api_key,
                        name=f"{model_request.name} API Key"
                    )
                    api_key_id = key_result['key_id']
                    logger.info(f"Created managed API key {api_key_id} for model configuration")
                except Exception as e:
                    logger.warning(f"Failed to create managed API key: {e}. Storing directly in model config.")
                    stored_api_key = model_request.api_key
            elif model_request.api_key:
                # Fallback to storing directly in model config
                stored_api_key = model_request.api_key
            elif model_request.api_key_id:
                # Use existing managed API key
                api_key_id = model_request.api_key_id
            
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
                        name, description, provider, model_id, api_key, api_key_id, api_url,
                        temperature, max_tokens, timeout, max_retries, retry_delay,
                        provider_options, usage_type, metadata, tags, enabled, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    RETURNING config_id, created_at, updated_at
                """
                
                row = await conn.fetchrow(
                    query,
                    model_request.name,
                    model_request.description,
                    model_request.provider.value,
                    model_request.model_id,
                    stored_api_key,  # Store directly only if API key manager failed
                    api_key_id,  # Reference to managed API key
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
                    api_key="***masked***" if (model_request.api_key or api_key_id) else None,
                    api_key_id=api_key_id,
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
                        if row['api_key_id'] and API_KEY_MANAGER_AVAILABLE:
                            # Retrieve from API key manager
                            try:
                                provider_enum = APIKeyProvider(row['provider'])
                                actual_api_key = await self.api_key_service.get_api_key_value(user_id, row['api_key_id'])
                                if not actual_api_key:
                                    raise ValueError(f"Managed API key {row['api_key_id']} not found or expired")
                            except Exception as e:
                                logger.error(f"Failed to retrieve managed API key: {e}")
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

    async def get_provider_models(self, provider_name: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get available models from a provider, with caching"""
        try:
            # Check cache age (24 hours)
            cache_ttl_hours = 24
            
            async with self.db_pool.acquire() as conn:
                # Check if provider exists in provider_configs
                provider_query = """
                    SELECT provider_id FROM provider_configs WHERE name = $1
                """
                provider_row = await conn.fetchrow(provider_query, provider_name)
                
                if not provider_row:
                    logger.warning(f"Provider {provider_name} not found in provider_configs")
                    # Fallback to unified API discovery
                    return await self._discover_models_from_provider(provider_name)
                
                provider_id = provider_row['provider_id']
                
                # Check if we need to refresh
                if not force_refresh:
                    cache_check_query = """
                        SELECT COUNT(*) as count
                        FROM provider_models
                        WHERE provider_id = $1
                        AND last_updated > NOW() - INTERVAL '1 hour' * $2
                    """
                    cache_row = await conn.fetchrow(cache_check_query, provider_id, cache_ttl_hours)
                    
                    if cache_row and cache_row['count'] > 0:
                        # Return cached models
                        models_query = """
                            SELECT provider_model_id, name, description, context_window, max_tokens,
                                   capabilities, deprecated, provider_metadata
                            FROM provider_models
                            WHERE provider_id = $1 AND NOT deprecated
                            ORDER BY name
                        """
                        model_rows = await conn.fetch(models_query, provider_id)
                        
                        models = []
                        for row in model_rows:
                            models.append({
                                'model_id': row['provider_model_id'],
                                'name': row['name'],
                                'description': row['description'],
                                'context_window': row['context_window'],
                                'max_tokens': row['max_tokens'],
                                'capabilities': json.loads(row['capabilities']) if isinstance(row['capabilities'], str) else row['capabilities'],
                                'deprecated': row['deprecated'],
                                'provider_metadata': json.loads(row['provider_metadata']) if isinstance(row['provider_metadata'], str) else row['provider_metadata']
                            })
                        
                        logger.info(f"Retrieved {len(models)} cached models for provider {provider_name}")
                        return models
                
                # Discover models from provider API
                discovered_models = await self._discover_models_from_provider(provider_name)
                
                # Cache the discovered models
                if discovered_models:
                    await self._cache_provider_models(conn, provider_id, discovered_models)
                
                return discovered_models
                
        except Exception as e:
            logger.error(f"Failed to get models for provider {provider_name}: {e}")
            # Fallback to provider discovery
            return await self._discover_models_from_provider(provider_name)

    async def _discover_models_from_provider(self, provider_name: str) -> List[Dict[str, Any]]:
        """Discover models from provider using unified API"""
        try:
            # Create a minimal config for the provider
            from unified_api.base import ModelConfig, ModelType
            
            # Get API key from environment or saved keys
            api_key = None
            if provider_name == 'openai':
                api_key = os.environ.get('OPENAI_API_KEY')
            elif provider_name == 'anthropic':
                api_key = os.environ.get('ANTHROPIC_API_KEY')
            elif provider_name == 'google':
                api_key = os.environ.get('GOOGLE_API_KEY')
            elif provider_name == 'huggingface':
                api_key = os.environ.get('HF_TOKEN')
            
            config = ModelConfig(
                provider=provider_name,
                model_id='default',  # Placeholder
                api_key=api_key,
                usage_type=ModelType.UTILITY
            )
            
            # Get provider instance
            provider = self.unified_api._get_provider_instance(config)
            
            # Call list_models (this is async)
            model_infos = await provider.list_models()
            
            # Convert to dict format
            models = []
            for model_info in model_infos:
                models.append({
                    'model_id': model_info.model_id,
                    'name': model_info.name,
                    'description': model_info.description,
                    'context_window': model_info.context_window,
                    'max_tokens': model_info.max_tokens,
                    'capabilities': model_info.capabilities,
                    'deprecated': model_info.deprecated,
                    'provider_metadata': model_info.provider_metadata
                })
            
            logger.info(f"Discovered {len(models)} models from provider {provider_name}")
            return models
            
        except Exception as e:
            logger.warning(f"Provider {provider_name} does not support model discovery: {e}")
            logger.info(f"Users must specify model_id manually for {provider_name}")
            # Return empty list - providers without discovery should return no models
            return []

    async def _cache_provider_models(self, conn, provider_id: int, models: List[Dict[str, Any]]):
        """Cache discovered models in database"""
        try:
            # Delete existing models for this provider
            delete_query = "DELETE FROM provider_models WHERE provider_id = $1"
            await conn.execute(delete_query, provider_id)
            
            # Insert new models
            for model in models:
                insert_query = """
                    INSERT INTO provider_models 
                    (provider_id, provider_model_id, name, description, context_window, max_tokens,
                     capabilities, deprecated, provider_metadata, source, last_updated)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'discovered', NOW())
                """
                await conn.execute(
                    insert_query,
                    provider_id,
                    model['model_id'],
                    model['name'],
                    model.get('description'),
                    model.get('context_window'),
                    model.get('max_tokens'),
                    json.dumps(model.get('capabilities', [])),
                    model.get('deprecated', False),
                    json.dumps(model.get('provider_metadata', {}))
                )
            
            logger.info(f"Cached {len(models)} models for provider_id {provider_id}")
            
        except Exception as e:
            logger.error(f"Failed to cache provider models: {e}")

    async def get_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all API keys for a user"""
        try:
            api_keys = await self.api_key_service.get_user_api_keys(user_id)
            logger.info(f"Retrieved {len(api_keys)} API keys for user {user_id}")
            return api_keys
            
        except Exception as e:
            logger.error(f"Failed to get user API keys for user {user_id}: {e}")
            raise

    async def create_user_api_key(
        self, 
        user_id: int, 
        provider: str, 
        key_value: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new API key for a user"""
        try:
            result = await self.api_key_service.create_user_api_key(
                user_id=user_id,
                provider=provider,
                key_value=key_value,
                name=name,
                description=description
            )
            
            logger.info(f"Created API key for user {user_id}, provider {provider}")
            return result
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create user API key for user {user_id}: {e}")
            raise

    async def update_user_api_key(
        self, 
        user_id: int, 
        key_id: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an API key's metadata"""
        try:
            result = await self.api_key_service.update_user_api_key(
                user_id=user_id,
                key_id=key_id,
                name=name,
                description=description
            )
            
            logger.info(f"Updated API key {key_id} for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to update user API key {key_id} for user {user_id}: {e}")
            raise

    async def delete_user_api_key(self, user_id: int, key_id: str) -> Dict[str, Any]:
        """Delete an API key"""
        try:
            result = await self.api_key_service.delete_user_api_key(
                user_id=user_id,
                key_id=key_id
            )
            
            logger.info(f"Deleted API key {key_id} for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete user API key {key_id} for user {user_id}: {e}")
            raise

    async def get_api_key_value(self, user_id: int, key_id: str) -> Optional[str]:
        """Get decrypted API key value for a specific key ID."""
        try:
            result = await self.api_key_service.get_api_key_value(user_id, key_id)
            if result:
                logger.info(f"Retrieved API key value for user {user_id}, key {key_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get API key value {key_id} for user {user_id}: {e}")
            raise


# Global models service instance
_models_service_instance = None

def get_models_service() -> ModelsService:
    """Get the global models service instance"""
    global _models_service_instance
    if _models_service_instance is None:
        # Import here to avoid circular imports
        from .database import get_db_pool
        pool = get_db_pool()
        if pool is None:
            raise RuntimeError("Database pool not initialized")
        _models_service_instance = ModelsService(pool)
    return _models_service_instance