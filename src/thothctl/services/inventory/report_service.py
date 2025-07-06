"""Report generation service for inventory management."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pdfkit
from json2html import json2html
from rich import box
from rich.align import Align
from rich.console import Console
from rich.style import Style
from rich.table import Table


logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating inventory reports."""

    def __init__(self, reports_directory: str = "Reports"):
        """Initialize report service."""
        self.reports_dir = Path(reports_directory)
        self.reports_dir.mkdir(exist_ok=True, parents=True)
        self.console = Console()

    def _create_report_path(self, report_name: str, extension: str, reports_directory: Optional[str] = None) -> Path:
        """Create report file path with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if reports_directory:
            reports_dir = Path(reports_directory)
            reports_dir.mkdir(exist_ok=True, parents=True)
        else:
            reports_dir = self.reports_dir
            
        return reports_dir / f"{report_name}_{timestamp}.{extension}"

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
                <title>Infrastructure Inventory Report</title>
                <style>
                    :root {{
                        --primary-color: #2563eb;
                        --secondary-color: #1e40af;
                        --success-color: #10b981;
                        --warning-color: #f59e0b;
                        --danger-color: #ef4444;
                        --info-color: #06b6d4;
                        --light-bg: #f8fafc;
                        --card-bg: #ffffff;
                        --text-primary: #1e293b;
                        --text-secondary: #64748b;
                        --border-color: #e2e8f0;
                        --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                    }}
                    
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    
                    body {{
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        color: var(--text-primary);
                        line-height: 1.6;
                    }}
                    
                    .container {{
                        max-width: 1400px;
                        margin: 0 auto;
                        padding: 2rem;
                    }}
                    
                    .header {{
                        background: var(--card-bg);
                        border-radius: 16px;
                        padding: 2rem;
                        margin-bottom: 2rem;
                        box-shadow: var(--shadow-lg);
                        text-align: center;
                        position: relative;
                        overflow: hidden;
                    }}
                    
                    .header::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 4px;
                        background: linear-gradient(90deg, var(--primary-color), var(--info-color), var(--success-color));
                    }}
                    
                    .header h1 {{
                        font-size: 2.5rem;
                        font-weight: 700;
                        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                        margin-bottom: 1rem;
                    }}
                    
                    .project-info {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 1rem;
                        margin-top: 1.5rem;
                    }}
                    
                    .info-item {{
                        background: var(--light-bg);
                        padding: 1rem;
                        border-radius: 8px;
                        border-left: 4px solid var(--primary-color);
                    }}
                    
                    .info-label {{
                        font-size: 0.875rem;
                        font-weight: 600;
                        color: var(--text-secondary);
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                    }}
                    
                    .info-value {{
                        font-size: 1.125rem;
                        font-weight: 600;
                        color: var(--text-primary);
                        margin-top: 0.25rem;
                    }}
                    
                    .summary-section {{
                        background: var(--card-bg);
                        border-radius: 16px;
                        padding: 2rem;
                        margin-bottom: 2rem;
                        box-shadow: var(--shadow-lg);
                    }}
                    
                    .summary-title {{
                        font-size: 1.875rem;
                        font-weight: 700;
                        color: var(--text-primary);
                        margin-bottom: 1.5rem;
                        text-align: center;
                    }}
                    
                    .summary-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 1.5rem;
                    }}
                    
                    .summary-card {{
                        background: var(--light-bg);
                        border-radius: 12px;
                        padding: 1.5rem;
                        text-align: center;
                        border: 2px solid transparent;
                        transition: all 0.3s ease;
                    }}
                    
                    .summary-card:hover {{
                        transform: translateY(-2px);
                        box-shadow: var(--shadow);
                    }}
                    
                    .summary-card.updated {{
                        border-color: var(--success-color);
                        background: linear-gradient(135deg, #ecfdf5, #f0fdf4);
                    }}
                    
                    .summary-card.outdated {{
                        border-color: var(--danger-color);
                        background: linear-gradient(135deg, #fef2f2, #fef7f7);
                    }}
                    
                    .summary-card.unknown {{
                        border-color: var(--warning-color);
                        background: linear-gradient(135deg, #fffbeb, #fefce8);
                    }}
                    
                    .summary-card.local {{
                        border-color: var(--info-color);
                        background: linear-gradient(135deg, #f0f9ff, #f7fafc);
                    }}
                    
                    .summary-number {{
                        font-size: 2.5rem;
                        font-weight: 800;
                        margin-bottom: 0.5rem;
                    }}
                    
                    .summary-label {{
                        font-size: 0.875rem;
                        font-weight: 600;
                        color: var(--text-secondary);
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                    }}
                    
                    .stack-section {{
                        background: var(--card-bg);
                        border-radius: 16px;
                        margin-bottom: 2rem;
                        box-shadow: var(--shadow-lg);
                        overflow: hidden;
                    }}
                    
                    .stack-header {{
                        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
                        color: white;
                        padding: 1.5rem 2rem;
                        font-size: 1.5rem;
                        font-weight: 700;
                    }}
                    
                    .stack-content {{
                        padding: 2rem;
                    }}
                    
                    .table-section {{
                        margin-bottom: 2rem;
                    }}
                    
                    .table-title {{
                        font-size: 1.25rem;
                        font-weight: 700;
                        color: var(--text-primary);
                        margin-bottom: 1rem;
                        display: flex;
                        align-items: center;
                        gap: 0.5rem;
                    }}
                    
                    .table-title::before {{
                        content: '';
                        width: 4px;
                        height: 1.5rem;
                        background: var(--primary-color);
                        border-radius: 2px;
                    }}
                    
                    .table-container {{
                        overflow-x: auto;
                        border-radius: 12px;
                        box-shadow: var(--shadow);
                        background: var(--card-bg);
                    }}
                    
                    .components-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 0.875rem;
                    }}
                    
                    .components-table th {{
                        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
                        color: white;
                        padding: 1rem 0.75rem;
                        text-align: left;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                        font-size: 0.75rem;
                        border: none;
                    }}
                    
                    .components-table td {{
                        padding: 1rem 0.75rem;
                        border-bottom: 1px solid var(--border-color);
                        vertical-align: top;
                        word-wrap: break-word;
                        max-width: 200px;
                    }}
                    
                    .components-table tr:hover {{
                        background: var(--light-bg);
                    }}
                    
                    .components-table tr:last-child td {{
                        border-bottom: none;
                    }}
                    
                    .status-badge {{
                        display: inline-flex;
                        align-items: center;
                        padding: 0.25rem 0.75rem;
                        border-radius: 9999px;
                        font-size: 0.75rem;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                    }}
                    
                    .status-updated {{
                        background: #dcfce7;
                        color: #166534;
                        border: 1px solid #bbf7d0;
                    }}
                    
                    .status-outdated {{
                        background: #fee2e2;
                        color: #991b1b;
                        border: 1px solid #fecaca;
                    }}
                    
                    .status-unknown {{
                        background: #fef3c7;
                        color: #92400e;
                        border: 1px solid #fde68a;
                    }}
                    
                    .version-badge {{
                        background: var(--light-bg);
                        padding: 0.25rem 0.5rem;
                        border-radius: 6px;
                        font-family: 'Monaco', 'Menlo', monospace;
                        font-size: 0.75rem;
                        border: 1px solid var(--border-color);
                    }}
                    
                    .source-link {{
                        color: var(--primary-color);
                        text-decoration: none;
                        font-weight: 500;
                        word-break: break-all;
                    }}
                    
                    .source-link:hover {{
                        text-decoration: underline;
                    }}
                    
                    .module-path {{
                        font-family: 'Monaco', 'Menlo', monospace;
                        font-size: 0.75rem;
                        background: var(--light-bg);
                        padding: 0.25rem 0.5rem;
                        border-radius: 4px;
                        border: 1px solid var(--border-color);
                        word-break: break-all;
                    }}
                    
                    .empty-state {{
                        text-align: center;
                        padding: 3rem;
                        color: var(--text-secondary);
                    }}
                    
                    .empty-state-icon {{
                        font-size: 3rem;
                        margin-bottom: 1rem;
                        opacity: 0.5;
                    }}
                    
                    @media (max-width: 768px) {{
                        .container {{
                            padding: 1rem;
                        }}
                        
                        .header h1 {{
                            font-size: 2rem;
                        }}
                        
                        .project-info {{
                            grid-template-columns: 1fr;
                        }}
                        
                        .summary-grid {{
                            grid-template-columns: repeat(2, 1fr);
                        }}
                        
                        .components-table {{
                            font-size: 0.75rem;
                        }}
                        
                        .components-table th,
                        .components-table td {{
                            padding: 0.5rem 0.25rem;
                        }}
                    }}
                    
                    @media print {{
                        body {{
                            background: white;
                        }}
                        
                        .container {{
                            max-width: none;
                            padding: 1rem;
                        }}
                        
                        .stack-section,
                        .summary-section,
                        .header {{
                            box-shadow: none;
                            border: 1px solid var(--border-color);
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🏗️ Infrastructure Inventory Report</h1>
                        <div class="project-info">
                            <div class="info-item">
                                <div class="info-label">Project Name</div>
                                <div class="info-value">{project_name}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Project Type</div>
                                <div class="info-value">{project_type}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Generated</div>
                                <div class="info-value">{timestamp}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="summary-section">
                        <h2 class="summary-title">📊 Summary Overview</h2>
                        {summary_table}
                    </div>
                    
                    {compatibility_section}
                    
                    <div class="stacks-container">
                        {content}
                    </div>
                </div>
            </body>
            </html>
            """

            # Generate summary statistics
            summary_html = self._generate_summary_html(inventory)
            
            # Generate schema compatibility section if available
            compatibility_html = self._generate_compatibility_html(inventory)
            
            # Generate custom HTML for components and providers
            components_html = ""
            for component_group in inventory.get("components", []):
                stack = component_group.get("stack", "Unknown")
                components_html += f"""
                <div class="stack-section">
                    <div class="stack-header">
                        📁 Stack: {stack}
                    </div>
                    <div class="stack-content">
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
                                            <th>Current Version</th>
                                            <th>Source</th>
                                            <th>Latest Version</th>
                                            <th>SourceUrl</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    """
                    
                    for component in components:
                        source = component.get("source", ["Unknown"])[0] if component.get("source") else "Unknown"
                        version = component.get("version", ["Unknown"])[0] if component.get("version") else "Unknown"
                        latest_version = component.get("latest_version", "Null")
                        source_url = component.get("source_url", "Null")
                        status = component.get("status", "Unknown")
                        
                        # Format version badges
                        version_badge = f'<span class="version-badge">{version}</span>' if version != "local" else f'<span class="version-badge" style="background: #e0f2fe; color: #0277bd;">{version}</span>'
                        latest_version_badge = f'<span class="version-badge">{latest_version}</span>' if latest_version != "Null" else '<span style="color: #9ca3af;">—</span>'
                        
                        # Format source URL
                        source_url_display = f'<a href="{source_url}" class="source-link" target="_blank">{source_url[:50]}{"..." if len(source_url) > 50 else ""}</a>' if source_url != "Null" and source_url.startswith("http") else (source_url if source_url != "Null" else '<span style="color: #9ca3af;">—</span>')
                        
                        # Format status badge
                        status_display = f'<span class="status-badge status-{status.lower()}">{status}</span>' if status != "Null" else '<span style="color: #9ca3af;">—</span>'
                        
                        components_html += f"""
                        <tr>
                            <td><strong>{component.get("type", "Unknown")}</strong></td>
                            <td><strong>{component.get("name", "Unknown")}</strong></td>
                            <td>{version_badge}</td>
                            <td><span class="module-path">{source}</span></td>
                            <td>{latest_version_badge}</td>
                            <td>{source_url_display}</td>
                            <td>{status_display}</td>
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
                    
                    # Get the stack name for this component group
                    stack_name = component_group.get("stack", "Unknown")
                    
                    for provider in providers:
                        # Use the stack name if the module is empty or "Root"
                        module_name = provider.get("module", "")
                        if not module_name or module_name == "Root":
                            module_name = stack_name
                        
                        # Get provider version information
                        latest_version = provider.get("latest_version", "Null")
                        status = provider.get("status", "Unknown")
                        
                        # Format version badges
                        version_badge = f'<span class="version-badge">{provider.get("version", "Unknown")}</span>'
                        latest_version_badge = f'<span class="version-badge">{latest_version}</span>' if latest_version != "Null" else '<span style="color: #9ca3af;">—</span>'
                        
                        # Format status badge
                        status_display = f'<span class="status-badge status-{status.lower()}">{status}</span>' if status != "Null" and status != "Unknown" else '<span style="color: #9ca3af;">—</span>'
                            
                        components_html += f"""
                        <tr>
                            <td><strong>{provider.get("name", "Unknown")}</strong></td>
                            <td>{version_badge}</td>
                            <td><span class="module-path">{provider.get("source", "Unknown")}</span></td>
                            <td>{latest_version_badge}</td>
                            <td>{status_display}</td>
                            <td><span class="module-path">{module_name}</span></td>
                            <td><em>{provider.get("component", "")}</em></td>
                        </tr>
                        """
                    
                    components_html += """
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    """
                
                components_html += """
                    </div>
                </div>
                """

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

    def create_pdf_report(
        self, html_path: Path, report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create PDF report from HTML file with custom options."""
        try:
            pdf_path = self._create_report_path(report_name, "pdf", reports_directory)

            options = {
                "page-size": "A4",
                "margin-top": "20mm",
                "margin-right": "20mm",
                "margin-bottom": "20mm",
                "margin-left": "20mm",
                "encoding": "UTF-8",
                "no-outline": None,
                "enable-local-file-access": None,
            }

            pdfkit.from_file(str(html_path), str(pdf_path), options=options)
            logger.info(f"PDF report created at: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Failed to create PDF report: {str(e)}")
            raise

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
                    
                    # Add both tables to the main table
                    grid = Table.grid()
                    grid.add_row(components_table)
                    grid.add_row(providers_table)
                    
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
        """Generate HTML section for schema compatibility analysis."""
        try:
            # Check if schema compatibility data exists
            compatibility_data = inventory.get("schema_compatibility")
            if not compatibility_data:
                return ""
            
            # Check if there's an error in compatibility analysis
            if "error" in compatibility_data:
                return f"""
                <div style="margin: 20px 0; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                    <h2 style="color: #856404;">🔍 Provider Schema Compatibility Analysis</h2>
                    <p><strong>Note:</strong> Schema compatibility analysis encountered an issue: {compatibility_data['error']}</p>
                </div>
                """
            
            # Get compatibility reports
            reports = compatibility_data.get("reports", [])
            if not reports:
                return ""
            
            # Generate compatibility section HTML
            compatibility_html = """
            <div style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 5px;">
                <h2 style="color: #007bff;">🔍 Provider Schema Compatibility Analysis</h2>
                <p style="color: #6c757d; font-style: italic;">
                    This section analyzes provider schema compatibility between your current versions and the latest available versions. 
                    It identifies potential breaking changes, deprecations, and new features that may affect your infrastructure code.
                </p>
            """
            
            # Process each compatibility report
            for report in reports:
                provider_name = report.get("provider_name", "Unknown")
                current_version = report.get("current_version", "Unknown")
                latest_version = report.get("latest_version", "Unknown")
                compatibility_level = report.get("compatibility_level", "unknown")
                summary = report.get("summary", "No summary available")
                
                # Determine border color based on compatibility level
                if compatibility_level == "compatible":
                    border_color = "#28a745"
                    bg_color = "#d4edda"
                elif compatibility_level == "minor_issues":
                    border_color = "#ffc107"
                    bg_color = "#fff3cd"
                elif compatibility_level == "breaking_changes":
                    border_color = "#dc3545"
                    bg_color = "#f8d7da"
                else:
                    border_color = "#6c757d"
                    bg_color = "#e9ecef"
                
                compatibility_html += f"""
                <div style="margin: 15px 0; padding: 15px; background-color: {bg_color}; border-left: 4px solid {border_color}; border-radius: 5px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0; color: #495057;">{provider_name}</h4>
                        <div style="font-family: monospace; font-size: 0.9em;">
                            <span style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px;">{current_version}</span>
                            <span style="margin: 0 8px; color: #6c757d;">→</span>
                            <span style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px;">{latest_version}</span>
                            <span style="margin-left: 10px; padding: 2px 8px; background: {border_color}; color: white; border-radius: 12px; font-size: 0.8em; text-transform: uppercase;">{compatibility_level.replace('_', ' ')}</span>
                        </div>
                    </div>
                    
                    <div style="margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 3px;">
                        <p style="margin: 0; color: #495057;">{summary}</p>
                    </div>
                """
                
                # Add breaking changes section
                breaking_changes = report.get("breaking_changes", [])
                if breaking_changes:
                    compatibility_html += """
                    <div style="margin: 10px 0;">
                        <h5 style="color: #dc3545; margin-bottom: 8px;">⚠️ Breaking Changes</h5>
                        <ul style="margin: 0; padding-left: 20px; background: rgba(220,53,69,0.1); padding: 10px; border-radius: 3px;">
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
                        <li style="margin: 5px 0;">
                            <strong style="font-family: monospace; color: #495057;">{change_text}</strong>
                            <br><span style="color: #6c757d; font-size: 0.9em;">{description}</span>
                        </li>
                        """
                    
                    # Show count if there are more changes
                    if len(breaking_changes) > 5:
                        compatibility_html += f"""
                        <li style="color: #6c757d; font-style: italic;">... and {len(breaking_changes) - 5} more breaking changes</li>
                        """
                    
                    compatibility_html += """
                        </ul>
                    </div>
                    """
                
                # Add recommendations section
                recommendations = report.get("recommendations", [])
                if recommendations:
                    compatibility_html += """
                    <div style="margin: 10px 0;">
                        <h5 style="color: #007bff; margin-bottom: 8px;">💡 Recommendations</h5>
                        <ul style="margin: 0; padding-left: 20px; background: rgba(0,123,255,0.1); padding: 10px; border-radius: 3px;">
                    """
                    
                    for recommendation in recommendations:
                        compatibility_html += f"""
                        <li style="margin: 5px 0; color: #495057;">{recommendation}</li>
                        """
                    
                    compatibility_html += """
                        </ul>
                    </div>
                    """
                
                compatibility_html += """
                </div>
                """
            
            compatibility_html += """
            </div>
            """
            
            return compatibility_html
            
        except Exception as e:
            logger.error(f"Failed to generate compatibility HTML: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
                <h2 style="color: #721c24;">🔍 Provider Schema Compatibility Analysis</h2>
                <p><strong>Error:</strong> Failed to generate compatibility report: {str(e)}</p>
            </div>
            """
