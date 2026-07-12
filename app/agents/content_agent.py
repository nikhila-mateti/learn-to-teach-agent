"""LangChain content agent using create_agent with structured output."""

from __future__ import annotations

import time
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from openai import RateLimitError

from app.agents.model_factory import create_chat_model
from app.agents.prompts import build_user_request, get_system_prompt
from app.agents.tools import AGENT_TOOLS
from app.config import Settings, get_settings
from app.schemas.content import ContentPackage


def build_content_agent(settings: Settings | None = None, model: Any | None = None):
    """
    Build a real LangChain agent that must call context tools before drafting.

    Uses create_agent with ToolStrategy(ContentPackage). Auto/ProviderStrategy can
    loop on tool calls without emitting structured output for this schema.
    """
    settings = settings or get_settings()
    chat_model = model or create_chat_model(settings)
    return create_agent(
        model=chat_model,
        tools=AGENT_TOOLS,
        system_prompt=get_system_prompt(),
        response_format=ToolStrategy(ContentPackage),
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

    last_error: Exception | None = None
    # Keep retries short so the admin UI does not appear to hang forever.
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"recursion_limit": 25},
            )
            structured = result.get("structured_response")
            if structured is None:
                raise RuntimeError(
                    "Agent did not return structured_response. "
                    "Try again; if this persists, check API key and model access."
                )
            if isinstance(structured, ContentPackage):
                return structured
            return ContentPackage.model_validate(structured)
        except RateLimitError as exc:
            last_error = exc
            if attempt + 1 >= max_attempts:
                break
            time.sleep(15)
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            if "rate limit" in message or "429" in message:
                last_error = exc
                if attempt + 1 >= max_attempts:
                    break
                time.sleep(15)
                continue
            raise

    raise RuntimeError(
        "Content generation hit an API rate limit and was not saved. "
        "Wait about a minute, then try Generate again. "
        f"Details: {last_error}"
    )
