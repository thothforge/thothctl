"""SecObserve publisher — uploads scan results and SBOMs to SecObserve.

SecObserve is an open-source vulnerability and license management system.
It supports SARIF (for scan findings) and CycloneDX (for SBOM/license tracking).

Endpoints:
- POST /api/import/file_upload_observations_by_name/ — scan results (SARIF)
- POST /api/import/file_upload_sbom_by_name/ — SBOM (CycloneDX)

Auth: APIToken header (not "Token" like DRF default)

Usage:
    thothctl inventory iac --check-versions --publish-sbom secobserve
    thothctl scan iac -t checkov -t kics --publish-to secobserve

Configuration:
    SECOBSERVE_URL — backend API base URL
    SECOBSERVE_API_TOKEN — API token (from SecObserve user settings)
    SECOBSERVE_PRODUCT_NAME — product name (must exist in SecObserve)

API Reference:
    https://github.com/SecObserve/SecObserve
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SecObserveConfig:
    """Configuration for SecObserve connection."""

    url: str = ""
    api_token: str = ""
    product_name: Optional[str] = None
    branch_name: Optional[str] = None
    origin_service: Optional[str] = None
    auto_create_product: bool = True

    @classmethod
    def from_env(cls) -> "SecObserveConfig":
        """Load configuration from environment variables."""
        import os

        return cls(
            url=os.environ.get("SECOBSERVE_URL", ""),
            api_token=os.environ.get("SECOBSERVE_API_TOKEN", ""),
            product_name=os.environ.get("SECOBSERVE_PRODUCT_NAME"),
            branch_name=os.environ.get("SECOBSERVE_BRANCH_NAME"),
            origin_service=os.environ.get("SECOBSERVE_ORIGIN_SERVICE"),
            auto_create_product=os.environ.get(
                "SECOBSERVE_AUTO_CREATE", "true"
            ).lower()
            == "true",
        )

    @classmethod
    def from_toml(cls, directory: str = ".") -> "SecObserveConfig":
        """Load configuration from .thothcf.toml."""
        import os

        config = cls.from_env()

        try:
            import toml

            toml_path = os.path.join(directory, ".thothcf.toml")
            if os.path.exists(toml_path):
                with open(toml_path, "r") as f:
                    data = toml.load(f)
                so = data.get("integrations", {}).get("secobserve", {})
                if so:
                    if not config.url:
                        config.url = so.get("url", "")
                    if not config.api_token:
                        config.api_token = so.get("api_token", "")
                    if not config.product_name:
                        config.product_name = so.get("product_name")
                    if not config.branch_name:
                        config.branch_name = so.get("branch_name")
                    if not config.origin_service:
                        config.origin_service = so.get("origin_service")
                    config.auto_create_product = so.get(
                        "auto_create_product", config.auto_create_product
                    )
        except Exception as e:
            logger.debug(f"Could not load .thothcf.toml: {e}")

        return config

    def validate(self) -> None:
        """Validate that required config is present."""
        if not self.url:
            raise ValueError(
                "SecObserve URL not configured. "
                "Set SECOBSERVE_URL environment variable or configure in .thothcf.toml:\n"
                "  [integrations.secobserve]\n"
                '  url = "http://secobserve-backend.localhost"'
            )
        if not self.api_token:
            raise ValueError(
                "SecObserve API token not configured. "
                "Set SECOBSERVE_API_TOKEN environment variable or configure in .thothcf.toml:\n"
                "  [integrations.secobserve]\n"
                '  api_token = "api_token_..."'
            )

    @property
    def base_url(self) -> str:
        """Get base URL stripped of trailing slashes."""
        return self.url.rstrip("/")


@dataclass
class SecObservePublishResult:
    """Result of publish operation to SecObserve."""

    success: bool
    product_name: str = ""
    observations_new: int = 0
    observations_updated: int = 0
    observations_resolved: int = 0
    license_components_new: int = 0
    error: Optional[str] = None
    url: Optional[str] = None


class SecObservePublisher:
    """Publishes scan results and SBOMs to SecObserve.

    Uses:
    - /api/import/file_upload_observations_by_name/ for SARIF scan results
    - /api/import/file_upload_sbom_by_name/ for CycloneDX SBOMs

    Auth: APIToken header (SecObserve's custom token format).
    """

    def __init__(self, config: SecObserveConfig):
        """Initialize publisher with connection config.

        Args:
            config: SecObserve connection configuration.

        Raises:
            ValueError: If required config (url, api_token) is missing.
        """
        config.validate()
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"APIToken {config.api_token}",
            }
        )

        # Handle .localhost domains that may not resolve in all environments
        # by setting Host header and rewriting URL to 127.0.0.1
        from urllib.parse import urlparse

        parsed = urlparse(config.url)
        if parsed.hostname and parsed.hostname.endswith(".localhost"):
            self._session.headers["Host"] = parsed.hostname
            # Rewrite to 127.0.0.1 for DNS resolution
            port = parsed.port or 80
            self._api_base = f"http://127.0.0.1:{port}"
        else:
            self._api_base = config.base_url

    def publish_observations(
        self,
        file_path: Path,
        product_name: Optional[str] = None,
        parser_name: str = "SARIF",
        service_name: Optional[str] = None,
    ) -> SecObservePublishResult:
        """Publish scan observations (findings) to SecObserve.

        Args:
            file_path: Path to the SARIF or scanner-native JSON file.
            product_name: Override product name.
            parser_name: SecObserve parser name (default: "SARIF").
            service_name: Origin service name for the observations.

        Returns:
            SecObservePublishResult with success status.
        """
        if not file_path.exists():
            return SecObservePublishResult(
                success=False,
                error=f"File not found: {file_path}",
            )

        effective_product = product_name or self.config.product_name
        if not effective_product:
            return SecObservePublishResult(
                success=False,
                error="Product name not configured. Set SECOBSERVE_PRODUCT_NAME.",
            )

        # Ensure product exists
        if self.config.auto_create_product:
            self._ensure_product(effective_product)

        url = f"{self._api_base}/api/import/file_upload_observations_by_name/"

        try:
            data = {
                "product_name": effective_product,
                "parser_name": parser_name,
            }
            if self.config.branch_name:
                data["branch_name"] = self.config.branch_name
            if service_name or self.config.origin_service:
                data["origin_service"] = service_name or self.config.origin_service

            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/json")}
                response = self._session.post(url, data=data, files=files, timeout=60)

            if response.status_code in (200, 201):
                result_data = response.json()
                return SecObservePublishResult(
                    success=True,
                    product_name=effective_product,
                    observations_new=result_data.get("observations_new", 0),
                    observations_updated=result_data.get("observations_updated", 0),
                    observations_resolved=result_data.get("observations_resolved", 0),
                )
            elif response.status_code == 401:
                return SecObservePublishResult(
                    success=False,
                    error="Authentication failed (401). Verify SECOBSERVE_API_TOKEN.",
                )
            else:
                body = response.text[:300]
                return SecObservePublishResult(
                    success=False,
                    error=f"Upload failed (HTTP {response.status_code}): {body}",
                )

        except requests.ConnectionError:
            return SecObservePublishResult(
                success=False,
                error=f"Cannot connect to SecObserve at {self.config.url}.",
            )
        except requests.Timeout:
            return SecObservePublishResult(
                success=False,
                error="Request timed out (60s).",
            )
        except Exception as e:
            return SecObservePublishResult(
                success=False,
                error=f"Unexpected error: {e}",
            )

    def publish_sbom(
        self,
        sbom_path: Path,
        product_name: Optional[str] = None,
    ) -> SecObservePublishResult:
        """Publish a CycloneDX SBOM to SecObserve for license tracking.

        Args:
            sbom_path: Path to the CycloneDX JSON file.
            product_name: Override product name.

        Returns:
            SecObservePublishResult with success status.
        """
        if not sbom_path.exists():
            return SecObservePublishResult(
                success=False,
                error=f"SBOM file not found: {sbom_path}",
            )

        effective_product = product_name or self.config.product_name
        if not effective_product:
            return SecObservePublishResult(
                success=False,
                error="Product name not configured. Set SECOBSERVE_PRODUCT_NAME.",
            )

        # Ensure product exists
        if self.config.auto_create_product:
            self._ensure_product(effective_product)

        url = f"{self._api_base}/api/import/file_upload_sbom_by_name/"

        try:
            data = {"product_name": effective_product}
            if self.config.branch_name:
                data["branch_name"] = self.config.branch_name

            with open(sbom_path, "rb") as f:
                files = {"file": (sbom_path.name, f, "application/json")}
                response = self._session.post(url, data=data, files=files, timeout=60)

            if response.status_code in (200, 201):
                result_data = response.json()
                return SecObservePublishResult(
                    success=True,
                    product_name=effective_product,
                    license_components_new=result_data.get(
                        "license_components_new", 0
                    ),
                )
            elif response.status_code == 401:
                return SecObservePublishResult(
                    success=False,
                    error="Authentication failed (401). Verify SECOBSERVE_API_TOKEN.",
                )
            else:
                body = response.text[:300]
                return SecObservePublishResult(
                    success=False,
                    error=f"Upload failed (HTTP {response.status_code}): {body}",
                )

        except requests.ConnectionError:
            return SecObservePublishResult(
                success=False,
                error=f"Cannot connect to SecObserve at {self.config.url}.",
            )
        except requests.Timeout:
            return SecObservePublishResult(
                success=False,
                error="Request timed out (60s).",
            )
        except Exception as e:
            return SecObservePublishResult(
                success=False,
                error=f"Unexpected error: {e}",
            )

    def _ensure_product(self, product_name: str) -> Optional[int]:
        """Ensure product exists in SecObserve. Creates if needed.

        Returns product ID or None.
        """
        url = f"{self._api_base}/api/products/"
        try:
            # Check if product exists
            response = self._session.get(
                url, params={"name": product_name}, timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    return results[0].get("id")

            # Create product
            response = self._session.post(
                url,
                json={"name": product_name, "description": f"IaC project: {product_name}"},
                timeout=10,
            )
            if response.status_code in (200, 201):
                return response.json().get("id")

        except Exception as e:
            logger.debug(f"Product ensure failed: {e}")

        return None
