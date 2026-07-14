"""List templates command."""

import click
from typing import Optional
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....common.common import get_space_vcs_provider
from ....core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
from ....core.integrations.github.get_github import get_pattern_from_github


class ListTemplatesCommand(ClickCommand):
    """Command to list available templates from VCS providers."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, space: Optional[str] = None, show_defaults: bool = False, **kwargs) -> None:
        """Execute templates listing"""
        
        # Show default GitHub templates if requested or no space provided
        if show_defaults:
            self._list_default_templates()
        
        # Show VCS templates from space if provided
        if space:
            self.ui.print_info(f"📋 Listing templates from space: {space}")
            
            # Get VCS provider from space
            vcs_provider = get_space_vcs_provider(space)
            if not vcs_provider:
                self.ui.print_error(f"No VCS provider configured for space '{space}'")
                return

            self.ui.print_info(f"🔄 Using VCS provider: {vcs_provider}")

            # Load credentials and list templates based on provider
            if vcs_provider == "azure_repos":
                self._list_azure_templates(space)
            elif vcs_provider == "github":
                self._list_github_templates(space)
            elif vcs_provider == "gitlab":
                self.ui.print_warning("GitLab integration is not yet implemented")
            else:
                self.ui.print_error(f"Unsupported VCS provider: {vcs_provider}")
        elif not show_defaults:
            # If no space and no explicit defaults flag, show help message
            self.ui.print_info("💡 Use --space to list templates from a VCS provider")
            self.ui.print_info("💡 Use --defaults to show default GitHub template repositories")

    def _list_default_templates(self) -> None:
        """List default GitHub template repositories"""
        from ....services.generate.create_template.github_template_loader import GitHubTemplateLoader
        from ....config.template_config import TemplateConfig
        
        loader = GitHubTemplateLoader()
        config = TemplateConfig()
        
        self.ui.print_info("📋 Default GitHub template repositories:")
        
        for project_type in ["terraform", "terragrunt", "terraform_module", "tofu", "cdkv2"]:
            custom_url = config.get_template_url(project_type)
            default_url = loader.DEFAULT_TEMPLATES.get(project_type)
            
            if custom_url:
                self.ui.print_info(f"  {project_type}: {custom_url} (custom)")
            elif default_url:
                self.ui.print_info(f"  {project_type}: {default_url} (default)")
            else:
                self.ui.print_warning(f"  {project_type}: No template available")

    def _list_azure_templates(self, space: str) -> None:
        """List templates from Azure Repos using pattern filtering"""
        try:
            from ....utils.crypto import get_credentials_with_password
            
            # Get credentials
            credentials, _ = get_credentials_with_password(space, "vcs")
            
            if credentials.get("type") != "azure_repos":
                self.ui.print_error("Space does not have Azure Repos credentials")
                return

            pat = credentials.get("pat")
            org_name = credentials.get("organization")
            
            if not pat or not org_name:
                self.ui.print_error("Missing PAT or organization in Azure Repos credentials")
                return

            org_url = f"https://dev.azure.com/{org_name}/"
            
            self.ui.print_info("🔍 Fetching templates from Azure DevOps...")
            # Use existing pattern filtering function
            get_pattern_from_azure(
                pat=pat,
                org_url=org_url,
                action="list",
                directory="temp"
            )
            
        except Exception as e:
            self.ui.print_error(f"Failed to list Azure Repos templates: {e}")

    def _list_github_templates(self, space: str) -> None:
        """List templates from GitHub using pattern filtering"""
        try:
            from ....utils.crypto import get_credentials_with_password
            
            # Get credentials
            credentials, _ = get_credentials_with_password(space, "vcs")
            
            if credentials.get("type") != "github":
                self.ui.print_error("Space does not have GitHub credentials")
                return

            token = credentials.get("token")
            username = credentials.get("username")
            
            if not token or not username:
                self.ui.print_error("Missing token or username in GitHub credentials")
                return

            self.ui.print_info("🔍 Fetching templates from GitHub...")
            # Use existing pattern filtering function
            get_pattern_from_github(
                token=token,
                username=username,
                action="list",
                directory="temp"
            )
            
        except Exception as e:
            self.ui.print_error(f"Failed to list GitHub templates: {e}")


# Create the Click command
cli = ListTemplatesCommand.as_click_command(
    help="List available templates from VCS providers and default GitHub templates"
)(
    click.option(
        "-s",
        "--space",
        help="Space name to get VCS provider and credentials from",
        default=None,
    ),
    click.option(
        "--defaults",
        "show_defaults",
        is_flag=True,
        help="Show default GitHub template repositories",
        default=False,
    ),
)
