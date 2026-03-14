"""VCS-agnostic PR comment publisher.

Detects CI environment, resolves credentials, formats results,
and delegates to VCS-specific integrations (azure_devops, github).
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum comment sizes per platform (characters)
MAX_COMMENT_SIZE_GITHUB = 65_536
MAX_COMMENT_SIZE_AZURE_DEVOPS = 150_000

TRUNCATION_NOTICE = "\n\n---\n⚠️ *Output truncated — exceeded maximum comment size.*"

# CI environment variable mappings
AZURE_PIPELINES_VARS = {
    "org": "SYSTEM_TEAMFOUNDATIONCOLLECTIONURI",
    "project": "SYSTEM_TEAMPROJECT",
    "repo": "BUILD_REPOSITORY_NAME",
    "pr_id": "SYSTEM_PULLREQUEST_PULLREQUESTID",
    "pat": "AZURE_DEVOPS_PAT",
}

GITHUB_ACTIONS_VARS = {
    "token": "GITHUB_TOKEN",
    "repo": "GITHUB_REPOSITORY",
    "ref": "GITHUB_REF",
}


def detect_ci_environment() -> Optional[str]:
    """Detect VCS provider from CI environment variables.

    Returns:
        'azure_repos', 'github', or None if not in a CI environment.
    """
    if os.environ.get(AZURE_PIPELINES_VARS["org"]):
        return "azure_repos"
    if os.environ.get("GITHUB_ACTIONS"):
        return "github"
    return None


def _truncate_comment(content: str, max_size: int) -> str:
    """Truncate content to fit within platform comment size limits."""
    if len(content) <= max_size:
        return content
    truncated = content[: max_size - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
    logger.warning(
        f"Comment truncated from {len(content)} to {len(truncated)} characters "
        f"(limit: {max_size})"
    )
    return truncated


def format_check_results(result_file: str) -> str:
    """Read a markdown result file and wrap it with a thothctl header.

    Args:
        result_file: Path to the markdown output file.

    Returns:
        Formatted markdown string ready for PR comment.
    """
    path = Path(result_file)
    if not path.exists():
        logger.warning(f"Result file not found: {result_file}")
        return ""

    content = path.read_text()
    return (
        "## 🔍 ThothCTL Check Results\n\n"
        f"{content}\n\n"
        "---\n"
        "*Posted by [ThothCTL](https://github.com/thothforge/thothctl)*"
    )


def publish_to_pr(
    content: str,
    vcs_provider: str = "auto",
    space: Optional[str] = None,
) -> bool:
    """Publish markdown content as a PR comment.

    Args:
        content: Markdown-formatted content to post.
        vcs_provider: 'azure_repos', 'github', or 'auto' (detect from env).
        space: Optional space name to load encrypted credentials from.

    Returns:
        True if the comment was posted successfully.
    """
    if vcs_provider == "auto":
        vcs_provider = detect_ci_environment()

    if not vcs_provider:
        logger.warning("No CI/CD environment detected. Skipping PR comment.")
        return False

    if vcs_provider == "azure_repos":
        content = _truncate_comment(content, MAX_COMMENT_SIZE_AZURE_DEVOPS)
        return _publish_azure_devops(content, space)
    elif vcs_provider == "github":
        content = _truncate_comment(content, MAX_COMMENT_SIZE_GITHUB)
        return _publish_github(content)

    logger.warning(f"PR comments not supported for provider: {vcs_provider}")
    return False


def _resolve_azure_credentials(space: Optional[str]) -> dict:
    """Resolve Azure DevOps credentials from env vars and optional space.

    Priority: environment variables > space credentials.
    """
    org_url = os.environ.get(AZURE_PIPELINES_VARS["org"], "")
    creds = {
        "org_name": org_url.rstrip("/").split("/")[-1] if org_url else "",
        "pat": os.environ.get(AZURE_PIPELINES_VARS["pat"], ""),
        "project": os.environ.get(AZURE_PIPELINES_VARS["project"], ""),
        "repo": os.environ.get(AZURE_PIPELINES_VARS["repo"], ""),
        "pr_id": os.environ.get(AZURE_PIPELINES_VARS["pr_id"], ""),
    }

    # Fallback to space credentials for org_name and pat
    if space and (not creds["pat"] or not creds["org_name"]):
        try:
            from thothctl.utils.crypto import get_credentials_with_password

            space_creds, _ = get_credentials_with_password(space, "vcs")
            if space_creds.get("type") == "azure_repos":
                creds["pat"] = creds["pat"] or space_creds.get("pat", "")
                creds["org_name"] = creds["org_name"] or space_creds.get("organization", "")
        except Exception as e:
            logger.warning(f"Could not load space credentials: {e}")

    return creds


def _publish_azure_devops(content: str, space: Optional[str] = None) -> bool:
    """Delegate to azure_devops/pull_request_comments.py."""
    from ..azure_devops.pull_request_comments import post_comment_to_azure_devops_pr

    creds = _resolve_azure_credentials(space)

    required = ["org_name", "pat", "project", "repo", "pr_id"]
    missing = [k for k in required if not creds.get(k)]
    if missing:
        logger.error(
            f"Missing Azure DevOps context: {', '.join(missing)}. "
            "Set env vars: SYSTEM_TEAMFOUNDATIONCOLLECTIONURI, SYSTEM_TEAMPROJECT, "
            "BUILD_REPOSITORY_NAME, SYSTEM_PULLREQUEST_PULLREQUESTID, AZURE_DEVOPS_PAT"
        )
        return False

    try:
        post_comment_to_azure_devops_pr(
            organization_name=creds["org_name"],
            personal_access_token=creds["pat"],
            project=creds["project"],
            repository_name=creds["repo"],
            pull_request_id=int(creds["pr_id"]),
            comment=content,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to post Azure DevOps PR comment: {e}")
        return False


def _resolve_github_pr_number() -> Optional[str]:
    """Extract PR number from GITHUB_REF (refs/pull/<number>/merge)."""
    ref = os.environ.get(GITHUB_ACTIONS_VARS["ref"], "")
    if "/pull/" in ref:
        return ref.split("/pull/")[1].split("/")[0]
    return os.environ.get("GITHUB_PR_NUMBER")


def _publish_github(content: str) -> bool:
    """Delegate to github/pull_request_comments.py."""
    from ..github.pull_request_comments import post_comment_to_github_pr

    token = os.environ.get(GITHUB_ACTIONS_VARS["token"], "")
    repo = os.environ.get(GITHUB_ACTIONS_VARS["repo"], "")
    pr_number = _resolve_github_pr_number()

    if not all([token, repo, pr_number]):
        logger.error(
            "Missing GitHub PR context. "
            "Set env vars: GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_REF"
        )
        return False

    try:
        return post_comment_to_github_pr(
            token=token,
            repository=repo,
            pull_request_number=int(pr_number),
            comment=content,
        )
    except Exception as e:
        logger.error(f"Failed to post GitHub PR comment: {e}")
        return False
