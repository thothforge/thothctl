"""Inventory management service."""
import logging
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import hcl2

from .models import Component, ComponentGroup, Inventory
from .report_service import ReportService
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

    def _walk_directory(self, directory: Path) -> Generator[Path, None, None]:
        """Walk directory and yield .tf files."""
        for path in directory.rglob("*.tf"):
            if path.is_file():
                yield path

    async def create_inventory(
        self,
        source_directory: str = ".",
        check_versions: bool = False,
        report_type: str = "html",
        reports_directory: str = "Reports",
    ) -> Dict[str, Any]:
        """Create inventory from source directory."""
        source_path = Path(source_directory).resolve()
        component_groups: List[ComponentGroup] = []

        # Collect all components
        for tf_file in self._walk_directory(source_path):
            components = list(self._parse_hcl_file(tf_file))

            if components:  # Only add if there are components
                relative_dir = str(tf_file.parent.relative_to(source_path))

                group = ComponentGroup(stack=f"./{relative_dir}", components=components)
                component_groups.append(group)

        # Create inventory
        inventory = Inventory(
            project_name=source_path.name, components=component_groups
        )
        inventory_dict = inventory.to_dict()
        # Check versions if requested
        if check_versions and inventory_dict:
            inventory_dict = await self.version_service.check_versions(inventory_dict)

        # Generate reports
        if report_type in ("html", "all"):
            html_path = self.report_service.create_html_report(inventory_dict)
            self.report_service.create_pdf_report(html_path)

        if report_type in ("json", "all"):
            self.report_service.create_json_report(inventory_dict)

        # Print to console
        self.report_service.print_inventory_console(inventory_dict)

        return inventory_dict

    def update_inventory(
        self, inventory_path: str, auto_approve: bool = False, action: str = "update"
    ):
        main_update_versions(
            inventory_file=inventory_path, auto_approve=auto_approve, action=action
        )
