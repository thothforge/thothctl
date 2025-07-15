# src/thothctl/core/logger.py
import logging
import os
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger instance"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Determine appropriate log level
    if level is not None:
        logger.setLevel(level)
    elif not logger.level or logger.level == logging.NOTSET:
        # Check environment variables for logging level
        if os.getenv("THOTHCTL_DEBUG") == "true":
            logger.setLevel(logging.DEBUG)
        elif os.getenv("THOTHCTL_VERBOSE") == "true":
            logger.setLevel(logging.INFO)
        else:
            # Default to WARNING to keep output clean
            logger.setLevel(logging.WARNING)

    return logger


def get_clean_logger(name: str) -> logging.Logger:
    """Get a logger that only shows warnings and errors by default"""
    return get_logger(name, logging.WARNING)


def get_verbose_logger(name: str) -> logging.Logger:
    """Get a logger that shows info, warnings and errors"""
    return get_logger(name, logging.INFO)
