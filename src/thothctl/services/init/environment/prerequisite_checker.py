"""Prerequisite checker — validates runtime dependencies without installing them.

Detects version managers (nvm, fnm, volta, pyenv, asdf) and provides
actionable hints when prerequisites are missing or outdated.
"""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from .tool_packs import Prerequisite

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class PrerequisiteResult:
    """Result of checking a single prerequisite."""

    name: str
    is_met: bool
    current_version: Optional[str] = None
    min_version: Optional[str] = None
    message: str = ""
    version_manager_detected: Optional[str] = None


def check_prerequisites(prerequisites: List[Prerequisite]) -> List[PrerequisiteResult]:
    """Check all prerequisites and return results.

    Never installs anything — only checks and reports.
    """
    results = []
    for prereq in prerequisites:
        result = _check_single_prerequisite(prereq)
        results.append(result)
    return results


def display_prerequisite_results(results: List[PrerequisiteResult]) -> bool:
    """Display prerequisite check results in a Rich table.

    Returns True if all prerequisites are met, False otherwise.
    """
    all_met = all(r.is_met for r in results)

    if not results:
        return True

    table = Table(
        title="🔍 Prerequisite Check",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Prerequisite", style="cyan", width=12)
    table.add_column("Status", width=12)
    table.add_column("Current", width=12)
    table.add_column("Required", width=12)
    table.add_column("Details", style="dim")

    for r in results:
        if r.is_met:
            status = "✅ OK"
            details = ""
            if r.version_manager_detected:
                details = f"via {r.version_manager_detected}"
        else:
            status = "❌ Missing"
            details = r.message[:50] if r.message else ""

        table.add_row(
            r.name,
            status,
            r.current_version or "—",
            r.min_version or "any",
            details,
        )

    console.print(table)

    if not all_met:
        console.print()
        console.print("[bold yellow]⚠️  Some prerequisites are not met:[/bold yellow]")
        for r in results:
            if not r.is_met:
                console.print(f"\n[bold red]{r.name}[/bold red]:")
                console.print(f"  {r.message}")
        console.print()

    return all_met


def _check_single_prerequisite(prereq: Prerequisite) -> PrerequisiteResult:
    """Check a single prerequisite."""
    # Check if the tool is available
    executable = shutil.which(prereq.name)
    if not executable and prereq.check_command:
        # Try the check command directly
        cmd_name = prereq.check_command.split()[0]
        executable = shutil.which(cmd_name)

    if not executable:
        # Check for version managers that might provide it
        vm_detected = _detect_version_manager(prereq.version_managers)
        hint = prereq.install_hint
        if vm_detected:
            hint = f"Detected '{vm_detected}' but {prereq.name} not active. {hint}"

        return PrerequisiteResult(
            name=prereq.name,
            is_met=False,
            min_version=prereq.min_version,
            message=hint,
            version_manager_detected=vm_detected,
        )

    # Tool exists — check version if required
    current_version = _get_version(prereq.check_command)
    vm_detected = _detect_version_manager(prereq.version_managers)

    if prereq.min_version and current_version:
        if not _version_satisfies(current_version, prereq.min_version):
            return PrerequisiteResult(
                name=prereq.name,
                is_met=False,
                current_version=current_version,
                min_version=prereq.min_version,
                message=(
                    f"Version {current_version} is below minimum {prereq.min_version}. "
                    f"{prereq.install_hint}"
                ),
                version_manager_detected=vm_detected,
            )

    return PrerequisiteResult(
        name=prereq.name,
        is_met=True,
        current_version=current_version,
        min_version=prereq.min_version,
        version_manager_detected=vm_detected,
    )


def _get_version(check_command: str) -> Optional[str]:
    """Run a version command and extract the version number."""
    if not check_command:
        return None

    try:
        result = subprocess.run(
            check_command.split(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # Extract version pattern (e.g., v18.17.0 → 18.17.0)
            match = re.search(r"v?(\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
            # Fallback: first line
            return output.split("\n")[0][:20]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


def _detect_version_manager(managers: List[str]) -> Optional[str]:
    """Detect if any version manager is installed."""
    for vm in managers:
        if shutil.which(vm):
            return vm
    return None


def _version_satisfies(current: str, minimum: str) -> bool:
    """Check if current version satisfies minimum requirement."""
    try:
        current_parts = [int(x) for x in current.split(".")[:3]]
        minimum_parts = [int(x) for x in minimum.split(".")[:3]]

        # Pad to 3 parts
        while len(current_parts) < 3:
            current_parts.append(0)
        while len(minimum_parts) < 3:
            minimum_parts.append(0)

        return tuple(current_parts) >= tuple(minimum_parts)
    except (ValueError, AttributeError):
        # Can't parse — assume it's fine
        return True
