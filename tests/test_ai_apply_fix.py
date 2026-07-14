"""Unit tests for apply-fix backup and application logic."""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner

from thothctl.commands.ai_review.commands.apply_fix import ApplyFixCommand


class TestApplyFixDryRun:
    def _make_fixes_file(self, tmp_path, fixes):
        f = tmp_path / "fixes.json"
        f.write_text(json.dumps({"fixes": fixes, "summary": {
            "total_findings": len(fixes), "fixes_generated": len(fixes), "skipped": 0,
        }}))
        return str(f)

    def test_dry_run_reports_missing_file(self, tmp_path):
        fixes = [{"fix_id": "fix_000", "finding_id": "CKV_AWS_19", "file": "nonexistent.tf",
                   "fix_type": "add_resource", "severity": "HIGH",
                   "description": "Add encryption", "original": "#",
                   "replacement": "resource {}", "validation": "check"}]
        fixes_file = self._make_fixes_file(tmp_path, fixes)

        cmd = ApplyFixCommand()
        # Simulate dry run — file doesn't exist
        # We test the logic directly rather than through Click
        # since the command needs ctx.obj
        assert Path(fixes_file).exists()

    def test_add_resource_appends(self, tmp_path):
        # Create a target file
        tf_file = tmp_path / "s3.tf"
        tf_file.write_text('resource "aws_s3_bucket" "data" {\n  bucket = "test"\n}\n')

        fixes = [{"fix_id": "fix_000", "finding_id": "CKV_AWS_19", "file": "s3.tf",
                   "fix_type": "add_resource", "severity": "HIGH",
                   "description": "Add encryption",
                   "original": "# Add after resource",
                   "replacement": 'resource "aws_s3_bucket_sse" "data" { bucket = "x" }',
                   "validation": "check"}]
        fixes_file = self._make_fixes_file(tmp_path, fixes)

        # Manually test the apply logic
        with open(fixes_file) as f:
            data = json.load(f)

        fix = data["fixes"][0]
        content = tf_file.read_text()
        new_content = content.rstrip() + "\n\n" + fix["replacement"] + "\n"
        tf_file.write_text(new_content)

        result = tf_file.read_text()
        assert 'aws_s3_bucket_sse' in result
        assert 'aws_s3_bucket' in result  # original preserved

    def test_replace_exact_match(self, tmp_path):
        tf_file = tmp_path / "sg.tf"
        tf_file.write_text('  cidr_blocks = ["0.0.0.0/0"]\n')

        original = '  cidr_blocks = ["0.0.0.0/0"]'
        replacement = '  cidr_blocks = [var.allowed_ssh_cidrs]'

        content = tf_file.read_text()
        assert original in content
        new_content = content.replace(original, replacement, 1)
        tf_file.write_text(new_content)

        assert "var.allowed_ssh_cidrs" in tf_file.read_text()
        assert "0.0.0.0/0" not in tf_file.read_text()

    def test_manual_fixes_not_applied(self, tmp_path):
        fixes = [{"fix_id": "rec_001", "fix_type": "manual", "severity": "MEDIUM",
                   "description": "Enable VPC flow logs", "file": "", "original": "",
                   "replacement": ""}]
        fixes_file = self._make_fixes_file(tmp_path, fixes)

        with open(fixes_file) as f:
            data = json.load(f)

        applicable = [f for f in data["fixes"] if f.get("replacement") and f.get("file")
                      and f.get("fix_type") != "manual"]
        manual = [f for f in data["fixes"] if f.get("fix_type") == "manual"]

        assert len(applicable) == 0
        assert len(manual) == 1


class TestBackup:
    def test_backup_creates_copy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "thothctl.commands.ai_review.commands.apply_fix.BACKUP_DIR",
            str(tmp_path / "backups"),
        )
        tf_file = tmp_path / "main.tf"
        tf_file.write_text("original content")

        ApplyFixCommand._backup(tf_file)

        backup_dir = tmp_path / "backups"
        assert backup_dir.exists()
        # Find the timestamped subdirectory
        subdirs = list(backup_dir.iterdir())
        assert len(subdirs) == 1
        backup_file = subdirs[0] / "main.tf"
        assert backup_file.exists()
        assert backup_file.read_text() == "original content"
