"""Async autobuild runner subagent (TASK-FW10-002, FEAT-FORGE-010).

This module is the production implementation of the long-running
autobuild stage. The supervisor dispatches it via
DeepAgents ``start_async_task`` (per ADR-ARCH-031); the compiled
:data:`graph` exported here is the addressable surface the
``AsyncSubAgentMiddleware`` looks up by ``graph_id="autobuild_runner"``
when ``langgraph.json`` resolves the ``autobuild_runner`` entry.

DDR-006 + DDR-007 — single transition site
==========================================

DDR-006 defines the ``async_tasks`` state-channel entry shape
(:class:`AutobuildState`) and mandates that every lifecycle transition
flow through one ``_update_state(...)`` helper. DDR-007 places the
``PipelineLifecycleEmitter`` call at the **same** boundary:

.. code-block:: text

    state-channel write   ─┐
                           ├── inside _update_state(), one function call
    emitter.on_transition ─┘

If a transition writes the channel but skips the emit (or vice versa),
operators see inconsistent live progress — that is a test failure (see
``tests/forge/test_autobuild_runner.py``).

Lifecycle progression (per DDR-006 ``Literal``):

.. code-block:: text

    starting → planning_waves → running_wave → awaiting_approval
              → pushing_pr → completed | cancelled | failed

ASSUM-018 — stage-complete envelope shape
=========================================

When the runner emits ``stage_complete`` from inside the subagent, the
envelope's ``target_kind`` is ``"subagent"`` and ``target_identifier``
is the runner's own ``task_id`` (the value returned by
``start_async_task``). The supervisor's emits for stages dispatched
*outside* the subagent retain the existing taxonomy.

Worktree confinement (Group E security scenario)
================================================

Filesystem writes performed by the subagent must fall under the
build's worktree allowlist. :func:`assert_within_worktree` resolves
the candidate path and rejects anything escaping the supplied root
(symlink-aware via :meth:`Path.resolve`).

Failure-mode contract (ADR-ARCH-008, DDR-007 §Failure-mode contract)
====================================================================

If the emitter call raises (NATS publish failure, broker outage, etc.)
the runner logs at ``WARNING`` and continues. SQLite remains the
authoritative source of truth; the build is not regressed by a
transient publish hiccup.

Forward compatibility
=====================

The subagent receives the emitter as an in-process Python object via
the ``start_async_task`` context payload (DDR-007 Option A). This
relies on DeepAgents ``0.5.3`` accepting non-serialisable context
under ASGI co-deployment (per ADR-ARCH-031). The smoke test in
``tests/forge/test_autobuild_runner.py`` exercises this contract; if
DeepAgents rejects the in-process emitter, the test is the canary —
the F3 risk on FEAT-FORGE-010 is that a runtime upgrade silently
flips this contract.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol, get_args, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifecycle literal & validation set (DDR-006)
# ---------------------------------------------------------------------------


#: DDR-006 lifecycle literal. Order mirrors the canonical progression
#: ``starting → planning_waves → running_wave → awaiting_approval →
#: pushing_pr → completed | cancelled | failed``. Adding states requires
#: a DDR-006 update — the literal is the contract.
AutobuildLifecycle = Literal[
    "starting",
    "planning_waves",
    "running_wave",
    "awaiting_approval",
    "pushing_pr",
    "completed",
    "cancelled",
    "failed",
]


#: Frozen view of the lifecycle literal — used for membership checks at
#: ``_update_state`` boundary so an out-of-set string raises
#: :class:`ValueError` instead of silently writing a corrupt entry.
LIFECYCLE_VALUES: frozenset[str] = frozenset(get_args(AutobuildLifecycle))


#: Terminal lifecycle states (DDR-006). Once a state-channel entry is
#: in one of these, no further transitions are emitted from the
#: subagent. The supervisor reads the terminal state via
#: ``check_async_task`` and reconciles with SQLite on restart.
TERMINAL_LIFECYCLES: frozenset[str] = frozenset(
    {"completed", "cancelled", "failed"}
)


#: Subagent name registered with DeepAgents ``AsyncSubAgentMiddleware``.
#: Mirrors :data:`forge.pipeline.dispatchers.autobuild_async.AUTOBUILD_RUNNER_NAME`
#: — re-exported here so the runner module is self-contained.
AUTOBUILD_RUNNER_NAME: str = "autobuild_runner"


# ---------------------------------------------------------------------------
# AutobuildState — Pydantic model (DDR-006)
# ---------------------------------------------------------------------------


class AutobuildState(BaseModel):
    """Pydantic model for one ``async_tasks`` state-channel entry.

    Schema is verbatim from DDR-006. Serialised to ``dict`` when written
    to the LangGraph state channel (LangGraph channel requirement). The
    ``model_config`` uses ``extra="ignore"`` so additive evolution does
    not break older readers.

    Attributes:
        task_id: Identifier returned by ``start_async_task``.
        build_id: Build the autobuild belongs to.
        feature_id: Feature the autobuild targets.
        lifecycle: Current lifecycle string — must appear in
            :data:`LIFECYCLE_VALUES`.
        wave_index: 0-indexed current wave.
        wave_total: Total wave count for the autobuild.
        task_index: 0-indexed task within the current wave.
        task_total: Total tasks in the current wave.
        current_task_label: Reasoning-model-chosen description of the
            in-flight task (or None when between tasks).
        tasks_completed: Cumulative completed task count.
        tasks_failed: Cumulative failed task count.
        last_coach_score: Coach quality score for the most recent task,
            or None.
        aggregate_coach_score: Weighted average across completed tasks,
            or None.
        waiting_for: Set when ``lifecycle="awaiting_approval"`` (e.g.
            ``"approval:Architecture Review"``); cleared on resume.
        pending_directives: Supervisor-injected directives queued via
            ``update_async_task``.
        started_at: UTC timestamp when ``start_async_task`` minted this
            entry.
        last_activity_at: UTC timestamp of the most recent state mutation
            — refreshed on every ``_update_state`` invocation.
        estimated_completion_at: UTC ETA computed from tasks remaining
            and per-task average duration (or None).
        worktree_path: Absolute path to the build's worktree allowlist
            root. Used by :func:`assert_within_worktree` for filesystem
            confinement.
        correlation_id: Originating correlation ID threaded through the
            dispatch (FEAT-FORGE-002).
    """

    model_config = ConfigDict(extra="ignore")

    # Identity
    task_id: str
    build_id: str
    feature_id: str

    # Progress
    lifecycle: AutobuildLifecycle
    wave_index: int = 0
    wave_total: int = 0
    task_index: int = 0
    task_total: int = 0
    current_task_label: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Quality
    last_coach_score: float | None = None
    aggregate_coach_score: float | None = None

    # Approval coupling (ADR-ARCH-021)
    waiting_for: str | None = None

    # Steering
    pending_directives: list[str] = Field(default_factory=list)

    # Timing
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    estimated_completion_at: datetime | None = None

    # Confinement (Group E security scenario)
    worktree_path: str | None = None

    # Correlation (FEAT-FORGE-002)
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Protocols (the only I/O surfaces the subagent depends on)
# ---------------------------------------------------------------------------


@runtime_checkable
class SubagentEmitter(Protocol):
    """Sync structural Protocol for the DDR-007 transition publish hook.

    The subagent calls ``emitter.on_transition(new_state)`` from inside
    :func:`_update_state` at the same boundary as the state-channel
    write. The Protocol is structural (``runtime_checkable``) so any
    object exposing a sync ``on_transition(state)`` method satisfies it
    — the production wiring threads an adapter around
    :class:`forge.pipeline.PipelineLifecycleEmitter` whose async
    ``emit_*`` methods are scheduled by the daemon's running event loop.
    """

    def on_transition(self, state: AutobuildState) -> None: ...


@runtime_checkable
class StateChannelWriter(Protocol):
    """Sync Protocol for the DDR-006 ``async_tasks`` channel writer.

    Production wires the LangGraph ``AsyncSubAgentMiddleware``
    ``async_tasks`` reducer; tests inject an in-memory recording fake.
    Calls are upsert-shaped on ``(build_id, feature_id, task_id)``.
    """

    def write(self, state: AutobuildState) -> None: ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _NullStateWriter:
    """No-op writer used as the default for :func:`_update_state`.

    The ASGI co-deployed runtime threads its own writer in via the
    ``AsyncSubAgentMiddleware`` reducer; tests that want to assert
    state-channel writes inject their own recording fake. Using a real
    object (not ``None``) keeps the call site linear and avoids an
    ``if writer is None`` branch around every transition.
    """

    def __init__(self) -> None:
        self.writes: list[AutobuildState] = []

    def write(self, state: AutobuildState) -> None:
        # Record so a default-constructed runner is still introspectable
        # in tests without forcing every caller to inject a writer.
        self.writes.append(state)


# ---------------------------------------------------------------------------
# Worktree confinement helper (Group E security scenario)
# ---------------------------------------------------------------------------


class WorktreeConfinementError(ValueError):
    """Raised when a filesystem write would escape the worktree allowlist."""


def assert_within_worktree(
    path: str | os.PathLike[str],
    worktree_root: str | os.PathLike[str],
) -> Path:
    """Resolve ``path`` and verify it falls under ``worktree_root``.

    Returns the resolved absolute :class:`Path` on success; raises
    :class:`WorktreeConfinementError` otherwise. Resolution uses
    :meth:`Path.resolve` so symlinks pointing outside the worktree
    root are caught alongside literal ``../`` escapes.

    Args:
        path: Filesystem path the subagent is about to write.
        worktree_root: The build's worktree allowlist root (per
            ``forward_context.worktree_path``).

    Raises:
        WorktreeConfinementError: ``path`` resolves outside
            ``worktree_root``, or ``worktree_root`` is empty.
    """
    if not worktree_root or not os.fspath(worktree_root).strip():
        raise WorktreeConfinementError(
            "worktree_root must be a non-empty path; refusing to evaluate "
            f"confinement of {path!r}"
        )
    root = Path(os.fspath(worktree_root)).resolve()
    candidate = Path(os.fspath(path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorktreeConfinementError(
            f"path {candidate} escapes worktree allowlist {root}"
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# _update_state — co-locates the DDR-006 write and DDR-007 emit
# ---------------------------------------------------------------------------


def _update_state(
    state: AutobuildState,
    *,
    emitter: SubagentEmitter,
    lifecycle: str | None = None,
    state_writer: StateChannelWriter | None = None,
    **deltas: Any,
) -> AutobuildState:
    """Apply state mutations and fire the publish hook in one boundary.

    Co-locates the DDR-006 ``async_tasks`` channel write and the
    DDR-007 ``emitter.on_transition`` call. Either both happen or
    neither does — the function is intentionally tight so the boundary
    cannot drift between two destinations the subagent must keep
    consistent (DDR-006 §Consequences).

    Args:
        state: Current :class:`AutobuildState`.
        emitter: A :class:`SubagentEmitter` (DDR-007). The transition
            publish runs *after* the state-channel write so observers
            never see an emitted lifecycle that is missing from the
            channel.
        lifecycle: New lifecycle string. Must appear in
            :data:`LIFECYCLE_VALUES` or :class:`ValueError` is raised.
            ``None`` keeps the current lifecycle (valid for delta-only
            updates such as ``current_task_label`` bumps); the emitter
            is still notified — every state mutation is observable.
        state_writer: A :class:`StateChannelWriter` for the
            ``async_tasks`` channel. When omitted defaults to the
            local :class:`_NullStateWriter` (used by tests that only
            care about the emitter side of the boundary; production
            threads a real writer).
        **deltas: Forwarded to :meth:`AutobuildState.model_copy`'s
            ``update=`` mapping. ``last_activity_at`` is always
            refreshed so observers can tell stale entries from active
            ones.

    Returns:
        The new :class:`AutobuildState`.

    Raises:
        ValueError: ``lifecycle`` is provided but is not a member of
            :data:`LIFECYCLE_VALUES`.
    """
    if lifecycle is not None and lifecycle not in LIFECYCLE_VALUES:
        raise ValueError(
            f"_update_state: lifecycle {lifecycle!r} is not in DDR-006's "
            f"literal set; allowed values are {sorted(LIFECYCLE_VALUES)!r}"
        )

    update_map: dict[str, Any] = {
        "last_activity_at": datetime.now(timezone.utc),
        **deltas,
    }
    if lifecycle is not None:
        update_map["lifecycle"] = lifecycle

    new_state = state.model_copy(update=update_map)

    # DDR-006: write the async_tasks channel FIRST. Observers (e.g.
    # ``forge status``) reading the channel before the emit fires see a
    # consistent view; if the emit then fails (NATS down, etc.) the
    # channel still reflects the new state.
    writer = state_writer if state_writer is not None else _NullStateWriter()
    writer.write(new_state)

    # DDR-007: emit at the SAME boundary. Failures are caught and
    # logged at WARNING per DDR-007 §Failure-mode contract — SQLite
    # (and the just-written async_tasks entry) remain authoritative
    # so the build does not regress on a transient publish hiccup
    # (ADR-ARCH-008).
    try:
        emitter.on_transition(new_state)
    except Exception as exc:  # noqa: BLE001 — DDR-007 demands swallow+log
        logger.warning(
            "autobuild_runner: emitter.on_transition raised %s for "
            "task_id=%s lifecycle=%s — build continues; SQLite remains "
            "authoritative (ADR-ARCH-008, DDR-007 §Failure-mode contract)",
            exc,
            new_state.task_id,
            new_state.lifecycle,
        )

    return new_state


# ---------------------------------------------------------------------------
# Stage-complete envelope helper (ASSUM-018)
# ---------------------------------------------------------------------------


def build_stage_complete_kwargs(state: AutobuildState) -> dict[str, str]:
    """Return the ``target_kind`` / ``target_identifier`` pair (ASSUM-018).

    When the runner emits ``stage_complete`` from inside the subagent
    the envelope MUST be tagged ``target_kind="subagent"`` with
    ``target_identifier`` equal to the runner's own ``task_id``. The
    supervisor's emits (for stages dispatched *outside* the subagent)
    use the existing taxonomy unchanged.

    Args:
        state: The :class:`AutobuildState` whose ``task_id`` identifies
            this subagent instance.

    Returns:
        Mapping suitable for splat into
        :meth:`PipelineLifecycleEmitter.emit_stage_complete` keyword
        arguments.

    Raises:
        ValueError: ``state.task_id`` is empty.
    """
    if not state.task_id:
        raise ValueError(
            "build_stage_complete_kwargs: state.task_id must be non-empty "
            "(ASSUM-018: target_identifier == task_id)"
        )
    return {
        "target_kind": "subagent",
        "target_identifier": state.task_id,
    }


# ---------------------------------------------------------------------------
# Compiled graph — exported for langgraph.json
# ---------------------------------------------------------------------------


_AUTOBUILD_RUNNER_SYSTEM_PROMPT = """\
You are the **autobuild_runner** AsyncSubAgent.

You are launched by the supervisor's ``start_async_task`` and execute the
long-running autobuild for one feature plan. Drive the lifecycle through
the DDR-006 transitions:

    starting → planning_waves → running_wave → awaiting_approval
              → pushing_pr → completed | cancelled | failed

On every lifecycle change the runtime calls ``_update_state`` which
writes the ``async_tasks`` state channel AND emits to the
``PipelineLifecycleEmitter`` at the same boundary (DDR-006 + DDR-007).
A transition that writes the channel without emitting (or vice versa)
is a contract violation.

Confine all filesystem writes to the build's worktree allowlist
(``forward_context.worktree_path``). Reject paths that escape the
allowlist (Group E security scenario).

When you emit ``stage_complete`` from inside this subagent, set
``target_kind="subagent"`` and ``target_identifier`` to your own
``task_id`` (ASSUM-018).

If the emitter raises (NATS publish failure, broker outage), log at
WARNING and continue — SQLite remains authoritative (ADR-ARCH-008,
DDR-007 §Failure-mode contract).
"""


def _build_runner_graph() -> Any:
    """Compile the autobuild_runner graph for ``langgraph.json``.

    Production: builds via :func:`deepagents.create_deep_agent` so the
    addressable surface DeepAgents ``AsyncSubAgentMiddleware`` looks up
    by ``graph_id="autobuild_runner"`` is a real
    :class:`langgraph.graph.state.CompiledStateGraph`.

    Fallback: if DeepAgents is unimportable in the current environment
    (rare — only seen during partially-installed dev shells) or
    construction raises, a minimal :class:`StateGraph` is compiled and
    returned so ``langgraph.json`` parsing still succeeds. The fallback
    is a safety net, not a production path; the warning log surfaces
    the regression at startup.

    Returns:
        A compiled state graph addressable as
        ``./src/forge/subagents/autobuild_runner.py:graph``.
    """
    try:
        from deepagents import create_deep_agent
    except ImportError as exc:  # pragma: no cover - dev-only fallback
        logger.warning(
            "autobuild_runner: deepagents not importable (%s) — exporting "
            "placeholder graph; production wiring requires deepagents>=0.5.3",
            exc,
        )
        return _build_placeholder_graph()

    try:
        return create_deep_agent(
            model="anthropic:claude-haiku-4-5",
            tools=[],
            system_prompt=_AUTOBUILD_RUNNER_SYSTEM_PROMPT,
            name=AUTOBUILD_RUNNER_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - construction-time safety net
        logger.warning(
            "autobuild_runner: create_deep_agent raised %s — exporting "
            "placeholder graph so langgraph.json still parses; investigate "
            "the underlying cause before relying on the subagent",
            exc,
        )
        return _build_placeholder_graph()


def _build_placeholder_graph() -> Any:
    """Return a trivial compiled :class:`StateGraph`.

    Used only when :func:`deepagents.create_deep_agent` cannot
    construct the production graph. The graph compiles, addresses, and
    invokes (returning state unchanged) so ``langgraph.json`` parse and
    LangGraph dev-server import paths still work; production behaviour
    is delegated to the real DeepAgents-built graph.
    """
    from langgraph.graph import END, START, StateGraph

    sg: StateGraph[dict[str, Any]] = StateGraph(dict)
    sg.add_node("noop", lambda state: state)
    sg.add_edge(START, "noop")
    sg.add_edge("noop", END)
    return sg.compile()


#: Module-level compiled graph addressed by ``langgraph.json`` as
#: ``./src/forge/subagents/autobuild_runner.py:graph``. Built once at
#: import time; the LangGraph dev server resolves the ``autobuild_runner``
#: graph entry to this object.
graph = _build_runner_graph()


__all__ = [
    "AUTOBUILD_RUNNER_NAME",
    "AutobuildLifecycle",
    "AutobuildState",
    "LIFECYCLE_VALUES",
    "StateChannelWriter",
    "SubagentEmitter",
    "TERMINAL_LIFECYCLES",
    "WorktreeConfinementError",
    "_update_state",
    "assert_within_worktree",
    "build_stage_complete_kwargs",
    "graph",
]
