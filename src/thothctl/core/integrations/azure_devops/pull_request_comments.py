"""Post comments to Azure DevOps pull requests."""
import logging
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

logger = logging.getLogger(__name__)


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
        organization_name: Azure DevOps organization name.
        personal_access_token: PAT for authentication.
        project: Project name.
        repository_name: Repository name.
        pull_request_id: PR ID.
        comment: Markdown content to post.

    Returns:
        The created thread object.

    Raises:
        ValueError: If the repository is not found.
    """
    credentials = BasicAuthentication("", personal_access_token)
    connection = Connection(
        base_url=f"https://dev.azure.com/{organization_name}",
        creds=credentials,
    )

    git_client = connection.clients.get_git_client()
    repositories = git_client.get_repositories(project)

    repository_id = next(
        (repo.id for repo in repositories if repo.name == repository_name),
        None,
    )
    if not repository_id:
        raise ValueError(f"Repository '{repository_name}' not found.")

    thread = {
        "comments": [
            {"parentCommentId": 0, "content": comment, "commentType": 1}
        ],
        "status": 1,
    }

    created_thread = git_client.create_thread(
        thread, repository_id, pull_request_id, project
    )

    if created_thread:
        logger.info(f"PR comment posted successfully (thread {created_thread.id})")
    else:
        logger.error("Failed to post PR comment — created_thread is None")

    return created_thread
