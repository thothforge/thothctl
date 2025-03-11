import errno
import logging
import shutil
import time
from pathlib import Path
from typing import List

import os
import psutil
from rich import print as rprint
from rich.console import Console


logger = logging.getLogger(__name__)
console = Console()


class DirectoryManager:
    """Manages directory operations with proper error handling and logging."""

    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    @staticmethod
    def _is_file_locked(file_path: Path) -> bool:
        """
        Check if a file is locked or in use.

        Args:
            file_path: Path to the file to check

        Returns:
            bool: True if file is locked, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                # Try to acquire exclusive access
                if os.name == "nt":  # Windows
                    import msvcrt

                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # Unix-like
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
        except (IOError, OSError):
            return True

    @staticmethod
    def _get_process_using_file(file_path: Path) -> List[psutil.Process]:
        """
        Get list of processes using a file.

        Args:
            file_path: Path to the file to check

        Returns:
            List[psutil.Process]: List of processes using the file
        """
        processes = []
        for proc in psutil.process_iter(["pid", "name", "open_files"]):
            try:
                for file in proc.open_files():
                    if Path(file.path) == file_path:
                        processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    def force_delete(
        self,
        directory_path: str,
        verbose: bool = False,
        ignore_errors: bool = False,
        force_close: bool = False,
    ) -> bool:
        """
        Force delete a directory and all its contents.

        Args:
            directory_path: Path to the directory to delete
            verbose: Whether to print detailed progress
            ignore_errors: Whether to ignore errors during deletion
            force_close: Whether to attempt to force close files in use

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        path = Path(directory_path)

        if not path.exists():
            if verbose:
                rprint(f"[yellow]Directory does not exist: {directory_path}[/yellow]")
            return True

        try:
            if verbose:
                rprint(f"[yellow]Deleting directory: {directory_path}[/yellow]")

            if path.is_file():
                self._delete_file(path, verbose, force_close)
                return True

            # Count items for progress feedback
            total_items = sum(1 for _ in path.rglob("*"))
            deleted_items = 0

            # Delete directory contents
            for item in path.rglob("*"):
                try:
                    self._delete_item(
                        item, verbose, force_close, deleted_items, total_items
                    )
                    deleted_items += 1

                except Exception as e:
                    logger.error(f"Error deleting {item}: {e}")
                    if not ignore_errors:
                        raise

            # Delete the root directory
            self._delete_item(path, verbose, force_close)

            if verbose:
                rprint(
                    f"[green]Successfully deleted directory: {directory_path}[/green]"
                )
            return True

        except Exception as e:
            error_msg = f"Error deleting directory {directory_path}: {e}"
            logger.error(error_msg)
            if verbose:
                rprint(f"[red]{error_msg}[/red]")

            if not ignore_errors:
                raise

            return False

    def _delete_item(
        self,
        path: Path,
        verbose: bool,
        force_close: bool,
        current_item: int = 0,
        total_items: int = 0,
    ):
        """
        Delete a file or directory with retries.
        """
        for attempt in range(self.max_retries):
            try:
                if path.is_file():
                    if self._is_file_locked(path):
                        if force_close:
                            self._handle_locked_file(path, verbose)
                        else:
                            raise OSError(errno.EACCES, f"File is in use: {path}")
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        # If directory not empty, try to remove contents
                        shutil.rmtree(path, ignore_errors=True)

                if verbose and total_items > 0:
                    rprint(
                        f"[green]Deleted: {path}[/green] ({current_item}/{total_items})"
                    )
                break

            except (PermissionError, OSError):
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay)

    def _handle_locked_file(self, path: Path, verbose: bool):
        """
        Handle locked file by identifying and optionally closing processes.
        """
        processes = self._get_process_using_file(path)
        if processes:
            if verbose:
                process_list = "\n".join(
                    f"- {p.name()} (PID: {p.pid})" for p in processes
                )
                rprint(f"[yellow]File in use by:\n{process_list}[/yellow]")

            for proc in processes:
                try:
                    if verbose:
                        rprint(
                            f"[yellow]Attempting to close process: {proc.name()} (PID: {proc.pid})[/yellow]"
                        )
                    proc.terminate()
                    proc.wait(timeout=3)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.TimeoutExpired,
                ) as e:
                    logger.warning(f"Could not terminate process {proc.pid}: {e}")

    @staticmethod
    def ensure_empty_directory(
        directory_path: str, verbose: bool = False, force_close: bool = False
    ) -> Path:
        """
        Ensure an empty directory exists at the specified path.

        Args:
            directory_path: Path to the directory
            verbose: Whether to print detailed progress
            force_close: Whether to attempt to force close files in use

        Returns:
            Path: Path object for the created directory
        """
        manager = DirectoryManager()
        path = Path(directory_path)

        # Delete if exists
        if path.exists():
            manager.force_delete(str(path), verbose=verbose, force_close=force_close)

        # Create fresh directory
        path.mkdir(parents=True, exist_ok=True)

        if verbose:
            rprint(f"[green]Created fresh directory: {directory_path}[/green]")

        return path
