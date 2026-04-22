"""Unit tests for parallel checkov scan and memory optimization."""

import gc
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from thothctl.services.scan.scan_service import ScanService
from thothctl.services.scan.scanners.checkov import CheckovScanner


class TestFindTerraformStacks:
    """Test _find_terraform_stacks discovery."""

    def test_finds_root_stack(self, tmp_path):
        svc = ScanService()
        (tmp_path / "main.tf").write_text("")
        stacks = svc._find_terraform_stacks(str(tmp_path))
        assert str(tmp_path) in stacks

    def test_finds_nested_stacks(self, tmp_path):
        for name in ["stack-a", "stack-b", "modules/vpc"]:
            d = tmp_path / name
            d.mkdir(parents=True)
            (d / "main.tf").write_text("")
        stacks = svc = ScanService()
        stacks = svc._find_terraform_stacks(str(tmp_path))
        assert len(stacks) == 3

    def test_finds_tfplan_json_stacks(self, tmp_path):
        d = tmp_path / "plan-stack"
        d.mkdir()
        (d / "tfplan.json").write_text("{}")
        svc = ScanService()
        stacks = svc._find_terraform_stacks(str(tmp_path))
        assert len(stacks) == 1
        assert "plan-stack" in stacks[0]

    def test_skips_hidden_dirs(self, tmp_path):
        hidden = tmp_path / ".terraform" / "modules" / "inner"
        hidden.mkdir(parents=True)
        (hidden / "main.tf").write_text("")
        (tmp_path / "main.tf").write_text("")
        svc = ScanService()
        stacks = svc._find_terraform_stacks(str(tmp_path))
        assert len(stacks) == 1

    def test_empty_dir_returns_empty(self, tmp_path):
        svc = ScanService()
        assert svc._find_terraform_stacks(str(tmp_path)) == []


class TestRecursiveTerraformScanParallel:
    """Test _recursive_terraform_scan with parallel execution."""

    def _make_stacks(self, tmp_path, count):
        for i in range(count):
            d = tmp_path / f"stack-{i}"
            d.mkdir()
            (d / "main.tf").write_text(f'resource "null_resource" "r{i}" {{}}')
        return tmp_path

    @patch.object(ScanService, '_find_terraform_stacks')
    def test_parallel_scans_all_stacks(self, mock_find):
        """All discovered stacks are scanned and results collected."""
        stacks = ["/a/stack-0", "/a/stack-1", "/a/stack-2"]
        mock_find.return_value = stacks

        svc = ScanService()
        mock_scanner = Mock()
        mock_scanner.execute_scan.return_value = {"status": "COMPLETE"}
        svc.available_scanners["checkov"] = Mock()
        svc.available_scanners["checkov"].execute_scan = mock_scanner.execute_scan

        results = svc._recursive_terraform_scan(
            directory="/a", reports_dir="/r", options={}, tftool="tofu",
            max_workers=2,
        )

        assert len(results) == 3
        assert mock_scanner.execute_scan.call_count == 3
        for s in stacks:
            assert s in results
            assert results[s]["status"] == "COMPLETE"

    @patch.object(ScanService, '_find_terraform_stacks')
    def test_single_worker_sequential(self, mock_find):
        """max_workers=1 still scans all stacks (sequential fallback)."""
        mock_find.return_value = ["/a/s1", "/a/s2"]

        svc = ScanService()
        mock_scanner = Mock()
        mock_scanner.execute_scan.return_value = {"status": "COMPLETE"}
        svc.available_scanners["checkov"] = Mock()
        svc.available_scanners["checkov"].execute_scan = mock_scanner.execute_scan

        results = svc._recursive_terraform_scan(
            directory="/a", reports_dir="/r", options={}, tftool="tofu",
            max_workers=1,
        )
        assert len(results) == 2

    @patch.object(ScanService, '_find_terraform_stacks')
    def test_failed_stack_does_not_block_others(self, mock_find):
        """A failing stack returns FAIL but other stacks still complete."""
        mock_find.return_value = ["/a/good", "/a/bad"]

        svc = ScanService()
        mock_scanner = Mock()

        def side_effect(directory, **kw):
            if "bad" in directory:
                raise RuntimeError("boom")
            return {"status": "COMPLETE"}

        mock_scanner.execute_scan.side_effect = side_effect
        svc.available_scanners["checkov"] = Mock()
        svc.available_scanners["checkov"].execute_scan = mock_scanner.execute_scan

        results = svc._recursive_terraform_scan(
            directory="/a", reports_dir="/r", options={}, tftool="tofu",
        )
        assert results["/a/good"]["status"] == "COMPLETE"
        assert results["/a/bad"]["status"] == "FAIL"
        assert "boom" in results["/a/bad"]["error"]

    @patch.object(ScanService, '_find_terraform_stacks')
    def test_no_stacks_returns_empty(self, mock_find):
        mock_find.return_value = []
        svc = ScanService()
        results = svc._recursive_terraform_scan(
            directory="/a", reports_dir="/r", options={}, tftool="tofu",
        )
        assert results == {}

    @patch.object(ScanService, '_find_terraform_stacks')
    def test_compact_flag_passed_to_scanner(self, mock_find):
        """compact=True adds compact key to options passed to scanner."""
        mock_find.return_value = ["/a/s1"]

        svc = ScanService()
        mock_scanner = Mock()
        mock_scanner.execute_scan.return_value = {"status": "COMPLETE"}
        svc.available_scanners["checkov"] = Mock()
        svc.available_scanners["checkov"].execute_scan = mock_scanner.execute_scan

        svc._recursive_terraform_scan(
            directory="/a", reports_dir="/r", options={}, tftool="tofu",
            compact=True,
        )

        call_opts = mock_scanner.execute_scan.call_args
        assert call_opts.kwargs.get("options", {}).get("compact") is True or \
               call_opts[1].get("options", {}).get("compact") is True


class TestCheckovBuildCommand:
    """Test checkov _build_command handles compact flag."""

    def test_compact_adds_flag(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"compact": True})
        assert "--compact" in cmd

    def test_no_compact_by_default(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {})
        assert "--compact" not in cmd

    def test_compact_false_no_flag(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"compact": False})
        assert "--compact" not in cmd

    def test_additional_args_string(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"additional_args": "--skip-check CKV_AWS_1"})
        assert "--skip-check" in cmd
        assert "CKV_AWS_1" in cmd

    def test_additional_args_list(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"additional_args": ["--framework", "terraform"]})
        assert "--framework" in cmd
        assert "terraform" in cmd

    def test_compact_with_additional_args(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"compact": True, "additional_args": "--quiet"})
        assert "--compact" in cmd
        assert "--quiet" in cmd
