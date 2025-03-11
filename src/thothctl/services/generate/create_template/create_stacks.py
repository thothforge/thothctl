from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import git
import os
import yaml
from jinja2 import Template


@dataclass
class TerraformModule:
    name: str
    repository_url: str
    version: str
    dependencies: List[str]
    variables: Dict[str, any]


class TerraformComposer:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.modules_cache = Path(workspace_dir) / ".modules"
        self.modules: Dict[str, TerraformModule] = {}

    def init_workspace(self):
        """Initialize the workspace and modules cache directory"""
        self.workspace_dir.mkdir(exist_ok=True)
        self.modules_cache.mkdir(exist_ok=True)

    def add_module(self, module: TerraformModule):
        """Register a new module"""
        self.modules[module.name] = module

    def fetch_module(self, module: TerraformModule) -> Path:
        """Fetch a module from its repository"""
        module_path = self.modules_cache / module.name / module.version

        if not module_path.exists():
            module_path.mkdir(parents=True)
            git.Repo.clone_from(module.repository_url, module_path)
            repo = git.Repo(module_path)
            repo.git.checkout(module.version)

        return module_path

    def generate_module_block(self, module: TerraformModule) -> str:
        """Generate Terraform module block"""
        template = """
module "{{ module.name }}" {
  source = "{{ source }}"
  {% for key, value in module.variables.items() %}
  {{ key }} = {{ value }}
  {% endfor %}
}
"""
        return Template(template).render(
            module=module, source=f"git::{module.repository_url}?ref={module.version}"
        )

    def generate_terraform_config(self, stack_name: str, modules: List[str]) -> str:
        """Generate complete Terraform configuration"""
        config_template = """
terraform {
  required_version = ">= 1.0.0"

  backend "s3" {
    bucket = "{{ backend_bucket }}"
    key    = "{{ stack_name }}/terraform.tfstate"
    region = "{{ region }}"
  }
}

{% for module_block in module_blocks %}
{{ module_block }}
{% endfor %}
"""
        module_blocks = []
        for module_name in modules:
            if module_name in self.modules:
                module = self.modules[module_name]
                module_blocks.append(self.generate_module_block(module))

        return Template(config_template).render(
            backend_bucket=os.getenv("TF_STATE_BUCKET", "default-tf-state"),
            stack_name=stack_name,
            region=os.getenv("AWS_REGION", "us-east-1"),
            module_blocks=module_blocks,
        )


class StackManager:
    def __init__(self, composer: TerraformComposer):
        self.composer = composer
        self.stacks: Dict[str, List[str]] = {}

    def create_stack(self, stack_name: str, modules: List[str]):
        """Create a new stack configuration"""
        self.stacks[stack_name] = modules
        stack_dir = self.composer.workspace_dir / stack_name
        stack_dir.mkdir(exist_ok=True)

        # Generate main.tf
        config = self.composer.generate_terraform_config(stack_name, modules)
        with open(stack_dir / "main.tf", "w") as f:
            f.write(config)

        # Generate variables.tf if needed
        self._generate_variables(stack_dir, modules)

    def _generate_variables(self, stack_dir: Path, modules: List[str]):
        """Generate variables.tf file for the stack"""
        variables = {}
        for module_name in modules:
            if module_name in self.composer.modules:
                module = self.composer.modules[module_name]
                variables.update(module.variables)

        if variables:
            with open(stack_dir / "variables.tf", "w") as f:
                for var_name, var_value in variables.items():
                    f.write(f'variable "{var_name}" {{\n')
                    f.write(f'  description = "Variable for {var_name}"\n')
                    f.write("  type = any\n")
                    f.write("}\n\n")


def load_stack_config(config_file: str) -> Dict:
    """Load stack configuration from YAML"""
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


# Example usage
def main():
    import click

    @click.command()
    @click.option("--config", "-c", required=True, help="Stack configuration file")
    @click.option(
        "--workspace", "-w", default="./terraform", help="Workspace directory"
    )
    def create_stack(config, workspace):
        # Initialize composer
        composer = TerraformComposer(workspace)
        composer.init_workspace()

        # Load configuration
        stack_config = load_stack_config(config)

        # Register modules
        for module_config in stack_config.get("modules", []):
            module = TerraformModule(
                name=module_config["name"],
                repository_url=module_config["repository"],
                version=module_config["version"],
                dependencies=module_config.get("dependencies", []),
                variables=module_config.get("variables", {}),
            )
            composer.add_module(module)

        # Create stack manager
        stack_manager = StackManager(composer)

        # Create stacks
        for stack in stack_config.get("stacks", []):
            stack_manager.create_stack(stack["name"], stack["modules"])

        click.echo("Stack(s) created successfully!")


if __name__ == "__main__":
    main()
