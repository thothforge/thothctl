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


def replace_template_placeholders(directory, project_properties, project_name, action="make_project"):
    """
    Replace template placeholders in project files with values from project properties,
    or convert values to template placeholders when creating templates.
    
    :param directory: Project directory
    :param project_properties: Dictionary of project properties
    :param project_name: Name of the project
    :param action: "make_project" to replace placeholders with values, "make_template" to replace values with placeholders
    :return: None
    """
    allowed_extensions = {
        "png", "svg", "xml", "toml", ".thothcf.toml", "drawio",
        "gitignore", ".terraform.lock.hcl", "catalog-info.yaml",
        "mkdocs.yaml", "pdf", "dot", "gif", "jpg", "jpeg", "exe", "bin",
        "dll", "so", "dylib", "zip", "tar", "gz", "bz2", "xz", "7z", "rar",
        ".gitignore", ".pre-commit-config.yaml", ".tflint.hcl", "LICENSE"
    }
    not_allowed_folders = {
        ".git", ".terraform", ".terragrunt-cache", "cdk.out",
        "catalog", "__pycache__", "node_modules", "node-compile-cache",
        ".X11-unix", "tmp", ".amazonq"
    }
    
    # Create a mapping for common parameter name variations
    parameter_mapping = {
        "deployment_region": project_properties.get("region", "us-east-2"),
        "project_name": project_properties.get("project", project_name),
        "backend_dynamodb": project_properties.get("dynamodb_backend", "db-terraform-lock"),
        "cloud_provider": "aws",  # Default value
        "project_code": project_name,  # Use project name as default
        "deployment_profile": "default",  # Default value
        "backend_profile": "default",  # Default value
    }
    
    print(f"{Fore.LIGHTBLUE_EX}👷 Replacing template placeholders... {Fore.RESET}")
    
    for dirpath, dirnames, filenames in os.walk(directory):
        # Skip not allowed folders
        if any(x in dirpath for x in not_allowed_folders):
            continue
            
        for f in filenames:
            # Skip files with binary extensions
            if f.split(".")[-1] in allowed_extensions or f in allowed_extensions:
                continue
                
            file_path = os.path.join(dirpath, f)
            try:
                # Try to detect if file is binary
                is_binary = False
                try:
                    with open(file_path, 'r', encoding='utf-8') as test_file:
                        test_file.read(1024)  # Try to read a small chunk
                except UnicodeDecodeError:
                    is_binary = True
                
                if is_binary:
                    continue
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = file.read()
                
                # Track if any replacements were made
                replaced = False
                
                if action == "make_template":
                    # Convert values to placeholders
                    print(f"✅ Converting values to template parameters in {os.path.relpath(file_path, directory)}")
                    
                    # Replace project properties values with placeholders
                    for param, value in project_properties.items():
                        if value and str(value) in data:
                            placeholder = f"#{{{param}}}#"
                            data = data.replace(str(value), placeholder)
                            replaced = True
                            print(f"  • {param}: {value} → {placeholder}")
                    
                    # Replace parameter mapping values with placeholders
                    for param, value in parameter_mapping.items():
                        if value and str(value) in data and param not in project_properties:
                            placeholder = f"#{{{param}}}#"
                            data = data.replace(str(value), placeholder)
                            replaced = True
                            print(f"  • {param}: {value} → {placeholder}")
                            
                else:
                    # Original logic: Replace placeholders with values
                    # Find all placeholders in the format #{parameter}#
                    placeholders = re.findall(r'#\{([^}]+)\}#', data)
                    
                    # Replace each found placeholder
                    for param in placeholders:
                        placeholder = f"#{{{param}}}#"
                        
                        # First check if the parameter exists in project_properties
                        if param in project_properties:
                            value = project_properties[param]
                            data = data.replace(placeholder, str(value))
                            replaced = True
                            print(f"  • Replaced {placeholder} with {value} in {os.path.relpath(file_path, directory)}")
                        # Then check if it's in our mapping
                        elif param in parameter_mapping:
                            value = parameter_mapping[param]
                            data = data.replace(placeholder, str(value))
                            replaced = True
                            print(f"  • Replaced {placeholder} with {value} in {os.path.relpath(file_path, directory)}")
                
                # Write updated content back to file if replacements were made
                if replaced:
                    with open(file_path, 'w', encoding='utf-8') as file:
                        file.write(data)
            except Exception as e:
                # Log errors but continue processing
                logging.debug(f"Error processing {os.path.relpath(file_path, directory)}: {str(e)}")
    
    print(f"{Fore.GREEN}✅ Template placeholders replaced successfully!{Fore.RESET}")


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
    batch_mode: bool = False,
) -> dict:
    """
    Get project properties.

    :param project_name:
    :param remote_bkd_cloud_provider:
    :param cloud_provider:
    :param directory:
    :param batch_mode: Run in batch mode with minimal prompts
    :return:
    """
    print(Fore.GREEN)
    project_properties = {}

    input_parameters = load_iac_conf(directory=directory).get(
        "template_input_parameters", {}
    )
    print(f"{Fore.CYAN}DEBUG: Loaded input_parameters: {input_parameters}{Fore.RESET}")
    
    if input_parameters == {}:
        if batch_mode:
            # Use default values in batch mode
            project_properties["project"] = project_name
            project_properties["environment"] = "dev"
            project_properties["owner"] = "thothctl"
            project_properties["client"] = "thothctl"
            
            if remote_bkd_cloud_provider == "aws":
                project_properties["backend_region"] = "us-east-2"
                project_properties["dynamodb_backend"] = "db-terraform-lock"
                project_properties["backend_bucket"] = f"{project_name}-tfstate"
            
            if cloud_provider == "aws":
                project_properties["region"] = "us-east-2"
                
            print(f"{Fore.MAGENTA}✅ Using default project properties in batch mode: {project_properties} {Fore.RESET}")
            return project_properties
            
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
            batch_mode=batch_mode,
        )

    return project_properties


def get_simple_project_props(
    input_parameters: dict, project_properties: dict, project_name: str, batch_mode: bool = False
) -> dict:
    """
    Get project properties.

    :param input_parameters:
    :param project_properties:
    :param project_name:
    :param batch_mode: Run in batch mode with minimal prompts
    :return:
    """
    print(f"{Fore.GREEN} Write project parameters for {project_name}")
    print(f"{Fore.CYAN}DEBUG: input_parameters type: {type(input_parameters)}, content: {input_parameters}{Fore.RESET}")
    
    # Check if input_parameters is empty or not properly formatted
    if not input_parameters:
        print(f"{Fore.YELLOW}⚠️ No input parameters defined. Using default project properties.{Fore.RESET}")
        return project_properties
    
    # Check if input_parameters is a simple dictionary of placeholders
    is_simple_dict = all(isinstance(v, str) for v in input_parameters.values())
    
    if batch_mode:
        # In batch mode, use sensible default values
        default_values = {
            'project': project_name,
            'environment': 'dev',
            'owner': 'thothctl',
            'client': 'thothctl',
            'backend_region': 'us-east-2',
            'dynamodb_backend': 'db-terraform-lock',
            'backend_bucket': f"{project_name}-tfstate",
            'region': 'us-east-2'
        }
        
        for k in input_parameters.keys():
            try:
                # Use sensible defaults instead of placeholder values
                if k in default_values:
                    default_value = default_values[k]
                else:
                    # For unknown keys, use a sensible default
                    if 'region' in k:
                        default_value = 'us-east-2'
                    elif 'bucket' in k:
                        default_value = f"{project_name}-{k}"
                    elif k in ['project', 'project_name']:
                        default_value = project_name
                    else:
                        default_value = f"{project_name}-{k}"
                
                project_properties[k] = default_value
                print(f"  • Using default value for {k}: {default_value}")
            except Exception as e:
                print(f"{Fore.RED}❌ Error setting default value for {k}: {str(e)}{Fore.RESET}")
        return project_properties
    
    # Interactive mode
    for k in input_parameters.keys():
        try:
            if is_simple_dict:
                # For simple dictionaries, just ask for the value
                questions = [
                    inquirer.Text(
                        name=k,
                        message=f"Input value for {k}: ",
                        default=project_name if k == "project" else None,
                    ),
                ]
                answer = inquirer.prompt(questions)
                if answer:  # Check if user didn't cancel
                    project_properties[k] = answer[k]
            else:
                # For complex dictionaries with metadata
                if isinstance(input_parameters[k], dict) and 'description' in input_parameters[k]:
                    message = f'Input {input_parameters[k]["description"]} '
                    
                    # Set up validation if condition exists
                    validate = None
                    if 'condition' in input_parameters[k]:
                        pattern = input_parameters[k]["condition"]
                        validate = lambda _, x: re.match(pattern=pattern, string=x)
                    
                    # Set up default from template_value
                    default = input_parameters[k].get("template_value")
                    
                    questions = [
                        inquirer.Text(
                            name=k,
                            message=message,
                            validate=validate,
                            default=default,
                        ),
                    ]
                    answer = inquirer.prompt(questions)
                    if answer:  # Check if user didn't cancel
                        project_properties[k] = answer[k]
                else:
                    # If not properly formatted, just ask for the value
                    questions = [
                        inquirer.Text(
                            name=k,
                            message=f"Input value for {k}: ",
                        ),
                    ]
                    answer = inquirer.prompt(questions)
                    if answer:  # Check if user didn't cancel
                        project_properties[k] = answer[k]
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing parameter {k}: {str(e)}{Fore.RESET}")
    
    return project_properties


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
