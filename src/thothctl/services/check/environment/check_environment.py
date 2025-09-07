"""Check environment tools."""
import json
import os
import subprocess
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ....core.version_tools import version_tools


class EnvironmentChecker:
    """Service class for checking development environment tools."""

    def __init__(self):
        self.console = Console()
        self.tools = self._load_tools()

    def _load_tools(self, mode: str = "generic") -> List[Dict]:
        """Load tools configuration."""
        if mode == "custom":
            with open("tools.json") as f:
                return json.load(f)
        return json.loads(version_tools)

    def _extract_version(self, version_output: str, tool_name: str) -> str:
        """Extract clean version number from tool output."""
        import re
        
        # Common version patterns
        patterns = [
            r'v?(\d+\.\d+\.\d+)',  # Standard semver
            r'version\s+v?(\d+\.\d+\.\d+)',  # "version 1.2.3"
            r'(\d+\.\d+\.\d+)',  # Just numbers
        ]
        
        for pattern in patterns:
            match = re.search(pattern, version_output, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Fallback: return first 15 chars
        return version_output[:15] + "..." if len(version_output) > 15 else version_output

    def _check_tool_installed(self, tool: Dict) -> Tuple[bool, str]:
        """Check if a tool is installed and get its version."""
        command = tool.get("command", f'{tool["name"]} --version')
        
        try:
            result = subprocess.run(
                command.split(), 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                # Extract version from output (first line, remove extra text)
                version_line = result.stdout.strip().split('\n')[0]
                clean_version = self._extract_version(version_line, tool["name"])
                return True, clean_version
            return False, ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, ""

    def check_environment(self) -> Dict:
        """Check all environment tools and return results."""
        results = {
            "installed": [],
            "missing": [],
            "total": len(self.tools)
        }

        # Create summary table
        table = Table(
            title="🔧 Development Environment Check",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Tool", style="cyan", width=20)
        table.add_column("Status", width=10)
        table.add_column("Current", style="blue", width=15)
        table.add_column("Recommended", style="yellow", width=15)

        for tool in self.tools:
            is_installed, version_output = self._check_tool_installed(tool)
            
            if is_installed:
                results["installed"].append(tool["name"])
                status = Text("✅ Installed", style="green")
                current_version = version_output
            else:
                results["missing"].append(tool["name"])
                status = Text("❌ Missing", style="red")
                current_version = "Not found"
            
            table.add_row(
                tool["name"],
                status,
                current_version,
                tool["version"]
            )

        # Display results
        self.console.print()
        self.console.print(table)
        
        # Summary panel
        installed_count = len(results["installed"])
        missing_count = len(results["missing"])
        
        if missing_count == 0:
            summary_text = f"🎉 All {installed_count} tools are installed!"
            panel_style = "green"
        else:
            summary_text = f"📊 {installed_count}/{results['total']} tools installed"
            if missing_count > 0:
                summary_text += f"\n❗ Missing: {', '.join(results['missing'])}"
            panel_style = "yellow"

        summary_panel = Panel(
            summary_text,
            title="Summary",
            style=panel_style,
            box=box.ROUNDED
        )
        
        self.console.print()
        self.console.print(summary_panel)
        
        if missing_count > 0:
            self.console.print()
            self.console.print(
                "💡 [bold blue]Tip:[/bold blue] Run [cyan]thothctl init env[/cyan] to install missing tools"
            )

        return results

    def get_tools_names(self) -> List[str]:
        """Get list of tool names."""
        return [tool["name"] for tool in self.tools]

    def get_tool_versions(self) -> Dict[str, str]:
        """Get dictionary of tool versions."""
        return {tool["name"]: tool["version"] for tool in self.tools}


# Backward compatibility functions
def load_tools(mode="generic"):
    """Load tools from configuration."""
    checker = EnvironmentChecker()
    return checker.tools

def get_tools_name(tools):
    """Get tools names."""
    return [tool["name"] for tool in tools]

def get_tool_version(tools):
    """Get tools versions."""
    return {tool["name"]: tool["version"] for tool in tools}

def check_environment():
    """Check environment tools."""
    checker = EnvironmentChecker()
    return checker.check_environment()
