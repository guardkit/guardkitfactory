"""Per-feature autobuild loop sequencer (TASK-MAG7-005, FEAT-FORGE-007).

This module defines :class:`PerFeatureLoopSequencer`, the pure-function
sequencer that refuses to permit a second feature's autobuild dispatch
while any earlier feature's autobuild remains in a non-terminal lifecycle
on the same build.

Why this exists
---------------

Per FEAT-FORGE-007 ASSUM-006 ("per-feature autobuild sequencing within a
build"), Mode A v1 forbids inter-feature autobuild parallelism *within a
single build*. Each :class:`forge.adapters.sqlite.models.Build` row owns a
single ``worktree_path``; running two autobuilds in that worktree would
create branch contention because both subagents would try to push to (and
manipulate) the same git working tree.

This sequencer is the executor-layer enforcement of that invariant: even
if the supervisor's reasoning model decides to dispatch a second feature's
autobuild while the first is still running, :meth:`may_start_autobuild`
returns ``False`` and the supervisor refuses to act. The
:class:`~forge.pipeline.stage_ordering_guard.StageOrderingGuard`
(TASK-MAG7-003) already enforces that the feature's plan is approved; this
sequencer adds the additional cross-feature constraint.

What stays parallel
-------------------

Concurrent *builds* (different ``build_id`` values) are unaffected — Group
F concurrency scenarios still hold. Each build has its own worktree, so
there is no contention to sequence away.

Pure-function shape
-------------------

The sequencer touches no I/O directly. It depends only on the two reader
:class:`typing.Protocol` types declared in this module
(:class:`StageLogReader`, :class:`AsyncTaskReader`). Production wires the
SQLite adapter (FEAT-FORGE-001) for the stage_log reader and the
DeepAgents :class:`AsyncSubAgentMiddleware` ``async_tasks`` state channel
for the async task reader. Tests inject in-memory fakes — the same shape
TASK-MAG7-003 uses for its :class:`StageLogReader` Protocol.

References:
    - TASK-MAG7-005 — this task brief.
    - TASK-MAG7-001 — :class:`~forge.pipeline.stage_taxonomy.StageClass`
      and :data:`~forge.pipeline.stage_taxonomy.PER_FEATURE_STAGES`.
    - TASK-MAG7-003 — :class:`StageOrderingGuard`, the per-stage
      sibling guard.
    - TASK-MAG7-010 — supervisor reasoning loop, the consumer of this
      sequencer.
    - DDR-006 — ``AutobuildState`` Pydantic model whose ``lifecycle``
      Literal supplies the terminal / non-terminal partition.
    - FEAT-FORGE-007 ASSUM-006 — per-feature autobuild sequencing
      assumption that motivates the existence of this guard.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

__all__ = [
    "NON_TERMINAL_AUTOBUILD_LIFECYCLES",
    "TERMINAL_AUTOBUILD_LIFECYCLES",
    "AsyncTaskReader",
    "AutobuildStateLike",
    "PerFeatureLoopSequencer",
    "StageLogReader",
]


# ---------------------------------------------------------------------------
# Lifecycle partition — mirrors DDR-006 ``AutobuildState.lifecycle`` literals
# ---------------------------------------------------------------------------


#: Lifecycles that count as *in flight* — an autobuild in any of these
#: states blocks a sibling feature's autobuild dispatch on the same build.
#:
#: Verbatim from TASK-MAG7-005 acceptance criterion AC-002 and from
#: DDR-006's ``AutobuildState.lifecycle`` ``Literal`` (the five non-terminal
#: members). Stored as a :class:`frozenset` so callers cannot mutate the
#: shared partition by accident.
NON_TERMINAL_AUTOBUILD_LIFECYCLES: frozenset[str] = frozenset(
    {
        "starting",
        "planning_waves",
        "running_wave",
        "awaiting_approval",
        "pushing_pr",
    }
)


#: Lifecycles that count as *finished* — an autobuild in any of these
#: states no longer holds the worktree and therefore does not block sibling
#: dispatch. Mirrors the three terminal members of
#: ``AutobuildState.lifecycle`` from DDR-006.
TERMINAL_AUTOBUILD_LIFECYCLES: frozenset[str] = frozenset(
    {"completed", "cancelled", "failed"}
)


# ---------------------------------------------------------------------------
# Reader Protocols — the only I/O surface the sequencer is allowed
# ---------------------------------------------------------------------------


@runtime_checkable
class AutobuildStateLike(Protocol):
    """Structural shape of a DDR-006 ``AutobuildState`` entry.

    The sequencer only reads two fields, so the Protocol is intentionally
    minimal. Production wires the full ``forge.subagents.autobuild_runner.
    AutobuildState`` Pydantic model (DDR-006); tests use a dataclass or
    :class:`types.SimpleNamespace` with the same two attributes.

    Attributes:
        feature_id: The feature whose autobuild this state describes.
        lifecycle: One of the eight lifecycle string literals from
            DDR-006's ``AutobuildState.lifecycle`` field. Compared against
            :data:`NON_TERMINAL_AUTOBUILD_LIFECYCLES` to decide whether
            this autobuild is still in flight.
    """

    feature_id: str
    lifecycle: str


@runtime_checkable
class StageLogReader(Protocol):
    """Read-side Protocol over the FEAT-FORGE-001 ``stage_log`` table.

    The sequencer needs exactly one query: "is the autobuild stage for
    ``(build_id, feature_id)`` recorded as approved (terminal completion)
    in stage_log?". DDR-006 explicitly states that SQLite is the
    authoritative source of terminal state and that the ``async_tasks``
    state channel is *advisory*; this Protocol is how we read the
    authoritative side.

    Implementations may be the FEAT-FORGE-001 SQLite adapter in production
    or an in-memory fake in tests.
    """

    def is_autobuild_approved(
        self, build_id: str, feature_id: str
    ) -> bool:  # pragma: no cover - protocol stub
        """Return True iff the autobuild stage for that feature is approved.

        Args:
            build_id: The build whose stage_log to consult.
            feature_id: The feature whose autobuild row to check.

        Returns:
            ``True`` if a stage_log row exists for the autobuild stage of
            ``(build_id, feature_id)`` with terminal-approved status,
            ``False`` otherwise (no row, or row exists but not yet approved).
        """
        ...


@runtime_checkable
class AsyncTaskReader(Protocol):
    """Read-side Protocol over the LangGraph ``async_tasks`` state channel.

    Production is the DeepAgents :class:`AsyncSubAgentMiddleware`
    ``async_tasks`` channel introspected via ``list_async_tasks``; tests
    use an in-memory fake that returns synthetic
    :class:`AutobuildStateLike` entries.

    The sequencer treats the returned iterable as a snapshot — it walks
    once and does not retain a reference. Implementations may therefore
    return a generator; they do not need to return a stable list.
    """

    def list_autobuild_states(
        self, build_id: str
    ) -> Iterable[AutobuildStateLike]:  # pragma: no cover - protocol stub
        """Return all autobuild ``AsyncTask`` state entries for ``build_id``.

        Args:
            build_id: The build whose async_tasks channel to read. Other
                builds' entries are filtered out by the implementation —
                this is the cross-build isolation guarantee from
                FEAT-FORGE-007 Group F.

        Returns:
            An iterable of objects satisfying :class:`AutobuildStateLike`
            — one per autobuild AsyncTask currently registered in the
            state channel for this build, regardless of lifecycle.
        """
        ...


# ---------------------------------------------------------------------------
# The sequencer
# ---------------------------------------------------------------------------


class PerFeatureLoopSequencer:
    """Pure-function gate over per-feature autobuild dispatch.

    Consulted by the supervisor's reasoning loop (TASK-MAG7-010) just
    before it would dispatch the autobuild stage for a feature. The
    sequencer is deliberately stateless — every method takes the readers
    by injection so the same instance can be reused across builds and
    threads without ownership ambiguity.

    The single rule, verbatim from FEAT-FORGE-007 ASSUM-006: a feature's
    autobuild may not start while any *other* feature on the same build
    has an autobuild in a non-terminal lifecycle.

    Example:
        >>> sequencer = PerFeatureLoopSequencer()
        >>> sequencer.may_start_autobuild(
        ...     build_id="build-FEAT-X-20260426",
        ...     feature_id="FEAT-2",
        ...     stage_log_reader=stage_log_reader,
        ...     async_task_reader=async_task_reader,
        ... )
        False  # FEAT-1's autobuild is still ``running_wave``
    """

    def may_start_autobuild(
        self,
        build_id: str,
        feature_id: str,
        stage_log_reader: StageLogReader,
        async_task_reader: AsyncTaskReader,
    ) -> bool:
        """Return ``True`` iff dispatching ``feature_id``'s autobuild is allowed.

        Walks every :class:`AutobuildStateLike` entry the
        ``async_task_reader`` reports for ``build_id`` and short-circuits
        with ``False`` the moment a sibling feature is found in a
        non-terminal lifecycle that is not also recorded as approved in
        ``stage_log``.

        Decision matrix per sibling entry:

        +---------------------+-----------------+----------------------+
        | async_tasks         | stage_log row   | Effect on dispatch   |
        | lifecycle           | approved?       |                      |
        +=====================+=================+======================+
        | terminal            | n/a             | ignored (sibling     |
        |                     |                 | finished)            |
        +---------------------+-----------------+----------------------+
        | non-terminal        | yes             | ignored (advisory    |
        |                     |                 | state is stale —     |
        |                     |                 | DDR-006 SQLite-wins) |
        +---------------------+-----------------+----------------------+
        | non-terminal        | no              | **block dispatch**   |
        +---------------------+-----------------+----------------------+

        Entries whose ``feature_id`` equals the requested ``feature_id``
        are skipped — a feature does not block itself.

        Args:
            build_id: The build the supervisor is reasoning over.
            feature_id: The feature whose autobuild the supervisor wants
                to dispatch next. Excluded from the sibling check.
            stage_log_reader: Authoritative source for terminal completion.
                Used to override stale ``async_tasks`` entries per DDR-006.
            async_task_reader: Live ``async_tasks`` state-channel reader.
                Treated as advisory — see the decision matrix above.

        Returns:
            ``True`` iff no other feature on this build has an autobuild
            still in flight. ``False`` otherwise.
        """
        for state in async_task_reader.list_autobuild_states(build_id):
            if state.feature_id == feature_id:
                # AC: a feature does not block its own dispatch.
                continue
            if state.lifecycle in TERMINAL_AUTOBUILD_LIFECYCLES:
                # Sibling has finished; releases the worktree.
                continue
            if state.lifecycle not in NON_TERMINAL_AUTOBUILD_LIFECYCLES:
                # Unknown lifecycle string — fail closed. The
                # async_tasks channel is supposed to mirror DDR-006's
                # eight literals; an unknown value indicates a contract
                # drift that should not silently permit dispatch.
                return False
            # Non-terminal lifecycle observed. DDR-006 says SQLite is
            # authoritative — if stage_log already shows the autobuild
            # as approved, the async_tasks entry is stale and we ignore it.
            if stage_log_reader.is_autobuild_approved(
                build_id, state.feature_id
            ):
                continue
            # Sibling is genuinely in flight — refuse dispatch.
            return False
        return True
