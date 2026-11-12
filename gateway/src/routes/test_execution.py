"""
Test Execution API Router
Provides endpoints for running compliance tests on AI systems using their model configurations
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from datetime import datetime
import json

# Import shared services and models
from ..shared.database import get_db_pool
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/systems", tags=["test-execution"])

class TestResultResponse(BaseModel):
    result_id: int
    test_id: int
    system_id: int
    framework: str
    score: Optional[float] = Field(None, ge=0, le=100)
    passed: Optional[bool] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    status: str
    created_at: datetime

async def get_db_pool_dependency():
    """Dependency to get database pool"""
    return get_db_pool()

@router.get("/{system_id}/tests", response_model=List[TestResultResponse])
async def get_system_test_results(
    system_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Get all test results for a specific AI system."""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Getting test results for system {system_id}, user {user_id}")
        
        async with db_pool.acquire() as conn:
            # Verify the system belongs to the user
            system_check = await conn.fetchrow(
                "SELECT system_id FROM ai_systems WHERE system_id = $1 AND user_id = $2",
                system_id, user_id
            )
            
            if not system_check:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"AI System {system_id} not found"
                )
            
            # Get test results
            results_query = """
                SELECT execution_id as result_id, execution_id as test_id,
                       system_id, framework, score, result, details,
                       status, created_at
                FROM compliance_test_executions
                WHERE system_id = $1 AND created_by = $2
                ORDER BY created_at DESC
            """

            results = await conn.fetch(results_query, system_id, user_id)

            test_results = []
            for result in results:
                details = result["details"]
                if isinstance(details, str):
                    details = json.loads(details)
                test_result = TestResultResponse(
                    result_id=result["result_id"],
                    test_id=result["test_id"],
                    system_id=result["system_id"],
                    framework=result["framework"],
                    score=result["score"],
                    passed=(result["result"] == "passed") if result["result"] else None,
                    details=details or {},
                    recommendations=[],
                    status=result["status"],
                    created_at=result["created_at"]
                )
                test_results.append(test_result)
        
        logger.info(f"Retrieved {len(test_results)} test results for system {system_id}")
        return test_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test results for system {system_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve test results"
        )
