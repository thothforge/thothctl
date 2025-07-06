"""Terragrunt HCL parser for inventory management."""
import logging
import re
from pathlib import Path
from typing import List, Tuple

import hcl2

from .models import Component

logger = logging.getLogger(__name__)


class TerragruntParser:
    """Parser for Terragrunt HCL files to extract module information."""

    def __init__(self):
        """Initialize the Terragrunt parser."""
        pass

    def parse_terragrunt_file(self, file_path: Path, source_directory: Path = None) -> List[Component]:
        """
        Parse Terragrunt HCL file and extract components.
        
        Args:
            file_path: Path to the terragrunt.hcl file
            source_directory: Base directory for relative path calculation
            
        Returns:
            List of components found in the file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                
            # Try to parse with hcl2 first
            try:
                data = hcl2.loads(content)
                components = self._extract_components_from_hcl(data, file_path, source_directory)
                if components:
                    logger.debug(f"Successfully parsed {file_path} with hcl2, found {len(components)} components")
                    return components
            except Exception as hcl_error:
                logger.debug(f"HCL2 parsing failed for {file_path}: {hcl_error}")
            
            # Fallback to regex parsing for terraform blocks
            components = self._extract_components_with_regex(content, file_path, source_directory)
            logger.debug(f"Regex parsing of {file_path} found {len(components)} components")
            return components
            
        except Exception as e:
            logger.error(f"Failed to parse Terragrunt file {file_path}: {str(e)}")
            return []

    def _extract_components_from_hcl(self, data: dict, file_path: Path, source_directory: Path = None) -> List[Component]:
        """Extract components from parsed HCL data."""
        components = []
        
        # Look for terraform blocks
        if "terraform" in data:
            terraform_blocks = data["terraform"]
            if isinstance(terraform_blocks, list):
                for block in terraform_blocks:
                    component = self._process_terraform_block(block, file_path, source_directory)
                    if component:
                        components.append(component)
            elif isinstance(terraform_blocks, dict):
                component = self._process_terraform_block(terraform_blocks, file_path, source_directory)
                if component:
                    components.append(component)
        
        return components

    def _process_terraform_block(self, terraform_block: dict, file_path: Path, source_directory: Path = None) -> Component:
        """Process a terraform block and create a Component."""
        source = terraform_block.get("source", "")
        
        if not source:
            return None
            
        # Handle source as list (from hcl2 parsing)
        if isinstance(source, list):
            source = source[0] if source else ""
            
        name, version, clean_source = self._extract_module_info(source)
        
        # Use the directory name as component name if we can't extract it from source
        if not name or name == "unknown":
            name = file_path.parent.name
            
        # Calculate relative file path
        if source_directory:
            try:
                relative_file_path = str(file_path.relative_to(source_directory))
            except ValueError:
                # If file_path is not relative to source_directory, use absolute path
                relative_file_path = str(file_path)
        else:
            try:
                relative_file_path = str(file_path.relative_to(Path.cwd()))
            except ValueError:
                relative_file_path = str(file_path)
            
        return Component(
            type="terragrunt_module",
            name=name,
            version=[version] if version else ["Null"],
            source=[clean_source] if clean_source else [source],
            file=relative_file_path,
            status="Null"
        )

    def _extract_components_with_regex(self, content: str, file_path: Path, source_directory: Path = None) -> List[Component]:
        """Extract components using regex parsing as fallback."""
        components = []
        
        # Regex to find terraform blocks with source
        terraform_block_pattern = r'terraform\s*\{[^}]*source\s*=\s*["\']([^"\']+)["\'][^}]*\}'
        
        matches = re.findall(terraform_block_pattern, content, re.DOTALL | re.MULTILINE)
        
        for source in matches:
            name, version, clean_source = self._extract_module_info(source)
            
            # Use the directory name as component name if we can't extract it from source
            if not name or name == "unknown":
                name = file_path.parent.name
                
            # Calculate relative file path
            if source_directory:
                try:
                    relative_file_path = str(file_path.relative_to(source_directory))
                except ValueError:
                    # If file_path is not relative to source_directory, use absolute path
                    relative_file_path = str(file_path)
            else:
                try:
                    relative_file_path = str(file_path.relative_to(Path.cwd()))
                except ValueError:
                    relative_file_path = str(file_path)
                
            component = Component(
                type="terragrunt_module",
                name=name,
                version=[version] if version else ["Null"],
                source=[clean_source] if clean_source else [source],
                file=relative_file_path,
                status="Null"
            )
            components.append(component)
            
        return components

    def _extract_module_info(self, source: str) -> Tuple[str, str, str]:
        """
        Extract module name, version, and clean source from a source string.
        
        Args:
            source: The source string from terragrunt.hcl
            
        Returns:
            Tuple of (name, version, clean_source)
        """
        if not source:
            return "unknown", "Null", source
            
        # Handle tfr:// format (Terraform Registry)
        if source.startswith("tfr:///"):
            # Format: tfr:///terraform-aws-modules/vpc/aws?version=5.0.0
            clean_source = source.replace("tfr:///", "")
            
            # Extract version from query parameter
            version = "Null"
            if "?" in clean_source:
                clean_source, query = clean_source.split("?", 1)
                version_match = re.search(r"version=([^&]+)", query)
                if version_match:
                    version = version_match.group(1)
            
            # Extract name from source (last part after /)
            parts = clean_source.split("/")
            name = parts[-1] if parts else "unknown"
            
            return name, version, clean_source
            
        # Handle Git sources
        elif source.startswith("git::"):
            # Format: git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v3.14.0
            version = "Null"
            clean_source = source.replace("git::", "")
            
            # Extract version from ref parameter
            if "?" in clean_source:
                clean_source_base, query = clean_source.split("?", 1)
                ref_match = re.search(r"ref=([^&]+)", query)
                if ref_match:
                    version = ref_match.group(1)
                clean_source = clean_source_base
            
            # Extract repository name
            if clean_source.endswith(".git"):
                clean_source = clean_source[:-4]
                
            name = clean_source.split("/")[-1] if "/" in clean_source else "unknown"
            
            # Clean up terraform- prefix for better naming
            if name.startswith("terraform-"):
                name = name.replace("terraform-", "", 1)
                
            return name, version, source.replace("git::", "")
            
        # Handle local modules
        elif source.startswith("../") or source.startswith("./") or source.startswith("/"):
            name = source.split("/")[-1] if "/" in source else source
            return name, "local", source
            
        # Handle registry modules (namespace/name/provider format)
        elif "/" in source and source.count("/") >= 2:
            parts = source.split("/")
            name = parts[-1] if len(parts) >= 3 else parts[-1]
            return name, "Null", source
            
        # Default case
        else:
            return source, "Null", source
