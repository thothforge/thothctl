"""Restored original IaC scan command with unified HTML styling."""
import logging
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Literal, Optional

import click
import rich.box
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ....core.commands import ClickCommand
from ....services.scan.scan_service import ScanService


logger = logging.getLogger(__name__)


class RestoredIaCScanCommand(ClickCommand):
    """Restored original IaC scan command with unified HTML styling."""

    def __init__(self):
        super().__init__()
        self.logger = logger
        self.console = Console()

    def validate(self, **kwargs) -> bool:
        """Validate scan parameters."""
        return True

    def _execute(
        self,
        tools: List[str],
        reports_dir: str,
        project_name: str = "Security Scan",
        options: Optional[str] = None,
        tftool: str = "tofu",
        verbose: bool = False,
        html_reports_format: Literal["simple", "xunit"] = "simple",
        **kwargs,
    ) -> None:
        """Execute original IaC security scan with unified HTML styling."""
        try:
            ctx = click.get_current_context()
            code_directory = ctx.obj.get("CODE_DIRECTORY")
            debug_mode = ctx.obj.get("DEBUG", False)
            
            # Set debug environment variable for the scan service
            if debug_mode:
                os.environ["THOTHCTL_DEBUG"] = "true"
            
            self.logger.info(f"Starting original recursive scan in {code_directory}")
            
            # Create a panel with scan information
            scan_info = Panel(
                f"[bold]Starting security scan (Original Mode)[/bold]\n\n"
                f"Directory: [cyan]{code_directory}[/cyan]\n"
                f"Project: [magenta]{project_name}[/magenta]\n"
                f"Tools: [yellow]{', '.join(tools)}[/yellow]\n"
                f"Reports directory: [green]{reports_dir}[/green]\n"
                f"Output: [blue]Original structure with unified styling[/blue]",
                title="[bold blue]ThothCTL Original Scan[/bold blue]",
                border_style="blue"
            )
            self.console.print(scan_info)

            # Use the original scan service
            scan_service = ScanService()
            start_time = time.perf_counter()
            
            # Execute scan with original functionality
            results = scan_service.execute_scans(
                directory=code_directory,
                reports_dir=reports_dir,
                selected_tools=tools,
                options=self._parse_options(options) if options else {},
                tftool=tftool,
                html_reports_format=html_reports_format,
            )
            
            # Enhanced data extraction and validation
            for tool_name in tools:
                if tool_name in results:
                    tool_results = results[tool_name]
                    
                    # Ensure report_data is properly populated
                    if not tool_results.get("report_data") or all(v == 0 for v in tool_results.get("report_data", {}).values()):
                        # Try to extract from detailed_reports first
                        if "detailed_reports" in tool_results and tool_results["detailed_reports"]:
                            detailed_reports = tool_results["detailed_reports"]
                            
                            # Calculate totals from detailed reports
                            passed = sum(r.get("passed", 0) for r in detailed_reports.values())
                            failed = sum(r.get("failed", 0) for r in detailed_reports.values())
                            skipped = sum(r.get("skipped", 0) for r in detailed_reports.values())
                            error = sum(r.get("error", 0) for r in detailed_reports.values())
                            
                            # Create or update report_data
                            tool_results["report_data"] = {
                                "passed_count": passed,
                                "failed_count": failed,
                                "skipped_count": skipped,
                                "error_count": error,
                            }
                            
                            self.logger.info(f"Enhanced data extraction for {tool_name}: passed={passed}, failed={failed}, skipped={skipped}, error={error}")
                            
                            # Update issues count for consistency
                            tool_results["issues_count"] = failed + error
                        
                        # If still no data, try to parse from report files directly
                        elif tool_results.get("status") == "COMPLETE":
                            # Try multiple possible locations for XML files
                            possible_paths = [
                                os.path.join(reports_dir, "security-scan"),  # Reports/security-scan/
                                tool_results.get("report_path", ""),  # Direct report path
                            ]
                            
                            xml_files = []
                            for base_path in possible_paths:
                                if base_path and os.path.exists(base_path):
                                    if os.path.isdir(base_path):
                                        # Search recursively for XML files
                                        for root, dirs, files in os.walk(base_path):
                                            for file in files:
                                                if file.endswith('.xml') and 'junit' in file.lower():
                                                    xml_files.append(os.path.join(root, file))
                                    elif base_path.endswith('.xml'):
                                        xml_files.append(base_path)
                            
                            if xml_files:
                                total_passed = total_failed = total_skipped = total_error = 0
                                
                                for xml_file in xml_files:
                                    try:
                                        self.logger.debug(f"Parsing XML file: {xml_file}")
                                        tree = ET.parse(xml_file)
                                        root = tree.getroot()
                                        
                                        # Count from testsuite attributes (most reliable)
                                        for testsuite in root.findall(".//testsuite"):
                                            tests = int(testsuite.get('tests', '0'))
                                            failures = int(testsuite.get('failures', '0'))
                                            errors = int(testsuite.get('errors', '0'))
                                            skipped = int(testsuite.get('skipped', '0'))
                                            
                                            total_failed += failures
                                            total_error += errors
                                            total_skipped += skipped
                                            total_passed += (tests - failures - errors - skipped)
                                            
                                            self.logger.debug(f"Testsuite data: tests={tests}, failures={failures}, errors={errors}, skipped={skipped}")
                                        
                                        # If no testsuite data, count individual testcases
                                        if total_passed + total_failed + total_skipped + total_error == 0:
                                            for testcase in root.findall(".//testcase"):
                                                failure = testcase.find("failure")
                                                skipped_tag = testcase.find("skipped")
                                                error_tag = testcase.find("error")
                                                
                                                if failure is not None:
                                                    total_failed += 1
                                                elif skipped_tag is not None:
                                                    total_skipped += 1
                                                elif error_tag is not None:
                                                    total_error += 1
                                                else:
                                                    total_passed += 1
                                    except Exception as e:
                                        self.logger.debug(f"Error parsing XML file {xml_file}: {e}")
                                
                                if total_passed + total_failed + total_skipped + total_error > 0:
                                    tool_results["report_data"] = {
                                        "passed_count": total_passed,
                                        "failed_count": total_failed,
                                        "skipped_count": total_skipped,
                                        "error_count": total_error,
                                    }
                                    tool_results["issues_count"] = total_failed + total_error
                                    
                                    self.logger.info(f"Direct XML extraction for {tool_name}: passed={total_passed}, failed={total_failed}, skipped={total_skipped}, error={total_error}")
                                    
                                    # Also create detailed_reports for consistency
                                    if not tool_results.get("detailed_reports"):
                                        tool_results["detailed_reports"] = {
                                            f"report_{tool_name}": {
                                                "passed": total_passed,
                                                "failed": total_failed,
                                                "skipped": total_skipped,
                                                "error": total_error,
                                                "total": total_passed + total_failed + total_skipped + total_error,
                                                "report_path": xml_files[0] if xml_files else ""
                                            }
                                        }
            
            # Display results using enhanced display method
            self._display_original_results(results)

            finish_time = time.perf_counter()
            scan_time = finish_time - start_time
            
            # Create completion panel
            completion_panel = Panel(
                f"[bold green]Original scan completed successfully![/bold green]\n\n"
                f"⏱️  Scan time: [cyan]{scan_time:.2f} seconds[/cyan]\n"
                f"📊 Reports directory: [blue]{reports_dir}[/blue]\n"
                f"🎨 HTML reports: [blue]Generated with unified styling[/blue]\n"
                f"🔍 Tools used: [yellow]{len(tools)}[/yellow]",
                title="[bold green]Original Scan Complete[/bold green]",
                border_style="green"
            )
            self.console.print(completion_panel)

        except Exception as e:
            error_panel = Panel(
                f"[bold red]Original scan failed![/bold red]\n\n"
                f"Error: [red]{str(e)}[/red]",
                title="[bold red]Error[/bold red]",
                border_style="red"
            )
            self.console.print(error_panel)
            self.logger.error(f"Original scan execution failed: {e}")
            raise

    def _parse_options(self, options_str: str) -> dict:
        """Parse options string into dictionary."""
        if not options_str:
            return {}
        
        # Simple parsing for key=value pairs separated by commas
        options = {}
        try:
            for pair in options_str.split(','):
                if '=' in pair:
                    key, value = pair.strip().split('=', 1)
                    options[key.strip()] = value.strip()
        except Exception as e:
            self.logger.warning(f"Error parsing options '{options_str}': {e}")
        
        return options

    def _display_original_results(self, results: dict):
        """Display original scan results in a formatted table."""
        # Create summary table (original style)
        summary_table = Table(
            title="[bold blue]Scan Results Summary[/bold blue]",
            box=rich.box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        
        summary_table.add_column("Tool", style="cyan", no_wrap=True)
        summary_table.add_column("Status", justify="center", style="bold")
        summary_table.add_column("Total Tests", justify="center", style="blue")
        summary_table.add_column("Passed", justify="center", style="green")
        summary_table.add_column("Failed", justify="center", style="red")
        summary_table.add_column("Errors", justify="center", style="yellow")
        summary_table.add_column("Skipped", justify="center", style="dim")
        summary_table.add_column("Success Rate", justify="center", style="bold")

        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0
        total_skipped = 0

        # Process results for each tool (original logic)
        for tool_name, tool_results in results.items():
            if tool_name in ["summary"]:
                continue
                
            if isinstance(tool_results, dict) and tool_results:
                # Get status
                status = tool_results.get("status", "UNKNOWN")
                status_style = "green" if status == "COMPLETE" else "red"
                
                # Extract counts from multiple sources
                passed = failed = errors = skipped = total = 0
                
                # First try report_data
                report_data = tool_results.get("report_data", {})
                if report_data and any(report_data.get(key, 0) > 0 for key in ["passed_count", "failed_count", "error_count", "skipped_count"]):
                    passed = report_data.get("passed_count", 0)
                    failed = report_data.get("failed_count", 0)
                    errors = report_data.get("error_count", 0)
                    skipped = report_data.get("skipped_count", 0)
                    total = passed + failed + errors + skipped
                    self.logger.debug(f"Using report_data for {tool_name}: passed={passed}, failed={failed}, errors={errors}, skipped={skipped}")
                
                # If report_data is empty, try detailed_reports
                elif "detailed_reports" in tool_results and tool_results["detailed_reports"]:
                    detailed_reports = tool_results["detailed_reports"]
                    passed = sum(r.get("passed", 0) for r in detailed_reports.values())
                    failed = sum(r.get("failed", 0) for r in detailed_reports.values())
                    errors = sum(r.get("error", 0) for r in detailed_reports.values())
                    skipped = sum(r.get("skipped", 0) for r in detailed_reports.values())
                    total = passed + failed + errors + skipped
                    self.logger.debug(f"Using detailed_reports for {tool_name}: passed={passed}, failed={failed}, errors={errors}, skipped={skipped}")
                    
                    # Update report_data for consistency
                    tool_results["report_data"] = {
                        "passed_count": passed,
                        "failed_count": failed,
                        "error_count": errors,
                        "skipped_count": skipped,
                    }
                
                # If we have valid data, display it
                if total > 0:
                    # Calculate success rate
                    success_rate = (passed / total * 100) if total > 0 else 0
                    
                    # Get tool icon
                    tool_icons = {
                        "checkov": "🔒",
                        "trivy": "🛡️",
                        "tfsec": "🔐",
                        "terraform-compliance": "📋"
                    }
                    icon = tool_icons.get(tool_name, "🔍")
                    
                    # Add to table
                    summary_table.add_row(
                        f"{icon} {tool_name.title()}",
                        f"[{status_style}]{status}[/{status_style}]",
                        str(total),
                        str(passed),
                        str(failed),
                        str(errors),
                        str(skipped),
                        f"{success_rate:.1f}%"
                    )
                    
                    # Update totals
                    total_tests += total
                    total_passed += passed
                    total_failed += failed
                    total_errors += errors
                    total_skipped += skipped
                else:
                    # Handle case where no data is available - try issues_count as fallback
                    issues_count = tool_results.get("issues_count", 0)
                    if issues_count > 0:
                        # Assume all issues are failures if no breakdown available
                        summary_table.add_row(
                            f"🔍 {tool_name.title()}",
                            f"[{status_style}]{status}[/{status_style}]",
                            str(issues_count),
                            "0",
                            str(issues_count),
                            "0",
                            "0",
                            "0.0%"
                        )
                        total_tests += issues_count
                        total_failed += issues_count
                    else:
                        # Show that scan completed but no data available
                        summary_table.add_row(
                            f"🔍 {tool_name.title()}",
                            f"[{status_style}]{status}[/{status_style}]",
                            "0",
                            "N/A",
                            "0",
                            "0",
                            "0",
                            "N/A"
                        )

        # Add totals row
        if total_tests > 0:
            overall_success_rate = (total_passed / total_tests * 100)
            summary_table.add_section()
            summary_table.add_row(
                "[bold]TOTAL[/bold]",
                "[bold green]COMPLETE[/bold green]",
                f"[bold]{total_tests}[/bold]",
                f"[bold green]{total_passed}[/bold green]",
                f"[bold red]{total_failed}[/bold red]",
                f"[bold yellow]{total_errors}[/bold yellow]",
                f"[bold dim]{total_skipped}[/bold dim]",
                f"[bold]{overall_success_rate:.1f}%[/bold]"
            )

        self.console.print(summary_table)
        
        # Display detailed results for each tool (original behavior)
        for tool_name, tool_results in results.items():
            if tool_name in ["summary"] or not isinstance(tool_results, dict):
                continue
                
            if tool_results.get("status") == "COMPLETE":
                # Show detailed reports if available
                detailed_reports = tool_results.get("detailed_reports", {})
                if detailed_reports:
                    detail_panel = Panel(
                        f"[bold]{tool_name.title()} Detailed Results[/bold]\n\n" +
                        "\n".join([
                            f"📁 {report_name}: "
                            f"✅ {data.get('passed', 0)} passed, "
                            f"❌ {data.get('failed', 0)} failed, "
                            f"⚠️ {data.get('error', 0)} errors, "
                            f"⏭️ {data.get('skipped', 0)} skipped"
                            for report_name, data in detailed_reports.items()
                        ]),
                        title=f"[bold blue]{tool_name.title()} Details[/bold blue]",
                        border_style="blue"
                    )
                    self.console.print(detail_panel)
                
                # Show report path
                report_path = tool_results.get("report_path", "N/A")
                if report_path != "N/A":
                    path_panel = Panel(
                        f"[bold]Report Location[/bold]\n\n"
                        f"📄 Path: [blue]{report_path}[/blue]\n"
                        f"🎨 Styling: [green]Unified HTML format applied[/green]",
                        title=f"[bold green]{tool_name.title()} Report[/bold green]",
                        border_style="green"
                    )
                    self.console.print(path_panel)
            else:
                # Show error information
                error_info = tool_results.get("error", "Unknown error")
                error_panel = Panel(
                    f"[bold red]Tool execution failed[/bold red]\n\n"
                    f"Error: [red]{error_info}[/red]",
                    title=f"[bold red]{tool_name.title()} Error[/bold red]",
                    border_style="red"
                )
                self.console.print(error_panel)
        
        # Display summary information (original behavior)
        summary = results.get("summary", {})
        total_issues = summary.get("total_issues", 0)
        
        if total_issues > 0:
            summary_panel = Panel(
                f"[bold yellow]Security Issues Found[/bold yellow]\n\n"
                f"🚨 Total Issues: [red]{total_issues}[/red]\n"
                f"📊 Review the generated reports for detailed information\n"
                f"🎨 Reports generated with unified styling for better readability",
                title="[bold yellow]Summary[/bold yellow]",
                border_style="yellow"
            )
            self.console.print(summary_panel)
        else:
            self.console.print(Panel(
                "[bold green]✅ No security issues detected![/bold green]\n\n"
                "All security checks passed successfully.\n"
                "Reports generated with unified styling.",
                title="[bold green]Security Status[/bold green]",
                border_style="green"
            ))


@click.command()
@click.option(
    "--tools",
    "-t",
    multiple=True,
    default=["checkov"],
    help="Security scanning tools to use",
    type=click.Choice(["checkov", "trivy", "tfsec", "terraform-compliance"]),
)
@click.option(
    "--reports-dir",
    "-r",
    default="Reports",
    help="Directory to save scan reports",
    type=click.Path(),
)
@click.option(
    "--project-name",
    "-p",
    default="Security Scan",
    help="Name of the project being scanned",
    type=str,
)
@click.option(
    "--options",
    "-o",
    help="Additional options for scanning tools (key=value,key2=value2)",
    type=str,
)
@click.option(
    "--tftool",
    default="tofu",
    help="Terraform tool to use (terraform or tofu)",
    type=click.Choice(["terraform", "tofu"]),
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--html-reports-format",
    default="simple",
    help="Format for HTML reports",
    type=click.Choice(["simple", "xunit"]),
)
@click.pass_context
def cli(ctx, tools, reports_dir, project_name, options, tftool, verbose, html_reports_format):
    """
    Scan IaC using security tools with original functionality and unified HTML styling.
    
    This is the restored original scan command that:
    - Uses the original recursive scanning logic
    - Maintains the original report structure
    - Applies unified HTML styling to generated reports
    - Preserves backward compatibility
    
    The scan will:
    - Recursively find Terraform files in subdirectories
    - Generate individual reports for each directory/stack
    - Apply modern unified styling to all HTML reports
    - Maintain the original file structure and organization
    
    Examples:
    
        # Original scan with Checkov (default)
        thothctl scan iac
        
        # Original scan with multiple tools
        thothctl scan iac -t checkov -t trivy -t tfsec
        
        # Original scan with custom project name
        thothctl scan iac -p "Production Infrastructure"
        
        # Original scan with custom reports directory
        thothctl scan iac -r /path/to/reports
        
        # Original scan with additional options
        thothctl scan iac -o "verbose=true,format=json"
    """
    command = RestoredIaCScanCommand()
    command.execute(
        tools=list(tools),
        reports_dir=reports_dir,
        project_name=project_name,
        options=options,
        tftool=tftool,
        verbose=verbose,
        html_reports_format=html_reports_format,
    )
