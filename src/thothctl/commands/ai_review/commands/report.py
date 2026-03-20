"""Report command - cost and usage reporting."""
import logging

import click
from rich.table import Table

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.ai_agent import AIReviewAgent

logger = logging.getLogger(__name__)


class ReportCommand(ClickCommand):
    """AI usage and cost reporting."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, period="daily", provider=None, export=None, **kwargs):
        try:
            agent = AIReviewAgent(provider=provider)
            report = agent.get_cost_report(period)

            table = Table(title=f"AI Cost Report ({period})")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Cost", f"${report['total_cost']:.4f}")
            table.add_row("Total Requests", str(report["total_requests"]))
            table.add_row("Input Tokens", f"{report['total_input_tokens']:,}")
            table.add_row("Output Tokens", f"{report['total_output_tokens']:,}")

            self.ui.console.print(table)

            if report["by_provider"]:
                prov_table = Table(title="By Provider")
                prov_table.add_column("Provider", style="cyan")
                prov_table.add_column("Cost", style="green")
                for p, cost in report["by_provider"].items():
                    prov_table.add_row(p, f"${cost:.4f}")
                self.ui.console.print(prov_table)

            if export:
                import json
                from pathlib import Path
                Path(export).write_text(json.dumps(report, indent=2))
                self.ui.print_success(f"Report exported to {export}")

        except Exception as e:
            self.ui.print_error(f"Failed to generate report: {e}")
            raise click.Abort()


cli = ReportCommand.as_click_command(name="report")(
    click.option(
        "--period",
        type=click.Choice(["daily", "weekly", "monthly"]),
        default="daily",
        help="Reporting period",
    ),
    click.option(
        "-p", "--provider",
        type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]),
        help="Filter by provider",
    ),
    click.option(
        "--export",
        type=click.Path(),
        help="Export report to file",
    ),
)
