"""Context builder for Intent-to-IaC generation.

Compiles organizational context from multiple sources into a structured payload
that gets injected into the AI prompt. This is what makes generated code
"governed" — the AI follows your org rules because they're in its context.

Sources (in priority order):
1. .thothcf.toml — project type, naming patterns, environment, tags
2. IaC rules — .kiro/steering/iac-rules.md or .claude/rules/*.md
3. Project overview — .kiro/steering/product.md or CLAUDE.md
4. Existing patterns — sample files from stacks/ (few-shot examples)
5. Org policies — OPA .rego file summaries (rule names + comments)
"""

import logging
import os
from pathlib import Path

from .models import ContextPayload

logger = logging.getLogger(__name__)

# Token budget per section (approximate, 1 token ≈ 4 chars)
_MAX_PROJECT_CONFIG_CHARS = 4000  # ~1000 tokens (scaffold rules are critical)
_MAX_IAC_RULES_CHARS = 8000  # ~2000 tokens
_MAX_PROJECT_OVERVIEW_CHARS = 2000  # ~500 tokens
_MAX_EXISTING_PATTERNS_CHARS = 8000  # ~2000 tokens
_MAX_ORG_POLICIES_CHARS = 2000  # ~500 tokens
_MAX_PATTERN_FILES = 3  # Max example files to include


class ContextBuilder:
    """Builds AI context from project configuration and conventions."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def build_context(
        self, directory: str, project_type: str = "auto"
    ) -> ContextPayload:
        """Compile organizational context from all available sources.

        Args:
            directory: Project root directory
            project_type: Target project type (or "auto" to detect)

        Returns:
            ContextPayload ready for prompt injection
        """
        dir_path = Path(directory).resolve()

        # Detect project type if auto
        if project_type == "auto":
            project_type = self._detect_project_type(dir_path)

        payload = ContextPayload(project_type=project_type)

        # 1. Load .thothcf.toml
        payload.project_config = self._load_thothcf(dir_path)

        # 2. Load IaC rules
        payload.iac_rules = self._load_iac_rules(dir_path)

        # 3. Load project overview
        payload.project_overview = self._load_project_overview(dir_path)

        # 4. Load existing patterns (few-shot examples)
        payload.existing_patterns = self._load_existing_patterns(dir_path, project_type)

        # 5. Load org policies
        payload.org_policies = self._load_org_policies(dir_path)

        self.logger.info(
            f"Context built: config={len(payload.project_config)}c, "
            f"rules={len(payload.iac_rules)}c, overview={len(payload.project_overview)}c, "
            f"patterns={len(payload.existing_patterns)}c, policies={len(payload.org_policies)}c"
        )

        return payload

    # ------------------------------------------------------------------
    # Source loaders
    # ------------------------------------------------------------------

    def _load_thothcf(self, directory: Path) -> str:
        """Extract scaffold/composition rules from .thothcf.toml.

        This is what makes generated code follow the framework structure.
        The AI must understand:
        - Where to place generated files (folder hierarchy)
        - What files each stack/module must contain
        - Naming conventions and constraints
        - Parent/child folder relationships
        """
        toml_path = directory / ".thothcf.toml"

        # Also check project-level config
        if not toml_path.exists():
            toml_path = directory / ".thothcf_project.toml"
        if not toml_path.exists():
            toml_path = directory / ".thothcf_module.toml"
        if not toml_path.exists():
            return ""

        try:
            import toml

            config = toml.load(toml_path)
        except Exception as e:
            self.logger.debug(f"Failed to load config: {e}")
            return ""

        lines = []

        # Project metadata
        thothcf = config.get("thothcf", {})
        if thothcf:
            lines.append(f"- Project type: {thothcf.get('project_type', 'unknown')}")
            if thothcf.get("project_id"):
                lines.append(f"- Project ID: {thothcf['project_id']}")

        # ----------------------------------------------------------
        # SCAFFOLD: Project Structure (composition rules)
        # ----------------------------------------------------------
        structure = config.get("project_structure", {})
        if structure:
            lines.append("\n## SCAFFOLD — File Structure Rules")
            lines.append(
                "Generated code MUST follow this structure. "
                "Place files in the correct folders."
            )

            root_files = structure.get("root_files", [])
            if root_files:
                lines.append("\nRoot files (must exist at project root):")
                for rf in root_files:
                    lines.append(f"  - {rf}")

            folders = structure.get("folders", [])
            if folders:
                lines.append("\nFolder structure:")
                # Build hierarchy
                root_folders = [
                    f for f in folders if f.get("type") == "root" or not f.get("parent")
                ]
                child_folders = [f for f in folders if f.get("parent")]

                for folder in root_folders:
                    name = folder.get("name", "")
                    mandatory = folder.get("mandatory", False)
                    content = folder.get("content", [])
                    status = "REQUIRED" if mandatory else "optional"

                    if content:
                        files_str = ", ".join(content)
                        lines.append(
                            f"  - {name}/ ({status}) — "
                            f"each entry must contain: [{files_str}]"
                        )
                    else:
                        lines.append(f"  - {name}/ ({status})")

                    # Add children
                    children = [c for c in child_folders if c.get("parent") == name]
                    for child in children:
                        child_name = child.get("name", "")
                        child_content = child.get("content", [])
                        child_mandatory = child.get("mandatory", False)
                        c_status = "REQUIRED" if child_mandatory else "optional"
                        if child_content:
                            files_str = ", ".join(child_content)
                            lines.append(
                                f"    - {name}/{child_name}/ ({c_status}) — "
                                f"must contain: [{files_str}]"
                            )
                        else:
                            lines.append(f"    - {name}/{child_name}/ ({c_status})")

            # Stack path convention (inferred from folder structure)
            stacks_folder = next(
                (f for f in folders if f.get("name") == "stacks"), None
            )
            if stacks_folder:
                content = stacks_folder.get("content", [])
                lines.append(
                    "\nStack composition rule:"
                    "\n  - Place new stacks in: stacks/<layer>/<domain>/<service>/"
                    "\n  - Layers: foundation → platform → application → observability"
                )
                if content:
                    files_str = ", ".join(content)
                    lines.append(f"  - Each stack directory MUST contain: {files_str}")

            # Module path convention
            modules_folder = next(
                (f for f in folders if f.get("name") == "modules"), None
            )
            if modules_folder:
                content = modules_folder.get("content", [])
                if content:
                    files_str = ", ".join(content)
                    lines.append(
                        f"\nModule composition rule:"
                        f"\n  - Place modules in: modules/<module_name>/"
                        f"\n  - Each module MUST contain: {files_str}"
                    )

            # Ignored folders (don't generate into these)
            ignore = structure.get("ignore_folders", [])
            if ignore:
                lines.append(f"\nNEVER generate files in: {', '.join(ignore)}")

        # ----------------------------------------------------------
        # NAMING: Template parameters & constraints
        # ----------------------------------------------------------
        params = config.get("template_input_parameters", {})
        if params:
            lines.append("\n## NAMING — Parameter Conventions")
            for key, val in params.items():
                desc = val.get("description", "")
                value = val.get("template_value", "")
                condition = val.get("condition", "")
                if condition:
                    lines.append(
                        f"  - {key}: pattern must match `{condition}` ({desc})"
                    )
                elif value:
                    lines.append(f"  - {key}: {value} ({desc})")

        result = "\n".join(lines)
        return result[:_MAX_PROJECT_CONFIG_CHARS]

    def _load_iac_rules(self, directory: Path) -> str:
        """Load IaC composition rules from steering docs or .claude/rules/."""
        content = ""

        # Try .kiro/steering/iac-rules.md first
        kiro_rules = directory / ".kiro" / "steering" / "iac-rules.md"
        if kiro_rules.exists():
            content = self._read_truncated(kiro_rules, _MAX_IAC_RULES_CHARS)

        # Try .claude/rules/*.md
        if not content:
            claude_rules_dir = directory / ".claude" / "rules"
            if claude_rules_dir.exists():
                parts = []
                for rule_file in sorted(claude_rules_dir.glob("*.md")):
                    text = rule_file.read_text(encoding="utf-8", errors="ignore")
                    # Strip YAML frontmatter
                    if text.startswith("---"):
                        end = text.find("---", 3)
                        if end != -1:
                            text = text[end + 3 :].strip()
                    parts.append(text)
                content = "\n\n".join(parts)
                content = content[:_MAX_IAC_RULES_CHARS]

        # Fallback: .kiro/steering/tech.md (technology stack info)
        if not content:
            tech_file = directory / ".kiro" / "steering" / "tech.md"
            if tech_file.exists():
                content = self._read_truncated(tech_file, _MAX_IAC_RULES_CHARS // 2)

        return content

    def _load_project_overview(self, directory: Path) -> str:
        """Load project overview from product.md or CLAUDE.md."""
        # Try CLAUDE.md first (concise, designed for AI)
        claude_md = directory / "CLAUDE.md"
        if claude_md.exists():
            return self._read_truncated(claude_md, _MAX_PROJECT_OVERVIEW_CHARS)

        # Try .kiro/steering/product.md
        product_md = directory / ".kiro" / "steering" / "product.md"
        if product_md.exists():
            return self._read_truncated(product_md, _MAX_PROJECT_OVERVIEW_CHARS)

        # Try .claude/CLAUDE.md (inside .claude directory)
        claude_inner = directory / ".claude" / "CLAUDE.md"
        if claude_inner.exists():
            return self._read_truncated(claude_inner, _MAX_PROJECT_OVERVIEW_CHARS)

        return ""

    def _load_existing_patterns(self, directory: Path, project_type: str) -> str:
        """Load example files from the project as few-shot patterns."""
        patterns = []
        stacks_dir = directory / "stacks"

        if not stacks_dir.exists():
            # Try flat structure
            stacks_dir = directory

        # Find example files based on project type
        if project_type in ("terraform-terragrunt", "terragrunt"):
            target_files = list(stacks_dir.rglob("terragrunt.hcl"))
        elif project_type == "cloudformation":
            target_files = [
                f for f in stacks_dir.rglob("*.yaml") if self._is_cfn_template(f)
            ]
        elif project_type == "cdkv2":
            target_files = list(stacks_dir.rglob("*.ts")) + list(
                stacks_dir.rglob("*.py")
            )
        else:
            target_files = list(stacks_dir.rglob("main.tf"))

        # Filter out cache/hidden dirs
        target_files = [
            f
            for f in target_files
            if ".terraform" not in str(f)
            and ".terragrunt-cache" not in str(f)
            and "node_modules" not in str(f)
        ]

        # Security: filter out files that may contain secrets
        _SENSITIVE_PATTERNS = {
            ".env", "secret", "password", "token", ".tfvars",
            ".key", "credentials", ".pem", ".pfx", "id_rsa",
        }
        target_files = [
            f
            for f in target_files
            if not any(p in str(f).lower() for p in _SENSITIVE_PATTERNS)
        ]

        # Take up to N example files, preferring diverse paths
        seen_parents = set()
        selected = []
        for f in sorted(target_files):
            parent = str(f.parent)
            if parent not in seen_parents and len(selected) < _MAX_PATTERN_FILES:
                seen_parents.add(parent)
                selected.append(f)

        # Format as examples
        for f in selected:
            rel_path = f.relative_to(directory)
            content = f.read_text(encoding="utf-8", errors="ignore")
            # Truncate individual files
            if len(content) > 2000:
                content = content[:2000] + "\n# ... (truncated)"
            patterns.append(f"### Example: {rel_path}\n```hcl\n{content}\n```")

        result = "\n\n".join(patterns)
        return result[:_MAX_EXISTING_PATTERNS_CHARS]

    def _load_org_policies(self, directory: Path) -> str:
        """Load organizational rules and policy summaries.

        Sources:
        1. THOTH_ORG_POLICY repo rules/base.toml (naming, tagging, security rules)
        2. THOTH_ORG_POLICY repo rules/<project_type>.toml (type-specific rules)
        3. OPA/Rego policy summaries (rule names + comments)
        """
        sections = []

        # Resolve org policy path
        org_policy_path = None
        org_policy_env = os.environ.get("THOTH_ORG_POLICY")
        if org_policy_env and not org_policy_env.startswith("git::"):
            org_policy_path = Path(org_policy_env)
        if not org_policy_path:
            # Check cached org policy
            cache_dir = Path.home() / ".thothcf" / ".policy_cache"
            if cache_dir.exists():
                for d in cache_dir.iterdir():
                    if d.is_dir() and (d / "rules").exists():
                        org_policy_path = d
                        break

        # 1. Load TOML rules from org policy repo
        if org_policy_path and (org_policy_path / "rules").exists():
            rules_section = self._load_org_toml_rules(org_policy_path)
            if rules_section:
                sections.append(rules_section)

        # 2. Load Rego policy summaries
        policy_dirs = [
            directory / "policies",
            directory / "policy",
        ]
        if org_policy_path:
            policy_dirs.append(org_policy_path)

        rego_summaries = []
        for policy_dir in policy_dirs:
            if not policy_dir.exists():
                continue
            for rego_file in sorted(policy_dir.rglob("*.rego")):
                summary = self._summarize_rego(rego_file)
                if summary:
                    rego_summaries.append(summary)

        if rego_summaries:
            sections.append(
                "OPA Policies (enforced via conftest):\n"
                + "\n".join(rego_summaries[:15])
            )

        if not sections:
            return ""

        return "\n\n".join(sections)[:_MAX_ORG_POLICIES_CHARS]

    def _load_org_toml_rules(self, org_policy_path: Path) -> str:
        """Load rules/base.toml + rules/<project_type>.toml from org policy repo."""
        try:
            import toml
        except ImportError:
            return ""

        lines = []
        rules_dir = org_policy_path / "rules"

        # Load base.toml
        base_path = rules_dir / "base.toml"
        if base_path.exists():
            try:
                config = toml.load(base_path)
                metadata = config.get("metadata", {})
                if metadata:
                    lines.append(
                        f"## Organization Rules: {metadata.get('name', 'Org Standards')}"
                        f" (enforcement: {metadata.get('enforcement', 'mandatory')})"
                    )

                rules = config.get("rules", {})

                # Naming rules
                naming = rules.get("naming", {})
                if naming:
                    pattern = naming.get("pattern", "")
                    enforcement = naming.get("enforcement", "mandatory")
                    lines.append(
                        f"\nNAMING ({enforcement}):"
                        f"\n  Resource names MUST match: `{pattern}`"
                    )

                # Tagging rules
                tagging = rules.get("tagging", {})
                if tagging:
                    tags = tagging.get("required_tags", [])
                    enforcement = tagging.get("enforcement", "mandatory")
                    if tags:
                        lines.append(
                            f"\nTAGGING ({enforcement}):"
                            f"\n  ALL resources MUST have tags: {', '.join(tags)}"
                        )

                # Security rules
                security = rules.get("security", {})
                if security:
                    enforcement = security.get("enforcement", "mandatory")
                    lines.append(f"\nSECURITY ({enforcement}):")
                    for key, value in security.items():
                        if key != "enforcement":
                            lines.append(f"  - {key}: {value}")

            except Exception as e:
                self.logger.debug(f"Failed to load org rules: {e}")

        return "\n".join(lines) if lines else ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_truncated(path: Path, max_chars: int) -> str:
        """Read a file, truncating to max_chars."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(content) > max_chars:
                return content[:max_chars] + "\n\n... (truncated)"
            return content
        except Exception:
            return ""

    @staticmethod
    def _detect_project_type(directory: Path) -> str:
        """Auto-detect project type from directory contents."""
        if (directory / "root.hcl").exists():
            return "terraform-terragrunt"
        if (directory / "terragrunt.hcl").exists():
            return "terragrunt"
        if (directory / "cdk.json").exists():
            return "cdkv2"

        # Check for CloudFormation templates
        for f in directory.iterdir():
            if f.suffix in (".yaml", ".yml") and f.is_file():
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:200]
                    if "AWSTemplateFormatVersion" in content:
                        return "cloudformation"
                except Exception:
                    pass

        # Default to terraform
        if list(directory.glob("*.tf")):
            return "terraform"

        return "terraform"

    @staticmethod
    def _is_cfn_template(path: Path) -> bool:
        """Check if a YAML file is a CloudFormation template."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")[:300]
            return "AWSTemplateFormatVersion" in content or "Transform:" in content
        except Exception:
            return False

    @staticmethod
    def _summarize_rego(path: Path) -> str:
        """Extract rule names and comments from a .rego file (first 10 lines of rules)."""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            package_name = ""
            rules = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("package "):
                    package_name = stripped.replace("package ", "")
                elif stripped.startswith("deny[") or stripped.startswith("violation["):
                    # Extract rule name from deny[msg] { or violation[msg] {
                    rules.append(stripped.split("{")[0].strip())
                elif stripped.startswith("# ") and not rules:
                    # Comments before first rule = description
                    rules.append(stripped)

                if len(rules) >= 5:
                    break

            if not rules:
                return ""

            rule_text = "; ".join(rules[:3])
            return f"- {package_name or path.stem}: {rule_text}"
        except Exception:
            return ""
