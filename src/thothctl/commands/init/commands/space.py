import click


@click.command(name="space")
@click.option("-sn", "--space-name", help="The space name")
@click.option(
    "-vcss",
    "--version-control-system-service",
    default="azure_repos",
    type=click.Choice(["azure_repos"], case_sensitive=True),
    help="The Version Control System Service for you IDP",
)
@click.option(
    "--ci",
    type=click.Choice(
        ["github-actions", "gitlab-ci", "azure-pipelines", "jenkins", "none"],
        case_sensitive=False,
    ),
    default="none",
    help="CI/CD tool to configure",
)
def cli(version_control_system_service, ci, space_name):
    """Initialize space for your IDP"""
    if version_control_system_service == "azure_repos":
        if ci == "none":
            click.echo(f"Initializing new project: {space_name}")
        else:
            print("Not implemented yet")
