"""Tests for check iac cost analysis PR comment integration."""
from types import SimpleNamespace
from thothctl.commands.check.commands.iac import CheckIaCCommand


def _make_analysis(monthly=0.0, annual=0.0, services=None):
    """Create a mock cost analysis object."""
    return SimpleNamespace(
        total_monthly_cost=monthly,
        total_annual_cost=annual,
        cost_breakdown_by_service=services or {},
    )


class TestBuildCostMarkdown:
    """Test markdown summary generation from cost analysis results."""

    def test_basic_summary(self):
        cmd = CheckIaCCommand()
        results = [
            {"stack": "vpc", "analysis": _make_analysis(150.0, 1800.0, {"EC2": 100.0, "VPC": 50.0})},
            {"stack": "eks", "analysis": _make_analysis(300.0, 3600.0, {"EKS": 200.0, "EC2": 100.0})},
        ]
        md = cmd._build_cost_markdown(results)
        assert "## 💰 ThothCTL Cost Analysis Summary" in md
        assert "| vpc | $150.00 | $1800.00 |" in md
        assert "| eks | $300.00 | $3600.00 |" in md
        assert "**$450.00**" in md
        assert "**$5400.00**" in md
        # Service breakdown aggregated
        assert "| EC2 | $200.00 |" in md
        assert "| EKS | $200.00 |" in md
        assert "| VPC | $50.00 |" in md

    def test_zero_cost(self):
        cmd = CheckIaCCommand()
        results = [
            {"stack": "iam-roles", "analysis": _make_analysis(0.0, 0.0)},
        ]
        md = cmd._build_cost_markdown(results)
        assert "| iam-roles | $0.00 | $0.00 |" in md
        assert "Cost by Service" not in md  # no services

    def test_post_execute_uses_cost_results_when_no_outmd(self):
        from unittest.mock import patch
        cmd = CheckIaCCommand()
        cmd._post_to_pr = True
        cmd._outmd = "nonexistent.md"
        cmd._vcs_provider = "github"
        cmd._space = None
        cmd._cost_results = [
            {"stack": "vpc", "analysis": _make_analysis(10.0, 120.0)},
        ]

        with patch(
            "thothctl.core.integrations.pr_comments.pr_comment_publisher.publish_to_pr",
            return_value=True,
        ) as mock_pub:
            cmd.post_execute()

        content = mock_pub.call_args[1]["content"]
        assert "Cost Analysis Summary" in content
        assert "| vpc |" in content
