"""Serve command - Start the AI Review REST API server."""
import logging

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI

logger = logging.getLogger(__name__)


class ServeCommand(ClickCommand):
    """Start the AI Review REST API server for CI/CD integration."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        return True

    def _execute(self, host="0.0.0.0", port=8080, **kwargs):
        self.ui.print_info(f"Starting AI Review API on {host}:{port}")
        self.ui.print_info("Endpoints: /health, /analyze, /review, /fix")
        try:
            import uvicorn
            uvicorn.run(
                "thothctl.services.ai_review.bedrock_agent_api:app",
                host=host, port=port, log_level="info",
            )
        except ImportError:
            self.ui.print_error("uvicorn required. Install with: pip install uvicorn")
            raise click.Abort()


cli = ServeCommand.as_click_command(name="serve")(
    click.option("--host", default="0.0.0.0", help="Bind host"),
    click.option("--port", default=8080, type=int, help="Bind port"),
)
