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
    get_template_props,
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
):
    """
    Create project configuration file.

    :param project_name:
    :param project_properties:
    :param template_input_parameters:
    :param directory:
    :param repo_metadata:
    :param space: Space name for the project
    :return:
    """
    file_path = os.path.join(directory, ".thothcf.toml")
    properties = {}
    if project_name is None:
        project_name = set_project_id()

    if not check_project_properties(directory="."):
        properties = load_iac_conf(directory=directory)
        properties.pop("project_properties")
        properties.pop("thothcf")

    if os.path.exists(file_path):
        mode = "a"
        if properties != {}:
            with open(file_path, "w") as file:
                toml.dump(properties, file)
    else:
        mode = "w"

    with open(file_path, mode) as file:
        logging.debug(f"{Fore.GREEN} Opening {file} ... {Fore.RESET}")
        properties = {"project_properties": project_properties}
        file.write("\n\n")
        toml.dump(properties, file)
        
        # Add space to thothcf configuration if provided
        thothcf_config = {"project_id": project_name}
        if space:
            thothcf_config["space"] = space
        
        toml.dump({"thothcf": thothcf_config}, file)

        if mode == "w" and template_input_parameters is None:
            template_input_parameters = {
                "template_input_parameters": g_project_properties_parse
            }
            toml.dump(template_input_parameters, file)

        elif mode == "w" and template_input_parameters is not None:
            template_input_parameters = {
                "template_input_parameters": template_input_parameters
            }
            toml.dump(template_input_parameters, file)
        set_meta_data(repo_metadata=repo_metadata, file_path=file_path)

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
):
    """
    Set project configuration.

    :param project_properties:
    :param project_name:
    :param template_input_parameters:
    :param directory:
    :param repo_metadata:
    :param space: Space name for the project
    :return:
    """
    if project_properties is None:
        project_properties = get_project_props(project_name=project_name)
    if template_input_parameters is None and check_template_properties(
        directory=directory
    ):
        template_input_parameters = get_template_props()

    create_project_conf(
        project_properties=project_properties,
        template_input_parameters=template_input_parameters,
        directory=directory,
        repo_metadata=repo_metadata,
        project_name=project_name,
        space=space,
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
    :param netsted:
    :param git_repo_url:
    :param project_properties:
    :param project_name:
    :param directory:
    :param space: Space name for the project
    :return:
    """
    if git_repo_url is None:
        git_repo_url = f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX{project_name}"
    if netsted:
        # Get relative path for specific directory
        relative_path = get_relative_path_from_git_root()
        git_repo_url = f"{git_repo_url}/{relative_path}"
        print(git_repo_url)
    if project_properties is None:
        project_properties = get_exist_project_props(directory=PurePath("."))

    idp_properties = get_exist_project_props(
        directory=PurePath("."),
        key="idp",
    )

    if project_properties is not None:
        catalog_info = {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Resource",
            "metadata": {
                "name": f"{project_name}",
                "description": f"{project_properties.get('description', '')}",
                "links": [
                    {
                        "url": git_repo_url,
                        "title": "Source Code",
                        "icon": "GitHub",
                    }
                ],
                "annotations": {
                    "backstage.io/techdocs-ref": "dir:.",
                    "dev.azure.com/project-repo": f"{az_project_name}/{project_name}",
                },
                "tags": idp_properties.get("tags", g_catalog_tags),
            },
            "spec": idp_properties.get("spec", g_catalog_spec),
        }
        
        # Add space to catalog info if provided
        if space:
            catalog_info["metadata"]["space"] = space
            
        # Create all necessary directories in the path
        path_catalog = f"{directory}/"
        os.makedirs(path_catalog, exist_ok=True)
        path_catalog = f"{path_catalog}/catalog-info.yaml"

        try:
            with open(path_catalog, "w") as file:
                yaml.dump(catalog_info, file, default_flow_style=False)
                print(
                    f"{Fore.CYAN} catalog-info.yaml file created in {path_catalog}. {Fore.RESET}"
                )
        except:
            logging.warning("catalog-info.yaml file not found")
            print(
                f"{Fore.YELLOW}  No such file or directory: {path_catalog} {Fore.RESET}"
            )


def get_git_metadata_repo_url(
    directory: PurePath = None, remote_name: str = "origin"
) -> str:
    """
    Get git metadata repo url.

    Args:
        directory (PurePath): Path to the git repository directory. If None, uses current directory.
        remote_name (str): Name of the remote to get URL from. Defaults to 'origin'.

    Returns:
        str: The remote repository URL
    """
    try:
        repo_path = directory if directory else "."
        repo = Repo(repo_path, search_parent_directories=True)

        # Get the specified remote
        remote = repo.remotes[remote_name]
        return remote.url
    except Exception as e:
        print(f"Error getting git remote URL: {str(e)}")
        return ""


def get_relative_path_from_git_root(file_path: PurePath = None) -> str:
    """
    Get the relative path from git root directory to the specified path.
    If no path is specified, uses current working directory.

    Args:
        file_path (PurePath): Path to get relative path for. If None, uses current directory.

    Returns:
        str: Relative path from git root to the specified path
    """
    try:
        # If no path specified, use current directory
        path_to_check = file_path if file_path else Path.cwd()

        # Initialize repo and get git root directory
        repo = Repo(path_to_check, search_parent_directories=True)
        git_root = Path(repo.git.rev_parse("--show-toplevel"))

        # Get relative path
        relative_path = str(Path(path_to_check).relative_to(git_root))

        return relative_path
    except Exception as e:
        print(f"Error getting relative path: {str(e)}")
        return ""


def create_idp_doc_main(
    directory_code: Path,
    project_name: str,
    az_project_name: str,
    directory_docs_file: PurePath = PurePath("docs/catalog"),
    nested: bool = False,
    space: Optional[str] = None,
):
    """
    Create idp doc main.

    :param az_project_name:
    :param nested:
    :param project_name:
    :param directory_docs_file:
    :param directory_code:
    :param space: Space name for the project
    :return:
    """

    remote_url = get_git_metadata_repo_url(directory=directory_code)

    create_catalog_info(
        directory=directory_docs_file,
        project_name=project_name,
        git_repo_url=remote_url,
        netsted=nested,
        az_project_name=az_project_name,
        space=space,
    )
