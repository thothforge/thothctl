"""Common variables, methods, to all project."""
import hashlib
import logging
from pathlib import Path, PurePath
from typing import Optional, Dict, Any

import os
import toml
from colorama import Fore
from rich.console import Console
from rich.table import Table

from ..utils.platform_utils import get_config_dir


config_file_name = ".thothcf.toml"


def load_iac_conf(directory, file_name=config_file_name):
    """
    Load iac config file.

    :param file_name:
    :param directory:
    :return:
    """
    config_path = Path(directory) / file_name

    if config_path.exists():
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
    config_dir = get_config_dir()
    config_path = config_dir / file_name
    
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        logging.debug(f"Folder {config_dir} created")

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
def create_info_project(project_name: str, file_name=config_file_name, content=None, space: Optional[str] = None):
    """
    Create project info in toml file for creating an array of tables.

    :param content: Project content
    :param project_name: Name of the project
    :param file_name: Config file name
    :param space: Space name for the project
    :return: Project configuration
    """
    if content is None:
        content = {"template_files": []}
        
    # Add thothcf section with space if provided
    if "thothcf" not in content:
        content["thothcf"] = {"project_id": project_name}
        
    if space:
        content["thothcf"]["space"] = space
        
    config_path = PurePath(f"{Path.home()}/.thothcf/", file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if project_name in config:
            # Check if project has space information
            space_info = ""
            if config[project_name].get("thothcf") and config[project_name]["thothcf"].get("space"):
                project_space = config[project_name]["thothcf"]["space"]
                space_info = f" in space '{project_space}'"
                
            # Create the exact removal command
            removal_cmd = f"thothctl remove project -pj {project_name}"
            
            raise ValueError(
                f"💥 Project '{project_name}'{space_info} already exists. \n"
                f"Run 👉 {Fore.CYAN}{removal_cmd}{Fore.RESET} 👈🏼 if you want to reuse the project name."
            )
        else:
            config[project_name] = content
            dump_iac_conf(content=config)
            return config[project_name]
    else:
        create_iac_conf()
        create_info_project(project_name, content=content, space=space)
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


def list_spaces():
    """
    List spaces in spaces.toml file.

    :return: List of space names
    """
    config_path = PurePath(f"{Path.home()}/.thothcf/spaces.toml")

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if "spaces" in config:
            return list(config["spaces"].keys())
    
    return []


def get_project_space(project_name):
    """
    Get the space associated with a project.

    :param project_name: Name of the project
    :return: Space name or None if not associated with a space
    """
    config_path = PurePath(f"{Path.home()}/.thothcf/", config_file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if project_name in config and "thothcf" in config[project_name]:
            return config[project_name]["thothcf"].get("space")
    
    return None


def get_space_details():
    """
    Get details for all spaces.

    :return: Dictionary with space details
    """
    config_path = PurePath(f"{Path.home()}/.thothcf/spaces.toml")
    space_details = {}

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        if "spaces" in config:
            for space_name, space_data in config["spaces"].items():
                space_details[space_name] = space_data
    
    return space_details


def get_space_vcs_provider(space_name: str) -> Optional[str]:
    """
    Get the VCS provider for a space.
    
    :param space_name: Name of the space
    :return: VCS provider name or None if not found
    """
    if not space_name:
        return None
        
    space_details = get_space_details()
    if space_name in space_details:
        return space_details[space_name].get("version_control", {}).get("provider")
    
    return None


def get_projects_in_space(space_name):
    """
    Get all projects in a specific space.
    
    :param space_name: Name of the space
    :return: List of project names in the space
    """
    projects = []
    config_path = PurePath(f"{Path.home()}/.thothcf/", config_file_name)

    if os.path.exists(config_path):
        with open(config_path, mode="rt", encoding="utf-8") as fp:
            config = toml.load(fp)

        for project_name, project_data in config.items():
            if isinstance(project_data, dict) and "thothcf" in project_data:
                if project_data["thothcf"].get("space") == space_name:
                    projects.append(project_name)
    
    
    return projects


def print_list_projects(show_space=True):
    """
    Print list projects.

    :param show_space: Whether to show space information
    :return:
    """
    table = Table(title="Project List", title_style="bold magenta", show_lines=True)
    table.add_column("ProjectName", justify="left", style="cyan", no_wrap=True)
    
    if show_space:
        table.add_column("Space", justify="left", style="green", no_wrap=True)
    
    projects = list_projects()
    if not projects:
        console = Console()
        console.print("[yellow]No projects found[/yellow]")
        return
        
    for p in projects:
        if show_space:
            space = get_project_space(p)
            space_display = space if space else "-"
            table.add_row(f"☑️  {p}", space_display)
        else:
            table.add_row(f"☑️  {p}")

    console = Console()
    console.print(table)


def print_list_spaces():
    """
    Print list of spaces.

    :return:
    """
    table = Table(title="🌌 Space List", title_style="bold magenta", show_lines=True)
    table.add_column("SpaceName", justify="left", style="green", no_wrap=True)
    table.add_column("Projects", justify="left", style="cyan", no_wrap=True)
    table.add_column("Description", justify="left", style="yellow", no_wrap=True)
    
    spaces = list_spaces()
    if not spaces:
        console = Console()
        console.print("[yellow]🔍 No spaces found. Create one with 'thothctl init space'[/yellow]")
        return
    
    # Get space descriptions if available
    space_details = get_space_details()
        
    for space in spaces:
        projects = get_projects_in_space(space)
        project_count = len(projects)
        project_display = f"{project_count} project{'s' if project_count != 1 else ''}"
        
        # Get description if available
        description = "No description"
        if space in space_details and "description" in space_details[space]:
            description = space_details[space]["description"]
        
        table.add_row(
            f"🌐 {space}", 
            f"{project_count} projects",
            f"{description}"
        )

    console = Console()
    console.print(table)
