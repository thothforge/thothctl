"""MCP Server for ThothCTL.

This module is deprecated. Please use thothctl.services.mcp instead.
"""

import warnings
from ..services.mcp import run_server, serve

warnings.warn(
    "The thothctl.mcp module is deprecated. Please use thothctl.services.mcp instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["run_server", "serve"]
