"""
Document Change Tracking Service
Provides version control and change history for documents
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from difflib import unified_diff

from ...shared.database import db_manager
from ...shared.models import GeneratedDocument, User
from ...shared.exceptions import ValidationError, NotFoundError

logger = structlog.get_logger()

class ChangeType(str, Enum):
    """Types of document changes."""
    CREATED = "created"
    CONTENT_MODIFIED = "content_modified"
    METADATA_MODIFIED = "metadata_modified"
    STATUS_CHANGED = "status_changed"
    WORKFLOW_UPDATED = "workflow_updated"
    APPROVAL_ADDED = "approval_added"
    COMMENT_ADDED = "comment_added"
    DELETED = "deleted"
    RESTORED = "restored"

class DocumentChangeTrackingService:
    """Service for tracking document changes and maintaining version history."""
    
    def __init__(self):
        self.initialized = False
        self.max_versions_per_document = 50
        self.diff_context_lines = 3
    
    async def initialize(self):
        """Initialize the change tracking service."""
        if self.initialized:
            return
        
        try:
            self.initialized = True
            logger.info("Document change tracking service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize change tracking service", error=str(e))
            raise ValidationError(f"Change tracking service initialization failed: {str(e)}")
    
    async def track_change(
        self,
        document_id: int,
        change_type: ChangeType,
        user_id: int,
        old_value: Any = None,
        new_value: Any = None,
        field_name: Optional[str] = None,
        change_description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Track a change to a document."""
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
                
                # Create change record
                change_record = {
                    "change_id": f"change_{document_id}_{int(datetime.utcnow().timestamp())}",
                    "document_id": document_id,
                    "change_type": change_type,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "field_name": field_name,
                    "old_value": self._serialize_value(old_value),
                    "new_value": self._serialize_value(new_value),
                    "change_description": change_description or self._generate_change_description(
                        change_type, field_name, old_value, new_value
                    ),
                    "metadata": metadata or {},
                    "content_hash": self._calculate_content_hash(document),
                    "diff": self._generate_diff(old_value, new_value) if change_type == ChangeType.CONTENT_MODIFIED else None
                }
                
                # Store change in document metadata
                if not document.metadata:
                    document.metadata = {}
                
                if "change_history" not in document.metadata:
                    document.metadata["change_history"] = []
                
                document.metadata["change_history"].append(change_record)
                
                # Limit history size
                if len(document.metadata["change_history"]) > self.max_versions_per_document:
                    document.metadata["change_history"] = document.metadata["change_history"][-self.max_versions_per_document:]
                
                # Update document modified timestamp
                document.updated_at = datetime.utcnow()
                
                await db.commit()
                
                logger.info("Document change tracked", 
                           document_id=document_id,
                           change_type=change_type,
                           change_id=change_record["change_id"],
                           user_id=user_id)
                
                return change_record
                
        except Exception as e:
            logger.error("Failed to track document change", 
                        document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to track document change: {str(e)}")
    
    async def get_change_history(
        self,
        document_id: int,
        limit: Optional[int] = None,
        change_type: Optional[ChangeType] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get change history for a document."""
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
                
                # Get change history from document metadata
                change_history = document.metadata.get("change_history", [])
                
                # Apply filters
                filtered_history = []
                for change in change_history:
                    # Filter by change type
                    if change_type and change.get("change_type") != change_type:
                        continue
                    
                    # Filter by user
                    if user_id and change.get("user_id") != user_id:
                        continue
                    
                    # Filter by date range
                    change_timestamp = datetime.fromisoformat(change.get("timestamp", ""))
                    if start_date and change_timestamp < start_date:
                        continue
                    if end_date and change_timestamp > end_date:
                        continue
                    
                    # Enhance change record with user information
                    enhanced_change = await self._enhance_change_record(change, db)
                    filtered_history.append(enhanced_change)
                
                # Sort by timestamp (newest first)
                filtered_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                
                # Apply limit
                if limit:
                    filtered_history = filtered_history[:limit]
                
                return filtered_history
                
        except Exception as e:
            logger.error("Failed to get change history", 
                        document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to get change history: {str(e)}")
    
    async def get_document_version(
        self,
        document_id: int,
        version_timestamp: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific version of a document based on timestamp."""
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
                
                change_history = document.metadata.get("change_history", [])
                
                # Find the change at or before the requested timestamp
                target_timestamp = datetime.fromisoformat(version_timestamp)
                
                # Sort changes by timestamp
                sorted_changes = sorted(
                    change_history,
                    key=lambda x: datetime.fromisoformat(x.get("timestamp", "")),
                    reverse=True
                )
                
                # Reconstruct document state at the target timestamp
                document_version = {
                    "document_id": document_id,
                    "version_timestamp": version_timestamp,
                    "content": document.content,
                    "metadata": document.metadata.copy(),
                    "status": document.status,
                    "title": document.title
                }
                
                # Apply changes in reverse order until we reach the target timestamp
                for change in sorted_changes:
                    change_timestamp = datetime.fromisoformat(change.get("timestamp", ""))
                    
                    if change_timestamp <= target_timestamp:
                        break
                    
                    # Reverse the change
                    if change.get("change_type") == ChangeType.CONTENT_MODIFIED:
                        field_name = change.get("field_name")
                        old_value = self._deserialize_value(change.get("old_value"))
                        
                        if field_name == "content":
                            document_version["content"] = old_value
                        elif field_name == "title":
                            document_version["title"] = old_value
                        elif field_name == "status":
                            document_version["status"] = old_value
                
                return document_version
                
        except Exception as e:
            logger.error("Failed to get document version", 
                        document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to get document version: {str(e)}")
    
    async def compare_versions(
        self,
        document_id: int,
        version1_timestamp: str,
        version2_timestamp: str
    ) -> Dict[str, Any]:
        """Compare two versions of a document."""
        if not self.initialized:
            await self.initialize()
        
        try:
            version1 = await self.get_document_version(document_id, version1_timestamp)
            version2 = await self.get_document_version(document_id, version2_timestamp)
            
            if not version1 or not version2:
                raise ValidationError("One or both versions not found")
            
            # Generate comparison
            comparison = {
                "document_id": document_id,
                "version1_timestamp": version1_timestamp,
                "version2_timestamp": version2_timestamp,
                "changes": [],
                "content_diff": None,
                "metadata_diff": None
            }
            
            # Compare content
            if version1["content"] != version2["content"]:
                content_diff = self._generate_diff(
                    version1["content"], 
                    version2["content"]
                )
                comparison["content_diff"] = content_diff
                comparison["changes"].append({
                    "field": "content",
                    "type": "modified",
                    "description": "Document content changed"
                })
            
            # Compare title
            if version1["title"] != version2["title"]:
                comparison["changes"].append({
                    "field": "title",
                    "type": "modified",
                    "old_value": version1["title"],
                    "new_value": version2["title"],
                    "description": f"Title changed from '{version1['title']}' to '{version2['title']}'"
                })
            
            # Compare status
            if version1["status"] != version2["status"]:
                comparison["changes"].append({
                    "field": "status",
                    "type": "modified",
                    "old_value": version1["status"],
                    "new_value": version2["status"],
                    "description": f"Status changed from '{version1['status']}' to '{version2['status']}'"
                })
            
            return comparison
            
        except Exception as e:
            logger.error("Failed to compare document versions", 
                        document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to compare document versions: {str(e)}")
    
    async def restore_version(
        self,
        document_id: int,
        version_timestamp: str,
        user_id: int,
        restore_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Restore a document to a previous version."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get the target version
                target_version = await self.get_document_version(document_id, version_timestamp)
                if not target_version:
                    raise NotFoundError("Document version", version_timestamp)
                
                # Get current document
                document_result = await db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                document = document_result.scalar_one_or_none()
                
                if not document:
                    raise NotFoundError("Document", document_id)
                
                # Store current state for tracking
                current_content = document.content
                current_title = document.title
                current_status = document.status
                
                # Restore document to target version
                document.content = target_version["content"]
                document.title = target_version["title"]
                document.status = target_version["status"]
                document.updated_at = datetime.utcnow()
                
                await db.commit()
                
                # Track the restoration
                await self.track_change(
                    document_id,
                    ChangeType.RESTORED,
                    user_id,
                    old_value={
                        "content": current_content,
                        "title": current_title,
                        "status": current_status
                    },
                    new_value={
                        "content": target_version["content"],
                        "title": target_version["title"],
                        "status": target_version["status"]
                    },
                    change_description=f"Document restored to version from {version_timestamp}. Reason: {restore_reason or 'Not specified'}",
                    metadata={
                        "restored_from_timestamp": version_timestamp,
                        "restore_reason": restore_reason
                    }
                )
                
                logger.info("Document version restored", 
                           document_id=document_id,
                           version_timestamp=version_timestamp,
                           user_id=user_id)
                
                return {
                    "document_id": document_id,
                    "restored_from": version_timestamp,
                    "restoration_timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "restore_reason": restore_reason
                }
                
        except Exception as e:
            logger.error("Failed to restore document version", 
                        document_id=document_id, error=str(e))
            raise ValidationError(f"Failed to restore document version: {str(e)}")
    
    async def get_change_statistics(
        self,
        document_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get statistics about document changes."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Build query based on filters
                query = select(GeneratedDocument)
                
                if document_id:
                    query = query.where(GeneratedDocument.document_id == document_id)
                
                documents_result = await db.execute(query)
                documents = documents_result.scalars().all()
                
                # Collect all changes
                all_changes = []
                for document in documents:
                    change_history = document.metadata.get("change_history", [])
                    
                    for change in change_history:
                        # Apply filters
                        if user_id and change.get("user_id") != user_id:
                            continue
                        
                        change_timestamp = datetime.fromisoformat(change.get("timestamp", ""))
                        if start_date and change_timestamp < start_date:
                            continue
                        if end_date and change_timestamp > end_date:
                            continue
                        
                        all_changes.append(change)
                
                # Calculate statistics
                stats = {
                    "total_changes": len(all_changes),
                    "changes_by_type": {},
                    "changes_by_user": {},
                    "changes_by_date": {},
                    "most_active_documents": {},
                    "average_changes_per_document": 0
                }
                
                # Group by change type
                for change in all_changes:
                    change_type = change.get("change_type", "unknown")
                    stats["changes_by_type"][change_type] = stats["changes_by_type"].get(change_type, 0) + 1
                
                # Group by user
                for change in all_changes:
                    user_id = change.get("user_id", "unknown")
                    stats["changes_by_user"][str(user_id)] = stats["changes_by_user"].get(str(user_id), 0) + 1
                
                # Group by date
                for change in all_changes:
                    date = change.get("timestamp", "")[:10]  # Extract date part
                    stats["changes_by_date"][date] = stats["changes_by_date"].get(date, 0) + 1
                
                # Most active documents
                for change in all_changes:
                    doc_id = change.get("document_id", "unknown")
                    stats["most_active_documents"][str(doc_id)] = stats["most_active_documents"].get(str(doc_id), 0) + 1
                
                # Average changes per document
                if documents:
                    stats["average_changes_per_document"] = len(all_changes) / len(documents)
                
                return stats
                
        except Exception as e:
            logger.error("Failed to get change statistics", error=str(e))
            raise ValidationError(f"Failed to get change statistics: {str(e)}")
    
    # Helper methods
    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for storage."""
        if value is None:
            return None
        
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        
        return str(value)
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize a stored value."""
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _calculate_content_hash(self, document: GeneratedDocument) -> str:
        """Calculate a hash of the document content for change detection."""
        content_str = json.dumps({
            "title": document.title,
            "content": document.content,
            "status": document.status,
            "metadata": document.metadata
        }, sort_keys=True, default=str)
        
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _generate_change_description(
        self,
        change_type: ChangeType,
        field_name: Optional[str],
        old_value: Any,
        new_value: Any
    ) -> str:
        """Generate a human-readable description of the change."""
        
        if change_type == ChangeType.CREATED:
            return "Document created"
        elif change_type == ChangeType.DELETED:
            return "Document deleted"
        elif change_type == ChangeType.RESTORED:
            return "Document restored from previous version"
        elif change_type == ChangeType.CONTENT_MODIFIED:
            if field_name:
                return f"Field '{field_name}' modified"
            return "Document content modified"
        elif change_type == ChangeType.STATUS_CHANGED:
            return f"Status changed from '{old_value}' to '{new_value}'"
        elif change_type == ChangeType.WORKFLOW_UPDATED:
            return "Workflow status updated"
        elif change_type == ChangeType.APPROVAL_ADDED:
            return "Approval added to workflow"
        elif change_type == ChangeType.COMMENT_ADDED:
            return "Comment added to document"
        else:
            return f"Document {change_type.value}"
    
    def _generate_diff(self, old_value: Any, new_value: Any) -> Optional[str]:
        """Generate a diff between two values."""
        if old_value is None or new_value is None:
            return None
        
        old_str = str(old_value)
        new_str = str(new_value)
        
        # For short strings, return simple before/after
        if len(old_str) < 100 and len(new_str) < 100:
            return f"Before: {old_str}\nAfter: {new_str}"
        
        # For longer content, generate unified diff
        old_lines = old_str.splitlines(keepends=True)
        new_lines = new_str.splitlines(keepends=True)
        
        diff = list(unified_diff(
            old_lines,
            new_lines,
            fromfile="before",
            tofile="after",
            n=self.diff_context_lines
        ))
        
        return "".join(diff) if diff else None
    
    async def _enhance_change_record(self, change: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """Enhance a change record with additional information like user details."""
        enhanced_change = change.copy()
        
        # Add user information
        user_id = change.get("user_id")
        if user_id:
            try:
                user_result = await db.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    enhanced_change["user_name"] = user.full_name
                    enhanced_change["user_email"] = user.email
            except Exception:
                # Don't fail if user lookup fails
                pass
        
        return enhanced_change

# Global change tracking service instance
change_tracking_service = DocumentChangeTrackingService()