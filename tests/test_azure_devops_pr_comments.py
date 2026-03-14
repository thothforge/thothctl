"""Unit tests for Azure DevOps pull request comments integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestPostCommentToAzureDevopsPR:
    """Test azure_devops/pull_request_comments.py"""

    @pytest.fixture
    def mock_connection(self):
        """Mock Azure DevOps connection and git client."""
        with patch(
            "thothctl.core.integrations.azure_devops.pull_request_comments.Connection"
        ) as mock_conn, patch(
            "thothctl.core.integrations.azure_devops.pull_request_comments.BasicAuthentication"
        ) as mock_auth:
            mock_repo = Mock()
            mock_repo.id = "repo-123"
            mock_repo.name = "my-repo"

            git_client = Mock()
            git_client.get_repositories.return_value = [mock_repo]
            git_client.create_thread.return_value = Mock(id=42)

            mock_conn.return_value.clients.get_git_client.return_value = git_client

            yield {
                "connection": mock_conn,
                "auth": mock_auth,
                "git_client": git_client,
            }

    def test_posts_comment_successfully(self, mock_connection):
        from thothctl.core.integrations.azure_devops.pull_request_comments import (
            post_comment_to_azure_devops_pr,
        )

        result = post_comment_to_azure_devops_pr(
            organization_name="my-org",
            personal_access_token="fake-pat",
            project="my-project",
            repository_name="my-repo",
            pull_request_id=1,
            comment="## Results\nAll good",
        )

        assert result.id == 42
        mock_connection["git_client"].create_thread.assert_called_once()
        call_args = mock_connection["git_client"].create_thread.call_args
        thread = call_args[0][0]
        assert thread["comments"][0]["content"] == "## Results\nAll good"

    def test_raises_on_repo_not_found(self, mock_connection):
        from thothctl.core.integrations.azure_devops.pull_request_comments import (
            post_comment_to_azure_devops_pr,
        )

        with pytest.raises(ValueError, match="not found"):
            post_comment_to_azure_devops_pr(
                organization_name="my-org",
                personal_access_token="fake-pat",
                project="my-project",
                repository_name="nonexistent-repo",
                pull_request_id=1,
                comment="test",
            )

    def test_returns_none_when_thread_creation_fails(self, mock_connection):
        from thothctl.core.integrations.azure_devops.pull_request_comments import (
            post_comment_to_azure_devops_pr,
        )

        mock_connection["git_client"].create_thread.return_value = None

        result = post_comment_to_azure_devops_pr(
            organization_name="my-org",
            personal_access_token="fake-pat",
            project="my-project",
            repository_name="my-repo",
            pull_request_id=1,
            comment="test",
        )

        assert result is None

    def test_connection_uses_correct_base_url(self, mock_connection):
        from thothctl.core.integrations.azure_devops.pull_request_comments import (
            post_comment_to_azure_devops_pr,
        )

        post_comment_to_azure_devops_pr(
            organization_name="contoso",
            personal_access_token="pat",
            project="proj",
            repository_name="my-repo",
            pull_request_id=1,
            comment="x",
        )

        mock_connection["connection"].assert_called_once()
        call_kwargs = mock_connection["connection"].call_args
        assert "https://dev.azure.com/contoso" in str(call_kwargs)
