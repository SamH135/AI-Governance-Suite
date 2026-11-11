"""Test orchestration and workflow management endpoints."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from services.shared.database import db_manager
from services.shared.auth import get_current_active_user
from services.shared.models import TestExecution, AISystem, Test, TestResult
from services.shared.schemas import UserResponse, ApiResponse
from services.shared.exceptions import ValidationError
from ..services.test_executor import test_executor, TestType

logger = structlog.get_logger()
router = APIRouter()

@router.get("/test-types", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_available_test_types(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get available test types and their configurations."""
    
    test_types = [
        {
            "type": TestType.COMPLIANCE,
            "name": "Compliance Testing",
            "description": "Test AI systems for regulatory compliance (GDPR, HIPAA, etc.)",
            "required_config": ["framework"],
            "optional_config": ["test_categories", "severity_filter"],
            "estimated_duration": "5-15 minutes"
        },
        {
            "type": TestType.PROMPT_GENERATION,
            "name": "Prompt Generation Testing",
            "description": "Generate and evaluate AI prompts with quality scoring",
            "required_config": ["requirements"],
            "optional_config": ["count", "optimization_params"],
            "estimated_duration": "2-5 minutes"
        },
        {
            "type": TestType.DOCUMENT_GENERATION,
            "name": "Document Generation Testing",
            "description": "Test automated document generation capabilities",
            "required_config": [],
            "optional_config": ["template_id", "format", "data"],
            "estimated_duration": "3-8 minutes"
        },
        {
            "type": TestType.INTEGRATED,
            "name": "Integrated Testing",
            "description": "Run comprehensive tests across all platform capabilities",
            "required_config": [],
            "optional_config": ["include_compliance", "include_prompts", "include_documents"],
            "estimated_duration": "10-30 minutes"
        }
    ]
    
    return ApiResponse(
        success=True,
        data=test_types,
        message=f"Found {len(test_types)} available test types"
    )

@router.post("/validate-config", response_model=ApiResponse[Dict[str, Any]])
async def validate_test_config(
    test_type: str,
    config: Dict[str, Any],
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Validate test configuration before execution."""
    
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "estimated_duration": "Unknown"
    }
    
    try:
        if test_type == TestType.COMPLIANCE:
            # Validate compliance config
            if "framework" not in config:
                validation_result["errors"].append("Framework is required for compliance tests")
                validation_result["valid"] = False
            
            framework = config.get("framework", "").upper()
            if framework not in ["GDPR", "HIPAA", "EU_AI_ACT"]:
                validation_result["warnings"].append(f"Framework '{framework}' may not be fully supported")
            
            validation_result["estimated_duration"] = "5-15 minutes"
            
        elif test_type == TestType.PROMPT_GENERATION:
            # Validate prompt config
            if "requirements" not in config or not config["requirements"].strip():
                validation_result["errors"].append("Requirements are required for prompt generation")
                validation_result["valid"] = False
            
            count = config.get("count", 1)
            if count > 10:
                validation_result["warnings"].append("Large prompt counts may take longer to process")
            
            validation_result["estimated_duration"] = f"{count * 1}-{count * 2} minutes"
            
        elif test_type == TestType.DOCUMENT_GENERATION:
            # Validate document config
            format_type = config.get("format", "html")
            if format_type not in ["html", "pdf", "markdown", "docx"]:
                validation_result["warnings"].append(f"Format '{format_type}' may not be supported")
            
            validation_result["estimated_duration"] = "3-8 minutes"
            
        elif test_type == TestType.INTEGRATED:
            # Validate integrated config
            if not any(config.get(key, False) for key in ["include_compliance", "include_prompts", "include_documents"]):
                validation_result["warnings"].append("No test types selected for integrated testing")
            
            validation_result["estimated_duration"] = "10-30 minutes"
            
        else:
            validation_result["errors"].append(f"Unknown test type: {test_type}")
            validation_result["valid"] = False
        
        logger.info("Test configuration validated", 
                   test_type=test_type, 
                   valid=validation_result["valid"],
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=validation_result,
            message="Configuration validation completed"
        )
        
    except Exception as e:
        logger.error("Configuration validation failed", 
                    test_type=test_type, error=str(e))
        raise ValidationError(f"Configuration validation failed: {str(e)}")

@router.get("/analytics/summary", response_model=ApiResponse[Dict[str, Any]])
async def get_test_analytics(
    system_id: int = None,
    days: int = 30,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get test execution analytics and statistics."""
    
    try:
        # Build base query for user's systems
        systems_query = select(AISystem).where(AISystem.user_id == current_user.user_id)
        if system_id:
            systems_query = systems_query.where(AISystem.system_id == system_id)
        
        systems_result = await db.execute(systems_query)
        user_systems = systems_result.scalars().all()
        system_ids = [s.system_id for s in user_systems]
        
        if not system_ids:
            return ApiResponse(
                success=True,
                data={
                    "total_executions": 0,
                    "success_rate": 0,
                    "average_duration": 0,
                    "test_type_distribution": {},
                    "recent_executions": []
                },
                message="No systems found for analytics"
            )
        
        # Get execution statistics
        executions_result = await db.execute(
            select(TestExecution).where(TestExecution.system_id.in_(system_ids))
        )
        executions = executions_result.scalars().all()
        
        # Calculate analytics
        total_executions = len(executions)
        completed_executions = len([e for e in executions if e.status == "completed"])
        success_rate = (completed_executions / total_executions * 100) if total_executions > 0 else 0
        
        # Calculate average duration for completed executions
        durations = []
        for execution in executions:
            if execution.started_at and execution.completed_at:
                duration = (execution.completed_at - execution.started_at).total_seconds()
                durations.append(duration)
        
        average_duration = sum(durations) / len(durations) if durations else 0
        
        # Test type distribution (simplified - would need more detailed tracking)
        test_type_distribution = {
            "compliance": len([e for e in executions if "compliance" in e.test_suite_name.lower()]),
            "prompt": len([e for e in executions if "prompt" in e.test_suite_name.lower()]),
            "document": len([e for e in executions if "document" in e.test_suite_name.lower()]),
            "integrated": len([e for e in executions if "integrated" in e.test_suite_name.lower()])
        }
        
        # Recent executions
        recent_executions = sorted(executions, key=lambda x: x.created_at, reverse=True)[:10]
        recent_data = [
            {
                "execution_id": e.execution_id,
                "test_suite_name": e.test_suite_name,
                "status": e.status,
                "progress": e.progress,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in recent_executions
        ]
        
        analytics = {
            "total_executions": total_executions,
            "completed_executions": completed_executions,
            "failed_executions": len([e for e in executions if e.status == "failed"]),
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(average_duration, 2),
            "test_type_distribution": test_type_distribution,
            "recent_executions": recent_data,
            "systems_analyzed": len(user_systems)
        }
        
        return ApiResponse(
            success=True,
            data=analytics,
            message=f"Analytics for {total_executions} test executions"
        )
        
    except Exception as e:
        logger.error("Test analytics failed", error=str(e))
        raise ValidationError(f"Analytics generation failed: {str(e)}")

@router.get("/health-check", response_model=ApiResponse[Dict[str, Any]])
async def orchestrator_health_check(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Check health of test orchestration services."""
    
    health_status = {
        "orchestrator": "healthy",
        "test_executor": "unknown",
        "services": {
            "compliance": "unknown",
            "prompts": "unknown", 
            "documents": "unknown"
        },
        "dependencies": {
            "database": "unknown",
            "redis": "unknown"
        }
    }
    
    try:
        # Check test executor
        if test_executor.initialized:
            health_status["test_executor"] = "healthy"
        else:
            health_status["test_executor"] = "unhealthy"
        
        # Check service connectivity (simplified)
        if test_executor.service_urls:
            for service_name in health_status["services"]:
                if service_name in test_executor.service_urls:
                    health_status["services"][service_name] = "configured"
        
        # Overall health
        overall_healthy = (
            health_status["test_executor"] == "healthy" and
            all(status != "unhealthy" for status in health_status["services"].values())
        )
        
        health_status["overall"] = "healthy" if overall_healthy else "degraded"
        
        return ApiResponse(
            success=True,
            data=health_status,
            message="Health check completed"
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        health_status["overall"] = "unhealthy"
        health_status["error"] = str(e)
        
        return ApiResponse(
            success=False,
            data=health_status,
            message="Health check failed"
        )