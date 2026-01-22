"""Report generation service for inventory management."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from json2html import json2html
from rich import box
from rich.align import Align
from rich.console import Console
from rich.style import Style
from rich.table import Table

from thothctl.utils.template_loader import get_template_loader


logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating inventory reports."""

    def __init__(self, reports_directory: str = "Reports"):
        """Initialize report service."""
        self.reports_dir = Path(reports_directory)
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.console = Console()
        self.template_loader = get_template_loader()

    def _create_report_path(self, report_name: str, extension: str, reports_directory: Optional[str] = None) -> Path:
        """Create report file path with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if reports_directory:
            reports_dir = Path(reports_directory)
            reports_dir.mkdir(exist_ok=True, parents=True)
        else:
            reports_dir = self.reports_dir
            
        return reports_dir / f"{report_name}_{timestamp}.{extension}"

    def create_json_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create formatted JSON report from inventory data."""
        try:
            report_path = self._create_report_path(report_name, "json", reports_directory)

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(inventory, f, indent=2, default=str, ensure_ascii=False)

            logger.info(f"JSON report created at: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to create JSON report: {str(e)}")
            raise

    def create_html_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create HTML report from inventory data with custom styling."""
        try:
            # Define HTML template with proper string formatting
            html_template = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Infrastructure Inventory Report - {project_name} ({project_type})</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
                <style>
                    :root {{
                        /* ThothCTL Brand Colors */
                        --thoth-primary: #667eea;
                        --thoth-secondary: #764ba2;
                        
                        /* Status Colors */
                        --status-success: #10b981;
                        --status-warning: #f59e0b;
                        --status-error: #ef4444;
                        --status-info: #3b82f6;
                        --status-neutral: #6b7280;
                        
                        /* Legacy compatibility */
                        --primary-color: #667eea;
                        --secondary-color: #6b7280;
                        --success-color: #10b981;
                        --warning-color: #f59e0b;
                        --danger-color: #ef4444;
                        --info-color: #3b82f6;
                        --light-color: #f9fafb;
                        --dark-color: #111827;
                        --border-radius: 8px;
                        --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        --transition: all 0.3s ease;
                    }}

                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}

                    body {{
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        line-height: 1.6;
                        color: var(--dark-color);
                        background: #f5f7fa;
                        min-height: 100vh;
                        padding: 20px;
                    }}

                    html {{
                        scroll-behavior: smooth;
                    }}

                    .container {{
                        max-width: 1400px;
                        margin: 0 auto;
                        background: white;
                        border-radius: var(--border-radius);
                        box-shadow: var(--box-shadow);
                        overflow: hidden;
                    }}

                    /* Navigation Styles */
                    .nav-header {{
                        background: linear-gradient(135deg, var(--primary-color), #0056b3);
                        color: white;
                        padding: 20px 30px;
                        position: sticky;
                        top: 0;
                        z-index: 100;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}

                    .nav-title {{
                        font-size: 1.8rem;
                        font-weight: 700;
                        margin-bottom: 10px;
                    }}

                    .nav-subtitle {{
                        font-size: 1rem;
                        opacity: 0.9;
                        margin-bottom: 15px;
                    }}

                    .nav-menu {{
                        display: flex;
                        gap: 20px;
                        flex-wrap: wrap;
                    }}

                    .nav-link {{
                        color: rgba(255,255,255,0.9);
                        text-decoration: none;
                        padding: 8px 16px;
                        border-radius: 20px;
                        transition: var(--transition);
                        font-weight: 500;
                        font-size: 0.9rem;
                    }}

                    .nav-link:hover {{
                        background: rgba(255,255,255,0.2);
                        color: white;
                        transform: translateY(-1px);
                    }}

                    /* Content Sections */
                    .content-section {{
                        padding: 30px;
                        border-bottom: 1px solid #e9ecef;
                    }}

                    .content-section:last-child {{
                        border-bottom: none;
                    }}

                    .section-header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 20px;
                        padding-bottom: 10px;
                        border-bottom: 2px solid var(--primary-color);
                    }}

                    .section-title {{
                        font-size: 1.5rem;
                        font-weight: 600;
                        color: var(--primary-color);
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }}

                    /* Expand/Collapse Functionality */
                    .collapsible {{
                        cursor: pointer;
                        user-select: none;
                        transition: var(--transition);
                        background: none;
                        border: none;
                        color: var(--primary-color);
                        font-size: 0.9rem;
                        font-weight: 500;
                        padding: 8px 16px;
                        border-radius: 20px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}

                    .collapsible:hover {{
                        background: rgba(0, 123, 255, 0.1);
                    }}

                    .collapsible-content {{
                        max-height: 2000px;
                        overflow: hidden;
                        transition: max-height 0.4s ease-out, opacity 0.3s ease;
                        opacity: 1;
                    }}

                    .collapsible-content.collapsed {{
                        max-height: 0;
                        opacity: 0;
                    }}

                    .expand-icon {{
                        transition: transform 0.3s ease;
                        font-size: 1rem;
                        color: var(--primary-color);
                    }}

                    .expand-icon.rotated {{
                        transform: rotate(180deg);
                    }}

                    /* Stack Sections */
                    .stack-section {{
                        margin-bottom: 30px;
                        border: 1px solid #e9ecef;
                        border-radius: var(--border-radius);
                        overflow: hidden;
                        background: white;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        transition: var(--transition);
                    }}

                    .stack-section:hover {{
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    }}

                    .stack-header {{
                        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
                        padding: 15px 20px;
                        border-bottom: 1px solid #dee2e6;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        cursor: pointer;
                        transition: var(--transition);
                    }}

                    .stack-header:hover {{
                        background: linear-gradient(135deg, #e9ecef, #dee2e6);
                    }}

                    .stack-title {{
                        font-size: 1.2rem;
                        font-weight: 600;
                        color: var(--dark-color);
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }}

                    .stack-path {{
                        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                        font-size: 0.85rem;
                        color: var(--secondary-color);
                        background: rgba(108, 117, 125, 0.1);
                        padding: 4px 8px;
                        border-radius: 4px;
                    }}

                    /* Table Styles */
                    .table-section {{
                        margin: 20px 0;
                    }}

                    .table-title {{
                        font-size: 1.1rem;
                        font-weight: 600;
                        margin-bottom: 15px;
                        color: var(--dark-color);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}

                    .table-container {{
                        max-height: 600px;
                        overflow-y: auto;
                        border-radius: var(--border-radius);
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        border: 1px solid #e9ecef;
                    }}

                    .table-container::-webkit-scrollbar {{
                        width: 8px;
                    }}

                    .table-container::-webkit-scrollbar-track {{
                        background: #f1f1f1;
                        border-radius: 4px;
                    }}

                    .table-container::-webkit-scrollbar-thumb {{
                        background: #c1c1c1;
                        border-radius: 4px;
                    }}

                    .table-container::-webkit-scrollbar-thumb:hover {{
                        background: #a8a8a8;
                    }}

                    .components-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 0;
                        background: white;
                        border-radius: 0;
                        box-shadow: none;
                        border: none;
                    }}

                    .components-table th {{
                        background: linear-gradient(135deg, var(--primary-color), #0056b3);
                        color: white;
                        padding: 12px 15px;
                        text-align: left;
                        font-weight: 600;
                        font-size: 0.9rem;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}

                    .components-table td {{
                        padding: 12px 15px;
                        border-bottom: 1px solid #e9ecef;
                        vertical-align: top;
                    }}

                    .components-table tr:hover {{
                        background-color: #f8f9fa;
                        transition: var(--transition);
                    }}

                    .components-table tr:last-child td {{
                        border-bottom: none;
                    }}

                    /* Status Badges */
                    .status-badge {{
                        padding: 4px 12px;
                        border-radius: 20px;
                        font-size: 0.8rem;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}

                    .status-current {{
                        background: var(--success-color);
                        color: white;
                    }}

                    .status-outdated {{
                        background: var(--warning-color);
                        color: #856404;
                    }}

                    .status-unknown {{
                        background: var(--secondary-color);
                        color: white;
                    }}

                    /* Summary Grid */
                    .summary-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}

                    .summary-card {{
                        background: white;
                        padding: 20px;
                        border-radius: var(--border-radius);
                        text-align: center;
                        box-shadow: var(--box-shadow);
                        border-left: 4px solid var(--primary-color);
                        transition: var(--transition);
                    }}

                    .summary-card:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    }}

                    .summary-number {{
                        font-size: 2.5rem;
                        font-weight: 700;
                        color: var(--primary-color);
                        margin-bottom: 5px;
                    }}

                    .summary-label {{
                        font-size: 0.9rem;
                        color: var(--secondary-color);
                        font-weight: 500;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}

                    /* Compatibility Section Styles */
                    .compatibility-section {{
                        margin: 20px 0;
                        padding: 15px;
                        background-color: #f8f9fa;
                        border-left: 4px solid #007bff;
                        border-radius: 5px;
                    }}

                    .compatibility-header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        cursor: pointer;
                        margin-bottom: 15px;
                    }}

                    .compatibility-content {{
                        transition: max-height 0.4s ease-out, opacity 0.3s ease;
                        max-height: 800px;
                        opacity: 1;
                        overflow-y: auto;
                    }}

                    .compatibility-content::-webkit-scrollbar {{
                        width: 8px;
                    }}

                    .compatibility-content::-webkit-scrollbar-track {{
                        background: #f1f1f1;
                        border-radius: 4px;
                    }}

                    .compatibility-content::-webkit-scrollbar-thumb {{
                        background: #c1c1c1;
                        border-radius: 4px;
                    }}

                    .compatibility-content::-webkit-scrollbar-thumb:hover {{
                        background: #a8a8a8;
                    }}

                    .compatibility-content.collapsed {{
                        max-height: 0;
                        opacity: 0;
                        overflow: hidden;
                    }}

                    .provider-compatibility-section {{
                        margin: 15px 0;
                        border: 1px solid #dee2e6;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}

                    .provider-compatibility-header {{
                        padding: 15px;
                        cursor: pointer;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        transition: background-color 0.3s ease;
                    }}

                    .provider-compatibility-content {{
                        background: white;
                        transition: max-height 0.4s ease-out, opacity 0.3s ease;
                        max-height: 1000px;
                        opacity: 1;
                        overflow-y: auto;
                        max-height: 500px;
                    }}

                    .provider-compatibility-content.collapsed {{
                        max-height: 0;
                        opacity: 0;
                        overflow: hidden;
                    }}

                    .provider-compatibility-content::-webkit-scrollbar {{
                        width: 8px;
                    }}

                    .provider-compatibility-content::-webkit-scrollbar-track {{
                        background: #f1f1f1;
                        border-radius: 4px;
                    }}

                    .provider-compatibility-content::-webkit-scrollbar-thumb {{
                        background: #c1c1c1;
                        border-radius: 4px;
                    }}

                    .provider-compatibility-content::-webkit-scrollbar-thumb:hover {{
                        background: #a8a8a8;
                    }}

                    /* Back to Top Button */
                    .back-to-top {{
                        position: fixed;
                        bottom: 20px;
                        right: 20px;
                        background: var(--primary-color);
                        color: white;
                        border: none;
                        border-radius: 50%;
                        width: 50px;
                        height: 50px;
                        font-size: 1.2rem;
                        cursor: pointer;
                        box-shadow: var(--box-shadow);
                        transition: var(--transition);
                        opacity: 0;
                        visibility: hidden;
                        z-index: 1000;
                    }}

                    .back-to-top.visible {{
                        opacity: 1;
                        visibility: visible;
                    }}

                    .back-to-top:hover {{
                        background: #0056b3;
                        transform: translateY(-2px);
                    }}

                    /* Responsive Design */
                    @media (max-width: 768px) {{
                        body {{
                            padding: 10px;
                        }}

                        .content-section {{
                            padding: 20px;
                        }}

                        .nav-menu {{
                            flex-direction: column;
                            gap: 10px;
                        }}

                        .summary-grid {{
                            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                            gap: 15px;
                        }}

                        .components-table {{
                            font-size: 0.85rem;
                        }}

                        .components-table th,
                        .components-table td {{
                            padding: 8px 10px;
                        }}

                        .section-header {{
                            flex-direction: column;
                            align-items: flex-start;
                            gap: 10px;
                        }}
                    }}

                    /* Print Styles */
                    @media print {{
                        body {{
                            background: white;
                            padding: 0;
                        }}

                        .container {{
                            box-shadow: none;
                            border-radius: 0;
                        }}

                        .nav-header {{
                            position: static;
                            background: var(--primary-color) !important;
                        }}

                        .collapsible-content {{
                            max-height: none !important;
                            opacity: 1 !important;
                        }}

                        .stack-section {{
                            break-inside: avoid;
                        }}

                        .back-to-top {{
                            display: none;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <!-- Navigation Header -->
                    <div class="nav-header">
                        <div class="nav-title">📊 Infrastructure Inventory Report</div>
                        <div class="nav-subtitle">
                            {project_name} • {project_type} • Generated on {timestamp}
                        </div>
                        <nav class="nav-menu">
                            <a href="#summary" class="nav-link">📈 Summary</a>
                            <a href="#compatibility" class="nav-link">🔍 Compatibility</a>
                            <a href="#components" class="nav-link">🧩 Components</a>
                        </nav>
                    </div>

                    <!-- Summary Section -->
                    <section id="summary" class="content-section">
                        <div class="section-header">
                            <h2 class="section-title">📈 Summary Overview</h2>
                        </div>
                        {summary_table}
                    </section>

                    <!-- Schema Compatibility Section -->
                    <section id="compatibility" class="content-section">
                        <div class="section-header">
                            <h2 class="section-title">🔍 Compatibility Analysis</h2>
                        </div>
                        {compatibility_section}
                    </section>

                    <!-- Components Section -->
                    <section id="components" class="content-section">
                        <div class="section-header">
                            <h2 class="section-title">🧩 Infrastructure Components</h2>
                            <button class="collapsible" onclick="toggleAllSections()">
                                <span id="toggle-all-text">Collapse All</span>
                                <span class="expand-icon" id="toggle-all-icon">▼</span>
                            </button>
                        </div>
                        <div class="stacks-container">
                            {content}
                        </div>
                    </section>
                </div>

                <!-- Back to Top Button -->
                <button class="back-to-top" id="backToTop" onclick="scrollToTop()">↑</button>

                <script>
                    // Navigation and Interactivity JavaScript
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Initialize collapsible sections
                        initializeCollapsibleSections();
                        
                        // Initialize back to top button
                        initializeBackToTop();
                        
                        // Initialize smooth scrolling for navigation links
                        initializeSmoothScrolling();
                        
                        // Add click tracking for analytics (optional)
                        trackUserInteractions();
                    }});

                    function initializeCollapsibleSections() {{
                        // Make stack headers collapsible
                        const stackHeaders = document.querySelectorAll('.stack-header');
                        stackHeaders.forEach(header => {{
                            // Add expand icon to stack headers
                            const expandIcon = document.createElement('span');
                            expandIcon.className = 'expand-icon';
                            expandIcon.innerHTML = '▼';
                            expandIcon.style.marginLeft = '10px';
                            header.appendChild(expandIcon);
                            
                            header.addEventListener('click', function() {{
                                toggleStackSection(this);
                            }});
                        }});
                    }}

                    function toggleStackSection(header) {{
                        const stackSection = header.parentElement;
                        const content = stackSection.querySelector('.table-section')?.parentElement || 
                                       stackSection.querySelector('.collapsible-content');
                        const icon = header.querySelector('.expand-icon');
                        
                        if (content) {{
                            // Create collapsible wrapper if it doesn't exist
                            if (!content.classList.contains('collapsible-content')) {{
                                const wrapper = document.createElement('div');
                                wrapper.className = 'collapsible-content';
                                content.parentNode.insertBefore(wrapper, content);
                                wrapper.appendChild(content);
                            }}
                            
                            const wrapper = content.classList.contains('collapsible-content') ? content : content.parentElement;
                            wrapper.classList.toggle('collapsed');
                            icon.classList.toggle('rotated');
                        }}
                    }}

                    function toggleAllSections() {{
                        const allStackSections = document.querySelectorAll('.stack-section');
                        const toggleText = document.getElementById('toggle-all-text');
                        const toggleIcon = document.getElementById('toggle-all-icon');
                        const isCollapsed = toggleText.textContent === 'Expand All';
                        
                        allStackSections.forEach(section => {{
                            const content = section.querySelector('.collapsible-content') || 
                                          section.querySelector('.table-section')?.parentElement;
                            const icon = section.querySelector('.stack-header .expand-icon');
                            
                            if (content) {{
                                // Create collapsible wrapper if it doesn't exist
                                if (!content.classList.contains('collapsible-content')) {{
                                    const wrapper = document.createElement('div');
                                    wrapper.className = 'collapsible-content';
                                    content.parentNode.insertBefore(wrapper, content);
                                    wrapper.appendChild(content);
                                }}
                                
                                const wrapper = content.classList.contains('collapsible-content') ? content : content.parentElement;
                                
                                if (isCollapsed) {{
                                    wrapper.classList.remove('collapsed');
                                    if (icon) icon.classList.remove('rotated');
                                }} else {{
                                    wrapper.classList.add('collapsed');
                                    if (icon) icon.classList.add('rotated');
                                }}
                            }}
                        }});
                        
                        // Update toggle button text
                        toggleText.textContent = isCollapsed ? 'Collapse All' : 'Expand All';
                        toggleIcon.textContent = isCollapsed ? '▼' : '▲';
                    }}

                    function initializeBackToTop() {{
                        const backToTopButton = document.getElementById('backToTop');
                        
                        window.addEventListener('scroll', function() {{
                            if (window.pageYOffset > 300) {{
                                backToTopButton.classList.add('visible');
                            }} else {{
                                backToTopButton.classList.remove('visible');
                            }}
                        }});
                    }}

                    function scrollToTop() {{
                        window.scrollTo({{
                            top: 0,
                            behavior: 'smooth'
                        }});
                    }}

                    function initializeSmoothScrolling() {{
                        const navLinks = document.querySelectorAll('.nav-link[href^="#"]');
                        navLinks.forEach(link => {{
                            link.addEventListener('click', function(e) {{
                                e.preventDefault();
                                const targetId = this.getAttribute('href').substring(1);
                                const targetElement = document.getElementById(targetId);
                                
                                if (targetElement) {{
                                    const offsetTop = targetElement.offsetTop - 80; // Account for sticky header
                                    window.scrollTo({{
                                        top: offsetTop,
                                        behavior: 'smooth'
                                    }});
                                }}
                            }});
                        }});
                    }}

                    function trackUserInteractions() {{
                        // Track section expansions
                        document.addEventListener('click', function(e) {{
                            if (e.target.closest('.stack-header')) {{
                                const stackTitle = e.target.closest('.stack-section')?.querySelector('.stack-title')?.textContent;
                                console.log('Stack section toggled:', stackTitle);
                            }}
                            
                            if (e.target.closest('.nav-link')) {{
                                console.log('Navigation clicked:', e.target.textContent);
                            }}
                        }});
                    }}

                    // Compatibility section toggle functions
                    function toggleProviderCompatibilitySection() {{
                        const content = document.getElementById('provider-compatibility-content');
                        const icon = document.getElementById('provider-compatibility-icon');
                        
                        if (content && icon) {{
                            content.classList.toggle('collapsed');
                            icon.classList.toggle('rotated');
                            
                            if (content.classList.contains('collapsed')) {{
                                icon.textContent = '▶';
                            }} else {{
                                icon.textContent = '▼';
                            }}
                        }}
                    }}

                    function toggleModuleCompatibilitySection() {{
                        const content = document.getElementById('module-compatibility-content');
                        const icon = document.getElementById('module-compatibility-icon');
                        
                        if (content && icon) {{
                            content.classList.toggle('collapsed');
                            icon.classList.toggle('rotated');
                            
                            if (content.classList.contains('collapsed')) {{
                                icon.textContent = '▶';
                            }} else {{
                                icon.textContent = '▼';
                            }}
                        }}
                    }}

                    function toggleProviderCompatibility(providerId) {{
                        const content = document.getElementById(providerId + '-content');
                        const icon = document.getElementById(providerId + '-icon');
                        
                        if (content && icon) {{
                            content.classList.toggle('collapsed');
                            icon.classList.toggle('rotated');
                            
                            if (content.classList.contains('collapsed')) {{
                                icon.textContent = '▶';
                            }} else {{
                                icon.textContent = '▼';
                            }}
                        }}
                    }}

                    function toggleModuleCompatibility(moduleId) {{
                        const content = document.getElementById(moduleId + '-content');
                        const icon = document.getElementById(moduleId + '-icon');
                        
                        if (content && icon) {{
                            content.classList.toggle('collapsed');
                            icon.classList.toggle('rotated');
                            
                            if (content.classList.contains('collapsed')) {{
                                icon.textContent = '▶';
                            }} else {{
                                icon.textContent = '▼';
                            }}
                        }}
                    }}

                    // Enhanced keyboard shortcuts
                    document.addEventListener('keydown', function(e) {{
                        // Escape to collapse all sections
                        if (e.key === 'Escape') {{
                            const expandedSections = document.querySelectorAll('.collapsible-content:not(.collapsed)');
                            if (expandedSections.length > 0) {{
                                toggleAllSections();
                            }}
                            
                            // Also collapse compatibility sections
                            const providerCompatibilityContent = document.getElementById('provider-compatibility-content');
                            if (providerCompatibilityContent && !providerCompatibilityContent.classList.contains('collapsed')) {{
                                toggleProviderCompatibilitySection();
                            }}
                            
                            const moduleCompatibilityContent = document.getElementById('module-compatibility-content');
                            if (moduleCompatibilityContent && !moduleCompatibilityContent.classList.contains('collapsed')) {{
                                toggleModuleCompatibilitySection();
                            }}
                        }}
                        
                        // Home key to scroll to top
                        if (e.key === 'Home' && e.ctrlKey) {{
                            e.preventDefault();
                            scrollToTop();
                        }}
                        
                        // 'C' key to toggle compatibility section
                        if (e.key === 'c' || e.key === 'C') {{
                            if (!e.ctrlKey && !e.altKey && !e.metaKey) {{
                                const compatibilitySection = document.querySelector('.compatibility-section');
                                if (compatibilitySection) {{
                                    toggleCompatibilitySection();
                                }}
                            }}
                        }}
                    }});

                    // Add section anchors for better navigation
                    function addSectionAnchors() {{
                        const stackSections = document.querySelectorAll('.stack-section');
                        stackSections.forEach((section, index) => {{
                            const title = section.querySelector('.stack-title');
                            if (title) {{
                                const anchor = title.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-');
                                section.id = `stack-${{index}}-${{anchor}}`;
                                
                                // Add anchor link to title
                                const anchorLink = document.createElement('a');
                                anchorLink.href = `#${{section.id}}`;
                                anchorLink.style.color = 'inherit';
                                anchorLink.style.textDecoration = 'none';
                                anchorLink.innerHTML = title.innerHTML;
                                title.innerHTML = '';
                                title.appendChild(anchorLink);
                            }}
                        }});
                    }}

                    // Initialize section anchors after DOM is loaded
                    document.addEventListener('DOMContentLoaded', addSectionAnchors);
                </script>
            </body>
            </html>
            """

            # Generate summary statistics
            summary_html = self._generate_summary_html(inventory)
            
            # Generate schema compatibility section if available
            compatibility_html = self._generate_compatibility_html(inventory)
            
            # Generate custom HTML for components and providers
            components_html = self._generate_components_html(inventory)

            # Create report file
            report_path = self._create_report_path(report_name, "html", reports_directory)

            # Write the report with proper formatting
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_template.format(
                    content=components_html,
                    summary_table=summary_html,
                    compatibility_section=compatibility_html,
                    project_name=inventory.get("projectName", inventory.get("project_name", "Unknown")),
                    project_type=inventory.get("projectType", "Terraform"),
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

            logger.info(f"HTML report created at: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to create HTML report: {str(e)}")
            raise

    def _generate_components_html(self, inventory: Dict[str, Any]) -> str:
        """Generate HTML for components and providers sections."""
        try:
            components_html = ""
            
            for component_group in inventory.get("components", []):
                stack = component_group.get("stack", "Unknown")
                stack_path = component_group.get("path", "")
                
                # Create unique ID for the stack section
                stack_id = stack.lower().replace("/", "-").replace("\\", "-").replace(" ", "-")
                
                components_html += f"""
                <div class="stack-section" id="stack-{stack_id}">
                    <div class="stack-header">
                        <div class="stack-title">
                            📁 {stack}
                        </div>
                        <div class="stack-path">{stack_path}</div>
                    </div>
                    <div class="collapsible-content">
                """
                
                # Add components table
                components = component_group.get("components", [])
                if components:
                    components_html += """
                        <div class="table-section">
                            <h3 class="table-title">🧩 Components</h3>
                            <div class="table-container">
                                <table class="components-table">
                                    <thead>
                                        <tr>
                                            <th>Type</th>
                                            <th>Name</th>
                                            <th>Source</th>
                                            <th>Version</th>
                                            <th>Latest</th>
                                            <th>SourceUrl</th>
                                            <th>Status</th>
                                            <th>Path</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    """
                    
                    for component in components:
                        source = component.get("source", "Unknown")
                        version = component.get("version", "Unknown")
                        latest_version = component.get("latest_version", "Unknown")
                        source_url = component.get("source_url", "Unknown")
                        status = component.get("status", "Unknown")
                        path = component.get("path", "Unknown")
                        name = component.get("name", "Unknown")
                        
                        # Determine status styling
                        status_display = f'<span class="status-badge status-{status.lower()}">{status}</span>' if status != "Null" else '<span style="color: #9ca3af;">—</span>'
                        
                        # Add anchor link for component
                        component_id = f"{stack_id}-{name.lower().replace(' ', '-')}"
                        
                        components_html += f"""
                        <tr id="component-{component_id}">
                            <td><strong>{component.get("type", "Unknown")}</strong></td>
                            <td>
                                <a href="#component-{component_id}" style="color: var(--primary-color); text-decoration: none;">
                                    {name}
                                </a>
                            </td>
                            <td><code style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">{source}</code></td>
                            <td><span style="font-family: monospace; color: var(--info-color);">{version}</span></td>
                            <td><span style="font-family: monospace; color: var(--success-color);">{latest_version}</span></td>
                            <td>{source_url if source_url != "Unknown" else '<span style="color: #9ca3af;">—</span>'}</td>
                            <td>{status_display}</td>
                            <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{path}</code></td>
                        </tr>
                        """
                    
                    components_html += """
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    """
                
                # Add providers table if available
                providers = component_group.get("providers", [])
                if providers:
                    components_html += """
                        <div class="table-section">
                            <h3 class="table-title">⚙️ Providers</h3>
                            <div class="table-container">
                                <table class="components-table">
                                    <thead>
                                        <tr>
                                            <th>Provider</th>
                                            <th>Version</th>
                                            <th>Source</th>
                                            <th>Latest Version</th>
                                            <th>SourceUrl</th>
                                            <th>Status</th>
                                            <th>Component</th>
                                            <th>Module</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    """
                    
                    for provider in providers:
                        name = provider.get("name", "Unknown")
                        version = provider.get("version", "Unknown")
                        source = provider.get("source", "Unknown")
                        latest_version = provider.get("latest_version", "Unknown")
                        source_url = provider.get("source_url", "Unknown")
                        status = provider.get("status", "Unknown")
                        module = provider.get("module", "Unknown")
                        component = provider.get("component", "Unknown")
                        
                        # Create provider anchor
                        provider_id = f"{stack_id}-provider-{name.lower().replace(' ', '-')}"
                        
                        # Format status badge with proper styling
                        if status.lower() == "current":
                            status_display = f'<span class="status-badge status-current">{status}</span>'
                        elif status.lower() == "outdated":
                            status_display = f'<span class="status-badge status-outdated">{status}</span>'
                        elif status != "Null" and status != "Unknown":
                            status_display = f'<span class="status-badge status-{status.lower()}">{status}</span>'
                        else:
                            status_display = '<span style="color: #9ca3af;">—</span>'
                        
                        # Format version with color coding
                        version_display = f'<span style="font-family: monospace; color: var(--info-color);">{version}</span>' if version != "Unknown" else '<span style="color: #9ca3af;">—</span>'
                        latest_version_display = f'<span style="font-family: monospace; color: var(--success-color);">{latest_version}</span>' if latest_version != "Unknown" else '<span style="color: #9ca3af;">—</span>'
                        
                        # Format source with proper styling
                        source_display = f'<code style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">{source}</code>' if source != "Unknown" else '<span style="color: #9ca3af;">—</span>'
                        
                        components_html += f"""
                        <tr id="provider-{provider_id}">
                            <td>
                                <strong>
                                    <a href="#provider-{provider_id}" style="color: var(--primary-color); text-decoration: none;">
                                        {name}
                                    </a>
                                </strong>
                            </td>
                            <td>{version_display}</td>
                            <td>{source_display}</td>
                            <td>{latest_version_display}</td>
                            <td>{source_url if source_url != "Unknown" else '<span style="color: #9ca3af;">—</span>'}</td>
                            <td>{status_display}</td>
                            <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{module}</code></td>
                            <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{component}</code></td>
                        </tr>
                        """
                    
                    components_html += """
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    """
                
                
                # Add resources table if available (for modules)
                resources = inventory.get("resources", [])
                if resources:
                    components_html += """
                        <div class="table-section">
                            <h3 class="table-title">📋 Resources</h3>
                            <div class="table-container">
                                <table class="components-table">
                                    <thead>
                                        <tr>
                                            <th>Type</th>
                                            <th>Name</th>
                                            <th>File</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    """
                    
                    for resource in resources:
                        resource_type = resource.get("resource_type", "Unknown")
                        name = resource.get("name", "Unknown")
                        file_name = resource.get("file", "Unknown")
                        
                        components_html += f"""
                        <tr>
                            <td><code style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px; font-size: 0.85em;">{resource_type}</code></td>
                            <td><strong>{name}</strong></td>
                            <td><span style="color: #6c757d;">{file_name}</span></td>
                        </tr>
                        """
                    
                    components_html += """
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    """                # Close the collapsible content and stack section
                components_html += """
                    </div>
                </div>
                """
            
            return components_html
            
        except Exception as e:
            logger.error(f"Failed to generate components HTML: {str(e)}")
            return f'<div class="error-message">Error generating components: {str(e)}</div>'


    def create_cyclonedx_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create CycloneDX SBOM JSON report from inventory data."""
        try:
            from datetime import datetime
            import uuid
            
            report_path = self._create_report_path(report_name + "_cyclonedx", "json", reports_directory)
            
            # Generate CycloneDX SBOM structure
            cyclonedx_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "serialNumber": f"urn:uuid:{str(uuid.uuid4())}",
                "version": 1,
                "metadata": {
                    "timestamp": datetime.now().isoformat() + "Z",
                    "tools": [
                        {
                            "vendor": "ThothForge",
                            "name": "thothctl",
                            "version": "latest"
                        }
                    ],
                    "component": {
                        "type": "application",
                        "bom-ref": inventory.get("projectName", "infrastructure-project"),
                        "name": inventory.get("projectName", "Infrastructure Project"),
                        "description": f"Infrastructure as Code project ({inventory.get('projectType', 'terraform')})"
                    }
                },
                "components": []
            }
            
            # Convert inventory components to CycloneDX components
            for component_group in inventory.get("components", []):
                stack_name = component_group.get("stack", "")
                
                for component in component_group.get("components", []):
                    # Extract version (handle list format)
                    version = component.get("version", ["latest"])
                    if isinstance(version, list):
                        version = version[0] if version else "latest"
                    
                    # Extract source (handle list format)
                    source = component.get("source", [""])
                    if isinstance(source, list):
                        source = source[0] if source else ""
                    
                    cyclonedx_component = {
                        "type": "library",
                        "bom-ref": f"{stack_name}/{component.get('name', 'unknown')}",
                        "name": component.get("name", "unknown"),
                        "version": version,
                        "scope": "required"
                    }
                    
                    # Add source information if available
                    if source and source != "Null":
                        cyclonedx_component["purl"] = f"terraform/{source}@{version}"
                        
                    # Add external references
                    external_refs = []
                    if component.get("source_url") and component.get("source_url") != "Null":
                        external_refs.append({
                            "type": "vcs",
                            "url": component.get("source_url")
                        })
                    
                    if external_refs:
                        cyclonedx_component["externalReferences"] = external_refs
                    
                    # Add properties for additional metadata
                    properties = [
                        {"name": "thothctl:stack", "value": stack_name},
                        {"name": "thothctl:type", "value": component.get("type", "module")},
                        {"name": "thothctl:file", "value": component.get("file", "")},
                        {"name": "thothctl:status", "value": component.get("status", "Unknown")}
                    ]
                    
                    if component.get("latest_version") and component.get("latest_version") != "Null":
                        properties.append({"name": "thothctl:latest_version", "value": component.get("latest_version")})
                    
                    cyclonedx_component["properties"] = properties
                    cyclonedx_data["components"].append(cyclonedx_component)
                
                # Add providers as components
                for provider in component_group.get("providers", []):
                    cyclonedx_provider = {
                        "type": "library",
                        "bom-ref": f"{stack_name}/provider-{provider.get('name', 'unknown')}",
                        "name": f"terraform-provider-{provider.get('name', 'unknown')}",
                        "version": provider.get("version", "latest"),
                        "scope": "required",
                        "properties": [
                            {"name": "thothctl:stack", "value": stack_name},
                            {"name": "thothctl:type", "value": "provider"},
                            {"name": "thothctl:source", "value": provider.get("source", "")},
                            {"name": "thothctl:status", "value": provider.get("status", "Unknown")}
                        ]
                    }
                    
                    if provider.get("latest_version") and provider.get("latest_version") != "Null":
                        cyclonedx_provider["properties"].append({
                            "name": "thothctl:latest_version", 
                            "value": provider.get("latest_version")
                        })
                    
                    if provider.get("source_url") and provider.get("source_url") != "Null":
                        cyclonedx_provider["externalReferences"] = [{
                            "type": "distribution",
                            "url": provider.get("source_url")
                        }]
                    
                    cyclonedx_data["components"].append(cyclonedx_provider)

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(cyclonedx_data, f, indent=2, ensure_ascii=False)

            logger.info(f"CycloneDX SBOM report created at: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to create CycloneDX report: {str(e)}")
            raise

    def print_inventory_console(self, inventory: Dict[str, Any]) -> None:
        """Print inventory to console using rich table with updated format."""
        try:
            # Create project info panel
            project_name = inventory.get("projectName", "Unknown")
            project_type = inventory.get("projectType", "Terraform")
            
            # Create main table
            table = Table(
                title=f"Infrastructure Inventory Report - {project_name} ({project_type})",
                box=box.ROUNDED,
                header_style="bold magenta",
                title_style="bold blue",
                show_lines=True,
                expand=True,
            )
            table.add_column("Stack", style="dim", max_width=40)
            table.add_column(
                "Components",
                style="dim",
            )

            # Process components
            for component_group in inventory.get("components", []):
                stack_path = component_group.get("stack", "Unknown")
                
                # Create components table
                components_table = Table(show_lines=True)
                components_table.add_column("Type", style="cyan")
                components_table.add_column("Name", style="blue")
                components_table.add_column("Current Version", style="green")
                components_table.add_column("Source", style="white", overflow="fold")
                components_table.add_column("Latest Version", style="yellow")
                components_table.add_column("SourceUrl")
                components_table.add_column("Status", justify="center")

                # Add components to table
                for component in component_group.get("components", []):
                    current_version = component.get("version", ["Null"])
                    if isinstance(current_version, list):
                        current_version = current_version[0]

                    status = component.get("status", "Unknown")
                    status_style = {
                        "Updated": Style(color="green", bold=True),
                        "Outdated": Style(color="red", bold=True),
                        "Unknown": Style(color="yellow", bold=True),
                        "Null": Style(color="blue", bold=True),
                    }.get(status, Style(color="white"))

                    source = component.get("source", ["Unknown"])
                    if isinstance(source, list) and source:
                        source = source[0]
                    else:
                        source = "Unknown"

                    components_table.add_row(
                        component.get("type", "Unknown"),
                        component.get("name", "Unknown"),
                        str(current_version),
                        str(source),
                        str(component.get("latest_version", "Unknown")),
                        str(component.get("source_url", "Unknown")),
                        status,
                    )
                
                # Create providers table if available
                providers = component_group.get("providers", [])
                if providers:
                    providers_table = Table(show_lines=True, title="Providers")
                    providers_table.add_column("Name", style="cyan")
                    providers_table.add_column("Version", style="green")
                    providers_table.add_column("Source", style="white", overflow="fold")
                    providers_table.add_column("Latest Version", style="yellow")
                    providers_table.add_column("SourceUrl", style="blue", overflow="fold")
                    providers_table.add_column("Status", style="red")
                    providers_table.add_column("Module", style="yellow", overflow="fold")
                    providers_table.add_column("Component", style="magenta", overflow="fold")
                    
                    # Get the stack name for this component group
                    stack_name = component_group.get("stack", "Unknown")
                    
                    for provider in providers:
                        # Use the stack name if the module is empty or "Root"
                        module_name = provider.get("module", "")
                        if not module_name or module_name == "Root":
                            module_name = stack_name
                            
                        # Get provider version information
                        latest_version = provider.get("latest_version", "Null")
                        source_url = provider.get("source_url", "Null")
                        status = provider.get("status", "Unknown")
                        
                        providers_table.add_row(
                            provider.get("name", "Unknown"),
                            provider.get("version", "Unknown"),
                            provider.get("source", "Unknown"),
                            latest_version,
                            source_url,
                            status,
                            module_name,
                            provider.get("component", ""),
                        )
                    
                    
                    # Create resources table if available (for modules)
                    resources = inventory.get("resources", [])
                    if resources:
                        resources_table = Table(show_lines=True, title="Resources")
                        resources_table.add_column("Type", style="cyan")
                        resources_table.add_column("Name", style="green")
                        resources_table.add_column("File", style="white")
                        
                        for resource in resources:
                            resources_table.add_row(
                                resource.get("resource_type", "Unknown"),
                                resource.get("name", "Unknown"),
                                resource.get("file", "Unknown"),
                            )
                    
                    # Add tables to the main table
                    grid = Table.grid()
                    grid.add_row(components_table)
                    grid.add_row(providers_table)
                    if resources:
                        grid.add_row(resources_table)
                    
                    table.add_row(
                        Align(f'[blue]{stack_path}[/blue]', vertical="middle"),
                        grid
                    )
                else:
                    # Add only components table
                    table.add_row(
                        Align(f'[blue]{stack_path}[/blue]', vertical="middle"),
                        components_table,
                    )

            # Print the table
            self.console.print()
            self.console.print(Align.center(table))
            self.console.print()

            # Print summary
            self._print_summary(inventory)

        except Exception as e:
            logger.error(f"Failed to print inventory to console: {str(e)}")
            self.console.print(f"[red]Error displaying inventory: {str(e)}[/red]")

    def _generate_summary_html(self, inventory: Dict[str, Any]) -> str:
        """Generate HTML summary table from inventory data."""
        try:
            # Calculate summary statistics using the same logic as CLI
            total_components = len(inventory.get("components", []))
            
            # Count components by status (for version checking)
            outdated_components = 0
            updated_components = 0
            unknown_components = 0
            
            # Count local modules based on source, not status
            local_components = 0
            
            # Use unique providers count if available, otherwise count all providers
            total_providers = inventory.get("unique_providers_count", 0)
            if total_providers == 0:
                # Fall back to counting all providers if unique count not available
                for component_group in inventory.get("components", []):
                    total_providers += len(component_group.get("providers", []))
            
            for component_group in inventory.get("components", []):
                for component in component_group.get("components", []):
                    # Count by version status
                    status = component.get("status", "Unknown")
                    if status == "Outdated":
                        outdated_components += 1
                    elif status == "Updated":
                        updated_components += 1
                    elif status == "Unknown" or status == "Null":
                        unknown_components += 1
                    
                    # Count local modules by source
                    source = component.get("source", [""])[0] if component.get("source") else ""
                    if self._is_local_source(source):
                        local_components += 1

            # Count framework-specific modules
            project_type = inventory.get('projectType', 'terraform').lower()
            terragrunt_modules = 0
            terraform_modules = 0
            
            for component_group in inventory.get("components", []):
                for component in component_group.get("components", []):
                    comp_type = component.get("type", "").lower()
                    if "terragrunt" in comp_type:
                        terragrunt_modules += 1
                    elif "terraform" in comp_type:
                        terraform_modules += 1

            # Generate modern card-based summary
            summary_html = f"""
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-number" style="color: var(--primary-color);">{total_components}</div>
                    <div class="summary-label">Total Components</div>
                </div>
                <div class="summary-card updated">
                    <div class="summary-number" style="color: var(--success-color);">{updated_components}</div>
                    <div class="summary-label">Updated Components</div>
                </div>
                <div class="summary-card outdated">
                    <div class="summary-number" style="color: var(--danger-color);">{outdated_components}</div>
                    <div class="summary-label">Outdated Components</div>
                </div>
                <div class="summary-card unknown">
                    <div class="summary-number" style="color: var(--warning-color);">{unknown_components}</div>
                    <div class="summary-label">Unknown Status</div>
                </div>
                <div class="summary-card local">
                    <div class="summary-number" style="color: var(--info-color);">{local_components}</div>
                    <div class="summary-label">Local Modules</div>
                </div>
            """
            
            # Add resources card if we have resources (for modules)
            resources = inventory.get("resources", [])
            if resources:
                summary_html += f"""
                <div class="summary-card">
                    <div class="summary-number" style="color: var(--info-color);">{len(resources)}</div>
                    <div class="summary-label">Resources</div>
                </div>
                """
            
            # Add providers card if we have providers
            if total_providers > 0:
                summary_html += f"""
                <div class="summary-card">
                    <div class="summary-number" style="color: var(--secondary-color);">{total_providers}</div>
                    <div class="summary-label">Providers</div>
                </div>
                """
            
            # Add framework-specific cards
            if project_type == 'terragrunt' and terragrunt_modules > 0:
                summary_html += f"""
                <div class="summary-card">
                    <div class="summary-number" style="color: #8b5cf6;">{terragrunt_modules}</div>
                    <div class="summary-label">Terragrunt Modules</div>
                </div>
                """
            elif terraform_modules > 0:
                summary_html += f"""
                <div class="summary-card">
                    <div class="summary-number" style="color: #8b5cf6;">{terraform_modules}</div>
                    <div class="summary-label">Terraform Modules</div>
                </div>
                """
            
            summary_html += "</div>"
            
            return summary_html

        except Exception as e:
            logger.error(f"Failed to generate summary HTML: {str(e)}")
            return f'<div class="empty-state"><div class="empty-state-icon">⚠️</div><p>Error generating summary: {str(e)}</p></div>'

    def _generate_providers_html(self, component_group: Dict[str, Any]) -> str:
        """Generate HTML table for provider information."""
        providers = component_group.get("providers", [])
        if not providers:
            return ""
            
        # Get the stack name for this component group
        stack_name = component_group.get("stack", "Unknown")
        
        providers_html = f"""
        <h3>Providers for {stack_name}</h3>
        <table class="components-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Source</th>
                    <th>Latest Version</th>
                    <th>Status</th>
                    <th>Module</th>
                    <th>Component</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for provider in providers:
            # Use the stack name if the module is empty or "Root"
            module_name = provider.get("module", "")
            if not module_name or module_name == "Root":
                module_name = stack_name
            
            # Get provider version information
            latest_version = provider.get("latest_version", "Null")
            status = provider.get("status", "Unknown")
            status_class = f"status-{status.lower()}" if status != "Null" and status != "Unknown" else ""
                
            providers_html += f"""
            <tr>
                <td>{provider.get('name', 'Unknown')}</td>
                <td>{provider.get('version', 'Unknown')}</td>
                <td>{provider.get('source', 'Unknown')}</td>
                <td>{latest_version}</td>
                <td class="{status_class}">{status}</td>
                <td>{module_name}</td>
                <td>{provider.get('component', '')}</td>
            </tr>
            """
            
        providers_html += """
            </tbody>
        </table>
        """
        
        return providers_html

    def _is_local_source(self, source: str) -> bool:
        """Check if a source is a local path."""
        if not source or source == "Null":
            return False
            
        return (source.startswith("./") or 
                source.startswith("../") or 
                source.startswith("/") or
                source.startswith("../../") or
                source.startswith("../../../") or
                source.startswith("../../../../") or
                (not source.startswith("http") and not source.startswith("git") and "/" in source and not source.count("/") == 2))

    def _print_summary(self, inventory: Dict[str, Any]) -> None:
        """Print inventory summary statistics."""
        try:
            total_components = sum(
                len(group.get("components", []))
                for group in inventory.get("components", [])
            )

            # Count by version status
            status_counts = {"Updated": 0, "Outdated": 0, "Unknown": 0}
            
            # Count local modules by source and providers
            local_modules = 0
            
            # Use unique providers count if available, otherwise count all providers
            total_providers = inventory.get("unique_providers_count", 0)
            if total_providers == 0:
                # Fall back to counting all providers if unique count not available
                for group in inventory.get("components", []):
                    total_providers += len(group.get("providers", []))

            for group in inventory.get("components", []):
                for component in group.get("components", []):
                    # Count by version status
                    status = component.get("status", "Unknown")
                    if status == "Null":
                        status = "Unknown"
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    # Count local modules by source
                    source = component.get("source", [""])[0] if component.get("source") else ""
                    if self._is_local_source(source):
                        local_modules += 1

            summary_table = Table(
                title="Summary",
                box=box.ROUNDED,
                show_header=False,
                title_style="bold blue",
            )

            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="magenta")

            summary_table.add_row("Project Type", inventory.get("projectType", "Terraform"))
            summary_table.add_row("Total Components", str(total_components))
            summary_table.add_row(
                "Updated Components", f"[green]{status_counts['Updated']}[/green]"
            )
            summary_table.add_row(
                "Outdated Components", f"[red]{status_counts['Outdated']}[/red]"
            )
            summary_table.add_row(
                "Unknown Status", f"[yellow]{status_counts['Unknown']}[/yellow]"
            )

            # Add local modules count if any exist
            if local_modules > 0:
                summary_table.add_row(
                    "Local Modules", f"[blue]{local_modules}[/blue]"
                )
                
            # Add providers count if any exist
            if total_providers > 0:
                summary_table.add_row(
                    "Providers", str(total_providers)
                )

            # Add terragrunt stacks count for terraform-terragrunt projects
            project_type = inventory.get('projectType', 'terraform').lower()
            if project_type == 'terraform-terragrunt':
                terragrunt_stacks_count = inventory.get('terragrunt_stacks_count', 0)
                summary_table.add_row("Terragrunt Stacks", str(terragrunt_stacks_count))

            self.console.print(Align.center(summary_table))
            self.console.print()

        except Exception as e:
            logger.error(f"Failed to print summary: {str(e)}")

    def _generate_compatibility_html(self, inventory: Dict[str, Any]) -> str:
        """Generate HTML section for compatibility analysis with collapsible functionality."""
        try:
            compatibility_html = ""
            
            # Generate provider schema compatibility section
            provider_compatibility_html = self._generate_provider_compatibility_html(inventory)
            if provider_compatibility_html:
                compatibility_html += provider_compatibility_html
            
            # Generate module compatibility section
            module_compatibility_html = self._generate_module_compatibility_html(inventory)
            if module_compatibility_html:
                compatibility_html += module_compatibility_html
            
            return compatibility_html
            
        except Exception as e:
            logger.error(f"Failed to generate compatibility HTML: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
                <h2 style="color: #721c24;">🔍 Compatibility Analysis</h2>
                <p><strong>Error:</strong> Failed to generate compatibility report: {str(e)}</p>
            </div>
            """

    def _generate_provider_compatibility_html(self, inventory: Dict[str, Any]) -> str:
        """Generate HTML section for provider schema compatibility analysis."""
        try:
            # Check if schema compatibility data exists
            compatibility_data = inventory.get("schema_compatibility")
            if not compatibility_data:
                return ""
            
            # Check if there's an error in compatibility analysis
            if "error" in compatibility_data:
                return f"""
                <div style="margin: 20px 0; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                    <h2 style="color: #856404;">🔧 Provider Schema Compatibility Analysis</h2>
                    <p><strong>Note:</strong> Schema compatibility analysis encountered an issue: {compatibility_data['error']}</p>
                </div>
                """
            
            # Get compatibility reports
            reports = compatibility_data.get("reports", [])
            if not reports:
                return ""
            
            # Generate compatibility section HTML with collapsible header
            compatibility_html = f"""
            <div class="compatibility-section">
                <div class="compatibility-header" onclick="toggleProviderCompatibilitySection()">
                    <h2 style="color: #007bff; margin: 0;">🔧 Provider Schema Compatibility Analysis</h2>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 0.9rem; color: #6c757d;">{len(reports)} provider(s) analyzed</span>
                        <span class="expand-icon" id="provider-compatibility-icon" style="font-size: 1.2rem; color: #007bff; transition: transform 0.3s ease;">▼</span>
                    </div>
                </div>
                
                <div class="compatibility-content" id="provider-compatibility-content">
                    <p style="color: #6c757d; font-style: italic; margin-bottom: 20px;">
                        This section analyzes provider schema compatibility between your current versions and the latest available versions. 
                        It identifies potential breaking changes, deprecations, and new features that may affect your infrastructure code.
                    </p>
            """
            
            # Process each compatibility report with individual collapsible sections
            for i, report in enumerate(reports):
                provider_name = report.get("provider_name", "Unknown")
                current_version = report.get("current_version", "Unknown")
                latest_version = report.get("latest_version", "Unknown")
                compatibility_level = report.get("compatibility_level", "unknown")
                summary = report.get("summary", "No summary available")
                
                # Create unique ID for this provider report
                provider_id = f"provider-{provider_name.lower()}-{i}"
                
                # Determine border color based on compatibility level
                if compatibility_level == "compatible":
                    border_color = "#28a745"
                    bg_color = "#d4edda"
                    status_icon = "✅"
                elif compatibility_level == "minor_issues":
                    border_color = "#ffc107"
                    bg_color = "#fff3cd"
                    status_icon = "⚠️"
                elif compatibility_level == "breaking_changes":
                    border_color = "#dc3545"
                    bg_color = "#f8d7da"
                    status_icon = "🔴"
                else:
                    border_color = "#6c757d"
                    bg_color = "#e9ecef"
                    status_icon = "❓"
                
                compatibility_html += f"""
                <div class="provider-compatibility-section" style="border-color: {border_color};">
                    <div class="provider-compatibility-header" style="background-color: {bg_color};" onclick="toggleProviderCompatibility('{provider_id}')">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.2rem;">{status_icon}</span>
                            <h4 style="margin: 0; color: #495057;">{provider_name}</h4>
                            <div style="font-family: monospace; font-size: 0.9em;">
                                <span style="background: rgba(255,255,255,0.8); padding: 2px 6px; border-radius: 3px;">{current_version}</span>
                                <span style="margin: 0 8px; color: #6c757d;">→</span>
                                <span style="background: rgba(255,255,255,0.8); padding: 2px 6px; border-radius: 3px;">{latest_version}</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="padding: 2px 8px; background: {border_color}; color: white; border-radius: 12px; font-size: 0.8em; text-transform: uppercase; font-weight: 600;">{compatibility_level.replace('_', ' ')}</span>
                            <span class="expand-icon" id="{provider_id}-icon" style="font-size: 1rem; color: {border_color}; transition: transform 0.3s ease;">▼</span>
                        </div>
                    </div>
                    
                    <div class="provider-compatibility-content" id="{provider_id}-content">
                        <div style="padding: 15px;">
                            <div style="margin-bottom: 15px; padding: 10px; background: rgba(0,0,0,0.02); border-radius: 5px; border-left: 3px solid {border_color};">
                                <p style="margin: 0; color: #495057; font-weight: 500;">{summary}</p>
                            </div>
                """
                
                # Add breaking changes section
                breaking_changes = report.get("breaking_changes", [])
                if breaking_changes:
                    compatibility_html += """
                            <div style="margin: 15px 0;">
                                <h5 style="color: #dc3545; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>⚠️</span>
                                    <span>Breaking Changes</span>
                                    <span style="background: #dc3545; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 0.7em; font-weight: bold;">""" + str(len(breaking_changes)) + """</span>
                                </h5>
                                <ul style="margin: 0; padding-left: 20px; background: rgba(220,53,69,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #dc3545;">
                    """
                    
                    # Show first 5 breaking changes
                    for change in breaking_changes[:5]:
                        resource = change.get("resource", "Unknown")
                        attribute = change.get("attribute", "")
                        description = change.get("description", "")
                        
                        change_text = f"{resource}"
                        if attribute:
                            change_text += f".{attribute}"
                        
                        compatibility_html += f"""
                                <li style="margin: 8px 0;">
                                    <strong style="font-family: 'Monaco', 'Menlo', monospace; color: #495057; background: rgba(255,255,255,0.8); padding: 2px 4px; border-radius: 3px;">{change_text}</strong>
                                    <br><span style="color: #6c757d; font-size: 0.9em; margin-left: 5px;">{description}</span>
                                </li>
                        """
                    
                    # Show count if there are more changes
                    if len(breaking_changes) > 5:
                        compatibility_html += f"""
                                <li style="color: #6c757d; font-style: italic; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(220,53,69,0.2);">
                                    <strong>... and {len(breaking_changes) - 5} more breaking changes</strong>
                                    <br><span style="font-size: 0.8em;">Click to expand this section for full details</span>
                                </li>
                        """
                    
                    compatibility_html += """
                                </ul>
                            </div>
                    """
                
                # Add changelog data section
                changelog_data = report.get("changelog_data")
                if changelog_data and changelog_data.get("breaking_changes"):
                    compatibility_html += """
                            <div style="margin: 15px 0;">
                                <h5 style="color: #6f42c1; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>📜</span>
                                    <span>Official CHANGELOG</span>
                                </h5>
                                <div style="background: rgba(111,66,193,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #6f42c1;">
                    """
                    
                    for change in changelog_data.get("breaking_changes", [])[:3]:
                        compatibility_html += f"""
                                <div style="margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.8); border-radius: 3px;">
                                    <strong style="color: #495057;">{change.get("version", "")}</strong>
                                    <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 0.9em;">{change.get("description", "")}</p>
                                </div>
                        """
                    
                    upgrade_url = changelog_data.get("upgrade_guide_url")
                    if upgrade_url:
                        compatibility_html += f"""
                                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(111,66,193,0.2);">
                                    <a href="{upgrade_url}" target="_blank" style="color: #6f42c1; text-decoration: none; font-weight: 500;">
                                        📖 View Full Upgrade Guide →
                                    </a>
                                </div>
                        """
                    
                    compatibility_html += """
                                </div>
                            </div>
                    """
                
                # Add recommendations section
                recommendations = report.get("recommendations", [])
                if recommendations:
                    compatibility_html += """
                            <div style="margin: 15px 0;">
                                <h5 style="color: #007bff; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>💡</span>
                                    <span>Recommendations</span>
                                </h5>
                                <ul style="margin: 0; padding-left: 20px; background: rgba(0,123,255,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #007bff;">
                    """
                    
                    for recommendation in recommendations:
                        compatibility_html += f"""
                                <li style="margin: 8px 0; color: #495057;">{recommendation}</li>
                        """
                    
                    compatibility_html += """
                                </ul>
                            </div>
                    """
                
                compatibility_html += """
                        </div>
                    </div>
                </div>
                """
            
            compatibility_html += """
                </div>
            </div>
            """
            
            return compatibility_html
            
        except Exception as e:
            logger.error(f"Failed to generate provider compatibility HTML: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
                <h2 style="color: #721c24;">🔧 Provider Schema Compatibility Analysis</h2>
                <p><strong>Error:</strong> Failed to generate provider compatibility report: {str(e)}</p>
            </div>
            """

    def _generate_module_compatibility_html(self, inventory: Dict[str, Any]) -> str:
        """Generate HTML section for module compatibility analysis."""
        try:
            # Check if module compatibility data exists
            module_compatibility = inventory.get("module_compatibility")
            if not module_compatibility:
                return ""
            
            # Check if there's an error in compatibility analysis
            if "error" in module_compatibility:
                return f"""
                <div style="margin: 20px 0; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                    <h2 style="color: #856404;">📦 Module Compatibility Analysis</h2>
                    <p><strong>Note:</strong> Module compatibility analysis encountered an issue: {module_compatibility['error']}</p>
                </div>
                """
            
            # Get compatibility reports
            reports = module_compatibility.get("reports", [])
            if not reports:
                return ""
            
            total_analyzed = module_compatibility.get("total_modules_analyzed", 0)
            safe_upgrades = module_compatibility.get("safe_upgrades", 0)
            breaking_changes = module_compatibility.get("breaking_changes", 0)
            
            # Generate module compatibility section HTML
            compatibility_html = f"""
            <div class="compatibility-section" style="margin-top: 30px;">
                <div class="compatibility-header" onclick="toggleModuleCompatibilitySection()">
                    <h2 style="color: #28a745; margin: 0;">📦 Module Compatibility Analysis</h2>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 0.9rem; color: #6c757d;">{total_analyzed} module(s) analyzed</span>
                        <span style="font-size: 0.8rem; color: #28a745;">✅ {safe_upgrades} safe</span>
                        <span style="font-size: 0.8rem; color: #dc3545;">⚠️ {breaking_changes} breaking</span>
                        <span class="expand-icon" id="module-compatibility-icon" style="font-size: 1.2rem; color: #28a745; transition: transform 0.3s ease;">▼</span>
                    </div>
                </div>
                
                <div class="compatibility-content" id="module-compatibility-content">
                    <p style="color: #6c757d; font-style: italic; margin-bottom: 20px;">
                        This section analyzes Terraform module compatibility between your current versions and the latest available versions. 
                        It identifies breaking changes in module inputs, outputs, and dependencies that may require code updates.
                    </p>
            """
            
            # Process each module compatibility report
            for i, report in enumerate(reports):
                module_name = report.get("module_name", "Unknown")
                current_version = report.get("current_version", "Unknown")
                latest_version = report.get("latest_version", "Unknown")
                compatibility_level = report.get("compatibility_level", "unknown")
                upgrade_safe = report.get("upgrade_safe", False)
                summary = report.get("summary", "No summary available")
                
                # Create unique ID for this module report
                module_id = f"module-{module_name.replace('/', '-').replace(' ', '-').lower()}-{i}"
                
                # Determine styling based on compatibility
                if upgrade_safe:
                    border_color = "#28a745"
                    bg_color = "#d4edda"
                    status_icon = "✅"
                    status_text = "Safe Upgrade"
                else:
                    border_color = "#dc3545"
                    bg_color = "#f8d7da"
                    status_icon = "⚠️"
                    status_text = "Breaking Changes"
                
                compatibility_html += f"""
                <div class="provider-compatibility-section" style="border-color: {border_color};">
                    <div class="provider-compatibility-header" style="background-color: {bg_color};" onclick="toggleModuleCompatibility('{module_id}')">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.2rem;">{status_icon}</span>
                            <h4 style="margin: 0; color: #495057;">{module_name}</h4>
                            <div style="font-family: monospace; font-size: 0.9em;">
                                <span style="background: rgba(255,255,255,0.8); padding: 2px 6px; border-radius: 3px;">{current_version}</span>
                                <span style="margin: 0 8px; color: #6c757d;">→</span>
                                <span style="background: rgba(255,255,255,0.8); padding: 2px 6px; border-radius: 3px;">{latest_version}</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="padding: 2px 8px; background: {border_color}; color: white; border-radius: 12px; font-size: 0.8em; text-transform: uppercase; font-weight: 600;">{status_text}</span>
                            <span class="expand-icon" id="{module_id}-icon" style="font-size: 1rem; color: {border_color}; transition: transform 0.3s ease;">▼</span>
                        </div>
                    </div>
                    
                    <div class="provider-compatibility-content" id="{module_id}-content">
                        <div style="padding: 15px;">
                            <div style="margin-bottom: 15px; padding: 10px; background: rgba(0,0,0,0.02); border-radius: 5px; border-left: 3px solid {border_color};">
                                <p style="margin: 0; color: #495057; font-weight: 500;">{summary}</p>
                            </div>
                """
                
                # Add breaking changes section
                breaking_changes = report.get("breaking_changes", [])
                if breaking_changes:
                    compatibility_html += f"""
                            <div style="margin: 15px 0;">
                                <h5 style="color: #dc3545; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>⚠️</span>
                                    <span>Breaking Changes</span>
                                    <span style="background: #dc3545; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 0.7em; font-weight: bold;">{len(breaking_changes)}</span>
                                </h5>
                                <ul style="margin: 0; padding-left: 20px; background: rgba(220,53,69,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #dc3545;">
                    """
                    
                    for change in breaking_changes:
                        category = change.get("category", "unknown")
                        message = change.get("message", "")
                        old_value = change.get("old_value", "")
                        new_value = change.get("new_value", "")
                        recommendation = change.get("recommendation", "")
                        
                        compatibility_html += f"""
                                <li style="margin: 8px 0;">
                                    <strong style="color: #495057; text-transform: capitalize;">{category}:</strong> {message}
                                    <br><span style="color: #6c757d; font-size: 0.9em; margin-left: 5px;">
                                        {old_value} → {new_value}
                                    </span>
                                    {f'<br><span style="color: #007bff; font-size: 0.9em; margin-left: 5px;"><strong>Recommendation:</strong> {recommendation}</span>' if recommendation else ''}
                                </li>
                        """
                    
                    compatibility_html += """
                                </ul>
                            </div>
                    """
                
                # Add warnings section
                warnings = report.get("warnings", [])
                if warnings:
                    compatibility_html += f"""
                            <div style="margin: 15px 0;">
                                <h5 style="color: #ffc107; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>⚠️</span>
                                    <span>Warnings</span>
                                    <span style="background: #ffc107; color: #856404; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 0.7em; font-weight: bold;">{len(warnings)}</span>
                                </h5>
                                <ul style="margin: 0; padding-left: 20px; background: rgba(255,193,7,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #ffc107;">
                    """
                    
                    for warning in warnings:
                        category = warning.get("category", "unknown")
                        message = warning.get("message", "")
                        old_value = warning.get("old_value", "")
                        new_value = warning.get("new_value", "")
                        recommendation = warning.get("recommendation", "")
                        
                        compatibility_html += f"""
                                <li style="margin: 8px 0;">
                                    <strong style="color: #495057; text-transform: capitalize;">{category}:</strong> {message}
                                    <br><span style="color: #6c757d; font-size: 0.9em; margin-left: 5px;">
                                        {old_value} → {new_value}
                                    </span>
                                    {f'<br><span style="color: #007bff; font-size: 0.9em; margin-left: 5px;"><strong>Recommendation:</strong> {recommendation}</span>' if recommendation else ''}
                                </li>
                        """
                    
                    compatibility_html += """
                                </ul>
                            </div>
                    """
                
                # Add changelog data section
                changelog_data = report.get("changelog_data")
                if changelog_data and changelog_data.get("breaking_changes"):
                    compatibility_html += """
                            <div style="margin: 15px 0;">
                                <h5 style="color: #6f42c1; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>📜</span>
                                    <span>Official CHANGELOG</span>
                                </h5>
                                <div style="background: rgba(111,66,193,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #6f42c1;">
                    """
                    
                    for change in changelog_data.get("breaking_changes", [])[:3]:
                        compatibility_html += f"""
                                <div style="margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.8); border-radius: 3px;">
                                    <strong style="color: #495057;">{change.get("version", "")}</strong>
                                    <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 0.9em;">{change.get("description", "")}</p>
                                </div>
                        """
                    
                    upgrade_url = changelog_data.get("upgrade_guide_url")
                    if upgrade_url:
                        compatibility_html += f"""
                                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(111,66,193,0.2);">
                                    <a href="{upgrade_url}" target="_blank" style="color: #6f42c1; text-decoration: none; font-weight: 500;">
                                        📖 View Full Upgrade Guide →
                                    </a>
                                </div>
                        """
                    
                    compatibility_html += """
                                </div>
                            </div>
                    """
                
                # Add recommendations section
                recommendations = report.get("recommendations", [])
                if recommendations:
                    compatibility_html += """
                            <div style="margin: 15px 0;">
                                <h5 style="color: #007bff; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;">
                                    <span>💡</span>
                                    <span>Recommendations</span>
                                </h5>
                                <ul style="margin: 0; padding-left: 20px; background: rgba(0,123,255,0.1); padding: 15px; border-radius: 5px; border-left: 3px solid #007bff;">
                    """
                    
                    for recommendation in recommendations:
                        if recommendation:  # Skip empty recommendations
                            compatibility_html += f"""
                                <li style="margin: 8px 0; color: #495057;">{recommendation}</li>
                            """
                    
                    compatibility_html += """
                                </ul>
                            </div>
                    """
                
                compatibility_html += """
                        </div>
                    </div>
                </div>
                """
            
            compatibility_html += """
                </div>
            </div>
            """
            
            return compatibility_html
            
        except Exception as e:
            logger.error(f"Failed to generate module compatibility HTML: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
                <h2 style="color: #721c24;">📦 Module Compatibility Analysis</h2>
                <p><strong>Error:</strong> Failed to generate module compatibility report: {str(e)}</p>
            </div>
            """
