"""Dependency-Track SBOM publisher — uploads CycloneDX BOMs to a Dependency-Track instance.

Supports:
- Upload BOM via /api/v1/bom endpoint (multipart or base64)
- Auto-create project if it doesn't exist (autoCreate=true)
- Project lookup by name (for UUID-based uploads)
- Configuration via env vars, .thothcf.toml, or CLI flags

Usage:
    thothctl inventory iac --check-versions --publish-sbom dependency-track

Configuration (priority order):
    1. CLI flags (--dtrack-url, --dtrack-api-key)
    2. Environment variables (DTRACK_URL, DTRACK_API_KEY)
    3. .thothcf.toml [integrations.dependency_track] section

API Reference:
    https://docs.dependencytrack.org/usage/cicd/
"""

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default Dependency-Track API version prefix
API_PREFIX = "/api/v1"


@dataclass
class DTrackConfig:
    """Configuration for Dependency-Track connection."""

    url: str = ""
    api_key: str = ""
    project_name: Optional[str] = None
    project_version: str = "latest"
    auto_create: bool = True
    parent_project: Optional[str] = None

    @classmethod
    def from_env(cls) -> "DTrackConfig":
        """Load configuration from environment variables."""
        import os

        return cls(
            url=os.environ.get("DTRACK_URL", ""),
            api_key=os.environ.get("DTRACK_API_KEY", ""),
            project_name=os.environ.get("DTRACK_PROJECT_NAME"),
            project_version=os.environ.get("DTRACK_PROJECT_VERSION", "latest"),
            auto_create=os.environ.get("DTRACK_AUTO_CREATE", "true").lower() == "true",
        )

    @classmethod
    def from_toml(cls, directory: str = ".") -> "DTrackConfig":
        """Load configuration from .thothcf.toml."""
        import os

        config = cls.from_env()

        try:
            import toml

            toml_path = os.path.join(directory, ".thothcf.toml")
            if os.path.exists(toml_path):
                with open(toml_path, "r") as f:
                    data = toml.load(f)
                dtrack = data.get("integrations", {}).get("dependency_track", {})
                if dtrack:
                    # Only override if not already set by env vars
                    if not config.url:
                        config.url = dtrack.get("url", "")
                    if not config.api_key:
                        config.api_key = dtrack.get("api_key", "")
                    if not config.project_name:
                        config.project_name = dtrack.get("project_name")
                    config.project_version = dtrack.get(
                        "project_version", config.project_version
                    )
                    config.auto_create = dtrack.get("auto_create", config.auto_create)
                    config.parent_project = dtrack.get("parent_project")
        except Exception as e:
            logger.debug(f"Could not load .thothcf.toml: {e}")

        return config

    def validate(self) -> None:
        """Validate that required config is present."""
        if not self.url:
            raise ValueError(
                "Dependency-Track URL not configured. "
                "Set DTRACK_URL environment variable or configure in .thothcf.toml:\n"
                "  [integrations.dependency_track]\n"
                '  url = "https://dtrack.example.com"'
            )
        if not self.api_key:
            raise ValueError(
                "Dependency-Track API key not configured. "
                "Set DTRACK_API_KEY environment variable or configure in .thothcf.toml:\n"
                "  [integrations.dependency_track]\n"
                '  api_key = "your-api-key"'
            )

    @property
    def base_url(self) -> str:
        """Get base URL with API prefix, stripping trailing slashes."""
        url = self.url.rstrip("/")
        if not url.endswith(API_PREFIX):
            url += API_PREFIX
        return url


@dataclass
class PublishResult:
    """Result of SBOM publish operation."""

    success: bool
    project_name: str = ""
    project_version: str = ""
    token: str = ""  # DTRACK processing token for async status check
    error: Optional[str] = None
    project_url: Optional[str] = None


class DependencyTrackPublisher:
    """Publishes CycloneDX SBOMs to OWASP Dependency-Track.

    Supports the /api/v1/bom endpoint with:
    - Base64-encoded BOM upload (preferred, supports autoCreate)
    - Project auto-creation when project doesn't exist
    - Project lookup by name for existing projects
    """

    def __init__(self, config: DTrackConfig):
        """Initialize publisher with connection config.

        Args:
            config: Dependency-Track connection configuration.

        Raises:
            ValueError: If required config (url, api_key) is missing.
        """
        config.validate()
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-Api-Key": config.api_key,
                "Accept": "application/json",
            }
        )

    def publish(
        self,
        sbom_path: Path,
        project_name: Optional[str] = None,
        project_version: Optional[str] = None,
    ) -> PublishResult:
        """Publish a CycloneDX SBOM to Dependency-Track.

        Uses the PUT /api/v1/bom endpoint with base64-encoded BOM body.
        This supports autoCreate for projects that don't yet exist.

        Args:
            sbom_path: Path to the CycloneDX JSON file.
            project_name: Override project name (default: from config or SBOM metadata).
            project_version: Override project version (default: from config).

        Returns:
            PublishResult with success status and processing token.
        """
        if not sbom_path.exists():
            return PublishResult(
                success=False,
                error=f"SBOM file not found: {sbom_path}",
            )

        # Read and encode the SBOM
        try:
            sbom_content = sbom_path.read_bytes()
            sbom_b64 = base64.b64encode(sbom_content).decode("utf-8")
        except Exception as e:
            return PublishResult(
                success=False,
                error=f"Failed to read SBOM file: {e}",
            )

        # Resolve project name from args > config > SBOM metadata
        effective_name = project_name or self.config.project_name
        if not effective_name:
            try:
                sbom_data = json.loads(sbom_content)
                effective_name = (
                    sbom_data.get("metadata", {}).get("component", {}).get("name")
                )
            except (json.JSONDecodeError, KeyError):
                pass

        if not effective_name:
            return PublishResult(
                success=False,
                error=(
                    "Project name could not be determined. "
                    "Set --project-name, DTRACK_PROJECT_NAME, or ensure SBOM has metadata.component.name"
                ),
            )

        effective_version = project_version or self.config.project_version

        # Build the PUT request body
        payload = {
            "projectName": effective_name,
            "projectVersion": effective_version,
            "autoCreate": self.config.auto_create,
            "bom": sbom_b64,
        }

        # Include parent project if configured (for hierarchical project structure)
        if self.config.parent_project:
            # Look up parent project UUID
            parent_uuid = self._lookup_project_uuid(self.config.parent_project)
            if parent_uuid:
                payload["parentUUID"] = parent_uuid

        # Upload BOM
        url = f"{self.config.base_url}/bom"
        logger.info(
            f"Publishing SBOM to Dependency-Track: {self.config.url} "
            f"(project: {effective_name}:{effective_version})"
        )

        try:
            response = self._session.put(
                url,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("token", "")
                project_url = (
                    f"{self.config.url.rstrip('/')}/projects/?name={effective_name}"
                )
                logger.info(
                    f"SBOM published successfully. Processing token: {token}"
                )
                return PublishResult(
                    success=True,
                    project_name=effective_name,
                    project_version=effective_version,
                    token=token,
                    project_url=project_url,
                )
            elif response.status_code == 401:
                return PublishResult(
                    success=False,
                    error=(
                        "Authentication failed (401). "
                        "Verify DTRACK_API_KEY has BOM_UPLOAD and "
                        "PROJECT_CREATION_UPLOAD permissions."
                    ),
                )
            elif response.status_code == 403:
                return PublishResult(
                    success=False,
                    error=(
                        "Forbidden (403). API key lacks required permissions. "
                        "Needs: BOM_UPLOAD, PROJECT_CREATION_UPLOAD (if autoCreate=true)."
                    ),
                )
            else:
                body = response.text[:300]
                return PublishResult(
                    success=False,
                    error=f"Upload failed (HTTP {response.status_code}): {body}",
                )

        except requests.ConnectionError:
            return PublishResult(
                success=False,
                error=(
                    f"Cannot connect to Dependency-Track at {self.config.url}. "
                    f"Verify the URL is correct and the server is running."
                ),
            )
        except requests.Timeout:
            return PublishResult(
                success=False,
                error="Request timed out (30s). The SBOM may be very large.",
            )
        except Exception as e:
            return PublishResult(
                success=False,
                error=f"Unexpected error during upload: {e}",
            )

    def _lookup_project_uuid(self, project_name: str) -> Optional[str]:
        """Look up a project UUID by name.

        Args:
            project_name: Project name to search for.

        Returns:
            Project UUID if found, None otherwise.
        """
        url = f"{self.config.base_url}/project"
        try:
            response = self._session.get(
                url,
                params={"name": project_name, "excludeInactive": "true"},
                timeout=10,
            )
            if response.status_code == 200:
                projects = response.json()
                if projects:
                    return projects[0].get("uuid")
        except Exception as e:
            logger.debug(f"Project lookup failed: {e}")
        return None

    def check_processing_status(self, token: str) -> Optional[bool]:
        """Check if BOM processing is complete.

        Args:
            token: Processing token returned from upload.

        Returns:
            True if processing is complete, False if still processing,
            None if status check failed.
        """
        if not token:
            return None

        url = f"{self.config.base_url}/bom/token/{token}"
        try:
            response = self._session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("processing", True) is False
        except Exception as e:
            logger.debug(f"Status check failed: {e}")
        return None
