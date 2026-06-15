"""Organizational Policy Loader — fetches and caches org policy repo."""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".thothcf" / ".policy_cache"


def get_org_policy_path(org_policy: Optional[str] = None) -> Optional[str]:
    """Resolve org policy repo path. Clones/caches if Git URL.

    Resolution:
        1. Explicit --org-policy argument
        2. THOTH_ORG_POLICY env var
        3. None (no org policy)

    Returns:
        Absolute path to cached org policy repo, or None.
    """
    source = org_policy or os.environ.get("THOTH_ORG_POLICY")
    if not source:
        return None

    # If it's already a local path
    if os.path.isdir(source):
        return os.path.abspath(source)

    # Git URL — clone/cache
    if _is_git_url(source):
        return _clone_or_pull(source)

    return None


def resolve_rules_dir(org_path: str) -> Optional[str]:
    """Get the rules/ directory from an org policy repo."""
    rules_dir = os.path.join(org_path, "rules")
    return rules_dir if os.path.isdir(rules_dir) else None


def resolve_policy_dir(org_path: str) -> Optional[str]:
    """Get the policy/ directory (OPA/Rego) from an org policy repo."""
    # Check policy/ first, then shared/policy/ (common convention)
    for candidate in ["policy", os.path.join("shared", "policy")]:
        policy_dir = os.path.join(org_path, candidate)
        if os.path.isdir(policy_dir):
            return policy_dir
    return None


def _is_git_url(value: str) -> bool:
    return value.startswith(("https://", "git@", "ssh://", "git://"))


def _clone_or_pull(repo_url: str) -> Optional[str]:
    """Clone or update a Git repo to local cache."""
    try:
        import git
    except ImportError:
        logger.error("GitPython required. Install: pip install gitpython")
        return None

    # Parse optional @ref
    ref = None
    if "@" in repo_url and not repo_url.startswith("git@"):
        repo_url, ref = repo_url.rsplit("@", 1)
    elif repo_url.startswith("git@") and repo_url.count("@") > 1:
        repo_url, ref = repo_url.rsplit("@", 1)

    url_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
    cache_path = CACHE_DIR / url_hash
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if (cache_path / ".git").exists():
            repo = git.Repo(cache_path)
            repo.remotes.origin.fetch()
            if ref:
                repo.git.checkout(ref)
            else:
                repo.remotes.origin.pull()
        else:
            kwargs = {"depth": 1} if not ref else {}
            repo = git.Repo.clone_from(repo_url, cache_path, **kwargs)
            if ref:
                repo.git.checkout(ref)

        return str(cache_path)
    except Exception as e:
        logger.error(f"Failed to clone org policy repo: {e}")
        return None
