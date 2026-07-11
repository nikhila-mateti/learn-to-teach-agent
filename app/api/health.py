"""Health endpoints that do not call paid LLM APIs."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    settings = get_settings()
    db_ok = check_db_connection()
    config_ok = settings.has_required_config
    payload = {
        "status": "ok" if db_ok and config_ok else "not_ready",
        "database": db_ok,
        "config": config_ok,
    }
    code = status.HTTP_200_OK if db_ok and config_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=code)
