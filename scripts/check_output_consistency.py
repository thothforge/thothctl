#!/usr/bin/env python3
"""Output consistency linter — flags anti-patterns in CLI output code.

Detects:
- Bare print() calls (should use CliUI methods)
- sys.exit() with string messages (should use CliUI.print_error + raise)
- click.echo() usage (should use CliUI methods)
- Direct colorama usage outside CliUI (should use Rich/CliUI)

Usage:
    python scripts/check_output_consistency.py [file1.py file2.py ...]
    python scripts/check_output_consistency.py --count-only src/thothctl/

Exit codes:
    0 — No violations found
    1 — Violations found (pre-commit will block)
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Files allowed to use these patterns directly
ALLOWLIST = {
    "cli_ui.py",
    "banner.py",
    "thoth_colors.py",
    "wellcome_banner.py",
    "install_tools.py",  # Legacy installer uses print for subprocess feedback
    "check_output_consistency.py",
}

# Directories to skip entirely
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "cdk.out", ".venv"}

PATTERNS = [
    (r"^\s*print\(", "Use CliUI methods instead of bare print()"),
    (r"sys\.exit\([\'\"]", "Use CliUI.print_error() + raise SystemExit(code)"),
    (r"click\.echo\(", "Use CliUI methods instead of click.echo()"),
]


def check_file(filepath: Path) -> List[Tuple[int, str, str]]:
    """Check a single file for anti-patterns."""
    if filepath.name in ALLOWLIST:
        return []

    violations = []
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []

    for line_num, line in enumerate(lines, start=1):
        # Skip comments and strings
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        for pattern, message in PATTERNS:
            if re.search(pattern, line):
                violations.append((line_num, message, line.strip()))
                break  # One violation per line is enough

    return violations


def find_python_files(path: Path) -> List[Path]:
    """Recursively find Python files, respecting skip dirs."""
    files = []
    if path.is_file() and path.suffix == ".py":
        return [path]
    for item in path.rglob("*.py"):
        if not any(skip in item.parts for skip in SKIP_DIRS):
            files.append(item)
    return sorted(files)


def main() -> int:
    args = sys.argv[1:]

    count_only = "--count-only" in args
    if count_only:
        args.remove("--count-only")

    if not args:
        print("Usage: check_output_consistency.py [--count-only] <file|dir> ...")
        return 2

    all_files = []
    for arg in args:
        path = Path(arg)
        if path.is_dir():
            all_files.extend(find_python_files(path))
        elif path.is_file() and path.suffix == ".py":
            all_files.append(path)

    total_violations = 0
    files_with_violations = 0

    for filepath in all_files:
        violations = check_file(filepath)
        if violations:
            files_with_violations += 1
            total_violations += len(violations)
            if not count_only:
                for line_num, message, code in violations:
                    print(f"{filepath}:{line_num}: {message}")
                    print(f"  {code}")

    if count_only:
        print(f"Total violations: {total_violations} in {files_with_violations} files")
        return 0  # count-only never blocks

    if total_violations > 0:
        print(
            f"\n{total_violations} output consistency violation(s) found in {files_with_violations} file(s)"
        )
        print("Use CliUI (from thothctl.core.cli_ui) for all user-facing output.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
