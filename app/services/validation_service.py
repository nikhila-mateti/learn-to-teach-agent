"""Deterministic validation of agent ContentPackage output."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from app.schemas.content import (
    ClaimWarning,
    ContentPackage,
    PublicationReadiness,
    QuizQuestion,
)

FIRST_PERSON_PATTERNS = [
    re.compile(r"\bI spent\b", re.I),
    re.compile(r"\bWhen I deployed\b", re.I),
    re.compile(r"\bI tested this in production\b", re.I),
    re.compile(r"\bI achieved\b", re.I),
    re.compile(r"\bI debugged\b", re.I),
    re.compile(r"\bmy application\b", re.I),
    re.compile(r"\bI ran into\b", re.I),
    re.compile(r"\bIn my experience\b", re.I),
]

METRIC_PATTERN = re.compile(
    r"\b(\d{1,3})\s*%\s*(improvement|faster|slower|reduction|increase|decrease)\b",
    re.I,
)
ABSOLUTE_PATTERN = re.compile(
    r"\b(always|never|guarantees|completely|100%\s+reliable)\b", re.I
)
GENERIC_AI_PHRASES = [
    "delve",
    "game-changer",
    "revolutionize",
    "testament",
    "in today's fast-paced world",
]
TESTED_COMMAND_PATTERN = re.compile(
    r"\b(I tested|we tested|verified in production|confirmed working)\b", re.I
)


def _collect_text(package: ContentPackage) -> str:
    parts = [
        package.title,
        package.summary,
        package.article_markdown,
        package.teaching_example.scenario,
        package.teaching_example.explanation,
        package.teaching_example.connection_to_goal,
    ]
    return "\n".join(parts)


def validate_quiz(quiz: list[QuizQuestion] | list[dict[str, Any]]) -> list[str]:
    """Validate quiz structure; return blocking issues."""
    issues: list[str] = []
    if len(quiz) != 5:
        issues.append(f"Quiz must contain exactly 5 questions, found {len(quiz)}")
        return issues

    for index, raw in enumerate(quiz):
        try:
            question = (
                raw if isinstance(raw, QuizQuestion) else QuizQuestion.model_validate(raw)
            )
        except ValidationError as exc:
            issues.append(f"Quiz question {index + 1} invalid: {exc.errors()[0]['msg']}")
            continue
        if len(question.choices) != 4:
            issues.append(f"Quiz question {index + 1} must have exactly 4 choices")
        if not (0 <= question.correct_index <= 3):
            issues.append(f"Quiz question {index + 1} correct_index out of range")
        if not question.correct_explanation.strip():
            issues.append(f"Quiz question {index + 1} missing correct explanation")
        if len(question.incorrect_explanations) != 4:
            issues.append(
                f"Quiz question {index + 1} must explain all four choice outcomes"
            )
        elif any(not item.strip() for item in question.incorrect_explanations):
            issues.append(f"Quiz question {index + 1} has empty incorrect explanations")
    return issues


def validate_content_package(
    raw: ContentPackage | dict[str, Any],
    *,
    commands_tested: bool = False,
) -> ContentPackage:
    """
    Validate structured output and attach claim warnings.

    Does not silently delete questionable content; records warnings and sets
    publication status to needs_review unless already blocked.
    """
    try:
        package = (
            raw
            if isinstance(raw, ContentPackage)
            else ContentPackage.model_validate(raw)
        )
    except ValidationError as exc:
        raise ValueError(f"Invalid ContentPackage: {exc}") from exc

    warnings = list(package.claim_warnings)
    blocking = list(package.publication_readiness.blocking_issues)
    checklist = list(package.publication_readiness.checklist)

    text = _collect_text(package)

    if package.generation_mode == "curriculum_aware":
        for pattern in FIRST_PERSON_PATTERNS:
            if pattern.search(text):
                warnings.append(
                    ClaimWarning(
                        claim=pattern.pattern,
                        reason=(
                            "Unsupported first-person experience claim in "
                            "curriculum-aware mode"
                        ),
                        severity="warning",
                    )
                )

    for match in METRIC_PATTERN.finditer(text):
        warnings.append(
            ClaimWarning(
                claim=match.group(0),
                reason="Numeric performance claim without supporting evidence",
                severity="warning",
            )
        )

    for match in ABSOLUTE_PATTERN.finditer(text):
        warnings.append(
            ClaimWarning(
                claim=match.group(0),
                reason="Absolute claim that may overstate certainty",
                severity="info",
            )
        )

    lowered = text.lower()
    for phrase in GENERIC_AI_PHRASES:
        if phrase in lowered:
            warnings.append(
                ClaimWarning(
                    claim=phrase,
                    reason="Generic AI phrasing detected",
                    severity="info",
                )
            )

    if not commands_tested and TESTED_COMMAND_PATTERN.search(text):
        warnings.append(
            ClaimWarning(
                claim="tested/verified command claim",
                reason="Commands presented as tested without application evidence",
                severity="warning",
            )
        )

    if not package.source_references:
        blocking.append("At least one approved source reference is required")
    else:
        checklist.append("Source references present")

    quiz_issues = validate_quiz(package.quiz)
    blocking.extend(quiz_issues)
    if not quiz_issues:
        checklist.append("Quiz schema valid (5 questions, 4 choices each)")

    checklist.append("Manual review required before publish")
    status = "blocked" if blocking else "needs_review"

    package.claim_warnings = warnings
    package.publication_readiness = PublicationReadiness(
        status=status,
        checklist=checklist,
        blocking_issues=blocking,
        notes=package.publication_readiness.notes,
    )
    return package
