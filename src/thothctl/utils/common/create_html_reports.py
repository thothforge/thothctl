import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Literal

from rich import print as rprint


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    BANNER_URL: str = "https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png"
    FAVICON_URL: str = "https://support.content.office.net/en-us/media/b2c496ff-a74d-4dd8-834e-9e414ede8af0.png"


class HTMLReportGenerator:
    """Handles HTML report generation from XML files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = ReportConfig()

    def _find_xml_files(self, directory: Path) -> Generator[Path, None, None]:
        """
        Recursively find all XML files in directory and its subdirectories.

        Args:
            directory: Root directory to search

        Yields:
            Path objects for each XML file found
        """
        try:
            # Recursively search for all .xml files
            return directory.rglob("*.xml")
        except Exception as e:
            self.logger.error(f"Error searching for XML files: {e}")
            raise

    def _convert_with_junit2html(self, xml_path: Path) -> None:
        """Convert XML to HTML using junit2html."""
        try:
            html_path = xml_path.with_suffix(".html")
            cmd = ["junit2html", str(xml_path), str(html_path)]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.debug(
                f"Successfully converted {xml_path.name} using junit2html"
            )
            rprint(
                f"[green]✓ Converted {xml_path.relative_to(xml_path.parent.parent)}[/green]"
            )

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"junit2html conversion failed for {xml_path.name}: {e.stderr}"
            )
            rprint(
                f"[red]✗ Failed to convert {xml_path.relative_to(xml_path.parent.parent)}: {e.stderr}[/red]"
            )
            raise

    def _convert_with_xunit(self, xml_path: Path) -> None:
        """Convert XML to HTML using xunit-viewer."""
        try:
            html_path = xml_path.with_suffix(".html")
            cmd = [
                "xunit-viewer",
                "-r",
                str(xml_path),
                "-o",
                str(html_path),
                "-b",
                self.config.BANNER_URL,
                "-t",
                f"thothctl-{xml_path.name}",
                "-f",
                self.config.FAVICON_URL,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.debug(
                f"Successfully converted {xml_path.name} using xunit-viewer"
            )
            rprint(
                f"[green]✓ Converted {xml_path.relative_to(xml_path.parent.parent)}[/green]"
            )

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"xunit-viewer conversion failed for {xml_path.name}: {e.stderr}"
            )
            rprint(
                f"[red]✗ Failed to convert {xml_path.relative_to(xml_path.parent.parent)}: {e.stderr}[/red]"
            )
            raise

    def _convert_single_file(
        self, xml_path: Path, mode: Literal["simple", "xunit"]
    ) -> None:
        """Convert a single XML file to HTML based on the specified mode."""
        try:
            if mode == "simple":
                self._convert_with_junit2html(xml_path)
            else:  # xunit mode
                self._convert_with_xunit(xml_path)

        except Exception as e:
            self.logger.error(f"Error processing {xml_path.name}: {str(e)}")

    def _create_compact_report(self, directory: Path, xml_files: List[Path]) -> None:
        """Create a single compact report using xunit-viewer for all XML files."""
        try:
            cmd = [
                "xunit-viewer",
                "-r",
                ".",  # Use current directory recursively
                "-o",
                "CompactReport",  # Output file name
                "-b",
                self.config.BANNER_URL,
                "-t",
                "thothctl - Complete Scan Report",
                "-f",
                self.config.FAVICON_URL,
            ]

            result = subprocess.run(
                cmd,
                cwd=str(directory),  # Execute in the target directory
                capture_output=True,
                text=True,
                check=True,
            )

            self.logger.info(f"Generated unified compact report in {directory}")
            rprint(f"[green]✓ Generated unified compact report in {directory}[/green]")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate unified compact report: {e.stderr}")
            rprint(
                f"[red]✗ Failed to generate unified compact report: {e.stderr}[/red]"
            )
            raise
        except Exception as e:
            self.logger.error(f"Error generating unified compact report: {str(e)}")
            raise

    def _process_directory(self, directory: Path, mode: str) -> None:
        """Process a single directory, creating a compact report if in xunit mode."""
        if mode == "xunit":
            try:
                self._create_compact_report(directory)
            except Exception as e:
                self.logger.error(
                    f"Compact report generation failed for {directory}: {e}"
                )

    def create_html_reports(
        self, directory: str, mode: Literal["simple", "xunit"] = "simple"
    ) -> None:
        """
        Create HTML reports from XML reports in parallel, including nested directories.

        Args:
            directory: Path to directory containing XML reports
            mode: Report generation mode ("simple" for junit2html or "xunit" for xunit-viewer)
        """
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")

            rprint(f"[green]Converting Reports using {mode} mode...[/green]")
            rprint("[yellow]Scanning for XML files in all subdirectories...[/yellow]")

            # Find all XML files recursively
            xml_files = list(self._find_xml_files(dir_path))

            if not xml_files:
                self.logger.warning(
                    f"No XML files found in {directory} or its subdirectories"
                )
                rprint("[yellow]No XML files found![/yellow]")
                return

            rprint(f"[green]Found {len(xml_files)} XML files to convert[/green]")

            # If using xunit mode, create a single compact report for all XML files
            if mode == "xunit":
                self._create_compact_report(dir_path, xml_files)

            # Process all XML files in parallel
            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self._convert_single_file, xml_file, mode)
                    for xml_file in xml_files
                ]

                # Wait for all conversions to complete
                for future in futures:
                    future.result()

            rprint("[green]✓ Report conversion completed[/green]")
            rprint(f"[green]Total files processed: {len(xml_files)}[/green]")

        except Exception as e:
            self.logger.error(f"Failed to create HTML reports: {str(e)}")
            rprint(f"[red]✗ Error creating HTML reports: {str(e)}[/red]")
            raise


def create_html_reports(
    directory: str, mode: Literal["simple", "xunit"] = "simple"
) -> None:
    """
    Legacy function to maintain backwards compatibility.
    """
    generator = HTMLReportGenerator()
    generator.create_html_reports(directory, mode)
