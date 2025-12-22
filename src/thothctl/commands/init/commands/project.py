import getpass
from pathlib import Path
from typing import Optional, List, Any

import click
from click.shell_completion import CompletionItem

from ....core.commands import ClickCommand
from ....services.init.project.project import ProjectService
from ....core.cli_ui import CliUI
from ....common.common import get_space_vcs_provider


class ProjectInitCommand(ClickCommand):
    """Command to initialize a new project"""

    def __init__(self):
        super().__init__()
        self.project_service = ProjectService(self.logger)
        self.ui = CliUI()

    def validate(self, project_name: str, **kwargs) -> bool:
        """Validate project initialization parameters"""
        if not project_name or not project_name.strip():
            self.ui.print_error("Project name is required and cannot be empty")
            raise ValueError("Project name is required and cannot be empty")
        
        # Check if project is already registered in ThothCTL
        from ....common.common import check_info_project
        project_info = check_info_project(project_name)
        
        # Check if project directory already exists
        project_path = Path(f"./{project_name}")
        project_exists = project_path.exists()
        
        # Determine the appropriate error message based on both conditions
        if project_info and project_exists:
            # Both the directory and ThothCTL registration exist
            space_info = ""
            if project_info.get("thothcf") and project_info["thothcf"].get("space"):
                space = project_info["thothcf"]["space"]
                space_info = f" in space '{space}'"
                
            removal_cmd = f"thothctl remove project -pj {project_name}"
            
            self.ui.print_error(f"Project '{project_name}'{space_info} already exists and is managed by ThothCTL")
            raise ValueError(
                f"Project '{project_name}'{space_info} already exists and is managed by ThothCTL.\n"
                f"The project directory '{project_path}' also exists.\n"
                f"To reuse this project name, run: {removal_cmd} and remove the directory."
            )
        elif project_info:
            # Only ThothCTL registration exists
            space_info = ""
            if project_info.get("thothcf") and project_info["thothcf"].get("space"):
                space = project_info["thothcf"]["space"]
                space_info = f" in space '{space}'"
                
            removal_cmd = f"thothctl remove project -pj {project_name}"
            
            self.ui.print_error(f"Project '{project_name}'{space_info} is already registered in ThothCTL")
            raise ValueError(
                f"Project '{project_name}'{space_info} is already registered in ThothCTL.\n"
                f"To reuse this project name, run: {removal_cmd}"
            )
        elif project_exists:
            # Only directory exists
            self.ui.print_error(f"Project directory '{project_path}' already exists")
            raise ValueError(
                f"Project directory '{project_path}' already exists.\n"
                f"Please choose a different name or remove the existing directory."
            )
            
        return True

    def _execute(
        self,
        project_name: str,
        setup_conf: bool,
        version_control_systems_service: str = ProjectService.DEFAULT_VCS_SERVICE,
        az_org_name: Optional[str] = None,
        github_username: Optional[str] = None,
        reuse: bool = False,
        project_type: str = "terraform",
        space: Optional[str] = None,
        batch: bool = False,
        **kwargs,
    ) -> None:
        """Execute project initialization"""
        project_name = project_name.strip()
        project_path = Path(f"./{project_name}")

        self.ui.print_info(f"🚀 Initializing project: {project_name}")
        
        # If space is provided, show info and get VCS provider
        vcs_provider = version_control_systems_service
        vcs_params = {}
        if space:
            self.ui.print_info(f"🌌 Using space: {space}")
            space_vcs = get_space_vcs_provider(space)
            if space_vcs:
                vcs_provider = space_vcs
                self.ui.print_info(f"🔄 Using VCS provider from space: {vcs_provider}")
        
        # Pass the appropriate parameters based on VCS provider
        if vcs_provider == "azure_repos" and az_org_name:
            vcs_params["az_org_name"] = az_org_name
        elif vcs_provider == "github" and github_username:
            vcs_params["github_username"] = github_username
        
        # If reuse is enabled, first let user select template before creating project
        if reuse:
            if space:
                self.ui.print_info(f"🔍 Discovering templates from space: {space}")
                space_vcs = get_space_vcs_provider(space)
                if space_vcs:
                    vcs_provider = space_vcs
                    self.ui.print_info(f"🔄 Using VCS provider from space: {vcs_provider}")
            
            # Get template selection before creating project
            selected_template = self._select_template(space, vcs_provider, **vcs_params)
            if not selected_template:
                self.ui.print_error("No template selected. Project creation cancelled.")
                return
        
        # Initialize project
        with self.ui.status_spinner("🏗️ Creating project structure..."):
            repo_metadata = self.project_service.initialize_project(project_name, project_type=project_type, reuse=reuse, space=space)

        # Setup configuration if requested - NO SPINNER for interactive prompts
        if setup_conf:
            self.ui.print_info("📝 Setting up project configuration...")
            self.project_service.setup_project_config(
                project_name, 
                space=space, 
                batch_mode=batch, 
                project_type=project_type,
                repo_metadata=repo_metadata
            )

        # Setup version control if reuse is enabled
        if reuse and selected_template:
            self.ui.print_info("🔄 Setting up version control with selected template...")
            self.project_service.setup_version_control(
                project_name=project_name,
                project_path=project_path,
                vcs_provider=vcs_provider,
                space=space,
                selected_template=selected_template,
                **vcs_params
            )
        
        self.ui.print_success(f"✨ Project '{project_name}' initialized successfully!")

    def _select_template(self, space: str, vcs_provider: str, **vcs_params) -> Optional[dict]:
        """Select template before project creation"""
        try:
            if vcs_provider == "azure_repos":
                return self._select_azure_template(space, **vcs_params)
            elif vcs_provider == "github":
                return self._select_github_template(space, **vcs_params)
            else:
                self.ui.print_error(f"Template selection not supported for {vcs_provider}")
                return None
        except Exception as e:
            self.ui.print_error(f"Failed to select template: {e}")
            return None

    def _select_azure_template(self, space: str, **kwargs) -> Optional[dict]:
        """Select template from Azure Repos"""
        try:
            from ....utils.crypto import get_credentials_with_password, save_credentials
            from ....core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
            
            pat = None
            org_name = None
            
            # Try to get credentials from space first
            try:
                credentials, _ = get_credentials_with_password(space, "vcs")
                
                if credentials.get("type") == "azure_repos":
                    pat = credentials.get("pat")
                    org_name = credentials.get("organization")
                    self.ui.print_info(f"✅ Using Azure DevOps credentials from space '{space}'")
                else:
                    self.ui.print_warning(f"Space '{space}' has non-Azure Repos VCS credentials")
                    
            except FileNotFoundError:
                self.ui.print_info(f"No Azure DevOps credentials found for space '{space}'")
                
                # Ask user if they want to set up credentials
                if self.ui.confirm("Would you like to set up Azure DevOps credentials for this space?"):
                    org_name = input("Enter Azure DevOps organization name: ")
                    self.ui.print_info("You'll need a Personal Access Token with appropriate permissions")
                    pat = getpass.getpass("Enter your Azure DevOps Personal Access Token: ")
                    
                    # Create and save credentials
                    credentials = {
                        "type": "azure_repos",
                        "organization": org_name,
                        "pat": pat
                    }
                    
                    encryption_password = getpass.getpass("Enter a password to encrypt your credentials: ")
                    
                    try:
                        save_credentials(
                            space_name=space,
                            credentials=credentials,
                            credential_type="vcs",
                            password=encryption_password
                        )
                        self.ui.print_success("🔒 Azure DevOps credentials saved securely for future use")
                    except Exception as e:
                        self.ui.print_error(f"Failed to save credentials: {e}")
                        # Continue without saving, use credentials for this session only
                else:
                    self.ui.print_error("Azure DevOps credentials are required for template access")
                    return None
            
            if not pat or not org_name:
                self.ui.print_error("Missing PAT or organization name")
                return None

            org_url = f"https://dev.azure.com/{org_name}/"
            
            # Try to list templates
            self.ui.print_info("🔍 Fetching available templates...")
            template_info = get_pattern_from_azure(
                pat=pat,
                org_url=org_url,
                directory="temp",  # Dummy directory for listing
                action="list",
            )
            
            return template_info
            
        except Exception as e:
            self.ui.print_error(f"Failed to select Azure template: {e}")
            return None

    def _select_github_template(self, space: str, **kwargs) -> Optional[dict]:
        """Select template from GitHub"""
        try:
            from ....utils.crypto import get_credentials_with_password, save_credentials
            from ....core.integrations.github.get_github import get_pattern_from_github
            
            token = None
            username = None
            
            # Try to get credentials from space first
            try:
                credentials, _ = get_credentials_with_password(space, "vcs")
                
                if credentials.get("type") == "github":
                    token = credentials.get("token")
                    username = credentials.get("username")
                    self.ui.print_info(f"✅ Using GitHub credentials from space '{space}'")
                else:
                    self.ui.print_warning(f"Space '{space}' has non-GitHub VCS credentials")
                    
            except FileNotFoundError:
                self.ui.print_info(f"No GitHub credentials found for space '{space}'")
                
                # Ask user if they want to set up credentials
                if self.ui.confirm("Would you like to set up GitHub credentials for this space?"):
                    username = input("Enter GitHub username or organization name: ")
                    self.ui.print_info("You'll need a Personal Access Token with appropriate permissions")
                    token = getpass.getpass("Enter your GitHub Personal Access Token: ")
                    
                    # Create and save credentials
                    credentials = {
                        "type": "github",
                        "username": username,
                        "token": token
                    }
                    
                    encryption_password = getpass.getpass("Enter a password to encrypt your credentials: ")
                    
                    try:
                        save_credentials(
                            space_name=space,
                            credentials=credentials,
                            credential_type="vcs",
                            password=encryption_password
                        )
                        self.ui.print_success("🔒 GitHub credentials saved securely for future use")
                    except Exception as e:
                        self.ui.print_error(f"Failed to save credentials: {e}")
                        # Continue without saving, use credentials for this session only
                else:
                    # User declined to set up credentials, try with public access
                    self.ui.print_info("Attempting to access public repositories...")
                    username = input("Enter GitHub username or organization name for public repositories: ")
                    # token remains None for public access
            
            if not username:
                self.ui.print_error("GitHub username is required")
                return None

            # Try to list templates
            self.ui.print_info("🔍 Fetching available templates...")
            template_info = get_pattern_from_github(
                token=token,  # Can be None for public repos
                username=username,
                directory="temp",  # Dummy directory for listing
                action="list",
            )
            
            return template_info
            
        except Exception as e:
            self.ui.print_error(f"Failed to select GitHub template: {e}")
            return None

    def get_completions(self, ctx: click.Context, args: List[str], incomplete: str) -> List[click.shell_completion.CompletionItem]:
        """
        Provide context-aware autocompletion
        """
        # Define subcommands and their options
        completions = {
            'create': {
                '--project-name': ['basic', 'advanced', 'custom'],
                '--project-type': ['terraform', 'tofu', 'cdkv2', 'terraform_module', 'terragrunt', 'custom'],
                '--region': ['us-east-1', 'us-west-2', 'eu-west-1']
            },
            'delete': {
                '--force': ['true', 'false'],
                '--backup': ['true', 'false']
            }
        }

        # If no args provided, suggest subcommands
        if not args:
            return [
                CompletionItem(cmd, help=f"Command to {cmd} project")
                for cmd in completions.keys()
                if cmd.startswith(incomplete)
            ]

        # Get current subcommand
        subcommand = next((arg for arg in args if arg in completions), None)
        if not subcommand:
            return []

        # If incomplete starts with '-', suggest options for current subcommand
        if incomplete.startswith('-'):
            return [
                CompletionItem(opt, help=f"Option for {opt.lstrip('-')}")
                for opt in completions[subcommand].keys()
                if opt.startswith(incomplete)
            ]

        # If we have a current option, suggest its values
        current_option = next((arg for arg in reversed(args)
                               if arg in completions[subcommand]), None)
        if current_option:
            values = completions[subcommand][current_option]
            return [
                CompletionItem(val, help=f"Value for {current_option}")
                for val in values
                if val.startswith(incomplete)
            ]

        return []


# Create the Click command
cli = ProjectInitCommand.as_click_command(help="Initialize a new project")(
    click.option(
        "-p",
        "--project-name",
        prompt="Project name",
        help="Name of the project",
        required=True,
    ),
    click.option(
        "-pt",
        "--project-type",
        default="terraform-terragrunt",
        type=click.Choice(
            [
                "terraform",
                "terraform-terragrunt",
                "tofu",
                "cdkv2",
                "terraform_module",
                "terragrunt",
                "custom",
            ],
            case_sensitive=True,
        ),
        help="Type of project to create",
    ),
    click.option(
        "-sc",
        "--setup-conf",
        is_flag=True,
        default=True,
        help="Setup project configuration",
    ),
    click.option(
        "-vcss",
        "--version-control-systems-service",
        default="azure_repos",
        type=click.Choice(["azure_repos", "github", "gitlab"], case_sensitive=True),
        help="The Version Control System Service for you IDP",
    ),
    click.option(
        "-reuse",
        "--reuse",
        help="Reuse templates, pattern, PoC, projects and more from your IDP catalog",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-az-org", 
        "--az-org-name", 
        help="Azure organization name (for Azure Repos)", 
        default=None
    ),
    click.option(
        "-gh-user", 
        "--github-username", 
        help="GitHub username or organization (for GitHub)", 
        default=None
    ),
    click.option(
        "-s",
        "--space",
        help="Space name for the project (used for loading credentials and configurations)",
        default=None,
    ),
    click.option(
        "--batch",
        is_flag=True,
        help="Run in batch mode with minimal prompts and use default values where possible",
        default=False,
    ),
)
