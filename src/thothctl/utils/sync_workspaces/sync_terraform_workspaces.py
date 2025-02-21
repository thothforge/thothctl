"""Sync workspaces."""
import json
import logging
import subprocess
from pathlib import Path, PurePath

import os
from colorama import Fore

from ..process_hcl.graph_manager import graph_dependencies_to_json


terragrun_file = "terragrunt.hcl"
terraform_path = ".terraform"
terragrunt_path = ".terragrunt-cache"


def r_sync_workspaces(directory):
    """
    Sync terraform workspaces in all directories.

    :param directory:
    :return:
    """
    d_name = Path(directory).resolve().name
    print(
        f"{Fore.LIGHTBLUE_EX}👾 Searching terragrunt files in {d_name}... {Fore.RESET}"
    )
    for dirpath, dirnames, filenames in os.walk(directory):
        for d in dirnames:
            if ".terraform" != d and ".terragrunt-cache" != d and ".git" != d:
                logging.info(f"{Fore.LIGHTBLUE_EX}👾 Folder {dirpath} {Fore.RESET}")
                logging.info(
                    f"{Fore.LIGHTBLUE_EX}👾 FileNames {filenames} {Fore.RESET}"
                )
                logging.info(f"{Fore.LIGHTBLUE_EX}👾 DirNames {d} {Fore.RESET}")

                if os.path.exists(PurePath(f"{d}/{terragrun_file}")):
                    p = PurePath(f"{d}/{terragrun_file}")

                    print(
                        f"{Fore.LIGHTBLUE_EX}👾 Find terragrunt file in {p}"
                        f"\n❇️ Synchronize Workspace  ... {Fore.RESET}"
                    )

                    print(p)
                    graph = json.loads(
                        graph_dependencies_to_json(os.path.join(os.getcwd()))
                    )

                    sync_workspaces(json_graph=graph)
                else:
                    logging.info(f" No terragrunt file in: {d}")

    # Synchronize local
    print(directory)

    if (
        os.path.exists(PurePath(f"{directory}/{terragrun_file}"))
        and terraform_path not in directory
        and terragrunt_path not in directory
    ):
        print(
            f"⚠️ {Fore.LIGHTBLUE_EX}   Find terragrunt.hcl files in {d} ... {Fore.RESET}"
            f"\n❇️ {Fore.LIGHTBLUE_EX} Synchronize Workspace ...  {Fore.RESET}"
        )
        graph = json.loads(graph_dependencies_to_json(directory))

        sync_workspaces(json_graph=graph)


def recursive_sync_workspace_all(directory):
    """
    Sync terraform workspaces in all directories.

    :param directory:
    :return:
    """
    logging.info(directory)
    ls_dir = os.listdir(directory)
    logging.info(ls_dir)

    for ld in ls_dir:
        nested_dir = os.path.join(directory, ld)
        print(f"Nested dir {nested_dir}")
        if (
            os.path.isdir(nested_dir)
            and ld.startswith(".") is False
            and terraform_path not in nested_dir
            and terragrunt_path not in nested_dir
        ):
            logging.info(f"Finding a folder {ld}...")
            recursive_sync_workspace(
                nested_dir,
            )
            if (
                os.path.exists(f"{nested_dir}/main.tf")
                and os.path.exists(
                    f"{nested_dir}/{terragrun_file}"
                    and terraform_path not in nested_dir
                    and terragrunt_path not in nested_dir
                )
                or (
                    os.path.exists(f"./{terragrun_file}")
                    and terraform_path not in nested_dir
                    and terragrunt_path not in nested_dir
                )
            ):
                print(
                    Fore.GREEN + f"⚠️Find terragrunt.hcl files in {nested_dir} ..."
                    f"\n❇️ Synchronize Workspace  ... " + Fore.RESET
                )
                graph = json.loads(graph_dependencies_to_json(nested_dir))

                sync_workspaces(json_graph=graph)
        else:
            if (
                os.path.exists("./main.tf")
                and os.path.exists(f"./{terragrun_file}")
                and terraform_path not in nested_dir
                and terragrunt_path not in nested_dir
            ) or (
                os.path.exists(f"./{terragrun_file}")
                and terraform_path not in nested_dir
                and terragrunt_path not in nested_dir
            ):
                print(
                    f"⚠️ {Fore.GREEN}  Find terragrunt.hcl files in {os.getcwd()} ... {Fore.RESET}"
                    f"\n❇️ {Fore.GREEN} Synchronize Workspace ...  {Fore.RESET}"
                )
                graph = json.loads(
                    graph_dependencies_to_json(os.path.join(os.getcwd()))
                )

                sync_workspaces(json_graph=graph)


def recursive_sync_workspace(directory):
    """
    Sync terraform workspaces recursively.

    :param directory:
    :return:
    """
    logging.info(directory)
    ls_dir = os.listdir(directory)
    logging.info(ls_dir)

    if (
        os.path.exists("./main.tf")
        and os.path.exists("./terragrunt.hcl")
        and terraform_path not in directory
        and terragrunt_path not in directory
    ) or (
        os.path.exists("./terragrunt.hcl")
        and terraform_path not in directory
        and terragrunt_path not in directory
    ):
        print(
            f"⚠️{Fore.LIGHTBLUE_EX}  Find terragrunt.hcl files in {os.getcwd()} ... "
            f"\n❇️ Synchronize Workspace ...  {Fore.RESET}"
        )
        graph = json.loads(graph_dependencies_to_json(os.path.join(os.getcwd())))

        sync_workspaces(json_graph=graph)


def sync_workspaces(json_graph):
    """
    Sync terraform workspaces.

    :param json_graph:
    :return:
    """
    after = []
    dict_list_dep = {}
    logging.info(json_graph)
    if "edges" in json_graph.keys():
        for a in json_graph["edges"]:
            for o in json_graph["objects"]:
                if a["tail"] == o["_gvid"]:
                    if o["name"] == "":
                        o["name"] = os.getcwd()
                    stack_name = json_graph["objects"][a["head"]]["name"]
                    dict_list_dep[stack_name] = {"check": True}
                    logging.info(o["name"] + " Depends of " + stack_name)
                    after.append(stack_name)

                    after = list(dict.fromkeys(after))

                    current_wk = show_workspace(o["name"])
                    print(
                        f'{Fore.MAGENTA}Workspace for main resource - {o["name"]}: {current_wk} '
                    )
                    depend_wk = show_workspace(stack_name)
                    print(
                        f"{Fore.MAGENTA}Workspace for dependency  - {stack_name}: {depend_wk} {Fore.RESET}"
                    )

                    if current_wk == depend_wk:
                        print(f"✅ {Fore.MAGENTA} Workspace sync{Fore.RESET} \n")
                    else:
                        print(
                            f"⚠️ {Fore.MAGENTA} Synchronizing workspace for {stack_name}. {Fore.RESET}\n"
                        )
                        select_workspace(directory=stack_name, workspace=current_wk)

        logging.info(f"after= {after}")


def get_workspace(file):
    """Get Workspaces.

    :param file:
    :return: workspace name.

    Example:
        >>> get_workspace(file)
        default

    """
    with open(file, "r", encoding="utf-8") as f:
        wk = f.readline()

    f.close()
    return wk


def show_workspace(directory):
    """
    Get workspace base on file or terragrunt command.

    :param directory:
    :return:
    """
    file = Path(f"{directory}/.terraform/environment")
    if os.path.exists(file):
        wk = get_workspace(file)
    else:
        command = f"cd {directory} && terragrunt init"
        run = os.popen(command)
        wk = run.read()
        print(wk)
        wk = "default"
    return wk


def select_workspace(directory, workspace):
    """
    Select Workspace using terragrunt command.

    :param directory: The directory to change to before running the command
    :param workspace: The workspace to select
    :return: The output of the terragrunt command
    """
    try:
        # Use subprocess.run instead of os.popen for better security and error handling
        result = subprocess.run(
            ["terragrunt", "workspace", "select", workspace],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )

        # Trim whitespace from the output
        wk = result.stdout.strip()

        # Set env var
        os.environ["env"] = wk

        print(wk)
        return wk

    except subprocess.CalledProcessError as e:
        print(f"Error selecting workspace: {e}")
        print(f"Error output: {e.stderr}")
        return None
