"""Agent memory — auto-selects backend based on runtime mode.

Modes:
    - "local"    → FileSessionManager (filesystem)
    - "agentcore"→ S3SessionManager (S3 bucket)
    - "auto"     → detect from environment

Memory stores:
    - Session history: conversation turns per repo/PR
    - Analysis cache: previous findings for a repo
    - Agent state: orchestrator metadata
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOCAL_SESSIONS_DIR = ".thothctl/ai_sessions"


@dataclass
class MemoryConfig:
    """Memory backend configuration."""
    mode: str = "auto"  # "local", "agentcore", "auto"
    # Local
    storage_dir: str = LOCAL_SESSIONS_DIR
    # S3 (agentcore)
    s3_bucket: str = ""
    s3_prefix: str = "thothctl/ai_sessions/"
    region: str = "us-east-1"

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        config = cls()
        config.mode = os.environ.get("THOTH_MEMORY_MODE", "auto")
        config.s3_bucket = os.environ.get("THOTH_MEMORY_S3_BUCKET", "")
        config.s3_prefix = os.environ.get("THOTH_MEMORY_S3_PREFIX", config.s3_prefix)
        config.region = os.environ.get("AWS_DEFAULT_REGION", config.region)
        config.storage_dir = os.environ.get("THOTH_MEMORY_DIR", config.storage_dir)
        return config


def detect_runtime() -> str:
    """Detect if running in AgentCore or locally."""
    # AgentCore sets these env vars
    if os.environ.get("AGENTCORE_RUNTIME") or os.environ.get("AWS_EXECUTION_ENV", "").startswith("AgentCore"):
        return "agentcore"
    # S3 bucket configured explicitly
    if os.environ.get("THOTH_MEMORY_S3_BUCKET"):
        return "agentcore"
    return "local"


class AgentMemory:
    """Unified memory interface — delegates to local or S3 backend.

    Usage:
        memory = AgentMemory.create()  # auto-detect
        memory = AgentMemory.create(mode="local")
        memory = AgentMemory.create(mode="agentcore")

        # Store/retrieve analysis results
        memory.save_analysis("owner/repo", analysis_dict)
        previous = memory.load_analysis("owner/repo")

        # Store/retrieve session messages
        memory.save_session("session-123", messages)
        messages = memory.load_session("session-123")
    """

    def __init__(self, backend: "MemoryBackend"):
        self._backend = backend

    @classmethod
    def create(cls, config: MemoryConfig = None) -> "AgentMemory":
        config = config or MemoryConfig.from_env()
        mode = config.mode if config.mode != "auto" else detect_runtime()

        if mode == "agentcore":
            backend = S3MemoryBackend(
                bucket=config.s3_bucket,
                prefix=config.s3_prefix,
                region=config.region,
            )
        else:
            backend = FileMemoryBackend(storage_dir=config.storage_dir)

        logger.info(f"Agent memory: {mode} backend ({backend})")
        return cls(backend)

    @property
    def mode(self) -> str:
        return self._backend.mode

    # -- Analysis cache (per repo + optional run scope) --

    def save_analysis(self, repo: str, analysis: Dict[str, Any], run_id: str = "") -> None:
        key = self._scoped_key(repo, "analysis", run_id)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo": repo,
            "run_id": run_id,
            "analysis": analysis,
        }
        self._backend.write(key, data)

    def load_analysis(self, repo: str, run_id: str = "") -> Optional[Dict[str, Any]]:
        key = self._scoped_key(repo, "analysis", run_id)
        data = self._backend.read(key)
        return data.get("analysis") if data else None

    # -- Session history (per session ID) --

    def save_session(self, session_id: str, messages: List[Dict]) -> None:
        key = f"sessions/{session_id}.json"
        self._backend.write(key, {
            "session_id": session_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
        })

    def load_session(self, session_id: str) -> List[Dict]:
        key = f"sessions/{session_id}.json"
        data = self._backend.read(key)
        return data.get("messages", []) if data else []

    # -- Agent state (key-value) --

    def save_state(self, agent_id: str, state: Dict[str, Any]) -> None:
        key = f"state/{agent_id}.json"
        self._backend.write(key, state)

    def load_state(self, agent_id: str) -> Dict[str, Any]:
        key = f"state/{agent_id}.json"
        return self._backend.read(key) or {}

    # -- Decision history (per repo) --

    def append_decision(self, repo: str, decision: Dict[str, Any]) -> None:
        key = self._repo_key(repo, "decisions")
        existing = self._backend.read(key) or {"decisions": []}
        existing["decisions"].append({
            **decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 50 decisions per repo
        existing["decisions"] = existing["decisions"][-50:]
        self._backend.write(key, existing)

    def load_decisions(self, repo: str, limit: int = 10) -> List[Dict]:
        key = self._repo_key(repo, "decisions")
        data = self._backend.read(key)
        if not data:
            return []
        return data.get("decisions", [])[-limit:]

    @staticmethod
    def _repo_key(repo: str, suffix: str) -> str:
        safe = repo.replace("/", "_").replace("\\", "_")
        return f"repos/{safe}/{suffix}.json"

    @staticmethod
    def _scoped_key(repo: str, suffix: str, run_id: str = "") -> str:
        """Key scoped to repo + optional run (PR number, pipeline ID, etc.)."""
        safe = repo.replace("/", "_").replace("\\", "_")
        if run_id:
            safe_run = str(run_id).replace("/", "_").replace("\\", "_")
            return f"repos/{safe}/runs/{safe_run}/{suffix}.json"
        return f"repos/{safe}/{suffix}.json"


# -- Backends --

class MemoryBackend:
    """Abstract backend interface."""
    mode: str = "unknown"

    def write(self, key: str, data: Dict) -> None:
        raise NotImplementedError

    def read(self, key: str) -> Optional[Dict]:
        raise NotImplementedError


class FileMemoryBackend(MemoryBackend):
    """Local filesystem backend."""
    mode = "local"

    def __init__(self, storage_dir: str = LOCAL_SESSIONS_DIR):
        self.base = Path(storage_dir)

    def write(self, key: str, data: Dict) -> None:
        path = self.base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    def read(self, key: str) -> Optional[Dict]:
        path = self.base / key
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Failed to read {path}: {e}")
            return None

    def __repr__(self):
        return f"FileMemoryBackend({self.base})"


class S3MemoryBackend(MemoryBackend):
    """S3 backend for AgentCore / cloud deployments."""
    mode = "agentcore"

    def __init__(self, bucket: str, prefix: str = "", region: str = "us-east-1"):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def write(self, key: str, data: Dict) -> None:
        s3_key = f"{self.prefix}{key}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=json.dumps(data, indent=2, default=str),
            ContentType="application/json",
        )

    def read(self, key: str) -> Optional[Dict]:
        s3_key = f"{self.prefix}{key}"
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.debug(f"Failed to read s3://{self.bucket}/{s3_key}: {e}")
            return None

    def __repr__(self):
        return f"S3MemoryBackend(s3://{self.bucket}/{self.prefix})"
