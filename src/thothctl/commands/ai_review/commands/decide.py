"""Decide command — run AI analysis and auto-decide on a PR."""
import logging

import click
from rich.table import Table

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.ai_agent import AIReviewAgent
from ....services.ai_review.decision_engine import DecisionEngine, Decision
from ....services.ai_review.pr_decision_publisher import PRDecisionPublisher, format_decision_comment
from ....services.ai_review.config.decision_rules import DecisionRules

logger = logging.getLogger(__name__)


class DecideCommand(ClickCommand):
    """Run AI analysis and auto-decide (approve/reject/request-changes) on a PR."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        if not kwargs.get("directory") and not kwargs.get("scan_results"):
            self.ui.print_error("Either --directory or --scan-results is required")
            return False
        return True

    def _execute(self, directory=None, scan_results=None, provider=None,
                 model=None, pr_number=None, repository=None,
                 platform=None, dry_run=False, **kwargs):
        ctx = click.get_current_context()
        code_directory = ctx.obj.get("CODE_DIRECTORY", ".")
        target = scan_results or directory or code_directory

        rules = DecisionRules.load()
        if not rules.enabled and not dry_run:
            self.ui.print_warning("Auto-decisions are disabled. Use --dry-run to preview, or enable with:")
            self.ui.print_info("  thothctl ai-review configure-decisions --enable")
            return

        # Run AI analysis
        self.ui.print_info(f"Analyzing {target}...")
        agent = AIReviewAgent(provider=provider, model=model)

        with self.ui.status_spinner("Running AI analysis..."):
            if scan_results:
                analysis = agent.analyze_scan_results(scan_results)
            else:
                analysis = agent.analyze_directory(target)

        # Evaluate decision
        engine = DecisionEngine(rules)
        result = engine.evaluate(
            analysis=analysis,
            repository=repository or "",
            pr_id=str(pr_number or ""),
        )

        # Display result
        self._display_decision(result)

        if dry_run:
            self.ui.print_warning("[DRY RUN] No action taken.")
            comment = format_decision_comment(result, analysis)
            self.ui.console.print("\n[dim]--- Preview comment ---[/dim]")
            self.ui.console.print(comment)
            return

        # Publish to PR
        if pr_number and repository:
            publisher = PRDecisionPublisher(platform=platform or "auto")
            with self.ui.status_spinner("Publishing decision to PR..."):
                pub_result = publisher.publish(result, analysis, repository, str(pr_number))

            if pub_result.get("error"):
                self.ui.print_error(f"Failed to publish: {pub_result['error']}")
            else:
                self.ui.print_success(f"Decision published: {result.decision.value.upper()}")
        else:
            self.ui.print_info("No --pr-number/--repository provided. Showing result only.")

    def _display_decision(self, result):
        icons = {Decision.APPROVE: "✅", Decision.REJECT: "🚫",
                 Decision.REQUEST_CHANGES: "🔄", Decision.COMMENT: "💬"}

        table = Table(title=f"{icons.get(result.decision, '🤖')} Decision: {result.decision.value.upper()}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Confidence", f"{result.confidence:.0%}")
        table.add_row("Risk Score", f"{result.risk_score:.0f}/100")
        table.add_row("Critical", str(result.findings_summary["critical"]))
        table.add_row("High", str(result.findings_summary["high"]))
        table.add_row("Medium", str(result.findings_summary["medium"]))
        table.add_row("Low", str(result.findings_summary["low"]))
        table.add_row("Reason", result.reason)
        if result.blocked_by_safety:
            table.add_row("Safety Block", result.safety_reason)
        self.ui.console.print(table)


cli = DecideCommand.as_click_command(name="decide")(
    click.option("-d", "--directory", type=click.Path(exists=True), help="Directory to analyze"),
    click.option("-s", "--scan-results", type=click.Path(exists=True), help="Existing scan results"),
    click.option("-p", "--provider", type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]), help="AI provider"),
    click.option("-m", "--model", help="Specific model"),
    click.option("--pr-number", type=int, help="PR number to act on"),
    click.option("--repository", help="Repository (owner/repo)"),
    click.option("--platform", type=click.Choice(["github", "azure_devops", "auto"]), default="auto", help="VCS platform"),
    click.option("--dry-run", is_flag=True, help="Preview decision without taking action"),
)
