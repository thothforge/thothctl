import logging
import click
from typing import Any, List, Optional
from pathlib import Path

from ....core.cli_ui import CliUI

from ....core.commands import ClickCommand
from ....services.generate.create_template.create_component_service import create_component

logger = logging.getLogger(__name__)


class GenComponentCommand(ClickCommand):
    """Command to Check IaC outputs and artifacts"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()


    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""
        # add validation for component name
        if not kwargs.get('component_name'):
            self.ui.print_error("Component name is required")
            return False
        if not kwargs.get('component_path'):
            self.ui.print_error("Component path is required")
            return False
        if not kwargs.get('component_type'):
            self.ui.print_error("Component type is required")
            return False
        return True

    def execute(self, **kwargs) -> Any:
        """Execute the check command """
        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY")

        try:
            self.ui.print_info(f"Creating component {kwargs.get('component_name')} in {kwargs.get('component_path')}")
            create_component(
                component_type=kwargs.get('component_type'),
                component_name=kwargs.get('component_name'),
                component_path=kwargs.get('component_path')
            )
        except Exception as e:
            logger.error(f"Failed to create component: {e}")
            raise click.Abort()



cli = GenComponentCommand.as_click_command(
    help="Create IaC component according to project rules and conventions"
)(
    click.option(
        '-ct','--component-type',
        help='Component Type for base template, there are the names for your folder in folders field in .thothcf.toml'
    ),
    click.option(
        "-cn",'--component-name',
        help='Component name for template'
    ),
    click.option(
        '-cph', "--component-path",
        help='Component path for base template, for example ./modules'
    ),

)


