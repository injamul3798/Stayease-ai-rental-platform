from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis import Redis, RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Conversation


class ConversationNotFoundError(Exception):
    """Raised when a conversation history cannot be found."""


class HistoryStoreError(Exception):
    """Raised when Redis history operations fail."""


class HistoryService:
    """Persist and cache conversation history across Postgres and Redis."""

    def __init__(self, session: Session, redis_client: Redis, cache_ttl_seconds: int = 3600) -> None:
        self.session = session
        self.redis_client = redis_client
        self.cache_ttl_seconds = cache_ttl_seconds

    def load_history(self, conversation_id: str) -> list[dict[str, str]]:
        cached_history = self._get_cached_history(conversation_id)
        if cached_history is not None:
            return cached_history

        records = self._fetch_history_from_db(conversation_id)
        if records:
            self._set_cached_history(conversation_id, records)
        return records

    def get_history_or_raise(self, conversation_id: str) -> list[Conversation]:
        records = self._fetch_conversation_rows(conversation_id)
        if not records:
            raise ConversationNotFoundError("conversation not found")
        return records

    def append_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        for item in messages:
            record = Conversation(
                conversation_id=conversation_id,
                role=item["role"],
                message_text=item["content"],
                intent=item.get("intent"),
                tool_name=item.get("tool_name"),
            )
            self.session.add(record)
        self.session.commit()
        self.refresh_cache(conversation_id)

    def refresh_cache(self, conversation_id: str) -> None:
        records = self._fetch_history_from_db(conversation_id)
        self._set_cached_history(conversation_id, records)

    def _fetch_history_from_db(self, conversation_id: str) -> list[dict[str, str]]:
        return [
            {"role": record.role, "content": record.message_text}
            for record in self._fetch_conversation_rows(conversation_id)
        ]

    def _fetch_conversation_rows(self, conversation_id: str) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.conversation_id == conversation_id)
            .order_by(Conversation.created_at.asc(), Conversation.id.asc())
        )
        return list(self.session.scalars(statement))

    def _get_cached_history(self, conversation_id: str) -> list[dict[str, str]] | None:
        key = self._cache_key(conversation_id)
        try:
            payload = self.redis_client.get(key)
        except RedisError as error:
            raise HistoryStoreError("redis operation failed") from error

        if not payload:
            return None

        items = json.loads(payload)
        return [{"role": item["role"], "content": item["content"]} for item in items]

    def _set_cached_history(self, conversation_id: str, messages: list[dict[str, str]]) -> None:
        key = self._cache_key(conversation_id)
        cache_payload = [
            {
                "role": item["role"],
                "content": item["content"],
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in messages
        ]
        try:
            self.redis_client.setex(key, self.cache_ttl_seconds, json.dumps(cache_payload))
        except RedisError as error:
            raise HistoryStoreError("redis operation failed") from error

    @staticmethod
    def _cache_key(conversation_id: str) -> str:
        return f"conversation:{conversation_id}"
