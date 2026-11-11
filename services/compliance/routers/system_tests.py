"""
System-based compliance testing
Implements Node.js test result creation with model configuration
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import logging
import json

from services.shared.database import db_manager
from services.shared.auth import get_current_user
from .systems import TestExecutionRequest

logger = logging.getLogger(__name__)
router = APIRouter()

class SystemTestRequest(BaseModel):
    """Test request matching Node.js createTestResult"""
    test_name: str
    framework: str
    evaluator_type: str
    evaluator_model: Optional[str] = "gpt-4"
    evaluator_provider: Optional[str] = "openai"
    test_parameters: Optional[Dict[str, Any]] = {}

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

async def execute_test_with_model(
    test_id: int,
    system: dict,
    test_request: SystemTestRequest
):
    """
    Execute the actual test using the system's model and configured evaluators.
    """
    try:
        from ..framework.core.registry import Registry
        from ..framework.core.model_manager import model_manager
        from shared.unified_api.base import ModelConfig, ModelType
        
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        
        # Get evaluator framework from test request
        framework = test_request.framework or test_request.evaluators[0] if test_request.evaluators else 'generic_compliance'
        
        # Get the evaluator
        evaluator = Registry.get_evaluator(framework)
        
        # Build evaluator LLM config from test request
        evaluator_config = None
        if test_request.evaluator_model_id:
            evaluator_config = ModelConfig(
                provider=test_request.evaluator_provider or 'local',
                model_id=test_request.evaluator_model_id,
                usage_type=ModelType.EVALUATOR
            )
        
        # Get test prompts
        test_prompts = test_request.test_prompts or test_request.testPrompts or [test_request.text] if test_request.text else []
        
        # Run evaluation with actual evaluator
        results = []
        overall_score = 0
        
        for prompt in test_prompts:
            result = evaluator.evaluate(
                text=prompt,
                evaluator_llm_config=evaluator_config
            )
            results.append(result)
            
            # Extract score from result (different evaluators use different field names)
            score = result.get('compliance_score') or result.get('bias_score') or result.get('safety_score') or 0
            overall_score += score
        
        # Calculate average score
        avg_score = overall_score / len(results) if results else 0
        
        # Determine pass/fail based on score
        result_status = "passed" if avg_score >= 70 else "failed"
        
        # Build details from actual evaluator results
        details = {
            "framework": framework,
            "average_score": avg_score,
            "total_evaluations": len(results),
            "individual_results": results
        }
        
        # Store test result in both places for compatibility
        async with db_manager.get_session() as db:
            # 1. Update compliance_test_executions
            await db.execute("""
                UPDATE compliance_test_executions 
                SET status = 'completed',
                    score = $1,
                    result = $2,
                    details = $3,
                    completed_at = NOW()
                WHERE execution_id = $4
            """, avg_score, result_status, json.dumps(details), test_id)
            
            # 2. Store in ai_model_test_results for compatibility
            await db.execute("""
                INSERT INTO ai_model_test_results (
                    config_id,
                    system_id,
                    test_name,
                    result,
                    evaluator_model,
                    evaluator_provider,
                    test_prompt,
                    response_content,
                    success,
                    test_metadata,
                    created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                system['config_id'],
                system['system_id'],
                test_request.test_name or f"{framework} compliance test",
                result_status,
                test_request.evaluator_model or 'local',
                test_request.evaluator_provider or 'local',
                json.dumps(test_prompts),
                json.dumps(results),
                result_status == "passed",
                json.dumps({
                    "score": avg_score,
                    "framework": framework,
                    "details": details
                }),
                1  # system user for background tasks
            )
            await db.commit()
            
        logger.info(f"Test {test_id} completed with score {avg_score}")
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        
        async with db_manager.get_session() as db:
            await db.execute("""
                UPDATE compliance_test_executions 
                SET status = 'failed', 
                    result = 'error',
                    details = $1,
                    completed_at = NOW() 
                WHERE execution_id = $2
            """, json.dumps({"error": str(e)}), test_id)
            await db.commit()

@router.get("/systems/{system_id}/tests")
async def get_system_tests(
    system_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get all test results for a system"""
    try:
        # Verify system ownership
        system = await db.fetchrow("""
            SELECT system_id FROM ai_systems 
            WHERE system_id = $1 AND user_id = $2
        """, system_id, current_user['user_id'])
        
        if not system:
            raise HTTPException(404, "System not found")
        
        # Get test results
        tests = await db.fetch("""
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
            WHERE system_id = $1
            ORDER BY created_at DESC
            LIMIT 50
        """, system_id)
            
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
    test_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific test result"""
    try:
        # Get test result with system ownership check
        test = await db.fetchrow("""
            SELECT 
                cte.*,
                s.name as system_name
            FROM compliance_test_executions cte
            JOIN ai_systems s ON cte.system_id = s.system_id
            WHERE cte.execution_id = $1 
            AND cte.system_id = $2 
            AND s.user_id = $3
        """, test_id, system_id, current_user['user_id'])
            
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