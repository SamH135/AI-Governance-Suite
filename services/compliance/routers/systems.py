"""AI Systems management endpoints."""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, text
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from datetime import datetime
import time
import structlog

from services.shared.database import db_manager
from services.shared.auth import get_current_active_user
from services.shared.unified_api_auth import setup_unified_api_auth_dependency
from services.shared.models import AISystem, User
from services.shared.schemas import (
    UserResponse, ApiResponse,
    AISystemCreate, AISystemUpdate, AISystemResponse
)
from services.shared.exceptions import NotFoundError, ValidationError
from services.shared.models import AIModelConfig
from ..services.compliance_service import ComplianceService
from ..services.evaluator_factory import EvaluatorFactory

# Import unified API system (consistent with model_configs.py)
try:
    from shared.unified_api import get_unified_api, ModelConfig
    UNIFIED_API_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Unified API not available: {e}")
    UNIFIED_API_AVAILABLE = False

logger = structlog.get_logger()
router = APIRouter()

@router.get("/systems", response_model=ApiResponse[List[AISystemResponse]])
async def get_ai_systems(
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get all AI systems for the current user."""
    logger.info("Getting AI systems", user_id=current_user.user_id)
    
    try:
        # Get all AI systems for the user
        result = await db.execute(
            select(AISystem)
            .where(AISystem.user_id == current_user.user_id)
            .order_by(AISystem.created_at.desc())
        )
        systems = result.scalars().all()
        
        # For each system, we need to get the model name
        systems_with_model_info = []
        for system in systems:
            system_dict = {
                "system_id": system.system_id,
                "name": system.name,
                "description": system.description,
                "version": system.version,
                "system_type": system.system_type,
                "compliance_frameworks": system.compliance_frameworks or [],
                "model_config_id": system.model_config_id,
                "industry": getattr(system, 'industry', None),
                "created_at": system.created_at,
                "updated_at": system.updated_at,
                "user_id": system.user_id,
                "model_name": None,  # Default
                "status": "active",  # Default
                "last_tested": None,  # Will be populated later
                "compliance_scores": {}  # Will be populated later
            }
            
            # Get model configuration name if available
            if system.model_config_id:
                model_result = await db.execute(
                    text("SELECT name FROM ai_model_configs WHERE config_id = :config_id"),
                    {"config_id": system.model_config_id}
                )
                model_row = model_result.fetchone()
                if model_row:
                    system_dict["model_name"] = model_row[0]
            
            systems_with_model_info.append(system_dict)
        
        logger.info("Retrieved AI systems", user_id=current_user.user_id, count=len(systems))
        
        return ApiResponse(
            success=True,
            data=systems_with_model_info
        )
        
    except Exception as e:
        logger.error("Failed to get AI systems", user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI systems"
        )

@router.get("/systems/{system_id}", response_model=ApiResponse[AISystemResponse])
async def get_ai_system(
    system_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific AI system by ID."""
    logger.info("Getting AI system", system_id=system_id, user_id=current_user.user_id)
    
    try:
        # Get the AI system
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        system = result.scalar_one_or_none()
        
        if not system:
            raise NotFoundError("AI System", system_id)
        
        # Build response with model info
        system_dict = {
            "system_id": system.system_id,
            "name": system.name,
            "description": system.description,
            "version": system.version,
            "system_type": system.system_type,
            "compliance_frameworks": system.compliance_frameworks or [],
            "model_config_id": system.model_config_id,
            "industry": getattr(system, 'industry', None),
            "created_at": system.created_at,
            "updated_at": system.updated_at,
            "user_id": system.user_id,
            "model_name": None,
            "status": "active",
            "last_tested": None,
            "compliance_scores": {}
        }
        
        # Get model configuration name if available
        if system.model_config_id:
            model_result = await db.execute(
                text("SELECT name FROM ai_model_configs WHERE config_id = :config_id"),
                {"config_id": system.model_config_id}
            )
            model_row = model_result.fetchone()
            if model_row:
                system_dict["model_name"] = model_row[0]
        
        logger.info("Retrieved AI system", system_id=system_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=system_dict
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI System {system_id} not found"
        )
    except Exception as e:
        logger.error("Failed to get AI system", system_id=system_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI system"
        )

@router.post("/systems", response_model=ApiResponse[AISystemResponse], status_code=status.HTTP_201_CREATED)
async def create_ai_system(
    system_data: AISystemCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Create a new AI system."""
    logger.info("Creating AI system", name=system_data.name, user_id=current_user.user_id)
    
    try:
        # Validate that model_config_id exists and belongs to user if provided
        model_config_id = getattr(system_data, 'model_config_id', None)
        model_name = None
        
        if model_config_id:
            model_result = await db.execute(
                text("SELECT name FROM ai_model_configs WHERE config_id = :config_id AND created_by = :user_id"),
                {"config_id": model_config_id, "user_id": current_user.user_id}
            )
            model_row = model_result.fetchone()
            if not model_row:
                raise ValidationError("Invalid model configuration ID")
            model_name = model_row[0]
        
        # Create the AI system
        system = AISystem(
            name=system_data.name,
            description=system_data.description,
            version=system_data.version,
            system_type=system_data.system_type,
            compliance_frameworks=system_data.compliance_frameworks,
            model_config_id=model_config_id,
            industry=getattr(system_data, 'industry', None),
            user_id=current_user.user_id
        )
        
        db.add(system)
        await db.commit()
        await db.refresh(system)
        
        # Build response
        system_dict = {
            "system_id": system.system_id,
            "name": system.name,
            "description": system.description,
            "version": system.version,
            "system_type": system.system_type,
            "compliance_frameworks": system.compliance_frameworks or [],
            "model_config_id": system.model_config_id,
            "industry": getattr(system, 'industry', None),
            "created_at": system.created_at,
            "updated_at": system.updated_at,
            "user_id": system.user_id,
            "model_name": model_name,
            "status": "active",
            "last_tested": None,
            "compliance_scores": {}
        }
        
        logger.info("Created AI system", system_id=system.system_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=system_dict
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create AI system", name=system_data.name, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create AI system"
        )

@router.put("/systems/{system_id}", response_model=ApiResponse[AISystemResponse])
async def update_ai_system(
    system_id: int,
    system_data: AISystemUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update an AI system."""
    logger.info("Updating AI system", system_id=system_id, user_id=current_user.user_id)
    
    try:
        # Get the existing AI system
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        system = result.scalar_one_or_none()
        
        if not system:
            raise NotFoundError("AI System", system_id)
        
        # Validate model_config_id if provided
        model_config_id = getattr(system_data, 'model_config_id', None)
        model_name = None
        
        if model_config_id:
            model_result = await db.execute(
                text("SELECT name FROM ai_model_configs WHERE config_id = :config_id AND created_by = :user_id"),
                {"config_id": model_config_id, "user_id": current_user.user_id}
            )
            model_row = model_result.fetchone()
            if not model_row:
                raise ValidationError("Invalid model configuration ID")
            model_name = model_row[0]
        elif system.model_config_id:
            # Keep existing model if not updating
            model_result = await db.execute(
                text("SELECT name FROM ai_model_configs WHERE config_id = :config_id"),
                {"config_id": system.model_config_id}
            )
            model_row = model_result.fetchone()
            if model_row:
                model_name = model_row[0]
        
        # Update fields
        update_data = system_data.dict(exclude_unset=True)
        if update_data:
            for field, value in update_data.items():
                setattr(system, field, value)
        
        await db.commit()
        await db.refresh(system)
        
        # Build response
        system_dict = {
            "system_id": system.system_id,
            "name": system.name,
            "description": system.description,
            "version": system.version,
            "system_type": system.system_type,
            "compliance_frameworks": system.compliance_frameworks or [],
            "model_config_id": system.model_config_id,
            "industry": getattr(system, 'industry', None),
            "created_at": system.created_at,
            "updated_at": system.updated_at,
            "user_id": system.user_id,
            "model_name": model_name,
            "status": "active",
            "last_tested": None,
            "compliance_scores": {}
        }
        
        logger.info("Updated AI system", system_id=system_id, user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=system_dict
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI System {system_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to update AI system", system_id=system_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update AI system"
        )

@router.delete("/systems/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_system(
    system_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Delete an AI system."""
    logger.info("Deleting AI system", system_id=system_id, user_id=current_user.user_id)
    
    try:
        # Check if system exists and belongs to user
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        system = result.scalar_one_or_none()
        
        if not system:
            raise NotFoundError("AI System", system_id)
        
        # Delete the system
        await db.execute(
            delete(AISystem).where(AISystem.system_id == system_id)
        )
        await db.commit()
        
        logger.info("Deleted AI system", system_id=system_id, user_id=current_user.user_id)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI System {system_id} not found"
        )
    except Exception as e:
        logger.error("Failed to delete AI system", system_id=system_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete AI system"
        )

class TestExecutionRequest(BaseModel):
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    # Test Subject Configuration
    test_subject_model_id: Optional[int] = None  # If None, use system's default model_config_id
    test_prompts: str  # Prompt(s) to send to test subject
    
    # Evaluator Configuration  
    evaluators: List[str]  # Which evaluators to run
    evaluator_model_id: int  # AI model to power the evaluators
    
    # Test Parameters (can override model defaults)
    test_subject_params: Optional[Dict[str, Any]] = {}  # Override test subject model defaults
    evaluator_params: Optional[Dict[str, Any]] = {}     # Override evaluator model defaults
    
    # Legacy fields for backward compatibility
    evaluatorModelId: Optional[int] = None  # Deprecated: use evaluator_model_id
    maxTokens: int = 1000     # Deprecated: use test_subject_params
    temperature: float = 0.7  # Deprecated: use test_subject_params
    
    # Test Execution Settings
    iterations: int = 1
    concurrent_evaluators: bool = True
    save_intermediate_results: bool = True
    
    def model_post_init(self, __context) -> None:
        """Post-initialization to handle legacy field mappings."""
        # Handle legacy evaluatorModelId field
        if self.evaluatorModelId and not self.evaluator_model_id:
            self.evaluator_model_id = self.evaluatorModelId
        
        # Handle legacy maxTokens and temperature in test_subject_params
        if not self.test_subject_params:
            self.test_subject_params = {}
        
        if 'max_tokens' not in self.test_subject_params:
            self.test_subject_params['max_tokens'] = self.maxTokens
            
        if 'temperature' not in self.test_subject_params:
            self.test_subject_params['temperature'] = self.temperature

async def _resolve_model_config(db: AsyncSession, model_config_id: int) -> Optional[Dict[str, Any]]:
    """Resolve AI model configuration from database."""
    try:
        result = await db.execute(
            select(AIModelConfig).where(AIModelConfig.config_id == model_config_id)
        )
        model_config = result.scalar_one_or_none()
        
        if not model_config:
            return None
        
        return {
            "config_id": model_config.config_id,
            "name": model_config.name,
            "provider": model_config.provider,
            "model_id": model_config.model_id,
            "api_key": model_config.api_key,
            "api_key_id": model_config.api_key_id if hasattr(model_config, 'api_key_id') else None,
            "api_url": model_config.api_url,
            "temperature": float(model_config.temperature) if model_config.temperature else 0.7,
            "max_tokens": model_config.max_tokens or 1000,
            "timeout": model_config.timeout or 30,
            "max_retries": model_config.max_retries or 3,
            "retry_delay": float(model_config.retry_delay) if model_config.retry_delay else 1.0,
            "provider_options": model_config.provider_options or {},
            # Include additional unified API fields (consistent with model_configs.py)
            "top_p": float(model_config.top_p) if hasattr(model_config, 'top_p') and model_config.top_p else 1.0,
            "frequency_penalty": float(model_config.frequency_penalty) if hasattr(model_config, 'frequency_penalty') and model_config.frequency_penalty else 0.0,
            "presence_penalty": float(model_config.presence_penalty) if hasattr(model_config, 'presence_penalty') and model_config.presence_penalty else 0.0,
            "enabled": model_config.enabled
        }
    except Exception as e:
        logger.error(f"Failed to resolve model config {model_config_id}: {e}")
        return None

def _create_unified_api_config(model_config: Dict[str, Any], param_overrides: Dict[str, Any] = None) -> ModelConfig:
    """Create ModelConfig for unified API from database model config (consistent with model_configs.py)."""
    if not UNIFIED_API_AVAILABLE:
        raise RuntimeError("Unified API not available")
    
    # Start with base ModelConfig parameters (universal across all providers)
    config_data = {
        "provider": model_config["provider"],
        "model_id": model_config["model_id"],
        "api_key": model_config["api_key"],
        "temperature": model_config["temperature"],
        "max_tokens": model_config["max_tokens"],
        "timeout": model_config.get("timeout", 30),
        "max_retries": model_config.get("max_retries", 3),
        "retry_delay": model_config.get("retry_delay", 1.0),
    }
    
    # All provider-specific options go in provider_options
    # This allows ANY provider to handle their own specific parameters
    config_data["provider_options"] = dict(model_config.get("provider_options", {}))
    
    # Add API URL if specified
    if model_config.get("api_url"):
        config_data["api_url"] = model_config["api_url"]
    
    # Apply parameter overrides (from test request)
    if param_overrides:
        config_data.update(param_overrides)
    
    return ModelConfig(**config_data)

async def _call_test_subject_model(
    unified_api, 
    model_config: ModelConfig, 
    test_prompt: str
) -> Optional[str]:
    """Call test subject model via unified API (consistent with model_configs.py approach)."""
    try:
        logger.info(f"Calling test subject model: {model_config.provider}/{model_config.model_id}")
        
        # Use the same method as model_configs.py test endpoint
        response = await unified_api.agenerate(
            prompt=test_prompt,
            config=model_config
        )
        
        if response.error:
            logger.error(f"Test subject model call failed: {response.error.message} ({response.error.type})")
            return None
        
        logger.info(f"Test subject model responded successfully: {len(response.content)} characters")
        return response.content
        
    except Exception as e:
        logger.error(f"Failed to call test subject model: {e}")
        return None

async def _update_test_execution_status(
    db: AsyncSession,
    execution_id: str,
    status: str,
    error_message: str = None,
    score: float = None,
    result: str = None,
    details: dict = None
):
    """Update test execution status in compliance_test_executions table."""
    try:
        # Convert execution_id to int for database query
        execution_id_int = int(execution_id) if execution_id.isdigit() else None
        
        # If execution_id is not a number, we can't update the DB record
        # This is a fallback case for when DB insert failed
        if not execution_id_int:
            logger.warning(f"Cannot update test execution status: execution_id '{execution_id}' is not a number")
            return
        
        update_data = {
            "status": status,
            "completed_at": datetime.utcnow()
        }
        if error_message:
            update_data["error_message"] = error_message
        if score is not None:
            update_data["score"] = score
        if result:
            update_data["result"] = result
        if details:
            update_data["details"] = details
        
        await db.execute(
            text("""
                UPDATE compliance_test_executions
                SET status = :status,
                    completed_at = :completed_at,
                    error_message = COALESCE(:error_message, error_message),
                    score = COALESCE(:score, score),
                    result = COALESCE(:result, result),
                    details = COALESCE(:details, details)
                WHERE execution_id = :execution_id
            """),
            {
                "execution_id": execution_id_int,
                "status": status,
                "completed_at": datetime.utcnow(),
                "error_message": error_message,
                "score": score,
                "result": result,
                "details": json.dumps(details) if details else None
            }
        )
        await db.commit()
        logger.info("Test execution status updated", execution_id=execution_id, status=status)
    except Exception as e:
        logger.error("Failed to update test execution status", execution_id=execution_id, error=str(e))
        await db.rollback()

async def _run_compliance_test_sync(
    system_id: int,
    test_request: TestExecutionRequest,
    user_id: int,
    db: AsyncSession
) -> Dict[str, Any]:
    """Run compliance test synchronously and return results directly."""
    logger.info("Starting synchronous compliance test", system_id=system_id, user_id=user_id)
    
    try:
        # 1. GET AI SYSTEM
        result = await db.execute(
            select(AISystem).where(AISystem.system_id == system_id)
        )
        system = result.scalar_one_or_none()
        
        if not system:
            return {
                "testId": f"test_{system_id}_{int(time.time())}",
                "status": "failed",
                "error": "System not found",
                "systemId": system_id
            }
        
        # 2. DETERMINE TEST SUBJECT MODEL
        test_subject_model_id = test_request.test_subject_model_id or system.model_config_id
        if not test_subject_model_id:
            return {
                "testId": f"test_{system_id}_{int(time.time())}",
                "status": "failed",
                "error": "No test subject model specified",
                "systemId": system_id
            }
        
        # 3. RESOLVE MODEL CONFIGURATIONS
        test_subject_config = await _resolve_model_config(db, test_subject_model_id)
        evaluator_config = await _resolve_model_config(db, test_request.evaluator_model_id)
        
        if not test_subject_config:
            return {
                "testId": f"test_{system_id}_{int(time.time())}",
                "status": "failed",
                "error": f"Test subject model config {test_subject_model_id} not found or missing API key",
                "systemId": system_id
            }
            
        if not evaluator_config:
            return {
                "testId": f"test_{system_id}_{int(time.time())}",
                "status": "failed",
                "error": f"Evaluator model config {test_request.evaluator_model_id} not found or missing API key",
                "systemId": system_id
            }
        
        logger.info(f"Using test subject model: {test_subject_config['provider']}/{test_subject_config['model_id']}")
        logger.info(f"Using evaluator model: {evaluator_config['provider']}/{evaluator_config['model_id']}")
        
        # 4. CALL TEST SUBJECT MODEL VIA UNIFIED API
        test_subject_response = None
        if UNIFIED_API_AVAILABLE:
            try:
                unified_api = get_unified_api()
                test_subject_model_config = _create_unified_api_config(
                    test_subject_config, 
                    test_request.test_subject_params
                )
                
                test_subject_response = await _call_test_subject_model(
                    unified_api, 
                    test_subject_model_config, 
                    test_request.test_prompts
                )
                
                if test_subject_response:
                    logger.info(f"Test subject responded with {len(test_subject_response)} characters")
                else:
                    logger.warning("Test subject returned no response")
            except Exception as e:
                logger.error(f"Test subject model call failed: {e}")
                return {
                    "testId": f"test_{system_id}_{int(time.time())}",
                    "status": "failed",
                    "error": f"Test subject model call failed: {str(e)}",
                    "systemId": system_id
                }
        else:
            logger.warning("Unified API not available, skipping test subject call")
        
        # 5. RUN EVALUATORS
        evaluator_factory = EvaluatorFactory()
        evaluator_results = {}
        
        for evaluator_name in test_request.evaluators:
            try:
                evaluator = evaluator_factory.get_evaluator(evaluator_name)
                if evaluator:
                    evaluation_result = await evaluator.aevaluate(
                        text=test_subject_response or "No response from test subject",
                        test_subject_config=test_subject_config,
                        evaluator_llm_config=_create_unified_api_config(evaluator_config, test_request.evaluator_params)
                    )
                    evaluator_results[evaluator_name] = {
                        "result": evaluation_result,
                        "status": "completed"
                    }
                    logger.info(f"Evaluator {evaluator_name} completed")
            except Exception as e:
                logger.error(f"Evaluator {evaluator_name} failed: {e}")
                evaluator_results[evaluator_name] = {
                    "result": {"error": str(e)},
                    "status": "failed"
                }
        
        # 6. COMPOSE FINAL RESULT
        final_result = {
            "testId": f"test_{system_id}_{int(time.time())}",
            "status": "completed",
            "systemId": system_id,
            "test_subject_model": {
                "name": test_subject_config["name"],
                "model_id": test_subject_config["model_id"],
                "provider": test_subject_config["provider"],
                "config_id": test_subject_model_id
            },
            "test_subject_response": test_subject_response,
            "evaluator_model": {
                "name": evaluator_config["name"],
                "model_id": evaluator_config["model_id"],
                "provider": evaluator_config["provider"],
                "config_id": test_request.evaluator_model_id
            },
            "evaluator_results": evaluator_results,
            "test_prompts": test_request.test_prompts,
            "evaluators": test_request.evaluators,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info("Synchronous test completed successfully", system_id=system_id)
        return final_result
        
    except Exception as e:
        logger.error("Synchronous test execution failed", system_id=system_id, error=str(e))
        return {
            "testId": f"test_{system_id}_{int(time.time())}",
            "status": "failed",
            "error": str(e),
            "systemId": system_id
        }


async def _run_compliance_test_background(
    system_id: int,
    execution_id: str,
    test_request: TestExecutionRequest,
    user_id: int,
    db: AsyncSession
):
    """Background task to run the actual compliance test with unified API integration."""
    logger.info("Starting background compliance test", execution_id=execution_id, system_id=system_id)
    
    try:
        # 1. GET AI SYSTEM
        result = await db.execute(
            select(AISystem).where(AISystem.system_id == system_id)
        )
        system = result.scalar_one_or_none()
        
        if not system:
            logger.error("System not found in background task", system_id=system_id)
            await _update_test_execution_status(db, execution_id, "failed", "System not found")
            return
        
        # 2. DETERMINE TEST SUBJECT MODEL
        test_subject_model_id = test_request.test_subject_model_id or system.model_config_id
        if not test_subject_model_id:
            logger.error("No test subject model specified and system has no default model", system_id=system_id)
            await _update_test_execution_status(db, execution_id, "failed", "No test subject model specified")
            return
        
        # 3. RESOLVE MODEL CONFIGURATIONS
        test_subject_config = await _resolve_model_config(db, test_subject_model_id)
        evaluator_config = await _resolve_model_config(db, test_request.evaluator_model_id)
        
        if not test_subject_config:
            error_msg = f"Test subject model config {test_subject_model_id} not found or missing API key"
            logger.error(error_msg, model_id=test_subject_model_id)
            await _update_test_execution_status(db, execution_id, "failed", error_msg)
            return
            
        if not evaluator_config:
            error_msg = f"Evaluator model config {test_request.evaluator_model_id} not found or missing API key"
            logger.error(error_msg, model_id=test_request.evaluator_model_id)
            await _update_test_execution_status(db, execution_id, "failed", error_msg)
            return
        
        logger.info(f"Using test subject model: {test_subject_config['provider']}/{test_subject_config['model_id']}")
        logger.info(f"Using evaluator model: {evaluator_config['provider']}/{evaluator_config['model_id']}")
        
        # 4. CALL TEST SUBJECT MODEL VIA UNIFIED API (consistent with model_configs.py)
        test_subject_response = None
        if UNIFIED_API_AVAILABLE:
            try:
                # Use the same pattern as model_configs.py
                unified_api = get_unified_api()
                test_subject_model_config = _create_unified_api_config(
                    test_subject_config, 
                    test_request.test_subject_params
                )
                
                test_subject_response = await _call_test_subject_model(
                    unified_api, 
                    test_subject_model_config, 
                    test_request.test_prompts
                )
                
                if test_subject_response:
                    logger.info(f"Test subject responded with {len(test_subject_response)} characters")
                else:
                    logger.error("Test subject model returned no response")
                    await _update_test_execution_status(db, execution_id, "failed", "Test subject model returned no response")
                    return
                    
            except ImportError as e:
                logger.error(f"Unified API import failed: {e}")
                await _update_test_execution_status(db, execution_id, "failed", f"Unified API import failed: {e}")
                return
            except Exception as e:
                logger.error(f"Failed to call test subject model via unified API: {e}")
                await _update_test_execution_status(db, execution_id, "failed", f"Test subject model call failed: {e}")
                return
        else:
            logger.error("Unified API not available - cannot call test subject model")
            await _update_test_execution_status(db, execution_id, "failed", "Unified API not available")
            return
        
        # 5. RUN EVALUATORS WITH TEST SUBJECT RESPONSE
        evaluator_factory = EvaluatorFactory()
        test_results = {}
        
        for evaluator_name in test_request.evaluators:
            try:
                logger.info(f"Running evaluator: {evaluator_name}")
                
                # Get the evaluator instance
                evaluator = evaluator_factory.get_evaluator(evaluator_name)
                if not evaluator:
                    logger.warning(f"Evaluator not found: {evaluator_name}")
                    continue
                
                # Create evaluator model config for unified API
                evaluator_model_config = _create_unified_api_config(
                    evaluator_config,
                    test_request.evaluator_params
                )
                
                # Run evaluation with test subject response
                evaluation_result = await evaluator.aevaluate(
                    text=test_subject_response,
                    test_subject_config=test_subject_model_config,  # For context
                    evaluator_llm_config=evaluator_model_config,    # For LLM-as-judge
                    **test_request.evaluator_params
                )
                
                test_results[evaluator_name] = {
                    "status": "completed",
                    "result": evaluation_result,
                    "execution_time": time.time()  # Add timestamp
                }
                
                logger.info(f"Evaluator {evaluator_name} completed successfully")
                
            except Exception as e:
                logger.error(f"Evaluator {evaluator_name} failed", error=str(e))
                test_results[evaluator_name] = {
                    "status": "failed", 
                    "error": str(e),
                    "execution_time": time.time()
                }
        
        # 6. PREPARE FINAL RESULTS
        final_results = {
            "execution_id": execution_id,
            "system_id": system_id,
            "test_subject_model": {
                "config_id": test_subject_model_id,
                "provider": test_subject_config["provider"],
                "model_id": test_subject_config["model_id"],
                "name": test_subject_config["name"]
            },
            "evaluator_model": {
                "config_id": test_request.evaluator_model_id,
                "provider": evaluator_config["provider"],
                "model_id": evaluator_config["model_id"],
                "name": evaluator_config["name"]
            },
            "test_prompts": test_request.test_prompts,
            "test_subject_response": test_subject_response,
            "evaluator_results": test_results,
            "metadata": {
                "iterations": test_request.iterations,
                "concurrent_evaluators": test_request.concurrent_evaluators,
                "test_subject_params": test_request.test_subject_params,
                "evaluator_params": test_request.evaluator_params,
                "completed_at": datetime.utcnow().isoformat()
            }
        }
        
        logger.info(f"Background test completed", execution_id=execution_id, results_count=len(test_results))
        
        # Save final_results to database for later retrieval
        await _update_test_execution_status(
            db, 
            execution_id, 
            "completed",
            score=_calculate_overall_score(test_results),
            result="passed" if _calculate_overall_score(test_results) >= 70 else "failed",
            details=final_results
        )
        
    except Exception as e:
        logger.error("Background compliance test failed", execution_id=execution_id, error=str(e))
        import traceback
        logger.error(traceback.format_exc())
        await _update_test_execution_status(db, execution_id, "failed", str(e))

def _calculate_overall_score(test_results: Dict[str, Any]) -> float:
    """Calculate overall score from evaluator results.

    Each entry is {"status", "result": <evaluator dict>} — read the nested
    result and prefer the evaluator's declared primary_output_key.
    """
    if not test_results:
        return 0.0

    scores = []
    for evaluator_name, wrapper in test_results.items():
        result = (wrapper or {}).get("result") if isinstance(wrapper, dict) else wrapper
        if not isinstance(result, dict):
            continue
        try:
            key = EvaluatorFactory.get_evaluator(evaluator_name).get_metadata().primary_output_key
        except Exception:
            key = None
        for candidate in (key, "compliance_score", "score"):
            if candidate and isinstance(result.get(candidate), (int, float)):
                scores.append(result[candidate])
                break

    if not scores:
        return 0.0

    return sum(scores) / len(scores)

@router.post("/systems/{system_id}/test-unified", response_model=ApiResponse[Dict[str, Any]])
async def run_system_test_unified(
    system_id: int,
    test_request: TestExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen),
    auth_manager: None = Depends(setup_unified_api_auth_dependency)
):
    """Run compliance tests on an AI system via unified API (legacy path)."""
    logger.info("Running unified test on AI system", system_id=system_id, user_id=current_user.user_id)
    
    try:
        # Get the AI system
        result = await db.execute(
            select(AISystem).where(
                AISystem.system_id == system_id,
                AISystem.user_id == current_user.user_id
            )
        )
        system = result.scalar_one_or_none()
        
        if not system:
            raise NotFoundError("AI System", system_id)
        
        # Validate evaluators
        evaluator_factory = EvaluatorFactory()
        valid_evaluators = []
        for evaluator_name in test_request.evaluators:
            if evaluator_factory.get_evaluator(evaluator_name):
                valid_evaluators.append(evaluator_name)
            else:
                logger.warning(f"Invalid evaluator requested: {evaluator_name}")
        
        if not valid_evaluators:
            raise ValidationError("No valid evaluators specified")
        
        # Run test synchronously and return results directly
        logger.info("Running unified test synchronously", system_id=system_id, user_id=current_user.user_id)
        
        # Execute the test
        test_result = await _run_compliance_test_sync(
            system_id,
            test_request,
            current_user.user_id,
            db
        )

        # Persist completed execution — coverage matrix + audit trail read these rows
        try:
            eval_results = test_result.get("evaluator_results", {})
            score = _calculate_overall_score(eval_results)
            subject = test_result.get("test_subject_model", {})
            judge = test_result.get("evaluator_model", {})
            await db.execute(
                text("""
                    INSERT INTO compliance_test_executions
                        (system_id, test_name, test_type, framework, status, config_id,
                         evaluator_model, evaluator_provider, score, result, details,
                         started_at, completed_at, created_by)
                    VALUES (:sid, :name, :type, :fw, 'completed', :cid, :emodel, :eprov,
                            :score, :res, :details, NOW(), NOW(), :uid)
                """),
                {
                    "sid": system_id,
                    "name": ",".join(test_request.evaluators)[:100] or "unified-eval",
                    "type": "unified",
                    "fw": "probe",
                    "cid": subject.get("config_id"),
                    "emodel": judge.get("model_id"),
                    "eprov": judge.get("provider"),
                    "score": score,
                    "res": "passed" if score >= 70 else "failed",
                    "details": json.dumps(test_result),
                    "uid": current_user.user_id,
                }
            )
            await db.commit()
        except Exception as e:
            # persistence failure must not fail the eval run itself
            logger.warning("Failed to persist test execution", error=str(e))

        return ApiResponse(
            success=True,
            data=test_result,
            message="Test execution completed"
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI System {system_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to run unified test on AI system", system_id=system_id, user_id=current_user.user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start test execution"
        )


@router.get("/systems/{system_id}/test-unified/{execution_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_test_execution_result(
    system_id: int,
    execution_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get the result of a test execution."""
    try:
        # Convert execution_id to int for database query
        execution_id_int = int(execution_id) if execution_id.isdigit() else None
        if not execution_id_int:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid execution_id format"
            )

        # Get the test execution record
        result = await db.execute(
            text("""
                SELECT * FROM compliance_test_executions
                WHERE execution_id = :execution_id AND system_id = :system_id
            """),
            {"execution_id": execution_id_int, "system_id": system_id}
        )
        execution_row = result.fetchone()

        if not execution_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test execution {execution_id} not found"
            )

        # Return the execution record including details
        execution_data = {
            "execution_id": execution_row[0],
            "system_id": execution_row[1],
            "test_name": execution_row[2],
            "test_type": execution_row[3],
            "framework": execution_row[4],
            "status": execution_row[5],
            "config_id": execution_row[6],
            "evaluator_model": execution_row[7],
            "evaluator_provider": execution_row[8],
            "score": float(execution_row[9]) if execution_row[9] else None,
            "result": execution_row[10],
            "details": execution_row[11],
            "error_message": execution_row[12],
            "started_at": execution_row[13].isoformat() if execution_row[13] else None,
            "completed_at": execution_row[14].isoformat() if execution_row[14] else None,
            "created_at": execution_row[15].isoformat() if execution_row[15] else None,
            "created_by": execution_row[16]
        }

        return ApiResponse(
            success=True,
            data=execution_data,
            message="Test execution result retrieved"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get test execution result", execution_id=execution_id, system_id=system_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve test execution result"
        )


@router.get("/systems/{system_id}/tests/{test_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_system_test_result(
    system_id: int,
    test_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get the result of a system test (alias for frontend compatibility)."""
    return await get_test_execution_result(system_id, test_id, current_user, db)