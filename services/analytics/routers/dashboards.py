"""Dashboard API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import structlog

from ...shared.auth import get_current_user
from ...shared.schemas import UserResponse
from ..services.analytics_service import analytics_service

logger = structlog.get_logger()
router = APIRouter()

@router.get("/overview")
async def get_dashboard_overview(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get dashboard overview with key metrics."""
    try:
        metrics = await analytics_service.get_dashboard_metrics(
            user_id=current_user.user_id,
            time_range=time_range
        )
        
        return {
            "success": True,
            "data": metrics
        }
        
    except Exception as e:
        logger.error("Failed to get dashboard overview", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "DASHBOARD_ERROR",
                    "message": "Failed to retrieve dashboard overview"
                }
            }
        )

@router.get("/compliance-status")
async def get_compliance_status(
    system_ids: Optional[List[int]] = Query(None),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get real-time compliance status for systems."""
    try:
        # This would query the latest test results for each system
        # For now, return placeholder data
        compliance_status = {
            "systems": [
                {
                    "system_id": 1,
                    "system_name": "Customer Service Bot",
                    "status": "compliant",
                    "last_tested": "2025-01-28T10:30:00Z",
                    "compliance_score": 0.89,
                    "risk_level": "low",
                    "issues": []
                },
                {
                    "system_id": 2,
                    "system_name": "Content Moderation AI",
                    "status": "warning",
                    "last_tested": "2025-01-28T09:15:00Z",
                    "compliance_score": 0.72,
                    "risk_level": "medium",
                    "issues": ["PII detection needs improvement"]
                },
                {
                    "system_id": 3,
                    "system_name": "Recommendation Engine",
                    "status": "non_compliant",
                    "last_tested": "2025-01-28T08:45:00Z",
                    "compliance_score": 0.58,
                    "risk_level": "high",
                    "issues": ["Bias detected in recommendations", "EU AI Act violations"]
                }
            ],
            "summary": {
                "total_systems": 3,
                "compliant": 1,
                "warning": 1,
                "non_compliant": 1,
                "overall_score": 0.73
            }
        }
        
        return {
            "success": True,
            "data": compliance_status
        }
        
    except Exception as e:
        logger.error("Failed to get compliance status", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "DASHBOARD_ERROR",
                    "message": "Failed to retrieve compliance status"
                }
            }
        )

@router.get("/risk-heatmap")
async def get_risk_heatmap(
    time_range: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get risk heatmap data for visualization."""
    try:
        # This would analyze test results to create a risk heatmap
        # For now, return placeholder data
        heatmap_data = {
            "categories": [
                "EU AI Act",
                "PII Detection",
                "Bias Detection",
                "Hallucination",
                "Safety",
                "Transparency"
            ],
            "systems": [
                "Customer Service Bot",
                "Content Moderation AI",
                "Recommendation Engine",
                "Document Analyzer"
            ],
            "risk_matrix": [
                [0.1, 0.2, 0.8, 0.3],  # EU AI Act
                [0.3, 0.7, 0.4, 0.2],  # PII Detection
                [0.2, 0.5, 0.9, 0.1],  # Bias Detection
                [0.4, 0.3, 0.6, 0.5],  # Hallucination
                [0.1, 0.4, 0.7, 0.2],  # Safety
                [0.3, 0.2, 0.5, 0.4]   # Transparency
            ],
            "color_scale": {
                "low": "#22c55e",      # Green
                "medium": "#f59e0b",   # Yellow
                "high": "#ef4444",     # Red
                "critical": "#7c2d12"  # Dark red
            },
            "time_range": time_range
        }
        
        return {
            "success": True,
            "data": heatmap_data
        }
        
    except Exception as e:
        logger.error("Failed to get risk heatmap", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "DASHBOARD_ERROR",
                    "message": "Failed to retrieve risk heatmap"
                }
            }
        )

@router.get("/alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get active alerts and notifications."""
    try:
        # This would query active alerts from the system
        # For now, return placeholder data
        alerts = {
            "active_alerts": [
                {
                    "id": 1,
                    "severity": "critical",
                    "title": "EU AI Act Compliance Failure",
                    "message": "Recommendation Engine failed EU AI Act compliance test",
                    "system_id": 3,
                    "system_name": "Recommendation Engine",
                    "created_at": "2025-01-28T08:45:00Z",
                    "acknowledged": False
                },
                {
                    "id": 2,
                    "severity": "high",
                    "title": "Bias Detection Alert",
                    "message": "Potential bias detected in content moderation responses",
                    "system_id": 2,
                    "system_name": "Content Moderation AI",
                    "created_at": "2025-01-28T09:15:00Z",
                    "acknowledged": False
                },
                {
                    "id": 3,
                    "severity": "medium",
                    "title": "PII Leakage Warning",
                    "message": "Possible PII exposure in customer service responses",
                    "system_id": 1,
                    "system_name": "Customer Service Bot",
                    "created_at": "2025-01-28T10:00:00Z",
                    "acknowledged": True
                }
            ],
            "summary": {
                "total_alerts": 3,
                "critical": 1,
                "high": 1,
                "medium": 1,
                "low": 0,
                "unacknowledged": 2
            }
        }
        
        # Filter by severity if specified
        if severity:
            alerts["active_alerts"] = [
                alert for alert in alerts["active_alerts"] 
                if alert["severity"] == severity
            ]
            
        # Apply limit
        alerts["active_alerts"] = alerts["active_alerts"][:limit]
        
        return {
            "success": True,
            "data": alerts
        }
        
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "DASHBOARD_ERROR",
                    "message": "Failed to retrieve active alerts"
                }
            }
        )