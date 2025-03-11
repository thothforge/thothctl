# config/constants.py
"""
Constants that are used across the application.
These values are not meant to be changed during runtime.
"""

from typing import Final


# API endpoints
AZURE_DEVOPS_URL: Final = "https://dev.azure.com"

# Command constants
DEFAULT_CLOUD_PROVIDER: Final = "aws"
DEFAULT_VCS_SERVICE: Final = "azure_repos"

# File system constants
TERRAMATE_FILE: Final = "terramate.tm.hcl"
REQUIRED_FILES: Final = ["main.tf", "terragrunt.hcl"]
