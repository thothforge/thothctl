"""REST API for ThothCTL AI Review — CI/CD and external integrations.

Start with:
    uvicorn thothctl.services.ai_review.bedrock_agent_api:app --host 0.0.0.0 --port 8080
"""
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="ThothCTL AI Review API", version="0.12.0")


# -- Request models --

class AnalyzeRequest(BaseModel):
    scan_dir: str
    provider: str = "bedrock_agent"
    model: Optional[str] = None


class ReviewRequest(BaseModel):
    directory: str
    provider: str = "bedrock_agent"
    model: Optional[str] = None
    roles: List[str] = ["security", "architecture", "fix"]
    parallel: int = 3
    repository: str = ""
    run_id: str = ""


class FixRequest(BaseModel):
    directory: str
    provider: str = "bedrock_agent"
    model: Optional[str] = None
    severity_filter: Optional[str] = None


# -- Endpoints --

@app.get("/health")
def health():
    """Health check and provider status."""
    from .config.ai_settings import AISettings
    try:
        settings = AISettings.load()
        providers = list(settings.providers.keys())
        return {"status": "healthy", "default_provider": settings.default_provider, "providers": providers}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Analyze pre-existing scan results with AI."""
    from .ai_agent import AIReviewAgent
    try:
        agent = AIReviewAgent(provider=req.provider, model=req.model)
        return agent.analyze_scan_results(req.scan_dir)
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/review")
def review(req: ReviewRequest):
    """Full multi-agent orchestrated review."""
    from .orchestrator import AgentOrchestrator, AgentRole
    try:
        role_map = {r.value: r for r in AgentRole}
        roles = [role_map[r] for r in req.roles if r in role_map]
        orchestrator = AgentOrchestrator(
            provider=req.provider, model=req.model, max_parallel=req.parallel,
        )
        result = orchestrator.run_agents(
            req.directory, roles=roles,
            repository=req.repository, run_id=req.run_id,
        )
        return result.to_dict() if hasattr(result, "to_dict") else result.__dict__
    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fix")
def fix(req: FixRequest):
    """Generate code fixes for scan findings."""
    from .ai_agent import AIReviewAgent
    try:
        agent = AIReviewAgent(provider=req.provider, model=req.model)
        return agent.generate_fixes(req.directory, severity_filter=req.severity_filter)
    except Exception as e:
        logger.error(f"Fix generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
