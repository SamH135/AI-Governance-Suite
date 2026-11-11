"""
Industry-Specific Document Templates Service
Provides templates for fintech, healthcare, regulatory compliance, and other industries
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import structlog
from jinja2 import Environment, DictLoader, select_autoescape

from ...shared.exceptions import ValidationError, NotFoundError
from .document_service import document_service

logger = structlog.get_logger()

class IndustryTemplatesService:
    """Service for managing industry-specific document templates."""
    
    def __init__(self):
        self.initialized = False
        self.templates_path = Path(__file__).parent / "templates"
        self.template_registry: Dict[str, Dict[str, Any]] = {}
        self.jinja_env = None
        
        # Industry template definitions
        self.industry_templates = {
            "fintech": {
                "name": "Financial Technology",
                "description": "Templates for financial services and fintech companies",
                "templates": {
                    "fair_lending_report": {
                        "name": "Fair Lending Compliance Report",
                        "description": "Comprehensive fair lending analysis and documentation",
                        "framework": "Fair Lending",
                        "sections": [
                            "executive_summary",
                            "model_overview",
                            "data_analysis",
                            "disparate_impact_testing",
                            "bias_mitigation",
                            "monitoring_plan",
                            "recommendations"
                        ],
                        "required_data": ["model_performance", "demographic_data", "approval_rates"],
                        "compliance_standards": ["ECOA", "Fair Housing Act", "CRA"]
                    },
                    "aml_risk_assessment": {
                        "name": "Anti-Money Laundering Risk Assessment",
                        "description": "AML compliance risk evaluation for AI systems",
                        "framework": "AML/KYC",
                        "sections": [
                            "risk_profile",
                            "customer_due_diligence",
                            "transaction_monitoring",
                            "risk_scoring_model",
                            "compliance_controls",
                            "reporting_procedures"
                        ],
                        "required_data": ["transaction_data", "customer_profiles", "risk_scores"],
                        "compliance_standards": ["BSA", "USA PATRIOT Act", "FATF Guidelines"]
                    },
                    "kyc_documentation": {
                        "name": "Know Your Customer Documentation",
                        "description": "KYC process documentation for AI-driven identity verification",
                        "framework": "KYC",
                        "sections": [
                            "customer_identification",
                            "verification_process",
                            "risk_assessment",
                            "ongoing_monitoring",
                            "documentation_requirements",
                            "escalation_procedures"
                        ],
                        "required_data": ["verification_results", "identity_documents", "risk_ratings"],
                        "compliance_standards": ["CIP", "CDD", "EDD"]
                    },
                    "credit_scoring_fairness": {
                        "name": "Credit Scoring Fairness Assessment",
                        "description": "Fair credit scoring practices documentation",
                        "framework": "Fair Credit",
                        "sections": [
                            "model_methodology",
                            "feature_analysis",
                            "fairness_metrics",
                            "adverse_action_analysis",
                            "model_validation",
                            "consumer_rights"
                        ],
                        "required_data": ["credit_scores", "feature_importance", "approval_decisions"],
                        "compliance_standards": ["FCRA", "ECOA", "Regulation B"]
                    }
                }
            },
            "healthcare": {
                "name": "Healthcare & Life Sciences",
                "description": "Templates for healthcare AI systems and medical devices",
                "templates": {
                    "hipaa_compliance_report": {
                        "name": "HIPAA Compliance Assessment",
                        "description": "Comprehensive HIPAA compliance evaluation for AI systems",
                        "framework": "HIPAA",
                        "sections": [
                            "administrative_safeguards",
                            "physical_safeguards",
                            "technical_safeguards",
                            "phi_handling",
                            "access_controls",
                            "audit_procedures",
                            "breach_response"
                        ],
                        "required_data": ["access_logs", "phi_usage", "security_measures"],
                        "compliance_standards": ["HIPAA Privacy Rule", "HIPAA Security Rule", "HITECH Act"]
                    },
                    "fda_validation_report": {
                        "name": "FDA Software Validation Report",
                        "description": "FDA validation documentation for medical AI software",
                        "framework": "FDA 21 CFR Part 820",
                        "sections": [
                            "software_classification",
                            "risk_analysis",
                            "verification_testing",
                            "validation_testing",
                            "clinical_evaluation",
                            "post_market_surveillance",
                            "change_control"
                        ],
                        "required_data": ["test_results", "clinical_data", "risk_assessments"],
                        "compliance_standards": ["FDA 21 CFR Part 820", "ISO 13485", "IEC 62304"]
                    },
                    "clinical_decision_support": {
                        "name": "Clinical Decision Support Documentation",
                        "description": "Documentation for AI-based clinical decision support systems",
                        "framework": "Clinical AI",
                        "sections": [
                            "clinical_purpose",
                            "evidence_basis",
                            "algorithm_description",
                            "performance_metrics",
                            "clinical_validation",
                            "user_interface",
                            "safety_monitoring"
                        ],
                        "required_data": ["clinical_outcomes", "performance_metrics", "user_feedback"],
                        "compliance_standards": ["CDS Hooks", "SMART on FHIR", "CQI Guidelines"]
                    },
                    "medical_device_software": {
                        "name": "Medical Device Software Documentation",
                        "description": "Software documentation for medical device AI components",
                        "framework": "Medical Device",
                        "sections": [
                            "software_lifecycle_process",
                            "software_safety_classification",
                            "software_requirements",
                            "architecture_design",
                            "integration_testing",
                            "risk_management",
                            "configuration_management"
                        ],
                        "required_data": ["requirements_trace", "test_coverage", "risk_analysis"],
                        "compliance_standards": ["IEC 62304", "ISO 14971", "FDA Guidance"]
                    }
                }
            },
            "regulatory": {
                "name": "Regulatory Compliance",
                "description": "Templates for various regulatory compliance frameworks",
                "templates": {
                    "sox_compliance_report": {
                        "name": "SOX Compliance Assessment",
                        "description": "Sarbanes-Oxley compliance for AI financial reporting systems",
                        "framework": "SOX",
                        "sections": [
                            "internal_controls",
                            "financial_reporting_risks",
                            "it_general_controls",
                            "application_controls",
                            "data_integrity",
                            "access_management",
                            "change_management"
                        ],
                        "required_data": ["control_testing", "audit_evidence", "risk_assessments"],
                        "compliance_standards": ["SOX Section 302", "SOX Section 404", "PCAOB Standards"]
                    },
                    "pci_dss_assessment": {
                        "name": "PCI DSS Compliance Assessment",
                        "description": "Payment Card Industry compliance for AI payment systems",
                        "framework": "PCI DSS",
                        "sections": [
                            "network_security",
                            "cardholder_data_protection",
                            "vulnerability_management",
                            "access_control_measures",
                            "network_monitoring",
                            "information_security_policy",
                            "compliance_validation"
                        ],
                        "required_data": ["security_scans", "access_logs", "network_diagrams"],
                        "compliance_standards": ["PCI DSS v4.0", "PA-DSS", "P2PE Standards"]
                    },
                    "iso_compliance_report": {
                        "name": "ISO Compliance Assessment",
                        "description": "ISO standards compliance for AI systems",
                        "framework": "ISO",
                        "sections": [
                            "management_system",
                            "risk_management",
                            "information_security",
                            "quality_management",
                            "continuous_improvement",
                            "audit_procedures",
                            "certification_maintenance"
                        ],
                        "required_data": ["audit_results", "risk_registers", "process_documentation"],
                        "compliance_standards": ["ISO 27001", "ISO 9001", "ISO 31000"]
                    },
                    "gdpr_compliance_report": {
                        "name": "GDPR Compliance Assessment",
                        "description": "General Data Protection Regulation compliance for AI systems",
                        "framework": "GDPR",
                        "sections": [
                            "lawful_basis",
                            "data_protection_principles",
                            "individual_rights",
                            "privacy_by_design",
                            "data_protection_impact_assessment",
                            "breach_notification",
                            "international_transfers"
                        ],
                        "required_data": ["data_flows", "consent_records", "privacy_measures"],
                        "compliance_standards": ["GDPR Articles", "EDPB Guidelines", "National DPA Guidance"]
                    }
                }
            },
            "technology": {
                "name": "Technology & Software",
                "description": "Templates for technology companies and software development",
                "templates": {
                    "ai_ethics_assessment": {
                        "name": "AI Ethics Assessment",
                        "description": "Comprehensive AI ethics evaluation and documentation",
                        "framework": "AI Ethics",
                        "sections": [
                            "ethical_principles",
                            "bias_assessment",
                            "fairness_evaluation",
                            "transparency_measures",
                            "accountability_framework",
                            "human_oversight",
                            "societal_impact"
                        ],
                        "required_data": ["bias_metrics", "fairness_tests", "impact_analysis"],
                        "compliance_standards": ["IEEE Standards", "Partnership on AI", "EU Ethics Guidelines"]
                    },
                    "algorithmic_impact_assessment": {
                        "name": "Algorithmic Impact Assessment",
                        "description": "Assessment of algorithmic decision-making systems",
                        "framework": "Algorithmic Accountability",
                        "sections": [
                            "system_overview",
                            "stakeholder_analysis",
                            "impact_identification",
                            "risk_assessment",
                            "mitigation_strategies",
                            "monitoring_plan",
                            "public_engagement"
                        ],
                        "required_data": ["system_metrics", "stakeholder_feedback", "impact_data"],
                        "compliance_standards": ["Algorithmic Accountability Act", "NYC AIA", "EU AI Act"]
                    }
                }
            }
        }
    
    async def initialize(self):
        """Initialize the industry templates service."""
        
        if self.initialized:
            return
            
        try:
            logger.info("Initializing Industry Templates Service")
            
            # Create templates directory if it doesn't exist
            try:
                self.templates_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Templates directory ensured: {self.templates_path}")
            except Exception as dir_error:
                logger.warning(f"Failed to create templates directory: {dir_error}")
                # Continue without file system templates
            
            # Initialize Jinja2 environment
            try:
                self.jinja_env = Environment(
                    loader=DictLoader({}),
                    autoescape=select_autoescape(['html', 'xml'])
                )
                logger.info("Jinja2 environment initialized")
            except Exception as jinja_error:
                logger.error(f"Failed to initialize Jinja2: {jinja_error}")
                raise ValidationError(f"Jinja2 initialization failed: {jinja_error}")
            
            # Load template registry - this is critical and should not fail
            try:
                await self._load_template_registry()
            except Exception as registry_error:
                logger.error(f"Failed to load template registry: {registry_error}")
                raise ValidationError(f"Template registry loading failed: {registry_error}")
            
            # Generate template files if they don't exist - this is optional
            try:
                await self._generate_template_files()
            except Exception as files_error:
                logger.warning(f"Template file generation failed: {files_error}")
                # Continue without file templates - not critical for service operation
            
            self.initialized = True
            logger.info("Industry Templates Service initialized successfully")
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error("Failed to initialize Industry Templates Service", error=str(e))
            raise ValidationError(f"Service initialization failed: {str(e)}")
    
    async def _load_template_registry(self):
        """Load template registry data."""
        try:
            # First, load from hardcoded templates
            self.template_registry = {}
            for industry_id, industry_data in self.industry_templates.items():
                self.template_registry[industry_id] = industry_data
            
            # Then, try to load additional templates from file if it exists
            registry_file = self.templates_path / "registry.json"
            if registry_file.exists():
                try:
                    registry_data = json.loads(registry_file.read_text(encoding="utf-8"))
                    # Merge with existing registry
                    self.template_registry.update(registry_data)
                    logger.info("Additional template registry loaded from file")
                except Exception as e:
                    logger.warning("Failed to load template registry from file", error=str(e))
            
            logger.info(f"Loaded template registry with {len(self.template_registry)} industries")
        except Exception as e:
            logger.error("Failed to load template registry", error=str(e))
            raise
    
    async def _generate_template_files(self):
        """Generate template files if they don't exist."""
        try:
            # Ensure templates directory exists
            if not self.templates_path.exists():
                self.templates_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created templates directory: {self.templates_path}")
            
            # Create a basic template structure for each industry/template combination
            for industry_id, industry_data in self.industry_templates.items():
                for template_id, template_data in industry_data["templates"].items():
                    template_file = self.templates_path / f"{industry_id}_{template_id}.html"
                    
                    if not template_file.exists():
                        try:
                            # Create a basic template structure
                            template_content = self._create_basic_template(template_data)
                            template_file.write_text(template_content, encoding='utf-8')
                            logger.info(f"Generated template file: {template_file.name}")
                        except Exception as file_error:
                            logger.warning(f"Failed to create template file {template_file.name}", error=str(file_error))
                            # Continue with other files rather than failing completely
                            continue
            
            logger.info("Template file generation completed")
        except Exception as e:
            logger.error("Failed to generate template files", error=str(e))
            # Don't raise the exception - log it and continue
            logger.warning("Template file generation failed, but service will continue without file templates")
    
    def _create_basic_template(self, template_data: Dict[str, Any]) -> str:
        """Create a basic template structure."""
        sections = template_data.get("sections", [])
        template_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{template_data.get("name", "Document Template")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .section {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>{template_data.get("name", "Document Template")}</h1>
    <p><strong>Framework:</strong> {template_data.get("framework", "N/A")}</p>
    <p><strong>Description:</strong> {template_data.get("description", "N/A")}</p>
    
"""
        
        for section in sections:
            section_title = section.replace("_", " ").title()
            template_content += f"""    <div class="section">
        <h2>{section_title}</h2>
        <p>{{{{ data.{section} | default("Content for {section_title} section will be populated here.") }}}}</p>
    </div>
    
"""
        
        template_content += """</body>
</html>"""
        
        return template_content
    
    async def get_industries(self) -> List[Dict[str, Any]]:
        """Get list of available industries."""
        
        if not self.initialized:
            await self.initialize()
            
        industries = []
        for industry_id, industry_data in self.industry_templates.items():
            industries.append({
                "id": industry_id,
                "name": industry_data["name"],
                "description": industry_data["description"],
                "template_count": len(industry_data["templates"])
            })
        
        return industries
    
    async def get_industry_templates(self, industry_id: str) -> List[Dict[str, Any]]:
        """Get templates for a specific industry."""
        
        if not self.initialized:
            await self.initialize()
            
        if industry_id not in self.industry_templates:
            raise NotFoundError("Industry", industry_id)
        
        industry_data = self.industry_templates[industry_id]
        templates = []
        
        for template_id, template_data in industry_data["templates"].items():
            templates.append({
                "id": template_id,
                "industry_id": industry_id,
                "name": template_data["name"],
                "description": template_data["description"],
                "framework": template_data["framework"],
                "sections": template_data["sections"],
                "required_data": template_data["required_data"],
                "compliance_standards": template_data["compliance_standards"]
            })
        
        return templates
    
    async def get_template_details(
        self, 
        industry_id: str, 
        template_id: str
    ) -> Dict[str, Any]:
        """Get detailed information about a specific template."""
        
        if not self.initialized:
            await self.initialize()
            
        if industry_id not in self.industry_templates:
            raise NotFoundError("Industry", industry_id)
        
        industry_data = self.industry_templates[industry_id]
        
        if template_id not in industry_data["templates"]:
            raise NotFoundError("Template", template_id)
        
        template_data = industry_data["templates"][template_id]
        
        return {
            "id": template_id,
            "industry_id": industry_id,
            "industry_name": industry_data["name"],
            **template_data,
            "template_file": f"{industry_id}_{template_id}.html",
            "created_at": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    
    async def generate_document(
        self,
        industry_id: str,
        template_id: str,
        data: Dict[str, Any],
        format_type: str = "html"
    ) -> Dict[str, Any]:
        """Generate a document using an industry template."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Get template details
            template_details = await self.get_template_details(industry_id, template_id)
            
            # Validate required data
            missing_data = self._validate_required_data(template_details, data)
            if missing_data:
                raise ValidationError(f"Missing required data: {', '.join(missing_data)}")
            
            # Load template content
            template_content = await self._load_template_content(industry_id, template_id)
            
            # Prepare template context
            context = self._prepare_template_context(template_details, data)
            
            # Render template
            template = self.jinja_env.from_string(template_content)
            rendered_content = template.render(**context)
            
            # Convert format if needed
            if format_type != "html":
                rendered_content = await self._convert_format(
                    rendered_content, "html", format_type
                )
            
            # Generate document metadata
            document_metadata = {
                "template_id": template_id,
                "industry_id": industry_id,
                "template_name": template_details["name"],
                "framework": template_details["framework"],
                "generated_at": datetime.utcnow().isoformat(),
                "format": format_type,
                "compliance_standards": template_details["compliance_standards"],
                "data_sources": list(data.keys())
            }
            
            logger.info(
                "Industry document generated",
                industry=industry_id,
                template=template_id,
                format=format_type
            )
            
            return {
                "content": rendered_content,
                "metadata": document_metadata,
                "success": True
            }
            
        except Exception as e:
            logger.error(
                "Document generation failed",
                industry=industry_id,
                template=template_id,
                error=str(e)
            )
            raise ValidationError(f"Document generation failed: {str(e)}")
    
    async def create_custom_template(
        self,
        industry_id: str,
        template_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a custom template for an industry."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Validate template data
            required_fields = ["name", "description", "framework", "sections", "template_content"]
            missing_fields = [field for field in required_fields if field not in template_data]
            
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Generate template ID
            template_id = template_data["name"].lower().replace(" ", "_").replace("-", "_")
            
            # Add to industry templates
            if industry_id not in self.industry_templates:
                self.industry_templates[industry_id] = {
                    "name": industry_id.title(),
                    "description": f"Custom {industry_id} templates",
                    "templates": {}
                }
            
            self.industry_templates[industry_id]["templates"][template_id] = {
                "name": template_data["name"],
                "description": template_data["description"],
                "framework": template_data["framework"],
                "sections": template_data["sections"],
                "required_data": template_data.get("required_data", []),
                "compliance_standards": template_data.get("compliance_standards", []),
                "custom": True,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Save template content to file
            template_file = self.templates_path / f"{industry_id}_{template_id}.html"
            template_file.write_text(template_data["template_content"], encoding="utf-8")
            
            # Update registry
            await self._save_template_registry()
            
            logger.info(
                "Custom template created",
                industry=industry_id,
                template=template_id
            )
            
            return {
                "template_id": template_id,
                "industry_id": industry_id,
                "success": True,
                "message": "Custom template created successfully"
            }
            
        except Exception as e:
            logger.error(
                "Custom template creation failed",
                industry=industry_id,
                error=str(e)
            )
            raise ValidationError(f"Custom template creation failed: {str(e)}")
    
    def _validate_required_data(
        self, 
        template_details: Dict[str, Any], 
        data: Dict[str, Any]
    ) -> List[str]:
        """Validate that all required data is provided."""
        
        required_data = template_details.get("required_data", [])
        missing_data = []
        
        for required_field in required_data:
            if required_field not in data or not data[required_field]:
                missing_data.append(required_field)
        
        return missing_data
    
    def _prepare_template_context(
        self, 
        template_details: Dict[str, Any], 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare context for template rendering."""
        
        context = {
            "template_name": template_details["name"],
            "framework": template_details["framework"],
            "compliance_standards": template_details["compliance_standards"],
            "generated_date": datetime.utcnow().strftime("%B %d, %Y"),
            "generated_time": datetime.utcnow().strftime("%I:%M %p UTC"),
            **data
        }
        
        # Add section-specific data
        for section in template_details["sections"]:
            section_data = data.get(section, {})
            context[f"{section}_data"] = section_data
        
        return context
    
    async def _load_template_content(
        self, 
        industry_id: str, 
        template_id: str
    ) -> str:
        """Load template content from file."""
        
        template_file = self.templates_path / f"{industry_id}_{template_id}.html"
        
        if not template_file.exists():
            # Generate default template if it doesn't exist
            await self._generate_default_template(industry_id, template_id)
        
        return template_file.read_text(encoding="utf-8")
    
    async def _generate_default_template(
        self, 
        industry_id: str, 
        template_id: str
    ):
        """Generate a default template file."""
        
        template_details = await self.get_template_details(industry_id, template_id)
        
        # Generate basic HTML template
        template_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ template_name }}}}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
        .section {{ margin-bottom: 30px; }}
        .section h2 {{ color: #333; border-bottom: 1px solid #ccc; padding-bottom: 10px; }}
        .metadata {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-top: 30px; }}
        .compliance-standards {{ margin-top: 20px; }}
        .compliance-standards ul {{ list-style-type: disc; margin-left: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{{{{ template_name }}}}</h1>
        <p><strong>Framework:</strong> {{{{ framework }}}}</p>
        <p><strong>Generated:</strong> {{{{ generated_date }}}} at {{{{ generated_time }}}}</p>
    </div>
    
"""
        
        # Add sections
        for section in template_details["sections"]:
            section_title = section.replace("_", " ").title()
            template_content += f"""    <div class="section">
        <h2>{section_title}</h2>
        <p>{{{{ {section}_data.description or "This section contains information about {section_title.lower()}." }}}}</p>
        
        {{% if {section}_data.content %}}
        <div class="content">
            {{{{ {section}_data.content | safe }}}}
        </div>
        {{% endif %}}
        
        {{% if {section}_data.items %}}
        <ul>
        {{% for item in {section}_data.items %}}
            <li>{{{{ item }}}}</li>
        {{% endfor %}}
        </ul>
        {{% endif %}}
    </div>
    
"""
        
        # Add compliance standards section
        template_content += """    <div class="compliance-standards">
        <h2>Compliance Standards</h2>
        <ul>
        {% for standard in compliance_standards %}
            <li>{{ standard }}</li>
        {% endfor %}
        </ul>
    </div>
    
    <div class="metadata">
        <h3>Document Metadata</h3>
        <p><strong>Template:</strong> {{ template_name }}</p>
        <p><strong>Framework:</strong> {{ framework }}</p>
        <p><strong>Generated:</strong> {{ generated_date }} at {{ generated_time }}</p>
    </div>
</body>
</html>"""
        
        # Save template file
        template_file = self.templates_path / f"{industry_id}_{template_id}.html"
        template_file.write_text(template_content, encoding="utf-8")
    
    
    async def _convert_format(
        self, 
        content: str, 
        from_format: str, 
        to_format: str
    ) -> str:
        """Convert document format."""
        
        # This would integrate with format conversion service
        # For now, return content as-is
        return content
    
    
    async def _save_template_registry(self):
        """Save template registry to file."""
        
        try:
            registry_file = self.templates_path / "registry.json"
            registry_file.write_text(
                json.dumps(self.template_registry, indent=2),
                encoding="utf-8"
            )
            logger.info("Template registry saved")
        except Exception as e:
            logger.warning("Failed to save template registry", error=str(e))
    
    async def get_template_usage_instructions(
        self,
        industry_id: str,
        template_id: str
    ) -> List[str]:
        """Get usage instructions for a specific template."""
        
        template_details = await self.get_template_details(industry_id, template_id)
        
        instructions = [
            f"This template generates a {template_details['name']} document",
            f"Framework: {template_details['framework']}",
            f"Required data fields: {', '.join(template_details['required_data'])}",
            "Provide data for each section to customize the output",
            "Ensure data accuracy and completeness",
            "Review generated content for accuracy",
            "Customize sections as needed for your specific use case"
        ]
        
        return instructions
    
    async def close(self):
        """Close the industry templates service."""
        
        try:
            if self.initialized:
                await self._save_template_registry()
                self.initialized = False
            
            logger.info("Industry Templates Service closed")
            
        except Exception as e:
            logger.error("Industry Templates Service close failed", error=str(e))

# Global industry templates service instance
industry_templates_service = IndustryTemplatesService()