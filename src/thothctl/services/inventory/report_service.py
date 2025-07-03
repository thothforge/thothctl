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
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        background-color: #f5f5f5;
                    }}
                    .inventory-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                        background-color: white;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                    }}
                    .inventory-table th, .inventory-table td {{
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }}
                    .inventory-table th {{
                        background-color: #4CAF50;
                        color: white;
                    }}
                    .inventory-table tr:nth-child(even) {{
                        background-color: #f9f9f9;
                    }}
                    .status-updated {{
                        color: green;
                        font-weight: bold;
                    }}
                    .status-outdated {{
                        color: red;
                        font-weight: bold;
                    }}
                    .status-unknown {{
                        color: orange;
                        font-weight: bold;
                    }}
                    .components-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 10px;
                        margin-bottom: 30px;
                        background-color: white;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                        table-layout: fixed;
                    }}
                    .components-table th, .components-table td {{
                        border: 1px solid #ddd;
                        padding: 8px;
                        text-align: left;
                        word-wrap: break-word;
                        overflow-wrap: break-word;
                    }}
                    .components-table th {{
                        background-color: #2196F3;
                        color: white;
                    }}
                    .components-table tr:nth-child(even) {{
                        background-color: #f9f9f9;
                    }}
                    /* Column width adjustments */
                    .components-table th:nth-child(1), .components-table td:nth-child(1) {{
                        width: 15%;  /* Name column */
                    }}
                    .components-table th:nth-child(2), .components-table td:nth-child(2) {{
                        width: 10%;  /* Version column */
                    }}
                    .components-table th:nth-child(3), .components-table td:nth-child(3) {{
                        width: 25%;  /* Source column */
                    }}
                    .components-table th:nth-child(4), .components-table td:nth-child(4) {{
                        width: 20%;  /* Module column */
                    }}
                    .components-table th:nth-child(5), .components-table td:nth-child(5) {{
                        width: 30%;  /* Component column */
                    }}
                    /* Module column specific styling */
                    .module-cell {{
                        font-family: monospace;
                        white-space: normal;
                        word-break: break-word;
                        max-width: 200px;
                    }}
                    /* Component column specific styling */
                    .component-cell {{
                        font-family: monospace;
                        white-space: normal;
                        word-break: break-word;
                    }}
                    h1 {{
                        color: #333;
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    h2 {{
                        color: #333;
                        margin-top: 30px;
                        margin-bottom: 15px;
                        border-bottom: 2px solid #4CAF50;
                        padding-bottom: 5px;
                    }}
                    h3 {{
                        color: #2196F3;
                        margin-top: 20px;
                        margin-bottom: 10px;
                    }}
                    .project-info {{
                        background-color: #e7f3fe;
                        border-left: 6px solid #2196F3;
                        padding: 10px;
                        margin-bottom: 20px;
                    }}
                    .summary-table {{
                        width: 50%;
                        margin: 20px auto;
                        border-collapse: collapse;
                        background-color: white;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                        border-radius: 8px;
                        overflow: hidden;
                    }}
                    .summary-table th {{
                        background-color: #2196F3;
                        color: white;
                        padding: 12px;
                        text-align: left;
                        font-weight: bold;
                    }}
                    .summary-table td {{
                        padding: 12px;
                        border-bottom: 1px solid #ddd;
                    }}
                    .summary-table tr:last-child td {{
                        border-bottom: none;
                    }}
                    .summary-table .metric {{
                        font-weight: bold;
                        color: #333;
                        width: 60%;
                    }}
                    .summary-table .value {{
                        text-align: right;
                        font-weight: bold;
                    }}
                    .value-updated {{
                        color: #4CAF50;
                    }}
                    .value-outdated {{
                        color: #f44336;
                    }}
                    .value-unknown {{
                        color: #ff9800;
                    }}
                    .value-local {{
                        color: #2196F3;
                    }}
                    .summary-container {{
                        text-align: center;
                        margin: 30px 0;
                    }}
                </style>
            </head>
            <body>
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
            </body>
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
                                <th>Version</th>
                                <th>Source</th>
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
                        
                        components_html += f"""
                        <tr>
                            <td>{component.get("type", "Unknown")}</td>
                            <td>{component.get("name", "Unknown")}</td>
                            <td>{version}</td>
                            <td>{source}</td>
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
                    components_html += """
                    <h3>Providers</h3>
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
                    
                    # Get the stack name for this component group
                    stack_name = component_group.get("stack", "Unknown")
                    
                    for provider in providers:
                        # Use the stack name if the module is empty or "Root"
                        module_name = provider.get("module", "")
                        if not module_name or module_name == "Root":
                            module_name = stack_name
                            
                        components_html += f"""
                        <tr>
                            <td>{provider.get("name", "Unknown")}</td>
                            <td>{provider.get("version", "Unknown")}</td>
                            <td>{provider.get("source", "Unknown")}</td>
                            <td class="module-cell">{module_name}</td>
                            <td class="component-cell">{provider.get("component", "")}</td>
                        </tr>
                        """
                    
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
                    
                    # Get the stack name for this component group
                    stack_name = component_group.get("stack", "Unknown")
                    
                    for provider in providers:
                        # Use the stack name if the module is empty or "Root"
                        module_name = provider.get("module", "")
                        if not module_name or module_name == "Root":
                            module_name = stack_name
                            
                        providers_table.add_row(
                            provider.get("name", "Unknown"),
                            provider.get("version", "Unknown"),
                            provider.get("source", "Unknown"),
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
