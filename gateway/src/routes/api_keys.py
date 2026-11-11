"""API Key Management Routes"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..shared.models_service import get_models_service  
from .auth import get_current_user
from ..logger_util import logger

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

# Request/Response Models
class CreateAPIKeyRequest(BaseModel):
    provider: str = Field(..., description="API key provider (openai, anthropic, google, etc.)")
    key_value: str = Field(..., description="The API key value")
    name: Optional[str] = Field(None, description="Optional name for the API key")
    description: Optional[str] = Field(None, description="Optional description")

class UpdateAPIKeyRequest(BaseModel):
    name: Optional[str] = Field(None, description="Updated name")
    description: Optional[str] = Field(None, description="Updated description")

class APIKeyResponse(BaseModel):
    key_id: str
    provider: str
    name: str
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str
    expires_at: Optional[str]
    is_expired: bool = False

@router.get("", response_model=List[APIKeyResponse])
async def get_user_api_keys(
    current_user: dict = Depends(get_current_user)
):
    """Get all API keys for the current user"""
    logger.info("Getting user API keys", user_id=current_user["user_id"])
    
    try:
        models_service = get_models_service()
        api_keys = await models_service.get_user_api_keys(current_user["user_id"])
        
        logger.info("Retrieved user API keys", user_id=current_user["user_id"], count=len(api_keys))
        return api_keys
        
    except Exception as e:
        logger.error("Failed to get user API keys", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )

@router.post("", response_model=Dict[str, Any])
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new API key"""
    logger.info("Creating API key", user_id=current_user["user_id"], provider=request.provider)
    
    try:
        models_service = get_models_service()
        result = await models_service.create_user_api_key(
            user_id=current_user["user_id"],
            provider=request.provider,
            key_value=request.key_value,
            name=request.name,
            description=request.description
        )
        
        logger.info("API key created successfully", user_id=current_user["user_id"], provider=request.provider)
        return result
        
    except ValueError as e:
        logger.warning("Invalid API key creation request", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create API key", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )

@router.put("/{key_id}", response_model=Dict[str, Any])
async def update_api_key(
    key_id: str,
    request: UpdateAPIKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update an API key's metadata"""
    logger.info("Updating API key", user_id=current_user["user_id"], key_id=key_id)
    
    try:
        models_service = get_models_service()
        result = await models_service.update_user_api_key(
            user_id=current_user["user_id"],
            key_id=key_id,
            name=request.name,
            description=request.description
        )
        
        logger.info("API key updated successfully", user_id=current_user["user_id"], key_id=key_id)
        return result
        
    except ValueError as e:
        logger.warning("Invalid API key update request", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to update API key", user_id=current_user["user_id"], key_id=key_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key"
        )

@router.delete("/{key_id}", response_model=Dict[str, Any])
async def delete_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an API key"""
    logger.info("Deleting API key", user_id=current_user["user_id"], key_id=key_id)
    
    try:
        models_service = get_models_service()
        result = await models_service.delete_user_api_key(
            user_id=current_user["user_id"],
            key_id=key_id
        )
        
        logger.info("API key deleted successfully", user_id=current_user["user_id"], key_id=key_id)
        return result
        
    except ValueError as e:
        logger.warning("Invalid API key deletion request", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to delete API key", user_id=current_user["user_id"], key_id=key_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key"
        )

@router.post("/{key_id}/rotate", response_model=Dict[str, Any])
async def rotate_api_key(
    key_id: str,
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """Rotate an API key by replacing it with a new one"""
    logger.info("Rotating API key", user_id=current_user["user_id"], key_id=key_id)
    
    try:
        models_service = get_models_service()
        
        # Delete old key and create new one
        await models_service.delete_user_api_key(current_user["user_id"], key_id)
        
        result = await models_service.create_user_api_key(
            user_id=current_user["user_id"],
            provider=request.provider,
            key_value=request.key_value,
            name=request.name,
            description=request.description
        )
        
        logger.info("API key rotated successfully", user_id=current_user["user_id"], old_key_id=key_id)
        return result
        
    except ValueError as e:
        logger.warning("Invalid API key rotation request", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to rotate API key", user_id=current_user["user_id"], key_id=key_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate API key"
        )

@router.get("/{key_id}/value", response_model=Dict[str, str])
async def get_api_key_value(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the decrypted value of an API key (for viewing purposes)"""
    logger.info("Getting API key value", user_id=current_user["user_id"], key_id=key_id)
    
    try:
        models_service = get_models_service()
        # Get the decrypted key value
        key_value = await models_service.get_api_key_value(current_user["user_id"], key_id)
        
        if not key_value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        logger.info("API key value retrieved", user_id=current_user["user_id"], key_id=key_id)
        return {"key_value": key_value}
        
    except ValueError as e:
        logger.warning("Invalid API key retrieval request", user_id=current_user["user_id"], error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to get API key value", user_id=current_user["user_id"], key_id=key_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key value"
        )

@router.get("/providers", response_model=List[str])
async def get_supported_providers():
    """Get list of supported API key providers"""
    logger.info("Getting supported API key providers")
    
    providers = [
        "openai",
        "anthropic", 
        "google",
        "azure",
        "huggingface",
        "cohere",
        "custom"
    ]
    
    return providers