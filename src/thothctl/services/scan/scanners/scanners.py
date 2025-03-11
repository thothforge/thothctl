from typing import Dict, List, Optional

from abc import ABC, abstractmethod


class ScannerPort(ABC):
    """Port interface for scanner implementations."""

    @abstractmethod
    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """Execute the scan operation."""
        pass


class Scanner:
    """Domain entity representing a security scanner."""

    def __init__(self, name: str, scanner_port: ScannerPort):
        self.name = name
        self._scanner = scanner_port

    def execute_scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        return self._scanner.scan(directory, reports_dir, options, tftool)


class ScanOrchestrator:
    """Domain service for orchestrating multiple scanners."""

    def __init__(self, scanners: List[Scanner]):
        self.scanners = scanners

    def run_scans(
        self,
        directory: str,
        reports_dir: str,
        options: Dict[str, Dict],
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        results = {}
        for scanner in self.scanners:
            scanner_options = options.get(scanner.name, {})
            try:
                result = scanner.execute_scan(
                    directory, reports_dir, scanner_options, tftool
                )
                results[scanner.name] = result
            except Exception as e:
                results[scanner.name] = {"status": "FAIL", "error": str(e)}
        return results
