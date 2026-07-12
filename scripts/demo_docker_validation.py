"""Demonstrate deterministic Docker article validation gates (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.content import (  # noqa: E402
    ContentPackage,
    PublicationReadiness,
    QuizQuestion,
    SourceReference,
    TeachingExample,
)
from app.services.validation_service import (  # noqa: E402
    UNTESTED_COMMAND_WARNING,
    validate_content_package,
)

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

The health endpoint should return JSON with `"status": "ok"`.

## Common confusions

- EXPOSE is documentation; `-p` publishes the port.

## Limitations

Docker packages dependencies and process isolation. It does not install NVIDIA drivers,
guarantee GPU access, fix architecture mismatches, or replace orchestration.

## Practice exercise

1. Create the Dockerfile and `app.py` above.
2. Build and run with `-p 8000:8080`.
3. Call `/health` and `/infer` from the host.

## What to learn next

Compose, then Kubernetes, then GPU device plugins.
"""


def _quiz() -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []
    for i in range(5):
        questions.append(
            QuizQuestion(
                question=f"Docker concept question {i + 1}?",
                choices=["Image", "Container", "Volume", "Network"],
                correct_index=0,
                correct_explanation="An image is the immutable template.",
                incorrect_explanations=[
                    "Reserved for correct answer.",
                    "Container is a running instance.",
                    "Volume persists data.",
                    "Network connects containers.",
                ],
                concept=f"docker-basics-{i + 1}",
            )
        )
    return questions


def _base_package(**overrides) -> ContentPackage:
    data = dict(
        generation_mode="curriculum_aware",
        title="Docker for Inference Engineers",
        audience="engineers preparing for production LLM inference",
        summary="Mock FastAPI inference packaging with Docker.",
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
                "main article. No real GPU weights are required."
            ),
            connection_to_goal="Same packaging unit later moves toward Kubernetes.",
            is_hypothetical=True,
        ),
        quiz=_quiz(),
        source_references=[
            SourceReference(
                title="Docker knowledge pack",
                reference="data/knowledge/docker.md",
                source_type="knowledge_pack",
                supports_claim="EXPOSE vs published host ports",
            )
        ],
        claim_warnings=[],
        publication_readiness=PublicationReadiness(status="needs_review"),
        prompt_version="v1",
    )
    data.update(overrides)
    return ContentPackage(**data)


def main() -> None:
    print("=== 1. Quality mocked Docker article ===")
    good = validate_content_package(_base_package(), topic="Docker")
    print(f"status={good.publication_readiness.status}")
    print(f"blocking={good.publication_readiness.blocking_issues}")
    print(f"has dockerfile fence={'```dockerfile' in good.article_markdown}")
    print(
        "untested warning present="
        f"{any(w.reason == UNTESTED_COMMAND_WARNING for w in good.claim_warnings)}"
    )
    print(f"exact warning text:\n  {UNTESTED_COMMAND_WARNING}")

    print("\n=== 2. Placeholder source rejected ===")
    bad_src = _base_package(
        source_references=[
            SourceReference(
                title="Example",
                reference="https://example.learningpath.com/docker",
                source_type="other",
                supports_claim="ports",
            )
        ]
    )
    result = validate_content_package(bad_src, topic="Docker")
    print(f"status={result.publication_readiness.status}")
    print(f"blocking={result.publication_readiness.blocking_issues}")

    print("\n=== 3. Duplicate title rejected ===")
    bad_title = _base_package(
        article_markdown="# Docker for Inference Engineers\n\n" + QUALITY_DOCKER_ARTICLE
    )
    result = validate_content_package(bad_title, topic="Docker")
    print(f"status={result.publication_readiness.status}")
    print(
        "blocking="
        f"{[i for i in result.publication_readiness.blocking_issues if 'title' in i.lower()]}"
    )

    print("\n=== 4. Publication remains blocked until fixed ===")
    broken = _base_package(
        article_markdown=(
            "# Docker for Inference Engineers\n\n"
            + QUALITY_DOCKER_ARTICLE
            + "\ndocker run --rm broken\n"
            + "\nThis image behaves the same everywhere and is production-ready.\n"
        ),
        source_references=[
            SourceReference(
                title="Example",
                reference="https://example.com/x",
                source_type="other",
                supports_claim="x",
            )
        ],
    )
    result = validate_content_package(broken, topic="Docker")
    print(f"status={result.publication_readiness.status}")
    print(f"issue_count={len(result.publication_readiness.blocking_issues)}")
    for issue in result.publication_readiness.blocking_issues:
        print(f"  - {issue}")
    fixed = validate_content_package(_base_package(), topic="Docker")
    print(f"after fix: status={fixed.publication_readiness.status}")


if __name__ == "__main__":
    main()
