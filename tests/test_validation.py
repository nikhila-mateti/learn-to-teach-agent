"""Deterministic validation tests for the publication-quality pipeline."""

import re

from app.schemas.content import ClaimWarning, ContentPackage, SourceReference
from app.services.validation_service import (
    UNTESTED_COMMAND_WARNING,
    validate_content_package,
    validate_quiz,
)


def test_unsupported_first_person_detection(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.generation_mode = "curriculum_aware"
    package.article_markdown += (
        "\nI spent hours debugging this container networking issue.\n"
    )
    validated = validate_content_package(package, topic="Docker")
    assert any("first-person" in w.reason.lower() for w in validated.claim_warnings)
    assert validated.publication_readiness.status == "blocked"


def test_fabricated_metric_detection(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += (
        "\nThis approach achieved a 40% improvement in latency.\n"
    )
    validated = validate_content_package(package, topic="Docker")
    assert any(
        "performance claim" in w.reason.lower() for w in validated.claim_warnings
    )
    assert validated.publication_readiness.status == "blocked"


def test_quiz_schema_validation_ok(fake_content_package: ContentPackage):
    assert validate_quiz(fake_content_package.quiz) == []


def test_quiz_schema_validation_bad_count(fake_content_package: ContentPackage):
    issues = validate_quiz(fake_content_package.quiz[:3])
    assert issues
    assert "exactly 5" in issues[0]


def test_requires_source_references(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.source_references = []
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "source reference" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_publication_status_needs_review(fake_content_package: ContentPackage):
    validated = validate_content_package(fake_content_package, topic="Docker")
    assert validated.publication_readiness.status == "needs_review"
    assert validated.publication_readiness.blocking_issues == []


def test_placeholder_source_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.source_references = [
        SourceReference(
            title="Example docs",
            reference="https://example.learningpath.com/docker",
            source_type="other",
            supports_claim="Docker basics",
        )
    ]
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "placeholder" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_empty_source_fields_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.source_references = [
        SourceReference(
            title=" ",
            reference="data/knowledge/docker.md",
            source_type="knowledge_pack",
            supports_claim="ports",
        )
    ]
    # Pydantic min_length=1 may already reject; if constructed via model_construct:
    package.source_references[0] = SourceReference.model_construct(
        title="",
        reference="data/knowledge/docker.md",
        source_type="knowledge_pack",
        supports_claim="",
    )
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    issues = " ".join(validated.publication_readiness.blocking_issues).lower()
    assert "title is empty" in issues
    assert "not associated with a specific claim" in issues


def test_unapproved_source_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.source_references = [
        SourceReference(
            title="Random blog",
            reference="https://some-random-blog.xyz/docker-tips",
            source_type="other",
            supports_claim="Containers are VMs",
        )
    ]
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "not from the approved" in issue.lower() or "not grounded" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_duplicate_title_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown = f"# {package.title}\n\n" + package.article_markdown
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "duplicate title" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_consecutive_repeated_headings_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown = package.article_markdown.replace(
        "## Prerequisites\n",
        "## Prerequisites\n\n## Prerequisites\n",
        1,
    )
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "consecutive repeated heading" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_unfenced_code_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += "\n\ndocker build -t bad:dev .\n"
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "outside fenced" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_empty_and_invalid_fences_rejected(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += "\n\n```python\n\n```\n\n```notalang\nprint(1)\n```\n"
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    issues = " ".join(validated.publication_readiness.blocking_issues).lower()
    assert "empty code fence" in issues
    assert "invalid code fence language" in issues


def test_code_fences_render_correctly_in_quality_article(
    fake_content_package: ContentPackage,
):
    validated = validate_content_package(fake_content_package, topic="Docker")
    assert validated.publication_readiness.status == "needs_review"
    assert "```dockerfile" in validated.article_markdown
    assert "```python" in validated.article_markdown
    assert "```bash" in validated.article_markdown


def test_overclaim_identical_everywhere_blocked(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += (
        "\n\nDocker behaves the same everywhere and guarantees reproducibility.\n"
    )
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "unsupported claim" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_qualified_non_guarantee_allowed(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += (
        "\n\nDocker does not guarantee identical behavior on every GPU host.\n"
    )
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "needs_review"


def test_missing_limitations_and_exercise_blocked(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown = "## Problem statement: why Docker matters\n\nText.\n\n"
    package.article_markdown += "## Prerequisites\n\nDocker installed.\n\n"
    package.article_markdown += "## Concept sequence\n\nImage then container.\n\n"
    package.article_markdown += "## Common confusions\n\nEXPOSE vs -p.\n\n"
    package.article_markdown += "## What to learn next\n\nKubernetes.\n"
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    issues = " ".join(validated.publication_readiness.blocking_issues).lower()
    assert "limitations" in issues
    assert "practical exercise" in issues


def test_teaching_example_must_not_repeat_article(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    snippet = re.sub(r"\s+", " ", package.article_markdown).strip()[80:380]
    package.teaching_example.scenario = snippet
    package.teaching_example.explanation = "Suppose we only restate the article body."
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    assert any(
        "repeat" in issue.lower() or "similar" in issue.lower()
        for issue in validated.publication_readiness.blocking_issues
    )


def test_untested_command_warning_is_deterministic(
    fake_content_package: ContentPackage,
):
    package = fake_content_package.model_copy(deep=True)
    package.claim_warnings = [
        ClaimWarning(
            claim="commands",
            reason="Commands were verified in production successfully.",
            severity="info",
        ),
        ClaimWarning(
            claim="commands",
            reason="Commands have not been tested yet.",
            severity="warning",
        ),
    ]
    validated = validate_content_package(package, topic="Docker")
    reasons = [w.reason for w in validated.claim_warnings]
    assert UNTESTED_COMMAND_WARNING in reasons
    assert "verified in production successfully" not in reasons
    assert reasons.count(UNTESTED_COMMAND_WARNING) == 1


def test_publication_blocked_until_failures_fixed(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown = (
        f"# {package.title}\n\n"
        + package.article_markdown
        + "\n\ndocker run --rm bad\n"
        + "\nDocker is production-ready and behaves the same everywhere.\n"
    )
    package.source_references = [
        SourceReference(
            title="Bad",
            reference="https://example.com/docker",
            source_type="other",
            supports_claim="everything",
        )
    ]
    validated = validate_content_package(package, topic="Docker")
    assert validated.publication_readiness.status == "blocked"
    issues = validated.publication_readiness.blocking_issues
    assert len(issues) >= 3

    fixed = validate_content_package(fake_content_package, topic="Docker")
    assert fixed.publication_readiness.status == "needs_review"
    assert fixed.publication_readiness.blocking_issues == []
