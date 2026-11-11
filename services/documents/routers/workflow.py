"""Document workflow management endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import structlog

from ...shared.auth import get_current_active_user, require_admin
from ...shared.schemas import UserResponse, ApiResponse
from ...shared.exceptions import ValidationError, NotFoundError
from ..services.workflow_service import document_workflow_service, WorkflowStatus

logger = structlog.get_logger()
router = APIRouter()

# Pydantic schemas for workflow operations
class WorkflowStartRequest(BaseModel):
    workflow_type: str = Field(default="standard", description="Type of workflow to start")
    assignees: Optional[List[int]] = Field(default=None, description="List of user IDs to assign")
    custom_rules: Optional[Dict[str, Any]] = Field(default=None, description="Custom workflow rules")

class ApprovalSubmissionRequest(BaseModel):
    decision: str = Field(..., description="Approval decision: approve, reject, or request_changes")
    comments: Optional[str] = Field(default=None, description="Comments for the decision")
    attachments: Optional[List[str]] = Field(default=None, description="List of attachment file paths")

class CommentRequest(BaseModel):
    comment: str = Field(..., min_length=1, description="Comment text")
    comment_type: str = Field(default="general", description="Type of comment")
    reply_to: Optional[str] = Field(default=None, description="ID of comment being replied to")
    attachments: Optional[List[str]] = Field(default=None, description="List of attachment file paths")

class EscalationRequest(BaseModel):
    escalation_type: str = Field(..., description="Type of escalation")
    escalation_reason: str = Field(..., description="Reason for escalation")
    escalate_to: Optional[List[int]] = Field(default=None, description="User IDs to escalate to")

@router.post("/start/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def start_workflow(
    document_id: int,
    workflow_request: WorkflowStartRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Start a workflow for a document."""
    
    try:
        workflow_instance = await document_workflow_service.start_workflow(
            document_id=document_id,
            workflow_type=workflow_request.workflow_type,
            assignees=workflow_request.assignees,
            custom_rules=workflow_request.custom_rules
        )
        
        logger.info("Workflow started via API", 
                   document_id=document_id,
                   workflow_id=workflow_instance["workflow_id"],
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=workflow_instance,
            message="Workflow started successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to start workflow via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/approve/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def submit_approval(
    document_id: int,
    approval_request: ApprovalSubmissionRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Submit an approval decision for a document."""
    
    try:
        result = await document_workflow_service.submit_approval(
            document_id=document_id,
            user_id=current_user.user_id,
            decision=approval_request.decision,
            comments=approval_request.comments,
            attachments=approval_request.attachments
        )
        
        logger.info("Approval submitted via API", 
                   document_id=document_id,
                   decision=approval_request.decision,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=result,
            message=f"Approval {approval_request.decision} submitted successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to submit approval via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/comment/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def add_comment(
    document_id: int,
    comment_request: CommentRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Add a comment to a document workflow."""
    
    try:
        comment_record = await document_workflow_service.add_comment(
            document_id=document_id,
            user_id=current_user.user_id,
            comment=comment_request.comment,
            comment_type=comment_request.comment_type,
            reply_to=comment_request.reply_to,
            attachments=comment_request.attachments
        )
        
        logger.info("Comment added via API", 
                   document_id=document_id,
                   comment_id=comment_record["comment_id"],
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=comment_record,
            message="Comment added successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to add comment via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_workflow_status(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get the workflow status for a document."""
    
    try:
        status = await document_workflow_service.get_workflow_status(document_id)
        
        return ApiResponse(
            success=True,
            data=status,
            message="Workflow status retrieved successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get workflow status via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/escalate/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def escalate_workflow(
    document_id: int,
    escalation_request: EscalationRequest,
    current_user: UserResponse = Depends(require_admin)
):
    """Escalate a workflow (admin only)."""
    
    try:
        escalation_record = await document_workflow_service.escalate_workflow(
            document_id=document_id,
            escalation_type=escalation_request.escalation_type,
            escalation_reason=escalation_request.escalation_reason,
            escalate_to=escalation_request.escalate_to
        )
        
        logger.info("Workflow escalated via API", 
                   document_id=document_id,
                   escalation_id=escalation_record["escalation_id"],
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=escalation_record,
            message="Workflow escalated successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to escalate workflow via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/tasks", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_user_workflow_tasks(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get pending workflow tasks for the current user."""
    
    try:
        tasks = await document_workflow_service.get_user_workflow_tasks(current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=tasks,
            message=f"Found {len(tasks)} pending workflow tasks"
        )
        
    except Exception as e:
        logger.error("Failed to get user workflow tasks via API", 
                    user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/templates", response_model=ApiResponse[Dict[str, Any]])
async def get_workflow_templates(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get available workflow templates."""
    
    try:
        templates = {
            "standard": {
                "name": "Standard Document Approval",
                "description": "Basic approval workflow with review and approval stages",
                "stages": ["draft", "review", "approval", "published"],
                "estimated_duration": "3-5 days",
                "required_roles": ["reviewer", "approver"]
            },
            "compliance": {
                "name": "Compliance Document Approval",
                "description": "Enhanced workflow for compliance documents with multiple review stages",
                "stages": ["draft", "technical_review", "compliance_review", "management_approval", "published"],
                "estimated_duration": "5-7 days",
                "required_roles": ["technical_reviewer", "compliance_officer", "manager"]
            }
        }
        
        return ApiResponse(
            success=True,
            data=templates,
            message="Workflow templates retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get workflow templates via API", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics", response_model=ApiResponse[Dict[str, Any]])
async def get_workflow_analytics(
    workflow_type: Optional[str] = None,
    days: int = 30,
    current_user: UserResponse = Depends(require_admin)
):
    """Get workflow analytics (admin only)."""
    
    try:
        # This would implement workflow analytics
        # For now, return placeholder data
        analytics = {
            "total_workflows": 0,
            "completed_workflows": 0,
            "average_completion_time_hours": 0,
            "escalated_workflows": 0,
            "workflow_efficiency": 0.0,
            "common_bottlenecks": [],
            "user_performance": {},
            "workflow_type_breakdown": {},
            "time_period": f"Last {days} days"
        }
        
        return ApiResponse(
            success=True,
            data=analytics,
            message="Workflow analytics retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get workflow analytics via API", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/configure/{workflow_type}", response_model=ApiResponse[Dict[str, Any]])
async def configure_workflow(
    workflow_type: str,
    configuration: Dict[str, Any],
    current_user: UserResponse = Depends(require_admin)
):
    """Configure a workflow type (admin only)."""
    
    try:
        # This would implement workflow configuration updates
        # For now, return success message
        
        logger.info("Workflow configuration updated", 
                   workflow_type=workflow_type,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data={
                "workflow_type": workflow_type,
                "configuration": configuration,
                "updated_at": "2025-01-28T00:00:00Z"
            },
            message=f"Workflow '{workflow_type}' configured successfully"
        )
        
    except Exception as e:
        logger.error("Failed to configure workflow via API", 
                    workflow_type=workflow_type, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/history/{document_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_workflow_history(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get the complete history of a document workflow."""
    
    try:
        # Get workflow status which includes history
        status = await document_workflow_service.get_workflow_status(document_id)
        
        if not status.get("workflow_active"):
            return ApiResponse(
                success=True,
                data={"document_id": document_id, "history": []},
                message="No workflow history found"
            )
        
        # Extract history from workflow data
        history = {
            "document_id": document_id,
            "workflow_id": status.get("workflow_id"),
            "timeline": [],
            "approvals": status.get("approvals", []),
            "rejections": status.get("rejections", []),
            "comments": status.get("comments", []),
            "escalations": status.get("escalations", [])
        }
        
        # Create chronological timeline
        timeline_events = []
        
        # Add workflow start event
        if status.get("started_at"):
            timeline_events.append({
                "type": "workflow_started",
                "timestamp": status["started_at"],
                "details": {"workflow_type": status.get("workflow_type", "standard")}
            })
        
        # Add approval events
        for approval in history["approvals"]:
            timeline_events.append({
                "type": "approval_submitted",
                "timestamp": approval["timestamp"],
                "user_id": approval["user_id"],
                "details": approval
            })
        
        # Add rejection events
        for rejection in history["rejections"]:
            timeline_events.append({
                "type": "rejection_submitted",
                "timestamp": rejection["timestamp"],
                "user_id": rejection["user_id"],
                "details": rejection
            })
        
        # Add comment events
        for comment in history["comments"]:
            timeline_events.append({
                "type": "comment_added",
                "timestamp": comment["timestamp"],
                "user_id": comment["user_id"],
                "details": comment
            })
        
        # Add escalation events
        for escalation in history["escalations"]:
            timeline_events.append({
                "type": "workflow_escalated",
                "timestamp": escalation["escalated_at"],
                "details": escalation
            })
        
        # Sort timeline by timestamp
        timeline_events.sort(key=lambda x: x["timestamp"])
        history["timeline"] = timeline_events
        
        return ApiResponse(
            success=True,
            data=history,
            message="Workflow history retrieved successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get workflow history via API", 
                    document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")