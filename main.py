from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.chat import router as chat_router
from config import get_settings
from db.session import init_db

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app() -> FastAPI:
    """Create and configure the StayEase FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="StayEase Backend", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
