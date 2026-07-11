"""Prompt helpers for the content agent."""

from app.services.prompt_loader import load_prompt, render_prompt


def get_system_prompt() -> str:
    return load_prompt("content_agent_system.md")


def get_reviewer_prompt() -> str:
    return load_prompt("reviewer_system.md")


def build_user_request(
    *,
    topic: str,
    notes: str,
    audience: str,
    content_type: str,
    tone: str,
    desired_length: str,
    include_quiz: bool,
    prompt_version: str,
) -> str:
    return render_prompt(
        "content_request.md",
        topic=topic,
        notes=notes or "(none provided)",
        audience=audience,
        content_type=content_type,
        tone=tone,
        desired_length=desired_length,
        include_quiz=str(include_quiz),
        prompt_version=prompt_version,
    )
