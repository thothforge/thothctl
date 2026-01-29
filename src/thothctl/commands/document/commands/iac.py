import logging
import click
from click.shell_completion import CompletionItem
from typing import Any, List, Optional
from pathlib import Path
from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.document.iac_documentation import create_terraform_docs

logger = logging.getLogger(__name__)


class DocumentIaCCommand(ClickCommand):
    """Command to document Infrastructure as Code"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.supported_iac_types = ['terraform', 'terragrunt',
                                    'terraform-terragrunt']  # 'cloudformation', 'ansible', 'kubernetes']

    def get_completions(self, ctx: click.Context, args: List[str], incomplete: str) -> List[click.shell_completion.CompletionItem]:
        """Provide autocompletion for IaC types and paths"""
        # If completing the IaC type
        if '--type' in args:
            return [
                CompletionItem(iac_type, help=f"Document {iac_type} infrastructure code")
                for iac_type in self.supported_iac_types
                
                if iac_type.startswith(incomplete)
            ]

        return []

    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""
        if 'framework' not in kwargs:
            self.logger.error("IaC type must be specified")
            return False

        if kwargs['framework'] not in self.supported_iac_types:
            self.logger.error(f"Unsupported IaC framework. Must be one of: {', '.join(self.supported_iac_types)}")
            return False


        return True

    def _execute(self, **kwargs) -> Any:
        """Execute the documentation generation"""
        ctx = click.get_current_context()
        iac_type = kwargs['framework']
        path = ctx.obj.get("CODE_DIRECTORY")

        self.logger.debug(f"Generating documentation for {iac_type} code in {path}")

        try:
            # Add your documentation generation logic here
            # This is a placeholder implementation

            # Auto-enable recursive for terragrunt projects
            framework = kwargs.get("framework", "terraform-terragrunt")
            recursive = kwargs.get('recursive', False)
            if not recursive and framework in ['terraform-terragrunt', 'terragrunt']:
                recursive = True

            self._generate_documentation(directory= path,
                mood= kwargs.get('mood', 'resources'),
                t_docs_path= kwargs.get('config_file', None),
                recursive= recursive,
                exclude= kwargs.get('exclude', ['.terraform', '.git', '.terragrunt-cache']),
                framework=framework,
                graph_type=kwargs.get('graph_type', 'dot')
                                         )

            self.logger.debug("Documentation generated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to generate documentation: {str(e)}")
            raise

    def _generate_documentation(self, directory: str | Path,
        mood: str = "resources",
        t_docs_path: Optional[str] = None,
        recursive: bool = False,
        exclude: List[str] = None,
        framework: str = "terraform-terragrunt",
        graph_type: str = "dot") -> None:
        """Internal method to generate the documentation"""
        try:
            with self.ui.status_spinner("Creating Documentation..."):
                success = create_terraform_docs(directory,
                mood= mood,
                t_docs_path= t_docs_path,
                recursive= recursive,
                exclude= exclude,
                framework = framework,
                graph_type = graph_type)
                
                if success:
                    self.ui.print_success("Documentation generated successfully!")
                else:
                    self.ui.print_error("Failed to generate documentation")
                    raise click.Abort()

        except Exception as e:
            self.ui.print_error(f"Failed to document Code: {str(e)}")
            logger.exception("Document code task failed")
            raise click.Abort()

cli = DocumentIaCCommand.as_click_command(
    help="Generate documentation for Infrastructure as Code"
)(
    click.option('-f',
        '--framework',
        type=click.Choice(['terraform', 'terragrunt', 'terraform-terragrunt'],
                          case_sensitive=False),
        required=True,
        help='Type of IaC framework to document',
        shell_complete=True,
        default='terraform-terragrunt'
    ),
    click.option(
        '--mood',
        type=click.Choice(['resources', 'modules']),
        default='resources',
        help='Type of documentation to generate'
    ),
    click.option(
        '--suffix',
        default='resources',
        help='Suffix for project root path (terragrunt only)'
    ),
    click.option(
        '--config-file',
        type=click.Path(exists=True),
        help='Custom terraform-docs configuration file'
    ),
click.option(
    '--exclude',
    multiple=True,
    default=['.terraform', '.git', ".terragrunt-cache"],
    help='Patterns to exclude from recursive generation'
),
    click.option(
    '--recursive/--no-recursive',
    default=False,
    help='Generate documentation recursively'
),
    click.option(
    '--graph-type',
    type=click.Choice(['dot', 'mermaid'], case_sensitive=False),
    default='dot',
    help='Graph format: dot (SVG) or mermaid (with dependency details)'
)
)
