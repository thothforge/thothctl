"""Create Inventory Methods."""
import datetime
import json
import logging
from pathlib import Path

import hcl2
import os
import pdfkit
from colorama import Fore
from json2html import json2html
from rich.align import Align
from rich.console import Console
from rich.table import Table

from .get_public_versions import (
    check_versions,
    print_summary_inventory,
    summary_inventory,
)


def get_components(file_hcl: str) -> list:
    """
    Get version into modules.

    :param file_hcl:
    """
    with open(file_hcl, "r", encoding="utf-8") as file:
        logging.info(f"Loading hcl file {file_hcl}")
        try:
            data = hcl2.load(file)
        except Exception as e:
            print(f"Can not read the file {file}, {e}")
            data = {}
        logging.debug(data)
        components = {}
        if "module" in data.keys():
            for m in data["module"]:
                for k, v in m.items():
                    component = {
                        "type": "module",
                        "name": k,
                        "version": m[k].get("version", "Null"),
                        "source": m[k].get("source", "Null"),
                        "file": file_hcl,
                    }
                    yield component

        else:
            print(f"{Fore.LIGHTBLUE_EX} No Modules in {file_hcl} {Fore.RESET}")
        logging.debug(components)


def cyclone_dx(components=None, project_name: str = None) -> dict:
    """
    Create macro inventory dict.

    :param components:
    :param project_name:
    :return:
    """
    if components is None:
        components = []
    inventory = {
        "version": 1,
        "projectName": project_name,
        "components": components,
    }

    return inventory


def walk_folder(directory):
    """
    Walk folders to find tf files and get components with lazy method.

    :param directory:
    :return:
    """
    full_invent = cyclone_dx()
    print(f"{Fore.LIGHTBLUE_EX}👾 Find External Dependencies ... {Fore.RESET}")
    for dirpath, dirnames, filenames in os.walk(directory):
        if not any(ext in dirpath for ext in [".terraform", ".terragrunt-cache"]):
            for f in filenames:
                if f.split(".")[-1] == "tf":
                    print(
                        f"{Fore.LIGHTBLUE_EX}👾 Find file {f} in {dirpath} {Fore.RESET}"
                    )
                    components = get_components(os.path.join(dirpath, f))
                    c = []
                    for component in components:
                        c.append(component)

                    resource = {"path": dirpath, "components": c}
                    if len(c) > 0:
                        full_invent["components"].append(resource)
    return full_invent


def create_report_html_pdf(report, reports_dir, report_name):
    """
    Create HTML and PDF Reports.

    :param reports_dir:
    :param report:
    :param report_name:
    :return:
    """
    date = datetime.datetime.today().strftime("%b%d%Y_%S")
    # initializing variables with values
    file_name = f"{report_name}_{date}"
    logging.info(" Creating reports ...")
    body = """
        <html>
        <style>
      .tbl { border-collapse: collapse; width:300px; }
      .tbl th, .tbl td { padding: 5px; border: solid 1px #777; }
      .tbl th { background-color: #00ff0080; }
      .tbl-separate { border-collapse: separate; border-spacing: 5px;}

          .fl-table {
            border-radius: 5px;
            font-size: 12px;
            font-weight: normal;
            border: none;
            border-collapse: collapse;
            width: 100%;
            max-width: 100%;
            white-space: nowrap;
            background-color: white;

        }

        .fl-table td, .fl-table th {
            text-align: left;
            padding: 8px;
            border: solid 1px #777;
        }

        .fl-table td {
            border-right: 1px solid #f8f8f8;
            font-size: 14px;
        }

        .fl-table thead th {
            color: #ffffff;
            background: #35259C;
        }


        .fl-table thead th:nth-child(odd) {
            color: #ffffff;
            background: #324960;
        }

        .fl-table tr:nth-child(even) {
            background: #F8F8F8;
        }

        </style>

          <h1 style="font-size:100px; color:black; margin:10px;">Modules Inventory and Update status - IaC </h1>

        <p style="font-size:30px; color: black;"><em>Modules Inventory and Update status  for IaC - create by thothctl </em></p>

          </html>
        """
    report_path = os.path.join(reports_dir, f"{file_name}.html")
    with open(report_path, "w") as file:
        file.write(body)
        print(f"{Fore.MAGENTA}👷 Creating HTML Report... {Fore.RESET}")
        print(f"{Fore.MAGENTA}📑 {file_name}.html")
        content = json2html.convert(
            json=report, table_attributes='id="report-table" class="fl-table"'
        )
        print(content, file=file)
    # Create pdf file
    options = {
        "page-size": "A0",
        "margin-top": "0.7in",
        "margin-right": "0.7in",
        "margin-bottom": "0.7in",
        "margin-left": "0.7in",
        "encoding": "UTF-8",
        "orientation": "Landscape",
    }
    logging.info("Creating HTML Report...")
    pdfkit.from_file(
        f"{reports_dir}/{file_name}.html",
        f"{reports_dir}/{file_name}.pdf",
        options=options,
    )
    files_paths = [f"{reports_dir}/{file_name}.html", f"{reports_dir}/{file_name}.pdf"]

    return files_paths


def create_json_report(report, reports_dir, report_name):
    """
    Create json report.

    :param report:
    :param reports_dir:
    :param report_name:
    :return:
    """
    print(f"{Fore.MAGENTA}👷 Creating JSON Report... {Fore.RESET}")
    date = datetime.datetime.today().strftime("%b%d%Y_%S")
    # initializing variables with values
    file_name = f"{report_name}_{date}"
    print(f"{Fore.MAGENTA}📑 {file_name}")
    report_path = os.path.join(reports_dir, f"{file_name}.json")
    with open(report_path, "w") as f:
        print(json.dumps(report), file=f)


def create_inventory(
    report_type: str = "html",
    reports_directory: str = "Reports",
    source_directory: str = ".",
    ch_versions: bool = False,
):
    """
    Create inventory for different formats and types.

    :param report_type:
    :param reports_directory:
    :param source_directory:
    :param ch_versions:
    :return:
    """
    com = walk_folder(directory=source_directory)
    if ch_versions:
        com = check_versions(inv=com)
    # Set project Name
    relative_path = Path(source_directory).resolve().name
    com["projectName"] = relative_path
    if report_type == "html":
        create_report_html_pdf(com, reports_directory, report_name="InventoryIaC")
    elif report_type == "json":
        create_json_report(com, reports_directory, report_name="InventoryIaC")

    elif report_type == "all":
        create_report_html_pdf(com, reports_directory, report_name="InventoryIaC")
        create_json_report(com, reports_directory, report_name="InventoryIaC")

    print_inventory(com)
    if ch_versions:
        create_report_html_pdf(
            summary_inventory(com)[0],
            reports_dir=reports_directory,
            report_name="SummaryInventoryIaC",
        )
        print_summary_inventory(summary_inventory(com)[0])


def print_inventory(inventory):
    """
    Print inventory to console using pretty style.

    :param inventory:
    :return:
    """
    console = Console()
    table = Table(
        title="Inventory - Modules and Versions",
        title_style="bold magenta",
        show_header=True,
        header_style="bold magenta",
        expand=True,
        show_lines=True,
    )
    table.add_column("Path", style="dim")
    table.add_column("Components", style="dim")

    for out in inventory["components"]:
        netsted_table = Table(show_lines=True)
        netsted_table.add_column("Type")
        netsted_table.add_column("Name")
        netsted_table.add_column("Version")
        netsted_table.add_column("Source")
        netsted_table.add_column("File")
        netsted_table.add_column("LatestVersion")
        netsted_table.add_column("SourceUrl")
        netsted_table.add_column("Status")

        for o in out["components"]:
            netsted_table.add_row(
                o["type"],
                o["name"],
                o["version"][0],
                o["source"][0],
                o["file"],
                o["latest_version"],
                o["source_url"],
                o["status"],
            )
        table.add_row(
            Align(f'[blue]{out["path"]}[/blue]', vertical="middle"), netsted_table
        )

    console.print(table)
