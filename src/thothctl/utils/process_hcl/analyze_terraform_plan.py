"""Analyze terraform plan and print summary."""
import json
import logging
import re
import subprocess
from collections import defaultdict
from itertools import groupby
from pathlib import Path, PurePath

import os
from colorama import Fore
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table


icons = {"update": "♻️", "create": "❇️", "delete": "⛔"}

output = defaultdict(
    lambda: {"header": "", "changes": [], "create": 0, "update": 0, "delete": 0}
)

tfplan_name = "tfplan.json"


def get_plan_results(directory: Path, plan_name: str = tfplan_name):
    """Get plan results from tfplan.json file.

    Args:
        directory (PurePath): Path to directory containing tfplan.json file.
        plan_name (str, optional): Name of tfplan.json file. Defaults to tfplan.json.

    Returns:
        dict: Dictionary containing plan results.
    """
    w = directory.name
    output[w]["header"] = w
    plan_path = Path.joinpath(directory, plan_name)
    if not os.path.exists(plan_path):
        return None

    output[w]["changes"] = []
    output[w]["create"] = 0
    output[w]["update"] = 0
    output[w]["delete"] = 0
    with open(plan_path, "r") as plan:
        data = json.load(plan)
        for x in data["resource_changes"]:
            if any(item not in ["no-op", "read"] for item in x["change"]["actions"]):
                for y in x["change"]["actions"]:
                    z = x.copy()
                    z["change"]["action"] = y
                    output[w]["changes"].append(z)
                    output[w][y] += 1
    return data


def pretty_print_diff(x, last=None):
    """Print line. assumes ordered list of changes by hierarchy (default)"""

    popped = x.pop(0)
    stripped = [x for x in re.split(r"(module\..*?)\.", popped["address"])]

    if len(stripped) - 1 == 0:
        print(f"{icons[popped['change']['action']]} {popped['address']}")
    else:
        if last != stripped[:-1]:
            print(f"{'.'.join(stripped[:-1])}:")
        if len(x) != 0:
            peek = list(filter(None, re.split(r"(module\..*?)\.", x[0]["address"])))
            if peek[:-1] == stripped[:-1]:
                print(f"{icons[popped['change']['action']]} ├── {stripped[-1]}")
            else:
                print(f"{icons[popped['change']['action']]} └── {stripped[-1]}")
        else:
            print(f"{icons[popped['change']['action']]} └── {stripped[-1]}")
    if len(x) > 0:
        pretty_print_diff(x, stripped[:-1])


# print summary table
def pretty_print_table(spare_plans: bool = False, json_plans: list = None):
    if spare_plans:
        return

    print("## Plan Summary\n\n<table><tr><td><b>State</b><td>❇️<td>♻️<td>⛔</tr>")

    sorted_plans = sorted(json_plans, key=has_changes)

    for has_change, group in groupby(sorted_plans, key=has_changes):
        for plan in group:
            if not has_change:
                print(
                    f"<tr><td><b>{output[plan]['header']}</b><td colspan=3>No changes.</td></tr>"
                )
            else:
                print(
                    f"<tr><td><b>{output[plan]['header']}</b>"
                    f"<td><b>{output[plan]['create']}</b>"
                    f"<td><b>{output[plan]['update']}</b>"
                    f"<td><b>{output[plan]['delete']}</b></tr>"
                )

    print("</table>\n")


def generate_table_string(spare_plans: bool = False, json_plans: defaultdict = None):
    if spare_plans or not json_plans:
        return ""

    table_string = (
        "## Plan Summary\n\n<table><tr><td><b>State</b><td>❇️<td>♻️<td>⛔</tr>\n"
    )

    sorted_plans = sorted(json_plans, key=has_changes)

    for has_change, group in groupby(sorted_plans, key=has_changes):
        for plan in group:
            if not has_change:
                table_string += f"<tr><td><b>{output[plan]['header']}</b><td colspan=3>No changes.</td></tr>\n"
            else:
                table_string += (
                    f"<tr><td><b>{output[plan]['header']}</b>"
                    f"<td><b>{output[plan]['create']}</b>"
                    f"<td><b>{output[plan]['update']}</b>"
                    f"<td><b>{output[plan]['delete']}</b></tr>\n"
                )

    table_string += "</table>\n"
    return table_string


def save_summary_to_file(filename, content):
    try:
        with open(filename, "w") as file:
            file.write(content)
        print(f"Summary has been saved to {filename}")
    except IOError as e:
        print(f"An error occurred while writing to the file: {e}")


# print summary plan
def print_plan_details(json_plan, changes):
    print(f"### {output[json_plan]['header']}")
    print("```diff")
    pretty_print_diff(changes)
    print("```")
    print(
        f"{Fore.GREEN}{output[json_plan]['create']} to add,  "
        f"{Fore.CYAN}{output[json_plan]['update']} to change, "
        f"{Fore.RED}{output[json_plan]['delete']} to destroy.\n{Fore.RESET}"
    )


def generate_plan_details(json_plan, changes):
    output_text = f"### {output[json_plan]['header']}\n"
    output_text += "```diff\n"

    # Assuming pretty_print_diff now returns a string instead of printing
    diff_output = pretty_pconsole_diff(changes)
    output_text += diff_output

    output_text += "```\n"

    # Using string formatting for color codes
    output_text += (
        f"{output[json_plan]['create']} to add, "
        f"{output[json_plan]['update']} to change, "
        f"{output[json_plan]['delete']} to destroy.\n\n"
    )

    return output_text


def has_changes(json_plan):
    return any(
        output[json_plan][action] > 0 for action in ["create", "update", "delete"]
    )


def pretty_pconsole_table(spare_plans: bool = False, json_plans: defaultdict = None):
    if spare_plans or not json_plans:
        return

    console = Console()
    table = Table(title="Plan Summary")

    # Add columns
    table.add_column("TFPlan", style="cyan", no_wrap=True)
    table.add_column("Create ❇️", style="green")
    table.add_column("Update ♻️", style="yellow")
    table.add_column("Delete ⛔", style="red")

    # Sort and group plans
    sorted_plans = sorted(json_plans, key=has_changes)

    for has_change, group in groupby(sorted_plans, key=has_changes):
        for plan in group:
            if not has_change:
                table.add_row(output[plan]["header"], "No changes", "", "")
            else:
                table.add_row(
                    output[plan]["header"],
                    str(output[plan]["create"]),
                    str(output[plan]["update"]),
                    str(output[plan]["delete"]),
                )

    # Print the table
    console.print(table)


def pretty_pconsole_diff(x, last=None, output=""):
    if not x:
        return output

    popped = x.pop(0)
    stripped = [x for x in re.split(r"(module\..*?)\.", popped["address"])]

    if len(stripped) - 1 == 0:
        output += f"{icons[popped['change']['action']]} {popped['address']}\n"
    else:
        if last != stripped[:-1]:
            output += f"{'.'.join(stripped[:-1])}:\n"
        if x:
            peek = list(filter(None, re.split(r"(module\..*?)\.", x[0]["address"])))
            if peek[:-1] == stripped[:-1]:
                output += f"{icons[popped['change']['action']]} ├── {stripped[-1]}\n"
            else:
                output += f"{icons[popped['change']['action']]} └── {stripped[-1]}\n"
        else:
            output += f"{icons[popped['change']['action']]} └── {stripped[-1]}\n"

    return pretty_pconsole_diff(x, stripped[:-1], output)


def print_pconsole_details(json_plan, changes):
    pch = pretty_pconsole_diff(changes)
    md = f"### {output[json_plan]['header']} \n" + "```diff\n" + f"{pch}\n" + "```"
    console = Console()
    md = Markdown(md)
    console.print(md)
    print(
        f"{Fore.GREEN}{output[json_plan]['create']} to add,  "
        f"{Fore.CYAN}{output[json_plan]['update']} to change, "
        f"{Fore.RED}{output[json_plan]['delete']} to destroy.\n{Fore.RESET}"
    )


def plans(directory: str, plan_name: str = "tfplan.json") -> list[Path]:
    """
    Recursively find all tfplan files in the given directory and its subdirectories.

    :param directory: The root directory to start the search
    :param plan_name: The name of the plan files to look for (default: "tfplan.json")
    :return: A list of Path objects representing the found plan files
    """
    root_dir = Path(directory)
    tplans = []

    for path in root_dir.rglob(plan_name):
        if path.is_file():
            tplans.append(path)

    return tplans


def convert_tfplan(directory: PurePath, tf_tool: str = "terraform") -> Path:
    """
    Convert Terraform plan to JSON format.

    :param directory: The directory containing the Terraform plan
    :param tf_tool: The Terraform tool to use (default: "terraform")
    :return: Path to the generated JSON file, or None if conversion failed
    """

    tf_plan = (
        Path(directory) / "tfplan"
        if Path(directory / "tfplan").exists()
        else Path(directory) / "tfplan.tfplan"
    )
    tf_plan_json = Path(directory) / "tfplan.json"

    if tf_plan.exists() and tf_plan_json.exists() == False:
        print(f"{Fore.CYAN}❇️ Converting ... {Fore.RESET}")
        try:
            result = subprocess.run(
                [tf_tool, "show", "-json", tf_plan.name],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )

            tf_plan_json.write_text(result.stdout)
            print(f"{Fore.GREEN}✅ Conversion successful.{Fore.RESET}")
            return tf_plan_json

        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error converting tfplan: {e}")
            print(f"Error output: {e.stderr} {Fore.RED}")
            return None
    else:
        print(f"⚠️ Terraform plan file not found: {tf_plan}")
        return None


def print_routine(p: Path, tf_tool, use_md: bool = False):
    """Print routine steps.

    :param p:
    :param tf_tool:
    :param use_md:
    :return:
    """
    name = Path(p).name
    convert_tfplan(directory=p, tf_tool=tf_tool)
    get_plan_results(directory=p, plan_name="tfplan.json")
    pretty_pconsole_table(json_plans=output)

    ch = output[name]["changes"]
    ch2 = ch.copy()

    print_pconsole_details(name, ch2)
    # print_plan_details(w, output[w]['changes'])
    if use_md:
        table_content = generate_table_string(json_plans=output)
        plan_details = generate_plan_details(
            json_plan=p.name, changes=output[name]["changes"]
        )
        print(table_content)
        content = table_content + "\n" + plan_details
        save_summary_to_file(filename="Summary.md", content=content)


def recursive_convert(
    directory, tf_tool="terraform", use_md: bool = False, mood="recursive"
):
    """
    Recursive convert TF plan according to the tool selected.


    :param mood:
    :param use_md:
    :param tf_tool:
    :param directory:

    :return:
    """
    if (
        os.path.exists(f"{directory}/tfplan")
        or os.path.exists(f"{directory}/tfplan.tfplan")
    ) and mood == "local":
        print_routine(p=directory, tf_tool=tf_tool, use_md=use_md)

    ls_dir = os.listdir(PurePath(directory))

    for ld in ls_dir:
        nested_dir = os.path.join(directory, ld)
        if os.path.isdir(nested_dir) and not ld.startswith("."):
            logging.info(f"Finding a folder {ld}...")
            print(f"Finding a folder {ld}...")
            recursive_convert(nested_dir, tf_tool=tf_tool, use_md=use_md)
            p = Path(f"{nested_dir}")
            if os.path.exists(f"{p}/tfplan") or os.path.exists(f"{p}/tfplan.tfplan"):
                print(
                    f"⚠️{Fore.GREEN}Find terraform plan in {nested_dir} ...\n❇️ Scanning ... "
                    + Fore.RESET
                )

                print_routine(p=p, tf_tool=tf_tool, use_md=use_md)
