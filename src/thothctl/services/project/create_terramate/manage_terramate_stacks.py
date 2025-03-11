"""Create and operate terramate stacks."""
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import git
import os
from colorama import Fore


@dataclass
class TerramateConfig:
    """Configuration for Terramate stack creation."""

    directory: Path
    optimized: bool = False
    default_branch: str = "master"


class TerramateStackManager:
    """Manages Terramate stack operations."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_directory_recursively(self, directory: Path) -> None:
        """
        Process directory recursively to create Terramate stacks.

        Args:
            directory: Root directory to process
        """
        try:
            self.logger.debug(f"Processing directory: {directory}")

            # Walk through all directories
            for current_dir, dirs, files in os.walk(directory):
                current_path = Path(current_dir)

                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                # Check if current directory is a Terragrunt project
                if self._is_terragrunt_project(current_path):
                    self.logger.debug(f"Found Terragrunt project in: {current_path}")
                    print(
                        f"{Fore.GREEN}⚠️ Found terragrunt.hcl files in {current_path} ...\n"
                        f"❇️ Creating Terramate stacks ...{Fore.RESET}"
                    )

                    try:
                        # Generate dependency graph
                        graph_json = self.get_dependency_graph(current_path)
                        graph = json.loads(graph_json)

                        # Create stack
                        self.create_stack(
                            json_graph=graph, directory=current_path, optimized=False
                        )
                        print(
                            f"{Fore.GREEN}✅ Created Terramate stack in: {current_path}{Fore.RESET}"
                        )

                    except Exception as e:
                        self.logger.error(
                            f"Failed to create stack in {current_path}: {e}"
                        )
                        print(
                            f"{Fore.RED}❌ Failed to create stack in: {current_path}{Fore.RESET}"
                        )
                        continue

        except Exception as e:
            self.logger.error(f"Failed to process directory recursively: {e}")
            raise

    def _is_terragrunt_project(self, path: Path) -> bool:
        """
        Check if directory contains Terragrunt project files.

        Args:
            path: Directory path to check

        Returns:
            bool: True if directory contains main.tf and terragrunt.hcl
        """
        main_tf = path / "main.tf"
        terragrunt_hcl = path / "terragrunt.hcl"

        has_files = main_tf.is_file() and terragrunt_hcl.is_file()
        if has_files:
            self.logger.debug(f"Found Terragrunt project files in: {path}")
        return has_files

    def get_dependency_graph(self, directory: Path) -> str:
        """
        Generate dependency graph in JSON format.

        Args:
            directory: Path to the directory containing Terragrunt files

        Returns:
            JSON string representing the dependency graph
        """
        try:
            full_path = directory.resolve()
            self.logger.debug(f"Getting dependencies graph for {full_path.name}")

            # Change to target directory
            original_dir = os.getcwd()
            os.chdir(full_path)

            try:
                # Execute terragrunt command
                terragrunt_process = subprocess.run(
                    [
                        "terragrunt",
                        "graph-dependencies",
                        "--terragrunt-non-interactive",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Process output through dot
                dot_process = subprocess.run(
                    ["dot", "-Tdot_json"],
                    input=terragrunt_process.stdout,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                return dot_process.stdout

            finally:
                # Always return to original directory
                os.chdir(original_dir)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate dependency graph: {e}")
            print(f"{Fore.RED}Failed to generate dependency graph: {e}{Fore.RESET}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error generating dependency graph: {e}")
            raise

    def create_stack(
        self, json_graph: Dict, directory: Path, optimized: bool = False
    ) -> None:
        """
        Create Terramate stack configuration.

        Args:
            json_graph: Dependency graph in JSON format
            directory: Target directory for stack creation
            optimized: Whether to optimize and add to git
        """
        try:
            # Process dependencies
            after = self._process_dependencies(json_graph, directory=directory)
            self.logger.debug(f"Dependencies: {after}")

            # Generate content
            content = self._generate_stack_content(after)

            # Write file
            terramate_file = directory / "stack.tm.hcl"
            terramate_file.write_text(content)
            print(f"{Fore.GREEN}Created Terramate file: {terramate_file}{Fore.RESET}")

            if optimized:
                self._add_to_git(terramate_file)

        except Exception as e:
            self.logger.error(f"Failed to create stack: {e}")
            raise

    def create_main_file(self, config: TerramateConfig) -> None:
        """
        Create main Terramate configuration file.

        Args:
            config: Terramate configuration
        """
        try:
            content = self._generate_main_content(config.default_branch)

            terramate_file = Path("terramate.tm.hcl")
            terramate_file.write_text(content)

            if config.optimized:
                self._add_to_git(terramate_file)

        except Exception as e:
            self.logger.error(f"Failed to create main file: {e}")
            raise

    def _process_dependencies(self, json_graph: Dict, directory: Path) -> List[str]:
        """Process dependency graph to extract dependencies and convert to relative paths."""
        try:
            after = []
            if "edges" not in json_graph:
                return after

            current_dir = directory.resolve()

            for edge in json_graph["edges"]:
                for obj in json_graph["objects"]:
                    if edge["tail"] == obj["_gvid"]:
                        dep_path = Path(json_graph["objects"][edge["head"]]["name"])
                        rel_path = self._get_relative_path(dep_path, current_dir)

                        self.logger.debug(f"Adding dependency: {rel_path}")
                        after.append(rel_path)

            return list(dict.fromkeys(after))

        except Exception as e:
            self.logger.error(f"Error processing dependencies: {e}")
            raise

    def _generate_stack_content(self, after: List[str]) -> str:
        """
        Generate Terramate stack configuration content.

        Args:
            after: List of relative path dependencies

        Returns:
            str: Stack configuration content
        """
        watch_content = """
            watch = [
                  "./terragrunt.hcl",
               ]"""

        # Format the after list with proper quotes around paths
        if after:
            paths_str = ", ".join(f'"{path}"' for path in after)
            after_content = f"    after = [{paths_str}]"
        else:
            after_content = ""

        content = f"""stack {{
    {after_content}{watch_content}
    }}"""
        return content

    def _get_relative_path(self, target_path: Path, current_dir: Path) -> str:
        """
        Get relative path from current directory to target path.

        Args:
            target_path: Target path to create relative path to
            current_dir: Current directory to create path from

        Returns:
            str: Relative path
        """
        try:
            # Resolve both paths to absolute paths
            target_abs = target_path.resolve()
            current_abs = current_dir.resolve()

            # Calculate relative path
            rel_path = os.path.relpath(target_abs, current_abs)

            # Convert Windows paths to Unix-style if needed
            rel_path = rel_path.replace(os.sep, "/")

            self.logger.debug(
                f"Relative path from {current_abs} to {target_abs}: {rel_path}"
            )
            return rel_path

        except Exception as e:
            self.logger.error(f"Error calculating relative path: {e}")
            # Return original path if conversion fails
            return str(target_path)

    def _generate_main_content(self, default_branch: str) -> str:
        """Generate main Terramate configuration content."""
        content = f"""
terramate {{
  config {{
    git {{
      default_remote = "origin"
      default_branch = "{default_branch}"
      check_untracked = false
      check_uncommitted = false
      check_remote = false
        }}
  }}
}}
"""
        return content

    def _add_to_git(self, file_path: Path) -> None:
        """Add file to git repository."""
        try:
            repo = git.Repo(".")
            repo.git.add(str(file_path))
            print(
                f"{Fore.GREEN}The file {file_path} was added to git project!{Fore.RESET}"
            )
        except git.GitCommandError as e:
            self.logger.error(f"Failed to add file to git: {e}")
            raise

    def _create_stack_for_directory(self, directory: Path) -> None:
        """Create Terramate stack for specified directory."""
        print(
            f"{Fore.GREEN}⚠️ Found terragrunt.hcl files in {directory} ...\n"
            f"❇️ Creating Terramate stacks ...{Fore.RESET}"
        )
        graph = json.loads(self.get_dependency_graph(directory))
        self.create_stack(graph, directory)
