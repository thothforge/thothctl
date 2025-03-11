"""Validate project structure."""
import logging
import pathlib
import sys
import warnings
from pathlib import Path

import os
from colorama import Fore

from ....common.common import load_iac_conf


def check_global_structure(directory, mood="soft", l_project_structure=None):
    """
    Check global structure.

    :param directory:
    :param mood:
    :param l_project_structure:
    :return:
    """
    differences = []
    optional = ""

    list_dict = set(os.listdir(Path(directory)))
    logging.info(list_dict)

    print(Fore.GREEN + "⚛️ Checking root structure" + Fore.RESET)

    for a in l_project_structure["folders"]:
        mandatory = a.get("mandatory", False)
        if not mandatory:
            optional = " but is optional"

        if a["name"] in list_dict and a["type"] == "root":
            print(
                f"{Fore.GREEN}✅ - {a['name']} {a['type']} exists! in {directory}{Fore.RESET}"
            )

            logging.info(f"{a['name']} Exist!")

        else:
            print(
                Fore.RED
                + f"❌ - {a['name']} Doesn't Exist! in {directory} {optional}"
                + Fore.RESET
            )
            if mandatory:
                differences.append({"Name": a["name"], "Check": "Fail", "path": a})

    for a in l_project_structure["root_files"]:
        if a in list_dict:
            print(Fore.GREEN + f"✅ - {a}  exists!" + Fore.RESET)
            logging.info(f"{a} Exist!")

        else:
            print(Fore.RED + f"❌ - {a} Doesn't Exist!" + Fore.RESET)
            differences.append({"Name": a, "Check": "Fail", "path": a})

    logging.info(differences)
    set_mood(mood=mood, differences=differences)
    return differences, list_dict


def get_keys(directory):
    """
    Get keys.

    :param directory:
    :return:
    """
    keys = os.listdir(directory)

    i_tree = {}
    for k in keys:
        if (
            k != ".git"
            and k != ".terraform"
            and k != ".terragrunt-cache"
            and Path(k).is_dir()
        ):
            i_tree[k] = []

    return i_tree


def create_project_structure(dirpath, tree: dict = None):
    """
    Create project structure.

    :param dirpath:
    :param tree:
    :return:
    """
    parts = Path(os.path.join(os.getcwd(), dirpath)).resolve().parts

    for k in tree.keys():
        if k in parts:
            tree[k].append(
                {
                    "name": Path(dirpath).resolve().name,
                    "path": dirpath,
                    "type": "child_folder",
                    "content": os.listdir(Path(dirpath).resolve()),
                }
            )
    logging.info(tree)
    return tree


def append_tree(directory):
    """
    Append directories.

    :param directory:
    :return:
    """
    tree = get_keys(directory)
    for dirpath, dirnames, filenames in os.walk(directory):
        if (
            ".git" not in dirpath
            and ".terraform" not in dirpath
            and ".terragrunt-cache" not in dirpath
        ):
            logging.info(dirpath)
            sub_list_dir = os.listdir(dirpath)
            logging.info(f"{dirpath}: {sub_list_dir}")

            # substr_exist = any(".tf" in sub for sub in sub_list_dir)
            # substr_exist_2 = any(".hcl" in sub for sub in sub_list_dir)
            # if substr_exist or substr_exist_2:
            logging.info(Path(dirpath).resolve().name)

            create_project_structure(dirpath=dirpath, tree=tree)

    return tree


def set_mood(mood="soft", differences=None):
    """
    Set checking mode.

    :param mood:
    :param differences:
    :return:
    """
    if differences is None:
        differences = []
    if mood == "hard" and len(differences) > 0:
        message = []
        print(f"\n{Fore.CYAN} Summary")
        for d in differences:
            message.append(f"❌ No Found file or archive  {d['Name']} ")

        print(Fore.RED + "\n".join(map(str, message)))

        sys.exit("The code doesn't compliant with the standard structure")

    elif mood == "soft" and len(differences) > 0:
        print(Fore.MAGENTA)
        warnings.warn("The code doesn't compliant with the standard structure")
    print(Fore.RESET)

    return 0


def check_files(content):
    """
    Check if file exists.

    :param content:
    :return:
    """
    file_types = [".tf", ".hcl", ".yaml"]
    find = False
    for f in file_types:
        if f in str(content):
            find = True
            break

    return find


def check_child_structure(structure: list = None, rule_list: list = None, mood="soft"):
    """
    Check child folder structure.

    :param structure:
    :param rule_list:
    :param mood:
    :return:
    """
    print(Fore.GREEN + "⚛️ Checking child structure" + Fore.RESET)
    logging.info(structure)

    differences = []
    for m in structure:
        logging.info(m)

        if m["type"] == "child_folder" and (check_files(m["content"])):
            print(Fore.GREEN + "\n" + m["path"] + Fore.RESET)
            for e in rule_list:
                if e in m["content"]:
                    print(Fore.GREEN + f"✅ - {e}  exists! " + Fore.RESET)
                else:
                    print(Fore.RED + f"❌ - {e} Doesn't Exist! " + Fore.RESET)
                    differences.append({"Name": e, "Check": "Fail", "path": m["path"]})

    logging.info(differences)
    set_mood(mood=mood, differences=differences)

    return differences


def check_common(structure: list = None, rule_list: list = None, mood="soft"):
    """
    Check common folder structure.

    :param structure:
    :param rule_list:
    :param mood:
    :return:
    """
    print(Fore.GREEN + "⚛️ Checking common structure" + Fore.RESET)
    differences = []
    for m in structure:
        for e in rule_list:
            if e in m["content"]:
                print(Fore.GREEN + f"✅ - {e}  exists! " + Fore.RESET)
            else:
                print(Fore.RED + f"❌ - {e} Doesn't Exist! " + Fore.RESET)

                differences.append({"Name": e, "Check": "Fail", "path": m["path"]})
        print("\n")

    set_mood(mood=mood, differences=differences)


def get_tree_structure(p_structure: dict = None):
    """
    Get tree structure.

    :param p_structure:
    :return:
    """
    tree = {}
    if p_structure is not None:
        for f in p_structure["folders"]:
            if f["mandatory"]:
                tree[f["name"]] = {}
    return tree


def get_folder_rules(p_structure: dict = None):
    """
    Get folder rules.

    :param p_structure:
    :return:
    """
    f_rules = {}
    if p_structure is not None:
        for f in p_structure["folders"]:
            if (
                f["mandatory"]
                and f.get("content", {}) != {}
                and (
                    f.get("type", "root") == "root"
                    or f.get("type", "root") == "child_folder"
                )
            ):
                f_rules[f["name"]] = f["content"]
    return f_rules


def init_check(directory=".", mood="soft", custom=False, check_type: str = "project"):
    """
    Check project structure.

    :param directory:
    :param mood:
    :param custom:
    :param check_type:
    :return:
    """
    dirname = os.path.dirname(__file__)
    if custom:
        print(f"{Fore.LIGHTBLUE_EX}Using Custom options")
        # Load project structure properties
        p_structure = load_iac_conf(directory=directory)["project_structure"]
        logging.info(f"Project structure {p_structure}")
        tree = get_tree_structure(p_structure)
        rules = get_folder_rules(p_structure)
        logging.info(f"Project rules {rules}")
        logging.info(tree)
        logging.info(p_structure)

    else:
        print(f"{Fore.LIGHTBLUE_EX}Using default options")
        # Set default rules
        if check_type == "module":
            file_name = ".thothcf_module.toml"
        else:
            file_name = ".thothcf_project.toml"

        p_structure = load_iac_conf(
            os.path.join(dirname, "../common/"), file_name=file_name
        )["project_structure"]
        rules = get_folder_rules(p_structure)

    # Check project
    directory = pathlib.PurePath(directory)

    check_global_structure(directory, l_project_structure=p_structure, mood=mood)
    print(Fore.GREEN + "\n⚛️ Get project structure" + Fore.RESET)
    t = append_tree(directory=directory)
    logging.info(t)
    logging.info(f"The project structure is: {t} ")
    logging.info(f"The rules are {rules}")

    extend_structure = get_child_folder(p_structure=t)
    logging.info(
        f"{Fore.BLUE} The project extend structure {str(extend_structure)}  {Fore.RESET}"
    )

    for rs in rules.keys():
        print(f"{Fore.CYAN}👷 Checking child folder {rs}. {Fore.RESET}")

        if rs in extend_structure.keys():
            logging.info(f"{extend_structure[rs]}, {rules[rs]}")
            check_child_structure(
                structure=extend_structure[rs], rule_list=rules[rs], mood=mood
            )
        else:
            print(
                f"{Fore.CYAN}Child folder {rs} skipped due doesn't exist. {Fore.RESET}"
            )


def get_child_folder(p_structure: dict, directory="."):
    """
    Get child folder for file project structure.

    :param p_structure:
    :param directory:
    :return:
    """
    tree = get_keys(directory)
    children = {}
    for d in p_structure.keys():
        if isinstance(p_structure[d], list):
            for a in p_structure[d]:
                if isinstance(a, dict):
                    if a.get("type", "none") == "child_folder":
                        children[a["name"]] = [a]
                        for t in tree.keys():
                            if (
                                f"./{t}" in a["path"]
                                and a["content"] != []
                                and (check_files(a["content"]))
                            ):
                                children[t].append(a)

    logging.info(children)

    return children


# TODO go in deep in rules for structure based on files or folders
