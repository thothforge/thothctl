"""Get project Data."""
import hashlib
import logging
import re
import shutil
import sys
from pathlib import Path, PurePath

import inquirer
import os
from colorama import Fore

from ....common.common import load_iac_conf, update_info_project
from .project_defaults import g_project_properties_parse


def check_project_properties(directory) -> bool:
    """
    Check if project_properties exists.

    :param directory:
    :return:
    """
    config = load_iac_conf(directory=directory)
    if config.get("project_properties", "Null") == "Null":
        return True
    else:
        return False


def check_template_properties(directory) -> bool:
    """
    Check if template_input_parameters exists.

    :param directory:
    :return:
    """
    config = load_iac_conf(directory=directory)
    if config.get("template_input_parameters", "Null") == "Null":
        return True
    else:
        return False


# get project props


# get project props
def get_exist_project_props(
    directory=PurePath("."), key: str = "project_properties"
) -> dict:
    """
    Get exist project properties.

    :param key:
    :param directory:
    :return:
    """
    project_properties = {}
    if not check_project_properties(directory=directory):
        project_properties = load_iac_conf(directory=directory).get(key, {})
    return project_properties


def get_project_props(
    project_name: str = None,
    remote_bkd_cloud_provider: str = "aws",
    cloud_provider: str = "aws",
    directory=PurePath("."),
) -> dict:
    """
    Get project properties.

    :param project_name:
    :param remote_bkd_cloud_provider:
    :param cloud_provider:
    :param directory:
    :return:
    """
    print(Fore.GREEN)
    project_properties = {}

    input_parameters = load_iac_conf(directory=directory).get(
        "template_input_parameters", {}
    )
    if input_parameters == {}:
        try:
            questions = [
                inquirer.Text(
                    "project",
                    message="Project name",
                    # validate if contains spaces and simbols
                    validate=lambda _, x: re.match(r"^[a-z0-9-_]+$", x),
                ),
                inquirer.Text(
                    "environment",
                    message="Default environment for example (dev, qa, prod) ",
                    # validate if contains spaces and simbols
                    validate=lambda _, x: re.match(
                        r"^(dev|qa|prod|prd|stg|sandbox|[a-z0-9]+)$", x
                    ),
                    default="dev",
                ),
                inquirer.Text(
                    "owner",
                    message="Team or user owner for your IaC project ",
                ),
                inquirer.Text(
                    "client",
                    message="Client or organization name for IaC project  ",
                ),
            ]

            answers = inquirer.prompt(questions)
            project_properties["project"] = answers["project"]

            project_properties["environment"] = answers["environment"]

            project_properties["owner"] = answers["owner"]

            project_properties["client"] = answers["client"]

            if remote_bkd_cloud_provider == "aws":
                questions_2 = [
                    inquirer.Text(
                        "backend_region",
                        message="Backend Region for remote state (us-east-2) ",
                        validate=lambda _, x: re.match(r"^[a-z]{2}-[a-z]+-\d$", x),
                        default="us-east-2",
                    ),
                    inquirer.Text(
                        "dynamodb_backend",
                        message="Dynamodb table name for lock state (db-terraform-lock) ",
                        default="db-terraform-lock",
                    ),
                    inquirer.Text(
                        "backend_bucket",
                        message="Bucket name for tfstate ",
                        validate=lambda _, x: re.match(
                            r"^[a-z0-9][a-z0-9-.]{1,61}[a-z0-9]$", x
                        ),
                    ),
                ]
                answers = inquirer.prompt(questions_2)
                project_properties["backend_region"] = answers["backend_region"]
                project_properties["dynamodb_backend"] = answers["dynamodb_backend"]
                project_properties["backend_bucket"] = answers["backend_bucket"]

            if cloud_provider == "aws":
                questions = [
                    inquirer.Text(
                        "region",
                        message="AWS Region for deployment, for example us-east-2",
                        validate=lambda _, x: re.match(r"^[a-z]{2}-[a-z]+-\d$", x),
                    ),
                ]
                answers = inquirer.prompt(questions)
                project_properties["region"] = answers["region"]

            print(
                f"{Fore.MAGENTA}✅ The project properties: {project_properties} {Fore.RESET}"
            )

        except ValueError:
            print(
                f"{Fore.RED}❌ Invalid input. Please enter a valid string. {Fore.RESET}"
            )
        except KeyboardInterrupt:
            print(f"{Fore.RED}❌ KeyboardInterrupt {Fore.RESET}")
            shutil.rmtree(directory)
            sys.exit(1)
    else:
        project_properties = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties=project_properties,
            project_name=project_name,
        )

    return project_properties


def get_simple_project_props(
    input_parameters: dict, project_properties: dict, project_name: str
) -> dict:
    """
    Get project properties.

    :param input_parameters:
    :param project_properties:
    :param project_name:
    :return:
    """
    print(f"{Fore.GREEN} Write project parameters for {project_name}")
    for k in input_parameters.keys():
        try:
            questions = [
                inquirer.Text(
                    name=k,
                    message=f'Input {input_parameters[k]["description"]} ',
                    validate=lambda _, x: re.match(
                        pattern=input_parameters[k]["condition"], string=x
                    ),
                    default=input_parameters[k].get("default", None),
                ),
            ]
            answer = inquirer.prompt(questions)
            project_properties[k] = answer[k]
        except ValueError:
            print(
                f"{Fore.RED}❌ Invalid input. Please enter a valid string. {Fore.RESET}"
            )
    return project_properties


# def check project props based on regex


def check_project_props(project_properties: dict, prop: str) -> bool:
    """
    Check project properties.

    :param prop:
    :param project_properties:
    :return:
    """
    for k in project_properties.keys():
        r = project_properties[k]["condition"]
        if re.match(pattern=r, string=prop):
            return True
        else:
            print(
                f"{Fore.RED}❌ Invalid input. Please enter a valid string according to {project_properties[k]['condition']}. {Fore.RESET}"
            )


def get_template_props() -> dict:
    """
    Get template repositories.

    :return:
    """

    template_input_parameters = {}
    x = "yes"
    while x != "no":
        try:
            key = (str(input("Input key:  "))).lower().replace(" ", "")

            value = (str(input(f"Input value for {key}: "))).lower().replace(" ", "")

            template_input_parameters[key] = value
            x = str(
                input(
                    f"{Fore.MAGENTA} Continue with template parameters  (yes/no):  {Fore.RESET}"
                )
            )

        except ValueError:
            print(
                f"{Fore.RED}❌ Invalid input. Please enter a valid string. {Fore.RESET}"
            )
    return template_input_parameters


def parse_project(
    project_properties: dict,
    project_properties_parse: dict = None,
    file_name: PurePath = None,
    project_conf_name: str = None,
    parser_type: str = "normal",
):
    """
    Parse project properties.

    :param project_conf_name:
    :param project_properties:
    :param project_properties_parse:
    :param file_name:
    :param parser_type: replace type , normal or invert
    :return:
    """
    change = False
    if project_properties_parse is None:
        project_properties_parse = g_project_properties_parse

    if parser_type == "invert":
        copy_files_info_project(project_name=project_conf_name)
    else:
        for prop in project_properties_parse["template_input_parameters"].keys():
            # creating a variable and storing the text that we want to search
            replace = project_properties.get(prop, None)
            search = project_properties_parse["template_input_parameters"][prop][
                "template_value"
            ]

            if replace is not None:
                # Opening our text file in read only
                # mode using the open() function
                with open(file_name, "r") as file:
                    # Reading the content of the file
                    # using the read() function and storing
                    # them in a new variable
                    data = file.read()
                    if search in data and change == False:
                        create_tmp_file(
                            file_name=file_name, project_name=project_conf_name
                        )
                        change = True
                    # Searching and replacing the text
                    # using the replace() function
                    data = data.replace(search, replace)

                with open(file_name, "w") as file:
                    file.write(data)

                # Printing Text replaced
                logging.debug(f"Text {search} replaced in {file_name} by {replace}")
                # verify if search is in data and copy the file


# create a copy of file to a tmp path home .thothcf folder
def create_tmp_file(file_name: PurePath = None, project_name: str = None) -> PurePath:
    """
    Create tmp file.

    :param file_name:
    :param project_name:
    :return:
    """
    # TODO create hash for file and add to entry to check if template changed or not after create check file hash

    if not os.path.exists(PurePath(f"{Path.home()}/.thothcf/{project_name}")):
        os.makedirs(PurePath(f"{Path.home()}/.thothcf/{project_name}"))
        logging.debug(
            f"Folder {PurePath(f'{Path.home()}/.thothcf/{project_name}')} created"
        )

    tmp_path = PurePath(
        f"{Path.home()}/.thothcf/{project_name}/{file_name.parent.as_posix()}"
    )
    os.makedirs(tmp_path, exist_ok=True)

    tmp_file = PurePath(f"{tmp_path}/{file_name.name}")

    if not os.path.exists(
        PurePath(f"{Path.home()}/.thothcf/{project_name}/")
    ) or not os.path.exists(tmp_file):
        print(f"{Fore.CYAN}👷 Modifying {file_name.name} for {project_name}")

        # todo check copy many times and entries in thothcf
        shutil.copy(file_name, tmp_file)
        update_info_project(file_path=Path(file_name), project_name=project_name)
    elif not check_hash_file(file_path=tmp_file, file_path_2=file_name) and (
        os.path.exists(PurePath(f"{Path.home()}/.thothcf/{project_name}/"))
        and os.path.exists(tmp_file)
    ):
        print(f"{Fore.CYAN}👷 Modifying {file_name.name} for {project_name}")
        os.remove(tmp_file)
        shutil.copy(file_name, tmp_file)
        update_info_project(file_path=Path(file_name), project_name=project_name)
    return tmp_file


def check_hash_file(file_path: PurePath = None, file_path_2: PurePath = None):
    """
    Check hash file.

    :param file_path_2:
    :param file_path:
    :return:
    """
    if file_path is not None and file_path_2 is not None:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        with open(file_path_2, "rb") as f:
            file_hash_2 = hashlib.sha256(f.read()).hexdigest()
        if file_hash == file_hash_2:
            return True
        else:
            return False
    else:
        return False


# copy home file in .thothcf folder to the specific project location  based on path
# and replace if exists
def copy_home_file(
    file_name: PurePath = None, directory: PurePath = None, project_name: str = None
):
    """
    Copy home file.

    :param project_name:
    :param file_name:
    :param directory:
    :return:
    """
    print(Fore.GREEN + f"Restoring file {file_name}" + Fore.RESET)
    tmp_file = PurePath(
        f"{Path.home()}/.thothcf/{project_name}/{directory}/{PurePath(file_name).name}"
    )
    if not os.path.exists(
        PurePath(f"{Path.home()}/.thothcf/{project_name}")
    ) or not os.path.exists(tmp_file):
        shutil.copy(file_name, tmp_file)
    if os.path.exists(file_name):
        os.remove(directory / file_name)
    shutil.copy(tmp_file, directory / file_name)


# copy all files in the array of dictionaries in .thothcf.toml at home
def copy_files_info_project(project_name: str):
    """
    Copy all files in the array of dictionaries in .thothcf.toml at home.

    :param project_name:

    :return:
    """

    config = load_iac_conf(directory=f"{Path.home()}/.thothcf/")

    if project_name in config:
        for file in config[project_name]["template_files"]:
            logging.debug(f"Copying {file['local']} to {file['source']}")
            copy_home_file(
                file_name=file["local"],
                directory=PurePath(file["source"]),
                project_name=project_name,
            )


def get_project_properties_parse(
    directory: PurePath = None,
    project_properties: dict = None,
) -> dict:
    """
    Get project properties parse.

    :param project_properties:
    :param directory:
    :return:
    """
    project_properties_parse = {}
    if directory is not None:
        project_properties_parse = load_iac_conf(directory=directory)
        project_properties = project_properties_parse.get(
            "project_properties", project_properties
        )
        logging.debug(project_properties_parse)
    return {
        "project_properties_parse": project_properties_parse,
        "project_properties": project_properties,
    }


def walk_folder_replace(
    directory,
    project_name: str,
    project_properties: dict = None,
    action="make_project",
):
    """
    Walk folder and replace keywords.

    :param project_name:
    :param directory:
    :param project_properties:
    :param action:
    :return:
    """

    project_properties_ = get_project_properties_parse(
        directory=directory,
        project_properties=project_properties,
    )

    project_properties_parse = project_properties_.get("project_properties_parse")
    project_properties = project_properties_.get("project_properties")

    if project_properties_parse != {} and action != "make_template":
        allowed_extensions = {
            "png",
            "svg",
            "xml",
            "toml",
            ".thothcf.toml",
            "drawio",
            "gitignore",
            ".terraform.lock.hcl",
            "catalog-info.yaml",
            "mkdocs.yaml",
            "pdf",
            "dot",
            "gif",
        }
        not_allowed_folders = {
            ".git",
            ".terraform",
            ".terragrunt-cache",
            "cdk.out",
            "catalog",
            "__pycache__",
        }

        print(f"{Fore.LIGHTBLUE_EX}👷 Parsing template ... {Fore.RESET}")
        for dirpath, dirnames, filenames in os.walk(directory):
            if not (any(x in dirpath for x in not_allowed_folders)):
                logging.debug(f"dirpath: {dirpath}, dirnames, filenames)")

                for f in filenames:
                    if (
                        f.split(".")[-1] not in allowed_extensions
                        and f not in allowed_extensions
                    ):
                        make_template_or_project(
                            directory=dirpath,
                            project_properties=project_properties,
                            project_properties_parse=project_properties_parse,
                            project_conf_name=project_name,
                            action=action,
                            file=f,
                        )

    elif action == "make_template":
        parse_project(
            project_properties=project_properties,
            project_properties_parse=project_properties_parse,
            parser_type="invert",
            project_conf_name=project_name,
        )
        # TODO unify make project and template for all kind of projects
    else:
        print(f"{Fore.RED}No project Config founds {Fore.RESET} ")

    print(f"✅{Fore.CYAN} Done! {Fore.RESET}")


def make_template_or_project(
    directory: PurePath = None,
    project_properties: dict = None,
    project_properties_parse: dict = None,
    project_type: str = "terraform",
    action: str = "make_project",
    project_conf_name: str = None,
    file: str = None,
):
    """
    Make template or project.

    :param project_conf_name:
    :param file:
    :param project_properties_parse:
    :param directory:
    :param project_properties:
    :param action:
    :param project_type:
    :return:
    """
    if project_type == "cdkv2":
        file = "project_configs/environment_options/environment_options.yml"

        project_properties_parse = get_project_properties_parse(
            directory=directory,
            project_properties=project_properties,
        )["project_properties_parse"]
        project_properties = get_exist_project_props(directory=directory)

    if (
        action == "make_project"
        # and project_properties is not None
        # and project_properties != {}
    ):
        file_path = PurePath(os.path.join(directory, file))
        logging.debug(f"The file to parser {file_path}")

        parse_project(
            project_properties=project_properties,
            file_name=file_path,
            project_properties_parse=project_properties_parse,
            project_conf_name=project_conf_name,
        )

    elif action == "make_template":
        file_path = PurePath(os.path.join(directory, file))
        logging.debug(f"The file to parser {file_path}")

        parse_project(
            project_properties=project_properties,
            file_name=file_path,
            project_properties_parse=project_properties_parse,
            parser_type="invert",
            project_conf_name=project_conf_name,
        )
