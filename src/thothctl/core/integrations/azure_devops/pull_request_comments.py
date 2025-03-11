"""Create pull request comment"""
from azure.devops.connection import Connection
from colorama import Fore
from msrest.authentication import BasicAuthentication


def post_comment_to_azure_devops_pr(
    organization_name: str,
    personal_access_token: str,
    project: str,
    repository_name: str,
    pull_request_id: int,
    comment: str,
) -> dict:
    """
    Post a comment to an Azure DevOps pull request.

    Args:
    organization_url (str): The URL of the Azure DevOps organization.
    personal_access_token (str): The personal access token for authentication.
    project (str): The name of the project.
    repository_name (str): The name of the repository.
    pull_request_id (int): The ID of the pull request.
    comment (str): The content of the comment to be posted.

    Returns:
    dict: The created thread information.

    Raises:
    ValueError: If the repository is not found.
    Exception: For any other errors during the process.
    """
    try:
        print(f"{Fore.CYAN}🤖 Posting comment to Azure DevOps... {Fore.RESET}")
        # Create a connection to the Azure DevOps organization
        credentials = BasicAuthentication("", personal_access_token)
        connection = Connection(
            base_url=f"https://dev.azure.com/{organization_name}", creds=credentials
        )

        # Get a client for the Git API
        git_client = connection.clients.get_git_client()

        # List repositories in the project
        repositories = git_client.get_repositories(project)

        # Find the repository ID based on the repository name
        repository_id = next(
            (repo.id for repo in repositories if repo.name == repository_name), None
        )

        if not repository_id:
            raise ValueError(f"Repository '{repository_name}' not found.")

        # Create the comment thread
        # Create the comment
        thread = {
            "comments": [{"parentCommentId": 0, "content": comment, "commentType": 1}],
            "status": 1,
        }

        # Post the comment to the pull request
        created_thread = git_client.create_thread(
            thread, repository_id, pull_request_id, project
        )
        if created_thread:
            print(f"{Fore.CYAN}☑️ Comment posted successfully. {Fore.RESET}")
            # You can access more details about the created thread if needed
            # For example: print(f"Thread ID: {created_thread.id}")
        else:
            print(
                f"{Fore.RED}📛 Failed to post comment. The created_thread is None. {Fore.RESET}"
            )
        return created_thread

    except ValueError as ve:
        raise ve
    except Exception as e:
        raise Exception(f"An error occurred while posting the comment: {str(e)}")
