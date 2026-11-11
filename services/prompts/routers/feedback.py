"""Prompt feedback management endpoints."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import PromptFeedback, GeneratedPrompt
from ...shared.schemas import (
    UserResponse, PromptFeedbackCreate, PromptFeedbackResponse, ApiResponse
)
from ...shared.exceptions import NotFoundError, ConflictError

logger = structlog.get_logger()
router = APIRouter()

@router.post("/{prompt_id}", response_model=ApiResponse[PromptFeedbackResponse])
async def create_feedback(
    prompt_id: int,
    feedback_data: PromptFeedbackCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Create feedback for a prompt."""
    
    # Verify prompt exists
    prompt_result = await db.execute(
        select(GeneratedPrompt).where(GeneratedPrompt.prompt_id == prompt_id)
    )
    prompt = prompt_result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    # Check if user already provided feedback
    existing_feedback = await db.execute(
        select(PromptFeedback).where(
            PromptFeedback.prompt_id == prompt_id,
            PromptFeedback.user_id == current_user.user_id
        )
    )
    if existing_feedback.scalar_one_or_none():
        raise ConflictError("You have already provided feedback for this prompt")
    
    # Create feedback
    feedback = PromptFeedback(
        prompt_id=prompt_id,
        user_id=current_user.user_id,
        is_approved=feedback_data.is_approved,
        feedback_text=feedback_data.feedback_text,
        score=feedback_data.score
    )
    
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    
    # Update prompt's average feedback score
    await update_prompt_feedback_score(db, prompt_id)
    
    logger.info("Prompt feedback created", 
               feedback_id=feedback.feedback_id,
               prompt_id=prompt_id,
               user_id=current_user.user_id,
               score=feedback_data.score)
    
    return ApiResponse(
        success=True,
        data=PromptFeedbackResponse.model_validate(feedback),
        message="Feedback submitted successfully"
    )

@router.get("/{prompt_id}", response_model=ApiResponse[List[PromptFeedbackResponse]])
async def get_prompt_feedback(
    prompt_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get all feedback for a prompt."""
    
    # Verify prompt exists
    prompt_result = await db.execute(
        select(GeneratedPrompt).where(GeneratedPrompt.prompt_id == prompt_id)
    )
    prompt = prompt_result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    # Get feedback
    result = await db.execute(
        select(PromptFeedback).where(PromptFeedback.prompt_id == prompt_id)
        .order_by(PromptFeedback.created_at.desc())
    )
    feedback_list = result.scalars().all()
    
    return ApiResponse(
        success=True,
        data=[PromptFeedbackResponse.model_validate(fb) for fb in feedback_list]
    )

async def update_prompt_feedback_score(db: AsyncSession, prompt_id: int):
    """Update the average feedback score for a prompt."""
    
    # Calculate average score
    result = await db.execute(
        select(func.avg(PromptFeedback.score)).where(PromptFeedback.prompt_id == prompt_id)
    )
    avg_score = result.scalar()
    
    if avg_score is not None:
        # Update prompt
        prompt_result = await db.execute(
            select(GeneratedPrompt).where(GeneratedPrompt.prompt_id == prompt_id)
        )
        prompt = prompt_result.scalar_one_or_none()
        
        if prompt:
            prompt.feedback_score = float(avg_score)
            await db.commit()