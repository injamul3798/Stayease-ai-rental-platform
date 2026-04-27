from __future__ import annotations

from typing import Any

from agent.state import AgentState
from agent.tools import create_booking, get_listing_details, search_available_properties
from services.message_parser import extract_booking_fields, extract_listing_id, extract_search_params


def route_request(state: AgentState) -> AgentState:
    """Classify the guest request into search, details, book, or escalate."""
    raw_message = state["latest_user_message"]
    message = raw_message.lower()

    if "book" in message or "confirm" in message:
        state["intent"] = "book"
        state["booking_request"] = extract_booking_fields(raw_message)
        if state["selected_listing_id"] and "listing_id" not in state["booking_request"]:
            state["booking_request"]["listing_id"] = state["selected_listing_id"]
        return state

    if "details" in message or "tell me about" in message or "listing" in message:
        state["intent"] = "details"
        state["selected_listing_id"] = extract_listing_id(raw_message)
        return state

    if any(keyword in message for keyword in ["room", "stay", "apartment", "guest", "guests", "cxb", "cox's bazar"]):
        state["intent"] = "search"
        state["search_params"] = extract_search_params(raw_message)
        return state

    state["intent"] = "escalate"
    state["escalation_reason"] = "Request is outside search, details, and booking scope."
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
    """Build the final assistant message from tool output or escalation state."""
    intent = state["intent"]
    tool_result = state.get("tool_result") or {}

    if intent == "search":
        if tool_result.get("status") == "clarification_needed":
            state["response_text"] = (
                "Please share the location, check-in date, check-out date, and guest count so I can search available stays."
            )
        else:
            properties = tool_result.get("properties", [])
            if not properties:
                state["response_text"] = "I could not find any available properties for those dates."
            else:
                lines = [
                    f'{item["listing_id"]} - {item["title"]} - BDT {item["price_bdt"]}/night'
                    for item in properties
                ]
                state["response_text"] = "Available properties:\n" + "\n".join(lines)
    elif intent == "details":
        if tool_result.get("status") == "clarification_needed":
            state["response_text"] = "Please share the listing ID, for example SEA-201, and I will show the property details."
        elif tool_result.get("status") == "error":
            state["response_text"] = "I could not find that listing. Please check the listing ID and try again."
        else:
            state["response_text"] = (
                f'{tool_result.get("title", "Listing")} in {tool_result.get("location", "Bangladesh")} '
                f'costs BDT {tool_result.get("nightly_price_bdt", 0)} per night.'
            )
    elif intent == "book":
        if tool_result.get("status") == "clarification_needed":
            state["response_text"] = (
                "To confirm the booking, please share the listing ID, check-in date, check-out date, guest count, your full name, and your email."
            )
        elif tool_result.get("status") == "error":
            state["response_text"] = str(tool_result.get("error", "I could not complete the booking."))
        else:
            state["response_text"] = (
                f'Your booking is {tool_result.get("status", "pending")} with booking ID '
                f'{tool_result.get("booking_id", "N/A")}.'
            )
    else:
        state["response_text"] = (
            "I can only help with property search, listing details, and bookings. "
            "I am escalating this chat to a human teammate."
        )

    state["messages"].append({"role": "assistant", "content": state["response_text"] or ""})
    return state
