"""MCP status command."""

import click
import requests
from colorama import Fore


@click.command(name="status")
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
def cli(port, host):
    """Check the status of the MCP server."""
    url = f"http://{host}:{port}/tools"
    
    try:
        response = requests.post(url, json={}, timeout=2)
        if response.status_code == 200:
            tools = response.json().get("tools", [])
            click.echo(f"{Fore.GREEN}✅ MCP server is running on {host}:{port}{Fore.RESET}")
            click.echo(f"{Fore.GREEN}Available tools: {len(tools)}{Fore.RESET}")
            
            for tool in tools:
                click.echo(f"  - {Fore.CYAN}{tool['name']}{Fore.RESET}: {tool['description']}")
        else:
            click.echo(f"{Fore.RED}❌ MCP server returned status code {response.status_code}{Fore.RESET}")
    except requests.exceptions.ConnectionError:
        click.echo(f"{Fore.RED}❌ Could not connect to MCP server at {host}:{port}{Fore.RESET}")
    except Exception as e:
        click.echo(f"{Fore.RED}❌ Error checking MCP server status: {str(e)}{Fore.RESET}")
