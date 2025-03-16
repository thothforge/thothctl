import logging
from functools import wraps
from typing import Any, Callable, List

import click

from abc import ABC, abstractmethod


class ClickCommand(ABC):
    """Base class for all Click commands"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # Prevent propagation to parent loggers
        self.logger.propagate = False

        # Clear any existing handlers
        self.logger.handlers = []

        # Add single handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the command"""
        pass

    def validate(self, **kwargs) -> bool:
        """Validate command inputs"""
        return True

    def pre_execute(self, **kwargs) -> None:
        """Hook for pre-execution tasks"""
        pass

    def post_execute(self, **kwargs) -> None:
        """Hook for post-execution tasks"""
        pass

    def get_completions(
        self, ctx: click.Context, args: List[str], incomplete: str
    ) -> List[tuple]:
        """
        Get autocomplete suggestions.
        Override this method in subclasses to provide custom completions.
        Returns a list of tuples (completion, description)
        """
        return []

    @classmethod
    def as_click_command(cls, **click_options: Any) -> Callable:
        """Convert to Click command"""

        def decorator(*options: Any) -> click.Command:
            cmd_instance = cls()

            @click.command(**click_options)
            @wraps(options[0] if options else lambda: None)
            def wrapped_command(**kwargs: Any) -> Any:
                try:
                    cmd_instance.pre_execute(**kwargs)
                    if cmd_instance.validate(**kwargs):
                        result = cmd_instance.execute(**kwargs)
                        cmd_instance.post_execute(**kwargs)
                        return result
                except Exception as e:
                    cmd_instance.logger.error(str(e))
                    raise click.ClickException(str(e))

            # Add shell completion support
            def complete(
                ctx: click.Context, args: List[str], incomplete: str
            ) -> List[tuple]:
                return cmd_instance.get_completions(ctx, args, incomplete)

            wrapped_command.shell_complete = complete

            # Apply all options to the command
            command = wrapped_command
            for option in reversed(options):
                command = option(command)

            return command

        return decorator
