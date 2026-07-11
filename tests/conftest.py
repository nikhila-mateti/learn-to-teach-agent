"""Shared pytest fixtures with a deterministic fake ContentPackage."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Configure test environment before app imports.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("MODEL_NAME", "gpt-4o-mini")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PROMPT_VERSION", "v1")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:8000")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$zaovZi/O6RspjKcr2O3Fmus84ItPhAfhVNWeYXZtbCLEbVslJLcRi",
)
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.content import Base
from app.schemas.content import (
    ContentPackage,
    PublicationReadiness,
    QuizQuestion,
    SourceReference,
    TeachingExample,
)

get_settings.cache_clear()


def make_quiz() -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []
    for i in range(5):
        questions.append(
            QuizQuestion(
                question=f"Docker concept question {i + 1}?",
                choices=["Image", "Container", "Volume", "Network"],
                correct_index=0,
                correct_explanation="An image is the immutable template.",
                incorrect_explanations=[
                    "This option is reserved for the correct answer slot.",
                    "A container is a running instance, not the template.",
                    "A volume persists data, it is not the build artifact.",
                    "A network connects containers, it is not the image.",
                ],
                concept=f"docker-basics-{i + 1}",
            )
        )
    return questions


@pytest.fixture
def fake_content_package() -> ContentPackage:
    return ContentPackage(
        generation_mode="curriculum_aware",
        title="Docker for Inference Engineers",
        audience="engineers preparing for production LLM inference",
        summary="A beginner-friendly introduction to packaging FastAPI inference services.",
        article_markdown=(
            "## Why Docker matters\n\n"
            "Imagine you package a FastAPI model-serving app so every environment "
            "starts from the same image.\n\n"
            "Containers help you move from local FastAPI experiments toward "
            "Kubernetes and later vLLM deployments.\n"
        ),
        teaching_example=TeachingExample(
            title="FastAPI inference container",
            scenario=(
                "Suppose you containerize a FastAPI service that loads a small "
                "model library and listens on port 8000."
            ),
            explanation=(
                "The Dockerfile installs Python dependencies once, copies the app, "
                "and exposes port 8000 for repeatable local runs."
            ),
            connection_to_goal=(
                "The same image becomes the unit you later schedule on Kubernetes "
                "before specializing for vLLM and monitoring."
            ),
            is_hypothetical=True,
        ),
        quiz=make_quiz(),
        source_references=[
            SourceReference(
                title="Docker knowledge pack",
                reference="data/knowledge/docker.md",
                source_type="knowledge_pack",
            )
        ],
        claim_warnings=[],
        publication_readiness=PublicationReadiness(
            status="needs_review",
            checklist=["Manual review required"],
            blocking_issues=[],
        ),
        prompt_version="v1",
    )


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client):
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "changeme"},
        follow_redirects=False,
    )
    assert response.status_code in (303, 302)
    return client
