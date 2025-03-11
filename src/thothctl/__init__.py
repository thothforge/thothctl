"""Init file."""
# src/thothctl/__init__.py
# rom .thothctl import thothctl

# __all__ = ['thothctl']
# src/thothctl/__init__.py
import logging

from .version import __version__


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

__all__ = ["__version__"]
