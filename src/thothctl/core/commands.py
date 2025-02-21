# src/thothctl/core/commands.py
import click
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from functools import wraps
import logging

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
        formatter = logging.Formatter('%(levelname)s - %(message)s')
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

            # Apply all options to the command
            command = wrapped_command
            for option in reversed(options):
                command = option(command)

            return command

        return decorator
