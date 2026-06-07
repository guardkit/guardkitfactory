"""Result extraction helpers for LangGraph/DeepAgents agent invocations.

Lifted from ``specialist-agent/src/specialist_agent/orchestrator/generation_loop.py``
lines 364-390 (TASK-HMIG-001B AC-004). Kept as a thin standalone module so
the harness skeleton, the future Player/Coach wiring (TASK-HMIG-007), and the
event-mapping adapter (TASK-HMIG-006) can all share one canonical extractor
without re-importing from the orchestrator package.

TASK-FIX-COACHBUDG01-LG (2026-06-07): :func:`extract_last_ai_reasoning` now
recovers reasoning from the **OpenAI Responses API** (``POST /v1/responses``)
AIMessage shape in addition to the chat-completions shape. deepagents' default
model resolution constructs a ``ChatOpenAI`` that routes through the Responses
API, which structures reasoning differently from chat-completions, so the
original ``additional_kwargs["reasoning_content"]``-only extractor returned
``""`` on that path and the orchestrator parser had nothing to fall through
to. See the task file for the run-9 evidence.
"""

from __future__ import annotations

from typing import Any

__all__ = ["extract_last_ai_message", "extract_last_ai_reasoning"]


# Content-block ``type`` values that carry the assistant's canonical *visible*
# text on the OpenAI Responses API. ``output_text`` is the raw Responses-API
# name; ``text`` is the langchain-core-normalised name. ``reasoning`` blocks
# are deliberately excluded here — the canonical-text path must never surface
# reasoning-as-text (TASK-FIX-COACHBUDG01-LG AC-004).
_CANONICAL_TEXT_BLOCK_TYPES = frozenset({"text", "output_text"})


def _text_from_content_blocks(blocks: Any) -> str:
    """Join the canonical assistant text from a list of content blocks.

    Used by :func:`extract_last_ai_message` for the OpenAI Responses API
    shape, where ``AIMessage.content`` is a *list* of typed blocks rather
    than a plain string. Returns the joined ``text`` of the visible
    output/text blocks, skipping ``reasoning`` blocks entirely (AC-004:
    the canonical-text path must never surface reasoning-as-text). Tolerates
    bare-string items (some providers interleave plain strings). Returns
    ``""`` when no canonical text block is present.
    """
    if not isinstance(blocks, (list, tuple)):
        return ""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            if block.strip():
                parts.append(block)
            continue
        if isinstance(block, dict) and block.get("type") in _CANONICAL_TEXT_BLOCK_TYPES:
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    return "\n".join(parts)


def extract_last_ai_message(result: Any) -> str | None:
    """Extract the content of the last AI/assistant message from a LangGraph result.

    LangGraph / DeepAgents agents return ``{"messages": [HumanMessage, ..., AIMessage]}``
    where the final ``AIMessage`` carries the agent's textual output. This
    helper walks the message list in reverse and returns the first
    non-empty assistant/AI content it finds, ignoring tool-call-only
    messages whose ``content`` is empty or whitespace.

    On the OpenAI Responses API path ``content`` may be a *list* of typed
    blocks rather than a plain string; in that case the canonical text is
    pulled from the visible ``text`` / ``output_text`` blocks via
    :func:`_text_from_content_blocks`, with ``reasoning`` blocks excluded
    (TASK-FIX-COACHBUDG01-LG AC-004 — reasoning is surfaced separately by
    :func:`extract_last_ai_reasoning`).

    Args:
        result: Raw dict (or dict-like) returned from ``agent.ainvoke()``.

    Returns:
        Content string of the last AI/assistant message, or ``None`` if no
        suitable message is present.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for msg in reversed(messages):
        # LangChain message objects expose a .content attribute (str or, on
        # the Responses API, a list of typed blocks).
        content = getattr(msg, "content", None)
        if content:
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text = _text_from_content_blocks(content)
                if text.strip():
                    return text
        # Plain dict messages (rare but possible).
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role in ("assistant", "ai"):
                dcontent = msg.get("content", "")
                if isinstance(dcontent, str) and dcontent.strip():
                    return dcontent
                if isinstance(dcontent, list):
                    text = _text_from_content_blocks(dcontent)
                    if text.strip():
                        return text
    return None


def _text_from_summary(summary: Any) -> str:
    """Join plaintext from an OpenAI Responses-API reasoning ``summary`` list.

    The summary is a list of ``{"type": "summary_text", "text": ...}`` blocks
    (the visible chain-of-thought OpenAI returns alongside the opaque
    ``encrypted_content``). Returns the joined non-empty ``text`` fields, or
    ``""``. Tolerates bare-string items defensively.
    """
    if not isinstance(summary, (list, tuple)):
        return ""
    parts: list[str] = []
    for item in summary:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
        elif isinstance(item, str) and item.strip():
            parts.append(item)
    return "\n".join(parts)


def _text_from_reasoning_content_list(content: Any) -> str:
    """Join plaintext from a Responses-API reasoning ``content`` list.

    TASK-FIX-AC006SMOKE-LG (2026-06-07): live probe against gemma4-coach on
    llama-swap's ``/v1/responses`` substrate via ``langchain-openai 1.2.2``
    showed the actual reasoning plaintext lives on
    ``reasoning_block["content"] = [{"type": "reasoning_text", "text": ...}]``
    (probe C captured 3288 chars there while every other key the extractor
    used to consult — ``reasoning``, ``text``, ``summary``,
    ``encrypted_content`` — was empty). The same list shows up under
    ``reasoning_block["extras"]["content"]`` on the langchain-core
    normalised ``content_blocks`` view; ``_plaintext_from_reasoning_block``
    consults both call-sites.

    Joins the non-empty ``.text`` fields of items whose ``type`` is
    ``"reasoning_text"``. Tolerates bare-string items defensively. Returns
    ``""`` when the list is missing, empty, or carries no plaintext.
    """
    if not isinstance(content, (list, tuple)):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "reasoning_text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
        elif isinstance(item, str) and item.strip():
            parts.append(item)
    return "\n".join(parts)


def _plaintext_from_reasoning_block(block: Any) -> str:
    """Extract plaintext reasoning from a single ``type == "reasoning"`` block.

    Precedence (first non-empty plaintext wins):

      1. langchain-core canonical ``reasoning`` (str)
      2. Responses-API ``text`` (str)
      3. Responses-API raw ``content`` list of
         ``{"type": "reasoning_text", "text": ...}`` items
         (TASK-FIX-AC006SMOKE-LG — the live gemma4-coach shape)
      4. langchain-core normalised wrapper ``extras["content"]``
         (same list as above, but moved under ``extras`` by the v1
         normaliser — see ``langchain_core.messages.content``
         ``ReasoningContentBlock``'s ``extras: NotRequired[dict]``)
      5. Responses-API ``summary`` list of
         ``{"type": "summary_text", "text": ...}`` items (often empty for
         hybrid-reasoning models; present as a final-fallback summary).

    NEVER returns ``encrypted_content`` — it is opaque ciphertext, useless
    to the downstream ``coach_output_parser``
    (TASK-FIX-COACHBUDG01-LG AC-002).
    """
    if not isinstance(block, dict):
        return ""
    for key in ("reasoning", "text"):
        val = block.get(key)
        if isinstance(val, str) and val.strip():
            return val
    text = _text_from_reasoning_content_list(block.get("content"))
    if text.strip():
        return text
    extras = block.get("extras")
    if isinstance(extras, dict):
        text = _text_from_reasoning_content_list(extras.get("content"))
        if text.strip():
            return text
    return _text_from_summary(block.get("summary"))


def _reasoning_from_content_blocks(blocks: Any) -> str:
    """Join plaintext reasoning across a list of typed content blocks.

    Walks every ``type == "reasoning"`` block and joins the recovered
    plaintext (AC-003: multiple fragments on one message are joined with a
    newline). Non-reasoning blocks are ignored.
    """
    if not isinstance(blocks, (list, tuple)):
        return ""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "reasoning":
            text = _plaintext_from_reasoning_block(block)
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _reasoning_from_additional_kwargs_reasoning(reasoning: Any) -> str:
    """Extract plaintext from the ``additional_kwargs["reasoning"]`` dict form.

    Some langchain-openai versions surface Responses-API reasoning as a dict
    on ``additional_kwargs`` rather than as a content block:
    ``{"summary": [...], "encrypted_content": "...", ...}``. Only the
    plaintext ``text`` / ``summary`` is useful; ``encrypted_content`` is
    never surfaced (AC-002). A bare-string value is returned verbatim.
    """
    if isinstance(reasoning, str):
        return reasoning if reasoning.strip() else ""
    if not isinstance(reasoning, dict):
        return ""
    text = reasoning.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return _text_from_summary(reasoning.get("summary"))


def _reasoning_for_message(msg: Any) -> str:
    """Recover plaintext reasoning from a single message across all known shapes.

    Precedence (first non-empty plaintext wins):

      1. chat-completions ``additional_kwargs["reasoning_content"]`` (str)
      2. Responses-API ``reasoning`` blocks inside list ``content``
      3. Responses-API ``additional_kwargs["reasoning"]`` dict
      4. typed ``content_blocks`` property (defensive — newer langchain-core
         can expose reasoning here even when raw ``content`` is a string)
      5. dict top-level ``reasoning_content`` (str)

    Returns ``""`` when the message carries no recoverable plaintext reasoning.
    """
    # Plain dict messages must be assistant/ai to carry reasoning — mirror the
    # original helper's role gate. LangChain message *objects* are not gated
    # (reasoning fields only appear on AIMessages anyway, and the original
    # object branch did not gate on role either).
    if isinstance(msg, dict) and msg.get("role", "") not in ("assistant", "ai"):
        return ""

    additional = (
        msg.get("additional_kwargs")
        if isinstance(msg, dict)
        else getattr(msg, "additional_kwargs", None)
    )

    # 1. chat-completions reasoning_content (existing behaviour, highest precedence)
    if isinstance(additional, dict):
        rc = additional.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc

    # 2. Responses API: reasoning blocks inside list content
    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    if isinstance(content, list):
        text = _reasoning_from_content_blocks(content)
        if text.strip():
            return text

    # 3. Responses API: additional_kwargs["reasoning"] dict
    if isinstance(additional, dict):
        text = _reasoning_from_additional_kwargs_reasoning(additional.get("reasoning"))
        if text.strip():
            return text

    # 4. Typed content_blocks property (defensive). Guarded — never raise on an
    #    unexpected message shape.
    try:
        blocks = getattr(msg, "content_blocks", None)
    except Exception:  # noqa: BLE001 — duck-typed: tolerate any message shape
        blocks = None
    if isinstance(blocks, list):
        text = _reasoning_from_content_blocks(blocks)
        if text.strip():
            return text

    # 5. dict top-level reasoning_content (existing behaviour — some servers
    #    return it at the top level of the message dict).
    if isinstance(msg, dict):
        rc = msg.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc

    return ""


def extract_last_ai_reasoning(result: Any) -> str:
    """Extract the reasoning of the last AI message from a LangGraph result.

    TASK-FIX-COACHBUDG01 (2026-06-06): hybrid-reasoning models (Gemma 4 IT,
    DeepSeek V4 with reasoning, Nemotron-3 with thinking, etc.) emit their
    chain-of-thought into a reasoning channel rather than ``message.content``.
    The orchestrator's ``coach_output_parser`` falls through to this channel
    when no fenced ``json`` block is found in the canonical ``content`` — so
    the substrate-parity invariant from ADR FB-004 requires the LangGraph
    harness to surface reasoning whenever the model emitted any, matching the
    SDK harness's ``ThinkingBlock.thinking`` extraction at
    ``guardkit/orchestrator/harness/sdk_harness.py``.

    TASK-FIX-COACHBUDG01-LG (2026-06-07): two transports carry reasoning
    differently, and both are supported here:

    - **chat-completions** (llama.cpp ``--reasoning auto``): reasoning rides
      on ``additional_kwargs["reasoning_content"]`` (or the top level of a
      plain dict message).
    - **OpenAI Responses API** (``POST /v1/responses`` — deepagents' default):
      reasoning rides on a ``type == "reasoning"`` content block (carrying
      ``text`` and/or a ``summary`` list of ``summary_text`` blocks) or on an
      ``additional_kwargs["reasoning"]`` dict. Only the plaintext is recovered;
      ``encrypted_content`` is opaque and never surfaced (AC-002).

    Walks the message list in reverse and returns the first non-empty
    plaintext reasoning found (AC-003). Returns the empty string when no
    reasoning is present — matching the default value of
    ``AssistantMessageEvent.reasoning_text``, so downstream consumers see no
    observable difference for models that don't emit reasoning. Never returns
    ``None`` — the field on ``AssistantMessageEvent`` is non-optional.

    Args:
        result: Raw dict (or dict-like) returned from ``agent.ainvoke()``.

    Returns:
        Recovered plaintext reasoning string of the last AI/assistant message
        carrying it, or ``""`` if no such content is present.
    """
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for msg in reversed(messages):
        reasoning = _reasoning_for_message(msg)
        if reasoning.strip():
            return reasoning
    return ""
