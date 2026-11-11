"""
Document Notification Service
Handles email, webhook, and SMS notifications for workflow events
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog
import httpx
import os
import json

from ...shared.exceptions import ExternalServiceError
from ...shared.websocket_service import real_time_updates

logger = structlog.get_logger()

class NotificationService:
    """Service for sending various types of notifications."""
    
    def __init__(self):
        self.initialized = False
        self.email_config = {}
        self.webhook_config = {}
        self.sms_config = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Email templates
        self.email_templates = {
            "workflow_started": {
                "subject": "Document Workflow Started: {document_title}",
                "template": """
Dear {user_name},

A new document workflow has been started and requires your attention.

Document: {document_title}
Workflow Type: {workflow_type}
Started By: {started_by}
Started At: {started_at}

Please log in to the system to review and take action.

Best regards,
AI Compliance Platform
"""
            },
            "approval_required": {
                "subject": "Action Required: Document Approval - {document_title}",
                "template": """
Dear {user_name},

A document is pending your approval in the workflow system.

Document: {document_title}
Current Stage: {stage_name}
Required Action: {required_action}
Due Date: {due_date}

Please log in to review and approve or reject this document.

Best regards,
AI Compliance Platform
"""
            },
            "workflow_escalated": {
                "subject": "URGENT: Workflow Escalated - {document_title}",
                "template": """
Dear {user_name},

A document workflow has been escalated and requires immediate attention.

Document: {document_title}
Escalation Reason: {escalation_reason}
Escalated At: {escalated_at}
Original Assignees: {original_assignees}

This workflow may be overdue or blocked. Please review immediately.

Best regards,
AI Compliance Platform
"""
            },
            "workflow_completed": {
                "subject": "Workflow Completed: {document_title}",
                "template": """
Dear {user_name},

The document workflow has been completed successfully.

Document: {document_title}
Final Status: {final_status}
Completed At: {completed_at}
Total Duration: {total_duration}

The document is now available for download from the system.

Best regards,
AI Compliance Platform
"""
            }
        }
    
    async def initialize(self):
        """Initialize the notification service."""
        if self.initialized:
            return
        
        try:
            # Configure email settings
            self.email_config = {
                "smtp_server": os.getenv("SMTP_SERVER", "localhost"),
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "smtp_username": os.getenv("SMTP_USERNAME", ""),
                "smtp_password": os.getenv("SMTP_PASSWORD", ""),
                "from_email": os.getenv("FROM_EMAIL", "noreply@aicomplianceplatform.com"),
                "from_name": os.getenv("FROM_NAME", "AI Compliance Platform")
            }
            
            # Configure webhook settings
            self.webhook_config = {
                "default_timeout": int(os.getenv("WEBHOOK_TIMEOUT", "30")),
                "retry_attempts": int(os.getenv("WEBHOOK_RETRIES", "3")),
                "retry_delay": int(os.getenv("WEBHOOK_RETRY_DELAY", "5"))
            }
            
            # Configure SMS settings (placeholder for future implementation)
            self.sms_config = {
                "provider": os.getenv("SMS_PROVIDER", "twilio"),
                "api_key": os.getenv("SMS_API_KEY", ""),
                "api_secret": os.getenv("SMS_API_SECRET", ""),
                "from_number": os.getenv("SMS_FROM_NUMBER", "")
            }
            
            # Initialize HTTP client for webhooks
            self.http_client = httpx.AsyncClient(timeout=self.webhook_config["default_timeout"])
            
            self.initialized = True
            logger.info("Notification service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize notification service", error=str(e))
            raise ExternalServiceError("NotificationService", f"Initialization failed: {str(e)}")
    
    async def close(self):
        """Close notification service connections."""
        if self.http_client:
            await self.http_client.aclose()
            logger.info("Notification service connections closed")
    
    async def send_workflow_notification(
        self,
        notification_type: str,
        recipients: List[Dict[str, Any]],
        workflow_data: Dict[str, Any],
        notification_methods: List[str] = None
    ):
        """Send workflow-related notifications to recipients."""
        if not self.initialized:
            await self.initialize()
        
        if not notification_methods:
            notification_methods = ["websocket", "email"]
        
        try:
            logger.info("Sending workflow notifications", 
                       type=notification_type,
                       recipient_count=len(recipients),
                       methods=notification_methods)
            
            # Prepare notification data
            notification_data = self._prepare_notification_data(notification_type, workflow_data)
            
            # Send notifications via different methods
            tasks = []
            
            for method in notification_methods:
                if method == "email":
                    tasks.append(self._send_email_notifications(
                        notification_type, recipients, notification_data
                    ))
                elif method == "websocket":
                    tasks.append(self._send_websocket_notifications(
                        notification_type, recipients, notification_data
                    ))
                elif method == "webhook":
                    tasks.append(self._send_webhook_notifications(
                        notification_type, recipients, notification_data
                    ))
                elif method == "sms":
                    tasks.append(self._send_sms_notifications(
                        notification_type, recipients, notification_data
                    ))
            
            # Execute all notification tasks
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Log results
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                error_count = len(results) - success_count
                
                logger.info("Workflow notifications sent", 
                           successful=success_count,
                           failed=error_count)
                
                # Log any errors
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error("Notification method failed", 
                                   method=notification_methods[i],
                                   error=str(result))
            
        except Exception as e:
            logger.error("Failed to send workflow notifications", 
                        type=notification_type, error=str(e))
            raise ExternalServiceError("NotificationService", f"Failed to send notifications: {str(e)}")
    
    def _prepare_notification_data(self, notification_type: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare notification data from workflow information."""
        
        base_data = {
            "notification_type": notification_type,
            "document_id": workflow_data.get("document_id"),
            "document_title": workflow_data.get("document_title", "Unknown Document"),
            "workflow_id": workflow_data.get("workflow_id"),
            "workflow_type": workflow_data.get("workflow_type", "standard"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add specific data based on notification type
        if notification_type == "workflow_started":
            base_data.update({
                "started_by": workflow_data.get("started_by", "System"),
                "started_at": workflow_data.get("started_at"),
                "assignees": workflow_data.get("assignees", [])
            })
        
        elif notification_type == "approval_required":
            current_stage = workflow_data.get("current_stage", {})
            base_data.update({
                "stage_name": current_stage.get("name", "Review"),
                "required_action": current_stage.get("required_action", "Approval"),
                "due_date": current_stage.get("due_date"),
                "timeout_hours": current_stage.get("timeout_hours")
            })
        
        elif notification_type == "workflow_escalated":
            escalation = workflow_data.get("escalation", {})
            base_data.update({
                "escalation_reason": escalation.get("reason", "Timeout"),
                "escalated_at": escalation.get("escalated_at"),
                "original_assignees": workflow_data.get("original_assignees", []),
                "escalation_type": escalation.get("type", "timeout")
            })
        
        elif notification_type == "workflow_completed":
            base_data.update({
                "final_status": workflow_data.get("final_status", "approved"),
                "completed_at": workflow_data.get("completed_at"),
                "total_duration": workflow_data.get("total_duration"),
                "file_path": workflow_data.get("file_path")
            })
        
        return base_data
    
    async def _send_email_notifications(
        self,
        notification_type: str,
        recipients: List[Dict[str, Any]],
        notification_data: Dict[str, Any]
    ):
        """Send email notifications."""
        
        if not self.email_config.get("smtp_username"):
            logger.warning("Email notifications disabled - no SMTP configuration")
            return
        
        template = self.email_templates.get(notification_type)
        if not template:
            logger.warning("No email template found", notification_type=notification_type)
            return
        
        try:
            # Connect to SMTP server
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.starttls()
                server.login(self.email_config["smtp_username"], self.email_config["smtp_password"])
                
                sent_count = 0
                for recipient in recipients:
                    try:
                        # Prepare email content
                        email_data = {**notification_data, **recipient}
                        subject = template["subject"].format(**email_data)
                        body = template["template"].format(**email_data)
                        
                        # Create message
                        msg = MIMEMultipart()
                        msg["From"] = f"{self.email_config['from_name']} <{self.email_config['from_email']}>"
                        msg["To"] = recipient.get("email", "")
                        msg["Subject"] = subject
                        
                        msg.attach(MIMEText(body, "plain"))
                        
                        # Send email
                        if recipient.get("email"):
                            server.send_message(msg)
                            sent_count += 1
                            
                            logger.debug("Email sent", 
                                       recipient=recipient.get("email"),
                                       subject=subject)
                    
                    except Exception as e:
                        logger.error("Failed to send email to recipient", 
                                   recipient=recipient.get("email"), error=str(e))
                
                logger.info("Email notifications sent", 
                           type=notification_type, sent=sent_count, total=len(recipients))
                
        except Exception as e:
            logger.error("Failed to send email notifications", error=str(e))
            raise
    
    async def _send_websocket_notifications(
        self,
        notification_type: str,
        recipients: List[Dict[str, Any]],
        notification_data: Dict[str, Any]
    ):
        """Send WebSocket notifications."""
        
        try:
            tasks = []
            for recipient in recipients:
                user_id = recipient.get("user_id")
                if user_id:
                    message = {
                        "type": f"workflow_{notification_type}",
                        **notification_data,
                        "recipient": recipient
                    }
                    tasks.append(real_time_updates.user_notification(user_id, message))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info("WebSocket notifications sent", 
                           type=notification_type, count=len(tasks))
        
        except Exception as e:
            logger.error("Failed to send WebSocket notifications", error=str(e))
            raise
    
    async def _send_webhook_notifications(
        self,
        notification_type: str,
        recipients: List[Dict[str, Any]],
        notification_data: Dict[str, Any]
    ):
        """Send webhook notifications."""
        
        webhook_urls = []
        for recipient in recipients:
            webhook_url = recipient.get("webhook_url")
            if webhook_url:
                webhook_urls.append(webhook_url)
        
        if not webhook_urls:
            return
        
        try:
            webhook_payload = {
                "event": f"workflow.{notification_type}",
                "data": notification_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            tasks = []
            for webhook_url in webhook_urls:
                tasks.append(self._send_webhook(webhook_url, webhook_payload))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                
                logger.info("Webhook notifications sent", 
                           type=notification_type,
                           successful=success_count,
                           total=len(webhook_urls))
        
        except Exception as e:
            logger.error("Failed to send webhook notifications", error=str(e))
            raise
    
    async def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """Send a single webhook with retry logic."""
        
        for attempt in range(self.webhook_config["retry_attempts"]):
            try:
                response = await self.http_client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code < 400:
                    logger.debug("Webhook sent successfully", 
                               url=webhook_url, status=response.status_code)
                    return True
                else:
                    logger.warning("Webhook failed", 
                                 url=webhook_url, 
                                 status=response.status_code,
                                 attempt=attempt + 1)
            
            except Exception as e:
                logger.warning("Webhook request failed", 
                             url=webhook_url, 
                             error=str(e),
                             attempt=attempt + 1)
            
            # Wait before retry
            if attempt < self.webhook_config["retry_attempts"] - 1:
                await asyncio.sleep(self.webhook_config["retry_delay"])
        
        logger.error("Webhook failed after all retries", url=webhook_url)
        return False
    
    async def _send_sms_notifications(
        self,
        notification_type: str,
        recipients: List[Dict[str, Any]],
        notification_data: Dict[str, Any]
    ):
        """Send SMS notifications (placeholder implementation)."""
        
        # This would integrate with SMS providers like Twilio, AWS SNS, etc.
        sms_recipients = [r for r in recipients if r.get("phone_number")]
        
        if not sms_recipients:
            return
        
        if not self.sms_config.get("api_key"):
            logger.warning("SMS notifications disabled - no SMS configuration")
            return
        
        try:
            # Prepare SMS message
            message_templates = {
                "workflow_started": "New document workflow started: {document_title}. Please check the system.",
                "approval_required": "Document approval required: {document_title}. Stage: {stage_name}",
                "workflow_escalated": "URGENT: Workflow escalated for {document_title}. Immediate action required.",
                "workflow_completed": "Workflow completed for {document_title}. Status: {final_status}"
            }
            
            message_template = message_templates.get(notification_type, "Workflow notification: {document_title}")
            message = message_template.format(**notification_data)
            
            # Placeholder for actual SMS sending logic
            logger.info("SMS notifications would be sent", 
                       type=notification_type,
                       recipient_count=len(sms_recipients),
                       message=message)
            
            # In a real implementation, this would integrate with:
            # - Twilio API
            # - AWS SNS
            # - Azure Communication Services
            # - etc.
            
        except Exception as e:
            logger.error("Failed to send SMS notifications", error=str(e))
            raise

# Global notification service instance
notification_service = NotificationService()