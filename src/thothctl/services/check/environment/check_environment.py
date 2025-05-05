"""Check environment tools."""
import json

import os
from colorama import Fore

from ....core.version_tools import version_tools


def is_tool(tool):
    """
    Check if tool exists.

    :param tool: dict with name, version I.E:
    {
                "name": "terraform",
                "version": "1.8.1"
        }
    :return: True or False if tool exists
    """
    command = tool.get("command", "Null")
    if command == "Null":
        command = f'{tool["name"]} --version'
    print(f"{Fore.MAGENTA} Checking  ➡️ {tool['name']} ")
    run = os.system(command)

    if run != 0:
        print(f"{Fore.RED}❌   {tool['name']} doesn't found, please install it \n")
        return False
    else:
        print(
            f'{Fore.GREEN}✅   {tool["name"]} already installed. Recommended version {tool["version"]} {Fore.RESET} \n'
        )
        return True


def get_tools_name(tools):
    """
    Get tools name.

    :param tools:
    :return:
    """
    names = []
    for tool in tools:
        names.append(tool["name"])
    return names


def get_tool_version(tools):
    """
    Get tools version.

    :param tools:
    :return:
    """
    versions = {}
    for tool in tools:
        print(
            f'{Fore.GREEN}✅   {tool["name"]} Recommended version {tool["version"]} {Fore.RESET} '
        )
        versions[tool["name"]] = tool["version"]

    return versions


def load_tools(mode="generic"):
    """
    Load tools from json file.

    :param mode:
    :return:
    """
    print("Load Tools...")
    if mode == "custom":
        f = open("tools.json")

        # returns JSON object as a dictionary
        tools = json.loads(f.read())
        f.close()
    else:
        tools = json.loads(version_tools)
    return tools


def check_environment():
    """
    Check environment tools.

    :param :
    :return:
    """
    tools = load_tools()
    print(
        f"{Fore.GREEN}Checking if your environment already have the necessary tools ... {Fore.RESET}"
    )

    for t in tools:
        is_tool(t)
