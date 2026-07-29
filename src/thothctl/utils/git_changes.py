"""Git-based change detection for scoping operations to modified directories."""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_changed_directories(
    base_ref: str = "HEAD~1",
    working_dir: Optional[str] = None,
) -> List[str]:
    """Get directories with changed IaC files since base_ref.

    Returns list of relative directory paths containing changes.
    Filters to IaC-relevant file extensions.
    """
    iac_extensions = {".tf", ".hcl", ".ts", ".py", ".json", ".yaml", ".yml", ".toml"}

    try:
        cmd = ["git", "diff", "--name-only", base_ref]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=working_dir,
        )
        if result.returncode != 0:
            # Fallback: try against main/master
            for fallback in ["main", "master", "HEAD"]:
                result = subprocess.run(
                    ["git", "diff", "--name-only", fallback],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=working_dir,
                )
                if result.returncode == 0:
                    break
            else:
                logger.warning("Could not determine git changes")
                return ["."]

        changed_files = result.stdout.strip().splitlines()
        dirs = set()
        for f in changed_files:
            path = Path(f)
            if path.suffix in iac_extensions:
                # Use the top-level directory (stack level)
                if len(path.parts) > 1:
                    dirs.add(str(path.parent))
                else:
                    dirs.add(".")

        return sorted(dirs) if dirs else ["."]

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"Git change detection failed: {e}")
        return ["."]
