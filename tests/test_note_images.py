"""Tests for note image transcription."""

from __future__ import annotations

import base64
import io

from app.services.note_image_service import (
    detect_image_mime,
    extract_text_from_note_image,
)

# 1x1 transparent PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class _FakeVisionModel:
    def __init__(self, text: str = "Layer caching notes from a photo."):
        self.text = text
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)

        class _Resp:
            def __init__(self, content: str):
                self.content = content

        return _Resp(self.text)


def test_detect_png_magic_bytes():
    assert detect_image_mime(TINY_PNG, ".png") == "image/png"


def test_detect_rejects_pdf_bytes_labeled_as_png():
    assert detect_image_mime(b"%PDF-1.4 fake", ".png") is None


def test_extract_text_from_note_image_uses_vision_model():
    model = _FakeVisionModel("Pin dependencies early in the Dockerfile.")
    text = extract_text_from_note_image(
        TINY_PNG,
        filename="whiteboard.png",
        suffix=".png",
        model=model,
    )
    assert "whiteboard.png" in text
    assert "Pin dependencies early" in text
    assert model.calls


def test_extract_text_empty_raises():
    model = _FakeVisionModel("   ")
    try:
        extract_text_from_note_image(
            TINY_PNG,
            filename="blank.png",
            suffix=".png",
            model=model,
        )
        raise AssertionError("Expected empty extraction to fail")
    except ValueError as exc:
        assert "extract readable text" in str(exc).lower()


def test_image_note_upload_persists_extracted_text(auth_client, monkeypatch):
    monkeypatch.setattr(
        "app.api.admin.extract_text_from_note_image",
        lambda *args, **kwargs: (
            "[Extracted from note image: notes.png]\n\n"
            "EXPOSE does not publish the port by itself."
        ),
    )
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Photo notes", "topic": "Docker", "content": ""},
        files={"uploads": ("notes.png", io.BytesIO(TINY_PNG), "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    listed = auth_client.get("/admin/notes")
    assert listed.status_code == 200
    assert b"Photo notes" in listed.content
    assert b"EXPOSE does not publish" in listed.content
    assert b"png" in listed.content


def test_image_note_upload_combines_pasted_text(auth_client, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.api.admin.extract_text_from_note_image",
        lambda *args, **kwargs: (
            "[Extracted from note image: board.jpg]\n\nHost port 8000 maps to 8080."
        ),
    )
    response = auth_client.post(
        "/admin/notes",
        data={
            "title": "Mixed notes",
            "topic": "Docker",
            "content": "I also noticed rebuilds got faster with layer caching.",
        },
        files={"uploads": ("board.jpg", io.BytesIO(TINY_PNG), "image/jpeg")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    from app.services import content_service

    notes = content_service.list_notes(db_session)
    note = next(n for n in notes if n.title == "Mixed notes")
    assert "rebuilds got faster" in note.content
    assert "Host port 8000" in note.content
    assert note.file_type == "jpg"


def test_multiple_image_uploads_combined_into_one_note(
    auth_client, monkeypatch, db_session
):
    def _fake_extract(image_bytes, *, filename, suffix, settings=None, model=None):
        return f"[Extracted from note image: {filename}]\n\nNotes from {filename}."

    monkeypatch.setattr("app.api.admin.extract_text_from_note_image", _fake_extract)
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Multi page notes", "topic": "Docker", "content": ""},
        files=[
            ("uploads", ("page1.png", io.BytesIO(TINY_PNG), "image/png")),
            ("uploads", ("page2.png", io.BytesIO(TINY_PNG), "image/png")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303
    from app.services import content_service

    notes = content_service.list_notes(db_session)
    note = next(n for n in notes if n.title == "Multi page notes")
    assert "page1.png" in note.content
    assert "page2.png" in note.content
    assert note.file_type == "images"
    assert note.original_filename == "page1.png, page2.png"


def test_image_upload_without_api_key_surfaces_error(auth_client, monkeypatch):
    def _boom(*args, **kwargs):
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    monkeypatch.setattr("app.api.admin.extract_text_from_note_image", _boom)
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Needs key", "topic": "Docker", "content": ""},
        files={"uploads": ("notes.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 400
    assert b"OPENAI_API_KEY" in response.content
