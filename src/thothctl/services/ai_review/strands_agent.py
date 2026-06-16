"""Strands-based IaC Security Agent — multi-agent orchestration.

Supports two modes:
- Swarm: Agents hand off autonomously (requires tool-calling models: Bedrock, OpenAI)
- Workflow: Deterministic pipeline (works with any model including Ollama)

NOTE: Strands Ollama adapter has a known streaming bug in v1.43.0.
For Ollama, use the existing ai_agent.py (direct OpenAI client).
This module is ready for Bedrock/OpenAI models.

Usage:
    from thothctl.services.ai_review.strands_agent import run_security_review
    
    # With Bedrock (recommended for production)
    report = run_security_review("us.anthropic.claude-3-5-sonnet-20241022-v2:0", ".")
    
    # With OpenAI
    report = run_security_review("openai/gpt-4-turbo", ".")
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from strands import Agent

logger = logging.getLogger(__name__)


def _get_model(model_id: str):
    """Create a Strands model from a model ID string."""
    if model_id.startswith("ollama/"):
        from strands.models.ollama import OllamaModel
        model_name = model_id.replace("ollama/", "")
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/v1").rstrip("/")
        return OllamaModel(model_id=model_name, host=host)
    elif model_id.startswith("openai/"):
        from strands.models.openai import OpenAIModel
        return OpenAIModel(model_id=model_id.replace("openai/", ""))
    else:
        # Default to Bedrock
        from strands.models.bedrock import BedrockModel
        return BedrockModel(model_id=model_id)


def _build_context(directory: str) -> str:
    """Build IaC context from thothctl services."""
    from .analyzers.context_builder import ContextBuilder
    builder = ContextBuilder()
    ctx = builder.build_context(directory)
    return builder.format_for_ai(ctx)


def run_security_review(model_id: str, directory: str) -> str:
    """Run multi-agent security review as a deterministic workflow.
    
    Pipeline: Context → Security Analysis → Architecture Review → Recommendations
    Each agent receives the previous agent's output as context.
    """
    os.environ["THOTH_AGENT_DIR"] = str(Path(directory).resolve())
    model = _get_model(model_id)
    context = _build_context(directory)

    # Agent 1: Security Analyst
    security_agent = Agent(
        model=model,
        system_prompt="""You are a security analyst. Given IaC scan findings, identify the TOP 5 most critical issues.
For each issue, include: severity, title (from scan data), resource name, file path, and a 1-line remediation.
Use ONLY the findings provided. Do NOT invent issues. Format as a numbered list.""",
    )

    # Agent 2: Architecture Reviewer  
    architecture_agent = Agent(
        model=model,
        system_prompt="""You are an architecture reviewer. Given security findings and IaC context, assess:
1. Module structure quality (are modules well-organized?)
2. Dependency risks (what's the blast radius?)
3. Version hygiene (outdated modules?)
Provide a brief assessment (5-7 sentences).""",
    )

    # Agent 3: Recommendations
    recommendations_agent = Agent(
        model=model,
        system_prompt="""You are a DevSecOps advisor. Given security findings and architecture assessment, provide:
1. Top 3 immediate actions (with exact file:line to modify)
2. Risk score (0-100, where 100 is critical)
3. Whether to block the pipeline (yes/no with reason)
Be concise. Max 10 lines.""",
    )

    # Execute pipeline
    logger.info("🔍 Agent 1: Security Analysis...")
    security_result = security_agent(f"Analyze these IaC findings:\n\n{context}")

    logger.info("🏗️ Agent 2: Architecture Review...")
    arch_result = architecture_agent(
        f"Context:\n{context}\n\nSecurity findings:\n{security_result}"
    )

    logger.info("💡 Agent 3: Recommendations...")
    recs_result = recommendations_agent(
        f"Security findings:\n{security_result}\n\nArchitecture assessment:\n{arch_result}"
    )

    # Combine results
    report = f"""# 🤖 AI Security Review (Multi-Agent)

## 🔍 Security Findings
{security_result}

## 🏗️ Architecture Assessment
{arch_result}

## 💡 Recommendations
{recs_result}
"""
    return report
