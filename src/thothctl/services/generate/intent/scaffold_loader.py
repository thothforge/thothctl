"""Scaffold Loader — fetches and parses scaffold structure for composition.

The scaffold defines the DETERMINISTIC part of project generation:
- Root files (root.hcl, .gitignore, README.md, etc.)
- Folder structure (common/, stacks/, modules/, docs/)
- Per-stack required files (main.tf, variables.tf, outputs.tf, terragrunt.hcl)
- Boilerplate content (root.hcl, common/common.hcl from the actual scaffold)

The AI only fills resource content WITHIN this structure.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Official scaffold repos per project type
SCAFFOLD_REGISTRY = {
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
    "cloudformation": {
        "name": "cloudformation_project_scaffold",
        "repo": "thothforge/cloudformation_project_scaffold",
    },
}


@dataclass
class ScaffoldStructure:
    """Parsed scaffold structure — the deterministic skeleton."""

    project_type: str
    root_files: List[str] = field(default_factory=list)
    folders: List[Dict] = field(default_factory=list)
    stack_required_files: List[str] = field(default_factory=list)
    module_required_files: List[str] = field(default_factory=list)
    ignore_folders: List[str] = field(default_factory=list)
    # Actual boilerplate content from the scaffold
    boilerplate: Dict[str, str] = field(default_factory=dict)
    # Real example stacks (non-empty .tf files)
    examples: Dict[str, str] = field(default_factory=dict)


class ScaffoldLoader:
    """Fetches and parses scaffold for scaffold-driven composition."""

    def __init__(self, project_type: str):
        self.project_type = project_type
        self._scaffold_dir: Optional[Path] = None

    def load(self) -> ScaffoldStructure:
        """Load scaffold structure from cache or GitHub.

        Returns:
            ScaffoldStructure with all rules and boilerplate content.
        """
        scaffold_dir = self._resolve_scaffold_dir()
        if not scaffold_dir:
            logger.warning(f"No scaffold found for {self.project_type}")
            return self._default_structure()

        self._scaffold_dir = scaffold_dir
        return self._parse_scaffold(scaffold_dir)

    def _resolve_scaffold_dir(self) -> Optional[Path]:
        """Resolve scaffold directory: check cache, then fetch from GitHub."""
        info = SCAFFOLD_REGISTRY.get(self.project_type)
        if not info:
            return None

        scaffold_cache = Path.home() / ".thothcf"
        scaffold_dir = scaffold_cache / info["name"]

        # Check if already cached with real content
        if scaffold_dir.exists() and (scaffold_dir / "root.hcl").exists():
            return scaffold_dir

        # Fetch from GitHub
        return self._fetch_from_github(info["repo"], scaffold_dir)

    def _fetch_from_github(self, repo: str, target: Path) -> Optional[Path]:
        """Clone scaffold from GitHub via gh CLI."""
        if not shutil.which("gh"):
            logger.info("gh CLI not available — cannot fetch scaffold")
            return None

        try:
            logger.info(f"Fetching scaffold from github.com/{repo}...")
            if target.exists():
                shutil.rmtree(target)
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

        return None

    def _parse_scaffold(self, scaffold_dir: Path) -> ScaffoldStructure:
        """Parse scaffold directory into ScaffoldStructure."""
        import toml

        structure = ScaffoldStructure(project_type=self.project_type)

        # Parse .thothcf_project.toml if it exists
        for config_name in (".thothcf_project.toml", ".thothcf.toml"):
            config_path = scaffold_dir / config_name
            if config_path.exists():
                try:
                    config = toml.load(config_path)
                    ps = config.get("project_structure", {})
                    if ps:
                        structure.root_files = ps.get("root_files", [])
                        structure.folders = ps.get("folders", [])
                        structure.ignore_folders = ps.get("ignore_folders", [])

                        # Extract per-stack required files
                        stacks_folder = next(
                            (f for f in structure.folders if f.get("name") == "stacks"),
                            None,
                        )
                        if stacks_folder:
                            structure.stack_required_files = stacks_folder.get(
                                "content", []
                            )

                        # Extract per-module required files
                        modules_folder = next(
                            (
                                f
                                for f in structure.folders
                                if f.get("name") == "modules"
                            ),
                            None,
                        )
                        if modules_folder:
                            structure.module_required_files = modules_folder.get(
                                "content", []
                            )
                        break
                except Exception as e:
                    logger.warning(f"Failed to parse scaffold config: {e}")

        # If no project_structure found in scaffold, load from ThothCTL defaults
        if not structure.root_files:
            structure = self._load_embedded_defaults(structure, scaffold_dir)

        # Load boilerplate content (actual files from scaffold)
        structure.boilerplate = self._load_boilerplate(scaffold_dir)

        # Load real example stacks (non-empty .tf files)
        structure.examples = self._load_examples(scaffold_dir)

        return structure

    def _load_embedded_defaults(
        self, structure: ScaffoldStructure, scaffold_dir: Path
    ) -> ScaffoldStructure:
        """Load project structure rules from ThothCTL's embedded defaults."""
        import toml

        # ThothCTL ships default structure definitions
        embedded_dir = Path(__file__).parent.parent.parent.parent / "common"
        type_map = {
            "terraform-terragrunt": "terragrunt",
            "terragrunt": "terragrunt",
        }
        subdir = type_map.get(self.project_type, "")
        embedded_config = embedded_dir / subdir / ".thothcf_project.toml"

        if embedded_config.exists():
            try:
                config = toml.load(embedded_config)
                ps = config.get("project_structure", {})
                structure.root_files = ps.get("root_files", [])
                structure.folders = ps.get("folders", [])
                structure.ignore_folders = ps.get("ignore_folders", [])

                stacks_folder = next(
                    (f for f in structure.folders if f.get("name") == "stacks"),
                    None,
                )
                if stacks_folder:
                    structure.stack_required_files = stacks_folder.get("content", [])

                modules_folder = next(
                    (f for f in structure.folders if f.get("name") == "modules"),
                    None,
                )
                if modules_folder:
                    structure.module_required_files = modules_folder.get("content", [])
            except Exception as e:
                logger.warning(f"Failed to load embedded defaults: {e}")

        return structure

    def _load_boilerplate(self, scaffold_dir: Path) -> Dict[str, str]:
        """Load actual boilerplate files from the scaffold (root.hcl, common/, etc.)."""
        boilerplate = {}

        # Root files with content
        for filename in ("root.hcl", ".gitignore", ".pre-commit-config.yaml"):
            filepath = scaffold_dir / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    boilerplate[filename] = content

        # Common directory files
        common_dir = scaffold_dir / "common"
        if common_dir.exists():
            for f in common_dir.iterdir():
                if f.is_file():
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if content.strip():
                        boilerplate[f"common/{f.name}"] = content

        return boilerplate

    def _load_examples(self, scaffold_dir: Path) -> Dict[str, str]:
        """Load non-empty example stack files as few-shot patterns."""
        examples = {}
        stacks_dir = scaffold_dir / "stacks"

        if not stacks_dir.exists():
            return examples

        # Find non-empty .tf and .hcl files in stacks/
        for tf_file in sorted(stacks_dir.rglob("*.tf")):
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
            if content.strip() and len(content) > 20:
                rel_path = str(tf_file.relative_to(stacks_dir))
                examples[rel_path] = content

        for hcl_file in sorted(stacks_dir.rglob("terragrunt.hcl")):
            content = hcl_file.read_text(encoding="utf-8", errors="ignore")
            if content.strip() and len(content) > 20:
                rel_path = str(hcl_file.relative_to(stacks_dir))
                examples[rel_path] = content

        return examples

    def _default_structure(self) -> ScaffoldStructure:
        """Fallback structure when no scaffold is available."""
        if self.project_type in ("terraform-terragrunt", "terragrunt"):
            return ScaffoldStructure(
                project_type=self.project_type,
                root_files=[".gitignore", "README.md", "root.hcl"],
                stack_required_files=[
                    "terragrunt.hcl",
                    "main.tf",
                    "variables.tf",
                    "outputs.tf",
                ],
                module_required_files=[
                    "main.tf",
                    "variables.tf",
                    "outputs.tf",
                    "README.md",
                ],
                folders=[
                    {
                        "name": "common",
                        "mandatory": True,
                        "content": ["common.hcl", "common.tfvars"],
                    },
                    {"name": "stacks", "mandatory": True},
                    {"name": "modules", "mandatory": True},
                    {"name": "docs", "mandatory": True},
                ],
            )
        elif self.project_type == "cdkv2":
            return ScaffoldStructure(
                project_type=self.project_type,
                root_files=["cdk.json", "package.json", "tsconfig.json", ".gitignore"],
                stack_required_files=[],
                folders=[
                    {"name": "bin", "mandatory": True},
                    {"name": "lib/stacks", "mandatory": True},
                    {"name": "lib/constructs", "mandatory": True},
                    {"name": "test", "mandatory": True},
                ],
            )
        else:
            return ScaffoldStructure(
                project_type=self.project_type,
                root_files=[".gitignore", "README.md"],
                stack_required_files=["main.tf", "variables.tf", "outputs.tf"],
            )
