"""thothctl workflow devsecops — composite DevSecOps SDLC command."""
import logging
import time

import click
import rich.box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from ....core.commands import ClickCommand
from ....services.workflow.models import Phase, PhaseResult, StepStatus
from ....services.workflow.workflow_service import WorkflowService, COMPOSITE_PHASES, PHASE_ORDER


logger = logging.getLogger(__name__)

# Phase icons for display
PHASE_ICONS = {
    Phase.PLAN: "📋",
    Phase.DEVELOP: "💻",
    Phase.BUILD: "🔨",
    Phase.TEST: "✅",
    Phase.SECURE: "🔒",
    Phase.DEPLOY: "🚀",
    Phase.MONITOR: "📊",
}


class DevSecOpsWorkflowCommand(ClickCommand):
    """Execute DevSecOps SDLC phases."""

    def _execute(self, phase: str, reports_dir: str, enforcement: str, **kwargs):
        console = Console()
        service = WorkflowService()

        # Resolve phase
        selected_phase = Phase(phase)

        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY", ".")

        # Build options from kwargs
        options = {}
        if kwargs.get("policy_dir"):
            options["policy_dir"] = kwargs["policy_dir"]
        if kwargs.get("tools"):
            options["tools"] = list(kwargs["tools"])

        # Header
        console.print(Panel(
            f"[bold]DevSecOps Workflow[/bold]\n\n"
            f"Phase: [cyan]{phase}[/cyan]\n"
            f"Directory: [cyan]{directory}[/cyan]\n"
            f"Enforcement: [{'red' if enforcement == 'hard' else 'green'}]{enforcement}[/]",
            title="[bold blue]ThothCTL Workflow[/bold blue]",
            border_style="blue",
        ))

        # Resolve which phases will run
        phases_to_run = self._resolve_phases(selected_phase, service)

        # Execute with live progress
        start = time.perf_counter()
        result = self._execute_with_progress(
            console, service, [selected_phase], directory, reports_dir, options, enforcement, phases_to_run
        )
        total_time = time.perf_counter() - start

        # Display final results
        self._display_results(console, result, total_time)

        if result.stopped_at:
            console.print(Panel(
                f"[bold red]Pipeline blocked at phase: {result.stopped_at.value}[/bold red]\n\n"
                f"Resolve {result.total_findings} finding(s) before deployment.\n"
                f"Use [bold]--enforcement soft[/bold] to report without blocking.",
                title="[bold red]\u26d4 Enforcement Failed[/bold red]",
                border_style="red",
            ))
            raise SystemExit(1)

    def _resolve_phases(self, phase: Phase, service: WorkflowService) -> list:
        """Resolve composite phases into ordered list."""
        if phase in COMPOSITE_PHASES:
            resolved = COMPOSITE_PHASES[phase]
        else:
            resolved = [phase]

        # Filter to only phases that have executors
        return [p for p in resolved if p in service._executors]

    def _execute_with_progress(
        self, console, service, phases, directory, reports_dir, options, enforcement, phases_to_run
    ):
        """Execute workflow with live spinner showing current phase."""
        from ....services.workflow.models import WorkflowResult

        options = options or {}
        options["enforcement"] = enforcement
        result = WorkflowResult(enforcement=enforcement)

        total_phases = len(phases_to_run)

        for idx, phase in enumerate(phases_to_run, 1):
            executor = service._executors.get(phase)
            if not executor:
                continue

            icon = PHASE_ICONS.get(phase, "⚙️")
            phase_name = phase.value.capitalize()

            # Show spinner while phase runs
            with console.status(
                f"[bold blue]{icon} Running phase {idx}/{total_phases}: {phase_name}[/bold blue]  "
                f"[dim]({executor.description})[/dim]",
                spinner="dots",
                spinner_style="cyan",
            ):
                phase_result = executor.execute(directory, reports_dir, options)

            # Show immediate result after phase completes
            if phase_result.total_findings > 0:
                console.print(
                    f"  {icon} [bold]{phase_name}[/bold] — "
                    f"[red]{phase_result.total_findings} finding(s)[/red]"
                )
            elif any(s.status == StepStatus.SKIPPED for s in phase_result.steps):
                console.print(
                    f"  {icon} [bold]{phase_name}[/bold] — "
                    f"[dim]skipped (prerequisites missing)[/dim]"
                )
            else:
                console.print(
                    f"  {icon} [bold]{phase_name}[/bold] — "
                    f"[green]passed[/green]"
                )

            result.phases.append(phase_result)

            # Stop on hard enforcement failure
            if enforcement == "hard" and phase_result.gate_blocked:
                result.stopped_at = phase
                break

        console.print()  # Blank line before results table
        return result

    def _display_results(self, console: Console, result, total_time: float):
        """Render workflow results."""
        table = Table(
            title="[bold]Workflow Results[/bold]",
            box=rich.box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Phase", style="cyan")
        table.add_column("Step", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Findings", justify="center")
        table.add_column("Duration", justify="right", style="dim")
        table.add_column("Summary")

        status_icons = {
            StepStatus.PASSED: "[green]\u2705 PASS[/green]",
            StepStatus.FAILED: "[red]\u274c FAIL[/red]",
            StepStatus.SKIPPED: "[dim]\u23ed SKIP[/dim]",
            StepStatus.WARNING: "[yellow]\u26a0\ufe0f  WARN[/yellow]",
        }

        for phase_result in result.phases:
            for i, step in enumerate(phase_result.steps):
                phase_label = phase_result.phase.value if i == 0 else ""
                table.add_row(
                    phase_label,
                    step.name,
                    status_icons.get(step.status, "?"),
                    str(step.findings_count) if step.findings_count > 0 else "-",
                    f"{step.duration_seconds:.1f}s",
                    step.summary,
                )
            if phase_result.steps:
                table.add_section()

        console.print(table)

        # Summary
        status_color = "green" if result.passed else "red"
        status_text = "\u2705 All phases passed" if result.passed else f"\u274c {result.total_findings} finding(s) detected"
        console.print(Panel(
            f"[bold {status_color}]{status_text}[/bold {status_color}]\n\n"
            f"\u23f1\ufe0f  Total time: [cyan]{total_time:.1f}s[/cyan]\n"
            f"Phases executed: [cyan]{len(result.phases)}[/cyan]",
            title="[bold green]Workflow Complete[/bold green]" if result.passed else "[bold red]Workflow Complete[/bold red]",
            border_style=status_color,
        ))


# Click wiring
cli = DevSecOpsWorkflowCommand.as_click_command(
    help="Execute DevSecOps SDLC workflow phases."
)(
    click.option(
        "--phase", "-p",
        type=click.Choice([p.value for p in Phase]),
        default="all",
        help="SDLC phase to execute (default: all)",
    ),
    click.option(
        "--reports-dir", "-r",
        default="Reports",
        help="Directory to save reports",
    ),
    click.option(
        "--enforcement",
        type=click.Choice(["soft", "hard"]),
        default="soft",
        help="Enforcement mode: soft (report) or hard (block on violations)",
    ),
    click.option(
        "--policy-dir",
        default=None,
        help="OPA policy directory or Git URL for secure phase",
    ),
    click.option(
        "--tools", "-t",
        multiple=True,
        default=None,
        help="Override scan tools for secure phase (e.g., -t checkov -t trivy)",
    ),
)
