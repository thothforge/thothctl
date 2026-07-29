"""Composable YAML workflow engine — custom DAG pipelines for ThothCTL commands."""

import logging
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNED = "warned"


class FailureAction(Enum):
    BLOCK = "block"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class StageResult:
    name: str
    status: StageStatus
    duration_seconds: float = 0.0
    output: str = ""
    error: str = ""


@dataclass
class CustomStage:
    name: str
    command: str
    args: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    on_failure: FailureAction = FailureAction.BLOCK
    condition: Optional[str] = None


@dataclass
class CustomWorkflow:
    name: str
    description: str = ""
    trigger: str = "manual"
    variables: Dict[str, str] = field(default_factory=dict)
    stages: List[CustomStage] = field(default_factory=list)


class WorkflowValidationError(Exception):
    pass


class CustomWorkflowEngine:
    """Parse, validate, and execute custom YAML workflows."""

    def __init__(self):
        self.variable_resolver = VariableResolver()

    def load(self, path: Path) -> CustomWorkflow:
        """Load and validate a workflow from YAML file."""
        if not path.exists():
            raise WorkflowValidationError(f"Workflow file not found: {path}")

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise WorkflowValidationError(f"Invalid YAML: {e}")

        if not data or not isinstance(data, dict):
            raise WorkflowValidationError("Workflow file is empty or invalid")

        workflow = self._parse_workflow(data)
        self._validate_workflow(workflow)
        return workflow

    def execute(self, workflow: CustomWorkflow) -> List[StageResult]:
        """Execute workflow stages in topological order."""
        order = self._topological_sort(workflow.stages)
        results: Dict[str, StageResult] = {}
        blocked = False

        console.print(
            Panel(
                f"[bold]{workflow.name}[/bold]\n{workflow.description}",
                title="▶️ Executing Workflow",
                border_style="green",
            )
        )

        for stage_name in order:
            stage = next(s for s in workflow.stages if s.name == stage_name)

            # Check if blocked by previous failure
            if blocked:
                results[stage_name] = StageResult(
                    name=stage_name, status=StageStatus.SKIPPED
                )
                continue

            # Check dependencies succeeded
            deps_ok = all(
                results.get(
                    dep, StageResult(name=dep, status=StageStatus.FAILED)
                ).status
                in (StageStatus.SUCCESS, StageStatus.WARNED)
                for dep in stage.depends_on
            )
            if not deps_ok:
                results[stage_name] = StageResult(
                    name=stage_name, status=StageStatus.SKIPPED
                )
                continue

            # Execute stage
            console.print(f"\n[bold cyan]▶ {stage_name}[/bold cyan]: {stage.command}")
            result = self._run_stage(stage, workflow.variables)
            results[stage_name] = result

            # Handle failure
            if result.status == StageStatus.FAILED:
                if stage.on_failure == FailureAction.BLOCK:
                    console.print("  [red]✘ BLOCKED[/red] — pipeline stopped")
                    blocked = True
                elif stage.on_failure == FailureAction.WARN:
                    result.status = StageStatus.WARNED
                    console.print("  [yellow]⚠ WARNING[/yellow] — continuing")
                elif stage.on_failure == FailureAction.SKIP:
                    result.status = StageStatus.SKIPPED
                    console.print("  [dim]⏭ SKIPPED[/dim]")
            else:
                console.print(
                    f"  [green]✔ SUCCESS[/green] ({result.duration_seconds:.1f}s)"
                )

        self._render_summary(list(results.values()))
        return list(results.values())

    def show_plan(self, workflow: CustomWorkflow) -> None:
        """Show execution plan without running (dry-run)."""
        order = self._topological_sort(workflow.stages)

        console.print(
            Panel(
                f"[bold]{workflow.name}[/bold]\n{workflow.description}",
                title="📋 Workflow Plan (dry-run)",
                border_style="yellow",
            )
        )

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", width=3)
        table.add_column("Stage")
        table.add_column("Command")
        table.add_column("Depends On")
        table.add_column("On Failure")

        for i, stage_name in enumerate(order, 1):
            stage = next(s for s in workflow.stages if s.name == stage_name)
            cmd_str = self._build_command_string(stage)
            deps = ", ".join(stage.depends_on) if stage.depends_on else "—"
            table.add_row(str(i), stage.name, cmd_str, deps, stage.on_failure.value)

        console.print(table)

    def _parse_workflow(self, data: Dict) -> CustomWorkflow:
        """Parse raw YAML dict into CustomWorkflow model."""
        stages = []
        for stage_data in data.get("stages", []):
            on_failure_str = stage_data.get("on_failure", "block")
            try:
                on_failure = FailureAction(on_failure_str)
            except ValueError:
                on_failure = FailureAction.BLOCK

            stages.append(
                CustomStage(
                    name=stage_data["name"],
                    command=stage_data["command"],
                    args=stage_data.get("args", {}),
                    depends_on=stage_data.get("depends_on", []),
                    on_failure=on_failure,
                    condition=stage_data.get("condition"),
                )
            )

        return CustomWorkflow(
            name=data.get("name", "Unnamed Workflow"),
            description=data.get("description", ""),
            trigger=data.get("trigger", "manual"),
            variables=data.get("variables", {}),
            stages=stages,
        )

    def _validate_workflow(self, workflow: CustomWorkflow) -> None:
        """Validate workflow structure."""
        stage_names = {s.name for s in workflow.stages}

        # Check for duplicate names
        if len(stage_names) != len(workflow.stages):
            raise WorkflowValidationError("Duplicate stage names found")

        # Check depends_on references exist
        for stage in workflow.stages:
            for dep in stage.depends_on:
                if dep not in stage_names:
                    raise WorkflowValidationError(
                        f"Stage '{stage.name}' depends on '{dep}' which doesn't exist"
                    )

        # Check for cycles
        self._topological_sort(workflow.stages)  # Raises on cycle

    def _topological_sort(self, stages: List[CustomStage]) -> List[str]:
        """Kahn's algorithm for DAG ordering. Raises on cycles."""
        in_degree = {s.name: 0 for s in stages}
        graph = {s.name: [] for s in stages}

        for stage in stages:
            for dep in stage.depends_on:
                graph[dep].append(stage.name)
                in_degree[stage.name] += 1

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(stages):
            raise WorkflowValidationError(
                "Circular dependency detected in workflow stages"
            )

        return order

    def _run_stage(self, stage: CustomStage, variables: Dict[str, str]) -> StageResult:
        """Execute a single stage by invoking thothctl as subprocess."""
        cmd_str = self._build_command_string(stage)
        resolved_cmd = self.variable_resolver.resolve_string(cmd_str, variables)

        start = time.time()
        try:
            result = subprocess.run(
                resolved_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            duration = time.time() - start

            if result.returncode == 0:
                return StageResult(
                    name=stage.name,
                    status=StageStatus.SUCCESS,
                    duration_seconds=duration,
                    output=result.stdout,
                )
            else:
                return StageResult(
                    name=stage.name,
                    status=StageStatus.FAILED,
                    duration_seconds=duration,
                    output=result.stdout,
                    error=result.stderr,
                )
        except subprocess.TimeoutExpired:
            return StageResult(
                name=stage.name,
                status=StageStatus.FAILED,
                duration_seconds=300.0,
                error="Stage timed out (300s limit)",
            )
        except Exception as e:
            return StageResult(
                name=stage.name,
                status=StageStatus.FAILED,
                duration_seconds=time.time() - start,
                error=str(e),
            )

    def _build_command_string(self, stage: CustomStage) -> str:
        """Build the thothctl command string from stage definition."""
        parts = ["thothctl", stage.command]
        for key, value in stage.args.items():
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    parts.append(flag)
            elif isinstance(value, list):
                for item in value:
                    parts.extend([flag, str(item)])
            else:
                parts.extend([flag, str(value)])
        return " ".join(parts)

    def _render_summary(self, results: List[StageResult]) -> None:
        """Render execution summary table."""
        console.print()
        table = Table(
            title="📊 Workflow Summary", show_header=True, header_style="bold"
        )
        table.add_column("Stage")
        table.add_column("Status")
        table.add_column("Duration")

        status_icons = {
            StageStatus.SUCCESS: "[green]✔ Success[/green]",
            StageStatus.FAILED: "[red]✘ Failed[/red]",
            StageStatus.SKIPPED: "[dim]⏭ Skipped[/dim]",
            StageStatus.WARNED: "[yellow]⚠ Warning[/yellow]",
        }

        for r in results:
            table.add_row(
                r.name,
                status_icons.get(r.status, str(r.status)),
                f"{r.duration_seconds:.1f}s" if r.duration_seconds > 0 else "—",
            )

        console.print(table)

        # Overall status
        failed = sum(1 for r in results if r.status == StageStatus.FAILED)
        if failed:
            console.print(f"\n[red]✘ Workflow failed ({failed} stage(s) failed)[/red]")
        else:
            console.print("\n[green]✔ Workflow completed successfully[/green]")


class VariableResolver:
    """Resolve {{variable}} placeholders in command strings."""

    def resolve_string(self, text: str, variables: Dict[str, str]) -> str:
        """Replace {{var}} placeholders with resolved values."""
        import re

        def replace_match(match):
            var_name = match.group(1).strip()
            # Check user-defined variables first
            if var_name in variables:
                return variables[var_name]
            # Built-in resolvers
            return self._resolve_builtin(var_name)

        return re.sub(r"\{\{\s*(.+?)\s*\}\}", replace_match, text)

    def _resolve_builtin(self, var_name: str) -> str:
        """Resolve built-in variables."""
        if var_name == "changed_stacks":
            return self._get_changed_stacks()
        elif var_name == "branch":
            return self._get_branch()
        elif var_name == "project":
            return Path.cwd().name
        elif var_name == "space":
            return self._get_active_space()
        return f"{{{{{var_name}}}}}"  # Return unresolved

    def _get_changed_stacks(self) -> str:
        """Get directories with changes from git diff."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                dirs = set()
                for line in result.stdout.strip().splitlines():
                    parts = Path(line).parts
                    if len(parts) > 1:
                        dirs.add(parts[0])
                return " ".join(sorted(dirs)) if dirs else "."
        except Exception:
            pass
        return "."

    def _get_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def _get_active_space(self) -> str:
        """Get active ThothCTL space."""
        active_file = Path.home() / ".thothcf" / "active_space"
        if active_file.exists():
            return active_file.read_text(encoding="utf-8").strip()
        return ""
