import logging
import time
from typing import List, Literal, Optional

import click

from rich import print as rprint

from ....core.commands import ClickCommand
from ....services.scan.scan_service import ScanService


logger = logging.getLogger(__name__)


class IaCScanCommand(ClickCommand):
    """Command to convert projects between different formats."""

    def __init__(self):
        super().__init__()
        self.logger = logger

    def validate(self, **kwargs) -> bool:
        """Validate conversion parameters."""
        return True

    def execute(
        self,
        tools: List[str],
        reports_dir: str,
        options: Optional[str] = None,
        tftool: str = "tofu",
        verbose: bool = False,
        html_reports_format: Literal["simple", "xunit"] = "simple",
        **kwargs,
    ) -> None:
        """Execute project conversion."""
        try:
            ctx = click.get_current_context()
            code_directory = ctx.obj.get("CODE_DIRECTORY")
            self.logger.info(f"Starting recursive scan in {code_directory}")
            rprint(f"[yellow]Starting recursive scan in {code_directory}[/yellow]")

            scan_service = ScanService()
            start_time = time.perf_counter()
            results = scan_service.execute_scans(
                directory=code_directory,
                reports_dir=reports_dir,
                selected_tools=tools,
                options=options,
                tftool=tftool,
                html_reports_format=html_reports_format,
            )
            # Display results
            self._display_results(results)

            finish_time = time.perf_counter()
            scan_time = finish_time - start_time
            rprint(f"[green]✨ Scan finished in {scan_time:.2f} seconds[/green]")

        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            raise click.ClickException(str(e))

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting Scan process")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("Scan process completed")

    def _display_results(self, results: dict) -> None:
        """Display scan results."""
        click.echo("\nScan Results:")
        for tool, result in results.items():
            status = result.get("status", "UNKNOWN")
            color = "green" if status == "COMPLETE" else "red"
            click.secho(f"{tool}: {status}", fg=color)

            if status == "FAIL" and "error" in result:
                click.secho(f"  Error: {result['error']}", fg="red")

            if "report_path" in result:
                click.echo(f"  Report: {result['report_path']}")


# Create the Click command
cli = IaCScanCommand.as_click_command(
    help="Scan IaC using tools like checkov, trivy, terraform-compliance, create reports and send them to AI tool for \n"
    "recommendations."
)(
    click.option(
        "--reports-dir",
        type=click.Path(),
        default="Reports",
        help="Directory to store scan reports",
    ),
    click.option(
        "--tools",
        "-t",
        multiple=True,
        type=click.Choice(
            ["trivy", "tfsec", "checkov", "terraform-compliance"], case_sensitive=False
        ),
        default=["trivy", "tfsec", "checkov"],
        help="Security scanning tools to use",
    ),
    click.option(
        "--features-dir",
        type=click.Path(exists=True),
        help="Directory containing terraform-compliance features",
    ),
    click.option("--trivy-options", help="Additional options for Trivy scanner"),
    click.option("--tfsec-options", help="Additional options for TFSec scanner"),
    click.option("--checkov-options", help="Additional options for Checkov scanner"),
    click.option(
        "--terraform-compliance-options",
        help="Additional options for Terraform-compliance scanner",
    ),
    click.option(
        "--tftool",
        type=click.Choice(["terraform", "tofu"]),
        default="tofu",
        help="Terraform tool to use (terraform or tofu)",
    ),
    click.option(
        "--output-format",
        type=click.Choice(["text", "json", "xml"]),
        default="text",
        help="Output format for the reports",
    ),
    click.option(
        "--html-reports-format",
        type=click.Choice(["simple", "xunit"]),
        default="simple",
        help="if you want create a html reports, if you select xunit you must have installed xunit-viewer (npm -g install xunit-viewer),",
    ),
    click.option("--verbose", is_flag=True, help="Enable verbose output"),
)
