"""Validate project structure using Clean Architecture principles."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Set, Optional, Protocol
import logging
from colorama import Fore, init
import os
import sys
from ....common.common import load_iac_conf

# Initialize colorama
init(autoreset=True)

# Constants
IGNORED_DIRECTORIES = {".git", ".terraform", ".terragrunt-cache"}


class ValidationMode(Enum):
    """Validation modes for project structure checking."""
    SOFT = "soft"
    HARD = "hard"


@dataclass
class ProjectItem:
    """Represents a project structure item."""
    name: str
    type: str
    mandatory: bool = False
    content: List = field(default_factory=list)
    children: Dict[str, 'ProjectItem'] = field(default_factory=dict)  # Add children field


@dataclass
class ValidationResult:
    """Result of structure validation."""
    differences: List[Dict]
    existing_items: Set[str]
    is_valid: bool


@dataclass
class ProjectStructure:
    """Project structure configuration."""
    folders: List[ProjectItem]
    root_files: List[str]


class ProjectValidator(Protocol):
    """Protocol for project structure validation."""

    def validate(self, directory: Path, mode: ValidationMode) -> ValidationResult:
        """Validate project structure."""
        pass

class StructureValidator:
    """Handles project structure validation."""

    def __init__(self, base_path: str,logger: logging.Logger):
        self.logger = logger
        self.base_path = base_path

    def _validate_content(self, folder_path: Path, required_content: List[str], differences: List[Dict]) -> None:
        """Validate folder content against required files."""
        if not required_content:
            return

        print(f"{Fore.CYAN}📝 Checking content of {folder_path.name}{Fore.RESET}")
        existing_content = set(os.listdir(folder_path))

        for required_file in required_content:
            if required_file in existing_content:
                self._print_success(f"Required file {required_file} exists in {folder_path.name}")
            else:
                self._print_error(f"Required file {required_file} missing in {folder_path.name}")
                differences.append({
                    "Name": required_file,
                    "Check": "Fail",
                    "path": str(folder_path / required_file)
                })

    def validate(self, directory: Path, structure: ProjectStructure, mode: ValidationMode) -> ValidationResult:
        """
        Validate project structure against defined rules.

        Args:
            directory: Project directory to validate
            structure: Project structure rules
            mode: Validation mode (soft/hard)

        Returns:
            ValidationResult containing validation details
        """
        try:
            differences = []
            existing_items = set(os.listdir(directory))

            self.logger.debug(f"Validating structure in: {directory}")
            print(f"{Fore.GREEN}⚛️ Checking root structure{Fore.RESET}")

            # Check folders and their children
            self._validate_folders(directory, existing_items, structure.folders, differences)

            # Check root files
            self._validate_files( existing_items, structure.root_files, differences)

            # Process results
            is_valid = len(differences) == 0 or mode == ValidationMode.SOFT

            if not is_valid:
                self._print_validation_summary(differences)

            return ValidationResult(
                differences=differences,
                existing_items=existing_items,
                is_valid=is_valid
            )

        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            raise

    def _validate_folders(
            self,
            directory: Path,
            existing_items: Set[str],
            folders: List[ProjectItem],
            differences: List[Dict]
    ) -> None:
        """Validate folder structure including subfolder content."""
        for folder in folders:
            folder_path = directory / folder.name
            optional_text = " (optional)" if not folder.mandatory else ""

            if folder.name in existing_items:
                if folder_path.is_dir():
                    self._print_success(f"{folder.name} {folder.type} exists! in {directory}")
                    self.logger.debug(f"{folder.name} exists")

                    # If this is a root folder with content rules, check applicable subfolders
                    if folder.type == "root" and folder.content:
                        self._validate_subfolders_content(folder_path, folder.content, differences)

                else:
                    self._print_error(f"{folder.name} exists but is not a directory")
                    if folder.mandatory:
                        differences.append({
                            "Name": folder.name,
                            "Check": "Fail",
                            "path": str(folder_path)
                        })
            else:
                self._print_error(f"{folder.name} doesn't exist in {directory}{optional_text}")
                if folder.mandatory:
                    differences.append({
                        "Name": folder.name,
                        "Check": "Fail",
                        "path": str(folder_path)
                    })

    def _validate_subfolders_content(self, root_folder: Path, required_content: List[str],
                                     differences: List[Dict]) -> None:
        """
        Validate content rules only in subfolders that contain any of the specified files.
        Skip validation for subfolders that don't contain any of the rule files.
        """
        try:
            # Get all subfolders recursively
            for subfolder_path in self._get_all_subfolders(root_folder):
                existing_content = set(os.listdir(subfolder_path))

                # Check if this subfolder contains any of the files we're interested in
                has_rule_files = any(file in existing_content for file in required_content)

                if has_rule_files:
                    print(
                        f"{Fore.CYAN}📝 Checking content of subfolder {subfolder_path.relative_to(root_folder)}{Fore.RESET}")
                    missing_files = []

                    # If we found any rule file, check for all required files
                    for required_file in required_content:
                        if required_file in existing_content:
                            self._print_success(
                                f"Required file {required_file} exists in {subfolder_path.relative_to(root_folder)}"
                            )
                        else:
                            missing_files.append(required_file)
                            self._print_error(
                                f"Required file {required_file} missing in {subfolder_path.relative_to(root_folder)}"
                            )

                    if missing_files:
                        differences.append({
                            "Name": str(subfolder_path.relative_to(root_folder)),
                            "Check": "Fail",
                            "path": str(subfolder_path),
                            "missing": missing_files
                        })
                else:
                    # Skip validation for this subfolder as it doesn't contain any rule files
                    self.logger.debug(
                        f"Skipping content validation for {subfolder_path.relative_to(root_folder)} "
                        f"(no rule files found)"
                    )

        except Exception as e:
            self.logger.error(f"Error validating subfolders content: {e}")

    def _get_all_subfolders(self, root_folder: Path) -> List[Path]:
        """Get all subfolders recursively, excluding ignored directories."""
        subfolders = []
        try:
            for item in os.scandir(root_folder):
                if item.is_dir() and item.name not in IGNORED_DIRECTORIES:
                    subfolder_path = Path(item.path)
                    subfolders.append(subfolder_path)
                    # Recursively get subfolders
                    subfolders.extend(self._get_all_subfolders(subfolder_path))
        except Exception as e:
            self.logger.error(f"Error scanning directory {root_folder}: {e}")
        return subfolders
    def transform_config(config: dict) -> dict:
        """Transform the configuration to include proper folder structure with content."""
        transformed = {
            "folders": [],
            "root_files": config.get("root_files", [])
        }

        for folder in config.get("folders", []):
            folder_item = {
                "name": folder["name"],
                "type": folder.get("type", "root"),
                "mandatory": folder.get("mandatory", True),
                "content": folder.get("content", [])
            }

            transformed["folders"].append(folder_item)

        return transformed
    def _validate_files(
            self,
            existing_items: Set[str],
            required_files: List[str],
            differences: List[Dict]
    ) -> None:
        """Validate required files."""
        for file in required_files:
            if file in existing_items:
                self._print_success(f"{file} exists!")
                self.logger.debug(f"{file} exists")
            else:
                self._print_error(f"{file} doesn't exist!")
                differences.append({
                    "Name": file,
                    "Check": "Fail",
                    "path": file
                })

    def get_child_folders(self, parent_path: str) -> dict:
        """Get all child folders in the given parent path"""
        child_structure = {}
        try:
            with os.scandir(parent_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        child_structure[entry.name] = entry.path
        except FileNotFoundError:
            logging.warning(f"Directory not found: {parent_path}")
        return child_structure

    def validate_structure(self, rules: dict, path: str = None, mood: str = "strict") -> bool:
        """
        Validate the folder structure against defined rules
        Args:
            rules: Dictionary containing structure rules
            path: Current path to validate (defaults to base_path)
            mood: Validation mood ('strict' or 'relaxed')
        """
        current_path = path or self.base_path
        is_valid = True

        # Validate current level
        for item_name, item_rules in rules.items():
            item_path = os.path.join(current_path, item_name)

            if isinstance(item_rules, dict):
                # This is a parent folder with child rules
                if os.path.exists(item_path):
                    print(f"{Fore.CYAN}👷 Checking parent folder {item_name}{Fore.RESET}")

                    # First validate that the parent exists and is a directory
                    if not os.path.isdir(item_path):
                        print(f"{Fore.RED}❌ {item_name} exists but is not a directory{Fore.RESET}")
                        is_valid = False
                        continue

                    # Get actual child folders
                    child_folders = self.get_child_folders(item_path)

                    # Validate child rules
                    for child_name, child_rules in item_rules.get('children', {}).items():
                        print(f"{Fore.CYAN}👷 Checking child folder {child_name}{Fore.RESET}")

                        if child_name in child_folders:
                            # Recursively validate child structure
                            child_valid = self.validate_structure(
                                {child_name: child_rules},
                                path=item_path,
                                mood=mood
                            )
                            is_valid = is_valid and child_valid
                        else:
                            if mood == "strict" and child_rules.get('required', True):
                                print(f"{Fore.RED}❌ Required child folder {child_name} missing{Fore.RESET}")
                                is_valid = False
                            else:
                                print(f"{Fore.CYAN}Child folder {child_name} skipped (doesn't exist){Fore.RESET}")

                else:
                    if mood == "strict" and item_rules.get('required', True):
                        print(f"{Fore.RED}❌ Required parent folder {item_name} missing{Fore.RESET}")
                        is_valid = False
                    else:
                        print(f"{Fore.CYAN}Parent folder {item_name} skipped (doesn't exist){Fore.RESET}")

            else:
                # This is a simple folder requirement
                if os.path.exists(item_path):
                    if not os.path.isdir(item_path):
                        print(f"{Fore.RED}❌ {item_name} exists but is not a directory{Fore.RESET}")
                        is_valid = False
                elif mood == "strict" and item_rules.get('required', True):
                    print(f"{Fore.RED}❌ Required folder {item_name} missing{Fore.RESET}")
                    is_valid = False

        return is_valid



    def _validate_child_folders(
            self,
            parent_path: Path,
            children: Dict[str, ProjectItem],
            differences: List[Dict]
    ) -> None:
        """Validate child folder structure."""
        try:
            existing_children = set(os.listdir(parent_path))

            print(f"{Fore.CYAN}👷 Checking child folders in {parent_path.name}{Fore.RESET}")

            for child_name, child_item in children.items():
                optional_text = " but is optional" if not child_item.mandatory else ""

                if child_name in existing_children:
                    child_path = parent_path / child_name
                    if child_path.is_dir():
                        self._print_success(f"Child folder {child_name} exists in {parent_path.name}")

                        # Recursively validate nested children
                        if child_item.children:
                            self._validate_child_folders(child_path, child_item.children, differences)
                    else:
                        self._print_error(f"{child_name} exists but is not a directory in {parent_path.name}")
                        if child_item.mandatory:
                            differences.append({
                                "Name": child_name,
                                "Check": "Fail",
                                "path": str(child_path)
                            })
                else:
                    self._print_error(f"Child folder {child_name} doesn't exist in {parent_path.name}{optional_text}")
                    if child_item.mandatory:
                        differences.append({
                            "Name": child_name,
                            "Check": "Fail",
                            "path": str(parent_path / child_name)
                        })

        except Exception as e:
            self.logger.error(f"Error validating child folders in {parent_path}: {e}")
            raise

    @staticmethod
    def _print_success(message: str) -> None:
        """Print success message."""
        print(f"{Fore.GREEN}✅ - {message}{Fore.RESET}")

    @staticmethod
    def _print_error(message: str) -> None:
        """Print error message."""
        print(f"{Fore.RED}❌ - {message}{Fore.RESET}")

    def _print_validation_summary(self, differences: List[Dict]) -> None:
        """Print validation summary."""
        print(f"\n{Fore.CYAN}Summary")
        for diff in differences:
            print(f"{Fore.RED}❌ No found file or archive {diff['Name']}")


class ProjectStructureAnalyzer:
    """Analyzes project structure and creates tree representation."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def analyze(self, directory: Path) -> Dict:
        """
        Analyze project structure and create tree representation.

        Args:
            directory: Project directory to analyze

        Returns:
            Dict containing project structure tree
        """
        try:
            tree = self._get_initial_tree(directory)
            self._build_tree(directory, tree)
            return tree
        except Exception as e:
            self.logger.error(f"Failed to analyze project structure: {e}")
            raise

    def _get_initial_tree(self, directory: Path) -> Dict:
        """Get initial tree structure."""
        return {
            item.name: []
            for item in directory.iterdir()
            if item.is_dir() and item.name not in IGNORED_DIRECTORIES
        }

    def _build_tree(self, directory: Path, tree: Dict) -> None:
        """Build complete tree structure."""
        for path in directory.rglob('*'):
            if self._should_process_path(path):
                self._process_path(path, tree)

    def _should_process_path(self, path: Path) -> bool:
        """Check if path should be processed."""
        return (
                path.is_dir() and
                not any(ignored in str(path) for ignored in IGNORED_DIRECTORIES)
        )

    def _process_path(self, path: Path, tree: Dict) -> None:
        """Process path and add to tree."""
        try:
            parts = path.resolve().parts
            for key in tree.keys():
                if key in parts:
                    tree[key].append({
                        "name": path.name,
                        "path": str(path),
                        "type": "child_folder",
                        "content": list(path.iterdir())
                    })
        except Exception as e:
            self.logger.error(f"Error processing path {path}: {e}")


def create_validator(path, logger: Optional[logging.Logger] = None) -> StructureValidator:
    """Create configured validator instance."""
    if logger is None:
        logger = logging.getLogger("ProjectValidator")
        logger.setLevel(logging.INFO)
    return StructureValidator(path, logger)


def create_analyzer(logger: Optional[logging.Logger] = None) -> ProjectStructureAnalyzer:
    """Create configured analyzer instance."""
    if logger is None:
        logger = logging.getLogger("ProjectAnalyzer")
        logger.setLevel(logging.INFO)
    return ProjectStructureAnalyzer(logger)


def validate_project_structure(directory: Path, structure_config: Dict, mode: str = "soft") -> ValidationResult:
    """Validate project structure against configuration."""
    logger = logging.getLogger(__name__)
    validator = StructureValidator(str(directory), logger)

    # Create ProjectStructure with proper folder hierarchy and content
    folders = []
    for folder_config in structure_config["folders"]:
        folder_item = ProjectItem(
            name=folder_config["name"],
            type=folder_config.get("type", "root"),
            mandatory=folder_config.get("mandatory", True),
            content=folder_config.get("content", [])  # Make sure content is properly passed
        )
        folders.append(folder_item)

    structure = ProjectStructure(
        folders=folders,
        root_files=structure_config.get("root_files", [])
    )

    return validator.validate(directory, structure, ValidationMode(mode))


def validate(directory: str, mode: str, check_type: str = "project"):
    """Validate project structure."""
    try:
        # Load configuration
        config = load_iac_conf(directory)
        dirname = os.path.dirname(__file__)
        if config == {} or config.get("project_structure", None) is None:
            print(f"{Fore.LIGHTBLUE_EX}Using default options")
            if check_type == "module":
                file_name = ".thothcf_module.toml"
            else:
                file_name = ".thothcf_project.toml"

            config = load_iac_conf(
                os.path.join(dirname, "../../../common/"), file_name=file_name
            )

        # Transform configuration to include content
        transformed_config = {
            "folders": [],
            "root_files": config["project_structure"].get("root_files", [])
        }

        # Ensure content is properly transferred from config to transformed_config
        for folder in config["project_structure"].get("folders", []):
            folder_item = {
                "name": folder["name"],
                "type": folder.get("type", "root"),
                "mandatory": folder.get("mandatory", True),
                "content": folder.get("content", [])  # Make sure content is included
            }
            transformed_config["folders"].append(folder_item)

        # Validate structure
        result = validate_project_structure(
            Path(directory),
            transformed_config,
            mode
        )

        if result.is_valid:
            print(f"{Fore.GREEN}Project structure is valid{Fore.RESET}")
        else:
            print(f"{Fore.RED}Project structure is invalid{Fore.RESET}")
            sys.exit(1)

    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Fore.RESET}")
        sys.exit(1)