import logging
import queue
import re
import subprocess
import threading
import time
import os
import signal
import select
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
        self.current_process_pid = None

    def _create_display(self) -> Group:
        """Create the display group with spinner and messages."""
        return Group(self.spinner, *self.messages)

    def start_scan_message(self, directory: str):
        """Display scan start message."""
        rprint(f"[green]👓 Running {self.tool_name} scan in {directory}[/green]")

    def show_error(self, message: str):
        """Display error message."""
        rprint(f"[red]✗ {message}[/red]")

    def show_warning(self, message: str):
        """Display warning message."""
        rprint(f"[yellow]⚠️ {message}[/yellow]")
        
    def show_info(self, message: str):
        """Display info message."""
        rprint(f"[blue]ℹ️ {message}[/blue]")

    def show_success(self, message: str = "Scan completed successfully"):
        """Display success message."""
        rprint(f"[green]✓ {message}[/green]")

    def _write_report(self, report_path: Path):
        """Write collected report content to file."""
        if self.messages:
            with open(report_path, "w") as f:
                for message in self.messages:
                    f.write(message.plain + "\n")

    def _kill_process_by_pid(self, pid):
        """Forcibly kill a process by PID."""
        try:
            os.kill(pid, signal.SIGKILL)
            self.logger.debug(f"Forcibly killed process with PID {pid}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to kill process with PID {pid}: {e}")
            return False

    def run_with_progress(
        self,
        cmd: List[str],
        reports_path: Path,
        report_filename: str,
        additional_processors: Optional[Dict[str, Callable]] = None,
        timeout: Optional[int] = 600,  # Increased to 10 minutes
    ) -> Dict[str, str]:
        """
        Run command with progress display and real-time output.

        Args:
            cmd: Command to execute
            reports_path: Path to reports directory
            report_filename: Name of the report file
            additional_processors: Optional dict of additional message type processors
            timeout: Optional timeout in seconds for the entire process
        """
        output_queue = queue.Queue()
        report_path = reports_path / report_filename
        process = None
        process_started = False
        self.current_process_pid = None
        
        # Add a watchdog thread to monitor for hangs
        def watchdog():
            self.logger.debug("Watchdog thread started")
            start_time = time.time()
            last_activity_time = start_time
            
            while True:
                time.sleep(10)  # Check every 10 seconds
                
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                # Check if total timeout has been reached
                if timeout and elapsed_time > timeout:
                    self.logger.error(f"WATCHDOG: Total timeout of {timeout} seconds reached")
                    self.show_error(f"Process timed out after {timeout} seconds")
                    
                    # Kill the process if it exists
                    if self.current_process_pid:
                        self._kill_process_by_pid(self.current_process_pid)
                    
                    # Force exit if necessary
                    try:
                        os._exit(1)
                    except:
                        pass
                    return
                
                # Check if there's been activity in the last 60 seconds
                if not output_queue.empty():
                    last_activity_time = current_time
                elif current_time - last_activity_time > 60:
                    self.logger.warning("WATCHDOG: No activity for 60 seconds")
                    
                    # After 120 seconds of inactivity, kill the process
                    if current_time - last_activity_time > 600:
                        self.logger.error("WATCHDOG: No activity for 120 seconds, killing process")
                        self.show_error("Process appears to be stuck - no activity for 120 seconds")
                        
                        # Kill the process if it exists
                        if self.current_process_pid:
                            self._kill_process_by_pid(self.current_process_pid)
                        
                        # Force exit if necessary
                        try:
                            os._exit(1)
                        except:
                            pass
                        return
                
                # Exit if process has completed
                if not process_started or (process and process.poll() is not None):
                    return
                
        # Start the watchdog thread
        watchdog_thread = threading.Thread(target=watchdog)
        watchdog_thread.daemon = True
        watchdog_thread.start()

        try:
            # Start the scan process
            self.logger.debug(f"Starting process with command: {' '.join(cmd)}")
            
            # Use Popen directly here so we can get the PID
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            
            self.current_process_pid = process.pid
            process_started = True
            
            self.logger.debug(f"Process started with PID: {process.pid}")

            # Set up polling for stdout and stderr
            stdout_poll = select.poll()
            stdout_poll.register(process.stdout, select.POLLIN)
            
            stderr_poll = select.poll()
            stderr_poll.register(process.stderr, select.POLLIN)
            
            # Monitor progress with timeout
            start_time = time.time()
            last_output_time = start_time
            last_progress_update = start_time
            
            with Live(self._create_display(), refresh_per_second=10) as live:
                while process.poll() is None:
                    # Check stdout
                    if stdout_poll.poll(100):  # 100ms timeout
                        line = process.stdout.readline()
                        if line:
                            last_output_time = time.time()
                            self.logger.debug(f"STDOUT: {line.strip()}")
                            output_queue.put(("output", line.strip()))
                    
                    # Check stderr
                    if stderr_poll.poll(100):  # 100ms timeout
                        line = process.stderr.readline()
                        if line:
                            last_output_time = time.time()
                            self.logger.debug(f"STDERR: {line.strip()}")
                            output_queue.put(("error", line.strip()))
                    
                    # Process any messages in the queue
                    while not output_queue.empty():
                        try:
                            msg_type, content = output_queue.get_nowait()
                            
                            # Handle message based on type
                            if msg_type == "output":
                                self._handle_output(content, live)
                            elif msg_type == "error":
                                self._handle_error(content, live)
                            elif msg_type == "status":
                                self._handle_status(content, live)
                            elif msg_type == "warning":
                                self.logger.warning(content)
                                message = Text(f"⚠️  {content}", style="yellow")
                                self.messages.append(message)
                                live.update(self._create_display())
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
                                    self.logger.error(f"Exception in process: {content}")
                                    raise Exception(content)

                            # Handle additional message types
                            if additional_processors and msg_type in additional_processors:
                                additional_processors[msg_type](content)
                        except queue.Empty:
                            break
                    
                    # Show progress update every 30 seconds
                    current_time = time.time()
                    if current_time - last_progress_update > 30:
                        elapsed = int(current_time - start_time)
                        progress_msg = f"Scan in progress... ({elapsed} seconds elapsed)"
                        self.logger.debug(progress_msg)
                        output_queue.put(("status", progress_msg))
                        last_progress_update = current_time
                    
                    # Check for inactivity
                    if current_time - last_output_time > 60:  # 60 seconds with no output
                        self.logger.warning(f"No output for 60 seconds, process may be stuck")
                        output_queue.put(("warning", f"No output for 60 seconds, process may be stuck"))
                        
                        # After 120 seconds of no output, kill the process
                        if current_time - last_output_time > 120:  # 2 minutes
                            self.logger.error(f"No output for 120 seconds, killing process")
                            self.show_error("Process appears to be stuck - no output for 120 seconds")
                            process.kill()
                            break
                    
                    time.sleep(0.1)  # Short sleep to prevent CPU spinning
            
            # Process has completed, read any remaining output
            for line in process.stdout:
                self.logger.debug(f"STDOUT: {line.strip()}")
                output_queue.put(("output", line.strip()))
            
            for line in process.stderr:
                self.logger.debug(f"STDERR: {line.strip()}")
                output_queue.put(("error", line.strip()))
            
            # Process any remaining messages in the queue
            while not output_queue.empty():
                try:
                    msg_type, content = output_queue.get_nowait()
                    if msg_type == "output":
                        self._handle_output(content, None)
                    elif msg_type == "error":
                        self._handle_error(content, None)
                except queue.Empty:
                    break

            # Check return code
            return_code = process.poll()
            self.logger.debug(f"Process completed with return code: {return_code}")
            
            if return_code != 0:
                self.logger.error(f"Process failed with return code {return_code}")
                self.show_error(f"Process failed with return code {return_code}")
                return {
                    "status": "FAIL",
                    "error": f"Command failed with return code {return_code}",
                }

            # Write report
            self._write_report(report_path)

            self.show_success()
            return {"status": "COMPLETE", "report_path": str(report_path)}

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Scan failed with return code {e.returncode}")
            self.show_error(f"Scan failed with return code {e.returncode}")
            return {
                "status": "FAIL",
                "error": f"Command failed with return code {e.returncode}",
            }
        except Exception as e:
            self.logger.error(f"Scan failed: {str(e)}", exc_info=True)
            self.show_error(f"Scan failed: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
        finally:
            # Make sure to clean up the process if it's still running
            if process and process.poll() is None:
                try:
                    process.kill()
                    self.logger.debug("Killed lingering process")
                except:
                    pass

    def _handle_output(self, content: str, live: Optional[Live]):
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

        # Update live display if available
        if live:
            live.update(self._create_display())

    def _handle_error(self, content: str, live: Optional[Live]):
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
        
        # Update live display if available
        if live:
            live.update(self._create_display())

    def _handle_status(self, content: str, live: Optional[Live]):
        """Handle status message type."""
        message = Text(content, style="green")
        self.messages.append(message)
        
        # Update live display if available
        if live:
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
