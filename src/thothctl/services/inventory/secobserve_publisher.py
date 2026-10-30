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

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SecObserveConfig:
    """Configuration for SecObserve connection."""

    url: str = ""
    api_token: str = ""
    product_name: Optional[str] = None
    product_group: Optional[str] = None
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
            product_group=os.environ.get("SECOBSERVE_PRODUCT_GROUP"),
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
                    if not config.product_group:
                        config.product_group = so.get("product_group")
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


@dataclass
class SecObserveGateResult:
    """SecObserve security gate state for a product (and optional branch).

    Attributes:
        evaluated: True when the gate state could be determined.
        passed: True/False when the gate is active; None when it is inactive
            (nothing to enforce) or could not be determined.
        active: Whether a gate applies (product -> group -> global); None if unknown.
        source: "product" (server-computed) or "branch" (evaluated by ThothCTL
            from branch counts, since SecObserve gates only the default branch).
        counts: Open observation counts per severity.
        thresholds: Effective thresholds per severity (empty if unknown/inactive).
    """

    product_name: str = ""
    branch_name: Optional[str] = None
    evaluated: bool = False
    passed: Optional[bool] = None
    active: Optional[bool] = None
    source: str = ""
    counts: Dict[str, int] = field(default_factory=dict)
    thresholds: Dict[str, Optional[int]] = field(default_factory=dict)
    url: Optional[str] = None
    error: Optional[str] = None

    @property
    def failed(self) -> bool:
        """True only when an active gate was evaluated and did not pass."""
        return self.evaluated and self.passed is False


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
        # Non-fatal notices (e.g. product group mismatch) for the caller to show.
        self.warnings: List[str] = []
        # product name -> id, so setup checks run once per publisher.
        self._ensured_products: Dict[str, int] = {}
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
                # SecObserve's upload API names this form field "service"
                # (FileUploadObservationsByNameRequest); "origin_service" is
                # silently ignored and leaves observations without a service.
                data["service"] = service_name or self.config.origin_service

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
            if self.config.origin_service:
                data["service"] = self.config.origin_service

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

    def _find_product(self, product_name: str) -> Optional[dict]:
        """Return the product with exactly this name, or None.

        SecObserve's ``name`` filter is a *contains* match, so results are
        filtered client-side for an exact name.
        """
        response = self._session.get(
            f"{self._api_base}/api/products/",
            params={"name": product_name},
            timeout=10,
        )
        response.raise_for_status()
        for product in response.json().get("results", []):
            if product.get("name") == product_name:
                return product
        return None

    def _ensure_product(self, product_name: str) -> Optional[int]:
        """Ensure product exists in SecObserve. Creates if needed.

        When ``product_group`` is configured, a newly created product is put in
        that group (the group is created too). Existing products are never
        moved, because the group decides which security gate applies; a
        mismatch is reported in ``self.warnings`` instead.

        Returns product ID or None.
        """
        if product_name in self._ensured_products:
            return self._ensured_products[product_name]

        url = f"{self._api_base}/api/products/"
        product_id = None
        try:
            product = self._find_product(product_name)
            if product:
                product_id = product.get("id")
                self._check_product_group(product)
            else:
                payload = {
                    "name": product_name,
                    "description": f"IaC project: {product_name}",
                }
                group_id = self._resolve_product_group()
                if group_id is not None:
                    payload["product_group"] = group_id
                response = self._session.post(url, json=payload, timeout=10)
                if response.status_code in (200, 201):
                    product_id = response.json().get("id")
                else:
                    self.warnings.append(
                        f"Could not create product '{product_name}' "
                        f"(HTTP {response.status_code}): {response.text[:200]}"
                    )

        except Exception as e:
            logger.debug(f"Product ensure failed: {e}")

        if product_id is not None:
            self._ensured_products[product_name] = product_id
        return product_id

    def _find_product_group(self, group_name: str) -> Optional[dict]:
        """Return the product group with exactly this name, or None."""
        response = self._session.get(
            f"{self._api_base}/api/product_groups/",
            params={"name": group_name},
            timeout=10,
        )
        response.raise_for_status()
        for group in response.json().get("results", []):
            if group.get("name") == group_name:
                return group
        return None

    def _resolve_product_group(self) -> Optional[int]:
        """Return the id of the configured product group, creating it if allowed."""
        group_name = self.config.product_group
        if not group_name:
            return None

        group = self._find_product_group(group_name)
        if group:
            return group.get("id")

        if not self.config.auto_create_product:
            self.warnings.append(
                f"Product group '{group_name}' not found and auto-create is "
                "disabled; product created without a group"
            )
            return None

        response = self._session.post(
            f"{self._api_base}/api/product_groups/",
            json={
                "name": group_name,
                "description": "Product group managed by ThothCTL",
            },
            timeout=10,
        )
        if response.status_code in (200, 201):
            return response.json().get("id")
        self.warnings.append(
            f"Could not create product group '{group_name}' "
            f"(HTTP {response.status_code}): {response.text[:200]}; "
            "product created without a group"
        )
        return None

    def _check_product_group(self, product: dict) -> None:
        """Warn when an existing product is not in the configured group."""
        group_name = self.config.product_group
        if not group_name:
            return
        group = self._find_product_group(group_name)
        if group is not None and product.get("product_group") == group.get("id"):
            return
        current = product.get("product_group_name") or "no group"
        self.warnings.append(
            f"Product '{product.get('name')}' is in {current!r}, not "
            f"'{group_name}'. It was left unchanged, because moving it would "
            "change which security gate applies; move it in SecObserve if intended."
        )

    def pop_warnings(self) -> List[str]:
        """Return and clear the collected warnings."""
        warnings, self.warnings = self.warnings, []
        return warnings

    # ── Security gate (read-only) ────────────────────────────────────────

    def get_security_gate(
        self, product_name: Optional[str] = None
    ) -> SecObserveGateResult:
        """Read the SecObserve security gate for a product (and branch).

        SecObserve only computes ``security_gate_passed`` from observations on
        the product's default branch (or branch-less observations when the
        product has no default branch). Therefore:

        - no branch configured and no default branch, or the configured branch
          is the default branch -> server-computed ``security_gate_passed``;
        - configured branch is not the default branch -> evaluated here from the
          branch's open-observation counts, with SecObserve's own rule
          (see ``_effective_thresholds``);
        - no branch configured but the product has a default branch -> the
          import did not update the gate, so it cannot be evaluated (set
          SECOBSERVE_BRANCH_NAME).

        Never raises; problems are reported via ``evaluated=False`` and ``error``.
        """
        name = product_name or self.config.product_name
        branch_name = self.config.branch_name
        result = SecObserveGateResult(product_name=name or "", branch_name=branch_name)
        if not name:
            result.error = "Product name not configured. Set SECOBSERVE_PRODUCT_NAME."
            return result

        try:
            product = self._find_product(name)
            if not product:
                result.error = f"Product '{name}' not found in SecObserve"
                return result
            result.url = f"{self.config.base_url}/#/products/{product['id']}/show"

            branch = None
            if branch_name:
                branch = self._find_branch(product["id"], branch_name)
                if branch is None:
                    result.error = (
                        f"Branch '{branch_name}' not found for product '{name}'"
                    )
                    return result
            elif product.get("repository_default_branch"):
                result.error = (
                    "product has a default branch, so imports without a branch do "
                    "not update its security gate; set SECOBSERVE_BRANCH_NAME"
                )
                return result

            # Thresholds are informational on the server path, required on the
            # branch path. None means "could not be read".
            try:
                thresholds = self._effective_thresholds(product)
            except requests.exceptions.RequestException:
                thresholds = None

            if branch is None or branch.get("is_default_branch"):
                result.source = "product"
                result.counts = _open_counts(product)
                result.passed = product.get("security_gate_passed")
                result.active = result.passed is not None
                result.thresholds = thresholds or {}
                result.evaluated = True
                return result

            # Non-default branch: evaluate locally, mirroring SecObserve.
            result.source = "branch"
            result.counts = _open_counts(branch)
            if thresholds is None:
                result.error = (
                    "could not read the security gate settings needed to evaluate "
                    "this branch (global settings may require more permissions)"
                )
                return result
            result.evaluated = True
            if not thresholds:  # no gate applies
                result.active = False
                result.passed = None
                return result
            result.active = True
            result.thresholds = thresholds
            result.passed = all(
                result.counts.get(sev, 0) <= limit for sev, limit in thresholds.items()
            )
            return result

        except requests.exceptions.RequestException as e:
            result.error = f"Could not query SecObserve: {e}"
            return result
        except Exception as e:  # defensive: never break the scan command
            logger.debug("Security gate lookup failed", exc_info=True)
            result.error = f"Unexpected error reading security gate: {e}"
            return result

    def _find_branch(self, product_id: int, branch_name: str) -> Optional[dict]:
        """Return the product branch with exactly this name, or None."""
        response = self._session.get(
            f"{self._api_base}/api/branches/",
            params={"product": product_id, "name": branch_name},
            timeout=10,
        )
        response.raise_for_status()
        for branch in response.json().get("results", []):
            if branch.get("name") == branch_name:
                return branch
        return None

    def _effective_thresholds(self, product: dict) -> Optional[Dict[str, int]]:
        """Resolve the security gate thresholds exactly like SecObserve does.

        Mirrors ``get_security_gate_thresholds`` in SecObserve
        (backend/application/core/services/security_gate.py):

        - the product group's ``security_gate_active`` wins when it is set,
          otherwise the product's;
        - active=False -> no gate; active=True -> thresholds of the group (if the
          group is active) else the product, with unset thresholds counting as 0;
        - unset (None) -> global settings, if their gate is active.

        Returns:
            dict severity -> threshold when a gate applies, ``{}`` when no gate
            applies, or None when a required setting could not be read.
        """
        group = None
        group_id = product.get("product_group")
        if group_id:
            response = self._session.get(
                f"{self._api_base}/api/product_groups/{group_id}/", timeout=10
            )
            if response.status_code != 200:
                return None
            group = response.json()

        if group is not None and group.get("security_gate_active") is not None:
            active = group.get("security_gate_active")
        else:
            active = product.get("security_gate_active")

        if active is False:
            return {}
        if active is True:
            source = (
                group
                if group is not None and group.get("security_gate_active") is True
                else product
            )
            return {
                sev: source.get(f"security_gate_threshold_{sev}") or 0
                for sev in _GATE_SEVERITIES
            }

        response = self._session.get(f"{self._api_base}/api/settings/1/", timeout=10)
        if response.status_code != 200:
            return None
        settings = response.json()
        if not settings.get("security_gate_active"):
            return {}
        return {
            sev: settings.get(f"security_gate_threshold_{sev}") or 0
            for sev in _GATE_SEVERITIES
        }


_GATE_SEVERITIES = ("critical", "high", "medium", "low", "none", "unknown")


def _open_counts(obj: dict) -> dict:
    """Extract open observation counts per severity from a product/branch."""
    return {
        sev: obj.get(f"open_{sev}_observation_count", 0) or 0
        for sev in _GATE_SEVERITIES
    }
