from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from config import get_settings
from db.session import init_db


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

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
