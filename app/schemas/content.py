"""Pydantic schemas for structured content packages."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceReference(BaseModel):
    """A cited source used to ground article claims."""

    title: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    source_type: Literal["knowledge_pack", "notes", "learning_path", "other"] = (
        "knowledge_pack"
    )


class ClaimWarning(BaseModel):
    """A warning about a questionable or unsupported claim."""

    claim: str
    reason: str
    severity: Literal["info", "warning", "error"] = "warning"


class PublicationReadiness(BaseModel):
    """Checklist describing whether content is ready to publish."""

    status: Literal["needs_review", "approved", "blocked"] = "needs_review"
    checklist: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    notes: str = ""


class TeachingExample(BaseModel):
    """An original teaching example tied to the learning path."""

    title: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    connection_to_goal: str = Field(min_length=1)
    is_hypothetical: bool = True


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question with explanations."""

    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    correct_explanation: str = Field(min_length=1)
    incorrect_explanations: list[str] = Field(min_length=4, max_length=4)
    concept: str = Field(min_length=1)

    @field_validator("choices")
    @classmethod
    def choices_nonempty(cls, value: list[str]) -> list[str]:
        if any(not choice.strip() for choice in value):
            raise ValueError("Each quiz choice must be nonempty")
        return value

    @field_validator("incorrect_explanations")
    @classmethod
    def explanations_nonempty(cls, value: list[str]) -> list[str]:
        if any(not explanation.strip() for explanation in value):
            raise ValueError("Each incorrect explanation must be nonempty")
        return value


class ContentPackage(BaseModel):
    """Structured output produced by the content agent."""

    generation_mode: Literal["notes_grounded", "curriculum_aware"]
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    article_markdown: str = Field(min_length=1)
    teaching_example: TeachingExample
    quiz: list[QuizQuestion] = Field(min_length=5, max_length=5)
    source_references: list[SourceReference] = Field(min_length=1)
    claim_warnings: list[ClaimWarning] = Field(default_factory=list)
    publication_readiness: PublicationReadiness
    prompt_version: str = Field(min_length=1)
