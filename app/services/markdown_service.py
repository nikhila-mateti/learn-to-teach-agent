"""Markdown rendering and HTML sanitization."""

import bleach
import markdown

ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "code",
    "pre",
    "blockquote",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def markdown_to_safe_html(source: str) -> str:
    """Convert Markdown to HTML and strip unsafe tags/scripts."""
    raw_html = markdown.markdown(
        source,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
