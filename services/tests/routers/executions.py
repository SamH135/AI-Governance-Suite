"""Test execution management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from services.shared.database import db_manager
from services.shared.auth import get_current_active_user
from services.shared.models import TestExecution, AISystem
from services.shared.schemas import (
    UserResponse, TestExecutionCreate, TestExecutionResponse,
    ApiResponse, PaginatedResponse
)
from services.shared.exceptions import NotFoundError, ValidationError
from services.tests.services.test_executor import test_executor

logger = structlog.get_logger()
router = APIRouter()

@router.post("/", response_model=ApiResponse[TestExecutionResponse])
async def create_test_execution(
    execution_data: TestExecutionCreate,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Create and start a new test execution."""
    
    # Verify AI system exists and belongs to user
    result = await db.execute(
        select(AISystem).where(
            AISystem.system_id == execution_data.system_id,
            AISystem.user_id == current_user.user_id
        )
    )
    ai_system = result.scalar_one_or_none()
    
    if not ai_system:
        raise NotFoundError("AI System", execution_data.system_id)
    
    # Create execution record
    execution = TestExecution(
        system_id=execution_data.system_id,
        test_suite_name=execution_data.test_suite_name,
        total_tests=execution_data.total_tests,
        created_by=current_user.user_id
    )
    
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    
    # Start execution in background
    background_tasks.add_task(
        run_test_execution,
        execution.execution_id,
        ai_system,
        {"test_config": "default"}  # Would come from request in real implementation
    )
    
    logger.info("Test execution created and started", 
               execution_id=execution.execution_id,
               system_id=execution_data.system_id,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=TestExecutionResponse.model_validate(execution),
        message="Test execution started"
    )

@router.get("/", response_model=ApiResponse[PaginatedResponse])
async def get_test_executions(
    system_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get test executions for the current user."""
    
    # Build query
    query = (
        select(TestExecution)
        .join(AISystem)
        .where(AISystem.user_id == current_user.user_id)
    )
    
    if system_id:
        query = query.where(TestExecution.system_id == system_id)
    if status:
        query = query.where(TestExecution.status == status)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(TestExecution.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    paginated_response = PaginatedResponse(
        items=[TestExecutionResponse.model_validate(exec) for exec in executions],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
    
    return ApiResponse(
        success=True,
        data=paginated_response
    )

@router.get("/{execution_id}", response_model=ApiResponse[TestExecutionResponse])
async def get_test_execution(
    execution_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get a specific test execution."""
    
    result = await db.execute(
        select(TestExecution)
        .join(AISystem)
        .where(
            TestExecution.execution_id == execution_id,
            AISystem.user_id == current_user.user_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise NotFoundError("Test Execution", execution_id)
    
    return ApiResponse(
        success=True,
        data=TestExecutionResponse.model_validate(execution)
    )

@router.get("/{execution_id}/status", response_model=ApiResponse[dict])
async def get_test_execution_status(
    execution_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get status and progress of a test execution (for WebSocket updates)."""
    
    result = await db.execute(
        select(TestExecution)
        .join(AISystem)
        .where(
            TestExecution.execution_id == execution_id,
            AISystem.user_id == current_user.user_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise NotFoundError("Test Execution", execution_id)
    
    # Calculate progress percentage
    progress = 0
    if execution.total_tests and execution.total_tests > 0:
        completed_tests = execution.progress if execution.progress else 0
        progress = min(100, (completed_tests / execution.total_tests) * 100)
    
    status_response = {
        "execution_id": execution.execution_id,
        "status": execution.status,
        "progress": progress,
        "total_tests": execution.total_tests,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "message": f"Test {execution.status}"
    }
    
    return ApiResponse(
        success=True,
        data=status_response
    )

@router.get("/{execution_id}/status", response_model=ApiResponse[dict])
async def get_execution_status(
    execution_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get real-time status of a test execution."""
    
    # Verify execution belongs to user
    result = await db.execute(
        select(TestExecution)
        .join(AISystem)
        .where(
            TestExecution.execution_id == execution_id,
            AISystem.user_id == current_user.user_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise NotFoundError("Test Execution", execution_id)
    
    # Get real-time status from executor
    status = await test_executor.get_execution_status(execution_id)
    
    if not status:
        # Return database status if no real-time status
        status = {
            "status": execution.status,
            "progress": execution.progress,
            "current_test": None,
            "results": []
        }
    
    return ApiResponse(
        success=True,
        data=status
    )

@router.post("/{execution_id}/cancel", response_model=ApiResponse[str])
async def cancel_test_execution(
    execution_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Cancel a running test execution."""
    
    # Verify execution belongs to user
    result = await db.execute(
        select(TestExecution)
        .join(AISystem)
        .where(
            TestExecution.execution_id == execution_id,
            AISystem.user_id == current_user.user_id
        )
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise NotFoundError("Test Execution", execution_id)
    
    # Cancel execution
    cancelled = await test_executor.cancel_execution(execution_id)
    
    if cancelled:
        # Update database
        execution.status = "cancelled"
        await db.commit()
        
        logger.info("Test execution cancelled", 
                   execution_id=execution_id,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data="Execution cancelled",
            message="Test execution has been cancelled"
        )
    else:
        return ApiResponse(
            success=False,
            message="Execution could not be cancelled (may have already completed)"
        )

async def run_test_execution(
    execution_id: int,
    ai_system: AISystem,
    test_config: dict
):
    """Background task to run test execution."""
    
    async with db_manager.get_session() as db:
        try:
            # Get execution
            result = await db.execute(
                select(TestExecution).where(TestExecution.execution_id == execution_id)
            )
            execution = result.scalar_one_or_none()
            
            if not execution:
                logger.error("Execution not found for background task", execution_id=execution_id)
                return
            
            # Update status to running
            execution.status = "running"
            execution.started_at = datetime.utcnow()
            await db.commit()
            
            # Execute test suite
            execution_result = await test_executor.execute_test_suite(
                execution, ai_system, test_config
            )
            
            # Update execution with results
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            execution.progress = 100
            
            await db.commit()
            
            logger.info("Test execution completed successfully", 
                       execution_id=execution_id)
            
        except Exception as e:
            # Update execution status to failed
            async with db_manager.get_session() as error_db:
                error_result = await error_db.execute(
                    select(TestExecution).where(TestExecution.execution_id == execution_id)
                )
                error_execution = error_result.scalar_one_or_none()
                if error_execution:
                    error_execution.status = "failed"
                    error_execution.completed_at = datetime.utcnow()
                    await error_db.commit()
            
            logger.error("Test execution failed", 
                        execution_id=execution_id, error=str(e))