from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, List
import logging
import subprocess
import os
from colorama import Fore, init
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
    exclude_patterns: List[str] = None
    framework: str = "terraform-terragrunt"


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

            # Prepare configuration file
            config_file = self._prepare_config_file(config)
            if not config_file:
                return DocsResult(
                    success=False,
                    error="Failed to prepare configuration file"
                )

            processed_dirs = []
            skipped_dirs = []

            if config.recursive:
                self._generate_recursive(
                    config.directory,
                    config_file,
                    processed_dirs,
                    skipped_dirs,
                    config.exclude_patterns or []
                )
            else:
                self.logger.debug(f"Generating documentation for: {config.directory}")
                success = self._generate_for_directory(config.directory, config_file)
                if success:
                    processed_dirs.append(config.directory)

                else:
                    logging.debug(f"Failed to generate documentation for: {config.directory}")
                    skipped_dirs.append(config.directory)

            return DocsResult(
                success=len(processed_dirs) > 0,
                processed_dirs=processed_dirs,
                skipped_dirs=skipped_dirs
            )

        except Exception as e:
            self.logger.error("Failed to generate documentation: %s", e)
            return DocsResult(success=False, error=str(e))

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
            # Process all directories recursively using os.walk
            for current_dir, dirs, files in os.walk(directory):
                current_path = Path(current_dir).resolve()

                # Skip if already processed
                if current_path in self.processed_directories:
                    continue

                # Add to processed set
                self.processed_directories.add(current_path)

                # Filter out directories to skip
                dirs[:] = [d for d in dirs
                           if not d.startswith('.')
                           and d not in exclude_patterns
                           and not any(pattern in d for pattern in exclude_patterns)]

                # Check if directory should be excluded
                if any(pattern in str(current_path) for pattern in exclude_patterns):
                    self.logger.debug(f"Skipping excluded directory: {current_path}")
                    skipped_dirs.append(current_path)
                    continue

                # Check for Terraform files in current directory
                has_terraform = False
                for ext in ["*.tf", "*.hcl"]:
                    if list(current_path.glob(ext)):
                        has_terraform = True
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

        except Exception as e:
            self.logger.error(f"Error processing directory {directory}: {e}")
            skipped_dirs.append(directory)

    def _generate_for_directory(self, directory: Path, config_file: Path) -> bool:
        """Generate documentation for a single directory."""
        try:
            if  self._validate_directory(directory):
               # return False
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

    def _validate_directory(self, directory: Path) -> tuple[bool, str]:
        """
            Validate directory based on presence of Terraform (.tf) and/or Terragrunt (.hcl) files.

            Valid configurations:
            1. Has both .tf and .hcl files (Complete configuration)
            2. Has only .tf files (Terraform-only configuration)
            3. Has only .hcl files (Terragrunt-only configuration)

            Invalid configurations:
            1. No .tf and no .hcl files (Empty configuration)

            Args:
                directory (Path): Directory to check
            Returns:
                tuple[bool, str]: (is_valid, reason)
            """
        try:
            has_tf = has_hcl = False

            # Single directory scan for efficiency
            for file in directory.iterdir():
                if file.is_file():
                    if file.suffix == '.tf':
                        has_tf = True
                    elif file.suffix == '.hcl':
                        has_hcl = True
                    if has_tf and has_hcl:  # Found both types
                        return True, "Complete configuration (Terraform + Terragrunt)"

            # Evaluate what was found
            if has_tf:
                self.logger.debug(f"Found Terraform-only configuration in {directory}")
                return True, "Terraform-only configuration"
            elif has_hcl:
                self.logger.debug(f"Found Terragrunt-only configuration in {directory}")
                return True, "Terragrunt-only configuration"
            else:
                self.logger.debug(f"No valid configuration files found in {directory}")
                return False, "No configuration files found"

        except Exception as e:
            error_msg = f"Error validating directory {directory}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg


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
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)

    # Initialize the file scanner
    file_scanner = FileScanner(
        exclude_patterns=exclude,
        max_workers=4
    )
    if framework.lower() in ["terraform-terragrunt", "terragrunt" ]:
        result = graph_dependencies(
            directory=Path(directory).absolute(),
            suffix="resources",
        )

        if result and result.success:
            print(f"Graph generated successfully at: {result.path}")
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
                print(f"{Fore.GREEN} ✨  Documentation generated successfully{Fore.RESET}")
                print(f"{Fore.GREEN} ✨  Generated .info.md files: {stats['processed']} {Fore.RESET}")
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
        print(f"{Fore.GREEN} ✨  Documentation generated successfully{Fore.RESET}")
        print(f"{Fore.GREEN} ✨  Processed directories: {len(result_docs.processed_dirs)} {Fore.RESET}")
        if result_docs.skipped_dirs:
            print(f"{Fore.YELLOW} ✨ Skipped directories: {len(result_docs.skipped_dirs)}")
    else:
        print(f"{Fore.RED}Failed to generate documentation: {result_docs.error}{Fore.RESET}")

    return result_docs.success


