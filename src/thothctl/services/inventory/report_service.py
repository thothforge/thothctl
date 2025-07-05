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
            <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
                                <style>
                    :root {
                        --primary-color: #3b82f6;
                        --secondary-color: #1e40af;
                        --success-color: #10b981;
                        --warning-color: #f59e0b;
                        --danger-color: #ef4444;
                        --gray-50: #f9fafb;
                        --gray-100: #f3f4f6;
                        --gray-200: #e5e7eb;
                        --gray-600: #4b5563;
                        --gray-700: #374151;
                        --gray-800: #1f2937;
                        --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
                        --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
                    }
                    
                    body {{
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        margin: 0;
                        padding: 2rem;
                        background: linear-gradient(135deg, var({{--gray-50}}) 0%, #ffffff 100%);
                        color: var({{--gray-800}});
                        line-height: 1.6;
                    }}
                    
                    .container {{
                        max-width: 1400px;
                        margin: 0 auto;
                    }}
                    
                    h1 {{
                        color: var({{--gray-800}});
                        text-align: center;
                        margin-bottom: 2rem;
                        font-size: 2.5rem;
                        font-weight: 700;
                        background: linear-gradient(135deg, var({{--primary-color}}), var({{--secondary-color}}));
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    
                    h2 {{
                        color: var({{--gray-700}});
                        margin-top: 3rem;
                        margin-bottom: 1.5rem;
                        font-size: 1.75rem;
                        font-weight: 600;
                        border-bottom: 3px solid var({{--primary-color}});
                        padding-bottom: 0.5rem;
                        display: flex;
                        align-items: center;
                        gap: 0.75rem;
                    }}
                    
                    h3 {{
                        color: var({{--primary-color}});
                        margin-top: 2rem;
                        margin-bottom: 1rem;
                        font-size: 1.25rem;
                        font-weight: 600;
                    }}
                    
                    .project-info {{
                        background: linear-gradient(135deg, #ffffff, var({{--gray-50}}));
                        border: 1px solid var({{--gray-200}});
                        border-left: 4px solid var({{--primary-color}});
                        border-radius: 0.75rem;
                        padding: 2rem;
                        margin-bottom: 2rem;
                        box-shadow: var({{--shadow}});
                    }}
                    
                    .project-info p {{
                        margin: 0.5rem 0;
                        font-size: 1.1rem;
                    }}
                    
                    .summary-container {{
                        text-align: center;
                        margin: 3rem 0;
                    }}
                    
                    .summary-table {{
                        width: 70%;
                        margin: 2rem auto;
                        border-collapse: collapse;
                        background: #ffffff;
                        box-shadow: var({{--shadow-lg}});
                        border-radius: 1rem;
                        overflow: hidden;
                        border: 1px solid var({{--gray-200}});
                    }}
                    
                    .summary-table th {{
                        background: linear-gradient(135deg, var({{--primary-color}}), var({{--secondary-color}}));
                        color: white;
                        padding: 1.25rem;
                        text-align: left;
                        font-weight: 600;
                        font-size: 1rem;
                    }}
                    
                    .summary-table td {{
                        padding: 1.25rem;
                        border-bottom: 1px solid var({{--gray-100}});
                        font-size: 1rem;
                    }}
                    
                    .summary-table tr:last-child td {{
                        border-bottom: none;
                    }}
                    
                    .summary-table tr:nth-child(even) {{
                        background-color: var({{--gray-50}});
                    }}
                    
                    .summary-table .metric {{
                        font-weight: 600;
                        color: var({{--gray-700}});
                        width: 60%;
                    }}
                    
                    .summary-table .value {{
                        text-align: right;
                        font-weight: 700;
                        font-size: 1.1rem;
                    }}
                    
                    .components-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin: 1.5rem 0;
                        background: #ffffff;
                        box-shadow: var({{--shadow}});
                        border-radius: 0.75rem;
                        overflow: hidden;
                        border: 1px solid var({{--gray-200}});
                    }}
                    
                    .components-table th {{
                        background: linear-gradient(135deg, var({{--gray-100}}), var({{--gray-200}}));
                        color: var({{--gray-700}});
                        padding: 1rem;
                        text-align: left;
                        font-weight: 600;
                        font-size: 0.875rem;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                        border-bottom: 2px solid var({{--gray-300}});
                    }}
                    
                    .components-table td {{
                        padding: 1rem;
                        border-bottom: 1px solid var({{--gray-100}});
                        vertical-align: top;
                        font-size: 0.9rem;
                    }}
                    
                    .components-table tbody tr:hover {{
                        background-color: var({{--gray-50}});
                        transform: scale(1.001);
                        transition: all 0.2s ease;
                    }}
                    
                    .components-table tbody tr:last-child td {{
                        border-bottom: none;
                    }}
                    
                    .status-updated {{
                        color: var({{--success-color}});
                        font-weight: 600;
                        padding: 0.25rem 0.75rem;
                        background: rgba(16, 185, 129, 0.1);
                        border-radius: 9999px;
                        font-size: 0.8rem;
                        text-transform: uppercase;
                    }}
                    
                    .status-current {{
                        color: var({{--success-color}});
                        font-weight: 600;
                        padding: 0.25rem 0.75rem;
                        background: rgba(16, 185, 129, 0.1);
                        border-radius: 9999px;
                        font-size: 0.8rem;
                        text-transform: uppercase;
                    }}
                    
                    .status-outdated {{
                        color: var({{--danger-color}});
                        font-weight: 600;
                        padding: 0.25rem 0.75rem;
                        background: rgba(239, 68, 68, 0.1);
                        border-radius: 9999px;
                        font-size: 0.8rem;
                        text-transform: uppercase;
                    }}
                    
                    .status-unknown {{
                        color: var({{--warning-color}});
                        font-weight: 600;
                        padding: 0.25rem 0.75rem;
                        background: rgba(245, 158, 11, 0.1);
                        border-radius: 9999px;
                        font-size: 0.8rem;
                        text-transform: uppercase;
                    }}
                    
                    .module-cell, .component-cell {{
                        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                        background: var({{--gray-50}});
                        padding: 0.25rem 0.5rem;
                        border-radius: 0.25rem;
                        font-size: 0.8rem;
                        color: var({{--gray-700}});
                        word-break: break-all;
                    }}
                    
                    .value-updated {{
                        color: var({{--success-color}});
                        font-weight: 600;
                    }}
                    
                    .value-outdated {{
                        color: var({{--danger-color}});
                        font-weight: 600;
                    }}
                    
                    .value-unknown {{
                        color: var({{--warning-color}});
                        font-weight: 600;
                    }}
                    
                    .value-local {{
                        color: var({{--primary-color}});
                        font-weight: 600;
                    }}
                    
                    /* Responsive Design */
                    @media (max-width: 768px) {{
                        body {{
                            padding: 1rem;
                        }}
                        
                        h1 {{
                            font-size: 2rem;
                        }}
                        
                        .summary-table {{
                            width: 95%;
                        }}
                        
                        .components-table {{
                            font-size: 0.8rem;
                        }}
                        
                        .components-table th,
                        .components-table td {{
                            padding: 0.75rem 0.5rem;
                        }}
                    }}
                    
                    /* Print Styles */
                    @media print {{
                        body {{
                            background: white;
                        }}
                        
                        .components-table,
                        .summary-table {{
                            break-inside: avoid;
                        }}
                    }}
                </style>
            </head>
            <body><div class="container">
                <h1>Infrastructure Inventory Report</h1>
                <div class="project-info">
                    <p><strong>Project Name:</strong> {project_name}</p>
                    <p><strong>Project Type:</strong> {project_type}</p>
                    <p><strong>Generated:</strong> {timestamp}</p>
                </div>
                
                <div class="summary-container">
                    <h2>Summary</h2>
                    {summary_table}
                </div>
                
                <h2>Detailed Inventory</h2>
                {content}
            </div></body>
            </html>
            """

            # Generate summary statistics
            summary_html = self._generate_summary_html(inventory)
            
            # Generate custom HTML for components and providers
            components_html = ""
            for component_group in inventory.get("components", []):
                stack = component_group.get("stack", "Unknown")
                components_html += f"<h2>Stack: {stack}</h2>"
                
                # Add components table
                components = component_group.get("components", [])
                if components:
                    components_html += """
                    <h3>Components</h3>
                    <table class="components-table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Name</th>
                                <th>Current Version</th>
                                <th>Source</th>
                                <th>Latest Version</th>
                                <th>Source URL</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                    """
                    
                    for component in components:
                        source = component.get("source", ["Unknown"])[0] if component.get("source") else "Unknown"
                        version = component.get("version", ["Unknown"])[0] if component.get("version") else "Unknown"
                        status = component.get("status", "Unknown")
                        status_class = f"status-{status.lower()}" if status != "Null" else ""
                        latest_version = component.get("latest_version", "Unknown")
                        source_url = component.get("source_url", "Unknown")
                        
                        components_html += f"""
                        <tr>
                            <td>{component.get("type", "Unknown")}</td>
                            <td>{component.get("name", "Unknown")}</td>
                            <td>{version}</td>
                            <td>{source}</td>
                            <td>{latest_version}</td>
                            <td>{source_url}</td>
                            <td class="{status_class}">{status}</td>
                        </tr>
                        """
                    
                    components_html += """
                        </tbody>
                    </table>
                    """
                
                # Add providers table if available
                providers = component_group.get("providers", [])
                if providers:
                    # Check if provider version information is available
                    has_version_info = inventory.get("provider_version_stats") is not None
                    
                    components_html += """
                    <h3>Providers</h3>
                    <table class="components-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Version</th>
                                <th>Source</th>
                                <th>Module</th>
                                <th>Component</th>"""
                    
                    if has_version_info:
                        components_html += """
                                <th>Latest Version</th>
                                <th>Status</th>"""
                    
                    components_html += """
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
                            
                        # Prepare HTML row data
                        row_html = f"""
                        <tr>
                            <td>{provider.get("name", "Unknown")}</td>
                            <td>{provider.get("version", "Unknown")}</td>
                            <td>{provider.get("source", "Unknown")}</td>
                            <td class="module-cell">{module_name}</td>
                            <td class="component-cell">{provider.get("component", "")}</td>"""
                        
                        # Add version information if available
                        if has_version_info:
                            latest_version = provider.get("latest_version", "Unknown")
                            status = provider.get("status", "unknown")
                            
                            # Style the status
                            status_class = ""
                            if status == "outdated":
                                status_class = "status-outdated"
                            elif status == "current":
                                status_class = "status-current"
                            else:
                                status_class = "status-unknown"
                            
                            row_html += f"""
                            <td>{latest_version}</td>
                            <td class="{status_class}">{status.title()}</td>"""
                        
                        row_html += """
                        </tr>
                        """
                        
                        components_html += row_html
                    
                    components_html += """
                        </tbody>
                    </table>
                    """

            # Create report file
            report_path = self._create_report_path(report_name, "html", reports_directory)

            # Write the report with proper formatting
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_template.format(
                    content=components_html,
                    summary_table=summary_html,
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
                    providers_table.add_column("Module", style="yellow", overflow="fold")
                    providers_table.add_column("Component", style="magenta", overflow="fold")
                    
                    # Check if provider version information is available
                    has_version_info = inventory.get("provider_version_stats") is not None
                    if has_version_info:
                        providers_table.add_column("Latest Version", style="yellow")
                        providers_table.add_column("Status", style="red", justify="center")
                    
                    # Get the stack name for this component group
                    stack_name = component_group.get("stack", "Unknown")
                    
                    for provider in providers:
                        # Use the stack name if the module is empty or "Root"
                        module_name = provider.get("module", "")
                        if not module_name or module_name == "Root":
                            module_name = stack_name
                            
                        # Prepare row data
                        row_data = [
                            provider.get("name", "Unknown"),
                            provider.get("version", "Unknown"),
                            provider.get("source", "Unknown"),
                            module_name,
                            provider.get("component", ""),
                        ]
                        
                        # Add version information if available
                        if has_version_info:
                            latest_version = provider.get("latest_version", "Unknown")
                            status = provider.get("status", "unknown")
                            
                            # Style the status
                            if status == "outdated":
                                status_styled = "[red]Outdated[/red]"
                            elif status == "current":
                                status_styled = "[green]Current[/green]"
                            else:
                                status_styled = "[yellow]Unknown[/yellow]"
                            
                            row_data.extend([latest_version, status_styled])
                        
                        providers_table.add_row(*row_data)
                    
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
                    elif "module" in comp_type:
                        terraform_modules += 1

            # Generate HTML table
            summary_html = f"""
            <table class="summary-table">
                <tr>
                    <td class="metric">Project Type</td>
                    <td class="value">{inventory.get("projectType", "Terraform")}</td>
                </tr>
                <tr>
                    <td class="metric">Total Components</td>
                    <td class="value">{total_components}</td>
                </tr>
                <tr>
                    <td class="metric">Updated Components</td>
                    <td class="value value-updated">{updated_components}</td>
                </tr>
                <tr>
                    <td class="metric">Outdated Components</td>
                    <td class="value value-outdated">{outdated_components}</td>
                </tr>
                <tr>
                    <td class="metric">Unknown Status</td>
                    <td class="value value-unknown">{unknown_components}</td>
                </tr>
            """
            
            # Add local modules count if any exist
            if local_components > 0:
                summary_html += f"""
                <tr>
                    <td class="metric">Local Modules</td>
                    <td class="value value-local">{local_components}</td>
                </tr>
                """
                
            # Add providers count if any exist
            if total_providers > 0:
                summary_html += f"""
                <tr>
                    <td class="metric">Providers</td>
                    <td class="value">{total_providers}</td>
                </tr>
                """
            
            # Add terragrunt stacks count for terraform-terragrunt projects
            if project_type == 'terraform-terragrunt':
                terragrunt_stacks_count = inventory.get('terragrunt_stacks_count', 0)
                summary_html += f"""
                <tr>
                    <td class="metric">Terragrunt Stacks</td>
                    <td class="value">{terragrunt_stacks_count}</td>
                </tr>
                """
            
            # Add framework-specific rows if applicable
            if 'terragrunt' in project_type and terragrunt_modules > 0:
                summary_html += f"""
                <tr>
                    <td class="metric">Terragrunt Modules</td>
                    <td class="value">{terragrunt_modules}</td>
                </tr>
                """
            
            if 'terraform' in project_type and terraform_modules > 0:
                summary_html += f"""
                <tr>
                    <td class="metric">Terraform Modules</td>
                    <td class="value">{terraform_modules}</td>
                </tr>
                """
            
            summary_html += "</table>"
            
            return summary_html

        except Exception as e:
            logger.error(f"Failed to generate summary HTML: {str(e)}")
            return f"<p>Error generating summary: {str(e)}</p>"

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
                
            providers_html += f"""
            <tr>
                <td>{provider.get('name', 'Unknown')}</td>
                <td>{provider.get('version', 'Unknown')}</td>
                <td>{provider.get('source', 'Unknown')}</td>
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
