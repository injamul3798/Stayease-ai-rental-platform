from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session

from db.redis_client import get_redis_client
from db.session import get_db_session


def db_session_dependency() -> Generator[Session, None, None]:
    yield from get_db_session()


def redis_dependency() -> Redis:
    return get_redis_client()


DbSession = Depends(db_session_dependency)
RedisClient = Depends(redis_dependency)
