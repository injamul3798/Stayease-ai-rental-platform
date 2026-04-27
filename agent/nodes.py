from __future__ import annotations

from typing import Any

from agent.state import AgentState
from agent.tools import create_booking, get_listing_details, search_available_properties


def route_request(state: AgentState) -> AgentState:
    """Classify the guest request into search, details, book, or escalate."""
    message = state["latest_user_message"].lower()

    if "book" in message or "confirm" in message:
        state["intent"] = "book"
        state["booking_request"] = {
            "listing_id": state.get("selected_listing_id") or "SEA-201",
            "check_in": "2026-05-14",
            "check_out": "2026-05-16",
            "guest_count": 2,
            "guest_name": "Guest Name",
            "guest_email": "guest@example.com",
        }
        return state

    if "details" in message or "tell me about" in message or "listing" in message:
        state["intent"] = "details"
        state["selected_listing_id"] = state.get("selected_listing_id") or "SEA-201"
        return state

    if any(keyword in message for keyword in ["room", "stay", "apartment", "guests", "cxb", "cox's bazar"]):
        state["intent"] = "search"
        state["search_params"] = {
            "location": "Cox's Bazar",
            "check_in": "2026-05-14",
            "check_out": "2026-05-16",
            "guest_count": 2,
        }
        return state

    state["intent"] = "escalate"
    state["escalation_reason"] = "Request is outside search, details, and booking scope."
    return state


def run_search_tool(state: AgentState) -> AgentState:
    """Execute the property search tool for a valid search request."""
    params = state["search_params"]
    state["tool_result"] = search_available_properties.invoke(params)
    return state


def run_details_tool(state: AgentState) -> AgentState:
    """Execute the listing details tool for a selected property."""
    listing_id = state["selected_listing_id"] or ""
    state["tool_result"] = get_listing_details.invoke({"listing_id": listing_id})
    return state


def run_booking_tool(state: AgentState) -> AgentState:
    """Execute the booking tool after the guest confirms a reservation."""
    payload: dict[str, Any] = state["booking_request"]
    state["tool_result"] = create_booking.invoke(payload)
    return state


def finalize_response(state: AgentState) -> AgentState:
    """Build the final assistant message from tool output or escalation state."""
    intent = state["intent"]
    tool_result = state.get("tool_result") or {}

    if intent == "search":
        properties = tool_result.get("properties", [])
        if not properties:
            state["response_text"] = "I could not find any available properties for those dates."
        else:
            lines = [
                f'{item["listing_id"]} — {item["title"]} — BDT {item["price_bdt"]}/night'
                for item in properties
            ]
            state["response_text"] = "Available properties:\n" + "\n".join(lines)
    elif intent == "details":
        state["response_text"] = (
            f'{tool_result.get("title", "Listing")} in {tool_result.get("location", "Bangladesh")} '
            f'costs BDT {tool_result.get("nightly_price_bdt", 0)} per night.'
        )
    elif intent == "book":
        state["response_text"] = (
            f'Your booking is {tool_result.get("status", "pending")} with booking ID '
            f'{tool_result.get("booking_id", "N/A")}.'
        )
    else:
        state["response_text"] = (
            "I can only help with property search, listing details, and bookings. "
            "I’m escalating this chat to a human teammate."
        )

    state["messages"].append({"role": "assistant", "content": state["response_text"] or ""})
    return state
