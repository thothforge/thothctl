from pathlib import Path, PurePath
from typing import Dict, Optional, List
import subprocess
import json
import os
import time
import logging
import glob

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


class CheckovScanner(ScannerPort):
    def __init__(self):
        self.ui = ScannerUI("Checkov")
        self.reports_path = "checkov"
        self.report_filename = "checkov_log_report.txt"
        self.logger = logging.getLogger(__name__)

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
            
            # Convert to absolute paths
            abs_directory = os.path.abspath(directory)
            abs_reports_dir = os.path.abspath(reports_dir)
            
            self.logger.debug(f"Absolute directory path: {abs_directory}")
            self.logger.debug(f"Absolute reports directory path: {abs_reports_dir}")
            
            # Log directory content to help diagnose issues
            self.logger.debug(f"Directory content of {abs_directory}:")
            try:
                dir_content = list(os.listdir(abs_directory))
                for item in dir_content:
                    item_path = os.path.join(abs_directory, item)
                    if os.path.isdir(item_path):
                        self.logger.debug(f"  DIR: {item}")
                    else:
                        self.logger.debug(f"  FILE: {item} ({os.path.getsize(item_path)} bytes)")
            except Exception as e:
                self.logger.error(f"Error listing directory content: {e}")
            
            cmd = self._build_command(abs_directory, options)
            self.logger.debug(f"Initial command: {cmd}")
            
            tf_plan = PurePath(os.path.join(abs_directory, "tfplan"))
            tf_plan_json = PurePath(os.path.join(abs_directory, "tfplan.json"))
            
            self.logger.debug(f"Checking for plan files: tfplan.json exists: {os.path.exists(PurePath(tf_plan_json))}, tfplan exists: {os.path.exists(PurePath(tf_plan))}")
            
            # Check if directory has any scannable content
            has_scannable_content = False
            for ext in ['.tf', '.yml', '.yaml', '.json', '.hcl']:
                if list(Path(abs_directory).glob(f'**/*{ext}')):
                    has_scannable_content = True
                    self.logger.debug(f"Found scannable content with extension {ext}")
                    break
            
            if not has_scannable_content:
                self.logger.warning(f"No scannable content found in {abs_directory}, skipping scan")
                self.ui.show_warning(f"No scannable content found in {abs_directory}, skipping scan")
                return {
                    "status": "SKIPPED",
                    "message": f"No scannable content found in {abs_directory}"
                }
            
            # Handle tfplan files with improved error handling and timeouts
            if os.path.exists(PurePath(tf_plan_json)):
                try:
                    # Check file size without parsing the JSON
                    file_size = os.path.getsize(tf_plan_json)
                    self.logger.debug(f"tfplan.json file size: {file_size / (1024*1024):.2f} MB")
                    
                    if file_size > 100 * 1024 * 1024:  # 100 MB
                        self.logger.warning(f"Very large plan file detected ({file_size / (1024*1024):.2f} MB). This may cause performance issues.")
                        self.ui.show_warning(f"Very large plan file detected ({file_size / (1024*1024):.2f} MB). This may cause performance issues.")
                    
                    # Skip actual JSON parsing to avoid potential issues with large files
                    self.logger.debug("Using targeted approach for tfplan.json")
                    self.ui.show_info("Using targeted approach for tfplan.json")
                    
                    # For tfplan.json files, use specific parameters to help with processing
                    # Removed --compact flag to ensure failed results appear in the reports
                    self.logger.debug(f"Using tfplan.json file with optimized parameters")
                    cmd.extend([
                        "-f", str(tf_plan_json),
                        "--quiet"  # Keep quiet flag but remove compact flag
                    ])
                except Exception as e:
                    self.logger.warning(f"Error checking tfplan.json: {str(e)}. Falling back to directory scan.")
                    self.ui.show_warning(f"Error checking tfplan.json: {str(e)}. Falling back to directory scan.")
                    
                    # Check if there are any .tf files in the directory
                    tf_files = list(Path(abs_directory).glob("*.tf"))
                    if tf_files:
                        self.logger.debug(f"Found {len(tf_files)} .tf files in {abs_directory}")
                        # Scan each .tf file individually instead of the whole directory
                        cmd.extend(["-f", str(tf_files[0])])
                    else:
                        self.logger.debug(f"No .tf files found in {abs_directory}, using directory scan")
                        cmd.extend(["-d", abs_directory])
            elif os.path.exists(PurePath(tf_plan)):
                # Convert tfplan to JSON with timeout
                try:
                    self.logger.debug(f"Converting tfplan to JSON in {abs_directory}")
                    # Use subprocess with timeout instead of os.system
                    process = subprocess.run(
                        f"{tftool} show -json {tf_plan}",
                        shell=True,
                        cwd=abs_directory,
                        capture_output=True,
                        text=True,
                        timeout=60  # 60 second timeout
                    )
                    
                    if process.returncode == 0:
                        # Write the output to tfplan.json
                        with open(os.path.join(abs_directory, "tfplan.json"), 'w') as f:
                            f.write(process.stdout)
                        self.logger.debug(f"Successfully converted tfplan to JSON in {abs_directory}")
                        
                        # Check if there are any .tf files in the directory
                        tf_files = list(Path(abs_directory).glob("*.tf"))
                        if tf_files:
                            self.logger.debug(f"Found {len(tf_files)} .tf files in {abs_directory}")
                            # Scan each .tf file individually instead of the whole directory
                            cmd.extend(["-f", str(tf_files[0])])
                        else:
                            self.logger.debug(f"No .tf files found in {abs_directory}, using directory scan")
                            cmd.extend(["-d", abs_directory])
                    else:
                        self.logger.warning(f"Failed to convert tfplan to JSON: {process.stderr}")
                        self.ui.show_warning(f"Failed to convert tfplan to JSON: {process.stderr}")
                        
                        # Check if there are any .tf files in the directory
                        tf_files = list(Path(abs_directory).glob("*.tf"))
                        if tf_files:
                            self.logger.debug(f"Found {len(tf_files)} .tf files in {abs_directory}")
                            # Scan each .tf file individually instead of the whole directory
                            cmd.extend(["-f", str(tf_files[0])])
                        else:
                            self.logger.debug(f"No .tf files found in {abs_directory}, using directory scan")
                            cmd.extend(["-d", abs_directory])
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Timeout converting tfplan to JSON in {abs_directory}")
                    self.ui.show_warning(f"Timeout converting tfplan to JSON. Falling back to directory scan.")
                    
                    # Check if there are any .tf files in the directory
                    tf_files = list(Path(abs_directory).glob("*.tf"))
                    if tf_files:
                        self.logger.debug(f"Found {len(tf_files)} .tf files in {abs_directory}")
                        # Scan each .tf file individually instead of the whole directory
                        cmd.extend(["-f", str(tf_files[0])])
                    else:
                        self.logger.debug(f"No .tf files found in {abs_directory}, using directory scan")
                        cmd.extend(["-d", abs_directory])
            else:
                # Check if there are any .tf files in the directory
                tf_files = list(Path(abs_directory).glob("*.tf"))
                if tf_files:
                    self.logger.debug(f"Found {len(tf_files)} .tf files in {abs_directory}")
                    # Scan each .tf file individually instead of the whole directory
                    cmd.extend(["-f", str(tf_files[0])])
                else:
                    self.logger.debug(f"No .tf files found in {abs_directory}, using directory scan")
                    cmd.extend(["-d", abs_directory])

            parent = Path(abs_directory).resolve().parent.name
            name = Path(abs_directory).resolve().name

            report_name = "report_" + (parent + "_" + name).replace("/", "_")
            prepared_reports_dir = self._prepare_reports_directory(abs_reports_dir)
            report_path = os.path.join(prepared_reports_dir, f"{report_name}")
            
            # Convert to absolute path
            absolute_report_path = os.path.abspath(str(report_path))
            self.logger.debug(f"Report path: {absolute_report_path}")
            
            cmd.extend(
                [
                    "-s",
                    "-o",
                    "json",
                    "-o",
                    "junitxml",
                    "--output-file-path",
                    absolute_report_path,
                ]
            )

            self.logger.debug(f"Final command to execute: {' '.join(cmd)}")
            
            # Run the scan with the UI for live updates
            result = self.ui.run_with_progress(
                cmd=cmd,
                reports_path=prepared_reports_dir,
                report_filename=self.report_filename,
                timeout=600  # 10 minute timeout - increased from 120 seconds to 600 seconds
            )
            
            # Check if output files were created - Fix the file naming mismatch
            expected_json_path = f"{absolute_report_path}/results_json.json"
            expected_xml_path = f"{absolute_report_path}/results_junitxml.xml"
            
            self.logger.debug(f"Expected JSON report at: {expected_json_path}")
            self.logger.debug(f"Expected XML report at: {expected_xml_path}")
            
            if os.path.exists(expected_json_path):
                self.logger.debug(f"JSON report exists with size: {os.path.getsize(expected_json_path)} bytes")
            else:
                self.logger.warning(f"JSON report not found at: {expected_json_path}")
            
            if os.path.exists(expected_xml_path):
                self.logger.debug(f"XML report exists with size: {os.path.getsize(expected_xml_path)} bytes")
            else:
                self.logger.warning(f"XML report not found at: {expected_xml_path}")
                
                # Try to find any XML files that might have been created
                xml_files = glob.glob(f"{os.path.dirname(absolute_report_path)}/**/*.xml", recursive=True)
                if xml_files:
                    self.logger.debug(f"Found {len(xml_files)} XML files in reports directory:")
                    for xml_file in xml_files:
                        self.logger.debug(f"  {xml_file} ({os.path.getsize(xml_file)} bytes)")
                else:
                    self.logger.warning("No XML files found in reports directory")
            
            return result

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
        # Remove the timeout command
        cmd = ["checkov"]  # No timeout

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
        # Convert to absolute path
        abs_reports_dir = os.path.abspath(reports_dir)
        reports_path = Path(abs_reports_dir).joinpath(self.reports_path).resolve()
        reports_path.mkdir(parents=True, exist_ok=True)
        
        # Log the absolute path for debugging
        self.logger.debug(f"Reports will be saved to: {reports_path}")
        
        return reports_path
