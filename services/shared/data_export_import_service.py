"""Data Export/Import Service for bulk operations and data migration."""

import asyncio
import json
import csv
import io
import zipfile
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO
from datetime import datetime
from enum import Enum
from pathlib import Path
import structlog
import pandas as pd

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, ExternalServiceError
from .audit_logging_service import audit_logging_service, AuditEventType, AuditStatus

logger = structlog.get_logger()

class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    XML = "xml"
    PARQUET = "parquet"

class ImportFormat(Enum):
    """Supported import formats."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    XML = "xml"

class ExportScope(Enum):
    """Export scope options."""
    ALL = "all"
    USER_DATA = "user_data"
    SYSTEM_DATA = "system_data"
    TEST_RESULTS = "test_results"
    DOCUMENTS = "documents"
    AUDIT_LOGS = "audit_logs"
    ANALYTICS = "analytics"

class DataExportImportService:
    """Service for bulk data operations and migrations."""
    
    def __init__(self):
        self.initialized = False
        self.temp_dir = Path(tempfile.gettempdir()) / "ai_compliance_exports"
        self.max_export_size = 1024 * 1024 * 1024  # 1GB limit
        self.chunk_size = 10000  # Records per chunk
        
    async def initialize(self):
        """Initialize the data export/import service."""
        if self.initialized:
            return
            
        try:
            # Create temp directory
            self.temp_dir.mkdir(exist_ok=True)
            
            self.initialized = True
            logger.info("Data Export/Import Service initialized successfully")
            
        except Exception as e:
            logger.error("Data Export/Import Service initialization failed", error=str(e))
            raise ExternalServiceError("DataExportImport", f"Initialization failed: {str(e)}")
    
    async def export_data(
        self,
        scope: ExportScope,
        format: ExportFormat,
        user_id: int,
        tenant_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Export data based on scope and format."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            export_id = f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user_id}"
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                user_id=user_id,
                action=f"Data export initiated: {scope.value}",
                resource_type="data_export",
                resource_id=export_id,
                details={
                    "scope": scope.value,
                    "format": format.value,
                    "filters": filters,
                    "include_metadata": include_metadata
                }
            )
            
            # Get data based on scope
            data = await self._get_export_data(scope, user_id, tenant_id, filters)
            
            # Check size limits
            estimated_size = self._estimate_data_size(data)
            if estimated_size > self.max_export_size:
                raise ValidationError(f"Export size ({estimated_size} bytes) exceeds limit ({self.max_export_size} bytes)")
            
            # Format data
            formatted_data = await self._format_export_data(data, format, include_metadata)
            
            # Create export file
            export_path = await self._create_export_file(export_id, formatted_data, format)
            
            # Store export metadata
            export_metadata = {
                "export_id": export_id,
                "scope": scope.value,
                "format": format.value,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "created_at": datetime.utcnow().isoformat(),
                "file_path": str(export_path),
                "file_size": export_path.stat().st_size,
                "record_count": len(data) if isinstance(data, list) else sum(len(v) if isinstance(v, list) else 1 for v in data.values()),
                "filters": filters,
                "include_metadata": include_metadata
            }
            
            # Cache metadata for retrieval
            await redis_client.setex(
                f"export:{export_id}",
                3600 * 24,  # 24 hours
                json.dumps(export_metadata, default=str)
            )
            
            logger.info("Data export completed", 
                       export_id=export_id,
                       scope=scope.value,
                       format=format.value,
                       file_size=export_metadata["file_size"])
            
            return {
                "export_id": export_id,
                "status": "completed",
                "file_path": str(export_path),
                "file_size": export_metadata["file_size"],
                "record_count": export_metadata["record_count"],
                "download_url": f"/api/exports/{export_id}/download",
                "expires_at": (datetime.utcnow().timestamp() + 86400)  # 24 hours
            }
            
        except Exception as e:
            logger.error("Data export failed", scope=scope.value, user_id=user_id, error=str(e))
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                user_id=user_id,
                action=f"Data export failed: {scope.value}",
                status=AuditStatus.FAILURE,
                details={"error": str(e)}
            )
            
            raise ValidationError(f"Data export failed: {str(e)}")
    
    async def import_data(
        self,
        file_data: bytes,
        format: ImportFormat,
        user_id: int,
        tenant_id: Optional[int] = None,
        import_options: Optional[Dict[str, Any]] = None,
        validate_only: bool = False
    ) -> Dict[str, Any]:
        """Import data from file."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            import_id = f"import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user_id}"
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,  # Using DATA_EXPORT for imports too
                user_id=user_id,
                action=f"Data import initiated: {format.value}",
                resource_type="data_import",
                resource_id=import_id,
                details={
                    "format": format.value,
                    "file_size": len(file_data),
                    "validate_only": validate_only,
                    "import_options": import_options
                }
            )
            
            # Parse file data
            parsed_data = await self._parse_import_data(file_data, format)
            
            # Validate data structure
            validation_results = await self._validate_import_data(parsed_data, import_options)
            
            if not validation_results["valid"]:
                return {
                    "import_id": import_id,
                    "status": "validation_failed",
                    "validation_results": validation_results,
                    "errors": validation_results["errors"]
                }
            
            if validate_only:
                return {
                    "import_id": import_id,
                    "status": "validation_passed",
                    "validation_results": validation_results,
                    "preview": parsed_data[:5] if isinstance(parsed_data, list) else {"sample": "data_preview"}
                }
            
            # Import data
            import_results = await self._import_validated_data(
                parsed_data, user_id, tenant_id, import_options
            )
            
            logger.info("Data import completed",
                       import_id=import_id,
                       format=format.value,
                       records_imported=import_results["records_imported"])
            
            return {
                "import_id": import_id,
                "status": "completed",
                "records_imported": import_results["records_imported"],
                "records_failed": import_results["records_failed"],
                "validation_results": validation_results,
                "summary": import_results["summary"]
            }
            
        except Exception as e:
            logger.error("Data import failed", format=format.value, user_id=user_id, error=str(e))
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                user_id=user_id,
                action=f"Data import failed: {format.value}",
                status=AuditStatus.FAILURE,
                details={"error": str(e)}
            )
            
            raise ValidationError(f"Data import failed: {str(e)}")
    
    async def get_export_status(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Get export status and metadata."""
        
        try:
            metadata = await redis_client.get(f"export:{export_id}")
            if metadata:
                return json.loads(metadata)
            return None
            
        except Exception as e:
            logger.error("Failed to get export status", export_id=export_id, error=str(e))
            return None
    
    async def download_export(self, export_id: str, user_id: int) -> Optional[bytes]:
        """Download export file."""
        
        try:
            # Get export metadata
            metadata = await self.get_export_status(export_id)
            if not metadata:
                return None
            
            # Verify user access
            if metadata["user_id"] != user_id:
                raise ValidationError("Access denied to export file")
            
            # Read file
            file_path = Path(metadata["file_path"])
            if not file_path.exists():
                raise ValidationError("Export file not found")
            
            # Log audit event
            await audit_logging_service.log_audit_event(
                event_type=AuditEventType.DOCUMENT_DOWNLOAD,
                user_id=user_id,
                action="Export file downloaded",
                resource_type="export_file",
                resource_id=export_id
            )
            
            return file_path.read_bytes()
            
        except Exception as e:
            logger.error("Export download failed", export_id=export_id, error=str(e))
            raise ValidationError(f"Export download failed: {str(e)}")
    
    async def cleanup_old_exports(self, max_age_hours: int = 24):
        """Clean up old export files."""
        
        try:
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
            
            # Get all export keys
            export_keys = await redis_client.keys("export:*")
            
            cleaned_count = 0
            for key in export_keys:
                try:
                    metadata = await redis_client.get(key)
                    if metadata:
                        export_data = json.loads(metadata)
                        created_at = datetime.fromisoformat(export_data["created_at"]).timestamp()
                        
                        if created_at < cutoff_time:
                            # Delete file
                            file_path = Path(export_data["file_path"])
                            if file_path.exists():
                                file_path.unlink()
                            
                            # Delete metadata
                            await redis_client.delete(key)
                            cleaned_count += 1
                            
                except Exception as e:
                    logger.warning("Failed to cleanup export", key=key, error=str(e))
            
            logger.info("Export cleanup completed", cleaned_count=cleaned_count)
            return cleaned_count
            
        except Exception as e:
            logger.error("Export cleanup failed", error=str(e))
            return 0
    
    async def _get_export_data(
        self,
        scope: ExportScope,
        user_id: int,
        tenant_id: Optional[int],
        filters: Optional[Dict[str, Any]]
    ) -> Union[List[Dict], Dict[str, List[Dict]]]:
        """Get data based on export scope."""
        
        async with db_manager.get_session() as session:
            if scope == ExportScope.ALL:
                # Export all user data
                data = {}
                data["users"] = await self._export_users(session, user_id, tenant_id)
                data["ai_systems"] = await self._export_ai_systems(session, user_id, tenant_id)
                data["models"] = await self._export_models(session, user_id, tenant_id)
                data["test_results"] = await self._export_test_results(session, user_id, tenant_id, filters)
                return data
                
            elif scope == ExportScope.USER_DATA:
                return await self._export_users(session, user_id, tenant_id)
                
            elif scope == ExportScope.SYSTEM_DATA:
                data = {}
                data["ai_systems"] = await self._export_ai_systems(session, user_id, tenant_id)
                data["models"] = await self._export_models(session, user_id, tenant_id)
                return data
                
            elif scope == ExportScope.TEST_RESULTS:
                return await self._export_test_results(session, user_id, tenant_id, filters)
                
            elif scope == ExportScope.AUDIT_LOGS:
                return await self._export_audit_logs(session, user_id, tenant_id, filters)
                
            else:
                raise ValidationError(f"Unsupported export scope: {scope.value}")
    
    async def _export_users(self, session, user_id: int, tenant_id: Optional[int]) -> List[Dict]:
        """Export user data."""
        
        # For security, only export current user's data
        query = "SELECT id, email, name, created_at, updated_at FROM users WHERE id = :user_id"
        result = await session.execute(query, {"user_id": user_id})
        
        users = []
        for row in result.fetchall():
            users.append({
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None
            })
        
        return users
    
    async def _export_ai_systems(self, session, user_id: int, tenant_id: Optional[int]) -> List[Dict]:
        """Export AI systems data."""
        
        query = """
            SELECT id, name, description, system_type, created_at, updated_at
            FROM ai_systems 
            WHERE user_id = :user_id
        """
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params = {"user_id": user_id, "tenant_id": tenant_id}
        else:
            params = {"user_id": user_id}
        
        result = await session.execute(query, params)
        
        systems = []
        for row in result.fetchall():
            systems.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "system_type": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None
            })
        
        return systems
    
    async def _export_models(self, session, user_id: int, tenant_id: Optional[int]) -> List[Dict]:
        """Export models data."""
        
        query = """
            SELECT m.id, m.name, m.model_type, m.configuration, m.created_at, m.updated_at
            FROM models m
            JOIN ai_systems s ON m.system_id = s.id
            WHERE s.user_id = :user_id
        """
        
        if tenant_id:
            query += " AND s.tenant_id = :tenant_id"
            params = {"user_id": user_id, "tenant_id": tenant_id}
        else:
            params = {"user_id": user_id}
        
        result = await session.execute(query, params)
        
        models = []
        for row in result.fetchall():
            models.append({
                "id": row[0],
                "name": row[1],
                "model_type": row[2],
                "configuration": json.loads(row[3]) if row[3] else {},
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None
            })
        
        return models
    
    async def _export_test_results(
        self, 
        session, 
        user_id: int, 
        tenant_id: Optional[int], 
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict]:
        """Export test results data."""
        
        query = """
            SELECT tr.id, tr.overall_score, tr.results, tr.created_at
            FROM test_results tr
            JOIN models m ON tr.model_id = m.id
            JOIN ai_systems s ON m.system_id = s.id
            WHERE s.user_id = :user_id
        """
        
        params = {"user_id": user_id}
        
        if tenant_id:
            query += " AND s.tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        # Apply filters
        if filters:
            if "start_date" in filters:
                query += " AND tr.created_at >= :start_date"
                params["start_date"] = filters["start_date"]
            
            if "end_date" in filters:
                query += " AND tr.created_at <= :end_date"
                params["end_date"] = filters["end_date"]
            
            if "min_score" in filters:
                query += " AND tr.overall_score >= :min_score"
                params["min_score"] = filters["min_score"]
        
        query += " ORDER BY tr.created_at DESC"
        
        result = await session.execute(query, params)
        
        test_results = []
        for row in result.fetchall():
            test_results.append({
                "id": row[0],
                "overall_score": row[1],
                "results": json.loads(row[2]) if row[2] else {},
                "created_at": row[3].isoformat() if row[3] else None
            })
        
        return test_results
    
    async def _export_audit_logs(
        self, 
        session, 
        user_id: int, 
        tenant_id: Optional[int], 
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict]:
        """Export audit logs data."""
        
        query = """
            SELECT event_id, event_type, action, status, severity, timestamp, details
            FROM audit_logs 
            WHERE user_id = :user_id
        """
        
        params = {"user_id": user_id}
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        # Apply filters
        if filters:
            if "start_date" in filters:
                query += " AND timestamp >= :start_date"
                params["start_date"] = filters["start_date"]
            
            if "end_date" in filters:
                query += " AND timestamp <= :end_date"
                params["end_date"] = filters["end_date"]
        
        query += " ORDER BY timestamp DESC LIMIT 10000"  # Limit for performance
        
        result = await session.execute(query, params)
        
        audit_logs = []
        for row in result.fetchall():
            audit_logs.append({
                "event_id": row[0],
                "event_type": row[1],
                "action": row[2],
                "status": row[3],
                "severity": row[4],
                "timestamp": row[5].isoformat() if row[5] else None,
                "details": json.loads(row[6]) if row[6] else {}
            })
        
        return audit_logs
    
    def _estimate_data_size(self, data: Union[List, Dict]) -> int:
        """Estimate data size in bytes."""
        
        try:
            json_str = json.dumps(data, default=str)
            return len(json_str.encode('utf-8'))
        except:
            return 0
    
    async def _format_export_data(
        self, 
        data: Union[List, Dict], 
        format: ExportFormat, 
        include_metadata: bool
    ) -> Union[str, bytes]:
        """Format data for export."""
        
        if include_metadata:
            export_metadata = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "format": format.value,
                "platform": "AI Compliance Platform",
                "version": "1.0.0"
            }
            
            if isinstance(data, dict):
                data["_metadata"] = export_metadata
            elif isinstance(data, list):
                data = {"data": data, "_metadata": export_metadata}
        
        if format == ExportFormat.JSON:
            return json.dumps(data, indent=2, default=str)
        
        elif format == ExportFormat.CSV:
            if isinstance(data, dict):
                # Handle multiple tables
                csv_data = io.StringIO()
                for table_name, table_data in data.items():
                    if table_name.startswith("_"):
                        continue
                    
                    csv_data.write(f"# {table_name}\n")
                    if table_data:
                        df = pd.DataFrame(table_data)
                        df.to_csv(csv_data, index=False)
                    csv_data.write("\n")
                
                return csv_data.getvalue()
            else:
                # Single table
                df = pd.DataFrame(data)
                return df.to_csv(index=False)
        
        elif format == ExportFormat.EXCEL:
            output = io.BytesIO()
            
            if isinstance(data, dict):
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    for table_name, table_data in data.items():
                        if table_name.startswith("_"):
                            continue
                        
                        if table_data:
                            df = pd.DataFrame(table_data)
                            df.to_excel(writer, sheet_name=table_name[:31], index=False)
            else:
                df = pd.DataFrame(data)
                df.to_excel(output, index=False)
            
            return output.getvalue()
        
        else:
            raise ValidationError(f"Unsupported export format: {format.value}")
    
    async def _create_export_file(
        self, 
        export_id: str, 
        data: Union[str, bytes], 
        format: ExportFormat
    ) -> Path:
        """Create export file."""
        
        file_extension = {
            ExportFormat.JSON: ".json",
            ExportFormat.CSV: ".csv",
            ExportFormat.EXCEL: ".xlsx",
            ExportFormat.XML: ".xml",
            ExportFormat.PARQUET: ".parquet"
        }
        
        file_path = self.temp_dir / f"{export_id}{file_extension[format]}"
        
        if isinstance(data, str):
            file_path.write_text(data, encoding='utf-8')
        else:
            file_path.write_bytes(data)
        
        return file_path
    
    async def _parse_import_data(self, file_data: bytes, format: ImportFormat) -> Union[List, Dict]:
        """Parse import file data."""
        
        if format == ImportFormat.JSON:
            return json.loads(file_data.decode('utf-8'))
        
        elif format == ImportFormat.CSV:
            csv_data = io.StringIO(file_data.decode('utf-8'))
            df = pd.read_csv(csv_data)
            return df.to_dict('records')
        
        elif format == ImportFormat.EXCEL:
            excel_data = io.BytesIO(file_data)
            df = pd.read_excel(excel_data)
            return df.to_dict('records')
        
        else:
            raise ValidationError(f"Unsupported import format: {format.value}")
    
    async def _validate_import_data(
        self, 
        data: Union[List, Dict], 
        options: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate import data structure."""
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "record_count": 0
        }
        
        try:
            if isinstance(data, list):
                validation_results["record_count"] = len(data)
                
                # Validate each record
                for i, record in enumerate(data[:100]):  # Validate first 100 records
                    if not isinstance(record, dict):
                        validation_results["errors"].append(f"Record {i} is not a valid object")
                        validation_results["valid"] = False
            
            elif isinstance(data, dict):
                if "data" in data:
                    return await self._validate_import_data(data["data"], options)
                else:
                    validation_results["record_count"] = len(data)
            
            else:
                validation_results["errors"].append("Invalid data format")
                validation_results["valid"] = False
            
        except Exception as e:
            validation_results["errors"].append(f"Validation error: {str(e)}")
            validation_results["valid"] = False
        
        return validation_results
    
    async def _import_validated_data(
        self, 
        data: Union[List, Dict], 
        user_id: int, 
        tenant_id: Optional[int], 
        options: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Import validated data into the system."""
        
        import_results = {
            "records_imported": 0,
            "records_failed": 0,
            "summary": {},
            "errors": []
        }
        
        try:
            # This is a simplified implementation
            # In a real system, you'd have specific importers for each data type
            
            if isinstance(data, list):
                # Import list of records
                for record in data:
                    try:
                        # Process record based on type
                        # This would need to be implemented based on your data models
                        import_results["records_imported"] += 1
                    except Exception as e:
                        import_results["records_failed"] += 1
                        import_results["errors"].append(str(e))
            
            elif isinstance(data, dict):
                # Import structured data
                for table_name, table_data in data.items():
                    if table_name.startswith("_"):
                        continue
                    
                    try:
                        # Import table data
                        # This would need specific implementation
                        import_results["summary"][table_name] = len(table_data) if isinstance(table_data, list) else 1
                        import_results["records_imported"] += len(table_data) if isinstance(table_data, list) else 1
                    except Exception as e:
                        import_results["records_failed"] += 1
                        import_results["errors"].append(f"Failed to import {table_name}: {str(e)}")
        
        except Exception as e:
            import_results["errors"].append(f"Import error: {str(e)}")
        
        return import_results

# Global instance
data_export_import_service = DataExportImportService()