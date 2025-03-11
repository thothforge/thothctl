"""Report generation service for inventory management."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pdfkit
from json2html import json2html
from rich import box
from rich.align import Align
from rich.console import Console
from rich.style import Style
from rich.table import Table


logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating inventory reports."""

    def __init__(self, reports_directory: str = "Reports"):
        """Initialize report service."""
        self.reports_dir = Path(reports_directory)
        self.reports_dir.mkdir(exist_ok=True)
        self.console = Console()

    def _create_report_path(self, report_name: str, extension: str) -> Path:
        """Create report file path with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.reports_dir / f"{report_name}_{timestamp}.{extension}"

    def create_html_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC"
    ) -> Path:
        """Create HTML report from inventory data with custom styling."""
        try:
            # Define HTML template with proper string formatting
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        background-color: #f5f5f5;
                    }}
                    .inventory-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                        background-color: white;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                    }}
                    .inventory-table th, .inventory-table td {{
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }}
                    .inventory-table th {{
                        background-color: #4CAF50;
                        color: white;
                    }}
                    .inventory-table tr:nth-child(even) {{
                        background-color: #f9f9f9;
                    }}
                    .status-updated {{
                        color: green;
                        font-weight: bold;
                    }}
                    .status-outdated {{
                        color: red;
                        font-weight: bold;
                    }}
                    .status-unknown {{
                        color: orange;
                        font-weight: bold;
                    }}
                    h1 {{
                        color: #333;
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                </style>
            </head>
            <body>
                <h1>Infrastructure Inventory Report</h1>
                {content}
            </body>
            </html>
            """

            # Convert inventory to HTML
            html_content = json2html.convert(
                json=inventory, table_attributes='class="inventory-table"'
            )

            # Create report file
            report_path = self._create_report_path(report_name, "html")

            # Write the report with proper formatting
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_template.format(content=html_content))

            logger.info(f"HTML report created at: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to create HTML report: {str(e)}")
            raise

    def create_pdf_report(
        self, html_path: Path, report_name: str = "InventoryIaC"
    ) -> Path:
        """Create PDF report from HTML file with custom options."""
        try:
            pdf_path = self._create_report_path(report_name, "pdf")

            options = {
                "page-size": "A4",
                "margin-top": "20mm",
                "margin-right": "20mm",
                "margin-bottom": "20mm",
                "margin-left": "20mm",
                "encoding": "UTF-8",
                "no-outline": None,
                "enable-local-file-access": None,
            }

            pdfkit.from_file(str(html_path), str(pdf_path), options=options)
            logger.info(f"PDF report created at: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Failed to create PDF report: {str(e)}")
            raise

    def create_json_report(
        self, inventory: Dict[str, Any], report_name: str = "InventoryIaC"
    ) -> Path:
        """Create formatted JSON report from inventory data."""
        try:
            report_path = self._create_report_path(report_name, "json")

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(inventory, f, indent=2, default=str, ensure_ascii=False)

            logger.info(f"JSON report created at: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Failed to create JSON report: {str(e)}")
            raise

    def print_inventory_console(self, inventory: Dict[str, Any]) -> None:
        """Print inventory to console using rich table with updated format."""
        try:
            # Create main table
            table = Table(
                title="Infrastructure Inventory Report",
                box=box.ROUNDED,
                header_style="bold magenta",
                title_style="bold blue",
                show_lines=True,
                expand=True,
            )
            table.add_column("Stack", style="dim", max_width=40)
            table.add_column(
                "Components",
                style="dim",
            )

            # Process components
            for component_group in inventory.get("components", []):
                # Add columns
                netsted_table = Table(show_lines=True)
                netsted_table.add_column("Type", style="cyan")
                netsted_table.add_column("Name", style="blue")
                netsted_table.add_column("Current Version", style="green")
                netsted_table.add_column("Source", style="white", overflow="fold")
                netsted_table.add_column("Latest Version", style="yellow")
                netsted_table.add_column("SourceUrl")
                netsted_table.add_column("Status", justify="center")

                for component in component_group.get("components", []):
                    current_version = component.get("version", ["Null"])
                    if isinstance(current_version, list):
                        current_version = current_version[0]

                    status = component.get("status", "Unknown")
                    status_style = {
                        "Updated": Style(color="green", bold=True),
                        "Outdated": Style(color="red", bold=True),
                        "Unknown": Style(color="yellow", bold=True),
                        "Null": Style(color="blue", bold=True),
                    }.get(status, Style(color="white"))

                    netsted_table.add_row(
                        component.get("type", "Unknown"),
                        component.get("name", "Unknown"),
                        str(current_version),
                        str(component.get("source", ["Unknown"])[0]),
                        str(component.get("latest_version", "Unknown")),
                        str(component.get("source_url", "Unknown")),
                        status,
                    )
                table.add_row(
                    Align(f'[blue]{component_group["path"]}[/blue]', vertical="middle"),
                    netsted_table,
                )

            # Print the table
            self.console.print()
            self.console.print(Align.center(table))
            self.console.print()

            # Print summary
            self._print_summary(inventory)

        except Exception as e:
            logger.error(f"Failed to print inventory to console: {str(e)}")
            self.console.print(f"[red]Error displaying inventory: {str(e)}[/red]")

    def _print_summary(self, inventory: Dict[str, Any]) -> None:
        """Print inventory summary statistics."""
        try:
            total_components = sum(
                len(group.get("components", []))
                for group in inventory.get("components", [])
            )

            status_counts = {"Updated": 0, "Outdated": 0, "Unknown": 0}

            for group in inventory.get("components", []):
                for component in group.get("components", []):
                    status = component.get("status", "Unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1

            summary_table = Table(
                title="Summary",
                box=box.ROUNDED,
                show_header=False,
                title_style="bold blue",
            )

            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="magenta")

            summary_table.add_row("Total Components", str(total_components))
            summary_table.add_row(
                "Updated Components", f"[green]{status_counts['Updated']}[/green]"
            )
            summary_table.add_row(
                "Outdated Components", f"[red]{status_counts['Outdated']}[/red]"
            )
            summary_table.add_row(
                "Unknown Status", f"[yellow]{status_counts['Unknown']}[/yellow]"
            )

            self.console.print(Align.center(summary_table))
            self.console.print()

        except Exception as e:
            logger.error(f"Failed to print summary: {str(e)}")
