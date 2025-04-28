from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, List
from dataclasses import dataclass, field
import logging
import subprocess
import os
from colorama import Fore
from .files_content import terraform_docs_content_modules, terraform_docs_content_resources
from .iac_grunt_graph import graph_dependencies,graph_dependencies_recursive
from .iac_grunt_info import TerragruntInfoGenerator
from .files_scan import FileScanner

@dataclass
class TerraformDocsConfig:
    """Configuration for Terraform documentation generation."""
    directory: Path
    mood: str = "resources"
    config_file: Optional[Path] = None
    recursive: bool = False
    exclude_patterns: List[str] = field(default_factory=lambda: ['.terraform', '.git', '.terragrunt-cache'])
    framework: str = "terraform-terragrunt"

    def __post_init__(self):
        """Ensure exclude_patterns is always a list."""
        if self.exclude_patterns is None:
            self.exclude_patterns = []
        elif isinstance(self.exclude_patterns, tuple):
            self.exclude_patterns = list(self.exclude_patterns)
        elif not isinstance(self.exclude_patterns, list):
            self.exclude_patterns = [str(self.exclude_patterns)]

@dataclass
class DocsResult:
    """Result of documentation generation."""
    success: bool
    processed_dirs: List[Path] = None
    skipped_dirs: List[Path] = None
    error: Optional[str] = None

class CommandExecutor(Protocol):
    """Protocol for command execution."""

    def execute(self, command: list[str], cwd: Path, input_data: Optional[str] = None) -> tuple[str, str, int]:
        """Execute command and return stdout, stderr, and return code."""
        pass


class SubprocessExecutor:
    """Subprocess-based command executor."""

    def execute(self, command: list[str], cwd: Path, input_data: Optional[str] = None) -> tuple[str, str, int]:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if input_data else None,
                text=True,
            )
            stdout, stderr = process.communicate(input=input_data)
            return stdout, stderr, process.returncode
        except subprocess.SubprocessError as e:
            return "", str(e), 1

class TerraformDocsGenerator:
    """Handles generation of Terraform documentation."""

    def __init__(
            self,
            executor: CommandExecutor,
            logger: logging.Logger,
            content_provider: 'TerraformDocsContentProvider'

    ):
        self.executor = executor
        self.logger = logger
        self.content_provider = content_provider
        self.temp_config_path = Path("/tmp/.terraform-docs.yml")
        # Add a set to track processed directories
        self.processed_directories = set()

    def generate(self, config: TerraformDocsConfig) -> DocsResult:
        """Generate Terraform documentation."""
        try:
            # Clear the processed directories set at the start of each generation
            self.processed_directories.clear()

            # Debug log the configuration
            self.logger.debug("Starting documentation generation with config:")
            self.logger.debug(f"Directory: {config.directory}")
            self.logger.debug(f"Recursive: {config.recursive}")
            self.logger.debug(f"Exclude patterns (before conversion): {config.exclude_patterns}")

            # Ensure exclude_patterns is a list
            if isinstance(config.exclude_patterns, tuple):
                config.exclude_patterns = list(config.exclude_patterns)
                self.logger.debug(f"Converted tuple to list: {config.exclude_patterns}")

            self.logger.debug(f"Framework: {config.framework}")
            self.logger.debug(f"Mood: {config.mood}")

            # Prepare configuration file
            config_file = self._prepare_config_file(config)
            if not config_file:
                self.logger.error("Failed to prepare configuration file")
                return DocsResult(
                    success=False,
                    error="Failed to prepare configuration file"
                )

            processed_dirs = []
            skipped_dirs = []

            if config.recursive:
                self.logger.debug("Starting recursive documentation generation")
                self.logger.debug(f"Using exclude patterns: {config.exclude_patterns}")

                # Convert exclude patterns to list if it's a tuple
                exclude_patterns = (
                    list(config.exclude_patterns)
                    if isinstance(config.exclude_patterns, tuple)
                    else config.exclude_patterns or []
                )

                self._generate_recursive(
                    directory=config.directory,
                    config_file=config_file,
                    processed_dirs=processed_dirs,
                    skipped_dirs=skipped_dirs,
                    exclude_patterns=exclude_patterns
                )
            else:
                self.logger.debug(f"Generating documentation for single directory: {config.directory}")
                success = self._generate_for_directory(config.directory, config_file)
                if success:
                    processed_dirs.append(config.directory)
                else:
                    self.logger.debug(f"Failed to generate documentation for: {config.directory}")
                    skipped_dirs.append(config.directory)

            # Log results
            self.logger.debug(f"Processed directories: {processed_dirs}")
            self.logger.debug(f"Skipped directories: {skipped_dirs}")

            return DocsResult(
                success=len(processed_dirs) > 0,
                processed_dirs=processed_dirs,
                skipped_dirs=skipped_dirs
            )

        except Exception as e:
            self.logger.error("Failed to generate documentation: %s", e)
            return DocsResult(success=False, error=str(e))

    def _should_exclude_directory(self, path: str, exclude_patterns: List[str]) -> bool:
        """
        Check if directory should be excluded based on patterns.

        Args:
            path: Directory path to check
            exclude_patterns: List of patterns to exclude
        Returns:
            bool: True if directory should be excluded, False otherwise
        """
        for pattern in exclude_patterns:
            if pattern in path:
                self.logger.debug(f"Directory {path} matches exclude pattern '{pattern}'")
                return True
        return False

    def _generate_recursive(
            self,
            directory: Path,
            config_file: Path,
            processed_dirs: List[Path],
            skipped_dirs: List[Path],
            exclude_patterns: List[str]
    ) -> None:
        """Recursively generate documentation for all Terraform directories."""
        try:
            self.logger.debug(f"Starting recursive generation in {directory}")
            self.logger.debug(f"Exclude patterns: {exclude_patterns}")

            # Process all directories recursively using os.walk
            for current_dir, dirs, files in os.walk(directory):
                current_path = Path(current_dir).resolve()
                str_current_path = str(current_path)

                # Log current directory being processed
                self.logger.debug(f"Processing directory: {current_path}")

                # Skip if already processed
                if current_path in self.processed_directories:
                    self.logger.debug(f"Skipping already processed directory: {current_path}")
                    continue

                # Add to processed set
                self.processed_directories.add(current_path)

                # Check if current directory should be excluded
                if self._should_exclude_directory(str_current_path, exclude_patterns):
                    self.logger.debug(f"Excluding directory: {current_path}")
                    skipped_dirs.append(current_path)
                    dirs.clear()  # Clear dirs to prevent further traversal into this directory
                    continue

                # Filter out directories to skip (modify dirs in place)
                original_dirs = dirs.copy()
                dirs[:] = [d for d in dirs if not self._should_exclude_directory(
                    str(current_path / d),
                    exclude_patterns
                )]

                # Log filtered directories
                filtered_dirs = set(original_dirs) - set(dirs)
                if filtered_dirs:
                    self.logger.debug(f"Filtered out directories: {filtered_dirs}")

                # Check for Terraform files in current directory
                has_terraform = False
                for ext in ["*.tf", "*.hcl"]:
                    if list(current_path.glob(ext)):
                        has_terraform = True
                        self.logger.debug(f"Found {ext} files in {current_path}")
                        break

                if has_terraform:
                    self.logger.debug(f"Generating documentation for: {current_path}")
                    success = self._generate_for_directory(current_path, config_file)
                    if success:
                        processed_dirs.append(current_path)
                        self.logger.debug(f"Successfully processed: {current_path}")
                    else:
                        skipped_dirs.append(current_path)
                        self.logger.warning(f"Failed to process: {current_path}")
                else:
                    self.logger.debug(f"No Terraform files found in: {current_path}")

        except Exception as e:
            self.logger.error(f"Error processing directory {directory}: {e}")
            skipped_dirs.append(directory)

    def _generate_for_directory(self, directory: Path, config_file: Path) -> bool:
        """Generate documentation for a single directory."""
        try:
            # First validate if directory contains Terraform files
            if not self._validate_directory(directory):
                self.logger.debug(f"Skipping {directory} - no Terraform/Terragrunt files found")
                return False

            readme_path = directory / "README.md"
            # Check if README.md exists and contains the required markers
            if not self._ensure_readme_markers(readme_path):
                self.logger.error(f"README.md in {directory} doesn't have required terraform-docs markers")
                return False

            command = [
                "terraform-docs",
                "markdown",
                ".",
                "--config",
                str(config_file)
            ]

            self.logger.debug(f"Generating documentation for: {directory}")
            stdout, stderr, return_code = self.executor.execute(command, directory)

            if return_code == 0:
                print(f"{Fore.GREEN}❇️  Generated documentation for {directory.name}{Fore.RESET}")
                return True
            else:
                self.logger.error(f"terraform-docs failed for {directory}: {stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating docs for {directory}: {e}")
            return False
    def _validate_directory(self, directory: Path) -> bool:
        """
        Validate directory based on presence of Terraform (.tf) and/or Terragrunt (.hcl) files.

        Args:
            directory (Path): Directory to check
        Returns:
            bool: True if directory contains valid configuration files, False otherwise
        """
        try:
            has_tf = False
            has_hcl = False

            # Check for Terraform and Terragrunt files
            for file in directory.iterdir():
                if file.is_file():
                    if file.suffix == '.tf':
                        has_tf = True
                    elif file.suffix == '.hcl':
                        has_hcl = True
                    if has_tf or has_hcl:  # Exit early if we found either type
                        break

            # Log the validation result
            if has_tf or has_hcl:
                self.logger.debug(f"Found configuration files in {directory}")
                return True
            else:
                self.logger.debug(f"No Terraform or Terragrunt files found in {directory}")
                return False

        except Exception as e:
            self.logger.error(f"Error validating directory {directory}: {e}")
            return False
    def _ensure_readme_markers(self, readme_path: Path) -> bool:
        """
        Ensure README.md exists and has the required terraform-docs markers.
        Creates the file with markers if it doesn't exist.
        """
        markers = (
            "<!-- BEGIN_TF_DOCS -->\n"
            "<!-- END_TF_DOCS -->"
        )

        try:
            if not readme_path.exists():
                # Create new README.md with markers
                readme_path.write_text(markers)
                return True

            content = readme_path.read_text()
            if "<!-- BEGIN_TF_DOCS -->" not in content or "<!-- END_TF_DOCS -->" not in content:
                # Append markers to existing README if they don't exist
                with readme_path.open('a') as f:
                    f.write(f"\n\n{markers}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to prepare README.md: {e}")
            return False
    def _prepare_config_file(self, config: TerraformDocsConfig) -> Optional[Path]:
        """Prepare terraform-docs configuration file."""
        try:
            # Use provided config file if it exists
            if config.config_file and config.config_file.is_file():
                self.logger.debug(f"Using custom config file: {config.config_file}")
                return config.config_file

            # Get content for the specified mood
            content = self.content_provider.get_content(config.mood)
            if not content:
                self.logger.error(f"Invalid documentation type: {config.mood}")
                return None

            # Write temporary config file
            self.temp_config_path.write_text(content)
            return self.temp_config_path

        except Exception as e:
            self.logger.error(f"Failed to prepare config file: {e}")
            return None


class TerraformDocsContentProvider:
    """Provides content templates for terraform-docs configuration."""

    def __init__(self):
        self.content_map = {
            "resources": terraform_docs_content_resources,
            "modules": terraform_docs_content_modules,
        }

    def get_content(self, mood: str) -> Optional[str]:
        return self.content_map.get(mood)


# Usage example
def create_terraform_docs(
        directory: str | Path,
        mood: str = "resources",
        t_docs_path: Optional[str] = None,
        recursive: bool = False,
        exclude: List[str] = None,
        framework: str = "terraform-terragrunt"
) -> bool:
    """Backward-compatible function for generating Terraform documentation."""
    logger = logging.getLogger("TerraformDocs")
    #logger.setLevel(level = logging.INFO,  )
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)

    # Initialize the file scanner
    file_scanner = FileScanner(
        exclude_patterns=exclude,
        max_workers=4
    )
    print(f"{Fore.YELLOW}The framework is: {framework}")
    if mood== "resources":
        if framework.lower() in ["terraform-terragrunt", "terragrunt" ]:
            result = graph_dependencies(
                directory=Path(directory).absolute(),
                suffix="resources",
            )

            if result and result.success:
                logging.debug(f"Graph generated successfully at: {result.path}")
                # Access other result properties if needed
                if result.content:
                    logging.debug("Graph content available")
                    # Example with basic recursive usage
            graph_dependencies_recursive(
                directory=Path(directory).absolute(),
                suffix="stacks",
                exclude_patterns=exclude,
                max_workers=4
            )

            if framework.lower() == 'terragrunt':
                terragrunt_info_generator = TerragruntInfoGenerator(logger)
                # Generate .info.md files for terragrunt
                def process_terragrunt_file(file_path: Path) -> bool:
                    if file_path.name == 'terragrunt.hcl':
                        return terragrunt_info_generator.generate_info_file(file_path)
                    return False

                # Scan and process terragrunt files
                stats = file_scanner.scan_and_process(
                    directory=Path(directory),
                    pattern="terragrunt.hcl",
                    recursive=True,
                    processor=process_terragrunt_file
                )
                if result:  # If terraform docs generation was successful
                    print(f"{Fore.GREEN}✨  Documentation generated successfully{Fore.RESET}")
                    print(f"{Fore.GREEN}✨  Generated .info.md files: {stats['processed']} {Fore.RESET}")
                    if stats['failed'] > 0:
                        print(f"{Fore.YELLOW}Failed to generate some .info.md files: {stats['failed']}{Fore.RESET}")

                else:
                    print(f"{Fore.RED}Failed to generate documentation{Fore.RESET}")


    generator = TerraformDocsGenerator(
        executor=SubprocessExecutor(),
        logger=logger,
        content_provider=TerraformDocsContentProvider()
    )

    config = TerraformDocsConfig(
        directory=Path(directory).absolute(),
        mood=mood,
        config_file=Path(t_docs_path).absolute() if t_docs_path else None,
        recursive=recursive,
        exclude_patterns=exclude or [],
        framework= framework
    )

    result_docs = generator.generate(config)
    if result_docs.success:
        print(f"{Fore.GREEN}✨  Documentation generated successfully{Fore.RESET}")
        print(f"{Fore.GREEN}✨  Processed directories: {len(result_docs.processed_dirs)} {Fore.RESET}")
        if result_docs.skipped_dirs:
            print(f"{Fore.YELLOW} ✨ Skipped directories: {len(result_docs.skipped_dirs)}")
    else:
        print(f"{Fore.RED}Failed to generate documentation: {result_docs.error}{Fore.RESET}")

    return result_docs.success


