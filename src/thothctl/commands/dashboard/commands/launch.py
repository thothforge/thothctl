import logging
import click

from thothctl.services.dashboard.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

@click.command()
@click.option('--port', '-p', default=8080, help='Port to run the dashboard on')
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind the dashboard to')
@click.option('--debug', is_flag=True, help='Run in debug mode')
@click.option('--no-browser', is_flag=True, help='Do not open browser automatically')
@click.pass_context
def cli(ctx, port, host, debug, no_browser):
    """Launch the ThothCTL web dashboard"""
    try:
        dashboard = DashboardService(port=port, host=host)
        dashboard.run(debug=debug, open_browser=not no_browser)
    except KeyboardInterrupt:
        click.echo("\n👋 Dashboard stopped by user")
    except Exception as e:
        click.echo(f"❌ Error starting dashboard: {e}", err=True)
        raise click.Abort()
