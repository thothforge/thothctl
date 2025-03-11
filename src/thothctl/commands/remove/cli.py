import click

from ...services.project.cleanup.clean_project import remove_projects


@click.command(name="list")
@click.option(
    "-pj",
    "--project-name",
    help="Project Name to delete",
    default=None,
)
def cli(project_name):
    """Remove Projects manage by thothctl"""
    remove_projects(project_name=project_name)
