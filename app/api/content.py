"""JSON API routes for content generation and retrieval."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.requests import ContentApproveRequest, ContentGenerateRequest
from app.services import content_service
from app.services.auth import require_admin

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_content(
    request: ContentGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    settings = get_settings()
    try:
        settings.require_llm_credentials()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        item = content_service.generate_and_persist(db, request, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Content generation failed: {exc}",
        ) from exc
    return content_service.content_to_dict(item, settings)


@router.get("/{content_id}")
def get_content(
    content_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    item = content_service.get_content(db, content_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content_service.content_to_dict(item)


@router.post("/{content_id}/approve")
def approve_content(
    content_id: int,
    body: ContentApproveRequest | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    item = content_service.get_content(db, content_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    try:
        item = content_service.approve_content(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return content_service.content_to_dict(item)
