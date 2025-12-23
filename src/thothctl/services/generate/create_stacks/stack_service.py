"""Service for generating infrastructure stacks."""
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .config_generator import TerraformConfigGenerator
from .remote_config_generation import TerragruntConfigGenerator


class StackService:
    """Service for generating infrastructure stacks."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize the template path
        template_dir = Path(__file__).parent / "templates"
        self.template_path = template_dir / "terragrunt.hcl.j2"
        
        if not self.template_path.exists():
            self.logger.warning(f"Template file not found: {self.template_path}")
        
        # Create generator with the template if it exists
        if self.template_path.exists():
            self.generator = TerragruntConfigGenerator(str(self.template_path))
        else:
            self.generator = None

    def generate_stacks_from_config(self, config_file: str, output_dir: Path) -> None:
        """Generate stacks from a YAML configuration file"""
        self.logger.info(f"Generating stacks from configuration file: {config_file}")

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
                self.logger.info(f"Generating stack: {stack_name}")

                # Create stack directory
                stack_dir = output_dir / stack_name
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

                    self.logger.info(f"Generated configuration for {module_name} in {stack_name}")

        except Exception as e:
            self.logger.error(f"Failed to process YAML configuration: {e}", exc_info=True)
            raise ValueError(f"Failed to process YAML configuration: {e}")

    def generate_single_stack(self, stack_name: str, modules: List[str], output_dir: Path) -> None:
        """Generate a single stack with specified modules"""
        self.logger.info(f"Generating stack: {stack_name}")
        
        if not modules:
            self.logger.warning("No modules specified, creating empty stack structure")
        
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
            
            self.logger.info(f"Created module: {module}")

    def create_example_config(self, output_file: Path) -> None:
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

    def _create_root_files(self, stack_dir: Path) -> None:
        """Create root configuration files for the stack according to .thothcf_project.toml template"""
        from ....common.common import load_iac_conf
        
        # Load template configuration
        try:
            dirname = Path(__file__).parent.parent.parent.parent / "common"
            config = load_iac_conf(str(dirname), file_name=".thothcf_project.toml")
            
            # Get stack content from template
            stack_content = []
            for folder in config.get("project_structure", {}).get("folders", []):
                if folder.get("name") == "stacks":
                    stack_content = folder.get("content", [])
                    break
        except Exception as e:
            self.logger.warning(f"Could not load template config: {e}, using defaults")
            stack_content = ["main.tf", "outputs.tf", "variables.tf", "README.md", "terragrunt.hcl", "graph.svg"]
        
        # Create files based on template
        for file_name in stack_content:
            if file_name == "main.tf":
                with open(stack_dir / "main.tf", "w") as f:
                    f.write("""# Main terraform configuration for this stack
# Define your resources here

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
""")
            elif file_name == "outputs.tf":
                with open(stack_dir / "outputs.tf", "w") as f:
                    f.write("""# Output values for this stack
# Define outputs that other stacks or modules can reference

# Example output:
# output "vpc_id" {
#   description = "ID of the VPC"
#   value       = module.vpc.vpc_id
# }
""")
            elif file_name == "variables.tf":
                with open(stack_dir / "variables.tf", "w") as f:
                    f.write("""# Input variables for this stack
# Define variables that can be passed to this stack

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
}
""")
            elif file_name == "terragrunt.hcl":
                with open(stack_dir / "terragrunt.hcl", "w") as f:
                    f.write("""# Terragrunt configuration for this stack
include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "provider" {
  path = find_in_parent_folders("provider.hcl")
}

# Local values
locals {
  # Add local values here
}

# Inputs to pass to terraform
inputs = {
  region       = local.region
  environment  = local.environment
  project_name = local.project_name
}

# Dependencies (if any)
# dependencies {
#   paths = ["../other-stack"]
# }
""")
            elif file_name == "README.md":
                with open(stack_dir / "README.md", "w") as f:
                    f.write(f"""# {stack_dir.name} Stack

## Description
This stack contains the infrastructure components for {stack_dir.name}.

## Structure
- `main.tf` - Main terraform configuration
- `outputs.tf` - Output definitions
- `variables.tf` - Input variable definitions
- `terragrunt.hcl` - Terragrunt configuration
- `README.md` - This documentation

## Usage

### Deploy the stack
```bash
terragrunt apply
```

### Destroy the stack
```bash
terragrunt destroy
```

### Plan changes
```bash
terragrunt plan
```

## Dependencies
List any dependencies this stack has on other stacks or modules.

## Outputs
List the outputs this stack provides for other stacks to consume.
""")
            elif file_name == "graph.svg":
                with open(stack_dir / "graph.svg", "w") as f:
                    f.write("""<!-- This file will be generated by running: terragrunt graph-dependencies | dot -Tsvg > graph.svg -->
<!-- Run the above command to generate the dependency graph visualization -->
""")
        
        # Also create the parent-level files that terragrunt needs
        parent_dir = stack_dir.parent
        
        # Create provider.hcl at parent level if it doesn't exist
        provider_file = parent_dir / "provider.hcl"
        if not provider_file.exists():
            with open(provider_file, "w") as f:
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
        
        # Create root.hcl at parent level if it doesn't exist
        root_file = parent_dir / "root.hcl"
        if not root_file.exists():
            with open(root_file, "w") as f:
                f.write("""
locals {
  region       = "us-east-1"
  environment  = "dev"
  project_name = "my-project"
}

inputs = {
  region       = local.region
  environment  = local.environment
  project_name = local.project_name
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
        Generate stacks from a YAML configuration file.
        
        Args:
            config_file: Path to the YAML configuration file
            output_dir: Directory where stacks will be generated
        """
        self.logger.info(f"Generating stacks from configuration file: {config_file}")
        
        # Read the YAML configuration
        with open(config_file, 'r') as f:
            yaml_content = f.read()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Process the configuration and generate stacks
        try:
            # Process the YAML configuration
            config = yaml.safe_load(yaml_content)
            
            # Create a mapping of module names to their configurations
            module_configs = {mod["name"]: mod for mod in config.get("modules", [])}
            
            # Process each stack
            for stack in config.get("stacks", []):
                stack_name = stack["name"]
                self.logger.info(f"Generating stack: {stack_name}")
                
                # Create root configuration files
                stack_dir = output_dir / stack_name
                os.makedirs(stack_dir, exist_ok=True)
                self._create_root_files(stack_dir)
                
                # Process each module in the stack
                for module_name in stack["modules"]:
                    module_config = module_configs[module_name]
                    
                    # Generate terragrunt configuration
                    try:
                        terragrunt_config = self.generator.generate_config(
                            module_config=module_config, 
                            stack_name=stack_name
                        )
                        
                        # Write configuration to file
                        module_dir = stack_dir / module_name
                        os.makedirs(module_dir, exist_ok=True)
                        
                        with open(module_dir / "terragrunt.hcl", "w") as f:
                            f.write(terragrunt_config)
                            
                        self.logger.info(f"Generated configuration for {module_name} in {stack_name}")
                    except Exception as e:
                        self.logger.error(f"Error generating config for {module_name}: {e}", exc_info=True)
                        self.logger.warning(f"Skipping {module_name} due to error: {e}")
                        
        except Exception as e:
            self.logger.error(f"Failed to process YAML configuration: {e}", exc_info=True)
            raise ValueError(f"Failed to process YAML configuration: {e}")

    def generate_stack(self, stack_name: str, modules: List[str], output_dir: Path) -> None:
        """
        Generate a single stack with specified modules.
        
        Args:
            stack_name: Name of the stack to generate
            modules: List of module names to include in the stack
            output_dir: Directory where the stack will be generated
        """
        self.logger.info(f"Generating stack: {stack_name}")
        
        if not modules:
            self.logger.warning("No modules specified, creating empty stack structure")
        
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
            
            self.logger.info(f"Created module: {module}")

    def _create_root_files(self, stack_dir: Path) -> None:
        """
        Create root configuration files for the stack.
        
        Args:
            stack_dir: Directory where root files will be created
        """
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

    def _create_basic_module_config(self, module_dir: Path, module_name: str) -> None:
        """
        Create a basic terragrunt.hcl configuration for a module.
        
        Args:
            module_dir: Directory where the module configuration will be created
            module_name: Name of the module
        """
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

    def create_example_config(self, output_file: Path) -> None:
        """
        Create an example YAML configuration file.
        
        Args:
            output_file: Path where the example configuration will be saved
        """
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
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Write the example configuration to file
        with open(output_file, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False)
            
        self.logger.info(f"Created example configuration file: {output_file}")
