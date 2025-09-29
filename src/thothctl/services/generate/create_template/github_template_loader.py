"""Load templates from GitHub public repositories based on project type."""
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import git
from colorama import Fore

from ....core.cli_ui import CliUI
from ....config.template_config import TemplateConfig


class GitHubTemplateLoader:
    """Load templates from GitHub public repositories."""
    
    # Default template repositories for each project type
    DEFAULT_TEMPLATES = {
        "terragrunt": "https://github.com/thothforge/terragrunt_project_scaffold.git",
        "terraform-terragrunt": "https://github.com/thothforge/terraform_terragrunt_scaffold_project.git",
        "terraform": "https://github.com/thothforge/terraform_project_scaffold.git",
        "terraform-module": "https://github.com/thothforge/terraform_module_scaffold.git",
        "tofu": "https://github.com/thothforge/tofu_project_scaffold.git",
        "cdkv2": "https://github.com/thothforge/cdkv2_project_scaffold.git",
    }
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.ui = CliUI()
        self.config = TemplateConfig()
    
    def load_template(self, project_name: str, project_type: str) -> dict:
        """
        Load template from GitHub repository based on project type.
        
        :param project_name: Name of the project
        :param project_type: Type of project (terragrunt, terraform, etc.)
        :return: Repository metadata dictionary if successful, empty dict otherwise
        """
        # First check user configuration, then fall back to defaults
        template_url = self.config.get_template_url(project_type) or self.DEFAULT_TEMPLATES.get(project_type)
        
        if not template_url:
            self.logger.warning(f"No template found for project type: {project_type}")
            return {}
        
        return self._clone_and_copy_template(template_url, project_name, project_type)
    
    def _clone_and_copy_template(self, template_url: str, project_name: str, project_type: str) -> dict:
        """
        Clone template repository and copy contents to project directory.
        
        :param template_url: GitHub repository URL
        :param project_name: Name of the project
        :param project_type: Type of project
        :return: Repository metadata dictionary
        """
        temp_dir = None
        try:
            # Create temporary directory for cloning
            temp_dir = tempfile.mkdtemp(prefix=f"thothctl_template_{project_type}_")
            self.logger.debug(f"Cloning template from {template_url} to {temp_dir}")
            
            # Clone the repository
            self.ui.print_info(f"📥 Loading {project_type} template from GitHub...")
            repo = git.Repo.clone_from(template_url, temp_dir, depth=1)
            
            # Get repository metadata
            repo_metadata = {
                "template_url": template_url,
                "template_type": project_type,
                "commit_hash": repo.head.commit.hexsha,
                "commit_date": repo.head.commit.committed_datetime.isoformat(),
                "source": "github_default_template",
                "cloned_at": self._get_current_timestamp()
            }
            
            # Copy template contents to project directory
            project_path = Path(project_name)
            self._copy_template_contents(Path(temp_dir), project_path)
            
            self.ui.print_success(f"✅ Template loaded successfully from {template_url}")
            return repo_metadata
            
        except git.exc.GitCommandError as e:
            self.logger.error(f"Failed to clone template repository: {e}")
            self.ui.print_error(f"Failed to load template from {template_url}")
            return {}
        except Exception as e:
            self.logger.error(f"Error loading template: {e}")
            self.ui.print_error(f"Error loading template: {e}")
            return {}
        finally:
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _copy_template_contents(self, source_dir: Path, target_dir: Path) -> None:
        """
        Copy template contents excluding .git directory.
        
        :param source_dir: Source template directory
        :param target_dir: Target project directory
        """
        for item in source_dir.iterdir():
            if item.name == '.git':
                continue
                
            target_item = target_dir / item.name
            
            if item.is_dir():
                shutil.copytree(item, target_item, dirs_exist_ok=True)
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_item)
    
    def is_template_available(self, project_type: str) -> bool:
        """
        Check if template is available for the given project type.
        
        :param project_type: Type of project
        :return: True if template is available, False otherwise
        """
        # Check both user config and defaults
        return (self.config.get_template_url(project_type) is not None or 
                project_type in self.DEFAULT_TEMPLATES)
