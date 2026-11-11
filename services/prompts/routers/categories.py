"""Prompt category management endpoints."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from services.shared.database import db_manager
from services.shared.auth import get_current_active_user, require_admin
from services.shared.models import PromptCategory
from services.shared.schemas import (
    UserResponse, PromptCategoryResponse, PromptCategoryBase, ApiResponse
)
from services.shared.exceptions import NotFoundError, ConflictError

logger = structlog.get_logger()
router = APIRouter()

@router.get("/", response_model=ApiResponse[List[PromptCategoryResponse]])
async def get_categories(
    framework: str = None,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get all prompt categories."""
    
    query = select(PromptCategory)
    
    if framework:
        query = query.where(PromptCategory.framework == framework)
    
    result = await db.execute(query.order_by(PromptCategory.name))
    categories = result.scalars().all()
    
    return ApiResponse(
        success=True,
        data=[PromptCategoryResponse.model_validate(cat) for cat in categories]
    )

@router.get("/{category_id}", response_model=ApiResponse[PromptCategoryResponse])
async def get_category(
    category_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get a specific prompt category."""
    
    result = await db.execute(
        select(PromptCategory).where(PromptCategory.category_id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise NotFoundError("Prompt Category", category_id)
    
    return ApiResponse(
        success=True,
        data=PromptCategoryResponse.model_validate(category)
    )

@router.post("/", response_model=ApiResponse[PromptCategoryResponse])
async def create_category(
    category_data: PromptCategoryBase,
    current_user: UserResponse = Depends(require_admin),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Create a new prompt category (admin only)."""
    
    # Check if category name already exists
    existing = await db.execute(
        select(PromptCategory).where(PromptCategory.name == category_data.name)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Category with name '{category_data.name}' already exists")
    
    # Create category
    category = PromptCategory(
        name=category_data.name,
        description=category_data.description,
        framework=category_data.framework
    )
    
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    logger.info("Prompt category created", 
               category_id=category.category_id,
               name=category.name,
               created_by=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=PromptCategoryResponse.model_validate(category),
        message="Prompt category created successfully"
    )