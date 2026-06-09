"""Tests for the space initialization command."""
import unittest
from unittest.mock import patch, MagicMock

from thothctl.commands.init.commands.space import SpaceInitCommand


class TestSpaceInitCommand(unittest.TestCase):
    """Test the space initialization command."""

    def setUp(self):
        """Set up the test environment."""
        self.command = SpaceInitCommand()
        self.command.space_service = MagicMock()

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


if __name__ == "__main__":
    unittest.main()
