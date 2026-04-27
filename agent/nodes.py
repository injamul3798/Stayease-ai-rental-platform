from __future__ import annotations

from typing import Any

from agent.state import AgentState
from agent.tools import create_booking, get_listing_details, search_available_properties
from services.openai_service import get_openai_service


def route_request(state: AgentState) -> AgentState:
    """Classify the guest request into search, details, book, or escalate using OpenAI."""
    service = get_openai_service()
    classification = service.classify_intent(
        latest_message=state["latest_user_message"],
        history=state["messages"],
    )
    state["intent"] = classification.get("intent", "escalate")
    state["search_params"] = _drop_nulls(classification.get("search_params") or {})
    state["selected_listing_id"] = classification.get("selected_listing_id")
    state["booking_request"] = _drop_nulls(classification.get("booking_request") or {})
    state["escalation_reason"] = classification.get("escalation_reason")
    return state


def run_search_tool(state: AgentState) -> AgentState:
    """Execute the property search tool for a valid search request."""
    params = state["search_params"]
    required = {"location", "check_in", "check_out", "guest_count"}
    if not required.issubset(params):
        state["tool_result"] = {
            "status": "clarification_needed",
            "missing_fields": sorted(required.difference(params.keys())),
        }
        return state

    state["tool_result"] = search_available_properties.invoke(params)
    return state


def run_details_tool(state: AgentState) -> AgentState:
    """Execute the listing details tool for a selected property."""
    listing_id = state["selected_listing_id"] or ""
    if not listing_id:
        state["tool_result"] = {
            "status": "clarification_needed",
            "missing_fields": ["listing_id"],
        }
        return state

    state["tool_result"] = get_listing_details.invoke({"listing_id": listing_id})
    return state


def run_booking_tool(state: AgentState) -> AgentState:
    """Execute the booking tool after the guest confirms a reservation."""
    payload: dict[str, Any] = state["booking_request"]
    required = {"listing_id", "check_in", "check_out", "guest_count", "guest_name", "guest_email"}
    if not required.issubset(payload):
        state["tool_result"] = {
            "status": "clarification_needed",
            "missing_fields": sorted(required.difference(payload.keys())),
        }
        return state

    state["tool_result"] = create_booking.invoke(payload)
    return state


def finalize_response(state: AgentState) -> AgentState:
    """Compose the final assistant reply using OpenAI Responses API."""
    service = get_openai_service()
    reply = service.compose_reply(
        intent=state["intent"] or "escalate",
        tool_result=state.get("tool_result"),
        context=state["messages"],
        escalation_reason=state.get("escalation_reason"),
    )
    state["response_text"] = reply
    state["messages"].append({"role": "assistant", "content": reply})
    return state


def _drop_nulls(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the dict with all None-valued keys removed."""
    return {k: v for k, v in data.items() if v is not None}
