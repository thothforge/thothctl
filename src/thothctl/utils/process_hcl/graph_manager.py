import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from colorama import init


# Initialize colorama
init(autoreset=True)


@dataclass
class TerragruntGraph:
    """Represents a Terragrunt dependency graph."""

    edges: List[Dict]
    objects: Dict[str, Dict]


class DependencyGraphManager:
    """Manages dependency graph operations."""

    # Constants
    TERRAGRUNT_CMD = "terragrunt graph-dependencies --terragrunt-non-interactive"
    DOT_CMD = "dot -Tdot_json"

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_dependency_graph(self, directory: Path) -> str:
        """
        Generate dependency graph JSON for a directory.

        Args:
            directory (Path): Directory to analyze

        Returns:
            str: JSON representation of dependency graph

        Raises:
            subprocess.CalledProcessError: If command execution fails
        """
        try:
            full_path = directory.resolve()
            self.logger.info(f"Getting dependencies graph for {full_path.name}")

            cmd = f"cd {full_path} && {self.TERRAGRUNT_CMD} | {self.DOT_CMD}"
            result = subprocess.run(
                cmd, shell=True, text=True, capture_output=True, check=True
            )

            self.logger.debug(f"Graph JSON: {result.stdout}")
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate dependency graph: {e}")
            raise

    def process_directory_recursively(self, directory: Path) -> None:
        """
        Recursively process directories and create Terramate stacks for those
        containing terragrunt.hcl files, preserving root terramate.tm.hcl.

        Args:
            directory (Path): Root directory to process
        """
        try:
            # Store root directory on first call
            if self.root_dir is None:
                self.root_dir = directory.resolve()
                self.logger.info(f"Root directory set to: {self.root_dir}")

            # List all items in current directory
            for item in directory.iterdir():
                if not item.is_dir():
                    continue

                # Skip if this is the root terramate.tm.hcl
                if (item / TERRAMATE_FILE).exists() and item == self.root_dir:
                    self.logger.debug(f"Skipping root {TERRAMATE_FILE}")
                    continue

                # Process nested directories
                self.process_directory_recursively(item)

                # Check if current directory contains required files
                if self._has_required_files(item):
                    relative_path = item.relative_to(self.root_dir)
                    self.logger.info(
                        f"{Fore.GREEN}⚠️ Found terragrunt.hcl files in {relative_path}..."
                        f"\n❇️ Creating Terramate stacks...{Fore.RESET}"
                    )
                    try:
                        graph = json.loads(self.get_dependency_graph(item))
                        self.create_stack(graph, item, relative_path)
                    except Exception as e:
                        self.logger.error(f"Failed to process {relative_path}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to process directory {directory}: {e}")
            raise

    def process_dependencies(self, json_graph: Dict, relative_path: Path) -> List[str]:
        """
        Process dependency graph and extract dependencies with relative paths.

        Args:
            json_graph (Dict): The dependency graph
            relative_path (Path): Path relative to root

        Returns:
            List[str]: List of relative paths for dependencies
        """
        after = []
        if "edges" not in json_graph:
            return after

        for edge in json_graph["edges"]:
            for obj in json_graph["objects"]:
                if edge["tail"] == obj["_gvid"]:
                    stack_name = json_graph["objects"][edge["head"]]["name"]
                    relative_stack = self._make_relative_path(stack_name, relative_path)
                    self.logger.debug(f"{obj['name']} depends on {relative_stack}")
                    after.append(relative_stack)

        return list(dict.fromkeys(after))

    def _make_relative_path(self, stack_path: str, current_path: Path) -> str:
        """
        Convert stack paths to be relative to root terramate.tm.hcl.

        Args:
            stack_path (str): Original stack path
            current_path (Path): Current directory's relative path

        Returns:
            str: Path relative to root terramate.tm.hcl
        """
        try:
            stack = Path(stack_path)
            if stack.is_absolute():
                return str(stack)

            # Handle relative paths
            relative_stack = current_path / stack
            return str(relative_stack.resolve())
        except Exception as e:
            self.logger.error(f"Error making relative path: {e}")
            raise


# Legacy wrapper functions for backward compatibility
def graph_dependencies_to_json(directory: str) -> str:
    """Legacy wrapper for get_dependency_graph."""
    manager = DependencyGraphManager()
    return manager.get_dependency_graph(Path(directory))


def create_terramate_stacks(
    json_graph: Dict, directory: str, optimized: bool = False
) -> None:
    """Legacy wrapper for create_stack."""
    manager = DependencyGraphManager()
    manager.create_stack(json_graph, Path(directory), optimized)


def recursive_graph_dependencies_to_json(directory: str) -> None:
    """
    Recursively process directories and create Terramate stacks for those
    containing terragrunt.hcl files.

    Args:
        directory (str): Root directory to process
    """
    try:
        manager = DependencyGraphManager()
        manager.process_directory_recursively(Path(directory))
    except Exception as e:
        logging.error(f"Failed to process directories recursively: {e}")
        raise
