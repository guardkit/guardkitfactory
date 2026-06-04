"""LangGraph/DeepAgents-backed :class:`HarnessAdapter` implementation.

Cross-repo dependency
=====================

This module imports the abstract :class:`HarnessAdapter` from
``guardkit.orchestrator.harness`` (defined in
``guardkit/guardkit/orchestrator/harness/adapter.py``, TASK-HMIG-001A) and
provides the LangGraph-side concrete subclass that AutoBuild dispatches to
when the ``GUARDKIT_HARNESS`` cutover flag is set to ``"langgraph"``.

The pairing is intentional: the ABC lives in ``guardkit`` so the
orchestrator can import it without pulling in LangGraph; the concrete
implementation lives here so ``guardkit`` doesn't gain a hard dependency on
``deepagents`` / ``langchain`` / ``langgraph``.

What this skeleton ships (TASK-HMIG-001B)
=========================================

* The :class:`LangGraphHarness` class plus the :meth:`invoke` async-
  generator stub wired to :func:`deepagents.create_deep_agent` (NOT to a
  bare ``ChatOpenAI`` / hand-rolled ``StateGraph`` — see the AC-003 note
  in the parent task on why that path was rejected).
* The :func:`assert_no_system_messages` safety guard from
  ``lib/factory_guards.py`` (TASK-REV-R2A1 mitigation against dual
  system messages → vLLM HTTP 400).
* Result extraction via :func:`extract_last_ai_message` lifted from
  specialist-agent ``generation_loop.py:364-390``.
* A minimal :class:`HarnessEvent` stream emitting one
  :class:`AssistantMessageEvent` plus one terminal
  :class:`ResultMessageEvent`. Bytewise-faithful event mapping with the
  SDK stream taxonomy is TASK-HMIG-006's responsibility.

What this skeleton does **not** ship
====================================

* The pluggable backend configuration (``LocalShellBackend`` /
  permissions / cwd plumbing) — that's TASK-HMIG-002R.
* The Player/Coach role-prompt registry — that's TASK-HMIG-007.
* Session resumption via LangGraph checkpointer — out of scope per
  decision D-07 in the parent review (JSON-on-disk checkpointing stays).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    HarnessAdapter,
    HarnessEvent,
    ResultMessageEvent,
    ToolUseEvent,
)

from guardkitfactory.harness.extractors import extract_last_ai_message
from lib.factory_guards import assert_no_system_messages

logger = logging.getLogger(__name__)

__all__ = ["LangGraphHarness", "LangGraphHarnessError"]


def _iter_tool_use_events(result: Any) -> list[ToolUseEvent]:
    """Extract ``ToolUseEvent`` values from a DeepAgents ``ainvoke`` result.

    TASK-HMIG-006.2: every ``AIMessage`` in ``result["messages"]`` can
    carry a ``.tool_calls`` list (LangChain v0.3 shape:
    ``[{"name": str, "args": dict, "id": str}, ...]``). Iterating the
    full messages list (not just the last) captures multi-step agent
    runs where intermediate AIMessages drive tool calls and a later
    AIMessage carries the final text. Duck-typed so non-AIMessage
    elements (HumanMessage, ToolMessage, dict-form messages) are
    silently skipped.

    Returns
    -------
    list[ToolUseEvent]
        Ordered by appearance in ``result["messages"]``. Empty when the
        result has no tool-call activity.
    """
    if not isinstance(result, dict):
        return []
    messages = result.get("messages", []) or []
    events: list[ToolUseEvent] = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            args = call.get("args", {}) or {}
            if not isinstance(args, dict):
                args = {}
            events.append(
                ToolUseEvent(
                    tool_use_id=str(call.get("id", "") or ""),
                    name=str(call.get("name", "") or ""),
                    input=args,
                )
            )
    return events


class LangGraphHarnessError(RuntimeError):
    """Raised when ``LangGraphHarness.invoke`` cannot construct or run the agent.

    Wraps the underlying ``langchain`` / ``deepagents`` exception with the
    role and (truncated) model identifier so failures stay attributable
    rather than surfacing as generic ``ValueError`` / ``RuntimeError`` from
    deep inside the LangChain stack.
    """


class LangGraphHarness(HarnessAdapter):
    """Concrete :class:`HarnessAdapter` backed by LangGraph + DeepAgents.

    The harness builds a fresh DeepAgent on every :meth:`invoke` call. The
    agent picks up the standard DeepAgents tool surface
    (``ls``/``read_file``/``write_file``/``edit_file``/``glob``/``grep``,
    plus ``execute`` from a sandbox backend, ``write_todos`` planning, and
    sub-agent delegation) **for free** through the ``backend`` parameter
    — wiring that backend is TASK-HMIG-002R's job, so the default
    ``backend=None`` here just falls through to DeepAgents' built-in
    ``StateBackend`` (in-memory, ephemeral).

    Args:
        model: The LLM the agent should use. Accepts the same shapes as
            :func:`deepagents.create_deep_agent`'s ``model`` parameter —
            either a ``BaseChatModel`` instance (e.g. ``ChatOpenAI(...)``,
            ``init_chat_model(...)``) or a provider-prefixed string
            (e.g. ``"openai:gpt-4o-mini"``).
        backend: Optional DeepAgents backend instance / factory. ``None``
            (the default) lets DeepAgents pick its built-in
            ``StateBackend``. Real backend wiring lands in TASK-HMIG-002R.
        permissions: Optional list of :class:`FilesystemPermission`
            rules to constrain the filesystem tool surface. ``None`` is
            an unrestricted run, which is acceptable for the skeleton —
            TASK-HMIG-002R will wire the real allowlist.
    """

    def __init__(
        self,
        model: Any,
        *,
        backend: Any = None,
        permissions: list[Any] | None = None,
    ) -> None:
        self.model = model
        self.backend = backend
        self.permissions = permissions

    def _build_input(self, prompt: str) -> dict[str, Any]:
        """Construct the ``ainvoke()`` input payload.

        Factored out so the AC-008 dual-system-message test can monkeypatch
        a system-message-bearing payload and prove the
        :func:`assert_no_system_messages` guard fires. Production calls
        never inject ``system`` messages here — the role-prompt becomes
        the agent's ``system_prompt`` via ``create_deep_agent``, which
        prepends it automatically (the dual-system-message hazard
        TASK-REV-R2A1 documents).
        """
        return {"messages": [{"role": "user", "content": prompt}]}

    async def invoke(
        self,
        prompt: str,
        role: str,
        tools: list,
        cwd: Path,
        *,
        timeout_seconds: int,
    ) -> AsyncIterator[HarnessEvent]:
        """Run one agent turn and stream the resulting :class:`HarnessEvent` values.

        Skeleton behaviour: yields exactly one :class:`AssistantMessageEvent`
        carrying the final AI text, followed by one terminal
        :class:`ResultMessageEvent` with ``session_id=None`` (resume is
        out of scope per AC-006). TASK-HMIG-006 will refine the event
        stream to mirror the SDK taxonomy more faithfully — until then,
        downstream consumers only need to dispatch on the terminal event.
        """
        input_data = self._build_input(prompt)
        assert_no_system_messages(input_data)

        # TASK-FIX-LGTOOLS (2026-06-03): drop the caller's ``tools`` list on
        # the Wave-2 path. The orchestrator passes SDK tool-name strings
        # (``["Read", "Write", "Bash", ...]``) which downstream — through
        # ``deepagents.create_deep_agent`` → ``SubAgentMiddleware`` →
        # ``langchain.agents.create_agent`` → ``langgraph.prebuilt.ToolNode``
        # — get iterated as if they were ``BaseTool`` instances. ToolNode
        # does ``tool_.name`` on each element and crashes with
        # ``'function' object has no attribute 'name'`` (the strings get
        # processed into raw functions somewhere in DeepAgents' built-in
        # tool merge). Surfaced by GuardKit TASK-HMIG-009A AC-001D
        # (langraph-run-2, 2026-06-03).
        #
        # Wave-2 contract per this module's docstring + the selector at
        # guardkit.orchestrator.harness.selector._translate_kwargs_for_langgraph
        # (docstring lines 56-58): "the LangGraph path receives its tool
        # surface through ... DeepAgents' built-in tool set (filesystem +
        # execute + planning + sub-agents)". The SDK tool-name strings are
        # meaningless to DeepAgents anyway — its built-ins cover the same
        # ground under different names. Passing ``tools=[]`` lets DeepAgents
        # use only its built-ins, which is the documented Wave-2 intent.
        #
        # Faithful tool translation (SDK names → BaseTool wrappers around
        # the operator's preferred implementations) is TASK-HMIG-002R's
        # scope, not the Wave-2 skeleton's.
        if tools:
            logger.debug(
                "LangGraphHarness Wave-2: dropping %d caller-supplied tool(s) "
                "(%s) — DeepAgents' built-in tool set is used instead. See "
                "TASK-HMIG-002R for faithful SDK→LangGraph tool translation.",
                len(tools),
                [t if isinstance(t, str) else type(t).__name__ for t in tools[:5]],
            )

        try:
            agent = create_deep_agent(
                model=self.model,
                tools=[],  # TASK-FIX-LGTOOLS — see note above
                backend=self.backend,
                permissions=self.permissions,
                system_prompt=role,
            )
        except Exception as exc:  # noqa: BLE001 — wrap-and-reraise on purpose
            raise LangGraphHarnessError(
                f"LangGraphHarness: failed to construct DeepAgent for "
                f"role={role!r} model={self.model!r}: {exc}"
            ) from exc

        try:
            result = await agent.ainvoke(input_data)
        except Exception as exc:  # noqa: BLE001 — wrap-and-reraise on purpose
            raise LangGraphHarnessError(
                f"LangGraphHarness: agent.ainvoke failed for "
                f"role={role!r} model={self.model!r}: {exc}"
            ) from exc

        text = extract_last_ai_message(result) or ""

        # TASK-HMIG-006.2: emit one ToolUseEvent per AIMessage.tool_calls
        # entry encountered in the result stream BEFORE the
        # AssistantMessageEvent. Mirrors the SDK harness's
        # ToolUseBlock-per-content-block extraction so the migrated
        # _track_tool_use / _extract_partial_from_messages consumers see
        # the same typed events on both substrates. LangChain AIMessage
        # exposes `.tool_calls` as a list of dicts (LangChain v0.3+):
        # ``{"name": str, "args": dict, "id": str}``.
        for tool_event in _iter_tool_use_events(result):
            yield tool_event

        yield AssistantMessageEvent(text=text, raw=result)
        yield ResultMessageEvent(
            session_id=None,
            stop_reason="end_turn",
            usage=None,
        )

    @property
    def session_id(self) -> str | None:
        """Always ``None`` for the skeleton — LangGraph checkpoint resume is out of scope.

        See AC-006 and parent review decision D-07: JSON-on-disk
        checkpointing remains AutoBuild's resume mechanism for this
        migration; the LangGraph checkpointer integration is deferred.
        """
        return None

    @property
    def supports_resume(self) -> bool:
        """Always ``False`` for the skeleton (AC-007)."""
        return False
