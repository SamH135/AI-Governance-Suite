"""Document template management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from ...shared.database import db_manager
from ...shared.auth import get_current_active_user, require_admin
from ...shared.models import DocumentTemplate
from ...shared.schemas import (
    UserResponse, DocumentTemplateBase, DocumentTemplateResponse, ApiResponse
)
from ...shared.exceptions import NotFoundError, ConflictError, ValidationError
from ..services.document_service import document_service
from ..services.template_processor import TemplateProcessor

logger = structlog.get_logger()
router = APIRouter()

@router.get("/", response_model=ApiResponse[List[DocumentTemplateResponse]])
async def get_templates(
    framework: Optional[str] = None,
    template_type: Optional[str] = None,
    is_active: bool = True,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get available document templates."""
    
    query = select(DocumentTemplate).where(DocumentTemplate.is_active == is_active)
    
    if framework:
        query = query.where(DocumentTemplate.framework == framework)
    if template_type:
        query = query.where(DocumentTemplate.template_type == template_type)
    
    result = await db.execute(query.order_by(DocumentTemplate.name))
    templates = result.scalars().all()
    
    return ApiResponse(
        success=True,
        data=[DocumentTemplateResponse.model_validate(template) for template in templates]
    )

@router.get("/{template_id}", response_model=ApiResponse[DocumentTemplateResponse])
async def get_template(
    template_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Get a specific document template."""
    
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.template_id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise NotFoundError("Document Template", template_id)
    
    return ApiResponse(
        success=True,
        data=DocumentTemplateResponse.model_validate(template)
    )

@router.post("/", response_model=ApiResponse[DocumentTemplateResponse])
async def create_template(
    template_data: DocumentTemplateBase,
    current_user: UserResponse = Depends(require_admin),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Create a new document template (admin only)."""
    
    # Check if template name already exists
    existing = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.name == template_data.name)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Template with name '{template_data.name}' already exists")
    
    # Validate template content
    processor = TemplateProcessor()
    await processor.initialize()
    
    validation_result = await processor.validate_template(template_data.content)
    if not validation_result["valid"]:
        raise ValidationError(
            "Template validation failed",
            details={
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"]
            }
        )
    
    # Create template
    template = DocumentTemplate(
        name=template_data.name,
        description=template_data.description,
        template_type=template_data.template_type,
        content=template_data.content,
        framework=template_data.framework,
        version=template_data.version,
        created_by=current_user.user_id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    logger.info("Document template created", 
               template_id=template.template_id,
               name=template.name,
               created_by=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=DocumentTemplateResponse.model_validate(template),
        message="Document template created successfully"
    )

@router.post("/custom", response_model=ApiResponse[dict])
async def create_custom_template(
    name: str,
    description: str,
    template_type: str,
    framework: str,
    sections: List[str],
    enhance_with_llm: bool = True,
    current_user: UserResponse = Depends(require_admin),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Create a custom template using AI assistance (admin only)."""
    
    try:
        # Generate custom template using document service
        template_content = await document_service.create_custom_template(
            name=name,
            description=description,
            template_type=template_type,
            framework=framework,
            sections=sections,
            enhance_with_llm=enhance_with_llm
        )
        
        # Validate generated template
        processor = TemplateProcessor()
        await processor.initialize()
        
        validation_result = await processor.validate_template(template_content)
        
        result = {
            "template_content": template_content,
            "validation": validation_result,
            "ready_to_save": validation_result["valid"]
        }
        
        logger.info("Custom template generated", 
                   name=name, 
                   framework=framework,
                   sections_count=len(sections),
                   valid=validation_result["valid"])
        
        return ApiResponse(
            success=True,
            data=result,
            message="Custom template generated successfully"
        )
        
    except Exception as e:
        logger.error("Custom template generation failed", 
                    name=name, error=str(e))
        raise ValidationError(f"Custom template generation failed: {str(e)}")

@router.put("/{template_id}", response_model=ApiResponse[DocumentTemplateResponse])
async def update_template(
    template_id: int,
    template_data: DocumentTemplateBase,
    current_user: UserResponse = Depends(require_admin),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update a document template (admin only)."""
    
    # Get template
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.template_id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise NotFoundError("Document Template", template_id)
    
    # Validate updated content
    processor = TemplateProcessor()
    await processor.initialize()
    
    validation_result = await processor.validate_template(template_data.content)
    if not validation_result["valid"]:
        raise ValidationError(
            "Template validation failed",
            details={
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"]
            }
        )
    
    # Update template
    template.name = template_data.name
    template.description = template_data.description
    template.template_type = template_data.template_type
    template.content = template_data.content
    template.framework = template_data.framework
    template.version = template_data.version
    
    await db.commit()
    await db.refresh(template)
    
    logger.info("Document template updated", 
               template_id=template_id,
               name=template.name,
               updated_by=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=DocumentTemplateResponse.model_validate(template),
        message="Document template updated successfully"
    )

@router.post("/{template_id}/validate", response_model=ApiResponse[dict])
async def validate_template(
    template_id: int,
    current_user: UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Validate a document template."""
    
    # Get template
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.template_id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise NotFoundError("Document Template", template_id)
    
    # Validate template
    processor = TemplateProcessor()
    await processor.initialize()
    
    validation_result = await processor.validate_template(template.content)
    
    logger.info("Template validation completed", 
               template_id=template_id,
               valid=validation_result["valid"],
               errors_count=len(validation_result["errors"]))
    
    return ApiResponse(
        success=True,
        data=validation_result,
        message=f"Template validation completed - {'Valid' if validation_result['valid'] else 'Invalid'}"
    )

@router.put("/{template_id}/status", response_model=ApiResponse[DocumentTemplateResponse])
async def update_template_status(
    template_id: int,
    is_active: bool,
    current_user: UserResponse = Depends(require_admin),
    db: AsyncSession = Depends(db_manager.get_session_gen)
):
    """Update template active status (admin only)."""
    
    # Get template
    result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.template_id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise NotFoundError("Document Template", template_id)
    
    # Update status
    template.is_active = is_active
    await db.commit()
    await db.refresh(template)
    
    status_text = "activated" if is_active else "deactivated"
    
    logger.info("Template status updated", 
               template_id=template_id,
               is_active=is_active,
               updated_by=current_user.user_id)
    
    return ApiResponse(
        success=True,
        data=DocumentTemplateResponse.model_validate(template),
        message=f"Template {status_text} successfully"
    )