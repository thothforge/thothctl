"""Tests for inventory iac PR comment integration."""
import os
from unittest.mock import patch

from thothctl.commands.inventory.commands.iac import IaCInvCommand


class TestBuildInventoryMarkdown:
    """Test markdown summary generation from inventory dict."""

    def test_basic_summary(self):
        cmd = IaCInvCommand()
        inventory = {
            "projectType": "terraform-terragrunt",
            "components": [
                {"providers": [{"name": "aws"}, {"name": "helm"}]},
                {"providers": [{"name": "aws"}]},
            ],
            "unique_providers_count": 2,
            "terragrunt_stacks_count": 5,
        }
        md = cmd._build_inventory_markdown(inventory)
        assert "## 📦 ThothCTL Inventory Summary" in md
        assert "| Total Components | 2 |" in md
        assert "| Providers | 2 |" in md
        assert "| Terragrunt Stacks | 5 |" in md
        assert "thothforge/thothctl" in md

    def test_includes_technical_debt(self):
        cmd = IaCInvCommand()
        inventory = {
            "projectType": "terraform",
            "components": [{}],
            "version_checks": True,
            "technical_debt": {
                "risk_level": "high",
                "debt_score": 42.5,
                "outdated_modules": 3,
                "total_components": 10,
                "modules_with_breaking_changes": 1,
                "providers_with_breaking_changes": 0,
            },
        }
        md = cmd._build_inventory_markdown(inventory)
        assert "42.5% (HIGH)" in md
        assert "| Outdated Modules | 3/10 |" in md
        assert "Breaking Changes (Modules) | 1" in md
        assert "Breaking Changes (Providers)" not in md

    def test_post_execute_skips_when_flag_not_set(self):
        cmd = IaCInvCommand()
        cmd._post_to_pr = False
        cmd._inventory = {"components": [{}]}
        # Should not raise or call publish_to_pr
        cmd.post_execute()

    def test_post_execute_calls_publish(self):
        cmd = IaCInvCommand()
        cmd._post_to_pr = True
        cmd._vcs_provider = "github"
        cmd._space = None
        cmd._inventory = {
            "projectType": "terraform",
            "components": [{"providers": []}],
        }

        with patch(
            "thothctl.core.integrations.pr_comments.pr_comment_publisher.publish_to_pr",
            return_value=True,
        ) as mock_pub:
            cmd.post_execute()

        mock_pub.assert_called_once()
        content = mock_pub.call_args[1]["content"]
        assert "ThothCTL Inventory Summary" in content
