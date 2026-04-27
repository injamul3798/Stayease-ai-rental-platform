from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from openai import OpenAI

from agent.prompts import CLASSIFICATION_PROMPT, REPLY_PROMPT
from config import get_settings


class OpenAIChatService:
    """Provide intent classification and reply composition via OpenAI Responses API."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def classify_intent(
        self,
        latest_message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Call OpenAI Responses API to classify intent and extract structured parameters."""
        input_items = self._to_input(history)
        input_items.append({"role": "user", "content": latest_message})
        response = self.client.responses.create(
            model=self.model,
            input=input_items,
            instructions=CLASSIFICATION_PROMPT,
            store=False,
        )
        return self._parse_json(response.output_text.strip())

    def compose_reply(
        self,
        intent: str,
        tool_result: dict[str, Any] | None,
        context: list[dict[str, str]],
        escalation_reason: str | None = None,
    ) -> str:
        """Call OpenAI Responses API to compose a guest-facing reply from tool output."""
        payload: dict[str, Any] = {"intent": intent, "tool_result": tool_result}
        if escalation_reason:
            payload["escalation_reason"] = escalation_reason

        input_items = self._to_input(context)
        input_items.append(
            {"role": "user", "content": f"Compose a guest-facing reply for this result:\n{json.dumps(payload)}"}
        )
        response = self.client.responses.create(
            model=self.model,
            input=input_items,
            instructions=REPLY_PROMPT,
            store=False,
        )
        return response.output_text.strip()

    @staticmethod
    def _to_input(history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Convert conversation history into the Responses API input format."""
        return [{"role": item["role"], "content": item["content"]} for item in history]

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """Parse a JSON string, stripping markdown code fences if present."""
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)


@lru_cache(maxsize=1)
def get_openai_service() -> OpenAIChatService:
    """Return a singleton OpenAIChatService instance for use by LangGraph nodes."""
    return OpenAIChatService()
