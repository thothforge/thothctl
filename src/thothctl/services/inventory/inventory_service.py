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
                    component = Component(
                        type="module",
                        name=name,
                        version=module[name].get(
                            "version",
                        ),  # ["Null"]),  # Make sure these are lists
                        source=module[name].get(
                            "source"
                        ),  # ["Null"]),  # Make sure these are lists
                        file=str(file_path.relative_to(Path.cwd())),
                    )
                    components.append(component)
        else:
            logger.debug(f"No modules found in {file_path}")
        return components

    def _parse_terragrunt_file(self, file_path: Path) -> List[Component]:
        """Parse Terragrunt HCL file and extract components."""
        return self.terragrunt_parser.parse_terragrunt_file(file_path)

    def _walk_directory(self, directory: Path) -> Generator[Tuple[str, Path], None, None]:
        """
        Walk directory and yield file type and path.
        
        Returns:
            Generator yielding tuples of (file_type, path)
            where file_type is either 'terraform' or 'terragrunt'
        """
        # First check for terragrunt.hcl files
        terragrunt_files = []
        
        # Skip .terragrunt-cache directories when scanning for terragrunt files
        for path in directory.rglob("terragrunt.hcl"):
            # Skip files in .terragrunt-cache directories
            if ".terragrunt-cache" not in str(path):
                if path.is_file():
                    terragrunt_files.append(path)
                    yield ('terragrunt', path)
        
        if terragrunt_files:
            self.is_terragrunt_project = True
            logger.info(f"Found {len(terragrunt_files)} terragrunt.hcl files")
        
        # Also check for regular .tf files
        for path in directory.rglob("*.tf"):
            # Skip files in .terragrunt-cache directories
            if ".terragrunt-cache" not in str(path):
                if path.is_file():
                    yield ('terraform', path)

    def _detect_project_type(self, source_path: Path) -> str:
        """
        Detect if the project is Terraform or Terragrunt based.
        
        Args:
            source_path: Path to the source directory
            
        Returns:
            'terragrunt', 'terraform', or 'terraform-terragrunt'
        """
        has_terragrunt = False
        has_terraform = False
        
        # Check for root terragrunt.hcl
        root_terragrunt = source_path / "terragrunt.hcl"
        if root_terragrunt.exists():
            has_terragrunt = True
            
        # Check for terragrunt.hcl files in subdirectories (excluding .terragrunt-cache)
        for path in source_path.rglob("terragrunt.hcl"):
            if ".terragrunt-cache" not in str(path):
                has_terragrunt = True
                break
                
        # Check for .tf files
        for _ in source_path.rglob("*.tf"):
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
    ) -> Dict[str, Any]:
        """Create inventory from source directory."""
        source_path = Path(source_directory).resolve()
        component_groups: List[ComponentGroup] = []
        processed_dirs: Set[str] = set()

        # Detect project type
        if framework_type == "auto":
            project_type = self._detect_project_type(source_path)
            logger.info(f"Auto-detected project type: {project_type}")
        else:
            project_type = framework_type
            logger.info(f"Using specified project type: {project_type}")
            
        # Set flag for terragrunt projects
        self.is_terragrunt_project = "terragrunt" in project_type

        # Collect all components
        for file_type, file_path in self._walk_directory(source_path):
            components = []
            
            if file_type == 'terragrunt':
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
