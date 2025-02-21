"""thothctl main functions."""
import argparse
import getpass
import logging
import shutil
from pathlib import Path, PurePath

import argcomplete
import click
import os
from colorama import Fore

from .services.check.environment.check_environment import check_environment
from .services.init.environment.install_tools import bootstrap_env
from .services.project.cleanup.clean_project import cleanup_project, remove_projects
from .common.common import (
    create_info_project,
    load_iac_conf,
    print_list_projects,
)
from .services.document.create_documentation import (
    recursive_documentation,
    single_documentation,
)
from .create_inventory.create_inventory import create_inventory
from .create_inventory.update_versions import main_update_versions
from .services.generate.create_template.create_code import create_multiple_repos
from .services.generate.create_template.create_component import create_component
from .services.generate.create_template.create_template import (
    create_project,
    disable_thothctl_integration,
    enable_thothctl_integration,
)
from .create_terramate.create_terramate_stacks import (
    create_terramate_main_file,
    recursive_graph_dependencies_to_json,
)
from .create_terramate.detect_changes_stacks import (
    create_changes_file,
    taint_stack,
)
from .core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
from .core.integrations.azure_devops.pull_request_comments import post_comment_to_azure_devops_pr
from .utils.parser_iac_templates.get_project_data import (
    check_project_properties,
    get_project_props,
    make_template_or_project,
    walk_folder_replace,
)
from .utils.parser_iac_templates.set_project_parameters import set_project_conf, create_idp_doc_main
from .integrate_messages_tools.sent_message_teams import check_reports
from .manage_backend_resources.manage_backend_resources import validate_backend
from .process_terraform.analyze_terraform_plan import recursive_convert
from .process_terraform.process_terraform_file import load_backend
from .process_terraform.graph_terragrunt_dependencies import graph_terragrunt_dependencies
from .scan_and_compliance.compliance_review import (
    create_html_reports,
    recursive_scan,
)
from .sync_workspaces.sync_terraform_workspaces import recursive_sync_workspace
from .sync_workspaces.sync_terragrunt_workspaces import grunt_sync_workspaces
from .validate_project.validate_project_structure import init_check


def init(args):
    """
    Init Options.

    :param args:
    :return:
    """
    project_name = args.project_name
    create_info_project(project_name=project_name)

    if args.reuse_patterns and args.project_name:
        # Fill in with your personal access token and org URL
        org_url = f"https://dev.azure.com/{args.org_name}/"
        print("Pass your Personal Access Token")
        pat = getpass.getpass()
        action = args.remote_actions

        repo_meta = get_pattern_from_azure(
            pat=pat,
            org_url=org_url,
            directory=project_name,
            action=action,
        )
        project_props = get_project_props(
            project_name=project_name,
            cloud_provider="aws",
            remote_bkd_cloud_provider="aws",
            directory=PurePath(f"./{project_name}"),
        )
        working_dir = PurePath(f"./{project_name}")
        # set current directory for working
        os.chdir(working_dir)
        walk_folder_replace(
            directory=PurePath("."),  # PurePath(f"./{project_name}"),
            project_properties=project_props,
            project_name=project_name,
        )
        set_project_conf(
            project_properties=project_props,
            project_name=project_name,
            directory=PurePath("."),  # PurePath(f"./{project_name}"),
            repo_metadata=repo_meta,
        )

    elif args.setup_conf:
        project_props = get_project_props(
            project_name=project_name,
            cloud_provider="aws",
            remote_bkd_cloud_provider="aws",
        )
        set_project_conf(
            project_name=project_name,
            project_properties=project_props,
        )

    else:
        create_project(project_name=project_name, project_type=args.project_type)


def list_projects(args):
    """
    List Options.

    :param args:
    :return:
    """
    if args.list:
        print_list_projects()


def scan(args):
    """
    Scan Options.

    :param args:
    :return:
    """
    if args.tool and args.directory_code:
        logging.info(args)
        tool = args.tool
        directory_code = args.directory_code

        if args.reports_path:
            reports_path = args.reports_path
            if os.path.exists(reports_path):
                print(Fore.GREEN + "Clean up Directory" + Fore.RESET)
                for f in os.listdir(reports_path):
                    os.remove(os.path.join(reports_path, f))

        else:
            reports_path = f"{directory_code}/Reports/{tool}"
            os.makedirs(reports_path, exist_ok=True)

        feature_path = args.feature_path
        recursive_scan(
            directory=directory_code,
            tool=tool,
            reports_dir=reports_path,
            features_dir=feature_path,
            options=args.tool_options,
            tftool=args.tftool
        )
        if args.browser_reports:
            create_html_reports(reports_path, mode=args.browser_reports)
            check_reports(
                directory=reports_path, report_tool=tool, webhook=args.webhook
            )


def document_code(args):
    """
    Document code options.

    :param args:
    :return:
    """
    if args.directory_code:
        mood = args.document_mood
        if args.terraform_docs_file:
            t_docs_path = args.terraform_docs_file
            print(Fore.GREEN + "Using custom docs file " + t_docs_path + Fore.RESET)

        else:
            t_docs_path = None
        if (
                args.document_mood == "modules"
                or args.document_mood == "resources"
                or args.document_mood == "root"
        ):

            recursive_documentation(
                directory=args.directory_code,
                mood=mood,
                t_docs_path=t_docs_path,

            )
        elif (
                args.document_mood == "local_module"
                or args.document_mood == "local_resource"
        ):
            single_documentation(
                directory=args.directory_code, mood=mood, t_docs_path=t_docs_path
            )
        elif args.document_mood == "idp_catalog":
            project_name = load_iac_conf(
                directory=args.directory_code, file_name=".thothcf.toml"
            )["project_properties"]["project"]
            create_idp_doc_main(directory_code= args.directory_code,
                                project_name= project_name,
                                nested=args.nested,

                                )

def transform_code(args):
    """
    Transform code between frameworks.

    :param args:
    :return:
    """
    if args.directory_code and args.init_terramate_project:
        branch = args.branch_name
        logging.info(f"Default branch tool is {branch}")
        create_terramate_main_file(branch)
        recursive_graph_dependencies_to_json(directory=PurePath(args.directory_code))
    elif args.use_terramate_stacks and args.directory_code and args.detect_changes:
        create_changes_file()
        create_changes_file(path_file=PurePath("./common/_main_changes.hcl"))
        taint_stack(args.directory_code, gd_mood=args.diff_mode, base_tag=args.base_tag)


def validate_project(args):
    """
    Validate project.

    :param args:
    :return:
    """
    if args.check_project and args.directory_code:
        custom = False
        if args.framework == "custom":
            custom = True

        init_check(
            directory=args.directory_code,
            mood=args.check_project_mode,
            custom=custom,
            check_type=args.check_project_type,
        )
    elif args.check_env and args.directory_code:
        check_environment()
    elif args.tfplan and args.directory_code:
        recursive_convert(
            directory=PurePath(args.directory_code),
            tf_tool=args.tftool,
            use_md=args.outmd,
            mood=args.validation_mood
        )
    elif args.grunt_dependencies and args.directory_code:
        graph_terragrunt_dependencies(directory=Path(args.directory_code))


def inventory(args):
    """
    Create inventory options.

    :param args:
    :return:
    """
    if args.create_inventory and args.inventory_format:
        if args.inventory_path:
            reports_path = args.inventory_path
            if os.path.exists(reports_path):
                print(Fore.GREEN + "Clean up Directory" + Fore.RESET)
                for f in os.listdir(reports_path):
                    os.remove(os.path.join(reports_path, f))

        else:
            reports_path = PurePath(f"{args.directory_code}/Reports/Inventory")
            os.makedirs(reports_path, exist_ok=True)

        ch_versions = args.check_versions
        create_inventory(
            report_type=args.inventory_format,
            reports_directory=reports_path,
            source_directory=args.directory_code,
            ch_versions=ch_versions,
        )

    if args.update_dependencies and args.directory_code:
        main_update_versions(
            inventory_file=PurePath(args.update_dependencies),
            auto_approve=args.auto_approve,
            action=args.update_action,
        )


def hand_workspaces(args):
    """
    Validate adn  Synchronize backend.

    :param args:
    :return:
    """
    if args.exist_backend and args.directory_code:
        directory_code = args.directory_code
        backend_data = load_backend(f"{directory_code}/common/common.hcl")
        validate_backend(backend_data)
    if args.sync_terraform_workspaces and args.directory_code:
        recursive_sync_workspace(directory=args.directory_code)

    if args.sync_terragrunt_workspaces and args.directory_code:
        grunt_sync_workspaces(directory=args.directory_code)


def automate_task(args):
    """
    Automate tasks for options.

    :param args:
    :return:
    """
    # tasks for project options
    if args.automate_subcommands == "project":
        automate_project_tasks(args)
    # tasks for create code
    elif (
            args.automate_subcommands == "code"
            and args.directory_code
            and args.add_repo
            and args.repo_name
            and args.repo_domain
    ):
        print("enter here Code")
        create_multiple_repos(
            file_hcl="parameters.tf",
            resource_name=args.repo_name,
            domain_pat=args.repo_domain,
            validate_repository_name=args.validate_repository_name,
        )
    elif args.automate_subcommands == "env" and args.bootstrap_env:
        bootstrap_env(args.operation_system)
    elif args.automate_subcommands == "idp":
        automate_idp_tasks(args=args)


def automate_idp_tasks(args):
    """
    Automate idp tasks.

    :param args:
    :return:
    """
    if args.azure_devops and args.directory_code:
        post_comment_to_azure_devops_pr(
            organization_name=args.organization_name,
            project=args.az_project_name,
            repository_name=args.repository_name,
            pull_request_id=args.pull_request_id,
            personal_access_token=args.personal_access_token,
            comment=args.comment
        )



def automate_project_tasks(args):
    """
    Automate task for project.

    :param args:
    :return:
    """
    if args.clean_project and args.directory_code:
        cleanup_project(
            directory=args.directory_code,
            additional_files=args.clean_additional_files,
            additional_folders=args.clean_additional_folders,
        )
    elif (
            args.directory_code
            and args.component_name
            and args.component_type
            and args.add_component
    ):
        create_component(
            code_directory=args.directory_code,
            component_path=args.component_path,
            component_type=args.component_type,
            component_name=args.component_name,
        )
    elif args.handling_template_code and args.directory_code:
        project_props = {}
        project_name = load_iac_conf(
            directory=args.directory_code, file_name=".thothcf.toml"
        )["iacpb"]["project_id"]
        hand_project_type = args.hand_project_type
        if hand_project_type == "terraform":
            if args.hand_template == "make_project" and check_project_properties(
                    directory=args.directory_code
            ):
                project_props = get_project_props(
                    cloud_provider="aws",
                    remote_bkd_cloud_provider="aws",
                )
                set_project_conf(project_properties=project_props)
            walk_folder_replace(
                directory=args.directory_code,
                action=args.hand_template,
                project_properties=project_props,
                project_name=project_name,
            )
        elif hand_project_type == "cdkv2":
            make_template_or_project(
                project_properties=project_props,
                directory=args.directory_code,
                action=args.hand_template,
                project_type=args.hand_project_type,
            )
    elif args.remove_project is not None:
        remove_projects(project_name=args.remove_project)

    elif args.directory_code and args.activate_thothctl_integration:
        enable_thothctl_integration(directory=args.directory_code)

    elif args.directory_code and args.deactivate_thothctl_integration:
        disable_thothctl_integration(directory=args.directory_code)

"""
# src/thothctl/cli.py
import os
import click
import importlib.util
from pathlib import Path


class ThothCLI(click.MultiCommand):
    def list_commands(self, ctx):
        commands = []
        commands_folder = os.path.join(os.path.dirname(__file__), "commands")

        try:
            for item in os.listdir(commands_folder):
                if os.path.isdir(os.path.join(commands_folder, item)) and not item.startswith('_'):
                    commands.append(item)
        except OSError as e:
            print(f"Error listing commands: {e}")
            return []

        commands.sort()
        return commands

    def get_command(self, ctx, cmd_name):
        try:
            # Construct the full path to the cli.py file
            commands_folder = os.path.join(os.path.dirname(__file__), "commands")
            module_path = os.path.join(commands_folder, cmd_name, "cli.py")

            # Load the module directly from the file path
            spec = importlib.util.spec_from_file_location(
                f"thothctl.commands.{cmd_name}.cli",
                module_path
            )
            if spec is None or spec.loader is None:
                print(f"Could not load spec for {module_path}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return module.cli
        except Exception as e:
            print(f"Debug - Error loading command {cmd_name}: {str(e)}")
            return None

@click.group(cls=ThothCLI)
def thothctl():
    "ThothForge CLI / The CLI for the Internal Developer Platform"
    pass


if __name__ == "__main__":
    thothctl()
"""
# src/thothctl/cli.py
import click
from pathlib import Path
import importlib.util
from typing import Optional
from functools import wraps

def global_options(f):
    @click.option('--debug', is_flag=True, help='Enable debug mode')
    @click.option('-d', '--code-directory', type=click.Path(exists=True),
                  help='Configuration file path', default= ".")
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper

class ThothCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.is_dir() and not item.name.startswith('_'):
                    commands.append(item.name)
        except Exception as e:
            click.echo(f"Error listing commands: {e}", err=True)
            return []

        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            module_path = Path(__file__).parent / "commands" / cmd_name / "cli.py"

            if not module_path.exists():
                return None

            spec = importlib.util.spec_from_file_location(
                f"thothctl.commands.{cmd_name}.cli",
                str(module_path)
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return getattr(module, 'cli', None)

        except Exception as e:
            click.echo(f"Error loading command {cmd_name}: {e}", err=True)
            return None


@click.command(cls=ThothCLI)
@global_options
@click.pass_context
def cli(ctx, debug, code_directory):
    """ThothForge CLI - The Internal Developer Platform CLI"""
    """Thoth CLI tool"""
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    ctx.obj['CODE_DIRECTORY'] = code_directory


if __name__ == "__main__":
    cli()



