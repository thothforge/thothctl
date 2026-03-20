"""Override command — manually override an AI decision."""
import json
import logging
import time
from datetime import date
from pathlib import Path

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI

logger = logging.getLogger(__name__)

ACTIONS_LOG_DIR = ".thothctl/ai_decisions"


class OverrideCommand(ClickCommand):
    """Manually override an AI decision for a PR."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        if not kwargs.get("repository") or not kwargs.get("pr_number"):
            self.ui.print_error("Both --repository and --pr-number are required")
            return False
        return True

    def _execute(self, repository, pr_number, action, reason="", publish=False,
                 platform="auto", **kwargs):
        record = {
            "timestamp": time.time(),
            "action": f"override_{action}",
            "repository": repository,
            "pr_id": str(pr_number),
            "confidence": 1.0,
            "reason": f"Manual override: {reason}" if reason else "Manual override",
        }

        # Persist
        log_dir = Path(ACTIONS_LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{date.today().isoformat()}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

        self.ui.print_success(
            f"Override recorded: {action.upper()} for {repository}#{pr_number}"
        )

        if publish:
            from ....services.ai_review.pr_decision_publisher import PRDecisionPublisher
            from ....services.ai_review.decision_engine import Decision, DecisionResult

            result = DecisionResult(
                decision=Decision(action),
                confidence=1.0,
                risk_score=0,
                reason=record["reason"],
                findings_summary={"critical": 0, "high": 0, "medium": 0, "low": 0},
            )
            publisher = PRDecisionPublisher(platform=platform)
            with self.ui.status_spinner("Publishing override to PR..."):
                pub = publisher.publish(result, {}, repository, str(pr_number))

            if pub.get("error"):
                self.ui.print_error(f"Failed to publish: {pub['error']}")
            else:
                self.ui.print_success("Override published to PR")
        else:
            self.ui.print_info("Use --publish to also post the override to the PR.")


cli = OverrideCommand.as_click_command(name="override")(
    click.option("--repository", required=True, help="Repository (owner/repo)"),
    click.option("--pr-number", required=True, type=int, help="PR number"),
    click.option("--action", required=True,
                 type=click.Choice(["approve", "reject", "request_changes", "comment"]),
                 help="Decision to apply"),
    click.option("--reason", default="", help="Reason for override"),
    click.option("--publish", is_flag=True, help="Also publish override to the PR"),
    click.option("--platform", type=click.Choice(["github", "azure_devops", "auto"]),
                 default="auto", help="VCS platform"),
)
