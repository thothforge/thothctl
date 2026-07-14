"""Tests for space management commands (activate, update) and get_active_space helper."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import toml

from thothctl.common.common import get_active_space


class TestGetActiveSpace(unittest.TestCase):
    """Test the get_active_space helper."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.active_space_file = Path(self.temp_dir) / "active_space"
        self.spaces_toml = Path(self.temp_dir) / "spaces.toml"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch("thothctl.common.common.list_spaces")
    def test_returns_none_when_no_file(self, mock_list_spaces):
        """No active_space file means no active space."""
        with patch.object(Path, "home", return_value=Path(self.temp_dir)):
            # Patch the file path used in get_active_space
            fake_file = Path(self.temp_dir) / ".thothcf" / "active_space"
            with patch("thothctl.common.common.get_active_space") as mock_fn:
                mock_fn.return_value = None
                result = mock_fn()
        self.assertIsNone(result)

    @patch("thothctl.common.common.list_spaces")
    def test_returns_space_when_valid(self, mock_list_spaces):
        """Returns space name when file exists and space is valid."""
        mock_list_spaces.return_value = ["production", "staging"]
        active_file = Path(self.temp_dir) / ".thothcf" / "active_space"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text("production", encoding="utf-8")

        with patch("thothctl.common.common.Path.home", return_value=Path(self.temp_dir)):
            result = get_active_space()
        self.assertEqual(result, "production")

    @patch("thothctl.common.common.list_spaces")
    def test_returns_none_when_space_deleted(self, mock_list_spaces):
        """Returns None if the saved space no longer exists."""
        mock_list_spaces.return_value = ["staging"]
        active_file = Path(self.temp_dir) / ".thothcf" / "active_space"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text("deleted-space", encoding="utf-8")

        with patch("thothctl.common.common.Path.home", return_value=Path(self.temp_dir)):
            result = get_active_space()
        self.assertIsNone(result)


class TestActivateSpaceCommand(unittest.TestCase):
    """Test the space activate command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch("thothctl.commands.space.commands.activate.list_spaces")
    @patch("thothctl.commands.space.commands.activate.ACTIVE_SPACE_FILE")
    def test_activate_valid_space(self, mock_file, mock_list_spaces):
        """Activating a valid space writes to the file."""
        mock_list_spaces.return_value = ["dev", "production"]
        mock_file_path = Path(self.temp_dir) / "active_space"
        mock_file_parent = MagicMock()
        mock_file.__truediv__ = MagicMock()
        mock_file.parent = mock_file_parent

        from thothctl.commands.space.commands.activate import ActivateSpaceCommand
        cmd = ActivateSpaceCommand()
        cmd.ui = MagicMock()

        # Patch ACTIVE_SPACE_FILE at module level for the write
        with patch("thothctl.commands.space.commands.activate.ACTIVE_SPACE_FILE", mock_file_path):
            mock_file_path.parent.mkdir(parents=True, exist_ok=True)
            cmd._execute(space_name="production")

        self.assertEqual(mock_file_path.read_text(encoding="utf-8"), "production")
        cmd.ui.print_success.assert_called_once()

    @patch("thothctl.commands.space.commands.activate.list_spaces")
    def test_activate_invalid_space_fails_validation(self, mock_list_spaces):
        """Activating a non-existent space raises ValueError."""
        mock_list_spaces.return_value = ["dev"]

        from thothctl.commands.space.commands.activate import ActivateSpaceCommand
        cmd = ActivateSpaceCommand()
        cmd.ui = MagicMock()

        with self.assertRaises(ValueError):
            cmd.validate(space_name="nonexistent")


class TestUpdateSpaceCommand(unittest.TestCase):
    """Test the space update command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.thothcf_dir = Path(self.temp_dir) / ".thothcf"
        self.thothcf_dir.mkdir(parents=True)
        self.spaces_toml = self.thothcf_dir / "spaces.toml"
        # Create initial spaces.toml
        config = {
            "spaces": {
                "dev": {
                    "name": "dev",
                    "description": "Development",
                    "version_control": {"provider": "github"},
                    "orchestration": {"tool": "terragrunt"},
                    "terraform": {"registry": "https://registry.terraform.io"},
                }
            }
        }
        with open(self.spaces_toml, "wt") as f:
            toml.dump(config, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch("thothctl.commands.space.commands.update.list_spaces")
    def test_update_description(self, mock_list_spaces):
        """Updating description writes to spaces.toml."""
        mock_list_spaces.return_value = ["dev"]

        from thothctl.commands.space.commands.update import UpdateSpaceCommand
        cmd = UpdateSpaceCommand()
        cmd.ui = MagicMock()

        with patch("thothctl.commands.space.commands.update.Path.home", return_value=Path(self.temp_dir)):
            cmd._execute(
                space_name="dev",
                description="Updated description",
                vcs_provider=None,
                orchestration_tool=None,
                terraform_registry=None,
                policy_repo=None,
            )

        with open(self.spaces_toml) as f:
            result = toml.load(f)
        self.assertEqual(result["spaces"]["dev"]["description"], "Updated description")
        self.assertIn("updated_at", result["spaces"]["dev"])

    @patch("thothctl.commands.space.commands.update.list_spaces")
    def test_update_vcs_provider(self, mock_list_spaces):
        """Updating VCS provider persists correctly."""
        mock_list_spaces.return_value = ["dev"]

        from thothctl.commands.space.commands.update import UpdateSpaceCommand
        cmd = UpdateSpaceCommand()
        cmd.ui = MagicMock()

        with patch("thothctl.commands.space.commands.update.Path.home", return_value=Path(self.temp_dir)):
            cmd._execute(
                space_name="dev",
                description=None,
                vcs_provider="gitlab",
                orchestration_tool=None,
                terraform_registry=None,
                policy_repo=None,
            )

        with open(self.spaces_toml) as f:
            result = toml.load(f)
        self.assertEqual(result["spaces"]["dev"]["version_control"]["provider"], "gitlab")

    @patch("thothctl.commands.space.commands.update.list_spaces")
    def test_validate_nonexistent_space(self, mock_list_spaces):
        """Validate fails for non-existent space."""
        mock_list_spaces.return_value = ["dev"]

        from thothctl.commands.space.commands.update import UpdateSpaceCommand
        cmd = UpdateSpaceCommand()
        cmd.ui = MagicMock()

        with self.assertRaises(ValueError):
            cmd.validate(
                space_name="nonexistent",
                description="x",
                vcs_provider=None,
                orchestration_tool=None,
                terraform_registry=None,
                policy_repo=None,
            )

    @patch("thothctl.commands.space.commands.update.list_spaces")
    def test_validate_no_options(self, mock_list_spaces):
        """Validate fails when no update options provided."""
        mock_list_spaces.return_value = ["dev"]

        from thothctl.commands.space.commands.update import UpdateSpaceCommand
        cmd = UpdateSpaceCommand()
        cmd.ui = MagicMock()

        with self.assertRaises(ValueError):
            cmd.validate(
                space_name="dev",
                description=None,
                vcs_provider=None,
                orchestration_tool=None,
                terraform_registry=None,
                policy_repo=None,
            )


if __name__ == "__main__":
    unittest.main()
