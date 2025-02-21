"""Clean up files and folders into a project."""
import shutil
from pathlib import Path

import inquirer
import os
from colorama import Fore

from ....common.common import dump_iac_conf, load_iac_conf


def cleanup_project(
    directory, additional_files: str = None, additional_folders: str = None
):
    """
    Clean up files and folders into a project.

    :param directory:
    :param additional_files:
    :param additional_folders:
    :return:
    """
    additional_files = (
        additional_files.split(",") if additional_files is not None else []
    )
    additional_folders = (
        additional_folders.split(",") if additional_folders is not None else []
    )

    print(f"{Fore.LIGHTBLUE_EX}👾 Cleaning project files ... {Fore.RESET}")
    for dirpath, dirnames, filenames in os.walk(directory):
        if any(ext in dirpath for ext in [".terraform", ".terragrunt-cache"]):
            print(f"{Fore.LIGHTBLUE_EX}👾 Clean folder {dirpath} {Fore.RESET}")
            shutil.rmtree(dirpath)

        for f in filenames:
            if any(cond for cond in ["tfplan" in f, f in additional_files]):
                print(f"{Fore.LIGHTBLUE_EX}👾 Clean file {f} {Fore.RESET}")

                file = Path(dirpath).joinpath(f)
                os.remove(file)

        if additional_folders is not None:
            for d in additional_folders:
                if d in dirpath:
                    print(f"{Fore.LIGHTBLUE_EX}👾 Clean folder {dirpath} {Fore.RESET}")
                    shutil.rmtree(dirpath)


def remove_projects(project_name: str):
    """
    Remove project from thothctl configuration file and clean residuals files.
    :param project_name:
    :return:
    """
    config_path = Path.joinpath(Path.home(), ".thothcf")
    conf = load_iac_conf(directory=config_path)
    if project_name in conf:
        choices = ["yes", "no"]
        questions = [
            inquirer.List(
                "delete",
                message=f" {Fore.CYAN} ⚠️ Are you sure to delete project {project_name} from configuration files? ",
                choices=choices,
            )
        ]

        answers = inquirer.prompt(questions)
        if answers["delete"] == "yes" and project_name in conf.keys():
            print(
                f'{Fore.YELLOW} ⚠️ Removing project "{project_name}" from configuration file. {Fore.RESET}'
            )
            conf.pop(project_name)
            # remove directory project if exists
            if os.path.exists(config_path.joinpath(project_name)):
                shutil.rmtree(config_path.joinpath(project_name))
                print(f'{Fore.YELLOW} Project "{project_name}" removed {Fore.RESET}')
            dump_iac_conf(content=conf)
    else:
        print(f'{Fore.RED}💥 Project "{project_name}" not found {Fore.RESET}')
