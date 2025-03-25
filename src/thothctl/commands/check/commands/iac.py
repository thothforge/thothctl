import logging
import click
from typing import Any, List, Optional
from pathlib import Path

from ....core.cli_ui import CliUI

from ....core.commands import ClickCommand
from ....services.check.project.check_project_structure import validate

logger = logging.getLogger(__name__)


class CheckIaCCommand(ClickCommand):
    """Command to Check IaC outputs and artifacts"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.supported_check_types = ["tfplan", "module", "project"]


    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""

        if kwargs['check_type'] not in self.supported_check_types:
            self.logger.error(f"Unsupported Check type. Must be one of: {', '.join(self.supported_check_types)}")
            return False


        return True

    def execute(self, **kwargs) -> Any:
        """Execute the check command """
        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY")


        try:
            # Add your documentation generation logic here
            # This is a placeholder implementation
            if kwargs['check_type']== "project":
                self._validate_project_structure(directory=directory, mode=kwargs['mode'], check_type=kwargs['check_type'])

            self.logger.debug("Documentation generated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to generate documentation: {str(e)}")
            raise

    def _validate_project_structure(self, directory: str, mode: str = "soft", check_type:str = "project", ) -> bool:
        """Validate the project structure"""
        return validate(directory=directory,check_type= check_type, mode=mode )


cli = CheckIaCCommand.as_click_command(
    help="Check Infrastructure as code artifacts like tfplan and dependencies"
)(
    click.option(
        '--mode',
        type=click.Choice(['soft', 'hard']),
        default='soft',
        help='Validation mode'
    ),
    click.option(
        "-deps",'--dependencies',
        default=False,
        help='View a dependency graph in asccii pretty shell output'
    ),
    click.option(
        '--recursive',
        type=click.Choice(['local', 'recursive']),
        help='Validate your terraform plan recursively or in one directory'
    ),
    click.option(
        '--outmd',
        help="Output markdown file path",
        is_flag=True,
        default=False,
    ),
    click.option("-type","--check_type",

                 help="Check module or project structure format, or check tfplan",
                 type=click.Choice(["tfplan", "module", "project"], case_sensitive=True),
                 default="project",
                 ),
    #click.option("--tfplan",
    #             help="Validate terraform plan",
    #             is_flag=True,
    #             default=False,
    #             )
)
