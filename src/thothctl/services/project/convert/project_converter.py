import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from abc import ABC, abstractmethod
from colorama import Fore

from ....common.common import load_iac_conf
from ..create_terramate.manage_terramate_stacks import TerramateConfig
from .get_project_data import (
    check_project_properties,
    get_project_props,
    replace_template_placeholders,
)
from .set_project_parameters import set_project_conf


@dataclass
class ProjectConversionConfig:
    """Configuration for project conversion."""

    code_directory: Path
    debug: bool = False
    branch_name: str = "main"
    project_type: Optional[str] = None
    make_project: bool = False
    make_template: bool = False
    make_terramate: bool = False


class ProjectConverter(ABC):
    """Abstract base class for project converters."""

    @abstractmethod
    def convert(self) -> None:
        """Execute the conversion process."""
        pass


class TerramateConverter(ProjectConverter):
    """Handles conversion to Terramate stacks."""

    def __init__(self, config: ProjectConversionConfig, stack_manager):
        self.config = config
        self.stack_manager = stack_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def convert(self) -> None:
        """Convert to Terramate stacks."""
        try:
            print(f"👷 {Fore.BLUE}Starting Terramate conversion...{Fore.RESET}")

            # Create configuration
            config = TerramateConfig(
                directory=self.config.code_directory,
                optimized=False,
                default_branch=self.config.branch_name or "main",
            )

            # Create main configuration file
            print(f"👷{Fore.BLUE}Creating main Terramate configuration...{Fore.RESET}")
            self.stack_manager.create_main_file(config=config)

            # Process directories
            print(
                f"👷{Fore.BLUE}Processing directories for Terramate stacks...{Fore.RESET}"
            )
            self.stack_manager.process_directory_recursively(config.directory)

            print(
                f"{Fore.GREEN}✅ Terramate conversion completed successfully!{Fore.RESET}"
            )

        except Exception as e:
            self.logger.error(f"Terramate conversion failed: {e}")
            print(f"{Fore.RED}❌ Terramate conversion failed: {e}{Fore.RESET}")
            raise


class ProjectTemplateConverter(ProjectConverter):
    """Handles conversion between projects and templates."""

    def __init__(self, config: ProjectConversionConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def convert(self) -> None:
        """Convert between project and template."""
        try:
            if self.config.make_project:
                # For make_project, restore backup first before getting project props
                project_name = self._get_project_name_from_current_or_restore()
                if not project_name:
                    print("❌ Could not determine project name for restoration")
                    return
                
                self._restore_project_config(project_name)
                project_props = self._get_project_properties()
                print(f"👷 {Fore.BLUE} Creating project {project_name} {Fore.RESET}")
                self._apply_project_configuration(project_props)
                self._process_directory(project_props, project_name)
            else:
                # For make_template, get project props normally
                project_props = self._get_project_properties()
                project_name = self._get_project_name()
                print(f"👷 {Fore.BLUE} Creating project {project_name} {Fore.RESET}")
                
                self._apply_project_configuration(project_props)
                self._process_directory(project_props, project_name)

        except Exception as e:
            self.logger.error(f"Project conversion failed: {e}")
            raise

    def _get_project_properties(self) -> dict:
        """Get project properties based on project type."""
        project_props = {}
        if self.config.project_type in [
            "terraform",
            "tofu",
        ] and check_project_properties(
            directory=self.config.code_directory,
        ):
            project_props = get_project_props(
                cloud_provider="aws", remote_bkd_cloud_provider="aws"
            )
            set_project_conf(project_properties=project_props, project_type=self.config.project_type or "terraform")

        return project_props

    def _get_project_name(self) -> str:
        """Get project name from configuration file."""
        return load_iac_conf(
            directory=self.config.code_directory, file_name=".thothcf.toml"
        )["thothcf"]["project_id"]

    def _apply_project_configuration(self, project_props: dict) -> None:
        """Apply project configuration if properties exist."""
        if project_props:
            set_project_conf(project_properties=project_props, project_type=self.config.project_type or "terraform")

    def _process_directory(self, project_props: dict, project_name: str) -> None:
        """Process directory for conversion."""
        action = "make_project"
        if self.config.make_template:
            action = "make_template"

        replace_template_placeholders(
            directory=self.config.code_directory,
            project_properties=project_props,
            project_name=project_name,
            action=action,
        )

        # If making a template, copy it to the global thothcf directory
        if self.config.make_template:
            self._save_template_to_global_directory(project_name)
            self._create_clean_template_config(project_name)
            self._clean_original_project_config()
            self._update_global_template_registry(project_name)
    
    def _get_project_name_from_current_or_restore(self) -> str:
        """Get project name from current config or find and restore from backup."""
        from pathlib import Path
        import toml
        import shutil
        
        config_path = Path(self.config.code_directory) / ".thothcf.toml"
        
        # Try to read project_id from current config
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = toml.load(f)
                if 'thothcf' in config and 'project_id' in config['thothcf']:
                    return config['thothcf']['project_id']
            except:
                pass
        
        # If no project_id found, try to find backup in template directories
        thothcf_home = Path.home() / ".thothcf"
        if thothcf_home.exists():
            for template_dir in thothcf_home.iterdir():
                if template_dir.is_dir():
                    backup_config = template_dir / f".thothcf.{template_dir.name}.backup.toml"
                    if backup_config.exists():
                        # Restore the backup and get project name
                        shutil.copy2(backup_config, config_path)
                        print(f"✅ Found and restored backup config from template: {template_dir.name}")
                        return template_dir.name
        
        return None
    
    def _update_global_template_registry(self, project_name: str) -> None:
        """Update the global .thothcf.toml registry with template file hashes."""
        import hashlib
        import toml
        from pathlib import Path
        
        # Global registry path
        thothcf_home = Path.home() / ".thothcf"
        global_registry = thothcf_home / ".thothcf.toml"
        
        # Initialize registry if it doesn't exist
        if not global_registry.exists():
            # Copy template from common
            template_path = Path(__file__).parent.parent.parent / "common" / ".thothcf_home.toml"
            if template_path.exists():
                import shutil
                shutil.copy2(template_path, global_registry)
            else:
                # Create empty registry
                with open(global_registry, 'w') as f:
                    f.write("")
        
        # Load existing registry
        try:
            with open(global_registry, 'r') as f:
                registry = toml.load(f)
        except:
            registry = {}
        
        # Initialize project section
        if project_name not in registry:
            registry[project_name] = {"template_files": []}
        
        # Scan template directory for files and calculate hashes
        template_dir = thothcf_home / project_name
        template_files = []
        
        for file_path in template_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                # Calculate relative path from template root
                relative_path = file_path.relative_to(template_dir)
                
                # Calculate file hash
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                
                template_files.append({
                    "source": str(relative_path.parent) if relative_path.parent != Path('.') else "",
                    "local": file_path.name,
                    "hash": file_hash
                })
        
        # Update registry
        registry[project_name]["template_files"] = template_files
        
        # Save registry
        with open(global_registry, 'w') as f:
            toml.dump(registry, f)
        
        print(f"✅ Updated global template registry with {len(template_files)} files")
    
    def _clean_original_project_config(self) -> None:
        """Remove only project_properties section from the original project .thothcf.toml file."""
        from pathlib import Path
        import toml
        
        config_path = Path(self.config.code_directory) / ".thothcf.toml"
        
        if config_path.exists():
            # Read the original config
            with open(config_path, 'r') as f:
                config = toml.load(f)
            
            # Remove only project_properties section (keep thothcf for project_id)
            if 'project_properties' in config:
                del config['project_properties']
            
            # Write clean config back to original
            with open(config_path, 'w') as f:
                toml.dump(config, f)
            
            print(f"✅ Cleaned original project config (removed project_properties)")
    
    def _restore_project_config(self, project_name: str) -> None:
        """Restore project configuration from template backup if available."""
        from pathlib import Path
        import shutil
        
        template_dir = Path.home() / ".thothcf" / project_name
        backup_config = template_dir / f".thothcf.{project_name}.backup.toml"
        target_config = Path(self.config.code_directory) / ".thothcf.toml"
        
        if backup_config.exists():
            shutil.copy2(backup_config, target_config)
            print(f"✅ Restored project config from template backup")
            self._check_template_updates(project_name)
        else:
            print("ℹ️  No backup config found in template, using current configuration")
    
    def _check_template_updates(self, project_name: str) -> None:
        """Check if template files have been updated and offer to sync changes."""
        import hashlib
        import toml
        from pathlib import Path
        
        # Load global registry
        thothcf_home = Path.home() / ".thothcf"
        global_registry = thothcf_home / ".thothcf.toml"
        
        if not global_registry.exists():
            return
        
        try:
            with open(global_registry, 'r') as f:
                registry = toml.load(f)
        except:
            return
        
        if project_name not in registry:
            return
        
        # Check current project files against registry
        template_files = registry[project_name].get("template_files", [])
        updated_files = []
        
        for file_info in template_files:
            local_file = Path(self.config.code_directory) / file_info["local"]
            if local_file.exists():
                # Calculate current hash
                with open(local_file, 'rb') as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Compare with registry hash
                if current_hash != file_info["hash"]:
                    updated_files.append(file_info["local"])
        
        if updated_files:
            print(f"ℹ️  Found {len(updated_files)} files that differ from template:")
            for file_name in updated_files[:5]:  # Show first 5
                print(f"  • {file_name}")
            if len(updated_files) > 5:
                print(f"  • ... and {len(updated_files) - 5} more")
            print("💡 Consider updating the template with: thothctl project convert --make-template")
        """Restore project configuration from template backup if available."""
        from pathlib import Path
        import shutil
        
        template_dir = Path.home() / ".thothcf" / project_name
        backup_config = template_dir / f".thothcf.{project_name}.backup.toml"
        target_config = Path(self.config.code_directory) / ".thothcf.toml"
        
        if backup_config.exists():
            shutil.copy2(backup_config, target_config)
            print(f"✅ Restored project config from template backup")
        else:
            print("ℹ️  No backup config found in template, using current configuration")
    
    def _create_clean_template_config(self, project_name: str) -> None:
        """Create a clean .thothcf.toml file for the template and backup the original."""
        from pathlib import Path
        import toml
        import shutil
        
        template_dir = Path.home() / ".thothcf" / project_name
        template_config_path = template_dir / ".thothcf.toml"
        backup_config_path = template_dir / f".thothcf.{project_name}.backup.toml"
        
        # First, backup the original config with sensitive data to template folder
        original_config_path = Path(self.config.code_directory) / ".thothcf.toml"
        if original_config_path.exists():
            shutil.copy2(original_config_path, backup_config_path)
            print(f"✅ Backed up original config to template folder")
        
        # Read the template config
        with open(template_config_path, 'r') as f:
            config = toml.load(f)
        
        # Remove only project_properties section from template (keep thothcf for project_id)
        if 'project_properties' in config:
            del config['project_properties']
        
        # Write clean template config
        with open(template_config_path, 'w') as f:
            toml.dump(config, f)
        
        print(f"✅ Created clean template configuration")
    
    def _save_template_to_global_directory(self, project_name: str) -> None:
        """Save the template to the global thothcf directory."""
        import shutil
        from pathlib import Path
        
        # Get the global thothcf directory
        thothcf_dir = Path.home() / ".thothcf"
        template_dir = thothcf_dir / project_name
        
        # Create the directory if it doesn't exist
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the current directory to the template directory
        source_dir = Path(self.config.code_directory)
        
        # Remove existing template if it exists
        if template_dir.exists():
            shutil.rmtree(template_dir)
        
        # Copy the directory
        shutil.copytree(source_dir, template_dir, ignore=shutil.ignore_patterns('.git', '.terraform', '.terragrunt-cache', '.amazonq'))
        
        print(f"✅ Template saved to {template_dir}")
        print(f"✅ Template '{project_name}' is now available for project creation")
