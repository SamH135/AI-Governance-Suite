"""Prompt generation and management endpoints with saved API key support."""

from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import GeneratedPrompt, PromptCategory, AISystem
from ...shared.schemas import (
    UserResponse, PromptGenerationRequest, GeneratedPromptResponse,
    GeneratedPromptCreate, ApiResponse, PaginatedResponse
)
from ...shared.exceptions import NotFoundError, ValidationError
from ...shared.redis_client import redis_client
from ...shared.unified_api_auth import setup_unified_api_auth_dependency
from ..services.j1_service import j1_service

logger = structlog.get_logger()
router = APIRouter()

@router.post("/generate", response_model=ApiResponse[List[GeneratedPromptResponse]])
async def generate_prompts(
    request: PromptGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Generate new prompts using J1 model."""
    
    # Validate system if provided
    system_context = None
    if request.system_id:
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == request.system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        ai_system = result.scalar_one_or_none()
        if not ai_system:
            raise NotFoundError("AI System", request.system_id)
        system_context = f"System: {ai_system.name} ({ai_system.system_type})"
    
    # Get category context if provided
    category_name = "general"
    if request.category_id:
        result = await db.execute(
            select(PromptCategory).where(PromptCategory.category_id == request.category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise NotFoundError("Prompt Category", request.category_id)
        category_name = category.name
    
    try:
        # Convert LLM config dict to ModelConfig if provided
        llm_config = None
        if request.llm_config:
            try:
                from shared.unified_api.base import ModelConfig
                llm_config = ModelConfig(**request.llm_config)
            except ImportError:
                logger.warning("Unified API not available - LLM config ignored")
            except Exception as e:
                logger.warning(f"Invalid LLM config provided: {e}")
        
        # Generate prompts using J1 service
        generated_data = await j1_service.generate_prompts(
            requirements=request.requirements,
            category=category_name,
            count=request.count,
            system_context=system_context,
            llm_config=llm_config,
            optimization_params=request.optimization_params
        )
        
        # Save generated prompts to database
        saved_prompts = []
        for prompt_data in generated_data:
            prompt = GeneratedPrompt(
                category_id=request.category_id,
                system_id=request.system_id,
                text=prompt_data["text"],
                metadata=prompt_data["metadata"],
                thinking_trace=prompt_data["thinking_trace"],
                created_by=current_user.user_id
            )
            
            db.add(prompt)
            await db.flush()  # Get the ID
            
            # Cache thinking trace for analysis
            if prompt_data.get("thinking_trace"):
                cache_key = f"thinking_trace:{prompt.prompt_id}"
                await redis_client.set_json(cache_key, prompt_data["thinking_trace"], ttl=86400)
            
            saved_prompts.append(prompt)
        
        await db.commit()
        
        # Refresh all prompts to get complete data
        for prompt in saved_prompts:
            await db.refresh(prompt)
        
        logger.info("Prompts generated successfully", 
                   count=len(saved_prompts),
                   user_id=current_user.user_id,
                   category=category_name)
        
        return ApiResponse(
            success=True,
            data=[GeneratedPromptResponse.model_validate(p) for p in saved_prompts],
            message=f"Generated {len(saved_prompts)} prompts successfully"
        )
        
    except Exception as e:
        logger.error("Prompt generation failed", 
                    requirements=request.requirements[:100], 
                    error=str(e))
        raise ValidationError(f"Prompt generation failed: {str(e)}")


@router.post("/generate-with-saved-keys", response_model=ApiResponse[List[GeneratedPromptResponse]])
async def generate_prompts_with_saved_keys(
    request: PromptGenerationRequest,
    background_tasks: BackgroundTasks,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen),
    auth_manager = Depends(setup_unified_api_auth_dependency)
):
    """Generate new prompts using J1 model with saved API keys."""
    
    # Validate system if provided
    system_context = None
    if request.system_id:
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == request.system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        ai_system = result.scalar_one_or_none()
        if not ai_system:
            raise NotFoundError("AI System", request.system_id)
        system_context = f"System: {ai_system.name} ({ai_system.system_type})"
    
    # Get category context if provided
    category_name = "general"
    if request.category_id:
        result = await db.execute(
            select(PromptCategory).where(PromptCategory.category_id == request.category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise NotFoundError("Prompt Category", request.category_id)
        category_name = category.name
    
    try:
        # Create LLM config that will use saved API keys
        llm_config = None
        if request.llm_config:
            try:
                from shared.unified_api.base import ModelConfig
                # Don't pass api_key - it will be retrieved from saved keys
                config_dict = {k: v for k, v in request.llm_config.items() if k != 'api_key'}
                llm_config = ModelConfig(**config_dict)
                logger.info(f"Using saved API keys for provider: {llm_config.provider}")
            except ImportError:
                logger.warning("Unified API not available - LLM config ignored")
            except Exception as e:
                logger.warning(f"Invalid LLM config provided: {e}")
        
        # Generate prompts using J1 service (which uses unified API internally)
        generated_data = await j1_service.generate_prompts(
            requirements=request.requirements,
            category=category_name,
            count=request.count,
            system_context=system_context,
            llm_config=llm_config,
            optimization_params=request.optimization_params
        )
        
        # Save generated prompts to database
        saved_prompts = []
        for prompt_data in generated_data:
            prompt = GeneratedPrompt(
                category_id=request.category_id,
                system_id=request.system_id,
                text=prompt_data["text"],
                metadata={
                    **prompt_data["metadata"],
                    "used_saved_keys": True,
                    "llm_provider": llm_config.provider if llm_config else None,
                    "llm_model": llm_config.model_id if llm_config else None
                },
                thinking_trace=prompt_data["thinking_trace"],
                created_by=current_user.user_id
            )
            
            db.add(prompt)
            await db.flush()  # Get the ID
            
            # Cache thinking trace for analysis
            if prompt_data.get("thinking_trace"):
                cache_key = f"thinking_trace:{prompt.prompt_id}"
                await redis_client.set_json(cache_key, prompt_data["thinking_trace"], ttl=86400)
            
            saved_prompts.append(prompt)
        
        await db.commit()
        
        # Refresh all prompts to get complete data
        for prompt in saved_prompts:
            await db.refresh(prompt)
        
        logger.info("Prompts generated successfully with saved keys", 
                   count=len(saved_prompts),
                   user_id=current_user.user_id,
                   category=category_name,
                   using_saved_keys=True)
        
        return ApiResponse(
            success=True,
            data=[GeneratedPromptResponse.model_validate(p) for p in saved_prompts],
            message=f"Generated {len(saved_prompts)} prompts successfully using saved API keys"
        )
        
    except Exception as e:
        logger.error("Prompt generation with saved keys failed", 
                    requirements=request.requirements[:100], 
                    error=str(e))
        raise ValidationError(f"Prompt generation with saved keys failed: {str(e)}")


@router.get("/", response_model=ApiResponse[PaginatedResponse])
async def get_prompts(
    category_id: Optional[int] = None,
    system_id: Optional[int] = None,
    approval_status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get generated prompts for the current user."""
    
    # Build query
    query = select(GeneratedPrompt).where(GeneratedPrompt.created_by == current_user.user_id)
    
    if category_id:
        query = query.where(GeneratedPrompt.category_id == category_id)
    if system_id:
        query = query.where(GeneratedPrompt.system_id == system_id)
    if approval_status:
        query = query.where(GeneratedPrompt.approval_status == approval_status)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(GeneratedPrompt.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    prompts = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    paginated_response = PaginatedResponse(
        items=[GeneratedPromptResponse.model_validate(prompt) for prompt in prompts],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
    
    return ApiResponse(
        success=True,
        data=paginated_response
    )

@router.get("/{prompt_id}", response_model=ApiResponse[GeneratedPromptResponse])
async def get_prompt(
    prompt_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific generated prompt."""
    
    result = await db.execute(
        select(GeneratedPrompt).where(
            GeneratedPrompt.prompt_id == prompt_id,
            GeneratedPrompt.created_by == current_user.user_id
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    return ApiResponse(
        success=True,
        data=GeneratedPromptResponse.model_validate(prompt)
    )

@router.post("/{prompt_id}/optimize", response_model=ApiResponse[GeneratedPromptResponse])
async def optimize_prompt(
    prompt_id: int,
    feedback: dict,
    optimization_goals: List[str] = None,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Optimize an existing prompt based on feedback."""
    
    # Get original prompt
    result = await db.execute(
        select(GeneratedPrompt).where(
            GeneratedPrompt.prompt_id == prompt_id,
            GeneratedPrompt.created_by == current_user.user_id
        )
    )
    original_prompt = result.scalar_one_or_none()
    
    if not original_prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    try:
        # Optimize using J1 service
        optimization_result = await j1_service.optimize_prompt(
            original_prompt=original_prompt.text,
            feedback=feedback,
            optimization_goals=optimization_goals or []
        )
        
        # Create new optimized prompt
        optimized_prompt = GeneratedPrompt(
            category_id=original_prompt.category_id,
            system_id=original_prompt.system_id,
            text=optimization_result["optimized_prompt"],
            metadata={
                **original_prompt.metadata,
                "optimized_from": prompt_id,
                "optimization_applied": True,
                "optimization_reasoning": optimization_result["optimization_reasoning"]
            },
            thinking_trace={
                "original_thinking": original_prompt.thinking_trace,
                "optimization_process": optimization_result["optimization_reasoning"]
            },
            created_by=current_user.user_id
        )
        
        db.add(optimized_prompt)
        await db.commit()
        await db.refresh(optimized_prompt)
        
        # Cache optimization data
        cache_key = f"optimization:{optimized_prompt.prompt_id}"
        await redis_client.set_json(cache_key, optimization_result, ttl=86400)
        
        logger.info("Prompt optimized successfully", 
                   original_id=prompt_id,
                   optimized_id=optimized_prompt.prompt_id,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=GeneratedPromptResponse.model_validate(optimized_prompt),
            message="Prompt optimized successfully"
        )
        
    except Exception as e:
        logger.error("Prompt optimization failed", 
                    prompt_id=prompt_id, error=str(e))
        raise ValidationError(f"Prompt optimization failed: {str(e)}")

@router.get("/{prompt_id}/thinking", response_model=ApiResponse[dict])
async def get_thinking_trace(
    prompt_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get the thinking trace analysis for a prompt."""
    
    # Verify prompt belongs to user
    result = await db.execute(
        select(GeneratedPrompt).where(
            GeneratedPrompt.prompt_id == prompt_id,
            GeneratedPrompt.created_by == current_user.user_id
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    try:
        # Get thinking trace analysis
        analysis = await j1_service.analyze_thinking_trace(str(prompt_id))
        
        return ApiResponse(
            success=True,
            data=analysis,
            message="Thinking trace analysis retrieved"
        )
        
    except Exception as e:
        logger.error("Thinking trace analysis failed", 
                    prompt_id=prompt_id, error=str(e))
        raise ValidationError(f"Thinking trace analysis failed: {str(e)}")

@router.put("/{prompt_id}/approval", response_model=ApiResponse[GeneratedPromptResponse])
async def update_prompt_approval(
    prompt_id: int,
    approval_status: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update the approval status of a prompt."""
    
    # Validate approval status
    valid_statuses = ["pending", "approved", "rejected", "needs_review"]
    if approval_status not in valid_statuses:
        raise ValidationError(
            f"Invalid approval status: {approval_status}",
            details={"valid_statuses": valid_statuses}
        )
    
    # Get prompt
    result = await db.execute(
        select(GeneratedPrompt).where(
            GeneratedPrompt.prompt_id == prompt_id,
            GeneratedPrompt.created_by == current_user.user_id
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    # Update approval status
    prompt.approval_status = approval_status
    await db.commit()
    await db.refresh(prompt)
    
    logger.info("Prompt approval status updated", 
               prompt_id=prompt_id,
               new_status=approval_status,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=GeneratedPromptResponse.model_validate(prompt),
        message=f"Prompt approval status updated to {approval_status}"
    )

@router.delete("/{prompt_id}", response_model=ApiResponse[str])
async def delete_prompt(
    prompt_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Delete a generated prompt."""
    
    # Get prompt
    result = await db.execute(
        select(GeneratedPrompt).where(
            GeneratedPrompt.prompt_id == prompt_id,
            GeneratedPrompt.created_by == current_user.user_id
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise NotFoundError("Generated Prompt", prompt_id)
    
    # Delete from database
    await db.delete(prompt)
    await db.commit()
    
    # Clean up cache
    cache_keys = [
        f"thinking_trace:{prompt_id}",
        f"optimization:{prompt_id}"
    ]
    for key in cache_keys:
        try:
            await redis_client.delete(key)
        except Exception:
            pass  # Ignore cache cleanup errors
    
    logger.info("Prompt deleted", 
               prompt_id=prompt_id,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data="Prompt deleted successfully",
        message="Prompt has been permanently deleted"
    )