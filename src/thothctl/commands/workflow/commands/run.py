"""Run a custom workflow from YAML definition."""

from pathlib import Path

import click

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.workflow.custom_workflow_engine import (
    CustomWorkflowEngine,
    WorkflowValidationError,
)


class WorkflowRunCommand(ClickCommand):
    """Command to run a custom YAML workflow."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.engine = CustomWorkflowEngine()

    def _execute(self, file: str, dry_run: bool = False, **kwargs) -> None:
        """Execute the workflow."""
        workflow_path = Path(file)

        try:
            workflow = self.engine.load(workflow_path)
        except WorkflowValidationError as e:
            self.ui.print_error(f"Workflow validation failed: {e}")
            return

        if dry_run:
            self.engine.show_plan(workflow)
        else:
            results = self.engine.execute(workflow)
            # Exit with error if any stage failed
            failed = any(r.status.value == "failed" for r in results)
            if failed:
                raise SystemExit(1)


cli = WorkflowRunCommand.as_click_command(
    help="Run a custom workflow from YAML definition"
)(
    click.option(
        "-f",
        "--file",
        default=".thothcf_workflow.yaml",
        type=click.Path(),
        help="Path to workflow YAML file (default: .thothcf_workflow.yaml)",
    ),
    click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Show execution plan without running",
    ),
)
