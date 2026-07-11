"""SQLAlchemy models for notes and content items."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSON().with_variant(JSONB(), "postgresql"),
        list[Any]: JSON().with_variant(JSONB(), "postgresql"),
    }


class Note(Base):
    """Author learning notes stored in PostgreSQL."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ContentItem(Base):
    """Generated and edited teaching content with publication lifecycle."""

    __tablename__ = "content_items"
    __table_args__ = (UniqueConstraint("slug", name="uq_content_items_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    article_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    article_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    teaching_example_json: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    quiz_json: Mapped[list[Any]] = mapped_column(nullable=False)
    sources_json: Mapped[list[Any]] = mapped_column(nullable=False)
    warnings_json: Mapped[list[Any]] = mapped_column(nullable=False, default=list)
    publication_readiness_json: Mapped[dict[str, Any]] = mapped_column(
        nullable=False, default=dict
    )
    request_input_json: Mapped[dict[str, Any]] = mapped_column(
        nullable=False, default=dict
    )
    generation_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="needs_review", index=True
    )
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    audience: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="tutorial")
    manual_review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
