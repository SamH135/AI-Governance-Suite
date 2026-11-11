"""
Document Workflow Management Service
Provides approval workflows, escalation, and collaboration features
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ...shared.database import db_manager
from ...shared.models import GeneratedDocument, User
from ...shared.exceptions import ValidationError, NotFoundError
from ...shared.websocket_service import websocket_manager, real_time_updates
from .notification_service import notification_service

logger = structlog.get_logger()

class WorkflowStatus(str, Enum):
    """Document workflow statuses."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class EscalationTrigger(str, Enum):
    """Escalation trigger types."""
    TIME_BASED = "time_based"
    APPROVAL_COUNT = "approval_count"
    REJECTION_COUNT = "rejection_count"
    MANUAL = "manual"

class NotificationType(str, Enum):
    """Notification types."""
    EMAIL = "email"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    SMS = "sms"

class WorkflowRule:
    """Workflow rule definition."""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        conditions: Dict[str, Any],
        actions: List[Dict[str, Any]],
        priority: int = 100
    ):
        self.rule_id = rule_id
        self.name = name
        self.conditions = conditions
        self.actions = actions
        self.priority = priority

class DocumentWorkflowService:
    """Service for managing document workflows and approvals."""
    
    def __init__(self):
        self.workflow_rules: Dict[str, WorkflowRule] = {}
        self.escalation_rules: Dict[str, Dict[str, Any]] = {}
        self.notification_handlers: Dict[str, callable] = {}
        self.initialized = False
        
        # Default workflow configurations
        self.default_workflows = {
            "standard": {
                "name": "Standard Document Approval",
                "stages": [
                    {"name": "draft", "required_approvals": 0, "timeout_hours": None},
                    {"name": "review", "required_approvals": 1, "timeout_hours": 72},
                    {"name": "approval", "required_approvals": 2, "timeout_hours": 48},
                    {"name": "published", "required_approvals": 0, "timeout_hours": None}
                ],
                "escalation_rules": [
                    {
                        "trigger": "timeout",
                        "action": "escalate_to_manager",
                        "notify": ["email", "websocket"]
                    }
                ]
            },
            "compliance": {
                "name": "Compliance Document Approval",
                "stages": [
                    {"name": "draft", "required_approvals": 0, "timeout_hours": None},
                    {"name": "technical_review", "required_approvals": 1, "timeout_hours": 48},
                    {"name": "compliance_review", "required_approvals": 1, "timeout_hours": 24},
                    {"name": "management_approval", "required_approvals": 1, "timeout_hours": 24},
                    {"name": "published", "required_approvals": 0, "timeout_hours": None}
                ],
                "escalation_rules": [
                    {
                        "trigger": "timeout",
                        "action": "escalate_to_compliance_officer",
                        "notify": ["email", "websocket", "webhook"]
                    }
                ]
            }
        }
    
    async def initialize(self):
        """Initialize the workflow service."""
        if self.initialized:
            return
        
        try:
            # Setup default workflow rules
            await self._setup_default_workflows()
            
            # Initialize notification service
            await notification_service.initialize()
            
            # Initialize notification handlers
            await self._setup_notification_handlers()
            
            # Start background tasks
            asyncio.create_task(self._escalation_monitor())
            
            self.initialized = True
            logger.info("Document workflow service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize workflow service", error=str(e))
            raise ValidationError(f"Workflow service initialization failed: {str(e)}")
    
    async def start_workflow(
        self,
        document_id: int,
        workflow_type: str = "standard",
        assignees: Optional[List[int]] = None,
        custom_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Start a workflow for a document."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get document
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document:
                    raise NotFoundError("Document", document_id)
                
                # Create workflow instance
                workflow_config = self.default_workflows.get(workflow_type, self.default_workflows["standard"])
                
                workflow_instance = {
                    "workflow_id": f"wf_{document_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    "document_id": document_id,
                    "workflow_type": workflow_type,
                    "config": workflow_config,
                    "current_stage": 0,
                    "status": WorkflowStatus.PENDING_REVIEW,
                    "assignees": assignees or [],
                    "approvals": [],
                    "rejections": [],
                    "comments": [],
                    "escalations": [],
                    "started_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "custom_rules": custom_rules or {}
                }
                
                # Store workflow in document metadata
                document.metadata = document.metadata or {}
                document.metadata["workflow"] = workflow_instance
                document.status = WorkflowStatus.PENDING_REVIEW
                
                await db.commit()
                
                # Send notifications to assignees
                await self._notify_workflow_started(workflow_instance)
                
                logger.info("Workflow started", 
                           workflow_id=workflow_instance["workflow_id"],
                           document_id=document_id,
                           workflow_type=workflow_type)
                
                return workflow_instance
                
        except Exception as e:
            logger.error("Failed to start workflow", document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to start workflow: {str(e)}")
    
    async def submit_approval(
        self,
        document_id: int,
        user_id: int,
        decision: str,
        comments: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Submit an approval decision for a document."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get document and workflow
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document or not document.metadata.get("workflow"):
                    raise NotFoundError("Document workflow", document_id)
                
                workflow = document.metadata["workflow"]
                
                # Validate decision
                if decision not in ["approve", "reject", "request_changes"]:
                    raise ValidationError(f"Invalid decision: {decision}")
                
                # Check if user is authorized to approve
                current_stage = workflow["config"]["stages"][workflow["current_stage"]]
                if workflow["assignees"] and user_id not in workflow["assignees"]:
                    raise ValidationError("User not authorized to approve this document")
                
                # Create approval record
                approval_record = {
                    "user_id": user_id,
                    "decision": decision,
                    "comments": comments,
                    "attachments": attachments or [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "stage": workflow["current_stage"]
                }
                
                # Add to appropriate list
                if decision == "approve":
                    workflow["approvals"].append(approval_record)
                elif decision == "reject":
                    workflow["rejections"].append(approval_record)
                else:  # request_changes
                    workflow["comments"].append(approval_record)
                
                # Check if stage is complete
                stage_result = await self._evaluate_stage_completion(workflow)
                
                if stage_result["complete"]:
                    if stage_result["approved"]:
                        # Move to next stage
                        workflow["current_stage"] += 1
                        if workflow["current_stage"] >= len(workflow["config"]["stages"]):
                            # Workflow complete
                            workflow["status"] = WorkflowStatus.APPROVED
                            document.status = WorkflowStatus.APPROVED
                        else:
                            workflow["status"] = WorkflowStatus.IN_REVIEW
                            await self._notify_next_stage_assignees(workflow)
                    else:
                        # Rejected or changes requested
                        if decision == "reject":
                            workflow["status"] = WorkflowStatus.REJECTED
                            document.status = WorkflowStatus.REJECTED
                        else:
                            workflow["status"] = WorkflowStatus.CHANGES_REQUESTED
                            document.status = WorkflowStatus.CHANGES_REQUESTED
                
                workflow["updated_at"] = datetime.utcnow().isoformat()
                document.metadata["workflow"] = workflow
                
                await db.commit()
                
                # Send real-time notifications
                await self._notify_workflow_update(workflow, approval_record)
                
                logger.info("Approval submitted", 
                           document_id=document_id,
                           user_id=user_id,
                           decision=decision,
                           workflow_status=workflow["status"])
                
                return {
                    "workflow_id": workflow["workflow_id"],
                    "status": workflow["status"],
                    "current_stage": workflow["current_stage"],
                    "approval_record": approval_record,
                    "stage_complete": stage_result["complete"]
                }
                
        except Exception as e:
            logger.error("Failed to submit approval", document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to submit approval: {str(e)}")
    
    async def add_comment(
        self,
        document_id: int,
        user_id: int,
        comment: str,
        comment_type: str = "general",
        reply_to: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add a comment to a document workflow."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get document and workflow
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document:
                    raise NotFoundError("Document", document_id)
                
                # Initialize workflow if not exists
                if not document.metadata.get("workflow"):
                    document.metadata = document.metadata or {}
                    document.metadata["workflow"] = {
                        "comments": [],
                        "document_id": document_id
                    }
                
                workflow = document.metadata["workflow"]
                
                # Create comment record
                comment_record = {
                    "comment_id": f"comment_{len(workflow.get('comments', []))}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    "user_id": user_id,
                    "comment": comment,
                    "comment_type": comment_type,
                    "reply_to": reply_to,
                    "attachments": attachments or [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "edited": False
                }
                
                # Add comment to workflow
                if "comments" not in workflow:
                    workflow["comments"] = []
                workflow["comments"].append(comment_record)
                
                workflow["updated_at"] = datetime.utcnow().isoformat()
                document.metadata["workflow"] = workflow
                
                await db.commit()
                
                # Send real-time notification
                await real_time_updates.document_generation_update(
                    document_id, "comment_added", 100
                )
                
                # Notify workflow participants
                await self._notify_comment_added(workflow, comment_record)
                
                logger.info("Comment added", 
                           document_id=document_id,
                           user_id=user_id,
                           comment_id=comment_record["comment_id"])
                
                return comment_record
                
        except Exception as e:
            logger.error("Failed to add comment", document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to add comment: {str(e)}")
    
    async def get_workflow_status(self, document_id: int) -> Dict[str, Any]:
        """Get the current workflow status for a document."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document:
                    raise NotFoundError("Document", document_id)
                
                workflow = document.metadata.get("workflow")
                if not workflow:
                    return {
                        "document_id": document_id,
                        "workflow_active": False,
                        "status": document.status
                    }
                
                # Calculate progress
                current_stage = workflow.get("current_stage", 0)
                total_stages = len(workflow.get("config", {}).get("stages", []))
                progress = (current_stage / max(total_stages, 1)) * 100
                
                # Get pending approvals
                current_stage_config = workflow["config"]["stages"][current_stage] if current_stage < total_stages else None
                required_approvals = current_stage_config.get("required_approvals", 0) if current_stage_config else 0
                current_approvals = len([a for a in workflow.get("approvals", []) if a.get("stage") == current_stage])
                
                return {
                    "document_id": document_id,
                    "workflow_id": workflow.get("workflow_id"),
                    "workflow_active": True,
                    "status": workflow.get("status"),
                    "current_stage": current_stage,
                    "total_stages": total_stages,
                    "progress": progress,
                    "current_stage_name": current_stage_config.get("name") if current_stage_config else "Completed",
                    "required_approvals": required_approvals,
                    "current_approvals": current_approvals,
                    "pending_approvals": max(0, required_approvals - current_approvals),
                    "assignees": workflow.get("assignees", []),
                    "approvals": workflow.get("approvals", []),
                    "rejections": workflow.get("rejections", []),
                    "comments": workflow.get("comments", []),
                    "escalations": workflow.get("escalations", []),
                    "started_at": workflow.get("started_at"),
                    "updated_at": workflow.get("updated_at")
                }
                
        except Exception as e:
            logger.error("Failed to get workflow status", document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to get workflow status: {str(e)}")
    
    async def escalate_workflow(
        self,
        document_id: int,
        escalation_type: str,
        escalation_reason: str,
        escalate_to: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Manually escalate a workflow."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document or not document.metadata.get("workflow"):
                    raise NotFoundError("Document workflow", document_id)
                
                workflow = document.metadata["workflow"]
                
                # Create escalation record
                escalation_record = {
                    "escalation_id": f"esc_{document_id}_{len(workflow.get('escalations', []))}",
                    "type": escalation_type,
                    "reason": escalation_reason,
                    "escalated_to": escalate_to or [],
                    "escalated_at": datetime.utcnow().isoformat(),
                    "trigger": EscalationTrigger.MANUAL,
                    "resolved": False
                }
                
                # Add escalation to workflow
                if "escalations" not in workflow:
                    workflow["escalations"] = []
                workflow["escalations"].append(escalation_record)
                
                # Update assignees if specified
                if escalate_to:
                    workflow["assignees"].extend(escalate_to)
                    workflow["assignees"] = list(set(workflow["assignees"]))  # Remove duplicates
                
                workflow["updated_at"] = datetime.utcnow().isoformat()
                document.metadata["workflow"] = workflow
                
                await db.commit()
                
                # Send notifications
                await self._notify_escalation(workflow, escalation_record)
                
                logger.info("Workflow escalated", 
                           document_id=document_id,
                           escalation_type=escalation_type,
                           escalation_id=escalation_record["escalation_id"])
                
                return escalation_record
                
        except Exception as e:
            logger.error("Failed to escalate workflow", document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to escalate workflow: {str(e)}")
    
    async def get_user_workflow_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending workflow tasks for a user."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get documents where user is assigned and workflow is active
                documents_result = await db.execute(
                    select(GeneratedDocument).where(
                        and_(
                            GeneratedDocument.metadata.contains({"workflow": {"assignees": [user_id]}}),
                            GeneratedDocument.status.in_([
                                WorkflowStatus.PENDING_REVIEW,
                                WorkflowStatus.IN_REVIEW,
                                WorkflowStatus.CHANGES_REQUESTED
                            ])
                        )
                    )
                )
                documents = documents_result.scalars().all()
                
                tasks = []
                for document in documents:
                    workflow = document.metadata.get("workflow", {})
                    if user_id in workflow.get("assignees", []):
                        current_stage = workflow.get("current_stage", 0)
                        stages = workflow.get("config", {}).get("stages", [])
                        stage_config = stages[current_stage] if current_stage < len(stages) else None
                        
                        # Check if user has already approved this stage
                        user_approved = any(
                            a.get("user_id") == user_id and a.get("stage") == current_stage
                            for a in workflow.get("approvals", [])
                        )
                        
                        if not user_approved and stage_config:
                            task = {
                                "document_id": document.document_id,
                                "title": document.title,
                                "workflow_id": workflow.get("workflow_id"),
                                "status": workflow.get("status"),
                                "current_stage": current_stage,
                                "stage_name": stage_config.get("name"),
                                "required_approvals": stage_config.get("required_approvals", 0),
                                "timeout_hours": stage_config.get("timeout_hours"),
                                "assigned_at": workflow.get("started_at"),
                                "updated_at": workflow.get("updated_at"),
                                "priority": self._calculate_task_priority(workflow)
                            }
                            tasks.append(task)
                
                # Sort by priority and date
                tasks.sort(key=lambda x: (x["priority"], x["updated_at"]), reverse=True)
                
                return tasks
                
        except Exception as e:
            logger.error("Failed to get user workflow tasks", user_id=user_id, error=str(e))
            raise ValidationError(f"Failed to get user workflow tasks: {str(e)}")
    
    # Private helper methods
    async def _setup_default_workflows(self):
        """Setup default workflow rules."""
        for workflow_type, config in self.default_workflows.items():
            rule = WorkflowRule(
                rule_id=f"default_{workflow_type}",
                name=config["name"],
                conditions={"workflow_type": workflow_type},
                actions=config.get("escalation_rules", [])
            )
            self.workflow_rules[rule.rule_id] = rule
    
    async def _setup_notification_handlers(self):
        """Setup notification handlers."""
        self.notification_handlers[NotificationType.WEBSOCKET] = self._send_websocket_notification
        self.notification_handlers[NotificationType.EMAIL] = self._send_email_notification
        self.notification_handlers[NotificationType.WEBHOOK] = self._send_webhook_notification
    
    async def _evaluate_stage_completion(self, workflow: Dict[str, Any]) -> Dict[str, bool]:
        """Evaluate if the current stage is complete."""
        current_stage = workflow["current_stage"]
        stages = workflow["config"]["stages"]
        
        if current_stage >= len(stages):
            return {"complete": True, "approved": True}
        
        stage_config = stages[current_stage]
        required_approvals = stage_config.get("required_approvals", 0)
        
        # Count approvals for current stage
        stage_approvals = len([
            a for a in workflow.get("approvals", [])
            if a.get("stage") == current_stage
        ])
        
        # Check if any rejections
        stage_rejections = [
            r for r in workflow.get("rejections", [])
            if r.get("stage") == current_stage
        ]
        
        if stage_rejections:
            return {"complete": True, "approved": False}
        
        if stage_approvals >= required_approvals:
            return {"complete": True, "approved": True}
        
        return {"complete": False, "approved": False}
    
    async def _notify_workflow_started(self, workflow: Dict[str, Any]):
        """Send notifications when workflow is started."""
        assignees = workflow.get("assignees", [])
        
        # Get user information for assignees
        recipients = []
        if assignees:
            async with db_manager.get_session() as db:
                for assignee_id in assignees:
                    user_result = await db.execute(
                        select(User).where(User.user_id == assignee_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        recipients.append({
                            "user_id": user.user_id,
                            "user_name": user.full_name,
                            "email": user.email
                        })
        
        # Send notifications via notification service
        if recipients:
            await notification_service.send_workflow_notification(
                "workflow_started",
                recipients,
                workflow,
                ["websocket", "email"]
            )
    
    async def _notify_next_stage_assignees(self, workflow: Dict[str, Any]):
        """Notify assignees of the next stage."""
        assignees = workflow.get("assignees", [])
        current_stage = workflow["current_stage"]
        stages = workflow["config"]["stages"]
        
        if current_stage < len(stages):
            # Get user information for assignees
            recipients = []
            if assignees:
                async with db_manager.get_session() as db:
                    for assignee_id in assignees:
                        user_result = await db.execute(
                            select(User).where(User.user_id == assignee_id)
                        )
                        user = user_result.scalar_one_or_none()
                        if user:
                            recipients.append({
                                "user_id": user.user_id,
                                "user_name": user.full_name,
                                "email": user.email
                            })
            
            # Prepare stage information
            stage_config = stages[current_stage]
            workflow_data = {
                **workflow,
                "current_stage": {
                    "name": stage_config.get("name", "Review"),
                    "required_action": "Approval",
                    "timeout_hours": stage_config.get("timeout_hours")
                }
            }
            
            # Send approval required notifications
            if recipients:
                await notification_service.send_workflow_notification(
                    "approval_required",
                    recipients,
                    workflow_data,
                    ["websocket", "email"]
                )
    
    async def _notify_workflow_update(self, workflow: Dict[str, Any], approval_record: Dict[str, Any]):
        """Send notifications for workflow updates."""
        message = {
            "type": "workflow_updated",
            "workflow_id": workflow["workflow_id"],
            "document_id": workflow["document_id"],
            "status": workflow["status"],
            "approval": approval_record
        }
        
        # Notify all participants
        all_users = set(workflow.get("assignees", []))
        
        for user_id in all_users:
            await real_time_updates.user_notification(user_id, message)
    
    async def _notify_comment_added(self, workflow: Dict[str, Any], comment_record: Dict[str, Any]):
        """Send notifications for new comments."""
        message = {
            "type": "comment_added",
            "workflow_id": workflow.get("workflow_id"),
            "document_id": workflow["document_id"],
            "comment": comment_record
        }
        
        # Notify all participants
        all_users = set(workflow.get("assignees", []))
        
        for user_id in all_users:
            if user_id != comment_record["user_id"]:  # Don't notify the commenter
                await real_time_updates.user_notification(user_id, message)
    
    async def _notify_escalation(self, workflow: Dict[str, Any], escalation_record: Dict[str, Any]):
        """Send escalation notifications."""
        message = {
            "type": "workflow_escalated",
            "workflow_id": workflow["workflow_id"],
            "document_id": workflow["document_id"],
            "escalation": escalation_record
        }
        
        # Notify escalated users
        escalated_to = escalation_record.get("escalated_to", [])
        for user_id in escalated_to:
            await real_time_updates.user_notification(user_id, message)
    
    async def _escalation_monitor(self):
        """Background task to monitor and trigger escalations."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                async with db_manager.get_session() as db:
                    # Get active workflows
                    documents_result = await db.execute(
                        select(GeneratedDocument).where(
                            GeneratedDocument.status.in_([
                                WorkflowStatus.PENDING_REVIEW,
                                WorkflowStatus.IN_REVIEW
                            ])
                        )
                    )
                    documents = documents_result.scalars().all()
                    
                    for document in documents:
                        workflow = document.metadata.get("workflow")
                        if not workflow:
                            continue
                        
                        await self._check_timeout_escalation(document, workflow)
                        
            except Exception as e:
                logger.error("Escalation monitor error", error=str(e))
    
    async def _check_timeout_escalation(self, document: GeneratedDocument, workflow: Dict[str, Any]):
        """Check if workflow stage has timed out."""
        current_stage = workflow.get("current_stage", 0)
        stages = workflow.get("config", {}).get("stages", [])
        
        if current_stage >= len(stages):
            return
        
        stage_config = stages[current_stage]
        timeout_hours = stage_config.get("timeout_hours")
        
        if not timeout_hours:
            return
        
        # Calculate time since stage started
        stage_start = datetime.fromisoformat(workflow.get("updated_at", workflow.get("started_at", datetime.utcnow().isoformat())))
        hours_elapsed = (datetime.utcnow() - stage_start).total_seconds() / 3600
        
        if hours_elapsed >= timeout_hours:
            # Trigger escalation
            await self.escalate_workflow(
                document.document_id,
                "timeout",
                f"Stage '{stage_config.get('name', 'Unknown')}' timed out after {timeout_hours} hours"
            )
    
    def _calculate_task_priority(self, workflow: Dict[str, Any]) -> int:
        """Calculate task priority based on workflow characteristics."""
        priority = 50  # Base priority
        
        # Increase priority for compliance workflows
        if workflow.get("workflow_type") == "compliance":
            priority += 30
        
        # Increase priority based on stage timeout
        current_stage = workflow.get("current_stage", 0)
        stages = workflow.get("config", {}).get("stages", [])
        
        if current_stage < len(stages):
            timeout_hours = stages[current_stage].get("timeout_hours")
            if timeout_hours and timeout_hours <= 24:
                priority += 20
        
        # Increase priority if escalated
        if workflow.get("escalations"):
            priority += 40
        
        return min(priority, 100)
    
    async def _send_websocket_notification(self, user_id: int, message: Dict[str, Any]):
        """Send WebSocket notification."""
        await real_time_updates.user_notification(user_id, message)
    
    async def _send_email_notification(self, user_id: int, message: Dict[str, Any]):
        """Send email notification (placeholder)."""
        # This would integrate with an email service
        logger.info("Email notification would be sent", user_id=user_id, message=message)
    
    async def _send_webhook_notification(self, webhook_url: str, message: Dict[str, Any]):
        """Send webhook notification (placeholder)."""
        # This would make HTTP POST to webhook URL
        logger.info("Webhook notification would be sent", webhook_url=webhook_url, message=message)

# Global workflow service instance
document_workflow_service = DocumentWorkflowService()