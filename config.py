from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class Settings(BaseModel):
    environment: str = "development"
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@127.0.0.1:5433/stayease")
    redis_url: str = Field(default="redis://localhost:6379/0")
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_file()
        raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        cors_origins = _parse_cors_origins(raw_cors)
        try:
            return cls(
                environment=os.getenv("ENVIRONMENT", "development"),
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                database_url=os.getenv(
                    "DATABASE_URL",
                    "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/stayease",
                ),
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                app_host=os.getenv("APP_HOST", "127.0.0.1"),
                app_port=int(os.getenv("APP_PORT", "8000")),
                cors_origins=cors_origins,
            )
        except ValidationError as error:
            raise RuntimeError(f"Invalid application configuration: {error}") from error


def _parse_cors_origins(raw_value: str) -> list[str]:
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
