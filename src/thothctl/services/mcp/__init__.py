"""MCP Service for ThothCTL."""

from .simple_http_server import run_simple_http_server as run_server
from .stdio_server import serve_amazon_q as serve

__all__ = ["run_server", "serve"]
