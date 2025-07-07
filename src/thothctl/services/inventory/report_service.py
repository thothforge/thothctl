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

    def create_html_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create HTML report from inventory data using external template."""
        try:
            # Generate summary statistics
            summary_html = self._generate_summary_html(inventory)
            
            # Generate schema compatibility section if available
            compatibility_html = self._generate_compatibility_html(inventory)
            
            # Generate custom HTML for components and providers
            components_html = self._generate_components_html(inventory)
            
            # Prepare template context
            context = {
                'content': components_html,
                'summary_table': summary_html,
                'compatibility_section': compatibility_html,
                'project_name': inventory.get("projectName", inventory.get("project_name", "Unknown")),
                'project_type': inventory.get("projectType", "Terraform"),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'script_path': ''  # Will be handled by template loader
            }
            
            # Render template with context
            html_content = self.template_loader.render_template(
                template_name="inventory_report",
                context=context,
                template_type="reports",
                inline_script=True  # Inline JavaScript for standalone HTML
            )
            
            # Create report file
            report_path = self._create_report_path(report_name, "html", reports_directory)
            
            # Write the report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_content)

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
                    components_html += self._generate_components_table(components, stack_id)
                
                # Add providers table if available
                providers = component_group.get("providers", [])
                if providers:
                    components_html += self._generate_providers_table(providers, stack_id)
                
                # Close the collapsible content and stack section
                components_html += """
                    </div>
                </div>
                """
            
            return components_html
            
        except Exception as e:
            logger.error(f"Failed to generate components HTML: {str(e)}")
            return f'<div class="error-message">Error generating components: {str(e)}</div>'

    def _generate_components_table(self, components: list, stack_id: str) -> str:
        """Generate HTML table for components."""
        html = """
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
                                <th>Registry</th>
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
            registry = component.get("registry", "Unknown")
            status = component.get("status", "Unknown")
            path = component.get("path", "Unknown")
            name = component.get("name", "Unknown")
            
            # Determine status styling
            status_display = f'<span class="status-badge status-{status.lower()}">{status}</span>' if status != "Null" else '<span style="color: #9ca3af;">—</span>'
            
            # Add anchor link for component
            component_id = f"{stack_id}-{name.lower().replace(' ', '-')}"
            
            html += f"""
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
                <td>{registry}</td>
                <td>{status_display}</td>
                <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{path}</code></td>
            </tr>
            """
        
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        """
        
        return html

    def _generate_providers_table(self, providers: list, stack_id: str) -> str:
        """Generate HTML table for providers."""
        html = """
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
                                <th>Registry</th>
                                <th>Status</th>
                                <th>Module</th>
                                <th>Component</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        for provider in providers:
            name = provider.get("name", "Unknown")
            version = provider.get("version", "Unknown")
            source = provider.get("source", "Unknown")
            latest_version = provider.get("latest_version", "Unknown")
            registry = provider.get("registry", "Unknown")
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
            
            html += f"""
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
                <td>{registry if registry != "Unknown" else '<span style="color: #9ca3af;">—</span>'}</td>
                <td>{status_display}</td>
                <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{module}</code></td>
                <td><code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; color: var(--secondary-color);">{component}</code></td>
            </tr>
            """
        
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        """
        
        return html
    def create_pdf_report(
        self, html_path: Path, report_name: str = "InventoryIaC", reports_directory: Optional[str] = None
    ) -> Path:
        """Create PDF report from HTML file with custom options."""
        try:
            pdf_path = self._create_report_path(report_name, "pdf", reports_directory)

            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None
            }

            pdfkit.from_file(str(html_path), str(pdf_path), options=options)
            logger.info(f"PDF report created at: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Failed to create PDF report: {str(e)}")
            raise

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
        """Generate HTML section for schema compatibility analysis with collapsible functionality."""
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
            
            # Generate compatibility section HTML with collapsible header
            compatibility_html = f"""
            <div class="compatibility-section" style="margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 5px;">
                <div class="compatibility-header" style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; margin-bottom: 15px;" onclick="toggleCompatibilitySection()">
                    <h2 style="color: #007bff; margin: 0;">🔍 Provider Schema Compatibility Analysis</h2>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 0.9rem; color: #6c757d;">{len(reports)} provider(s) analyzed</span>
                        <span class="expand-icon" id="compatibility-icon" style="font-size: 1.2rem; color: #007bff; transition: transform 0.3s ease;">▼</span>
                    </div>
                </div>
                
                <div class="compatibility-content" id="compatibility-content" style="transition: max-height 0.4s ease-out, opacity 0.3s ease; max-height: 2000px; opacity: 1; overflow: hidden;">
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
                <div class="provider-compatibility-section" style="margin: 15px 0; border: 1px solid {border_color}; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div class="provider-compatibility-header" style="background-color: {bg_color}; padding: 15px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background-color 0.3s ease;" onclick="toggleProviderCompatibility('{provider_id}')">
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
                    
                    <div class="provider-compatibility-content" id="{provider_id}-content" style="background: white; transition: max-height 0.4s ease-out, opacity 0.3s ease; max-height: 1000px; opacity: 1; overflow: hidden;">
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
            logger.error(f"Failed to generate compatibility HTML: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
                <h2 style="color: #721c24;">🔍 Provider Schema Compatibility Analysis</h2>
                <p><strong>Error:</strong> Failed to generate compatibility report: {str(e)}</p>
            </div>
            """
