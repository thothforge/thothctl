"""Unit tests for AgentMemory — local and S3 backends."""

import json
import os
import pytest
from unittest.mock import patch, Mock, MagicMock

from thothctl.services.ai_review.memory import (
    AgentMemory, MemoryConfig, FileMemoryBackend, S3MemoryBackend,
    detect_runtime,
)


class TestDetectRuntime:
    def test_local_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert detect_runtime() == "local"

    def test_agentcore_from_env(self):
        with patch.dict(os.environ, {"AGENTCORE_RUNTIME": "true"}):
            assert detect_runtime() == "agentcore"

    def test_agentcore_from_s3_bucket(self):
        with patch.dict(os.environ, {"THOTH_MEMORY_S3_BUCKET": "my-bucket"}, clear=True):
            assert detect_runtime() == "agentcore"


class TestMemoryConfig:
    def test_defaults(self):
        config = MemoryConfig()
        assert config.mode == "auto"

    def test_from_env(self):
        with patch.dict(os.environ, {"THOTH_MEMORY_MODE": "local", "THOTH_MEMORY_DIR": "/tmp/test"}):
            config = MemoryConfig.from_env()
            assert config.mode == "local"
            assert config.storage_dir == "/tmp/test"


class TestFileMemoryBackend:
    def test_write_and_read(self, tmp_path):
        backend = FileMemoryBackend(storage_dir=str(tmp_path))
        backend.write("test/data.json", {"key": "value"})
        result = backend.read("test/data.json")
        assert result == {"key": "value"}

    def test_read_missing(self, tmp_path):
        backend = FileMemoryBackend(storage_dir=str(tmp_path))
        assert backend.read("nonexistent.json") is None

    def test_creates_directories(self, tmp_path):
        backend = FileMemoryBackend(storage_dir=str(tmp_path))
        backend.write("deep/nested/path/data.json", {"x": 1})
        assert (tmp_path / "deep" / "nested" / "path" / "data.json").exists()


class TestAgentMemoryLocal:
    @pytest.fixture
    def memory(self, tmp_path):
        config = MemoryConfig(mode="local", storage_dir=str(tmp_path))
        return AgentMemory.create(config)

    def test_mode(self, memory):
        assert memory.mode == "local"

    def test_save_load_analysis(self, memory):
        analysis = {"risk_score": 42, "summary": {"critical": 1}}
        memory.save_analysis("owner/repo", analysis)
        loaded = memory.load_analysis("owner/repo")
        assert loaded["risk_score"] == 42

    def test_load_missing_analysis(self, memory):
        assert memory.load_analysis("nonexistent/repo") is None

    def test_save_load_session(self, memory):
        msgs = [{"role": "user", "content": "hello"}]
        memory.save_session("sess-1", msgs)
        loaded = memory.load_session("sess-1")
        assert len(loaded) == 1
        assert loaded[0]["role"] == "user"

    def test_save_load_state(self, memory):
        memory.save_state("security", {"last_run": "2026-01-01"})
        state = memory.load_state("security")
        assert state["last_run"] == "2026-01-01"

    def test_append_decisions(self, memory):
        memory.append_decision("owner/repo", {"action": "approve"})
        memory.append_decision("owner/repo", {"action": "reject"})
        decisions = memory.load_decisions("owner/repo")
        assert len(decisions) == 2
        assert decisions[0]["action"] == "approve"
        assert decisions[1]["action"] == "reject"
        assert "timestamp" in decisions[0]

    def test_decisions_limit(self, memory):
        decisions = memory.load_decisions("owner/repo", limit=1)
        assert len(decisions) == 0  # no decisions yet


class TestS3MemoryBackend:
    def test_write_calls_put_object(self):
        mock_client = MagicMock()
        backend = S3MemoryBackend(bucket="test-bucket", prefix="prefix/", region="us-east-1")
        backend._client = mock_client

        backend.write("test.json", {"key": "value"})
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "prefix/test.json"

    def test_read_calls_get_object(self):
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b'{"key": "value"}'
        mock_client.get_object.return_value = {"Body": mock_body}
        backend = S3MemoryBackend(bucket="test-bucket", prefix="p/", region="us-east-1")
        backend._client = mock_client

        result = backend.read("test.json")
        assert result == {"key": "value"}

    def test_read_missing_returns_none(self):
        mock_client = MagicMock()
        mock_client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
        mock_client.get_object.side_effect = mock_client.exceptions.NoSuchKey()
        backend = S3MemoryBackend(bucket="b", prefix="", region="us-east-1")
        backend._client = mock_client

        assert backend.read("missing.json") is None


class TestAgentMemoryAutoDetect:
    def test_auto_local(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            config = MemoryConfig(mode="auto", storage_dir=str(tmp_path))
            mem = AgentMemory.create(config)
            assert mem.mode == "local"

    def test_auto_agentcore(self):
        with patch.dict(os.environ, {"AGENTCORE_RUNTIME": "true"}):
            config = MemoryConfig(mode="auto", s3_bucket="bucket", region="us-east-1")
            mem = AgentMemory.create(config)
            assert mem.mode == "agentcore"
