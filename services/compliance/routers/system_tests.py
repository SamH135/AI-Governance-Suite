"""
System-based compliance testing
Implements Node.js test result creation with model configuration
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from services.shared.database import db_manager
from services.shared.auth import get_current_user
from .systems import TestExecutionRequest

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/systems/{system_id}/test")
async def run_system_test(
    system_id: int,
    test_request: TestExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """
    Run compliance test on system using its configured model.
    Uses the same logic as the unified endpoint for consistency.
    """
    from .systems import _run_compliance_test_background
    from services.shared.auth import get_current_active_user
    import time
    
    # Get user_id from current_user object
    user_id = current_user.get('user_id') if isinstance(current_user, dict) else current_user.user_id
    
    try:
        # Check if system exists and belongs to user
        result = await db.execute(
            text("SELECT system_id, name FROM ai_systems WHERE system_id = :system_id AND user_id = :user_id"),
            {"system_id": system_id, "user_id": user_id}
        )
        system_row = result.fetchone()
        
        if not system_row:
            raise HTTPException(404, "System not found")
        
        # Validate that we have an evaluator model
        if not test_request.evaluator_model_id:
            raise HTTPException(400, "evaluator_model_id is required")
        
        # Create test ID
        test_id = f"test_{system_id}_{int(time.time())}"
        
        # Start background task
        background_tasks.add_task(
            _run_compliance_test_background,
            system_id,
            test_id,
            test_request,
            user_id,
            db
        )
        
        return {
            "test_id": test_id,
            "testId": test_id,  # Include both formats for compatibility
            "status": "running",
            "message": f"Test started for system {system_row[1]}",
            "systemId": system_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start test: {e}")
        raise HTTPException(500, f"Failed to start test: {str(e)}")

@router.get("/systems/{system_id}/tests")
async def get_system_tests(
    system_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get all test results for a system"""
    try:
        # Verify system ownership
        result = await db.execute(
            text("SELECT system_id FROM ai_systems WHERE system_id = :system_id AND user_id = :user_id"),
            {"system_id": system_id, "user_id": current_user['user_id']}
        )
        if not result.fetchone():
            raise HTTPException(404, "System not found")

        # Get test results
        result = await db.execute(
            text("""
                SELECT
                    execution_id,
                    test_name,
                    framework,
                    status,
                    score,
                    result,
                    details,
                    evaluator_model,
                    evaluator_provider,
                    started_at,
                    completed_at,
                    created_at
                FROM compliance_test_executions
                WHERE system_id = :system_id
                ORDER BY created_at DESC
                LIMIT 50
            """),
            {"system_id": system_id}
        )
        tests = result.mappings().all()

        return [
            {
                "execution_id": test['execution_id'],
                "test_name": test['test_name'],
                "framework": test['framework'],
                "status": test['status'],
                "score": float(test['score']) if test['score'] else None,
                "result": test['result'],
                "details": test['details'],
                "evaluator_model": test['evaluator_model'],
                "evaluator_provider": test['evaluator_provider'],
                "started_at": test['started_at'],
                "completed_at": test['completed_at'],
                "created_at": test['created_at']
            }
            for test in tests
        ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tests for system {system_id}: {e}")
        raise HTTPException(500, f"Failed to retrieve tests: {str(e)}")

@router.get("/systems/{system_id}/tests/{test_id}")
async def get_test_result(
    system_id: int,
    test_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific test result"""
    try:
        # Get test result with system ownership check
        result = await db.execute(
            text("""
                SELECT
                    cte.*,
                    s.name as system_name
                FROM compliance_test_executions cte
                JOIN ai_systems s ON cte.system_id = s.system_id
                WHERE cte.execution_id = :test_id
                AND cte.system_id = :system_id
                AND s.user_id = :user_id
            """),
            {"test_id": test_id, "system_id": system_id, "user_id": current_user['user_id']}
        )
        test = result.mappings().first()

        if not test:
            raise HTTPException(404, "Test result not found")

        return {
            "execution_id": test['execution_id'],
            "system_id": test['system_id'],
            "system_name": test['system_name'],
            "test_name": test['test_name'],
            "framework": test['framework'],
            "status": test['status'],
            "score": float(test['score']) if test['score'] else None,
            "result": test['result'],
            "details": test['details'],
            "evaluator_model": test['evaluator_model'],
            "evaluator_provider": test['evaluator_provider'],
            "started_at": test['started_at'],
            "completed_at": test['completed_at'],
            "created_at": test['created_at']
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test {test_id}: {e}")
        raise HTTPException(500, f"Failed to retrieve test result: {str(e)}")