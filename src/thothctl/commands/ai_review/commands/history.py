"""History command — view past AI decision records."""
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import click
from rich.table import Table

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI

logger = logging.getLogger(__name__)

ACTIONS_LOG_DIR = ".thothctl/ai_decisions"


class HistoryCommand(ClickCommand):
    """View AI decision history."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, days=7, repository=None, action=None, json_output=False, **kwargs):
        log_dir = Path(ACTIONS_LOG_DIR)
        if not log_dir.exists():
            self.ui.print_warning("No decision history found.")
            return

        records = []
        for i in range(days):
            d = date.today() - timedelta(days=i)
            log_file = log_dir / f"{d.isoformat()}.jsonl"
            if log_file.exists():
                for line in log_file.read_text().strip().split("\n"):
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        if repository and r.get("repository") != repository:
                            continue
                        if action and r.get("action") != action:
                            continue
                        records.append(r)
                    except json.JSONDecodeError:
                        continue

        if not records:
            self.ui.print_warning(f"No decisions in the last {days} day(s).")
            return

        if json_output:
            click.echo(json.dumps(records, indent=2))
            return

        table = Table(title=f"AI Decision History (last {days} days)")
        table.add_column("Time", style="dim")
        table.add_column("Action", style="cyan")
        table.add_column("Repository")
        table.add_column("PR")
        table.add_column("Confidence", style="green")
        table.add_column("Reason", max_width=40)

        from datetime import datetime
        for r in sorted(records, key=lambda x: x["timestamp"], reverse=True):
            ts = datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M")
            action_style = {"approve": "green", "reject": "red",
                            "request_changes": "yellow"}.get(r["action"], "white")
            table.add_row(
                ts,
                f"[{action_style}]{r['action']}[/{action_style}]",
                r.get("repository", ""),
                r.get("pr_id", ""),
                f"{r.get('confidence', 0):.0%}",
                r.get("reason", "")[:40],
            )

        self.ui.console.print(table)
        self.ui.print_info(f"Total: {len(records)} decisions")


cli = HistoryCommand.as_click_command(name="history")(
    click.option("--days", type=int, default=7, help="Number of days to look back"),
    click.option("--repository", help="Filter by repository"),
    click.option("--action", type=click.Choice(["approve", "reject", "request_changes", "comment"]),
                 help="Filter by action type"),
    click.option("--json", "json_output", is_flag=True, help="Output as JSON"),
)
