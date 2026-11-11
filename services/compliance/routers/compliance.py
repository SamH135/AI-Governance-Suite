"""Compliance testing endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import Test, TestResult, AISystem
from ...shared.schemas import (
    UserResponse, TestCreate, TestResponse, TestResultResponse,
    ComplianceResult, ApiResponse
)
from ...shared.exceptions import NotFoundError, ValidationError
from ..services.compliance_service import ComplianceService
from ..services.evaluator_factory import EvaluatorFactory

logger = structlog.get_logger()
router = APIRouter()

@router.post("/tests", response_model=ApiResponse[TestResponse])
async def create_compliance_test(
    test_data: TestCreate,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Create a new compliance test."""
    
    # Verify AI system exists and belongs to user
    result = await db.execute(
        select(AISystem).where(
            AISystem.system_id == test_data.system_id,
            AISystem.user_id == current_user.user_id
        )
    )
    ai_system = result.scalar_one_or_none()
    
    if not ai_system:
        raise NotFoundError("AI System", test_data.system_id)
    
    # Create test record
    test = Test(
        system_id=test_data.system_id,
        framework_id=test_data.framework_id,
        test_name=test_data.test_name,
        test_type=test_data.test_type,
        configuration=test_data.configuration,
        created_by=current_user.user_id
    )
    
    db.add(test)
    await db.commit()
    await db.refresh(test)
    
    # Start compliance test in background
    background_tasks.add_task(
        run_compliance_test,
        test.test_id,
        test_data.configuration
    )
    
    logger.info("Compliance test created", test_id=test.test_id, user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=TestResponse.model_validate(test),
        message="Compliance test created and started"
    )

@router.get("/tests", response_model=ApiResponse[List[TestResponse]])
async def get_compliance_tests(
    system_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get compliance tests for the current user."""
    
    query = select(Test).join(AISystem).where(AISystem.user_id == current_user.user_id)
    
    if system_id:
        query = query.where(Test.system_id == system_id)
    if status:
        query = query.where(Test.status == status)
    
    result = await db.execute(query.order_by(Test.created_at.desc()))
    tests = result.scalars().all()
    
    return ApiResponse(
        success=True,
        data=[TestResponse.model_validate(test) for test in tests]
    )

@router.get("/tests/{test_id}", response_model=ApiResponse[TestResponse])
async def get_compliance_test(
    test_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific compliance test."""
    
    result = await db.execute(
        select(Test).join(AISystem).where(
            Test.test_id == test_id,
            AISystem.user_id == current_user.user_id
        )
    )
    test = result.scalar_one_or_none()
    
    if not test:
        raise NotFoundError("Test", test_id)
    
    return ApiResponse(
        success=True,
        data=TestResponse.model_validate(test)
    )

@router.get("/tests/{test_id}/results", response_model=ApiResponse[List[TestResultResponse]])
async def get_test_results(
    test_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get results for a specific compliance test."""
    
    # Verify test belongs to user
    test_result = await db.execute(
        select(Test).join(AISystem).where(
            Test.test_id == test_id,
            AISystem.user_id == current_user.user_id
        )
    )
    test = test_result.scalar_one_or_none()
    
    if not test:
        raise NotFoundError("Test", test_id)
    
    # Get test results
    results_query = await db.execute(
        select(TestResult).where(TestResult.test_id == test_id)
        .order_by(TestResult.created_at.desc())
    )
    results = results_query.scalars().all()
    
    return ApiResponse(
        success=True,
        data=[TestResultResponse.model_validate(result) for result in results]
    )

@router.post("/tests/{test_id}/run", response_model=ApiResponse[str])
async def run_compliance_test_endpoint(
    test_id: int,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Re-run a compliance test."""
    
    result = await db.execute(
        select(Test).join(AISystem).where(
            Test.test_id == test_id,
            AISystem.user_id == current_user.user_id
        )
    )
    test = result.scalar_one_or_none()
    
    if not test:
        raise NotFoundError("Test", test_id)
    
    # Update test status
    test.status = "pending"
    await db.commit()
    
    # Start test in background
    background_tasks.add_task(
        run_compliance_test,
        test_id,
        test.configuration
    )
    
    logger.info("Compliance test restarted", test_id=test_id, user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data="Test started",
        message="Compliance test has been queued for execution"
    )

@router.post("/evaluate", response_model=ApiResponse[ComplianceResult])
async def evaluate_compliance(
    system_id: int,
    framework: str,
    test_config: dict,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Perform immediate compliance evaluation."""
    
    # Verify AI system exists and belongs to user
    result = await db.execute(
        select(AISystem).where(
            AISystem.system_id == system_id,
            AISystem.user_id == current_user.user_id
        )
    )
    ai_system = result.scalar_one_or_none()
    
    if not ai_system:
        raise NotFoundError("AI System", system_id)
    
    try:
        # Get evaluator
        evaluator = EvaluatorFactory.get_evaluator(framework)
        
        # Run evaluation
        compliance_service = ComplianceService()
        result = await compliance_service.evaluate_system(
            ai_system, evaluator, test_config
        )
        
        logger.info("Compliance evaluation completed", 
                   system_id=system_id, framework=framework, 
                   score=result.overall_score)
        
        return ApiResponse(
            success=True,
            data=result,
            message="Compliance evaluation completed"
        )
        
    except Exception as e:
        logger.error("Compliance evaluation failed", 
                    system_id=system_id, framework=framework, error=str(e))
        raise ValidationError(f"Evaluation failed: {str(e)}")

async def run_compliance_test(test_id: int, configuration: dict):
    """Background task to run compliance test."""
    
    async with db_manager.get_session() as db:
        try:
            # Get test
            result = await db.execute(select(Test).where(Test.test_id == test_id))
            test = result.scalar_one_or_none()
            
            if not test:
                logger.error("Test not found for background execution", test_id=test_id)
                return
            
            # Update status to running
            test.status = "running"
            await db.commit()
            
            # Get AI system
            system_result = await db.execute(
                select(AISystem).where(AISystem.system_id == test.system_id)
            )
            ai_system = system_result.scalar_one_or_none()
            
            if not ai_system:
                test.status = "failed"
                await db.commit()
                logger.error("AI system not found", system_id=test.system_id)
                return
            
            # Run compliance test
            compliance_service = ComplianceService()
            
            # Determine framework from test configuration or use default
            framework = configuration.get("framework", "GDPR")
            evaluator = EvaluatorFactory.get_evaluator(framework)
            
            # Execute evaluation
            result = await compliance_service.evaluate_system(
                ai_system, evaluator, configuration
            )
            
            # Save results
            for test_result_data in result.test_results:
                test_result = TestResult(
                    test_id=test_id,
                    score=test_result_data.score,
                    passed=test_result_data.passed,
                    details=test_result_data.details,
                    recommendations=test_result_data.recommendations
                )
                db.add(test_result)
            
            # Update test status
            test.status = "completed"
            await db.commit()
            
            logger.info("Compliance test completed successfully", 
                       test_id=test_id, overall_score=result.overall_score)
            
        except Exception as e:
            # Update test status to failed
            async with db_manager.get_session() as error_db:
                error_result = await error_db.execute(
                    select(Test).where(Test.test_id == test_id)
                )
                error_test = error_result.scalar_one_or_none()
                if error_test:
                    error_test.status = "failed"
                    await error_db.commit()
            
            logger.error("Compliance test failed", test_id=test_id, error=str(e))