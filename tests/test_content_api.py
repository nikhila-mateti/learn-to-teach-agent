"""Content API and persistence tests."""

from app.schemas.requests import ContentGenerateRequest
from app.services import content_service


def test_generate_requires_credentials(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    response = auth_client.post(
        "/api/v1/content/generate",
        json={
            "topic": "Docker",
            "audience": "engineers",
            "content_type": "tutorial",
            "tone": "clear",
            "desired_length": "medium",
            "include_quiz": True,
        },
    )
    assert response.status_code == 503
    get_settings.cache_clear()


def test_generate_and_get_content(auth_client, monkeypatch, fake_content_package):
    from app.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    get_settings.cache_clear()

    def fake_generate(db, request, settings=None, model=None):
        return content_service.persist_package(
            db,
            fake_content_package,
            request,
            settings or get_settings(),
        )

    monkeypatch.setattr(
        "app.api.content.content_service.generate_and_persist",
        fake_generate,
    )
    response = auth_client.post(
        "/api/v1/content/generate",
        json={
            "topic": "Docker",
            "notes": "",
            "audience": "engineers preparing for production LLM inference",
            "content_type": "tutorial",
            "tone": "clear",
            "desired_length": "medium",
            "include_quiz": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "needs_review"
    content_id = body["id"]
    fetched = auth_client.get(f"/api/v1/content/{content_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == fake_content_package.title
    get_settings.cache_clear()


def test_content_persistence(db_session, fake_content_package):
    from app.config import get_settings

    request = ContentGenerateRequest(topic="Docker")
    item = content_service.persist_package(
        db_session, fake_content_package, request, get_settings()
    )
    loaded = content_service.get_content(db_session, item.id)
    assert loaded is not None
    assert loaded.status == "needs_review"
    assert loaded.title == fake_content_package.title
    assert len(loaded.quiz_json) == 5


def test_unauthenticated_api_generate(client):
    response = client.post(
        "/api/v1/content/generate",
        json={"topic": "Docker"},
    )
    assert response.status_code == 401
