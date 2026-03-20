"""Configure command - manage AI provider settings."""
import logging

import click
from rich.table import Table

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.config.ai_settings import AISettings

logger = logging.getLogger(__name__)


class ConfigureCommand(ClickCommand):
    """Configure AI review provider settings."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, provider=None, api_key=None, model=None,
                 daily_limit=None, monthly_budget=None, show=False, **kwargs):
        settings = AISettings.load()

        if show:
            self._display_config(settings)
            return

        changed = False

        if provider:
            settings.default_provider = provider
            changed = True
            self.ui.print_success(f"Default provider set to: {provider}")

        if api_key and provider:
            pc = settings.get_provider_config(provider)
            pc.api_key = api_key
            changed = True
            self.ui.print_success(f"API key set for {provider}")

        if model and provider:
            pc = settings.get_provider_config(provider)
            pc.model = model
            changed = True
            self.ui.print_success(f"Model set to {model} for {provider}")

        if daily_limit is not None:
            settings.cost_controls.daily_limit = daily_limit
            changed = True
            self.ui.print_success(f"Daily limit set to: ${daily_limit}")

        if monthly_budget is not None:
            settings.cost_controls.monthly_budget = monthly_budget
            changed = True
            self.ui.print_success(f"Monthly budget set to: ${monthly_budget}")

        if changed:
            settings.save()
            self.ui.print_success("Configuration saved.")
        else:
            self.ui.print_warning("No changes specified. Use --show to view current config.")

    def _display_config(self, settings: AISettings):
        table = Table(title="AI Review Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Default Provider", settings.default_provider)
        table.add_row("Daily Limit", f"${settings.cost_controls.daily_limit}")
        table.add_row("Monthly Budget", f"${settings.cost_controls.monthly_budget}")
        table.add_row("Auto Fallback", str(settings.cost_controls.auto_fallback))
        table.add_row("Risk Threshold", settings.analysis.risk_threshold)

        for name, pc in settings.providers.items():
            table.add_row(f"[{name}] Model", pc.model or "default")
            table.add_row(f"[{name}] API Key", "***set***" if pc.api_key else "not set")
            if pc.endpoint:
                table.add_row(f"[{name}] Endpoint", pc.endpoint)

        self.ui.console.print(table)


cli = ConfigureCommand.as_click_command(name="configure")(
    click.option(
        "-p", "--provider",
        type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]),
        help="Set default AI provider",
    ),
    click.option("--api-key", help="Set API key for provider"),
    click.option("-m", "--model", help="Set model for provider"),
    click.option("--daily-limit", type=int, help="Set daily usage limit ($)"),
    click.option("--monthly-budget", type=float, help="Set monthly budget ($)"),
    click.option("--show", is_flag=True, help="Show current configuration"),
)
