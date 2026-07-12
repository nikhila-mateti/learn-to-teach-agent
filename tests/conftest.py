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

QUALITY_DOCKER_ARTICLE = """## Problem statement: why Docker matters for inference

Packaging a FastAPI mock-inference service is hard when Python dependencies, ports,
and optional model weights differ between laptops. Docker gives you a repeatable
build unit without promising identical runtime on every host, OS, architecture, or GPU.

## Prerequisites

- Basic Python and terminal familiarity
- Docker Engine installed locally
- Comfort reading a short Dockerfile

## Concept sequence

1. **Dockerfile** — instructions that build an image.
2. **Image** — the immutable layered template.
3. **Container** — a running instance of an image.
4. **Host port vs container port** — `-p 8000:8080` maps host `8000` to container `8080`.
5. **Request flow** — client → host port → published mapping → FastAPI in the container.
6. **Dependency packaging** — install Python deps in the image so rebuilds are predictable.
7. **EXPOSE** — documents the intended container port; it does not publish that port alone.

## Runnable technical example

Build a mock `/infer` FastAPI service (no real model weights required):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

```python
from fastapi import FastAPI

app = FastAPI()
# Mock "model load" — no real weights.
MODEL = {"name": "mock-embedder", "ready": True}

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL["name"]}

@app.post("/infer")
def infer(payload: dict):
    text = payload.get("text", "")
    return {"embedding_dim": 8, "token_count": len(text.split())}
```

```bash
docker build -t fastapi-inference:dev .
docker run --rm -p 8000:8080 fastapi-inference:dev
curl -s http://127.0.0.1:8000/health
```

### Expected behavior

The health endpoint should return JSON with `"status": "ok"`. Requests hit host port
8000 and reach the process listening on container port 8080.

## Common confusions

- EXPOSE is documentation; `-p` publishes the port.
- An image is not a running service; a container is.
- Copying secrets into the image is a risk; inject them at runtime.

## Limitations

Docker packages dependencies and process isolation. It does not install NVIDIA drivers,
guarantee GPU access, fix architecture mismatches, or replace orchestration, quotas,
or monitoring. Resource limits still matter when loading weights.

## Practice exercise

1. Create the Dockerfile and `app.py` above.
2. Build and run with `-p 8000:8080`.
3. Call `/health` and `/infer` from the host.
4. Change only the host port mapping and confirm the container port stays 8080.

## What to learn next

Compose for multi-service local stacks, then Kubernetes scheduling, then GPU device
plugins and specialized inference runtimes.
"""


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
        summary=(
            "A beginner-friendly introduction to packaging a mock FastAPI "
            "inference service with Docker."
        ),
        article_markdown=QUALITY_DOCKER_ARTICLE,
        teaching_example=TeachingExample(
            title="Mock FastAPI inference with mounted weights",
            scenario=(
                "Imagine a FastAPI API that loads mock model-loading code at startup, "
                "installs Python dependencies in the image, mounts optional model weights "
                "read-only at /models, listens on internal container port 8080, publishes "
                "host port 8000, and exposes a /health endpoint before /infer accepts traffic."
            ),
            explanation=(
                "This hypothetical scenario adds mounting and health-gate detail beyond the "
                "main article's basic Dockerfile. The container does not need real GPU weights; "
                "the mount keeps the image small while dependency packaging stays in the build."
            ),
            connection_to_goal=(
                "The same packaging pattern becomes the unit you later schedule on Kubernetes "
                "before specializing for GPU drivers, vLLM, and monitoring."
            ),
            is_hypothetical=True,
        ),
        quiz=make_quiz(),
        source_references=[
            SourceReference(
                title="Docker knowledge pack",
                reference="data/knowledge/docker.md",
                source_type="knowledge_pack",
                supports_claim=(
                    "EXPOSE documents the container port and does not publish it; "
                    "host vs container port mapping uses -p"
                ),
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
