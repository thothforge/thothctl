import logging
import getpass
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Optional

import os

from ....common.common import create_info_project
from ....core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
from ....core.integrations.github.get_github import get_pattern_from_github
from ....services.generate.create_template.create_template import create_project
from ...project.convert.get_project_data import (
    replace_template_placeholders,
    get_project_props,
)
from ...project.convert.set_project_parameters import set_project_conf
from ....utils.crypto import load_credentials, validate_credentials
from ....core.cli_ui import CliUI


class ProjectService:
    AZURE_DEVOPS_URL: Final = "https://dev.azure.com"
    DEFAULT_CLOUD_PROVIDER: Final = "aws"
    DEFAULT_VCS_SERVICE: Final = "azure_repos"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.ui = CliUI()

    def initialize_project(
        self, project_name: str, project_type: str = "terraform", reuse=False, space: Optional[str] = None
    ) -> Optional[dict]:
        """Initialize the basic project structure"""
        self.logger.debug(f"Initializing project: {project_name}")
        create_info_project(project_name=project_name, space=space)
        self.logger.debug(f"Project {project_name} initialized successfully")

        repo_metadata = None
        if not reuse:
            repo_metadata = create_project(project_name=project_name, project_type=project_type)
        
        return repo_metadata

    def setup_project_config(
        self, 
        project_name: str, 
        space: Optional[str] = None, 
        batch_mode: bool = False, 
        project_type: str = "terraform",
        repo_metadata: Optional[dict] = None
    ) -> None:
        """Setup project configuration"""
        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            batch_mode=batch_mode
        )
        set_project_conf(
            project_name=project_name,
            project_properties=project_props,
            space=space,
            batch_mode=batch_mode,
            project_type=project_type,
            repo_metadata=repo_metadata,
        )

    def setup_version_control(
        self,
        project_name: str,
        project_path: Path,
        vcs_provider: str,
        space: Optional[str] = None,
        selected_template: Optional[dict] = None,
        **kwargs
    ) -> None:
        """
        Setup version control integration based on provider type
        
        :param project_name: Name of the project
        :param project_path: Path to the project
        :param vcs_provider: Version control system provider (azure_repos, github, gitlab)
        :param space: Space name to load credentials from
        :param selected_template: Pre-selected template information
        :param kwargs: Additional provider-specific parameters
        """
        self.ui.print_info(f"🔄 Setting up {vcs_provider.replace('_', ' ').title()} integration...")
        
        if vcs_provider == "azure_repos":
            self.setup_azure_repos(
                project_name=project_name,
                project_path=project_path,
                space=space,
                selected_template=selected_template,
                **kwargs
            )
        elif vcs_provider == "github":
            self.setup_github(
                project_name=project_name,
                project_path=project_path,
                space=space,
                selected_template=selected_template,
                **kwargs
            )
        elif vcs_provider == "gitlab":
            self.setup_gitlab(
                project_name=project_name,
                project_path=project_path,
                space=space,
                selected_template=selected_template,
                **kwargs
            )
        else:
            self.ui.print_error(f"Unsupported VCS provider: {vcs_provider}")
            raise ValueError(f"Unsupported VCS provider: {vcs_provider}")

    def setup_azure_repos(
        self,
        project_name: str,
        project_path: Path,
        az_org_name: Optional[str] = None,
        pat: Optional[str] = None,
        space: Optional[str] = None,
        selected_template: Optional[dict] = None,
    ) -> None:
        """Setup Azure Repos configuration"""
        # Try to load credentials from space if provided
        if space:
            try:
                # Use the get_credentials_with_password function to avoid multiple password prompts
                from ....utils.crypto import get_credentials_with_password
                
                try:
                    # Get credentials and password in one call
                    credentials, password = get_credentials_with_password(space, "vcs")
                    
                    # Verify it's Azure Repos credentials
                    if credentials.get("type") == "azure_repos":
                        # Use organization from credentials if not provided
                        if not az_org_name:
                            az_org_name = credentials.get("organization")
                        
                        # Use PAT from credentials if not provided
                        if not pat:
                            pat = credentials.get("pat")
                            self.logger.debug(f"Using Azure DevOps PAT from space '{space}'")
                    else:
                        self.logger.warning(f"Space '{space}' has non-Azure VCS credentials")
                except (FileNotFoundError, ValueError) as e:
                    self.logger.warning(f"Failed to load credentials from space '{space}': {e}")
            except Exception as e:
                self.logger.warning(f"Error accessing credentials: {e}")
        
        # If we still don't have a PAT, ask for it
        if not pat:
            self.ui.print_info("Azure DevOps Personal Access Token required")
            pat = getpass.getpass("Enter your Azure DevOps Personal Access Token: ")
        
        # If we still don't have an organization name, ask for it
        if not az_org_name:
            az_org_name = input("Enter Azure DevOps organization name: ")
        
        # Use selected template if provided, otherwise get template
        if selected_template:
            repo_meta = selected_template
        else:
            # Fallback to original behavior if no template was pre-selected
            org_url = f"{self.AZURE_DEVOPS_URL}/{az_org_name}/"
            repo_meta = get_pattern_from_azure(
                pat=pat,
                org_url=org_url,
                directory=project_name,
                action="reuse",
            )

        if not repo_meta:
            self.ui.print_error("Failed to get template from Azure DevOps")
            return

        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            directory=project_path,
        )

        with self._change_directory(project_path):
            replace_template_placeholders(
                directory=Path("."),
                project_properties=project_props,
                project_name=project_name,
            )

            set_project_conf(
                project_properties=project_props,
                project_name=project_name,
                directory=Path("."),
                repo_metadata=repo_meta,
                space=space,
                project_type="terraform",  # Default for VCS setup
            )

    def setup_github(
        self,
        project_name: str,
        project_path: Path,
        github_username: Optional[str] = None,
        token: Optional[str] = None,
        space: Optional[str] = None,
        selected_template: Optional[dict] = None,
    ) -> None:
        """Setup GitHub configuration"""
        # Try to load credentials from space if provided
        if space:
            try:
                # Use the get_credentials_with_password function to avoid multiple password prompts
                from ....utils.crypto import get_credentials_with_password, save_credentials
                
                try:
                    # Get credentials and password in one call
                    credentials, password = get_credentials_with_password(space, "vcs")
                    
                    # Verify it's GitHub credentials
                    if credentials.get("type") == "github":
                        # Use username from credentials if not provided
                        if not github_username:
                            github_username = credentials.get("username")
                        
                        # Use token from credentials if not provided
                        if not token:
                            token = credentials.get("token")
                            self.logger.debug(f"Using GitHub token from space '{space}'")
                    else:
                        self.logger.warning(f"Space '{space}' has non-GitHub VCS credentials")
                except (FileNotFoundError, ValueError) as e:
                    self.logger.warning(f"Failed to load credentials from space '{space}': {e}")
                    
                    # If credentials don't exist, offer to create them
                    if isinstance(e, FileNotFoundError) and "not found" in str(e):
                        self.ui.print_info(f"No GitHub credentials found for space '{space}'")
                        if self.ui.confirm("Would you like to set up GitHub credentials for this space?"):
                            # Ask for GitHub username
                            if not github_username:
                                github_username = input("Enter GitHub username or organization name: ")
                            
                            # Ask for token securely
                            self.ui.print_info("You'll need a Personal Access Token with appropriate permissions")
                            token = getpass.getpass("Enter your GitHub Personal Access Token: ")
                            
                            # Create credentials dictionary
                            credentials = {
                                "type": "github",
                                "username": github_username,
                                "token": token
                            }
                            
                            # Ask for encryption password
                            encryption_password = getpass.getpass("Enter a password to encrypt your credentials: ")
                            
                            # Save encrypted credentials
                            try:
                                save_credentials(
                                    space_name=space,
                                    credentials=credentials,
                                    credential_type="vcs",
                                    password=encryption_password
                                )
                                self.ui.print_success("🔒 GitHub credentials saved securely for future use")
                            except Exception as e:
                                self.logger.error(f"Failed to save credentials: {e}")
                                self.ui.print_error(f"Failed to save credentials: {e}")
                    
            except Exception as e:
                self.logger.warning(f"Error accessing credentials: {e}")
        
        # If we still don't have a token, ask for it
        if not token:
            self.ui.print_info("GitHub Personal Access Token required")
            token = getpass.getpass("Enter your GitHub Personal Access Token: ")
        
        # If we still don't have a username, ask for it
        if not github_username:
            github_username = input("Enter GitHub username or organization name: ")
        
        # Use selected template if provided, otherwise get template
        if selected_template:
            repo_meta = selected_template
        else:
            # Fallback to original behavior if no template was pre-selected
            repo_meta = get_pattern_from_github(
                token=token,
                username=github_username,
                directory=project_name,
                action="reuse",
            )

        if not repo_meta:
            self.ui.print_error("Failed to get template from GitHub")
            return

        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            directory=project_path,
        )

        with self._change_directory(project_path):
            replace_template_placeholders(
                directory=Path("."),
                project_properties=project_props,
                project_name=project_name,
            )

            set_project_conf(
                project_properties=project_props,
                project_name=project_name,
                directory=Path("."),
                repo_metadata=repo_meta,
                space=space,
                project_type="terraform",  # Default for VCS setup
            )

    def setup_gitlab(
        self,
        project_name: str,
        project_path: Path,
        gitlab_username: Optional[str] = None,
        token: Optional[str] = None,
        space: Optional[str] = None,
        selected_template: Optional[dict] = None,
    ) -> None:
        """Setup GitLab configuration"""
        # This is a placeholder for GitLab integration
        # Similar to GitHub and Azure Repos implementations
        self.ui.print_warning("GitLab integration is not yet implemented")
        raise NotImplementedError("GitLab integration is not yet implemented")

    @staticmethod
    @contextmanager
    def _change_directory(path: Path):
        """Safely change directory and return to original"""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)
            os.chdir(original_dir)
