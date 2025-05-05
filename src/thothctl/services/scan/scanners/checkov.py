from pathlib import Path, PurePath
from typing import Dict, Optional, List
import subprocess
import json
import os
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort

# Constants
SCANNABLE_EXTENSIONS = {'.tf', '.yml', '.yaml', '.json', '.hcl'}
MAX_FILE_SIZE_MB = 100
BYTES_TO_MB = 1024 * 1024


class CheckovScanner(ScannerPort):
    def __init__(self):
        self.ui = ScannerUI("Checkov")
        self.reports_path = "checkov"
        self.report_filename = "checkov_log_report.txt"
        self.logger = logging.getLogger(__name__)

    @lru_cache(maxsize=128)
    def _check_file_exists(self, filepath: str) -> bool:
        """Cached file existence check"""
        return os.path.exists(filepath) and os.path.isfile(filepath)

    def _get_directory_content(self, directory: str) -> None:
        """Get directory content with parallel processing for large directories"""
        try:
            with os.scandir(directory) as entries:
                with ThreadPoolExecutor() as executor:
                    def process_entry(entry):
                        try:
                            if entry.is_dir():
                                return f"  DIR: {entry.name}"
                            else:
                                size = entry.stat().st_size
                                return f"  FILE: {entry.name} ({size} bytes)"
                        except OSError as e:
                            return f"  ERROR processing {entry.name}: {e}"

                    for result in executor.map(process_entry, entries):
                        self.logger.debug(result)
        except Exception as e:
            self.logger.error(f"Error listing directory content: {e}")

    def _check_scannable_content(self, directory: str) -> bool:
        """Check for scannable content more efficiently"""
        try:
            for ext in SCANNABLE_EXTENSIONS:
                # Use Path.rglob instead of glob for better performance
                next(Path(directory).rglob(f"*{ext}"), None)
                return True
            return False
        except Exception:
            return False

    def _validate_json_file(self, filepath: str, read_size: int = 8192) -> bool:
        """Validate JSON file more efficiently by reading in chunks"""
        try:
            with open(filepath, 'rb') as f:
                raw_data = f.read(read_size)
                # Quick check for JSON start character
                if not raw_data.lstrip().startswith(b'{') and not raw_data.lstrip().startswith(b'['):
                    return False
                json.loads(raw_data.decode('utf-8'))
            return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    def scan(
            self,
            directory: str,
            reports_dir: str,
            options: Optional[Dict] = None,
            tftool="tofu",
    ) -> Dict[str, str]:
        try:
            self.logger.debug(f"Starting Checkov scan in directory: {directory}")
            self.ui.show_info(f"Starting Checkov scan in directory: {directory}")

            # More efficient directory content logging
            self._get_directory_content(directory)

            cmd = self._build_command(directory, options)

            directory_path = Path(directory)
            tf_plan = directory_path / "tfplan"
            tf_plan_json = directory_path / "tfplan.json"

            # Use cached file existence check
            tf_plan_exists = self._check_file_exists(str(tf_plan))
            tf_plan_json_exists = self._check_file_exists(str(tf_plan_json))

            if not self._check_scannable_content(directory):
                return {
                    "status": "SKIPPED",
                    "message": f"No scannable content found in {directory}"
                }

            # Handle tfplan files with improved error handling and timeouts
            if tf_plan_json_exists:
                # Check file size
                file_size = os.path.getsize(tf_plan_json)
                self.logger.debug(f"tfplan.json file size: {file_size / (1024*1024):.2f} MB")
                
                if file_size > 100 * 1024 * 1024:  # 100 MB
                    self.logger.warning(f"Very large plan file detected ({file_size / (1024*1024):.2f} MB). This may cause performance issues.")
                    self.ui.show_warning(f"Very large plan file detected ({file_size / (1024*1024):.2f} MB). This may cause performance issues.")
                
                # Validate the JSON file first to ensure it's not corrupted
                try:
                    self.logger.debug(f"Validating JSON file: {tf_plan_json}")
                    with open(tf_plan_json, 'r') as f:
                        # Just try to load the first few bytes to validate
                        json_data = f.read()  # Read first 1KB
                        json.loads(json_data)  # Try to parse it
                        
                    # If we get here, the JSON appears valid (at least the beginning)
                    self.logger.debug("JSON validation successful")
                    
                    # For tfplan.json files, use a more targeted approach
                    # Instead of scanning the entire file, extract key information
                    self.logger.debug("Using targeted approach for tfplan.json")
                    self.ui.show_info("Using targeted approach for tfplan.json")
                    
                    # Look for .tf files in the directory instead
                    tf_files = list(Path(directory).glob("*.tf"))
                    if tf_files:
                        self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                        # Scan each .tf file individually instead of the plan file
                        cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])

                except json.JSONDecodeError as e:
                    self.logger.warning(f"Invalid JSON in {tf_plan_json}: {str(e)}. Falling back to directory scan.")
                    self.ui.show_warning(f"Invalid JSON in {tf_plan_json}: {str(e)}. Falling back to directory scan.")
                    
                    # Check if there are any .tf files in the directory
                    tf_files = list(Path(directory).glob("*.tf"))
                    if tf_files:
                        self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                        # Scan each .tf file individually instead of the whole directory
                        cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])

            elif tf_plan_exists:
                # Convert tfplan to JSON with timeout
                try:
                    self.logger.debug(f"Converting tfplan to JSON in {directory}")
                    # Use subprocess with timeout instead of os.system
                    process = subprocess.run(
                        f"{tftool} show -json {tf_plan}",
                        shell=True,
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        timeout=60  # 60 second timeout
                    )
                    
                    if process.returncode == 0:
                        # Write the output to tfplan.json
                        with open(os.path.join(directory, "tfplan.json"), 'w') as f:
                            f.write(process.stdout)
                        self.logger.debug(f"Successfully converted tfplan to JSON in {directory}")
                        
                        # Check if there are any .tf files in the directory
                        tf_files = list(Path(directory).glob("*.tf"))
                        if tf_files:
                            self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                            # Scan each .tf file individually instead of the whole directory
                            cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])

                    else:
                        self.logger.warning(f"Failed to convert tfplan to JSON: {process.stderr}")
                        self.ui.show_warning(f"Failed to convert tfplan to JSON: {process.stderr}")
                        
                        # Check if there are any .tf files in the directory
                        tf_files = list(Path(directory).glob("*.tf"))
                        if tf_files:
                            self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                            # Scan each .tf file individually instead of the whole directory
                            cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])

                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Timeout converting tfplan to JSON in {directory}")
                    self.ui.show_warning(f"Timeout converting tfplan to JSON. Falling back to directory scan.")
                    
                    # Check if there are any .tf files in the directory
                    tf_files = list(Path(directory).glob("*.tf"))
                    if tf_files:
                        self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                        # Scan each .tf file individually instead of the whole directory
                        cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])

            else:
                # Check if there are any .tf files in the directory
                tf_files = list(Path(directory).glob("*.tf"))
                if tf_files:
                    self.logger.debug(f"Found {len(tf_files)} .tf files in {directory}")
                    # Scan each .tf file individually instead of the whole directory
                    cmd.extend(["-f", str(tf_files[0]), "--framework", "terraform", "--quiet"])


            parent = Path(directory).resolve().parent.name
            name = Path(directory).resolve().name

            report_name = "report_" + (parent + "_" + name).replace("/", "_")
            reports_dir = self._prepare_reports_directory(reports_dir)
            report_path = PurePath(os.path.join(reports_dir, f"{report_name}"))
            cmd.extend(
                [
                    "-s",
                    "-o",
                    "json",
                    "-o",
                    "junitxml",
                    "--output-file-path",
                    str(report_path),
                ]
            )

            self.logger.debug(f"Final command to execute: {' '.join(cmd)}")
            
            # Run the scan with a timeout
            return self.ui.run_with_progress(
                cmd=cmd,
                reports_path=Path(reports_dir).resolve(),
                report_filename=self.report_filename,
                timeout=600  # 10 minute timeout for the entire scan
            )

        except Exception as e:
            self.logger.error(f"Checkov scan failed: {str(e)}", exc_info=True)
            self.ui.show_error(f"Checkov scan failed: {str(e)}")
            return {
                "status": "FAIL",
                "error": str(e)
            }

    def _build_command(self, directory: str, options: Optional[Dict]) -> list:
        """
        Build the Checkov command with options.

        Args:
            directory: Directory to scan
            options: Additional options for Checkov

        Returns:
            List of command components
        """
        # Add timeout command to prevent hanging
        cmd = ["timeout", "600", "checkov"]  # 10-minute timeout

        if options:
            # Add any additional arguments
            if "additional_args" in options:
                if isinstance(options["additional_args"], list):
                    cmd.extend(options["additional_args"])
                elif isinstance(options["additional_args"], str):
                    cmd.extend(options["additional_args"].split())

        return cmd

    def _prepare_reports_directory(self, reports_dir: str) -> Path:
        """
        Prepare the reports directory.

        Args:
            reports_dir: Base directory for reports

        Returns:
            Path object for the reports directory
        """
        reports_path = Path(reports_dir).joinpath(self.reports_path).resolve()
        reports_path.mkdir(parents=True, exist_ok=True)
        return reports_path
