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
from .project_templates import terraform_module_template, terraform_template, terragrunt_template


# TODO Create project based on type / terraform module / terraform terragrunt / cdkv2 custom / ML /
def init_thothcf_content(project_type="terraform-terragrunt"):
    """
    Init thothcf content based in project type.

    :param project_type:
    :return:
    """

    if project_type == "terraform":
        template = thothcf_toml_content
    elif project_type == "terraform-module":
        template = thothcf_toml_module_content
    elif project_type in ["terragrunt", "terraform-terragrunt"]:
        template = thothcf_toml_content  # Use same content as terraform for now
    else:
        logging.error(f"Project type {project_type} not supported")
        raise ValueError(f"Project type {project_type} not supported")
    return template


def create_project(
    project_name: str, project_type="terraform-terragrunt", template=terraform_template
):
    """
    Create file structure for a project using terraform + terragrunt.

     :param template:
     :param project_type:
     :param project_name:
     :return: Repository metadata if GitHub template was used, None otherwise
    """
    # Parent Directory path
    parent_dir = os.getcwd()

    # Path
    path = os.path.join(parent_dir, project_name)

    # Create the directory
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

    # Try to load template from GitHub first
    from .github_template_loader import GitHubTemplateLoader
    
    github_loader = GitHubTemplateLoader()
    repo_metadata = github_loader.load_template(project_name, project_type)
    
    if repo_metadata:
        # Template loaded successfully from GitHub
        return repo_metadata
    
    # Fallback to local hardcoded templates
    print(f"{Fore.YELLOW}⚠️ Using local template as fallback{Fore.RESET}")
    
    if project_type == "terraform":
        template = terraform_template
    elif project_type == "terraform-module":
        template = terraform_module_template
    elif project_type in ["terragrunt", "terraform-terragrunt"]:
        template = terragrunt_template
    else:
        template = terraform_template  # Default fallback

    create_template(template=template, parent_dir=path, project_type=project_type)
    return None  # No metadata for local templates


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
            logging.debug("Creating directory: " + t["name"])
            logging.debug("Directory contents: " + str(t.get("contents", [])))

        elif t["type"] == "file":
            file = t["name"]
            logging.debug("Creating file: " + file)
            create_common_files(file_name=file, path=path)
            create_project_files(
                file_name=file, path=path, project_type=project_type, cloud=cloud
            )

        if "contents" in t:
            logging.debug("Processing contents: " + json.dumps(t["contents"]))
            if t["name"] != ".":
                path = os.path.join(parent_dir, t["name"])
                logging.debug("Processing directory: " + t["name"])
            else:
                logging.debug("Processing root directory: " + t["name"])
                logging.debug("Path: " + path)

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
