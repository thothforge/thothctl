"""Get azure devops projects and templates."""
import shutil

import git
import inquirer
import os
from azure.devops.connection import Connection
from colorama import Fore
from msrest.authentication import BasicAuthentication

from .pattern_names import allowed_patterns_names, allowed_patterns_names_end


def create_connection(personal_access_token, organization_url):
    """
    Create azure devops connection.

    :param personal_access_token:
    :param organization_url:
    :return:
    conn
    """
    # Create a connection to the org
    print(f"{Fore.MAGENTA}Establishing connection...")
    credentials = BasicAuthentication("", personal_access_token)
    connection = Connection(base_url=organization_url, creds=credentials)

    return connection


def get_repos_patterns(
    project_name, git_client, allowed_pattern_names, allowed_pattern_names_end
):
    """
    Get repositories based on patterns.

    :param allowed_pattern_names_end:
    :param allowed_pattern_names:
    :param project_name:
    :param git_client:
    :return:
    """
    repos_response = git_client.get_repositories(project=project_name)
    print(Fore.GREEN + "\nPatterns available: " + Fore.RESET)

    repos = []

    for r in repos_response:
        if any(r.name.startswith(f) for f in allowed_pattern_names) and any(
            r.name.endswith(f) for f in allowed_pattern_names_end
        ):
            repos.append({"Name": r.name, "RemoteUrl": r.remote_url})

    if len(repos) > 0:
        return repos
    else:
        print(
            f"{Fore.RED} No repositories available for reuse in this project. 😥 {Fore.RESET}"
        )
        exit()


def get_latest_tag_info(repo: git.Repo) -> tuple[str, str]:
    """
    Get the latest tag information from repository.

    Args:
        repo: Git repository object

    Returns:
        tuple: (tag_name, commit_sha)
    """
    try:
        tags = list(repo.tags)
        if not tags:
            main_commit = repo.rev_parse("origin/main")
            return "", main_commit.hexsha

        latest_tag = tags[-1]
        tag_name = latest_tag.name if hasattr(latest_tag, "name") else str(latest_tag)
        commit_sha = latest_tag.commit.hexsha

        return tag_name, commit_sha
    except Exception as e:
        print(
            f"{Fore.YELLOW}Warning: Error processing tags: {e}. Falling back to main branch.{Fore.RESET}"
        )
        main_commit = repo.rev_parse("origin/main")
        return "", main_commit.hexsha


def clone_repo(
    git_client,
    project_name,
    path="test",
):
    """
    Clone repositories.

    :param git_client:
    :param path:
    :param project_name:
    :return:
    """
    repositories = get_repos_patterns(
        project_name=project_name,
        git_client=git_client,
        allowed_pattern_names=allowed_patterns_names,
        allowed_pattern_names_end=allowed_patterns_names_end,
    )
    repository_names = [r["Name"] for r in repositories]
    questions = [
        inquirer.List(
            "repository",
            message=f"{Fore.GREEN} Select a pattern to reuse: {Fore.RESET} 🔍 ",
            choices=repository_names,
        ),
    ]
    tmp_repo = inquirer.prompt(questions)
    repository_name = tmp_repo["repository"]
    repository = [r for r in repositories if r["Name"] == repository_name][0]
    print(
        f"{Fore.GREEN}\nThe pattern is: \n{repository_name} ➡️ {repository['RemoteUrl']} "
    )

    print(f"{Fore.YELLOW}✨ Cloning repository {Fore.RESET}")

    repo = git.Repo.clone_from(url=repository["RemoteUrl"], to_path=path)

    # List all available tags
    tag, sha = get_latest_tag_info(repo)
    # Get the SHA of main branch

    if tag:
        print(f"{Fore.GREEN}✨ Latest tag: {tag} {Fore.RESET}")
    else:
        print(f"{Fore.YELLOW}No tags found. Using main branch.{Fore.RESET}")

    print("❗ Clean up metadata ... ")
    # Get repositories
    g_path = os.path.join(path, ".git")
    shutil.rmtree(g_path)
    git.Repo.init(path=path, mkdir=False)

    print(
        f"{Fore.GREEN}✨ Template is almost ready for project {path} 🧑🏽‍💻! {Fore.RESET}"
    )
    repo_meta = {
        "repo_name": repository["Name"],
        "repo_url": repository["RemoteUrl"],
        "commit": f"{sha}".replace('"', "'"),
        "tag": tag,
    }

    return repo_meta


def get_pattern_from_azure(pat, org_url, action="list", directory="lab"):
    """
    Get patterns from azure devops.

    :param pat:
    :param org_url:
    :param action:
    :param directory:
    :return:
    """
    # Get a client (the "core" client provides access to projects, teams, etc)
    conn = create_connection(personal_access_token=pat, organization_url=org_url)
    core_client = conn.clients.get_core_client()

    # Get the first page of projects
    get_projects_response = core_client.get_projects()

    projects = []
    print(f"{Fore.GREEN}You have access to the following projects:{Fore.RESET}\n")

    for project in get_projects_response:
        projects.append(project.name)

    git_client = conn.clients.get_git_client()
    try:
        questions = [
            inquirer.List(
                "project",
                message=f"{Fore.GREEN} What is the templates project?",
                choices=projects,
            ),
        ]
        tmp_project = inquirer.prompt(questions)
        project_name = tmp_project["project"]
        print(f"{Fore.GREEN} ✅  {project_name} was selected. {Fore.RESET}")

        if action == "list":
            get_repos_patterns(
                project_name=project_name,
                git_client=git_client,
                allowed_pattern_names=allowed_patterns_names,
                allowed_pattern_names_end=allowed_patterns_names_end,
            )
        elif action == "reuse":
            repo_meta = clone_repo(
                project_name=project_name, git_client=git_client, path=directory
            )
            return repo_meta

    except ValueError:
        print(f"{Fore.RED}❌ Something happen. {Fore.RESET}")
