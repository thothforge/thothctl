import logging
import queue
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from rich import print as rprint
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text


class ScannerUI:
    """Reusable UI components for scanners using Rich."""

    def __init__(self, tool_name: str):
        self.console = Console()
        self.tool_name = tool_name
        self.spinner = Spinner("dots", text=" 🚥 Scanning...")
        self.report_content: List[str] = []
        self.messages: List[Text] = []  # Store messages as Text objects
        self.logger = logging.getLogger(__name__)

    def _create_display(self) -> Group:
        """Create the display group with spinner and messages."""
        return Group(self.spinner, *self.messages)

    def start_scan_message(self, directory: str):
        """Display scan start message."""
        rprint(f"[green]👓 Running {self.tool_name} scan in {directory}[/green]")

    def show_error(self, message: str):
        """Display error message."""
        rprint(f"[red]✗ {message}[/red]")

    def show_success(self, message: str = "Scan completed successfully"):
        """Display success message."""
        rprint(f"[green]✓ {message}[/green]")

    def _write_report(self, report_path: Path):
        """Write collected report content to file."""
        if self.messages:
            with open(report_path, "w") as f:
                for message in self.messages:
                    f.write(message.plain + "\n")

    def run_with_progress(
        self,
        cmd: List[str],
        reports_path: Path,
        report_filename: str,
        additional_processors: Optional[Dict[str, Callable]] = None,
    ) -> Dict[str, str]:
        """
        Run command with progress display and real-time output.

        Args:
            cmd: Command to execute
            reports_path: Path to reports directory
            report_filename: Name of the report file
            additional_processors: Optional dict of additional message type processors
        """
        output_queue = queue.Queue()
        report_path = reports_path / report_filename

        try:
            # Start the scan process
            scan_thread = threading.Thread(
                target=self._run_process, args=(cmd, output_queue)
            )
            scan_thread.start()

            # Monitor progress and collect output
            self._monitor_progress(scan_thread, output_queue, additional_processors)

            # Write report
            self._write_report(report_path)

            self.show_success()
            return {"status": "COMPLETE", "report_path": str(report_path)}

        except subprocess.CalledProcessError as e:
            self.show_error(f"Scan failed with return code {e.returncode}")
            return {
                "status": "FAIL",
                "error": f"Command failed with return code {e.returncode}",
            }
        except Exception as e:
            self.show_error(f"Scan failed: {str(e)}")
            return {"status": "FAIL", "error": str(e)}

    def _run_process(self, cmd: List[str], output_queue: queue.Queue):
        """Run the process and put output in queue."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Handle stdout
            for line in process.stdout:
                output_queue.put(("output", line.strip()))

            # Handle stderr
            for line in process.stderr:
                output_queue.put(("error", line.strip()))

            process.wait()
            if process.returncode != 0:
                output_queue.put(
                    (
                        "exception",
                        f"Process failed with return code {process.returncode}",
                    )
                )

        except Exception as e:
            output_queue.put(("exception", str(e)))

    def _monitor_progress(
        self,
        scan_thread: threading.Thread,
        output_queue: queue.Queue,
        additional_processors: Optional[Dict[str, Callable]] = None,
    ):
        """Monitor scan progress and update display."""
        with Live(self._create_display(), refresh_per_second=10) as live:
            while scan_thread.is_alive() or not output_queue.empty():
                try:
                    msg_type, content = output_queue.get_nowait()

                    # Handle message based on type
                    if msg_type == "output":
                        self._handle_output(content, live)
                    elif msg_type == "error":
                        self._handle_error(content, live)
                    elif msg_type == "status":
                        self._handle_status(content, live)
                    elif msg_type == "exception":
                        warning_patterns = [
                            r".*\[WARNI\].*Failed to download module.*",
                            r".*\[WARNI\].*",
                        ]
                        is_warning = any(
                            re.search(pattern, content) for pattern in warning_patterns
                        )

                        if is_warning:
                            self.logger.warning(content)
                            message = Text(f"⚠️  {content}", style="yellow")
                            self.messages.append(message)
                            live.update(self._create_display())
                        else:
                            raise Exception(content)

                    # Handle additional message types
                    if additional_processors and msg_type in additional_processors:
                        additional_processors[msg_type](content)

                except queue.Empty:
                    continue

    def _handle_output(self, content: str, live: Live):
        """Handle output message type."""
        warning_patterns = [
            r".*\[WARNI\].*Failed to download module.*",
            r".*\[WARNI\].*",  # General warning pattern
        ]

        is_warning = any(re.search(pattern, content) for pattern in warning_patterns)

        if is_warning:
            self.logger.warning(content)
            message = Text(f"⚠️  {content}", style="yellow")
            self.messages.append(message)
        else:
            self.logger.debug(content)
            # message = Text(content, style="blue")

        # self.messages.append(message)
        live.update(self._create_display())

    def _handle_error(self, content: str, live: Live):
        """Handle error message type."""
        warning_patterns = [
            r".*\[WARNI\].*Failed to download module.*",
            r".*\[WARNI\].*",
        ]

        is_warning = any(re.search(pattern, content) for pattern in warning_patterns)

        if is_warning:
            self.logger.warning(content)
            message = Text(f"⚠️  {content}", style="yellow")
        else:
            self.logger.error(content)
            message = Text(f"❌ {content}", style="red")

        self.messages.append(message)
        live.update(self._create_display())

    def _handle_status(self, content: str, live: Live):
        """Handle status message type."""
        message = Text(content, style="green")
        self.messages.append(message)
        live.update(self._create_display())


class CliUI:
    """CLI user interface helper."""

    def __init__(self):
        """Initialize CLI UI."""
        self.console = Console()

    def status_spinner(self, message: str):
        """Create a status spinner context."""
        return self.console.status(message, spinner="dots")

    def print_success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"✅ {message}", style="green")

    def print_error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"❌ {message}", style="red")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"⚠️ {message}", style="yellow")

    def print_info(self, message: str) -> None:
        """Print info message."""
        self.console.print(f"ℹ️ {message}", style="blue")
