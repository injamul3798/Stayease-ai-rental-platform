from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.nodes import finalize_response, route_request, run_booking_tool, run_details_tool, run_search_tool
from agent.state import AgentState


def _next_after_route(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "search":
        return "run_search_tool"
    if intent == "details":
        return "run_details_tool"
    if intent == "book":
        return "run_booking_tool"
    return "finalize_response"


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("route_request", route_request)
    workflow.add_node("run_search_tool", run_search_tool)
    workflow.add_node("run_details_tool", run_details_tool)
    workflow.add_node("run_booking_tool", run_booking_tool)
    workflow.add_node("finalize_response", finalize_response)

    workflow.set_entry_point("route_request")
    workflow.add_conditional_edges(
        "route_request",
        _next_after_route,
        {
            "run_search_tool": "run_search_tool",
            "run_details_tool": "run_details_tool",
            "run_booking_tool": "run_booking_tool",
            "finalize_response": "finalize_response",
        },
    )
    workflow.add_edge("run_search_tool", "finalize_response")
    workflow.add_edge("run_details_tool", "finalize_response")
    workflow.add_edge("run_booking_tool", "finalize_response")
    workflow.add_edge("finalize_response", END)

    return workflow.compile()
