"""
Audit Logging Router
REST API endpoints for audit logging and compliance reporting
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import structlog

from .auth import get_current_active_user
from .schemas import UserResponse, ApiResponse
from .exceptions import ValidationError
from .audit_logging_service import (
    audit_logging_service, 
    AuditEventType, 
    AuditSeverity, 
    AuditStatus
)

logger = structlog.get_logger()
router = APIRouter()

# Pydantic schemas for audit logging
class AuditEventRequest(BaseModel):
    event_type: AuditEventType = Field(..., description="Type of audit event")
    action: str = Field(..., description="Action description")
    status: AuditStatus = Field(default=AuditStatus.SUCCESS, description="Event status")
    severity: AuditSeverity = Field(default=AuditSeverity.LOW, description="Event severity")
    resource_type: Optional[str] = Field(default=None, description="Resource type")
    resource_id: Optional[str] = Field(default=None, description="Resource ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")
    old_values: Optional[Dict[str, Any]] = Field(default=None, description="Old values")
    new_values: Optional[Dict[str, Any]] = Field(default=None, description="New values")
    compliance_tags: Optional[List[str]] = Field(default=None, description="Compliance tags")

class AuditTrailRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, description="Filter by user ID")
    event_type: Optional[AuditEventType] = Field(default=None, description="Filter by event type")
    resource_type: Optional[str] = Field(default=None, description="Filter by resource type")
    resource_id: Optional[str] = Field(default=None, description="Filter by resource ID")
    start_date: Optional[datetime] = Field(default=None, description="Start date filter")
    end_date: Optional[datetime] = Field(default=None, description="End date filter")
    severity: Optional[AuditSeverity] = Field(default=None, description="Filter by severity")
    status: Optional[AuditStatus] = Field(default=None, description="Filter by status")
    limit: int = Field(default=100, le=1000, description="Number of records to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

class ComplianceReportRequest(BaseModel):
    compliance_framework: str = Field(..., description="Compliance framework (gdpr, hipaa, sox, pci_dss, iso27001)")
    start_date: datetime = Field(..., description="Report start date")
    end_date: datetime = Field(..., description="Report end date")

class AuditSearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters")
    limit: int = Field(default=100, le=500, description="Number of results to return")

@router.post("/events", response_model=ApiResponse[str])
async def log_audit_event(
    event_request: AuditEventRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Log a new audit event."""
    
    try:
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        event_id = await audit_logging_service.log_event(
            event_type=event_request.event_type,
            user_id=current_user.user_id,
            action=event_request.action,
            status=event_request.status,
            severity=event_request.severity,
            resource_type=event_request.resource_type,
            resource_id=event_request.resource_id,
            session_id=event_request.session_id,
            ip_address=event_request.ip_address,
            user_agent=event_request.user_agent,
            details=event_request.details,
            old_values=event_request.old_values,
            new_values=event_request.new_values,
            compliance_tags=event_request.compliance_tags
        )
        
        logger.info("Audit event logged via API", 
                   event_id=event_id,
                   event_type=event_request.event_type,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=event_id,
            message="Audit event logged successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to log audit event via API", 
                    event_type=event_request.event_type, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/trail", response_model=ApiResponse[Dict[str, Any]])
async def get_audit_trail(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    event_type: Optional[AuditEventType] = Query(None, description="Filter by event type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    severity: Optional[AuditSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AuditStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get audit trail with filtering options."""
    
    try:
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        # For non-admin users, restrict to their own events
        if current_user.role not in ["admin", "super_admin", "compliance_officer"]:
            user_id = current_user.user_id
        
        audit_trail = await audit_logging_service.get_audit_trail(
            user_id=user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            severity=severity,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return ApiResponse(
            success=True,
            data=audit_trail,
            message=f"Retrieved {len(audit_trail['events'])} audit events"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get audit trail", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/trail/search", response_model=ApiResponse[Dict[str, Any]])
async def get_audit_trail_filtered(
    trail_request: AuditTrailRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get audit trail with complex filtering (POST for complex queries)."""
    
    try:
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        # For non-admin users, restrict to their own events
        if current_user.role not in ["admin", "super_admin", "compliance_officer"]:
            trail_request.user_id = current_user.user_id
        
        audit_trail = await audit_logging_service.get_audit_trail(
            user_id=trail_request.user_id,
            event_type=trail_request.event_type,
            resource_type=trail_request.resource_type,
            resource_id=trail_request.resource_id,
            start_date=trail_request.start_date,
            end_date=trail_request.end_date,
            severity=trail_request.severity,
            status=trail_request.status,
            limit=trail_request.limit,
            offset=trail_request.offset
        )
        
        return ApiResponse(
            success=True,
            data=audit_trail,
            message=f"Retrieved {len(audit_trail['events'])} audit events"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get filtered audit trail", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/compliance/report", response_model=ApiResponse[Dict[str, Any]])
async def generate_compliance_report(
    report_request: ComplianceReportRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Generate compliance report for specific framework."""
    
    try:
        # Check if user has permission to generate compliance reports
        if current_user.role not in ["admin", "super_admin", "compliance_officer"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        # Validate date range
        if report_request.end_date <= report_request.start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        # Validate compliance framework
        supported_frameworks = ["gdpr", "hipaa", "sox", "pci_dss", "iso27001"]
        if report_request.compliance_framework.lower() not in supported_frameworks:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported compliance framework. Supported: {supported_frameworks}"
            )
        
        compliance_report = await audit_logging_service.get_compliance_report(
            compliance_framework=report_request.compliance_framework,
            start_date=report_request.start_date,
            end_date=report_request.end_date
        )
        
        logger.info("Compliance report generated", 
                   framework=report_request.compliance_framework,
                   user_id=current_user.user_id,
                   start_date=report_request.start_date.isoformat(),
                   end_date=report_request.end_date.isoformat())
        
        return ApiResponse(
            success=True,
            data=compliance_report,
            message=f"Compliance report generated for {report_request.compliance_framework.upper()}"
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate compliance report", 
                    framework=report_request.compliance_framework, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/search", response_model=ApiResponse[List[Dict[str, Any]]])
async def search_audit_logs(
    search_request: AuditSearchRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Search audit logs using text search."""
    
    try:
        # Check if user has permission to search audit logs
        if current_user.role not in ["admin", "super_admin", "compliance_officer", "analyst"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        # For non-admin users, add user filter to restrict results
        filters = search_request.filters or {}
        if current_user.role not in ["admin", "super_admin", "compliance_officer"]:
            filters["user_id"] = current_user.user_id
        
        search_results = await audit_logging_service.search_audit_logs(
            query_string=search_request.query,
            filters=filters,
            limit=search_request.limit
        )
        
        logger.info("Audit log search performed", 
                   query=search_request.query,
                   user_id=current_user.user_id,
                   results_count=len(search_results))
        
        return ApiResponse(
            success=True,
            data=search_results,
            message=f"Found {len(search_results)} matching audit events"
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to search audit logs", 
                    query=search_request.query, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/events/types", response_model=ApiResponse[List[str]])
async def get_audit_event_types(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of available audit event types."""
    
    try:
        event_types = [event_type.value for event_type in AuditEventType]
        
        return ApiResponse(
            success=True,
            data=event_types,
            message=f"Retrieved {len(event_types)} audit event types"
        )
        
    except Exception as e:
        logger.error("Failed to get audit event types", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/summary", response_model=ApiResponse[Dict[str, Any]])
async def get_audit_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to summarize"),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get audit summary for the specified time period."""
    
    try:
        # Check if user has permission to view audit summary
        if current_user.role not in ["admin", "super_admin", "compliance_officer", "analyst"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        if not audit_logging_service.initialized:
            await audit_logging_service.initialize()
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get audit trail for the period
        audit_trail = await audit_logging_service.get_audit_trail(
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Get more data for summary
        )
        
        events = audit_trail["events"]
        total_events = len(events)
        
        # Calculate summary statistics
        event_type_counts = {}
        severity_counts = {}
        status_counts = {}
        user_activity = {}
        high_risk_events = 0
        
        for event in events:
            # Event type breakdown
            event_type = event.get("event_type", "unknown")
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            
            # Severity breakdown
            severity = event.get("severity", "low")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Status breakdown
            status = event.get("status", "success")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # User activity
            user_id = event.get("user_id")
            if user_id:
                user_activity[user_id] = user_activity.get(user_id, 0) + 1
            
            # High-risk events
            risk_score = event.get("risk_score", 0)
            if risk_score and risk_score >= 70:
                high_risk_events += 1
        
        summary = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "totals": {
                "total_events": total_events,
                "high_risk_events": high_risk_events,
                "unique_users": len(user_activity),
                "risk_percentage": (high_risk_events / total_events * 100) if total_events > 0 else 0
            },
            "breakdowns": {
                "by_event_type": event_type_counts,
                "by_severity": severity_counts,
                "by_status": status_counts
            },
            "top_users": dict(sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10])
        }
        
        return ApiResponse(
            success=True,
            data=summary,
            message=f"Audit summary generated for {days} days"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate audit summary", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
async def get_audit_service_health(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get audit logging service health status."""
    
    try:
        health_status = {
            "service": "audit_logging",
            "initialized": audit_logging_service.initialized,
            "elasticsearch_available": audit_logging_service.elasticsearch_client is not None,
            "retention_days": audit_logging_service.retention_days,
            "risk_threshold": audit_logging_service.risk_threshold
        }
        
        if audit_logging_service.initialized:
            # Get recent statistics
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=24)
            
            recent_trail = await audit_logging_service.get_audit_trail(
                start_date=start_date,
                end_date=end_date,
                limit=1000
            )
            
            health_status["recent_activity"] = {
                "events_last_24h": len(recent_trail["events"]),
                "last_event_time": recent_trail["events"][0]["timestamp"] if recent_trail["events"] else None
            }
        
        return ApiResponse(
            success=True,
            data=health_status,
            message="Audit service health status retrieved"
        )
        
    except Exception as e:
        logger.error("Failed to get audit service health", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")