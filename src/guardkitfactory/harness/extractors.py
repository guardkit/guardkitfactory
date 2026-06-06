"""Result extraction helpers for LangGraph/DeepAgents agent invocations.

Lifted from ``specialist-agent/src/specialist_agent/orchestrator/generation_loop.py``
lines 364-390 (TASK-HMIG-001B AC-004). Kept as a thin standalone module so
the harness skeleton, the future Player/Coach wiring (TASK-HMIG-007), and the
event-mapping adapter (TASK-HMIG-006) can all share one canonical extractor
without re-importing from the orchestrator package.
"""

from __future__ import annotations

from typing import Any

__all__ = ["extract_last_ai_message", "extract_last_ai_reasoning"]


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


def extract_last_ai_reasoning(result: Any) -> str:
    """Extract the reasoning_content of the last AI message from a LangGraph result.

    TASK-FIX-COACHBUDG01 (2026-06-06): hybrid-reasoning models (Gemma 4 IT,
    DeepSeek V4 with reasoning, Nemotron-3 with thinking, etc.) emit their
    chain-of-thought into ``message.reasoning_content`` (llama.cpp's
    ``--reasoning auto`` mode) rather than ``message.content``. LangChain
    surfaces this on the ``AIMessage`` as ``additional_kwargs["reasoning_content"]``.

    The orchestrator's ``coach_output_parser`` falls through to this channel
    when no fenced ``json`` block is found in the canonical ``content`` — so
    the substrate-parity invariant from ADR FB-004 requires the LangGraph
    harness to surface ``reasoning_content`` whenever the model emitted any,
    matching the SDK harness's ``ThinkingBlock.thinking`` extraction at
    ``guardkit/orchestrator/harness/sdk_harness.py``.

    Walks the message list in reverse and returns the joined
    ``reasoning_content`` of the first AI/assistant message that carries it.
    Returns the empty string when no reasoning content is present — matching
    the default value of ``AssistantMessageEvent.reasoning_text``, so
    downstream consumers see no observable difference for models that don't
    emit reasoning.

    Args:
        result: Raw dict (or dict-like) returned from ``agent.ainvoke()``.

    Returns:
        Joined ``reasoning_content`` string of the last AI/assistant message
        carrying it, or ``""`` if no such content is present. Never ``None``
        — the field on ``AssistantMessageEvent`` is non-optional.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for msg in reversed(messages):
        # LangChain AIMessage exposes additional_kwargs as a dict; the
        # reasoning_content key is populated by langchain-openai's adapter
        # when llama-cpp returns the field under --reasoning auto.
        additional = getattr(msg, "additional_kwargs", None)
        if isinstance(additional, dict):
            reasoning = additional.get("reasoning_content")
            if reasoning and isinstance(reasoning, str) and reasoning.strip():
                return reasoning
        # Plain dict messages mirror the same shape.
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role not in ("assistant", "ai"):
                continue
            extra = msg.get("additional_kwargs")
            if isinstance(extra, dict):
                reasoning = extra.get("reasoning_content")
                if reasoning and isinstance(reasoning, str) and reasoning.strip():
                    return reasoning
            # Some servers return reasoning_content at the top level of the
            # message dict rather than nested in additional_kwargs.
            reasoning = msg.get("reasoning_content")
            if reasoning and isinstance(reasoning, str) and reasoning.strip():
                return reasoning
    return ""
