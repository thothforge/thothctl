"""Post comments to GitHub pull requests."""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


def post_comment_to_github_pr(
    token: str,
    repository: str,
    pull_request_number: int,
    comment: str,
) -> bool:
    """
    Post a comment to a GitHub pull request.

    Args:
        token: GitHub personal access token or GITHUB_TOKEN.
        repository: Repository in 'owner/repo' format.
        pull_request_number: PR number.
        comment: Markdown content to post.

    Returns:
        True if comment was posted successfully.

    Raises:
        ValueError: If required parameters are missing.
    """
    url = f"https://api.github.com/repos/{repository}/issues/{pull_request_number}/comments"
    data = json.dumps({"body": comment}).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        method="POST",
    )

    try:
        response = urllib.request.urlopen(req)
        if response.status == 201:
            logger.info(f"GitHub PR comment posted successfully to {repository}#{pull_request_number}")
            return True
        else:
            logger.error(f"Unexpected response status: {response.status}")
            return False
    except urllib.error.HTTPError as e:
        logger.error(f"GitHub API error: {e.code} - {e.read().decode()}")
        raise
