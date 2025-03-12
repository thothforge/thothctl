from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
from typing import Dict, List, Optional
import re
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader, Template
import json

@dataclass
class TerraformVariable:
    """Represents a Terraform variable."""
    name: str
    type: str
    description: Optional[str] = None
    default: Optional[any] = None

@dataclass
class IncludeBlock:
    name: str
    path: str


@dataclass
class Dependency:
    name: str
    config_path: str
    mock_outputs: Dict[str, any]


class TerraformConfigGenerator:
    def __init__(self, template_dir: str = "templates"):
        self.var_pattern = re.compile(
            r'variable\s+"([^"]+)"\s*{([^}]+)}',
            re.MULTILINE | re.DOTALL
        )
        self.type_pattern = re.compile(r'type\s*=\s*([^\n]+)')
        self.description_pattern = re.compile(r'description\s*=\s*"([^"]+)"')
        self.default_pattern = re.compile(r'default\s*=\s*(.+?)(?=\s*[}\n])')

        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )

    def parse_variables(self, content: str) -> List[TerraformVariable]:
        """Parse Terraform variables from content."""
        variables = []

        for match in self.var_pattern.finditer(content):
            name = match.group(1)
            block = match.group(2)

            type_match = self.type_pattern.search(block)
            desc_match = self.description_pattern.search(block)
            default_match = self.default_pattern.search(block)

            var = TerraformVariable(
                name=name,
                type=type_match.group(1).strip() if type_match else "string",
                description=desc_match.group(1) if desc_match else None,
                default=default_match.group(1).strip() if default_match else None
            )
            variables.append(var)

        return variables

    def generate_terragrunt_config(self,
                                   includes: List[IncludeBlock],
                                   dependencies: List[Dict],
                                   variables: List[TerraformVariable]) -> str:
        """
        Generate Terragrunt configuration with dynamic includes and dependencies.

        Args:
            includes: List of include blocks to add
            dependencies: List of dependency configurations
            variables: List of Terraform variables
        """
        # Process dependencies
        processed_deps = []
        for dep in dependencies:
            mock_outputs = {}
            for output in dep['outputs']:
                mock_value = self._generate_mock_value(output['value'])
                if mock_value:
                    mock_outputs[output['name']] = mock_value

            processed_deps.append(Dependency(
                name=dep['name'],
                config_path=dep['config_path'],
                mock_outputs=mock_outputs
            ))

        # Match variables with outputs for inputs block
        inputs = {}
        for var in variables:
            matching_dep = self._find_matching_dependency_output(var.name, dependencies)
            if matching_dep:
                dep_name = matching_dep['dependency']
                output_name = matching_dep['output']
                inputs[var.name] = f"dependency.{dep_name}.outputs.{output_name}"

        # Load and render template
        template = self.env.get_template('terragrunt.hcl.j2')

        return template.render(
            includes=includes,
            dependencies=processed_deps,
            inputs=inputs
        )

    def _find_matching_dependency_output(self, var_name: str, dependencies: List[Dict]) -> Optional[Dict]:
        """Find matching output across all dependencies."""
        for dep in dependencies:
            for output in dep['outputs']:
                if self._is_matching_output(var_name, output['name']):
                    return {
                        'dependency': dep['name'],
                        'output': output['name']
                    }
        return None

    def _is_matching_output(self, var_name: str, output_name: str) -> bool:
        """Check if variable and output names match."""
        var_parts = set(var_name.lower().split('_'))
        output_parts = set(output_name.lower().split('_'))
        return bool(var_parts & output_parts)  # Return True if there's any intersection

    def _generate_mock_value(self, output_value: str) -> Optional[str]:
        """Generate mock value based on output value pattern."""
        if 'vpc_id' in output_value.lower():
            return '"vpc-12345678"'
        elif 'subnet' in output_value.lower():
            return '["subnet-12345678"]'
        elif 'cidr' in output_value.lower():
            return '["10.0.0.0/24"]'
        elif 'security_group' in output_value.lower():
            return '["sg-12345678"]'
        return None

    def _find_matching_output(self, var_name: str, outputs: List[dict]) -> Optional[dict]:
        """Find matching output for a variable."""
        # Direct match
        for output in outputs:
            if output['name'] == var_name:
                return output

        # Pattern matching
        var_parts = set(var_name.lower().split('_'))
        for output in outputs:
            output_parts = set(output['name'].lower().split('_'))
            if var_parts & output_parts:  # If there's any intersection
                return output

        return None

# Example usage:
def main():
    generator = TerraformConfigGenerator(template_dir="templates")

    # Define includes
    includes = [
        IncludeBlock(name="root", path="root.hcl"),
        IncludeBlock(name="env", path="env.hcl")
    ]

    # Define dependencies
    dependencies = [
        {
            "name": "vpc",
            "config_path": "${get_parent_terragrunt_dir()}/vpc",
            "outputs": [
                {"name": "vpc_id", "value": "module.vpc.vpc_id"},
                {"name": "private_subnets", "value": "module.vpc.private_subnets"}
            ]
        },
        {
            "name": "security_groups",
            "config_path": "${get_parent_terragrunt_dir()}/security-groups",
            "outputs": [
                {"name": "bastion_sg_id", "value": "module.security_groups.bastion_sg_id"}
            ]
        }
    ]

    # Parse variables from Terraform files
    with open('variables.tf', 'r') as f:
        variables = generator.parse_variables(f.read())

    # Generate configuration
    config = generator.generate_terragrunt_config(
        includes=includes,
        dependencies=dependencies,
        variables=variables
    )

    # Save to file
    with open('terragrunt.hcl', 'w') as f:
        f.write(config)

    print("Generated terragrunt.hcl:")
    print(config)


if __name__ == "__main__":
    main()
