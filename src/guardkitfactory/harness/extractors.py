"""Result extraction helpers for LangGraph/DeepAgents agent invocations.

Lifted from ``specialist-agent/src/specialist_agent/orchestrator/generation_loop.py``
lines 364-390 (TASK-HMIG-001B AC-004). Kept as a thin standalone module so
the harness skeleton, the future Player/Coach wiring (TASK-HMIG-007), and the
event-mapping adapter (TASK-HMIG-006) can all share one canonical extractor
without re-importing from the orchestrator package.
"""

from __future__ import annotations

from typing import Any

__all__ = ["extract_last_ai_message"]


def extract_last_ai_message(result: Any) -> str | None:
    """Extract the content of the last AI/assistant message from a LangGraph result.

    LangGraph / DeepAgents agents return ``{"messages": [HumanMessage, ..., AIMessage]}``
    where the final ``AIMessage`` carries the agent's textual output. This
    helper walks the message list in reverse and returns the first
    non-empty assistant/AI content it finds, ignoring tool-call-only
    messages whose ``content`` is empty or whitespace.

    Args:
        result: Raw dict (or dict-like) returned from ``agent.ainvoke()``.

    Returns:
        Content string of the last AI/assistant message, or ``None`` if no
        suitable message is present.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for msg in reversed(messages):
        # LangChain message objects expose a .content attribute.
        content = getattr(msg, "content", None)
        if content and isinstance(content, str) and content.strip():
            return content
        # Plain dict messages (rare but possible).
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if (
                role in ("assistant", "ai")
                and isinstance(content, str)
                and content.strip()
            ):
                return content
    return None
