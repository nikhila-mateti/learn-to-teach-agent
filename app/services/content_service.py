"""Content lifecycle, persistence, and publishing services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.content_agent import run_content_agent
from app.config import Settings, get_settings
from app.models.content import ContentItem, Note
from app.schemas.content import ContentPackage, QuizQuestion
from app.schemas.requests import ContentGenerateRequest
from app.services.markdown_service import markdown_to_safe_html
from app.services.validation_service import validate_content_package, validate_quiz

VALID_TRANSITIONS = {
    "draft": {"needs_review"},
    "needs_review": {"approved"},
    "approved": {"published"},
    "published": {"approved"},
}


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:180] or "article"


def notes_are_meaningful(notes: str | None) -> bool:
    if not notes:
        return False
    cleaned = notes.strip()
    if len(cleaned) < 80:
        return False
    generic_markers = [
        "in today's fast-paced world",
        "delve into",
        "game-changer",
        "revolutionize",
    ]
    lowered = cleaned.lower()
    if sum(1 for marker in generic_markers if marker in lowered) >= 2:
        return False
    return True


def gather_notes_text(db: Session, request: ContentGenerateRequest) -> str:
    parts: list[str] = []
    if request.notes and request.notes.strip():
        parts.append(request.notes.strip())
    if request.note_ids:
        rows = db.scalars(select(Note).where(Note.id.in_(request.note_ids))).all()
        for row in rows:
            parts.append(f"# {row.title}\n\n{row.content}")
    return "\n\n---\n\n".join(parts)


def generate_and_persist(
    db: Session,
    request: ContentGenerateRequest,
    *,
    settings: Settings | None = None,
    model: Any | None = None,
) -> ContentItem:
    """Run the agent, validate, and store content as needs_review."""
    settings = settings or get_settings()
    settings.require_llm_credentials()
    combined_notes = gather_notes_text(db, request)
    package = run_content_agent(
        topic=request.topic,
        notes=combined_notes if notes_are_meaningful(combined_notes) else combined_notes,
        audience=request.audience,
        content_type=request.content_type,
        tone=request.tone,
        desired_length=request.desired_length,
        include_quiz=request.include_quiz,
        settings=settings,
        model=model,
    )
    # Force curriculum-aware when notes are weak/missing regardless of model claim.
    if not notes_are_meaningful(combined_notes):
        package.generation_mode = "curriculum_aware"
    else:
        package.generation_mode = "notes_grounded"

    package = validate_content_package(package)
    if package.publication_readiness.blocking_issues:
        raise ValueError(
            "Generated content failed validation: "
            + "; ".join(package.publication_readiness.blocking_issues)
        )

    return persist_package(db, package, request, settings)


def persist_package(
    db: Session,
    package: ContentPackage,
    request: ContentGenerateRequest,
    settings: Settings,
) -> ContentItem:
    base_slug = slugify(package.title)
    slug = base_slug
    counter = 1
    while db.scalar(select(ContentItem.id).where(ContentItem.slug == slug)):
        counter += 1
        slug = f"{base_slug}-{counter}"

    item = ContentItem(
        title=package.title,
        slug=slug,
        topic=request.topic,
        summary=package.summary,
        article_markdown=package.article_markdown,
        article_html=markdown_to_safe_html(package.article_markdown),
        teaching_example_json=package.teaching_example.model_dump(),
        quiz_json=[q.model_dump() for q in package.quiz],
        sources_json=[s.model_dump() for s in package.source_references],
        warnings_json=[w.model_dump() for w in package.claim_warnings],
        publication_readiness_json=package.publication_readiness.model_dump(),
        request_input_json=request.model_dump(),
        generation_mode=package.generation_mode,
        status="needs_review",
        model_provider=settings.llm_provider,
        model_name=settings.model_name,
        prompt_version=package.prompt_version or settings.prompt_version,
        audience=package.audience,
        content_type=request.content_type,
        manual_review_status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_content(db: Session, content_id: int) -> ContentItem | None:
    return db.get(ContentItem, content_id)


def get_published_by_slug(db: Session, slug: str) -> ContentItem | None:
    return db.scalar(
        select(ContentItem).where(
            ContentItem.slug == slug,
            ContentItem.status == "published",
        )
    )


def list_published(db: Session) -> list[ContentItem]:
    return list(
        db.scalars(
            select(ContentItem)
            .where(ContentItem.status == "published")
            .order_by(ContentItem.published_at.desc())
        ).all()
    )


def list_content_by_status(db: Session, status: str | None = None) -> list[ContentItem]:
    stmt = select(ContentItem).order_by(ContentItem.updated_at.desc())
    if status:
        stmt = stmt.where(ContentItem.status == status)
    return list(db.scalars(stmt).all())


def dashboard_stats(db: Session) -> dict[str, int]:
    def count_status(status: str) -> int:
        return db.scalar(
            select(func.count()).select_from(ContentItem).where(ContentItem.status == status)
        ) or 0

    notes_count = db.scalar(select(func.count()).select_from(Note)) or 0
    return {
        "notes": notes_count,
        "draft": count_status("draft"),
        "needs_review": count_status("needs_review"),
        "approved": count_status("approved"),
        "published": count_status("published"),
    }


def update_content(
    db: Session,
    item: ContentItem,
    *,
    title: str,
    slug: str,
    summary: str,
    article_markdown: str,
    teaching_example_json: dict[str, Any],
    quiz_json: list[dict[str, Any]],
    sources_json: list[dict[str, Any]],
) -> ContentItem:
    quiz_issues = validate_quiz(quiz_json)
    if quiz_issues:
        raise ValueError("; ".join(quiz_issues))
    # Ensure each question validates as QuizQuestion
    for raw in quiz_json:
        QuizQuestion.model_validate(raw)

    slug = slugify(slug)
    existing = db.scalar(
        select(ContentItem).where(ContentItem.slug == slug, ContentItem.id != item.id)
    )
    if existing:
        raise ValueError("Duplicate slug rejected")

    item.title = title
    item.slug = slug
    item.summary = summary
    item.article_markdown = article_markdown
    item.article_html = markdown_to_safe_html(article_markdown)
    item.teaching_example_json = teaching_example_json
    item.quiz_json = quiz_json
    item.sources_json = sources_json
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return item


def transition_status(item: ContentItem, new_status: str) -> None:
    allowed = VALID_TRANSITIONS.get(item.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition from {item.status} to {new_status}"
        )
    item.status = new_status


def approve_content(db: Session, item: ContentItem) -> ContentItem:
    transition_status(item, "approved")
    item.manual_review_status = "approved"
    item.approved_at = datetime.now(UTC)
    item.updated_at = datetime.now(UTC)
    readiness = dict(item.publication_readiness_json or {})
    readiness["status"] = "approved"
    item.publication_readiness_json = readiness
    db.commit()
    db.refresh(item)
    return item


def publish_content(db: Session, item: ContentItem, settings: Settings | None = None) -> ContentItem:
    settings = settings or get_settings()
    if item.status != "approved":
        raise ValueError("Only approved content can be published")
    if not item.title.strip() or not item.slug.strip() or not item.article_markdown.strip():
        raise ValueError("Title, slug, and article content are required to publish")
    quiz_issues = validate_quiz(item.quiz_json or [])
    if quiz_issues:
        raise ValueError("; ".join(quiz_issues))
    transition_status(item, "published")
    item.published_at = datetime.now(UTC)
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return item


def unpublish_content(db: Session, item: ContentItem) -> ContentItem:
    if item.status != "published":
        raise ValueError("Only published content can be unpublished")
    transition_status(item, "approved")
    item.published_at = None
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return item


def public_url(item: ContentItem, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return f"{settings.public_base_url.rstrip('/')}/blog/{item.slug}"


def create_note(
    db: Session,
    *,
    title: str,
    topic: str,
    content: str,
    original_filename: str | None,
    file_type: str,
) -> Note:
    note = Note(
        title=title,
        topic=topic,
        content=content,
        original_filename=original_filename,
        file_type=file_type,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(db: Session) -> list[Note]:
    return list(db.scalars(select(Note).order_by(Note.updated_at.desc())).all())


def content_to_dict(item: ContentItem, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    return {
        "id": item.id,
        "title": item.title,
        "slug": item.slug,
        "topic": item.topic,
        "summary": item.summary,
        "article_markdown": item.article_markdown,
        "article_html": item.article_html,
        "teaching_example": item.teaching_example_json,
        "quiz": item.quiz_json,
        "sources": item.sources_json,
        "warnings": item.warnings_json,
        "publication_readiness": item.publication_readiness_json,
        "generation_mode": item.generation_mode,
        "status": item.status,
        "model_provider": item.model_provider,
        "model_name": item.model_name,
        "prompt_version": item.prompt_version,
        "audience": item.audience,
        "content_type": item.content_type,
        "approved_at": item.approved_at.isoformat() if item.approved_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "public_url": public_url(item, settings) if item.status == "published" else None,
    }


def safe_commit_slug(db: Session, item: ContentItem) -> ContentItem:
    try:
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Duplicate slug rejected") from exc
