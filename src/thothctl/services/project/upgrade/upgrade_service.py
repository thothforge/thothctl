"""Project upgrade service implementation."""
import hashlib
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set
import subprocess
import toml
from datetime import datetime


logger = logging.getLogger(__name__)


class ProjectUpgradeService:
    """Service for upgrading project scaffold files from remote templates."""

    def __init__(self):
        """Initialize the upgrade service."""
        pass

    def upgrade_project(
        self,
        project_path: Path,
        dry_run: bool = False,
        force: bool = False,
        interactive: bool = False
    ) -> Dict:
        """
        Upgrade project scaffold files from remote template.
        
        Args:
            project_path: Path to the project directory
            dry_run: If True, only check what would be updated
            force: If True, overwrite files even if they have local modifications
            interactive: If True, allow selective file import
            
        Returns:
            Dictionary with upgrade results
        """
        try:
            # Read project metadata
            metadata = self._read_project_metadata(project_path)
            if not metadata:
                return {"success": False, "error": "No project metadata found in .thothcf.toml"}

            # Get remote template info
            template_url = metadata.get("template_url")
            if not template_url:
                return {"success": False, "error": "No template_url found in project metadata"}

            # Clone/update remote template
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                remote_path = self._clone_template(template_url, temp_path)
                
                # Compare and identify changes
                changes = self._identify_changes(project_path, remote_path, force)
                
                if dry_run:
                    return {"success": True, "changes": changes}
                
                if interactive:
                    # Handle interactive mode - include conflicts by setting force=True for identification
                    changes = self._identify_changes(project_path, remote_path, True)
                    selected_files = self._interactive_file_selection(changes)
                    if selected_files:
                        self._apply_selected_changes(project_path, remote_path, selected_files)
                        changes["selected_files"] = selected_files
                    return {"success": True, "changes": changes}
                
                # Apply changes
                self._apply_changes(project_path, remote_path, changes)
                
                # Update metadata
                self._update_project_metadata(project_path, remote_path)
                
                return {"success": True, "changes": changes}

        except Exception as e:
            logger.exception("Project upgrade failed")
            return {"success": False, "error": str(e)}

    def _read_project_metadata(self, project_path: Path) -> Optional[Dict]:
        """Read project metadata from .thothcf.toml."""
        toml_path = project_path / ".thothcf.toml"
        
        if not toml_path.exists():
            return None
            
        try:
            with open(toml_path, 'r') as f:
                config = toml.load(f)
            return config.get("origin_metadata", {})
        except Exception as e:
            logger.error(f"Failed to read project metadata: {e}")
            return None

    def _clone_template(self, template_url: str, temp_path: Path) -> Path:
        """Clone the remote template to a temporary directory."""
        clone_path = temp_path / "template"
        
        try:
            import git
            git.Repo.clone_from(template_url, clone_path, depth=1)
            return clone_path
        except Exception as e:
            raise Exception(f"Failed to clone template: {str(e)}")

    def _identify_changes(
        self, 
        project_path: Path, 
        remote_path: Path, 
        force: bool
    ) -> Dict[str, List[str]]:
        """Identify what files need to be updated."""
        changes = {
            "new_files": [],
            "updated_files": [],
            "conflicts": [],
            "skipped": [],
            "commit_info": {}
        }
        
        # Get commit information for comparison
        local_metadata = self._read_project_metadata(project_path)
        remote_commit_info = self._get_latest_commit_info(remote_path)
        
        local_commit_hash = local_metadata.get("commit_hash", "") if local_metadata else ""
        remote_commit_hash = remote_commit_info.get("hash", "")
        
        changes["commit_info"] = {
            "local_hash": local_commit_hash,
            "remote_hash": remote_commit_hash,
            "needs_update": local_commit_hash != remote_commit_hash
        }
        
        # If commits are the same, no need to check files
        if local_commit_hash == remote_commit_hash and local_commit_hash:
            return changes
        
        # Focus on .kiro folder and other scaffold files
        target_files = self._get_target_files(remote_path)
        
        for rel_path in target_files:
            remote_file = remote_path / rel_path
            local_file = project_path / rel_path
            
            if not local_file.exists():
                changes["new_files"].append(str(rel_path))
            elif self._files_differ(local_file, remote_file):
                if force or not self._has_local_modifications(local_file):
                    changes["updated_files"].append(str(rel_path))
                else:
                    changes["conflicts"].append(str(rel_path))
        
        return changes

    def _get_target_files(self, remote_path: Path) -> Set[str]:
        """Get list of target files to sync from remote template."""
        target_files = set()
        
        # Get all files from remote template, excluding git and common ignore patterns
        ignore_patterns = {'.git', '__pycache__', '.pytest_cache', '.venv', 'node_modules', '.DS_Store'}
        ignore_extensions = {'.pyc', '.pyo', '.log'}
        
        # Exclude specific project files that should not be compared
        exclude_files = {
            '.thothcf.toml',
            'common/common.hcl',
            'common/common.tfvars',
            'docs/catalog/catalog-info.yaml'
        }
        
        for file_path in remote_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(remote_path)
                rel_path_str = str(rel_path)
                
                # Skip ignored patterns
                if any(pattern in rel_path.parts for pattern in ignore_patterns):
                    continue
                if any(rel_path_str.endswith(ext) for ext in ignore_extensions):
                    continue
                if rel_path_str in exclude_files:
                    continue
                    
                target_files.add(rel_path_str)
        
        return target_files

    def _files_differ(self, local_file: Path, remote_file: Path) -> bool:
        """Check if two files differ by comparing their hashes."""
        try:
            local_hash = self._get_file_hash(local_file)
            remote_hash = self._get_file_hash(remote_file)
            return local_hash != remote_hash
        except Exception:
            return True  # Assume they differ if we can't compare

    def _get_file_hash(self, file_path: Path) -> str:
        """Get SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _has_local_modifications(self, file_path: Path) -> bool:
        """Check if file has local modifications (simplified check)."""
        # For now, assume files in .kiro don't have local modifications
        # This can be enhanced with git status checking
        return ".kiro" not in str(file_path)

    def _apply_changes(
        self, 
        project_path: Path, 
        remote_path: Path, 
        changes: Dict[str, List[str]]
    ) -> None:
        """Apply the identified changes to the project."""
        all_files = changes["new_files"] + changes["updated_files"]
        
        for rel_path in all_files:
            remote_file = remote_path / rel_path
            local_file = project_path / rel_path
            
            # Create parent directories if needed
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file from remote to local
            shutil.copy2(remote_file, local_file)
            logger.info(f"Updated: {rel_path}")

    def _update_project_metadata(self, project_path: Path, remote_path: Path) -> None:
        """Update project metadata with latest commit info."""
        toml_path = project_path / ".thothcf.toml"
        
        if not toml_path.exists():
            return
            
        try:
            # Get latest commit info
            commit_info = self._get_latest_commit_info(remote_path)
            
            # Read current config
            with open(toml_path, 'r') as f:
                config = toml.load(f)
            
            # Update origin_metadata
            if "origin_metadata" in config:
                config["origin_metadata"]["commit_hash"] = commit_info["hash"]
                config["origin_metadata"]["commit_date"] = commit_info["date"]
                config["origin_metadata"]["updated_at"] = datetime.now().isoformat()
            
            # Write back to file
            with open(toml_path, 'w') as f:
                toml.dump(config, f)
                
        except Exception as e:
            logger.warning(f"Failed to update project metadata: {e}")

    def _get_latest_commit_info(self, repo_path: Path) -> Dict[str, str]:
        """Get latest commit information from the repository."""
        try:
            import git
            repo = git.Repo(repo_path)
            latest_commit = repo.head.commit
            
            return {
                "hash": latest_commit.hexsha,
                "date": latest_commit.committed_datetime.isoformat()
            }
        except Exception:
            return {
                "hash": "unknown",
                "date": datetime.now().isoformat()
            }

    def _interactive_file_selection(self, changes: Dict[str, List[str]]) -> List[str]:
        """Allow user to select which files to import interactively."""
        import inquirer
        
        available_files = []
        
        # Add new files
        for file_path in changes.get("new_files", []):
            available_files.append(f"📄 NEW: {file_path}")
        
        # Add updated files
        for file_path in changes.get("updated_files", []):
            available_files.append(f"🔄 UPDATE: {file_path}")
        
        if not available_files:
            print("ℹ️  No files available for import")
            return []
        
        # Interactive selection
        questions = [
            inquirer.Checkbox(
                'files',
                message="Select files to import (use SPACE to select, ENTER to confirm)",
                choices=available_files,
            ),
        ]
        
        try:
            answers = inquirer.prompt(questions)
            if not answers or not answers['files']:
                return []
            
            # Extract actual file paths from the formatted choices
            selected_files = []
            for choice in answers['files']:
                if choice.startswith("📄 NEW: "):
                    selected_files.append(choice[7:])  # Remove "📄 NEW: "
                elif choice.startswith("🔄 UPDATE: "):
                    selected_files.append(choice[10:])  # Remove "🔄 UPDATE: "
                elif choice.startswith("⚠️  CONFLICT: "):
                    selected_files.append(choice[14:])  # Remove "⚠️  CONFLICT: "
            
            return selected_files
            
        except KeyboardInterrupt:
            print("\n❌ Selection cancelled")
            return []

    def _apply_selected_changes(
        self, 
        project_path: Path, 
        remote_path: Path, 
        selected_files: List[str]
    ) -> None:
        """Apply only the selected file changes to the project."""
        for rel_path in selected_files:
            remote_file = remote_path / rel_path
            local_file = project_path / rel_path
            
            # Create parent directories if needed
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file from remote to local
            shutil.copy2(remote_file, local_file)
            logger.info(f"Imported: {rel_path}")

    def _interactive_file_selection(self, changes: Dict[str, List[str]]) -> List[str]:
        """Allow user to select which files to import interactively."""
        import inquirer
        
        available_files = []
        
        # Add new files
        for file_path in changes.get("new_files", []):
            available_files.append(f"📄 NEW: {file_path}")
        
        # Add updated files
        for file_path in changes.get("updated_files", []):
            available_files.append(f"🔄 UPDATE: {file_path}")
        
        if not available_files:
            print("ℹ️  No files available for import")
            return []
        
        # Interactive selection
        questions = [
            inquirer.Checkbox(
                'files',
                message="Select files to import (use SPACE to select, ENTER to confirm)",
                choices=available_files,
            ),
        ]
        
        try:
            answers = inquirer.prompt(questions)
            if not answers or not answers['files']:
                return []
            
            # Extract actual file paths from the formatted choices
            selected_files = []
            for choice in answers['files']:
                if choice.startswith("📄 NEW: "):
                    selected_files.append(choice[7:])  # Remove "📄 NEW: "
                elif choice.startswith("🔄 UPDATE: "):
                    selected_files.append(choice[10:])  # Remove "🔄 UPDATE: "
            
            return selected_files
            
        except KeyboardInterrupt:
            print("\n❌ Selection cancelled")
            return []

    def _apply_selected_changes(
        self, 
        project_path: Path, 
        remote_path: Path, 
        selected_files: List[str]
    ) -> None:
        """Apply only the selected file changes to the project."""
        for rel_path in selected_files:
            remote_file = remote_path / rel_path
            local_file = project_path / rel_path
            
            # Create parent directories if needed
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file from remote to local
            shutil.copy2(remote_file, local_file)
            logger.info(f"Imported: {rel_path}")
