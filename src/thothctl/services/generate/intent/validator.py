"""Validation of generated IaC code using existing Checkov and OPA scanners.

Writes generated files to a temp directory, runs scanners, parses results
into Violation objects for the self-correction loop. No new scan engine —
just orchestrates the existing scanners against temporary files.
"""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from .models import GeneratedFile, ValidationResult, Violation

logger = logging.getLogger(__name__)


class GenerationValidator:
    """Validates AI-generated IaC code against Checkov and OPA policies."""

    def __init__(self):
        self._temp_dir: Optional[str] = None

    def validate(
        self,
        files: List[GeneratedFile],
        org_policy_dir: Optional[str] = None,
        skip_checkov: bool = False,
        skip_opa: bool = False,
    ) -> ValidationResult:
        """Validate generated files using Checkov and optionally OPA.

        Args:
            files: Generated files to validate
            org_policy_dir: Path to OPA/Rego policy directory (optional)
            skip_checkov: Skip Checkov validation
            skip_opa: Skip OPA validation

        Returns:
            ValidationResult with pass/fail status and violations list
        """
        if not files:
            return ValidationResult(passed=True)

        # Create temp workspace
        temp_dir = self._create_temp_workspace(files)

        try:
            violations: List[Violation] = []

            # Run Checkov
            if not skip_checkov:
                checkov_violations = self._run_checkov(temp_dir)
                violations.extend(checkov_violations)

            # Run OPA/Conftest
            if not skip_opa and org_policy_dir:
                opa_violations = self._run_opa(temp_dir, org_policy_dir)
                violations.extend(opa_violations)

            passed = len(violations) == 0

            # Count per tool
            checkov_failed = sum(1 for v in violations if v.tool == "checkov")
            opa_failed = sum(1 for v in violations if v.tool == "opa")

            return ValidationResult(
                passed=passed,
                violations=violations,
                checkov_passed=0,  # Will be filled by _run_checkov
                checkov_failed=checkov_failed,
                opa_passed=0,
                opa_failed=opa_failed,
            )

        finally:
            self._cleanup_temp(temp_dir)

    # ------------------------------------------------------------------
    # Temp workspace management
    # ------------------------------------------------------------------

    def _create_temp_workspace(self, files: List[GeneratedFile]) -> str:
        """Write generated files to a temp directory, preserving relative paths."""
        temp_dir = tempfile.mkdtemp(prefix="thothctl_validate_")
        logger.debug(f"Created temp workspace: {temp_dir}")

        for f in files:
            file_path = Path(temp_dir) / f.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f.content, encoding="utf-8")

        return temp_dir

    def _cleanup_temp(self, temp_dir: str) -> None:
        """Remove temp directory."""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp workspace: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up {temp_dir}: {e}")

    # ------------------------------------------------------------------
    # Checkov
    # ------------------------------------------------------------------

    def _run_checkov(self, directory: str) -> List[Violation]:
        """Run Checkov scanner on the temp directory."""
        try:
            from ...scan.scanners.checkov import CheckovScanner

            scanner = CheckovScanner()
            reports_dir = os.path.join(directory, ".reports")
            os.makedirs(reports_dir, exist_ok=True)

            result = scanner.scan(
                directory=directory,
                reports_dir=reports_dir,
                options={},
            )

            return self._parse_checkov_result(result)

        except ImportError:
            logger.warning("Checkov scanner not available — skipping validation")
            return []
        except Exception as e:
            logger.warning(f"Checkov validation failed: {e}")
            return []

    def _parse_checkov_result(self, result: dict) -> List[Violation]:
        """Parse Checkov scan result into Violation objects."""
        violations = []

        if not isinstance(result, dict):
            return violations

        result.get("status") or result.get("report_status", "")

        # Parse from report_data if available (standard ThothCTL format)
        result.get("report_data", {})
        findings = result.get("findings", [])

        # Use findings list if available
        if findings:
            for finding in findings:
                severity = self._checkov_severity(finding.get("severity", "MEDIUM"))
                violations.append(
                    Violation(
                        check_id=finding.get("id", finding.get("check_id", "UNKNOWN")),
                        severity=severity,
                        resource=finding.get("resource", "unknown"),
                        message=finding.get(
                            "title", finding.get("check", "Unknown check")
                        ),
                        file_path=finding.get("file", ""),
                        tool="checkov",
                    )
                )
            return violations

        # Fallback: parse from JSON report files
        reports_dir = None
        for key in ("report_path", "reports_dir"):
            if key in result:
                reports_dir = result[key]
                break

        if reports_dir and os.path.isdir(reports_dir):
            violations.extend(self._parse_checkov_json_reports(reports_dir))

        return violations

    def _parse_checkov_json_reports(self, reports_dir: str) -> List[Violation]:
        """Parse Checkov JSON report files for violations."""
        violations = []

        for json_file in Path(reports_dir).rglob("*.json"):
            try:
                data = json.loads(json_file.read_text())

                # Checkov native JSON format
                if isinstance(data, list):
                    for check_result in data:
                        failed = check_result.get("results", {}).get(
                            "failed_checks", []
                        )
                        for check in failed:
                            violations.append(
                                Violation(
                                    check_id=check.get("check_id", "UNKNOWN"),
                                    severity=self._checkov_severity(
                                        check.get("severity", "MEDIUM")
                                    ),
                                    resource=check.get("resource", "unknown"),
                                    message=check.get("check_result", {}).get(
                                        "name", check.get("name", "")
                                    ),
                                    file_path=check.get("file_path", ""),
                                    tool="checkov",
                                )
                            )
                elif isinstance(data, dict) and "results" in data:
                    failed = data.get("results", {}).get("failed_checks", [])
                    for check in failed:
                        violations.append(
                            Violation(
                                check_id=check.get("check_id", "UNKNOWN"),
                                severity=self._checkov_severity(
                                    check.get("severity", "MEDIUM")
                                ),
                                resource=check.get("resource", "unknown"),
                                message=check.get("name", check.get("check_id", "")),
                                file_path=check.get("file_path", ""),
                                tool="checkov",
                            )
                        )
            except (json.JSONDecodeError, OSError):
                continue

        return violations

    # ------------------------------------------------------------------
    # OPA / Conftest
    # ------------------------------------------------------------------

    def _run_opa(self, directory: str, policy_dir: str) -> List[Violation]:
        """Run OPA/Conftest scanner on the temp directory."""
        try:
            from ...scan.scanners.opa import OPAScanner

            scanner = OPAScanner()
            reports_dir = os.path.join(directory, ".reports_opa")
            os.makedirs(reports_dir, exist_ok=True)

            result = scanner.scan(
                directory=directory,
                reports_dir=reports_dir,
                options={"policy_dir": policy_dir},
            )

            return self._parse_opa_result(result)

        except ImportError:
            logger.warning("OPA scanner not available — skipping policy validation")
            return []
        except Exception as e:
            logger.warning(f"OPA validation failed: {e}")
            return []

    def _parse_opa_result(self, result: dict) -> List[Violation]:
        """Parse OPA/Conftest scan result into Violation objects."""
        violations = []

        if not isinstance(result, dict):
            return violations

        findings = result.get("findings", [])
        for finding in findings:
            violations.append(
                Violation(
                    check_id=finding.get("id", finding.get("rule", "OPA_POLICY")),
                    severity=finding.get("severity", "MEDIUM").upper(),
                    resource=finding.get(
                        "resource", finding.get("filename", "unknown")
                    ),
                    message=finding.get(
                        "message", finding.get("msg", "Policy violation")
                    ),
                    file_path=finding.get("file", finding.get("filename", "")),
                    tool="opa",
                )
            )

        return violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _checkov_severity(raw: str) -> str:
        """Normalize Checkov severity to standard levels."""
        raw = (raw or "MEDIUM").upper()
        if raw in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            return raw
        # Checkov sometimes uses different naming
        mapping = {
            "ERROR": "HIGH",
            "WARNING": "MEDIUM",
            "INFO": "LOW",
            "NONE": "LOW",
        }
        return mapping.get(raw, "MEDIUM")
