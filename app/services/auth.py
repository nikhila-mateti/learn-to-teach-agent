"""Simple single-admin session authentication for the portfolio MVP."""

from __future__ import annotations

from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def add_session_middleware(app, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="lta_session",
        https_only=False,
        same_site="lax",
        max_age=60 * 60 * 12,
    )


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin_authenticated"))


def require_admin(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


def require_admin_html(request: Request) -> RedirectResponse | None:
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return None


AdminDep = Annotated[None, Depends(require_admin)]


def attempt_login(
    request: Request,
    username: str,
    password: str,
    settings: Settings | None = None,
) -> bool:
    settings = settings or get_settings()
    if username != settings.admin_username:
        return False
    if not verify_password(password, settings.admin_password_hash):
        return False
    request.session["admin_authenticated"] = True
    request.session["admin_username"] = username
    return True


def logout(request: Request) -> None:
    request.session.clear()
