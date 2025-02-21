import click
from contextlib import contextmanager

from pathlib import Path, PurePath
import os
import json

from thothctl.core.commands import ClickCommand
from thothctl.create_terramate.create_terramate_stacks import (
    create_terramate_main_file,
    recursive_graph_dependencies_to_json,
)
from thothctl.create_terramate.manage_terramate_stacks import (
    TerramateStackManager,

)


class ConvertProjectCommand(ClickCommand):
    """Command to initialize a new project"""

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""

        return True

    def execute(
            self,
            use_terramate_stacks: bool= False,

            **kwargs
    ) -> None:
        """Execute Environment initialization"""
        ctx = click.get_current_context()
        debug = ctx.obj.get('DEBUG')
        code_directory = ctx.obj.get('CODE_DIRECTORY')
        if use_terramate_stacks:
            manager = TerramateStackManager()

            try:
                # Process single directory
                directory = Path(code_directory)
                graph = manager.get_dependency_graph(directory)
                manager.create_stack(json.loads(graph), directory, optimized=False)

                # Or process recursively
                manager.process_directory_recursively(directory)

            except Exception as e:
                self.logger.error(f"Operation failed: {e}")
            #self._convert_to_terramate(code_directory, "main")

    def _convert_to_terramate(self, code_directory: str, branch_name) -> None:
        """Convert from terragrunt to terramate stacks"""
        branch = branch_name
        self.logger.info(f"Default branch tool is {branch}")
        create_terramate_main_file(branch)
        recursive_graph_dependencies_to_json(directory=PurePath(code_directory))

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting project cleanup")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("Project cleanup completed")

    @contextmanager
    def _change_directory(self, path: Path):
        """Safely change directory and return to original"""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)


# Create the Click command
cli = ConvertProjectCommand.as_click_command(
    help="Convert project to template, template to project or between frameworks like terragrunt and terramate for IaC"
)(

    click.option("-tm",
                 "--use_terramate_stacks",
                 help="Create create terramate stack for advance deployments",
                 is_flag=True,
                 default=False

                 ),

    click.option("-mpro", "--make-project",

                 help="Create project from template",
                 default=None,
                 ),
    click.option("-mtem", "--make-template",
                 help="Create template from project",
                 default=None,
                 ),
    click.option('-tpt', "--template-project-type",
                 help="Provide project type according to Internal Developer Portal and frameworks",
                 type=click.Choice(["terraform", "tofu",
                                    "cdkv2",
                                    ], case_sensitive=True
                                   ),
                 default="terraform"
                 ),
    click.option("-br","--branch-name",
                 help="Provide branch name for terramate stacks",
                 default="main"
                 )

)
