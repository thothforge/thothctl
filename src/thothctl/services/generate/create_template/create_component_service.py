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

@dataclass
class FolderStructure:
    """Represents a folder in the project structure."""
    name: str
    mandatory: bool
    content: Optional[List[str]] = None
    parent: Optional[str] = None
    type: str = "child"
    children: List['FolderStructure'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

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
            confs = load_iac_conf(
                self.dirname / "../../../common",
                file_name=self.config.project_file_structure
            )


        project_structure = confs.get("project_structure", {})
        if project_structure == {}:
            logger.info("Using custom project structure")
            confs = load_iac_conf(
                self.dirname / "../../../common",
                file_name=self.config.project_file_structure
            )

        return confs["project_structure"]

    def _load_project_structure(self) -> Dict:
        """Load and return the project structure configuration."""
        cache_key = f"{self.config.code_directory}:{self.config.project_file_structure}"
        return self._get_cached_structure(cache_key)

    def _build_folder_tree(self, folders: List[Dict]) -> Dict[str, FolderStructure]:
        """Build a tree structure from the flat list of folders."""
        # First create all folder objects
        folder_map = {}
        logger.debug(f"Processing folders: {folders}")

        for folder in folders:
            folder_map[folder["name"]] = FolderStructure(
                name=folder["name"],
                mandatory=folder.get("mandatory", False),
                content=folder.get("content", []),
                parent=folder.get("parent"),
                type=folder.get("type", "child")
            )

        logger.debug(f"Created folder map: {[f'{k}: parent={v.parent}' for k, v in folder_map.items()]}")

        # Then establish parent-child relationships
        root_folders = {}
        for folder_name, folder in folder_map.items():
            if folder.parent is None:
                root_folders[folder_name] = folder
                logger.debug(f"Added root folder: {folder_name}")
            else:
                parent = folder_map.get(folder.parent)
                if parent:
                    parent.children.append(folder)
                    logger.debug(f"Added {folder_name} as child to {folder.parent}")
                else:
                    logger.warning(f"Parent folder {folder.parent} not found for {folder_name}")

        logger.debug(f"Root folders: {list(root_folders.keys())}")
        for root_name, root_folder in root_folders.items():
            logger.debug(f"Root {root_name} has children: {[child.name for child in root_folder.children]}")

        return root_folders
    def _get_folder_name(self, folder_name: str) -> str:
        """Get the actual folder name, replacing placeholders with component name."""
        if self.config.component_name:
            return folder_name.replace("#{component_name}#", self.config.component_name)
        return folder_name

    def _create_folder(self, path: Path) -> None:
        """Create a new folder at the specified path."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created folder: {path}")
        except Exception as e:
            logger.error(f"Failed to create folder {path}", exc_info=True)
            raise RuntimeError(f"Failed to create folder: {str(e)}") from e

    def _create_file(self, base_path: Path, file_name: str, folder_name: str) -> None:
        """Create and populate a file with appropriate content."""
        try:
            content = FileTemplates.get_content(file_name, self._get_folder_name(folder_name))
            file_path = base_path / file_name
            file_path.write_text(content)
            logger.debug(f"Created file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to create file {file_name}", exc_info=True)
            raise RuntimeError(f"Failed to create file {file_name}: {str(e)}") from e

    def _create_component_structure(self, base_path: Path, folder: FolderStructure, is_root: bool = True) -> None:
        """Recursively create the component structure including nested folders."""
        try:
            # For root folder, use component name instead of folder.name
            actual_folder_name = self.config.component_name if is_root else folder.name
            folder_path = base_path / actual_folder_name

            logger.debug(f"Creating structure for {'root' if is_root else 'child'} folder: {actual_folder_name}")
            logger.debug(f"Has children: {[child.name for child in folder.children]}")

            # Create the current folder
            logger.debug(f"Creating folder: {folder_path}")
            folder_path.mkdir(parents=True, exist_ok=True)

            # Create files in the current folder
            if folder.content:
                logger.debug(f"Creating files in {folder_path}: {folder.content}")
                with ThreadPoolExecutor(max_workers=min(len(folder.content), os.cpu_count() or 1)) as executor:
                    list(executor.map(
                        lambda f: self._create_file(folder_path, f, actual_folder_name),
                        folder.content
                    ))

            # Process child folders recursively
            if folder.children:
                logger.debug(
                    f"Processing children of {actual_folder_name}: {[child.name for child in folder.children]}")
                for child in folder.children:
                    self._create_component_structure(folder_path, child, is_root=False)

        except Exception as e:
            logger.error(f"Error creating structure for folder {folder.name}", exc_info=True)
            raise

    def create(self) -> None:
        """Create the component with the specified configuration."""
        if not self.config.component_type:
            logger.warning("No component type specified")
            return

        if not self.config.component_name:
            logger.warning("No component name specified")
            return

        logger.info(f"Creating {self.config.component_type} "
                    f"{self.config.component_name} in {self.config.component_path}")

        try:
            project_structure = self._load_project_structure()
            folders_structure = project_structure.get("folders", [])

            # Log the loaded structure for debugging
            logger.debug(f"Loaded folders structure: {folders_structure}")

            folder_names = self.get_folders_names(folders_structure)
            if self.config.component_type not in folder_names:
                raise ValueError(f"Invalid component type: {self.config.component_type}")

            # Build the folder tree
            root_folders = self._build_folder_tree(folders_structure)
            logger.debug(f"Built folder tree with roots: {list(root_folders.keys())}")

            # Get the root folder for this component type
            root_folder = root_folders.get(self.config.component_type)
            if not root_folder:
                raise ValueError(f"No structure defined for component type: {self.config.component_type}")

            # Debug log to check children
            logger.debug(
                f"Root folder {self.config.component_type} has children: {[child.name for child in root_folder.children]}")

            # Create the component base path
            component_path = Path(self.config.component_path)

            # Create the entire folder structure recursively
            self._create_component_structure(component_path, root_folder, is_root=True)

            logger.info(f"Successfully created component {self.config.component_name}")

        except Exception as e:
            logger.error("Failed during component creation", exc_info=True)
            raise RuntimeError(f"Component creation failed: {str(e)}") from e

    def _create_files_parallel(self, base_path: Path, file_names: List[str]) -> None:
        """Create multiple files in parallel."""
        with ThreadPoolExecutor(max_workers=min(len(file_names), os.cpu_count() or 1)) as executor:
            list(executor.map(lambda f: self._create_file(base_path, f), file_names))




def create_component(**kwargs) -> None:
    """Create a new component with the specified configuration."""
    try:
        config = ComponentConfig(**kwargs)
        creator = ComponentCreator(config)
        creator.create()
    except Exception as e:
        logger.error("Failed to create component", exc_info=True)
        raise RuntimeError(f"Component creation failed: {str(e)}") from e
