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
        self.supported_check_types = ["tfplan", "deps", "blast-radius", "cost-analysis"]

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

        try:
            # Process based on check type
            if kwargs['check_type'] == "tfplan":
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
            elif kwargs['check_type'] == "blast-radius":
                self.ui.print_info("💥 Running blast radius assessment...")
                result = self._run_blast_radius_check(directory=directory, **kwargs)
                return result
            elif kwargs['check_type'] == "cost-analysis":
                self.ui.print_info("💰 Running cost analysis...")
                result = self._run_cost_analysis(directory=directory, **kwargs)
                return result

            self.logger.debug("Check completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to execute check command: {str(e)}")
            raise

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

    def _visualize_dependencies(self, directory: str, dagtool: str = 'terragrunt') -> bool:
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
            
            # Parse and visualize the DOT graph
            dot_graph = result.stdout
            
            # Parse the DOT graph to extract nodes and edges
            nodes, edges = self._parse_dot_graph(dot_graph)
            
            # Calculate risk percentages for each component
            risks = calculate_component_risks(nodes, edges, directory)
            
            # Parse terragrunt.hcl files to get dependency details
            dep_info = self._parse_terragrunt_dependencies(directory)
            
            # Display the enhanced visualization with risk percentages and dependency info
            self._display_dependency_graph(dot_graph, risks, dep_info)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to visualize dependencies: {str(e)}")
            self.console.print(f"[red]Error: {str(e)}[/red]")
            return False
    
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
    
    def _display_dependency_graph(self, dot_graph: str, risks: Dict[str, float] = None, dep_info: Dict = None) -> None:
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

    def _run_blast_radius_check(self, directory: str, recursive: bool = False, **kwargs) -> bool:
        """Run blast radius assessment combining deps and plan analysis."""
        try:
            # Find existing tfplan.json files instead of generating new ones
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
            
            # Generate unified index page
            if tfplan_files:
                reports_dir = Path("Reports") / "cost-analysis"
                index_path = unified_report.generate_unified_index(reports_dir, "Infrastructure")
                self.ui.print_success(f"\n🌐 Unified cost analysis index generated:")
                self.ui.print_info(f"  {index_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Blast radius assessment failed: {str(e)}")
            self.ui.print_error(f"Failed to assess blast radius: {str(e)}")
            return False

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
            
            # Analyze Terraform plans
            if tfplan_files:
                for tfplan_file in tfplan_files:
                    self.ui.print_info(f"Analyzing Terraform plan: {tfplan_file}")
                    analysis = analyzer.analyze_terraform_plan(tfplan_file)
                    self._display_cost_analysis(analysis)
                    
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
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cost analysis failed: {e}")
            self.ui.print_error(f"Failed to run cost analysis: {str(e)}")
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


cli = CheckIaCCommand.as_click_command(
    help="Analyze IaC artifacts: plans, dependencies, costs, and blast radius"
)(
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
                 help="tfplan: analyze plans | deps: view dependencies | blast-radius: impact analysis | cost-analysis: estimate costs",
                 type=click.Choice(["tfplan", "deps", "blast-radius", "cost-analysis"], case_sensitive=True),
                 default="tfplan",
                 ),
)
