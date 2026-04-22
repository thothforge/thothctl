"""Unit tests for AgentCore Runtime entrypoint (main.py)."""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from thothctl.services.ai_review.main import app, _detect_mode, _dispatch


client = TestClient(app)


# ── /ping ────────────────────────────────────────────────────────────

class TestPing:
    def test_ping_returns_healthy(self):
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


# ── /health ──────────────────────────────────────────────────────────

class TestHealth:
    @patch("thothctl.services.ai_review.main.health")
    def test_health_endpoint_exists(self, _mock):
        resp = client.get("/health")
        assert resp.status_code == 200


# ── _detect_mode ─────────────────────────────────────────────────────

class TestDetectMode:
    @pytest.mark.parametrize("prompt,expected", [
        ("Fix the S3 encryption issue", "fix"),
        ("improve security posture", "fix"),
        ("remediate findings", "fix"),
        ("patch the vulnerability", "fix"),
        ("Full review of my terraform", "review"),
        ("orchestrate a multi-agent scan", "review"),
        ("Analyze my infrastructure", "analyze"),
        ("scan for security issues", "analyze"),
        ("", "analyze"),
    ])
    def test_mode_detection(self, prompt, expected):
        assert _detect_mode(prompt) == expected


# ── _dispatch ────────────────────────────────────────────────────────

class TestDispatch:
    @patch("thothctl.services.ai_review.main._dispatch")
    def test_dispatch_called_on_invocations(self, mock_dispatch):
        mock_dispatch.return_value = {"summary": "ok"}
        resp = client.post("/invocations", json={"prompt": "analyze this"})
        assert resp.status_code == 200

    @patch("thothctl.services.ai_review.ai_agent.AIReviewAgent")
    def test_dispatch_analyze(self, MockAgent):
        instance = MockAgent.return_value
        instance.analyze_directory.return_value = {"risk_score": 10}
        result = _dispatch(mode="analyze", directory="/tmp", provider="ollama")
        instance.analyze_directory.assert_called_once_with("/tmp")
        assert result["risk_score"] == 10

    @patch("thothctl.services.ai_review.ai_agent.AIReviewAgent")
    def test_dispatch_fix(self, MockAgent):
        instance = MockAgent.return_value
        instance.generate_fixes.return_value = {"fixes": []}
        result = _dispatch(mode="fix", directory="/tmp", provider="ollama")
        instance.generate_fixes.assert_called_once()
        assert "fixes" in result

    @patch("thothctl.services.ai_review.orchestrator.AgentOrchestrator")
    def test_dispatch_review(self, MockOrch):
        from dataclasses import dataclass, field
        from typing import Any, Dict, List

        @dataclass
        class FakeResult:
            security: Dict[str, Any] = field(default_factory=dict)
            errors: List[str] = field(default_factory=list)

        MockOrch.return_value.run_agents.return_value = FakeResult()
        result = _dispatch(mode="review", directory="/tmp", provider="ollama",
                           roles=["security"])
        MockOrch.return_value.run_agents.assert_called_once()
        assert "security" in result


# ── /invocations ─────────────────────────────────────────────────────

class TestInvocations:
    @patch("thothctl.services.ai_review.main._dispatch")
    def test_invocations_auto_detect_analyze(self, mock_dispatch):
        mock_dispatch.return_value = {"risk_score": 5}
        resp = client.post("/invocations", json={"prompt": "check my terraform"})
        assert resp.status_code == 200
        assert resp.json()["result"]["risk_score"] == 5
        call_kwargs = mock_dispatch.call_args
        assert call_kwargs.kwargs.get("mode") == "analyze" or call_kwargs[1].get("mode") == "analyze"

    @patch("thothctl.services.ai_review.main._dispatch")
    def test_invocations_explicit_mode(self, mock_dispatch):
        mock_dispatch.return_value = {"fixes": []}
        resp = client.post("/invocations", json={"prompt": "do stuff", "mode": "fix"})
        assert resp.status_code == 200
        call_kwargs = mock_dispatch.call_args
        assert call_kwargs.kwargs.get("mode") == "fix" or call_kwargs[1].get("mode") == "fix"

    @patch("thothctl.services.ai_review.main._dispatch")
    def test_invocations_passes_repository_and_run_id(self, mock_dispatch):
        mock_dispatch.return_value = {}
        client.post("/invocations", json={
            "prompt": "review", "mode": "review",
            "repository": "org/repo", "run_id": "pr/42",
        })
        kw = mock_dispatch.call_args.kwargs
        assert kw["repository"] == "org/repo"
        assert kw["run_id"] == "pr/42"

    @patch("thothctl.services.ai_review.main._dispatch", side_effect=RuntimeError("boom"))
    def test_invocations_returns_500_on_error(self, _mock):
        resp = client.post("/invocations", json={"prompt": "fail"})
        assert resp.status_code == 500
        assert "boom" in resp.json()["error"]

    @patch("thothctl.services.ai_review.main._dispatch")
    def test_invocations_default_directory_from_env(self, mock_dispatch, monkeypatch):
        monkeypatch.setenv("THOTH_SCAN_DIR", "/custom/dir")
        mock_dispatch.return_value = {}
        client.post("/invocations", json={"prompt": "analyze"})
        kw = mock_dispatch.call_args.kwargs
        assert kw["directory"] == "/custom/dir"
