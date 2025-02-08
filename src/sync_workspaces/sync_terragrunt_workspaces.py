"""Sync terragrunt workspaces."""
import json
import logging
from pathlib import Path

import os
from colorama import Fore

from .sync_terraform_workspaces import (
    get_workspace,
    graph_dependencies_to_json,
    select_workspace,
)


wk_file = ".terraform/environment"
terragrun_file = "terragrunt.hcl"


def grunt_show_workspace(directory):
    """
    Show grunt workspaces.

    :param directory:
    :return:
    """
    find = False
    wk = "default"
    for dirpath, dirnames, filenames in os.walk(directory):
        for d in dirnames:
            if ".terraform" == d:
                r_p = Path(dirpath).resolve().absolute()
                logging.info(r_p)
                file = Path(f"{r_p}/{wk_file}").resolve()
                logging.info(file)
                if Path.exists(file):
                    wk = get_workspace(file)
                    set_t_wk(directory=directory, workspace=wk)
                    print(f"{Fore.LIGHTBLUE_EX}👾 Get workspace ... {Fore.RESET}")
                    find = True
    if not find:
        command = f"cd {directory} && terragrunt init"
        run = os.popen(command)
        wk = run.read()
        logging.info(wk)
        wk = "default"
        set_t_wk(directory=directory, workspace=wk)
    return wk


def t_sync_workspaces(json_graph):
    """
    Sync Workspaces for terragrunt projects.

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

                    current_wk = grunt_show_workspace(o["name"])

                    print(
                        f'{Fore.MAGENTA}Workspace for main resource - {o["name"]}: {current_wk} '
                    )
                    depend_wk = grunt_show_workspace(stack_name)
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


def grunt_sync_workspaces(directory):
    """
    Sync Workspace for terragrunt projects.

    :param directory:
    :return:
    """
    print(f"{Fore.LIGHTBLUE_EX}👾 Searching terragrunt files ... {Fore.RESET}")
    for dirpath, dirnames, filenames in os.walk(directory):
        if (
            ".terraform" not in dirpath
            and ".terragrunt-cache" not in dirpath
            and ".git" not in dirpath
        ):
            r_p = Path(dirpath).resolve().absolute()
            logging.info(r_p)
            file = Path(f"{r_p}/{terragrun_file}").resolve()

            if Path.exists(file):
                logging.info(f"Find folder {file}")
                set_t_wk(
                    directory=directory, workspace=grunt_show_workspace(directory=r_p)
                )
                graph = json.loads(graph_dependencies_to_json(r_p))
                t_sync_workspaces(graph)


terragrunt_wk_file = ".environment.hcl"


def set_t_wk(
    directory,
    workspace: str,
):
    """
    Set workspace for terragrunt project.

    :param directory:
    :param workspace:
    :return:
    """
    file_name = Path(os.path.join(directory, terragrunt_wk_file)).resolve().absolute()
    content = 'locals { workspace = get_env("TF_VAR_env", "' + workspace + '")  }'
    logging.info(content)

    with open(file_name, "w") as a_file:
        a_file.write(content)

    a_file.close()
