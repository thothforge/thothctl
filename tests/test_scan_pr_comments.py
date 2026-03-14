"""Tests for scan iac PR comment integration."""
from thothctl.commands.scan.commands.iac import RestoredIaCScanCommand


class TestBuildScanMarkdown:
    """Test markdown summary generation from scan results."""

    def test_basic_summary(self):
        cmd = RestoredIaCScanCommand()
        results = {
            "checkov": {
                "status": "COMPLETE",
                "report_data": {
                    "passed_count": 423,
                    "failed_count": 90,
                    "error_count": 0,
                    "skipped_count": 0,
                },
            },
            "summary": {"total_issues": 90},
        }
        md = cmd._build_scan_markdown(results)
        assert "## 🔒 ThothCTL Scan Results" in md
        assert "| checkov | COMPLETE | 513 | 423 | 90 | 0 | 0 | 82.5% |" in md
        assert "**TOTAL**" in md
        assert "Security Issues Found: 90" in md
        assert "thothforge/thothctl" in md

    def test_multiple_tools(self):
        cmd = RestoredIaCScanCommand()
        results = {
            "checkov": {
                "status": "COMPLETE",
                "report_data": {"passed_count": 10, "failed_count": 2, "error_count": 0, "skipped_count": 0},
            },
            "trivy": {
                "status": "COMPLETE",
                "report_data": {"passed_count": 5, "failed_count": 1, "error_count": 0, "skipped_count": 0},
            },
            "summary": {"total_issues": 3},
        }
        md = cmd._build_scan_markdown(results)
        assert "checkov" in md
        assert "trivy" in md
        assert "**18**" in md  # total tests

    def test_no_issues(self):
        cmd = RestoredIaCScanCommand()
        results = {
            "checkov": {
                "status": "COMPLETE",
                "report_data": {"passed_count": 50, "failed_count": 0, "error_count": 0, "skipped_count": 0},
            },
            "summary": {"total_issues": 0},
        }
        md = cmd._build_scan_markdown(results)
        assert "Security Issues Found" not in md
        assert "100.0%" in md
