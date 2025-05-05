import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import os
import yaml
from jinja2 import Template
import importlib.util

# Try to import TerraformModuleDetails using a more robust approach
try:
    # First try direct import
    from thothctl.utils.modules_ops.terraform_module_details import TerraformModuleDetails
except ImportError:
    try:
        # Then try relative import
        from .....utils.modules_ops.terraform_module_details import TerraformModuleDetails
    except ImportError:
        # If both fail, create a mock class
        class TerraformModuleDetails:
            def get_module_details(self, namespace, name, provider):
                return self._create_mock_module_details(namespace, name, provider)
                
            def _create_mock_module_details(self, namespace, name, provider):
                # Basic module info
                basic_info = {
                    "id": f"{namespace}/{name}/{provider}",
                    "namespace": namespace,
                    "name": name,
                    "provider": provider,
                    "version": "1.0.0",
                    "description": f"Mock {name} module for {provider}",
                }
                
                # Root module inputs and outputs based on module name
                root = {"inputs": [], "outputs": []}
                
                # Add inputs and outputs based on module name
                if name == "vpc":
                    root["inputs"] = [
                        {
                            "name": "vpc_cidr",
                            "type": "string",
                            "description": "The CIDR block for the VPC",
                            "default": "10.0.0.0/16",
                        },
                        {
                            "name": "azs",
                            "type": "list(string)",
                            "description": "A list of availability zones in the region",
                        },
                    ]
                    root["outputs"] = [
                        {
                            "name": "vpc_id",
                            "description": "The ID of the VPC",
                            "value": "module.vpc.vpc_id",
                        },
                    ]
                
                # Return complete module details
                return {
                    "basic_info": basic_info,
                    "root": root,
                }


@dataclass
class VariableDefinition:
    name: str
    type: str
    description: str
    default: Any = None
    required: bool = True
    sensitive: bool = False


@dataclass
class ModuleIO:
    """Class to store module inputs and outputs with their full definitions"""

    inputs: Dict[str, VariableDefinition]
    outputs: Dict[str, VariableDefinition]


@dataclass
class IncludeBlock:
    name: str
    path: str


@dataclass
class Dependency:
    name: str
    config_path: str
    mock_outputs: Dict[str, Any]


class VariableMapper:
    """Enhanced variable mapper using descriptions and common patterns"""

    # Common infrastructure terminology patterns with type information and related terms
    COMMON_PATTERNS = {
        "subnet": {
            "terms": ["subnet", "sub_net", "subnetwork"],
            "context": ["vpc", "network", "private", "public", "database", "db"],
            "common_types": ["list(string)", "set(string)", "string"],
            "related_inputs": ["subnet_ids", "db_subnet_group_name"],
        },
        "vpc": {
            "terms": ["vpc", "virtual_private_cloud"],
            "context": ["network", "cloud", "private"],
            "common_types": ["string"],
            "related_inputs": ["vpc_id"],
        },
        "security_group": {
            "terms": ["sg", "security_group", "secgroup"],
            "context": ["firewall", "rules", "ingress", "egress"],
            "common_types": ["list(string)", "string"],
            "related_inputs": ["security_group_ids", "vpc_security_group_ids"],
        },
        "log_volume": {
            "terms": ["log_volume", "dlv", "dedicated_log"],
            "context": ["dedicated", "volume", "storage"],
            "common_types": ["bool"],
            "related_inputs": ["dedicated_log_volume"],
        },
    }

    @staticmethod
    def type_compatibility_score(source_type: str, target_type: str) -> float:
        """Calculate type compatibility score"""
        if source_type == target_type:
            return 1.0

        # Handle list types
        if ("list" in source_type and "list" in target_type) or (
            "set" in source_type and "set" in target_type
        ):
            return 0.8

        # Penalize heavily for incompatible types
        if ("list" in source_type and "bool" in target_type) or (
            "bool" in source_type and "list" in target_type
        ):
            return 0.0

        return 0.1

    @staticmethod
    def extract_key_terms(text: str) -> Set[str]:
        """Extract key terms from text with focus on infrastructure terms"""
        if not text:
            return set()

        # Infrastructure-specific terms to preserve
        infra_terms = {
            "subnet",
            "vpc",
            "database",
            "db",
            "security",
            "group",
            "log",
            "volume",
            "dedicated",
            "ids",
            "list",
            "private",
        }

        words = set()
        for word in re.findall(r"\b\w+\b", text.lower()):
            if (
                word in infra_terms or len(word) > 3
            ):  # Keep infrastructure terms and meaningful words
                words.add(word)
        return words

    @staticmethod
    def description_context_match(
        source_desc: str, target_desc: str, source_type: str, target_type: str
    ) -> float:
        """Calculate context match score between descriptions with type consideration"""
        if not source_desc or not target_desc:
            return 0.0

        source_terms = VariableMapper.extract_key_terms(source_desc)
        target_terms = VariableMapper.extract_key_terms(target_desc)

        # Check for type indicators in descriptions
        type_context_match = False
        if "list" in source_type:
            type_context_match = any(
                term in source_terms | target_terms for term in ["list", "ids", "array"]
            )
        elif "bool" in source_type:
            type_context_match = any(
                term in source_terms | target_terms
                for term in ["enable", "flag", "boolean"]
            )

        # Calculate intersection with infrastructure terms
        common_terms = source_terms.intersection(target_terms)
        infrastructure_relevance = sum(
            1
            for term in common_terms
            if any(
                term in pattern["terms"] or term in pattern["context"]
                for pattern in VariableMapper.COMMON_PATTERNS.values()
            )
        )

        base_score = len(common_terms) / max(len(source_terms), len(target_terms))
        return (
            base_score
            * (1.2 if type_context_match else 1.0)
            * (1.3 if infrastructure_relevance > 0 else 1.0)
        )

    @staticmethod
    def find_best_match(
        source_var: VariableDefinition,
        target_vars: Dict[str, VariableDefinition],
        threshold: float = 0.6,
    ) -> Optional[str]:
        """Find the best matching variable with strong type checking and context awareness"""
        best_match = None
        best_score = threshold

        for target_name, target_var in target_vars.items():
            # Strong type compatibility check
            type_score = VariableMapper.type_compatibility_score(
                source_var.type, target_var.type
            )
            if type_score == 0.0:  # Skip if types are incompatible
                continue

            # Calculate context and description similarity
            desc_score = VariableMapper.description_context_match(
                source_var.description,
                target_var.description,
                source_var.type,
                target_var.type,
            )

            # Check pattern matching
            pattern_score = 0.0
            for pattern in VariableMapper.COMMON_PATTERNS.values():
                if source_var.type in pattern[
                    "common_types"
                ] and target_name in pattern.get("related_inputs", []):
                    pattern_score = 0.3

            # Combined score with higher weight on type compatibility
            combined_score = (
                type_score * 0.4  # Type compatibility is crucial
                + desc_score * 0.4  # Description context is equally important
                + pattern_score * 0.2  # Pattern matching as supporting evidence
            )

            if combined_score > best_score:
                best_score = combined_score
                best_match = target_name

        return best_match

    @staticmethod
    def infer_mapping(
        source_var: VariableDefinition, target_vars: Dict[str, VariableDefinition]
    ) -> Optional[str]:
        """Infer mapping between output and input variables with strict type checking"""

        # Direct name and type match
        if (
            source_var.name in target_vars
            and source_var.type == target_vars[source_var.name].type
        ):
            return source_var.name

        # Find best match with strict type checking
        best_match = VariableMapper.find_best_match(source_var, target_vars)
        if best_match:
            return best_match

        # Fall back to pattern matching only if types are compatible
        for target_name, target_var in target_vars.items():
            if (
                VariableMapper.type_compatibility_score(
                    source_var.type, target_var.type
                )
                > 0
            ):
                for pattern in VariableMapper.COMMON_PATTERNS.values():
                    if source_var.type in pattern[
                        "common_types"
                    ] and target_name in pattern.get("related_inputs", []):
                        return target_name

        return None


class TerragruntConfigGenerator:
    def __init__(self, template_path: str):
        self.module_details = TerraformModuleDetails()
        self.module_io_cache: Dict[str, ModuleIO] = {}
        self.module_details = TerraformModuleDetails()
        self.module_io_cache: Dict[str, ModuleIO] = {}
        self.variable_mapper = VariableMapper()

        with open(template_path, "r") as f:
            self.template = Template(f.read())

    def get_module_io(
        self, module_name: str, provider: str = "aws"
    ) -> Optional[ModuleIO]:
        """Get module inputs and outputs with their definitions"""
        if module_name in self.module_io_cache:
            return self.module_io_cache[module_name]

        # Get module details from registry
        module_info = self.module_details.get_module_details(
            namespace="terraform-aws-modules",  # or appropriate namespace
            name=module_name,
            provider=provider,
        )

        if not module_info or "root" not in module_info:
            return None

        # Parse inputs
        inputs = {}
        if "inputs" in module_info["root"]:
            input_vars = parse_variables(module_info["root"]["inputs"])
            for var in input_vars:
                inputs[var.name] = var

        # Parse outputs
        outputs = {}
        if "outputs" in module_info["root"]:
            output_vars = parse_variables(module_info["root"]["outputs"])
            for var in output_vars:
                outputs[var.name] = var

        module_io = ModuleIO(inputs=inputs, outputs=outputs)
        self.module_io_cache[module_name] = module_io
        return module_io

    def _infer_module_mappings(
        self, source_module: str, target_module: str
    ) -> Dict[str, str]:
        """Infer variable mappings between two modules using enhanced matching"""
        source_io = self.get_module_io(source_module)
        target_io = self.get_module_io(target_module)

        if not source_io or not target_io:
            return {}

        mappings = {}
        for output_name, output_def in source_io.outputs.items():
            mapped_input = VariableMapper.infer_mapping(output_def, target_io.inputs)
            if mapped_input:
                mappings[output_name] = mapped_input

        return mappings

    def _process_variable_value(
        self, var_name: str, var_value: Any, module_name: str
    ) -> tuple[Any, Optional[str]]:
        """Process variable value with enhanced mapping"""
        if isinstance(var_value, str) and "." in var_value:
            ref_module, output = var_value.split(".")

            # Get module I/O information
            source_io = self._get_module_io(ref_module)
            target_io = self._get_module_io(module_name)

            if source_io and target_io and output in source_io.outputs:
                # Use enhanced mapping
                mappings = self._infer_module_mappings(ref_module, module_name)
                mapped_var_name = mappings.get(output, var_name)
                return f"dependency.{ref_module}.outputs.{output}", ref_module

        if isinstance(var_value, str):
            return f'"{var_value}"', None

        return var_value, None

    def _find_matching_outputs(
        self, source_module: str, target_module: str
    ) -> Dict[str, str]:
        """
        Find matching outputs from source module that could satisfy target module's required inputs.
        Returns a dict of {output_name: mapped_input_name}
        """
        source_io = self.get_module_io(source_module)
        target_io = self.get_module_io(target_module)

        if not source_io or not target_io:
            return {}

        matches = {}
        for input_name, input_var in target_io.inputs.items():
            if not input_var.required:
                continue

            # Try to find matching output from source module
            for output_name, output_var in source_io.outputs.items():
                if self.variable_mapper.find_best_match(
                    output_var, {input_name: input_var}, threshold=0.6
                ):
                    matches[output_name] = input_name

        return matches

    def generate_config(self, module_config: Dict[str, Any], stack_name: str) -> str:
        """Generate terragrunt configuration for a module"""
        module_name = module_config["name"]

        # Get module I/O information
        module_io = self.get_module_io(module_name)
        if not module_io:
            # If we can't get module info, create a basic config
            return self._generate_basic_config(module_name, module_config)

        # Process dependencies and their variables
        dependencies = []
        processed_inputs = {}

        # Handle explicit dependencies
        if "dependencies" in module_config:
            for dep_name in module_config["dependencies"]:
                dep_io = self.get_module_io(dep_name)
                if not dep_io:
                    continue

                # Create dependency block
                dependency = Dependency(
                    name=dep_name,
                    config_path=f"../{dep_name}",
                    mock_outputs=self._generate_mock_outputs(dep_io.outputs),
                )
                dependencies.append(dependency)

        # Process variables and infer mappings
        if "variables" in module_config:
            for var_name, var_value in module_config["variables"].items():
                # Skip if var_value is not a string or is None
                if not isinstance(var_value, str):
                    processed_inputs[var_name] = var_value
                    continue

                # Handle module reference (e.g., "network.database_subnets")
                if "." in var_value:
                    try:
                        ref_module, output_name = var_value.split(
                            ".", 1
                        )  # Split only on first occurrence
                        dep_io = self.get_module_io(ref_module)

                        if dep_io and output_name in dep_io.outputs:
                            # Find best matching input variable
                            source_var = dep_io.outputs[output_name]
                            mapped_name = self.variable_mapper.infer_mapping(
                                source_var, module_io.inputs
                            )

                            if mapped_name:
                                processed_inputs[
                                    mapped_name
                                ] = f"dependency.{ref_module}.outputs.{output_name}"
                            else:
                                # Fallback to original name if no mapping found
                                processed_inputs[
                                    var_name
                                ] = f"dependency.{ref_module}.outputs.{output_name}"

                            # Add dependency if not already present
                            if not any(d.name == ref_module for d in dependencies):
                                dependency = Dependency(
                                    name=ref_module,
                                    config_path=f"../{ref_module}",
                                    mock_outputs=self._generate_mock_outputs(
                                        dep_io.outputs
                                    ),
                                )
                                dependencies.append(dependency)
                        else:
                            # If not a valid module reference, treat as regular string
                            processed_inputs[var_name] = f'"{var_value}"'
                    except ValueError:
                        # If split fails, treat as regular string
                        processed_inputs[var_name] = f'"{var_value}"'
                else:
                    # Handle direct value assignment
                    processed_inputs[var_name] = f'"{var_value}"'

        # Generate the configuration
        return self.template.render(
            includes=self._generate_includes(),
            dependencies=dependencies,
            inputs=processed_inputs,
        )

    def _generate_basic_config(self, module_name: str, module_config: Dict[str, Any]) -> str:
        """Generate a basic terragrunt configuration when module info is not available"""
        dependencies = []
        processed_inputs = {}

        # Handle explicit dependencies
        if "dependencies" in module_config:
            for dep_name in module_config["dependencies"]:
                # Create a basic dependency block
                dependency = Dependency(
                    name=dep_name,
                    config_path=f"../{dep_name}",
                    mock_outputs={},
                )
                dependencies.append(dependency)

        # Process variables
        if "variables" in module_config:
            for var_name, var_value in module_config["variables"].items():
                if isinstance(var_value, str) and "." in var_value:
                    ref_module, output_name = var_value.split(".", 1)
                    processed_inputs[var_name] = f"dependency.{ref_module}.outputs.{output_name}"
                    
                    # Add dependency if not already present
                    if not any(d.name == ref_module for d in dependencies):
                        dependency = Dependency(
                            name=ref_module,
                            config_path=f"../{ref_module}",
                            mock_outputs={},
                        )
                        dependencies.append(dependency)
                else:
                    processed_inputs[var_name] = f'"{var_value}"' if isinstance(var_value, str) else var_value

        # Generate the configuration
        return self.template.render(
            includes=self._generate_includes(),
            dependencies=dependencies,
            inputs=processed_inputs,
        )

    def _generate_mock_outputs(
        self, outputs: Dict[str, VariableDefinition]
    ) -> Dict[str, Any]:
        """Generate mock outputs based on variable definitions"""
        mock_outputs = {}

        for name, var_def in outputs.items():
            # Generate appropriate mock value based on name and type
            if any(substr in name.lower() for substr in ["id", "arn"]):
                mock_outputs[name] = f'"mock-{name}"'
            elif "subnet" in name.lower():
                mock_outputs[name] = '["mock-subnet-1", "mock-subnet-2"]'
            elif any(substr in name.lower() for substr in ["cidr", "ip"]):
                mock_outputs[name] = '"10.0.0.0/16"'
            elif var_def.type == "list":
                mock_outputs[name] = f'["mock-{name}-1", "mock-{name}-2"]'
            elif var_def.type == "map":
                mock_outputs[name] = "{}"
            else:
                mock_outputs[name] = f'"mock-{name}"'

        return mock_outputs

    def _generate_includes(self) -> List[IncludeBlock]:
        """Generate standard include blocks."""
        return [
            IncludeBlock(name="root", path="root.hcl"),
            IncludeBlock(name="provider", path="provider.hcl"),
        ]

    def _generate_dependencies(
        self, module_config: Dict[str, Any], stack_name: str
    ) -> List[Dependency]:
        """Generate dependency blocks based on module configuration."""
        dependencies = []

        if "dependencies" in module_config:
            for dep_name in module_config["dependencies"]:
                # Create a dependency block for each dependency
                dependency = Dependency(
                    name=dep_name,
                    config_path=f"../{dep_name}",  # Relative path to dependent module
                    mock_outputs=self._get_mock_outputs(dep_name),
                )
                dependencies.append(dependency)

        return dependencies

    def _get_mock_outputs(self, module_name: str) -> Dict[str, Any]:
        """Generate mock outputs for a dependency."""
        # This could be enhanced to provide more specific mock outputs based on module type
        mock_outputs = {
            "network": {
                "vpc_id": "mock-vpc-id",
                "private_subnets": ["mock-subnet-1", "mock-subnet-2"],
                "vpc_cidr": "mock-cidr",
            },
            "database": {"endpoint": "mock-db-endpoint", "port": "5432"},
        }
        return mock_outputs.get(module_name, {})

    def _generate_inputs(self, module_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate inputs block from module variables."""
        inputs = {}
        if "variables" in module_config:
            for var_name, var_value in module_config["variables"].items():
                inputs[var_name] = var_value
        return inputs


def parse_variables(module_info: List[Dict[str, Any]]) -> List[VariableDefinition]:
    """Parse module input variables and return list of VariableDefinition objects."""
    parsed_variables = []

    for var in module_info:
        name = var.get("name", "")
        if not name:
            continue

        variable = VariableDefinition(
            name=name,
            type=var.get("type", "any"),
            description=var.get("description", ""),
            default=var.get("default"),
            required="default" not in var,
            sensitive=var.get("sensitive", False),
        )

        parsed_variables.append(variable)

    return parsed_variables


def get_module_io(module_name: str, provider: str = "aws") -> Optional[ModuleIO]:
    """Get module inputs and outputs with their definitions"""
    module_details = TerraformModuleDetails()
    
    # Get module details from registry
    module_info = module_details.get_module_details(
        namespace="terraform-aws-modules",  # or appropriate namespace
        name=module_name,
        provider=provider,
    )

    if not module_info or "root" not in module_info:
        return None

    # Parse inputs
    inputs = {}
    if "inputs" in module_info["root"]:
        input_vars = parse_variables(module_info["root"]["inputs"])
        for var in input_vars:
            inputs[var.name] = var

    # Parse outputs
    outputs = {}
    if "outputs" in module_info["root"]:
        output_vars = parse_variables(module_info["root"]["outputs"])
        for var in output_vars:
            outputs[var.name] = var

    return ModuleIO(inputs=inputs, outputs=outputs)


def process_yaml_config(yaml_content: str, output_dir: str) -> None:
    """Process the YAML configuration and generate terragrunt files."""
    config = yaml.safe_load(yaml_content)
    
    # Get the template path
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    template_path = os.path.join(template_dir, "terragrunt.hcl.j2")
    
    if not os.path.exists(template_path):
        # Fallback to using the terragrunt.hcl file as a template
        template_path = os.path.join(os.path.dirname(__file__), "terragrunt.hcl")
    
    generator = TerragruntConfigGenerator(template_path)

    # Create a mapping of module names to their configurations
    module_configs = {mod["name"]: mod for mod in config.get("modules", [])}

    # Process each stack
    for stack in config.get("stacks", []):
        stack_name = stack["name"]

        # Process each module in the stack
        for module_name in stack["modules"]:
            module_config = module_configs[module_name]

            # Generate terragrunt configuration
            terragrunt_config = generator.generate_config(
                module_config=module_config, stack_name=stack_name
            )

            # Write configuration to file
            output_path = os.path.join(output_dir, stack_name, module_name, "terragrunt.hcl")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(terragrunt_config)

            print(
                f"Generated terragrunt configuration for {module_name} in {stack_name}"
            )
