from __future__ import annotations

from datetime import datetime

from redis import Redis
from sqlalchemy.orm import Session

from agent.state import AgentState, Intent
from api.schema import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryItem,
    ConversationHistoryResponse,
)
from services.agent_runtime import get_graph
from services.booking_service import BookingConflictError, BookingService, BookingValidationError
from services.history_service import HistoryService
from services.listing_service import ListingService
from services.message_parser import extract_booking_fields, extract_listing_id, extract_search_params


class ChatService:
    """Coordinate history, graph invocation, and response assembly."""

    def __init__(self, session: Session, redis_client: Redis) -> None:
        self.session = session
        self.redis_client = redis_client
        self.history_service = HistoryService(session=session, redis_client=redis_client)
        self.listing_service = ListingService(session=session)
        self.booking_service = BookingService(session=session)
        self.graph = get_graph()

    def handle_message(self, conversation_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
        message = payload.message.strip()
        if not message:
            raise ValueError("message must not be empty")

        history = self.history_service.load_history(conversation_id)
        history.append({"role": "user", "content": message})
        result = self.graph.invoke(self._build_initial_state(conversation_id=conversation_id, history=history, message=message))

        intent = result["intent"] or "escalate"
        tool_result, reply = self._resolve_business_response(intent=intent, message=message, fallback_reply=result.get("response_text") or "")

        self.history_service.append_messages(
            conversation_id=conversation_id,
            messages=[
                {"role": "user", "content": message, "intent": intent},
                {"role": "assistant", "content": reply, "intent": intent, "tool_name": self._tool_name_for_intent(intent)},
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

    def _build_initial_state(self, *, conversation_id: str, history: list[dict[str, str]], message: str) -> AgentState:
        return {
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

    def _resolve_business_response(
        self,
        *,
        intent: Intent,
        message: str,
        fallback_reply: str,
    ) -> tuple[dict[str, object] | None, str]:
        if intent == "search":
            return self._handle_search(message=message, fallback_reply=fallback_reply)
        if intent == "details":
            return self._handle_details(message=message, fallback_reply=fallback_reply)
        if intent == "book":
            return self._handle_booking(message=message, fallback_reply=fallback_reply)
        return None, fallback_reply

    def _handle_search(self, *, message: str, fallback_reply: str) -> tuple[dict[str, object] | None, str]:
        params = extract_search_params(message)
        required = {"location", "check_in", "check_out", "guest_count"}
        if not required.issubset(params):
            return None, (
                "Please share location, check-in date, check-out date, and guest count so I can search available stays."
            )

        result = self.listing_service.search_available_properties(
            location=params["location"],
            check_in=params["check_in"],
            check_out=params["check_out"],
            guest_count=params["guest_count"],
        )
        properties = result["properties"]
        if not properties:
            return result, "I could not find any available properties for those dates."

        lines = [
            f'{item["listing_id"]} - {item["title"]} in {item["area"]}, {item["location"]} - BDT {item["price_bdt"]}/night'
            for item in properties
        ]
        reply = "Available properties:\n" + "\n".join(lines)
        return result, reply

    def _handle_details(self, *, message: str, fallback_reply: str) -> tuple[dict[str, object] | None, str]:
        listing_id = extract_listing_id(message)
        if not listing_id:
            return None, "Please share the listing ID, for example SEA-201, and I’ll show the property details."

        result = self.listing_service.get_listing_details(listing_id)
        if result is None:
            return None, "I could not find that listing. Please check the listing ID and try again."

        reply = (
            f'{result["title"]} in {result["area"]}, {result["location"]} costs '
            f'BDT {result["nightly_price_bdt"]} per night and fits up to {result["max_guests"]} guests.'
        )
        return result, reply

    def _handle_booking(self, *, message: str, fallback_reply: str) -> tuple[dict[str, object] | None, str]:
        fields = extract_booking_fields(message)
        required = {"listing_id", "check_in", "check_out", "guest_count", "guest_name", "guest_email"}
        if not required.issubset(fields):
            return None, (
                "To confirm the booking, please send listing ID, check-in date, check-out date, guest count, your name, and email."
            )

        try:
            result = self.booking_service.create_booking(
                listing_code=fields["listing_id"],
                check_in=fields["check_in"],
                check_out=fields["check_out"],
                guest_count=fields["guest_count"],
                guest_name=fields["guest_name"],
                guest_email=fields["guest_email"],
            )
        except (BookingConflictError, BookingValidationError) as error:
            return None, str(error)

        reply = (
            f'Your booking is confirmed. Booking ID: {result["booking_id"]}. '
            f'Total price: BDT {result["total_price_bdt"]}.'
        )
        return result, reply

    @staticmethod
    def _tool_name_for_intent(intent: Intent) -> str | None:
        mapping = {
            "search": "search_available_properties",
            "details": "get_listing_details",
            "book": "create_booking",
            "escalate": None,
        }
        return mapping[intent]
