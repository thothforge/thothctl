import logging
import click
import os
import json
import subprocess
import re
from typing import Any, List, Optional, Dict, Tuple
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich import box
from rich.tree import Tree
from rich.text import Text
from rich.syntax import Syntax

from ....core.cli_ui import CliUI

from ....core.commands import ClickCommand
from ....services.check.project.risk_assessment import calculate_component_risks
from ....services.check.project.blast_radius_service import BlastRadiusService

logger = logging.getLogger(__name__)


class CheckIaCCommand(ClickCommand):
    """Command to Check IaC outputs and artifacts"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.console = Console()
        self.supported_check_types = ["tfplan", "deps", "blast-radius", "cost-analysis", "drift", "stack-optimizer"]

    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""

        if kwargs['check_type'] not in self.supported_check_types:
            self.logger.error(f"Unsupported Check type. Must be one of: {', '.join(self.supported_check_types)}")
            return False

        return True

    def _execute(self, **kwargs) -> Any:
        """Execute the check command """
        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY")

        # Store for post_execute
        self._post_to_pr = kwargs.get('post_to_pr', False)
        self._outmd = kwargs.get('outmd')
        self._space = kwargs.get('space')
        self._vcs_provider = kwargs.get('vcs_provider', 'auto')

        try:
            # Process based on check type
            if kwargs['check_type'] == "tfplan":
                # Process tfplan validation
                result = self._validate_tfplan(
                    directory=directory,
                    recursive=kwargs.get('recursive', False),
                    outmd=kwargs.get('outmd'),
                    dependencies=False,
                    tftool=kwargs.get('tftool', 'tofu')
                )
                return result
                
            # Handle dependency graph visualization - always use terragrunt
            elif kwargs['check_type'] == "deps":
                result = self._visualize_dependencies(
                    directory=directory,
                    dagtool='terragrunt',
                    output_format=kwargs.get('format', 'tree'),
                )
                return result
            elif kwargs['check_type'] == "blast-radius":
                self.ui.print_info("💥 Running blast radius assessment...")
                result = self._run_blast_radius_check(directory=directory, **kwargs)
                return result
            elif kwargs['check_type'] == "cost-analysis":
                self.ui.print_info("💰 Running cost analysis...")
                result = self._run_cost_analysis(directory=directory, **kwargs)
                return result
            elif kwargs['check_type'] == "drift":
                self.ui.print_info("🔍 Running drift detection...")
                result = self._run_drift_detection(directory=directory, **kwargs)
                return result
            elif kwargs['check_type'] == "stack-optimizer":
                result = self._run_stack_optimizer(directory=directory, **kwargs)
                return result

            self.logger.debug("Check completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to execute check command: {str(e)}")
            raise

    def post_execute(self, **kwargs) -> None:
        """Post results to PR if --post-to-pr flag is set."""
        if not getattr(self, '_post_to_pr', False):
            return

        from ....core.integrations.pr_comments.pr_comment_publisher import (
            format_check_results,
            publish_to_pr,
        )

        # Try markdown file first (tfplan, deps)
        outmd = getattr(self, '_outmd', None)
        if outmd and os.path.exists(outmd):
            content = format_check_results(outmd)
        # Blast radius assessment
        elif getattr(self, '_blast_assessment', None):
            content = self._build_blast_radius_markdown(self._blast_assessment)
        # Drift detection results
        elif getattr(self, '_drift_summary', None):
            from ....services.check.project.drift.drift_report import DriftReportGenerator
            content = DriftReportGenerator().generate_markdown(self._drift_summary)
        # Fall back to cost analysis results
        elif getattr(self, '_cost_results', None):
            content = self._build_cost_markdown(self._cost_results)
        else:
            self.ui.print_warning("No results found to post to PR")
            return

        if publish_to_pr(
            content=content,
            vcs_provider=getattr(self, '_vcs_provider', 'auto'),
            space=getattr(self, '_space', None),
        ):
            self.ui.print_success("✅ Results posted to PR")
        else:
            self.ui.print_warning("⚠️ Could not post results to PR")

    def _build_cost_markdown(self, cost_results: list) -> str:
        """Build markdown summary from cost analysis results."""
        total_monthly = sum(r["analysis"].total_monthly_cost for r in cost_results)
        total_annual = sum(r["analysis"].total_annual_cost for r in cost_results)

        lines = [
            "## 💰 ThothCTL Cost Analysis Summary\n",
            f"| Stack | Monthly Cost | Annual Cost |",
            f"|-------|-------------|-------------|",
        ]

        for r in cost_results:
            a = r["analysis"]
            lines.append(f"| {r['stack']} | ${a.total_monthly_cost:.2f} | ${a.total_annual_cost:.2f} |")

        lines.append(f"| **TOTAL** | **${total_monthly:.2f}** | **${total_annual:.2f}** |")

        # Service breakdown across all stacks
        services = {}
        for r in cost_results:
            for svc, cost in (r["analysis"].cost_breakdown_by_service or {}).items():
                services[svc] = services.get(svc, 0) + cost

        if services:
            lines.append("\n### Cost by Service\n")
            lines.append("| Service | Monthly Cost |")
            lines.append("|---------|-------------|")
            for svc, cost in sorted(services.items(), key=lambda x: -x[1]):
                lines.append(f"| {svc} | ${cost:.2f} |")

        lines.append("\n---")
        lines.append("*Posted by [ThothCTL](https://github.com/thothforge/thothctl)*")
        return "\n".join(lines)

    def _build_blast_radius_markdown(self, assessment) -> str:
        """Build markdown summary from blast radius assessment."""
        lines = [
            "## 💥 ThothCTL Blast Radius Assessment\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Risk Level | {assessment.risk_level.value.upper()} |",
            f"| Change Type | {assessment.change_type.value.upper()} |",
            f"| Total Components | {assessment.total_components} |",
            f"| Affected Components | {len(assessment.affected_components)} |",
        ]

        if assessment.affected_components:
            lines.append("\n### Affected Components\n")
            lines.append("| Component | Change | Risk | Criticality |")
            lines.append("|-----------|--------|------|-------------|")
            for comp in assessment.affected_components:
                lines.append(f"| {comp.name} | {comp.change_type} | {comp.risk_score:.2f} | {comp.criticality} |")

        if assessment.recommendations:
            lines.append("\n### ITIL v4 Recommendations\n")
            for rec in assessment.recommendations:
                lines.append(f"- {rec}")

        lines.append("\n---")
        lines.append("*Posted by [ThothCTL](https://github.com/thothforge/thothctl)*")
        return "\n".join(lines)

    def _validate_tfplan(self, directory: str, recursive: bool = False, outmd: str = None, dependencies: bool = False,
                         tftool: str = 'tofu') -> bool:
        """Validate terraform plan files"""
        self.logger.info(f"Validating {tftool} plan in {directory} (recursive: {recursive})")

        # Find tfplan files - only JSON files
        tfplan_files = self._find_tfplan_files(directory, recursive)

        if not tfplan_files:
            self.console.print(f"[yellow]No {tftool} JSON plan files found in the specified directory[/yellow]")
            return False

        # Process each tfplan file
        results = []
        for tfplan_file in tfplan_files:
            result = self._process_tfplan_file(tfplan_file, dependencies, tftool)
            results.append(result)

        # Generate summary
        summary = self._generate_summary(results)

        # Display rich output
        self._display_rich_output(summary, results, tftool)

        # Generate markdown if requested
        if outmd:
            self._generate_markdown(outmd, summary, results, tftool)
            self.console.print(f"[green]Markdown report generated: {outmd}[/green]")

        return True

    def _find_tfplan_files(self, directory: str, recursive: bool, prefer_json: bool = True) -> List[str]:
        """Find tfplan files in the directory, only processing JSON files"""
        tfplan_files = []
        json_files = []

        if recursive:
            # Find all JSON tfplan files recursively
            for root, _, files in os.walk(directory):
                for file in files:
                    if file == "tfplan.json":
                        json_files.append(os.path.join(root, file))
        else:
            # Find JSON tfplan files only in the current directory
            for file in os.listdir(directory):
                if file == "tfplan.json":
                    json_files.append(os.path.join(directory, file))

        # Only return JSON files
        tfplan_files = json_files

        return tfplan_files

    def _process_tfplan_file(self, tfplan_file: str, dependencies: bool, tftool: str) -> Dict:
        """Process a single tfplan file"""
        self.logger.info(f"Processing {tftool} plan file: {tfplan_file}")

        result = {
            "file": tfplan_file,
            "resources": [],
            "changes": {
                "create": [],
                "update": [],
                "delete": [],
                "no_op": []
            },
            "issues": [],
            "dependencies": []
        }

        # Check if file exists and is readable
        if not os.path.isfile(tfplan_file):
            result["issues"].append(f"File not found: {tfplan_file}")
            return result

        # Process JSON tfplan file
        try:
            with open(tfplan_file, 'r') as f:
                plan_data = json.load(f)

            # Extract resources and categorize by action
            self._extract_resources_from_json(plan_data, result)

            # Extract dependencies if requested
            if dependencies:
                self._extract_dependencies_from_json(plan_data, result)

        except Exception as e:
            result["issues"].append(f"Error parsing JSON: {str(e)}")

        return result

    def _extract_resources_from_json(self, plan_data: Dict, result: Dict) -> None:
        """Extract resources from JSON plan data and categorize by action"""
        # Extract resources from planned_values
        if "planned_values" in plan_data and "root_module" in plan_data["planned_values"]:
            resources = plan_data["planned_values"]["root_module"].get("resources", [])
            result["resources"] = resources

        # Extract resource changes
        if "resource_changes" in plan_data:
            for change in plan_data["resource_changes"]:
                action = change.get("change", {}).get("actions", ["no-op"])

                # Create a simplified resource representation
                resource_info = {
                    "address": change.get("address", "unknown"),
                    "type": change.get("type", "unknown"),
                    "name": change.get("name", "unknown"),
                    "provider": change.get("provider_name", "unknown")
                }

                # Categorize by action
                if "create" in action:
                    result["changes"]["create"].append(resource_info)
                elif "update" in action:
                    result["changes"]["update"].append(resource_info)
                elif "delete" in action:
                    result["changes"]["delete"].append(resource_info)
                else:
                    result["changes"]["no_op"].append(resource_info)

    def _extract_dependencies_from_json(self, plan_data: Dict, result: Dict) -> None:
        """Extract dependencies from JSON plan data"""
        if "configuration" in plan_data and "root_module" in plan_data["configuration"]:
            deps = []
            for resource in plan_data["configuration"]["root_module"].get("resources", []):
                if "depends_on" in resource:
                    deps.append({
                        "resource": f"{resource.get('type', '')}.{resource.get('name', '')}",
                        "depends_on": resource["depends_on"]
                    })
            result["dependencies"] = deps

    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Generate a summary of the results"""
        summary = {
            "total_files": len(results),
            "total_resources": sum(len(result.get("resources", [])) for result in results),
            "total_issues": sum(len(result.get("issues", [])) for result in results),
            "resource_types": {},
            "files_with_issues": [],
            "changes": {
                "create": 0,
                "update": 0,
                "delete": 0,
                "no_op": 0
            }
        }

        # Count resource types from both resources and changes
        for result in results:
            # Count from resources section
            for resource in result.get("resources", []):
                resource_type = resource.get("type", "unknown")
                if resource_type in summary["resource_types"]:
                    summary["resource_types"][resource_type] += 1
                else:
                    summary["resource_types"][resource_type] = 1

            # Count from changes section for more complete coverage
            for action in ["create", "update", "delete", "no_op"]:
                for resource in result["changes"].get(action, []):
                    resource_type = resource.get("type", "unknown")
                    if resource_type in summary["resource_types"]:
                        summary["resource_types"][resource_type] += 1
                    else:
                        summary["resource_types"][resource_type] = 1

        # Count changes by action
        for result in results:
            summary["changes"]["create"] += len(result["changes"]["create"])
            summary["changes"]["update"] += len(result["changes"]["update"])
            summary["changes"]["delete"] += len(result["changes"]["delete"])
            summary["changes"]["no_op"] += len(result["changes"]["no_op"])

        # List files with issues
        for result in results:
            if result.get("issues"):
                summary["files_with_issues"].append({
                    "file": result["file"],
                    "issues": result["issues"]
                })

        return summary

    def _display_rich_output(self, summary: Dict, results: List[Dict], tftool: str):
        """Display rich output in the terminal"""
        # Display summary
        self.console.print(
            Panel(f"[bold blue]{tftool.capitalize()} Plan Analysis Summary[/bold blue]", box=box.ROUNDED))

        # Display changes summary with color coding
        changes_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        changes_table.add_column("Action")
        changes_table.add_column("Count")

        changes_table.add_row("Create", f"[green]{summary['changes']['create']}[/green]")
        changes_table.add_row("Update", f"[yellow]{summary['changes']['update']}[/yellow]")
        changes_table.add_row("Delete", f"[red]{summary['changes']['delete']}[/red]")
        changes_table.add_row("No Change", f"[blue]{summary['changes']['no_op']}[/blue]")
        changes_table.add_row("Total",
                              f"[bold]{summary['changes']['create'] + summary['changes']['update'] + summary['changes']['delete'] + summary['changes']['no_op']}[/bold]")

        self.console.print(changes_table)

        # Display detailed changes if any
        if summary['changes']['create'] > 0 or summary['changes']['update'] > 0 or summary['changes']['delete'] > 0:
            self.console.print("\n[bold]Resource Changes:[/bold]")

            # Create a tree for better visualization
            tree = Tree("[bold]Changes[/bold]")

            # Add resources to be created
            if summary['changes']['create'] > 0:
                create_node = tree.add("[green]Create[/green]")
                for result in results:
                    for resource in result["changes"]["create"]:
                        create_node.add(f"[green]{resource['address']} ({resource['provider']})[/green]")

            # Add resources to be updated
            if summary['changes']['update'] > 0:
                update_node = tree.add("[yellow]Update[/yellow]")
                for result in results:
                    for resource in result["changes"]["update"]:
                        update_node.add(f"[yellow]{resource['address']} ({resource['provider']})[/yellow]")

            # Add resources to be deleted
            if summary['changes']['delete'] > 0:
                delete_node = tree.add("[red]Delete[/red]")
                for result in results:
                    for resource in result["changes"]["delete"]:
                        delete_node.add(f"[red]{resource['address']} ({resource['provider']})[/red]")

            self.console.print(tree)

        # Display resource types with change information
        if summary["resource_types"]:
            self.console.print("\n[bold]Resource Types with Change Information:[/bold]")

            resource_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            resource_table.add_column("Resource Type")
            resource_table.add_column("Count")
            resource_table.add_column("Change Type")  # New column

            # Create a mapping of resource types to their change types
            resource_change_types = {}
            
            for result in results:
                # Process create actions
                for resource in result["changes"]["create"]:
                    resource_type = resource.get("type", "unknown")
                    resource_change_types[resource_type] = "Create"
                    
                # Process update actions
                for resource in result["changes"]["update"]:
                    resource_type = resource.get("type", "unknown")
                    resource_change_types[resource_type] = "Update"
                    
                # Process delete actions
                for resource in result["changes"]["delete"]:
                    resource_type = resource.get("type", "unknown")
                    resource_change_types[resource_type] = "Delete"

            # Add rows to the table with change type information
            for resource_type, count in sorted(summary["resource_types"].items()):
                change_type = resource_change_types.get(resource_type, "No Change")
                
                # Color-code the change type
                if change_type == "Create":
                    formatted_change = f"[green]{change_type}[/green]"
                elif change_type == "Update":
                    formatted_change = f"[yellow]{change_type}[/yellow]"
                elif change_type == "Delete":
                    formatted_change = f"[red]{change_type}[/red]"
                else:
                    formatted_change = f"[blue]{change_type}[/blue]"
                    
                resource_table.add_row(resource_type, str(count), formatted_change)

            self.console.print(resource_table)

        # Display issues
        if summary["files_with_issues"]:
            self.console.print("\n[bold red]Issues Found:[/bold red]")

            for file_issue in summary["files_with_issues"]:
                self.console.print(f"\n[yellow]File: {file_issue['file']}[/yellow]")

                for issue in file_issue["issues"]:
                    self.console.print(f"  - {issue}")

    def _generate_markdown(self, outmd: str, summary: Dict, results: List[Dict], tftool: str):
        """Generate markdown report"""
        with open(outmd, 'w') as f:
            f.write(f"# {tftool.capitalize()} Plan Analysis Report\n\n")

            # Summary section
            f.write("## Summary\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Total Files | {summary['total_files']} |\n")
            f.write(f"| Total Resources | {summary['total_resources']} |\n")
            f.write(f"| Files with Issues | {len(summary['files_with_issues'])} |\n")
            f.write(f"| Total Issues | {summary['total_issues']} |\n\n")

            # Changes section
            f.write("## Changes\n\n")
            f.write("| Action | Count |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Create | {summary['changes']['create']} |\n")
            f.write(f"| Update | {summary['changes']['update']} |\n")
            f.write(f"| Delete | {summary['changes']['delete']} |\n")
            f.write(f"| No Change | {summary['changes']['no_op']} |\n")
            f.write(
                f"| **Total** | **{summary['changes']['create'] + summary['changes']['update'] + summary['changes']['delete'] + summary['changes']['no_op']}** |\n\n")

            # Detailed changes
            if summary['changes']['create'] > 0:
                f.write("### Resources to Create\n\n")
                for result in results:
                    for resource in result["changes"]["create"]:
                        f.write(f"- `{resource['address']}` ({resource['provider']})\n")
                f.write("\n")

            if summary['changes']['update'] > 0:
                f.write("### Resources to Update\n\n")
                for result in results:
                    for resource in result["changes"]["update"]:
                        f.write(f"- `{resource['address']}` ({resource['provider']})\n")
                f.write("\n")

            if summary['changes']['delete'] > 0:
                f.write("### Resources to Delete\n\n")
                for result in results:
                    for resource in result["changes"]["delete"]:
                        f.write(f"- `{resource['address']}` ({resource['provider']})\n")
                f.write("\n")

            # Resource types section with change information
            if summary["resource_types"]:
                f.write("## Resource Types with Change Information\n\n")
                f.write("| Resource Type | Count | Change Type |\n")
                f.write("|--------------|-------|-------------|\n")

                # Create a mapping of resource types to their change types
                resource_change_types = {}
                
                for result in results:
                    # Process create actions
                    for resource in result["changes"]["create"]:
                        resource_type = resource.get("type", "unknown")
                        resource_change_types[resource_type] = "Create"
                        
                    # Process update actions
                    for resource in result["changes"]["update"]:
                        resource_type = resource.get("type", "unknown")
                        resource_change_types[resource_type] = "Update"
                        
                    # Process delete actions
                    for resource in result["changes"]["delete"]:
                        resource_type = resource.get("type", "unknown")
                        resource_change_types[resource_type] = "Delete"

                for resource_type, count in sorted(summary["resource_types"].items()):
                    change_type = resource_change_types.get(resource_type, "No Change")
                    f.write(f"| {resource_type} | {count} | {change_type} |\n")

                f.write("\n")

            # Issues section
            if summary["files_with_issues"]:
                f.write("## Issues\n\n")

                for file_issue in summary["files_with_issues"]:
                    f.write(f"### {file_issue['file']}\n\n")

                    for issue in file_issue["issues"]:
                        f.write(f"- {issue}\n")

                    f.write("\n")

            # Dependencies section
            has_dependencies = any(result.get("dependencies") for result in results)
            if has_dependencies:
                f.write("## Dependencies\n\n")

                for result in results:
                    if result["dependencies"]:
                        f.write(f"### {result['file']}\n\n")
                        f.write("| Resource | Depends On |\n")
                        f.write("|----------|------------|\n")

                        for dep in result["dependencies"]:
                            resource = dep.get("resource", "unknown")
                            depends_on = ", ".join(dep.get("depends_on", []))

                            f.write(f"| {resource} | {depends_on} |\n")

                        f.write("\n")

    def _visualize_dependencies(self, directory: str, dagtool: str = 'terragrunt', output_format: str = 'tree') -> bool:
        """Visualize infrastructure dependencies using terragrunt graph commands"""
        self.logger.info(f"Visualizing dependencies in {directory} using {dagtool}")
        
        try:
            # Use terragrunt dag graph command
            cmd = [dagtool, "dag", "graph"]
            self.console.print("[blue]📊 Generating dependency graph...[/blue]")
            
            # Check if workspace parameter should be added
            if os.path.exists(os.path.join(directory, "terragrunt.hcl")):
                cmd.extend(["--working-dir", directory])
            
            # Run the command
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                self.console.print(f"[red]Error running {dagtool} command:[/red]")
                self.console.print(result.stderr)
                return False
            
            dot_graph = result.stdout

            # Route to the appropriate renderer
            if output_format == "dot":
                click.echo(dot_graph)
                return True
            elif output_format == "boxart":
                return self._render_boxart(dot_graph, directory)
            elif output_format == "html":
                return self._render_html_topology(dot_graph, directory)

            # Default: tree format
            nodes, edges = self._parse_dot_graph(dot_graph)
            risks = calculate_component_risks(nodes, edges, directory)
            dep_info = self._parse_terragrunt_dependencies(directory)
            self._display_dependency_graph(dot_graph, risks, dep_info, directory)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to visualize dependencies: {str(e)}")
            self.console.print(f"[red]Error: {str(e)}[/red]")
            return False
    

    def _render_boxart(self, dot_graph: str, directory: str) -> bool:
        """Render dependency graph as ASCII box art using graph-easy or fallback."""
        # Try graph-easy first (best output)
        try:
            result = subprocess.run(
                ['graph-easy', '--from=dot', '--as=boxart'],
                input=dot_graph, capture_output=True, text=True, check=True
            )
            self.console.print(Panel("[bold blue]🔄 Dependency Topology[/bold blue]", box=box.ROUNDED))
            click.echo(result.stdout)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Fallback: pure Python box rendering
        nodes, edges = self._parse_dot_graph(dot_graph)
        risks = calculate_component_risks(nodes, edges, directory)

        self.console.print(Panel("[bold blue]🔄 Dependency Topology (boxart)[/bold blue]", box=box.ROUNDED))
        self.console.print("[dim]Install graph-easy for better rendering: sudo apt install libgraph-easy-perl[/dim]\n")

        # Simple layered box drawing
        # Build adjacency: who depends on whom
        dependents = {n: set() for n in nodes}
        for src, tgt in edges:
            if src in dependents:
                dependents[src].add(tgt)

        # Find layers (topological sort by depth)
        depth = {n: 0 for n in nodes}
        changed = True
        while changed:
            changed = False
            for src, tgt in edges:
                if depth.get(src, 0) <= depth.get(tgt, 0):
                    depth[src] = depth[tgt] + 1
                    changed = True

        max_depth = max(depth.values()) if depth else 0
        layers = [[] for _ in range(max_depth + 1)]
        for n, d in depth.items():
            layers[max_depth - d].append(n)

        # Render boxes per layer
        for i, layer in enumerate(layers):
            if not layer:
                continue
            boxes = []
            for node in layer:
                short = node.split("/")[-1] if "/" in node else node
                risk = risks.get(node, 0)
                boxes.append(f"┌{'─' * (len(short) + 6)}┐")
                boxes.append(f"│ {short} {risk:.0f}% │")
                boxes.append(f"└{'─' * (len(short) + 6)}┘")

            # Print boxes side by side
            lines_per_box = 3
            row_boxes = [boxes[j:j+lines_per_box] for j in range(0, len(boxes), lines_per_box)]
            for line_idx in range(lines_per_box):
                click.echo("  ".join(b[line_idx] for b in row_boxes))

            # Print arrows between layers
            if i < len(layers) - 1:
                click.echo("         │")
                click.echo("         ▼")

        return True

    def _render_html_topology(self, dot_graph: str, directory: str) -> bool:
        """Render interactive HTML topology and open in browser."""
        import webbrowser
        from pathlib import Path

        nodes, edges = self._parse_dot_graph(dot_graph)
        risks = calculate_component_risks(nodes, edges, directory)

        # Build nodes/edges JSON for vis.js
        vis_nodes = []
        for i, node in enumerate(nodes):
            short = node.split("/")[-1] if "/" in node else node
            risk = risks.get(node, 0)
            color = "#4caf50" if risk < 30 else "#ff9800" if risk < 50 else "#f44336"
            vis_nodes.append(f'{{id: {i}, label: "{short}\\n{risk:.0f}% risk", color: "{color}", title: "{node}"}}')

        node_idx = {n: i for i, n in enumerate(nodes)}
        vis_edges = []
        for src, tgt in edges:
            if src in node_idx and tgt in node_idx:
                vis_edges.append(f'{{from: {node_idx[src]}, to: {node_idx[tgt]}, arrows: "to"}}')

        html = f"""<!DOCTYPE html>
<html><head><title>ThothCTL - Dependency Topology</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
body {{ margin: 0; font-family: Inter, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
#graph {{ width: 100vw; height: 100vh; }}
h1 {{ position: absolute; top: 10px; left: 20px; color: white; font-size: 1.2em; z-index: 10; }}
</style></head><body>
<h1>🔄 ThothCTL Dependency Topology</h1>
<div id="graph"></div>
<script>
var nodes = new vis.DataSet([{', '.join(vis_nodes)}]);
var edges = new vis.DataSet([{', '.join(vis_edges)}]);
var container = document.getElementById('graph');
var data = {{ nodes: nodes, edges: edges }};
var options = {{
  layout: {{ hierarchical: {{ direction: "UD", sortMethod: "directed" }} }},
  physics: false,
  nodes: {{ shape: "box", font: {{ size: 14 }}, margin: 10 }},
  edges: {{ color: "#ffffff80", width: 2 }}
}};
new vis.Network(container, data, options);
</script></body></html>"""

        out_path = Path(directory) / "Reports" / "dependency_topology.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html)

        self.console.print(f"[green]✅ HTML topology saved to {out_path}[/green]")
        webbrowser.open(f"file://{out_path.resolve()}")
        return True

    def _parse_terragrunt_dependencies(self, directory: str) -> Dict[str, Dict]:
        """Parse terragrunt.hcl files to extract dependency and mock_outputs information.
        
        Args:
            directory: Directory to search for terragrunt.hcl files
            
        Returns:
            Dictionary mapping stack paths to their dependency information
        """
        import hcl2
        dependencies_info = {}
        
        try:
            # Find all terragrunt.hcl files
            for root, dirs, files in os.walk(directory):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in ['.terraform', '.terragrunt-cache', '.git']]
                
                if 'terragrunt.hcl' in files:
                    hcl_path = os.path.join(root, 'terragrunt.hcl')
                    try:
                        with open(hcl_path, 'r') as f:
                            content = f.read()
                            # Parse HCL
                            parsed = hcl2.loads(content)
                            
                            # Extract dependency blocks
                            if 'dependency' in parsed:
                                stack_name = os.path.relpath(root, directory)
                                dependencies_info[stack_name] = {
                                    'dependencies': {},
                                    'path': root
                                }
                                
                                # hcl2 returns dependency as a list of dicts
                                for dep_block in parsed['dependency']:
                                    for dep_name, dep_config in dep_block.items():
                                        config_path = dep_config.get('config_path', [''])[0] if isinstance(dep_config.get('config_path'), list) else dep_config.get('config_path', '')
                                        mock_outputs_list = dep_config.get('mock_outputs', [])
                                        mock_outputs = mock_outputs_list[0] if mock_outputs_list else {}
                                        
                                        dep_info = {
                                            'config_path': config_path,
                                            'mock_outputs': mock_outputs
                                        }
                                        dependencies_info[stack_name]['dependencies'][dep_name] = dep_info
                    
                    except Exception as e:
                        self.logger.debug(f"Could not parse {hcl_path}: {e}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error parsing terragrunt files: {e}")
        
        return dependencies_info
    
    def _display_dependency_graph(self, dot_graph: str, risks: Dict[str, float] = None, dep_info: Dict = None, directory: str = ".") -> None:
        """
        Display the dependency graph in a visually appealing way
        
        Args:
            dot_graph: DOT graph string
            risks: Dictionary mapping component names to risk percentages
            dep_info: Dictionary with parsed dependency and mock_outputs information
        """
        self.console.print(Panel("[bold blue]🔄 Enhanced Dependency Visualization 🔄[/bold blue]", box=box.ROUNDED))
        
        # Parse the DOT graph to extract nodes and edges
        nodes, edges = self._parse_dot_graph(dot_graph)
        
        # Create a rich tree representation with risk percentages
        tree = self._create_dependency_tree(nodes, edges, risks)
        
        # Display the tree visualization
        self.console.print(tree)
        
        # Display dependency details if available
        if dep_info:
            self._display_dependency_details(dep_info)

        # Display summary
        total_modules = self._count_modules_in_stacks(nodes, directory)
        self.console.print(
            f"\n[green]✅ Found {len(nodes)} stacks, "
            f"{total_modules} modules, "
            f"{len(edges)} dependencies[/green]"
        )

        # Display risk legend
        if risks:
            self._display_risk_legend()
    
    def _display_dependency_details(self, dep_info: Dict) -> None:
        """Display detailed dependency information from terragrunt.hcl files.
        
        Args:
            dep_info: Dictionary with parsed dependency and mock_outputs information
        """
        self.console.print("\n")
        self.console.print(Panel("[bold cyan]📋 Dependency Details (from terragrunt.hcl)[/bold cyan]", box=box.ROUNDED))
        
        for stack_name, info in dep_info.items():
            if info['dependencies']:
                self.console.print(f"\n[bold yellow]{stack_name}[/bold yellow]")
                
                for dep_name, dep_config in info['dependencies'].items():
                    self.console.print(f"  └─ [cyan]{dep_name}[/cyan]")
                    self.console.print(f"     Path: [dim]{dep_config['config_path']}[/dim]")
                    
                    # Display mock_outputs if available
                    if dep_config['mock_outputs']:
                        self.console.print(f"     Mock Outputs:")
                        for key, value in dep_config['mock_outputs'].items():
                            # Truncate long values
                            value_str = str(value)
                            if len(value_str) > 50:
                                value_str = value_str[:47] + "..."
                            self.console.print(f"       • {key} = [green]{value_str}[/green]")


    def _count_modules_in_stacks(self, nodes: list, directory: str) -> int:
        """Count total module blocks across all stacks."""
        import re
        total = 0
        for node in nodes:
            stack_dir = os.path.join(directory, node)
            if not os.path.isdir(stack_dir):
                continue
            for f in os.listdir(stack_dir):
                if f.endswith(".tf"):
                    try:
                        content = open(os.path.join(stack_dir, f)).read()
                        total += len(re.findall(r'^module\s+"', content, re.MULTILINE))
                    except OSError:
                        pass
        return total

    def _display_risk_legend(self) -> None:
        """Display a legend for risk levels"""
        legend = Table(show_header=False, box=box.SIMPLE)
        legend.add_column("Risk Level", style="bold")
        legend.add_column("Description")
        
        legend.add_row("[green]Low Risk (0-25%)[/green]", "Minimal risk of issues if changed")
        legend.add_row("[yellow]Medium Risk (26-50%)[/yellow]", "Moderate risk, changes should be reviewed")
        legend.add_row("[orange1]High Risk (51-75%)[/orange1]", "Significant risk, careful testing needed")
        legend.add_row("[red]Critical Risk (76-100%)[/red]", "Very high risk, changes may cause cascading issues")
        
        self.console.print("\n[bold]Risk Level Legend:[/bold]")
        self.console.print(legend)
    
    def _parse_dot_graph(self, dot_graph: str) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Parse the DOT graph to extract nodes and edges"""
        nodes = []
        edges = []
        
        # Extract nodes (all quoted strings that aren't part of an edge)
        node_pattern = r'"([^"]+)"\s*;'
        for match in re.finditer(node_pattern, dot_graph):
            nodes.append(match.group(1))
        
        # Extract edges (connections between nodes)
        edge_pattern = r'"([^"]+)"\s*->\s*"([^"]+)"'
        for match in re.finditer(edge_pattern, dot_graph):
            edges.append((match.group(1), match.group(2)))
        
        return nodes, edges
    
    def _create_dependency_tree(self, nodes: List[str], edges: List[Tuple[str, str]], 
                             risks: Dict[str, float] = None) -> Tree:
        """
        Create a rich tree visualization of the dependency graph
        
        Args:
            nodes: List of node names
            edges: List of edges (source, target)
            risks: Dictionary mapping component names to risk percentages
            
        Returns:
            Rich Tree object
        """
        # Find root nodes (nodes with no incoming edges)
        incoming_edges = {node: [] for node in nodes}
        for source, target in edges:
            incoming_edges[target].append(source)
        
        root_nodes = [node for node in nodes if not incoming_edges[node]]
        
        # If no root nodes found, use all nodes as potential roots
        if not root_nodes:
            root_nodes = nodes
        
        # Create the main tree
        main_tree = Tree("[bold]Infrastructure Modules[/bold]")
        
        # Track processed nodes to avoid cycles
        processed = set()
        
        # Build tree for each root node
        for root in root_nodes:
            if root not in processed:
                # Format node with risk percentage if available
                if risks and root in risks:
                    risk_percent = risks[root]
                    risk_color = self._get_risk_color(risk_percent)
                    node_label = f"[{risk_color}]{root} ({risk_percent:.1f}% risk)[/{risk_color}]"
                else:
                    node_label = f"[bold blue]{root}[/bold blue]"
                
                node_tree = main_tree.add(node_label)
                self._build_tree_recursive(root, edges, node_tree, processed, risks=risks)
        
        return main_tree
    
    def _build_tree_recursive(self, current_node: str, edges: List[Tuple[str, str]], 
                             tree_node: Tree, processed: set, depth: int = 0, risks: Dict[str, float] = None) -> None:
        """
        Recursively build the dependency tree
        
        Args:
            current_node: Current node being processed
            edges: List of edges (source, target)
            tree_node: Current tree node
            processed: Set of already processed nodes
            depth: Current recursion depth
            risks: Dictionary mapping component names to risk percentages
        """
        # Avoid infinite recursion
        if depth > 10 or current_node in processed:
            return
        
        processed.add(current_node)
        
        # Find all edges where this node is the source
        for source, target in edges:
            if source == current_node:
                # Format node with risk percentage if available
                if risks and target in risks:
                    risk_percent = risks[target]
                    risk_color = self._get_risk_color(risk_percent)
                    node_label = f"[{risk_color}]{target} ({risk_percent:.1f}% risk)[/{risk_color}]"
                else:
                    node_label = f"[green]{target}[/green]"
                
                child = tree_node.add(node_label)
                self._build_tree_recursive(target, edges, child, processed, depth + 1, risks=risks)
    
    def _get_risk_color(self, risk_percent: float) -> str:
        """
        Get color based on risk percentage
        
        Args:
            risk_percent: Risk percentage (0-100)
            
        Returns:
            Color name for rich formatting
        """
        if risk_percent <= 25:
            return "green"
        elif risk_percent <= 50:
            return "yellow"
        elif risk_percent <= 75:
            return "orange1"  # Using orange1 as "orange" isn't a standard Rich color
        else:
            return "red"

    def _run_blast_radius_check(self, directory: str, recursive: bool = False, **kwargs) -> bool:
        """Run blast radius assessment combining deps and plan analysis."""
        try:
            live_mode = kwargs.get('live', False)
            stack_name = kwargs.get('stack_name')

            # Detect project type
            from ....services.scan.scan_service import ScanService
            scan_svc = ScanService()
            project_type = scan_svc.detect_project_type(directory)
            self.logger.info(f"Blast radius: project_type={project_type}, live={live_mode}")

            # Route to CFN/CDK blast radius for non-terraform projects
            if project_type in ("cloudformation", "cdk"):
                # Remove keys that are passed explicitly to avoid duplicates
                cfn_kwargs = {k: v for k, v in kwargs.items()
                              if k not in ("live", "stack_name", "plan_file")}
                return self._run_cfn_blast_radius(
                    directory=directory,
                    recursive=recursive,
                    project_type=project_type,
                    live=live_mode,
                    stack_name=stack_name,
                    **cfn_kwargs,
                )

            # Terraform: use existing logic
            # Use explicit plan file if provided, otherwise auto-discover
            explicit_plan = kwargs.get('plan_file')
            if explicit_plan and os.path.exists(explicit_plan):
                tfplan_files = [explicit_plan]
            else:
                tfplan_files = self._find_tfplan_files(directory, recursive)
            
            if not tfplan_files:
                self.ui.print_warning("No tfplan.json files found. Run 'terraform plan -out=tfplan && terraform show -json tfplan > tfplan.json' first.")
                return False
            
            blast_service = BlastRadiusService()
            
            # Use the first tfplan file found (or could process all)
            plan_file = tfplan_files[0]
            if len(tfplan_files) > 1:
                self.ui.print_info(f"Found {len(tfplan_files)} tfplan files, using: {plan_file}")
            
            # Run blast radius assessment
            assessment = blast_service.assess_blast_radius(
                directory=directory,
                recursive=recursive,
                plan_file=plan_file
            )
            
            # Display results
            self._display_blast_radius_results(assessment)

            # Save reports to Reports/blast-radius/
            self._save_blast_radius_reports(assessment, directory)

            # Generate topology report alongside blast radius
            self._save_topology_report(directory)

            # Store for post_execute PR posting
            self._blast_assessment = assessment

            return True
            
        except Exception as e:
            self.logger.error(f"Blast radius assessment failed: {str(e)}")
            self.ui.print_error(f"Failed to assess blast radius: {str(e)}")
            return False

    def _run_cfn_blast_radius(self, directory: str, recursive: bool, project_type: str, live: bool, stack_name: str, **kwargs) -> bool:
        """Run blast radius for CloudFormation/CDK projects."""
        from ....services.check.project.cfn_blast_radius_service import CfnBlastRadiusService, result_to_dict
        from ....services.scan.scan_service import ScanService

        try:
            cfn_service = CfnBlastRadiusService()
            scan_svc = ScanService()
            profile = kwargs.get("profile")

            # Find templates
            if project_type == "cdk":
                templates = scan_svc._find_cdk_templates(directory)
                if not templates:
                    self.ui.print_warning("No CDK templates found in cdk.out/. Run 'cdk synth' first.")
                    return False
            else:
                templates = scan_svc._find_cloudformation_templates(directory)
                if not templates:
                    self.ui.print_warning("No CloudFormation templates found.")
                    return False

            self.ui.print_info(f"Found {len(templates)} {'CDK' if project_type == 'cdk' else 'CloudFormation'} template(s)")

            all_results = []
            for template in templates:
                template_name = Path(template).stem
                self.ui.print_info(f"  Assessing: {template_name}")

                if live:
                    if not stack_name:
                        # Infer stack name from template filename
                        stack_name_inferred = template_name.replace(".template", "").replace("_", "-")
                        self.ui.print_info(f"  Using inferred stack name: {stack_name_inferred}")
                    else:
                        stack_name_inferred = stack_name

                    result = cfn_service.assess_live(
                        template_path=template,
                        stack_name=stack_name_inferred,
                        region=kwargs.get("region", "us-east-1"),
                        profile=profile,
                    )
                else:
                    result = cfn_service.assess_static(
                        template_path=template,
                        directory=directory,
                    )

                all_results.append(result)

                # Display per-template results
                self._display_cfn_blast_radius(result)

            # Save reports
            self._save_cfn_blast_radius_reports(all_results, directory)

            return True

        except Exception as e:
            self.logger.error(f"CFN blast radius failed: {e}")
            self.ui.print_error(f"Failed to assess CloudFormation blast radius: {str(e)}")
            return False

    def _display_cfn_blast_radius(self, result) -> None:
        """Display CloudFormation blast radius results."""
        from rich.table import Table
        import rich.box

        risk_colors = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}
        risk_color = risk_colors.get(result.risk_level, "white")

        self.console.print(f"\n{'='*60}")
        self.console.print(f"💥 [{risk_color}]{result.risk_level}[/{risk_color}] — {result.stack_name} ({result.mode} mode)")
        self.console.print(f"   Resources: {result.total_resources} total, {len(result.changed_resources)} affected ({result.blast_radius_percentage:.1f}%)")

        if result.changed_resources:
            table = Table(box=rich.box.SIMPLE, show_lines=False)
            table.add_column("Resource", style="cyan")
            table.add_column("Type", style="dim")
            table.add_column("Action", style="yellow")
            table.add_column("Scope")

            for r in result.changed_resources[:15]:
                action_colors = {"add": "green", "modify": "yellow", "remove": "red", "affected": "blue"}
                action_style = action_colors.get(r.action, "white")
                table.add_row(
                    r.logical_id,
                    r.resource_type.replace("AWS::", ""),
                    f"[{action_style}]{r.action}[/{action_style}]",
                    ", ".join(r.scope[:3]) or "—",
                )
            if len(result.changed_resources) > 15:
                table.add_row("...", f"+{len(result.changed_resources)-15} more", "", "")

            self.console.print(table)

        for rec in result.recommendations:
            self.console.print(f"  {rec}")
        self.console.print(f"{'='*60}")

    def _save_cfn_blast_radius_reports(self, results, directory: str) -> None:
        """Save CFN blast radius results to Reports/blast-radius/."""
        from datetime import datetime
        from pathlib import Path
        from ....services.check.project.cfn_blast_radius_service import result_to_dict

        try:
            reports_dir = Path(directory) / "Reports" / "blast-radius"
            reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            report_data = {
                "timestamp": datetime.now().isoformat(),
                "mode": results[0].mode if results else "static",
                "stacks": [result_to_dict(r) for r in results],
                "summary": {
                    "total_stacks": len(results),
                    "total_resources": sum(r.total_resources for r in results),
                    "total_affected": sum(len(r.changed_resources) for r in results),
                    "highest_risk": max((r.risk_level for r in results), default="LOW"),
                },
            }

            json_path = reports_dir / f"blast_radius_cfn_{timestamp}.json"
            with open(json_path, "w") as f:
                import json as json_mod
                json_mod.dump(report_data, f, indent=2)

            self.ui.print_info(f"📄 CFN blast radius report saved: {json_path}")

        except Exception as e:
            self.logger.warning(f"Failed to save CFN blast radius report: {e}")

    def _save_blast_radius_reports(self, assessment, directory: str) -> None:
        """Save blast radius assessment as JSON and HTML to Reports/blast-radius/."""
        from datetime import datetime
        from pathlib import Path

        try:
            reports_dir = Path(directory) / "Reports" / "blast-radius"
            reports_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # JSON report
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "total_components": assessment.total_components,
                "risk_level": assessment.risk_level.value,
                "change_type": assessment.change_type.value,
                "affected_components": [
                    {
                        "name": c.name,
                        "path": c.path,
                        "change_type": c.change_type,
                        "risk_score": c.risk_score,
                        "criticality": c.criticality,
                        "dependencies": c.dependencies,
                        "dependents": c.dependents,
                    }
                    for c in assessment.affected_components
                ],
                "recommendations": assessment.recommendations,
                "mitigation_steps": assessment.mitigation_steps,
                "rollback_plan": assessment.rollback_plan,
            }

            json_path = reports_dir / f"blast_radius_{timestamp}.json"
            with open(json_path, "w") as f:
                import json as json_mod
                json_mod.dump(report_data, f, indent=2)

            self.ui.print_info(f"📄 Blast radius report saved: {json_path}")

        except Exception as e:
            self.logger.warning(f"Failed to save blast radius report: {e}")

    def _save_topology_report(self, directory: str) -> None:
        """Generate and save infrastructure topology to Reports/topology/."""
        from pathlib import Path

        try:
            from ....services.document.topology_generator import (
                generate_topology, render_topology_mermaid, topology_to_dict,
            )

            reports_dir = Path(directory) / "Reports" / "topology"
            reports_dir.mkdir(parents=True, exist_ok=True)

            # Generate topology from stacks/tfplan directories
            plan_dirs = [Path(directory) / "stacks", Path(directory)]
            topology = None
            for plan_dir in plan_dirs:
                if plan_dir.exists():
                    topology = generate_topology(str(plan_dir), Path(directory).name)
                    if topology.stacks:
                        break

            if not topology or not topology.stacks:
                return

            # Save mermaid
            mermaid = render_topology_mermaid(topology)
            mermaid_path = reports_dir / "topology.mmd"
            mermaid_path.write_text(mermaid)

            # Save JSON
            import json as json_mod
            from datetime import datetime

            topo_data = topology_to_dict(topology)
            topo_data["mermaid"] = mermaid
            topo_data["timestamp"] = datetime.now().isoformat()
            json_path = reports_dir / "topology.json"
            with open(json_path, "w") as f:
                json_mod.dump(topo_data, f, indent=2)

            # Generate architecture diagram with official AWS icons (PNG + SVG)
            try:
                from ....services.document.architecture_renderer import render_architecture_diagram
                png_path = render_architecture_diagram(topology, str(reports_dir), fmt="png")
                if png_path:
                    self.ui.print_info(f"📷 Architecture diagram: {png_path}")
                    topo_data["diagram_path"] = png_path
                    # Re-save JSON with diagram path
                    with open(json_path, "w") as f:
                        json_mod.dump(topo_data, f, indent=2)
            except Exception as e:
                self.logger.debug(f"Architecture diagram generation skipped: {e}")

            self.ui.print_info(f"🗺️ Topology report saved: {reports_dir}")

        except Exception as e:
            self.logger.warning(f"Failed to save topology report: {e}")

    def _run_cost_analysis(self, directory: str, recursive: bool = False, **kwargs) -> bool:
        """Run cost analysis using the new service"""
        try:
            from ....services.check.project.cost.cost_analyzer import CostAnalyzer
            from ....services.check.project.cost.unified_cost_report import UnifiedCostReportGenerator
            from pathlib import Path
            from datetime import datetime
            
            # Find Terraform plan files
            tfplan_files = self._find_tfplan_files(directory, recursive)
            
            # Find CloudFormation templates
            cf_templates = self._find_cloudformation_templates(directory, recursive)
            
            if not tfplan_files and not cf_templates:
                self.ui.print_warning("No tfplan.json files or CloudFormation templates found.")
                self.ui.print_info("For Terraform: Run 'terraform plan -out=tfplan && terraform show -json tfplan > tfplan.json'")
                self.ui.print_info("For CloudFormation: Ensure .yaml, .yml, or .json template files are present")
                return False
            
            analyzer = CostAnalyzer()
            unified_report = UnifiedCostReportGenerator()
            cost_results = []
            
            # Analyze Terraform plans
            if tfplan_files:
                for tfplan_file in tfplan_files:
                    self.ui.print_info(f"Analyzing Terraform plan: {tfplan_file}")
                    analysis = analyzer.analyze_terraform_plan(tfplan_file)
                    self._display_cost_analysis(analysis)
                    cost_results.append({"stack": Path(tfplan_file).parent.name, "analysis": analysis})
                    
                    # Generate reports
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    reports_dir = Path("Reports") / "cost-analysis"
                    
                    # Use directory name in report filename for clarity
                    plan_dir = Path(tfplan_file).parent.name
                    json_path = reports_dir / f"cost_analysis_{plan_dir}_{timestamp}.json"
                    html_path = reports_dir / f"cost_analysis_{plan_dir}_{timestamp}.html"
                    
                    analyzer.generate_json_report(analysis, json_path)
                    analyzer.generate_html_report(analysis, html_path)
                    
                    # Add to unified report
                    unified_report.add_stack_report(plan_dir, analysis, html_path)
                    
                    self.ui.print_success(f"\n📄 Reports generated:")
                    self.ui.print_info(f"  JSON: {json_path}")
                    self.ui.print_info(f"  HTML: {html_path}")
            
            # Analyze CloudFormation templates
            if cf_templates:
                for template in cf_templates[:3]:  # Limit to first 3 templates
                    self.ui.print_info(f"Analyzing CloudFormation template: {template}")
                    analysis = analyzer.analyze_cloudformation_template(template)
                    self._display_cost_analysis(analysis)
                    cost_results.append({"stack": Path(template).stem, "analysis": analysis})
                    
                    # Generate reports for CloudFormation
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    reports_dir = Path("Reports") / "cost-analysis"
                    template_name = Path(template).stem
                    
                    json_path = reports_dir / f"cost_analysis_{template_name}_{timestamp}.json"
                    html_path = reports_dir / f"cost_analysis_{template_name}_{timestamp}.html"
                    
                    analyzer.generate_json_report(analysis, json_path)
                    analyzer.generate_html_report(analysis, html_path)
                    
                    # Add to unified report
                    unified_report.add_stack_report(plan_dir, analysis, html_path)
                    
                    self.ui.print_success(f"\n📄 Reports generated:")
                    self.ui.print_info(f"  JSON: {json_path}")
                    self.ui.print_info(f"  HTML: {html_path}")
            
            # Generate unified index page
            if tfplan_files:
                reports_dir = Path("Reports") / "cost-analysis"
                index_path = unified_report.generate_unified_index(reports_dir, "Infrastructure")
                self.ui.print_success(f"\n🌐 Unified cost analysis index generated:")
                self.ui.print_info(f"  {index_path}")
            
            self._cost_results = cost_results

            # Enforce cost policies via OPA/Conftest if --enforce-policy is set
            enforce_policy = kwargs.get("enforce_policy")
            if enforce_policy and cost_results:
                policy_passed = self._enforce_cost_policy(
                    cost_results=cost_results,
                    policy_dir=enforce_policy,
                    directory=directory,
                )
                if not policy_passed:
                    return False

            return True
            
        except Exception as e:
            self.logger.error(f"Cost analysis failed: {e}")
            self.ui.print_error(f"Failed to run cost analysis: {str(e)}")
            return False


    def _run_cfn_drift(self, directory: str, recursive: bool, project_type: str,
                       filter_tags: Optional[Dict] = None, **kwargs):
        """Run drift detection for CloudFormation/CDK projects.

        Returns a DriftSummary compatible with the rest of the drift pipeline.
        """
        from ....services.check.project.drift.cfn_drift_service import CfnDriftDetectionService
        from ....services.check.project.drift.models import DriftSummary

        region = kwargs.get('region') or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        profile = kwargs.get('profile')
        stack_name = kwargs.get('stack_name')
        live = kwargs.get('live', True)

        service = CfnDriftDetectionService(region=region, profile=profile)

        stack_names = [stack_name] if stack_name else None

        if project_type == "cdk":
            self.ui.print_info(f"🔍 Detecting drift for CDK project (region: {region})...")
        else:
            self.ui.print_info(f"🔍 Detecting drift for CloudFormation project (region: {region})...")

        if stack_names:
            self.ui.print_info(f"  Stack(s): {', '.join(stack_names)}")
        elif live:
            self.ui.print_info("  Auto-discovering deployed stacks from templates...")
        else:
            self.ui.print_info("  Static mode: comparing templates vs deployed state...")

        summary = service.detect_drift(
            directory=directory,
            recursive=recursive,
            stack_names=stack_names,
            live=live,
            filter_tags=filter_tags,
        )

        return summary


    @staticmethod
    def _parse_filter_tags(raw: str) -> dict:
        """Parse 'key=value,key2=value2' into a dict. Supports key-only (implies key=*)."""
        if not raw:
            return {}
        tags = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                tags[k.strip()] = v.strip()
            elif pair:
                tags[pair] = "*"
        return tags

    def _run_drift_detection(self, directory: str, recursive: bool = False, **kwargs) -> bool:
        """Run drift detection with policy evaluation, history tracking, and optional AI analysis."""
        try:
            from ....services.check.project.drift.drift_service import DriftDetectionService
            from ....services.check.project.drift.drift_report import DriftReportGenerator
            from ....services.check.project.drift.drift_history import DriftHistory
            from ....services.check.project.drift.drift_policy import DriftPolicyEngine, DriftAction
            from pathlib import Path
            from datetime import datetime

            tftool = kwargs.get('tftool', 'tofu')
            reporter = DriftReportGenerator()

            # Parse tag filters
            filter_tags = self._parse_filter_tags(kwargs.get('filter_tags'))
            if filter_tags:
                self.ui.print_info(f"🏷️  Filtering by tags: {filter_tags}")

            # Detect project type and route accordingly
            from ....services.scan.scan_service import ScanService
            scan_svc = ScanService()
            project_type = scan_svc.detect_project_type(directory)

            if project_type in ("cloudformation", "cdk"):
                summary = self._run_cfn_drift(
                    directory=directory, recursive=recursive,
                    project_type=project_type, filter_tags=filter_tags, **kwargs
                )
            else:
                # Terraform/Terragrunt path
                service = DriftDetectionService(tftool=tftool)
                plan_files = self._find_tfplan_files(directory, recursive)

                if plan_files:
                    self.ui.print_info(f"Found {len(plan_files)} tfplan.json file(s), analysing for drift...")
                    summary = service.detect_drift(directory, recursive, plan_files=plan_files, filter_tags=filter_tags)
                else:
                    self.ui.print_info(f"No tfplan.json found. Running live {tftool} plan to detect drift...")
                    summary = service.detect_drift(directory, recursive, filter_tags=filter_tags)

            summary_dict = summary.to_dict()

            # --- Policy evaluation ---
            policy_engine = DriftPolicyEngine.load(directory)
            evaluation = policy_engine.evaluate(summary_dict)

            if evaluation.ignored_addresses:
                self.ui.print_info(f"📋 Policy: {len(evaluation.ignored_addresses)} resource(s) ignored by .driftpolicy")
            if evaluation.accepted_addresses:
                self.ui.print_info(f"✅ Policy: {len(evaluation.accepted_addresses)} resource(s) auto-accepted by .driftpolicy")

            # Filter ignored resources from display
            for result in summary.results:
                result.drifted_resources = [
                    r for r in result.drifted_resources
                    if r.address not in evaluation.ignored_addresses
                ]

            # Apply severity overrides from policy
            override_map = {v.address: v.severity_override for v in evaluation.verdicts if v.severity_override}
            if override_map:
                from ....services.check.project.drift.models import DriftSeverity
                for result in summary.results:
                    for r in result.drifted_resources:
                        if r.address in override_map:
                            try:
                                r.severity = DriftSeverity(override_map[r.address])
                            except ValueError:
                                pass

            # Display console output
            reporter.display_console(summary, self.console)

            # --- History / trending ---
            project_name = kwargs.get('project_name') or Path(directory).resolve().name
            history = DriftHistory()
            history.save_snapshot(project_name, summary_dict)
            trend = history.get_trend(project_name)

            if trend.get("snapshots", 0) > 1:
                from rich.panel import Panel
                trend_icon = {"improving": "📈", "degrading": "📉", "stable": "➡️"}.get(trend["trend"], "")
                self.console.print(Panel(
                    f"Trend: {trend_icon} {trend['trend'].upper()} "
                    f"(Δ {trend['coverage_delta']:+.1f}% over {trend['snapshots']} snapshots)\n"
                    f"Coverage range: {trend['min_coverage']}% — {trend['max_coverage']}%\n"
                    f"Current: {trend['current_coverage']}% | Peak drifted: {trend['peak_drifted']}",
                    title="📊 Drift Trend",
                    border_style="cyan",
                ))

            threshold_warning = history.check_threshold(project_name)
            if threshold_warning:
                self.ui.print_warning(threshold_warning)

            # --- AI analysis (if provider configured) ---
            ai_provider = kwargs.get('ai_provider')
            ai_result = None
            if ai_provider and summary.has_drift:
                self.ui.print_info(f"🤖 Running AI drift analysis (provider: {ai_provider})...")
                from ....services.check.project.drift.drift_ai import analyze_drift_with_ai
                ai_result = analyze_drift_with_ai(
                    summary_dict, trend=trend,
                    provider=ai_provider, model=kwargs.get('ai_model'),
                )
                ai_summary = ai_result.get("summary", {})
                from rich.panel import Panel
                self.console.print(Panel(
                    f"Risk score: {ai_summary.get('risk_score', 'N/A')}/100\n"
                    f"Security risks: {ai_summary.get('security_risks', 0)}\n"
                    f"Block deploy: {'YES' if ai_summary.get('should_block_deploy') else 'NO'}\n"
                    f"Recommendation: {ai_summary.get('recommendation', 'N/A')}",
                    title="🤖 AI Drift Analysis",
                    border_style="magenta",
                ))
                for rec in ai_result.get("recommendations", []):
                    self.ui.print_info(f"  💡 {rec}")

            # --- Generate reports ---
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            reports_dir = Path("Reports") / "drift-detection"

            json_path = reports_dir / f"drift_{timestamp}.json"
            html_path = reports_dir / f"drift_{timestamp}.html"

            reporter.generate_json(summary, str(json_path))
            reporter.generate_html(summary, str(html_path))

            self.ui.print_success(f"\n📄 Reports generated:")
            self.ui.print_info(f"  JSON: {json_path}")
            self.ui.print_info(f"  HTML: {html_path}")

            # Store for post_execute PR posting
            self._drift_summary = summary

            # --- Policy enforcement ---
            if evaluation.blocked:
                for reason in evaluation.block_reasons:
                    self.ui.print_error(f"🚫 {reason}")
                self.ui.print_error("Deployment blocked by drift policy.")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Drift detection failed: {e}")
            self.ui.print_error(f"Failed to run drift detection: {str(e)}")
            return False

    def _find_cloudformation_templates(self, directory: str, recursive: bool) -> List[str]:
        """Find CloudFormation template files"""
        import os
        templates = []
        
        extensions = ['.yaml', '.yml', '.json']
        
        # Exclude patterns for non-CloudFormation files
        exclude_patterns = [
            'cost_analysis',  # Our own cost reports
            'tfstate',
            'terraform.tfstate'
        ]
        
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    # Skip excluded files
                    if any(pattern in file.lower() for pattern in exclude_patterns):
                        continue
                    
                    if any(file.lower().endswith(ext) for ext in extensions):
                        file_path = os.path.join(root, file)
                        if self._is_cloudformation_template(file_path):
                            templates.append(file_path)
        else:
            for file in os.listdir(directory):
                # Skip excluded files
                if any(pattern in file.lower() for pattern in exclude_patterns):
                    continue
                    
                if any(file.lower().endswith(ext) for ext in extensions):
                    file_path = os.path.join(directory, file)
                    if self._is_cloudformation_template(file_path):
                        templates.append(file_path)
        
        return templates
    
    def _is_cloudformation_template(self, file_path: str, indicators: List[str] = None) -> bool:
        """Check if file is a CloudFormation template"""
        try:
            import json
            import yaml
            
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            
            # CloudFormation templates must have AWSTemplateFormatVersion or be a dict with Resources
            if isinstance(data, dict):
                # Strong indicator: AWSTemplateFormatVersion
                if 'AWSTemplateFormatVersion' in data:
                    return True
                
                # Check for Resources section with CloudFormation resource types
                if 'Resources' in data and isinstance(data['Resources'], dict):
                    # Verify at least one resource has CloudFormation type (AWS::*)
                    for resource in data['Resources'].values():
                        if isinstance(resource, dict) and 'Type' in resource:
                            if resource['Type'].startswith('AWS::'):
                                return True
            
            return False
        except Exception:
            return False

    def _enforce_cost_policy(self, cost_results: list, policy_dir: str, directory: str) -> bool:
        """Enforce OPA/Rego policies against cost analysis results.

        Feeds cost JSON to conftest as input and evaluates deny/warn rules.

        Args:
            cost_results: List of {"stack": name, "analysis": CostAnalysis}
            policy_dir: Policy directory, Git URL, or 'cost' for org default
            directory: Project directory

        Returns:
            True if all policies pass, False if violations detected
        """
        import json as json_mod
        import subprocess
        import tempfile
        from pathlib import Path
        from ....utils.platform_utils import find_executable

        conftest = find_executable("conftest")
        if not conftest:
            self.ui.print_warning("conftest not found — skipping cost policy enforcement")
            return True

        # Resolve policy directory
        if policy_dir == "cost":
            # Use org-iac-policies/cost/ from THOTH_ORG_POLICY
            org_policy = os.environ.get("THOTH_ORG_POLICY")
            if org_policy:
                from ....services.scan.scanners.opa import OPAScanner
                scanner = OPAScanner()
                resolved = scanner._resolve_policy_dir(directory, "cost")
                if resolved:
                    policy_dir = resolved
                else:
                    self.ui.print_warning("No 'cost' policy directory found in org policies")
                    return True
            else:
                local_cost = os.path.join(directory, "policy", "cost")
                if os.path.isdir(local_cost):
                    policy_dir = local_cost
                else:
                    self.ui.print_warning("No cost policy directory found. Create policy/cost/*.rego")
                    return True

        if not os.path.isdir(policy_dir):
            # Might be a Git URL — let OPA scanner resolve it
            from ....services.scan.scanners.opa import OPAScanner
            scanner = OPAScanner()
            resolved = scanner._resolve_policy_dir(directory, policy_dir)
            if resolved:
                policy_dir = resolved
            else:
                self.ui.print_warning(f"Could not resolve policy directory: {policy_dir}")
                return True

        # Prepare YAML data files (config.yaml → config.json)
        from ....services.scan.scanners.opa import OPAScanner
        opa_scanner = OPAScanner()
        opa_scanner._prepare_data_files(policy_dir)

        # Build combined cost input JSON (all stacks merged)
        combined = {
            "summary": {
                "total_monthly_cost": sum(
                    r["analysis"].total_monthly_cost for r in cost_results
                ),
                "total_annual_cost": sum(
                    r["analysis"].total_annual_cost for r in cost_results
                ),
                "total_running_monthly_cost": sum(
                    r["analysis"].analysis_metadata.get("total_running_monthly_cost", r["analysis"].total_monthly_cost)
                    for r in cost_results
                ),
                "stacks": len(cost_results),
            },
            "resources": [],
            "cost_by_service": {},
            "stacks": [],
        }

        for r in cost_results:
            analysis = r["analysis"]
            stack_name = r["stack"]
            combined["stacks"].append({
                "name": stack_name,
                "monthly_cost": analysis.total_monthly_cost,
            })
            for rc in analysis.resource_costs:
                combined["resources"].append({
                    "address": rc.resource_address,
                    "type": rc.resource_type,
                    "service": rc.service_name,
                    "monthly_cost": rc.monthly_cost,
                    "action": rc.action.value,
                    "confidence": rc.confidence_level,
                    "details": rc.pricing_details,
                    "stack": stack_name,
                })
            for svc, cost in analysis.cost_breakdown_by_service.items():
                combined["cost_by_service"][svc] = combined["cost_by_service"].get(svc, 0) + cost

        # Write input JSON to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json_mod.dump(combined, f, indent=2, default=str)
            input_path = f.name

        try:
            # Find data files in policy directory
            data_args = []
            for data_file in sorted(Path(policy_dir).glob("*.json")):
                data_args.extend(["--data", str(data_file)])

            # Run conftest
            cmd = [
                conftest, "test", input_path,
                "--policy", policy_dir,
                "--output", "json",
                "--all-namespaces",
            ] + data_args

            self.ui.print_info(f"🔒 Enforcing cost policies from: {policy_dir}")
            self.logger.info(f"Running cost policy: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Parse results
            try:
                results_json = json_mod.loads(result.stdout) if result.stdout else []
            except json_mod.JSONDecodeError:
                results_json = []

            failures = []
            warnings = []
            for r in results_json:
                failures.extend(r.get("failures", []))
                warnings.extend(r.get("warnings", []))

            # Display results
            if warnings:
                for w in warnings:
                    self.ui.print_warning(f"  ⚠️  {w.get('msg', w)}")

            if failures:
                self.console.print()
                from rich.panel import Panel
                violation_msgs = "\n".join(f"  • {f.get('msg', f)}" for f in failures)
                panel = Panel(
                    f"[bold red]Cost policy violations detected[/bold red]\n\n"
                    f"{violation_msgs}\n\n"
                    f"[dim]Policies:[/dim] {policy_dir}\n"
                    f"[dim]Total monthly cost:[/dim] ${combined['summary']['total_monthly_cost']:,.2f}",
                    title="[bold red]⛔ Cost Policy Enforcement Failed[/bold red]",
                    border_style="red",
                )
                self.console.print(panel)
                return False
            else:
                self.ui.print_success("✅ All cost policies passed")
                return True

        except subprocess.TimeoutExpired:
            self.ui.print_warning("Cost policy check timed out")
            return True
        except Exception as e:
            self.logger.error(f"Cost policy enforcement failed: {e}")
            self.ui.print_warning(f"Cost policy enforcement error: {e}")
            return True
        finally:
            os.unlink(input_path)

    def _display_cost_analysis(self, analysis) -> None:
        """Display cost analysis results"""
        from ....services.check.project.cost.models.cost_models import CostAnalysis
        
        # Main header
        self.console.print("\n" + "="*80)
        self.console.print("💰 AWS COST ANALYSIS", style="bold cyan")
        self.console.print("="*80)
        
        # Cost summary
        self.console.print(f"\n📊 [bold]Total Monthly Cost:[/bold] [green]${analysis.total_monthly_cost:.2f}[/green]")
        self.console.print(f"📅 [bold]Total Annual Cost:[/bold] [green]${analysis.total_annual_cost:.2f}[/green]")
        
        # Service breakdown
        if analysis.cost_breakdown_by_service:
            self.console.print(f"\n🏗️ [bold]Cost by Service:[/bold]")
            for service, cost in analysis.cost_breakdown_by_service.items():
                self.console.print(f"  • {service}: [green]${cost:.2f}/month[/green]")
        
        # Action breakdown
        if analysis.cost_breakdown_by_action:
            self.console.print(f"\n⚡ [bold]Cost by Action:[/bold]")
            for action, cost in analysis.cost_breakdown_by_action.items():
                color = "green" if action == "create" else "yellow" if action == "update" else "red"
                self.console.print(f"  • {action}: [{color}]${cost:.2f}/month[/{color}]")
        
        # Resource details
        if analysis.resource_costs:
            self.console.print(f"\n📋 [bold]Resource Details:[/bold]")
            for resource in analysis.resource_costs[:10]:  # Show first 10
                confidence_color = "green" if resource.confidence_level == "high" else "yellow"
                self.console.print(f"  • {resource.resource_address}")
                self.console.print(f"    Type: {resource.resource_type} | Cost: [green]${resource.monthly_cost:.2f}/month[/green] | Confidence: [{confidence_color}]{resource.confidence_level}[/{confidence_color}]")
        
        # Recommendations
        if analysis.recommendations:
            self.console.print(f"\n💡 [bold]Recommendations:[/bold]")
            for rec in analysis.recommendations:
                self.console.print(f"  {rec}")
        
        # Warnings
        if analysis.warnings:
            self.console.print(f"\n⚠️ [bold]Warnings:[/bold]")
            for warning in analysis.warnings:
                self.console.print(f"  • [yellow]{warning}[/yellow]")
        
        # Metadata
        metadata = analysis.analysis_metadata
        api_status = "✅ Online" if metadata.get('api_available') else "⚠️ Offline (using estimates)"
        self.console.print(f"\n📈 [bold]Analysis Info:[/bold] Region: {metadata.get('region')} | API: {api_status}")
        self.console.print("="*80)
    
    def _display_blast_radius_results(self, assessment) -> None:
        """Display blast radius assessment results."""
        from ....services.check.project.blast_radius_service import ChangeRisk, ChangeType
        
        # Main header
        self.console.print("\n" + "="*80)
        self.console.print("🎯 BLAST RADIUS ASSESSMENT (ITIL v4 Compliant)", style="bold cyan")
        self.console.print("="*80)
        
        # Risk summary panel
        risk_color = self._get_blast_radius_color(assessment.risk_level)
        summary_text = f"""
[bold]Risk Level:[/bold] [{risk_color}]{assessment.risk_level.value.upper()}[/{risk_color}]
[bold]Change Type:[/bold] {assessment.change_type.value.upper()}
[bold]Total Components:[/bold] {assessment.total_components}
[bold]Affected Components:[/bold] {len(assessment.affected_components)}
        """
        
        self.console.print(Panel(
            summary_text.strip(),
            title="📊 Risk Summary",
            border_style=risk_color
        ))
        
        # Affected components table
        if assessment.affected_components:
            table = Table(title="💥 Affected Components", box=box.ROUNDED)
            table.add_column("Component", style="cyan")
            table.add_column("Change Type", style="yellow")
            table.add_column("Risk Score", justify="center")
            table.add_column("Criticality", justify="center")
            table.add_column("Dependencies", justify="center")
            table.add_column("Dependents", justify="center")
            
            for comp in assessment.affected_components:
                risk_color = self._get_risk_color(comp.risk_score * 100)
                crit_color = self._get_criticality_color(comp.criticality)
                
                table.add_row(
                    comp.name,
                    comp.change_type,
                    f"[{risk_color}]{comp.risk_score:.2f}[/{risk_color}]",
                    f"[{crit_color}]{comp.criticality}[/{crit_color}]",
                    str(len(comp.dependencies)),
                    str(len(comp.dependents))
                )
            
            self.console.print(table)
        
        # Recommendations
        if assessment.recommendations:
            rec_text = "\n".join(f"• {rec}" for rec in assessment.recommendations)
            self.console.print(Panel(
                rec_text,
                title="📋 ITIL v4 Recommendations",
                border_style="blue"
            ))
        
        # Mitigation steps
        if assessment.mitigation_steps:
            mit_text = "\n".join(assessment.mitigation_steps)
            self.console.print(Panel(
                mit_text,
                title="🛡️ Risk Mitigation Steps",
                border_style="green"
            ))
        
        # Rollback plan
        if assessment.rollback_plan:
            rollback_text = "\n".join(assessment.rollback_plan)
            self.console.print(Panel(
                rollback_text,
                title="🔄 Rollback Plan",
                border_style="orange3"
            ))
        
        # Final recommendation based on risk level
        if assessment.risk_level in [ChangeRisk.HIGH, ChangeRisk.CRITICAL]:
            self.console.print(Panel(
                "⚠️ HIGH/CRITICAL RISK DETECTED ⚠️\n\n"
                "This change requires additional approval and careful planning.\n"
                "Consider implementing changes in phases or during maintenance windows.",
                title="🚨 Action Required",
                border_style="red"
            ))
    
    def _get_blast_radius_color(self, risk_level) -> str:
        """Get color for blast radius risk level."""
        from ....services.check.project.blast_radius_service import ChangeRisk
        
        color_map = {
            ChangeRisk.LOW: "green",
            ChangeRisk.MEDIUM: "yellow", 
            ChangeRisk.HIGH: "orange3",
            ChangeRisk.CRITICAL: "red"
        }
        return color_map.get(risk_level, "white")
    
    def _get_criticality_color(self, criticality: str) -> str:
        """Get color for component criticality."""
        color_map = {
            "low": "green",
            "medium": "yellow",
            "high": "orange3", 
            "critical": "red"
        }
        return color_map.get(criticality, "white")

    def _run_stack_optimizer(self, directory: str, **kwargs) -> bool:
        """Run stack optimizer to deduplicate overlapping terragrunt filters."""
        from ....services.check.stack_optimizer import StackOptimizer
        import sys

        stacks_input = kwargs.get("stacks", "")
        base_path_name = kwargs.get("stacks_base_path", "resources")
        output_format = kwargs.get("output_format", "table")

        if not stacks_input:
            self.ui.print_error("--stacks is required for stack-optimizer (comma-separated list)")
            return False

        target_stacks = [s.strip() for s in re.split(r'[,\s]+', stacks_input) if s.strip()]
        base_path = Path(directory)

        if output_format != "list":
            self.ui.print_info(f"🔧 Optimizing {len(target_stacks)} stack filter(s)...")

        optimizer = StackOptimizer(base_path=base_path, stacks_base=base_path_name)
        result = optimizer.optimize(target_stacks)

        if output_format == "list":
            # Machine-readable: one filter per line, no extra output
            for f in result["optimized_filters"]:
                sys.stdout.write(f + "\n")
        elif output_format == "json":
            print(json.dumps(result, indent=2))
        else:
            # Rich table output
            table = Table(title="Stack Optimizer Results", box=box.ROUNDED)
            table.add_column("Stack Filter", style="cyan")
            table.add_column("Direct Units", justify="right")
            table.add_column("With Deps", justify="right")
            table.add_column("Status", style="bold")

            for stack, detail in result["details"].items():
                status = "[red]REDUNDANT ✗[/red]" if detail["redundant"] else "[green]KEEP ✓[/green]"
                table.add_row(
                    stack,
                    str(detail["direct_units"]),
                    str(detail["with_deps"]),
                    status,
                )

            self.console.print(table)

            if result["removed_redundant"]:
                self.console.print(
                    f"\n[yellow]⚡ Removed {len(result['removed_redundant'])} redundant filter(s): "
                    f"{', '.join(result['removed_redundant'])}[/yellow]"
                )
            self.console.print(
                f"[green]📦 Units before: {result['total_units_before']} → "
                f"after dedup: {result['total_units_after']}[/green]"
            )

        return result


cli = CheckIaCCommand.as_click_command(
    help="Analyze IaC artifacts: plans, dependencies, costs, blast radius, and drift"
)(
    click.option(
        '--recursive',
        is_flag=True,
        default=False,
        help='Search for tfplan files recursively in subdirectories'
    ),
    click.option(
        '--outmd',
        help="Output markdown file path",
        type=str,
        default="tfplan_check_results.md",
    ),
    click.option(
        '--tftool',
        help="Terraform tool to use (terraform or tofu)",
        type=click.Choice(['terraform', 'tofu']),
        default='tofu',
    ),
    click.option("-type", "--check_type",
                 help="tfplan: analyze plans | deps: view dependencies | blast-radius: impact analysis | cost-analysis: estimate costs | drift: detect infrastructure drift | stack-optimizer: deduplicate overlapping stacks",
                 type=click.Choice(["tfplan", "deps", "blast-radius", "cost-analysis", "drift", "stack-optimizer"], case_sensitive=True),
                 default="tfplan",
                 ),
    click.option(
        '--format',
        type=click.Choice(['tree', 'boxart', 'html', 'dot'], case_sensitive=True),
        default='tree',
        help='Output format for deps visualization (tree: Rich tree, boxart: ASCII boxes, html: interactive browser, dot: raw DOT)'
    ),
    click.option(
        '--plan-file',
        help="Path to terraform plan JSON file (for blast-radius)",
        type=str,
        default=None,
    ),
    click.option(
        '--live',
        is_flag=True,
        default=False,
        help="Use live AWS change set for blast radius (requires credentials). "
             "For CloudFormation/CDK projects only.",
    ),
    click.option(
        '--stack-name',
        help="CloudFormation stack name for live blast radius assessment",
        type=str,
        default=None,
    ),
    click.option(
        '--profile',
        help="AWS CLI profile name for live mode (uses default credential chain if not set)",
        type=str,
        default=None,
    ),
    click.option(
        '--enforce-policy',
        help="OPA/Rego policy directory to enforce against cost analysis results. "
             "Supports: local path, Git URL, or 'cost' to use org-iac-policies/cost/",
        type=str,
        default=None,
    ),
    click.option(
        '--post-to-pr',
        is_flag=True,
        default=False,
        help='Post results as a comment to the current pull request'
    ),
    click.option(
        '--vcs-provider',
        type=click.Choice(['auto', 'azure_repos', 'github'], case_sensitive=True),
        default='auto',
        help='VCS provider for PR comments (auto-detects from CI environment)'
    ),
    click.option(
        '--space',
        type=str,
        default=None,
        help='Space name to load VCS credentials from'
    ),
    click.option(
        '--ai-provider',
        type=click.Choice(['openai', 'bedrock', 'azure', 'ollama'], case_sensitive=True),
        default=None,
        help='AI provider for drift analysis (drift check type only)'
    ),
    click.option(
        '--ai-model',
        type=str,
        default=None,
        help='AI model override (e.g. gpt-4, llama3)'
    ),
    click.option(
        '--project-name',
        type=str,
        default=None,
        help='Project name for drift history tracking'
    ),
    click.option(
        '--filter-tags',
        type=str,
        default=None,
        help='Filter drift results by resource tags (e.g. "env=prod,team=platform"). Supports key=value, key=* (any value), or key (exists)'
    ),
    click.option(
        '--stacks',
        type=str,
        default=None,
        help='Comma-separated list of stack filters for stack-optimizer (e.g. "Network/**,Compute/EC2/**")'
    ),
    click.option(
        '--stacks-base-path',
        type=str,
        default='resources',
        help='Base path for stack resolution (default: resources)'
    ),
    click.option(
        '--output-format',
        type=click.Choice(['table', 'json', 'list'], case_sensitive=True),
        default='table',
        help='Output format for stack-optimizer results'
    ),
)
