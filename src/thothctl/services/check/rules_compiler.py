"""Rules Compiler — generates Rego policies from .thothcf.toml rules.

Instead of re-implementing what OPA/conftest already does, this module
compiles user-friendly TOML rule definitions into standard Rego files
that are evaluated by the existing OPA/conftest scanner infrastructure.

Flow:
    .thothcf.toml [rules] → RulesCompiler → .rego files → conftest test

Phase 2.2 of the Policy Engine roadmap.
"""

import logging
import os
import textwrap
from typing import Any, Dict, List, Optional

import toml

logger = logging.getLogger(__name__)

# Default output directory for compiled Rego policies
DEFAULT_OUTPUT_DIR = ".thothctl/compiled_policies"


class RulesCompiler:
    """Compiles .thothcf.toml rules into Rego policies for conftest/OPA.

    Usage:
        compiler = RulesCompiler()
        policy_dir = compiler.compile(project_dir="/path/to/project")
        # Then pass policy_dir to OPA scanner
    """

    def __init__(self, output_dir: Optional[str] = None):
        """Initialize the compiler.

        Args:
            output_dir: Where to write compiled .rego files.
                        Defaults to .thothctl/compiled_policies/ in project dir.
        """
        self._output_dir = output_dir

    def compile(self, project_dir: str) -> Optional[str]:
        """Compile rules from .thothcf.toml into Rego policies.

        Args:
            project_dir: Path to the project root containing .thothcf.toml.

        Returns:
            Path to directory containing compiled .rego files,
            or None if no rules found.
        """
        config_path = os.path.join(project_dir, ".thothcf.toml")
        if not os.path.exists(config_path):
            logger.info("No .thothcf.toml found, skipping rules compilation")
            return None

        config = self._load_toml(config_path)
        rules_config = config.get("rules", {})

        if not rules_config:
            logger.info("No [rules] section in .thothcf.toml")
            return None

        # Determine output directory
        output_dir = self._output_dir or os.path.join(project_dir, DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        generated_files = []

        # Compile each rule type into its own .rego file
        if "naming" in rules_config:
            path = self._compile_naming_rules(rules_config["naming"], output_dir)
            if path:
                generated_files.append(path)

        if "tagging" in rules_config:
            path = self._compile_tagging_rules(rules_config["tagging"], output_dir)
            if path:
                generated_files.append(path)

        if "security" in rules_config:
            path = self._compile_security_rules(rules_config["security"], output_dir)
            if path:
                generated_files.append(path)

        if "architecture" in rules_config:
            path = self._compile_architecture_rules(
                rules_config["architecture"], output_dir
            )
            if path:
                generated_files.append(path)

        if generated_files:
            logger.info(
                f"Compiled {len(generated_files)} Rego policy file(s) to {output_dir}"
            )
            return output_dir

        return None

    # --- Naming rules ---

    def _compile_naming_rules(
        self, rules: List[Dict[str, Any]], output_dir: str
    ) -> Optional[str]:
        """Compile naming rules into Rego.

        Input TOML:
            [[rules.naming]]
            name = "resource_naming"
            severity = "error"
            [rules.naming.config]
            pattern = "^(dev|stg|prd)_[a-z_]+$"
            resource_types = ["aws_s3_bucket", "aws_instance"]
        """
        rego_rules = []

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            config = rule.get("config", rule)
            pattern = config.get("pattern", "")
            resource_types = config.get("resource_types", [])
            name = rule.get("name", "naming_convention")
            severity = rule.get("severity", "error")

            if not pattern:
                continue

            deny_or_warn = "deny" if severity == "error" else "warn"

            rego_rule = textwrap.dedent(
                f"""\
                # Rule: {name}
                {deny_or_warn}[msg] {{
                    resource_block := input.resource[_]
                    resource_types := object.keys(resource_block)
                    resource_type := resource_types[_]
                    {"type_check := " + repr(resource_types) + chr(10) + "    resource_type == type_check[_]" if resource_types else ""}
                    instances := resource_block[resource_type]
                    instance_name := object.keys(instances)[_]
                    not regex.match(`{pattern}`, instance_name)
                    msg := sprintf("{name}: resource '%s.%s' does not match naming pattern '{pattern}'", [resource_type, instance_name])
                }}
            """
            )
            rego_rules.append(rego_rule)

        if not rego_rules:
            return None

        return self._write_rego_file(output_dir, "naming", rego_rules)

    # --- Tagging rules ---

    def _compile_tagging_rules(
        self, rules: List[Dict[str, Any]], output_dir: str
    ) -> Optional[str]:
        """Compile tagging rules into Rego.

        Input TOML:
            [[rules.tagging]]
            name = "required_tags"
            [rules.tagging.config]
            required_tags = ["Environment", "Owner", "CostCenter"]
        """
        rego_rules = []

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            config = rule.get("config", rule)
            required_tags = config.get("required_tags", [])
            name = rule.get("name", "required_tags")
            severity = rule.get("severity", "error")
            resource_types = config.get("resource_types", [])

            if not required_tags:
                continue

            deny_or_warn = "deny" if severity == "error" else "warn"
            tags_str = ", ".join(f'"{t}"' for t in required_tags)

            type_filter_line = ""
            if resource_types:
                types_str = ", ".join(f'"{t}"' for t in resource_types)
                type_filter_line = (
                    f"    allowed_types := [{types_str}]\n"
                    f"    resource_type == allowed_types[_]\n"
                )

            rego_rule = textwrap.dedent(
                f"""\
                # Rule: {name}
                {deny_or_warn}[msg] {{
                    resource_block := input.resource[_]
                    resource_type := object.keys(resource_block)[_]
                {type_filter_line}    instances := resource_block[resource_type]
                    instance_name := object.keys(instances)[_]
                    instance := instances[instance_name]
                    required_tags := [{tags_str}]
                    required_tag := required_tags[_]
                    not instance.tags[required_tag]
                    msg := sprintf("{name}: resource '%s.%s' missing required tag '%s'", [resource_type, instance_name, required_tag])
                }}
            """
            )
            rego_rules.append(rego_rule)

        if not rego_rules:
            return None

        return self._write_rego_file(output_dir, "tagging", rego_rules)

    # --- Security rules ---

    def _compile_security_rules(
        self, rules: List[Dict[str, Any]], output_dir: str
    ) -> Optional[str]:
        """Compile security rules into Rego.

        Input TOML:
            [[rules.security]]
            name = "no_public_access"
            severity = "error"
            [rules.security.config]
            banned_patterns = ["acl.*public", "publicly_accessible.*true"]
        """
        rego_rules = []

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            config = rule.get("config", rule)
            banned_patterns = config.get("banned_patterns", [])
            name = rule.get("name", "security_check")
            severity = rule.get("severity", "error")

            if not banned_patterns:
                continue

            deny_or_warn = "deny" if severity == "error" else "warn"

            for i, pattern in enumerate(banned_patterns):
                rule_id = f"{name}_{i}" if len(banned_patterns) > 1 else name
                rego_rule = textwrap.dedent(
                    f"""\
                    # Rule: {rule_id} — banned pattern: {pattern}
                    {deny_or_warn}[msg] {{
                        resource_block := input.resource[_]
                        resource_type := object.keys(resource_block)[_]
                        instances := resource_block[resource_type]
                        instance_name := object.keys(instances)[_]
                        instance := instances[instance_name]
                        walk(instance, [path, value])
                        key_str := concat(".", path)
                        val_str := sprintf("%v", [value])
                        combined := sprintf("%s=%s", [key_str, val_str])
                        regex.match(`{pattern}`, combined)
                        msg := sprintf("{name}: resource '%s.%s' matches banned pattern '{pattern}' at %s", [resource_type, instance_name, key_str])
                    }}
                """
                )
                rego_rules.append(rego_rule)

        if not rego_rules:
            return None

        return self._write_rego_file(output_dir, "security", rego_rules)

    # --- Architecture rules ---

    def _compile_architecture_rules(
        self, rules: List[Dict[str, Any]], output_dir: str
    ) -> Optional[str]:
        """Compile architecture rules into Rego.

        Input TOML:
            [[rules.architecture]]
            name = "require_multi_az"
            [rules.architecture.config]
            require_multi_az = true
            max_resources_per_file = 10
            require_modules = ["terraform-aws-modules/vpc/aws"]
        """
        rego_rules = []

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            config = rule.get("config", rule)
            name = rule.get("name", "architecture_check")
            severity = rule.get("severity", "error")
            deny_or_warn = "deny" if severity == "error" else "warn"

            # require_multi_az
            if config.get("require_multi_az", False):
                db_types = [
                    "aws_db_instance",
                    "aws_rds_cluster",
                    "aws_elasticache_replication_group",
                ]
                types_str = ", ".join(f'"{t}"' for t in db_types)
                rego_rule = textwrap.dedent(
                    f"""\
                    # Rule: {name} — require multi-AZ for databases
                    {deny_or_warn}[msg] {{
                        resource_block := input.resource[_]
                        resource_type := object.keys(resource_block)[_]
                        db_types := [{types_str}]
                        resource_type == db_types[_]
                        instances := resource_block[resource_type]
                        instance_name := object.keys(instances)[_]
                        instance := instances[instance_name]
                        not instance.multi_az == true
                        msg := sprintf("{name}: resource '%s.%s' should have multi_az = true", [resource_type, instance_name])
                    }}
                """
                )
                rego_rules.append(rego_rule)

            # require_modules
            required_modules = config.get("require_modules", [])
            if required_modules:
                for mod in required_modules:
                    rego_rule = textwrap.dedent(
                        f"""\
                        # Rule: {name} — require module: {mod}
                        {deny_or_warn}[msg] {{
                            modules := object.get(input, "module", [])
                            module_sources := [src |
                                mod_block := modules[_]
                                mod_name := object.keys(mod_block)[_]
                                src := mod_block[mod_name].source
                            ]
                            not "{mod}" == module_sources[_]
                            msg := "{name}: required module '{mod}' not found in project"
                        }}
                    """
                    )
                    rego_rules.append(rego_rule)

            # max_resources_per_file (advisory — conftest runs per-file)
            max_resources = config.get("max_resources_per_file")
            if max_resources is not None:
                rego_rule = textwrap.dedent(
                    f"""\
                    # Rule: {name} — max {max_resources} resources per file
                    {deny_or_warn}[msg] {{
                        resources := input.resource
                        count(resources) > {max_resources}
                        msg := sprintf("{name}: file has %d resources (max {max_resources})", [count(resources)])
                    }}
                """
                )
                rego_rules.append(rego_rule)

        if not rego_rules:
            return None

        return self._write_rego_file(output_dir, "architecture", rego_rules)

    # --- Helpers ---

    def _write_rego_file(
        self, output_dir: str, rule_type: str, rules: List[str]
    ) -> str:
        """Write compiled rules to a .rego file."""
        file_path = os.path.join(output_dir, f"{rule_type}.rego")

        header = textwrap.dedent(
            f"""\
            # Auto-generated by ThothCTL Rules Compiler
            # Source: .thothcf.toml [rules.{rule_type}]
            # Do not edit — regenerate with: thothctl check iac --type rules
            package main

            import rego.v1

        """
        )

        content = header + "\n".join(rules)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug(f"Wrote compiled policy: {file_path}")
        return file_path

    def _load_toml(self, path: str) -> Dict[str, Any]:
        """Load a TOML file safely."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return toml.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return {}
