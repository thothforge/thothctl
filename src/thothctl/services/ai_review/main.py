"""Amazon Bedrock AgentCore Runtime entrypoint for ThothCTL AI Agent.

AgentCore requires either:
  - @app.entrypoint from bedrock-agentcore SDK, or
  - /invocations POST + /ping GET HTTP endpoints

This module implements the HTTP contract, delegating to the existing
ThothCTL AI review orchestrator and agent.

Deploy:
  agentcore deploy          # via AgentCore CLI
  # or zip + boto3 (see docs/framework/commands/ai-review/agentcore.md)

Test locally:
  agentcore dev --no-browser
  curl -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Analyze ./terraform for security issues"}'
"""
import json
import logging
import os
import re
import tempfile
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="ThothCTL AgentCore Agent", version="0.13.2")


# ── AgentCore contract ──────────────────────────────────────────────

@app.get("/ping")
def ping():
    """AgentCore health probe."""
    return {"status": "healthy"}


@app.post("/invocations")
async def invocations(request: Request):
    """AgentCore invocation endpoint.

    Accepts:
      {"prompt": "..."}                          → auto-detect intent
      {"prompt": "...", "mode": "analyze|review|fix"}  → explicit mode
      {"prompt": "...", "directory": "/path"}     → explicit directory
    """
    body = await request.json()
    prompt = body.get("prompt", "")
    mode = body.get("mode", "")
    directory = body.get("directory", os.environ.get("THOTH_SCAN_DIR", "."))
    provider = body.get("provider", os.environ.get("THOTH_AI_PROVIDER", "bedrock"))
    model = body.get("model")
    repository = body.get("repository", "")
    run_id = body.get("run_id", "")
    roles = body.get("roles", ["security", "architecture", "fix"])

    if not mode:
        mode = _detect_mode(prompt)

    try:
        result = _dispatch(
            mode=mode, directory=directory, provider=provider, model=model,
            roles=roles, repository=repository, run_id=run_id, prompt=prompt,
        )
        return JSONResponse(content={"result": result})
    except Exception as e:
        logger.exception("Invocation failed")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Existing REST endpoints (kept for direct API use) ───────────────

@app.get("/health")
def health():
    from thothctl.services.ai_review.config.ai_settings import AISettings
    try:
        settings = AISettings.load()
        return {"status": "healthy", "default_provider": settings.default_provider}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.post("/analyze")
def analyze(request_body: dict):
    return _dispatch(mode="analyze", **{k: request_body[k] for k in request_body})


@app.post("/review")
def review(request_body: dict):
    return _dispatch(mode="review", **{k: request_body[k] for k in request_body})


@app.post("/fix")
def fix(request_body: dict):
    return _dispatch(mode="fix", **{k: request_body[k] for k in request_body})


# ── Internal dispatch ───────────────────────────────────────────────

def _dispatch(mode: str, directory: str = ".", provider: str = "bedrock",
              model: str = None, roles: list = None, repository: str = "",
              run_id: str = "", **kwargs) -> Dict[str, Any]:
    """Route to the appropriate agent workflow."""
    if mode == "review":
        from thothctl.services.ai_review.orchestrator import AgentOrchestrator, AgentRole
        role_map = {r.value: r for r in AgentRole}
        parsed_roles = [role_map[r] for r in (roles or ["security", "architecture", "fix"]) if r in role_map]
        orch = AgentOrchestrator(provider=provider, model=model)
        result = orch.run_agents(directory, roles=parsed_roles, repository=repository, run_id=run_id)
        return result.__dict__

    if mode == "fix":
        from thothctl.services.ai_review.ai_agent import AIReviewAgent
        agent = AIReviewAgent(provider=provider, model=model)
        return agent.generate_fixes(directory, severity_filter=kwargs.get("severity_filter"))

    # Default: analyze
    from thothctl.services.ai_review.ai_agent import AIReviewAgent
    agent = AIReviewAgent(provider=provider, model=model)
    return agent.analyze_directory(directory)


def _detect_mode(prompt: str) -> str:
    """Infer mode from natural-language prompt."""
    p = prompt.lower()
    if any(w in p for w in ["fix", "improve", "remediat", "patch"]):
        return "fix"
    if any(w in p for w in ["review", "orchestrat", "multi-agent", "full"]):
        return "review"
    return "analyze"
