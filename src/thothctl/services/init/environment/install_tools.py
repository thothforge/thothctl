"""Install tool required for development using custom framework and opensource tools."""
import logging
import sys

import inquirer
import os
from colorama import Fore

from ...check.environment.check_environment import (
    get_tool_version,
    get_tools_name,
    load_tools,
)


def check_result(result, tool, version=""):
    """
    Check result of installation.

    :param result:
    :param tool:
    :param version:
    :return:
    """
    if result == 0:
        print(
            f"{Fore.MAGENTA}✅   {tool} was installed successfully {version}{Fore.RESET}"
        )
    else:
        sys.exit(f"{Fore.RED}❌   Error Installing {tool} {version}{Fore.RESET}")


# Linux installation
def install_tfswich():
    """
    Install TFSwich.

    :return:
    """
    print(f"{Fore.MAGENTA}Installing TFSwitch latest Version {Fore.RESET}")
    _exit = os.system(
        "curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | sudo bash"
    )
    check_result(result=_exit, tool="tfswitch")

    command = "tfswitch --version"
    _exit = os.system(command)

    if _exit == 0:
        print(f"{Fore.MAGENTA}✅   TFSwitch was installed successfully {Fore.RESET}")
    else:
        sys.exit(f"{Fore.RED}❌   Error Installing TFSwitch {Fore.RESET}")


def install_terraform_linux(version):
    """
    Install terraform tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA} Installing Terraform latest Version {Fore.RESET}")

    print(f"{Fore.MAGENTA}✅   Terraform already was installed {Fore.RESET}")
    print(f"{Fore.MAGENTA}✅   Changing to recommended version {Fore.RESET}")
    install_tfswich()
    command = f"sudo tfswitch {version}"
    _exit = os.system(command)
    check_result(result=_exit, tool="Terraform", version=version)

    os.system(
        "mkdir -p $HOME/.terraform.d/plugin-cache && echo 'plugin_cache_dir   = \"$HOME/.terraform.d/plugin-cache\"' > ~/.terraformrc"
    )


def install_terragrunt(version):
    """
    Install terragrunt.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing terragrunt {version}{Fore.RESET}")
    _exit = os.system(
        f"wget https://github.com/gruntwork-io/terragrunt/releases/download/v{version}/terragrunt_linux_amd64 -q \
     && sudo mv terragrunt_linux_amd64 /usr/local/bin/terragrunt \
     && sudo chmod +x /usr/local/bin/terragrunt"
    )

    check_result(result=_exit, tool="Terragrunt", version=version)


def install_tfsec(version):
    """
    Install tfsec tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing Tfsec {version}{Fore.RESET}")
    _exit = os.system(
        f"wget https://github.com/aquasecurity/tfsec/releases/download/v{version}/tfsec-linux-amd64 \
      && sudo mv tfsec-linux-amd64 /usr/local/bin/tfsec \
      && sudo chmod +x /usr/local/bin/tfsec \
      && tfsec --version"
    )

    check_result(result=_exit, tool="tfsec", version=version)


def install_terraform_docs(version):
    """
    Install terraform docs.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing Terraform-docs {version}{Fore.RESET}")
    _exit = os.system(
        f"curl -sSLo ./terraform-docs.tar.gz https://terraform-docs.io/dl/v{version}/terraform-docs-v{version}-Linux-amd64.tar.gz \
    && tar -xzf terraform-docs.tar.gz \
    && rm -rf terraform-docs.tar.gz \
    && chmod +x terraform-docs \
    && sudo mv terraform-docs /usr/local/bin/terraform-docs  && terraform-docs --version "
    )

    check_result(result=_exit, tool="Terraform-docs", version=version)


def install_terramate(version):
    """
    Install terrramate tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing Terramate {version}{Fore.RESET}")
    _exit = os.system(
        f"wget https://github.com/mineiros-io/terramate/releases/download/v{version}/terramate_{version}_linux_x86_64.tar.gz \
      && tar -xzf terramate_{version}_linux_x86_64.tar.gz \
      && rm -rf terramate_{version}_linux_x86_64.tar.gz \
      && sudo mv terramate /usr/local/bin/terramate \
      && sudo chmod +x /usr/local/bin/terramate \
      && terramate --version"
    )

    check_result(result=_exit, tool="Terramate", version=version)


def install_trivy(version):
    """
    Install trivy tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing Trivy {version}{Fore.RESET}")

    _exit = os.system(
        "curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo  sh -s -- -b /usr/local/bin \
        && trivy --version"
    )

    if _exit == 0:
        print(
            f"{Fore.MAGENTA}✅ trivy was installed successfully {version}{Fore.RESET}"
        )
    else:
        print(
            "Please Run -> curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin "
        )
        sys.exit(f"{Fore.RED}❌   Error Installing trivy {version}{Fore.RESET}")


def install_snyk():
    """
    Install snyk tool.

    :return:
    """
    print(f"{Fore.MAGENTA}Installing snyk {Fore.RESET}")
    _exit = os.system(
        "sudo curl --compressed https://static.snyk.io/cli/latest/snyk-linux -o snyk && sudo chmod +x ./snyk \
         && sudo mv ./snyk /usr/local/bin/ "
    )

    check_result(result=_exit, tool="snyk")


def install_pre_commit(version):
    """Install precommit tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing pre-commit {version}{Fore.RESET}")
    _exit = os.system(
        f'pip3 install --no-cache-dir --upgrade "pre-commit=={version}" --break-system-packages'
    )

    check_result(result=_exit, tool="pre-commit", version=version)


def install_tflint():
    """Install tflint tool."""
    print(f"{Fore.MAGENTA}Installing tflint {Fore.RESET}")
    _exit = os.system(
        "sudo curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | sudo bash"
    )

    check_result(
        result=_exit,
        tool="tflint",
    )


def install_terraform_compliance(version):
    """Install terraform-compliance tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing terraform-compliance {version}{Fore.RESET}")
    _exit = os.system(
        f'pip3 install --no-cache-dir --upgrade "terraform-compliance=={version}" --break-system-packages'
    )

    check_result(result=_exit, tool="terraform-compliance", version=version)


def install_commitizen(version):
    """
    Install commitizen tool.

    :param version:
    :return:
    """
    print(f"{Fore.MAGENTA}Installing commitizen {version}{Fore.RESET}")
    _exit = os.system(
        f'pip3 install --no-cache-dir --upgrade "commitizen=={version}" --break-system-packages'
    )

    check_result(result=_exit, tool="commitizen", version=version)


# install open tofu
def install_open_tofu():
    """
    Install open tofu.

    :return:
    """
    print(f"{Fore.MAGENTA}Installing open tofu {Fore.RESET}")

    _exit = os.system(
        # Download the installer script:
        "curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh"
        "&& chmod +x install-opentofu.sh "
        "&& ./install-opentofu.sh --install-method deb"
        " && rm install-opentofu.sh"
    )

    check_result(
        result=_exit,
        tool="tofu",
    )


def install_pipx():
    """Install pipx."""
    print(f"{Fore.MAGENTA}Installing pipx {Fore.RESET}")

    _exit = os.system(
        "python3 -m pip3 install pipx && python3 -m pipx ensurepath --break-system-packages"
    )

    check_result(
        result=_exit,
        tool="pipx",
    )


def install_tool(
    tool_name,
    versions,
    version=None,
):
    tool_installers = {
        "pipx": install_pipx,
        "tfswitch": install_tfswich,
        "terraform": lambda: install_terraform_linux(version=versions["terraform"]),
        "terragrunt": lambda: install_terragrunt(version=versions["terragrunt"]),
        "tfsec": lambda: install_tfsec(version=versions["tfsec"]),
        "terraform-docs": lambda: install_terraform_docs(
            version=versions["terraform-docs"]
        ),
        "terramate": lambda: install_terramate(version=versions["terramate"]),
        "pre-commit": lambda: install_pre_commit(version=versions["pre-commit"]),
        "terraform-compliance": lambda: install_terraform_compliance(
            version=versions["terraform-compliance"]
        ),
        "tflint": install_tflint,
        "commitizen": lambda: install_commitizen(version=versions["commitizen"]),
        "open-tofu": install_open_tofu,
        # "trivy": lambda: install_trivy(version=versions["trivy"]),
        "snyk": install_snyk,
        "tofu": install_open_tofu,
    }

    if tool_name in tool_installers:
        installer_func = tool_installers[tool_name]
        if version:
            installer_func(version)
        else:
            installer_func()


def install_selected_tools(names, selected_tools, versions):
    """
    Install selected tools.

    :param versions:
    :param selected_tools:
    :param names:

    :return:
    """
    if selected_tools:
        for tn in names:
            if tn in selected_tools:
                install_tool(tool_name=tn, versions=versions)
    else:
        print(f"{Fore.RED}No tools selected!{Fore.RESET}")


def bootstrap_env(so):
    """
    Bootstrap environment.

    Installing tools for dev tasks.
    :param so:
    :return:
    """
    tools = load_tools()
    versions = get_tool_version(tools)
    # ask list of tool to install or upgrade according to recommended version using inquirer library

    # Define the list of choices
    names = get_tools_name(tools)
    names.append("All")
    choices = names

    # Create the checkbox question
    questions = [
        inquirer.Checkbox(
            "tools",
            message="Select tools to install or upgrade",
            choices=choices,
            carousel=True,
        )
    ]

    # Prompt the user with the checkbox question
    answers = inquirer.prompt(questions)

    # Access the selected tools
    selected_tools = answers["tools"]
    print(f"{Fore.MAGENTA}You selected: {', '.join(selected_tools)}")

    print(f"Installing tools {Fore.RESET}")

    if so == "Linux/Debian":
        os.chdir("/tmp")
        if selected_tools == ["All"]:
            install_pipx()
            install_tfswich()
            install_terraform_linux(versions["terraform"])
            install_terragrunt(version=versions["terragrunt"])
            install_tfsec(version=versions["tfsec"])
            install_terraform_docs(version=versions["terraform-docs"])
            install_terramate(version=versions["terramate"])
            install_pre_commit(version=versions["pre-commit"])
            install_terraform_compliance(version=versions["terraform-compliance"])
            install_tflint()
            install_commitizen(version=versions["commitizen"])
            install_open_tofu()
            install_trivy(version=versions["trivy"])
            install_snyk()
        else:
            logging.debug(f"{names} vs {selected_tools}")
            install_selected_tools(
                names=names, selected_tools=selected_tools, versions=versions
            )

    else:
        sys.exit(
            f"{Fore.RED}❌   Error Installing Tools the  {so} is not supported. Use manual method.{Fore.RESET}"
        )
