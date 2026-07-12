"""Extract text from uploaded note images via a vision-capable chat model."""

from __future__ import annotations

import base64
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.agents.model_factory import create_chat_model
from app.config import Settings, get_settings

IMAGE_SUFFIX_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

EXTRACTION_PROMPT = (
    "You are transcribing learning notes from an image.\n"
    "Extract all readable text faithfully, including headings, bullets, and code-like lines.\n"
    "Do not invent content that is not visible in the image.\n"
    "If handwriting is unclear, keep the best guess and mark uncertain words with [?].\n"
    "Return only the transcribed notes as plain text. No preamble or commentary."
)


def detect_image_mime(image_bytes: bytes, suffix: str) -> str | None:
    """Return a MIME type when bytes look like a supported image, else None."""
    suffix = suffix.lower()
    if suffix not in IMAGE_SUFFIX_TO_MIME:
        return None

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if (
        len(image_bytes) >= 12
        and image_bytes[0:4] == b"RIFF"
        and image_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"

    # Fall back to extension only when magic bytes are unknown but suffix is allowed.
    # Still reject clearly non-image payloads that start with text/PDF markers.
    head = image_bytes[:16].lstrip()
    if head.startswith(b"%PDF") or head.startswith(b"<") or head.startswith(b"{"):
        return None
    return IMAGE_SUFFIX_TO_MIME[suffix]


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(part for part in parts if part.strip()).strip()
    return str(content).strip()


def extract_text_from_note_image(
    image_bytes: bytes,
    *,
    filename: str,
    suffix: str,
    settings: Settings | None = None,
    model: BaseChatModel | None = None,
) -> str:
    """
    Use the configured vision-capable LLM to transcribe note text from an image.

    The extracted text is what generation later consumes as untrusted note data.
    """
    settings = settings or get_settings()
    mime = detect_image_mime(image_bytes, suffix)
    if not mime:
        raise ValueError(
            "Upload does not look like a supported image "
            "(.png, .jpg, .jpeg, .webp, .gif)."
        )

    if model is None:
        settings.require_llm_credentials()
        chat = create_chat_model(settings)
    else:
        chat = model
    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"

    message = HumanMessage(
        content=[
            {"type": "text", "text": EXTRACTION_PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    )
    response = chat.invoke([message])
    text = _response_text(response.content)
    if not text:
        raise ValueError(
            "Could not extract readable text from the image. "
            "Try a clearer photo or paste the notes as text."
        )

    header = f"[Extracted from note image: {filename}]\n\n"
    return header + text
