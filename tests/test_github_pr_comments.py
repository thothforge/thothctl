"""Unit tests for GitHub pull request comments integration."""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock


class TestPostCommentToGithubPR:
    """Test github/pull_request_comments.py"""

    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.urlopen")
    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.Request")
    def test_posts_comment_successfully(self, mock_request_cls, mock_urlopen):
        from thothctl.core.integrations.github.pull_request_comments import (
            post_comment_to_github_pr,
        )

        mock_response = Mock()
        mock_response.status = 201
        mock_urlopen.return_value = mock_response

        result = post_comment_to_github_pr(
            token="ghp_fake",
            repository="owner/repo",
            pull_request_number=42,
            comment="## Check Results\nPassed",
        )

        assert result is True
        mock_request_cls.assert_called_once()
        call_args = mock_request_cls.call_args
        assert "owner/repo" in call_args[0][0]
        assert "42" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "token ghp_fake"

    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.urlopen")
    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.Request")
    def test_returns_false_on_non_201(self, mock_request_cls, mock_urlopen):
        from thothctl.core.integrations.github.pull_request_comments import (
            post_comment_to_github_pr,
        )

        mock_response = Mock()
        mock_response.status = 403
        mock_urlopen.return_value = mock_response

        result = post_comment_to_github_pr(
            token="ghp_fake",
            repository="owner/repo",
            pull_request_number=1,
            comment="test",
        )

        assert result is False

    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.urlopen")
    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.Request")
    def test_raises_on_http_error(self, mock_request_cls, mock_urlopen):
        import urllib.error

        from thothctl.core.integrations.github.pull_request_comments import (
            post_comment_to_github_pr,
        )

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=401, msg="Unauthorized", hdrs=None, fp=Mock(read=lambda: b"bad token")
        )

        with pytest.raises(urllib.error.HTTPError):
            post_comment_to_github_pr(
                token="bad",
                repository="owner/repo",
                pull_request_number=1,
                comment="test",
            )

    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.urlopen")
    @patch("thothctl.core.integrations.github.pull_request_comments.urllib.request.Request")
    def test_sends_correct_json_body(self, mock_request_cls, mock_urlopen):
        from thothctl.core.integrations.github.pull_request_comments import (
            post_comment_to_github_pr,
        )

        mock_response = Mock()
        mock_response.status = 201
        mock_urlopen.return_value = mock_response

        post_comment_to_github_pr(
            token="t", repository="o/r", pull_request_number=5, comment="hello"
        )

        call_kwargs = mock_request_cls.call_args
        # data is passed as positional arg (url, data) or keyword
        data = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("data")
        body = json.loads(data)
        assert body == {"body": "hello"}
