"""Create documentation for project."""
import logging
import subprocess
from pathlib import Path
from typing import Optional

import os
from colorama import Fore, init

from .files_content import (
    terraform_docs_content_modules,
    terraform_docs_content_resources,
)


# Initialize colorama for cross-platform color support
init(autoreset=True)


def graph_dependencies(
    directory: Path | str, suffix: str = "resources"
) -> Optional[str]:
    """
    Create dependencies graph using terragrunt.

    Args:
        directory (Union[Path, str]): The directory path to create dependencies graph for
        suffix:  The suffix for removing path from graph svg

    Returns:
        Optional[str]: The command output if successful, None if failed

    Raises:
        subprocess.SubprocessError: If the command execution fails

    """
    try:
        # Convert to Path object if string and resolve path once
        dir_path = Path(directory).resolve()

        # Get required path components
        dir_name = dir_path.name
        full_path = dir_path.absolute()
        replace_path = dir_path.parents[2]

        # Get the project root path dynamically
        project_root = None
        current_path = dir_path
        while current_path != current_path.parent:
            if (current_path / ".git").exists():
                project_root = f"{current_path}/{suffix}"
                break
            current_path = current_path.parent

        # Log directory information
        logging.info("Processing directory: %s", full_path)
        logging.info("Replace path: %s", replace_path)

        print(f"{Fore.GREEN}Creating dependencies graph for {dir_name}{Fore.RESET}")

        # Construct the command as a list for better security and handling
        command = ["terragrunt", "graph-dependencies", "--terragrunt-non-interactive"]

        # Execute the command using subprocess
        try:
            # Change to the target directory
            process = subprocess.Popen(
                command,
                cwd=str(full_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Get the output and process it
            output, error = process.communicate()

            if process.returncode != 0:
                logging.error("Command failed: %s", error)
                return None

            # Process the output through sed-like functionality in Python
            processed_output = output.replace(str(replace_path), "")
            processed_output = processed_output.replace(str(project_root), "")

            # Write to SVG file
            svg_path = full_path / "graph.svg"
            try:
                # Use dot command to generate SVG
                dot_process = subprocess.Popen(
                    ["dot", "-Tsvg"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                )
                svg_content, dot_error = dot_process.communicate(input=processed_output)

                if dot_process.returncode == 0:
                    svg_path.write_text(svg_content)
                    logging.info("Successfully created graph at: %s", svg_path)
                    return svg_content
                else:
                    logging.error("Dot command failed: %s", dot_error)
                    return None

            except subprocess.SubprocessError as e:
                logging.error("Failed to generate SVG: %s", e)
                return None

        except subprocess.SubprocessError as e:
            logging.error("Failed to execute terragrunt command: %s", e)
            return None

    except Exception as e:
        logging.error("Unexpected error: %s", e)
        raise


def create_terraform_docs(directory, mood="resources", t_docs_path=None):
    """
    Create terraform docs file.

    :param directory: The directory to create docs for
    :param mood: The type of documentation to create (default: "resources")
    :param t_docs_path: Custom path for terraform-docs config file
    :return: None
    """
    custom = False
    file = Path("/tmp/.terraform-docs.yml")
    if t_docs_path and isinstance(t_docs_path, (str, os.PathLike)):
        file_path = Path(t_docs_path)
        if file_path.is_file():
            file = Path(t_docs_path).resolve() if Path(t_docs_path).exists() else file
            print(f"{Fore.BLUE}Using custom docs file {t_docs_path}{Fore.RESET}")
            custom = True

    content_map = {
        "resources": terraform_docs_content_resources,
        "modules": terraform_docs_content_modules,
        "local_resource": terraform_docs_content_resources,
        "local_module": terraform_docs_content_modules,
    }

    if mood not in content_map:
        print(f"{Fore.GREEN}{mood} isn't a valid option...{Fore.RESET}")
        return

    print_path = (
        directory.split("modules")[1]
        if "modules" in directory and mood == "modules"
        else directory
    )
    print(f"{Fore.GREEN}Creating terraform docs for {print_path} {Fore.RESET}")

    if custom is False:
        with file.open("w") as fp:
            fp.write(content_map[mood])

    direc = Path(directory).resolve()

    command = f"terraform-docs markdown . --config {file}"
    print(f"{Fore.CYAN}Running {command}{Fore.RESET}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=direc,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"{Fore.GREEN}Command output:{Fore.RESET}")
        print(result.stdout)

        if result.stderr:
            print(f"{Fore.YELLOW}Command stderr:{Fore.RESET}")
            print(result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error occurred while running the command:{Fore.RESET}")
        print(f"Return code: {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")

    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred:{Fore.RESET}")
        print(str(e))


def single_documentation(directory, mood="local_resource", t_docs_path: str = "None"):
    """
    Create single documentation.

    :param t_docs_path: Path for terraform docs file if you are using customizations
    :param directory:
    :param mood:
    :return:
    """
    if (
        os.path.exists(f"{directory}/main.tf")
        and os.path.exists(f"{directory}/terragrunt.hcl")
        or (os.path.exists(f"{directory}/terragrunt.hcl"))
    ) and mood == "local_resource":
        print(
            Fore.GREEN
            + f"⚠️Find terragrunt.hcl file in {directory} ...\n❇️ Creating Documentation ... "
            + Fore.RESET
        )
        graph_dependencies(directory)
    elif os.path.exists(f"{directory}/main.tf") and mood == "local_module":
        print(
            Fore.GREEN
            + f"⚠️Find main.tf file in {directory} ...\n[❇️] Creating Documentation ... "
            + Fore.RESET
        )

    create_terraform_docs(directory, mood=mood, t_docs_path=t_docs_path)


def recursive_documentation(directory, mood="resources", t_docs_path="None"):
    """
    Create documentation recursively for a project.

    :param mood:
    :param directory:
    :param t_docs_path:
    :return:
    """
    logging.info(f"The t_docs: {t_docs_path}")
    ls_dir = os.listdir(directory)

    if directory == "." and ".tf" in str(ls_dir) and mood == "root":
        create_terraform_docs(directory, t_docs_path=t_docs_path)
    elif directory == "." and ".tf" not in str(ls_dir) and mood == "root":
        print(f"{Fore.RED} No .tf files in this folder{Fore.RESET}")

    for d in ls_dir:
        nested_dir = os.path.join(directory, d)
        if os.path.isdir(nested_dir) and not d.startswith("."):
            logging.info(f"Finding a folder {d}...")
            recursive_documentation(nested_dir, mood=mood, t_docs_path=t_docs_path)
            if os.path.exists(f"{nested_dir}/terragrunt.hcl") and mood == "resources":
                print(
                    Fore.GREEN
                    + f"⚠️Find terragrunt.hcl file in {nested_dir} ...\n❇️ Creating Documentation ... "
                    + Fore.RESET
                )
                graph_dependencies(
                    directory=nested_dir,
                )
                create_terraform_docs(
                    directory=nested_dir, mood=mood, t_docs_path=t_docs_path
                )
            elif (
                os.path.exists(f"{nested_dir}/main.tf")
                and "modules" in nested_dir
                and mood == "modules"
            ):
                print(
                    f"{Fore.GREEN}⚠️ Find main.tf file in {nested_dir}\n❇️ Creating documentation ... {Fore.RESET}"
                )

                create_terraform_docs(nested_dir, mood=mood, t_docs_path=t_docs_path)
