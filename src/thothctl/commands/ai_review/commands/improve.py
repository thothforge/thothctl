"""Improve command — generate code fix suggestions for scan findings."""
import json
import logging

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.ai_agent import AIReviewAgent

logger = logging.getLogger(__name__)


class ImproveCommand(ClickCommand):
    """Generate actionable code fixes for security findings."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, directory=None, scan_results=None, provider=None,
                 model=None, severity=None, output=None, json_output=False, **kwargs):
        ctx = click.get_current_context()
        target = directory or scan_results or ctx.obj.get("CODE_DIRECTORY", ".")

        self.ui.print_info(f"Generating fixes for {target}...")

        agent = AIReviewAgent(provider=provider, model=model)

        with self.ui.status_spinner("Analyzing and generating fixes..."):
            if scan_results:
                from ....services.ai_review.analyzers.report_analyzer import ReportAnalyzer
                analyzer = ReportAnalyzer()
                parsed = analyzer.parse_scan_results(scan_results)
                result = agent.generate_fixes(target, scan_results=parsed, severity_filter=severity)
            else:
                result = agent.generate_fixes(target, severity_filter=severity)

        if json_output:
            click.echo(json.dumps(result, indent=2))
            if output:
                with open(output, "w") as f:
                    json.dump(result, f, indent=2)
                self.ui.print_success(f"Fixes saved to {output}")
            return

        # Display summary
        summary = result.get("summary", {})
        self.ui.print_info(
            f"Findings: {summary.get('total_findings', 0)} | "
            f"Fixes: {summary.get('fixes_generated', 0)} | "
            f"Skipped: {summary.get('skipped', 0)}"
        )

        if result.get("_note"):
            self.ui.print_warning(result["_note"])

        # Display fixes
        fixes = result.get("fixes", [])
        if not fixes:
            self.ui.print_warning("No fixes generated.")
            return

        from rich.table import Table
        table = Table(title="Suggested Fixes")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Check", width=15)
        table.add_column("Severity", width=8)
        table.add_column("File", width=25)
        table.add_column("Description", max_width=40)

        for fix in fixes:
            sev = fix.get("severity", "MEDIUM")
            sev_style = {"CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "blue"}.get(sev, "white")
            table.add_row(
                fix.get("fix_id", ""),
                fix.get("finding_id", ""),
                f"[{sev_style}]{sev}[/{sev_style}]",
                fix.get("file", "")[:25],
                fix.get("description", "")[:40],
            )

        self.ui.console.print(table)

        # Show fix details
        self.ui.console.print("\n[bold]Fix Details:[/bold]")
        for fix in fixes[:10]:  # Limit display
            self.ui.console.print(f"\n[cyan]{fix.get('fix_id')}[/cyan] - {fix.get('description')}")
            if fix.get("replacement"):
                self.ui.console.print("[dim]Replacement:[/dim]")
                self.ui.console.print(f"```\n{fix.get('replacement')}\n```")
            if fix.get("validation"):
                self.ui.console.print(f"[dim]Validate:[/dim] {fix.get('validation')}")

        if len(fixes) > 10:
            self.ui.print_info(f"... and {len(fixes) - 10} more fixes. Use --json for full output.")

        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2)
            self.ui.print_success(f"Full results saved to {output}")
        else:
            self.ui.print_info("Use --output FILE to save fixes for apply-fix command.")


cli = ImproveCommand.as_click_command(name="improve")(
    click.option("-d", "--directory", type=click.Path(exists=True), help="Directory to analyze"),
    click.option("-s", "--scan-results", type=click.Path(exists=True), help="Existing scan results directory"),
    click.option("-p", "--provider", type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]), help="AI provider"),
    click.option("-m", "--model", help="Specific model"),
    click.option("--severity", type=click.Choice(["critical", "high", "medium", "low"]),
                 default="medium", help="Minimum severity to fix"),
    click.option("-o", "--output", type=click.Path(), help="Save fixes to JSON file"),
    click.option("--json", "json_output", is_flag=True, help="Output as JSON"),
)
