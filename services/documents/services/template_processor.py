"""Template processing service for document generation."""

import json
from typing import Dict, Any, List
from datetime import datetime
import structlog
from jinja2 import Environment, DictLoader, select_autoescape, Template

from ...shared.models import DocumentTemplate, AISystem
from ...shared.exceptions import ValidationError

logger = structlog.get_logger()

class TemplateProcessor:
    """Processes document templates with dynamic data."""
    
    def __init__(self):
        self.jinja_env = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize the template processor."""
        
        if self.initialized:
            return
        
        try:
            # Initialize Jinja2 environment
            self.jinja_env = Environment(
                loader=DictLoader({}),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # Add custom filters
            self.jinja_env.filters['format_date'] = self._format_date
            self.jinja_env.filters['format_list'] = self._format_list
            self.jinja_env.filters['capitalize_words'] = self._capitalize_words
            
            self.initialized = True
            logger.info("Template processor initialized")
            
        except Exception as e:
            logger.error("Failed to initialize template processor", error=str(e))
            raise
    
    async def process_template(
        self,
        template: DocumentTemplate,
        ai_system: AISystem,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a template with provided data."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            logger.debug("Processing template", 
                        template_id=template.template_id,
                        system_id=ai_system.system_id)
            
            # Prepare template context
            context = self._build_template_context(ai_system, data)
            
            # Process template content
            template_content = template.content
            processed_sections = {}
            
            # Process each section in the template
            for section_name, section_config in template_content.get("sections", {}).items():
                processed_section = await self._process_section(
                    section_name, section_config, context
                )
                processed_sections[section_name] = processed_section
            
            # Build final document structure
            result = {
                "metadata": {
                    "template_name": template.name,
                    "template_type": template.template_type,
                    "framework": template.framework,
                    "system_name": ai_system.name,
                    "system_type": ai_system.system_type,
                    "generated_at": datetime.utcnow().isoformat(),
                    "version": template.version
                },
                "sections": processed_sections,
                "structure": template_content.get("structure", list(processed_sections.keys())),
                "styling": template_content.get("styling", {})
            }
            
            logger.debug("Template processed successfully", 
                        template_id=template.template_id,
                        sections_count=len(processed_sections))
            
            return result
            
        except Exception as e:
            logger.error("Template processing failed", 
                        template_id=template.template_id, error=str(e))
            raise ValidationError(f"Template processing failed: {str(e)}")
    
    def _build_template_context(
        self,
        ai_system: AISystem,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the context for template processing."""
        
        context = {
            # System information
            "system": {
                "name": ai_system.name,
                "description": ai_system.description or "",
                "version": ai_system.version or "1.0",
                "type": ai_system.system_type,
                "compliance_frameworks": ai_system.compliance_frameworks or [],
                "created_at": ai_system.created_at.isoformat() if ai_system.created_at else "",
                "updated_at": ai_system.updated_at.isoformat() if ai_system.updated_at else ""
            },
            
            # Document metadata
            "document": {
                "generated_at": datetime.utcnow().isoformat(),
                "generated_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "generated_time": datetime.utcnow().strftime("%H:%M:%S"),
                "year": datetime.utcnow().year
            },
            
            # User-provided data
            "data": data,
            
            # Utility functions
            "utils": {
                "current_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "current_year": datetime.utcnow().year,
                "format_date": self._format_date,
                "format_list": self._format_list
            }
        }
        
        # Flatten data for easier access in templates
        context.update(data)
        
        return context
    
    async def _process_section(
        self,
        section_name: str,
        section_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Process a single template section."""
        
        try:
            # Get section template
            section_template = section_config.get("template", "")
            
            if not section_template:
                logger.warning("Empty template for section", section=section_name)
                return ""
            
            # Create Jinja2 template
            template = Template(section_template, environment=self.jinja_env)
            
            # Render template with context
            rendered_content = template.render(**context)
            
            # Post-process content
            processed_content = self._post_process_content(rendered_content, section_config)
            
            return processed_content
            
        except Exception as e:
            logger.error("Section processing failed", 
                        section=section_name, error=str(e))
            return f"Error processing {section_name}: {str(e)}"
    
    def _post_process_content(
        self,
        content: str,
        section_config: Dict[str, Any]
    ) -> str:
        """Post-process rendered content."""
        
        # Remove excessive whitespace
        content = "\n".join(line.strip() for line in content.split("\n") if line.strip())
        
        # Apply section-specific formatting
        if section_config.get("format") == "list":
            content = self._format_as_list(content)
        elif section_config.get("format") == "table":
            content = self._format_as_table(content)
        
        return content
    
    def _format_as_list(self, content: str) -> str:
        """Format content as a list."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        return "\n".join(f"• {line}" for line in lines)
    
    def _format_as_table(self, content: str) -> str:
        """Format content as a simple table."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if len(lines) < 2:
            return content
        
        # Simple table formatting
        table_lines = []
        table_lines.append("| " + " | ".join(lines[0].split(",")) + " |")
        table_lines.append("|" + "---|" * len(lines[0].split(",")) + "")
        
        for line in lines[1:]:
            table_lines.append("| " + " | ".join(line.split(",")) + " |")
        
        return "\n".join(table_lines)
    
    # Jinja2 custom filters
    def _format_date(self, date_value, format_string="%Y-%m-%d"):
        """Format date filter for Jinja2."""
        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except ValueError:
                return date_value
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime(format_string)
        
        return str(date_value)
    
    def _format_list(self, items, separator=", "):
        """Format list filter for Jinja2."""
        if isinstance(items, list):
            return separator.join(str(item) for item in items)
        return str(items)
    
    def _capitalize_words(self, text):
        """Capitalize words filter for Jinja2."""
        if isinstance(text, str):
            return " ".join(word.capitalize() for word in text.split())
        return str(text)
    
    async def validate_template(self, template_content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a template structure."""
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "sections_validated": 0
        }
        
        try:
            # Check required fields
            required_fields = ["sections"]
            for field in required_fields:
                if field not in template_content:
                    validation_result["errors"].append(f"Missing required field: {field}")
                    validation_result["valid"] = False
            
            # Validate sections
            sections = template_content.get("sections", {})
            for section_name, section_config in sections.items():
                section_validation = await self._validate_section(section_name, section_config)
                
                if not section_validation["valid"]:
                    validation_result["errors"].extend(section_validation["errors"])
                    validation_result["valid"] = False
                
                validation_result["warnings"].extend(section_validation["warnings"])
                validation_result["sections_validated"] += 1
            
            # Check template syntax
            for section_name, section_config in sections.items():
                template_text = section_config.get("template", "")
                if template_text:
                    try:
                        Template(template_text, environment=self.jinja_env)
                    except Exception as e:
                        validation_result["errors"].append(
                            f"Template syntax error in {section_name}: {str(e)}"
                        )
                        validation_result["valid"] = False
            
            logger.info("Template validation completed", 
                       valid=validation_result["valid"],
                       sections=validation_result["sections_validated"],
                       errors=len(validation_result["errors"]))
            
            return validation_result
            
        except Exception as e:
            logger.error("Template validation failed", error=str(e))
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "sections_validated": 0
            }
    
    async def _validate_section(
        self,
        section_name: str,
        section_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a single template section."""
        
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required section fields
        if "template" not in section_config:
            result["errors"].append(f"Section {section_name} missing template field")
            result["valid"] = False
        
        # Check template content
        template_text = section_config.get("template", "")
        if not template_text.strip():
            result["warnings"].append(f"Section {section_name} has empty template")
        
        # Validate section configuration
        if section_config.get("required", False) and not template_text:
            result["errors"].append(f"Required section {section_name} has no template")
            result["valid"] = False
        
        return result