"""thothctl main cli."""
import importlib.util
from functools import wraps
from pathlib import Path
from typing import Optional
from importlib.metadata import version
import click


def global_options(f):
    @click.option("--debug", is_flag=True, help="Enable debug mode")
    @click.option(
        "-d",
        "--code-directory",
        type=click.Path(exists=True),
        help="Configuration file path",
        default=".",
    )

    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


class ThothCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    commands.append(item.name)
        except Exception as e:
            click.echo(f"Error listing commands: {e}", err=True)
            return []

        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            module_path = Path(__file__).parent / "commands" / cmd_name / "cli.py"

            if not module_path.exists():
                return None

            spec = importlib.util.spec_from_file_location(
                f"thothctl.commands.{cmd_name}.cli", str(module_path)
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return getattr(module, "cli", None)

        except Exception as e:
            click.echo(f"Error loading command {cmd_name}: {e}", err=True)
            return None


@click.command(cls=ThothCLI)
@click.version_option(version=version('thothctl'),
    prog_name='thothctl',
    message='%(prog)s version %(version)s',
    help='Show the version and exit.')
@global_options
@click.pass_context
def cli(ctx, debug, code_directory):
    """ThothForge CLI - The Open Source Internal Developer Platform CLI"""
    """Thoth CLI tool"""
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["CODE_DIRECTORY"] = code_directory


if __name__ == "__main__":
    cli()
