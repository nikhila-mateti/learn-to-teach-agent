"""Public blog and landing routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import content_service

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    published = content_service.list_published(db)[:5]
    return templates.TemplateResponse(
        request,
        "public_home.html",
        {"articles": published},
    )


@router.get("/blog", response_class=HTMLResponse)
def blog_list(request: Request, db: Session = Depends(get_db)):
    articles = content_service.list_published(db)
    return templates.TemplateResponse(
        request,
        "blog_list.html",
        {"articles": articles},
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
def blog_article(request: Request, slug: str, db: Session = Depends(get_db)):
    item = content_service.get_published_by_slug(db, slug)
    if not item:
        return HTMLResponse("Article not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "article.html",
        {"item": item},
    )


@router.get("/blog/{slug}/quiz", response_class=HTMLResponse)
def blog_quiz(request: Request, slug: str, db: Session = Depends(get_db)):
    item = content_service.get_published_by_slug(db, slug)
    if not item:
        return HTMLResponse("Quiz not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "quiz.html",
        {"item": item, "quiz": item.quiz_json},
    )


@router.get("/content/{content_id}", response_class=HTMLResponse)
def legacy_content_view(request: Request, content_id: int, db: Session = Depends(get_db)):
    """Author preview alias used by older links; requires published or redirects."""
    item = content_service.get_content(db, content_id)
    if not item or item.status != "published":
        return HTMLResponse("Content not found", status_code=404)
    return templates.TemplateResponse(request, "article.html", {"item": item})


@router.get("/content/{content_id}/quiz", response_class=HTMLResponse)
def legacy_quiz_view(request: Request, content_id: int, db: Session = Depends(get_db)):
    item = content_service.get_content(db, content_id)
    if not item or item.status != "published":
        return HTMLResponse("Quiz not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "quiz.html",
        {"item": item, "quiz": item.quiz_json},
    )
