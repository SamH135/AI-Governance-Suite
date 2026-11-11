"""
Audit Logging Service
Provides comprehensive audit logging for compliance and security monitoring
"""

import os
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
import structlog
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

try:
    import elasticsearch
    from elasticsearch import AsyncElasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    elasticsearch = None
    AsyncElasticsearch = None

from .database import db_manager
from .exceptions import ValidationError, ExternalServiceError

logger = structlog.get_logger()

class AuditEventType(str, Enum):
    """Types of audit events."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTRATION = "user_registration"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_ASSIGNMENT = "role_assignment"
    ROLE_REMOVAL = "role_removal"
    
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_READ = "document_read"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"
    
    TEST_CREATE = "test_create"
    TEST_EXECUTE = "test_execute"
    TEST_UPDATE = "test_update"
    TEST_DELETE = "test_delete"
    
    EVALUATION_CREATE = "evaluation_create"
    EVALUATION_APPROVE = "evaluation_approve"
    EVALUATION_REJECT = "evaluation_reject"
    EVALUATION_UPDATE = "evaluation_update"
    
    PROMPT_CREATE = "prompt_create"
    PROMPT_EXECUTE = "prompt_execute"
    PROMPT_UPDATE = "prompt_update"
    PROMPT_DELETE = "prompt_delete"
    
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SECURITY_VIOLATION = "security_violation"
    API_ACCESS = "api_access"
    DATA_EXPORT = "data_export"
    COMPLIANCE_CHECK = "compliance_check"

class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditStatus(str, Enum):
    """Status of audit events."""
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class AuditEvent:
    """Represents an audit event."""
    event_id: str
    event_type: AuditEventType
    user_id: Optional[int]
    session_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    status: AuditStatus
    severity: AuditSeverity
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    compliance_tags: Optional[List[str]] = None
    risk_score: Optional[int] = None

# Database model for audit logs
Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=True)
    session_id = Column(String(255), nullable=True)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    action = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    compliance_tags = Column(JSON, nullable=True)
    risk_score = Column(Integer, nullable=True)
    indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLoggingService:
    """Service for comprehensive audit logging."""
    
    def __init__(self):
        self.initialized = False
        self.elasticsearch_client: Optional[AsyncElasticsearch] = None
        self.elasticsearch_index = "audit_logs"
        self.retention_days = 2555  # 7 years for compliance
        self.risk_threshold = 80
        
    async def initialize(self):
        """Initialize the audit logging service."""
        if self.initialized:
            return
        
        try:
            # Create database tables
            await self._create_tables()
            
            # Initialize Elasticsearch if available
            await self._initialize_elasticsearch()
            
            # Start background tasks
            asyncio.create_task(self._elasticsearch_sync_task())
            asyncio.create_task(self._cleanup_task())
            asyncio.create_task(self._risk_monitoring_task())
            
            self.initialized = True
            logger.info("Audit logging service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize audit logging service", error=str(e))
            raise ExternalServiceError("AuditLogging", f"Initialization failed: {str(e)}")
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[int],
        action: str,
        status: AuditStatus = AuditStatus.SUCCESS,
        severity: AuditSeverity = AuditSeverity.LOW,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        compliance_tags: Optional[List[str]] = None
    ) -> str:
        """Log an audit event."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Create audit event
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user_id,
                session_id=session_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                status=status,
                severity=severity,
                timestamp=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                old_values=old_values,
                new_values=new_values,
                compliance_tags=compliance_tags or [],
                risk_score=self._calculate_risk_score(event_type, status, severity)
            )
            
            # Store in database
            await self._store_audit_event(event)
            
            # Log structured event
            logger.info("Audit event logged", 
                       event_id=event.event_id,
                       event_type=event.event_type,
                       user_id=user_id,
                       action=action,
                       status=status,
                       severity=severity)
            
            # Check for high-risk events
            if event.risk_score and event.risk_score >= self.risk_threshold:
                await self._handle_high_risk_event(event)
            
            return event.event_id
            
        except Exception as e:
            logger.error("Failed to log audit event", 
                        event_type=event_type, error=str(e))
            raise ValidationError(f"Failed to log audit event: {str(e)}")
    
    async def get_audit_trail(
        self,
        user_id: Optional[int] = None,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        status: Optional[AuditStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get audit trail with filtering options."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Build query
                query = select(AuditLog)
                conditions = []
                
                if user_id:
                    conditions.append(AuditLog.user_id == user_id)
                if event_type:
                    conditions.append(AuditLog.event_type == event_type)
                if resource_type:
                    conditions.append(AuditLog.resource_type == resource_type)
                if resource_id:
                    conditions.append(AuditLog.resource_id == resource_id)
                if start_date:
                    conditions.append(AuditLog.timestamp >= start_date)
                if end_date:
                    conditions.append(AuditLog.timestamp <= end_date)
                if severity:
                    conditions.append(AuditLog.severity == severity)
                if status:
                    conditions.append(AuditLog.status == status)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Get total count
                count_query = select(func.count(AuditLog.id))
                if conditions:
                    count_query = count_query.where(and_(*conditions))
                
                total_result = await db.execute(count_query)
                total_count = total_result.scalar()
                
                # Get paginated results
                query = query.order_by(AuditLog.timestamp.desc())
                query = query.limit(limit).offset(offset)
                
                result = await db.execute(query)
                audit_logs = result.scalars().all()
                
                # Convert to dict format
                events = []
                for log in audit_logs:
                    events.append({
                        "event_id": log.event_id,
                        "event_type": log.event_type,
                        "user_id": log.user_id,
                        "session_id": log.session_id,
                        "resource_type": log.resource_type,
                        "resource_id": log.resource_id,
                        "action": log.action,
                        "status": log.status,
                        "severity": log.severity,
                        "timestamp": log.timestamp.isoformat(),
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent,
                        "details": log.details,
                        "old_values": log.old_values,
                        "new_values": log.new_values,
                        "compliance_tags": log.compliance_tags,
                        "risk_score": log.risk_score
                    })
                
                return {
                    "events": events,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
                
        except Exception as e:
            logger.error("Failed to get audit trail", error=str(e))
            raise ValidationError(f"Failed to get audit trail: {str(e)}")
    
    async def get_compliance_report(
        self,
        compliance_framework: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate compliance report for specific framework."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Define compliance tag mappings
            framework_tags = {
                "gdpr": ["data_access", "data_modification", "data_deletion", "consent"],
                "hipaa": ["phi_access", "phi_modification", "authentication", "authorization"],
                "sox": ["financial_data", "access_controls", "change_management"],
                "pci_dss": ["cardholder_data", "access_controls", "security_testing"],
                "iso27001": ["information_security", "access_management", "incident_response"]
            }
            
            relevant_tags = framework_tags.get(compliance_framework.lower(), [])
            
            async with db_manager.get_session() as db:
                # Get events with relevant compliance tags
                query = select(AuditLog).where(
                    and_(
                        AuditLog.timestamp >= start_date,
                        AuditLog.timestamp <= end_date,
                        or_(*[
                            AuditLog.compliance_tags.contains([tag])
                            for tag in relevant_tags
                        ])
                    )
                )
                
                result = await db.execute(query)
                audit_logs = result.scalars().all()
                
                # Analyze compliance metrics
                total_events = len(audit_logs)
                high_risk_events = len([log for log in audit_logs if log.risk_score and log.risk_score >= 70])
                failed_events = len([log for log in audit_logs if log.status == AuditStatus.FAILURE])
                
                # Event type breakdown
                event_breakdown = {}
                for log in audit_logs:
                    event_type = log.event_type
                    if event_type not in event_breakdown:
                        event_breakdown[event_type] = 0
                    event_breakdown[event_type] += 1
                
                # User activity summary
                user_activity = {}
                for log in audit_logs:
                    if log.user_id:
                        if log.user_id not in user_activity:
                            user_activity[log.user_id] = 0
                        user_activity[log.user_id] += 1
                
                # Compliance score calculation
                compliance_score = max(0, 100 - (high_risk_events * 5) - (failed_events * 3))
                
                return {
                    "compliance_framework": compliance_framework,
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "summary": {
                        "total_events": total_events,
                        "high_risk_events": high_risk_events,
                        "failed_events": failed_events,
                        "compliance_score": compliance_score
                    },
                    "event_breakdown": event_breakdown,
                    "top_users": dict(sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]),
                    "risk_analysis": {
                        "high_risk_percentage": (high_risk_events / total_events * 100) if total_events > 0 else 0,
                        "failure_rate": (failed_events / total_events * 100) if total_events > 0 else 0
                    }
                }
                
        except Exception as e:
            logger.error("Failed to generate compliance report", error=str(e))
            raise ValidationError(f"Failed to generate compliance report: {str(e)}")
    
    async def search_audit_logs(
        self,
        query_string: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search audit logs using Elasticsearch if available."""
        if not self.initialized:
            await self.initialize()
        
        if not self.elasticsearch_client:
            # Fallback to database search
            return await self._search_database(query_string, filters, limit)
        
        try:
            # Build Elasticsearch query
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query_string,
                                    "fields": ["action", "details", "resource_type", "event_type"]
                                }
                            }
                        ]
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": limit
            }
            
            # Add filters
            if filters:
                for field, value in filters.items():
                    es_query["query"]["bool"]["must"].append({
                        "term": {field: value}
                    })
            
            # Execute search
            response = await self.elasticsearch_client.search(
                index=self.elasticsearch_index,
                body=es_query
            )
            
            # Format results
            results = []
            for hit in response["hits"]["hits"]:
                results.append(hit["_source"])
            
            return results
            
        except Exception as e:
            logger.error("Elasticsearch search failed, falling back to database", error=str(e))
            return await self._search_database(query_string, filters, limit)
    
    # Private helper methods
    async def _create_tables(self):
        """Create audit log database tables."""
        try:
            async with db_manager.get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Audit log tables created")
        except Exception as e:
            logger.error("Failed to create audit log tables", error=str(e))
            raise
    
    async def _initialize_elasticsearch(self):
        """Initialize Elasticsearch client if available."""
        if not ELASTICSEARCH_AVAILABLE:
            logger.info("Elasticsearch not available, using database only")
            return
        
        try:
            elasticsearch_url = os.getenv("ELASTICSEARCH_URL")
            if elasticsearch_url:
                self.elasticsearch_client = AsyncElasticsearch([elasticsearch_url])
                
                # Test connection
                await self.elasticsearch_client.ping()
                
                # Create index if it doesn't exist
                index_exists = await self.elasticsearch_client.indices.exists(index=self.elasticsearch_index)
                if not index_exists:
                    await self._create_elasticsearch_index()
                
                logger.info("Elasticsearch initialized for audit logging")
            
        except Exception as e:
            logger.warning("Failed to initialize Elasticsearch, using database only", error=str(e))
            self.elasticsearch_client = None
    
    async def _create_elasticsearch_index(self):
        """Create Elasticsearch index for audit logs."""
        index_mapping = {
            "mappings": {
                "properties": {
                    "event_id": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "user_id": {"type": "integer"},
                    "session_id": {"type": "keyword"},
                    "resource_type": {"type": "keyword"},
                    "resource_id": {"type": "keyword"},
                    "action": {"type": "text", "analyzer": "standard"},
                    "status": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "ip_address": {"type": "ip"},
                    "user_agent": {"type": "text"},
                    "details": {"type": "object"},
                    "old_values": {"type": "object"},
                    "new_values": {"type": "object"},
                    "compliance_tags": {"type": "keyword"},
                    "risk_score": {"type": "integer"}
                }
            }
        }
        
        await self.elasticsearch_client.indices.create(
            index=self.elasticsearch_index,
            body=index_mapping
        )
    
    async def _store_audit_event(self, event: AuditEvent):
        """Store audit event in database."""
        async with db_manager.get_session() as db:
            audit_log = AuditLog(
                event_id=event.event_id,
                event_type=event.event_type,
                user_id=event.user_id,
                session_id=event.session_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action=event.action,
                status=event.status,
                severity=event.severity,
                timestamp=event.timestamp,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details=event.details,
                old_values=event.old_values,
                new_values=event.new_values,
                compliance_tags=event.compliance_tags,
                risk_score=event.risk_score
            )
            
            db.add(audit_log)
            await db.commit()
    
    def _calculate_risk_score(
        self,
        event_type: AuditEventType,
        status: AuditStatus,
        severity: AuditSeverity
    ) -> int:
        """Calculate risk score for an audit event."""
        base_scores = {
            AuditEventType.SECURITY_VIOLATION: 90,
            AuditEventType.PERMISSION_GRANT: 70,
            AuditEventType.ROLE_ASSIGNMENT: 60,
            AuditEventType.SYSTEM_CONFIG_CHANGE: 80,
            AuditEventType.DATA_EXPORT: 50,
            AuditEventType.DOCUMENT_DELETE: 40,
            AuditEventType.USER_LOGIN: 10
        }
        
        severity_multipliers = {
            AuditSeverity.LOW: 0.5,
            AuditSeverity.MEDIUM: 1.0,
            AuditSeverity.HIGH: 1.5,
            AuditSeverity.CRITICAL: 2.0
        }
        
        status_modifiers = {
            AuditStatus.SUCCESS: 0,
            AuditStatus.WARNING: 10,
            AuditStatus.FAILURE: 20,
            AuditStatus.ERROR: 25
        }
        
        base_score = base_scores.get(event_type, 20)
        multiplier = severity_multipliers.get(severity, 1.0)
        modifier = status_modifiers.get(status, 0)
        
        risk_score = int((base_score * multiplier) + modifier)
        return min(100, max(0, risk_score))
    
    async def _handle_high_risk_event(self, event: AuditEvent):
        """Handle high-risk audit events."""
        logger.warning("High-risk audit event detected",
                      event_id=event.event_id,
                      event_type=event.event_type,
                      risk_score=event.risk_score,
                      user_id=event.user_id)
        
        # Here you could implement notifications, alerts, or automatic responses
        # For example: send email alerts, trigger security workflows, etc.
    
    async def _elasticsearch_sync_task(self):
        """Background task to sync database events to Elasticsearch."""
        if not self.elasticsearch_client:
            return
        
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                async with db_manager.get_session() as db:
                    # Get unindexed events
                    query = select(AuditLog).where(AuditLog.indexed == False).limit(100)
                    result = await db.execute(query)
                    unindexed_logs = result.scalars().all()
                    
                    for log in unindexed_logs:
                        try:
                            # Index in Elasticsearch
                            doc = {
                                "event_id": log.event_id,
                                "event_type": log.event_type,
                                "user_id": log.user_id,
                                "session_id": log.session_id,
                                "resource_type": log.resource_type,
                                "resource_id": log.resource_id,
                                "action": log.action,
                                "status": log.status,
                                "severity": log.severity,
                                "timestamp": log.timestamp,
                                "ip_address": log.ip_address,
                                "user_agent": log.user_agent,
                                "details": log.details,
                                "old_values": log.old_values,
                                "new_values": log.new_values,
                                "compliance_tags": log.compliance_tags,
                                "risk_score": log.risk_score
                            }
                            
                            await self.elasticsearch_client.index(
                                index=self.elasticsearch_index,
                                id=log.event_id,
                                body=doc
                            )
                            
                            # Mark as indexed
                            log.indexed = True
                            await db.commit()
                            
                        except Exception as e:
                            logger.error("Failed to index audit log in Elasticsearch",
                                       event_id=log.event_id, error=str(e))
                
            except Exception as e:
                logger.error("Elasticsearch sync task error", error=str(e))
    
    async def _cleanup_task(self):
        """Background task to clean up old audit logs."""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Run daily
                
                cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
                
                async with db_manager.get_session() as db:
                    # Count old records
                    count_query = select(func.count(AuditLog.id)).where(
                        AuditLog.timestamp < cutoff_date
                    )
                    count_result = await db.execute(count_query)
                    old_count = count_result.scalar()
                    
                    if old_count > 0:
                        # Delete old records in batches
                        batch_size = 1000
                        deleted_total = 0
                        
                        while True:
                            delete_query = select(AuditLog.id).where(
                                AuditLog.timestamp < cutoff_date
                            ).limit(batch_size)
                            
                            result = await db.execute(delete_query)
                            ids_to_delete = result.scalars().all()
                            
                            if not ids_to_delete:
                                break
                            
                            for audit_id in ids_to_delete:
                                await db.execute(
                                    "DELETE FROM audit_logs WHERE id = :id",
                                    {"id": audit_id}
                                )
                            
                            await db.commit()
                            deleted_total += len(ids_to_delete)
                        
                        logger.info("Audit log cleanup completed",
                                   deleted_count=deleted_total,
                                   cutoff_date=cutoff_date.isoformat())
                
            except Exception as e:
                logger.error("Audit log cleanup task error", error=str(e))
    
    async def _risk_monitoring_task(self):
        """Background task to monitor risk patterns."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly
                
                # Check for suspicious patterns in the last hour
                start_time = datetime.utcnow() - timedelta(hours=1)
                
                async with db_manager.get_session() as db:
                    # Check for multiple failed logins
                    failed_login_query = select(AuditLog).where(
                        and_(
                            AuditLog.event_type == AuditEventType.USER_LOGIN,
                            AuditLog.status == AuditStatus.FAILURE,
                            AuditLog.timestamp >= start_time
                        )
                    )
                    
                    result = await db.execute(failed_login_query)
                    failed_logins = result.scalars().all()
                    
                    # Group by IP address
                    ip_failures = {}
                    for login in failed_logins:
                        if login.ip_address:
                            if login.ip_address not in ip_failures:
                                ip_failures[login.ip_address] = 0
                            ip_failures[login.ip_address] += 1
                    
                    # Alert on suspicious activity
                    for ip, count in ip_failures.items():
                        if count >= 5:  # 5 or more failed attempts
                            await self.log_event(
                                event_type=AuditEventType.SECURITY_VIOLATION,
                                user_id=None,
                                action=f"Multiple failed login attempts from IP {ip}",
                                status=AuditStatus.WARNING,
                                severity=AuditSeverity.HIGH,
                                ip_address=ip,
                                details={"failed_attempts": count, "timeframe": "1_hour"}
                            )
                
            except Exception as e:
                logger.error("Risk monitoring task error", error=str(e))
    
    async def _search_database(
        self,
        query_string: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback search using database."""
        async with db_manager.get_session() as db:
            query = select(AuditLog)
            conditions = []
            
            # Simple text search in action field
            if query_string:
                conditions.append(AuditLog.action.contains(query_string))
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(AuditLog, field):
                        conditions.append(getattr(AuditLog, field) == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
            
            result = await db.execute(query)
            audit_logs = result.scalars().all()
            
            return [
                {
                    "event_id": log.event_id,
                    "event_type": log.event_type,
                    "user_id": log.user_id,
                    "action": log.action,
                    "status": log.status,
                    "severity": log.severity,
                    "timestamp": log.timestamp.isoformat(),
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details
                }
                for log in audit_logs
            ]

# Global audit logging service instance
audit_logging_service = AuditLoggingService()