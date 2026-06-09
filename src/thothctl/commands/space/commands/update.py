"""Update an existing space configuration."""
from datetime import datetime
from pathlib import Path

import click
import toml

from ....common.common import list_spaces
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


class UpdateSpaceCommand(ClickCommand):
    """Command to update an existing space's configuration."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, space_name: str, description, vcs_provider, orchestration_tool, terraform_registry, **kwargs) -> bool:
        spaces = list_spaces()
        if space_name not in spaces:
            raise ValueError(f"Space '{space_name}' does not exist")
        if not any([description, vcs_provider, orchestration_tool, terraform_registry]):
            raise ValueError("Provide at least one option to update (--description, --vcs-provider, --orchestration-tool, --terraform-registry)")
        return True

    def _execute(self, space_name: str, description, vcs_provider, orchestration_tool, terraform_registry, **kwargs) -> None:
        config_path = Path.home() / ".thothcf" / "spaces.toml"
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        space = config["spaces"][space_name]

        if description is not None:
            space["description"] = description
        if vcs_provider is not None:
            space.setdefault("version_control", {})["provider"] = vcs_provider
        if orchestration_tool is not None:
            space.setdefault("orchestration", {})["tool"] = orchestration_tool
        if terraform_registry is not None:
            space.setdefault("terraform", {})["registry"] = terraform_registry

        space["updated_at"] = datetime.now().isoformat()

        with open(config_path, mode="wt", encoding="utf-8") as fp:
            toml.dump(config, fp)

        self.ui.print_success(f"🔧 Space '{space_name}' updated successfully")


cli = UpdateSpaceCommand.as_click_command(help="Update an existing space's configuration")(
    click.argument("space_name"),
    click.option("-d", "--description", help="New description for the space", default=None),
    click.option(
        "-vcs", "--vcs-provider",
        type=click.Choice(["azure_repos", "github", "gitlab"], case_sensitive=True),
        help="Version Control System provider",
        default=None,
    ),
    click.option(
        "-ot", "--orchestration-tool",
        type=click.Choice(["terragrunt", "terramate", "none"], case_sensitive=True),
        help="Default orchestration tool",
        default=None,
    ),
    click.option(
        "-tr", "--terraform-registry",
        help="Terraform registry URL",
        default=None,
    ),
)
