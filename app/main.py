"""FastAPI application entrypoint for the learn-to-teach-agent platform."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import admin, content, health, public
from app.database import init_db
from app.services.auth import add_session_middleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Learn to Teach Agent",
    description=(
        "AI-assisted technical teaching platform with notes, drafts, "
        "quizzes, and a self-hosted public blog."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

add_session_middleware(app)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(health.router)
app.include_router(content.router)
app.include_router(public.router)
app.include_router(admin.router)
