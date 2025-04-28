"""Create template based in standardization Format."""
import json
import logging
import sys

import os
from colorama import Fore

from .files_content import (
    common_hcl_content,
    common_tfvars_content,
    git_ignore,
    thothcf_toml_module_content,
    main_tf_content,
    pre_commit_content,
    terragrunt_hcl_clean,
    terragrunt_hcl_content,
    terragrunt_root_hcl_content,
    tflint_hcl,
    thothcf_toml_content,
    variables_tf_content,
)
from .project_templates import terraform_module_template, terraform_template


# TODO Create project based on type / terraform module / terraform terragrunt / cdkv2 custom / ML /
def init_thothcf_content(project_type="terraform"):
    """
    Init thothcf content based in project type.

    :param project_type:
    :return:
    """

    if project_type == "terraform":
        template = thothcf_toml_content
    elif project_type == "terraform_module":
        template = thothcf_toml_module_content
    else:
        logging.error(f"Project type {project_type} not supported")
        raise ValueError(f"Project type {project_type} not supported")
    return template


def create_project(
    project_name: str, project_type="terraform", template=terraform_template
):
    """
    Create file structure for a project using terraform + terragrunt.

     :param template:
     :param project_type:
     :param project_name:
     :return:
    """
    # Parent Directory path
    parent_dir = os.getcwd()

    # Path

    path = os.path.join(parent_dir, project_name)

    # Create the directory
    # 'Nikhil'
    try:
        os.makedirs(path, exist_ok=True)
        print(
            Fore.GREEN
            + "✅️ Project folder for "
            + project_name
            + " created successfully!"
            + Fore.RESET
        )
    except OSError as error:
        print(
            Fore.RED
            + "❌ Project folder for  "
            + project_name
            + " can not be created"
            + str(error)
            + Fore.RESET
        )
        sys.exit(str(error))

    if project_type == "terraform":
        template = terraform_template
    elif project_type == "terraform_module":
        template = terraform_module_template

    create_template(template=template, parent_dir=path, project_type=project_type)


def create_common_files(file_name, path):
    """
    Create common files for project.


    :param file_name:
    :param path:
    :return:
    """
    with open(os.path.join(path, file_name), "w") as fp:
        if file_name == "variables.tf":
            fp.write(variables_tf_content)
        elif file_name == "main.tf":
            fp.write(main_tf_content)
        elif file_name == "outputs.tf":
            fp.write(f"#{file_name}")
        elif file_name == "README.md":
            fp.write(f"#{file_name}")


def create_project_files(file_name, path, project_type, cloud="aws"):
    """
    Create project files based in project type.

    :param project_type:
    :param file_name:
    :param path:
    :return:
    """
    with open(os.path.join(path, file_name), "w") as fp:
        if file_name == "terragrunt.hcl":
            fp.write(terragrunt_hcl_content)
        if file_name == "root.hcl":
            fp.write(terragrunt_root_hcl_content)
        elif file_name == "common.hcl":
            fp.write(common_hcl_content)
        elif file_name == "common.tfvars":
            fp.write(common_tfvars_content)
        elif file_name == ".tflint.hcl":
            content_tflint_hcl = tflint_hcl.replace("template", cloud)
            fp.write(content_tflint_hcl)
        elif file_name == ".gitignore":
            fp.write(git_ignore)
        elif file_name == ".pre-commit-config.yaml":
            fp.write(pre_commit_content)
        elif file_name == ".thothcf.toml":
            fp.write(init_thothcf_content(project_type=project_type))


def create_template(template, parent_dir, cloud="aws", project_type="terraform"):
    """
    Create template for clean project.

    :param project_type:
    :param cloud:
    :param template:
    :param parent_dir:
    :return:
    """

    # Create template
    path = os.path.join(parent_dir)
    for t in template:
        if t["type"] == "directory" and t["name"] != ".":
            path = os.path.join(parent_dir, t["name"])
            os.makedirs(path)
            logging.info("Directory Name  " + t["name"])
            logging.info(t["contents"])

        elif t["type"] == "file":
            file = t["name"]
            logging.info("file name " + file)
            create_common_files(file_name=file, path=path)
            create_project_files(
                file_name=file, path=path, project_type=project_type, cloud=cloud
            )

        if "contents" in t:
            logging.info("out  " + json.dumps(t["contents"]))
            if t["name"] != ".":
                path = os.path.join(parent_dir, t["name"])
                logging.info("Directory Name 2 " + t["name"])
            else:
                logging.info("Directory Name 2 " + t["name"])
                logging.info(path)

            create_template(t["contents"], path, project_type=project_type)


def disable_thothctl_integration(directory):
    """
    Disable thothctl integration.

    :param directory:
    :return:
    """
    filepath = os.path.join(directory, "terragrunt.hcl")
    # replace terragrunt hcl file content with clean content
    with open(filepath, "w") as fp:
        fp.write(terragrunt_hcl_clean)
        print(f"{Fore.YELLOW}⚠️ Integration disabled ! {Fore.RESET}")


def enable_thothctl_integration(directory):
    """
    Enable thothctl integration.

    :return:
    """

    filepath = os.path.join(directory, "terragrunt.hcl")
    # replace terragrunt hcl file content with clean content
    with open(filepath, "w") as fp:
        fp.write(terragrunt_root_hcl_content)
        print(f"{Fore.GREEN}✅️ Integration enabled ! {Fore.RESET}")
