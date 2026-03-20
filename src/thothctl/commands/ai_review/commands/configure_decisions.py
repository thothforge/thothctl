"""Configure-decisions command — manage auto-decision rules and safety controls."""
import logging

import click
from rich.table import Table

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.config.decision_rules import DecisionRules
from ....services.ai_review.safety.safety_guard import SafetyGuard

logger = logging.getLogger(__name__)


class ConfigureDecisionsCommand(ClickCommand):
    """Configure auto-decision thresholds and safety controls."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, enable=False, disable=False,
                 approve_threshold=None, reject_threshold=None,
                 confidence=None, show=False, stats=False, **kwargs):
        rules = DecisionRules.load()

        if show:
            self._display_rules(rules)
            return

        if stats:
            guard = SafetyGuard(rules.safety)
            s = guard.get_today_stats()
            self.ui.console.print(f"Today ({s['date']}): {s['total']} actions — {s['actions']}")
            return

        changed = False

        if enable:
            rules.enabled = True
            changed = True
            self.ui.print_success("Auto-decisions ENABLED")
        if disable:
            rules.enabled = False
            changed = True
            self.ui.print_warning("Auto-decisions DISABLED")
        if approve_threshold is not None:
            rules.approve.risk_score_max = approve_threshold
            changed = True
            self.ui.print_success(f"Auto-approve threshold: risk ≤ {approve_threshold}")
        if reject_threshold is not None:
            rules.reject.risk_score_min = reject_threshold
            changed = True
            self.ui.print_success(f"Auto-reject threshold: risk ≥ {reject_threshold}")
        if confidence is not None:
            rules.approve.confidence_min = confidence
            rules.reject.confidence_min = max(confidence - 0.05, 0.70)
            rules.request_changes.confidence_min = max(confidence - 0.10, 0.60)
            changed = True
            self.ui.print_success(f"Confidence thresholds updated (base: {confidence:.0%})")

        if changed:
            rules.save()
            self.ui.print_success("Decision rules saved.")
        elif not show and not stats:
            self.ui.print_warning("No changes. Use --show to view, --enable/--disable to toggle.")

    def _display_rules(self, rules: DecisionRules):
        table = Table(title="Auto-Decision Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Enabled", "✅ Yes" if rules.enabled else "❌ No")
        table.add_row("", "")
        table.add_row("[bold]Auto-Approve[/bold]", "")
        table.add_row("  Risk score ≤", str(rules.approve.risk_score_max))
        table.add_row("  Confidence ≥", f"{rules.approve.confidence_min:.0%}")
        table.add_row("  Max critical", str(rules.approve.critical_issues_max))
        table.add_row("  Max high", str(rules.approve.high_issues_max))
        table.add_row("", "")
        table.add_row("[bold]Auto-Reject[/bold]", "")
        table.add_row("  Risk score ≥", str(rules.reject.risk_score_min))
        table.add_row("  Confidence ≥", f"{rules.reject.confidence_min:.0%}")
        table.add_row("  Min critical", str(rules.reject.critical_issues_min))
        table.add_row("", "")
        table.add_row("[bold]Safety[/bold]", "")
        table.add_row("  Max approvals/day", str(rules.safety.max_auto_approvals_per_day))
        table.add_row("  Max rejections/day", str(rules.safety.max_auto_rejections_per_day))
        table.add_row("  Cooldown", f"{rules.safety.cooldown_between_actions}s")
        table.add_row("  Emergency labels", ", ".join(rules.safety.emergency_labels))
        table.add_row("  Trusted bots", ", ".join(rules.safety.trusted_bots) or "none")

        self.ui.console.print(table)


cli = ConfigureDecisionsCommand.as_click_command(name="configure-decisions")(
    click.option("--enable", is_flag=True, help="Enable auto-decisions"),
    click.option("--disable", is_flag=True, help="Disable auto-decisions"),
    click.option("--approve-threshold", type=int, help="Max risk score for auto-approve (0-100)"),
    click.option("--reject-threshold", type=int, help="Min risk score for auto-reject (0-100)"),
    click.option("--confidence", type=float, help="Base confidence threshold (0.0-1.0)"),
    click.option("--show", is_flag=True, help="Show current decision rules"),
    click.option("--stats", is_flag=True, help="Show today's decision stats"),
)
