from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.state import Intent


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    guest_id: str | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    intent: Intent
    reply: str
    tool_result: dict[str, Any] | None
    escalated: bool


class ConversationHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    message_text: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationHistoryItem]
