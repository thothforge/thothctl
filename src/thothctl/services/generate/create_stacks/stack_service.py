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
            raise FileNotFoundError(f"Template file not found: {self.template_path}")
        
        # Create generator with the template
        self.generator = TerragruntConfigGenerator(str(self.template_path))

    def generate_stacks_from_config(self, config_file: str, output_dir: Path) -> None:
        """
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
