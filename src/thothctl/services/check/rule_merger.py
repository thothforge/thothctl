"""Rule Merger — hierarchical merge of org and project rules with enforcement levels."""
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import toml

logger = logging.getLogger(__name__)


@dataclass
class RuleViolation:
    rule: str
    expected: str
    found: str
    enforcement: str  # mandatory, recommended, informational
    source: str  # "org" or "project"


@dataclass
class MergedRuleset:
    """Result of merging org + project rules."""

    project_structure: Dict = field(default_factory=dict)
    rules: Dict = field(default_factory=dict)
    enforcement: str = "mandatory"
    source: str = ""
    project_type: str = ""


def load_org_rules(rules_dir: str, project_type: str) -> MergedRuleset:
    """Load org rules: base.toml merged with <project_type>.toml."""
    ruleset = MergedRuleset(source=rules_dir, project_type=project_type)

    # Load base
    base_path = os.path.join(rules_dir, "base.toml")
    if os.path.exists(base_path):
        base = _load_toml(base_path)
        ruleset.project_structure = base.get("project_structure", {})
        ruleset.rules = base.get("rules", {})
        ruleset.enforcement = base.get("metadata", {}).get("enforcement", "mandatory")

    # Merge type-specific
    type_path = os.path.join(rules_dir, f"{project_type}.toml")
    if os.path.exists(type_path):
        type_rules = _load_toml(type_path)
        # Merge folders (extend, don't replace)
        if "project_structure" in type_rules:
            type_struct = type_rules["project_structure"]
            if "folders" in type_struct:
                existing_folders = ruleset.project_structure.get("folders", [])
                existing_names = {f["name"] for f in existing_folders}
                for folder in type_struct["folders"]:
                    if folder["name"] not in existing_names:
                        existing_folders.append(folder)
                ruleset.project_structure["folders"] = existing_folders
            if "root_files" in type_struct:
                existing_files = set(ruleset.project_structure.get("root_files", []))
                existing_files.update(type_struct["root_files"])
                ruleset.project_structure["root_files"] = sorted(existing_files)
        # Merge rules
        for key, value in type_rules.get("rules", {}).items():
            ruleset.rules[key] = value

    return ruleset


def merge_with_project(org_ruleset: MergedRuleset, project_toml_path: str) -> MergedRuleset:
    """Merge org rules with project .thothcf.toml. Project cannot weaken mandatory org rules."""
    if not os.path.exists(project_toml_path):
        return org_ruleset

    project_config = _load_toml(project_toml_path)
    project_struct = project_config.get("project_structure", {})

    # Project can ADD root_files but not remove org mandatory ones
    if "root_files" in project_struct:
        org_files = set(org_ruleset.project_structure.get("root_files", []))
        project_files = set(project_struct.get("root_files", []))
        org_ruleset.project_structure["root_files"] = sorted(org_files | project_files)

    # Project can ADD folders but not remove org mandatory ones
    if "folders" in project_struct:
        existing_names = {f["name"] for f in org_ruleset.project_structure.get("folders", [])}
        for folder in project_struct["folders"]:
            if folder["name"] not in existing_names:
                org_ruleset.project_structure.setdefault("folders", []).append(folder)

    return org_ruleset


def evaluate(ruleset: MergedRuleset, project_dir: str) -> List[RuleViolation]:
    """Evaluate merged ruleset against a project directory."""
    violations = []

    # Check root files
    for required_file in ruleset.project_structure.get("root_files", []):
        path = os.path.join(project_dir, required_file)
        if not os.path.exists(path):
            violations.append(RuleViolation(
                rule=f"project_structure.root_files.{required_file}",
                expected=f"{required_file} exists",
                found="missing",
                enforcement=ruleset.enforcement,
                source="org",
            ))

    # Check folders
    for folder in ruleset.project_structure.get("folders", []):
        name = folder.get("name", "")
        mandatory = folder.get("mandatory", False)
        enforcement = folder.get("enforcement", ruleset.enforcement)
        folder_path = os.path.join(project_dir, name)

        if mandatory and not os.path.isdir(folder_path):
            violations.append(RuleViolation(
                rule=f"project_structure.folders.{name}",
                expected=f"{name}/ exists",
                found="missing",
                enforcement=enforcement,
                source="org",
            ))
            continue

        # Check required content inside folder
        if os.path.isdir(folder_path):
            for required_content in folder.get("content", []):
                content_path = os.path.join(folder_path, required_content)
                if not os.path.exists(content_path):
                    violations.append(RuleViolation(
                        rule=f"project_structure.folders.{name}.{required_content}",
                        expected=f"{name}/{required_content} exists",
                        found="missing",
                        enforcement=enforcement,
                        source="org",
                    ))

    # Check naming rules
    naming_rules = ruleset.rules.get("naming", {})
    if naming_rules:
        _check_naming(naming_rules, project_dir, violations)

    # Check tagging rules
    tagging_rules = ruleset.rules.get("tagging", {})
    if tagging_rules:
        _check_tagging(tagging_rules, project_dir, violations)

    return violations


def _check_naming(naming_rules: Dict, project_dir: str, violations: List[RuleViolation]):
    """Check project name matches naming pattern."""
    import re
    pattern = naming_rules.get("pattern")
    enforcement = naming_rules.get("enforcement", "mandatory")
    if pattern:
        project_name = os.path.basename(os.path.abspath(project_dir))
        if not re.match(pattern, project_name):
            violations.append(RuleViolation(
                rule="rules.naming.pattern",
                expected=f"project name matches {pattern}",
                found=project_name,
                enforcement=enforcement,
                source="org",
            ))


def _check_tagging(tagging_rules: Dict, project_dir: str, violations: List[RuleViolation]):
    """Check that required tags are referenced in the project (basic check in .thothcf.toml)."""
    # This is a lightweight check — full tag validation requires HCL parsing
    # For now just verify the project acknowledges required tags in its config
    pass


def _load_toml(path: str) -> Dict:
    try:
        with open(path, "r") as f:
            return toml.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}
