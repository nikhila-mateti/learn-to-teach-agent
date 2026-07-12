"""Deterministic validation of agent ContentPackage output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import get_settings
from app.schemas.content import (
    ClaimWarning,
    ContentPackage,
    PublicationReadiness,
    QuizQuestion,
    SourceReference,
)

UNTESTED_COMMAND_WARNING = (
    "Commands have not been automatically executed or verified. "
    "Run them in a safe local environment before publishing."
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

OVERCLAIM_PATTERNS = [
    (
        re.compile(r"\bbehaves? the same everywhere\b", re.I),
        "Overclaim: identical behavior everywhere",
    ),
    (
        re.compile(r"\bguarantees?\s+reproducibility\b", re.I),
        "Overclaim: guarantees reproducibility",
    ),
    (
        re.compile(r"\beliminates?\s+dependency problems?\b", re.I),
        "Overclaim: eliminates dependency problems",
    ),
    (
        re.compile(r"\bproduction[- ]ready\b", re.I),
        "Overclaim: production-ready without qualification",
    ),
    (
        re.compile(r"\bguarantees?\b", re.I),
        "Absolute 'guarantees' claim without qualification",
    ),
    (
        re.compile(r"\bidentical (behavior|results|environment)s?\b", re.I),
        "Overclaim: identical behavior/results",
    ),
]

ABSOLUTE_PATTERN = re.compile(r"\b(always|never|completely|100%\s+reliable)\b", re.I)

GENERIC_AI_PHRASES = [
    "delve",
    "game-changer",
    "revolutionize",
    "testament",
    "in today's fast-paced world",
    "in conclusion, docker is essential",
    "unlock the power",
    "seamlessly",
]

TESTED_COMMAND_PATTERN = re.compile(
    r"\b(I tested|we tested|verified in production|confirmed working|"
    r"ran successfully in production|executed in production)\b",
    re.I,
)

PLACEHOLDER_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(example\.com|example\.org|example\.net|"
    r"example\.learningpath\.com|placeholder\.[a-z]+|yourdomain\.[a-z]+|"
    r"domain\.com|test\.com)\b",
    re.I,
)

CODE_FENCE_PATTERN = re.compile(r"```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```", re.M)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
ALLOWED_FENCE_LANGS = {
    "",
    "bash",
    "sh",
    "shell",
    "zsh",
    "dockerfile",
    "docker",
    "python",
    "py",
    "json",
    "yaml",
    "yml",
    "toml",
    "text",
    "markdown",
    "md",
    "console",
    "http",
}

UNFENCED_DOCKERFILE_LINE = re.compile(
    r"^\s*(FROM|RUN|COPY|ADD|EXPOSE|CMD|ENTRYPOINT|WORKDIR|ENV|ARG|USER|VOLUME)\s+\S+"
)
UNFENCED_SHELL_LINE = re.compile(
    r"^\s*(docker\s+(build|run|compose|pull|push|image|ps|logs|exec|stop|rm|volume|network)\b|"
    r"pip\s+install\b|uvicorn\s+\S+|apt-get\s+\S+|python\s+-m\s+\S+|curl\s+https?://\S+)",
    re.I,
)

REQUIRED_SECTION_PATTERNS = [
    (
        re.compile(r"^#{2,3}\s+.*(problem|why .+ matter)", re.I | re.M),
        "problem statement",
    ),
    (re.compile(r"^#{2,3}\s+.*prerequisite", re.I | re.M), "prerequisites"),
    (re.compile(r"^#{2,3}\s+.*concept", re.I | re.M), "concept sequence"),
    (re.compile(r"^#{2,3}\s+.*limitation", re.I | re.M), "limitations"),
    (
        re.compile(r"^#{2,3}\s+.*(practice|exercise)", re.I | re.M),
        "practical exercise",
    ),
    (
        re.compile(r"^#{2,3}\s+.*(common confusion|confusion)", re.I | re.M),
        "common confusions",
    ),
    (
        re.compile(
            r"^#{2,3}\s+.*(what to learn next|next step|next topic)", re.I | re.M
        ),
        "what to learn next",
    ),
]

HYPOTHETICAL_MARKERS = ("imagine", "suppose", "consider")

NEGATION_BEFORE_CLAIM = re.compile(
    r"(does\s+not|do\s+not|don't|cannot|can\s+not|without|not)\b.{0,40}$",
    re.I | re.S,
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


def _strip_code_fences(markdown: str) -> str:
    return CODE_FENCE_PATTERN.sub("", markdown)


def _paragraphs(markdown: str) -> list[str]:
    chunks = [p.strip() for p in re.split(r"\n\s*\n", markdown) if p.strip()]
    return chunks


def _claim_is_negated(text: str, start: int) -> bool:
    """True when the claim is already qualified/negated in nearby context."""
    prefix = text[max(0, start - 60) : start]
    return bool(NEGATION_BEFORE_CLAIM.search(prefix))


def validate_quiz(quiz: list[QuizQuestion] | list[dict[str, Any]]) -> list[str]:
    """Validate quiz structure; return blocking issues."""
    issues: list[str] = []
    if len(quiz) != 5:
        issues.append(f"Quiz must contain exactly 5 questions, found {len(quiz)}")
        return issues

    for index, raw in enumerate(quiz):
        try:
            question = (
                raw
                if isinstance(raw, QuizQuestion)
                else QuizQuestion.model_validate(raw)
            )
        except ValidationError as exc:
            issues.append(
                f"Quiz question {index + 1} invalid: {exc.errors()[0]['msg']}"
            )
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


def _approved_source_lines(topic: str | None) -> list[str]:
    if not topic:
        return []
    settings = get_settings()
    slug = topic.strip().lower().replace(" ", "-")
    path = Path(settings.data_dir) / "knowledge" / f"{slug}.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    collecting = False
    collected: list[str] = []
    for line in lines:
        if line.strip().lower() == "## source references":
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting:
            stripped = line.strip().lstrip("-").strip()
            if stripped:
                collected.append(stripped)
    # Always allow explicit local knowledge pack path references.
    collected.append(f"data/knowledge/{slug}.md")
    collected.append("learning_path.json")
    collected.append("data/learning_path.json")
    return collected


def validate_sources(
    sources: list[SourceReference],
    *,
    topic: str | None,
) -> tuple[list[str], list[ClaimWarning]]:
    blocking: list[str] = []
    warnings: list[ClaimWarning] = []
    if not sources:
        blocking.append("At least one approved source reference is required")
        return blocking, warnings

    approved = _approved_source_lines(topic)
    approved_lower = [item.lower() for item in approved]

    for source in sources:
        if not source.title.strip():
            blocking.append("Source title is empty")
        if not source.reference.strip():
            blocking.append("Source reference is empty")
        if not source.supports_claim.strip():
            blocking.append("Source is not associated with a specific claim or section")

        blob = f"{source.title} {source.reference}".lower()
        if PLACEHOLDER_URL_PATTERN.search(blob) or "example.com" in blob:
            blocking.append(f"Placeholder source rejected: {source.reference}")
            warnings.append(
                ClaimWarning(
                    claim=source.reference,
                    reason="Placeholder or example domain is not an approved source",
                    severity="error",
                )
            )
            continue

        if source.source_type not in {"knowledge_pack", "learning_path", "notes"}:
            blocking.append(
                f"Source type '{source.source_type}' is not grounded in approved local data"
            )

        if approved_lower:
            grounded = any(
                allowed in blob
                or blob in allowed
                or source.reference.lower() in allowed
                for allowed in approved_lower
            )
            # Also accept exact local file references and pack titles.
            grounded = grounded or any(
                token in blob
                for token in (
                    "knowledge pack",
                    "learning path",
                    "official docker documentation",
                    f"data/knowledge/{(topic or '').strip().lower().replace(' ', '-')}.md",
                )
            )
            if not grounded:
                blocking.append(
                    f"Source is not from the approved knowledge pack or learning path: "
                    f"{source.title}"
                )
    return blocking, warnings


def validate_markdown_quality(
    title: str,
    markdown: str,
) -> tuple[list[str], list[ClaimWarning]]:
    blocking: list[str] = []
    warnings: list[ClaimWarning] = []

    headings = HEADING_PATTERN.findall(markdown)
    h1_texts = [text.strip() for level, text in headings if len(level) == 1]
    if len(h1_texts) > 1:
        blocking.append("Duplicate H1 headings found in article markdown")
    if any(text.strip().lower() == title.strip().lower() for text in h1_texts):
        blocking.append("Duplicate title: article H1 repeats the package title")

    # Consecutive repeated headings
    normalized_heads = [text.strip().lower() for _, text in headings]
    for index in range(1, len(normalized_heads)):
        if normalized_heads[index] == normalized_heads[index - 1]:
            blocking.append(f"Consecutive repeated heading: {normalized_heads[index]}")

    for match in CODE_FENCE_PATTERN.finditer(markdown):
        lang = (match.group(1) or "").strip().lower()
        body = match.group(2)
        if not body.strip():
            blocking.append("Empty code fence detected")
        if lang not in ALLOWED_FENCE_LANGS:
            blocking.append(f"Invalid code fence language label: {lang or '(empty)'}")

    outside = _strip_code_fences(markdown)
    for line in outside.splitlines():
        if UNFENCED_DOCKERFILE_LINE.search(line) or UNFENCED_SHELL_LINE.search(line):
            blocking.append(
                "Code-like shell/Dockerfile content found outside fenced Markdown blocks"
            )
            break

    if PLACEHOLDER_URL_PATTERN.search(markdown):
        blocking.append("Placeholder URL found in article markdown")

    paras = _paragraphs(outside)
    seen: set[str] = set()
    for para in paras:
        key = re.sub(r"\s+", " ", para.lower())
        if len(key) < 40:
            continue
        if key in seen:
            blocking.append("Duplicate paragraph detected in article markdown")
            break
        seen.add(key)

    for pattern, label in REQUIRED_SECTION_PATTERNS:
        if not pattern.search(markdown):
            blocking.append(f"Article missing required section: {label}")

    return blocking, warnings


def validate_claims(
    text: str,
    *,
    generation_mode: str,
    commands_tested: bool,
    has_command_like_content: bool,
) -> tuple[list[str], list[ClaimWarning]]:
    blocking: list[str] = []
    warnings: list[ClaimWarning] = []

    if generation_mode == "curriculum_aware":
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
                blocking.append(
                    "Unsupported first-person claims remain in curriculum-aware mode"
                )

    for match in METRIC_PATTERN.finditer(text):
        warnings.append(
            ClaimWarning(
                claim=match.group(0),
                reason="Numeric performance claim without supporting evidence",
                severity="warning",
            )
        )
        blocking.append("Unsupported numeric performance claims remain")

    for pattern, reason in OVERCLAIM_PATTERNS:
        for match in pattern.finditer(text):
            if _claim_is_negated(text, match.start()):
                continue
            warnings.append(
                ClaimWarning(claim=match.group(0), reason=reason, severity="error")
            )
            blocking.append(f"Unsupported claim remains: {reason}")
            break

    for match in ABSOLUTE_PATTERN.finditer(text):
        if _claim_is_negated(text, match.start()):
            continue
        warnings.append(
            ClaimWarning(
                claim=match.group(0),
                reason="Absolute claim that may overstate certainty",
                severity="warning",
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

    if TESTED_COMMAND_PATTERN.search(text) and not commands_tested:
        warnings.append(
            ClaimWarning(
                claim="tested/verified command claim",
                reason=UNTESTED_COMMAND_WARNING,
                severity="error",
            )
        )
        blocking.append("Commands presented as tested without execution evidence")

    if has_command_like_content and not commands_tested:
        warnings.append(
            ClaimWarning(
                claim="shell or Dockerfile commands",
                reason=UNTESTED_COMMAND_WARNING,
                severity="warning",
            )
        )

    return blocking, warnings


def validate_teaching_example(
    package: ContentPackage,
    *,
    topic: str | None = None,
) -> list[str]:
    blocking: list[str] = []
    example = package.teaching_example
    example_text = f"{example.scenario}\n{example.explanation}".strip()
    article = package.article_markdown.strip()

    if len(example_text) < 120:
        blocking.append("Teaching example is too thin to add a concrete scenario")

    # Require hypothetical framing for hypothetical examples.
    if example.is_hypothetical:
        lowered = example_text.lower()
        if not any(marker in lowered for marker in HYPOTHETICAL_MARKERS):
            blocking.append(
                "Hypothetical teaching example must use Imagine, Suppose, or Consider"
            )

    # Detect near-duplication: large chunk of example already in article.
    compact_example = re.sub(r"\s+", " ", example_text.lower())
    compact_article = re.sub(r"\s+", " ", article.lower())
    if len(compact_example) > 80 and compact_example[:80] in compact_article:
        blocking.append(
            "Teaching example repeats the article instead of adding a scenario"
        )
    if len(compact_example) > 120 and compact_example in compact_article:
        blocking.append(
            "Teaching example is too similar to the article; add distinct scenario detail"
        )

    topic_key = (topic or "").strip().lower()
    if topic_key in {"docker", "docker for inference"} or "docker" in topic_key:
        required_bits = [
            "fastapi",
            "port",
            "dependenc",
            "health",
            "weight",
        ]
        lowered = example_text.lower()
        missing = [bit for bit in required_bits if bit not in lowered]
        if missing:
            blocking.append(
                "Teaching example missing concrete FastAPI/port/dependency/"
                "weights/health detail"
            )
    return blocking


def validate_content_package(
    raw: ContentPackage | dict[str, Any],
    *,
    commands_tested: bool = False,
    topic: str | None = None,
) -> ContentPackage:
    """
    Validate structured output and attach deterministic claim warnings.

    Model-authored warnings are discarded and rebuilt from validation results so
    warning text cannot contradict itself.
    """
    try:
        package = (
            raw
            if isinstance(raw, ContentPackage)
            else ContentPackage.model_validate(raw)
        )
    except ValidationError as exc:
        raise ValueError(f"Invalid ContentPackage: {exc}") from exc

    warnings: list[ClaimWarning] = []
    blocking: list[str] = []
    checklist: list[str] = []

    text = _collect_text(package)
    has_commands = bool(
        CODE_FENCE_PATTERN.search(package.article_markdown)
        or UNFENCED_DOCKERFILE_LINE.search(package.article_markdown)
        or UNFENCED_SHELL_LINE.search(package.article_markdown)
        or re.search(
            r"```(?:bash|sh|shell|dockerfile|docker)\b", package.article_markdown, re.I
        )
    )

    md_blocking, md_warnings = validate_markdown_quality(
        package.title, package.article_markdown
    )
    blocking.extend(md_blocking)
    warnings.extend(md_warnings)

    source_blocking, source_warnings = validate_sources(
        package.source_references, topic=topic
    )
    blocking.extend(source_blocking)
    warnings.extend(source_warnings)
    if not source_blocking:
        checklist.append("Approved grounded source references present")

    claim_blocking, claim_warnings = validate_claims(
        text,
        generation_mode=package.generation_mode,
        commands_tested=commands_tested,
        has_command_like_content=has_commands,
    )
    blocking.extend(claim_blocking)
    warnings.extend(claim_warnings)

    blocking.extend(validate_teaching_example(package, topic=topic))

    quiz_issues = validate_quiz(package.quiz)
    blocking.extend(quiz_issues)
    if not quiz_issues:
        checklist.append("Quiz schema valid (5 questions, 4 choices each)")

    # Deduplicate while preserving order
    deduped_blocking: list[str] = []
    for item in blocking:
        if item not in deduped_blocking:
            deduped_blocking.append(item)

    deduped_warnings: list[ClaimWarning] = []
    seen_warn: set[tuple[str, str]] = set()
    for warning in warnings:
        key = (warning.claim, warning.reason)
        if key not in seen_warn:
            seen_warn.add(key)
            deduped_warnings.append(warning)

    checklist.append("Manual review required before publish")
    status = "blocked" if deduped_blocking else "needs_review"

    package.claim_warnings = deduped_warnings
    package.publication_readiness = PublicationReadiness(
        status=status,
        checklist=checklist,
        blocking_issues=deduped_blocking,
        notes=package.publication_readiness.notes,
    )
    return package
