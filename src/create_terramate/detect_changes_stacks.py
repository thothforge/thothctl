"""Functions to detect changes in stacks and run pipeline just for those resources."""

import base64
import json
import logging
from datetime import datetime

import os
from colorama import Fore
from git import Repo

from .create_terramate_stacks import graph_dependencies_to_json


true = "true"
false = "false"
#
content_changes_hcl = """
include "changes" {
  
  path   = "pwd/common/_changes.hcl"
}
"""
content_main_chain_hcl = """
include "m_changes" {
  
  path   = "pwd/common/_main_changes.hcl"
}
"""


def git_diff(gd_mood="commit", directory=".", base_tag="v1.0.0"):
    """
    Get git diff based on commits or tags.

    :param base_tag:
    :param gd_mood:
    :param directory:

    :return:
    """
    # repo is a Repo instance pointing to the git-python repository.
    # For all you know, the first argument to Repo is a path to the repository
    # you want to work with
    repo = Repo(directory)
    base = ""
    assert not repo.bare
    if gd_mood == "commit":
        # Compare the last commits
        c_0 = repo.commit("HEAD")
        logging.info(f"The last commit is: {c_0} ")

        c_1 = repo.commit("HEAD~1")
        logging.info(f"The base commit is: {c_1} ")

        base = c_1
    elif gd_mood == "simple_tags":
        print(f"{Fore.MAGENTA}Evaluate with {gd_mood} and {base_tag}{Fore.RESET}")
        tags = repo.tags

        if len(tags) > 0 and len(tags) >= 2:
            logging.info(f"The tags are: {tags} ")
            logging.info(f"The last tag is: {tags[-1]} ")
            logging.info(f"The previous tag is: {tags[-2]} ")
            p_tag = tags[-2]
            print(
                f"{Fore.MAGENTA}Analyze changes base on {tags[-1]} vs {p_tag}{Fore.RESET}"
            )

            base = str(p_tag)
        elif len(tags) > 0:
            logging.info(f"The tags are: {tags} ")
            logging.info(f"The last tag is: {tags[-1]} ")
            p_tag = tags[-1]
            base = str(p_tag)

    elif gd_mood == "complex_tags":
        tags = repo.tags
        print(f"{Fore.MAGENTA}Evaluate with {gd_mood} and {base_tag}{Fore.RESET}")
        if len(tags) > 0 and base_tag in tags:
            logging.info(f"The tags are: {tags} ")
            logging.info(f"The last tag is: {tags[-1]} ")
            logging.info(f"The previous tag is: {tags[-2]} ")
            p_tag = base_tag
            print(
                f"{Fore.MAGENTA}Analyze changes base on {base_tag} vs {p_tag}{Fore.RESET}"
            )
            base = str(p_tag)
        else:
            print(f"{Fore.MAGENTA}Tag no found! Using Simple tags mode.{Fore.RESET}")
            base = git_diff(gd_mood="simple_tags", directory=directory)
    else:
        logging.info("No Tags Found, use commit mode!")
        base = git_diff(gd_mood="commit", directory=directory)

    return base


def taint_stack(directory, gd_mood="commit", base_tag="v1.0.0"):
    """
    Taint stacks based on git changes.

    :param directory:
    :param gd_mood:
    :param base_tag:
    :return:
    """
    logging.info(directory)

    print(f"{Fore.GREEN}Getting modules for changes {Fore.RESET}")
    git_rev = git_diff(gd_mood=gd_mood, base_tag=base_tag)

    command = f"terramate list --changed --git-change-base {git_rev}"
    run = os.popen(command)
    stack_to_taint = run.read()
    logging.debug(stack_to_taint)

    if stack_to_taint != "":
        print(Fore.GREEN + f"Modules changes was: \n{stack_to_taint}" + Fore.RESET)
        list_stack = stack_to_taint.strip().split("\n")
        logging.info(list_stack)

        for s in list_stack:
            # Taint dependencies
            modify_terragrunt_file(stack_name=f"./{s}", content=content_main_chain_hcl)

    else:
        print(Fore.CYAN + "No modules with changes" + Fore.RESET)
    return stack_to_taint


def modify_terragrunt_file(stack_name, content=content_changes_hcl):
    """Modify terragrunt hcl file.

    :param stack_name:
    :param content:
    :return:
    """
    # Get date and encode it with base64.b64encode() method.
    # The method returns a bytes object, so we need to convert it to a string.
    # We also need to encode it to UTF-8, so that it can be used in a HCL file.
    # The encoded date is then appended to the content of the terragrunt.hcl file.
    # The content is then written to the terragrunt.hcl file.
    # The terragrunt.hcl file is then closed.
    # The encoded date is then appended to the content of the terragrunt.hcl file.
    # The content is then written to the terragrunt.hcl file.
    # The terragrunt.hcl file is then closed.
    # The encoded date is then appended to the content of the terragrunt.hcl file.
    # The content is then written to the terragrunt.hcl file.
    enc_date = base64.b64encode(bytes(str(datetime.today()), "utf-8"))
    # Modify terrragrunt hcl

    content += "#" + str(enc_date)

    directory = os.getcwd()
    content = content.replace("pwd", directory)
    path = os.path.join(directory, stack_name, "terragrunt.hcl")
    mood = "a"
    with open(path, mood) as fp:
        print(content, file=fp)

    fp.close()

    print(Fore.GREEN + f"Taint Stack {stack_name}" + Fore.RESET)

    return content


def read_file(file):
    """Read terragrunt hcl file.

    :param file:
    :return:
    """
    directory = os.getcwd()
    path = os.path.join(directory, file, "terragrunt.hcl")
    mood = "r"
    with open(path, mood) as fp:
        file = fp.read()

    fp.close()
    return file


def recursive_taint(json_graph):
    """Taint recursively discovering the tree dependencies.

    :param json_graph:
    :return:
    """
    after = []
    logging.debug(json_graph)
    if "edges" in json_graph.keys():
        for a in json_graph["edges"]:
            for o in json_graph["objects"]:
                if a["tail"] == o["_gvid"]:
                    stack_name = json_graph["objects"][a["head"]]["name"]

                    logging.info(o["name"] + " Depends of " + stack_name)
                    after.append(stack_name)
                    after = list(dict.fromkeys(after))
                    logging.info(f'The {o["name"]} depends of {after}')

    if len(after) > 0:
        check_taint(stack_names=after)

        logging.info(f"after= {after}")


# check if already taint
def check_taint(stack_names):
    """Check if a resource is already with changes.

    If not, it will create the changes file  and add the resource to the changes file. If it is already taint, it will just log it.

    :param stack_names:
    :return:
    """
    for i in stack_names:
        if "_changes.hcl" in read_file(f".{i}"):
            logging.info("Already taint")
        else:
            modify_terragrunt_file(stack_name=f".{i}")
        graph = graph_dependencies_to_json(f".{i}")
        recursive_taint(json.loads(graph))


def create_changes_file(path_file="./common/_changes.hcl"):
    """Create changes file for running pipeline based on changed stacks.

    :param path_file:
    :return:
    """
    terragrunt_file = path_file
    content = """
locals {
  changes= true
}
"""
    mood = "w"
    with open(terragrunt_file, mood) as fp:
        print(content, file=fp)

    fp.close()

    print(
        Fore.GREEN
        + f"The file {terragrunt_file} was added to the project !."
        + Fore.RESET
    )
