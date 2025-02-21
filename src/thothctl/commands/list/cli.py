import click
from ...common.common import print_list_projects

@click.command(name="list")
def cli():
    """Initialize space for your IDP"""
    print_list_projects()

