"""
Models API Router
Provides endpoints for AI model configuration management
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import ValidationError

# Import shared services and models
from ..shared.models_service import (
    ModelsService, AIModelConfigRequest, AIModelConfigResponse, 
    ModelTestRequest, ModelTestResponse, ProviderType, UsageType
)

from ..shared.database import get_db_pool
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

async def get_models_service() -> ModelsService:
    """Dependency to get models service instance"""
    db_pool = get_db_pool()  # This is synchronous, not async
    return ModelsService(db_pool)

@router.get("/", response_model=List[AIModelConfigResponse])
async def get_models(
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Get all AI model configurations for the current user"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Getting model configurations for user {user_id}")
        
        models = await models_service.get_models(user_id)
        logger.info(f"Retrieved {len(models)} model configurations for user {user_id}")
        
        return models
        
    except Exception as e:
        logger.error(f"Failed to get model configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model configurations: {str(e)}"
        )

@router.get("/{config_id}", response_model=AIModelConfigResponse)
async def get_model(
    config_id: int,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Get a specific AI model configuration"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Getting model configuration {config_id} for user {user_id}")
        
        model = await models_service.get_model(config_id, user_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration {config_id} not found"
            )
        
        logger.info(f"Retrieved model configuration {config_id} for user {user_id}")
        return model
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model configuration: {str(e)}"
        )

@router.post("/", response_model=AIModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_request: AIModelConfigRequest,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Create a new AI model configuration"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Creating model configuration '{model_request.name}' for user {user_id}")
        
        model = await models_service.create_model(model_request, user_id)
        logger.info(f"Created model configuration {model.id} for user {user_id}")
        
        return model
        
    except ValueError as e:
        logger.warning(f"Validation error creating model configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        logger.warning(f"Request validation error creating model configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create model configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create model configuration: {str(e)}"
        )

@router.put("/{config_id}", response_model=AIModelConfigResponse)
async def update_model(
    config_id: int,
    model_request: AIModelConfigRequest,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Update an AI model configuration"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Updating model configuration {config_id} for user {user_id}")
        
        model = await models_service.update_model(config_id, model_request, user_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration {config_id} not found"
            )
        
        logger.info(f"Updated model configuration {config_id} for user {user_id}")
        return model
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        logger.warning(f"Request validation error updating model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model configuration: {str(e)}"
        )

@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    config_id: int,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Delete an AI model configuration"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Deleting model configuration {config_id} for user {user_id}")
        
        success = await models_service.delete_model(config_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration {config_id} not found"
            )
        
        logger.info(f"Deleted model configuration {config_id} for user {user_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete model configuration: {str(e)}"
        )

@router.post("/test", response_model=ModelTestResponse)
async def test_model(
    test_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Test an AI model configuration"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Testing model configuration for user {user_id}")
        
        result = await models_service.test_model(test_data, user_id)
        
        if result.success:
            logger.info(f"Model test successful for user {user_id}")
        else:
            logger.warning(f"Model test failed for user {user_id}: {result.error_message}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to test model configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test model configuration: {str(e)}"
        )

@router.get("/providers/", response_model=List[Dict[str, Any]])
async def get_providers(
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Get available AI providers"""
    try:
        logger.info("Getting available AI providers")
        
        providers = await models_service.get_providers()
        logger.info(f"Retrieved {len(providers)} available providers")
        
        return providers
        
    except Exception as e:
        logger.error(f"Failed to get AI providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve AI providers: {str(e)}"
        )

@router.get("/providers/{provider_name}/models", response_model=List[Dict[str, Any]])
async def get_provider_models(
    provider_name: str,
    force_refresh: bool = False,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Get available models from a specific provider, discovering from API if needed"""
    try:
        logger.info(f"Getting models for provider {provider_name} (force_refresh={force_refresh})")
        
        models = await models_service.get_provider_models(provider_name, force_refresh)
        logger.info(f"Retrieved {len(models)} models for provider {provider_name}")
        
        return models
        
    except Exception as e:
        logger.error(f"Failed to get models for provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve models for provider {provider_name}: {str(e)}"
        )

@router.post("/providers/{provider_name}/refresh", response_model=Dict[str, Any])
async def refresh_provider_models(
    provider_name: str,
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Force refresh models from a specific provider API"""
    try:
        logger.info(f"Force refreshing models for provider {provider_name}")
        
        models = await models_service.get_provider_models(provider_name, force_refresh=True)
        logger.info(f"Refreshed {len(models)} models for provider {provider_name}")
        
        return {
            "success": True,
            "provider": provider_name,
            "models_count": len(models),
            "message": f"Successfully refreshed {len(models)} models from {provider_name}"
        }
        
    except Exception as e:
        logger.error(f"Failed to refresh models for provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh models for provider {provider_name}: {str(e)}"
        )

# Additional endpoints for model management

@router.patch("/{config_id}/toggle", response_model=AIModelConfigResponse)
async def toggle_model(
    config_id: int,
    enabled: Dict[str, bool],
    current_user: dict = Depends(get_current_user),
    models_service: ModelsService = Depends(get_models_service)
):
    """Toggle model enabled/disabled status"""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Toggling model configuration {config_id} enabled status for user {user_id}")
        
        # Get current model
        current_model = await models_service.get_model(config_id, user_id)
        if not current_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration {config_id} not found"
            )
        
        # Create update request with only enabled field changed
        update_request = AIModelConfigRequest(
            name=current_model.name,
            description=current_model.description,
            provider=ProviderType(current_model.provider),
            model_id=current_model.model_id,
            api_key=None,  # Don't update API key
            api_url=current_model.api_url,
            temperature=current_model.temperature,
            max_tokens=current_model.max_tokens,
            timeout=current_model.timeout,
            max_retries=current_model.max_retries,
            retry_delay=current_model.retry_delay,
            provider_options=current_model.provider_options,
            usage_type=UsageType(current_model.usage_type),
            metadata=current_model.metadata,
            tags=current_model.tags,
            enabled=enabled.get('enabled', current_model.enabled)
        )
        
        model = await models_service.update_model(config_id, update_request, user_id)
        logger.info(f"Toggled model configuration {config_id} enabled status for user {user_id}")
        
        return model
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle model configuration {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle model configuration: {str(e)}"
        )