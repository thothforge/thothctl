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
        composition: str = "single",
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

    def _generate_diagram(
        self,
        directory: str,
        files: List[GeneratedFile] = None,
        resources: List[str] = None,
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

            # Write to file
            diagram_path = Path(directory) / "architecture.md"
            diagram_content = f"# Architecture Diagram\n\n```mermaid\n{mermaid}\n```\n"
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

        Searches cached scaffolds for a similar stack and returns its files
        as an example the AI should follow. This makes the scaffold the single
        source of truth for code structure — not hardcoded prompts.
        """
        from pathlib import Path

        # Search scaffold cache for matching examples
        scaffold_cache = Path.home() / ".thothcf"
        scaffold_names = {
            "terraform-terragrunt": "terraform_terragrunt_scaffold_project",
            "terragrunt": "terraform_terragrunt_scaffold_project",
        }
        scaffold_dir = scaffold_cache / scaffold_names.get(project_type, "")

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
            "- Generate ONLY: main.tf, variables.tf, outputs.tf (flat paths)\n"
            "- main.tf must contain ONLY resources/modules/data — "
            "NO terraform{}, provider{}, or backend{} blocks\n"
            "- Provider and backend are managed by root.hcl (terragrunt generates them)\n"
            "- Use var.tags for tags (passed from terragrunt inputs)\n"
            "- Use var.project and var.environment for naming\n"
        )

        if example_parts:
            return (
                f"FOLLOW THIS SCAFFOLD PATTERN (from your org's official scaffold):\n\n"
                + "\n\n".join(example_parts[:3])  # Max 3 files as example
                + f"\n\n{rules}"
            )
        else:
            return rules

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
    ) -> IntentResult:
        """Generate a full multi-stack project from a complex intent.

        1. Build context
        2. Decompose intent into stacks (AI call)
        3. Generate code per stack (AI call per stack)
        4. Assemble project structure (deterministic)
        5. Validate + write
        """
        from .composition_models import CompositionPlan
        from .intent_decomposer import IntentDecomposer
        from .project_assembler import ProjectAssembler

        logger.info(
            f"Composition generation: '{intent[:80]}' "
            f"(type={project_type}, mode={'incremental' if incremental else 'full'})"
        )

        # Step 1: Build context
        context_payload = self.context_builder.build_context(directory, project_type)
        context_text = context_payload.compile()
        resolved_type = context_payload.project_type

        # Step 2: Decompose intent into stacks
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

        # Step 3: Assemble project structure (root.hcl, common/, terragrunt.hcl per stack)
        assembler = ProjectAssembler(project_type=resolved_type)
        structure_files = assembler.assemble(
            plan, target_dir, existing_project=incremental
        )

        # Step 4: Generate code per stack (AI calls)
        all_files = list(structure_files)
        ordered_stacks = plan.topological_order()

        for stack in ordered_stacks:
            logger.info(f"Generating stack: {stack.path} ({stack.intent[:50]})")

            # Load scaffold example as few-shot pattern
            # The scaffold IS the source of truth, not hardcoded prompts
            scaffold_example = self._load_scaffold_example(resolved_type, stack)
            stack_intent = f"{stack.intent}\n\n{scaffold_example}"

            # Generate the Terraform code for this stack
            stack_generation = self.code_generator.generate(
                intent=stack_intent,
                context=context_text,
                project_type="terraform",  # Generate pure TF resources
            )

            if stack_generation.files:
                # Prefix file paths with stack path
                # Strip any nested path from AI output — keep only filename
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
                    all_files.append(GeneratedFile(path=prefixed_path, content=content))

        if not all_files:
            return IntentResult(
                success=False,
                error="No files generated for any stack",
                context_tokens=context_payload.total_tokens_estimate,
            )

        # Step 5: Validate (optional)
        validation = ValidationResult(passed=True)
        if not skip_validation:
            org_policy_dir = self._resolve_org_policy_dir(directory)
            validation = self.validator.validate(
                files=all_files,
                project_type=resolved_type,
                project_dir=directory,
                org_policy_dir=org_policy_dir,
                skip_framework_validate=True,  # Can't run terraform validate on partial project
            )

        # Step 6: Write to disk if --apply
        if apply and all_files:
            self._write_files(all_files, target_dir)
            logger.info(f"Project written to: {target_dir}")

        # Step 7: Generate diagram
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
