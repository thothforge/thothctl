"""Utility functions for consistent HTML report generation."""
import os
from pathlib import Path
from typing import Optional


class HTMLReportUtils:
    """Utility class for consistent HTML report generation."""
    
    @staticmethod
    def get_unified_css() -> str:
        """Get the unified CSS styles for all reports."""
        css_file = Path(__file__).parent / "templates" / "unified_report_styles.css"
        try:
            with open(css_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to inline CSS if file doesn't exist
            return HTMLReportUtils._get_fallback_css()
    
    @staticmethod
    def _get_fallback_css() -> str:
        """Fallback CSS in case the external file is not found."""
        return """
        /* Unified Report Styles for ThothCTL - Inventory & Scan Reports */
        :root {
            --primary-color: #007bff;
            --secondary-color: #6c757d;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --info-color: #17a2b8;
            --light-color: #f8f9fa;
            --dark-color: #343a40;
            --border-radius: 8px;
            --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            --transition: all 0.3s ease;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--dark-color);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        """
    
    @staticmethod
    def get_html_head(title: str, additional_meta: Optional[str] = None) -> str:
        """Generate consistent HTML head section."""
        additional_meta = additional_meta or ""
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    {additional_meta}
    <style>
        {HTMLReportUtils.get_unified_css()}
    </style>
</head>"""
    
    @staticmethod
    def get_report_header(title: str, subtitle: Optional[str] = None, nav_links: Optional[list] = None) -> str:
        """Generate consistent report header."""
        subtitle_html = f'<div class="nav-subtitle">{subtitle}</div>' if subtitle else ""
        
        nav_links_html = ""
        if nav_links:
            nav_items = []
            for link in nav_links:
                if isinstance(link, dict):
                    nav_items.append(f'<a href="{link.get("href", "#")}" class="nav-link">{link.get("text", "")}</a>')
                else:
                    nav_items.append(f'<a href="#{link.lower().replace(" ", "-")}" class="nav-link">{link}</a>')
            nav_links_html = f'<div class="nav-menu">{"".join(nav_items)}</div>'
        
        return f"""
        <div class="nav-header">
            <div class="nav-title">{title}</div>
            {subtitle_html}
            {nav_links_html}
        </div>"""
    
    @staticmethod
    def get_summary_cards(data: dict) -> str:
        """Generate summary cards section."""
        cards_html = []
        
        for key, value in data.items():
            card_class = key.lower()
            cards_html.append(f"""
            <div class="summary-card {card_class}">
                <div class="card-number {card_class}">{value}</div>
                <div class="card-label">{key.replace('_', ' ').title()}</div>
            </div>""")
        
        return f"""
        <div class="summary-grid">
            {"".join(cards_html)}
        </div>"""
    
    @staticmethod
    def validate_report_consistency(report_path: str) -> dict:
        """Validate that a report follows the unified styling standards."""
        validation_results = {
            "has_unified_css": False,
            "has_proper_head": False,
            "has_meta_charset": False,
            "has_viewport": False,
            "has_inter_font": False,
            "issues": []
        }
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for unified CSS
            if "Unified Report Styles for ThothCTL" in content:
                validation_results["has_unified_css"] = True
            else:
                validation_results["issues"].append("Missing unified CSS styles")
            
            # Check for proper HTML head structure
            if '<meta charset="UTF-8">' in content:
                validation_results["has_meta_charset"] = True
            else:
                validation_results["issues"].append("Missing charset meta tag")
            
            if 'name="viewport"' in content:
                validation_results["has_viewport"] = True
            else:
                validation_results["issues"].append("Missing viewport meta tag")
            
            if "Inter" in content and "fonts.googleapis.com" in content:
                validation_results["has_inter_font"] = True
            else:
                validation_results["issues"].append("Missing Inter font import")
            
            if "<title>" in content:
                validation_results["has_proper_head"] = True
            else:
                validation_results["issues"].append("Missing title tag")
                
        except Exception as e:
            validation_results["issues"].append(f"Error reading file: {str(e)}")
        
        return validation_results
    
    @staticmethod
    def fix_report_consistency(report_path: str) -> bool:
        """Attempt to fix consistency issues in a report."""
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it needs fixing
            validation = HTMLReportUtils.validate_report_consistency(report_path)
            if not validation["issues"]:
                return True  # Already consistent
            
            # Basic fixes
            fixed_content = content
            
            # Fix missing charset
            if not validation["has_meta_charset"]:
                fixed_content = fixed_content.replace(
                    '<head>',
                    '<head>\n    <meta charset="UTF-8">'
                )
            
            # Fix missing viewport
            if not validation["has_viewport"]:
                charset_pos = fixed_content.find('<meta charset="UTF-8">')
                if charset_pos != -1:
                    insert_pos = fixed_content.find('\n', charset_pos) + 1
                    fixed_content = (
                        fixed_content[:insert_pos] +
                        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
                        fixed_content[insert_pos:]
                    )
            
            # Write back the fixed content
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            return True
            
        except Exception as e:
            print(f"Error fixing report consistency: {e}")
            return False
