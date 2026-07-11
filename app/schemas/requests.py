"""Request schemas for content generation and editing."""

from typing import Literal

from pydantic import BaseModel, Field


class ContentGenerateRequest(BaseModel):
    """API request body for generating a content package."""

    topic: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    note_ids: list[int] = Field(default_factory=list)
    audience: str = Field(default="engineers preparing for production LLM inference")
    content_type: Literal["tutorial", "linkedin_post", "project_update"] = "tutorial"
    tone: str = Field(default="clear, practical, beginner-friendly")
    desired_length: Literal["short", "medium", "long"] = "medium"
    include_quiz: bool = True


class ContentApproveRequest(BaseModel):
    """Optional body for approval endpoints."""

    reviewer_notes: str | None = None


class ContentEditRequest(BaseModel):
    """Editable fields for author review before publish."""

    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    article_markdown: str = Field(min_length=1)
    teaching_example_json: dict
    quiz_json: list[dict]
    sources_json: list[dict]
