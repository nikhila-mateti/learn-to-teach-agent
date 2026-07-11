"""LangChain content agent using create_agent with structured output."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent

from app.agents.model_factory import create_chat_model
from app.agents.prompts import build_user_request, get_system_prompt
from app.agents.tools import AGENT_TOOLS
from app.config import Settings, get_settings
from app.schemas.content import ContentPackage


def build_content_agent(settings: Settings | None = None, model: Any | None = None):
    """
    Build a real LangChain agent that must call context tools before drafting.

    Uses create_agent with response_format=ContentPackage for structured output.
    """
    settings = settings or get_settings()
    chat_model = model or create_chat_model(settings)
    return create_agent(
        model=chat_model,
        tools=AGENT_TOOLS,
        system_prompt=get_system_prompt(),
        response_format=ContentPackage,
    )


def run_content_agent(
    *,
    topic: str,
    notes: str | None,
    audience: str,
    content_type: str,
    tone: str,
    desired_length: str,
    include_quiz: bool,
    settings: Settings | None = None,
    model: Any | None = None,
) -> ContentPackage:
    """Invoke the content agent and return a validated ContentPackage."""
    settings = settings or get_settings()
    agent = build_content_agent(settings=settings, model=model)
    user_message = build_user_request(
        topic=topic,
        notes=notes or "",
        audience=audience,
        content_type=content_type,
        tone=tone,
        desired_length=desired_length,
        include_quiz=include_quiz,
        prompt_version=settings.prompt_version,
    )
    result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    structured = result.get("structured_response")
    if structured is None:
        raise RuntimeError("Agent did not return structured_response")
    if isinstance(structured, ContentPackage):
        return structured
    return ContentPackage.model_validate(structured)
