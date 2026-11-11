"""
Test Execution API Router
Provides endpoints for running compliance tests on AI systems using their model configurations
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
import json

# Import shared services and models
from ..shared.database import get_db_pool
from .auth import get_current_user
from ..shared.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/systems", tags=["test-execution"])

# Pydantic models for requests and responses
class TestExecutionRequest(BaseModel):
    framework: str = Field(..., description="Compliance framework to test (e.g., 'GDPR', 'HIPAA')")
    evaluator: Optional[str] = Field(None, description="Specific evaluator to use")
    test_config: Dict[str, Any] = Field(default_factory=dict, description="Additional test configuration")

class TestExecutionResponse(BaseModel):
    test_id: int
    system_id: int
    framework: str
    status: str = Field(default="running", description="Test execution status")
    message: str = Field(default="Test execution started", description="Status message")
    created_at: datetime

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

@router.post("/{system_id}/test", response_model=TestExecutionResponse, status_code=status.HTTP_201_CREATED)
async def run_system_test(
    system_id: int,
    test_request: TestExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Run a compliance test on an AI system using its configured model."""
    try:
        user_id = current_user["user_id"]
        logger.info(f"Starting compliance test for system {system_id}, framework {test_request.framework}, user {user_id}")
        
        async with db_pool.acquire() as conn:
            # First, verify the AI system exists and belongs to the user
            system_query = """
                SELECT system_id, name, description, system_type, 
                       compliance_frameworks, industry, model_config_id
                FROM ai_systems 
                WHERE system_id = $1 AND user_id = $2
            """
            system_row = await conn.fetchrow(system_query, system_id, user_id)
            
            if not system_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"AI System {system_id} not found"
                )
            
            # Get all model configurations associated with this system
            models_query = """
                SELECT mc.config_id, mc.name, mc.provider, mc.model_id, 
                       mc.api_key, mc.temperature, mc.max_tokens, mc.timeout,
                       smc.model_role, smc.is_primary
                FROM ai_system_model_configs smc
                JOIN ai_model_configs mc ON smc.config_id = mc.config_id
                WHERE smc.system_id = $1
                ORDER BY smc.is_primary DESC, smc.model_role
            """
            models_rows = await conn.fetch(models_query, system_id)
            
            if not models_rows:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"AI System {system_id} does not have any model configurations. Please configure at least one model before running tests."
                )
            
            # Get primary model for test execution (fallback to first model)
            primary_model = None
            for model in models_rows:
                if model["is_primary"]:
                    primary_model = model
                    break
            
            if not primary_model:
                primary_model = models_rows[0]  # Use first model if no primary is set
            
            # Create a test record (simplified structure for gateway implementation)
            test_insert = """
                INSERT INTO compliance_test_executions (
                    system_id, user_id, framework, evaluator, test_config, 
                    status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                RETURNING test_execution_id, created_at
            """
            
            # Create the test_config with system and model information
            enhanced_test_config = {
                **test_request.test_config,
                "system_info": {
                    "system_id": system_row["system_id"],
                    "name": system_row["name"],
                    "system_type": system_row["system_type"],
                    "industry": system_row["industry"],
                    "compliance_frameworks": system_row["compliance_frameworks"]
                },
                "primary_model_config": {
                    "config_id": primary_model["config_id"],
                    "model_name": primary_model["name"],
                    "provider": primary_model["provider"],
                    "model_id": primary_model["model_id"],
                    "temperature": primary_model["temperature"],
                    "max_tokens": primary_model["max_tokens"],
                    "timeout": primary_model["timeout"],
                    "role": primary_model["model_role"]
                },
                "all_models": [
                    {
                        "config_id": model["config_id"],
                        "name": model["name"],
                        "provider": model["provider"],
                        "model_id": model["model_id"],
                        "role": model["model_role"],
                        "is_primary": model["is_primary"]
                    } for model in models_rows
                ]
            }
            
            # Convert any Decimal objects to float for JSON serialization
            def convert_decimals(obj):
                if isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimals(v) for v in obj]
                elif hasattr(obj, '__dict__'):
                    return convert_decimals(obj.__dict__)
                elif str(type(obj)) == "<class 'decimal.Decimal'>":
                    return float(obj)
                else:
                    return obj
            
            enhanced_test_config_json = convert_decimals(enhanced_test_config)
            
            test_row = await conn.fetchrow(
                test_insert,
                system_id,
                user_id, 
                test_request.framework,
                test_request.evaluator or f"{test_request.framework.lower()}_evaluator",
                json.dumps(enhanced_test_config_json),
                "pending"
            )
            
            test_id = test_row["test_execution_id"]
            created_at = test_row["created_at"]
        
        # Create comprehensive system info for background task
        system_info = {
            **dict(system_row),
            "primary_model": dict(primary_model),
            "all_models": [dict(model) for model in models_rows]
        }
        
        # Start the test execution in the background
        background_tasks.add_task(
            execute_compliance_test,
            test_id,
            system_info,
            test_request.framework,
            enhanced_test_config
        )
        
        logger.info(f"Created compliance test {test_id} for system {system_id}")
        
        return TestExecutionResponse(
            test_id=test_id,
            system_id=system_id,
            framework=test_request.framework,
            status="running",
            message=f"Compliance test for {test_request.framework} framework has been started",
            created_at=created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start compliance test for system {system_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start compliance test"
        )

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
                SELECT test_execution_id as result_id, test_execution_id as test_id, 
                       system_id, framework, score, passed, details, 
                       recommendations, status, created_at, updated_at
                FROM compliance_test_executions 
                WHERE system_id = $1 AND user_id = $2 
                ORDER BY created_at DESC
            """
            
            results = await conn.fetch(results_query, system_id, user_id)
            
            test_results = []
            for result in results:
                test_result = TestResultResponse(
                    result_id=result["result_id"],
                    test_id=result["test_id"],
                    system_id=result["system_id"],
                    framework=result["framework"],
                    score=result["score"],
                    passed=result["passed"],
                    details=json.loads(result["details"]) if result["details"] else {},
                    recommendations=json.loads(result["recommendations"]) if result["recommendations"] else [],
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

async def execute_compliance_test(
    test_id: int,
    system_info: dict,
    framework: str,
    test_config: dict
):
    """Background task to execute compliance test using the system's model configuration."""
    db_pool = get_db_pool()
    
    async with db_pool.acquire() as conn:
        try:
            logger.info(f"Executing compliance test {test_id} for framework {framework}")
            logger.info(f"System info type: {type(system_info)}, value: {system_info}")
            logger.info(f"Test config type: {type(test_config)}, keys: {list(test_config.keys()) if test_config else 'None'}")
            
            # Update status to running
            await conn.execute(
                "UPDATE compliance_test_executions SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE test_execution_id = $1",
                test_id
            )

            # Call compliance service evaluator API
            settings = get_settings()
            compliance_service_url = settings.COMPLIANCE_SERVICE_URL

            # Prepare evaluator request
            evaluator_request = {
                "text": test_config.get("test_text", system_info.get("description", "")),
                "llm_config": test_config.get("llm_config", {})
            }

            async with httpx.AsyncClient(timeout=60.0) as http_client:
                evaluator_response = await http_client.post(
                    f"{compliance_service_url}/evaluators/test/{framework}",
                    json=evaluator_request
                )
                evaluator_response.raise_for_status()
                evaluator_data = evaluator_response.json()

            if not evaluator_data.get("success"):
                raise Exception(f"Evaluator failed: {evaluator_data.get('error', 'Unknown error')}")

            evaluator_result = evaluator_data.get("data", {})

            # Convert evaluator result to test results format
            test_results = {
                "status": "completed",
                "score": evaluator_result.get("compliance_score", 0.0),
                "passed": evaluator_result.get("compliance_score", 0.0) >= 70.0,
                "details": {
                    "framework": framework,
                    "evaluator_result": evaluator_result,
                    "system_info": system_info
                },
                "recommendations": evaluator_result.get("recommendations", [])
            }
            
            # Update test record with results
            await conn.execute("""
                UPDATE compliance_test_executions 
                SET status = $1, score = $2, passed = $3, details = $4, 
                    recommendations = $5, updated_at = CURRENT_TIMESTAMP
                WHERE test_execution_id = $6
            """,
                test_results["status"],
                test_results["score"],
                test_results["passed"],
                json.dumps(test_results["details"]),
                json.dumps(test_results["recommendations"]),
                test_id
            )
            
            logger.info(f"Completed compliance test {test_id} with score {test_results['score']}")
            
        except Exception as e:
            logger.error(f"Error executing compliance test {test_id}: {e}")
            # Mark test as failed
            await conn.execute(
                "UPDATE compliance_test_executions SET status = 'failed', error_message = $1, updated_at = CURRENT_TIMESTAMP WHERE test_execution_id = $2",
                str(e), test_id
            )