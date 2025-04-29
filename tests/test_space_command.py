"""Tests for the space initialization command."""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from thothctl.commands.init.commands.space import SpaceInitCommand
from thothctl.services.init.space.space_config import SpaceConfig, VersionControlSystem, CISystem


class TestSpaceInitCommand(unittest.TestCase):
    """Test the space initialization command."""

    def setUp(self):
        """Set up the test environment."""
        self.runner = CliRunner()
        self.command = SpaceInitCommand()
        
        # Create a mock space service
        self.mock_space_service = MagicMock()
        self.command.space_service = self.mock_space_service

    def test_validate_valid_name(self):
        """Test validation with a valid space name."""
        result = self.command.validate(space_name="test-space")
        self.assertTrue(result)

    def test_validate_empty_name(self):
        """Test validation with an empty space name."""
        with self.assertRaises(ValueError):
            self.command.validate(space_name="")
        
        with self.assertRaises(ValueError):
            self.command.validate(space_name="   ")

    @patch('click.confirm')
    def test_execute_new_space(self, mock_confirm):
        """Test executing the command for a new space."""
        # Set up mocks
        self.mock_space_service.get_space.return_value = None
        mock_space_config = MagicMock(spec=SpaceConfig)
        mock_space_config.name = "test-space"
        mock_space_config.version_control = VersionControlSystem.GITHUB
        mock_space_config.ci_system = CISystem.GITHUB_ACTIONS
        self.mock_space_service.initialize_space.return_value = mock_space_config
        
        # Execute the command
        self.command.execute(
            space_name="test-space",
            version_control_system_service="github",
            ci="github-actions",
            description="Test space",
            terraform_registry="https://registry.terraform.io"
        )
        
        # Verify the service was called correctly
        self.mock_space_service.get_space.assert_called_once_with("test-space")
        self.mock_space_service.initialize_space.assert_called_once_with(
            space_name="test-space",
            vcs="github",
            ci="github-actions",
            description="Test space",
            terraform_registry="https://registry.terraform.io",
            force=False
        )
        
        # Confirm was not called since the space doesn't exist
        mock_confirm.assert_not_called()

    @patch('click.confirm')
    def test_execute_existing_space_overwrite(self, mock_confirm):
        """Test executing the command for an existing space with overwrite."""
        # Set up mocks
        mock_space_config = MagicMock(spec=SpaceConfig)
        self.mock_space_service.get_space.return_value = mock_space_config
        mock_confirm.return_value = True  # User confirms overwrite
        
        # Execute the command
        self.command.execute(
            space_name="test-space",
            version_control_system_service="github",
            ci="github-actions",
            description="Test space",
            terraform_registry="https://custom.registry.example.com"
        )
        
        # Verify the service was called correctly
        self.mock_space_service.get_space.assert_called_once_with("test-space")
        self.mock_space_service.initialize_space.assert_called_once_with(
            space_name="test-space",
            vcs="github",
            ci="github-actions",
            description="Test space",
            terraform_registry="https://custom.registry.example.com",
            force=True
        )
        
        # Confirm was called since the space exists
        mock_confirm.assert_called_once()

    @patch('click.confirm')
    def test_execute_existing_space_cancel(self, mock_confirm):
        """Test executing the command for an existing space with cancel."""
        # Set up mocks
        mock_space_config = MagicMock(spec=SpaceConfig)
        self.mock_space_service.get_space.return_value = mock_space_config
        mock_confirm.return_value = False  # User cancels overwrite
        
        # Execute the command
        self.command.execute(
            space_name="test-space",
            version_control_system_service="github",
            ci="github-actions",
            description="Test space"
        )
        
        # Verify the service was called correctly
        self.mock_space_service.get_space.assert_called_once_with("test-space")
        
        # Initialize space should not be called since the user cancelled
        self.mock_space_service.initialize_space.assert_not_called()
        
        # Confirm was called since the space exists
        mock_confirm.assert_called_once()

    def test_get_completions(self):
        """Test getting command completions."""
        # Create mock context and command
        mock_ctx = MagicMock()
        mock_param = MagicMock()
        mock_param.opts = ['--version-control-system-service', '-vcss']
        mock_param.help = 'The Version Control System Service for your IDP'
        mock_ctx.command.params = [mock_param]
        
        # Test completing an option
        completions = self.command.get_completions(mock_ctx, [], '--ver')
        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0][0], '--version-control-system-service')
        
        # Test completing an option value
        completions = self.command.get_completions(mock_ctx, ['--ci'], 'git')
        self.assertEqual(len(completions), 2)  # github-actions and gitlab-ci
        self.assertTrue(any(c[0] == 'github-actions' for c in completions))
        self.assertTrue(any(c[0] == 'gitlab-ci' for c in completions))


if __name__ == "__main__":
    unittest.main()
