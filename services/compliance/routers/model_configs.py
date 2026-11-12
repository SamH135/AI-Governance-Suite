"""AI Model Configuration CRUD endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import structlog

from services.shared.database import db_manager
from services.shared.auth import get_current_active_user
from services.shared.models import AIModelConfig, User
from services.shared.schemas import (
    UserResponse, ApiResponse,
    AIModelConfigCreate, AIModelConfigUpdate, AIModelConfigResponse
)
from services.shared.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger()
router = APIRouter()

@router.get("/models", response_model=ApiResponse[List[AIModelConfigResponse]])
async def get_model_configs(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get all AI model configurations for the current user."""
    logger.info("Getting model configurations", user_id=current_user.user_id)
    
    try:
        # Get all model configurations for the user
        result = await db.execute(
            select(AIModelConfig)
            .where(AIModelConfig.created_by == current_user.user_id)
            .order_by(AIModelConfig.created_at.desc())
        )
        configs = result.scalars().all()
        
        # Convert to response format
        config_responses = []
        for config in configs:
            config_dict = {
                "id": config.config_id,
                "config_id": config.config_id,
                "name": config.name,
                "description": config.description,
                "provider": config.provider,
                "model_id": config.model_id,
                "api_key": "***HIDDEN***" if config.api_key else None,  # Hide API key for security
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                                "timeout": config.timeout,
                "enabled": config.enabled,
                "tags": config.tags or [],
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "created_by": config.created_by
            }
            config_responses.append(config_dict)
        
        logger.info("Retrieved model configurations", user_id=current_user.user_id, count=len(configs))
        
        return ApiResponse(
            success=True,
            data=config_responses
        )
        
    except Exception as e:
        logger.error("Failed to get model configurations", user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model configurations"
        )

@router.get("/models/{config_id}", response_model=ApiResponse[AIModelConfigResponse])
async def get_model_config(
    config_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific AI model configuration by ID."""
    logger.info("Getting model configuration", config_id=config_id, user_id=current_user.user_id)
    
    try:
        # Get the model configuration
        result = await db.execute(
            select(AIModelConfig).where(
                AIModelConfig.config_id == config_id,
                AIModelConfig.created_by == current_user.user_id
            )
        )
        config = result.scalar_one_or_none()
        
        if not config:
            raise NotFoundError("AI Model Configuration", config_id)
        
        # Build response
        config_dict = {
            "id": config.config_id,
            "config_id": config.config_id,
            "name": config.name,
            "description": config.description,
            "provider": config.provider,
            "model_id": config.model_id,
            "api_key": config.api_key,  # Return actual API key for editing
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
                        "timeout": config.timeout,
            "enabled": config.enabled,
            "tags": config.tags or [],
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "created_by": config.created_by
        }
        
        logger.info("Retrieved model configuration", config_id=config_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=config_dict
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model Configuration {config_id} not found"
        )
    except Exception as e:
        logger.error("Failed to get model configuration", config_id=config_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model configuration"
        )

@router.post("/models", response_model=ApiResponse[AIModelConfigResponse], status_code=status.HTTP_201_CREATED)
async def create_model_config(
    config_data: AIModelConfigCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Create a new AI model configuration."""
    logger.info("Creating model configuration", name=config_data.name, user_id=current_user.user_id)
    
    try:
        # Create the model configuration
        config = AIModelConfig(
            name=config_data.name,
            description=config_data.description,
            provider=config_data.provider,
            model_id=config_data.model_id,
            api_key=config_data.api_key,
            api_url=getattr(config_data, 'api_url', None),
            temperature=config_data.temperature,
            max_tokens=config_data.max_tokens,
            timeout=getattr(config_data, 'timeout', 30),
            enabled=getattr(config_data, 'enabled', True),
            tags=getattr(config_data, 'tags', []),
            created_by=current_user.user_id
        )
        
        db.add(config)
        await db.commit()
        await db.refresh(config)
        
        # Build response
        config_dict = {
            "id": config.config_id,
            "config_id": config.config_id,
            "name": config.name,
            "description": config.description,
            "provider": config.provider,
            "model_id": config.model_id,
            "api_key": "***HIDDEN***",  # Hide API key in response
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
                        "timeout": config.timeout,
            "enabled": config.enabled,
            "tags": config.tags or [],
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "created_by": config.created_by
        }
        
        logger.info("Created model configuration", config_id=config.config_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=config_dict
        )
        
    except Exception as e:
        logger.error("Failed to create model configuration", name=config_data.name, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model configuration"
        )

@router.put("/models/{config_id}", response_model=ApiResponse[AIModelConfigResponse])
async def update_model_config(
    config_id: int,
    config_data: AIModelConfigUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update an AI model configuration."""
    logger.info("Updating model configuration", config_id=config_id, user_id=current_user.user_id)
    
    try:
        # Get the existing model configuration
        result = await db.execute(
            select(AIModelConfig).where(
                AIModelConfig.config_id == config_id,
                AIModelConfig.created_by == current_user.user_id
            )
        )
        config = result.scalar_one_or_none()
        
        if not config:
            raise NotFoundError("AI Model Configuration", config_id)
        
        # Update fields
        update_data = config_data.dict(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                setattr(config, field, value)
        
        await db.commit()
        await db.refresh(config)
        
        # Build response
        config_dict = {
            "id": config.config_id,
            "config_id": config.config_id,
            "name": config.name,
            "description": config.description,
            "provider": config.provider,
            "model_id": config.model_id,
            "api_key": "***HIDDEN***",  # Hide API key in response
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
                        "timeout": config.timeout,
            "enabled": config.enabled,
            "tags": config.tags or [],
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "created_by": config.created_by
        }
        
        logger.info("Updated model configuration", config_id=config_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=config_dict
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model Configuration {config_id} not found"
        )
    except Exception as e:
        logger.error("Failed to update model configuration", config_id=config_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model configuration"
        )

@router.delete("/models/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
    config_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Delete an AI model configuration."""
    logger.info("Deleting model configuration", config_id=config_id, user_id=current_user.user_id)
    
    try:
        # Check if config exists and belongs to user
        result = await db.execute(
            select(AIModelConfig).where(
                AIModelConfig.config_id == config_id,
                AIModelConfig.created_by == current_user.user_id
            )
        )
        config = result.scalar_one_or_none()
        
        if not config:
            raise NotFoundError("AI Model Configuration", config_id)
        
        # Delete the configuration
        await db.execute(
            delete(AIModelConfig).where(AIModelConfig.config_id == config_id)
        )
        await db.commit()
        
        logger.info("Deleted model configuration", config_id=config_id, user_id=current_user.user_id)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model Configuration {config_id} not found"
        )
    except Exception as e:
        logger.error("Failed to delete model configuration", config_id=config_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model configuration"
        )

@router.post("/models/test")
async def test_model_config(
    config_data: dict,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Test an AI model configuration."""
    logger.info("Testing model configuration", user_id=current_user.user_id)
    
    try:
        # Import unified API here to avoid circular imports
        from shared.unified_api import get_unified_api, ModelConfig
        
        unified_api = get_unified_api()
        
        # Create ModelConfig from the provided configuration
        config = ModelConfig(**config_data)
        
        # Test with a simple prompt
        test_prompt = "Hello, this is a test message. Please respond briefly."
        
        response = await unified_api.agenerate(
            prompt=test_prompt,
            config=config
        )
        
        if response.error:
            return ApiResponse(
                success=False,
                data={"error": response.error.message, "error_type": response.error.type},
                message="Model configuration test failed"
            )
        
        return ApiResponse(
            success=True,
            data={
                "test_prompt": test_prompt,
                "response": response.content[:200] + "..." if len(response.content) > 200 else response.content,
                "provider": response.provider,
                "model_id": response.model_id,
                "usage": response.usage
            },
            message="Model configuration test successful"
        )
        
    except ImportError:
        return ApiResponse(
            success=False,
            message="Unified API not available for testing"
        )
    except Exception as e:
        logger.error("Failed to test model configuration", user_id=current_user.user_id, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Model test failed: {str(e)}"
        )