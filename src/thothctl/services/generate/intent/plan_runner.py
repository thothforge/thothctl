"""Plan runner for Intent-to-IaC validation.

Executes terraform/terragrunt plan and parses results into Violation objects.

Three execution modes:
1. Terragrunt per-stack: `terragrunt plan` in a single stack directory
2. Terragrunt full-project: `terragrunt run --all -- plan --graph`
3. Terraform/tofu: `terraform plan -json` (follows DriftDetectionService pattern)

Terragrunt v0.99+ features used:
- --non-interactive: no prompts
- --provider-cache: shared provider plugins across stacks
- --iam-assume-role: temporal credentials via STS
- --auth-provider-cmd: dynamic credential provider
- --json-out-dir: structured JSON plan output
- --graph: DAG-aware execution for full-project mode
- --filter: targeted stack validation
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import PlanResult, Violation

logger = logging.getLogger(__name__)

# Default timeouts (seconds)
_DEFAULT_PLAN_TIMEOUT = 120
_DEFAULT_PLAN_ALL_TIMEOUT = 600
_DEFAULT_INIT_TIMEOUT = 60


class PlanRunner:
    """Executes terraform/terragrunt plan with security controls."""

    def __init__(
        self,
        project_type: str = "terraform-terragrunt",
        tftool: str = "tofu",
        config: Optional[Dict] = None,
    ):
        """Initialize the plan runner.

        Args:
            project_type: Project type determines execution tool.
            tftool: Terraform binary name for non-terragrunt projects.
            config: Plan configuration from .thothcf.toml [generation.plan].
        """
        self.project_type = project_type
        self.tftool = tftool
        self.config = config or {}

    # ==================================================================
    # Public API
    # ==================================================================

    def run_per_stack(self, stack_dir: str) -> PlanResult:
        """Validate a single stack via plan.

        For terragrunt: runs `terragrunt plan` in the stack directory.
        For terraform: runs `terraform plan` in the workspace.

        Args:
            stack_dir: Directory containing the stack to validate.

        Returns:
            PlanResult with violations and execution metadata.
        """
        is_terragrunt = self.project_type in ("terraform-terragrunt", "terragrunt")

        if is_terragrunt:
            return self._run_terragrunt_plan_stack(stack_dir)
        else:
            return self._run_terraform_plan(stack_dir)

    def run_full_project(self, project_dir: str) -> PlanResult:
        """Validate entire project (all stacks, DAG-aware).

        For terragrunt: runs `terragrunt run --all -- plan --graph`.
        For terraform: runs `terraform plan` on the root module.

        Args:
            project_dir: Root directory of the project.

        Returns:
            PlanResult with combined violations from all stacks.
        """
        is_terragrunt = self.project_type in ("terraform-terragrunt", "terragrunt")

        if is_terragrunt:
            return self._run_terragrunt_plan_all(project_dir)
        else:
            return self._run_terraform_plan(project_dir)

    def run_filtered(
        self, project_dir: str, stack_filter: str
    ) -> PlanResult:
        """Validate specific stacks matching a filter pattern.

        Uses terragrunt's --filter capability.

        Args:
            project_dir: Root directory of the project.
            stack_filter: Terragrunt filter expression (e.g., "stacks/foundation/**").

        Returns:
            PlanResult with violations from matched stacks.
        """
        return self._run_terragrunt_plan_filtered(project_dir, stack_filter)

    # ==================================================================
    # Terragrunt Per-Stack Execution
    # ==================================================================

    def _run_terragrunt_plan_stack(self, stack_dir: str) -> PlanResult:
        """Run `terragrunt plan` in a single stack directory.

        Uses terragrunt v0.99+ flags:
        - --non-interactive: no prompts
        - --provider-cache: shared providers across stacks
        - --iam-assume-role: temporal credentials (if configured)
        - --auth-provider-cmd: dynamic auth (if configured)
        """
        tg_bin = shutil.which("terragrunt")
        if not tg_bin:
            return PlanResult(skipped=True, skip_reason="terragrunt binary not found")

        # Verify stack has terragrunt.hcl
        if not (Path(stack_dir) / "terragrunt.hcl").exists():
            return PlanResult(
                skipped=True,
                skip_reason=f"No terragrunt.hcl in {stack_dir}",
            )

        cmd = self._build_terragrunt_plan_cmd()
        timeout = self.config.get("plan_timeout", _DEFAULT_PLAN_TIMEOUT)
        env = self._build_subprocess_env()

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=stack_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            elapsed = time.time() - start

            # Parse plan output for errors
            violations = self._parse_terragrunt_output(result.stdout, result.stderr)

            return PlanResult(
                violations=violations,
                plan_succeeded=(result.returncode == 0),
                execution_time_seconds=elapsed,
                skipped=False,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            logger.warning(
                f"Terragrunt plan timed out after {timeout}s in {stack_dir}"
            )
            return PlanResult(
                skipped=True,
                skip_reason=f"Plan timed out after {timeout}s",
                execution_time_seconds=elapsed,
            )
        except Exception as e:
            logger.warning(f"Terragrunt plan failed: {e}")
            return PlanResult(
                skipped=True,
                skip_reason=f"Plan execution error: {str(e)[:200]}",
            )

    def _build_terragrunt_plan_cmd(self) -> List[str]:
        """Build the terragrunt plan command with configured flags."""
        cmd = ["terragrunt", "plan"]

        # Always non-interactive for automation
        cmd.append("--non-interactive")

        # Provider caching
        if self.config.get("provider_cache", True):
            cmd.append("--provider-cache")

        # Temporal credentials via IAM role
        iam_role = self.config.get("iam_assume_role")
        if iam_role:
            cmd.extend(["--iam-assume-role", iam_role])
            duration = str(self.config.get("session_duration", 900))
            cmd.extend(["--iam-assume-role-duration", duration])
            session_name = self.config.get(
                "session_name", f"thothctl-plan-{int(time.time())}"
            )
            cmd.extend(["--iam-assume-role-session-name", session_name])

        # Dynamic auth provider command
        auth_cmd = self.config.get("auth_provider_cmd")
        if auth_cmd:
            cmd.extend(["--auth-provider-cmd", auth_cmd])

        # No color for clean output parsing
        cmd.append("--no-color")

        return cmd

    # ==================================================================
    # Terragrunt Full-Project Execution
    # ==================================================================

    def _run_terragrunt_plan_all(self, project_dir: str) -> PlanResult:
        """Run `terragrunt run --all -- plan --graph` for entire project.

        Validates all stacks respecting dependency order (DAG).
        """
        tg_bin = shutil.which("terragrunt")
        if not tg_bin:
            return PlanResult(skipped=True, skip_reason="terragrunt binary not found")

        cmd = self._build_terragrunt_run_all_cmd()
        timeout = self.config.get("plan_timeout_all", _DEFAULT_PLAN_ALL_TIMEOUT)
        env = self._build_subprocess_env()

        # Create temp dir for JSON output
        json_out_dir = tempfile.mkdtemp(prefix="thothctl_plan_all_")

        # Add json-out-dir to command
        cmd.extend(["--json-out-dir", json_out_dir])

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            elapsed = time.time() - start

            # Parse JSON plan output files
            violations = self._parse_json_out_dir(json_out_dir)

            # Also parse stderr for terragrunt-level errors
            tg_violations = self._parse_terragrunt_output(
                result.stdout, result.stderr
            )
            violations.extend(tg_violations)

            return PlanResult(
                violations=violations,
                plan_succeeded=(result.returncode == 0),
                execution_time_seconds=elapsed,
                skipped=False,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            logger.warning(
                f"Terragrunt run --all plan timed out after {timeout}s"
            )
            return PlanResult(
                skipped=True,
                skip_reason=f"Full project plan timed out after {timeout}s",
                execution_time_seconds=elapsed,
            )
        except Exception as e:
            logger.warning(f"Terragrunt run --all plan failed: {e}")
            return PlanResult(
                skipped=True,
                skip_reason=f"Full project plan error: {str(e)[:200]}",
            )
        finally:
            # Cleanup JSON output dir
            shutil.rmtree(json_out_dir, ignore_errors=True)

    def _build_terragrunt_run_all_cmd(self) -> List[str]:
        """Build terragrunt run --all -- plan command."""
        cmd = ["terragrunt", "run", "--all", "--", "plan"]

        # DAG-aware execution
        cmd.insert(3, "--graph")  # Before the -- separator

        # Rebuild: terragrunt run --all --graph --non-interactive ... -- plan
        cmd = ["terragrunt", "run", "--all"]

        # Terragrunt flags (before --)
        cmd.append("--graph")
        cmd.append("--non-interactive")

        if self.config.get("provider_cache", True):
            cmd.append("--provider-cache")

        iam_role = self.config.get("iam_assume_role")
        if iam_role:
            cmd.extend(["--iam-assume-role", iam_role])
            duration = str(self.config.get("session_duration", 900))
            cmd.extend(["--iam-assume-role-duration", duration])
            session_name = self.config.get(
                "session_name", f"thothctl-plan-all-{int(time.time())}"
            )
            cmd.extend(["--iam-assume-role-session-name", session_name])

        auth_cmd = self.config.get("auth_provider_cmd")
        if auth_cmd:
            cmd.extend(["--auth-provider-cmd", auth_cmd])

        cmd.append("--no-color")

        # Separator and terraform command
        cmd.extend(["--", "plan"])

        return cmd

    # ==================================================================
    # Terragrunt Filtered Execution
    # ==================================================================

    def _run_terragrunt_plan_filtered(
        self, project_dir: str, stack_filter: str
    ) -> PlanResult:
        """Run plan on filtered stacks only."""
        tg_bin = shutil.which("terragrunt")
        if not tg_bin:
            return PlanResult(skipped=True, skip_reason="terragrunt binary not found")

        cmd = self._build_terragrunt_run_all_cmd()

        # Insert filter before the -- separator
        separator_idx = cmd.index("--")
        cmd.insert(separator_idx, stack_filter)
        cmd.insert(separator_idx, "--filter")

        timeout = self.config.get("plan_timeout_all", _DEFAULT_PLAN_ALL_TIMEOUT)

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start

            violations = self._parse_terragrunt_output(result.stdout, result.stderr)

            return PlanResult(
                violations=violations,
                plan_succeeded=(result.returncode == 0),
                execution_time_seconds=elapsed,
                skipped=False,
            )

        except subprocess.TimeoutExpired:
            return PlanResult(
                skipped=True,
                skip_reason=f"Filtered plan timed out after {timeout}s",
            )
        except Exception as e:
            return PlanResult(
                skipped=True,
                skip_reason=f"Filtered plan error: {str(e)[:200]}",
            )

    # ==================================================================
    # Terraform/Tofu Execution (non-terragrunt)
    # ==================================================================

    def _run_terraform_plan(self, work_dir: str) -> PlanResult:
        """Run terraform/tofu plan following DriftDetectionService pattern.

        Steps:
        1. terraform init -input=false
        2. terraform plan -json -lock=false -input=false -detailed-exitcode
        3. Parse streaming JSON output for diagnostics
        """
        tf_cmd = shutil.which(self.tftool) or shutil.which("terraform")
        if not tf_cmd:
            return PlanResult(
                skipped=True,
                skip_reason=f"No {self.tftool}/terraform binary found",
            )

        init_timeout = self.config.get("init_timeout", _DEFAULT_INIT_TIMEOUT)
        plan_timeout = self.config.get("plan_timeout", _DEFAULT_PLAN_TIMEOUT)
        env = self._build_subprocess_env()

        start = time.time()

        # Step 1: Init
        try:
            init_result = subprocess.run(
                [tf_cmd, "init", "-input=false", "-no-color"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=init_timeout,
                env=env,
            )
            if init_result.returncode != 0:
                violations = self._parse_terraform_errors(
                    init_result.stderr, "INIT"
                )
                return PlanResult(
                    violations=violations,
                    plan_succeeded=False,
                    execution_time_seconds=time.time() - start,
                    skipped=False,
                )
        except subprocess.TimeoutExpired:
            return PlanResult(
                skipped=True,
                skip_reason=f"terraform init timed out after {init_timeout}s",
                execution_time_seconds=time.time() - start,
            )

        # Step 2: Plan
        try:
            plan_result = subprocess.run(
                [
                    tf_cmd, "plan",
                    "-input=false",
                    "-no-color",
                    "-json",
                    "-lock=false",
                    "-detailed-exitcode",
                ],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=plan_timeout,
                env=env,
            )
            elapsed = time.time() - start

            # Exit codes: 0=no changes, 1=error, 2=changes
            if plan_result.returncode == 1:
                violations = self._parse_streaming_json(plan_result.stdout)
                if not violations:
                    # Fallback: parse stderr if JSON parsing found nothing
                    violations = self._parse_terraform_errors(
                        plan_result.stderr, "PLAN"
                    )
                return PlanResult(
                    violations=violations,
                    plan_succeeded=False,
                    execution_time_seconds=elapsed,
                    skipped=False,
                )

            return PlanResult(
                violations=[],
                plan_succeeded=True,
                execution_time_seconds=elapsed,
                skipped=False,
            )

        except subprocess.TimeoutExpired:
            return PlanResult(
                skipped=True,
                skip_reason=f"terraform plan timed out after {plan_timeout}s",
                execution_time_seconds=time.time() - start,
            )

    # ==================================================================
    # Environment & Credentials
    # ==================================================================

    def _build_subprocess_env(self) -> Optional[Dict[str, str]]:
        """Build subprocess environment with AWS profile/credential support.

        Supports:
        - aws_profile: Sets AWS_PROFILE env var (named profile from ~/.aws/credentials)
        - aws_region: Sets AWS_DEFAULT_REGION and AWS_REGION
        - Inherits parent environment (so SSO sessions, IRSA, IMDS all work)

        For terragrunt: --iam-assume-role is handled at CLI flag level.
        For terraform: AWS_PROFILE in env is how terraform resolves credentials.

        Returns None to use parent env if no overrides configured.
        """
        aws_profile = self.config.get("aws_profile") or os.environ.get(
            "THOTH_PLAN_AWS_PROFILE"
        )
        aws_region = self.config.get("aws_region") or os.environ.get(
            "THOTH_PLAN_AWS_REGION"
        )

        if not aws_profile and not aws_region:
            return None  # Use parent environment unchanged

        # Start with copy of current environment (preserves SSO tokens, etc.)
        env = os.environ.copy()

        if aws_profile:
            env["AWS_PROFILE"] = aws_profile
            logger.debug(f"Plan subprocess: AWS_PROFILE={aws_profile}")

        if aws_region:
            env["AWS_DEFAULT_REGION"] = aws_region
            env["AWS_REGION"] = aws_region

        return env

    # ==================================================================
    # Output Parsing
    # ==================================================================

    def _parse_terragrunt_output(
        self, stdout: str, stderr: str
    ) -> List[Violation]:
        """Parse terragrunt plan output for errors.

        Terragrunt wraps terraform output. Errors appear as:
        - Terraform errors in stdout (JSON when -json flag propagates)
        - Terragrunt errors in stderr (e.g., dependency resolution failures)
        """
        violations = []

        # Parse stdout for terraform JSON diagnostics
        if stdout:
            violations.extend(self._parse_streaming_json(stdout))

        # Parse stderr for terragrunt-specific errors
        if stderr:
            for line in stderr.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Terragrunt error patterns
                if "Error" in line or "error" in line:
                    # Skip noise lines
                    if any(skip in line for skip in [
                        "download", "Getting", "Initializing",
                        "Copying", "exit status",
                    ]):
                        continue
                    violations.append(Violation(
                        check_id="TG_PLAN",
                        severity="HIGH",
                        resource="",
                        message=self._clean_message(line),
                        file_path="",
                        tool="plan",
                    ))

        return violations[:20]  # Limit to avoid overwhelming the AI

    def _parse_streaming_json(self, output: str) -> List[Violation]:
        """Parse terraform plan -json streaming output (one JSON object per line).

        Each line is a JSON message with @level, @message, and optionally diagnostic.
        """
        violations = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only process error/warning diagnostics
            level = msg.get("@level", "")
            msg_type = msg.get("type", "")

            if level == "error" or msg_type == "diagnostic":
                diag = msg.get("diagnostic", {})
                severity_raw = diag.get("severity", "error")
                severity = "HIGH" if severity_raw == "error" else "MEDIUM"

                # Extract file/line info
                range_info = diag.get("range", {})
                filename = range_info.get("filename", "")
                start_line = range_info.get("start", {}).get("line", 0)
                file_ref = f"{filename}:{start_line}" if start_line else filename

                message = diag.get("detail") or diag.get("summary") or msg.get(
                    "@message", "Unknown plan error"
                )

                violations.append(Violation(
                    check_id="TF_PLAN",
                    severity=severity,
                    resource=diag.get("address", ""),
                    message=self._clean_message(message),
                    file_path=file_ref,
                    tool="plan",
                ))

        return violations

    def _parse_json_out_dir(self, json_dir: str) -> List[Violation]:
        """Parse JSON plan files from --json-out-dir output.

        Terragrunt writes one JSON file per stack when using --json-out-dir.
        Each file is a standard terraform plan JSON (resource_changes, etc.)
        or streaming diagnostics.
        """
        violations = []
        json_path = Path(json_dir)

        if not json_path.exists():
            return violations

        for json_file in sorted(json_path.rglob("*.json")):
            try:
                content = json_file.read_text(encoding="utf-8")

                # Try as terraform show -json output (has resource_changes)
                try:
                    plan_data = json.loads(content)
                    if "resource_changes" in plan_data:
                        # This is a successful plan — check for diagnostics
                        for diag in plan_data.get("diagnostics", []):
                            severity_raw = diag.get("severity", "error")
                            violations.append(Violation(
                                check_id="TF_PLAN",
                                severity="HIGH" if severity_raw == "error" else "MEDIUM",
                                resource=diag.get("address", ""),
                                message=diag.get("detail", diag.get("summary", "")),
                                file_path=diag.get("range", {}).get("filename", ""),
                                tool="plan",
                            ))
                        continue
                except json.JSONDecodeError:
                    pass

                # Try as streaming JSON (one object per line)
                violations.extend(self._parse_streaming_json(content))

            except Exception as e:
                logger.debug(f"Failed to parse plan JSON {json_file}: {e}")

        return violations

    def _parse_terraform_errors(
        self, stderr: str, stage: str
    ) -> List[Violation]:
        """Parse non-JSON terraform errors from stderr."""
        violations = []
        if not stderr:
            return violations

        for line in stderr.splitlines()[:10]:
            line = line.strip()
            if not line:
                continue
            if "Error" in line or "error" in line:
                violations.append(Violation(
                    check_id=f"TF_{stage}",
                    severity="HIGH",
                    resource="",
                    message=self._clean_message(line),
                    file_path="",
                    tool="plan",
                ))

        if not violations and stderr.strip():
            violations.append(Violation(
                check_id=f"TF_{stage}",
                severity="HIGH",
                resource="",
                message=self._clean_message(stderr[:500]),
                file_path="",
                tool="plan",
            ))

        return violations

    @staticmethod
    def _clean_message(text: str) -> str:
        """Clean up error messages for AI consumption."""
        import re
        # Remove ANSI escape codes
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Security: remove AWS account IDs, ARNs, and resource IDs
        text = re.sub(r"arn:aws[a-z-]*:[^\s\"',]+", "arn:aws:***:***:***", text)
        text = re.sub(r"\b\d{12}\b", "***ACCOUNT***", text)
        text = re.sub(
            r"(vpc|subnet|sg|igw|rtb|acl|nat|eni|i|vol|snap)-[0-9a-f]{8,17}",
            r"\1-***",
            text,
        )
        # Remove excessive whitespace
        text = " ".join(text.split())
        # Truncate
        if len(text) > 300:
            text = text[:300] + "..."
        return text.strip()
