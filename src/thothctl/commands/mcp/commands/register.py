"""MCP register command."""

import click
import subprocess
from colorama import Fore


@click.command(name="register")
@click.option(
    "-p",
    "--port",
    type=int,
    default=8080,
    help="Port of the MCP server",
)
@click.option(
    "-h",
    "--host",
    type=str,
    default="localhost",
    help="Host of the MCP server",
)
@click.option(
    "-n",
    "--name",
    type=str,
    default="thothctl",
    help="Name to register the MCP server with",
)
def cli(port, host, name):
    """Register the MCP server with Amazon Q."""
    url = f"http://{host}:{port}"
    
    try:
        # Check if q command is available
        result = subprocess.run(
            ["which", "q"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            click.echo(f"{Fore.RED}❌ Amazon Q CLI not found. Please install it first.{Fore.RESET}")
            click.echo(f"{Fore.YELLOW}To install Amazon Q CLI, follow the instructions at:{Fore.RESET}")
            click.echo(f"{Fore.YELLOW}https://docs.aws.amazon.com/amazonq/latest/cli-user-guide/getting-started.html{Fore.RESET}")
            return
        
        # Register with Amazon Q
        click.echo(f"{Fore.CYAN}Registering MCP server with Amazon Q as '{name}'...{Fore.RESET}")
        result = subprocess.run(
            ["q", "mcp", "add", name, url], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            click.echo(f"{Fore.GREEN}✅ Successfully registered MCP server with Amazon Q{Fore.RESET}")
            click.echo(f"{Fore.GREEN}You can now use ThothCTL with Amazon Q!{Fore.RESET}")
        else:
            click.echo(f"{Fore.RED}❌ Failed to register MCP server with Amazon Q{Fore.RESET}")
            click.echo(f"{Fore.RED}Error: {result.stderr}{Fore.RESET}")
    except Exception as e:
        click.echo(f"{Fore.RED}❌ Error registering MCP server: {str(e)}{Fore.RESET}")
