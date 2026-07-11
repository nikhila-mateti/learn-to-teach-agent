"""Prompt file loader for externalized prompt engineering assets."""

from pathlib import Path

from app.config import get_settings


def load_prompt(name: str) -> str:
    """Load a markdown prompt file from the prompts directory."""
    settings = get_settings()
    path = Path(settings.prompts_dir) / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt and substitute simple {{placeholder}} values."""
    template = load_prompt(name)
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
