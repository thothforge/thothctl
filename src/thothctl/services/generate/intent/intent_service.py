"""Intent-to-IaC pipeline orchestrator.

Wires together: context → generate → validate → self-correct → output.
This is the main entry point called by the CLI command and MCP tool.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from .code_generator import CodeGenerator
from .context_builder import ContextBuilder
from .models import (
    GeneratedFile,
    IntentResult,
    ValidationResult,
)
from .validator import GenerationValidator

logger = logging.getLogger(__name__)


class IntentToIaCService:
    """Orchestrates the full Intent-to-IaC generation pipeline."""

    def __init__(
        self,
        provider: str = "ollama",
        model: str = None,
    ):
        """Initialize the service with an AI provider.

        Args:
            provider: AI provider name (ollama, bedrock, openai, azure)
            model: Optional model override
        """
        self.provider = provider
        self.model = model
        self.context_builder = ContextBuilder()
        self.code_generator = CodeGenerator(provider=provider, model=model)
        self.validator = GenerationValidator()

    def generate(
        self,
        intent: str,
        directory: str = ".",
        project_type: str = "auto",
        output_dir: Optional[str] = None,
        apply: bool = False,
        self_correct: bool = True,
        max_iterations: int = 3,
        skip_validation: bool = False,
        include_diagram: bool = True,
    ) -> IntentResult:
        """Run the full Intent-to-IaC pipeline.

        Args:
            intent: Natural language description of desired infrastructure
            directory: Project root (for loading context)
            project_type: Target project type (auto, terraform, terraform-terragrunt, etc.)
            output_dir: Where to write files (default: current directory)
            apply: If True, write files to disk. If False, dry-run only.
            self_correct: If True, re-prompt AI on validation failures
            max_iterations: Maximum self-correction attempts
            skip_validation: Skip Checkov/OPA validation entirely
            include_diagram: Generate Mermaid diagram of the output

        Returns:
            IntentResult with generated files, validation status, and metadata
        """
        logger.info(
            f"Intent-to-IaC: '{intent[:80]}' (type={project_type}, provider={self.provider})"
        )

        # Step 1: Build context
        context_payload = self.context_builder.build_context(directory, project_type)
        context_text = context_payload.compile()
        resolved_type = context_payload.project_type

        logger.info(
            f"Context compiled: {context_payload.total_tokens_estimate} tokens (type={resolved_type})"
        )

        # Step 2: Generate
        generation = self.code_generator.generate(intent, context_text, resolved_type)

        if not generation.files:
            return IntentResult(
                success=False,
                error=f"AI returned no files. Raw: {generation.raw_response[:500] if generation.raw_response else 'empty'}",
                context_tokens=context_payload.total_tokens_estimate,
            )

        # Step 3: Validate + self-correct loop
        validation = ValidationResult(passed=True)
        iterations = 0

        if not skip_validation:
            org_policy_dir = self._resolve_org_policy_dir(directory)

            for i in range(max_iterations if self_correct else 1):
                iterations = i + 1
                validation = self.validator.validate(
                    files=generation.files,
                    org_policy_dir=org_policy_dir,
                )

                if validation.passed:
                    logger.info(f"Validation passed (iteration {iterations})")
                    break

                logger.info(
                    f"Validation failed: {validation.total_violations} violations "
                    f"(iteration {iterations}/{max_iterations})"
                )

                # Self-correct if enabled and not on last iteration
                if self_correct and i < max_iterations - 1:
                    generation = self.code_generator.fix(
                        generation, validation, context_text
                    )
                    if not generation.files:
                        break  # Fix produced nothing — stop
        else:
            iterations = 0

        # Step 4: Write to disk if --apply
        if apply and generation.files:
            target = output_dir or directory
            self._write_files(generation.files, target)
            logger.info(f"Files written to: {target}")

        # Step 5: Generate diagram (optional)
        if include_diagram and generation.files and apply:
            self._generate_diagram(output_dir or directory)

        return IntentResult(
            success=generation.file_count > 0,
            files=generation.files,
            validation=validation,
            iterations=iterations,
            explanation=generation.explanation,
            modules_used=generation.modules_used,
            estimated_resources=generation.estimated_resources,
            context_tokens=context_payload.total_tokens_estimate,
            generation_tokens=0,  # Provider doesn't expose this cleanly yet
        )

    # ------------------------------------------------------------------
    # File output
    # ------------------------------------------------------------------

    def _write_files(self, files: List[GeneratedFile], target_dir: str) -> None:
        """Write generated files to the target directory."""
        target = Path(target_dir)
        for f in files:
            file_path = target / f.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f.content, encoding="utf-8")
            logger.debug(f"Written: {file_path}")

    # ------------------------------------------------------------------
    # Org policy resolution
    # ------------------------------------------------------------------

    def _resolve_org_policy_dir(self, directory: str) -> Optional[str]:
        """Find org policy directory for OPA validation.

        Checks (in order):
        1. Local policies/ directory
        2. Local policy/ directory
        3. THOTH_ORG_POLICY env var (if it's a local path)
        4. Cached org policy repo (~/.thothcf/.policy_cache/)
        """
        # Local policy dirs
        for name in ("policies", "policy"):
            local_dir = os.path.join(directory, name)
            if os.path.isdir(local_dir):
                rego_files = list(Path(local_dir).rglob("*.rego"))
                if rego_files:
                    return local_dir

        # Env var (only local paths, not git:: URLs)
        env_policy = os.environ.get("THOTH_ORG_POLICY", "")
        if (
            env_policy
            and not env_policy.startswith("git::")
            and os.path.isdir(env_policy)
        ):
            return env_policy

        # Cached org policy
        cache_dir = Path.home() / ".thothcf" / ".policy_cache"
        if cache_dir.exists():
            for d in cache_dir.iterdir():
                if d.is_dir() and list(d.rglob("*.rego")):
                    return str(d)

        return None

    # ------------------------------------------------------------------
    # Diagram generation
    # ------------------------------------------------------------------

    def _generate_diagram(self, directory: str) -> Optional[str]:
        """Generate a Mermaid diagram from the output (best-effort)."""
        try:
            from ...document.topology_generator import TopologyGenerator

            TopologyGenerator()
            # topology_generator works from tfplan.json — which we don't have
            # For now, return None (diagram generation requires plan)
            # Future: generate diagram from resource list
            return None
        except Exception:
            return None
