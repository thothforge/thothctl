"""Analyze command - AI-powered scan result and code analysis."""
import logging

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.ai_agent import AIReviewAgent
from ....services.ai_review.utils.formatters import format_analysis_as_markdown, format_analysis_as_json

logger = logging.getLogger(__name__)


class AnalyzeCommand(ClickCommand):
    """AI-powered analysis of scan results and IaC code."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        directory = kwargs.get("directory")
        scan_results = kwargs.get("scan_results")
        if not directory and not scan_results:
            ctx = click.get_current_context()
            if not ctx.obj.get("CODE_DIRECTORY"):
                self.ui.print_error("Either --directory or --scan-results is required")
                return False
        return True

    def _execute(self, directory=None, scan_results=None,
                 provider=None, model=None, output="markdown", **kwargs):
        ctx = click.get_current_context()
        code_directory = ctx.obj.get("CODE_DIRECTORY", ".")
        target = scan_results or directory or code_directory

        self.ui.print_info(
            f"AI Security Analysis | Target: {target} | "
            f"Provider: {provider or 'default'} | Output: {output}"
        )

        try:
            agent = AIReviewAgent(provider=provider, model=model)

            if scan_results:
                with self.ui.status_spinner("Analyzing scan results..."):
                    result = agent.analyze_scan_results(scan_results)
            elif directory:
                with self.ui.status_spinner("Analyzing directory..."):
                    result = agent.analyze_directory(directory)
            else:
                with self.ui.status_spinner("Analyzing current directory..."):
                    result = agent.analyze_directory(code_directory)

            if output == "json":
                self.ui.console.print(format_analysis_as_json(result))
            else:
                self.ui.console.print(format_analysis_as_markdown(result))

            cost_report = agent.get_cost_report("daily")
            if cost_report["total_cost"] > 0:
                self.ui.print_info(
                    f"💰 Today's AI cost: ${cost_report['total_cost']:.4f} "
                    f"({cost_report['total_requests']} requests)"
                )

        except ImportError as e:
            self.ui.print_error(f"Missing dependency: {e}")
            self.ui.print_warning("Install with: pip install openai boto3")
        except Exception as e:
            self.ui.print_error(f"Analysis failed: {e}")
            raise click.Abort()


cli = AnalyzeCommand.as_click_command(name="analyze")(
    click.option(
        "-d", "--directory",
        type=click.Path(exists=True),
        help="Directory to analyze",
    ),
    click.option(
        "-s", "--scan-results",
        type=click.Path(exists=True),
        help="Existing scan results directory",
    ),
    click.option(
        "-p", "--provider",
        type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]),
        help="AI provider",
    ),
    click.option(
        "-m", "--model",
        help="Specific model to use",
    ),
    click.option(
        "-o", "--output",
        type=click.Choice(["json", "markdown", "html"]),
        default="markdown",
        help="Output format",
    ),
)
