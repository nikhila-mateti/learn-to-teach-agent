"""Generation mode selection tests with mocked LLM agent."""

from app.schemas.requests import ContentGenerateRequest
from app.services import content_service
from app.services.content_service import notes_are_meaningful


def test_notes_meaningful_true():
    notes = (
        "I noticed rebuilding after dependency changes is slow. "
        "Pinning base images helped reproducibility while preparing "
        "a FastAPI inference service for later Kubernetes work."
    )
    assert notes_are_meaningful(notes) is True


def test_notes_missing_is_not_meaningful():
    assert notes_are_meaningful(None) is False
    assert notes_are_meaningful("short") is False


def test_notes_grounded_mode(db_session, monkeypatch, fake_content_package):
    package = fake_content_package.model_copy(deep=True)
    package.generation_mode = "notes_grounded"

    def fake_run(**kwargs):
        return package

    monkeypatch.setattr(content_service, "run_content_agent", fake_run)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    notes = (
        "I noticed rebuilding after dependency changes is slow. "
        "Pinning base images helped reproducibility while preparing "
        "a FastAPI inference service for later Kubernetes work."
    )
    request = ContentGenerateRequest(topic="Docker", notes=notes)
    item = content_service.generate_and_persist(db_session, request, settings=get_settings())
    assert item.generation_mode == "notes_grounded"
    assert item.status == "needs_review"
    get_settings.cache_clear()


def test_curriculum_aware_when_notes_missing(db_session, monkeypatch, fake_content_package):
    package = fake_content_package.model_copy(deep=True)
    package.generation_mode = "notes_grounded"  # model may claim wrong mode

    def fake_run(**kwargs):
        return package

    monkeypatch.setattr(content_service, "run_content_agent", fake_run)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    request = ContentGenerateRequest(topic="Docker", notes="")
    item = content_service.generate_and_persist(db_session, request, settings=get_settings())
    assert item.generation_mode == "curriculum_aware"
    get_settings.cache_clear()
