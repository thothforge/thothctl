"""thothctl main functions."""
import argparse
import getpass
import logging
import shutil
from pathlib import Path, PurePath

import argcomplete
import os
from colorama import Fore

from .check_environment.check_environment import check_environment
from .check_environment.install_tools import bootstrap_env
from .cleanup_project.clean_project import cleanup_project, remove_projects
from .common.common import (
    create_info_project,
    load_iac_conf,
    print_list_projects,
)
from .create_documentation.create_documentation import (
    recursive_documentation,
    single_documentation,
)
from .create_inventory.create_inventory import create_inventory
from .create_inventory.update_versions import main_update_versions
from .create_template.create_code import create_multiple_repos
from .create_template.create_component import create_component
from .create_template.create_template import (
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
from .idp.azure_devops.get_azure_devops import get_pattern_from_azure
from .idp.azure_devops.pull_request_comments import post_comment_to_azure_devops_pr
from .idp.parser_iac_templates.get_project_data import (
    check_project_properties,
    get_project_props,
    make_template_or_project,
    walk_folder_replace,
)
from .idp.parser_iac_templates.set_project_parameters import set_project_conf, create_idp_doc_main
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
from .version import __version__
from .wellcome_banner import simple_banner


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


def main():
    """
    Create main menu.

    :return:
    """
    # Initialize parser
    parser = argparse.ArgumentParser(
        prog="thothctl",
        description="Accelerate your deployments with Thothctl - Your CLI Platform Interface.",
        epilog="Thanks for using %(prog)s! ",
        allow_abbrev=True,

    )
    parser.add_argument(
        "-tftool",
        "--tftool",
        help="Set tf tool to manage IaC, you can setup an environment variable TFTOOL=tofu or TFTOOL=terraform",
        default="tofu",
        choices=("terraform", "tofu"),
    )
    # Create subparsers
    subparsers = parser.add_subparsers(
        dest="commands",
        title="Commands",
        help="%(prog)s Commands",
        description="Command and functionalities",
    )

    # Create init subcommand options
    init_parser = subparsers.add_parser(
        name="init",
        description="Initialize project from idp, default template or custom values",
        help="Initialize project, provide project name,"
             "example: %(prog)s init -pj <project-name>",
    )
    sub_init = init_parser.add_argument_group(
        "Init project and handling projects and templates options and flags"
    )
    sub_init.add_argument(
        "-pj",
        "--project_name",
        metavar="PROJECT_NAME",
        help="Initialize project, provide project name",
        required=True,
    )
    sub_init.add_argument(
        "-pjt",
        "--project_type",
        metavar="PROJECT_TYPE",
        help="Provide project type according to Internal Developer Portal and frameworks",
        required=False,
        choices=(
            "terraform",
            "cdkv2",
            "terraform_module",
            "terragrunt_project",
            "custom",
        ),
        default="terraform",
        # TODO include in filters for IDP projects
    )
    sub_init.add_argument(
        "-sp",
        "--setup_conf",
        help="Setup .thothcf.toml for thothctl configuration file",
        action="store_true",
    )

    # Add idp options
    idp_group = init_parser.add_argument_group(
        "Interact with the internal developer platform options and flags"
    )
    idp_group.add_argument(
        "-reuse",
        "--reuse_patterns",
        help="Reuse pattern from external repository. Use with init option",
        action="store_true",
    )
    idp_group.add_argument(
        "-azp",
        "--az_project_name",
        help='Reuse pattern from external repository, default  "CoE DevOps Sophos" '
             "Use with init option, (default: %(default)s)",
        default="CoE DevOps Sophos",
    )
    idp_group.add_argument(
        "-org_name",
        "--org_name",
        help="Organization tool for azure DevOps, (default: %(default)s) "
             "Use with init option",
        default="sophosproyectos",
    )

    idp_group.add_argument(
        "-r_action",
        "--remote_actions",
        help="Action for clone or list repositories or patterns. Values: reuse, clone, (default: %(default)s)\n"
             "Use with init option",
        default="reuse",
        choices=("reuse", "clone"),
    )

    # Create init subcommand options
    scan_parser = subparsers.add_parser(
        name="scan",
        description="Scan code using tools like checkov, tfsec, terraform-compliance",
        help="Scan code using tools example: %(prog)s scan -t checkov ",
    )

    # add scan group
    scan_group = scan_parser.add_argument_group("Scan code options and flags")

    scan_group.add_argument(
        "-s",
        "--scan",
        help="Scan project",
        action="store_true",
    )
    scan_group.add_argument(
        "-t",
        "--tool",
        help="Use this flag for setting the tool of scanning tool. "
             "Allowed values are: tfsec, terraform-compliance or checkov, (default: %(default)s)",
        default="checkov",
        choices=("tfsec", "terraform-compliance", "checkov"),
    )
    scan_group.add_argument(
        "-op",
        "--tool_options",
        help="Use for passing more arguments for your tool. Use with -t option ",
        default=None,
    )

    scan_group.add_argument(
        "-r",
        "--reports_path",
        help="Path for saving scanning reports",
        default=None,
    )
    parser.add_argument(
        "-d",
        "--directory_code",
        help="Root path for code project (default: %(default)s)",
        default=".",
    )
    scan_group.add_argument(
        "-b",
        "--browser_reports",
        help="Use if you want create a html reports, if you select xunit you must have installed xunit-viewer (npm -g install xunit-viewer),"
             " (default: %(default)s)",
        default="single",
        choices=("single", "xunit"),
    )
    scan_group.add_argument(
        "-m",
        "--messages",
        help="Use this flag to send messages to microsoft teams. "
             "Allowed values are: Teams, (default: %(default)s)",
        default=None,
        choices=("Teams",),
    )
    scan_group.add_argument(
        "-w",
        "--webhook",
        help="Webhook url for Microsoft Teams channel, (default: %(default)s)",
        default="",
    )
    scan_group.add_argument(
        "-f",
        "--feature_path",
        help="The feature path for terraform-compliance, (default: %(default)s)",
        default="",
    )
    # add documentation group
    # Create doc subcommand options
    doc_parser = subparsers.add_parser(
        name="doc",
        description="Create and document IaC using terraform-docs",
        help="Create and document IaC using terraform-docs"
             "example: %(prog)s doc -d . -dm local_module ",
    )

    doc_group = doc_parser.add_argument_group("Documentation options and flags")
    doc_group.add_argument(
        "-c",
        "--create_documentation",
        help="Create code documentation base in terraform docs",
        action="store_true",
    )
    doc_group.add_argument(
        "-dm",
        "--document_mood",
        help="Activate documentation mood for modules or resources, "
             "available values: root, modules, resources, local_resource, local_module, (default: %(default)s)",
        default="resources",
        choices=("modules", "resources", "local_resource", "local_module", "root", "idp_catalog"),
    )
    doc_group.add_argument(
        "-tdcs",
        "--terraform_docs_file",
        help="Use to indicate the terraform docs config file, for example, ./.terraform-docs.yaml",
    )
    doc_group.add_argument(
        "-nt",
        "--nested",
        help="Use to indicate the document mode to create de catalog doc metadata is in a monorepo o subfolder.",
        action="store_true",
    )

    # Create transform subcommand options
    trans_parser = subparsers.add_parser(
        name="transform",
        description="Handling and transformer code to move and add metadata from terragrunt to terramate",
        help="Transform your code to use terramate and terragrunt together or single"
             "example: %(prog)s -d . -l transform -j -y $main_branch  ",
    )
    # add transform and handling terraform code group
    trans_group = trans_parser.add_argument_group(
        "Handling and transformer code to move and add metadata from terragrunt to terramate "
    )
    trans_group.add_argument(
        "-df",
        "--diff_mode",
        help="Specify the mode for checking differences between commits using terramate"
             "you must pass branch tool if default branch is different from master use -y option, "
             "Valid values are commit, simple_tags or complex_tags, (default: %(default)s)",
        default="commit",
        choices=("commit", "simple_tags", "complex_tags"),
    )
    trans_group.add_argument(
        "-bt",
        "--base_tag",
        help="Specify base tag for checking differences between commits using terramate"
             "you must pass branch tool if default branch is different from master use -y option, (default: %(default)s) ",
        default="v0.0.0",
    )
    trans_group.add_argument(
        "-z",
        "--use_terramate_stacks",
        help="Enable create terramate stack for advance deployments,"
             "you must pass branch tool if default branch is different from master use -y option",
        action="store_true",
    )
    trans_group.add_argument(
        "-x",
        "--detect_changes",
        help="Enable taint resources with identify changes, use with -z option  ",
        action="store_true",
    )
    trans_group.add_argument(
        "-y",
        "--branch_name",
        help="Enable taint resources with identify changes, use with -z option, (default: %(default)s)  ",
        default="master",
    )
    trans_group.add_argument(
        "-j",
        "--init_terramate_project",
        help="Init terramate project use with -z option  ",
        action="store_true",
    )
    # Global options
    parser.add_argument(
        "-v",
        "--version",
        help="Get Version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Create validation project subcommand options
    vald_parser = subparsers.add_parser(
        name="validate",
        description="Validation projects structure",
        help="Check project structure based on default framework or custom framework. For example: %(prog)s validate -cp -d -cm hard ",
    )

    # Add validation project options
    vald_group = vald_parser.add_argument_group(
        "Validation projects structure options and flags"
    )

    vald_group.add_argument(
        "-ch",
        "--check_env",
        help="Check if your environment already have all tools for right framework use",
        action="store_true",
    )
    vald_group.add_argument(
        "-cp",
        "--check_project",
        help="Enable Check project structure and standard practices",
        action="store_true",
    )

    vald_group.add_argument(
        "-cpt",
        "--check_project_type",
        help="Project type to check, ",
        default="project",
        choices=("project", "module"),
    )

    vald_group.add_argument(
        "-fr",
        "--framework",
        help="Specify the IaC framework, use default for Terraform-Terragrunt or custom for other. "
             "\n If custom, you must have a .thothcf.toml file, (default: %(default)s)",
        default="default",
        choices=("default", "custom"),
    )
    vald_group.add_argument(
        "-cm",
        "--check_project_mode",
        help="Check project structure and standard practices, "
             "available values: soft or hard, (default: %(default)s)",
        default="soft",
        choices=("hard", "soft"),
    )
    sub_validate = vald_parser.add_subparsers(
        dest="validate_subcommands",
        title="validate tasks SubCommands",
        help="%(prog)s Commands",
        description="Sub Commands and functionalities for validate Command",
    )
    # Local Environment automate tasks
    sub_validate_terra_parser = sub_validate.add_parser(
        name="terraform",
        help="Automate terraform validation tasks, example: %(prog)s terraform ",
        description="Command for validate terraform plans and another outputs",
    )

    sub_validate_terra_parser.add_argument(
        "-deps",
        "--grunt_dependencies",
        help="Use this flag to view a dependency graph in asccii pretty shell output",
        action="store_true",
    )
    sub_validate_terra_parser.add_argument(
        "-tfplan",
        "--tfplan",
        help="Use this flag to validate your terraform plan",
        action="store_true",
    )
    sub_validate_terra_parser.add_argument(
        "-valmd",
        "--validation_mood",
        help="Use this flag to validate your terraform plan recursively or in one directory.",
        choices=("local", "recursive"),
        default="recursive",
    )

    sub_validate_terra_parser.add_argument(
        "-outmd",
        "--outmd",
        help="Create markdown summary file with plan output",
        action="store_true",
    )

    # Create handling workspaces subcommand options
    wk_ops_parser = subparsers.add_parser(
        name="hand-wk",
        description="Handling workspaces operations",
        help="Handling workspaces operations for example, check if already exists the backend configuration, synchronize for modules and resources according to IaC Framework, "
             "example: %(prog)s hand-wk -sw ",
    )

    # add advance options for other ops
    wk_ops = wk_ops_parser.add_argument_group(
        "Handling workspaces operations options and flags"
    )
    wk_ops.add_argument(
        "-eb",
        "--exist_backend",
        help="Use this flag to validate"
             "backend resources associated with the project.",
        action="store_true",
    )

    # add workspaces operations
    wk_ops.add_argument(
        "-sw",
        "--sync_terraform_workspaces",
        help="Synchronize terraform workspaces for dependencies tree base on terragrunt + terraform framework",
        action="store_true",
    )
    parser.add_argument(
        "-sw",
        "--sync_terraform_workspaces",
        help="Synchronize terraform workspaces for dependencies tree base on terragrunt + terraform framework",
        action="store_true",
    )

    wk_ops.add_argument(
        "-stw",
        "--sync_terragrunt_workspaces",
        help="Synchronize terraform workspaces for dependencies tree when you are using terragrunt",
        action="store_true",
    )

    # Create automation tasks subcommand options
    automate_parser = subparsers.add_parser(
        name="automate",
        description="Automate tasks for resources folders based on your configurations",
        help="Automate tasks for example adding resources folders based on your configurations. \n"
             "Create code component template based on project structure define into .thothcf.toml"
             "example: %(prog)s add -cn test -ct resource -cph ./resources/myresource ",
    )
    sub_automate = automate_parser.add_subparsers(
        dest="automate_subcommands",
        title="Automate tasks SubCommands",
        help="%(prog)s Commands",
        description="Sub Commands and functionalities for Add Command",
    )

    # Local Environment automate tasks
    sub_automate_env_parser = sub_automate.add_parser(
        name="env",
        description="Command for run automate tasks for install tools and prepare your local Environment for Developing",
        help="Automate the boostrap local environment task and more",
    )

    sub_automate_env_group = sub_automate_env_parser.add_argument_group(
        "Sub Commands for environment automate tasks code actions"
    )
    sub_automate_env_group.add_argument(
        "-bv",
        "--bootstrap_env",
        help="Install base tools for you environment.",
        action="store_true",
    )
    sub_automate_env_group.add_argument(
        "-os",
        "--operation_system",
        help="Install base tools for you environment, (default: %(default)s). "
             "Use with --bootstrap_env \nAllowed values: 'Linux/Debian'",
        default="Linux/Debian",
        choices=("Linux/Debian",),
    )
    # Code automate tasks
    sub_automate_parser = sub_automate.add_parser(
        name="code",
        description="add code command for insert some codes into a terraform file",
        help="Automate the code creation for specific use cases",
    )

    sub_automate_group_code = sub_automate_parser.add_argument_group(
        "Sub Commands for adding code actions"
    )
    sub_automate_group_code.add_argument(
        "-arp",
        "--add_repo",
        help="Add repository code",
        action="store_true",
    )

    sub_automate_group_code.add_argument(
        "-vlr",
        "--validate_repository_name",
        help="Validate repository name",
        action="store_true",
    )

    sub_automate_group_code.add_argument(
        "-rn",
        "--repo_name",
        help="Repository name",
    )
    sub_automate_group_code.add_argument(
        "-fhcl", "--file_hcl", help="HCL to insert code name", default="parameters.tf"
    )
    sub_automate_group_code.add_argument(
        "-rdo",
        "--repo_domain",
        help="Repository Domain name where code is hcl is present, according to the project, example: data, terraform_projects ",
    )
    # Create idp subcommand options
    sub_automate_idp_parser = sub_automate.add_parser(
        name="idp",
        description="Task to automate use cases with ci/cd tools, for example, create pull request comments",
        help="Task for interactive use cases with ci/cd tools, for example, create pull request comments "
             "example: %(prog)s automate idp comment azure-repos -pat $$$ -project xproject -pullid 1234 -repname myrepo -comment ",
    )

    # Add group for handling code
    idp_group = sub_automate_idp_parser.add_argument_group(
        "Azure Repos automate tasks"
    )

    # create docs automate for integration with IDP


    idp_auto_sub_parser = sub_automate_idp_parser.add_subparsers(

        dest="automate_idp_subcommands",
        title="Automate idp tasks SubCommands",
        help="%(prog)s Commands",
        description="Sub Commands and functionalities for Add Command",
    )

    # pull request comment command
    comment = idp_auto_sub_parser.add_parser(
        name="comment",
        description="Create pull request comment on Azure DevOps",
        help="Create pull request comment on Azure DevOps, example: %(prog)s automate idp comment -az -pat $$$ -project xproject -pullid 1234 -repname myrepo -comment "
    )
    comment.add_argument(
        "-az",
        "--azure_devops",
        help="Create pull request comment on Azure DevOps",
        action="store_true",
    )
    comment.add_argument(
        "-pat",
        "--personal_access_token",
        help="Azure DevOps personal access token",
        default=None,
    )
    comment.add_argument(
        "-org",
        "--organization_name",
        help="Azure DevOps organization name",
        default=None,
    )
    comment.add_argument(
        "-project",
        "--az_project_name",
        help="Azure DevOps project name",
        default=None,
    )
    comment.add_argument(
        "-pullid",
        "--pull_request_id",
        help="Azure DevOps pull request id",
        default=None,
    )
    comment.add_argument(
        "-repname",
        "--repository_name",
        help="Azure DevOps repository name",
        default=None,
    )
    comment.add_argument(
        "-comment",
        "--comment",
        help="Azure DevOps pull request comment",
        default=None,
    )

    # Create transform subcommand options
    sub_automate_project_parser = sub_automate.add_parser(
        name="project",
        description="Handling code, clean folders, files, and add template resources",
        help="Handling code, clean folders, files, and add template resources, for "
             "example: %(prog)s automate project -cls -cfs file1,file2",
    )

    # Add group for handling code
    project_group = sub_automate_project_parser.add_argument_group(
        "Handling code, clean folders, files, and add template resources"
    )
    project_group.add_argument(
        "-cls",
        "--clean_project",
        help="Clean project, remove .terraform, .terragrunt-cache and tfplan files recursively",
        action="store_true",
    )
    project_group.add_argument(
        "-cfs",
        "--clean_additional_files",
        help="Add folders file to clean specify:  -cfs file_1,file_2",
        default=None,
    )
    project_group.add_argument(
        "-cfd",
        "--clean_additional_folders",
        help="Add folders file to clean specify:  -cfd folder_1,folder_2",
        default=None,
    )

    project_group.add_argument(
        "-rm",
        "--remove_project",
        help="Remove project from .thothcf global config and residual files",
        default=None,
    )

    project_group.add_argument(
        "-eiacpb",
        "--activate_thothctl_integration",
        help="Enable thothctl integration to the project IaC project. "
             "Recreate terragrunt.hcl master file."
             "Be careful This command must run in root project path.",
        action="store_true",
    )
    project_group.add_argument(
        "-diacpb",
        "--deactivate_thothctl_integration",
        help="Disable thothctl integration to the project IaC project."
             "Recreate terragrunt.hcl master file."
             "Be careful This command must run in root project path.",
        action="store_true",
    )

    project_group.add_argument(
        "-add",
        "--add_component",
        help="Add component based on  in .thothcf.toml specifications",
        action="store_true",
    )
    # args for handling project code
    project_group.add_argument(
        "-ht",
        "--hand_template",
        help="Create project template using .thothcf.toml parameters. \n "
             "This action clean the project and set #{values}# in project files for project attributes, (default: %(default)s) ",
        default="make_template",
        choices=("make_template", "make_project"),
    )

    project_group.add_argument(
        "-hd",
        "--handling_template_code",
        help="manipulate the template to convert it into a project or template \n "
             "Example: %(prog)s -hd -ht make_project ",
        action="store_true",
    )
    project_group.add_argument(
        "-hpt",
        "--hand_project_type",
        metavar="PROJECT_TYPE",
        help="Provide project type according to Internal Developer Portal and frameworks",
        required=False,
        choices=(
            "terraform",
            "cdkv2",
        ),
        default="terraform",
        # TODO include in filters for IDP projects
    )

    project_group.add_argument(
        "-cn",
        "--component_name",
        help="Component name for template",
    )
    project_group.add_argument(
        "-ct",
        "--component_type",
        help="Component Type for base template, there are the names for your folder in p_structure.folders field in .thothcf.toml",
    )
    project_group.add_argument(
        "-cph",
        "--component_path",
        help="Component path for base template, for example ./modules",
    )

    # Create Inventory subcommand options
    inv_parser = subparsers.add_parser(
        name="inventory",
        description="Create Inventory for the iac composition.\n",
        help="Create a inventory about IaC modules composition for terraform/tofu projects"
             "example: %(prog)s inventory -ci -if all -check ",
    )

    # add inventory options group
    inv_group = inv_parser.add_argument_group(
        "Create, update and handling inventory options and flags"
    )
    inv_group.add_argument(
        "-ci",
        "--create_inventory",
        help="Create inventory. Create a report with modules and versions",
        action="store_true",
    )
    inv_group.add_argument(
        "-ip",
        "--inventory_path",
        help="Path for saving inventory reports",
        default=None,
    )
    inv_group.add_argument(
        "-if",
        "--inventory_format",
        help="Use with -ci option for create a inventory report. Allowed values: html, json, all, (default: %(default)s)",
        default="json",
        choices=("html", "json", "all"),
    )
    inv_group.add_argument(
        "-check",
        "--check_versions",
        help="Use with -ci option for creating a inventory report.",
        action="store_true",
    )
    inv_group.add_argument(
        "-updep",
        "--update_dependencies",
        help="Pass the inventory json file path for updating dependencies.",
    )
    inv_group.add_argument(
        "-av",
        "--auto_approve",
        help="Use with --update_dependencies option for auto approve updating dependencies.",
        action="store_true",
    )
    inv_group.add_argument(
        "-upact",
        "--update_action",
        help="Use with --update_action option to update or restore versions based "
             "on the inventory json file path for dependencies.",
        choices=("update", "restore"),
        default="update",
    )

    # Logging mode
    parser.add_argument(
        "-verb",
        "--verbose",
        help="Enable debug Mode",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--list",
        help="List projects manage by %(prog)s" "example: %(prog)s --list",
        action="store_true",
    )

    # Read arguments from command line
    args = parser.parse_args()
    # Add autocomplete
    argcomplete.autocomplete(parser)

    log = logging.getLogger("thothctl")

    log.info("thothctl Logs")

    try:
        simple_banner()
        os.putenv("TFTOOL", args.tftool)

        if args.verbose:
            log.setLevel(level=logging.DEBUG)

        if args.commands == "init":
            print(f"👷 {Fore.GREEN}Init project {Fore.RESET}")
            init(args=args)
        elif args.commands == "scan":
            print(f"👷 {Fore.GREEN}Scan Code {Fore.RESET}")
            scan(args=args)
        elif args.commands == "doc":
            print(f"👷 {Fore.GREEN}Document Code {Fore.RESET}")
            document_code(args=args)

        elif args.commands == "transform":
            print(f"👷 {Fore.GREEN}Transform Code {Fore.RESET}")

        elif args.commands == "validate":
            print(f"👷 {Fore.GREEN}Validate {Fore.RESET}")
            validate_project(args=args)

        elif args.commands == "automate":
            print(f"👷 {Fore.GREEN}Automating tasks {Fore.RESET}")
            automate_task(args=args)
        elif args.commands == "inventory":
            print(f"👷 {Fore.GREEN}Create and handling code inventory {Fore.RESET}")
            inventory(args=args)
        elif args.list:
            list_projects(args=args)
        # Temp to sync wk
        if args.sync_terraform_workspaces and args.directory_code:
            recursive_sync_workspace(directory=args.directory_code)
    except KeyboardInterrupt:
        print(Fore.RED + "Interrupted by user" + Fore.RESET)
        if Path(args.project_name).exists():
            shutil.rmtree(args.project_name)
        return 1
    except Exception as err:
        # output error, and return with an error code
        print(Fore.RED + str(err) + Fore.RESET)
    return 0


if __name__ == "__main__":
    main()
