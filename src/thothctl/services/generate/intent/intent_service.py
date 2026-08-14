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
        plan_config: Optional[dict] = None,
    ):
        """Initialize the service with an AI provider.

        Args:
            provider: AI provider name (ollama, bedrock, openai, azure)
            model: Optional model override
            plan_config: Optional plan validation config from .thothcf.toml [generation.plan].
                         Enables terraform plan validation when plan_validation != "disabled".
        """
        self.provider = provider
        self.model = model
        self.plan_config = plan_config
        self.context_builder = ContextBuilder()
        self.code_generator = CodeGenerator(provider=provider, model=model)
        self.validator = GenerationValidator(plan_config=plan_config)

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
        composition: str = "single",
        output_mode: str = "project",
        space: Optional[str] = None,
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
            composition: Generation mode: single (default), full (project), incremental

        Returns:
            IntentResult with generated files, validation status, and metadata
        """
        # Route to composition generation if requested
        if composition in ("full", "incremental"):
            return self._generate_composition(
                intent=intent,
                directory=directory,
                project_type=project_type,
                output_dir=output_dir,
                apply=apply,
                self_correct=self_correct,
                max_iterations=max_iterations,
                skip_validation=skip_validation,
                include_diagram=include_diagram,
                incremental=(composition == "incremental"),
                output_mode=output_mode,
                space=space,
            )

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
            previous_violation_count = float("inf")
            stagnation_counter = 0

            for i in range(max_iterations if self_correct else 1):
                iterations = i + 1
                validation = self.validator.validate(
                    files=generation.files,
                    project_type=resolved_type,
                    project_dir=directory,
                    org_policy_dir=org_policy_dir,
                )

                if validation.passed:
                    logger.info(f"Validation passed (iteration {iterations})")
                    break

                logger.info(
                    f"Validation failed: {validation.total_violations} violations "
                    f"(iteration {iterations}/{max_iterations})"
                )

                # Convergence detection: stop if violations aren't improving
                current_count = validation.total_violations
                if current_count >= previous_violation_count:
                    stagnation_counter += 1
                    if stagnation_counter >= 3:
                        logger.info(
                            "Self-correction stagnated (no improvement in 3 iterations)"
                            " — stopping"
                        )
                        break
                else:
                    stagnation_counter = 0
                previous_violation_count = current_count

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
        diagram = None
        if include_diagram and generation.files:
            diagram = self._generate_diagram(
                output_dir or directory,
                files=generation.files,
                resources=generation.estimated_resources,
                apply=apply,
            )

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
            diagram=diagram,
        )

    # ------------------------------------------------------------------
    # File output
    # ------------------------------------------------------------------

    def _write_files(self, files: List[GeneratedFile], target_dir: str) -> None:
        """Write generated files to the target directory."""
        target = Path(target_dir).resolve()
        for f in files:
            # Security: validate path stays within target directory
            file_path = (target / f.path).resolve()
            if not str(file_path).startswith(str(target)):
                logger.warning(f"Path traversal blocked: {f.path}")
                continue
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

    def _generate_diagram(
        self,
        directory: str,
        files: List[GeneratedFile] = None,
        resources: List[str] = None,
        apply: bool = False,
    ) -> Optional[str]:
        """Generate a Mermaid architecture diagram from generated resources.

        Works without tfplan.json by building diagram from:
        1. estimated_resources list (resource types)
        2. File structure (modules/stacks)
        3. Resource relationships inferred from type names

        Returns:
            Mermaid diagram string, or None on failure.
        """
        try:
            # Build resource list from estimated_resources or file analysis
            resource_types = resources or []

            if not resource_types and files:
                # Extract resource types from generated .tf/.yaml files
                resource_types = self._extract_resource_types(files)

            if not resource_types:
                return None

            # Generate Mermaid diagram
            mermaid = self._build_mermaid_diagram(resource_types)

            # Write to file (only when --apply, not in dry-run)
            if apply:
                diagram_path = Path(directory) / "architecture.md"
                diagram_content = (
                    f"# Architecture Diagram\n\n```mermaid\n{mermaid}\n```\n"
                )
                diagram_path.write_text(diagram_content, encoding="utf-8")
                logger.info(f"Architecture diagram written to {diagram_path}")

            return mermaid

        except Exception as e:
            logger.warning(f"Diagram generation failed: {e}")
            return None

    def _extract_resource_types(self, files: List[GeneratedFile]) -> List[str]:
        """Extract resource type names from generated files."""
        import re

        resource_types = []

        for f in files:
            # Terraform: resource "aws_vpc" "main" {
            tf_resources = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', f.content)
            for rtype, rname in tf_resources:
                resource_types.append(f"{rtype}.{rname}")

            # CloudFormation: Type: AWS::EC2::VPC
            cfn_resources = re.findall(r"Type:\s*(AWS::[A-Za-z0-9:]+)", f.content)
            resource_types.extend(cfn_resources)

            # CDK: new ec2.Vpc(... or new s3.Bucket(...
            cdk_resources = re.findall(
                r"new\s+([a-z][a-z0-9_]*)\.([A-Z][A-Za-z]+)\(", f.content
            )
            for module, construct in cdk_resources:
                resource_types.append(f"aws_{module}_{construct.lower()}")

        return resource_types

    def _build_mermaid_diagram(self, resource_types: List[str]) -> str:
        """Build a Mermaid architecture diagram from resource types."""
        # Categorize resources into layers
        layers = {
            "Network": [],
            "Compute": [],
            "Storage": [],
            "Database": [],
            "Security": [],
            "Other": [],
        }

        layer_patterns = {
            "Network": [
                "vpc",
                "subnet",
                "gateway",
                "route",
                "nat",
                "elb",
                "alb",
                "nlb",
                "lb",
                "cloudfront",
                "VPC",
                "Subnet",
                "InternetGateway",
                "NATGateway",
                "LoadBalancer",
                "ElasticLoadBalancing",
            ],
            "Database": [
                "rds",
                "db_instance",
                "db_cluster",
                "dynamodb",
                "elasticache",
                "aurora",
                "redshift",
                "DBInstance",
                "DBCluster",
                "Table",
                "ReplicationGroup",
            ],
            "Compute": [
                "instance",
                "ec2",
                "lambda",
                "ecs",
                "eks",
                "fargate",
                "auto_scaling",
                "launch_template",
                "Function",
                "Instance",
                "Cluster",
                "Service",
                "TaskDefinition",
            ],
            "Storage": [
                "s3",
                "bucket",
                "ebs",
                "efs",
                "Bucket",
                "FileSystem",
            ],
            "Security": [
                "iam",
                "security_group",
                "kms",
                "waf",
                "acl",
                "policy",
                "role",
                "Role",
                "Policy",
                "SecurityGroup",
                "Key",
            ],
        }

        for resource in resource_types:
            placed = False
            for layer_name, patterns in layer_patterns.items():
                if any(p.lower() in resource.lower() for p in patterns):
                    layers[layer_name].append(resource)
                    placed = True
                    break
            if not placed:
                layers["Other"].append(resource)

        # Build Mermaid graph
        lines = ["graph TB"]

        for layer_name, resources in layers.items():
            if not resources:
                continue

            # Create subgraph per layer
            layer_id = layer_name.lower()
            lines.append(f'    subgraph {layer_id}["{layer_name} Layer"]')

            for i, resource in enumerate(resources[:8]):  # Limit per layer
                # Clean resource name for display
                display_name = resource.split(".")[-1] if "." in resource else resource
                display_name = display_name.replace("aws_", "").replace("AWS::", "")
                node_id = f"{layer_id}_{i}"
                lines.append(f'        {node_id}["{display_name}"]')

            lines.append("    end")

        # Add connections between layers (inferred)
        active_layers = [layer for layer in layers if layers[layer]]
        # Network → Compute, Compute → Database, Security → all
        connections = [
            ("Network", "Compute"),
            ("Compute", "Database"),
            ("Compute", "Storage"),
            ("Network", "Database"),
        ]
        for src, dst in connections:
            if src in active_layers and dst in active_layers:
                src_id = f"{src.lower()}_0"
                dst_id = f"{dst.lower()}_0"
                lines.append(f"    {src_id} --> {dst_id}")

        return "\n".join(lines)

    def _load_scaffold_example(self, project_type: str, stack) -> str:
        """Load a real scaffold example as few-shot context for per-stack generation.

        Fetches the official scaffold from GitHub (cached locally) and uses its
        real stack files as examples the AI should follow. The scaffold IS the
        source of truth for code structure.

        Resolution order:
        1. Local cache (~/.thothcf/<scaffold_name>/)
        2. Auto-clone from GitHub (thothforge org) on first use
        """
        from pathlib import Path

        # Official scaffolds per project type
        scaffold_registry = {
            "terraform-terragrunt": {
                "name": "terraform_terragrunt_scaffold_project",
                "repo": "thothforge/terraform_terragrunt_scaffold_project",
            },
            "terragrunt": {
                "name": "terraform_terragrunt_scaffold_project",
                "repo": "thothforge/terraform_terragrunt_scaffold_project",
            },
            "terraform": {
                "name": "terraform_project_scaffold",
                "repo": "thothforge/terraform_project_scaffold",
            },
            "cdkv2": {
                "name": "cdkv2_typescript_scaffold",
                "repo": "thothforge/cdkv2_typescript_scaffold",
            },
        }

        scaffold_info = scaffold_registry.get(project_type)
        if not scaffold_info:
            return self._default_composition_rules()

        scaffold_cache = Path.home() / ".thothcf"
        scaffold_dir = scaffold_cache / scaffold_info["name"]

        # Auto-fetch scaffold from GitHub if not cached
        if not scaffold_dir.exists() or not list(scaffold_dir.rglob("*.tf")):
            scaffold_dir = self._fetch_scaffold(scaffold_info["repo"], scaffold_dir)

        example_parts = []

        if scaffold_dir.exists():
            # Find a matching or similar stack in the scaffold
            stacks_dir = scaffold_dir / "stacks"
            if stacks_dir.exists():
                # Try exact match first, then same domain, then any from same layer
                candidates = list(stacks_dir.rglob("main.tf"))
                best_match = None

                for candidate in candidates:
                    rel = str(candidate.relative_to(stacks_dir))
                    if stack.domain in rel or stack.name in rel:
                        best_match = candidate.parent
                        break

                if not best_match and candidates:
                    # Take first example from the same layer
                    for candidate in candidates:
                        rel = str(candidate.relative_to(stacks_dir))
                        if stack.layer in rel:
                            best_match = candidate.parent
                            break

                if best_match:
                    # Load the example files
                    for tf_file in sorted(best_match.glob("*.tf")):
                        content = tf_file.read_text(encoding="utf-8", errors="ignore")
                        if content.strip():
                            example_parts.append(
                                f"### Scaffold example: {tf_file.name}\n```hcl\n{content.strip()}\n```"
                            )
                    tg_file = best_match / "terragrunt.hcl"
                    if tg_file.exists():
                        content = tg_file.read_text(encoding="utf-8", errors="ignore")
                        if content.strip():
                            example_parts.append(
                                f"### Scaffold example: terragrunt.hcl\n```hcl\n{content.strip()}\n```"
                            )

        # Always include the composition rules (whether scaffold found or not)
        rules = (
            "COMPOSITION RULES (from scaffold):\n"
            "- Generate EXACTLY these files with STRICT content separation:\n"
            "  * variables.tf — ONLY variable blocks (all inputs for this stack)\n"
            "  * main.tf — ONLY resources, modules, data sources, locals\n"
            "  * outputs.tf — ONLY output blocks (values for dependent stacks)\n"
            "- NEVER put variable blocks in main.tf\n"
            "- NEVER put output blocks in main.tf\n"
            "- NEVER include terraform{}, provider{}, or backend{} blocks "
            "(managed by root.hcl)\n"
            "- Use var.tags for tags (passed from terragrunt inputs)\n"
            "- Use var.project and var.environment for naming\n"
            "- File paths must be flat (just filename, no subdirectories)\n"
        )

        if example_parts:
            return (
                "FOLLOW THIS SCAFFOLD PATTERN (from your org's official scaffold):\n\n"
                + "\n\n".join(example_parts[:3])  # Max 3 files as example
                + f"\n\n{rules}"
            )
        else:
            return rules

    @staticmethod
    def _fetch_scaffold(repo: str, target_dir) -> "Path":
        """Fetch official scaffold from GitHub via gh CLI (cached locally)."""
        import shutil
        import subprocess
        from pathlib import Path

        target = Path(target_dir)

        if shutil.which("gh"):
            try:
                logger.info(f"Fetching scaffold from github.com/{repo}...")
                target.parent.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(
                    ["gh", "repo", "clone", repo, str(target), "--", "--depth=1"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"Scaffold cached at {target}")
                    return target
                else:
                    logger.warning(f"Failed to fetch scaffold: {result.stderr[:200]}")
            except Exception as e:
                logger.warning(f"Scaffold fetch failed: {e}")

        return target

    @staticmethod
    def _default_composition_rules() -> str:
        """Fallback composition rules when no scaffold is available."""
        return (
            "COMPOSITION RULES:\n"
            "- Generate EXACTLY these files with STRICT content separation:\n"
            "  * variables.tf — ONLY variable blocks (all inputs)\n"
            "  * main.tf — ONLY resources, modules, data sources, locals\n"
            "  * outputs.tf — ONLY output blocks\n"
            "- NEVER put variable or output blocks in main.tf\n"
            "- NEVER include terraform{}, provider{}, or backend{} blocks\n"
            "- Provider and backend are managed by root.hcl (terragrunt generates them)\n"
            "- Use var.tags for tags (passed from terragrunt inputs)\n"
            "- Use var.project and var.environment for naming\n"
        )

    @staticmethod
    def _strip_terraform_block(content: str) -> str:
        """Remove terraform {}, provider {}, and backend blocks from generated code.

        In terragrunt projects, root.hcl handles provider and backend config.
        Per-stack .tf files should only contain resources, data sources, and locals.
        """
        import re

        # Remove terraform { ... } block (multi-line, handles nested braces)
        content = re.sub(
            r"terraform\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?",
            "",
            content,
            flags=re.DOTALL,
        )

        # Remove provider "aws" { ... } block
        content = re.sub(
            r'provider\s+"[^"]+"\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?',
            "",
            content,
            flags=re.DOTALL,
        )

        # Clean up excessive blank lines left behind
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip() + "\n"

    # ------------------------------------------------------------------
    # Composition generation (multi-stack)
    # ------------------------------------------------------------------

    def _generate_composition(
        self,
        intent: str,
        directory: str,
        project_type: str,
        output_dir: Optional[str],
        apply: bool,
        self_correct: bool,
        max_iterations: int,
        skip_validation: bool,
        include_diagram: bool,
        incremental: bool = False,
        output_mode: str = "project",
        space: Optional[str] = None,
    ) -> IntentResult:
        """Generate a full multi-stack project from a complex intent.

        Uses scaffold-driven generation:
        1. Load scaffold structure (deterministic skeleton)
        2. Build context
        3. Decompose intent into stacks (AI call)
        4. Assemble project structure using scaffold boilerplate (deterministic)
        5. Generate code per stack using scaffold examples as context (AI per stack)
        6. Post-process: validate completeness against scaffold rules
        7. Validate + write
        """
        from .intent_decomposer import IntentDecomposer
        from .project_assembler import ProjectAssembler
        from .scaffold_loader import ScaffoldLoader

        logger.info(
            f"Composition generation: '{intent[:80]}' "
            f"(type={project_type}, mode={'incremental' if incremental else 'full'})"
        )

        # Step 1: Load scaffold structure (deterministic skeleton)
        # The scaffold defines the project skeleton — AI only fills resource content.
        scaffold_loader = ScaffoldLoader(project_type=project_type)
        scaffold = scaffold_loader.load()
        logger.info(
            f"Scaffold loaded: {scaffold.project_type} "
            f"(root_files={len(scaffold.root_files)}, "
            f"boilerplate={len(scaffold.boilerplate)}, "
            f"examples={len(scaffold.examples)})"
        )

        # Step 2: Build context
        context_payload = self.context_builder.build_context(directory, project_type)
        context_text = context_payload.compile()
        resolved_type = context_payload.project_type

        # Step 3: Decompose intent into stacks
        decomposer = IntentDecomposer(provider=self.provider, model=self.model)
        plan = decomposer.decompose(intent, resolved_type, context_text)

        if not plan or not plan.stacks:
            return IntentResult(
                success=False,
                error="Failed to decompose intent into stacks",
                context_tokens=context_payload.total_tokens_estimate,
            )

        logger.info(
            f"Decomposed into {plan.stack_count} stacks: "
            f"{[s.name for s in plan.stacks]}"
        )

        # Determine if root config exists
        target_dir = output_dir or directory
        plan.needs_root_config = not Path(target_dir).joinpath("root.hcl").exists()
        plan.needs_common = not Path(target_dir).joinpath("common").exists()

        if incremental:
            plan.needs_root_config = False
            plan.needs_common = False

        # Step 4: Assemble project structure using scaffold boilerplate
        assembler = ProjectAssembler(project_type=resolved_type)
        structure_files = assembler.assemble(
            plan, target_dir, existing_project=incremental, scaffold=scaffold
        )

        # Step 5: Generate code per stack using scaffold examples as context
        all_files = list(structure_files)
        try:
            ordered_stacks = plan.topological_order()
        except ValueError as e:
            return IntentResult(
                success=False,
                error=f"Circular dependency in stack plan: {e}",
                context_tokens=context_payload.total_tokens_estimate,
            )

        for stack in ordered_stacks:
            logger.info(f"Generating stack: {stack.path} ({stack.intent[:50]})")

            # Build scaffold context for this stack from loaded scaffold
            scaffold_context = self._build_scaffold_context(scaffold, stack)
            stack_intent = f"{stack.intent}\n\n{scaffold_context}"

            # Generate the Terraform code for this stack
            stack_generation = self.code_generator.generate(
                intent=stack_intent,
                context=context_text,
                project_type="terraform",  # Generate pure TF resources
            )

            if stack_generation.files:
                # Prefix file paths with stack path
                # Strip any nested path from AI output — keep only filename
                stack_tf_files = []
                for f in stack_generation.files:
                    # AI sometimes returns full paths or nested structures
                    # We only want the filename (main.tf, variables.tf, etc.)
                    filename = Path(f.path).name
                    # Skip files that aren't Terraform files
                    if not filename.endswith((".tf", ".tfvars", ".hcl", ".md")):
                        continue
                    # Skip if AI regenerated a terragrunt.hcl (assembler already made one)
                    if filename == "terragrunt.hcl":
                        continue
                    # Strip terraform/provider/backend blocks from .tf files
                    # (root.hcl handles these in terragrunt projects)
                    content = f.content
                    if resolved_type in ("terraform-terragrunt", "terragrunt"):
                        content = self._strip_terraform_block(content)
                    prefixed_path = f"{stack.path}/{filename}"
                    stack_tf_files.append(
                        GeneratedFile(path=prefixed_path, content=content)
                    )

                # Per-stack plan validation (if enabled)
                # Validates this stack via `terragrunt plan` before moving to next
                if (
                    not skip_validation
                    and self.validator._plan_validator
                    and stack_tf_files
                ):
                    max_plan_retries = min(max_iterations, 3)
                    for plan_attempt in range(max_plan_retries):
                        plan_violations = (
                            self.validator._plan_validator.validate_per_stack(
                                files=stack_tf_files,
                                project_dir=target_dir,
                                stack_path=stack.path,
                            )
                        )
                        if not plan_violations:
                            break  # Plan passed

                        if not self_correct or plan_attempt >= max_plan_retries - 1:
                            break  # Can't fix or last attempt

                        logger.info(
                            f"Plan validation failed for {stack.path}: "
                            f"{len(plan_violations)} violations "
                            f"(attempt {plan_attempt + 1}/{max_plan_retries})"
                        )
                        # Build a ValidationResult for the fix() method
                        plan_vr = ValidationResult(
                            passed=False, violations=plan_violations
                        )
                        # Re-generate with violation feedback
                        stack_generation = self.code_generator.fix(
                            stack_generation, plan_vr, context_text
                        )
                        # Re-process the fixed files
                        stack_tf_files = []
                        for f in stack_generation.files:
                            filename = Path(f.path).name
                            if not filename.endswith((".tf", ".tfvars")):
                                continue
                            if filename == "terragrunt.hcl":
                                continue
                            content = f.content
                            if resolved_type in (
                                "terraform-terragrunt",
                                "terragrunt",
                            ):
                                content = self._strip_terraform_block(content)
                            prefixed_path = f"{stack.path}/{filename}"
                            stack_tf_files.append(
                                GeneratedFile(path=prefixed_path, content=content)
                            )

                all_files.extend(stack_tf_files)

        if not all_files:
            return IntentResult(
                success=False,
                error="No files generated for any stack",
                context_tokens=context_payload.total_tokens_estimate,
            )

        # Step 6: Post-process — ensure completeness against scaffold rules
        all_files = self._ensure_scaffold_completeness(
            all_files, scaffold, ordered_stacks
        )

        # Step 7: Validate (optional)
        validation = ValidationResult(passed=True)
        if not skip_validation:
            org_policy_dir = self._resolve_org_policy_dir(directory)
            validation = self.validator.validate(
                files=all_files,
                project_type=resolved_type,
                project_dir=directory,
                org_policy_dir=org_policy_dir,
                skip_framework_validate=True,  # Can't run terraform validate on partial project
                skip_plan=True,  # Plan already validated per-stack during generation
            )

        # Step 7.5: Resolve #{...}# placeholders when mode=project
        if output_mode == "project" and all_files:
            all_files = self._resolve_placeholders(
                files=all_files,
                intent=intent,
                space=space,
                project_name=self._derive_project_name(output_dir, intent),
                scaffold_dir=scaffold_loader.scaffold_dir if hasattr(scaffold_loader, 'scaffold_dir') else None,
            )

        # Step 8: Write to disk if --apply
        if apply and all_files:
            self._write_files(all_files, target_dir)
            logger.info(f"Project written to: {target_dir}")

        # Step 9: Generate diagram
        diagram = None
        if include_diagram and all_files:
            resources = []
            for stack in ordered_stacks:
                resources.append(f"stack_{stack.layer}_{stack.name}")
            diagram = self._build_mermaid_diagram(resources)

        return IntentResult(
            success=True,
            files=all_files,
            validation=validation,
            iterations=1,
            explanation=(
                f"Generated {plan.stack_count} stacks across layers: "
                + ", ".join(f"{s.layer}/{s.domain}/{s.name}" for s in ordered_stacks)
            ),
            modules_used=[s.module_source for s in plan.stacks if s.module_source],
            estimated_resources=[s.name for s in plan.stacks],
            context_tokens=context_payload.total_tokens_estimate,
            generation_tokens=sum(len(f.content) // 4 for f in all_files),
            diagram=diagram,
        )

    # ------------------------------------------------------------------
    # Scaffold-driven helpers (Tasks 3-6)
    # ------------------------------------------------------------------

    def _build_scaffold_context(self, scaffold, stack) -> str:
        """Build scaffold context for per-stack generation from ScaffoldStructure.

        Uses scaffold.examples to find the best matching few-shot pattern for
        the current stack (by domain/layer/name similarity). Falls back to
        composition rules if no example matches.

        Args:
            scaffold: ScaffoldStructure with examples and rules.
            stack: StackPlan being generated.

        Returns:
            Prompt section with scaffold examples and rules.
        """

        example_parts = []

        if scaffold.examples:
            # Find best matching examples: prefer same domain, then same layer
            scored_examples = []
            for rel_path, content in scaffold.examples.items():
                score = 0
                path_lower = rel_path.lower()
                if stack.domain and stack.domain in path_lower:
                    score += 3
                if stack.name and stack.name in path_lower:
                    score += 5
                if stack.layer and stack.layer in path_lower:
                    score += 2
                scored_examples.append((score, rel_path, content))

            # Sort by score descending, take top 3
            scored_examples.sort(key=lambda x: x[0], reverse=True)
            for _score, rel_path, content in scored_examples[:3]:
                example_parts.append(
                    f"### Scaffold example: {rel_path}\n```hcl\n{content.strip()}\n```"
                )

        # Build composition rules from scaffold metadata
        required_files = ", ".join(scaffold.stack_required_files) or (
            "main.tf, variables.tf, outputs.tf"
        )
        rules = (
            f"COMPOSITION RULES (from scaffold):\n"
            f"- Generate ONLY these files: {required_files}\n"
            f"- main.tf must contain ONLY resources/modules/data — "
            f"NO terraform{{}}, provider{{}}, or backend{{}} blocks\n"
            f"- Provider and backend are managed by root.hcl (terragrunt generates them)\n"
            f"- Use var.tags for tags (passed from terragrunt inputs)\n"
            f"- Use var.project and var.environment for naming\n"
        )

        if example_parts:
            return (
                "FOLLOW THIS SCAFFOLD PATTERN (from your org's official scaffold):\n\n"
                + "\n\n".join(example_parts)
                + f"\n\n{rules}"
            )
        else:
            return rules

    def _ensure_scaffold_completeness(
        self, files: List[GeneratedFile], scaffold, ordered_stacks
    ) -> List[GeneratedFile]:
        """Ensure all stacks have the required files per scaffold rules.

        If the AI missed generating a required file (e.g., outputs.tf),
        add a placeholder so the project structure is complete.

        Args:
            files: All generated files so far.
            scaffold: ScaffoldStructure with stack_required_files.
            ordered_stacks: Stacks in the plan.

        Returns:
            Updated file list with any missing required files added.
        """
        if not scaffold.stack_required_files:
            return files

        # Build a set of existing file paths
        existing_paths = {f.path for f in files}
        added = []

        for stack in ordered_stacks:
            for required_file in scaffold.stack_required_files:
                # terragrunt.hcl is handled by the assembler
                if required_file == "terragrunt.hcl":
                    continue

                expected_path = f"{stack.path}/{required_file}"
                if expected_path not in existing_paths:
                    # Generate a minimal placeholder
                    placeholder = self._placeholder_for_file(
                        required_file, stack.name, stack.domain
                    )
                    added.append(GeneratedFile(path=expected_path, content=placeholder))
                    logger.info(
                        f"Scaffold completeness: added missing {expected_path}"
                    )

        if added:
            logger.info(
                f"Post-processing added {len(added)} missing required files"
            )

        return files + added

    @staticmethod
    def _placeholder_for_file(filename: str, stack_name: str, domain: str) -> str:
        """Generate a minimal placeholder for a missing required file.

        Args:
            filename: The required filename (e.g., "variables.tf", "outputs.tf").
            stack_name: Stack name for contextual comments.
            domain: Stack domain for contextual comments.

        Returns:
            Minimal valid HCL content for the file.
        """
        if filename == "variables.tf":
            return (
                f"# Variables for {stack_name} ({domain})\n"
                f"# Generated placeholder — populate with required inputs\n\n"
                f'variable "project" {{\n'
                f'  description = "Project name"\n'
                f'  type        = string\n'
                f"}}\n\n"
                f'variable "environment" {{\n'
                f'  description = "Environment name"\n'
                f'  type        = string\n'
                f"}}\n\n"
                f'variable "tags" {{\n'
                f'  description = "Common tags for all resources"\n'
                f'  type        = map(string)\n'
                f"  default     = {{}}\n"
                f"}}\n"
            )
        elif filename == "outputs.tf":
            return (
                f"# Outputs for {stack_name} ({domain})\n"
                f"# Generated placeholder — add outputs consumed by dependent stacks\n"
            )
        elif filename == "main.tf":
            return (
                f"# Main resources for {stack_name} ({domain})\n"
                f"# Generated placeholder — add resource definitions\n"
            )
        elif filename == "README.md":
            return (
                f"# {stack_name}\n\n"
                f"Stack for {domain} resources.\n\n"
                f"## Usage\n\n"
                f"```bash\n"
                f"terragrunt plan\n"
                f"terragrunt apply\n"
                f"```\n"
            )
        else:
            return f"# {filename} for {stack_name} ({domain})\n"

    # ------------------------------------------------------------------
    # Placeholder Resolution (blueprint vs project mode)
    # ------------------------------------------------------------------

    def _resolve_placeholders(
        self,
        files: List[GeneratedFile],
        intent: str,
        space: Optional[str] = None,
        project_name: Optional[str] = None,
        scaffold_dir: Optional[str] = None,
    ) -> List[GeneratedFile]:
        """Resolve #{...}# placeholders in all generated files.

        Called when output_mode="project". Replaces template placeholders
        with concrete values derived from space config, intent, and defaults.

        Args:
            files: Generated files (may contain #{...}# placeholders).
            intent: Natural language intent (for extracting region, env, etc.)
            space: Space name to load config from.
            project_name: Explicit project name (from output dir or CLI).
            scaffold_dir: Path to cached scaffold (for loading template_input_parameters).

        Returns:
            Updated list of GeneratedFile with placeholders resolved.
        """
        from .parameter_resolver import ParameterResolver

        # Load scaffold template_input_parameters if available
        scaffold_params = self._load_scaffold_params(scaffold_dir)

        resolver = ParameterResolver(
            intent=intent,
            space_name=space,
            project_name=project_name,
            scaffold_params=scaffold_params,
        )

        values = resolver.resolve_all()

        if not values:
            logger.debug("No parameter values resolved — skipping placeholder resolution")
            return files

        # Resolve placeholders in all file contents
        resolved_files = []
        for f in files:
            resolved_content = resolver.resolve_content(f.content, values)
            resolved_files.append(
                GeneratedFile(path=f.path, content=resolved_content)
            )

        # Log any remaining unresolved placeholders
        for f in resolved_files:
            unresolved = resolver.has_unresolved(f.content, values)
            if unresolved:
                logger.warning(
                    f"Unresolved placeholders in {f.path}: {unresolved}"
                )

        logger.info(
            f"Resolved placeholders in {len(resolved_files)} files "
            f"(mode=project, values: {list(values.keys())})"
        )

        return resolved_files

    @staticmethod
    def _derive_project_name(
        output_dir: Optional[str], intent: str
    ) -> Optional[str]:
        """Derive project name from output directory or intent.

        Priority:
        1. Last component of output_dir path (e.g., /tmp/vpc-test → "vpc-test")
        2. First noun-phrase from intent (simplified extraction)
        """
        if output_dir:
            name = Path(output_dir).name
            if name and name != "." and name != "/":
                return name

        # Simple extraction from intent: take first 2-3 meaningful words
        import re
        words = re.findall(r"[a-z]+", intent.lower())
        # Skip common filler words
        skip = {"create", "a", "an", "the", "with", "for", "and", "in", "my", "our"}
        meaningful = [w for w in words if w not in skip][:3]
        if meaningful:
            return "-".join(meaningful)

        return None

    @staticmethod
    def _load_scaffold_params(scaffold_dir: Optional[str]) -> dict:
        """Load template_input_parameters from scaffold's .thothcf.toml."""
        if not scaffold_dir:
            # Try default scaffold location
            scaffold_dir = str(
                Path.home() / ".thothcf" / "terraform_terragrunt_scaffold_project"
            )

        toml_path = Path(scaffold_dir) / ".thothcf.toml"
        if not toml_path.exists():
            return {}

        try:
            import toml
            data = toml.load(toml_path)
            return data.get("template_input_parameters", {})
        except Exception:
            return {}
