"""Create Component based on attributes and types."""
import logging
from pathlib import Path

import os
from colorama import Fore

from ....common.common import load_iac_conf
from .files_content import (
    main_tf_content,
    parameters_tf_content,
    terragrunt_hcl_resource_content,
)


dirname = os.path.dirname(__file__)


def get_folders_names(folders_structure):
    """
    Get folder names.

    :param folders_structure:
    :return:
    """
    names = []
    for f in folders_structure:
        names.append(f["name"])
    logging.info(f"Available component types {names}")
    return names


def get_folder_structure(folders_structure, folder_name):
    """
    Get folder structure.

    :param folders_structure:
    :param folder_name:
    :return:
    """
    for f in folders_structure:
        if f["name"] == folder_name:
            return f["content"]


def create_component(
    code_directory: str = ".",
    component_path: str = ".",
    component_type: str = None,
    component_name: str = None,
    project_file_structure=".thothcf_project.toml",
):
    """
    Create Component based on attributes.

    :param project_file_structure:
    :param code_directory:
    :param component_path:
    :param component_type:
    :param component_name:
    :return:
    """
    if component_type is not None:
        print(
            f"{Fore.LIGHTBLUE_EX}👷 Creating {component_type} {component_name} in {component_path}{Fore.RESET}"
        )
        logging.info(f"Creating {component_type} {component_name} in {component_path}")

        confs = load_iac_conf(directory=code_directory)
        if confs == {}:
            print(f"{Fore.LIGHTBLUE_EX} Using default project structure {Fore.RESET}")
            tmp_project_structure = load_iac_conf(
                os.path.join(dirname, "../common/"), file_name=project_file_structure
            )["project_structure"]

        else:
            tmp_project_structure = confs["project_structure"]

            print(f"{Fore.LIGHTBLUE_EX} Using custom project structure {Fore.RESET}")

        if "folders" in tmp_project_structure.keys():
            folders_structure = tmp_project_structure.get("folders")
            if component_type in get_folders_names(folders_structure):
                local_module_structure = get_folder_structure(
                    folders_structure=folders_structure, folder_name=component_type
                )

                logging.info(f"The module structure is: {local_module_structure}")
                print(
                    f"{Fore.LIGHTBLUE_EX} The {component_type} structure is: {local_module_structure}{Fore.RESET}"
                )

                create_folder(directory=component_path, folder_name=component_name)
                for f in local_module_structure:
                    create_file(
                        directory=component_path,
                        folder_name=component_name,
                        file_name=f,
                    )


def create_folder(directory, folder_name):
    """
    Create Folder.

    :param directory:
    :param folder_name:
    :return:
    """
    path = Path(os.path.join(directory, folder_name)).resolve().absolute()
    try:
        os.makedirs(path)
    except Exception as e:
        logging.exception(f"The folder {path} could be created")
        raise e


def create_file(directory, folder_name, file_name):
    """
    Create file.

    :param directory:
    :param folder_name:
    :param file_name:
    :return:
    """
    path = Path(os.path.join(directory, folder_name, file_name)).resolve().absolute()
    with open(path, "w") as fp:
        if file_name == "parameters.tf":
            fp.write(f"#{folder_name}-{file_name}")
            fp.write(parameters_tf_content)
        elif file_name == "terragrunt.hcl":
            fp.write(f"#{folder_name}-{file_name}")
            fp.write(terragrunt_hcl_resource_content)
        elif file_name == "main.tf":
            fp.write(main_tf_content.replace("#{resource_name}#", folder_name))
