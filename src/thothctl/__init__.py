"""Init file."""
# src/thothctl/__init__.py
import logging
import os

from .version import __version__

# Configure logging with clean defaults
# Priority: DEBUG > VERBOSE > WARNING (default)
if os.getenv("THOTHCTL_DEBUG") == "true":
    log_level = logging.DEBUG
elif os.getenv("THOTHCTL_VERBOSE") == "true":
    log_level = logging.INFO
else:
    log_level = logging.WARNING

logging.basicConfig(
    level=log_level,
    format="%(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Suppress overly verbose third-party loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

__all__ = ["__version__"]
