import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Optional, Callable


class FileScanner:
    """
    A class to handle file scanning operations with parallel processing capabilities.
    """

    def __init__(self,
                 exclude_patterns: List[str] = None,
                 max_workers: int = 4):
        """
        Initialize the FileScanner.

        Args:
            exclude_patterns (List[str]): Patterns to exclude from scanning
            max_workers (int): Maximum number of parallel workers
        """
        self.exclude_patterns = exclude_patterns or []
        self.max_workers = max_workers

    def _should_exclude(self, path: str) -> bool:
        """
        Check if a path should be excluded based on patterns.

        Args:
            path (str): Path to check

        Returns:
            bool: True if path should be excluded
        """
        return any(pattern in path for pattern in self.exclude_patterns)

    def find_files(self,
                   directory: Path,
                   pattern: str = "*",
                   recursive: bool = True) -> Set[Path]:
        """
        Find files matching the pattern in the directory.

        Args:
            directory (Path): Directory to scan
            pattern (str): File pattern to match
            recursive (bool): Whether to scan recursively

        Returns:
            Set[Path]: Set of matching file paths
        """
        matching_files = set()

        try:
            if recursive:
                for root, dirs, files in os.walk(directory):
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if not self._should_exclude(d)]

                    path = Path(root)
                    for file in files:
                        if Path(file).match(pattern) and not self._should_exclude(file):
                            matching_files.add(path / file)
            else:
                # Non-recursive search
                for file in directory.glob(pattern):
                    if not self._should_exclude(str(file)):
                        matching_files.add(file)

        except Exception as e:
            print(f"Error scanning directory {directory}: {str(e)}")

        return matching_files

    def process_files(self,
                      files: Set[Path],
                      processor: Callable[[Path], bool]) -> dict:
        """
        Process files in parallel using the provided processor function.

        Args:
            files (Set[Path]): Set of files to process
            processor (Callable[[Path], bool]): Function to process each file

        Returns:
            dict: Processing statistics
        """
        stats = {
            'processed': 0,
            'failed': 0,
            'total': len(files)
        }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(processor, file): file
                for file in files
            }

            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    if future.result():
                        stats['processed'] += 1
                    else:
                        stats['failed'] += 1
                except Exception as e:
                    print(f"Error processing {file}: {str(e)}")
                    stats['failed'] += 1

        return stats

    def scan_and_process(self,
                         directory: Path,
                         pattern: str = "*",
                         recursive: bool = True,
                         processor: Optional[Callable[[Path], bool]] = None) -> dict:
        """
        Scan directory and process matching files.

        Args:
            directory (Path): Directory to scan
            pattern (str): File pattern to match
            recursive (bool): Whether to scan recursively
            processor (Callable[[Path], bool]): Function to process each file

        Returns:
            dict: Processing statistics
        """
        # Find matching files
        matching_files = self.find_files(directory, pattern, recursive)

        if not processor:
            return {'found': len(matching_files)}

        # Process the files
        stats = self.process_files(matching_files, processor)
        stats['found'] = len(matching_files)

        return stats
