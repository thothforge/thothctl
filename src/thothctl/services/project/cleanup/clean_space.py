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
    import toml
    
    config_path = Path.joinpath(Path.home(), ".thothcf")
    spaces_config_path = config_path.joinpath("spaces.toml")
    
    # Load main config for projects
    conf = load_iac_conf(directory=config_path)
    
    # Load spaces config
    spaces_config = {}
    if os.path.exists(spaces_config_path):
        with open(spaces_config_path, mode="rt", encoding="utf-8") as fp:
            spaces_config = toml.load(fp)
    
    # Find projects in this space
    projects_in_space = get_projects_in_space(space_name)
    
    # Check if space exists by looking for its directory
    space_dir = config_path.joinpath("spaces", space_name)
    space_exists = os.path.exists(space_dir)
    
    # Check if space exists in spaces configuration
    space_in_config = "spaces" in spaces_config and space_name in spaces_config["spaces"]
    
    if not space_exists and not projects_in_space and not space_in_config:
        print(f"{Fore.RED}Space '{space_name}' not found.{Fore.RESET}")
        return
    
    # Confirm space removal
    choices = ["yes", "no"]
    message = f"{Fore.CYAN}⚠️ Are you sure you want to remove space '{space_name}'?"
    if projects_in_space:
        message += f" ({len(projects_in_space)} projects found)"
    
    questions = [
        inquirer.List(
            "delete",
            message=message,
            choices=choices,
        )
    ]
    
    answers = inquirer.prompt(questions)
    if answers["delete"] != "yes":
        print(f"{Fore.GREEN}Space removal cancelled.{Fore.RESET}")
        return
    
    # Handle projects in the space
    if projects_in_space:
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
    else:
        print(f"{Fore.YELLOW}No projects found in space '{space_name}'{Fore.RESET}")
    
    # Always remove space directory if it exists
    if space_exists:
        try:
            import shutil
            shutil.rmtree(space_dir)
            print(f"{Fore.GREEN}Removed space directory: {space_dir}{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error removing space directory: {e}{Fore.RESET}")
    
    # Remove the space entry from the spaces configuration file
    if "spaces" in spaces_config and space_name in spaces_config["spaces"]:
        del spaces_config["spaces"][space_name]
        print(f"{Fore.GREEN}Removed space '{space_name}' from spaces configuration.{Fore.RESET}")
        
        # Save updated spaces configuration
        with open(spaces_config_path, mode="wt", encoding="utf-8") as fp:
            toml.dump(spaces_config, fp)
    
    # Save updated main configuration (for project associations)
    dump_iac_conf(content=conf)
    print(f"{Fore.GREEN}Space '{space_name}' has been removed.{Fore.RESET}")
