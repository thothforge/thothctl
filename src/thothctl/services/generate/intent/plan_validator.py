"""Plan validator orchestrator for Intent-to-IaC pipeline.

Wires together StateResolver + PlanRunner to provide a single entry point
for plan validation. Routes to the correct execution mode based on
project type and configuration.

Graceful degradation: if ANY component fails (no binary, timeout,
credential error), plan validation is SKIPPED and returns empty violations.
The pipeline continues with terraform validate + checkov + opa.
"""

import logging
import shutil
from typing import Dict, List, Optional

from .models import GeneratedFile, PlanContext, PlanMode, PlanResult, Violation
from .plan_runner import PlanRunner
from .state_resolver import StateResolver

logger = logging.getLogger(__name__)


class PlanValidator:
    """Orchestrates plan validation for generated IaC code.

    Usage in GenerationValidator:
        plan_validator = PlanValidator(config, project_type, tftool)
        violations = plan_validator.validate_per_stack(
            files=generated_files,
            project_dir="/path/to/project",
            stack_path="stacks/foundation/network/vpc",
        )

    Usage for full-project validation:
        violations = plan_validator.validate_full_project(
            project_dir="/path/to/project",
        )
    """

    def __init__(
        self,
        config: Dict,
        project_type: str = "terraform-terragrunt",
        tftool: str = "tofu",
    ):
        """Initialize the plan validator.

        Args:
            config: Plan configuration from .thothcf.toml [generation.plan].
            project_type: Detected project type.
            tftool: Terraform binary name for non-terragrunt projects.
        """
        self.config = config
        self.project_type = project_type
        self.tftool = tftool

        # Resolve plan mode from config
        mode_str = config.get("plan_validation", "disabled")
        try:
            self.mode = PlanMode(mode_str)
        except ValueError:
            logger.warning(
                f"Invalid plan_validation mode '{mode_str}', defaulting to disabled"
            )
            self.mode = PlanMode.DISABLED

        # Initialize components
        self.state_resolver = StateResolver()
        self.plan_runner = PlanRunner(
            project_type=project_type, tftool=tftool, config=config
        )

    @property
    def is_enabled(self) -> bool:
        """Whether plan validation is enabled."""
        return self.mode != PlanMode.DISABLED

    # ==================================================================
    # Public API
    # ==================================================================

    def validate_per_stack(
        self,
        files: List[GeneratedFile],
        project_dir: str,
        stack_path: str = "",
        temp_dir: Optional[str] = None,
    ) -> List[Violation]:
        """Validate a single generated stack via terraform plan.

        For terragrunt projects:
        1. Write generated .tf files to project_dir/stack_path/
        2. Run `terragrunt plan` in that directory
        3. Parse plan output → violations
        4. Rollback written files (caller decides whether to keep via --apply)

        For terraform projects:
        1. Use existing temp_dir (from GenerationValidator)
        2. Run `terraform plan -json -lock=false`
        3. Parse output → violations

        Args:
            files: Generated files to validate.
            project_dir: Root of the IaC project.
            stack_path: Relative path to the stack directory.
            temp_dir: Temp workspace (for terraform mode; already has files written).

        Returns:
            List of Violation objects. Empty if plan is skipped.
        """
        if not self.is_enabled:
            return []

        # Gate: check binary availability
        if not self._check_binary_available():
            return []

        # Resolve execution context
        context = self.state_resolver.resolve(
            project_dir=project_dir,
            project_type=self.project_type,
            stack_path=stack_path,
            plan_mode=self.mode,
        )

        # For terraform mode, use the temp dir
        if not context.is_in_place and temp_dir:
            context = PlanContext(
                mode=context.mode,
                work_dir=temp_dir,
                project_type=context.project_type,
                stack_path=context.stack_path,
                is_in_place=False,
                written_files=[],
            )

        # Write files for in-place validation (terragrunt)
        if context.is_in_place:
            try:
                context = self.state_resolver.write_files_for_plan(files, context)
            except Exception as e:
                logger.warning(f"Failed to write files for plan: {e}")
                return []

        try:
            # Execute plan
            result = self.plan_runner.run_per_stack(context.work_dir)

            if result.skipped:
                logger.info(f"Plan skipped: {result.skip_reason}")
                return []

            if result.execution_time_seconds > 0:
                logger.info(
                    f"Plan completed in {result.execution_time_seconds:.1f}s "
                    f"({len(result.violations)} violations)"
                )

            return result.violations

        except Exception as e:
            logger.warning(f"Plan validation failed unexpectedly: {e}")
            return []

        finally:
            # Always rollback in-place files after validation
            # (caller re-writes with --apply if generation succeeds)
            if context.is_in_place:
                self.state_resolver.rollback(context)

    def validate_full_project(
        self,
        project_dir: str,
    ) -> List[Violation]:
        """Validate entire project (all stacks, DAG-aware).

        Runs `terragrunt run --all -- plan --graph` for terragrunt projects.
        Runs `terraform plan` for plain terraform projects.

        Best used AFTER all stacks are generated and written to disk.

        Args:
            project_dir: Root directory of the project.

        Returns:
            List of Violation objects. Empty if plan is skipped.
        """
        if not self.is_enabled:
            return []

        if not self._check_binary_available():
            return []

        try:
            result = self.plan_runner.run_full_project(project_dir)

            if result.skipped:
                logger.info(f"Full project plan skipped: {result.skip_reason}")
                return []

            logger.info(
                f"Full project plan completed in {result.execution_time_seconds:.1f}s "
                f"({len(result.violations)} violations, "
                f"succeeded={result.plan_succeeded})"
            )

            return result.violations

        except Exception as e:
            logger.warning(f"Full project plan validation failed: {e}")
            return []

    def validate_filtered(
        self,
        project_dir: str,
        stack_filter: str,
    ) -> List[Violation]:
        """Validate specific stacks matching a filter pattern.

        Args:
            project_dir: Root directory of the project.
            stack_filter: Terragrunt filter expression.

        Returns:
            List of Violation objects. Empty if plan is skipped.
        """
        if not self.is_enabled:
            return []

        if not self._check_binary_available():
            return []

        try:
            result = self.plan_runner.run_filtered(project_dir, stack_filter)

            if result.skipped:
                logger.info(f"Filtered plan skipped: {result.skip_reason}")
                return []

            return result.violations

        except Exception as e:
            logger.warning(f"Filtered plan validation failed: {e}")
            return []

    # ==================================================================
    # Stack Discovery
    # ==================================================================

    def discover_stacks(self, project_dir: str) -> List[str]:
        """Find all stacks in the project using terragrunt find.

        Returns:
            List of relative stack paths. Empty if discovery fails.
        """
        import json
        import subprocess

        tg_bin = shutil.which("terragrunt")
        if not tg_bin:
            return []

        try:
            result = subprocess.run(
                ["terragrunt", "find", "--format", "json",
                 "--working-dir", project_dir],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                # terragrunt find --format json returns a list of paths
                if isinstance(data, list):
                    return data
            return []
        except Exception as e:
            logger.debug(f"Stack discovery failed: {e}")
            return []

    # ==================================================================
    # Internal Helpers
    # ==================================================================

    def _check_binary_available(self) -> bool:
        """Check if the required binary (terragrunt or terraform) is available."""
        is_terragrunt = self.project_type in ("terraform-terragrunt", "terragrunt")

        if is_terragrunt:
            if not shutil.which("terragrunt"):
                logger.debug("Terragrunt binary not found — skipping plan validation")
                return False
        else:
            if not (shutil.which(self.tftool) or shutil.which("terraform")):
                logger.debug(
                    f"No {self.tftool}/terraform binary — skipping plan validation"
                )
                return False

        return True
