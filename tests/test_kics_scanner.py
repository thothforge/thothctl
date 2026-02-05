"""Unit tests for KICS scanner."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from thothctl.services.scan.scanners.kics import KICSScanner
from thothctl.services.scan.scanners.scan_reports import ReportScanner


class TestKICSScanner:
    """Test KICS scanner functionality."""

    def test_scanner_initialization(self):
        """Test KICS scanner initializes correctly."""
        scanner = KICSScanner()
        assert scanner.docker_image == "checkmarx/kics:latest"
        assert scanner.ui is not None
        assert scanner.logger is not None

    @patch('subprocess.run')
    def test_check_docker_available(self, mock_run):
        """Test Docker availability check when Docker is installed."""
        mock_run.return_value = Mock(returncode=0)
        scanner = KICSScanner()
        assert scanner._check_docker() is True

    @patch('subprocess.run')
    def test_check_docker_unavailable(self, mock_run):
        """Test Docker availability check when Docker is not installed."""
        mock_run.side_effect = FileNotFoundError()
        scanner = KICSScanner()
        assert scanner._check_docker() is False

    @patch('subprocess.run')
    def test_scan_without_docker(self, mock_run):
        """Test scan fails gracefully when Docker is not available."""
        mock_run.side_effect = FileNotFoundError()
        scanner = KICSScanner()
        
        result = scanner.scan(
            directory="/tmp/test",
            reports_dir="/tmp/reports"
        )
        
        assert result["status"] == "error"
        assert "Docker is required" in result["error"]

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('subprocess.run')
    def test_scan_success(self, mock_run, mock_makedirs, mock_exists):
        """Test successful KICS scan."""
        # Mock Docker check
        mock_run.side_effect = [
            Mock(returncode=0),  # Docker check
            Mock(returncode=0, stdout="", stderr="")  # KICS scan
        ]
        mock_exists.return_value = True
        
        scanner = KICSScanner()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '{"total_counter": 5}'
            
            result = scanner.scan(
                directory="/tmp/test",
                reports_dir="/tmp/reports"
            )
        
        assert result["status"] == "success"
        assert result["findings"] == 5


class TestKICSReportParser:
    """Test KICS report parsing for report generation."""

    def test_parse_kics_report(self):
        """Test parsing KICS JSON report."""
        # Create sample KICS report
        kics_report = {
            "total_counter": 10,
            "severity_counters": {
                "HIGH": 3,
                "MEDIUM": 4,
                "LOW": 2,
                "INFO": 1
            },
            "queries": []
        }
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(kics_report, f)
            temp_path = f.name
        
        try:
            # Parse report
            scanner = ReportScanner()
            result = scanner.scan_report(temp_path, "kics")
            
            assert result is not None
            assert result.total_tests == 10
            assert result.failures == 9  # HIGH + MEDIUM + LOW (excluding INFO)
            assert result.module_name == "kics-scan"
        finally:
            Path(temp_path).unlink()

    def test_parse_kics_report_no_issues(self):
        """Test parsing KICS report with no issues."""
        kics_report = {
            "total_counter": 0,
            "severity_counters": {},
            "queries": []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(kics_report, f)
            temp_path = f.name
        
        try:
            scanner = ReportScanner()
            result = scanner.scan_report(temp_path, "kics")
            
            assert result is not None
            assert result.total_tests == 0
            assert result.failures == 0
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
