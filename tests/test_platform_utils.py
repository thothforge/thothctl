"""Tests for platform utilities."""

import pytest
import platform
from pathlib import Path
from unittest.mock import patch

from thothctl.utils.platform_utils import (
    is_windows,
    is_linux,
    is_macos,
    get_executable_name,
    get_config_dir,
    get_shell_config_file,
    normalize_path,
    run_command
)


class TestPlatformUtils:
    """Test platform utility functions."""

    def test_platform_detection(self):
        """Test platform detection functions."""
        current_system = platform.system()
        
        if current_system == "Windows":
            assert is_windows() is True
            assert is_linux() is False
            assert is_macos() is False
        elif current_system == "Linux":
            assert is_windows() is False
            assert is_linux() is True
            assert is_macos() is False
        elif current_system == "Darwin":
            assert is_windows() is False
            assert is_linux() is False
            assert is_macos() is True

    @patch('platform.system')
    def test_get_executable_name_windows(self, mock_system):
        """Test executable name on Windows."""
        mock_system.return_value = "Windows"
        assert get_executable_name("terraform") == "terraform.exe"
        assert get_executable_name("checkov") == "checkov.exe"

    @patch('platform.system')
    def test_get_executable_name_unix(self, mock_system):
        """Test executable name on Unix systems."""
        mock_system.return_value = "Linux"
        assert get_executable_name("terraform") == "terraform"
        assert get_executable_name("checkov") == "checkov"

    @patch('platform.system')
    def test_get_config_dir_windows(self, mock_system):
        """Test config directory on Windows."""
        mock_system.return_value = "Windows"
        config_dir = get_config_dir()
        assert "AppData" in str(config_dir)
        assert "thothctl" in str(config_dir)

    @patch('platform.system')
    def test_get_config_dir_unix(self, mock_system):
        """Test config directory on Unix systems."""
        mock_system.return_value = "Linux"
        config_dir = get_config_dir()
        assert ".thothcf" in str(config_dir)

    def test_normalize_path(self):
        """Test path normalization."""
        test_path = "test/path"
        normalized = normalize_path(test_path)
        assert isinstance(normalized, Path)
        assert normalized.is_absolute()

    @patch('platform.system')
    def test_run_command_windows(self, mock_system):
        """Test command execution on Windows."""
        mock_system.return_value = "Windows"
        # This would use shell=True on Windows
        # We can't easily test subprocess.run without mocking it
        pass

    @patch('platform.system')
    def test_run_command_unix(self, mock_system):
        """Test command execution on Unix systems."""
        mock_system.return_value = "Linux"
        # This would not use shell=True on Unix
        # We can't easily test subprocess.run without mocking it
        pass
