"""Core document generation service."""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import structlog
from jinja2 import Environment, DictLoader, select_autoescape

from ...shared.models import AISystem, DocumentTemplate, GeneratedDocument
from ...shared.schemas import DocumentFormat
from ...shared.exceptions import ValidationError, ExternalServiceError
from .template_processor import TemplateProcessor
from .format_converter import FormatConverter

# Import Unified API with fallback
try:
    from shared.unified_api.base import ModelConfig, ModelType
    from shared.unified_api import get_unified_api
except ImportError:
    ModelConfig = Any
    ModelType = Any
    get_unified_api = None

logger = structlog.get_logger()

class DocumentService:
    """Service for generating compliance documents with Unified API support."""
    
    def __init__(self):
        self.unified_api = None
        self.jinja_env = None
        self.template_processor = TemplateProcessor()
        self.format_converter = FormatConverter()
        self.storage_path = Path(os.getenv("FILE_STORAGE_PATH", "./storage"))
        self.initialized = False
    
    async def initialize(self):
        """Initialize the document service with Unified API support."""
        
        if self.initialized:
            return
        
        try:
            # Initialize Unified API for LLM enhancement
            if get_unified_api:
                self.unified_api = get_unified_api()
                providers = self.unified_api.list_providers()
                logger.info("Unified API initialized for document service", providers=providers)
            else:
                logger.warning("Unified API not available - LLM enhancement disabled")
            
            # Initialize Jinja2 environment
            self.jinja_env = Environment(
                loader=DictLoader({}),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # Create storage directory
            self.storage_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize processors
            await self.template_processor.initialize()
            await self.format_converter.initialize()
            
            self.initialized = True
            logger.info("Document service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize document service", error=str(e))
            raise ExternalServiceError("DocumentService", f"Initialization failed: {str(e)}")
    
    async def close(self):
        """Close document service connections."""
        # Unified API doesn't require explicit closing
        logger.info("Document service connections closed")
    
    async def generate_document(
        self,
        template: DocumentTemplate,
        ai_system: AISystem,
        data: Dict[str, Any],
        format: DocumentFormat = DocumentFormat.PDF,
        enhance_with_llm: bool = True,
        llm_config: Optional[ModelConfig] = None
    ) -> Dict[str, Any]:
        """Generate a document from template and data."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            logger.info("Generating document", 
                       template_id=template.template_id,
                       system_id=ai_system.system_id,
                       format=format)
            
            # Process template with data
            processed_content = await self.template_processor.process_template(
                template, ai_system, data
            )
            
            # Enhance content with LLM if enabled
            if enhance_with_llm and self.unified_api and llm_config:
                enhanced_content = await self._enhance_content_with_llm(
                    processed_content, template.framework, ai_system, llm_config
                )
                processed_content.update(enhanced_content)
            
            # Generate document in requested format
            document_data = await self._generate_formatted_document(
                processed_content, format, template.name
            )
            
            result = {
                "content": processed_content,
                "file_path": document_data.get("file_path"),
                "file_size": document_data.get("file_size"),
                "format": format,
                "generation_metadata": {
                    "template_id": template.template_id,
                    "system_id": ai_system.system_id,
                    "enhanced_with_llm": enhance_with_llm and self.unified_api is not None and llm_config is not None,
                    "llm_provider": llm_config.provider if llm_config else None,
                    "llm_model": llm_config.model_id if llm_config else None,
                    "generated_at": datetime.utcnow().isoformat(),
                    "sections_generated": len(processed_content.get("sections", {}))
                }
            }
            
            logger.info("Document generated successfully", 
                       template_id=template.template_id,
                       format=format,
                       file_size=document_data.get("file_size", 0))
            
            return result
            
        except Exception as e:
            logger.error("Document generation failed", 
                        template_id=template.template_id, error=str(e))
            raise ValidationError(f"Document generation failed: {str(e)}")
    
    async def _enhance_content_with_llm(
        self,
        content: Dict[str, Any],
        framework: str,
        ai_system: AISystem,
        llm_config: ModelConfig
    ) -> Dict[str, Any]:
        """Enhance document content using LLM."""
        
        try:
            logger.debug("Enhancing content with LLM", framework=framework)
            
            # Build enhancement prompt
            system_prompt = f"""You are an expert compliance documentation specialist for {framework or 'general'} frameworks.
Your task is to enhance and improve compliance documentation content while maintaining accuracy and professional tone.

Guidelines:
1. Maintain factual accuracy
2. Use professional, clear language
3. Ensure compliance-specific terminology is correct
4. Add relevant details where content seems sparse
5. Improve structure and readability
6. Keep the original meaning intact

System context: {ai_system.name} ({ai_system.system_type})
Framework: {framework or 'General'}"""
            
            enhanced_sections = {}
            
            # Enhance each section
            for section_name, section_content in content.get("sections", {}).items():
                if isinstance(section_content, str) and len(section_content) > 50:
                    try:
                        enhanced_section = await self._enhance_section(
                            system_prompt, section_name, section_content, llm_config
                        )
                        enhanced_sections[f"{section_name}_enhanced"] = enhanced_section
                        
                        # Add small delay to avoid rate limits
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning("Section enhancement failed", 
                                     section=section_name, error=str(e))
                        enhanced_sections[f"{section_name}_enhanced"] = section_content
            
            return {
                "enhanced_sections": enhanced_sections,
                "enhancement_metadata": {
                    "enhanced_at": datetime.utcnow().isoformat(),
                    "sections_enhanced": len(enhanced_sections),
                    "framework": framework
                }
            }
            
        except Exception as e:
            logger.error("LLM content enhancement failed", error=str(e))
            return {"enhancement_error": str(e)}
    
    async def _enhance_section(
        self,
        system_prompt: str,
        section_name: str,
        section_content: str,
        llm_config: ModelConfig
    ) -> str:
        """Enhance a single section with LLM."""
        
        user_prompt = f"""Please enhance this {section_name} section of a compliance document:

ORIGINAL CONTENT:
{section_content}

Please improve this content by:
1. Making it more comprehensive and detailed
2. Ensuring professional compliance language
3. Adding relevant context where appropriate
4. Improving clarity and structure
5. Maintaining the original intent and accuracy

Return only the enhanced content, no additional commentary."""
        
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = await self.unified_api.agenerate(
                full_prompt,
                llm_config,
                temperature=0.3,
                max_tokens=1000
            )
            
            if response.error:
                raise Exception(f"LLM enhancement error: {response.error}")
            
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Section enhancement failed: {e}")
            return section_content  # Return original content on failure
    
    async def _generate_formatted_document(
        self,
        content: Dict[str, Any],
        format: DocumentFormat,
        document_name: str
    ) -> Dict[str, Any]:
        """Generate document in the specified format."""
        
        try:
            # Generate base filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in document_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            base_filename = f"{safe_name}_{timestamp}"
            
            # Convert to requested format
            if format == DocumentFormat.HTML:
                result = await self.format_converter.to_html(content, base_filename)
            elif format == DocumentFormat.PDF:
                result = await self.format_converter.to_pdf(content, base_filename)
            elif format == DocumentFormat.MARKDOWN:
                result = await self.format_converter.to_markdown(content, base_filename)
            elif format == DocumentFormat.DOCX:
                result = await self.format_converter.to_docx(content, base_filename)
            else:
                raise ValidationError(f"Unsupported format: {format}")
            
            # Save to storage
            file_path = self.storage_path / result["filename"]
            
            with open(file_path, "wb" if format == DocumentFormat.PDF else "w", 
                     encoding=None if format == DocumentFormat.PDF else "utf-8") as f:
                f.write(result["content"])
            
            file_size = file_path.stat().st_size
            
            return {
                "file_path": str(file_path),
                "filename": result["filename"],
                "file_size": file_size,
                "format": format
            }
            
        except Exception as e:
            logger.error("Document formatting failed", format=format, error=str(e))
            raise ValidationError(f"Document formatting failed: {str(e)}")
    
    async def create_custom_template(
        self,
        name: str,
        description: str,
        template_type: str,
        framework: str,
        sections: List[str],
        enhance_with_llm: bool = True
    ) -> Dict[str, Any]:
        """Create a custom document template."""
        
        try:
            logger.info("Creating custom template", name=name, framework=framework)
            
            # Build base template structure
            template_content = {
                "metadata": {
                    "name": name,
                    "description": description,
                    "type": template_type,
                    "framework": framework,
                    "created_at": datetime.utcnow().isoformat()
                },
                "sections": {},
                "structure": sections
            }
            
            # Generate section templates
            for section in sections:
                section_template = await self._generate_section_template(
                    section, framework, enhance_with_llm
                )
                template_content["sections"][section] = section_template
            
            # Add styling and formatting
            template_content["styling"] = self._get_default_styling(framework)
            
            logger.info("Custom template created", 
                       name=name, sections_count=len(sections))
            
            return template_content
            
        except Exception as e:
            logger.error("Custom template creation failed", name=name, error=str(e))
            raise ValidationError(f"Custom template creation failed: {str(e)}")
    
    async def _generate_section_template(
        self,
        section_name: str,
        framework: str,
        enhance_with_llm: bool
    ) -> Dict[str, Any]:
        """Generate a template for a specific section."""
        
        # Base section structure
        section_template = {
            "title": section_name.replace("_", " ").title(),
            "template": f"{{{{ {section_name} }}}}",
            "description": f"Content for {section_name} section",
            "required": True,
            "type": "text"
        }
        
        # Enhance with LLM if enabled (disabled until full integration)
        if enhance_with_llm and False:  # Temporarily disabled - needs llm_config parameter
            try:
                enhanced_template = await self._enhance_section_template(
                    section_name, framework
                )
                section_template.update(enhanced_template)
            except Exception as e:
                logger.warning("Section template enhancement failed", 
                             section=section_name, error=str(e))
        
        return section_template
    
    async def _enhance_section_template(
        self,
        section_name: str,
        framework: str
    ) -> Dict[str, Any]:
        """Enhance section template with LLM."""
        
        prompt = f"""Create a detailed template structure for a "{section_name}" section in a {framework} compliance document.

Provide:
1. A clear title
2. A template with placeholders for dynamic content
3. A helpful description
4. Suggested content structure
5. Key points that should be covered

Return as JSON with keys: title, template, description, structure, key_points"""
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        try:
            enhanced_data = json.loads(response.choices[0].message.content)
            return enhanced_data
        except json.JSONDecodeError:
            return {}
    
    def _get_default_styling(self, framework: str) -> Dict[str, Any]:
        """Get default styling for a framework."""
        
        base_styling = {
            "colors": {
                "primary": "#2563eb",
                "secondary": "#64748b",
                "accent": "#0ea5e9"
            },
            "fonts": {
                "heading": "Arial, sans-serif",
                "body": "Arial, sans-serif",
                "code": "Courier New, monospace"
            },
            "layout": {
                "margin": "2cm",
                "line_height": "1.6",
                "font_size": "11pt"
            }
        }
        
        # Framework-specific styling
        if framework == "GDPR":
            base_styling["colors"]["primary"] = "#1e40af"
            base_styling["colors"]["accent"] = "#3b82f6"
        elif framework == "HIPAA":
            base_styling["colors"]["primary"] = "#059669"
            base_styling["colors"]["accent"] = "#10b981"
        
        return base_styling

# Global document service instance
document_service = DocumentService()