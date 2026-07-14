"""Unit tests for AI tool configuration in project initialization."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from thothctl.services.init.project.project import ProjectService


class TestConfigureAiTools:
    """Test the configure_ai_tools method."""

    def setup_method(self):
        """Create a temp directory with .kiro and .claude structures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.service = ProjectService()

        # Create .kiro structure
        kiro_dir = self.temp_dir / ".kiro"
        kiro_dir.mkdir()
        (kiro_dir / "steering").mkdir()
        (kiro_dir / "steering" / "product.md").write_text("# Product")
        (kiro_dir / "settings").mkdir()
        (kiro_dir / "settings" / "mcp.json").write_text('{"mcpServers": {}}')

        # Create .claude structure
        claude_dir = self.temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "rules").mkdir()
        (claude_dir / "rules" / "iac-rules.md").write_text("# Rules")
        (claude_dir / "settings.json").write_text('{"permissions": {}}')

        # Create CLAUDE.md and .mcp.json at root
        (self.temp_dir / "CLAUDE.md").write_text("# Project")
        (self.temp_dir / ".mcp.json").write_text('{"mcpServers": {}}')

    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_keep_both(self):
        """Selection 'both' keeps all AI tool files."""
        self.service.configure_ai_tools(self.temp_dir, "both")

        assert (self.temp_dir / ".kiro").exists()
        assert (self.temp_dir / ".claude").exists()
        assert (self.temp_dir / "CLAUDE.md").exists()
        assert (self.temp_dir / ".mcp.json").exists()

    def test_keep_kiro_only(self):
        """Selection 'kiro' removes Claude Code files, keeps Kiro."""
        self.service.configure_ai_tools(self.temp_dir, "kiro")

        assert (self.temp_dir / ".kiro").exists()
        assert not (self.temp_dir / ".claude").exists()
        assert not (self.temp_dir / "CLAUDE.md").exists()
        assert not (self.temp_dir / ".mcp.json").exists()

    def test_keep_claude_code_only(self):
        """Selection 'claude-code' removes Kiro files, keeps Claude Code."""
        self.service.configure_ai_tools(self.temp_dir, "claude-code")

        assert not (self.temp_dir / ".kiro").exists()
        assert (self.temp_dir / ".claude").exists()
        assert (self.temp_dir / "CLAUDE.md").exists()
        assert (self.temp_dir / ".mcp.json").exists()

    def test_remove_none(self):
        """Selection 'none' removes all AI tool files."""
        self.service.configure_ai_tools(self.temp_dir, "none")

        assert not (self.temp_dir / ".kiro").exists()
        assert not (self.temp_dir / ".claude").exists()
        assert not (self.temp_dir / "CLAUDE.md").exists()
        assert not (self.temp_dir / ".mcp.json").exists()

    def test_no_ai_dirs_does_nothing(self):
        """If no .kiro or .claude exists, does nothing."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            (empty_dir / "main.tf").write_text("# terraform")
            self.service.configure_ai_tools(empty_dir, "kiro")
            # Should not raise and directory should be unchanged
            assert (empty_dir / "main.tf").exists()
        finally:
            shutil.rmtree(empty_dir)

    def test_only_kiro_exists_keep_kiro(self):
        """When only .kiro exists and user selects kiro, keep it."""
        # Remove .claude files
        shutil.rmtree(self.temp_dir / ".claude")
        (self.temp_dir / "CLAUDE.md").unlink()
        (self.temp_dir / ".mcp.json").unlink()

        self.service.configure_ai_tools(self.temp_dir, "kiro")
        assert (self.temp_dir / ".kiro").exists()

    def test_only_claude_exists_keep_claude(self):
        """When only .claude exists and user selects claude-code, keep it."""
        # Remove .kiro
        shutil.rmtree(self.temp_dir / ".kiro")

        self.service.configure_ai_tools(self.temp_dir, "claude-code")
        assert (self.temp_dir / ".claude").exists()
        assert (self.temp_dir / "CLAUDE.md").exists()

    def test_batch_mode_defaults_to_both(self):
        """In batch mode with no selection, defaults to 'both'."""
        self.service.configure_ai_tools(self.temp_dir, None, batch_mode=True)

        assert (self.temp_dir / ".kiro").exists()
        assert (self.temp_dir / ".claude").exists()
        assert (self.temp_dir / "CLAUDE.md").exists()

    @patch("inquirer.prompt")
    def test_interactive_mode_prompts_user(self, mock_prompt):
        """In interactive mode, prompts user for selection."""
        mock_prompt.return_value = {"ai_tools": "kiro"}

        self.service.configure_ai_tools(self.temp_dir, None, batch_mode=False)

        mock_prompt.assert_called_once()
        assert (self.temp_dir / ".kiro").exists()
        assert not (self.temp_dir / ".claude").exists()

    @patch("inquirer.prompt")
    def test_interactive_claude_selection(self, mock_prompt):
        """Interactive selection of claude-code removes kiro."""
        mock_prompt.return_value = {"ai_tools": "claude-code"}

        self.service.configure_ai_tools(self.temp_dir, None, batch_mode=False)

        assert not (self.temp_dir / ".kiro").exists()
        assert (self.temp_dir / ".claude").exists()

    def test_kiro_steering_files_preserved(self):
        """When keeping kiro, all steering files are intact."""
        self.service.configure_ai_tools(self.temp_dir, "kiro")

        assert (self.temp_dir / ".kiro" / "steering" / "product.md").exists()
        assert (self.temp_dir / ".kiro" / "settings" / "mcp.json").exists()

    def test_claude_rules_preserved(self):
        """When keeping claude-code, all rules files are intact."""
        self.service.configure_ai_tools(self.temp_dir, "claude-code")

        assert (self.temp_dir / ".claude" / "rules" / "iac-rules.md").exists()
        assert (self.temp_dir / ".claude" / "settings.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
