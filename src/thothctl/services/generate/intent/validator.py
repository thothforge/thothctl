"""Validation of generated IaC code using existing scanners + framework-native tools.

Supports multi-framework validation:
- Terraform/OpenTofu: terraform validate (schema + references)
- CloudFormation: cfn-lint (if available) or aws cloudformation validate-template
- SAM: sam validate
- CDK: cdk synth (if cdk.json present)
- All frameworks: Checkov + OPA for security/policy

Writes generated files to a temp directory, runs validators, parses results
into Violation objects for the self-correction loop.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from .models import GeneratedFile, ValidationResult, Violation

logger = logging.getLogger(__name__)


class GenerationValidator:
    """Validates AI-generated IaC code using framework-native + security tools."""

    def __init__(self, plan_config: Optional[dict] = None):
        """Initialize the validator.

        Args:
            plan_config: Configuration from .thothcf.toml [generation.plan].
                         If provided and plan_validation != "disabled",
                         enables terraform plan validation in the pipeline.
        """
        self._temp_dir: Optional[str] = None
        self._plan_validator = None

        if plan_config and plan_config.get("plan_validation", "disabled") != "disabled":
            try:
                from .plan_validator import PlanValidator

                project_type = plan_config.get("project_type", "terraform-terragrunt")
                tftool = plan_config.get("tftool", "tofu")
                self._plan_validator = PlanValidator(
                    config=plan_config,
                    project_type=project_type,
                    tftool=tftool,
                )
                logger.info(
                    f"Plan validation enabled: mode={plan_config.get('plan_validation')}"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize plan validator: {e}")
                self._plan_validator = None

    def validate(
        self,
        files: List[GeneratedFile],
        project_type: str = "terraform",
        project_dir: Optional[str] = None,
        org_policy_dir: Optional[str] = None,
        skip_checkov: bool = False,
        skip_opa: bool = False,
        skip_framework_validate: bool = False,
        skip_plan: bool = False,
        stack_path: str = "",
    ) -> ValidationResult:
        """Validate generated files using framework-native tools + scanners.

        Args:
            files: Generated files to validate
            project_type: Framework type (terraform, cloudformation, cdkv2, sam, etc.)
            project_dir: Original project directory (for loading .thothcf.toml rules)
            org_policy_dir: Path to OPA/Rego policy directory (optional)
            skip_checkov: Skip Checkov validation
            skip_opa: Skip OPA validation
            skip_framework_validate: Skip framework-native validation
            skip_plan: Skip terraform plan validation
            stack_path: Stack path for per-stack plan validation (terragrunt)

        Returns:
            ValidationResult with pass/fail status and violations list
        """
        if not files:
            return ValidationResult(passed=True)

        # Create temp workspace
        temp_dir = self._create_temp_workspace(files)

        try:
            violations: List[Violation] = []

            # Step 1: Framework-native validation (highest priority — catches
            # schema errors that Checkov won't find)
            if not skip_framework_validate:
                fw_violations = self._run_framework_validate(temp_dir, project_type)
                violations.extend(fw_violations)

            # Step 2: Plan validation (deployability — catches errors that
            # terraform validate misses: invalid attribute combos, provider
            # constraints, cross-resource reference issues)
            if not skip_plan and self._plan_validator:
                plan_violations = self._plan_validator.validate_per_stack(
                    files=files,
                    project_dir=project_dir or ".",
                    stack_path=stack_path,
                    temp_dir=temp_dir,
                )
                violations.extend(plan_violations)

            # Step 3: Run Checkov (security best practices)
            if not skip_checkov:
                checkov_violations = self._run_checkov(temp_dir)
                violations.extend(checkov_violations)

            # Step 4: Run OPA/Conftest (org policies)
            if not skip_opa and org_policy_dir:
                opa_violations = self._run_opa(temp_dir, org_policy_dir)
                violations.extend(opa_violations)

            # Step 5: Run compiled .thothcf.toml rules (naming, tagging, security, architecture)
            if not skip_opa and project_dir:
                rules_violations = self._run_compiled_rules(temp_dir, project_dir)
                violations.extend(rules_violations)

            passed = not any(
                v.severity in ("CRITICAL", "HIGH")
                for v in violations
            )

            # Count per tool
            checkov_failed = sum(1 for v in violations if v.tool == "checkov")
            opa_failed = sum(1 for v in violations if v.tool == "opa")

            return ValidationResult(
                passed=passed,
                violations=violations,
                checkov_passed=0,
                checkov_failed=checkov_failed,
                opa_passed=0,
                opa_failed=opa_failed,
            )

        finally:
            self._cleanup_temp(temp_dir)

    # ------------------------------------------------------------------
    # Framework-native validation
    # ------------------------------------------------------------------

    def _run_framework_validate(
        self, directory: str, project_type: str
    ) -> List[Violation]:
        """Run framework-specific validation based on project type.

        - terraform/terraform-terragrunt/terragrunt: terraform validate
        - cloudformation: cfn-lint or aws cloudformation validate-template
        - sam: sam validate
        - cdkv2: cdk synth --no-staging
        """
        dispatch = {
            "terraform": self._validate_terraform,
            "terraform-terragrunt": self._validate_terraform,
            "terragrunt": self._validate_terraform,
            "cloudformation": self._validate_cloudformation,
            "sam": self._validate_sam,
            "cdkv2": self._validate_cdk,
        }

        handler = dispatch.get(project_type, self._validate_terraform)
        try:
            return handler(directory)
        except Exception as e:
            logger.warning(f"Framework validation ({project_type}) failed: {e}")
            return []

    def _validate_terraform(self, directory: str) -> List[Violation]:
        """Run terraform init -backend=false && terraform validate."""
        violations = []

        # Detect tool: prefer tofu, fall back to terraform
        tf_cmd = self._find_tool(["tofu", "terraform"])
        if not tf_cmd:
            logger.info("No terraform/tofu binary found — skipping validate")
            return []

        # Init (no backend, no providers download to keep it fast)
        init_result = subprocess.run(
            [tf_cmd, "init", "-backend=false", "-input=false"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=directory,
        )

        if init_result.returncode != 0:
            # Parse init errors (usually provider/module issues)
            violations.extend(
                self._parse_terraform_errors(init_result.stderr, "terraform init")
            )
            return violations

        # Validate
        validate_result = subprocess.run(
            [tf_cmd, "validate", "-json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=directory,
        )

        if validate_result.returncode != 0:
            violations.extend(
                self._parse_terraform_validate_json(validate_result.stdout)
            )

        return violations

    def _validate_cloudformation(self, directory: str) -> List[Violation]:
        """Run cfn-lint on CloudFormation templates."""
        violations = []

        # Find CFN templates
        cfn_files = self._find_cfn_templates(directory)
        if not cfn_files:
            return []

        # Try cfn-lint first (richer output)
        cfn_lint = self._find_tool(["cfn-lint"])
        if cfn_lint:
            for cfn_file in cfn_files:
                result = subprocess.run(
                    [cfn_lint, "-f", "json", str(cfn_file)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=directory,
                )
                violations.extend(
                    self._parse_cfn_lint_json(result.stdout, cfn_file, directory)
                )
            return violations

        # Fallback: python3 -m cfnlint
        try:
            for cfn_file in cfn_files:
                result = subprocess.run(
                    ["python3", "-m", "cfnlint", "-f", "json", str(cfn_file)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=directory,
                )
                violations.extend(
                    self._parse_cfn_lint_json(result.stdout, cfn_file, directory)
                )
            return violations
        except Exception:
            pass

        # Last resort: basic YAML schema check
        logger.info("No cfn-lint available — skipping CloudFormation validation")
        return []

    def _validate_sam(self, directory: str) -> List[Violation]:
        """Run sam validate on SAM templates."""
        violations = []

        sam_cmd = self._find_tool(["sam"])
        if not sam_cmd:
            # Fall back to CloudFormation validation
            return self._validate_cloudformation(directory)

        # Find SAM template (template.yaml or template.yml)
        template = None
        for name in ("template.yaml", "template.yml", "sam-template.yaml"):
            candidate = Path(directory) / name
            if candidate.exists():
                template = candidate
                break

        if not template:
            # No SAM template found, try CFN validation
            return self._validate_cloudformation(directory)

        result = subprocess.run(
            [sam_cmd, "validate", "--template", str(template), "--lint"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=directory,
        )

        if result.returncode != 0:
            error_text = result.stderr or result.stdout
            violations.append(
                Violation(
                    check_id="SAM_VALIDATE",
                    severity="HIGH",
                    resource="template",
                    message=self._clean_error_message(error_text),
                    file_path=str(template.relative_to(directory)),
                    tool="framework",
                )
            )

        return violations

    def _validate_cdk(self, directory: str) -> List[Violation]:
        """Run cdk synth --no-staging for CDK validation."""
        violations = []

        cdk_cmd = self._find_tool(["cdk"])
        if not cdk_cmd:
            logger.info("No cdk binary found — skipping CDK validation")
            return []

        # Check if cdk.json exists (required for cdk synth)
        cdk_json = Path(directory) / "cdk.json"
        if not cdk_json.exists():
            # Can't run cdk synth without cdk.json — skip
            return []

        # Install deps if package.json exists
        pkg_json = Path(directory) / "package.json"
        if pkg_json.exists():
            subprocess.run(
                ["npm", "install", "--silent"],
                capture_output=True,
                cwd=directory,
                timeout=120,
            )

        result = subprocess.run(
            [cdk_cmd, "synth", "--no-staging", "--quiet"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=directory,
            env={
                **os.environ,
                "CDK_DEFAULT_ACCOUNT": "123456789012",
                "CDK_DEFAULT_REGION": "us-east-1",
            },
        )

        if result.returncode != 0:
            error_text = result.stderr or result.stdout
            # Parse CDK errors (TypeScript compile errors, construct errors)
            violations.extend(self._parse_cdk_errors(error_text, directory))

        return violations

    # ------------------------------------------------------------------
    # Framework-specific error parsers
    # ------------------------------------------------------------------

    def _parse_terraform_validate_json(self, json_output: str) -> List[Violation]:
        """Parse terraform validate -json output."""
        violations = []
        try:
            data = json.loads(json_output)
            for diag in data.get("diagnostics", []):
                severity = diag.get("severity", "error").upper()
                if severity == "ERROR":
                    severity = "HIGH"
                elif severity == "WARNING":
                    severity = "MEDIUM"

                # Extract file/line info
                range_info = diag.get("range", {})
                filename = range_info.get("filename", "")
                start = range_info.get("start", {})
                line = start.get("line", 0)

                violations.append(
                    Violation(
                        check_id="TF_VALIDATE",
                        severity=severity,
                        resource=diag.get("address", ""),
                        message=diag.get("detail", diag.get("summary", "")),
                        file_path=f"{filename}:{line}" if line else filename,
                        tool="framework",
                    )
                )
        except (json.JSONDecodeError, TypeError):
            pass
        return violations

    def _parse_terraform_errors(self, stderr: str, stage: str) -> List[Violation]:
        """Parse terraform init/plan errors from stderr."""
        violations = []
        if not stderr:
            return violations

        # Extract meaningful error lines
        error_lines = [
            line.strip()
            for line in stderr.splitlines()
            if line.strip()
            and not line.strip().startswith("╷")
            and not line.strip().startswith("╵")
            and not line.strip().startswith("│")
            and "Error:" in line
        ]

        for line in error_lines[:5]:  # Limit to 5 errors
            violations.append(
                Violation(
                    check_id=f"TF_{stage.upper().replace(' ', '_')}",
                    severity="HIGH",
                    resource="",
                    message=self._clean_error_message(line),
                    file_path="",
                    tool="framework",
                )
            )

        # If no structured errors found but returncode != 0, add generic
        if not violations and stderr.strip():
            violations.append(
                Violation(
                    check_id=f"TF_{stage.upper().replace(' ', '_')}",
                    severity="HIGH",
                    resource="",
                    message=self._clean_error_message(stderr[:500]),
                    file_path="",
                    tool="framework",
                )
            )

        return violations

    def _parse_cfn_lint_json(
        self, json_output: str, cfn_file: Path, directory: str
    ) -> List[Violation]:
        """Parse cfn-lint JSON output."""
        violations = []
        try:
            findings = json.loads(json_output) if json_output.strip() else []
            for finding in findings:
                level = finding.get("Level", "Error")
                severity_map = {
                    "Error": "HIGH",
                    "Warning": "MEDIUM",
                    "Informational": "LOW",
                }
                violations.append(
                    Violation(
                        check_id=finding.get("Rule", {}).get("Id", "CFN_LINT"),
                        severity=severity_map.get(level, "MEDIUM"),
                        resource=finding.get("Location", {}).get("Path", [""])[-1]
                        if isinstance(finding.get("Location", {}).get("Path"), list)
                        else "",
                        message=finding.get("Message", ""),
                        file_path=str(
                            Path(finding.get("Filename", str(cfn_file))).relative_to(
                                directory
                            )
                        )
                        if finding.get("Filename")
                        else str(cfn_file.relative_to(directory)),
                        tool="framework",
                    )
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return violations

    def _parse_cdk_errors(self, error_text: str, directory: str) -> List[Violation]:
        """Parse CDK synth errors (TypeScript/Python compile errors)."""
        violations = []
        lines = error_text.splitlines()

        for line in lines:
            stripped = line.strip()
            # TypeScript errors: file.ts(line,col): error TS...
            if "error TS" in stripped or "Error:" in stripped:
                violations.append(
                    Violation(
                        check_id="CDK_SYNTH",
                        severity="HIGH",
                        resource="",
                        message=self._clean_error_message(stripped),
                        file_path="",
                        tool="framework",
                    )
                )
            # Python errors
            elif "SyntaxError" in stripped or "ImportError" in stripped:
                violations.append(
                    Violation(
                        check_id="CDK_SYNTH",
                        severity="HIGH",
                        resource="",
                        message=self._clean_error_message(stripped),
                        file_path="",
                        tool="framework",
                    )
                )

        if not violations and error_text.strip():
            violations.append(
                Violation(
                    check_id="CDK_SYNTH",
                    severity="HIGH",
                    resource="",
                    message=self._clean_error_message(error_text[:500]),
                    file_path="",
                    tool="framework",
                )
            )

        return violations[:5]  # Limit

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_cfn_templates(self, directory: str) -> List[Path]:
        """Find CloudFormation/SAM template files."""
        templates = []
        for ext in ("*.yaml", "*.yml", "*.json"):
            for f in Path(directory).rglob(ext):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:300]
                    if (
                        "AWSTemplateFormatVersion" in content
                        or "Transform:" in content
                        or '"AWSTemplateFormatVersion"' in content
                    ):
                        templates.append(f)
                except Exception:
                    pass
        return templates

    @staticmethod
    def _find_tool(names: List[str]) -> Optional[str]:
        """Find the first available tool from a list of names."""
        for name in names:
            path = shutil.which(name)
            if path:
                return path
        return None

    @staticmethod
    def _clean_error_message(text: str) -> str:
        """Clean up error messages for display."""
        # Remove ANSI codes
        import re

        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Remove excessive whitespace
        text = " ".join(text.split())
        # Truncate
        if len(text) > 300:
            text = text[:300] + "..."
        return text.strip()

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
    # Compiled Rules (.thothcf.toml → Rego → conftest)
    # ------------------------------------------------------------------

    def _run_compiled_rules(self, directory: str, project_dir: str) -> List[Violation]:
        """Compile .thothcf.toml rules to Rego and evaluate via conftest.

        This is the Phase 2.4 integration: organizational rules (naming,
        tagging, security, architecture) are enforced at generation time.
        """
        try:
            from ...check.rules_compiler import RulesCompiler

            # Compile rules from the real project dir (not the temp workspace)
            compiler = RulesCompiler()
            compiled_dir = compiler.compile(project_dir)

            if not compiled_dir:
                return []

            logger.info(
                f"Evaluating compiled org rules from {project_dir} "
                f"against generated code"
            )

            # Run conftest with compiled policies against the temp workspace
            return self._run_opa(directory, compiled_dir)

        except ImportError:
            logger.debug("RulesCompiler not available — skipping rules validation")
            return []
        except Exception as e:
            logger.warning(f"Compiled rules validation failed: {e}")
            return []

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
