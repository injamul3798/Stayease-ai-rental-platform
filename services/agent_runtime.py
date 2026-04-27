from __future__ import annotations

from functools import lru_cache

from agent.graph import build_graph


@lru_cache(maxsize=1)
def get_graph():
    """Return a compiled LangGraph instance for chat orchestration."""
    return build_graph()
