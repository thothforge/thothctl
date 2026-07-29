"""CDK CycloneDX SBOM generator and construct compatibility checker."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)


class CDKSbomGenerator:
    """Generate CycloneDX 1.6 SBOM for CDK projects."""

    def generate(
        self,
        inventory_dict: Dict[str, Any],
        project_name: str = "",
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate CycloneDX 1.6 SBOM from CDK inventory.

        Args:
            inventory_dict: The inventory dict produced by inventory_service
            project_name: Project name for metadata
            output_path: Where to write the JSON file (optional)

        Returns:
            The CycloneDX SBOM dict
        """
        from thothctl.version import __version__

        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "serialNumber": f"urn:uuid:{uuid4()}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": {
                    "type": "application",
                    "name": project_name
                    or inventory_dict.get("projectName", "unknown"),
                    "version": inventory_dict.get("version", "0.0.0"),
                },
                "tools": [
                    {
                        "vendor": "ThothForge",
                        "name": "thothctl",
                        "version": __version__,
                    }
                ],
            },
            "components": [],
            "dependencies": [],
            "formulation": [],
        }

        # Build components from inventory
        for group in inventory_dict.get("components", []):
            for comp in group.get("components", []):
                if comp.get("type") not in ("cdk_construct", "cdk-construct"):
                    continue

                name = comp.get("name", "")
                version = comp.get("version", [""])
                if isinstance(version, list):
                    version = version[0] if version else ""

                # Determine registry and PURL
                source = comp.get("source", [""])
                if isinstance(source, list):
                    source = source[0] if source else ""

                if "npm" in source:
                    purl = f"pkg:npm/{name}@{version}"
                    registry = "npm"
                elif "pypi" in source:
                    purl = f"pkg:pypi/{name}@{version}"
                    registry = "pypi"
                else:
                    purl = f"pkg:npm/{name}@{version}"
                    registry = "npm"

                # Build component entry
                license_id = comp.get("license", "")
                component = {
                    "type": "library",
                    "name": name,
                    "version": version,
                    "purl": purl,
                    "licenses": [{"license": {"id": license_id}}] if license_id else [],
                    "externalReferences": [],
                    "properties": [
                        {"name": "iac:component-type", "value": "cdk-construct"},
                        {"name": "iac:source-type", "value": registry},
                        {
                            "name": "iac:pinned",
                            "value": str(not self._is_range_version(comp)).lower(),
                        },
                    ],
                }

                # Add source URL
                source_url = comp.get("source_url", "")
                if source_url:
                    component["externalReferences"].append(
                        {"type": "website", "url": source_url}
                    )

                # Add integrity hash if available
                integrity = comp.get("integrity", "")
                if integrity:
                    # Parse npm integrity format: sha512-abc123...
                    if integrity.startswith("sha512-"):
                        component["hashes"] = [
                            {"alg": "SHA-512", "content": integrity[7:]}
                        ]
                    elif integrity.startswith("sha256-"):
                        component["hashes"] = [
                            {"alg": "SHA-256", "content": integrity[7:]}
                        ]

                # Add version/staleness properties
                latest = comp.get("latest_version", "")
                if latest:
                    component["properties"].append(
                        {"name": "iac:latest-available", "value": latest}
                    )
                    is_outdated = comp.get("status") == "Outdated"
                    component["properties"].append(
                        {"name": "iac:outdated", "value": str(is_outdated).lower()}
                    )

                release_date = comp.get("release_date", "")
                if release_date:
                    component["properties"].append(
                        {"name": "iac:last-updated", "value": release_date}
                    )

                # Add evidence (how this component was identified)
                component["evidence"] = {
                    "identity": {
                        "field": "purl",
                        "confidence": 0.95,
                        "methods": [
                            {
                                "technique": "source-code-analysis",
                                "value": f"Parsed from {comp.get('file', 'package.json')}",
                            }
                        ],
                    }
                }

                sbom["components"].append(component)

                # Add to dependency graph
                sbom["dependencies"].append({"ref": purl, "dependsOn": []})

        # Add formulation (tools and workflow that produced this SBOM)
        sbom["formulation"] = [
            {
                "components": [
                    {
                        "name": "thothctl",
                        "description": "IaC inventory and SBOM generation",
                    },
                    {
                        "name": "npm registry",
                        "description": "Package version and metadata resolution",
                    },
                    {
                        "name": "cdk-nag",
                        "description": "CDK security compliance validation",
                    },
                    {
                        "name": "CycloneDX 1.6",
                        "description": "SBOM standard (ECMA-424)",
                    },
                ],
                "workflows": [
                    {
                        "uid": "cdk-inventory",
                        "tasks": [
                            {
                                "uid": "parse-package-json",
                                "name": "Parse package dependencies",
                            },
                            {
                                "uid": "check-registry",
                                "name": "Check npm/PyPI for latest versions",
                            },
                            {
                                "uid": "generate-sbom",
                                "name": "Generate CycloneDX 1.6 SBOM",
                            },
                        ],
                    }
                ],
            }
        ]

        # Write to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(sbom, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"CDK SBOM written to {output_path}")

        return sbom

    @staticmethod
    def _is_range_version(comp: Dict) -> bool:
        """Check if the declared version uses a range constraint."""
        source = comp.get("source", [""])
        if isinstance(source, list):
            source = source[0] if source else ""
        # If source contains ^ or ~ it's a range
        return any(c in str(source) for c in ("^", "~", ">=", ">"))


# ── CDK Construct Compatibility Checker ──────────────────────────────────────


class CDKCompatibilityChecker:
    """Check compatibility between CDK construct versions.

    Uses semver analysis and GitHub changelog/release notes to detect
    breaking changes between versions.
    """

    # Known CDK construct GitHub repos
    KNOWN_REPOS = {
        "aws-cdk-lib": "aws/aws-cdk",
        "constructs": "aws/constructs",
        "cdk-nag": "cdklabs/cdk-nag",
    }

    def check_compatibility(
        self, components: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check compatibility for all CDK components.

        Returns list of compatibility reports per component.
        """
        reports = []
        for comp in components:
            if comp.get("type") not in ("cdk_construct", "cdk-construct"):
                continue
            if comp.get("status") != "Outdated":
                continue

            report = self._check_single_component(comp)
            if report:
                reports.append(report)

        return reports

    def _check_single_component(self, comp: Dict) -> Optional[Dict]:
        """Check compatibility for a single component."""
        name = comp.get("name", "")
        current = comp.get("version", [""])
        if isinstance(current, list):
            current = current[0] if current else ""
        latest = comp.get("latest_version", "")

        if not current or not latest or current == latest:
            return None

        # Semver analysis
        semver_result = self._analyze_semver(current, latest)

        # Changelog analysis (for known repos)
        changelog_result = self._fetch_changelog_summary(name, current, latest)

        # Build report
        report = {
            "name": name,
            "current_version": current,
            "latest_version": latest,
            "semver_change": semver_result["change_type"],
            "is_breaking": semver_result["is_breaking"],
            "upgrade_safe": semver_result["upgrade_safe"],
            "compatibility_level": semver_result["compatibility_level"],
            "recommendations": semver_result["recommendations"],
            "changelog_summary": changelog_result,
        }

        return report

    def _analyze_semver(self, current: str, latest: str) -> Dict:
        """Analyze semantic version difference."""
        try:
            cur_parts = [int(x) for x in current.split(".")[:3]]
            lat_parts = [int(x) for x in latest.split(".")[:3]]

            # Pad to 3
            while len(cur_parts) < 3:
                cur_parts.append(0)
            while len(lat_parts) < 3:
                lat_parts.append(0)

            cur_major, cur_minor, cur_patch = cur_parts
            lat_major, lat_minor, lat_patch = lat_parts

            if lat_major > cur_major:
                return {
                    "change_type": "major",
                    "is_breaking": True,
                    "upgrade_safe": False,
                    "compatibility_level": "breaking_changes",
                    "recommendations": [
                        f"Major version upgrade ({cur_major}.x → {lat_major}.x) — likely contains breaking changes.",
                        "Review the migration guide before upgrading.",
                        "Test thoroughly in a non-production environment.",
                    ],
                }
            elif lat_minor > cur_minor:
                return {
                    "change_type": "minor",
                    "is_breaking": False,
                    "upgrade_safe": True,
                    "compatibility_level": "minor_issues",
                    "recommendations": [
                        f"Minor version upgrade ({cur_major}.{cur_minor} → {lat_major}.{lat_minor}) — new features, possible deprecations.",
                        "Check release notes for deprecation warnings.",
                    ],
                }
            else:
                return {
                    "change_type": "patch",
                    "is_breaking": False,
                    "upgrade_safe": True,
                    "compatibility_level": "compatible",
                    "recommendations": [
                        f"Patch upgrade ({current} → {latest}) — bug fixes only. Safe to upgrade.",
                    ],
                }
        except (ValueError, IndexError):
            return {
                "change_type": "unknown",
                "is_breaking": False,
                "upgrade_safe": False,
                "compatibility_level": "unknown",
                "recommendations": ["Unable to parse version. Review manually."],
            }

    def _fetch_changelog_summary(self, name: str, current: str, latest: str) -> Dict:
        """Fetch changelog/release notes from GitHub."""
        repo = self.KNOWN_REPOS.get(name)
        if not repo:
            return {"available": False, "reason": "Unknown repository"}

        try:
            # Fetch releases between current and latest
            url = f"https://api.github.com/repos/{repo}/releases"
            resp = requests.get(url, timeout=10, params={"per_page": 20})
            if resp.status_code != 200:
                return {
                    "available": False,
                    "reason": f"GitHub API error: {resp.status_code}",
                }

            releases = resp.json()
            relevant_releases = []

            for release in releases:
                tag = release.get("tag_name", "").lstrip("v")
                if self._version_between(tag, current, latest):
                    body = release.get("body", "")
                    breaking_changes = self._extract_breaking_changes(body)
                    relevant_releases.append(
                        {
                            "version": tag,
                            "name": release.get("name", ""),
                            "breaking_changes": breaking_changes,
                            "has_breaking": len(breaking_changes) > 0,
                        }
                    )

            return {
                "available": True,
                "releases_between": len(relevant_releases),
                "releases_with_breaking": sum(
                    1 for r in relevant_releases if r["has_breaking"]
                ),
                "breaking_changes": [
                    change
                    for r in relevant_releases
                    for change in r["breaking_changes"]
                ][:10],  # Limit to 10
            }

        except requests.RequestException as e:
            return {"available": False, "reason": str(e)}

    def _version_between(self, version: str, lower: str, upper: str) -> bool:
        """Check if version is between lower (exclusive) and upper (inclusive)."""
        try:
            v = tuple(int(x) for x in version.split(".")[:3])
            lo = tuple(int(x) for x in lower.split(".")[:3])
            up = tuple(int(x) for x in upper.split(".")[:3])
            return lo < v <= up
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _extract_breaking_changes(body: str) -> List[str]:
        """Extract breaking change entries from release notes."""
        if not body:
            return []

        breaking = []
        lines = body.splitlines()
        in_breaking_section = False

        for line in lines:
            lower = line.lower().strip()
            # Detect breaking change headers
            if any(
                kw in lower for kw in ("breaking change", "breaking:", "⚠ breaking")
            ):
                in_breaking_section = True
                # If the header itself has content after ":"
                if ":" in line:
                    content = line.split(":", 1)[1].strip()
                    if content:
                        breaking.append(content)
                continue

            # Detect end of breaking section
            if in_breaking_section:
                if line.startswith("#") or line.startswith("##"):
                    in_breaking_section = False
                    continue
                stripped = line.strip().lstrip("- *")
                if stripped:
                    breaking.append(stripped)

        return breaking
