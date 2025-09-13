"""Set project Parameters."""
import logging
import re
from pathlib import Path, PurePath
from typing import Optional

import inquirer
import os.path
import toml
import yaml
from colorama import Fore
from git import Repo

from ....common.common import load_iac_conf
from .get_project_data import (
    check_project_properties,
    check_template_properties,
    get_exist_project_props,
    get_project_props,
)
from .project_defaults import (
    g_catalog_spec,
    g_catalog_tags,
    g_project_properties_parse,
)


def inv_parse_project(
    project_properties: dict, file_name: PurePath, project_properties_parse: dict = None
):
    """
    Parse project properties.

    :param project_properties:
    :param file_name:
    :param project_properties_parse:
    :return:
    """
    # creating a variable and storing the text that we want to search
    if project_properties != {}:
        if project_properties_parse is None:
            project_properties_parse = g_project_properties_parse
        for prop in project_properties_parse.keys():
            replace = f'"{project_properties_parse[prop]}"'
            search = f'"{project_properties.get(prop, None)}"'

            if search != "None":
                # Opening our text file in read only
                # mode using the open() function
                with open(file_name, "r") as file:
                    # Reading the content of the file
                    # using the read() function and storing
                    # them in a new variable
                    data = file.read()

                    # Searching and replacing the text
                    # using the replace() function
                    data = data.replace(search, replace)

                with open(file_name, "w") as file:
                    file.write(data)

                # Printing Text replaced
                logging.info(
                    f"{Fore.MAGENTA}Text {search} replaced in {file_name} by {replace} {Fore.RESET}"
                )
    else:
        print(f"{Fore.RED}No project properties found. {Fore.RESET} ")


def set_project_id():
    """
    Set project id.

    :return:
    """
    try:
        questions = [
            inquirer.Text(
                name="project_id",
                message="Write Project id: ",
                validate=lambda _, x: re.match(pattern="^[a-zA-Z_]+$", string=x),
            ),
        ]
        answer = inquirer.prompt(questions)
        project_id = answer["project_id"]
        return project_id
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid string. {Fore.RESET}")


def create_project_conf(
    project_properties: dict = None,
    template_input_parameters: dict = None,
    directory: PurePath = None,
    repo_metadata: dict = None,
    project_name: str = None,
    space: Optional[str] = None,
    project_type: str = "terraform",
):
    """
    Create project configuration file.

    :param project_name:
    :param project_properties:
    :param template_input_parameters:
    :param directory:
    :param repo_metadata:
    :param space: Space name for the project
    :param project_type: Type of project (terraform, terragrunt, etc.)
    :return:
    """
    file_path = os.path.join(directory, ".thothcf.toml")
    if project_name is None:
        project_name = set_project_id()

    # Read existing content if file exists (from template)
    existing_config = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as file:
                existing_config = toml.load(file)
        except Exception as e:
            logging.warning(f"Could not parse existing .thothcf.toml: {e}")

    # Create new configuration structure
    new_config = {}
    
    # Add project_properties section first
    if project_properties:
        new_config["project_properties"] = project_properties
    
    # Add or update thothcf section
    thothcf_section = existing_config.get("thothcf", {})
    thothcf_section["project_id"] = project_name  # Always update project_id
    thothcf_section["project_type"] = project_type
    if space:
        thothcf_section["space"] = space
    new_config["thothcf"] = thothcf_section
    
    # Add template_input_parameters section
    if template_input_parameters:
        new_config["template_input_parameters"] = template_input_parameters
    elif "template_input_parameters" in existing_config:
        # Keep existing template parameters if no new ones provided
        new_config["template_input_parameters"] = existing_config["template_input_parameters"]
    
    # Add metadata if provided
    if repo_metadata:
        new_config["origin_metadata"] = repo_metadata
    elif "origin_metadata" in existing_config:
        new_config["origin_metadata"] = existing_config["origin_metadata"]

    # Write the complete configuration
    with open(file_path, "w") as file:
        toml.dump(new_config, file)

    # Create catalog info
    create_catalog_info(
        directory=PurePath.joinpath(directory, "docs/catalog/"),
        project_properties=project_properties,
        project_name=project_name,
        space=space,
    )


def set_project_conf(
    project_properties: dict = None,
    project_name: str = None,
    template_input_parameters: dict = None,
    directory=PurePath("."),
    repo_metadata: dict = None,
    space: Optional[str] = None,
    batch_mode: bool = False,
    project_type: str = "terraform",
):
    """
    Set project configuration.

    :param project_properties:
    :param project_name:
    :param template_input_parameters:
    :param directory:
    :param repo_metadata:
    :param space: Space name for the project
    :param batch_mode: Run in batch mode with minimal prompts
    :param project_type: Type of project (terraform, terragrunt, etc.)
    :return:
    """
    # If directory is not provided or is current directory, use project_name as directory
    if directory == PurePath(".") and project_name:
        directory = PurePath(project_name)
    
    if project_properties is None:
        project_properties = get_project_props(project_name=project_name, batch_mode=batch_mode)
    
    if template_input_parameters is None and check_template_properties(directory=directory):
        # Automatically create template parameters from project properties
        template_input_parameters = {}
        
        # Use all collected project properties to create template parameters
        for key in project_properties:
            template_input_parameters[key] = f"#{{{key}}}#"
            
        print(f"{Fore.GREEN}✅ Automatically created template parameters from project properties{Fore.RESET}")
        
        # Display the template parameters
        print(f"{Fore.CYAN}Template parameters:{Fore.RESET}")
        for key, value in template_input_parameters.items():
            print(f"  • {key}: {value}")

    # Create project configuration
    create_project_conf(
        project_properties=project_properties,
        template_input_parameters=template_input_parameters,
        directory=directory,
        repo_metadata=repo_metadata,
        project_name=project_name,
        space=space,
        project_type=project_type,
    )
    
    # Execute template replacement logic to replace placeholders in files
    from .get_project_data import replace_template_placeholders
    replace_template_placeholders(
        directory=directory,
        project_properties=project_properties,
        project_name=project_name
    )


def set_meta_data(repo_metadata: dict = None, file_path: str = None):
    """
    Set metadata for project reused.

    :param repo_metadata:
    :param file_path:
    :return:
    """
    if repo_metadata is not None:
        if os.path.exists(file_path):
            mode = "a"

        else:
            mode = "w"

        with open(file_path, mode) as file:
            logging.info(f"{Fore.GREEN} Opening {file} ... {Fore.RESET}")
            meta = {"origin_metadata": repo_metadata}
            file.write("\n\n")
            toml.dump(meta, file)


# create catalog-info.yaml file and replace the current file


# create catalog-info.yaml file and replace the current file
def create_catalog_info(
    az_project_name: str = None,
    directory: PurePath = None,
    project_name: str = None,
    project_properties: dict = None,
    git_repo_url: str = None,
    netsted: bool = False,
    space: Optional[str] = None,
):
    """
    Create catalog info.

    :param az_project_name:
    :param directory:
    :param project_name:
    :param project_properties:
    :param git_repo_url:
    :param netsted:
    :param space: Space name for the project
    :return:
    """
    if project_name is None:
        project_name = "project"

    if project_properties is None:
        project_properties = {}

    if not os.path.exists(directory):
        os.makedirs(directory)

    file_path = os.path.join(directory, "catalog-info.yaml")
    catalog_info = {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {
            "name": project_name,
            "description": f"IaC project for {project_name}",
            "annotations": {
                "backstage.io/techdocs-ref": "dir:.",
                "github.com/project-slug": f"{project_name}",
            },
            "tags": g_catalog_tags,
        },
        "spec": g_catalog_spec,
    }
    
    # Add space to metadata if provided
    if space:
        catalog_info["metadata"]["space"] = space

    if project_properties != {}:
        catalog_info["metadata"]["annotations"]["project_properties"] = project_properties

    if git_repo_url is not None:
        catalog_info["metadata"]["annotations"]["github.com/project-slug"] = git_repo_url

    if az_project_name is not None:
        catalog_info["metadata"]["annotations"][
            "dev.azure.com/project-repo"
        ] = az_project_name

    with open(file_path, "w") as file:
        yaml.dump(catalog_info, file, default_flow_style=False)
        print(f"{Fore.CYAN} catalog-info.yaml file created in {file_path}. {Fore.RESET}")


def get_git_repo_url(directory: PurePath = None):
    """
    Get git repo url.

    :param directory:
    :return:
    """
    try:
        repo = Repo(directory)
        remote_url = repo.remotes.origin.url
        return remote_url
    except Exception as e:
        logging.error(f"{Fore.RED}Error getting git repo url: {e}{Fore.RESET}")
        return None
