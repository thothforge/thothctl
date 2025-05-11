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
from ....services.check.project.check_project_structure import validate
from ....services.check.project.risk_assessment import calculate_component_risks

logger = logging.getLogger(__name__)


class CheckIaCCommand(ClickCommand):
    """Command to Check IaC outputs and artifacts"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.console = Console()
        self.supported_check_types = ["tfplan", "module", "project", "deps"]

    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""

        if kwargs['check_type'] not in self.supported_check_types:
            self.logger.error(f"Unsupported Check type. Must be one of: {', '.join(self.supported_check_types)}")
            return False

        return True

    def execute(self, **kwargs) -> Any:
        """Execute the check command """
        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY")

        try:
            # Process based on check type
            if kwargs['check_type'] == "project":
                result = self._validate_project_structure(directory=directory, mode=kwargs['mode'],
                                                          check_type=kwargs['check_type'])
                self.logger.debug("Project structure validation completed")
                return result

            elif kwargs['check_type'] == "tfplan":
                # Process tfplan validation
                result = self._validate_tfplan(
                    directory=directory,
                    recursive=kwargs.get('recursive', False),
                    outmd=kwargs.get('outmd'),
                    dependencies=kwargs.get('dependencies', False),
                    tftool=kwargs.get('tftool', 'tofu')
                )
                return result
                
            # Handle dependency graph visualization - always use terragrunt
            elif kwargs['dependencies'] or kwargs['check_type'] == "deps":
                result = self._visualize_dependencies(
                    directory=directory,
                    dagtool='terragrunt'  # Force terragrunt as the tool for dependencies
                )
                return result

            self.logger.debug("Check completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to execute check command: {str(e)}")
            raise

    def _validate_project_structure(self, directory: str, mode: str = "soft", check_type: str = "project", ) -> bool:
        """Validate the project structure"""
        return validate(directory=directory, check_type=check_type, mode=mode)

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

        # Display resource types
        if summary["resource_types"]:
            self.console.print("\n[bold]Resource Types:[/bold]")

            resource_table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            resource_table.add_column("Resource Type")
            resource_table.add_column("Count")

            for resource_type, count in sorted(summary["resource_types"].items()):
                resource_table.add_row(resource_type, str(count))

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

            # Resource types section
            if summary["resource_types"]:
                f.write("## Resource Types\n\n")
                f.write("| Resource Type | Count |\n")
                f.write("|--------------|-------|\n")

                for resource_type, count in sorted(summary["resource_types"].items()):
                    f.write(f"| {resource_type} | {count} |\n")

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

    def _visualize_dependencies(self, directory: str, dagtool: str = 'terragrunt') -> bool:
        """Visualize infrastructure dependencies using terragrunt dag graph"""
        self.logger.info(f"Visualizing dependencies in {directory} using {dagtool}")
        
        try:
            # Run terragrunt dag graph command
            cmd = [dagtool, "dag", "graph"]
            
            # Check if workspace parameter should be added
            if os.path.exists(os.path.join(directory, "terragrunt.hcl")):
                cmd.extend(["--terragrunt-working-dir", directory])
            
            # Run the command but don't print the running message
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                self.console.print(f"[red]Error running {dagtool} dag graph:[/red]")
                self.console.print(result.stderr)
                return False
            
            # Parse and visualize the DOT graph
            dot_graph = result.stdout
            
            # Parse the DOT graph to extract nodes and edges
            nodes, edges = self._parse_dot_graph(dot_graph)
            
            # Calculate risk percentages for each component
            risks = calculate_component_risks(nodes, edges, directory)
            
            # Only display the enhanced visualization with risk percentages
            self._display_dependency_graph(dot_graph, risks)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to visualize dependencies: {str(e)}")
            self.console.print(f"[red]Error: {str(e)}[/red]")
            return False
    
    def _display_dependency_graph(self, dot_graph: str, risks: Dict[str, float] = None) -> None:
        """
        Display the dependency graph in a visually appealing way
        
        Args:
            dot_graph: DOT graph string
            risks: Dictionary mapping component names to risk percentages
        """
        self.console.print(Panel("[bold blue]🔄 Enhanced Dependency Visualization 🔄[/bold blue]", box=box.ROUNDED))
        
        # Parse the DOT graph to extract nodes and edges
        nodes, edges = self._parse_dot_graph(dot_graph)
        
        # Create a rich tree representation with risk percentages
        tree = self._create_dependency_tree(nodes, edges, risks)
        
        # Display the tree visualization
        self.console.print(tree)
        
        # Display summary
        self.console.print(f"\n[green]✅ Found {len(nodes)} modules with {len(edges)} dependencies[/green]")
        
        # Display risk legend
        if risks:
            self._display_risk_legend()
    
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


cli = CheckIaCCommand.as_click_command(
    help="Check Infrastructure as code artifacts like tfplan and dependencies"
)(
    click.option(
        '--mode',
        type=click.Choice(['soft', 'hard']),
        default='soft',
        help='Validation mode'
    ),
    click.option(
        "-deps", '--dependencies',
        is_flag=True,
        default=False,
        help='View a dependency graph in ASCII pretty shell output'
    ),
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
                 help="Check module or project structure format, check tfplan, or visualize dependencies",
                 type=click.Choice(["tfplan", "module", "project", "deps"], case_sensitive=True),
                 default="project",
                 ),
    # click.option("--tfplan",
    #             help="Validate terraform plan",
    #             is_flag=True,
    #             default=False,
    #             )
)
