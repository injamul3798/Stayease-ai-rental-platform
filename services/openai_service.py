from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from config import get_settings
from services.booking_service import BookingConflictError, BookingService, BookingValidationError
from services.listing_service import ListingService


SYSTEM_PROMPT = """
You are StayEase's guest messaging assistant for a Bangladesh short-term rental platform.

You may do only four things:
1. Reply naturally to greetings or simple conversational messages.
2. Search for available properties.
3. Return details about a specific property.
4. Create a booking when the guest clearly wants to book.

If the user asks for anything outside those areas, do not invent support. Explain briefly and use the escalate_to_human tool.

Rules:
- Use search_available_properties only when you have location, check_in, check_out, and guest_count.
- Use get_listing_details only when you know the listing_id.
- Use create_booking only when you have listing_id, check_in, check_out, guest_count, guest_name, and guest_email.
- If information is missing, ask a short follow-up question instead of calling a tool.
- When a tool returns data, use it to write a warm, concise, human-friendly answer in plain language with BDT pricing.
- Respect previous conversation context from earlier turns.
""".strip()


@dataclass
class AIChatResult:
    intent: str
    reply: str
    tool_result: dict[str, Any] | None
    tool_name: str | None
    escalated: bool


class OpenAIChatService:
    """Run the StayEase conversation through OpenAI Responses API with tool calling."""

    def __init__(self, session: Session) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.listing_service = ListingService(session=session)
        self.booking_service = BookingService(session=session)

    def respond(self, history: list[dict[str, str]]) -> AIChatResult:
        input_items: list[dict[str, Any]] = self._to_response_input(history)
        response = self.client.responses.create(
            model=self.model,
            input=input_items,
            tools=self._tools(),
            instructions=SYSTEM_PROMPT,
            store=False,
        )

        last_tool_name: str | None = None
        last_tool_result: dict[str, Any] | None = None

        while True:
            tool_calls = [item for item in response.output if self._item_type(item) == "function_call"]
            if not tool_calls:
                reply = response.output_text.strip()
                intent = self._intent_from_tool_name(last_tool_name)
                if intent == "general" and not reply:
                    reply = "Hello! I can help you search stays, view listing details, or make a booking."
                return AIChatResult(
                    intent=intent,
                    reply=reply,
                    tool_result=last_tool_result,
                    tool_name=last_tool_name,
                    escalated=intent == "escalate",
                )

            tool_outputs: list[dict[str, Any]] = []
            for call in tool_calls:
                tool_name = self._item_value(call, "name")
                call_id = self._item_value(call, "call_id")
                raw_arguments = self._item_value(call, "arguments") or "{}"
                arguments = json.loads(raw_arguments)

                last_tool_name = tool_name
                last_tool_result = self._execute_tool(tool_name, arguments)
                tool_output = {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(last_tool_result),
                }
                tool_outputs.append(tool_output)

            input_items.extend(self._response_output_as_input_items(response.output))
            input_items.extend(tool_outputs)

            response = self.client.responses.create(
                model=self.model,
                input=input_items,
                tools=self._tools(),
                instructions=SYSTEM_PROMPT,
                store=False,
            )

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_available_properties":
            return self.listing_service.search_available_properties(
                location=arguments["location"],
                check_in=date.fromisoformat(arguments["check_in"]),
                check_out=date.fromisoformat(arguments["check_out"]),
                guest_count=arguments["guest_count"],
            )

        if name == "get_listing_details":
            result = self.listing_service.get_listing_details(arguments["listing_id"])
            if result is None:
                return {"status": "error", "error": "listing not found"}
            return result

        if name == "create_booking":
            try:
                return self.booking_service.create_booking(
                    listing_code=arguments["listing_id"],
                    check_in=date.fromisoformat(arguments["check_in"]),
                    check_out=date.fromisoformat(arguments["check_out"]),
                    guest_count=arguments["guest_count"],
                    guest_name=arguments["guest_name"],
                    guest_email=arguments["guest_email"],
                )
            except (BookingConflictError, BookingValidationError) as error:
                return {"status": "error", "error": str(error)}

        if name == "escalate_to_human":
            return {"status": "escalated", "reason": arguments["reason"]}

        return {"status": "error", "error": f"unknown tool: {name}"}

    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "search_available_properties",
                "description": "Search available StayEase listings for Bangladesh locations.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "check_in": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "check_out": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "guest_count": {"type": "integer", "minimum": 1},
                    },
                    "required": ["location", "check_in", "check_out", "guest_count"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_listing_details",
                "description": "Get details for a specific StayEase listing.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"listing_id": {"type": "string"}},
                    "required": ["listing_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "create_booking",
                "description": "Create a StayEase booking after the guest confirms the stay.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "listing_id": {"type": "string"},
                        "check_in": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "check_out": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "guest_count": {"type": "integer", "minimum": 1},
                        "guest_name": {"type": "string"},
                        "guest_email": {"type": "string"},
                    },
                    "required": ["listing_id", "check_in", "check_out", "guest_count", "guest_name", "guest_email"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "escalate_to_human",
                "description": "Escalate unsupported requests to a human support agent.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
            },
        ]

    @staticmethod
    def _to_response_input(history: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{"role": item["role"], "content": item["content"]} for item in history]

    def _response_output_as_input_items(self, output_items: list[Any]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for item in output_items:
            item_type = self._item_type(item)
            if item_type == "message":
                role = self._item_value(item, "role") or "assistant"
                content = self._extract_message_text(item)
                if content:
                    converted.append({"role": role, "content": content})
            elif item_type == "function_call":
                converted.append(
                    {
                        "type": "function_call",
                        "call_id": self._item_value(item, "call_id"),
                        "name": self._item_value(item, "name"),
                        "arguments": self._item_value(item, "arguments"),
                    }
                )
        return converted

    def _extract_message_text(self, item: Any) -> str:
        content = self._item_value(item, "content") or []
        if isinstance(content, str):
            return content

        chunks: list[str] = []
        for part in content:
            part_type = self._item_value(part, "type")
            if part_type in {"output_text", "input_text", "text"}:
                text_value = self._item_value(part, "text")
                if text_value:
                    chunks.append(str(text_value))
        return "".join(chunks).strip()

    @staticmethod
    def _item_type(item: Any) -> str | None:
        if isinstance(item, dict):
            return item.get("type")
        return getattr(item, "type", None)

    @staticmethod
    def _item_value(item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    @staticmethod
    def _intent_from_tool_name(tool_name: str | None) -> str:
        if tool_name == "search_available_properties":
            return "search"
        if tool_name == "get_listing_details":
            return "details"
        if tool_name == "create_booking":
            return "book"
        if tool_name == "escalate_to_human":
            return "escalate"
        return "general"
