"""Unit tests for the VCS-agnostic PR comment publisher."""

import os
import pytest
import tempfile
from unittest.mock import patch, Mock


class TestDetectCIEnvironment:
    """Test CI environment auto-detection."""

    def test_detects_azure_pipelines(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            detect_ci_environment,
        )

        with patch.dict(os.environ, {"SYSTEM_TEAMFOUNDATIONCOLLECTIONURI": "https://dev.azure.com/org/"}):
            assert detect_ci_environment() == "azure_repos"

    def test_detects_github_actions(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            detect_ci_environment,
        )

        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            # Ensure Azure var is not set
            env = os.environ.copy()
            env.pop("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", None)
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
                    assert detect_ci_environment() == "github"

    def test_returns_none_when_no_ci(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            detect_ci_environment,
        )

        with patch.dict(os.environ, {}, clear=True):
            assert detect_ci_environment() is None


class TestFormatCheckResults:
    """Test markdown formatting."""

    def test_formats_existing_file(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            format_check_results,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| Action | Count |\n|--------|-------|\n| Create | 3 |")
            f.flush()

            result = format_check_results(f.name)

        os.unlink(f.name)

        assert "ThothCTL Check Results" in result
        assert "| Create | 3 |" in result
        assert "thothforge/thothctl" in result

    def test_returns_empty_for_missing_file(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            format_check_results,
        )

        assert format_check_results("/nonexistent/path.md") == ""


class TestTruncateComment:
    """Test comment truncation for platform limits."""

    def test_no_truncation_when_under_limit(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _truncate_comment,
        )

        content = "short comment"
        assert _truncate_comment(content, 65_536) == content

    def test_truncates_when_over_limit(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            TRUNCATION_NOTICE,
            _truncate_comment,
        )

        content = "x" * 70_000
        result = _truncate_comment(content, 65_536)
        assert len(result) <= 65_536
        assert result.endswith(TRUNCATION_NOTICE)

    def test_github_limit_applied_in_publish(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            TRUNCATION_NOTICE,
            publish_to_pr,
        )

        big_content = "x" * 70_000
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_TOKEN": "ghp_fake",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_REF": "refs/pull/1/merge",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "thothctl.core.integrations.github.pull_request_comments.post_comment_to_github_pr",
            return_value=True,
        ) as mock_post:
            publish_to_pr(big_content, vcs_provider="github")

        posted = mock_post.call_args[1]["comment"]
        assert len(posted) <= 65_536
        assert posted.endswith(TRUNCATION_NOTICE)

    def test_azure_limit_applied_in_publish(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        # Content under GitHub limit but we verify Azure uses its own limit
        content = "x" * 100_000
        env = {
            "SYSTEM_TEAMFOUNDATIONCOLLECTIONURI": "https://dev.azure.com/myorg/",
            "SYSTEM_TEAMPROJECT": "proj",
            "BUILD_REPOSITORY_NAME": "repo",
            "SYSTEM_PULLREQUEST_PULLREQUESTID": "42",
            "AZURE_DEVOPS_PAT": "pat123",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "thothctl.core.integrations.azure_devops.pull_request_comments.post_comment_to_azure_devops_pr",
        ) as mock_post:
            publish_to_pr(content, vcs_provider="azure_repos")

        posted = mock_post.call_args[1]["comment"]
        # 100K is under Azure's 150K limit, so no truncation
        assert len(posted) == 100_000


class TestPublishToPR:
    """Test the main publish_to_pr orchestrator."""

    def test_skips_when_no_ci_detected(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        with patch.dict(os.environ, {}, clear=True):
            result = publish_to_pr(content="test", vcs_provider="auto")
            assert result is False

    def test_returns_false_for_unsupported_provider(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        result = publish_to_pr(content="test", vcs_provider="bitbucket")
        assert result is False

    @patch(
        "thothctl.core.integrations.pr_comments.pr_comment_publisher._publish_azure_devops",
        return_value=True,
    )
    def test_routes_to_azure_devops(self, mock_publish):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        result = publish_to_pr(content="md content", vcs_provider="azure_repos", space="my-space")

        assert result is True
        mock_publish.assert_called_once_with("md content", "my-space")

    @patch(
        "thothctl.core.integrations.pr_comments.pr_comment_publisher._publish_github",
        return_value=True,
    )
    def test_routes_to_github(self, mock_publish):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        result = publish_to_pr(content="md content", vcs_provider="github")

        assert result is True
        mock_publish.assert_called_once_with("md content")

    @patch(
        "thothctl.core.integrations.pr_comments.pr_comment_publisher.detect_ci_environment",
        return_value="github",
    )
    @patch(
        "thothctl.core.integrations.pr_comments.pr_comment_publisher._publish_github",
        return_value=True,
    )
    def test_auto_detects_and_routes(self, mock_publish, mock_detect):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            publish_to_pr,
        )

        result = publish_to_pr(content="test", vcs_provider="auto")

        assert result is True
        mock_detect.assert_called_once()


class TestResolveAzureCredentials:
    """Test Azure DevOps credential resolution."""

    def test_resolves_from_env_vars(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_azure_credentials,
        )

        env = {
            "SYSTEM_TEAMFOUNDATIONCOLLECTIONURI": "https://dev.azure.com/myorg/",
            "SYSTEM_TEAMPROJECT": "myproject",
            "BUILD_REPOSITORY_NAME": "myrepo",
            "SYSTEM_PULLREQUEST_PULLREQUESTID": "99",
            "AZURE_DEVOPS_PAT": "secret-pat",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = _resolve_azure_credentials(space=None)

        assert creds["org_name"] == "myorg"
        assert creds["pat"] == "secret-pat"
        assert creds["project"] == "myproject"
        assert creds["repo"] == "myrepo"
        assert creds["pr_id"] == "99"

    def test_falls_back_to_space_credentials(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_azure_credentials,
        )

        space_creds = {"type": "azure_repos", "pat": "space-pat", "organization": "space-org"}

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "thothctl.utils.crypto.get_credentials_with_password",
                return_value=(space_creds, "pw"),
            ):
                creds = _resolve_azure_credentials(space="my-space")

        assert creds["pat"] == "space-pat"
        assert creds["org_name"] == "space-org"

    def test_env_vars_take_priority_over_space(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_azure_credentials,
        )

        space_creds = {"type": "azure_repos", "pat": "space-pat", "organization": "space-org"}
        env = {
            "SYSTEM_TEAMFOUNDATIONCOLLECTIONURI": "https://dev.azure.com/env-org/",
            "AZURE_DEVOPS_PAT": "env-pat",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch(
                "thothctl.utils.crypto.get_credentials_with_password",
                return_value=(space_creds, "pw"),
            ):
                creds = _resolve_azure_credentials(space="my-space")

        assert creds["pat"] == "env-pat"
        assert creds["org_name"] == "env-org"


class TestPublishAzureDevops:
    """Test Azure DevOps publishing delegation."""

    @patch(
        "thothctl.core.integrations.azure_devops.pull_request_comments.post_comment_to_azure_devops_pr"
    )
    def test_delegates_to_integration(self, mock_post):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _publish_azure_devops,
        )

        env = {
            "SYSTEM_TEAMFOUNDATIONCOLLECTIONURI": "https://dev.azure.com/org/",
            "SYSTEM_TEAMPROJECT": "proj",
            "BUILD_REPOSITORY_NAME": "repo",
            "SYSTEM_PULLREQUEST_PULLREQUESTID": "7",
            "AZURE_DEVOPS_PAT": "pat",
        }

        with patch.dict(os.environ, env, clear=True):
            result = _publish_azure_devops("## Results", space=None)

        assert result is True
        mock_post.assert_called_once_with(
            organization_name="org",
            personal_access_token="pat",
            project="proj",
            repository_name="repo",
            pull_request_id=7,
            comment="## Results",
        )

    def test_returns_false_when_missing_env_vars(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _publish_azure_devops,
        )

        with patch.dict(os.environ, {}, clear=True):
            result = _publish_azure_devops("test", space=None)

        assert result is False


class TestResolveGithubPRNumber:
    """Test GitHub PR number extraction."""

    def test_extracts_from_github_ref(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_github_pr_number,
        )

        with patch.dict(os.environ, {"GITHUB_REF": "refs/pull/123/merge"}):
            assert _resolve_github_pr_number() == "123"

    def test_falls_back_to_explicit_env_var(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_github_pr_number,
        )

        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_PR_NUMBER": "55"}):
            assert _resolve_github_pr_number() == "55"

    def test_returns_none_when_not_a_pr(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _resolve_github_pr_number,
        )

        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"}, clear=True):
            assert _resolve_github_pr_number() is None


class TestPublishGithub:
    """Test GitHub publishing delegation."""

    @patch(
        "thothctl.core.integrations.github.pull_request_comments.post_comment_to_github_pr",
        return_value=True,
    )
    def test_delegates_to_integration(self, mock_post):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _publish_github,
        )

        env = {
            "GITHUB_TOKEN": "ghp_fake",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_REF": "refs/pull/10/merge",
        }

        with patch.dict(os.environ, env, clear=True):
            result = _publish_github("## Results")

        assert result is True
        mock_post.assert_called_once_with(
            token="ghp_fake",
            repository="owner/repo",
            pull_request_number=10,
            comment="## Results",
        )

    def test_returns_false_when_missing_env_vars(self):
        from thothctl.core.integrations.pr_comments.pr_comment_publisher import (
            _publish_github,
        )

        with patch.dict(os.environ, {}, clear=True):
            result = _publish_github("test")

        assert result is False
