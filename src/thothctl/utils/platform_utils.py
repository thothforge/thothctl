"""Platform-specific utility functions for cross-platform compatibility."""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def get_executable_name(tool: str) -> str:
    """Get platform-specific executable name."""
    if is_windows():
        return f"{tool}.exe"
    return tool


def find_executable(tool: str) -> Optional[str]:
    """Find executable in PATH with platform-specific handling."""
    executable_name = get_executable_name(tool)
    return shutil.which(executable_name)


def run_command(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run command with platform-specific handling."""
    if is_windows():
        # On Windows, use shell=True for better PATH resolution
        return subprocess.run(cmd, shell=True, **kwargs)
    else:
        return subprocess.run(cmd, **kwargs)


def get_config_dir() -> Path:
    """Get platform-specific configuration directory."""
    if is_windows():
        return Path.home() / "AppData" / "Local" / "thothctl"
    else:
        return Path.home() / ".thothcf"


def get_shell_config_file() -> Path:
    """Get platform-specific shell configuration file."""
    if is_windows():
        # PowerShell profile
        return Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    else:
        # Default to bash on Unix systems
        return Path.home() / ".bashrc"


def get_temp_dir() -> Path:
    """Get platform-specific temporary directory."""
    if is_windows():
        return Path.home() / "AppData" / "Local" / "Temp" / "thothctl"
    else:
        return Path("/tmp") / "thothctl"


def normalize_path(path: str) -> Path:
    """Normalize path for current platform."""
    return Path(path).resolve()
