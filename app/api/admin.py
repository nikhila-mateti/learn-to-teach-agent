"""Admin HTML routes for notes, drafts, review, and publishing."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.requests import ContentGenerateRequest
from app.services import content_service
from app.services.auth import attempt_login, is_authenticated, logout
from app.services.note_image_service import (
    IMAGE_SUFFIX_TO_MIME,
    extract_text_from_note_image,
)

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

ALLOWED_TEXT_NOTE_TYPES = {".txt": "txt", ".md": "md"}
ALLOWED_IMAGE_NOTE_TYPES = {
    suffix: suffix.lstrip(".") for suffix in IMAGE_SUFFIX_TO_MIME
}
ALLOWED_NOTE_TYPES = {**ALLOWED_TEXT_NOTE_TYPES, **ALLOWED_IMAGE_NOTE_TYPES}


def _redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("/admin/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"error": None},
    )


@router.post("/admin/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if attempt_login(request, username, password):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"error": "Invalid username or password"},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@router.post("/admin/logout")
def admin_logout(request: Request):
    logout(request)
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("/admin", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    stats = content_service.dashboard_stats(db)
    recent = content_service.list_content_by_status(db)[:10]
    warnings = []
    for item in recent:
        for warning in item.warnings_json or []:
            warnings.append({"content_id": item.id, "title": item.title, **warning})
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"stats": stats, "recent": recent, "warnings": warnings[:20]},
    )


@router.get("/admin/notes", response_class=HTMLResponse)
def notes_list(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    notes = content_service.list_notes(db)
    return templates.TemplateResponse(
        request,
        "admin/notes_list.html",
        {"notes": notes},
    )


@router.get("/admin/notes/new", response_class=HTMLResponse)
def notes_new(request: Request):
    if not is_authenticated(request):
        return _redirect_login()
    return templates.TemplateResponse(
        request,
        "admin/note_form.html",
        {"error": None},
    )


@router.post("/admin/notes")
async def notes_create(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    topic: str = Form(...),
    content: str = Form(""),
    uploads: list[UploadFile] = File(default=[]),
):
    if not is_authenticated(request):
        return _redirect_login()
    settings = get_settings()
    pasted = content.strip()
    parts: list[str] = []
    if pasted:
        parts.append(pasted)

    files = [f for f in uploads if f is not None and getattr(f, "filename", None)]
    original_names: list[str] = []
    file_types: list[str] = []

    for upload in files:
        name = upload.filename or "upload"
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if suffix not in ALLOWED_NOTE_TYPES:
            return templates.TemplateResponse(
                request,
                "admin/note_form.html",
                {
                    "error": (
                        f"Unsupported file type for {name}. Upload .txt, .md, or images "
                        "(.png, .jpg, .jpeg, .webp, .gif)."
                    )
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raw = await upload.read()
        is_image = suffix in ALLOWED_IMAGE_NOTE_TYPES
        max_bytes = (
            settings.max_image_upload_bytes if is_image else settings.max_upload_bytes
        )
        if len(raw) > max_bytes:
            return templates.TemplateResponse(
                request,
                "admin/note_form.html",
                {"error": f"{name} exceeds max upload size of {max_bytes} bytes."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        original_names.append(name)
        file_types.append(ALLOWED_NOTE_TYPES[suffix])
        if is_image:
            try:
                extracted = extract_text_from_note_image(
                    raw,
                    filename=name,
                    suffix=suffix,
                    settings=settings,
                )
            except ValueError as exc:
                return templates.TemplateResponse(
                    request,
                    "admin/note_form.html",
                    {"error": f"{name}: {exc}"},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            parts.append(extracted)
        else:
            decoded = raw.decode("utf-8", errors="replace").strip()
            if decoded:
                parts.append(f"[Uploaded file: {name}]\n\n{decoded}")

    body = "\n\n---\n\n".join(parts).strip()
    if not body:
        return templates.TemplateResponse(
            request,
            "admin/note_form.html",
            {"error": "Provide note text or upload one or more files/images."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(file_types) == 1:
        file_type = file_types[0]
    elif file_types and all(t in ALLOWED_IMAGE_NOTE_TYPES.values() for t in file_types):
        file_type = "images"
    elif file_types:
        file_type = "mixed"
    else:
        file_type = "text"

    content_service.create_note(
        db,
        title=title,
        topic=topic,
        content=body,
        original_filename=", ".join(original_names) if original_names else None,
        file_type=file_type,
    )
    return RedirectResponse(url="/admin/notes", status_code=303)


@router.get("/admin/content", response_class=HTMLResponse)
def content_list(
    request: Request, db: Session = Depends(get_db), status_filter: str | None = None
):
    if not is_authenticated(request):
        return _redirect_login()
    items = content_service.list_content_by_status(db, status_filter)
    return templates.TemplateResponse(
        request,
        "admin/content_list.html",
        {"items": items, "status_filter": status_filter},
    )


@router.get("/admin/generate", response_class=HTMLResponse)
def generate_form(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    notes = content_service.list_notes(db)
    return templates.TemplateResponse(
        request,
        "admin/generate.html",
        {"notes": notes, "error": None},
    )


@router.post("/admin/generate")
async def generate_submit(
    request: Request,
    db: Session = Depends(get_db),
):
    if not is_authenticated(request):
        return _redirect_login()
    settings = get_settings()
    form = await request.form()
    selected_ids = [int(v) for v in form.getlist("note_ids") if str(v).isdigit()]
    include_quiz = "include_quiz" in form
    gen_request = ContentGenerateRequest(
        topic=str(form.get("topic") or ""),
        notes=str(form.get("notes") or "") or None,
        note_ids=selected_ids,
        audience=str(
            form.get("audience") or "engineers preparing for production LLM inference"
        ),
        content_type=str(form.get("content_type") or "tutorial"),  # type: ignore[arg-type]
        tone=str(form.get("tone") or "clear, practical, beginner-friendly"),
        desired_length=str(form.get("desired_length") or "medium"),  # type: ignore[arg-type]
        include_quiz=include_quiz,
    )
    try:
        settings.require_llm_credentials()
        item = content_service.generate_and_persist(db, gen_request, settings=settings)
    except Exception as exc:  # noqa: BLE001
        notes_list = content_service.list_notes(db)
        return templates.TemplateResponse(
            request,
            "admin/generate.html",
            {"notes": notes_list, "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url=f"/admin/content/{item.id}/preview", status_code=303)


@router.get("/admin/content/{content_id}/edit", response_class=HTMLResponse)
def content_edit(request: Request, content_id: int, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "admin/content_form.html",
        {
            "item": item,
            "quiz_json": json.dumps(item.quiz_json, indent=2),
            "teaching_example_json": json.dumps(item.teaching_example_json, indent=2),
            "sources_json": json.dumps(item.sources_json, indent=2),
            "error": None,
        },
    )


@router.post("/admin/content/{content_id}/edit")
async def content_edit_submit(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    title: str = Form(...),
    slug: str = Form(...),
    summary: str = Form(...),
    article_markdown: str = Form(...),
    teaching_example_json: str = Form(...),
    quiz_json: str = Form(...),
    sources_json: str = Form(...),
):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    try:
        te = json.loads(teaching_example_json)
        quiz = json.loads(quiz_json)
        sources = json.loads(sources_json)
        content_service.update_content(
            db,
            item,
            title=title,
            slug=slug,
            summary=summary,
            article_markdown=article_markdown,
            teaching_example_json=te,
            quiz_json=quiz,
            sources_json=sources,
        )
    except Exception as exc:  # noqa: BLE001
        return templates.TemplateResponse(
            request,
            "admin/content_form.html",
            {
                "item": item,
                "quiz_json": quiz_json,
                "teaching_example_json": teaching_example_json,
                "sources_json": sources_json,
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url=f"/admin/content/{content_id}/preview", status_code=303)


@router.get("/admin/content/{content_id}/preview", response_class=HTMLResponse)
def content_preview(request: Request, content_id: int, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "admin/content_preview.html",
        {
            "item": item,
            "public_url": content_service.public_url(item, settings),
        },
    )


@router.post("/admin/content/{content_id}/approve")
def content_approve(request: Request, content_id: int, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    try:
        content_service.approve_content(db, item)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return RedirectResponse(url=f"/admin/content/{content_id}/preview", status_code=303)


@router.post("/admin/content/{content_id}/publish")
def content_publish(request: Request, content_id: int, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    try:
        content_service.publish_content(db, item)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return RedirectResponse(url=f"/admin/content/{content_id}/preview", status_code=303)


@router.post("/admin/content/{content_id}/unpublish")
def content_unpublish(request: Request, content_id: int, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return _redirect_login()
    item = content_service.get_content(db, content_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    try:
        content_service.unpublish_content(db, item)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return RedirectResponse(url=f"/admin/content/{content_id}/preview", status_code=303)
