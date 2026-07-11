"""Deterministic validation tests."""

from app.schemas.content import ContentPackage
from app.services.validation_service import validate_content_package, validate_quiz


def test_unsupported_first_person_detection(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.generation_mode = "curriculum_aware"
    package.article_markdown += "\nI spent hours debugging this container networking issue.\n"
    validated = validate_content_package(package)
    assert any("first-person" in w.reason.lower() for w in validated.claim_warnings)


def test_fabricated_metric_detection(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.article_markdown += "\nThis approach achieved a 40% improvement in latency.\n"
    validated = validate_content_package(package)
    assert any("performance claim" in w.reason.lower() for w in validated.claim_warnings)


def test_quiz_schema_validation_ok(fake_content_package: ContentPackage):
    assert validate_quiz(fake_content_package.quiz) == []


def test_quiz_schema_validation_bad_count(fake_content_package: ContentPackage):
    issues = validate_quiz(fake_content_package.quiz[:3])
    assert issues
    assert "exactly 5" in issues[0]


def test_requires_source_references(fake_content_package: ContentPackage):
    package = fake_content_package.model_copy(deep=True)
    package.source_references = []
    validated = validate_content_package(package)
    assert validated.publication_readiness.status == "blocked"
    assert any("source reference" in issue.lower() for issue in validated.publication_readiness.blocking_issues)


def test_publication_status_needs_review(fake_content_package: ContentPackage):
    validated = validate_content_package(fake_content_package)
    assert validated.publication_readiness.status == "needs_review"
