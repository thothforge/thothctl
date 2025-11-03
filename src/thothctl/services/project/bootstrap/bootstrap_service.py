"""Project bootstrap service implementation."""
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import toml


logger = logging.getLogger(__name__)


class ProjectBootstrapService:
    """Service for bootstrapping existing projects with ThothCTL support."""

    def __init__(self):
        """Initialize the bootstrap service."""
        self.default_templates = {
            "terraform": "https://github.com/thothforge/terraform_project_scaffold.git",
            "terragrunt": "https://github.com/thothforge/terragrunt_project_scaffold.git",
            "terraform-terragrunt": "https://github.com/thothforge/terragrunt_project_scaffold.git",
            "tofu": "https://github.com/thothforge/terraform_project_scaffold.git",
            "terraform_module": "https://github.com/thothforge/terraform_module_scaffold.git",
        }

    def bootstrap_project(
        self,
        project_path: Path,
        project_type: str = "auto",
        template_url: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False
    ) -> Dict:
        """
        Bootstrap project with ThothCTL support.
        
        Args:
            project_path: Path to the project directory
            project_type: Type of project or 'auto' for detection
            template_url: Custom template URL
            force: Force update existing files
            dry_run: Only check what would be done
            
        Returns:
            Dictionary with bootstrap results
        """
        try:
            # Analyze project
            project_info = self._analyze_project(project_path)
            
            # Detect or use specified project type
            if project_type == "auto":
                detected_type = project_info["detected_type"]
            else:
                detected_type = project_type
            
            project_info["detected_type"] = detected_type
            
            # Get template URL
            if not template_url:
                template_url = self.default_templates.get(detected_type)
            
            # Identify changes needed
            changes = self._identify_bootstrap_changes(
                project_path, project_info, template_url, force
            )
            
            if dry_run:
                return {
                    "success": True,
                    "project_info": project_info,
                    "changes": changes
                }
            
            # Apply changes
            self._apply_bootstrap_changes(
                project_path, project_info, template_url, changes
            )
            
            return {
                "success": True,
                "project_info": project_info,
                "changes": changes
            }

        except Exception as e:
            logger.exception("Project bootstrap failed")
            return {"success": False, "error": str(e)}

    def _analyze_project(self, project_path: Path) -> Dict:
        """Analyze existing project structure."""
        info = {
            "has_config": False,
            "detected_type": "terraform",
            "existing_files": set(),
            "project_name": project_path.name
        }
        
        # Check for .thothcf.toml
        config_path = project_path / ".thothcf.toml"
        info["has_config"] = config_path.exists()
        
        # Detect project type
        info["detected_type"] = self._detect_project_type(project_path)
        
        # Scan existing files
        for file_path in project_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(project_path)
                info["existing_files"].add(str(rel_path))
        
        return info

    def _detect_project_type(self, project_path: Path) -> str:
        """Detect project type based on files present."""
        # Check for terragrunt
        if list(project_path.rglob("terragrunt.hcl")):
            # Check if also has terraform files
            if list(project_path.rglob("*.tf")):
                return "terraform-terragrunt"
            return "terragrunt"
        
        # Check for terraform module
        version_files = list(project_path.glob("version*.tf"))
        if version_files and not list(project_path.rglob("*/terragrunt.hcl")):
            return "terraform_module"
        
        # Check for CDK
        if (project_path / "cdk.json").exists():
            return "cdkv2"
        
        # Default to terraform
        return "terraform"

    def _identify_bootstrap_changes(
        self,
        project_path: Path,
        project_info: Dict,
        template_url: Optional[str],
        force: bool
    ) -> Dict[str, List[str]]:
        """Identify what changes need to be made."""
        changes = {
            "config_action": None,
            "new_files": [],
            "updated_files": [],
            "skipped": []
        }
        
        # Check config file
        if not project_info["has_config"]:
            changes["config_action"] = "create"
        else:
            # Check if metadata needs to be added
            if self._needs_metadata_update(project_path):
                changes["config_action"] = "update"
        
        # Check scaffold files if template URL available
        if template_url:
            scaffold_changes = self._check_scaffold_files(
                project_path, template_url, project_info["existing_files"], force
            )
            changes.update(scaffold_changes)
        
        return changes

    def _needs_metadata_update(self, project_path: Path) -> bool:
        """Check if .thothcf.toml needs metadata update."""
        config_path = project_path / ".thothcf.toml"
        
        try:
            with open(config_path, 'r') as f:
                config = toml.load(f)
            
            # Check if origin_metadata exists
            return "origin_metadata" not in config
        except Exception:
            return True

    def _check_scaffold_files(
        self,
        project_path: Path,
        template_url: str,
        existing_files: Set[str],
        force: bool
    ) -> Dict[str, List[str]]:
        """Check what scaffold files need to be added/updated."""
        changes = {
            "new_files": [],
            "updated_files": [],
            "skipped": []
        }
        
        # Get actual files from template
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_path = Path(temp_dir) / "template"
                subprocess.run([
                    "git", "clone", "--depth", "1", template_url, str(clone_path)
                ], check=True, capture_output=True, text=True)
                
                # Find all .amazonq files in template
                amazonq_files = []
                amazonq_dir = clone_path / ".amazonq"
                if amazonq_dir.exists():
                    for file_path in amazonq_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(clone_path)
                            amazonq_files.append(str(rel_path))
                
                # Check other common scaffold files
                common_files = [".gitignore", "README.md", ".pre-commit-config.yaml"]
                
                # Process all files
                all_target_files = amazonq_files + common_files
                
                for file_path in all_target_files:
                    if file_path not in existing_files:
                        changes["new_files"].append(file_path)
                    elif force:
                        changes["updated_files"].append(file_path)
                    else:
                        changes["skipped"].append(file_path)
                        
        except subprocess.CalledProcessError:
            # Fallback to basic file list if clone fails
            basic_files = [
                ".amazonq/project.json",
                ".amazonq/chat_history.json", 
                ".amazonq/workspace_state.json",
                ".gitignore",
                "README.md",
                ".pre-commit-config.yaml"
            ]
            
            for file_path in basic_files:
                if file_path not in existing_files:
                    changes["new_files"].append(file_path)
                elif force:
                    changes["updated_files"].append(file_path)
                else:
                    changes["skipped"].append(file_path)
        
        return changes

    def _apply_bootstrap_changes(
        self,
        project_path: Path,
        project_info: Dict,
        template_url: Optional[str],
        changes: Dict
    ) -> None:
        """Apply the bootstrap changes."""
        created_files = []
        
        # Handle config file
        if changes.get("config_action"):
            self._handle_config_file(project_path, project_info, template_url, changes["config_action"])
            if changes["config_action"] == "create":
                created_files.append(".thothcf.toml")
        
        # Handle scaffold files
        if template_url and (changes.get("new_files") or changes.get("updated_files")):
            new_files = changes.get("new_files", [])
            updated_files = changes.get("updated_files", [])
            self._handle_scaffold_files(project_path, template_url, changes)
            created_files.extend(new_files)
        
        # Add new files to git if repository exists
        if created_files and self._is_git_repo(project_path):
            self._add_files_to_git(project_path, created_files)

    def _is_git_repo(self, project_path: Path) -> bool:
        """Check if the project is a git repository."""
        return (project_path / ".git").exists()

    def _add_files_to_git(self, project_path: Path, files: List[str]) -> None:
        """Add new files to git staging area."""
        try:
            for file_path in files:
                full_path = project_path / file_path
                if full_path.exists():
                    subprocess.run([
                        "git", "-C", str(project_path), "add", file_path
                    ], check=True, capture_output=True, text=True)
                    logger.info(f"Added to git: {file_path}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to add files to git: {e}")
            # Don't fail the bootstrap if git add fails

    def _handle_config_file(
        self,
        project_path: Path,
        project_info: Dict,
        template_url: Optional[str],
        action: str
    ) -> None:
        """Create or update .thothcf.toml file."""
        config_path = project_path / ".thothcf.toml"
        
        if action == "create":
            # Create new config
            config = {
                "thothcf": {
                    "version": "1.0.0",
                    "project_id": project_info["project_name"],
                    "project_type": project_info["detected_type"]
                }
            }
            
            if template_url:
                config["origin_metadata"] = self._create_metadata(template_url)
            
            with open(config_path, 'w') as f:
                toml.dump(config, f)
                
        elif action == "update":
            # Update existing config
            try:
                with open(config_path, 'r') as f:
                    config = toml.load(f)
                
                # Add missing metadata
                if template_url and "origin_metadata" not in config:
                    config["origin_metadata"] = self._create_metadata(template_url)
                
                # Ensure thothcf section has required fields
                if "thothcf" not in config:
                    config["thothcf"] = {}
                
                thothcf = config["thothcf"]
                if "version" not in thothcf:
                    thothcf["version"] = "1.0.0"
                if "project_id" not in thothcf:
                    thothcf["project_id"] = project_info["project_name"]
                if "project_type" not in thothcf:
                    thothcf["project_type"] = project_info["detected_type"]
                
                with open(config_path, 'w') as f:
                    toml.dump(config, f)
                    
            except Exception as e:
                logger.error(f"Failed to update config: {e}")

    def _create_metadata(self, template_url: str) -> Dict:
        """Create origin metadata for template."""
        return {
            "template_url": template_url,
            "template_type": "scaffold",
            "commit_hash": "unknown",
            "commit_date": datetime.now().isoformat(),
            "source": "bootstrap",
            "cloned_at": datetime.now().isoformat()
        }

    def _handle_scaffold_files(
        self,
        project_path: Path,
        template_url: str,
        changes: Dict
    ) -> None:
        """Download and apply scaffold files from template."""
        all_files = changes.get("new_files", []) + changes.get("updated_files", [])
        
        if not all_files:
            return
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone template
                clone_path = Path(temp_dir) / "template"
                subprocess.run([
                    "git", "clone", "--depth", "1", template_url, str(clone_path)
                ], check=True, capture_output=True, text=True)
                
                # Copy all files from template
                for rel_path in all_files:
                    source_file = clone_path / rel_path
                    target_file = project_path / rel_path
                    
                    if source_file.exists():
                        # Create parent directories
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        # For .amazonq files, merge with existing if they exist
                        if ".amazonq" in rel_path and target_file.exists():
                            self._merge_amazonq_file(source_file, target_file, rel_path)
                        else:
                            # Copy file directly
                            shutil.copy2(source_file, target_file)
                        
                        logger.info(f"Created/Updated: {rel_path}")
                    else:
                        # If file doesn't exist in template, create basic version
                        if ".amazonq" in rel_path:
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            self._create_amazonq_file(target_file, rel_path)
                            logger.info(f"Created basic: {rel_path}")
                        
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to clone template: {e}")
            # Fallback: create basic files only if template clone completely fails
            self._create_basic_files(project_path, all_files)

    def _merge_amazonq_file(self, source_file: Path, target_file: Path, rel_path: str) -> None:
        """Merge Amazon Q files from template with existing files."""
        try:
            # Read existing file
            with open(target_file, 'r') as f:
                existing_content = json.load(f)
            
            # Read template file
            with open(source_file, 'r') as f:
                template_content = json.load(f)
            
            # Merge based on file type
            if "project.json" in rel_path:
                # Update project.json but keep existing name if set
                merged = template_content.copy()
                if existing_content.get("name"):
                    merged["name"] = existing_content["name"]
                else:
                    merged["name"] = target_file.parent.parent.name
                
            elif "chat_history.json" in rel_path:
                # Keep existing conversations, update structure from template
                merged = template_content.copy()
                if "conversations" in existing_content:
                    merged["conversations"] = existing_content["conversations"]
                
            elif "workspace_state.json" in rel_path:
                # Merge workspace state, keeping existing settings
                merged = template_content.copy()
                if "workspace" in existing_content:
                    merged["workspace"].update(existing_content["workspace"])
                
            else:
                # For other files, use template as base
                merged = template_content.copy()
            
            # Write merged content
            with open(target_file, 'w') as f:
                json.dump(merged, f, indent=2)
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to merge {rel_path}: {e}, using template version")
            # If merge fails, just copy template file
            shutil.copy2(source_file, target_file)

    def _create_amazonq_file(self, file_path: Path, rel_path: str) -> None:
        """Create basic Amazon Q configuration files."""
        project_name = file_path.parent.parent.name
        
        if "project.json" in rel_path:
            content = {
                "name": project_name,
                "type": "infrastructure",
                "framework": "terraform",
                "created_at": datetime.now().isoformat()
            }
        elif "chat_history.json" in rel_path:
            content = {
                "conversations": [],
                "last_updated": datetime.now().isoformat()
            }
        elif "workspace_state.json" in rel_path:
            content = {
                "workspace": {
                    "root": str(file_path.parent.parent),
                    "initialized": True,
                    "last_sync": datetime.now().isoformat()
                }
            }
        else:
            content = {}
        
        with open(file_path, 'w') as f:
            json.dump(content, f, indent=2)

    def _create_basic_amazonq_files(self, project_path: Path, file_list: List[str]) -> None:
        """Create basic Amazon Q files when template clone fails."""
        amazonq_files = [f for f in file_list if ".amazonq" in f]
        
        for rel_path in amazonq_files:
            file_path = project_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._create_amazonq_file(file_path, rel_path)
            logger.info(f"Created: {rel_path}")

    def _create_basic_files(self, project_path: Path, file_list: List[str]) -> None:
        """Create basic versions of files when template clone fails completely."""
        for rel_path in file_list:
            file_path = project_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if ".amazonq" in rel_path:
                # Create basic Amazon Q files as fallback
                self._create_amazonq_file(file_path, rel_path)
            elif rel_path == ".gitignore":
                content = """# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl

# Terragrunt
.terragrunt-cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
"""
            elif rel_path == "README.md":
                content = f"""# {project_path.name}

This project has been bootstrapped with ThothCTL support.

## Getting Started

1. Configure your infrastructure
2. Run `thothctl inventory iac` to analyze your setup
3. Use `thothctl project upgrade` to keep scaffold files updated

## ThothCTL Integration

This project includes:
- `.thothcf.toml` - Project configuration and metadata
- `.amazonq/` - Amazon Q integration files
- Standard scaffold files for best practices
"""
            elif rel_path == ".pre-commit-config.yaml":
                content = """repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
"""
            else:
                content = f"# {rel_path}\n# Created by ThothCTL bootstrap\n"
            
            if not ".amazonq" in rel_path:
                with open(file_path, 'w') as f:
                    f.write(content)
            
            logger.info(f"Created fallback: {rel_path}")
