from __future__ import annotations

from datetime import datetime

from redis import Redis
from sqlalchemy.orm import Session

from agent.state import AgentState
from api.schema import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryItem,
    ConversationHistoryResponse,
)
from services.agent_runtime import get_graph
from services.history_service import HistoryService


_INTENT_TO_TOOL_NAME: dict[str, str] = {
    "search": "search_available_properties",
    "details": "get_listing_details",
    "book": "create_booking",
    "escalate": "escalate_to_human",
}


class ChatService:
    """Coordinate Redis-backed history, LangGraph agent orchestration, and persistence."""

    def __init__(self, session: Session, redis_client: Redis) -> None:
        self.history_service = HistoryService(session=session, redis_client=redis_client)
        self.graph = get_graph()

    def handle_message(self, conversation_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
        """Run the guest message through the LangGraph agent and persist both turns."""
        message = payload.message.strip()
        if not message:
            raise ValueError("message must not be empty")

        history = self.history_service.load_history(conversation_id)

        initial_state: AgentState = {
            "conversation_id": conversation_id,
            "messages": history,
            "latest_user_message": message,
            "intent": None,
            "search_params": {},
            "selected_listing_id": None,
            "booking_request": {},
            "tool_result": None,
            "response_text": None,
            "escalation_reason": None,
        }

        result_state = self.graph.invoke(initial_state)

        intent = result_state.get("intent") or "general"
        reply = result_state.get("response_text") or ""
        tool_result = result_state.get("tool_result")
        tool_name = _INTENT_TO_TOOL_NAME.get(intent)

        self.history_service.append_messages(
            conversation_id=conversation_id,
            messages=[
                {"role": "user", "content": message, "intent": intent},
                {
                    "role": "assistant",
                    "content": reply,
                    "intent": intent,
                    "tool_name": tool_name,
                },
            ],
        )

        return ChatMessageResponse(
            conversation_id=conversation_id,
            intent=intent,
            reply=reply,
            tool_result=tool_result,
            escalated=intent == "escalate",
        )

    def get_history(self, conversation_id: str) -> ConversationHistoryResponse:
        """Return the ordered conversation history for one thread."""
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
