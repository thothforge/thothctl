"""Create and generate Code."""
import json
import logging
import re
import sys
from pathlib import Path

import os.path
from colorama import Fore


def create_multiple_repos(
    file_hcl: str,
    domain_pat: str,
    resource_name: str,
    default_branch: str = "main",
    validate_repository_name=False,
):
    """
    Create multiple repositories.

    :param file_hcl:
    :param domain_pat:
    :param resource_name:
    :param default_branch:
    :param validate_repository_name:
    :return:
    """
    for r in resource_name.split(","):
        create_code_repo(
            file_hcl=file_hcl,
            domain_pat=domain_pat,
            resource_name=r,
            default_branch=default_branch,
            validate_repository_name=validate_repository_name,
        )


def create_code_repo(
    file_hcl: str,
    domain_pat: str,
    resource_name: str,
    default_branch: str = "main",
    validate_repository_name=False,
):
    """
    Create and add repo hcl code.

    :param file_hcl:
    :param domain_pat:
    :param resource_name:
    :param default_branch:
    :return:


    """
    # validate domain path
    d_path = validate_exist_domain_pat(domain_pat)
    # validate name structure
    if validate_repository_name:
        validate_repo_name(repo_name=resource_name, domain_name=domain_pat)

    p_file_hcl = Path.joinpath(d_path, file_hcl)
    print(p_file_hcl)

    modules = {
        resource_name: {
            "name": resource_name,
            "default_branch": f"refs/heads/{default_branch}",
            "initialization": {"init_type": "Clean"},
            "create_pipeline": True,
        }
    }
    print("Creating code block")
    print(json.dumps(modules, indent=2))

    mod = modules[resource_name]

    with open(p_file_hcl, "r") as f:
        contents = f.readlines()
    logging.info(contents)
    ind = 0
    for c in contents:
        if c.replace(" ", "").__contains__("repos={") or c.replace(
            " ", ""
        ).__contains__("repositories={".replace(" ", "")):
            logging.info(c)
            ind = contents.index(c)
    logging.info(ind)
    line = f'{resource_name} = {json.dumps(mod, indent=2, separators=[",", " = "])} \n'
    contents.insert(ind + 1, line)

    with open(p_file_hcl, "w") as f:
        contents = "".join(contents)
        f.write(contents)


def validate_exist_domain_pat(domain_pat: str):
    """
    Validate if a domain exists.

    :param domain_pat:
    :return:
    """
    path_1 = os.path.join("resources/repositories", domain_pat)
    path_2 = os.path.join("resources/repos", domain_pat)

    if Path(path_1).exists():
        print(f"✅ {path_1} Exist! ")
        return Path(path_1)
    elif Path(path_2).exists():
        print(f"✅ {path_2} Exist! ")
        return Path(path_2)
    else:
        sys.exit(
            f"{Fore.RED}❌ Error, the domain {domain_pat} doesn't exists ({path_1} or {path_2}). "
        )


# function for validate repository structure name
def validate_repo_name(repo_name: str, domain_name: str):
    """
    Validate the repository name.

    :param repo_name:
    :param domain_name:
    :return:
    """
    print(f"{Fore.GREEN}👷 Validating repository name {Fore.RESET}")
    # dict rules expressions for repository name
    rules = {
        "repo_name": "^[a-zA-Z0-9-_]+$",
    }
    # Regular expression for repository names that begin with data_, qa_, process_auto_, terraform_
    # and contain only letters, numbers, underscores.

    regex = re.compile(rules["repo_name"])
    # check if the repository name matches the regular expression
    domains = {"data_", "qa_", "process_auto_", "terraform_", "idp_", "cdkv2_", "aws_"}
    if regex.match(repo_name) and any(domain_name.lower() in d for d in domains):
        return repo_name
    else:
        sys.exit(
            f"{Fore.RED} ❌  Error, the repository name {repo_name} is not valid. Valid prefix are {domains} {Fore.RESET}"
        )
