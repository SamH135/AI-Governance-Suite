"""Analytics API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import structlog

from ...shared.auth import get_current_user
from ...shared.schemas import UserResponse
from ..services.analytics_service import analytics_service

logger = structlog.get_logger()
router = APIRouter()

@router.get("/dashboard")
async def get_dashboard_metrics(
    time_range: str = Query("7d", pattern="^(24h|7d|30d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get dashboard metrics for the current user."""
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
        logger.error("Failed to get dashboard metrics", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "ANALYTICS_ERROR",
                    "message": "Failed to retrieve dashboard metrics"
                }
            }
        )

@router.get("/test-analytics")
async def get_test_analytics(
    test_id: Optional[int] = Query(None),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get detailed test analytics."""
    try:
        analytics = await analytics_service.get_test_analytics(
            user_id=current_user.user_id,
            test_id=test_id
        )
        
        return {
            "success": True,
            "data": analytics
        }
        
    except Exception as e:
        logger.error("Failed to get test analytics", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "ANALYTICS_ERROR",
                    "message": "Failed to retrieve test analytics"
                }
            }
        )

@router.get("/performance-trends")
async def get_performance_trends(
    system_id: Optional[int] = Query(None),
    time_range: str = Query("30d", pattern="^(7d|30d|90d)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get performance trends over time."""
    try:
        # This would be implemented in analytics_service
        # For now, return placeholder data
        trends = {
            "timeline": [
                {"date": "2025-01-21", "score": 0.85},
                {"date": "2025-01-22", "score": 0.87},
                {"date": "2025-01-23", "score": 0.82},
                {"date": "2025-01-24", "score": 0.89},
                {"date": "2025-01-25", "score": 0.91},
                {"date": "2025-01-26", "score": 0.88},
                {"date": "2025-01-27", "score": 0.90}
            ],
            "average_score": 0.87,
            "trend": "improving",
            "system_id": system_id,
            "time_range": time_range
        }
        
        return {
            "success": True,
            "data": trends
        }
        
    except Exception as e:
        logger.error("Failed to get performance trends", error=str(e), user_id=current_user.user_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "ANALYTICS_ERROR",
                    "message": "Failed to retrieve performance trends"
                }
            }
        )