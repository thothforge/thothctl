"""Restored original IaC scan command with unified HTML styling."""
import logging
import os
import time
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
        max_workers: int = 2,
        compact: bool = False,
        output: str = "text",
        **kwargs,
    ) -> None:
        """Execute original IaC security scan with unified HTML styling."""
        # Store for post_execute
        self._post_to_pr = kwargs.get('post_to_pr', False)
        self._vcs_provider = kwargs.get('vcs_provider', 'auto')
        self._space = kwargs.get('space')
        self._enforcement = kwargs.get('enforcement', 'soft')
        self._scan_results = None

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
                f"[bold]Starting security scan[/bold]\n\n"
                f"Directory: [cyan]{code_directory}[/cyan]\n"
                f"Project: [magenta]{project_name}[/magenta]\n"
                f"Tools: [yellow]{', '.join(tools)}[/yellow]\n"
                f"Reports directory: [green]{reports_dir}[/green]\n"
                f"Enforcement: [{'red' if self._enforcement == 'hard' else 'green'}]{self._enforcement}[/{'red' if self._enforcement == 'hard' else 'green'}]",
                title="[bold blue]ThothCTL Security Scan[/bold blue]",
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
                max_workers=max_workers,
                compact=compact,
            )
            
            # Display results using enhanced display method
            self._display_original_results(results)
            self._scan_results = results

            # Trend comparison (local SQLite history)
            trend_rows = None
            trend_date = ""
            try:
                from ....services.scan.scan_history import save_scan, get_previous_run, build_trend

                previous = get_previous_run(code_directory)
                save_scan(code_directory, results)

                if previous:
                    trend_rows = build_trend(previous, results)
                    trend_date = previous["timestamp"][:10]
                    self._display_trend(trend_rows, previous["timestamp"])
            except Exception as e:
                self.logger.debug(f"Scan history unavailable: {e}")

            # Generate unified HTML report (replaces per-tool HTML re-parsing)
            try:
                from ....utils.common.render_scan_report import render_unified_report

                html_path = render_unified_report(
                    results=results,
                    reports_dir=reports_dir,
                    project_name=project_name,
                    scan_duration=f"{time.perf_counter() - start_time:.1f}s",
                    trend=trend_rows,
                    trend_date=trend_date,
                )
                self.console.print(f"🌐 HTML report saved to [blue]{html_path}[/blue]")
            except Exception as e:
                self.logger.warning(f"HTML report generation failed: {e}")

            # Always save markdown summary to reports directory
            md_summary = self._build_scan_markdown(results)
            md_path = os.path.join(reports_dir, "scan_summary.md")
            with open(md_path, "w") as f:
                f.write(md_summary)
            self.console.print(f"📝 Markdown summary saved to [blue]{md_path}[/blue]")

            # JSON output mode
            if output == "json":
                import json
                json_report = self._build_json_report(results, code_directory)
                json_path = os.path.join(reports_dir, "scan_report.json")
                with open(json_path, "w") as f:
                    json.dump(json_report, f, indent=2)
                self.console.print_json(data=json_report)
                self.console.print(f"📄 JSON report saved to [blue]{json_path}[/blue]")

            # SARIF output mode
            if output == "sarif":
                from ....services.scan.sarif_output import save_sarif
                sarif_path = save_sarif(results, code_directory, reports_dir)
                self.console.print(f"📄 SARIF report saved to [blue]{sarif_path}[/blue]")
                self.console.print("💡 Upload to GitHub: gh api repos/:owner/:repo/code-scanning/sarifs -f sarif=@" + sarif_path)

            finish_time = time.perf_counter()
            scan_time = finish_time - start_time
            
            # Check if hard enforcement should fail the pipeline
            has_violations = False
            if self._enforcement == "hard":
                for tool_name, tool_result in results.items():
                    if tool_name == "summary" or not isinstance(tool_result, dict):
                        continue
                    rd = tool_result.get("report_data", {})
                    failed = rd.get("failed_count", 0)
                    errors = rd.get("error_count", 0)
                    if failed + errors > 0:
                        has_violations = True
                        break

            # Create completion panel
            completion_panel = Panel(
                f"[bold green]Security scan completed![/bold green]\n\n"
                f"⏱️  Scan time: [cyan]{scan_time:.2f} seconds[/cyan]\n"
                f"📊 Reports directory: [blue]{reports_dir}[/blue]\n"
                f"🎨 HTML reports: [blue]Generated with unified styling[/blue]\n"
                f"🔍 Tools used: [yellow]{len(tools)}[/yellow]",
                title="[bold green]Scan Complete[/bold green]",
                border_style="green"
            )
            self.console.print(completion_panel)

            # Exit with code 1 if hard enforcement failed
            if has_violations:
                ctx = click.get_current_context()
                # Collect violation details per tool
                violation_lines = []
                for tool_name, tool_result in results.items():
                    if tool_name == "summary" or not isinstance(tool_result, dict):
                        continue
                    rd = tool_result.get("report_data", {})
                    failed = rd.get("failed_count", 0)
                    errors = rd.get("error_count", 0)
                    if failed + errors > 0:
                        violation_lines.append(
                            f"  • [yellow]{tool_name}[/yellow]: {failed} violation{'s' if failed != 1 else ''}, {errors} error{'s' if errors != 1 else ''}"
                        )

                violations_detail = "\n".join(violation_lines)
                enforcement_panel = Panel(
                    f"[bold red]Security policy violations detected[/bold red]\n\n"
                    f"{violations_detail}\n\n"
                    f"[dim]Mode:[/dim] [bold]--enforcement hard[/bold] — pipeline will exit with code 1\n"
                    f"[dim]Fix:[/dim]  Resolve the violations above, or use [bold]--enforcement soft[/bold] to report without blocking.\n"
                    f"[dim]Reports:[/dim] See [blue]{reports_dir}[/blue] for details.",
                    title="[bold red]⛔ Enforcement Failed[/bold red]",
                    border_style="red"
                )
                self.console.print(enforcement_panel)
                ctx.exit(1)

        except Exception as e:
            error_panel = Panel(
                f"[bold red]Security scan could not complete[/bold red]\n\n"
                f"[red]{str(e)}[/red]\n\n"
                f"[dim]This is an execution error, not a policy violation.\n"
                f"Check that the required tools are installed and the target directory is valid.[/dim]",
                title="[bold red]❌ Scan Error[/bold red]",
                border_style="red"
            )
            self.console.print(error_panel)
            self.logger.error(f"Scan execution failed: {e}")
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
        summary_table.add_column("Warnings", justify="center", style="dark_orange")
        summary_table.add_column("Errors", justify="center", style="yellow")
        summary_table.add_column("Skipped", justify="center", style="dim")
        summary_table.add_column("Success Rate", justify="center", style="bold")

        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_warnings = 0
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
                passed = failed = warnings = errors = skipped = total = 0
                
                # First try report_data
                report_data = tool_results.get("report_data", {})
                if report_data and any(report_data.get(key, 0) > 0 for key in ["passed_count", "failed_count", "error_count", "skipped_count", "warning_count"]):
                    passed = report_data.get("passed_count", 0)
                    failed = report_data.get("failed_count", 0)
                    warnings = report_data.get("warning_count", 0)
                    errors = report_data.get("error_count", 0)
                    skipped = report_data.get("skipped_count", 0)
                    total = passed + failed + warnings + errors + skipped
                    self.logger.debug(f"Using report_data for {tool_name}: passed={passed}, failed={failed}, warnings={warnings}, errors={errors}, skipped={skipped}")
                
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
                        "kics": "🔍",
                        "terraform-compliance": "📋",
                        "opa": "📜"
                    }
                    icon = tool_icons.get(tool_name, "🔍")
                    
                    # Add to table
                    summary_table.add_row(
                        f"{icon} {tool_name.title()}",
                        f"[{status_style}]{status}[/{status_style}]",
                        str(total),
                        str(passed),
                        str(failed),
                        str(warnings),
                        str(errors),
                        str(skipped),
                        f"{success_rate:.1f}%"
                    )
                    
                    # Update totals
                    total_tests += total
                    total_passed += passed
                    total_failed += failed
                    total_warnings += warnings
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
                f"[bold dark_orange]{total_warnings}[/bold dark_orange]",
                f"[bold yellow]{total_errors}[/bold yellow]",
                f"[bold dim]{total_skipped}[/bold dim]",
                f"[bold]{overall_success_rate:.1f}%[/bold]"
            )

        self.console.print(summary_table)

        # Display severity breakdown if findings are available
        severity_counts = {}
        for tool_name, tool_results in results.items():
            if tool_name == "summary" or not isinstance(tool_results, dict):
                continue
            for finding in tool_results.get("findings", []):
                sev = finding.get("severity", "MEDIUM")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        if severity_counts:
            sev_table = Table(
                title="[bold]Severity Breakdown[/bold]",
                box=rich.box.SIMPLE,
                show_header=True,
                header_style="bold",
            )
            sev_table.add_column("Severity", style="bold")
            sev_table.add_column("Count", justify="center")

            sev_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
            sev_styles = {"CRITICAL": "bold red", "HIGH": "red", "MEDIUM": "dark_orange", "LOW": "yellow", "INFO": "dim"}
            for sev in sev_order:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    sev_table.add_row(f"[{sev_styles.get(sev, '')}]{sev}[/]", str(count))

            self.console.print(sev_table)
        
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

    def _display_trend(self, trend_rows: list, previous_timestamp: str):
        """Display scan trend comparison table."""
        trend_table = Table(
            title=f"[bold]📈 Trend (vs {previous_timestamp[:10]})[/bold]",
            box=rich.box.SIMPLE,
            show_header=True,
            header_style="bold",
        )
        trend_table.add_column("Metric", style="bold")
        trend_table.add_column("Previous", justify="center")
        trend_table.add_column("Current", justify="center")
        trend_table.add_column("Delta", justify="center")

        for row in trend_rows:
            delta_str = f"{row['symbol']} {row['delta']:+d}"
            if row["status"] == "improved":
                delta_style = "green"
            elif row["status"] == "regressed":
                delta_style = "red"
            else:
                delta_style = "dim"

            trend_table.add_row(
                row["metric"],
                str(row["previous"]),
                str(row["current"]),
                f"[{delta_style}]{delta_str}[/]",
            )

        self.console.print(trend_table)

    def _build_scan_markdown(self, results: dict) -> str:
        """Build a markdown summary from scan results."""
        lines = [
            "## 🔒 ThothCTL Scan Results\n",
            "| Tool | Status | Total | Passed | Failed | Warnings | Errors | Skipped | Success Rate |",
            "|------|--------|-------|--------|--------|----------|--------|---------|-------------|",
        ]

        total_tests = total_passed = total_failed = total_warnings = total_errors = total_skipped = 0

        for tool_name, tool_results in results.items():
            if tool_name == "summary" or not isinstance(tool_results, dict):
                continue
            status = tool_results.get("status", "UNKNOWN")
            rd = tool_results.get("report_data", {})
            passed = rd.get("passed_count", 0)
            failed = rd.get("failed_count", 0)
            warnings = rd.get("warning_count", 0)
            errors = rd.get("error_count", 0)
            skipped = rd.get("skipped_count", 0)
            total = passed + failed + warnings + errors + skipped
            rate = f"{(passed / total * 100):.1f}%" if total > 0 else "N/A"
            lines.append(f"| {tool_name} | {status} | {total} | {passed} | {failed} | {warnings} | {errors} | {skipped} | {rate} |")
            total_tests += total
            total_passed += passed
            total_failed += failed
            total_warnings += warnings
            total_errors += errors
            total_skipped += skipped

        if total_tests > 0:
            overall_rate = f"{(total_passed / total_tests * 100):.1f}%"
            lines.append(f"| **TOTAL** | | **{total_tests}** | **{total_passed}** | **{total_failed}** | **{total_warnings}** | **{total_errors}** | **{total_skipped}** | **{overall_rate}** |")

        total_issues = results.get("summary", {}).get("total_issues", 0)
        if total_issues > 0:
            lines.append(f"\n🚨 **Security Issues Found: {total_issues}**")

        # Severity breakdown
        severity_counts = {}
        for tool_name, tool_results in results.items():
            if tool_name == "summary" or not isinstance(tool_results, dict):
                continue
            for finding in tool_results.get("findings", []):
                sev = finding.get("severity", "MEDIUM")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        if severity_counts:
            lines.append("\n### Severity Breakdown\n")
            lines.append("| Severity | Count |")
            lines.append("|----------|-------|")
            for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    lines.append(f"| {sev} | {count} |")

        lines.append("\n---")
        lines.append("*Generated by [ThothCTL](https://github.com/thothforge/thothctl)*")
        return "\n".join(lines)

    def _build_json_report(self, results: dict, directory: str) -> dict:
        """Build a structured JSON report from scan results."""
        from datetime import datetime

        tools = []
        for tool_name, tool_results in results.items():
            if tool_name == "summary" or not isinstance(tool_results, dict):
                continue
            rd = tool_results.get("report_data", {})
            tools.append({
                "tool": tool_name,
                "status": tool_results.get("status", "UNKNOWN"),
                "passed": rd.get("passed_count", 0),
                "failed": rd.get("failed_count", 0),
                "skipped": rd.get("skipped_count", 0),
                "warnings": rd.get("warning_count", 0),
                "errors": rd.get("error_count", 0),
                "findings": tool_results.get("findings", []),
            })

        severity_counts = {}
        for t in tools:
            for f in t.get("findings", []):
                sev = f.get("severity", "MEDIUM")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "timestamp": datetime.now().isoformat(),
            "directory": directory,
            "total_findings": results.get("summary", {}).get("total_issues", 0),
            "severity_counts": severity_counts,
            "tools": tools,
        }

    def post_execute(self, **kwargs) -> None:
        """Post scan summary to PR if --post-to-pr flag is set."""
        if not getattr(self, '_post_to_pr', False):
            return
        results = getattr(self, '_scan_results', None)
        if not results:
            return

        from ....core.integrations.pr_comments.pr_comment_publisher import publish_to_pr

        content = self._build_scan_markdown(results)
        if publish_to_pr(
            content=content,
            vcs_provider=getattr(self, '_vcs_provider', 'auto'),
            space=getattr(self, '_space', None),
        ):
            self.console.print("[green]✅ Scan summary posted to PR[/green]")
        else:
            self.console.print("[yellow]⚠️ Could not post scan summary to PR[/yellow]")


# Create the Click command
cli = RestoredIaCScanCommand.as_click_command(
    help="Scan IaC using security tools with original functionality and unified HTML styling."
)(
    click.option(
        "--tools",
        "-t",
        multiple=True,
        default=["checkov"],
        help="Security scanning tools to use (Note: KICS requires Docker)",
        type=click.Choice(["checkov", "trivy", "kics", "terraform-compliance", "opa"]),
    ),
    click.option(
        "--reports-dir",
        "-r",
        default="Reports",
        help="Directory to save scan reports",
        type=click.Path(),
    ),
    click.option(
        "--project-name",
        "-p",
        default="Security Scan",
        help="Name of the project being scanned",
        type=str,
    ),
    click.option(
        "--options",
        "-o",
        help="Additional options for scanning tools (key=value,key2=value2)",
        type=str,
    ),
    click.option(
        "--tftool",
        default="tofu",
        help="Terraform tool to use (terraform or tofu)",
        type=click.Choice(["terraform", "tofu"]),
    ),
    click.option(
        "--verbose",
        "-v",
        is_flag=True,
        help="Enable verbose output",
    ),
    click.option(
        "--html-reports-format",
        default="simple",
        help="Format for HTML reports",
        type=click.Choice(["simple", "xunit"]),
    ),
    click.option(
        "--post-to-pr",
        is_flag=True,
        default=False,
        help="Post scan summary as a PR comment (Azure DevOps or GitHub)",
    ),
    click.option(
        "--vcs-provider",
        type=click.Choice(["auto", "azure_repos", "github"], case_sensitive=False),
        default="auto",
        help="VCS provider for PR comments (default: auto-detect from CI environment)",
    ),
    click.option(
        "--space",
        help="Space name for credential resolution (Azure DevOps)",
        default=None,
    ),
    click.option(
        "--enforcement",
        type=click.Choice(["soft", "hard"], case_sensitive=False),
        default="soft",
        help="Enforcement mode: 'soft' reports violations (exit 0), 'hard' fails the pipeline (exit 1) when any tool finds violations",
    ),
    click.option(
        "--max-workers",
        type=int,
        default=2,
        help="Max parallel checkov scans (default: 2, reduce to 1 on low-memory agents)",
    ),
    click.option(
        "--compact",
        is_flag=True,
        default=False,
        help="Use checkov --compact mode to reduce memory usage on constrained CI agents",
    ),
    click.option(
        "--output",
        type=click.Choice(["text", "json", "sarif"], case_sensitive=False),
        default="text",
        help="Output format: 'text' (default), 'json' (structured), or 'sarif' (GitHub/IDE compatible)",
    ),
)
