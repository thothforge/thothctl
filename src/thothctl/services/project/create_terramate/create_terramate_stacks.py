"""Create and operate terramate stacks."""
import json
import logging
from pathlib import Path

import git
import os
from colorama import Fore


true = "true"
false = "false"


def graph_dependencies_to_json(directory):
    """
    Graph dependencies and convert to json.

    :param directory:
    :return:
    """
    logging.debug(directory)
    d = Path(directory).resolve().name
    full_path = Path(directory).resolve().absolute()
    pwd = os.getcwd()
    logging.debug(f"Current path {pwd}")

    replace = Path(directory).resolve().parents[1]
    logging.debug(replace)
    logging.debug(pwd)

    logging.info(f"Getting dependencies graph for {d} ")

    command = f"cd {full_path} && terragrunt graph-dependencies --terragrunt-non-interactive |  dot -Tdot_json "
    run = os.popen(command)
    graph_json = run.read()
    logging.debug(graph_json)
    return graph_json


def create_terramate_stacks(json_graph, directory, optimized=False):
    """
    Create terramate stacks.

    :param json_graph:
    :param directory:
    :param optimized:
    :return:
    """
    after = []
    logging.debug(json_graph)
    if "edges" in json_graph.keys():
        for a in json_graph["edges"]:
            for o in json_graph["objects"]:
                if a["tail"] == o["_gvid"]:
                    stack_name = json_graph["objects"][a["head"]]["name"]
                    logging.debug(o["name"] + " Depends of " + stack_name)
                    after.append(stack_name)
                    after = list(dict.fromkeys(after))

        logging.info(f"after= {after}")
        cont = f"after= {after}"
    else:
        cont = ""

    w_content = """
        watch = [
              "./terragrunt.hcl",
           ]"""
    content = "stack { \n" + cont + w_content + "\n}"
    content = content.replace("'", '"')

    terramate_file = os.path.join(directory, "terramate.tm.hcl")

    mood = "w"
    with open(terramate_file, mood) as fp:
        print(content, file=fp)

    fp.close()

    if optimized:
        repo = git.Repo(".")
        repo.git.add(terramate_file)
        print(
            Fore.GREEN
            + f"The file {terramate_file} was added to git project !."
            + Fore.RESET
        )


def recursive_graph_dependencies_to_json(directory):
    """
    Graph dependencies recursively.

    :param directory:
    :return:
    """
    logging.info(directory)
    ls_dir = os.listdir(directory)

    for ld in ls_dir:
        nested_dir = os.path.join(directory, ld)
        if not os.path.isdir(nested_dir) and ld.startswith("."):
            logging.info(f"Finding a folder {ld}...")
            recursive_graph_dependencies_to_json(nested_dir)
            if os.path.exists(f"{nested_dir}/main.tf") and os.path.exists(
                f"{nested_dir}/terragrunt.hcl"
            ):
                print(
                    Fore.GREEN
                    + f"⚠️{Fore.GREEN} Find terragrunt.hcl files in {nested_dir} ... {Fore.RESET}"
                    f"\n❇️ {Fore.GREEN} Creating Terramate stacks ... " + Fore.RESET
                )
                graph = json.loads(graph_dependencies_to_json(nested_dir))

                create_terramate_stacks(json_graph=graph, directory=nested_dir)


def create_terramate_main_file(default_branch="master", optimized=False):
    """
    Create the main terramate file.

    :param default_branch:
    :param optimized:
    :return:
    """
    terramate_file = "terramate.tm.hcl"
    content = """
terramate {
  config {
    git {
      default_remote = "origin"
      default_branch = "master"
      check_untracked = false
      check_uncommitted = false
      check_remote = false
        }
  }
}
terramate {
    required_version = "~> 0.2"
}"""
    if default_branch != "master":
        content = content.replace("master", default_branch)
    mood = "w"
    with open(terramate_file, mood) as fp:
        print(content, file=fp)

    fp.close()

    if optimized:
        repo = git.Repo(".")
        repo.git.add(terramate_file)
        print(
            Fore.GREEN
            + f"The file {terramate_file} was added to git project !."
            + Fore.RESET
        )
