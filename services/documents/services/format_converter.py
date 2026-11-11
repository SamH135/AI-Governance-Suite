"""Format conversion service for documents."""

import os
import subprocess
from typing import Dict, Any
from pathlib import Path
import structlog
import markdown
from datetime import datetime

logger = structlog.get_logger()

class FormatConverter:
    """Converts document content to different formats."""
    
    def __init__(self):
        self.initialized = False
        self.wkhtmltopdf_available = False
    
    async def initialize(self):
        """Initialize the format converter."""
        
        if self.initialized:
            return
        
        try:
            # Check if wkhtmltopdf is available for PDF generation
            try:
                subprocess.run(["wkhtmltopdf", "--version"], 
                             capture_output=True, check=True)
                self.wkhtmltopdf_available = True
                logger.info("wkhtmltopdf available for PDF generation")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("wkhtmltopdf not available - PDF generation will be limited")
                self.wkhtmltopdf_available = False
            
            self.initialized = True
            logger.info("Format converter initialized")
            
        except Exception as e:
            logger.error("Failed to initialize format converter", error=str(e))
            raise
    
    async def to_html(self, content: Dict[str, Any], base_filename: str) -> Dict[str, Any]:
        """Convert content to HTML format."""
        
        try:
            html_content = self._build_html_document(content)
            filename = f"{base_filename}.html"
            
            return {
                "content": html_content,
                "filename": filename,
                "format": "html"
            }
            
        except Exception as e:
            logger.error("HTML conversion failed", error=str(e))
            raise
    
    async def to_pdf(self, content: Dict[str, Any], base_filename: str) -> Dict[str, Any]:
        """Convert content to PDF format."""
        
        try:
            if self.wkhtmltopdf_available:
                return await self._generate_pdf_with_wkhtmltopdf(content, base_filename)
            else:
                return await self._generate_pdf_fallback(content, base_filename)
                
        except Exception as e:
            logger.error("PDF conversion failed", error=str(e))
            raise
    
    async def to_markdown(self, content: Dict[str, Any], base_filename: str) -> Dict[str, Any]:
        """Convert content to Markdown format."""
        
        try:
            markdown_content = self._build_markdown_document(content)
            filename = f"{base_filename}.md"
            
            return {
                "content": markdown_content,
                "filename": filename,
                "format": "markdown"
            }
            
        except Exception as e:
            logger.error("Markdown conversion failed", error=str(e))
            raise
    
    async def to_docx(self, content: Dict[str, Any], base_filename: str) -> Dict[str, Any]:
        """Convert content to DOCX format."""
        
        try:
            # For now, generate HTML and suggest conversion
            # In a full implementation, you'd use python-docx
            html_content = self._build_html_document(content)
            filename = f"{base_filename}.html"  # Would be .docx with proper implementation
            
            return {
                "content": html_content,
                "filename": filename,
                "format": "html",  # Would be "docx" with proper implementation
                "note": "DOCX generation requires python-docx library implementation"
            }
            
        except Exception as e:
            logger.error("DOCX conversion failed", error=str(e))
            raise
    
    def _build_html_document(self, content: Dict[str, Any]) -> str:
        """Build a complete HTML document."""
        
        metadata = content.get("metadata", {})
        sections = content.get("sections", {})
        structure = content.get("structure", list(sections.keys()))
        styling = content.get("styling", {})
        
        # Build HTML
        html_parts = []
        
        # HTML header
        html_parts.append(self._get_html_header(metadata, styling))
        
        # Document title
        title = metadata.get("template_name", "Compliance Document")
        html_parts.append(f"<h1>{title}</h1>")
        
        # Document metadata
        html_parts.append(self._build_metadata_section(metadata))
        
        # Document sections
        for section_name in structure:
            if section_name in sections:
                section_content = sections[section_name]
                html_parts.append(self._build_html_section(section_name, section_content))
        
        # Enhanced sections if available
        enhanced_sections = content.get("enhanced_sections", {})
        if enhanced_sections:
            html_parts.append("<h2>Enhanced Content</h2>")
            for section_name, enhanced_content in enhanced_sections.items():
                html_parts.append(self._build_html_section(section_name, enhanced_content))
        
        # HTML footer
        html_parts.append(self._get_html_footer())
        
        return "\n".join(html_parts)
    
    def _get_html_header(self, metadata: Dict[str, Any], styling: Dict[str, Any]) -> str:
        """Generate HTML header with styling."""
        
        colors = styling.get("colors", {})
        fonts = styling.get("fonts", {})
        layout = styling.get("layout", {})
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.get('template_name', 'Compliance Document')}</title>
    <style>
        body {{
            font-family: {fonts.get('body', 'Arial, sans-serif')};
            font-size: {layout.get('font_size', '11pt')};
            line-height: {layout.get('line_height', '1.6')};
            margin: {layout.get('margin', '2cm')};
            color: #333;
        }}
        h1, h2, h3 {{
            font-family: {fonts.get('heading', 'Arial, sans-serif')};
            color: {colors.get('primary', '#2563eb')};
        }}
        h1 {{ font-size: 24pt; margin-bottom: 20px; }}
        h2 {{ font-size: 18pt; margin-top: 30px; margin-bottom: 15px; }}
        h3 {{ font-size: 14pt; margin-top: 20px; margin-bottom: 10px; }}
        .metadata {{
            background-color: #f8f9fa;
            padding: 15px;
            border-left: 4px solid {colors.get('accent', '#0ea5e9')};
            margin-bottom: 30px;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .section-title {{
            color: {colors.get('secondary', '#64748b')};
            border-bottom: 2px solid {colors.get('accent', '#0ea5e9')};
            padding-bottom: 5px;
        }}
        code {{
            font-family: {fonts.get('code', 'Courier New, monospace')};
            background-color: #f1f5f9;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        ul, ol {{ margin-left: 20px; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: {colors.get('primary', '#2563eb')};
            color: white;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 9pt;
            color: #666;
        }}
    </style>
</head>
<body>"""
    
    def _build_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """Build metadata section HTML."""
        
        metadata_html = ['<div class="metadata">']
        metadata_html.append('<h3>Document Information</h3>')
        metadata_html.append('<table>')
        
        metadata_items = [
            ("System Name", metadata.get("system_name", "N/A")),
            ("System Type", metadata.get("system_type", "N/A")),
            ("Framework", metadata.get("framework", "N/A")),
            ("Template Type", metadata.get("template_type", "N/A")),
            ("Generated At", metadata.get("generated_at", "N/A")),
            ("Version", metadata.get("version", "N/A"))
        ]
        
        for label, value in metadata_items:
            metadata_html.append(f'<tr><td><strong>{label}</strong></td><td>{value}</td></tr>')
        
        metadata_html.append('</table>')
        metadata_html.append('</div>')
        
        return "\n".join(metadata_html)
    
    def _build_html_section(self, section_name: str, section_content: str) -> str:
        """Build HTML for a document section."""
        
        section_title = section_name.replace("_", " ").title()
        
        # Convert markdown-like content to HTML
        html_content = self._convert_text_to_html(section_content)
        
        return f"""<div class="section">
    <h2 class="section-title">{section_title}</h2>
    <div class="section-content">
        {html_content}
    </div>
</div>"""
    
    def _convert_text_to_html(self, text: str) -> str:
        """Convert plain text to HTML with basic formatting."""
        
        if not text:
            return "<p>No content available.</p>"
        
        # Split into paragraphs
        paragraphs = text.split('\n\n')
        html_parts = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Handle lists
            if paragraph.startswith('•') or paragraph.startswith('-'):
                list_items = [line.strip().lstrip('•-').strip() 
                             for line in paragraph.split('\n') if line.strip()]
                html_parts.append('<ul>')
                for item in list_items:
                    html_parts.append(f'<li>{item}</li>')
                html_parts.append('</ul>')
            
            # Handle numbered lists
            elif any(paragraph.startswith(f'{i}.') for i in range(1, 10)):
                list_items = [line.strip() for line in paragraph.split('\n') if line.strip()]
                html_parts.append('<ol>')
                for item in list_items:
                    # Remove number prefix
                    clean_item = item.split('.', 1)[1].strip() if '.' in item else item
                    html_parts.append(f'<li>{clean_item}</li>')
                html_parts.append('</ol>')
            
            # Regular paragraph
            else:
                # Replace line breaks with <br>
                formatted_paragraph = paragraph.replace('\n', '<br>')
                html_parts.append(f'<p>{formatted_paragraph}</p>')
        
        return '\n'.join(html_parts)
    
    def _get_html_footer(self) -> str:
        """Generate HTML footer."""
        
        return f"""
    <div class="footer">
        <p>Generated by AI Compliance Platform on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>
</body>
</html>"""
    
    def _build_markdown_document(self, content: Dict[str, Any]) -> str:
        """Build a Markdown document."""
        
        metadata = content.get("metadata", {})
        sections = content.get("sections", {})
        structure = content.get("structure", list(sections.keys()))
        
        markdown_parts = []
        
        # Document title
        title = metadata.get("template_name", "Compliance Document")
        markdown_parts.append(f"# {title}\n")
        
        # Document metadata
        markdown_parts.append("## Document Information\n")
        metadata_items = [
            ("System Name", metadata.get("system_name", "N/A")),
            ("System Type", metadata.get("system_type", "N/A")),
            ("Framework", metadata.get("framework", "N/A")),
            ("Generated At", metadata.get("generated_at", "N/A"))
        ]
        
        for label, value in metadata_items:
            markdown_parts.append(f"- **{label}**: {value}")
        
        markdown_parts.append("")  # Empty line
        
        # Document sections
        for section_name in structure:
            if section_name in sections:
                section_content = sections[section_name]
                section_title = section_name.replace("_", " ").title()
                markdown_parts.append(f"## {section_title}\n")
                markdown_parts.append(section_content)
                markdown_parts.append("")  # Empty line
        
        # Enhanced sections if available
        enhanced_sections = content.get("enhanced_sections", {})
        if enhanced_sections:
            markdown_parts.append("## Enhanced Content\n")
            for section_name, enhanced_content in enhanced_sections.items():
                section_title = section_name.replace("_", " ").title()
                markdown_parts.append(f"### {section_title}\n")
                markdown_parts.append(enhanced_content)
                markdown_parts.append("")  # Empty line
        
        # Footer
        markdown_parts.append("---")
        markdown_parts.append(f"*Generated by AI Compliance Platform on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*")
        
        return "\n".join(markdown_parts)
    
    async def _generate_pdf_with_wkhtmltopdf(
        self, 
        content: Dict[str, Any], 
        base_filename: str
    ) -> Dict[str, Any]:
        """Generate PDF using wkhtmltopdf."""
        
        # First generate HTML
        html_content = self._build_html_document(content)
        
        # Create temporary HTML file
        temp_html = f"/tmp/{base_filename}.html"
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Generate PDF
        pdf_filename = f"{base_filename}.pdf"
        temp_pdf = f"/tmp/{pdf_filename}"
        
        cmd = [
            "wkhtmltopdf",
            "--page-size", "A4",
            "--margin-top", "2cm",
            "--margin-bottom", "2cm",
            "--margin-left", "2cm",
            "--margin-right", "2cm",
            "--encoding", "UTF-8",
            temp_html,
            temp_pdf
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Read PDF content
            with open(temp_pdf, "rb") as f:
                pdf_content = f.read()
            
            # Clean up temp files
            os.unlink(temp_html)
            os.unlink(temp_pdf)
            
            return {
                "content": pdf_content,
                "filename": pdf_filename,
                "format": "pdf"
            }
            
        except subprocess.CalledProcessError as e:
            logger.error("wkhtmltopdf failed", error=str(e))
            # Fallback to HTML
            return await self.to_html(content, base_filename)
    
    async def _generate_pdf_fallback(
        self, 
        content: Dict[str, Any], 
        base_filename: str
    ) -> Dict[str, Any]:
        """Fallback PDF generation (returns HTML)."""
        
        logger.warning("PDF generation not available, returning HTML")
        return await self.to_html(content, base_filename)