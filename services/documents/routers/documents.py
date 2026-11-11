"""Document generation and management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import os

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user
from ...shared.models import GeneratedDocument, DocumentTemplate, AISystem
from ...shared.schemas import (
    UserResponse, GeneratedDocumentCreate, GeneratedDocumentResponse,
    DocumentFormat, ApiResponse, PaginatedResponse
)
from ...shared.exceptions import NotFoundError, ValidationError
from ..services.document_service import document_service

logger = structlog.get_logger()
router = APIRouter()

@router.post("/generate", response_model=ApiResponse[GeneratedDocumentResponse])
async def generate_document(
    document_data: GeneratedDocumentCreate,
    background_tasks: BackgroundTasks,
    enhance_with_llm: bool = True,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Generate a new document from template."""
    
    # Get template
    template_result = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.template_id == document_data.template_id,
            DocumentTemplate.is_active == True
        )
    )
    template = template_result.scalar_one_or_none()
    
    if not template:
        raise NotFoundError("Document Template", document_data.template_id)
    
    # Get AI system
    system_result = await db.execute(
        select(AISystem).where(
            AISystem.system_id == document_data.system_id,
            AISystem.user_id == current_user.user_id
        )
    )
    ai_system = system_result.scalar_one_or_none()
    
    if not ai_system:
        raise NotFoundError("AI System", document_data.system_id)
    
    # Create document record
    document = GeneratedDocument(
        template_id=document_data.template_id,
        system_id=document_data.system_id,
        title=document_data.title,
        content=document_data.content,
        format=document_data.format,
        created_by=current_user.user_id
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Generate document in background
    background_tasks.add_task(
        generate_document_file,
        document.document_id,
        template,
        ai_system,
        document_data.content or {},
        document_data.format,
        enhance_with_llm
    )
    
    logger.info("Document generation started", 
               document_id=document.document_id,
               template_id=document_data.template_id,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=GeneratedDocumentResponse.model_validate(document),
        message="Document generation started"
    )

@router.get("/", response_model=ApiResponse[PaginatedResponse])
async def get_documents(
    template_id: Optional[int] = None,
    system_id: Optional[int] = None,
    status: Optional[str] = None,
    format: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get generated documents for the current user."""
    
    # Build query
    query = (
        select(GeneratedDocument)
        .join(AISystem)
        .where(AISystem.user_id == current_user.user_id)
    )
    
    if template_id:
        query = query.where(GeneratedDocument.template_id == template_id)
    if system_id:
        query = query.where(GeneratedDocument.system_id == system_id)
    if status:
        query = query.where(GeneratedDocument.status == status)
    if format:
        query = query.where(GeneratedDocument.format == format)
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(GeneratedDocument.created_at.desc()).offset(offset).limit(per_page)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    paginated_response = PaginatedResponse(
        items=[GeneratedDocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
    
    return ApiResponse(
        success=True,
        data=paginated_response
    )

@router.get("/{document_id}", response_model=ApiResponse[GeneratedDocumentResponse])
async def get_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific generated document."""
    
    result = await db.execute(
        select(GeneratedDocument)
        .join(AISystem)
        .where(
            GeneratedDocument.document_id == document_id,
            AISystem.user_id == current_user.user_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise NotFoundError("Generated Document", document_id)
    
    return ApiResponse(
        success=True,
        data=GeneratedDocumentResponse.model_validate(document)
    )

@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Download a generated document file."""
    
    # Get document
    result = await db.execute(
        select(GeneratedDocument)
        .join(AISystem)
        .where(
            GeneratedDocument.document_id == document_id,
            AISystem.user_id == current_user.user_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise NotFoundError("Generated Document", document_id)
    
    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found"
        )
    
    # Determine media type
    media_type_map = {
        "pdf": "application/pdf",
        "html": "text/html",
        "markdown": "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    
    media_type = media_type_map.get(document.format, "application/octet-stream")
    filename = f"{document.title}.{document.format}"
    
    return FileResponse(
        path=document.file_path,
        media_type=media_type,
        filename=filename
    )

@router.put("/{document_id}/status", response_model=ApiResponse[GeneratedDocumentResponse])
async def update_document_status(
    document_id: int,
    status: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update the status of a generated document."""
    
    # Validate status
    valid_statuses = ["draft", "review", "approved", "published"]
    if status not in valid_statuses:
        raise ValidationError(
            f"Invalid status: {status}",
            details={"valid_statuses": valid_statuses}
        )
    
    # Get document
    result = await db.execute(
        select(GeneratedDocument)
        .join(AISystem)
        .where(
            GeneratedDocument.document_id == document_id,
            AISystem.user_id == current_user.user_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise NotFoundError("Generated Document", document_id)
    
    # Update status
    document.status = status
    await db.commit()
    await db.refresh(document)
    
    logger.info("Document status updated", 
               document_id=document_id,
               new_status=status,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=GeneratedDocumentResponse.model_validate(document),
        message=f"Document status updated to {status}"
    )

@router.delete("/{document_id}", response_model=ApiResponse[str])
async def delete_document(
    document_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Delete a generated document."""
    
    # Get document
    result = await db.execute(
        select(GeneratedDocument)
        .join(AISystem)
        .where(
            GeneratedDocument.document_id == document_id,
            AISystem.user_id == current_user.user_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise NotFoundError("Generated Document", document_id)
    
    # Delete file if exists
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.unlink(document.file_path)
        except Exception as e:
            logger.warning("Failed to delete document file", 
                          file_path=document.file_path, error=str(e))
    
    # Delete from database
    await db.delete(document)
    await db.commit()
    
    logger.info("Document deleted", 
               document_id=document_id,
               user_id=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data="Document deleted successfully",
        message="Document has been permanently deleted"
    )

async def generate_document_file(
    document_id: int,
    template: DocumentTemplate,
    ai_system: AISystem,
    data: dict,
    format: DocumentFormat,
    enhance_with_llm: bool
):
    """Background task to generate document file."""
    
    async with db_manager.get_session() as db:
        try:
            # Get document record
            result = await db.execute(
                select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error("Document not found for file generation", document_id=document_id)
                return
            
            # Update status to processing
            document.status = "review"
            await db.commit()
            
            # Generate document
            generation_result = await document_service.generate_document(
                template=template,
                ai_system=ai_system,
                data=data,
                format=format,
                enhance_with_llm=enhance_with_llm
            )
            
            # Update document with results
            document.content = generation_result["content"]
            document.file_path = generation_result.get("file_path")
            document.status = "approved"
            
            await db.commit()
            
            logger.info("Document file generated successfully", 
                       document_id=document_id,
                       file_path=generation_result.get("file_path"))
            
        except Exception as e:
            # Update document status to failed
            async with db_manager.get_session() as error_db:
                error_result = await error_db.execute(
                    select(GeneratedDocument).where(GeneratedDocument.document_id == document_id)
                )
                error_document = error_result.scalar_one_or_none()
                if error_document:
                    error_document.status = "draft"  # Reset to draft on error
                    await error_db.commit()
            
            logger.error("Document file generation failed", 
                        document_id=document_id, error=str(e))