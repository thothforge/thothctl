"""Clean up space and optionally its associated projects."""
import inquirer
import os
from pathlib import Path
from colorama import Fore

from ....common.common import dump_iac_conf, load_iac_conf
from .clean_project import remove_projects


def get_projects_in_space(space_name: str):
    """
    Get all projects that belong to the specified space.
    
    :param space_name: Name of the space
    :return: List of project names in the space
    """
    config_path = Path.joinpath(Path.home(), ".thothcf")
    conf = load_iac_conf(directory=config_path)
    
    projects_in_space = []
    
    for project_name, project_data in conf.items():
        # Skip non-project entries
        if not isinstance(project_data, dict):
            continue
            
        # Check if project has thothcf section with space info
        if "thothcf" in project_data and "space" in project_data["thothcf"]:
            if project_data["thothcf"]["space"] == space_name:
                projects_in_space.append(project_name)
    
    return projects_in_space


def remove_space(space_name: str, remove_projects: bool = False):
    """
    Remove a space and optionally its associated projects.
    
    :param space_name: Name of the space to remove
    :param remove_projects: Whether to remove projects in the space
    :return: None
    """
    config_path = Path.joinpath(Path.home(), ".thothcf")
    conf = load_iac_conf(directory=config_path)
    
    # Find projects in this space
    projects_in_space = get_projects_in_space(space_name)
    
    if not projects_in_space:
        print(f"{Fore.YELLOW}No projects found in space '{space_name}'{Fore.RESET}")
        return
    
    # Confirm space removal
    choices = ["yes", "no"]
    questions = [
        inquirer.List(
            "delete",
            message=f"{Fore.CYAN}⚠️ Are you sure you want to remove space '{space_name}'? ({len(projects_in_space)} projects found)",
            choices=choices,
        )
    ]
    
    answers = inquirer.prompt(questions)
    if answers["delete"] != "yes":
        print(f"{Fore.GREEN}Space removal cancelled.{Fore.RESET}")
        return
    
    # Handle projects in the space
    if remove_projects:
        print(f"{Fore.YELLOW}Removing all projects in space '{space_name}'...{Fore.RESET}")
        for project_name in projects_in_space:
            remove_projects(project_name)
    else:
        # Update projects to remove space association
        print(f"{Fore.YELLOW}Removing space association from projects...{Fore.RESET}")
        for project_name in projects_in_space:
            if project_name in conf and "thothcf" in conf[project_name]:
                if "space" in conf[project_name]["thothcf"]:
                    del conf[project_name]["thothcf"]["space"]
                    print(f"{Fore.GREEN}Removed space association from project '{project_name}'{Fore.RESET}")
    
    # Remove space directory if it exists
    space_dir = config_path.joinpath("spaces", space_name)
    if os.path.exists(space_dir):
        try:
            import shutil
            shutil.rmtree(space_dir)
            print(f"{Fore.GREEN}Removed space directory: {space_dir}{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error removing space directory: {e}{Fore.RESET}")
    
    # Save updated configuration
    dump_iac_conf(content=conf)
    print(f"{Fore.GREEN}Space '{space_name}' has been removed.{Fore.RESET}")
