"""Module for creating infrastructure components based on templates."""
import logging
from pathlib import Path
import os
from typing import List, Dict, Optional, Set, Sequence
from dataclasses import dataclass
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from ....common.common import load_iac_conf
from .files_content import (
    main_tf_content,
    parameters_tf_content,
    terragrunt_hcl_resource_content,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComponentConfig:
    """Configuration for component creation."""
    code_directory: str = "."
    component_path: str = "."
    component_type: Optional[str] = None
    component_name: Optional[str] = None
    project_file_structure: str = ".thothcf_project.toml"


class FileTemplates:
    """Mapping of file templates to their content with template preprocessing."""
    TEMPLATES = {
        "parameters.tf": parameters_tf_content,
        "terragrunt.hcl": terragrunt_hcl_resource_content,
        "main.tf": main_tf_content
    }

    HEADER_TEMPLATES = {"parameters.tf", "terragrunt.hcl"}

    @classmethod
    def get_content(cls, file_name: str, folder_name: str) -> str:
        """Get preprocessed template content."""
        content = cls.TEMPLATES.get(file_name, "")
        if not content:
            return ""

        if file_name in cls.HEADER_TEMPLATES:
            return f"#{folder_name}-{file_name}\n{content}"
        elif file_name == "main.tf":
            return content.replace("#{resource_name}#", folder_name)
        return content


class ComponentCreator:
    """Handles the creation of infrastructure components."""

    def __init__(self, config: ComponentConfig):
        self.config = config
        self.dirname = Path(__file__).parent
        self._structure_cache = {}

    @staticmethod
    def _create_hashable_key(folder_structure: Sequence[Dict]) -> tuple:
        """Convert folder structure to a hashable format."""
        return tuple(
            tuple(sorted(folder.items()))
            for folder in folder_structure
        )

    @staticmethod
    def get_folders_names(folders_structure: Sequence[Dict]) -> Set[str]:
        """Extract folder names from the structure."""
        names = {f["name"] for f in folders_structure}
        logger.info(f"Available component types: {names}")
        return names

    @staticmethod
    def get_folder_structure(folders_structure: Sequence[Dict], folder_name: str) -> Optional[List]:
        """Get the content structure for a specific folder."""
        return next((f["content"] for f in folders_structure if f["name"] == folder_name), None)

    @lru_cache(maxsize=32)
    def _get_cached_structure(self, structure_key: str) -> Dict:
        """Cached version of project structure loading."""
        confs = load_iac_conf(directory=self.config.code_directory)
        if not confs:
            logger.info("Using default project structure")
            return load_iac_conf(
                self.dirname / "../../../common",
                file_name=self.config.project_file_structure
            )["project_structure"]
        logger.info("Using custom project structure")
        return confs["project_structure"]

    def _load_project_structure(self) -> Dict:
        """Load and return the project structure configuration."""
        cache_key = f"{self.config.code_directory}:{self.config.project_file_structure}"
        return self._get_cached_structure(cache_key)

    def _create_folder(self, path: Path) -> None:
        """Create a new folder at the specified path."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create folder {path}", exc_info=True)
            raise RuntimeError(f"Failed to create folder: {str(e)}") from e

    def _create_file(self, base_path: Path, file_name: str) -> None:
        """Create and populate a file with appropriate content."""
        try:
            content = FileTemplates.get_content(file_name, self.config.component_name)
            file_path = base_path / file_name
            file_path.write_text(content)
            logger.debug(f"Created file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to create file {file_name}", exc_info=True)
            raise RuntimeError(f"Failed to create file {file_name}: {str(e)}") from e

    def _create_files_parallel(self, base_path: Path, file_names: List[str]) -> None:
        """Create multiple files in parallel."""
        with ThreadPoolExecutor(max_workers=min(len(file_names), os.cpu_count() or 1)) as executor:
            list(executor.map(lambda f: self._create_file(base_path, f), file_names))

    def create(self) -> None:
        """Create the component with the specified configuration."""
        if not self.config.component_type:
            logger.warning("No component type specified")
            return

        logger.info(f"Creating {self.config.component_type} "
                    f"{self.config.component_name} in {self.config.component_path}")

        try:
            project_structure = self._load_project_structure()
            folders_structure = project_structure.get("folders", [])

            folder_names = self.get_folders_names(folders_structure)

            if self.config.component_type not in folder_names:
                raise ValueError(f"Invalid component type: {self.config.component_type}")

            module_structure = self.get_folder_structure(folders_structure, self.config.component_type)
            if not module_structure:
                raise ValueError(f"No structure defined for component type: {self.config.component_type}")

            component_path = Path(self.config.component_path) / self.config.component_name
            self._create_folder(component_path)
            self._create_files_parallel(component_path, module_structure)

            logger.info(f"Successfully created component {self.config.component_name}")

        except Exception as e:
            logger.error("Failed during component creation", exc_info=True)
            raise RuntimeError(f"Component creation failed: {str(e)}") from e


def create_component(**kwargs) -> None:
    """Create a new component with the specified configuration."""
    try:
        config = ComponentConfig(**kwargs)
        creator = ComponentCreator(config)
        creator.create()
    except Exception as e:
        logger.error("Failed to create component", exc_info=True)
        raise RuntimeError(f"Component creation failed: {str(e)}") from e
