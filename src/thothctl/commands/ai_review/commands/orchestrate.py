"""Orchestrate command — run multiple AI agents for comprehensive review."""
import json
import logging

import click
from rich.table import Table
from rich.panel import Panel

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.ai_review.orchestrator import AgentOrchestrator, AgentRole

logger = logging.getLogger(__name__)

ROLE_MAP = {
    "security": AgentRole.SECURITY,
    "architecture": AgentRole.ARCHITECTURE,
    "fix": AgentRole.FIX,
    "decision": AgentRole.DECISION,
    "all": None,  # sentinel
}


class OrchestrateCommand(ClickCommand):
    """Run multiple specialized AI agents for comprehensive IaC review."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, directory=None, provider=None, model=None,
                 agents=None, parallel=2, output=None, json_output=False,
                 repository=None, run_id=None, **kwargs):
        ctx = click.get_current_context()
        target = directory or ctx.obj.get("CODE_DIRECTORY", ".")

        # Parse agent roles
        if not agents or "all" in agents:
            roles = [AgentRole.SECURITY, AgentRole.ARCHITECTURE, AgentRole.FIX, AgentRole.DECISION]
        else:
            roles = [ROLE_MAP[a] for a in agents if a in ROLE_MAP and ROLE_MAP[a]]

        role_names = ", ".join(r.value for r in roles)
        self.ui.print_info(f"Orchestrating agents: {role_names}")
        self.ui.print_info(f"Target: {target} | Parallel: {parallel}")

        orchestrator = AgentOrchestrator(
            provider=provider, model=model, max_parallel=parallel,
        )

        with self.ui.status_spinner("Running AI agents..."):
            result = orchestrator.run_agents(
                target, roles=roles,
                repository=repository or "",
                run_id=run_id or "",
            )

        if json_output:
            data = {
                "security": result.security,
                "architecture": result.architecture,
                "fixes": result.fixes,
                "decision": result.decision,
                "errors": result.errors,
                "cost": result.cost,
            }
            click.echo(json.dumps(data, indent=2, default=str))
            if output:
                with open(output, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                self.ui.print_success(f"Results saved to {output}")
            return

        # Display results per agent
        if result.security:
            self._display_security(result.security)
        if result.architecture:
            self._display_architecture(result.architecture)
        if result.fixes:
            self._display_fixes(result.fixes)
        if result.decision:
            self._display_decision(result.decision)

        if result.errors:
            self.ui.console.print(Panel("\n".join(result.errors), title="⚠️ Agent Errors", border_style="yellow"))

        if output:
            data = {"security": result.security, "architecture": result.architecture,
                    "fixes": result.fixes, "decision": result.decision, "errors": result.errors}
            with open(output, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self.ui.print_success(f"Full results saved to {output}")

    def _display_security(self, data):
        summary = data.get("summary", {})
        table = Table(title="🔒 Security Agent")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_row("Risk Score", f"{data.get('risk_score', 0):.0f}/100")
        table.add_row("Critical", str(summary.get("critical", 0)))
        table.add_row("High", str(summary.get("high", 0)))
        table.add_row("Medium", str(summary.get("medium", 0)))
        table.add_row("Findings", str(summary.get("total_findings", 0)))
        self.ui.console.print(table)

    def _display_architecture(self, data):
        summary = data.get("summary", {})
        self.ui.console.print(Panel(
            data.get("overall_assessment", "No assessment available.")[:300],
            title="🏗️ Architecture Agent",
        ))

    def _display_fixes(self, data):
        fixes = data.get("fixes", [])
        summary = data.get("summary", {})
        self.ui.console.print(
            f"🔧 Fix Agent: {summary.get('fixes_generated', len(fixes))} fixes, "
            f"{summary.get('skipped', 0)} skipped"
        )

    def _display_decision(self, data):
        icons = {"approve": "✅", "reject": "🚫", "request_changes": "🔄", "comment": "💬"}
        action = data.get("action", "comment")
        self.ui.console.print(Panel(
            f"Action: {action.upper()}\n"
            f"Confidence: {data.get('confidence', 0):.0%}\n"
            f"Reason: {data.get('reason', '')}",
            title=f"{icons.get(action, '🤖')} Decision Agent",
        ))


cli = OrchestrateCommand.as_click_command(name="orchestrate")(
    click.option("-d", "--directory", type=click.Path(exists=True), help="Directory to analyze"),
    click.option("-p", "--provider", type=click.Choice(["openai", "bedrock", "bedrock_agent", "azure", "ollama"]), help="AI provider"),
    click.option("-m", "--model", help="Specific model"),
    click.option("-a", "--agents", multiple=True,
                 type=click.Choice(["security", "architecture", "fix", "decision", "all"]),
                 default=["all"], help="Which agents to run"),
    click.option("--parallel", type=int, default=2, help="Max parallel agents"),
    click.option("--repository", help="Repository identifier (owner/repo) for memory"),
    click.option("--run-id", help="Pipeline/PR identifier for isolation (e.g. pr/42, run/123)"),
    click.option("-o", "--output", type=click.Path(), help="Save results to JSON file"),
    click.option("--json", "json_output", is_flag=True, help="Output as JSON"),
)
