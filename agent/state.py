from __future__ import annotations

from typing import Any, Literal, TypedDict


Intent = Literal["search", "details", "book", "escalate"]


class AgentState(TypedDict):
    conversation_id: str
    messages: list[dict[str, str]]
    latest_user_message: str
    intent: Intent | None
    search_params: dict[str, Any]
    selected_listing_id: str | None
    booking_request: dict[str, Any]
    tool_result: dict[str, Any] | None
    response_text: str | None
    escalation_reason: str | None
