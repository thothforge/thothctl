"""Parser for Terragrunt HCL files."""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import hcl2

from .models import Component


logger = logging.getLogger(__name__)


class TerragruntParser:
    """Parser for Terragrunt HCL files."""

    def __init__(self):
        """Initialize Terragrunt parser."""
        # Pattern for matching source URLs with version/ref parameters
        self.source_pattern = re.compile(
            r"(?:tfr:\/\/\/|github\.com\/|git::https:\/\/|git::ssh:\/\/git@|git@github\.com:|https:\/\/github\.com\/|\/\/)([\w\-\.\/]+)(?:\?ref=|\?version=|@)([\w\.\-]+)"
        )
        # Pattern for matching version parameter
        self.version_pattern = re.compile(r"\?version=([0-9]+\.[0-9]+\.[0-9]+)")
        # Pattern for matching ref parameter
        self.ref_pattern = re.compile(r"\?ref=([a-zA-Z0-9\.\-]+)")
        # Pattern for Terraform Registry modules
        self.tfr_pattern = re.compile(r"tfr:///([^?]+)\?version=([0-9\.]+)")

    def parse_terragrunt_file(self, file_path: Path) -> List[Component]:
        """
        Parse Terragrunt HCL file and extract module information.
        
        Args:
            file_path: Path to the terragrunt.hcl file
            
        Returns:
            List of Component objects extracted from the file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = hcl2.load(file)
            
            components = []
            
            # Extract terraform source block
            if "terraform" in data and isinstance(data["terraform"], list):
                for terraform_block in data["terraform"]:
                    if "source" in terraform_block:
                        source = terraform_block["source"]
                        
                        # Handle source as string or list
                        if isinstance(source, list):
                            for src in source:
                                name, version, source_clean = self._extract_module_info(src)
                                if name and version:
                                    component = self._create_component(name, version, source_clean, file_path)
                                    components.append(component)
                        else:
                            name, version, source_clean = self._extract_module_info(source)
                            if name and version:
                                component = self._create_component(name, version, source_clean, file_path)
                                components.append(component)
            
            return components
        
        except Exception as e:
            logger.error(f"Failed to parse Terragrunt file {file_path}: {str(e)}")
            return []

    def _create_component(self, name: str, version: str, source_clean: str, file_path: Path) -> Component:
        """
        Create a Component object from parsed information.
        
        Args:
            name: Module name
            version: Module version
            source_clean: Clean source path
            file_path: Path to the terragrunt.hcl file
            
        Returns:
            Component object
        """
        return Component(
            type="terragrunt_module",
            name=name,
            version=[version],
            source=[source_clean],
            file=str(file_path.relative_to(Path.cwd())),
        )

    def _extract_module_info(self, source: str) -> Tuple[str, str, str]:
        """
        Extract module name, version, and clean source from Terragrunt source string.
        
        Args:
            source: The source string from terragrunt.hcl
            
        Returns:
            Tuple of (name, version, clean_source)
        """
        try:
            # Ensure source is a string
            if not isinstance(source, str):
                logger.warning(f"Source is not a string: {source}")
                return "unknown", "unknown", str(source)
                
            # Handle tfr:// format (Terraform Registry)
            if source.startswith("tfr:///"):
                # Extract module name and version from tfr:///terraform-aws-modules/alb/aws?version=8.7.0
                match = self.tfr_pattern.search(source)
                if match:
                    module_path = match.group(1)
                    version = match.group(2)
                    name_parts = module_path.split("/")
                    name = name_parts[-1] if len(name_parts) > 0 else "unknown"
                    return name, version, module_path
                else:
                    # Try to extract just the module path if version is not in the expected format
                    module_path = source.replace("tfr:///", "").split("?")[0]
                    version_match = re.search(r"\?version=([^&]+)", source)
                    version = version_match.group(1) if version_match else "unknown"
                    name_parts = module_path.split("/")
                    name = name_parts[-1] if len(name_parts) > 0 else "unknown"
                    return name, version, module_path
            
            # Handle git sources with ref or version
            git_match = self.source_pattern.search(source)
            if git_match:
                module_path = git_match.group(1)
                version = git_match.group(2)
                name_parts = module_path.split("/")
                name = name_parts[-1] if len(name_parts) > 0 else "unknown"
                return name, version, module_path
            
            # Handle local modules
            if source.startswith("../") or source.startswith("./"):
                path_parts = Path(source).parts
                name = path_parts[-1] if path_parts else "local-module"
                return name, "local", source
            
            # Handle direct module references (e.g., terraform-aws-modules/vpc/aws)
            if "/" in source and not source.startswith("http"):
                path_parts = source.split("/")
                name = path_parts[-1] if path_parts else "unknown"
                
                # Check for version in the source string
                version_match = re.search(r"~>\s*([0-9\.]+)", source)
                version = version_match.group(1) if version_match else "latest"
                
                return name, version, source
            
            # Default case - try to extract name from path
            path_parts = source.split("/")
            name = path_parts[-1] if path_parts else "unknown"
            return name, "unknown", source
            
        except Exception as e:
            logger.error(f"Failed to extract module info from {source}: {str(e)}")
            return "unknown", "unknown", str(source)
