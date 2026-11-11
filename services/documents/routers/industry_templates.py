"""Industry-specific document templates endpoints."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import structlog

from ...shared.auth import get_current_active_user, require_admin
from ...shared.schemas import UserResponse, ApiResponse
from ...shared.exceptions import ValidationError, NotFoundError
from ..services.industry_templates_service import industry_templates_service

logger = structlog.get_logger()
router = APIRouter()

# Pydantic schemas for industry templates
class IndustryDocumentRequest(BaseModel):
    industry_id: str = Field(..., description="Industry identifier")
    template_id: str = Field(..., description="Template identifier")
    system_data: Dict[str, Any] = Field(..., description="AI system data for template")
    document_title: Optional[str] = Field(default=None, description="Custom document title")
    custom_data: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom data")

class TemplateDataValidationRequest(BaseModel):
    industry_id: str = Field(..., description="Industry identifier")
    template_id: str = Field(..., description="Template identifier")
    provided_data: Dict[str, Any] = Field(..., description="Data to validate against template requirements")

@router.get("/industries", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_available_industries(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of available industries with templates."""
    
    try:
        industries = await industry_templates_service.get_available_industries()
        
        return ApiResponse(
            success=True,
            data=industries,
            message=f"Found {len(industries)} available industries"
        )
        
    except Exception as e:
        logger.error("Failed to get available industries", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/industries/{industry_id}/templates", response_model=ApiResponse[Dict[str, Any]])
async def get_industry_templates(
    industry_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get templates for a specific industry."""
    
    try:
        templates = await industry_templates_service.get_industry_templates(industry_id)
        
        return ApiResponse(
            success=True,
            data=templates,
            message=f"Found {len(templates['templates'])} templates for {templates['industry_name']}"
        )
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get industry templates", 
                    industry_id=industry_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/industries/{industry_id}/templates/{template_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_template_details(
    industry_id: str,
    template_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get detailed information about a specific template."""
    
    try:
        template_details = await industry_templates_service.get_template_details(industry_id, template_id)
        
        return ApiResponse(
            success=True,
            data=template_details,
            message="Template details retrieved successfully"
        )
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to get template details", 
                    industry_id=industry_id, template_id=template_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/generate", response_model=ApiResponse[Dict[str, Any]])
async def generate_industry_document(
    document_request: IndustryDocumentRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Generate a document using an industry-specific template."""
    
    try:
        document_content = await industry_templates_service.generate_industry_document(
            industry_id=document_request.industry_id,
            template_id=document_request.template_id,
            system_data=document_request.system_data,
            document_title=document_request.document_title,
            custom_data=document_request.custom_data
        )
        
        logger.info("Industry document generated", 
                   industry=document_request.industry_id,
                   template=document_request.template_id,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=document_content,
            message="Industry document generated successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to generate industry document", 
                    industry=document_request.industry_id,
                    template=document_request.template_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/validate", response_model=ApiResponse[Dict[str, Any]])
async def validate_template_data(
    validation_request: TemplateDataValidationRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Validate data against template requirements."""
    
    try:
        validation_result = await industry_templates_service.validate_template_data(
            industry_id=validation_request.industry_id,
            template_id=validation_request.template_id,
            provided_data=validation_request.provided_data
        )
        
        return ApiResponse(
            success=True,
            data=validation_result,
            message="Data validation completed"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to validate template data", 
                    industry=validation_request.industry_id,
                    template=validation_request.template_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/industries/{industry_id}/templates/{template_id}/sample", response_model=ApiResponse[Dict[str, Any]])
async def get_template_sample_data(
    industry_id: str,
    template_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get sample data for testing a template."""
    
    try:
        sample_data = await industry_templates_service.get_template_samples(industry_id, template_id)
        
        return ApiResponse(
            success=True,
            data=sample_data,
            message="Sample data retrieved successfully"
        )
        
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=404 if isinstance(e, NotFoundError) else 400, detail=str(e))
    except Exception as e:
        logger.error("Failed to get template sample data", 
                    industry_id=industry_id, template_id=template_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/compliance-frameworks", response_model=ApiResponse[Dict[str, Any]])
async def get_compliance_frameworks(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of supported compliance frameworks by industry."""
    
    try:
        # Compile compliance frameworks from all industries
        frameworks = {}
        industries = await industry_templates_service.get_available_industries()
        
        for industry in industries:
            industry_id = industry["industry_id"]
            industry_templates = await industry_templates_service.get_industry_templates(industry_id)
            
            frameworks[industry_id] = {
                "industry_name": industry["name"],
                "frameworks": []
            }
            
            # Extract unique frameworks
            framework_set = set()
            for template in industry_templates["templates"]:
                framework_set.add(template["framework"])
                framework_set.update(template["compliance_standards"])
            
            frameworks[industry_id]["frameworks"] = sorted(list(framework_set))
        
        return ApiResponse(
            success=True,
            data=frameworks,
            message="Compliance frameworks retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get compliance frameworks", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/template-categories", response_model=ApiResponse[Dict[str, Any]])
async def get_template_categories(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get templates organized by category and complexity."""
    
    try:
        categories = {
            "by_complexity": {
                "low": [],
                "medium": [],
                "high": []
            },
            "by_time_estimate": {
                "quick": [],  # < 30 min
                "moderate": [],  # 30-60 min
                "extended": []  # > 60 min
            },
            "by_industry": {}
        }
        
        industries = await industry_templates_service.get_available_industries()
        
        for industry in industries:
            industry_id = industry["industry_id"]
            industry_templates = await industry_templates_service.get_industry_templates(industry_id)
            
            categories["by_industry"][industry_id] = {
                "name": industry["name"],
                "templates": []
            }
            
            for template in industry_templates["templates"]:
                template_info = {
                    "industry_id": industry_id,
                    "template_id": template["template_id"],
                    "name": template["name"],
                    "framework": template["framework"],
                    "estimated_time": template["estimated_time"]
                }
                
                # Get detailed info for complexity
                details = await industry_templates_service.get_template_details(
                    industry_id, template["template_id"]
                )
                complexity = details["complexity"].lower()
                
                # Categorize by complexity
                categories["by_complexity"][complexity].append(template_info)
                
                # Categorize by time estimate
                if "15-30" in template["estimated_time"] or "30 min" in template["estimated_time"]:
                    categories["by_time_estimate"]["quick"].append(template_info)
                elif "30-60" in template["estimated_time"] or "1 hour" in template["estimated_time"]:
                    categories["by_time_estimate"]["moderate"].append(template_info)
                else:
                    categories["by_time_estimate"]["extended"].append(template_info)
                
                # Add to industry category
                categories["by_industry"][industry_id]["templates"].append(template_info)
        
        return ApiResponse(
            success=True,
            data=categories,
            message="Template categories retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get template categories", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search", response_model=ApiResponse[List[Dict[str, Any]]])
async def search_templates(
    query: str,
    industry: Optional[str] = None,
    framework: Optional[str] = None,
    complexity: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Search templates by query, industry, framework, or complexity."""
    
    try:
        results = []
        industries = await industry_templates_service.get_available_industries()
        
        for industry_data in industries:
            industry_id = industry_data["industry_id"]
            
            # Filter by industry if specified
            if industry and industry.lower() not in industry_data["name"].lower():
                continue
            
            industry_templates = await industry_templates_service.get_industry_templates(industry_id)
            
            for template in industry_templates["templates"]:
                # Get detailed info
                details = await industry_templates_service.get_template_details(
                    industry_id, template["template_id"]
                )
                
                # Apply filters
                if framework and framework.lower() not in template["framework"].lower():
                    continue
                
                if complexity and complexity.lower() != details["complexity"].lower():
                    continue
                
                # Search in template content
                search_text = f"{template['name']} {template['description']} {template['framework']} {' '.join(template['compliance_standards'])}"
                
                if query.lower() in search_text.lower():
                    results.append({
                        "industry_id": industry_id,
                        "industry_name": industry_data["name"],
                        "template_id": template["template_id"],
                        "name": template["name"],
                        "description": template["description"],
                        "framework": template["framework"],
                        "complexity": details["complexity"],
                        "estimated_time": template["estimated_time"],
                        "compliance_standards": template["compliance_standards"]
                    })
        
        return ApiResponse(
            success=True,
            data=results,
            message=f"Found {len(results)} matching templates"
        )
        
    except Exception as e:
        logger.error("Failed to search templates", query=query, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/custom-template", response_model=ApiResponse[Dict[str, Any]])
async def create_custom_template(
    template_data: Dict[str, Any],
    current_user: UserResponse = Depends(require_admin)
):
    """Create a custom industry template (admin only)."""
    
    try:
        # Validate required fields
        required_fields = ["name", "description", "industry", "framework", "sections"]
        for field in required_fields:
            if field not in template_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Create custom template using document service
        custom_template = await document_service.create_custom_template(
            name=template_data["name"],
            description=template_data["description"],
            template_type="industry_specific",
            framework=template_data["framework"],
            sections=template_data["sections"],
            enhance_with_llm=template_data.get("enhance_with_llm", True)
        )
        
        logger.info("Custom template created", 
                   template_name=template_data["name"],
                   industry=template_data["industry"],
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=custom_template,
            message="Custom template created successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create custom template", 
                    template_name=template_data.get("name"), error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics", response_model=ApiResponse[Dict[str, Any]])
async def get_template_analytics(
    days: int = 30,
    current_user: UserResponse = Depends(require_admin)
):
    """Get analytics on template usage (admin only)."""
    
    try:
        # This would implement template usage analytics
        # For now, return placeholder data
        analytics = {
            "most_used_templates": [
                {"industry": "fintech", "template": "fair_lending_report", "usage_count": 45},
                {"industry": "healthcare", "template": "hipaa_compliance_report", "usage_count": 32},
                {"industry": "regulatory", "template": "gdpr_compliance_report", "usage_count": 28}
            ],
            "usage_by_industry": {
                "fintech": 78,
                "healthcare": 65,
                "regulatory": 52,
                "technology": 34,
                "energy": 12
            },
            "completion_rates": {
                "successful": 87.5,
                "failed": 12.5
            },
            "average_generation_time": "2.3 minutes",
            "time_period": f"Last {days} days"
        }
        
        return ApiResponse(
            success=True,
            data=analytics,
            message="Template analytics retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get template analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")