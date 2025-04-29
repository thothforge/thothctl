"""Tests for the space configuration manager."""
import os
import tempfile
import unittest
from pathlib import Path

from thothctl.services.init.space.space_config import (
    SpaceConfigManager,
    SpaceConfig,
    VersionControlSystem,
    CISystem,
    RegistryConfig
)


class TestSpaceConfigManager(unittest.TestCase):
    """Test the space configuration manager."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for test configurations
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_manager = SpaceConfigManager(self.temp_dir.name)

    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()

    def test_create_space(self):
        """Test creating a space configuration."""
        # Create a space
        space_name = "test-space"
        space_config = self.config_manager.create_space(
            space_name=space_name,
            vcs="github",
            ci="github-actions",
            description="Test space"
        )

        # Check that the space was created
        self.assertTrue(self.config_manager.space_exists(space_name))
        self.assertEqual(space_config.name, space_name)
        self.assertEqual(space_config.version_control, VersionControlSystem.GITHUB)
        self.assertEqual(space_config.ci_system, CISystem.GITHUB_ACTIONS)
        self.assertEqual(space_config.description, "Test space")

    def test_load_space(self):
        """Test loading a space configuration."""
        # Create a space
        space_name = "test-space"
        created_config = self.config_manager.create_space(
            space_name=space_name,
            vcs="github",
            ci="github-actions",
            description="Test space"
        )

        # Load the space
        loaded_config = self.config_manager.load_space(space_name)

        # Check that the loaded space matches the created space
        self.assertEqual(loaded_config.name, created_config.name)
        self.assertEqual(loaded_config.version_control, created_config.version_control)
        self.assertEqual(loaded_config.ci_system, created_config.ci_system)
        self.assertEqual(loaded_config.description, created_config.description)

    def test_list_spaces(self):
        """Test listing spaces."""
        # Create some spaces
        self.config_manager.create_space("space1")
        self.config_manager.create_space("space2")
        self.config_manager.create_space("space3")

        # List spaces
        spaces = self.config_manager.list_spaces()

        # Check that all spaces are listed
        self.assertIn("space1", spaces)
        self.assertIn("space2", spaces)
        self.assertIn("space3", spaces)

    def test_delete_space(self):
        """Test deleting a space."""
        # Create a space
        space_name = "test-space"
        self.config_manager.create_space(space_name)

        # Check that the space exists
        self.assertTrue(self.config_manager.space_exists(space_name))

        # Delete the space
        result = self.config_manager.delete_space(space_name)

        # Check that the space was deleted
        self.assertTrue(result)
        self.assertFalse(self.config_manager.space_exists(space_name))

    def test_invalid_vcs(self):
        """Test creating a space with an invalid VCS."""
        # Create a space with an invalid VCS
        space_name = "test-space"
        space_config = self.config_manager.create_space(
            space_name=space_name,
            vcs="invalid-vcs",
            ci="none"
        )

        # Check that the default VCS was used
        self.assertEqual(space_config.version_control, VersionControlSystem.AZURE_REPOS)

    def test_invalid_ci(self):
        """Test creating a space with an invalid CI system."""
        # Create a space with an invalid CI system
        space_name = "test-space"
        space_config = self.config_manager.create_space(
            space_name=space_name,
            vcs="github",
            ci="invalid-ci"
        )

        # Check that the default CI system was used
        self.assertEqual(space_config.ci_system, CISystem.NONE)


if __name__ == "__main__":
    unittest.main()
