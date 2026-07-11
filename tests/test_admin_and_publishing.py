"""Admin auth, notes, publishing lifecycle, and theme tests."""

import io

from app.config import get_settings
from app.schemas.requests import ContentGenerateRequest
from app.services import content_service


def test_admin_requires_authentication(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code in (303, 302)
    assert "/admin/login" in response.headers["location"]


def test_public_routes_do_not_require_auth(client):
    assert client.get("/").status_code == 200
    assert client.get("/blog").status_code == 200


def test_txt_note_upload(auth_client):
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Docker TXT", "topic": "Docker", "content": ""},
        files={"upload": ("notes.txt", io.BytesIO(b"Layer caching notes for Docker."), "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_markdown_note_upload(auth_client):
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Docker MD", "topic": "Docker", "content": ""},
        files={"upload": ("notes.md", io.BytesIO(b"# Notes\n\nUseful Docker observations."), "text/markdown")},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_unsupported_file_upload_fails(auth_client):
    response = auth_client.post(
        "/admin/notes",
        data={"title": "Bad", "topic": "Docker", "content": ""},
        files={"upload": ("notes.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert response.status_code == 400
    assert b"Unsupported file type" in response.content


def test_notes_persist(db_session):
    note = content_service.create_note(
        db_session,
        title="Persisted",
        topic="Docker",
        content="Persistent note body with enough text.",
        original_filename="n.md",
        file_type="md",
    )
    notes = content_service.list_notes(db_session)
    assert any(n.id == note.id for n in notes)


def _seed_item(db_session, fake_content_package, slug="docker-for-inference"):
    package = fake_content_package.model_copy(deep=True)
    request = ContentGenerateRequest(topic="Docker")
    item = content_service.persist_package(db_session, package, request, get_settings())
    item.slug = slug
    db_session.commit()
    db_session.refresh(item)
    return item


def test_generated_content_starts_needs_review(db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package)
    assert item.status == "needs_review"


def test_unapproved_cannot_publish(db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package, slug="cannot-publish")
    try:
        content_service.publish_content(db_session, item)
        raise AssertionError("Expected publish to fail")
    except ValueError as exc:
        assert "approved" in str(exc).lower()


def test_approved_can_publish_and_appear_publicly(auth_client, db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package, slug="published-docker")
    content_service.approve_content(db_session, item)
    content_service.publish_content(db_session, item)
    response = auth_client.get("/blog/published-docker")
    assert response.status_code == 200
    assert b"Docker for Inference Engineers" in response.content


def test_draft_returns_404_publicly(client, db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package, slug="secret-draft")
    assert item.status == "needs_review"
    response = client.get("/blog/secret-draft")
    assert response.status_code == 404


def test_duplicate_slugs_rejected(db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package, slug="unique-slug")
    try:
        content_service.update_content(
            db_session,
            item,
            title=item.title,
            slug="unique-slug",
            summary=item.summary,
            article_markdown=item.article_markdown,
            teaching_example_json=item.teaching_example_json,
            quiz_json=item.quiz_json,
            sources_json=item.sources_json,
        )
        # same slug on same item is fine
    except ValueError:
        raise AssertionError("Updating same slug on same item should succeed")

    other = _seed_item(db_session, fake_content_package, slug="other-slug")
    try:
        content_service.update_content(
            db_session,
            other,
            title=other.title,
            slug="unique-slug",
            summary=other.summary,
            article_markdown=other.article_markdown,
            teaching_example_json=other.teaching_example_json,
            quiz_json=other.quiz_json,
            sources_json=other.sources_json,
        )
        raise AssertionError("Expected duplicate slug rejection")
    except ValueError as exc:
        assert "duplicate" in str(exc).lower()


def test_unpublish_removes_public_access(client, db_session, fake_content_package):
    item = _seed_item(db_session, fake_content_package, slug="temp-public")
    content_service.approve_content(db_session, item)
    content_service.publish_content(db_session, item)
    assert client.get("/blog/temp-public").status_code == 200
    content_service.unpublish_content(db_session, item)
    assert client.get("/blog/temp-public").status_code == 404


def test_theme_stylesheet_loaded(client):
    for path in ["/", "/blog", "/admin/login"]:
        response = client.get(path)
        assert response.status_code == 200
        assert b"/static/theme.css" in response.content


def test_templates_inherit_base(client):
    html = client.get("/").text
    assert "Learn to Teach" in html
    assert "site-header" in html


def test_no_hardcoded_theme_colors_outside_theme_css():
    from pathlib import Path

    static = Path("app/static")
    for path in static.glob("*.css"):
        if path.name == "theme.css":
            continue
        text = path.read_text(encoding="utf-8")
        assert "font-family:" not in text or "var(--font" in text
        # Disallow raw hex colors outside theme.css
        import re

        hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", text)
        assert hexes == [], f"{path} contains hardcoded colors: {hexes}"
