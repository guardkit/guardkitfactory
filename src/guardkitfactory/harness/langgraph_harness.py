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

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import suppress
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
from langchain_core.language_models import BaseChatModel

from guardkitfactory.harness.extractors import (
    extract_last_ai_message,
    extract_last_ai_reasoning,
)
from guardkitfactory.harness.model_config import resolve_autobuild_model
from lib.factory_guards import assert_no_system_messages

logger = logging.getLogger(__name__)


def _install_langsmith_executor_guard() -> None:
    """Make LangSmith tracing safe against asyncio executor teardown.

    TASK-FIX-LSTRACE01. ``langsmith.run_helpers.async_wrapper`` dispatches its
    run-tree setup/teardown (``_setup_run`` / ``_on_run_end``) via
    ``loop.run_in_executor(None, ...)`` on the asyncio loop's DEFAULT
    ``ThreadPoolExecutor`` — UNCONDITIONALLY, before any tracing-enabled check.
    When a ``task_timeout`` teardown shuts that executor down mid-invoke (the
    Layer-1 cancellation race in ``.claude/rules/harness-cancellation-contract.md``),
    the dispatch raises ``RuntimeError: cannot schedule new futures after
    shutdown`` and cascades through the deepagents summarization middleware to
    fail BOTH the player and coach ``agent.ainvoke`` (FEAT-E2CB run 1,
    2026-06-12). Idempotent; best-effort (never raises).

    Disabling tracing alone does NOT fix this — ``async_wrapper`` dispatches to
    the executor regardless of tracing state. The load-bearing fix is the
    LangSmith runtime override below, which runs the (cheap) run-tree
    setup/teardown INLINE so a torn-down executor can never crash the invoke.
    """
    # Hygiene: autobuild has no LangSmith project. Opt out unless explicitly kept.
    if os.environ.get("GUARDKIT_KEEP_LANGSMITH", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        for _var in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGCHAIN_TRACING"):
            os.environ[_var] = "false"

    # Load-bearing: run LangSmith's aio_to_thread work inline instead of on the
    # loop's default executor (the public override hook; cf. LangSmith's own
    # Temporal example, which has the same "no run_in_executor" constraint).
    try:
        import langsmith

        async def _inline_aio_to_thread(_default, ctx, func, /, *args, **kwargs):
            return ctx.run(func, *args, **kwargs)

        langsmith.set_runtime_overrides(aio_to_thread=_inline_aio_to_thread)
    except Exception:  # pragma: no cover - langsmith optional / API drift
        logger.debug(
            "TASK-FIX-LSTRACE01: LangSmith executor guard not installed",
            exc_info=True,
        )


_install_langsmith_executor_guard()

# TASK-FIX-CTOUT01: deadline applied by :meth:`LangGraphHarness.cancel` when
# waiting for the cancelled in-flight ``agent.ainvoke`` task to unwind. If
# LangChain's httpx client does not honour ``asyncio.CancelledError`` within
# this window we log and leak the task — the orchestrator's outer
# ``LATE_APPROVAL_GRACE_S`` (TASK-ATR-003) is the safety net of last resort.
_CANCEL_DEADLINE_ENV = "GUARDKIT_HARNESS_CANCEL_DEADLINE"
_CANCEL_DEADLINE_DEFAULT_S = 30

# TASK-ARCH-COACHSPLIT (D-3): generation budget for the toolless Coach
# verdict-synthesis call. Default 16384 leaves room for a reasoning prefix
# plus the grammar-constrained verdict fence on hybrid-reasoning Gemma models
# (matches the gemma4:26b max_tokens_coach registry budget). Override per-run
# with GUARDKIT_COACH_SYNTHESIS_MAX_TOKENS.
_SYNTHESIS_MAX_TOKENS_ENV = "GUARDKIT_COACH_SYNTHESIS_MAX_TOKENS"
_SYNTHESIS_MAX_TOKENS_DEFAULT = 16384

# TASK-PERF-COACHTURNBUDGET (Lever 2): default-off per-request reasoning-budget
# curtailment for the toolless synthesis. On a dense hybrid-reasoning model
# (gemma4:31b under ``--reasoning auto``) the synthesis latency is dominated by
# ``reasoning_content`` generation grinding toward the ``max_tokens`` ceiling
# (run-23 TP05: 41m43s / 16384-token grind → TIMEOUT_BUDGET_EXHAUSTED before the
# fix turn). A per-request reasoning budget caps the *thinking* phase so
# generation stops when the verdict is done — WITHOUT lowering ``max_tokens``,
# which would truncate the ``criteria_verification`` + ``issues`` that ARE the
# bug report (the AC-3 tension this task must respect).
#
# Default UNSET → the field is omitted entirely → behaviour is unchanged and the
# server's own ``--reasoning`` policy governs. Set to an int to inject
# ``reasoning_budget`` into the synthesis request body (llama.cpp semantics:
# ``0`` disables thinking, ``-1`` unlimited, ``N`` caps the reasoning tokens).
# Live verification that the GB10's llama.cpp build + gemma4:31b honour this
# wire-field is the AC-4 falsifier run (mirrors COACHSYNTH's deferred-live
# pattern); until then the default-off knob carries zero risk to current runs.
_SYNTHESIS_REASONING_BUDGET_ENV = "GUARDKIT_COACH_SYNTHESIS_REASONING_BUDGET"

# TASK-FIX-COACHREASON01 (FEAT-9DDE run-3 follow-up): default-off toggle that
# suppresses the toolless-synthesis reasoning_content phase via the
# chat-template kwarg ``enable_thinking=false`` rather than the llama.cpp
# ``reasoning_budget`` field above. This resolves the AC-4 falsifier deferred by
# COACHTURNBUDGET: on the GB10 llama-swap endpoint the ``reasoning_budget`` wire
# field is IGNORED for gemma4-31b (a reasoning_budget=0 probe still emitted 3041
# chars of reasoning_content / 776 tokens), but
# ``chat_template_kwargs={"enable_thinking": false}`` drops reasoning_content to
# 0 (47→2 completion tokens) while the grammar-constrained verdict still emits.
# That ~31-min Coach turn (FEAT-9DDE run 3 turn 1) is the latency this closes.
# Default UNSET/falsey → the field is omitted and behaviour is unchanged. Truthy
# ("1"/"true"/"yes"/"on") → ``chat_template_kwargs`` rides in ``extra_body`` as a
# top-level body field (servers that don't define the template var ignore it,
# exactly like ``grammar``). Orthogonal to ``reasoning_budget`` — set whichever
# the target server honours; both can be set together.
_SYNTHESIS_DISABLE_THINKING_ENV = "GUARDKIT_COACH_SYNTHESIS_DISABLE_THINKING"

# TASK-PERF-COACHSYNTH: hard ceiling on the DeepAgents/LangGraph super-step
# count for a single ``invoke``. ``None`` (the default) preserves LangGraph's
# own default (25) — unchanged behaviour for the Player and synthesis paths.
# The Coach B-full Phase-A *gather* sets a SMALL value (see
# ``AgentInvoker._invoke_coach_gather``): the gather is the load-bearing F20
# surface — its tool-using agentic loop appends tool-result tokens every
# round-trip, and ``max_turns`` is DROPPED on this substrate
# (``selector._translate_kwargs_for_langgraph`` docstring), so this
# ``recursion_limit`` is the ONLY hard bound on how many tool cycles the
# gather can run. When the limit is reached LangGraph raises
# ``GraphRecursionError``, which :meth:`invoke` wraps into
# ``LangGraphHarnessError``; the orchestrator's gather catches it and
# degrades to B-min (a verdict still emerges within budget — AC-2). A runaway
# gather thus trips this ceiling within a few cycles instead of eating the
# whole task budget and overflowing the 98 K window (run-22 TP05).
_RECURSION_LIMIT_DEFAULT: int | None = None

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
        recursion_limit: int | None = _RECURSION_LIMIT_DEFAULT,
    ) -> None:
        self.model = model
        self.backend = backend
        self.permissions = permissions
        # TASK-PERF-COACHSYNTH: per-invoke super-step ceiling forwarded to
        # ``agent.ainvoke(..., config={"recursion_limit": N})``. ``None``
        # preserves LangGraph's default (25). The Coach gather passes a small
        # value to bound its tool-using loop; see module-level constant.
        self.recursion_limit = recursion_limit
        # TASK-FIX-CTOUT01: handle to the in-flight ``agent.ainvoke``
        # asyncio Task, exposed for cooperative cancellation by
        # :meth:`cancel`. Set inside :meth:`invoke` after
        # :func:`asyncio.create_task` wraps the ``ainvoke`` coroutine,
        # cleared in the ``finally`` block. ``None`` when no invoke is
        # currently active. The indirection (``create_task`` rather than
        # a direct ``await``) is what makes the in-flight ``ainvoke``
        # cancellable from a sibling task — under direct ``await`` the
        # only way to stop the coroutine is to cancel the consumer task
        # iterating the harness's async generator, which is more invasive
        # than the substrate boundary contract permits.
        self._ainvoke_task: asyncio.Task[Any] | None = None

    def _resolve_model_for_invoke(self, role: str | None = None) -> Any:
        """Resolve ``self.model`` and attach profile metadata for invocation.

        TASK-HMIG-002R-MODEL-PROFILE (2026-06-04): wrap
        :func:`guardkitfactory.harness.model_config.resolve_autobuild_model`
        so the model passed into ``create_deep_agent`` carries
        ``model.profile["max_input_tokens"]`` when the operator registry
        knows it. Without the profile, deepagents' summarisation middleware
        falls back to a 170 k-token trigger that is larger than sub-Sonnet
        context windows (qwen36-workhorse: 131 k) and the model overflows
        its context before summarisation fires. See
        ``autobuild-FEAT-AOF-run-2.md`` line 350 for the symptom.

        Resolution is per-invoke (rather than once in ``__init__``) for
        three reasons:

        1. Backward compatibility: existing tests construct the harness
           with sentinel strings like ``"ignored"`` and patch
           ``create_deep_agent``. Eager resolution would call
           ``init_chat_model("ignored")`` at construction time and fail.
        2. ``create_deep_agent`` itself runs per-invoke, so this is not a
           net regression in cost — only a relocation of the existing
           resolution.
        3. Strings vs ``BaseChatModel`` are both handled by the helper;
           ``None`` and other shapes fall through unchanged so the
           construction-failure path keeps its current attribution.

        Resolution failures (e.g. ``init_chat_model("nonexistent:foo")``
        raising ``ValueError`` for an unknown provider) are caught and the
        original ``self.model`` is returned unchanged. The downstream
        ``create_deep_agent`` call then surfaces the same failure with the
        existing attribution shape — keeping AC-008.3
        (``test_construction_failure_wraps_into_langgraph_harness_error``)
        intact. Profile injection is a best-effort fallback; never a
        failure mode.
        """
        model = self.model
        if not isinstance(model, (str, BaseChatModel)):
            return model
        try:
            return resolve_autobuild_model(model, role=role)
        except Exception as exc:  # noqa: BLE001 — best-effort, see docstring
            logger.debug(
                "TASK-HMIG-002R-MODEL-PROFILE: resolve_autobuild_model(%r) "
                "raised %s; passing original model through unchanged.",
                model,
                exc.__class__.__name__,
            )
            return model

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

        # TASK-HMIG-002R-MODEL-PROFILE: resolve here so a known operator-
        # registered model carries ``model.profile["max_input_tokens"]``
        # into the summarisation middleware. See ``_resolve_model_for_invoke``.
        # TASK-FIX-COACHBUDG01: pass ``role`` so per-role max_tokens budgets
        # are applied. Coach (16384 for hybrid-reasoning models) vs Player
        # (8192 default) — without per-role budget injection, hybrid-
        # reasoning models route reasoning_content + content squeeze and
        # produce empty Coach turns (§9.13 of AUTOBUILD-ON-LLAMA-SWAP findings).
        resolved_model = self._resolve_model_for_invoke(role=role)

        try:
            agent = create_deep_agent(
                model=resolved_model,
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

        # TASK-FIX-CTOUT01: wrap ``ainvoke`` in an explicit asyncio.Task
        # so :meth:`cancel` (called from
        # ``AgentInvoker._cancel_monitor`` when the orchestrator's
        # ``cancellation_event`` fires) can propagate
        # ``asyncio.CancelledError`` into LangChain's httpx client before
        # the in-flight HTTP request to the LLM completes.
        #
        # Without this indirection (i.e. a bare ``await agent.ainvoke``),
        # cancellation can only reach the consumer task iterating the
        # async generator — which the orchestrator's outer
        # ``asyncio.timeout(self.sdk_timeout_seconds)`` already covers
        # but the SHORTER outer feature timeout (``task_timeout``) cannot,
        # because ``_cancel_monitor`` does not own the consumer task.
        # TASK-PERF-COACHSYNTH: forward the per-invoke super-step ceiling
        # ONLY when one is set. A ``None`` limit calls ``ainvoke`` with the
        # historical single-arg shape so LangGraph applies its own default
        # (25) — unchanged Player/synthesis behaviour. A small limit (Coach
        # gather) caps the tool-using loop; exceeding it raises
        # ``GraphRecursionError`` which the wrap-and-reraise below turns into
        # ``LangGraphHarnessError`` → orchestrator degrades to B-min (AC-2).
        if self.recursion_limit is not None:
            self._ainvoke_task = asyncio.create_task(
                agent.ainvoke(
                    input_data, config={"recursion_limit": self.recursion_limit}
                )
            )
        else:
            self._ainvoke_task = asyncio.create_task(agent.ainvoke(input_data))
        # TASK-FIX-LGACLOSE: the outer try/finally below spans the whole
        # body — including the yields — so that a consumer closing this
        # async generator mid-stream (``GeneratorExit`` thrown into a
        # suspended ``yield`` by ``aclosing()`` / ``gen.aclose()``) still
        # finalises the in-flight ``ainvoke`` task. CTOUT01 wrapped
        # ``ainvoke`` in a Task so :meth:`cancel` can propagate
        # ``CancelledError``; this fixes CTOUT01's own surface — the
        # generator was abandoned without ``aclose()`` on the cancel
        # path, leaving an orphaned ``async_generator_athrow`` /
        # pending ainvoke task that the GC tried to close at interpreter
        # shutdown (RuntimeWarning "coroutine method 'aclose' ... was
        # never awaited"). The defensive finalisation here is
        # belt-and-suspenders with the consumer-side ``aclosing()``
        # (guardkit ``agent_invoker``); either alone closes the leak.
        try:
            try:
                result = await self._ainvoke_task
            except asyncio.CancelledError:
                # Re-raise so the orchestrator's outer
                # ``asyncio.timeout(...) + CancelledError`` cascade
                # (agent_invoker.py around line 2891) receives the cancel
                # verbatim — matching the SDK harness's behaviour at
                # ``sdk_harness.py:410-419``. Do NOT wrap into
                # ``LangGraphHarnessError``; the orchestrator dispatches on
                # the bare ``asyncio.CancelledError`` type.
                raise
            except Exception as exc:  # noqa: BLE001 — wrap-and-reraise on purpose
                raise LangGraphHarnessError(
                    f"LangGraphHarness: agent.ainvoke failed for "
                    f"role={role!r} model={self.model!r}: {exc}"
                ) from exc

            text = extract_last_ai_message(result) or ""
            # TASK-FIX-COACHBUDG01 (2026-06-06): surface reasoning_content
            # alongside the canonical text. ADR FB-004 / substrate-parity:
            # both harnesses MUST populate
            # ``AssistantMessageEvent.reasoning_text`` when the model
            # emitted reasoning. The orchestrator-side
            # ``coach_output_parser`` falls through to this field when
            # ``text`` does not contain a fenced JSON block — closing the
            # F17 substrate gap for hybrid-reasoning models (Gemma 4 IT,
            # future DeepSeek V4 with reasoning, etc.) without requiring
            # the brittle ``--reasoning off`` llama.cpp flag.
            reasoning_text = extract_last_ai_reasoning(result)

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

            yield AssistantMessageEvent(
                text=text,
                raw=result,
                reasoning_text=reasoning_text,
            )
            yield ResultMessageEvent(
                session_id=None,
                stop_reason="end_turn",
                usage=None,
            )
        finally:
            # TASK-FIX-LGACLOSE: defensive finalisation on EVERY exit path
            # — normal completion, error, ``CancelledError``, or
            # ``GeneratorExit`` from a consumer's ``aclose()``. Clear the
            # handle FIRST so a concurrent :meth:`cancel` racing this
            # finalisation observes the empty handle and returns. If the
            # ainvoke task is still pending (the generator was closed
            # while suspended at a yield before natural completion),
            # cancel it and best-effort await its unwind so no orphaned
            # pending task survives to interpreter shutdown. Suppress the
            # resulting ``CancelledError`` (and any settle-time error) so
            # it does not escape ``aclose()``.
            task = self._ainvoke_task
            self._ainvoke_task = None
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task

    def _synthesis_max_tokens(self) -> int:
        """Resolve the toolless-synthesis generation budget (env-overridable)."""
        raw = os.environ.get(_SYNTHESIS_MAX_TOKENS_ENV)
        if raw:
            try:
                return int(raw)
            except ValueError:
                logger.debug(
                    "TASK-ARCH-COACHSPLIT: ignoring non-int %s=%r; using default %d",
                    _SYNTHESIS_MAX_TOKENS_ENV, raw, _SYNTHESIS_MAX_TOKENS_DEFAULT,
                )
        return _SYNTHESIS_MAX_TOKENS_DEFAULT

    def _synthesis_reasoning_budget(self) -> int | None:
        """Resolve the optional toolless-synthesis reasoning budget.

        TASK-PERF-COACHTURNBUDGET (Lever 2). Returns ``None`` (the default) when
        ``GUARDKIT_COACH_SYNTHESIS_REASONING_BUDGET`` is unset, empty, or non-int
        — the synthesis request then OMITS the field entirely and behaviour is
        unchanged (the server's own ``--reasoning`` policy governs). An int value
        (including ``0`` and ``-1``) is injected into the request body as
        ``reasoning_budget`` to curtail the ``reasoning_content`` phase without
        touching ``max_tokens`` (which would truncate the verdict — AC-3).
        """
        raw = os.environ.get(_SYNTHESIS_REASONING_BUDGET_ENV)
        if raw is None or raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            logger.debug(
                "TASK-PERF-COACHTURNBUDGET: ignoring non-int %s=%r; reasoning "
                "budget unset (synthesis request omits the field)",
                _SYNTHESIS_REASONING_BUDGET_ENV, raw,
            )
            return None

    def _synthesis_disable_thinking(self) -> bool:
        """Resolve whether to suppress the synthesis reasoning_content phase via
        the chat-template ``enable_thinking=false`` toggle.

        TASK-FIX-COACHREASON01. Returns ``True`` only when
        ``GUARDKIT_COACH_SYNTHESIS_DISABLE_THINKING`` is a truthy string
        (``1``/``true``/``yes``/``on``, case-insensitive). When True the
        synthesis request body carries
        ``chat_template_kwargs={"enable_thinking": False}`` — the toggle the
        GB10 llama-swap gemma models actually honour (the llama.cpp
        ``reasoning_budget`` field is ignored there). Default-off: unset or any
        other value omits the field and leaves behaviour unchanged.
        """
        raw = os.environ.get(_SYNTHESIS_DISABLE_THINKING_ENV)
        if raw is None:
            return False
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _build_synthesis_model(self, *, grammar: str | None, role: str) -> Any:
        """Build the **toolless** model for a Coach verdict-synthesis turn.

        TASK-ARCH-COACHSPLIT (D-3). Deliberately BYPASSES
        :func:`deepagents.create_deep_agent` (which always binds DeepAgents'
        built-in tool surface, making every request tool-bound) so the
        resulting request carries **no** ``tools`` field — the precondition
        for llama.cpp to honour a per-request GBNF ``grammar`` (a tool-bound
        request is hard-rejected with HTTP 400 "Cannot use custom grammar
        constraints with tools"; verified 2026-06-09).

        Two construction paths:

        * **Injected model** (``self.model`` is already a ``BaseChatModel`` —
          the unit-test / explicit-model case): bind the grammar via
          ``extra_body`` and return it. ``.bind`` adds NO tools, so the call
          stays toolless.
        * **String alias** (production — e.g. ``"openai:gemma4:31b"`` from the
          selector): build a fresh ``ChatOpenAI`` on the **chat-completions**
          transport (``use_responses_api=False``), with the grammar as a
          top-level body field via ``extra_body={"grammar": ...}``. This
          mirrors the validated probe EXACTLY. The deepagents default
          resolver routes through the Responses API (``/v1/responses``) where
          the grammar is UNVALIDATED — chat-completions is where the toolless
          grammar guarantee was confirmed, so we force it here.

        The grammar is honoured by llama.cpp; Anthropic/OpenAI ignore an
        unknown ``extra_body`` field. ``grammar=None`` runs unconstrained.
        """
        from langchain_core.language_models import BaseChatModel

        # TASK-PERF-COACHTURNBUDGET (Lever 2): assemble the request-body extras.
        # ``grammar`` (TASK-ARCH-COACHSPLIT) and ``reasoning_budget`` (this task,
        # default-off) ride together as top-level body fields. When BOTH are
        # absent ``extra_body`` collapses to ``None`` and the call is unchanged.
        _extras: dict[str, Any] = {}
        if grammar:
            _extras["grammar"] = grammar
        reasoning_budget = self._synthesis_reasoning_budget()
        if reasoning_budget is not None:
            _extras["reasoning_budget"] = reasoning_budget
        disable_thinking = self._synthesis_disable_thinking()
        if disable_thinking:
            _extras["chat_template_kwargs"] = {"enable_thinking": False}
        extra_body: dict[str, Any] | None = _extras or None

        if isinstance(self.model, BaseChatModel):
            model = self.model
            if extra_body is not None:
                try:
                    model = model.bind(extra_body=extra_body)
                except Exception as exc:  # noqa: BLE001 — best-effort
                    logger.warning(
                        "TASK-ARCH-COACHSPLIT: failed to bind extra_body %r onto "
                        "injected model %s (%s); running synthesis WITHOUT the "
                        "grammar/reasoning_budget request fields.",
                        sorted(extra_body), type(self.model).__name__, exc,
                    )
            return model

        # Production string-alias path: build a chat-completions ChatOpenAI.
        from langchain_openai import ChatOpenAI

        from guardkitfactory.harness.model_config import _bare_model_name

        bare = _bare_model_name(str(self.model))
        kwargs: dict[str, Any] = {
            "model": bare,
            "temperature": 0.0,
            "max_tokens": self._synthesis_max_tokens(),
        }
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        # ChatOpenAI reads OPENAI_BASE_URL / OPENAI_API_KEY from env when the
        # explicit kwargs are absent, but pass them through when present so
        # the synthesis call targets the same llama-swap endpoint the rest of
        # the run uses (the autobuild recipe exports both).
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            kwargs["api_key"] = api_key
        logger.info(
            "TASK-ARCH-COACHSPLIT: toolless synthesis model role=%r model=%r "
            "grammar=%s reasoning_budget=%s disable_thinking=%s "
            "transport=chat-completions max_tokens=%d",
            role, bare, "present" if grammar else "none",
            reasoning_budget if reasoning_budget is not None else "unset",
            disable_thinking,
            kwargs["max_tokens"],
        )
        # Force chat-completions transport (probe-faithful). Tolerate an older
        # langchain-openai that lacks the kwarg.
        try:
            return ChatOpenAI(use_responses_api=False, **kwargs)
        except TypeError:
            return ChatOpenAI(**kwargs)

    async def invoke_synthesis(
        self,
        prompt: str,
        role: str,
        *,
        grammar: str | None,
        cwd: Path,
        timeout_seconds: int,
    ) -> AsyncIterator[HarnessEvent]:
        """Run one **toolless** verdict-synthesis turn (TASK-ARCH-COACHSPLIT).

        Mirrors :meth:`invoke`'s event stream (one
        :class:`AssistantMessageEvent` carrying the final text + reasoning,
        then one terminal :class:`ResultMessageEvent`) and its CTOUT01
        cancellation wiring (the ``ainvoke`` coroutine is wrapped in an
        ``asyncio.Task`` so :meth:`cancel` can propagate ``CancelledError``,
        and the ``finally`` block finalises it on every exit path). The key
        difference from :meth:`invoke`: it invokes the **bare** model
        (no ``create_deep_agent``, no tools) so the request honours the
        grammar and emits no tool-call markers.
        """
        input_data = self._build_input(prompt)
        assert_no_system_messages(input_data)

        model = self._build_synthesis_model(grammar=grammar, role=role)

        # TASK-FIX-CTOUT01 parity: wrap ainvoke in an explicit Task so
        # :meth:`cancel` can propagate CancelledError into the in-flight
        # HTTP request (same rationale as :meth:`invoke`).
        self._ainvoke_task = asyncio.create_task(
            model.ainvoke(input_data["messages"])
        )
        try:
            try:
                result = await self._ainvoke_task
            except asyncio.CancelledError:
                # Re-raise verbatim so the orchestrator's outer
                # asyncio.timeout + CancelledError cascade handles it
                # (matches :meth:`invoke` and the SDK harness).
                raise
            except Exception as exc:  # noqa: BLE001 — wrap-and-reraise
                raise LangGraphHarnessError(
                    f"LangGraphHarness: synthesis ainvoke failed for "
                    f"role={role!r} model={self.model!r}: {exc}"
                ) from exc

            # A bare-model ainvoke returns a single AIMessage, not a graph
            # state dict. Wrap it into the {"messages": [...]} shape the
            # extractors expect so their chat-completions / Responses-API
            # reasoning recovery applies unchanged (substrate parity,
            # ADR FB-004). No ToolUseEvents — the synthesis turn is toolless.
            wrapped = {"messages": [result]}
            text = extract_last_ai_message(wrapped) or ""
            reasoning_text = extract_last_ai_reasoning(wrapped)

            yield AssistantMessageEvent(
                text=text,
                raw=result,
                reasoning_text=reasoning_text,
            )
            yield ResultMessageEvent(
                session_id=None,
                stop_reason="end_turn",
                usage=None,
            )
        finally:
            # TASK-FIX-LGACLOSE parity: finalise on EVERY exit path. Clear the
            # handle first so a concurrent :meth:`cancel` observes the empty
            # handle and returns; cancel + best-effort await any still-pending
            # task so none survives to interpreter shutdown.
            task = self._ainvoke_task
            self._ainvoke_task = None
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task

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

    async def cancel(self) -> None:
        """TASK-FIX-CTOUT01: cancel the in-flight ``agent.ainvoke`` task.

        Called by ``AgentInvoker._cancel_monitor`` when the orchestrator's
        ``cancellation_event`` fires during a Coach or Player invocation.
        Cancellation reaches LangChain's pregel loop at its next
        checkpoint boundary, which in turn propagates
        ``asyncio.CancelledError`` into the httpx client so the
        in-flight HTTP request to the LLM is abandoned rather than
        running to natural completion.

        Behaviour vs ClaudeSDKHarness.cancel:

        * SDK substrate: cancel() closes the active ``query()`` async
          generator; the orchestrator's separate
          ``_kill_child_claude_processes`` (TASK-FIX-ASPF-004) is the
          OS-level escalation.
        * LangGraph substrate: cancel() is the ONLY thing that unblocks
          the in-flight call — the ``_kill_child_claude_processes``
          path is a no-op here (no subprocess to terminate; the LLM
          HTTP request lives inside the Python process).

        Deadline: cancel() waits up to
        ``GUARDKIT_HARNESS_CANCEL_DEADLINE`` seconds (default 30) for
        the cancelled task to actually unwind. If LangChain's httpx
        client ignores the cancellation past the deadline, a WARNING
        is logged and the task is leaked to GC — the orchestrator's
        ``LATE_APPROVAL_GRACE_S`` reconciliation
        (``feature_orchestrator.py:_check_late_approval``) is the
        safety net that maps a late-arriving Coach approval to
        ``approved_late/success=True`` in the bookkeeping.

        Idempotent: no-op if no invoke is currently active, or if the
        in-flight task has already completed. Safe to call concurrently
        with the natural finalisation in :meth:`invoke`'s ``finally``
        block — the task-handle clear is the only shared state and the
        ``task.done()`` guard makes a double-cancel a no-op.

        See ``.claude/rules/harness-cancellation-contract.md`` Layer 3
        for the four-layer cancellation taxonomy this method
        participates in.
        """
        task = self._ainvoke_task
        if task is None or task.done():
            return
        task.cancel()
        # Float-seconds parsing so tests can drive the deadline branch
        # below one second; production callers set integer seconds via
        # the env var so float parsing is a permissive superset.
        try:
            deadline_s = float(
                os.environ.get(_CANCEL_DEADLINE_ENV, _CANCEL_DEADLINE_DEFAULT_S)
            )
        except ValueError:
            deadline_s = float(_CANCEL_DEADLINE_DEFAULT_S)

        # ``asyncio.wait_for`` semantics: awaits ``task`` up to
        # ``deadline_s``. If ``task`` settles (success / error /
        # CancelledError from our prior task.cancel()) within the
        # deadline → returns or raises that exception. If the deadline
        # fires first → raises ``asyncio.TimeoutError`` and the in-flight
        # task is left to GC.
        #
        # Note on ``asyncio.timeout(...) + suppress(...)`` (rejected
        # design): suppressing CancelledError INSIDE the
        # ``async with asyncio.timeout()`` block swallows the cancel
        # before the context manager's ``__aexit__`` can convert it to
        # ``TimeoutError``, so the deadline-expiry branch never fires.
        # ``wait_for`` has the inverse semantics and is the right
        # primitive here.
        try:
            await asyncio.wait_for(task, timeout=deadline_s)
        except asyncio.TimeoutError:
            logger.warning(
                "LangGraphHarness.cancel: ainvoke task did not honour "
                "cancellation within %.2fs deadline (env=%s); leaking "
                "task to GC. The orchestrator's LATE_APPROVAL_GRACE_S "
                "reconciliation will catch a late Coach approval if it "
                "lands in time.",
                deadline_s,
                _CANCEL_DEADLINE_ENV,
            )
        except (asyncio.CancelledError, Exception):
            # Task settled within deadline — by raising CancelledError
            # (which is what we wanted) or any other exception. We
            # cancelled by design; do not propagate.
            pass
