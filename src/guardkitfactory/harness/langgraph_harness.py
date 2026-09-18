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
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Literal

from deepagents import create_deep_agent
from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    HarnessAdapter,
    HarnessEvent,
    ResultMessageEvent,
    ToolResultEvent,
    ToolUseEvent,
)
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from guardkitfactory.harness.extractors import (
    extract_last_ai_message,
    extract_last_ai_reasoning,
)
from guardkitfactory.harness.http_clients import (
    create_chat_openai,
    with_invocation_clients,
)
from guardkitfactory.harness.model_config import resolve_autobuild_model
from guardkitfactory.harness.player_config import (
    PlayerConfig,
    PlayerConfigError,
    revalidate_player_config,
)
from guardkitfactory.lib.factory_guards import assert_no_system_messages

logger = logging.getLogger(__name__)

_COMMON_AGENT_INSTRUCTIONS = """\
Work inside the assigned repository and inspect the relevant files before acting.
For multi-step work, use write_todos to keep a short, current plan.
Use the filesystem, search, and execute tools to gather evidence and verify results.
Keep all file mutations inside approved roots and do not change project-declared protected paths.
Report concrete results and any verification that could not be completed.
"""

_ROLE_AGENT_INSTRUCTIONS = {
    "player": """\
Implement the requested change completely. Follow repository instructions,
preserve existing behavior outside the requested scope, and run focused checks.
""",
    "coach": """\
Review the implementation independently against the supplied acceptance
criteria. Inspect the actual diff and test evidence, run focused checks when
needed, and return the structured verdict requested by the user prompt.
""",
}


def _system_prompt_for_role(role: str) -> str:
    role_instructions = _ROLE_AGENT_INSTRUCTIONS.get(
        role,
        "Complete the assigned software-engineering task and verify the result.\n",
    )
    return f"{_COMMON_AGENT_INSTRUCTIONS}\n{role_instructions}"


def _player_context_prompt(
    config: PlayerConfig,
    required_skill_documents: tuple[dict[str, Any], ...] = (),
) -> str:
    """Render the validated project context supplied to the dcode user turn."""

    sections = [
        "## Factory-supplied project context",
        f"The assigned task worktree is exactly: {config.cwd}",
        "Filesystem-tool paths are absolute. Relative shell paths resolve from "
        f"{config.cwd}.",
    ]
    if config.repository_instructions:
        sections.append("### Repository instructions")
        for path in config.repository_instructions:
            relative = path.relative_to(config.cwd)
            sections.append(f"#### {relative}\n{path.read_text(encoding='utf-8')}")
    if required_skill_documents:
        sections.append(
            "### Required selected-skill reads\n"
            "Before execution, delegation, or file changes, use read_file to read "
            "every document below. Discovery alone does not satisfy this requirement."
        )
        sections.extend(
            f"- {item['path']} (sha256 {item['sha256']}; "
            f"read from offset 0 with limit at least {item['line_count']})"
            for item in required_skill_documents
        )
    if config.declared_commands:
        sections.append("### Project-declared commands (use unchanged)")
        sections.extend(f"- {name}: `{command}`" for name, command in config.declared_commands)
    if config.protected_paths:
        sections.append("### Project-declared protected paths (read-only)")
        sections.extend(f"- {path.relative_to(config.cwd)}" for path in config.protected_paths)
    return "\n\n".join(sections)


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


def _iter_tool_result_events(result: Any) -> list[ToolResultEvent]:
    """Extract ``ToolResultEvent`` values from a DeepAgents ``ainvoke`` result.

    TASK-FIX-COACHTRES01 (capture fix, substrate parity). Every
    ``ToolMessage`` in ``result["messages"]`` carries the *output* of a prior
    tool call (LangChain v0.3 shape: ``.content`` ``str | list``,
    ``.tool_call_id`` ``str``, ``.status`` ``"success" | "error"``). Mirrors
    :func:`_iter_tool_use_events` so the Coach's independent-test path
    (``coach_validator._run_tests_via_sdk``) sees the *real* command output
    (e.g. the pytest stdout from the Bash/execute tool) on the LangGraph
    substrate — not just the agent's final narration. This closes the same
    FEAT-HARV narration-capture defect on the LangGraph side that the SDK
    harness fix closes by surfacing the dropped ``UserMessage``/
    ``ToolResultBlock``: the consumer's pre-existing ``ToolResultEvent``
    branch prefers ``bash_output`` over the narration ``collected_text``.

    Duck-typed by class name so non-``ToolMessage`` elements (AIMessage,
    HumanMessage, dict-form messages) are silently skipped. ``content`` is
    passed through verbatim (``str`` or ``list``) — the consumer handles both.

    Returns
    -------
    list[ToolResultEvent]
        Ordered by appearance in ``result["messages"]``. Empty when the
        result has no tool-result activity.
    """
    if not isinstance(result, dict):
        return []
    messages = result.get("messages", []) or []
    events: list[ToolResultEvent] = []
    for msg in messages:
        if type(msg).__name__ != "ToolMessage":
            continue
        content = getattr(msg, "content", "")
        events.append(
            ToolResultEvent(
                tool_use_id=str(getattr(msg, "tool_call_id", "") or ""),
                content=content if content is not None else "",
                is_error=getattr(msg, "status", "success") == "error",
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

    def __init__(self, message: str, *, raw_result: Any = None) -> None:
        super().__init__(message)
        self.raw_result = raw_result


@dataclass(frozen=True)
class NativeToolEvent:
    """A native tool boundary captured while ``ainvoke`` is running."""

    phase: Literal["start", "end", "error"]
    run_id: str
    parent_run_id: str | None
    tool_name: str | None
    payload: Any


class NativeToolEvidenceError(RuntimeError):
    """An enabled progressive tool-evidence sink could not record."""


class _ModelActivityCallbackHandler(BaseCallbackHandler):
    """LangChain callback that pings ``on_model_activity`` on real LLM/tool work.

    TASK-FIX-SPECINVOKE01. The orchestrator's no-model-activity watchdog
    (``guardkit.orchestrator.specialist_invocations._run_specialist_with_watchdog``)
    keys on ``AgentInvoker._last_activity_monotonic``, which the consumer
    loop in ``AgentInvoker._invoke_with_role`` only refreshes when a
    :class:`HarnessEvent` is *yielded*. But :meth:`LangGraphHarness.invoke`
    awaits the **entire** multi-turn ``agent.ainvoke()`` before yielding any
    event, so the activity clock stays frozen at its seed value for the whole
    run — and the watchdog kills a *live, model-active* specialist at the
    150 s mark (FEAT-9DDE run 3: ~18 successful ``/v1/responses`` POSTs, yet
    ``0 events`` reached the consumer). This handler restores a faithful
    activity signal: it fires on every model-call boundary and every tool
    boundary, so the watchdog measures *real* model activity rather than the
    LangGraph harness's buffered event-arrival cadence. A genuine hang
    (the substrate stops calling the model entirely, e.g. run-9 turn-2) still
    starves the callback, so the watchdog continues to catch it.

    The activity callback remains best-effort. When progressive evidence is
    enabled, its sink is fail-closed so a missing record cannot look complete.
    """

    def __init__(
        self,
        on_model_activity: Callable[[], None] | None,
        on_native_tool_event: Callable[[NativeToolEvent], None] | None = None,
    ) -> None:
        self._on_model_activity = on_model_activity
        self._on_native_tool_event = on_native_tool_event
        # LangChain otherwise logs and suppresses callback failures. Enabled
        # evidence capture must fail visibly instead of producing a silently
        # incomplete trace.
        self.raise_error = on_native_tool_event is not None
        self._tool_names: dict[str, str | None] = {}

    def _ping(self) -> None:
        if self._on_model_activity is None:
            return
        try:
            self._on_model_activity()
        except Exception:  # noqa: BLE001 — activity sink must never abort a run
            logger.debug(
                "TASK-FIX-SPECINVOKE01: on_model_activity callback raised; "
                "ignoring.",
                exc_info=True,
            )

    # Model-call boundaries. ``on_chat_model_start`` covers chat models
    # (ChatOpenAI / init_chat_model — the autobuild default); ``on_llm_start``
    # covers completion models; ``on_llm_new_token`` covers any streamed
    # token; ``on_llm_end`` covers the response landing.
    def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
        self._ping()

    def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
        self._ping()

    def on_llm_new_token(self, *args: Any, **kwargs: Any) -> None:
        self._ping()

    def on_llm_end(self, *args: Any, **kwargs: Any) -> None:
        self._ping()

    # Tool boundaries — a long-running tool (e.g. the test-orchestrator's
    # background pytest poll) is also genuine progress, not a hang.

    @staticmethod
    def _correlation(kwargs: dict[str, Any]) -> tuple[str, str | None]:
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        return str(run_id or ""), (
            str(parent_run_id) if parent_run_id is not None else None
        )

    @classmethod
    def _evidence_payload(cls, value: Any) -> Any:
        """Return a lossless JSON-shaped view of common tool payloads."""
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Mapping):
            return {
                str(key): cls._evidence_payload(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._evidence_payload(item) for item in value]
        if is_dataclass(value) and not isinstance(value, type):
            return cls._evidence_payload(asdict(value))
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return cls._evidence_payload(model_dump())
        return repr(value)

    def _emit_tool_event(self, event: NativeToolEvent) -> None:
        if self._on_native_tool_event is None:
            return
        try:
            self._on_native_tool_event(event)
        except Exception as exc:  # noqa: BLE001 -- fail closed with context
            logger.error(
                "Progressive native tool evidence failed for phase=%s "
                "run_id=%s tool=%r: %s",
                event.phase, event.run_id, event.tool_name, exc,
                exc_info=True,
            )
            raise NativeToolEvidenceError(
                "progressive native tool evidence could not be recorded "
                f"for phase={event.phase} run_id={event.run_id}"
            ) from exc

    def on_tool_start(
        self,
        serialized: dict[str, Any] | None = None,
        input_str: str = "",
        **kwargs: Any,
    ) -> None:
        self._ping()
        run_id, parent_run_id = self._correlation(kwargs)
        raw_name = serialized.get("name") if isinstance(serialized, dict) else None
        payload = kwargs.get("inputs")
        if payload is None:
            payload = input_str
        tool_name = str(raw_name) if raw_name is not None else None
        self._tool_names[run_id] = tool_name
        self._emit_tool_event(
            NativeToolEvent(
                phase="start",
                run_id=run_id,
                parent_run_id=parent_run_id,
                tool_name=tool_name,
                payload=self._evidence_payload(payload),
            )
        )

    def on_tool_end(self, output: Any = None, **kwargs: Any) -> None:
        self._ping()
        run_id, parent_run_id = self._correlation(kwargs)
        self._emit_tool_event(
            NativeToolEvent(
                phase="end",
                run_id=run_id,
                parent_run_id=parent_run_id,
                tool_name=self._tool_names.pop(run_id, None),
                payload=self._evidence_payload(output),
            )
        )

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._ping()
        run_id, parent_run_id = self._correlation(kwargs)
        self._emit_tool_event(
            NativeToolEvent(
                phase="error",
                run_id=run_id,
                parent_run_id=parent_run_id,
                tool_name=self._tool_names.pop(run_id, None),
                payload={"type": type(error).__name__, "message": str(error)},
            )
        )


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
        on_model_activity: Callable[[], None] | None = None,
        on_native_tool_event: Callable[[NativeToolEvent], None] | None = None,
        player_config: PlayerConfig | None = None,
    ) -> None:
        self.model = model
        self.backend = backend
        self.permissions = permissions
        # TASK-FIX-SPECINVOKE01: optional sink pinged on every LLM/tool
        # boundary during ``agent.ainvoke``. The orchestrator threads
        # ``AgentInvoker._bump_activity`` here so the no-model-activity
        # watchdog measures real model activity rather than this harness's
        # buffered (await-then-yield) event cadence. ``None`` (the default,
        # and what every existing test/construction site supplies) installs
        # no callbacks — behaviour is byte-for-byte unchanged.
        self.on_model_activity = on_model_activity
        self.on_native_tool_event = on_native_tool_event
        self.player_config = player_config
        self.last_player_evidence: dict[str, Any] | None = None
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

    def _player_backend_root(self) -> Path:
        """Return the proved execution root used by an enabled config."""

        default = getattr(self.backend, "default", None)
        backend_cwd = getattr(self.backend, "cwd", None)
        default_cwd = getattr(default, "cwd", None)
        execution_label = "default backend cwd" if default is not None else "backend cwd"
        execution_root = default_cwd if default is not None else backend_cwd
        if execution_root is None:
            raise LangGraphHarnessError(
                "LangGraphHarness: a Player requires an explicit "
                f"execution cwd ({execution_label}); artifacts_root alone does not "
                "prove where commands run"
            )

        raw_roots = [
            ("artifacts_root", getattr(self.backend, "artifacts_root", None)),
            ("backend cwd", backend_cwd),
            ("default backend cwd", default_cwd),
        ]
        selected = [(label, root) for label, root in raw_roots if root is not None]

        resolved_roots: list[tuple[str, Path]] = []
        for label, root in selected:
            try:
                resolved = Path(root).resolve(strict=True)
            except (OSError, RuntimeError, TypeError) as exc:
                raise LangGraphHarnessError(
                    "LangGraphHarness: Player config "
                    f"{label} is invalid: {root!r}"
                ) from exc
            if not resolved.is_dir():
                raise LangGraphHarnessError(
                    "LangGraphHarness: Player config "
                    f"{label} is not a directory: {resolved}"
                )
            resolved_roots.append((label, resolved))

        unique_roots = {root for _, root in resolved_roots}
        if len(unique_roots) != 1:
            detail = ", ".join(f"{label}={root}" for label, root in resolved_roots)
            raise LangGraphHarnessError(
                "LangGraphHarness: Player config has conflicting backend roots: "
                f"{detail}"
            )
        return next(root for label, root in resolved_roots if label == execution_label)

    def _create_agent(self, *, role: str, cwd: Path, resolved_model: Any) -> Any:
        """Construct the shared Coach graph or the required dcode Player."""

        config = self.player_config
        if role != "player":
            if config is not None:
                raise LangGraphHarnessError(
                    "LangGraphHarness: player_config may only be used for role='player'"
                )
            return create_deep_agent(
                model=resolved_model,
                tools=[],
                middleware=[TodoListMiddleware()],
                backend=self.backend,
                permissions=self.permissions,
                system_prompt=_system_prompt_for_role(role),
            )

        if config is None:
            raise LangGraphHarnessError(
                "LangGraphHarness: role='player' requires a validated Player config; "
                "the native Player implementation has been retired"
            )
        try:
            revalidate_player_config(config, cwd=cwd)
        except PlayerConfigError as exc:
            raise LangGraphHarnessError(
                f"LangGraphHarness: invalid Player config at invocation: {exc}"
            ) from exc
        invocation_root = Path(cwd).resolve(strict=True)
        backend_root = self._player_backend_root()
        if backend_root != invocation_root:
            raise LangGraphHarnessError(
                "LangGraphHarness: Player config backend/worktree mismatch: "
                f"backend={backend_root} invocation={invocation_root}"
            )

        from guardkitfactory.harness.dcode_harness import create_dcode_player

        return create_dcode_player(
            model=resolved_model,
            backend=self.backend,
            cwd=invocation_root,
            config=config,
            recursion_limit=self.recursion_limit,
        )

    @staticmethod
    def _player_terminal_message(result: Any) -> AIMessage:
        """Return the last actual AIMessage without falling back to older text."""

        messages = result.get("messages", []) if isinstance(result, dict) else []
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message
        raise LangGraphHarnessError(
            "LangGraphHarness: Player returned no terminal AIMessage",
            raw_result=result,
        )

    @staticmethod
    def _player_terminal_metadata(
        message: AIMessage,
    ) -> tuple[str, str | None, dict[str, object] | None, str]:
        """Extract terminal metadata from the same actual AIMessage."""

        single_message_result = {"messages": [message]}
        text = extract_last_ai_message(single_message_result) or ""
        reasoning = extract_last_ai_reasoning(single_message_result)
        response_metadata = getattr(message, "response_metadata", None)
        finish_reason: str | None = None
        if isinstance(response_metadata, Mapping):
            raw_finish = response_metadata.get("finish_reason") or response_metadata.get(
                "stop_reason"
            )
            if raw_finish is not None:
                finish_reason = str(raw_finish)
        if finish_reason is None:
            additional_kwargs = getattr(message, "additional_kwargs", None)
            if isinstance(additional_kwargs, Mapping):
                raw_finish = additional_kwargs.get("finish_reason")
                if raw_finish is not None:
                    finish_reason = str(raw_finish)

        raw_usage = getattr(message, "usage_metadata", None)
        if not isinstance(raw_usage, Mapping) and isinstance(response_metadata, Mapping):
            raw_usage = response_metadata.get("token_usage")
        usage = dict(raw_usage) if isinstance(raw_usage, Mapping) else None
        return text, finish_reason, usage, reasoning

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

        Local OpenAI construction failures fail visibly: fallback would bypass
        invocation-owned clients. Other resolution failures (e.g.
        ``init_chat_model("nonexistent:foo")``
        raising ``ValueError`` for an unknown provider) are caught and the
        original ``self.model`` is returned unchanged. The downstream
        ``create_deep_agent`` call then surfaces the same failure with the
        existing attribution shape — keeping AC-008.3
        (``test_construction_failure_wraps_into_langgraph_harness_error``)
        intact. Profile injection is a best-effort fallback; never a
        failure mode.
        """
        model = self.model
        if role == "player" and "GUARDKIT_PLAYER_MODEL_LIMITS" in os.environ:
            from guardkitfactory.harness.model_config import resolve_player_model_limits

            try:
                return resolve_player_model_limits(
                    model, os.environ["GUARDKIT_PLAYER_MODEL_LIMITS"]
                )
            except Exception as exc:
                raise LangGraphHarnessError(
                    f"LangGraphHarness: explicit Player model limits refused: {exc}"
                ) from exc
        if not isinstance(model, (str, BaseChatModel)):
            return model
        try:
            return resolve_autobuild_model(model, role=role)
        except Exception as exc:  # noqa: BLE001 — retain nonlocal fallback only
            if isinstance(model, str) and model.startswith("openai:"):
                # Falling back here would let Deep Agents bypass ownership and
                # resolve another cached client (and possibly Responses API).
                raise LangGraphHarnessError(
                    f"LangGraphHarness: failed to construct local model {model!r}: {exc}"
                ) from exc
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

    def _build_invoke_config(self) -> dict[str, Any] | None:
        """Assemble the ``ainvoke`` ``config`` dict, or ``None`` when empty.

        TASK-FIX-SPECINVOKE01 / TASK-PERF-COACHSYNTH. Combines two optional
        knobs:

        * ``recursion_limit`` — the per-invoke super-step ceiling (LangGraph
          default 25 when ``None``).
        * ``callbacks`` — a single :class:`_ModelActivityCallbackHandler`
          wrapping ``self.on_model_activity`` so the orchestrator's
          no-model-activity watchdog sees real LLM/tool progress through this
          harness's await-then-yield event cadence.

        Returns ``None`` when neither knob is set so the historical single-arg
        ``agent.ainvoke(input_data)`` call shape (and the tests that assert it)
        is preserved unchanged.
        """
        config: dict[str, Any] = {}
        if self.recursion_limit is not None:
            config["recursion_limit"] = self.recursion_limit
        if (
            self.on_model_activity is not None
            or self.on_native_tool_event is not None
        ):
            config["callbacks"] = [
                _ModelActivityCallbackHandler(
                    self.on_model_activity, self.on_native_tool_event
                )
            ]
        return config or None

    @with_invocation_clients
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
        required_skill_documents: tuple[dict[str, Any], ...] = ()
        if role == "player" and self.player_config is not None:
            self.last_player_evidence = None
            try:
                revalidate_player_config(self.player_config, cwd=cwd)
            except PlayerConfigError as exc:
                raise LangGraphHarnessError(
                    f"LangGraphHarness: invalid Player config at invocation: {exc}"
                ) from exc
            from guardkitfactory.harness.dcode_harness import required_skill_reads

            required_skill_documents = required_skill_reads(self.player_config)
            prompt = (
                f"{_player_context_prompt(self.player_config, required_skill_documents)}"
                "\n\n## Assigned task\n\n"
                f"{prompt}"
            )
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
            agent = self._create_agent(role=role, cwd=cwd, resolved_model=resolved_model)
        except LangGraphHarnessError:
            raise
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
        # TASK-FIX-SPECINVOKE01: ``_build_invoke_config`` folds the
        # ``recursion_limit`` super-step ceiling together with the optional
        # model-activity callbacks. When BOTH are unset it returns ``None`` so
        # the historical single-arg ``ainvoke(input_data)`` shape is preserved
        # byte-for-byte (the unchanged Player/synthesis default).
        _config = self._build_invoke_config()
        if _config is not None:
            self._ainvoke_task = asyncio.create_task(
                agent.ainvoke(input_data, config=_config)
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

            terminal_message: AIMessage | None = None
            if self.player_config is not None:
                terminal_message = self._player_terminal_message(result)
                text, stop_reason, usage, reasoning_text = (
                    self._player_terminal_metadata(terminal_message)
                )
                if not text.strip():
                    raise LangGraphHarnessError(
                        "LangGraphHarness: Player returned an empty "
                        "terminal assistant answer",
                        raw_result=result,
                    )
                if stop_reason is not None and stop_reason.casefold() == "length":
                    raise LangGraphHarnessError(
                        "LangGraphHarness: Player terminal answer was "
                        "truncated (finish_reason='length')",
                        raw_result=result,
                    )
                from guardkitfactory.harness.skill_read_middleware import (
                    SelectedSkillReadError,
                    SelectedSkillReadMiddleware,
                )

                skill_gate = getattr(agent, "guardkit_skill_read_gate", None)
                if not isinstance(skill_gate, SelectedSkillReadMiddleware):
                    raise LangGraphHarnessError(
                        "LangGraphHarness: dcode Player did not expose its skill-read gate",
                        raw_result=result,
                    )
                try:
                    consumption = skill_gate.evidence()
                except SelectedSkillReadError as exc:
                    raise LangGraphHarnessError(
                        f"dcode Player: {exc}", raw_result=result
                    ) from exc
                evidence = getattr(agent, "guardkit_dcode_evidence", None)
                if not isinstance(evidence, dict):
                    raise LangGraphHarnessError(
                        "LangGraphHarness: dcode Player did not expose construction evidence",
                        raw_result=result,
                    )
                evidence["skill_consumption"] = consumption
                self.last_player_evidence = dict(evidence)
            else:
                text = extract_last_ai_message(result) or ""
                stop_reason = "end_turn"
                usage = None
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
            if self.player_config is None:
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

            # TASK-FIX-COACHTRES01 (capture fix, substrate parity): emit one
            # ToolResultEvent per ToolMessage in the result history, BEFORE the
            # terminal events, so the Coach independent-test consumer captures
            # the real tool output (pytest stdout) rather than the agent's
            # narration. Mirrors the SDK harness's UserMessage/ToolResultBlock
            # emission. Ordered after the tool-USE events to preserve the
            # use-then-result textual order; the consumer takes the last
            # ToolResultEvent's content as ``bash_output`` (last-wins).
            for tool_result_event in _iter_tool_result_events(result):
                yield tool_result_event

            yield AssistantMessageEvent(
                text=text,
                raw=result,
                reasoning_text=reasoning_text,
            )
            yield ResultMessageEvent(
                session_id=None,
                stop_reason=stop_reason,
                usage=usage,
                raw=terminal_message,
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
            # Injected local ChatOpenAI instances need the same transport
            # normalisation as Player/Coach graph models. Resolve without a
            # role here so a caller-provided synthesis budget stays intact.
            model = resolve_autobuild_model(self.model)
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
        configured_key = os.environ.get("OPENAI_API_KEY")
        if configured_key:
            kwargs["api_key"] = configured_key
        logger.info(
            "TASK-ARCH-COACHSPLIT: toolless synthesis model role=%r model=%r "
            "grammar=%s reasoning_budget=%s disable_thinking=%s "
            "transport=chat-completions max_tokens=%d",
            role, bare, "present" if grammar else "none",
            reasoning_budget if reasoning_budget is not None else "unset",
            disable_thinking,
            kwargs["max_tokens"],
        )
        # Force chat-completions transport (probe-faithful). All supported
        # langchain-openai versions accept this setting. Let construction
        # errors propagate so an owned transport failure cannot trigger a
        # second model construction or silently switch transport APIs.
        return create_chat_openai(use_responses_api=False, **kwargs)

    @with_invocation_clients
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
        # TASK-FIX-SPECINVOKE01 parity: thread the model-activity callback so
        # a long synthesis turn also refreshes the orchestrator activity clock.
        # The bare-model synthesis path has no ``recursion_limit``, so only the
        # callbacks knob applies here.
        if self.on_model_activity is not None:
            self._ainvoke_task = asyncio.create_task(
                model.ainvoke(
                    input_data["messages"],
                    config={
                        "callbacks": [
                            _ModelActivityCallbackHandler(self.on_model_activity)
                        ]
                    },
                )
            )
        else:
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
        # fires first → raises ``TimeoutError`` and the in-flight
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
        except TimeoutError:
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
