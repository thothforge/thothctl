"""Update versions."""
import json
import logging

import inquirer
import os
from colorama import Fore
from rich.console import Console
from rich.table import Table

from .create_inventory import summary_inventory


def load_inventory(inventory_file: str):
    """
    Load inventory file.

    :param inventory_file:
    :return:
    """
    with open(inventory_file) as invent:
        inv = json.loads(invent.read())
        return inv


def print_table(list_outdated: list):
    """
    Print table pretty.

    :param list_outdated:
    :return:
    """
    console = Console()
    table = Table(
        title="Modules version to Update",
        title_style="bold magenta",
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Name", style="dim")
    table.add_column("ActualVersion", style="dim")
    table.add_column("NewVersion", style="dim")
    table.add_column("Source", style="dim")
    table.add_column("File", style="dim")

    for out in list_outdated:
        table.add_row(
            out["name"],
            f'[red]{out["version"][0]}[/red]',
            f'[green]{out["latest_version"]}[/green]',
            out["source"][0],
            out["file"],
        )

    console.print(table)


def update_versions(list_outdated: list, auto_approve=False, action="update"):
    """
    Update versions.

    :param list_outdated:
    :param auto_approve:
    :param action:
    :return:
    """
    if not auto_approve:
        # use inquirer to  prompt the user
        auto_approve = approve_update(action="main")

    if auto_approve:
        auto_apply_all = approve_update(action="all_modules")
        for out in list_outdated:
            file_name = out["file"]
            search, replace = get_version_strings(file_details=out, action=action)

            if auto_apply_all:
                print(f"{Fore.GREEN} Autoplaying ... {Fore.RESET}")
            else:
                control_update = approve_update(
                    search=search, replace=replace, file_name=file_name, action="single"
                )

                if not control_update:
                    continue

            if replace is not None:
                with open(file_name, "r") as file:
                    data = file.read()

                data = replace_version(data, search, replace)

                with open(file_name, "w") as file:
                    file.write(data)

                # Printing Text replaced
                print(f"Version {search} changed to {replace} in {file_name}")
                logging.info(f"Version {search} changed to {replace} in {file_name}")
                os.system(f"terraform fmt {file_name}")
                print(
                    f"{Fore.GREEN}✔️ Version changed successfully. "
                    f"Run plan and apply for checking changes.{Fore.RESET} \n"
                )
    else:
        print(f"{Fore.RED}❌ No changes to apply.{Fore.RESET}")


def approve_update(search="", replace="", file_name="", action="main") -> bool:
    """
    Approve or update message.

    :param search:
    :param replace:
    :param file_name:
    :param action:
    :return:
    """
    message = f"{Fore.BLUE} ⚠️ Are you sure to continue with the update?"
    if action == "single":
        message = f"⚠️ Are you sure to continue with to change version {search}  to {replace} in {file_name}?"
    elif action == "all_modules":
        message = f"{Fore.BLUE}⚠️ Apply to all modules ? {Fore.RESET}"
    # prompt user for approval
    # use inquirer to  prompt the user
    questions = [
        inquirer.List("update", message=message, choices=["yes", "no"], default="yes"),
    ]
    answers = inquirer.prompt(questions)
    control_update = answers["update"]
    return control_update == "yes"


def get_version_strings(file_details: dict, action="update"):
    """
    Get version in files.

    :param file_details:
    :param action:
    :return:
    """
    # extract from config or details
    search = file_details["version"][0]
    replace = file_details["latest_version"]

    if action == "restore":
        search = file_details["latest_version"]
        replace = file_details["version"][0]
    return search, replace


def replace_version(contents: str, search: str, replace: str) -> str:
    """
    Replace version.

    :param contents:
    :param search:
    :param replace:
    :return:
    """
    return contents.replace(search, replace)


def main_update_versions(inventory_file, auto_approve: bool = False, action="update"):
    """
    Update versions.

    :param inventory_file:
    :param auto_approve:
    :param action:
    :return:
    """
    inventory = load_inventory(inventory_file=inventory_file)
    checks = summary_inventory(inv=inventory)
    print_table(list_outdated=checks[1])
    update_versions(list_outdated=checks[1], auto_approve=auto_approve, action=action)
