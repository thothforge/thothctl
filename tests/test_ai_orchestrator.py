"""Unit tests for AgentOrchestrator."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from dataclasses import dataclass, field
from typing import Dict, List, Any

from thothctl.services.ai_review.orchestrator import (
    AgentOrchestrator, AgentRole, AgentTask, OrchestratorResult,
)
from thothctl.services.ai_review.analyzers.context_builder import IaCContext


class TestAgentRole:
    def test_roles(self):
        assert AgentRole.SECURITY.value == "security"
        assert AgentRole.ARCHITECTURE.value == "architecture"
        assert AgentRole.FIX.value == "fix"
        assert AgentRole.DECISION.value == "decision"


class TestOrchestratorResult:
    def test_defaults(self):
        r = OrchestratorResult()
        assert r.security == {}
        assert r.architecture == {}
        assert r.fixes == {}
        assert r.decision == {}
        assert r.errors == []
        assert r.cost == {}


class TestAgentTask:
    def test_creation(self):
        task = AgentTask(
            role=AgentRole.SECURITY,
            system_prompt="You are a security analyst.",
            context="Some findings here.",
        )
        assert task.role == AgentRole.SECURITY
        assert task.post_process is None


class TestContextFormatters:
    """Test the context formatting methods produce correct slices."""

    def _make_orchestrator(self):
        """Create orchestrator with mocked provider."""
        with patch.object(AgentOrchestrator, '__init__', lambda self, **kw: None):
            orch = AgentOrchestrator.__new__(AgentOrchestrator)
            orch.settings = None
            orch.cost_tracker = Mock()
            orch.cost_tracker.check_budget.return_value = True
            orch.context_builder = Mock()
            orch.max_parallel = 1
            orch._provider = Mock()
            return orch

    def _make_context(self):
        ctx = IaCContext(directory="/test")
        ctx.project_type = "terraform"
        ctx.modules = [{"name": "vpc", "version": "3.0", "latest_version": "4.0", "status": "outdated"}]
        ctx.providers = [{"name": "aws", "version": "5.0", "source": "hashicorp/aws"}]
        ctx.scan_results = {
            "total_findings": 2,
            "tools": {"checkov": {
                "passed": 10, "failed": 2,
                "findings": [
                    {"severity": "HIGH", "check_id": "CKV_AWS_19", "check_name": "S3 encryption",
                     "resource": "aws_s3_bucket.data", "file": "s3.tf"},
                    {"severity": "MEDIUM", "check_id": "CKV_AWS_23", "check_name": "SG description",
                     "resource": "aws_security_group.web", "file": "sg.tf"},
                ],
            }},
        }
        ctx.blast_radius = {"total_components": 5, "risk_level": "MEDIUM", "affected_components": []}
        ctx.code_files = {"s3.tf": 'resource "aws_s3_bucket" "data" {}', "sg.tf": 'resource "aws_security_group" "web" {}'}
        return ctx

    def test_security_context_includes_findings(self):
        orch = self._make_orchestrator()
        ctx = self._make_context()
        result = orch._format_security_context(ctx)
        assert "CKV_AWS_19" in result
        assert "CKV_AWS_23" in result
        assert "s3.tf" in result

    def test_security_context_empty_when_no_findings(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        result = orch._format_security_context(ctx)
        assert result == ""

    def test_architecture_context_includes_modules(self):
        orch = self._make_orchestrator()
        ctx = self._make_context()
        result = orch._format_architecture_context(ctx)
        assert "vpc" in result
        assert "v3.0" in result
        assert "v4.0" in result
        assert "Blast Radius" in result

    def test_fix_context_includes_findings(self):
        orch = self._make_orchestrator()
        ctx = self._make_context()
        result = orch._format_fix_context(ctx)
        assert "CKV_AWS_19" in result or "Findings" in result

    def test_fix_context_empty_when_no_findings(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        result = orch._format_fix_context(ctx)
        assert result == ""


class TestTaskCreation:
    def _make_orchestrator(self):
        with patch.object(AgentOrchestrator, '__init__', lambda self, **kw: None):
            orch = AgentOrchestrator.__new__(AgentOrchestrator)
            orch.settings = None
            orch.cost_tracker = Mock()
            orch.context_builder = Mock()
            orch.max_parallel = 1
            orch._provider = Mock()
            return orch

    def test_creates_security_task(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        ctx.scan_results = {"total_findings": 1, "tools": {"checkov": {
            "passed": 0, "failed": 1,
            "findings": [{"severity": "HIGH", "check_id": "X", "check_name": "Y",
                          "resource": "R", "file": "f.tf"}],
        }}}
        ctx.code_files = {"f.tf": "content"}
        tasks = orch._create_tasks(ctx, [AgentRole.SECURITY])
        assert len(tasks) == 1
        assert tasks[0].role == AgentRole.SECURITY

    def test_skips_empty_roles(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")  # empty context
        tasks = orch._create_tasks(ctx, [AgentRole.SECURITY, AgentRole.FIX])
        # Both should be skipped — no findings, no code
        assert len(tasks) == 0

    def test_creates_architecture_task(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        ctx.modules = [{"name": "vpc", "version": "1.0"}]
        tasks = orch._create_tasks(ctx, [AgentRole.ARCHITECTURE])
        assert len(tasks) == 1
        assert tasks[0].role == AgentRole.ARCHITECTURE


class TestOfflineResult:
    def _make_orchestrator(self):
        with patch.object(AgentOrchestrator, '__init__', lambda self, **kw: None):
            orch = AgentOrchestrator.__new__(AgentOrchestrator)
            orch.settings = None
            orch.cost_tracker = Mock()
            orch.context_builder = Mock()
            orch.max_parallel = 1
            orch._provider = Mock()
            return orch

    def test_offline_with_findings(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        ctx.scan_results = {
            "total_findings": 1,
            "tools": {"checkov": {"findings": [
                {"severity": "HIGH", "check_id": "CKV_AWS_19",
                 "check_name": "S3", "resource": "aws_s3_bucket.x", "file": "s3.tf"},
            ]}},
        }
        ctx.code_files = {}
        result = orch._offline_result(ctx, [AgentRole.SECURITY, AgentRole.FIX])
        assert "AI budget exceeded" in result.errors[0]
        assert result.security.get("risk_score", 0) > 0

    def test_offline_empty(self):
        orch = self._make_orchestrator()
        ctx = IaCContext(directory="/test")
        result = orch._offline_result(ctx, [AgentRole.SECURITY])
        assert result.security == {}
        assert len(result.errors) == 1
