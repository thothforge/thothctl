import logging
import os
import click
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .....core.commands import ClickCommand
from .....services.check.project.check_project_structure import validate

logger = logging.getLogger(__name__)


class CheckProjectIaCCommand(ClickCommand):
    """Command to check IaC project structure and configuration"""

    def __init__(self):
        super().__init__()
        self.console = Console()
        self.supported_check_types = ["structure", "metadata", "compliance"]

    def validate(self, **kwargs) -> bool:
        """Validate project IaC check parameters"""
        if kwargs.get('check_type') and kwargs['check_type'] not in self.supported_check_types:
            self.logger.error(f"Unsupported check type. Must be one of: {', '.join(self.supported_check_types)}")
            return False
        return True

    def _format_validation_output(self, output: str) -> None:
        """Format the validation output with Rich styling"""
        lines = output.strip().split('\n')
        
        # Separate root and nested items
        root_items = []
        nested_items = []
        current_section = "root"
        
        for line in lines:
            if not line.strip():
                continue
                
            # Skip certain lines
            if any(skip in line for skip in ["Using default options", "Project structure is", "No config file found"]):
                continue
                
            # Track sections
            if "📝 Checking content" in line:
                current_section = "nested"
                self.console.print(f"[blue]📝 {line.split('📝 ')[1]}[/blue]")
                continue
                
            elif "⚛️ Checking root structure" in line:
                current_section = "root"
                self.console.print(f"[blue]⚛️ {line.split('⚛️ ')[1]}[/blue]")
                continue
                
            # Parse validation lines
            if "✅" in line or "❌" in line:
                item_data = self._parse_validation_line(line)
                if item_data:
                    # Root items: "root exists! in ." OR "exists!" (no path) OR "doesn't exist in ."
                    # Module items: "exists in [subfolder]" OR "missing in [subfolder]"
                    if (" root exists! in " in line or 
                        " exists!" in line or 
                        (" doesn't exist in ." in line and "optional" in line) or
                        (" doesn't exist in ." in line and "optional" not in line)):
                        root_items.append(item_data)
                    else:
                        nested_items.append(item_data)

        # Display root structure table
        if root_items:
            self._display_table("🏗️ Root Structure", root_items)
        
        # Display nested structure table
        if nested_items:
            self._display_table("📁 Module Structure", nested_items)

    def _parse_validation_line(self, line: str) -> dict:
        """Parse a validation line and return item data"""
        parts = line.split(" - ", 1)
        if len(parts) <= 1:
            return None
            
        item_text = parts[1]
        
        # Clean up item name - remove redundant prefixes
        if "Required file " in item_text:
            item = item_text.replace("Required file ", "")
            if " exists in " in item:
                item = item.split(" exists in ")[0]
            elif " missing in " in item:
                item = item.split(" missing in ")[0]
        elif " root exists! in " in item_text:
            item = item_text.split(" root exists! in ")[0]
        elif " exists!" in item_text:
            item = item_text.split(" exists!")[0]
        elif " doesn't exist" in item_text:
            item = item_text.split(" doesn't exist")[0]
        else:
            item = item_text
        
        # Determine type (folder vs file) - use file extension detection
        if item.endswith(('.tf', '.hcl', '.yaml', '.yml', '.md', '.txt', '.json', '.toml')) or '.' in item:
            item_type = "📄"
        else:
            item_type = "📁"  # Default to folder for items without extensions
        
        # Determine if required or optional
        if "(optional)" in item_text:
            required = "Optional"
            item = item.replace(" (optional)", "")
        else:
            required = "Required"
        
        # Status
        if "✅" in line:
            status = Text("✅ Pass", style="green")
        else:
            status = Text("❌ Fail", style="red")
        
        # Details - clean up and make more concise
        details = ""
        if " in " in item_text:
            detail_part = item_text.split(" in ")[-1]
            if detail_part and detail_part != ".":
                details = detail_part.replace(" (optional)", "")
        
        # Determine if this is a root file based on file extension
        is_root_file = '.' in item and not item.startswith('.')
        
        return {
            "item": item,
            "type": item_type,
            "required": required,
            "status": status,
            "details": details,
            "is_root_file": is_root_file
        }

    def _display_table(self, title: str, items: list) -> None:
        """Display a table with the given items"""
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Item", style="cyan", width=25)
        table.add_column("Type", style="blue", width=8)
        table.add_column("Required", style="yellow", width=10)
        table.add_column("Status", width=10)
        table.add_column("Details", style="dim", width=30)

        for item_data in items:
            table.add_row(
                item_data["item"],
                item_data["type"],
                item_data["required"],
                item_data["status"],
                item_data["details"]
            )

        self.console.print()
        self.console.print(table)

    def _execute(self, **kwargs) -> None:
        """Execute IaC project structure check"""
        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY", ".")
        project_type = kwargs.get('project_type', 'stack')
        org_policy = kwargs.get('org_policy')
        enforcement = kwargs.get('enforcement', 'soft')
        
        # Create header with project type
        header_text = f"🏗️ Infrastructure as Code {'Module' if project_type == 'module' else 'Stack'} Structure Check"
        self.console.print()
        self.console.print(Panel(
            header_text,
            style="bold blue",
            box=box.ROUNDED
        ))
        
        try:
            # Run org policy check if source is provided
            org_violations = self._check_org_policy(directory, project_type, org_policy, skip_org=kwargs.get('skip_org_policy', False))

            # Capture stdout to format it nicely
            captured_output = io.StringIO()
            
            with redirect_stdout(captured_output):
                try:
                    result = self._validate_project_structure(
                        directory=directory, 
                        mode=kwargs.get('mode', 'soft'),
                        check_type=kwargs.get('check_type', 'structure'),
                        project_type=project_type
                    )
                except SystemExit as e:
                    result = e.code == 0
            
            # Format and display the captured output
            output = captured_output.getvalue()
            if output.strip():
                self._format_validation_output(output)

            # Display org policy results
            if org_violations is not None:
                self._display_org_violations(org_violations, enforcement)
                mandatory_fails = [v for v in org_violations if v.enforcement == "mandatory"]
                if mandatory_fails and enforcement == "hard":
                    result = False
            
            # Create summary
            if result:
                summary_panel = Panel(
                    "✅ [green]IaC project structure validation passed[/green]",
                    title="Summary",
                    style="green",
                    box=box.ROUNDED
                )
            else:
                summary_panel = Panel(
                    "❌ [red]IaC project structure validation failed[/red]\n"
                    "💡 [blue]Review the issues above and ensure your project follows the expected structure[/blue]",
                    title="Summary", 
                    style="red",
                    box=box.ROUNDED
                )
            
            self.console.print()
            self.console.print(summary_panel)
            
            # Exit with error code if hard enforcement has mandatory violations
            if not result and (kwargs.get('mode') == 'strict' or enforcement == 'hard'):
                exit(1)
                
        except Exception as e:
            self.console.print(f"❌ [red]Error during validation: {str(e)}[/red]")
            self.logger.error(f"Failed to execute IaC project check: {str(e)}")
            raise

    def _check_org_policy(self, directory: str, project_type: str, org_policy=None, skip_org: bool = False):
        """Check project against organizational policy if available."""
        if skip_org:
            self.console.print("[dim]📜 Org policy check skipped (--skip-org-policy)[/dim]")
            return None

        from .....services.check.org_policy_loader import get_org_policy_path, resolve_rules_dir
        from .....services.check.rule_merger import load_org_rules, merge_with_project, evaluate

        org_path = get_org_policy_path(org_policy)
        if not org_path:
            return None

        rules_dir = resolve_rules_dir(org_path)
        if not rules_dir:
            logger.info(f"No rules/ directory in org policy at {org_path}")
            return None

        self.console.print(f"[blue]📜 Loading org policy from: {org_path}[/blue]")

        # Map CLI project_type to toml filename
        type_map = {"stack": "terraform-terragrunt", "module": "terraform_module"}
        rule_type = type_map.get(project_type, project_type)

        ruleset = load_org_rules(rules_dir, rule_type)
        project_toml = os.path.join(directory, ".thothcf.toml")
        ruleset = merge_with_project(ruleset, project_toml)

        return evaluate(ruleset, directory)

    def _display_org_violations(self, violations, enforcement: str):
        """Display org policy violations in a Rich table."""
        if not violations:
            self.console.print(Panel(
                "✅ [green]Organization policy check passed[/green]",
                title="Org Policy",
                style="green",
                box=box.ROUNDED,
            ))
            return

        mandatory = [v for v in violations if v.enforcement == "mandatory"]
        recommended = [v for v in violations if v.enforcement == "recommended"]
        info = [v for v in violations if v.enforcement == "informational"]

        if mandatory:
            table = Table(title="❌ Mandatory Violations", box=box.ROUNDED, header_style="bold red")
            table.add_column("Rule", style="cyan")
            table.add_column("Expected", style="green")
            table.add_column("Found", style="red")
            for v in mandatory:
                table.add_row(v.rule, v.expected, v.found)
            self.console.print(table)

        if recommended:
            table = Table(title="⚠️ Recommendations", box=box.ROUNDED, header_style="bold yellow")
            table.add_column("Rule", style="cyan")
            table.add_column("Expected", style="green")
            table.add_column("Found", style="yellow")
            for v in recommended:
                table.add_row(v.rule, v.expected, v.found)
            self.console.print(table)

        if info:
            for v in info:
                self.console.print(f"  ℹ️  {v.rule}: {v.expected} (found: {v.found})")

    def _validate_project_structure(self, directory: str, mode: str = "soft", check_type: str = "structure", project_type: str = "stack") -> bool:
        """Validate the IaC project structure
        
        Args:
            directory: Directory to validate
            mode: Validation mode (soft/strict)
            check_type: Type of check (structure/metadata/compliance)
            project_type: Type of project (stack/module) - determines which template to use
        """
        # Map project_type to check_type for the validation service
        validation_check_type = "module" if project_type == "module" else "project"
        return validate(directory=directory, check_type=validation_check_type, mode=mode)


# Create the Click command
cli = CheckProjectIaCCommand.as_click_command(
    help="Check Infrastructure as Code project structure and configuration"
)(
    click.option(
        "-m", "--mode",
        help="Validation mode: soft (warnings) or strict (errors)",
        type=click.Choice(["soft", "strict"], case_sensitive=False),
        default="soft"
    ),
    click.option(
        "-t", "--check-type",
        help="Type of IaC check to perform",
        type=click.Choice(["structure", "metadata", "compliance"], case_sensitive=False),
        default="structure"
    ),
    click.option(
        "-p", "--project-type",
        help="Project type: stack (full project with modules/environments) or module (single reusable module)",
        type=click.Choice(["stack", "module"], case_sensitive=False),
        default="stack"
    ),
    click.option(
        "--org-policy",
        help="Organization policy source (Git URL or local path). Also reads THOTH_ORG_POLICY env var.",
        default=None,
    ),
    click.option(
        "--enforcement",
        help="Enforcement mode: soft (report only) or hard (fail on mandatory violations)",
        type=click.Choice(["soft", "hard"], case_sensitive=False),
        default="soft",
    ),
    click.option(
        "--skip-org-policy",
        is_flag=True,
        default=False,
        help="Skip organizational policy check (use when project has explicit exceptions)",
    ),
)
