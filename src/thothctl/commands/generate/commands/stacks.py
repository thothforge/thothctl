import logging
import os
from pathlib import Path
from typing import Optional, List

import click
import yaml

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


class GenStacksCommand(ClickCommand):
    """Command to generate infrastructure stacks based on configuration"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""
        if not kwargs.get('config_file') and not kwargs.get('stack_name') and not kwargs.get('create_example'):
            self.ui.print_error("Either config file, stack name, or create-example flag is required")
            return False
        return True

    def execute(self, **kwargs) -> None:
        """Execute the stacks generation command"""
        ctx = click.get_current_context()
        directory = Path(ctx.obj.get("CODE_DIRECTORY", "."))

        config_file = kwargs.get('config_file')
        stack_name = kwargs.get('stack_name')
        output_dir = Path(kwargs.get('output_dir') or directory / "stacks")  # Convert to Path here
        create_example = kwargs.get('create_example')

        try:
            if create_example:
                example_path = directory / "stack-config-example.yaml"
                self._create_example_config(example_path)
                self.ui.print_success(f"Created example configuration file: {example_path}")
                return

            if config_file:
                self._generate_from_config(config_file, output_dir)
            else:
                modules = kwargs.get('modules', [])
                self._generate_stack(stack_name, modules, output_dir)

            self.ui.print_success(f"Successfully generated stack(s) in {output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to generate stacks: {e}", exc_info=True)
            self.ui.print_error(f"Failed to generate stacks: {e}")
            raise click.Abort()

    def _generate_from_config(self, config_file: str, output_dir: Path) -> None:
        """Generate stacks from a YAML configuration file"""
        self.ui.print_info(f"Generating stacks from configuration file: {config_file}")

        # Read the YAML configuration
        with open(config_file, 'r') as f:
            yaml_content = f.read()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Process the configuration and generate stacks
        try:
            # Parse the YAML configuration
            config = yaml.safe_load(yaml_content)

            # Create a mapping of module names to their configurations
            module_configs = {mod["name"]: mod for mod in config.get("modules", [])}

            # Process each stack
            for stack in config.get("stacks", []):
                stack_name = stack["name"]
                self.ui.print_info(f"Generating stack: {stack_name}")

                # Create stack directory
                stack_dir = output_dir / stack_name  # This should work now that output_dir is a Path
                os.makedirs(stack_dir, exist_ok=True)

                # Create root configuration files
                self._create_root_files(stack_dir)

                # Process each module in the stack
                for module_name in stack["modules"]:
                    module_config = module_configs[module_name]

                    # Create module directory
                    module_dir = stack_dir / module_name
                    os.makedirs(module_dir, exist_ok=True)

                    # Create terragrunt.hcl for the module
                    self._create_module_config(module_dir, module_name, module_config)

                    self.ui.print_info(f"Generated configuration for {module_name} in {stack_name}")

        except Exception as e:
            self.logger.error(f"Failed to process YAML configuration: {e}", exc_info=True)
            raise ValueError(f"Failed to process YAML configuration: {e}")

    def _generate_stack(self, stack_name: str, modules: List[str], output_dir: Path) -> None:
        """Generate a single stack with specified modules"""
        self.ui.print_info(f"Generating stack: {stack_name}")
        
        if not modules:
            self.ui.print_warning("No modules specified, creating empty stack structure")
        
        # Create stack directory
        stack_dir = output_dir / stack_name
        os.makedirs(stack_dir, exist_ok=True)
        
        # Create root configuration files
        self._create_root_files(stack_dir)
        
        # Create module directories and configurations
        for module in modules:
            module_dir = stack_dir / module
            os.makedirs(module_dir, exist_ok=True)
            
            # Create basic terragrunt.hcl for the module
            self._create_basic_module_config(module_dir, module)
            
            self.ui.print_info(f"Created module: {module}")

    def _create_root_files(self, stack_dir: Path) -> None:
        """Create root configuration files for the stack"""
        # Create provider.hcl
        with open(stack_dir / "provider.hcl", "w") as f:
            f.write("""
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite"
  contents  = <<EOF
provider "aws" {
  region = var.region
}
EOF
}
""")
        
        # Create root.hcl
        with open(stack_dir / "root.hcl", "w") as f:
            f.write("""
locals {
  region = "us-east-1"
}

inputs = {
  region = local.region
}

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket         = "terraform-state-${get_aws_account_id()}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.region
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
""")

    def _create_module_config(self, module_dir: Path, module_name: str, module_config: dict) -> None:
        """Create a terragrunt.hcl configuration for a module based on its config"""
        # Extract dependencies and variables
        dependencies = module_config.get("dependencies", [])
        variables = module_config.get("variables", {})
        
        # Build dependency blocks
        dependency_blocks = ""
        for dep in dependencies:
            dependency_blocks += f"""
dependency "{dep}" {{
  config_path = "../{dep}"
  
  mock_outputs = {{
    # Mock outputs will be generated here
  }}
  
  mock_outputs_merge_strategy_with_state = "shallow"
}}
"""
        
        # Build inputs block
        inputs_block = "inputs = {\n"
        for var_name, var_value in variables.items():
            if isinstance(var_value, str) and "." in var_value:
                # Handle reference to another module's output
                ref_module, output_name = var_value.split(".", 1)
                inputs_block += f'  {var_name} = dependency.{ref_module}.outputs.{output_name}\n'
            else:
                # Handle direct value
                if isinstance(var_value, str):
                    inputs_block += f'  {var_name} = "{var_value}"\n'
                else:
                    inputs_block += f'  {var_name} = {var_value}\n'
        inputs_block += "}"
        
        # Create the complete terragrunt.hcl file
        with open(module_dir / "terragrunt.hcl", "w") as f:
            f.write(f"""
include "root" {{
  path = find_in_parent_folders("root.hcl")
}}

include "provider" {{
  path = find_in_parent_folders("provider.hcl")
}}

terraform {{
  source = "git::https://github.com/terraform-aws-modules/{module_name}.git?ref=v1.0.0"
}}

{dependency_blocks}

{inputs_block}
""")

    def _create_basic_module_config(self, module_dir: Path, module_name: str) -> None:
        """Create a basic terragrunt.hcl configuration for a module"""
        with open(module_dir / "terragrunt.hcl", "w") as f:
            f.write(f"""
include "root" {{
  path = find_in_parent_folders("root.hcl")
}}

include "provider" {{
  path = find_in_parent_folders("provider.hcl")
}}

terraform {{
  source = "git::https://github.com/terraform-aws-modules/{module_name}.git?ref=v1.0.0"
}}

inputs = {{
  # Add your module inputs here
}}
""")

    def _create_example_config(self, output_file: Path) -> None:
        """Create an example YAML configuration file"""
        example_config = {
            "cloud": "aws",
            "modules": [
                {
                    "name": "vpc",
                    "variables": {
                        "vpc_cidr": "10.0.0.0/16",
                        "environment": "production"
                    }
                },
                {
                    "name": "ec2-instance",
                    "variables": {
                        "subnet_id": "vpc.private_subnets"
                    },
                    "dependencies": ["vpc"]
                },
                {
                    "name": "rds",
                    "dependencies": ["vpc"],
                    "variables": {
                        "engine": "postgres",
                        "engine_version": "15.1",
                        "instance_class": "db.t3.medium",
                        "database_subnets": "vpc.database_subnets"
                    }
                }
            ],
            "stacks": [
                {
                    "name": "production-platform",
                    "modules": ["vpc", "rds", "ec2-instance"]
                }
            ]
        }

        # Create parent directory if needed and it's not the current directory
        parent_dir = os.path.dirname(str(output_file))
        if parent_dir:  # Only create if parent_dir is not empty
            os.makedirs(parent_dir, exist_ok=True)

        # Write the example configuration to file
        with open(output_file, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False)


# Create the Click command
cli = GenStacksCommand.as_click_command(
    help="Generate infrastructure stacks based on configuration"
)(
    click.option(
        "-c",
        "--config-file",
        help="Path to YAML configuration file defining stacks and modules",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    ),
    click.option(
        "-s",
        "--stack-name",
        help="Name of the stack to generate (when not using config file)",
    ),
    click.option(
        "-m",
        "--modules",
        help="Comma-separated list of modules to include in the stack",
        callback=lambda ctx, param, value: value.split(",") if value else [],
    ),
    click.option(
        "-o",
        "--output-dir",
        help="Directory where stacks will be generated",
        type=click.Path(file_okay=False),
    ),
    click.option(
        "--create-example",
        is_flag=True,
        help="Create an example stack configuration file",
        default=False,
    ),
)
