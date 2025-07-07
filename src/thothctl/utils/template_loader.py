"""Template loader utility for managing HTML templates."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Utility class for loading and managing HTML templates."""
    
    def __init__(self, templates_dir: Optional[str] = None):
        """Initialize template loader with templates directory."""
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to templates directory relative to this file
            current_dir = Path(__file__).parent.parent
            self.templates_dir = current_dir / "templates"
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
    
    def load_template(self, template_name: str, template_type: str = "reports") -> str:
        """
        Load HTML template from file.
        
        Args:
            template_name: Name of the template file (without extension)
            template_type: Type/category of template (e.g., 'reports', 'emails')
            
        Returns:
            Template content as string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            IOError: If template file can't be read
        """
        try:
            template_path = self.templates_dir / template_type / f"{template_name}.html"
            
            if not template_path.exists():
                raise FileNotFoundError(f"Template not found: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            logger.debug(f"Loaded template: {template_path}")
            return template_content
            
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {str(e)}")
            raise
    
    def load_script(self, script_name: str, template_type: str = "reports") -> str:
        """
        Load JavaScript file content.
        
        Args:
            script_name: Name of the script file (without extension)
            template_type: Type/category of template
            
        Returns:
            Script content as string
        """
        try:
            script_path = self.templates_dir / template_type / f"{script_name}.js"
            
            if not script_path.exists():
                logger.warning(f"Script not found: {script_path}")
                return ""
            
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            logger.debug(f"Loaded script: {script_path}")
            return script_content
            
        except Exception as e:
            logger.error(f"Failed to load script {script_name}: {str(e)}")
            return ""
    
    def render_template(self, template_name: str, context: Dict[str, Any], 
                       template_type: str = "reports", inline_script: bool = True) -> str:
        """
        Render template with context data.
        
        Args:
            template_name: Name of the template file
            context: Dictionary with template variables
            template_type: Type/category of template
            inline_script: Whether to inline JavaScript or reference external file
            
        Returns:
            Rendered HTML content
        """
        try:
            template_content = self.load_template(template_name, template_type)
            
            # Handle script inclusion
            if inline_script:
                # Load and inline the JavaScript
                script_content = self.load_script(template_name, template_type)
                if script_content:
                    # Replace script src with inline script
                    script_tag = f"<script>{script_content}</script>"
                    template_content = template_content.replace(
                        '<script src="{script_path}"></script>', 
                        script_tag
                    )
                else:
                    # Remove script tag if no script found
                    template_content = template_content.replace(
                        '<script src="{script_path}"></script>', 
                        ""
                    )
            else:
                # Use external script reference
                script_path = self.templates_dir / template_type / f"{template_name}.js"
                context['script_path'] = str(script_path)
            
            # Render template with context using manual replacement to avoid JavaScript conflicts
            rendered_content = self._manual_replace(template_content, context)
            
            logger.debug(f"Rendered template: {template_name}")
            return rendered_content
            
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {str(e)}")
            raise
    
    def _manual_replace(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        Manually replace template variables to avoid conflicts with JavaScript curly braces.
        
        Args:
            template_content: Template content with placeholders
            context: Context variables for replacement
            
        Returns:
            Content with variables replaced
        """
        try:
            result = template_content
            
            # Replace each context variable manually
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))
            
            return result
            
        except Exception as e:
            logger.error(f"Manual replacement failed: {str(e)}")
            raise
    
    def list_templates(self, template_type: str = "reports") -> list:
        """
        List available templates in a category.
        
        Args:
            template_type: Type/category of template
            
        Returns:
            List of template names (without extensions)
        """
        try:
            template_dir = self.templates_dir / template_type
            if not template_dir.exists():
                return []
            
            templates = []
            for file_path in template_dir.glob("*.html"):
                templates.append(file_path.stem)
            
            return sorted(templates)
            
        except Exception as e:
            logger.error(f"Failed to list templates: {str(e)}")
            return []
    
    def template_exists(self, template_name: str, template_type: str = "reports") -> bool:
        """
        Check if a template exists.
        
        Args:
            template_name: Name of the template file
            template_type: Type/category of template
            
        Returns:
            True if template exists, False otherwise
        """
        template_path = self.templates_dir / template_type / f"{template_name}.html"
        return template_path.exists()
    
    def get_template_path(self, template_name: str, template_type: str = "reports") -> Path:
        """
        Get full path to template file.
        
        Args:
            template_name: Name of the template file
            template_type: Type/category of template
            
        Returns:
            Path object to template file
        """
        return self.templates_dir / template_type / f"{template_name}.html"


# Global template loader instance
_template_loader = None

def get_template_loader() -> TemplateLoader:
    """Get global template loader instance."""
    global _template_loader
    if _template_loader is None:
        _template_loader = TemplateLoader()
    return _template_loader
