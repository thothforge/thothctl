"""State resolver for plan validation execution context.

Determines WHERE and HOW plan validation should execute:

For terragrunt projects (v0.99+):
  - In-place: writes generated .tf files to their target stack directory
  - Terragrunt handles backend, provider, init, credentials natively
  - Rollback: removes written files if plan fails or --dry-run

For plain terraform/tofu projects:
  - Temp workspace: uses existing GenerationValidator temp dir pattern
  - Backend config injected from project's backend.tf
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .models import GeneratedFile, PlanContext, PlanMode, StateConfig

logger = logging.getLogger(__name__)


class StateResolver:
    """Resolves plan execution context based on project type and configuration."""

    def resolve(
        self,
        project_dir: str,
        project_type: str,
        stack_path: str = "",
        plan_mode: PlanMode = PlanMode.PER_STACK,
    ) -> PlanContext:
        """Determine the plan execution context.

        For terragrunt projects:
          Returns in-place context (work_dir = project_dir/stack_path).
          Terragrunt handles everything: backend, provider, init.

        For terraform projects:
          Returns temp workspace context (work_dir will be set later by caller).

        Args:
            project_dir: Root of the IaC project.
            project_type: Detected project type (terraform-terragrunt, terraform, etc.)
            stack_path: Relative path to specific stack (for per-stack mode).
            plan_mode: Requested plan validation mode.

        Returns:
            PlanContext with execution parameters.
        """
        is_terragrunt = project_type in ("terraform-terragrunt", "terragrunt")

        if is_terragrunt:
            # In-place: terragrunt plan runs in the stack directory
            if stack_path:
                work_dir = str(Path(project_dir) / stack_path)
            else:
                work_dir = project_dir

            return PlanContext(
                mode=plan_mode,
                work_dir=work_dir,
                project_type=project_type,
                stack_path=stack_path,
                is_in_place=True,
                written_files=[],
            )
        else:
            # Temp workspace: terraform plan runs in isolated dir
            return PlanContext(
                mode=plan_mode,
                work_dir="",  # Will be set to temp_dir by caller
                project_type=project_type,
                stack_path=stack_path,
                is_in_place=False,
                written_files=[],
            )

    def write_files_for_plan(
        self,
        files: List[GeneratedFile],
        context: PlanContext,
    ) -> PlanContext:
        """Write generated files to the plan execution directory.

        For terragrunt (in-place):
          Writes .tf files to the stack directory in the real project.
          Tracks written paths for rollback.

        For terraform (temp workspace):
          Files are already written by GenerationValidator._create_temp_workspace().
          This method is a no-op (returns context unchanged).

        Args:
            files: Generated files to write.
            context: Plan context (determines where to write).

        Returns:
            Updated PlanContext with written_files populated.
        """
        if not context.is_in_place:
            # Temp workspace mode — files handled by GenerationValidator
            return context

        # In-place mode: write to real project directory
        work_dir = Path(context.work_dir)
        written: List[str] = []

        try:
            work_dir.mkdir(parents=True, exist_ok=True)

            for f in files:
                # Only write .tf files (not terragrunt.hcl — that's from assembler)
                if not f.path.endswith((".tf", ".tfvars")):
                    continue

                # Extract just the filename (AI might return nested paths)
                filename = Path(f.path).name
                file_path = work_dir / filename

                # Don't overwrite existing files (safety)
                if file_path.exists():
                    backup = file_path.with_suffix(file_path.suffix + ".thothctl_bak")
                    shutil.copy2(file_path, backup)
                    written.append(str(backup))
                    logger.debug(f"Backed up existing: {file_path} → {backup}")

                file_path.write_text(f.content, encoding="utf-8")
                written.append(str(file_path))
                logger.debug(f"Written for plan: {file_path}")

        except Exception as e:
            logger.error(f"Failed to write files for plan validation: {e}")
            # Rollback anything written so far
            self.rollback(PlanContext(
                mode=context.mode,
                work_dir=context.work_dir,
                project_type=context.project_type,
                stack_path=context.stack_path,
                is_in_place=True,
                written_files=written,
            ))
            raise

        # Return updated context with tracked files
        return PlanContext(
            mode=context.mode,
            work_dir=context.work_dir,
            project_type=context.project_type,
            stack_path=context.stack_path,
            is_in_place=context.is_in_place,
            written_files=written,
        )

    def rollback(self, context: PlanContext) -> None:
        """Remove files written for plan validation (rollback).

        Called when:
        - Plan validation fails and self-correction will retry
        - User ran in --dry-run mode (files should not persist)
        - An error occurred during plan execution

        For in-place mode: removes written .tf files and restores backups.
        For temp workspace: no-op (temp dir cleaned by GenerationValidator).
        """
        if not context.is_in_place or not context.written_files:
            return

        for file_path_str in context.written_files:
            file_path = Path(file_path_str)

            if not file_path.exists():
                continue

            if file_path.suffix == ".thothctl_bak":
                # This is a backup — restore the original
                original = file_path.with_suffix("")
                if file_path.exists():
                    shutil.move(str(file_path), str(original))
                    logger.debug(f"Restored backup: {file_path} → {original}")
            else:
                # This is a generated file — remove it
                file_path.unlink(missing_ok=True)
                logger.debug(f"Rolled back: {file_path}")

        logger.info(
            f"Rollback complete: {len(context.written_files)} file(s) in "
            f"{context.work_dir}"
        )

    def detect_terragrunt_project(self, directory: str) -> bool:
        """Check if directory is a terragrunt project (has root.hcl or terragrunt.hcl)."""
        dir_path = Path(directory)
        return (
            (dir_path / "root.hcl").exists()
            or (dir_path / "terragrunt.hcl").exists()
        )

    def find_terragrunt_binary(self) -> Optional[str]:
        """Find terragrunt binary."""
        return shutil.which("terragrunt")

    def find_tf_binary(self, prefer: str = "tofu") -> Optional[str]:
        """Find terraform or tofu binary (for non-terragrunt projects)."""
        # Prefer tofu (same as drift service)
        for name in ([prefer, "terraform"] if prefer == "tofu" else [prefer, "tofu"]):
            path = shutil.which(name)
            if path:
                return path
        return None
