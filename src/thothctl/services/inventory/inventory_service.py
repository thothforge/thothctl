"""Inventory management service."""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import hcl2

from .models import Component, ComponentGroup, Inventory
from .report_service import ReportService
from .terragrunt_parser import TerragruntParser
from .update_versions import main_update_versions
from .version_service import InventoryVersionManager


logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing infrastructure inventory."""

    def __init__(
        self,
        version_service: Optional[InventoryVersionManager] = None,
        report_service: Optional[ReportService] = None,
    ):
        """Initialize inventory service."""
        self.version_service = version_service or InventoryVersionManager()
        self.report_service = report_service or ReportService()
        self.terragrunt_parser = TerragruntParser()
        self.is_terragrunt_project = False

    def _parse_hcl_file(self, file_path: Path) -> List[Component]:
        """Parse HCL file and extract components."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = hcl2.load(file)
        except Exception as e:
            logger.error(f"Failed to load HCL file {file_path}: {str(e)}")
            data = {}
        components = []

        if "module" in data.keys():
            for module in data["module"]:
                for name, details in module.items():
                    source = module[name].get("source", "")
                    version = module[name].get("version", ["Null"])
                    
                    # Ensure source and version are lists
                    if not isinstance(source, list):
                        source = [source] if source else ["Null"]
                    if not isinstance(version, list):
                        version = [version] if version else ["Null"]
                    
                    component = Component(
                        type="module",
                        name=name,
                        version=version,
                        source=source,
                        file=str(file_path.relative_to(Path.cwd())),
                        status="Null"  # Keep original status logic - will be updated by version service
                    )
                    components.append(component)
        else:
            logger.debug(f"No modules found in {file_path}")
        return components

    def _is_local_module(self, source: str) -> bool:
        """
        Check if a module source is a local path.
        
        Args:
            source: The source string from the module
            
        Returns:
            True if the source is a local path, False otherwise
        """
        if not source or source == "Null":
            return False
            
        # Check for local paths
        return (source.startswith("./") or 
                source.startswith("../") or 
                source.startswith("/") or
                # Check for relative paths with multiple levels
                source.startswith("../../") or
                source.startswith("../../../") or
                source.startswith("../../../../") or
                # Check for absolute paths without protocol
                (not source.startswith("http") and not source.startswith("git") and "/" in source and not source.count("/") == 2))

    def _determine_module_status(self, source: str) -> str:
        """
        Determine the status of a module based on its source.
        
        Args:
            source: The source string from the module
            
        Returns:
            Status string: "Local", "Registry", "Git", or "Unknown"
        """
        if not source or source == "Null":
            return "Unknown"
            
        # Check for local paths
        if self._is_local_module(source):
            return "Local"
            
        # Check for Terraform Registry format (namespace/name/provider)
        if "/" in source and source.count("/") == 2 and not source.startswith("git") and not source.startswith("http"):
            # Additional check: registry modules typically don't have file extensions or deep paths
            if not source.endswith(".git") and "?" not in source:
                return "Registry"
                
        # Check for Git sources
        if (source.startswith("git::") or 
            source.startswith("git@") or
            source.endswith(".git") or
            "github.com" in source or
            "gitlab.com" in source or
            "bitbucket.org" in source):
            return "Git"
            
        # Check for HTTP sources
        if source.startswith("http://") or source.startswith("https://"):
            return "HTTP"
            
        return "Unknown"

    def _parse_terragrunt_file(self, file_path: Path) -> List[Component]:
        """Parse Terragrunt HCL file and extract components."""
        return self.terragrunt_parser.parse_terragrunt_file(file_path)

    def _walk_directory(self, directory: Path, complete: bool = False) -> Generator[Tuple[str, Path], None, None]:
        """
        Walk directory and yield file type and path.
        
        Args:
            directory: Directory to walk
            complete: If True, exclude .terraform and .terragrunt-cache folders
        
        Returns:
            Generator yielding tuples of (file_type, path)
            where file_type is either 'terraform' or 'terragrunt'
        """
        # First check for terragrunt.hcl files
        terragrunt_files = []
        
        # Skip .terragrunt-cache directories when scanning for terragrunt files
        for path in directory.rglob("terragrunt.hcl"):
            # Skip files in excluded directories
            if self._should_exclude_path(path, complete):
                continue
            if path.is_file():
                terragrunt_files.append(path)
                yield ('terragrunt', path)
        
        if terragrunt_files:
            self.is_terragrunt_project = True
            logger.info(f"Found {len(terragrunt_files)} terragrunt.hcl files")
        
        # Also check for regular .tf files
        for path in directory.rglob("*.tf"):
            # Skip files in excluded directories
            if self._should_exclude_path(path, complete):
                continue
            if path.is_file():
                yield ('terraform', path)

    def _should_exclude_path(self, path: Path, complete: bool) -> bool:
        """
        Check if a path should be excluded from analysis.
        
        Args:
            path: Path to check
            complete: If True, include everything (complete analysis). If False, exclude cache folders.
            
        Returns:
            True if path should be excluded, False otherwise
        """
        # If complete flag is set, don't exclude anything (complete analysis)
        if complete:
            return False
            
        path_str = str(path)
        
        # Without complete flag, exclude both .terraform and .terragrunt-cache folders
        if ".terragrunt-cache" in path_str or ".terraform" in path_str:
            return True
            
        return False

    def _detect_project_type(self, source_path: Path, complete: bool = False) -> str:
        """
        Detect if the project is Terraform or Terragrunt based.
        
        Args:
            source_path: Path to the source directory
            complete: If True, exclude .terraform and .terragrunt-cache folders
            
        Returns:
            'terragrunt', 'terraform', or 'terraform-terragrunt'
        """
        has_terragrunt = False
        has_terraform = False
        
        # Check for root terragrunt.hcl
        root_terragrunt = source_path / "terragrunt.hcl"
        if root_terragrunt.exists():
            has_terragrunt = True
            
        # Check for terragrunt.hcl files in subdirectories (excluding specified folders)
        for path in source_path.rglob("terragrunt.hcl"):
            if not self._should_exclude_path(path, complete):
                has_terragrunt = True
                break
                
        # Check for .tf files (excluding specified folders)
        for path in source_path.rglob("*.tf"):
            if not self._should_exclude_path(path, complete):
                has_terraform = True
                break
            
        # Determine project type based on findings
        if has_terragrunt and has_terraform:
            return "terraform-terragrunt"
        elif has_terragrunt:
            return "terragrunt"
        else:
            return "terraform"

    async def create_inventory(
        self,
        source_directory: str = ".",
        check_versions: bool = False,
        report_type: str = "html",
        reports_directory: str = "Reports",
        framework_type: str = "auto",
        complete: bool = False,
    ) -> Dict[str, Any]:
        """Create inventory from source directory."""
        source_path = Path(source_directory).resolve()
        component_groups: List[ComponentGroup] = []
        processed_dirs: Set[str] = set()
        terragrunt_stacks: List[str] = []  # Track terragrunt stacks

        # Detect project type
        if framework_type == "auto":
            project_type = self._detect_project_type(source_path, complete)
            logger.info(f"Auto-detected project type: {project_type}")
        else:
            project_type = framework_type
            logger.info(f"Using specified project type: {project_type}")
            
        # Set flag for terragrunt projects
        self.is_terragrunt_project = "terragrunt" in project_type

        # Collect all components and track terragrunt stacks
        for file_type, file_path in self._walk_directory(source_path, complete):
            components = []
            
            if file_type == 'terragrunt':
                # Track terragrunt stack (folder containing terragrunt.hcl)
                relative_dir = str(file_path.parent.relative_to(source_path))
                stack_path = f"./{relative_dir}" if relative_dir != "." else "./"
                if stack_path not in terragrunt_stacks:
                    terragrunt_stacks.append(stack_path)
                
                components = self._parse_terragrunt_file(file_path)
            else:  # terraform
                components = self._parse_hcl_file(file_path)

            if components:  # Only add if there are components
                relative_dir = str(file_path.parent.relative_to(source_path))
                
                # Skip if we've already processed this directory
                if relative_dir in processed_dirs:
                    continue
                    
                processed_dirs.add(relative_dir)
                group = ComponentGroup(stack=f"./{relative_dir}", components=components)
                component_groups.append(group)

        # Create inventory
        inventory = Inventory(
            project_name=source_path.name, 
            components=component_groups,
            project_type=project_type
        )
        inventory_dict = inventory.to_dict()
        
        # Add terragrunt stacks information to inventory dict
        if project_type == "terraform-terragrunt" and terragrunt_stacks:
            inventory_dict["terragrunt_stacks"] = terragrunt_stacks
            inventory_dict["terragrunt_stacks_count"] = len(terragrunt_stacks)
        
        # Check versions if requested
        if check_versions and inventory_dict:
            inventory_dict = await self.version_service.check_versions(inventory_dict)

        # Generate reports
        reports_path = Path(reports_directory)
        if not reports_path.is_absolute():
            reports_path = source_path / reports_path
            
        reports_path.mkdir(exist_ok=True, parents=True)
        
        if report_type in ("html", "all"):
            html_path = self.report_service.create_html_report(
                inventory_dict, 
                reports_directory=str(reports_path)
            )
            self.report_service.create_pdf_report(
                html_path, 
                reports_directory=str(reports_path)
            )

        if report_type in ("json", "all"):
            self.report_service.create_json_report(
                inventory_dict,
                reports_directory=str(reports_path)
            )

        # Print to console
        self.report_service.print_inventory_console(inventory_dict)

        return inventory_dict

    def update_inventory(
        self, inventory_path: str, auto_approve: bool = False, action: str = "update"
    ):
        main_update_versions(
            inventory_file=inventory_path, auto_approve=auto_approve, action=action
        )
