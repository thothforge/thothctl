"""Common variables, methods, to all project."""
import hashlib
import logging
from pathlib import Path, PurePath

import os
import toml
from colorama import Fore
from rich.console import Console
from rich.table import Table


config_file_name = ".thothcf.toml"


def load_iac_conf(directory, file_name=config_file_name):
    """
    Load iac config file.

    :param file_name:
    :param directory:
    :return:
    """
    config_path = Path(os.path.join(directory, file_name))

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        logging.debug(config)
    else:
        print(f"{Fore.RED}No config file found. {config_path} {Fore.RESET}")
        config = {}

    return config


def create_iac_conf(file_name=config_file_name):
    """
    Create iac config file.

    :param file_name:
    :return:
    """
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)
    if not os.path.exists(PurePath(f"{Path.home()}/.thothcf/")):
        os.makedirs(PurePath(f"{Path.home()}/.thothcf/"))
        logging.debug(f"Folder {PurePath(f'{Path.home()}/.thothcf/')} created")

    if not os.path.exists(config_path):
        with open(config_path, mode="wt", encoding="utf-8") as fp:
            toml.dump({}, fp)

        print(f"{Fore.GREEN}Config file created. {config_path} {Fore.RESET}")
    else:
        print(f"{Fore.RED}Config file already exists. {config_path} {Fore.RESET}")

    return config_path


# dump content in toml file .thothcf.toml
def dump_iac_conf(file_name=config_file_name, content=None):
    """
    Dump iac config file.

    :param content:
    :param file_name:
    :return:
    """
    if content is None:
        content = {}
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    with open(config_path, mode="wt", encoding="utf-8") as fp:
        toml.dump(content, fp)

    logging.debug(f"{Fore.GREEN}Config file updated. {config_path} {Fore.RESET}")

    return config_path


# check if info project exists in toml file
# if exists doesn't update it, if not exists create it
def check_info_project(
    project_name: str,
    file_name=config_file_name,
):
    """
    Check if info project exists in toml file.

    :param project_name:
    :param file_name:

    :return:
    """
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if project_name in config:
            return config[project_name]
        else:
            return None
    else:
        return None


# create project info in toml file for creating an array of tables
def create_info_project(project_name: str, file_name=config_file_name, content=None):
    """
    Create project info in toml file for creating an array of tables.

    :param content:
    :param project_name:
    :param file_name:

    :return:
    """
    if content is None:
        content = {"template_files": []}
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if project_name in config:
            raise ValueError(
                f'💥 Project  "{project_name}" already exists. \n '
                f"Run 👉 {Fore.CYAN} thothctl remove -pj {project_name} 👈🏼 {Fore.RED}if you want to reuse the project name."
            )

        else:
            config[project_name] = content
            dump_iac_conf(content=config)
            return config[project_name]
    else:
        create_iac_conf()
        create_info_project(project_name, content=content)
        return None


# update info project file based on an array of dictionaries
# if an element of the array already exists it will be updated with the new content
def update_info_project(
    project_name: str, file_name=config_file_name, file_path: Path = None
):
    """
    Update info project file based on an array of dictionaries.

    :param file_path:
    :param project_name:
    :param file_name:

    :return:
    """
    logging.info(f"Updating project info {project_name}")

    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if project_name in config:
            entry = {
                "source": file_path.parent.as_posix(),
                "local": file_path.name,
                "hash": create_hash_file(file_path=file_path),
            }

            check, c_ = check_file_entry(
                entry=entry, config=config[project_name]["template_files"]
            )
            if check == 3:
                config[project_name]["template_files"].append(entry)
            elif check == 2:
                config[project_name]["template_files"].remove(entry)
                config[project_name]["template_files"].append(c_)

            dump_iac_conf(content=config)

            return config[project_name]
        else:
            create_info_project(project_name)
            update_info_project(
                project_name=project_name, file_name=file_name, file_path=file_path
            )


def check_file_entry(entry: dict = None, config: list = None):
    """
    Check file entry.

    :param config:
    :param entry:

    :return:
    """
    # check if entry are in template files array
    if not config:
        return 3, entry
    else:
        for p in config:
            if entry == p:
                logging.info(f"exists {p}")
                return 1, entry

            # check if hash are the same
            elif (
                entry["hash"] != p["hash"]
                and entry["source"] == p["source"]
                and entry["local"] == p["local"]
            ):
                logging.info(f"exists but was modified {entry}")
                entry["hash"] = p["hash"]
                logging.info(f" to {p}")
                return 2, entry
            else:
                logging.info(f"Doesn't exists {entry}")
                return 3, entry


# create function to create hash for a file and add to entry to check if template changed or not after create check file hash
def create_hash_file(file_path: PurePath = None):
    """
    Create hash file.

    :param file_path:
    :return:
    """
    if file_path is not None:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            return file_hash


# Create function for list projects in iacpb_home.toml file
def list_projects(file_name=config_file_name):
    """
    List projects in iacpb_home.toml file.

    :param file_name:
    :return project_list:

    """
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        return list(config.keys())
    else:
        return None


def print_list_projects():
    """
    Print list projects.

    :return:
    """

    table = Table(title="Project List", title_style="bold magenta", show_lines=True)
    table.add_column("ProjectName", justify="left", style="cyan", no_wrap=True)
    for p in list_projects():
        table.add_row(f"☑️ {Fore.CYAN} {p} {Fore.RESET}")

    console = Console()
    console.print(table)
