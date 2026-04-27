from __future__ import annotations

from datetime import datetime

from redis import Redis
from sqlalchemy.orm import Session

from api.schema import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryItem,
    ConversationHistoryResponse,
)
from services.history_service import HistoryService
from services.openai_service import OpenAIChatService


class ChatService:
    """Coordinate Redis-backed history, OpenAI tool orchestration, and persistence."""

    def __init__(self, session: Session, redis_client: Redis) -> None:
        self.history_service = HistoryService(session=session, redis_client=redis_client)
        self.openai_chat_service = OpenAIChatService(session=session)

    def handle_message(self, conversation_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
        message = payload.message.strip()
        if not message:
            raise ValueError("message must not be empty")

        history = self.history_service.load_history(conversation_id)
        history.append({"role": "user", "content": message})
        ai_result = self.openai_chat_service.respond(history)

        self.history_service.append_messages(
            conversation_id=conversation_id,
            messages=[
                {"role": "user", "content": message, "intent": ai_result.intent},
                {
                    "role": "assistant",
                    "content": ai_result.reply,
                    "intent": ai_result.intent,
                    "tool_name": ai_result.tool_name,
                },
            ],
        )

        return ChatMessageResponse(
            conversation_id=conversation_id,
            intent=ai_result.intent,
            reply=ai_result.reply,
            tool_result=ai_result.tool_result,
            escalated=ai_result.escalated,
        )

    def get_history(self, conversation_id: str) -> ConversationHistoryResponse:
        records = self.history_service.get_history_or_raise(conversation_id)
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[
                ConversationHistoryItem(
                    role=record.role,  # type: ignore[arg-type]
                    message_text=record.message_text,
                    created_at=record.created_at if isinstance(record.created_at, datetime) else datetime.utcnow(),
                )
                for record in records
            ],
        )
