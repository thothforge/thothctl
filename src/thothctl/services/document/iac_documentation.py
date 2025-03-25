from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, List
import logging
import subprocess
from colorama import Fore, init
from .files_content import terraform_docs_content_modules, terraform_docs_content_resources
from .iac_grunt_graph import graph_dependencies,graph_dependencies_recursive

@dataclass
class TerraformDocsConfig:
    """Configuration for Terraform documentation generation."""
    directory: Path
    mood: str = "resources"
    config_file: Optional[Path] = None
    recursive: bool = False
    exclude_patterns: List[str] = None


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
            # Convert to absolute path for consistent comparison
            abs_dir = directory.resolve()

            # Skip if already processed
            if abs_dir in self.processed_directories:
                return

            # Add to processed set
            self.processed_directories.add(abs_dir)

            # Check if directory should be excluded
            if any(pattern in str(abs_dir) for pattern in exclude_patterns):
                self.logger.debug(f"Skipping excluded directory: {abs_dir}")
                skipped_dirs.append(abs_dir)
                return

            # Check for Terraform files
            has_terraform = any(abs_dir.glob("*.tf"))

            if has_terraform:
                self.logger.debug(f"Generating documentation for: {abs_dir}")
                success = self._generate_for_directory(abs_dir, config_file)
                if success:
                    processed_dirs.append(abs_dir)
                else:
                    skipped_dirs.append(abs_dir)

            # Recursively process subdirectories
            for subdir in abs_dir.iterdir():
                if (subdir.is_dir() and
                        not subdir.name.startswith('.') and
                        not subdir.name in ['modules', '.terraform']):  # Skip common directories to ignore
                    self._generate_recursive(
                        subdir,
                        config_file,
                        processed_dirs,
                        skipped_dirs,
                        exclude_patterns
                    )

        except Exception as e:
            self.logger.error(f"Error processing directory {directory}: {e}")
            skipped_dirs.append(directory)

    def _generate_for_directory(self, directory: Path, config_file: Path) -> bool:
        """Generate documentation for a single directory."""
        try:
            if not self._validate_directory(directory):
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
        """Validate that the directory contains Terraform files."""
        try:
            terraform_files = list(directory.glob("*.tf"))
            if not terraform_files:
                self.logger.debug(f"No Terraform files found in {directory}")
                return False
            terragrunt_files = list(directory.glob("*.hcl"))
            if not terragrunt_files:
                self.logger.debug(f"No Terragrunt files found in {directory}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Failed to validate directory: {e}")
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
        exclude: List[str] = None
) -> bool:
    """Backward-compatible function for generating Terraform documentation."""
    logger = logging.getLogger("TerraformDocs")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    # Example with all options
    result = graph_dependencies(
        directory=Path(directory).absolute(),
        suffix="resources",
        #project_root=Path("/path/to/project/root"),
        #replace_path=Path("/path/to/replace")
    )

    if result and result.success:
        print(f"Graph generated successfully at: {result.path}")
        # Access other result properties if needed
        if result.content:
            print("Graph content available")
            # Example with basic recursive usage
    graph_dependencies_recursive(
        directory=Path(directory).absolute(),
        suffix="stacks",
        exclude_patterns=['.terraform', '.git', ".terragrunt-cache"],
        max_workers=4
    )
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
        exclude_patterns=exclude or []
    )

    result = generator.generate(config)

    if result.success:
        print(f"{Fore.GREEN} ✨  Documentation generated successfully{Fore.RESET}")
        print(f"{Fore.GREEN} ✨  Processed directories: {len(result.processed_dirs)} {Fore.RESET}")
        if result.skipped_dirs:
            print(f"Skipped directories: {len(result.skipped_dirs)}")
    else:
        print(f"{Fore.RED}Failed to generate documentation: {result.error}{Fore.RESET}")

    return result.success
