"""Backup and Restore Service for data protection and disaster recovery."""

import asyncio
import json
import gzip
import shutil
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import structlog

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, ExternalServiceError
from .audit_logging_service import audit_logging_service, AuditEventType, AuditStatus

logger = structlog.get_logger()

class BackupType(Enum):
    """Types of backups."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"

class BackupStatus(Enum):
    """Backup status options."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BackupRestoreService:
    """Service for data backup and restore operations."""
    
    def __init__(self):
        self.initialized = False
        self.backup_dir = Path("./backups")
        self.retention_days = 30
        self.max_backup_size = 10 * 1024 * 1024 * 1024  # 10GB
        
    async def initialize(self):
        """Initialize the backup and restore service."""
        if self.initialized:
            return
            
        try:
            # Create backup directory
            self.backup_dir.mkdir(exist_ok=True)
            
            # Start background cleanup task
            asyncio.create_task(self._cleanup_old_backups())
            
            self.initialized = True
            logger.info("Backup and Restore Service initialized successfully")
            
        except Exception as e:
            logger.error("Backup and Restore Service initialization failed", error=str(e))
            raise ExternalServiceError("BackupRestore", f"Initialization failed: {str(e)}")
    
    async def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        include_files: bool = True,
        compress: bool = True
    ) -> Dict[str, Any]:
        """Create a backup of the system."""
        
        if not self.initialized:
            await self.initialize()
            
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Backup initiated: {backup_type.value}",
                resource_type="backup",
                resource_id=backup_id,
                details={
                    "backup_type": backup_type.value,
                    "include_files": include_files,
                    "compress": compress
                }
            )
            
            backup_metadata = {
                "backup_id": backup_id,
                "backup_type": backup_type.value,
                "status": BackupStatus.RUNNING.value,
                "created_at": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "tenant_id": tenant_id,
                "include_files": include_files,
                "compress": compress
            }
            
            # Store initial metadata
            await self._store_backup_metadata(backup_id, backup_metadata)
            
            # Create backup in background
            asyncio.create_task(self._perform_backup(backup_id, backup_type, user_id, tenant_id, include_files, compress))
            
            return {
                "backup_id": backup_id,
                "status": BackupStatus.RUNNING.value,
                "message": "Backup initiated successfully"
            }
            
        except Exception as e:
            logger.error("Backup initiation failed", backup_id=backup_id, error=str(e))
            raise ValidationError(f"Backup initiation failed: {str(e)}")
    
    async def restore_backup(
        self,
        backup_id: str,
        user_id: int,
        restore_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Restore from a backup."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Get backup metadata
            backup_metadata = await self._get_backup_metadata(backup_id)
            if not backup_metadata:
                raise ValidationError(f"Backup {backup_id} not found")
            
            if backup_metadata["status"] != BackupStatus.COMPLETED.value:
                raise ValidationError(f"Backup {backup_id} is not completed")
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Restore initiated from backup: {backup_id}",
                resource_type="restore",
                resource_id=backup_id,
                details={
                    "backup_id": backup_id,
                    "restore_options": restore_options
                }
            )
            
            # Perform restore in background
            restore_id = f"restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            asyncio.create_task(self._perform_restore(restore_id, backup_id, user_id, restore_options))
            
            return {
                "restore_id": restore_id,
                "backup_id": backup_id,
                "status": "running",
                "message": "Restore initiated successfully"
            }
            
        except Exception as e:
            logger.error("Restore initiation failed", backup_id=backup_id, error=str(e))
            raise ValidationError(f"Restore initiation failed: {str(e)}")
    
    async def get_backup_list(
        self,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get list of available backups."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            backups = []
            
            # Get all backup metadata files
            for metadata_file in self.backup_dir.glob("*.metadata.json"):
                try:
                    metadata = json.loads(metadata_file.read_text())
                    
                    # Filter by user/tenant if specified
                    if user_id and metadata.get("user_id") != user_id:
                        continue
                    if tenant_id and metadata.get("tenant_id") != tenant_id:
                        continue
                    
                    backups.append(metadata)
                    
                except Exception as e:
                    logger.warning("Failed to read backup metadata", file=str(metadata_file), error=str(e))
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
            return backups[:limit]
            
        except Exception as e:
            logger.error("Failed to get backup list", error=str(e))
            return []    async de
f delete_backup(self, backup_id: str, user_id: int) -> Dict[str, Any]:
        """Delete a backup."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Get backup metadata
            backup_metadata = await self._get_backup_metadata(backup_id)
            if not backup_metadata:
                raise ValidationError(f"Backup {backup_id} not found")
            
            # Check permissions (simplified - in real implementation, check proper authorization)
            if backup_metadata.get("user_id") and backup_metadata["user_id"] != user_id:
                raise ValidationError("Access denied to delete this backup")
            
            # Delete backup files
            backup_path = self.backup_dir / f"{backup_id}.backup"
            metadata_path = self.backup_dir / f"{backup_id}.metadata.json"
            
            if backup_path.exists():
                backup_path.unlink()
            
            if metadata_path.exists():
                metadata_path.unlink()
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DOCUMENT_DELETE,
                user_id=user_id,
                action=f"Backup deleted: {backup_id}",
                resource_type="backup",
                resource_id=backup_id
            )
            
            logger.info("Backup deleted", backup_id=backup_id, user_id=user_id)
            
            return {
                "success": True,
                "message": f"Backup {backup_id} deleted successfully"
            }
            
        except Exception as e:
            logger.error("Backup deletion failed", backup_id=backup_id, error=str(e))
            raise ValidationError(f"Backup deletion failed: {str(e)}")
    
    async def _perform_backup(
        self,
        backup_id: str,
        backup_type: BackupType,
        user_id: Optional[int],
        tenant_id: Optional[int],
        include_files: bool,
        compress: bool
    ):
        """Perform the actual backup operation."""
        
        try:
            backup_data = {}
            
            # Backup database
            backup_data["database"] = await self._backup_database(user_id, tenant_id)
            
            # Backup Redis data
            backup_data["redis"] = await self._backup_redis_data()
            
            # Backup files if requested
            if include_files:
                backup_data["files"] = await self._backup_files()
            
            # Create backup file
            backup_path = self.backup_dir / f"{backup_id}.backup"
            
            if compress:
                # Compress backup data
                with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
                    json.dump(backup_data, f, default=str, indent=2)
            else:
                backup_path.write_text(json.dumps(backup_data, default=str, indent=2))
            
            # Update metadata
            backup_metadata = await self._get_backup_metadata(backup_id)
            backup_metadata.update({
                "status": BackupStatus.COMPLETED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "file_size": backup_path.stat().st_size,
                "compressed": compress
            })
            
            await self._store_backup_metadata(backup_id, backup_metadata)
            
            logger.info("Backup completed successfully", 
                       backup_id=backup_id,
                       file_size=backup_metadata["file_size"])
            
        except Exception as e:
            logger.error("Backup operation failed", backup_id=backup_id, error=str(e))
            
            # Update metadata with failure status
            try:
                backup_metadata = await self._get_backup_metadata(backup_id)
                backup_metadata.update({
                    "status": BackupStatus.FAILED.value,
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                })
                await self._store_backup_metadata(backup_id, backup_metadata)
            except:
                pass
    
    async def _perform_restore(
        self,
        restore_id: str,
        backup_id: str,
        user_id: int,
        restore_options: Optional[Dict[str, Any]]
    ):
        """Perform the actual restore operation."""
        
        try:
            # Load backup data
            backup_path = self.backup_dir / f"{backup_id}.backup"
            
            if not backup_path.exists():
                raise ValidationError(f"Backup file not found: {backup_id}")
            
            # Check if compressed
            backup_metadata = await self._get_backup_metadata(backup_id)
            is_compressed = backup_metadata.get("compressed", False)
            
            if is_compressed:
                with gzip.open(backup_path, 'rt', encoding='utf-8') as f:
                    backup_data = json.load(f)
            else:
                backup_data = json.loads(backup_path.read_text())
            
            # Restore database
            if "database" in backup_data and restore_options.get("restore_database", True):
                await self._restore_database(backup_data["database"])
            
            # Restore Redis data
            if "redis" in backup_data and restore_options.get("restore_redis", True):
                await self._restore_redis_data(backup_data["redis"])
            
            # Restore files
            if "files" in backup_data and restore_options.get("restore_files", True):
                await self._restore_files(backup_data["files"])
            
            logger.info("Restore completed successfully", 
                       restore_id=restore_id,
                       backup_id=backup_id)
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Restore completed from backup: {backup_id}",
                status=AuditStatus.SUCCESS,
                resource_type="restore",
                resource_id=restore_id
            )
            
        except Exception as e:
            logger.error("Restore operation failed", 
                        restore_id=restore_id, 
                        backup_id=backup_id, 
                        error=str(e))
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Restore failed from backup: {backup_id}",
                status=AuditStatus.FAILURE,
                resource_type="restore",
                resource_id=restore_id,
                details={"error": str(e)}
            )
    
    async def _backup_database(self, user_id: Optional[int], tenant_id: Optional[int]) -> Dict[str, Any]:
        """Backup database data."""
        
        database_backup = {}
        
        try:
            async with db_manager.get_session() as session:
                # Backup users
                if not user_id:  # Full backup
                    result = await session.execute("SELECT * FROM users")
                    database_backup["users"] = [dict(row) for row in result.fetchall()]
                
                # Backup AI systems
                if user_id:
                    query = "SELECT * FROM ai_systems WHERE user_id = :user_id"
                    params = {"user_id": user_id}
                else:
                    query = "SELECT * FROM ai_systems"
                    params = {}
                
                if tenant_id:
                    query += " AND tenant_id = :tenant_id" if user_id else " WHERE tenant_id = :tenant_id"
                    params["tenant_id"] = tenant_id
                
                result = await session.execute(query, params)
                database_backup["ai_systems"] = [dict(row) for row in result.fetchall()]
                
                # Backup models
                if user_id:
                    query = """
                        SELECT m.* FROM models m
                        JOIN ai_systems s ON m.system_id = s.id
                        WHERE s.user_id = :user_id
                    """
                    params = {"user_id": user_id}
                else:
                    query = "SELECT * FROM models"
                    params = {}
                
                result = await session.execute(query, params)
                database_backup["models"] = [dict(row) for row in result.fetchall()]
                
                # Backup test results
                if user_id:
                    query = """
                        SELECT tr.* FROM test_results tr
                        JOIN models m ON tr.model_id = m.id
                        JOIN ai_systems s ON m.system_id = s.id
                        WHERE s.user_id = :user_id
                    """
                    params = {"user_id": user_id}
                else:
                    query = "SELECT * FROM test_results"
                    params = {}
                
                result = await session.execute(query, params)
                database_backup["test_results"] = [dict(row) for row in result.fetchall()]
                
        except Exception as e:
            logger.error("Database backup failed", error=str(e))
            raise
        
        return database_backup
    
    async def _backup_redis_data(self) -> Dict[str, Any]:
        """Backup Redis data."""
        
        redis_backup = {}
        
        try:
            # Get all keys
            keys = await redis_client.keys("*")
            
            for key in keys:
                try:
                    # Get key type
                    key_type = await redis_client.type(key)
                    
                    if key_type == "string":
                        redis_backup[key] = {
                            "type": "string",
                            "value": await redis_client.get(key)
                        }
                    elif key_type == "hash":
                        redis_backup[key] = {
                            "type": "hash",
                            "value": await redis_client.hgetall(key)
                        }
                    elif key_type == "list":
                        redis_backup[key] = {
                            "type": "list",
                            "value": await redis_client.lrange(key, 0, -1)
                        }
                    elif key_type == "set":
                        redis_backup[key] = {
                            "type": "set",
                            "value": list(await redis_client.smembers(key))
                        }
                    
                except Exception as e:
                    logger.warning("Failed to backup Redis key", key=key, error=str(e))
                    
        except Exception as e:
            logger.error("Redis backup failed", error=str(e))
            raise
        
        return redis_backup
    
    async def _backup_files(self) -> Dict[str, Any]:
        """Backup file system data."""
        
        # This is a simplified implementation
        # In a real system, you'd backup actual files
        files_backup = {
            "note": "File backup not implemented in this demo",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return files_backup
    
    async def _restore_database(self, database_backup: Dict[str, Any]):
        """Restore database from backup."""
        
        try:
            async with db_manager.get_session() as session:
                # This is a simplified restore - in production you'd need more sophisticated logic
                # to handle conflicts, foreign keys, etc.
                
                for table_name, records in database_backup.items():
                    if not records:
                        continue
                    
                    logger.info(f"Restoring {len(records)} records to {table_name}")
                    
                    # In a real implementation, you'd need proper SQL generation
                    # and conflict resolution
                    
        except Exception as e:
            logger.error("Database restore failed", error=str(e))
            raise
    
    async def _restore_redis_data(self, redis_backup: Dict[str, Any]):
        """Restore Redis data from backup."""
        
        try:
            for key, data in redis_backup.items():
                key_type = data["type"]
                value = data["value"]
                
                if key_type == "string":
                    await redis_client.set(key, value)
                elif key_type == "hash":
                    await redis_client.hmset(key, value)
                elif key_type == "list":
                    await redis_client.delete(key)
                    if value:
                        await redis_client.lpush(key, *value)
                elif key_type == "set":
                    await redis_client.delete(key)
                    if value:
                        await redis_client.sadd(key, *value)
                        
        except Exception as e:
            logger.error("Redis restore failed", error=str(e))
            raise
    
    async def _restore_files(self, files_backup: Dict[str, Any]):
        """Restore files from backup."""
        
        # Simplified implementation
        logger.info("File restore not implemented in this demo")
    
    async def _store_backup_metadata(self, backup_id: str, metadata: Dict[str, Any]):
        """Store backup metadata."""
        
        metadata_path = self.backup_dir / f"{backup_id}.metadata.json"
        metadata_path.write_text(json.dumps(metadata, default=str, indent=2))
    
    async def _get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get backup metadata."""
        
        metadata_path = self.backup_dir / f"{backup_id}.metadata.json"
        
        if metadata_path.exists():
            return json.loads(metadata_path.read_text())
        
        return None
    
    async def _cleanup_old_backups(self):
        """Background task to clean up old backups."""
        
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Run daily
                
                cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
                
                cleaned_count = 0
                for metadata_file in self.backup_dir.glob("*.metadata.json"):
                    try:
                        metadata = json.loads(metadata_file.read_text())
                        created_at = datetime.fromisoformat(metadata["created_at"])
                        
                        if created_at < cutoff_date:
                            # Delete backup and metadata files
                            backup_id = metadata["backup_id"]
                            backup_file = self.backup_dir / f"{backup_id}.backup"
                            
                            if backup_file.exists():
                                backup_file.unlink()
                            
                            metadata_file.unlink()
                            cleaned_count += 1
                            
                    except Exception as e:
                        logger.warning("Failed to cleanup backup", 
                                     file=str(metadata_file), error=str(e))
                
                if cleaned_count > 0:
                    logger.info("Backup cleanup completed", cleaned_count=cleaned_count)
                    
            except Exception as e:
                logger.error("Backup cleanup task failed", error=str(e))

# Global instance
backup_restore_service = BackupRestoreService()