"""Get public version for modules from public or private registry."""
import logging

import requests
from colorama import Fore


def get_public_github_version(resource: str):
    """
    Get public version from github.

    :param resource:
    :return:
    """
    print(f"{Fore.MAGENTA} Getting version for {resource}{Fore.RESET}")
    if "//" in resource:
        resource = resource.split("//")[0]

    source_url = f"https://registry.terraform.io/v1/modules/{resource}"
    print(source_url)
    response = requests.get(source_url)
    p_version = response.json()["version"]

    return p_version, source_url

    # print(response.json(), "\n", "\n")


def get_public_version(resource: str):
    """
    Get public version from public registry.

    :param resource:
    :return:
    """
    print(f"{Fore.MAGENTA} Getting version for {resource}{Fore.RESET}")
    if "//" in resource:
        resource = resource.split("//")[0]
    source_url = check_source_format(resource)
    print("the url is: ", source_url)
    source_url = f"{source_url}/{resource}"
    print(source_url)
    p_version = "Null"
    if "github" not in source_url:
        response = requests.get(source_url)
        p_version = response.json()["version"]
    # TODO add github compatibility
    return p_version, source_url


def check_version(
    latest_version: str, local_version: str, resource: str, resource_name: str
) -> str:
    """
    Check if the resource is outdated or not.

    :param latest_version:
    :param local_version:
    :param resource:
    :param resource_name:
    :return:
    """
    status = "Outdated"
    if latest_version in local_version:
        print(
            f"{Fore.MAGENTA}The resource {resource_name} is {Fore.GREEN}Updated{Fore.MAGENTA},"
            f" latest_version {latest_version} vs local_version {local_version} for {resource}"
        )
        status = "Updated"
    else:
        print(
            f"{Fore.MAGENTA} The resource {resource_name} is {Fore.RED}Outdated{Fore.MAGENTA}, "
            f"latest_version {latest_version} vs local_version {local_version}  for {resource}"
        )

    return status


def check_source_format(source: str = None):
    """
    Check Source format. If url in terraform or github.

    :param source:
    :return:
    """
    url = "https://registry.terraform.io/v1/modules"
    print("the source is", source)
    if "github.com" in source:
        print(f"{Fore.CYAN}Source: {source}")
        # if source.startswith("github.com"):
        url = "https://api.github.com/repos"
    elif "terraform-aws-modules" in source:
        url = "https://registry.terraform.io/v1/modules"

    return url


def get_version(component: dict):
    """
    Get version in local inventory.

    :param component:
    :return:
    """
    version = component.get("version", "None")
    if version == "Null":
        resource = component["source"][0]
        if "ref=" in resource:
            version = resource.split("ref=")[1]
            logging.info(version)
            component["version"] = [version]
            print(component)
    return component


def check_versions(inv: dict) -> dict:
    """
    Check Inventory versions.

    :param inv:
    :return:
    """
    inv["version"] = 2
    for components in inv["components"]:
        for c in components["components"]:
            local_version = get_version(c)["version"]
            logging.info(f"The component is: {c}")
            if isinstance(local_version, list):
                resource = c["source"][0]
                print(resource)
                get_p_version = get_public_version(resource)
                c["latest_version"] = get_p_version[0]
                c["source_url"] = get_p_version[1]

                logging.info(f'The latest version is {c["latest_version"]}')
                c["status"] = check_version(
                    latest_version=c["latest_version"],
                    local_version=local_version[0],
                    resource=resource,
                    resource_name=c["name"],
                )
            else:
                c["latest_version"] = "Null"
                c["source_url"] = "Null"
                c["status"] = "Null"

    return inv


def summary_inventory(
    inv,
):
    """
    Create summary inventory.

    :param inv:
    :return:
    """
    inv_summary = {}  # "ProjectName": project_name
    outdated = 0
    updated = 0
    local = 0
    list_outdated = []
    st = None
    for components in inv["components"]:
        for c in components["components"]:
            logging.info(c)
            local_version = c["version"]

            if isinstance(local_version, list):
                st = c.get("status", None)
                if st == "Updated":
                    updated += 1
                elif st == "Outdated":
                    outdated += 1
                    list_outdated.append(c)
            elif st is None and local_version == "Null":
                local += 1
    total = local + updated + outdated
    inv_summary["TotalModules"] = total
    inv_summary["LocalModules"] = local
    inv_summary["RemoteModules"] = updated + outdated
    inv_summary["Updated"] = updated
    inv_summary["Outdated"] = outdated
    print(inv_summary)

    inv_summary["UpdateStatus"] = f"{str((updated / total) * 100)} %"

    return inv_summary, list_outdated


# Print summary inventory based on rich print table
def print_summary_inventory(inv_summary):
    """
    Print summary inventory.

    :param inv_summary:
    :return:
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(
        title="Inventory - Summary",
        title_style="bold magenta",
        show_header=True,
        header_style="bold magenta",
        expand=True,
        show_lines=True,
    )
    table.add_column("Modules", style="dim")
    table.add_column("Status", style="dim")

    table.add_row("Total Modules", str(inv_summary["TotalModules"]))
    table.add_row("Local Modules", str(inv_summary["LocalModules"]))
    table.add_row("Remote Modules", str(inv_summary["RemoteModules"]))
    table.add_row("Updated", str(inv_summary["Updated"]))
    table.add_row("Outdated", str(inv_summary["Outdated"]))
    table.add_row("Update Status", str(inv_summary["UpdateStatus"]))

    console.print(table)
