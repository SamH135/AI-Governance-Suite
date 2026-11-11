"""Reports API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import structlog

from ...shared.auth import get_current_user
from ...shared.schemas import UserResponse
from ..services.analytics_service import analytics_service

logger = structlog.get_logger()
router = APIRouter()

@router.get("/compliance")
async def get_compliance_report(
    system_id: Optional[int] = Query(None),
    time_range: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Generate comprehensive compliance report."""
    try:
        report = await analytics_service.get_compliance_report(
            user_id=current_user.user_id,
            system_id=system_id,
            time_range=time_range
        )
        
        return {
            "success": True,
            "data": report
        }
        
    except Exception as e:
        logger.error("Failed to generate compliance report", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "REPORT_ERROR",
                    "message": "Failed to generate compliance report"
                }
            }
        )

@router.get("/executive-summary")
async def get_executive_summary(
    time_range: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Generate executive summary report."""
    try:
        # Get dashboard metrics for summary
        metrics = await analytics_service.get_dashboard_metrics(
            user_id=current_user.user_id,
            time_range=time_range
        )
        
        # Get compliance report for detailed analysis
        compliance = await analytics_service.get_compliance_report(
            user_id=current_user.user_id,
            time_range=time_range
        )
        
        # Create executive summary
        summary = {
            "overview": {
                "total_tests_conducted": metrics["summary"]["total_tests"],
                "systems_monitored": metrics["summary"]["total_systems"],
                "models_evaluated": metrics["summary"]["total_models"],
                "overall_compliance_score": compliance["summary"]["overall_compliance_score"]
            },
            "key_findings": [
                f"Conducted {metrics['summary']['total_tests']} compliance tests across {metrics['summary']['total_systems']} AI systems",
                f"Overall compliance score: {compliance['summary']['overall_compliance_score']:.1%}",
                f"Pass rate: {compliance['summary']['pass_rate']:.1%}",
                f"Critical risks identified: {compliance['risk_distribution']['critical']}"
            ],
            "recommendations": [
                "Focus on addressing critical risk items",
                "Implement regular compliance monitoring",
                "Review and update AI system configurations",
                "Establish continuous improvement processes"
            ],
            "compliance_breakdown": compliance["compliance_by_category"],
            "risk_assessment": compliance["risk_distribution"],
            "time_range": time_range,
            "generated_at": compliance["generated_at"]
        }
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error("Failed to generate executive summary", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "REPORT_ERROR",
                    "message": "Failed to generate executive summary"
                }
            }
        )

@router.get("/audit-trail")
async def get_audit_trail(
    system_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get audit trail for compliance activities."""
    try:
        # This would integrate with the audit logging service
        # For now, return placeholder data
        audit_trail = {
            "total_records": 250,
            "records": [
                {
                    "timestamp": "2025-01-28T10:30:00Z",
                    "action": "test_executed",
                    "system_id": 1,
                    "model_id": 1,
                    "user_id": current_user.id,
                    "details": "EU AI Act compliance test completed",
                    "result": "passed"
                },
                {
                    "timestamp": "2025-01-28T09:15:00Z",
                    "action": "system_updated",
                    "system_id": 1,
                    "user_id": current_user.id,
                    "details": "Updated system configuration",
                    "result": "success"
                },
                {
                    "timestamp": "2025-01-28T08:45:00Z",
                    "action": "test_executed",
                    "system_id": 2,
                    "model_id": 3,
                    "user_id": current_user.id,
                    "details": "PII detection test completed",
                    "result": "failed"
                }
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": True
            }
        }
        
        return {
            "success": True,
            "data": audit_trail
        }
        
    except Exception as e:
        logger.error("Failed to get audit trail", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "AUDIT_ERROR",
                    "message": "Failed to retrieve audit trail"
                }
            }
        )