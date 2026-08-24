"""DefectDojo SBOM/scan publisher — uploads CycloneDX BOMs to a DefectDojo instance.

Supports:
- Upload via /api/v2/reimport-scan/ endpoint (recommended by DefectDojo docs)
- Token-based authentication
- Auto-create product and engagement if they don't exist
- CycloneDX scan type for IaC SBOM imports

Usage:
    thothctl inventory iac --check-versions --publish-sbom defectdojo

Configuration (priority order):
    1. Environment variables (DEFECTDOJO_URL, DEFECTDOJO_TOKEN)
    2. .thothcf.toml [integrations.defectdojo] section

API Reference:
    https://docs.defectdojo.com/import_data/import_scan_files/api_pipeline_modelling/
"""

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# DefectDojo API prefix
API_PREFIX = "/api/v2"

# Scan type for CycloneDX SBOM imports in DefectDojo
SCAN_TYPE_CYCLONEDX = "CycloneDX Scan"


@dataclass
class DefectDojoConfig:
    """Configuration for DefectDojo connection."""

    url: str = ""
    token: str = ""
    product_name: Optional[str] = None
    product_type_name: str = "Infrastructure"
    engagement_name: Optional[str] = None
    auto_create: bool = True
    close_old_findings: bool = True
    deduplication_on_engagement: bool = True

    @classmethod
    def from_env(cls) -> "DefectDojoConfig":
        """Load configuration from environment variables."""
        import os

        return cls(
            url=os.environ.get("DEFECTDOJO_URL", ""),
            token=os.environ.get("DEFECTDOJO_TOKEN", ""),
            product_name=os.environ.get("DEFECTDOJO_PRODUCT_NAME"),
            product_type_name=os.environ.get(
                "DEFECTDOJO_PRODUCT_TYPE", "Infrastructure"
            ),
            engagement_name=os.environ.get("DEFECTDOJO_ENGAGEMENT_NAME"),
            auto_create=os.environ.get("DEFECTDOJO_AUTO_CREATE", "true").lower()
            == "true",
            close_old_findings=os.environ.get(
                "DEFECTDOJO_CLOSE_OLD_FINDINGS", "true"
            ).lower()
            == "true",
        )

    @classmethod
    def from_toml(cls, directory: str = ".") -> "DefectDojoConfig":
        """Load configuration from .thothcf.toml."""
        import os

        config = cls.from_env()

        try:
            import toml

            toml_path = os.path.join(directory, ".thothcf.toml")
            if os.path.exists(toml_path):
                with open(toml_path, "r") as f:
                    data = toml.load(f)
                dd = data.get("integrations", {}).get("defectdojo", {})
                if dd:
                    if not config.url:
                        config.url = dd.get("url", "")
                    if not config.token:
                        config.token = dd.get("token", "")
                    if not config.product_name:
                        config.product_name = dd.get("product_name")
                    config.product_type_name = dd.get(
                        "product_type_name", config.product_type_name
                    )
                    if not config.engagement_name:
                        config.engagement_name = dd.get("engagement_name")
                    config.auto_create = dd.get("auto_create", config.auto_create)
                    config.close_old_findings = dd.get(
                        "close_old_findings", config.close_old_findings
                    )
                    config.deduplication_on_engagement = dd.get(
                        "deduplication_on_engagement",
                        config.deduplication_on_engagement,
                    )
        except Exception as e:
            logger.debug(f"Could not load .thothcf.toml: {e}")

        return config

    def validate(self) -> None:
        """Validate that required config is present."""
        if not self.url:
            raise ValueError(
                "DefectDojo URL not configured. "
                "Set DEFECTDOJO_URL environment variable or configure in .thothcf.toml:\n"
                "  [integrations.defectdojo]\n"
                '  url = "http://defectdojo.example.com:8090"'
            )
        if not self.token:
            raise ValueError(
                "DefectDojo API token not configured. "
                "Set DEFECTDOJO_TOKEN environment variable or configure in .thothcf.toml:\n"
                "  [integrations.defectdojo]\n"
                '  token = "your-api-token"'
            )

    @property
    def base_url(self) -> str:
        """Get base URL with API prefix."""
        url = self.url.rstrip("/")
        if not url.endswith(API_PREFIX):
            url += API_PREFIX
        return url


@dataclass
class DefectDojoPublishResult:
    """Result of SBOM publish operation to DefectDojo."""

    success: bool
    product_name: str = ""
    engagement_name: str = ""
    test_id: Optional[int] = None
    findings_count: int = 0
    error: Optional[str] = None
    url: Optional[str] = None


class DefectDojoPublisher:
    """Publishes CycloneDX SBOMs to OWASP DefectDojo.

    Uses the /api/v2/reimport-scan/ endpoint which:
    - Creates a new Test on first import
    - Updates existing Test on reimport (deduplicates findings)
    - Can auto-close findings no longer present in the scan
    """

    def __init__(self, config: DefectDojoConfig):
        """Initialize publisher with connection config.

        Args:
            config: DefectDojo connection configuration.

        Raises:
            ValueError: If required config (url, token) is missing.
        """
        config.validate()
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token {config.token}",
                "Accept": "application/json",
            }
        )

    def publish(
        self,
        sbom_path: Path,
        product_name: Optional[str] = None,
        engagement_name: Optional[str] = None,
        scan_type: str = SCAN_TYPE_CYCLONEDX,
    ) -> DefectDojoPublishResult:
        """Publish a CycloneDX SBOM to DefectDojo.

        Uses /api/v2/reimport-scan/ which handles both initial import
        and subsequent reimports with deduplication.

        Args:
            sbom_path: Path to the CycloneDX JSON file.
            product_name: Override product name.
            engagement_name: Override engagement name.
            scan_type: DefectDojo scan type (default: "CycloneDX Scan").

        Returns:
            DefectDojoPublishResult with success status.
        """
        if not sbom_path.exists():
            return DefectDojoPublishResult(
                success=False,
                error=f"SBOM file not found: {sbom_path}",
            )

        # Resolve names
        effective_product = product_name or self.config.product_name
        if not effective_product:
            return DefectDojoPublishResult(
                success=False,
                error=(
                    "Product name not configured. "
                    "Set --project-name, DEFECTDOJO_PRODUCT_NAME, or "
                    "configure in .thothcf.toml"
                ),
            )

        effective_engagement = (
            engagement_name
            or self.config.engagement_name
            or "IaC Supply Chain Inventory"
        )

        # Ensure product and engagement exist (auto-create if configured)
        if self.config.auto_create:
            product_id = self._ensure_product(effective_product)
            if not product_id:
                return DefectDojoPublishResult(
                    success=False,
                    error=f"Failed to find or create product: {effective_product}",
                )

            engagement_id = self._ensure_engagement(
                product_id, effective_engagement
            )
            if not engagement_id:
                return DefectDojoPublishResult(
                    success=False,
                    error=f"Failed to find or create engagement: {effective_engagement}",
                )

        # Upload via reimport-scan
        url = f"{self.config.base_url}/reimport-scan/"

        logger.info(
            f"Publishing SBOM to DefectDojo: {self.config.url} "
            f"(product: {effective_product}, engagement: {effective_engagement})"
        )

        try:
            with open(sbom_path, "rb") as f:
                data = {
                    "product_name": effective_product,
                    "engagement_name": effective_engagement,
                    "scan_type": scan_type,
                    "active": "true",
                    "verified": "false",
                    "close_old_findings": str(
                        self.config.close_old_findings
                    ).lower(),
                    "deduplication_on_engagement": str(
                        self.config.deduplication_on_engagement
                    ).lower(),
                    "auto_create_context": str(self.config.auto_create).lower(),
                }

                files = {"file": (sbom_path.name, f, "application/json")}

                response = self._session.post(
                    url,
                    data=data,
                    files=files,
                    timeout=60,
                )

            if response.status_code in (200, 201):
                result_data = response.json()
                test_id = result_data.get("test", result_data.get("id"))
                # Extract findings count from various response formats
                stats = result_data.get("statistics", {})
                if isinstance(stats, dict) and "after" in stats:
                    findings_count = stats["after"].get("total", 0)
                elif isinstance(stats, dict) and "total" in stats:
                    findings_count = stats["total"]
                else:
                    findings_count = 0

                # Build URL to the test in DefectDojo UI
                test_url = None
                if test_id:
                    test_url = f"{self.config.url.rstrip('/')}/test/{test_id}"

                return DefectDojoPublishResult(
                    success=True,
                    product_name=effective_product,
                    engagement_name=effective_engagement,
                    test_id=test_id,
                    findings_count=findings_count,
                    url=test_url,
                )
            elif response.status_code == 400:
                body = response.text[:500]
                return DefectDojoPublishResult(
                    success=False,
                    error=f"Bad request (400): {body}",
                )
            elif response.status_code == 401:
                return DefectDojoPublishResult(
                    success=False,
                    error=(
                        "Authentication failed (401). "
                        "Verify DEFECTDOJO_TOKEN is a valid API token. "
                        "Generate at: User → API v2 Key"
                    ),
                )
            elif response.status_code == 403:
                return DefectDojoPublishResult(
                    success=False,
                    error="Forbidden (403). Token lacks import permissions.",
                )
            else:
                body = response.text[:300]
                return DefectDojoPublishResult(
                    success=False,
                    error=f"Upload failed (HTTP {response.status_code}): {body}",
                )

        except requests.ConnectionError:
            return DefectDojoPublishResult(
                success=False,
                error=(
                    f"Cannot connect to DefectDojo at {self.config.url}. "
                    f"Verify the URL and that the server is running."
                ),
            )
        except requests.Timeout:
            return DefectDojoPublishResult(
                success=False,
                error="Request timed out (60s). The SBOM may be very large.",
            )
        except Exception as e:
            return DefectDojoPublishResult(
                success=False,
                error=f"Unexpected error: {e}",
            )

    def _ensure_product(self, product_name: str) -> Optional[int]:
        """Find or create a product in DefectDojo.

        Returns product ID or None on failure.
        """
        # Try to find existing product
        url = f"{self.config.base_url}/products/"
        try:
            response = self._session.get(
                url, params={"name": product_name}, timeout=10
            )
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    return results[0]["id"]

            # Create new product
            product_type_id = self._get_or_create_product_type(
                self.config.product_type_name
            )

            response = self._session.post(
                url,
                json={
                    "name": product_name,
                    "description": f"IaC project: {product_name}",
                    "prod_type": product_type_id,
                },
                timeout=10,
            )
            if response.status_code in (200, 201):
                return response.json().get("id")

            logger.error(
                f"Failed to create product: {response.status_code} {response.text[:200]}"
            )

        except Exception as e:
            logger.error(f"Product lookup/creation failed: {e}")

        return None

    def _ensure_engagement(
        self, product_id: int, engagement_name: str
    ) -> Optional[int]:
        """Find or create an engagement in DefectDojo.

        Returns engagement ID or None on failure.
        """
        url = f"{self.config.base_url}/engagements/"
        try:
            response = self._session.get(
                url,
                params={"product": product_id, "name": engagement_name},
                timeout=10,
            )
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    return results[0]["id"]

            # Create new engagement
            today = date.today().isoformat()
            response = self._session.post(
                url,
                json={
                    "name": engagement_name,
                    "product": product_id,
                    "target_start": today,
                    "target_end": today,
                    "engagement_type": "CI/CD",
                    "status": "In Progress",
                    "deduplication_on_engagement": self.config.deduplication_on_engagement,
                },
                timeout=10,
            )
            if response.status_code in (200, 201):
                return response.json().get("id")

            logger.error(
                f"Failed to create engagement: {response.status_code} {response.text[:200]}"
            )

        except Exception as e:
            logger.error(f"Engagement lookup/creation failed: {e}")

        return None

    def _get_or_create_product_type(self, type_name: str) -> int:
        """Get or create a product type. Returns ID (defaults to 1 on failure)."""
        url = f"{self.config.base_url}/product_types/"
        try:
            response = self._session.get(
                url, params={"name": type_name}, timeout=10
            )
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    return results[0]["id"]

            # Create
            response = self._session.post(
                url, json={"name": type_name}, timeout=10
            )
            if response.status_code in (200, 201):
                return response.json().get("id", 1)

        except Exception as e:
            logger.debug(f"Product type lookup failed: {e}")

        return 1  # Default product type ID
