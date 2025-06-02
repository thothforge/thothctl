"""Get GitHub projects and templates."""
import os
import shutil
import git
import inquirer
import requests
from colorama import Fore
from ..pattern_names  import allowed_pattern_prefixes, allowed_pattern_suffixes


def create_connection(token):
    """
    Create GitHub API connection.

    :param token: GitHub personal access token
    :return: Session with authorization
    """
    print(f"{Fore.MAGENTA}Establishing GitHub connection...")
    session = requests.Session()
    session.headers.update({
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    })
    return session


def get_repos_patterns(session, username, allowed_pattern_prefixes, allowed_pattern_suffixes):
    """
    Get repositories based on patterns.

    :param session: GitHub API session
    :param username: GitHub username or organization
    :param allowed_pattern_prefixes: List of allowed repository name prefixes
    :param allowed_pattern_suffixes: List of allowed repository name suffixes
    :return: List of matching repositories
    """
    # First try to get repos from an organization
    url = f"https://api.github.com/orgs/{username}/repos"
    response = session.get(url)
    
    # If not found, try as a user
    if response.status_code != 200:
        url = f"https://api.github.com/users/{username}/repos"
        response = session.get(url)
        
    if response.status_code != 200:
        print(f"{Fore.RED}Error accessing GitHub repositories: {response.status_code} - {response.text}{Fore.RESET}")
        return []
        
    repos_data = response.json()
    print(Fore.GREEN + "\nPatterns available: " + Fore.RESET)

    repos = []
    for repo in repos_data:
        if any(repo['name'].startswith(prefix) for prefix in allowed_pattern_prefixes) and \
           any(repo['name'].endswith(suffix) for suffix in allowed_pattern_suffixes):
            repos.append({
                "Name": repo['name'],
                "RemoteUrl": repo['clone_url'],
                "Description": repo.get('description', '')
            })

    if len(repos) > 0:
        return repos
    else:
        print(f"{Fore.RED} No repositories available for reuse in this project. 😥 {Fore.RESET}")
        return []


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
    session,
    username,
    path="test",
    allowed_pattern_prefixes=None,
    allowed_pattern_suffixes=None,
):
    """
    Clone repositories.

    :param session: GitHub API session
    :param username: GitHub username or organization
    :param path: Path to clone to
    :param allowed_pattern_prefixes: List of allowed repository name prefixes
    :param allowed_pattern_suffixes: List of allowed repository name suffixes
    :return: Repository metadata
    """
    if allowed_pattern_prefixes is None:
        allowed_pattern_prefixes = ["template-", "pattern-", "poc-"]
    
    if allowed_pattern_suffixes is None:
        allowed_pattern_suffixes = ["-template", "-pattern", "-poc", ""]
        
    repositories = get_repos_patterns(
        session=session,
        username=username,
        allowed_pattern_prefixes=allowed_pattern_prefixes,
        allowed_pattern_suffixes=allowed_pattern_suffixes,
    )
    
    if not repositories:
        return None
        
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


def get_pattern_from_github(token, username, action="list", directory="lab"):
    """
    Get patterns from GitHub.

    :param token: GitHub personal access token
    :param username: GitHub username or organization
    :param action: Action to perform (list or reuse)
    :param directory: Directory to clone to
    :return: Repository metadata if action is reuse, None otherwise
    """
    # Create a session with the token
    session = create_connection(token)
    


    try:
        if action == "list":
            get_repos_patterns(
                session=session,
                username=username,
                allowed_pattern_prefixes=allowed_pattern_prefixes,
                allowed_pattern_suffixes=allowed_pattern_suffixes,
            )
            return None
        elif action == "reuse":
            repo_meta = clone_repo(
                session=session,
                username=username,
                path=directory,
                allowed_pattern_prefixes=allowed_pattern_prefixes,
                allowed_pattern_suffixes=allowed_pattern_suffixes,
            )
            return repo_meta
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {e} {Fore.RESET}")
        return None
