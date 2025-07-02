"""Terragrunt HCL parser for inventory management."""
import logging
from pathlib import Path
from typing import List

from .models import Component

logger = logging.getLogger(__name__)


class TerragruntParser:
    """
    Minimal Terragrunt parser to satisfy import requirements.
    
    Note: In terraform-terragrunt projects, the inventory service analyzes
    .tf files for modules, not terragrunt.hcl files. This parser exists
    primarily to prevent import errors.
    """

    def __init__(self):
        """Initialize the Terragrunt parser."""
        pass

    def parse_terragrunt_file(self, file_path: Path) -> List[Component]:
        """
        Parse Terragrunt HCL file and extract components.
        
        For terraform-terragrunt projects, this method returns an empty list
        because the analysis focuses on .tf files, not terragrunt.hcl files.
        
        Args:
            file_path: Path to the terragrunt.hcl file
            
        Returns:
            Empty list of components (analysis is done on .tf files instead)
        """
        logger.debug(f"Terragrunt file detected but not parsed: {file_path}")
        logger.debug("For terraform-terragrunt projects, analysis focuses on .tf files")
        
        # Return empty list - the actual module analysis happens in .tf files
        return []
