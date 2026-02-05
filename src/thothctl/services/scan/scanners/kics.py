"""KICS scanner implementation using Docker."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


class KICSScanner(ScannerPort):
    """KICS scanner using Docker container."""
    
    def __init__(self):
        self.ui = ScannerUI("KICS")
        self.logger = logging.getLogger(__name__)
        self.docker_image = "checkmarx/kics:latest"

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """
        Execute KICS scan using Docker.
        
        Note: Requires Docker to be installed and running.
        """
        try:
            # Check Docker availability
            if not self._check_docker():
                error_msg = (
                    "Docker is required to run KICS scanner. "
                    "Please install Docker: https://docs.docker.com/get-docker/"
                )
                self.ui.show_error(error_msg)
                raise RuntimeError(error_msg)

            self.logger.info(f"Starting KICS scan in directory: {directory}")
            self.ui.show_info(f"Starting KICS scan in directory: {directory}")

            # Convert to absolute paths
            abs_directory = str(Path(directory).resolve())
            abs_reports_dir = str(Path(reports_dir).resolve())
            
            # Create reports directory
            os.makedirs(abs_reports_dir, exist_ok=True)

            # Prepare output files
            json_output = os.path.join(abs_reports_dir, "kics-results.json")
            sarif_output = os.path.join(abs_reports_dir, "kics-results.sarif")
            
            # Build Docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{abs_directory}:/path",
                "-v", f"{abs_reports_dir}:/output",
                self.docker_image,
                "scan",
                "-p", "/path",
                "-o", "/output",
                "--report-formats", "json,sarif",
                "--output-name", "kics-results"
            ]

            # Add optional parameters
            if options:
                if options.get("exclude_paths"):
                    for exclude in options["exclude_paths"]:
                        docker_cmd.extend(["--exclude-paths", exclude])
                
                if options.get("exclude_queries"):
                    docker_cmd.extend(["--exclude-queries", options["exclude_queries"]])
                
                if options.get("include_queries"):
                    docker_cmd.extend(["--include-queries", options["include_queries"]])

            self.logger.debug(f"Running Docker command: {' '.join(docker_cmd)}")
            self.ui.show_info("Running KICS scan via Docker...")

            # Execute scan
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            # KICS exit codes: 0=no issues, 20=info, 30=low, 40=medium, 50=high, 60=critical
            if result.returncode in [0, 20, 30, 40, 50, 60]:
                self.ui.show_success("KICS scan completed")
                
                # Parse results
                findings_count = 0
                if os.path.exists(json_output):
                    with open(json_output, 'r') as f:
                        data = json.load(f)
                        findings_count = data.get("total_counter", 0)
                
                self.ui.show_info(f"Found {findings_count} issues")
                
                return {
                    "status": "success",
                    "json_report": json_output,
                    "sarif_report": sarif_output,
                    "findings": findings_count,
                    "exit_code": result.returncode
                }
            else:
                error_msg = f"KICS scan failed with exit code {result.returncode}"
                self.logger.error(f"{error_msg}\nStderr: {result.stderr}")
                self.ui.show_error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "stderr": result.stderr
                }

        except subprocess.TimeoutExpired:
            error_msg = "KICS scan timed out after 10 minutes"
            self.logger.error(error_msg)
            self.ui.show_error(error_msg)
            return {"status": "error", "error": error_msg}
        
        except Exception as e:
            error_msg = f"KICS scan failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui.show_error(error_msg)
            return {"status": "error", "error": error_msg}
