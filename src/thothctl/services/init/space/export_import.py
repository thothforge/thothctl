"""Space export/import service for sharing configurations across teams."""

import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import toml

from ....version import __version__

logger = logging.getLogger(__name__)

# Keys that contain credential-related data and should be stripped on export
CREDENTIAL_KEYS = {
    "token",
    "secret",
    "password",
    "api_key",
    "access_key",
    "private_key",
    "credentials",
}


def _strip_credentials(data: dict) -> dict:
    """Recursively strip credential-related keys from a dict."""
    cleaned = {}
    for key, value in data.items():
        if key.lower() in CREDENTIAL_KEYS:
            continue
        if isinstance(value, dict):
            cleaned[key] = _strip_credentials(value)
        else:
            cleaned[key] = value
    return cleaned


def export_space(space_name: str, output_path: Optional[str] = None) -> Path:
    """
    Export a space configuration for sharing across teams.

    :param space_name: Name of the space to export
    :param output_path: Optional output file path (default: <space_name>.space.toml in CWD)
    :return: Path to the exported file
    """
    config_path = Path.home() / ".thothcf" / "spaces.toml"

    if not config_path.exists():
        raise ValueError("No spaces configuration found")

    with open(config_path, mode="rt", encoding="utf-8") as fp:
        config = toml.load(fp)

    if "spaces" not in config or space_name not in config["spaces"]:
        raise ValueError(f"Space '{space_name}' does not exist")

    space_config = config["spaces"][space_name]

    # Build export dict
    export_data = {
        "meta": {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "thothctl_version": __version__,
            "source_space": space_name,
        },
        "space": _strip_credentials(space_config),
    }

    # Determine output path
    if output_path:
        dest = Path(output_path)
    else:
        dest = Path.cwd() / f"{space_name}.space.toml"

    # Ensure parent directory exists
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, mode="wt", encoding="utf-8") as fp:
        toml.dump(export_data, fp)

    logger.info("Exported space '%s' to %s", space_name, dest)
    return dest


def import_space(source: str, space_name: Optional[str] = None) -> str:
    """
    Import a space configuration from a file or git URL.

    :param source: Local file path (.toml) or git URL
    :param space_name: Optional override for the space name
    :return: Name of the created space
    """
    export_data = _load_source(source)

    # Validate schema version
    meta = export_data.get("meta", {})
    if meta.get("schema_version") != "1.0":
        raise ValueError(
            f"Unsupported schema version: {meta.get('schema_version', 'missing')}. "
            "Expected '1.0'."
        )

    # Extract space config
    space_config = export_data.get("space")
    if not space_config:
        raise ValueError("Export file is missing [space] section")

    # Determine space name
    name = space_name or meta.get("source_space")
    if not name:
        raise ValueError(
            "Cannot determine space name. Provide --name or ensure export has meta.source_space."
        )

    # Check if space already exists
    config_path = Path.home() / ".thothcf" / "spaces.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)
    else:
        config = {"spaces": {}}

    if "spaces" not in config:
        config["spaces"] = {}

    if name in config["spaces"]:
        raise ValueError(
            f"Space '{name}' already exists. Use a different name with --name."
        )

    # Update the name field in the config to match the target name
    space_config["name"] = name

    # Write to spaces.toml
    config["spaces"][name] = space_config
    with open(config_path, mode="wt", encoding="utf-8") as fp:
        toml.dump(config, fp)

    # Create directory structure
    space_dir = Path.home() / ".thothcf" / "spaces" / name
    space_dir.mkdir(parents=True, exist_ok=True)
    (space_dir / "credentials").mkdir(exist_ok=True)
    (space_dir / "configs").mkdir(exist_ok=True)
    (space_dir / "vcs").mkdir(exist_ok=True)
    (space_dir / "terraform").mkdir(exist_ok=True)
    (space_dir / "orchestration").mkdir(exist_ok=True)

    logger.info("Imported space '%s' from %s", name, source)
    return name


def _load_source(source: str) -> dict:
    """
    Load export data from a local file or git URL.

    :param source: Local .toml path or git URL
    :return: Parsed export dict
    """
    # Check if it's a local file
    source_path = Path(source)
    if source_path.exists() and source_path.suffix == ".toml":
        with open(source_path, mode="rt", encoding="utf-8") as fp:
            return toml.load(fp)

    # Try as a git URL
    try:
        import git
    except ImportError:
        raise ImportError(
            "GitPython is required for importing from git URLs. "
            "Install it with: pip install gitpython"
        )

    tmpdir = tempfile.mkdtemp(prefix="thothctl-space-import-")
    try:
        git.Repo.clone_from(source, tmpdir, depth=1)

        # Look for space export files
        tmp_path = Path(tmpdir)
        candidates = list(tmp_path.glob("*.space.toml"))
        if not candidates:
            candidates = [tmp_path / "space-export.toml"]

        for candidate in candidates:
            if candidate.exists():
                with open(candidate, mode="rt", encoding="utf-8") as fp:
                    return toml.load(fp)

        raise FileNotFoundError(
            f"No *.space.toml or space-export.toml found in repository: {source}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
