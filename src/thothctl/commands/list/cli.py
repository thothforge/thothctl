import click

from ...common.common import print_list_projects


@click.command(name="list")
def cli():
    """List Projects manage by thothctl locally"""
    print_list_projects()
