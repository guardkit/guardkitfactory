"""Production binding for ``StageLogRecorder`` (TASK-FW10-004).

This module is one of the four production wirings for
:func:`forge.pipeline.dispatchers.autobuild_async.dispatch_autobuild_async`.
It returns a :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`
Protocol implementation that delegates to the FEAT-FORGE-001 SQLite
writer (:meth:`forge.lifecycle.persistence.SqliteLifecyclePersistence.record_stage`).

Design rules
------------

* **Protocol surface only.** :class:`_AutobuildStageLogRecorder` exposes
  exactly the single method declared on
  :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`
  (``record_running``). The persistence facade carries far more API
  than the dispatcher needs; this adapter narrows the surface so the
  dispatcher cannot accidentally reach into the wider lifecycle write
  path.
* **No second pool.** The factory accepts the same persistence facade
  the rest of FEAT-FORGE-010 wires (the "sqlite_pool" in
  ``IMPLEMENTATION-GUIDE.md`` §5). Writes route through the existing
  connection-scoped ``BEGIN IMMEDIATE`` session pattern in
  :mod:`forge.lifecycle.persistence`. We do not open a new SQLite
  connection here.
* **Mapping → :class:`StageLogEntry`.** The dispatcher's Protocol
  passes the dispatch metadata as ``details_json`` (a
  :class:`~typing.Mapping`); :meth:`record_stage` requires a
  :class:`~forge.lifecycle.persistence.StageLogEntry` Pydantic value
  object. This adapter is the only place that translation happens —
  ``target_kind="subagent"``, ``target_identifier=feature_id`` (the
  most-identifying field for an autobuild row at dispatch time, since
  the ``task_id`` may be ``None`` on the pre-dispatch call), and
  ``status=AUTOBUILD_RUNNING_STATUS`` (a schema-valid status — see the
  constant's docstring). The ``details`` payload preserves every key
  the dispatcher passed plus a ``feature_id`` echo and a ``state``
  marker (``"running"``) so a reader on the same pool can reconstruct
  the dispatch shape without joining against the ``builds`` table and
  can distinguish a dispatch-attempt row from a true terminal-pass
  row.

References:
    - TASK-FW10-004 — this task brief.
    - :mod:`forge.pipeline.dispatchers.autobuild_async` — the
      :class:`StageLogRecorder` Protocol surface.
    - :mod:`forge.lifecycle.persistence` — the
      :class:`SqliteLifecyclePersistence` facade and
      :class:`StageLogEntry` value object.
    - ``IMPLEMENTATION-GUIDE.md`` §4 contract: ``StageLogRecorder``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

from forge.lifecycle.persistence import StageLogEntry
from forge.pipeline.dispatchers.autobuild_async import StageLogRecorder
from forge.pipeline.stage_taxonomy import StageClass

logger = logging.getLogger(__name__)


__all__ = [
    "AUTOBUILD_LIFECYCLE_STATE_KEY",
    "AUTOBUILD_LIFECYCLE_STATE_VALUE",
    "AUTOBUILD_RUNNING_STATUS",
    "AUTOBUILD_TARGET_KIND",
    "build_stage_log_recorder",
]


#: ``stage_log.target_kind`` value for an autobuild dispatch row.
#:
#: The dispatcher launches a long-running ``AsyncSubAgent``
#: (``autobuild_runner``); the row's natural target is the subagent the
#: dispatcher handed control to. Mirrors the convention used by
#: :class:`forge.lifecycle.persistence.SqliteStageSkipRecorder` (which
#: writes ``target_kind="local_tool"`` for skip rows) — the column
#: encodes *what kind of thing* received the work, not the build itself.
AUTOBUILD_TARGET_KIND: str = "subagent"

#: ``stage_log.status`` value written by :meth:`record_running`.
#:
#: The :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`
#: Protocol's docstring describes the row as carrying
#: ``state="running"``, but the FEAT-FORGE-001 ``stage_log.status``
#: column is constrained by a SQLite ``CHECK`` to one of
#: ``{'PASSED', 'FAILED', 'GATED', 'SKIPPED'}`` — there is no
#: ``RUNNING`` status in the schema. The dispatch action (writing a
#: durable record that a dispatch was attempted) is itself a passed
#: action: the dispatcher successfully recorded its intent. We
#: therefore write ``status="PASSED"`` to satisfy the schema and put
#: the lifecycle marker (``"running"``) on
#: :data:`AUTOBUILD_LIFECYCLE_STATE_KEY` in ``details_json`` so a
#: reader can distinguish a dispatch-attempt row from a stage's
#: terminal pass.
AUTOBUILD_RUNNING_STATUS: str = "PASSED"

#: Key on the ``details_json`` payload that carries the lifecycle
#: state. ``"running"`` for the dispatch-attempt rows the autobuild
#: dispatcher writes; downstream consumers should treat the absence of
#: this key as "not a dispatch row" and interpret ``status`` directly.
AUTOBUILD_LIFECYCLE_STATE_KEY: str = "lifecycle_state"

#: The :data:`AUTOBUILD_LIFECYCLE_STATE_KEY` value written by
#: :meth:`record_running`. Mirrors DDR-006's
#: :class:`AutobuildState.lifecycle` ``"starting"`` literal in spirit,
#: but lives on the ``stage_log`` side rather than the ``async_tasks``
#: channel — the two writes are paired by the dispatcher (see
#: ``dispatch_autobuild_async`` invariant 3).
AUTOBUILD_LIFECYCLE_STATE_VALUE: str = "running"


class _StageLogWriter(Protocol):
    """Duck-typed slice of :class:`SqliteLifecyclePersistence` we need.

    The factory accepts any object exposing :meth:`record_stage`. In
    production the caller passes the full
    :class:`~forge.lifecycle.persistence.SqliteLifecyclePersistence`
    facade (the daemon's "sqlite_pool"); tests can pass an in-memory
    persistence built around an in-memory SQLite database without any
    further wrapping. Keeping this Protocol private to the module
    (``_StageLogWriter``) signals the duck-typed dependency without
    leaking it into the package's public surface.
    """

    def record_stage(self, entry: StageLogEntry) -> None:  # pragma: no cover - protocol stub
        """Append the ``stage_log`` row described by ``entry``."""
        ...


class _AutobuildStageLogRecorder:
    """:class:`StageLogRecorder` adapter that writes via the SQLite facade.

    The class is module-private (leading underscore) — callers should
    construct instances via :func:`build_stage_log_recorder`. The
    factory is the single documented entry point so the wiring stays
    discoverable from ``IMPLEMENTATION-GUIDE.md`` §4 without exposing
    the adapter type to inspection or subclassing.

    Args:
        persistence: The lifecycle persistence facade. Used solely as a
            :class:`_StageLogWriter` (only :meth:`record_stage` is
            invoked); the wider read/write API is intentionally not
            referenced from this adapter.
        clock: Optional zero-arg callable returning a timezone-aware
            :class:`~datetime.datetime`. Defaults to
            ``datetime.now(UTC)``. Tests can inject a deterministic
            clock to assert ``started_at`` / ``completed_at`` values.
    """

    __slots__ = ("_persistence", "_clock")

    def __init__(
        self,
        persistence: _StageLogWriter,
        *,
        clock: "Any" = None,
    ) -> None:
        self._persistence = persistence
        # Default clock returns UTC ``now`` per FEAT-FORGE-001 convention
        # (every timestamp on the stage_log table is UTC).
        self._clock = clock if clock is not None else _utc_now

    def record_running(
        self,
        build_id: str,
        feature_id: str,
        stage: StageClass,
        details_json: Mapping[str, Any],
    ) -> None:
        """Write a ``status="running"`` row to ``stage_log``.

        Mirrors the
        :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`
        Protocol exactly — same argument names, same types, same
        ordering. The body translates the Protocol's ``Mapping``
        payload into a :class:`StageLogEntry` and forwards it to the
        SQLite writer.

        Validation is fail-fast: empty ``build_id`` / ``feature_id``
        raise :class:`ValueError` so a misconfigured caller surfaces a
        clear error rather than writing a row keyed on an empty string.
        :class:`StageLogEntry`'s Pydantic ``min_length=1`` constraint
        on ``build_id`` would catch ``build_id=""`` anyway, but we add
        the explicit guard so the error message names the offending
        argument.

        Args:
            build_id: Build the row is scoped to. Non-empty.
            feature_id: Feature the row is attributed to. Non-empty;
                stored in both ``target_identifier`` and ``details`` so
                a downstream reader can filter by feature without
                joining ``stage_log`` against ``builds``.
            stage: Stage classification. The dispatcher always passes
                :attr:`StageClass.AUTOBUILD`; the recorder accepts any
                :class:`StageClass` so the surface remains general
                (the Protocol declaration does not pin the value).
            details_json: JSON-serialisable mapping persisted onto the
                row's ``details_json`` column. The dispatcher threads
                ``correlation_id`` and the resolved context entries
                through this mapping (and ``task_id`` once
                ``start_async_task`` returns). The adapter copies the
                mapping into a ``dict`` before adding the
                ``feature_id`` echo so the caller's mapping object is
                never mutated.
        """
        if not build_id:
            raise ValueError(
                "_AutobuildStageLogRecorder.record_running: build_id must "
                "be a non-empty string"
            )
        if not feature_id:
            raise ValueError(
                "_AutobuildStageLogRecorder.record_running: feature_id "
                "must be a non-empty string"
            )
        if not isinstance(stage, StageClass):
            raise TypeError(
                "_AutobuildStageLogRecorder.record_running: stage must be a "
                f"StageClass; got {type(stage).__name__}"
            )

        # Copy the mapping into a fresh dict so we never mutate the
        # caller's payload. The dispatcher reuses its ``details`` dict
        # across the pre/post-dispatch calls; mutating it here would
        # bleed cross-call state through the recorder.
        details: dict[str, Any] = dict(details_json)
        # Echo feature_id into details so a stage_log reader filtering
        # on ``details_json`` can identify the feature without a
        # separate column. Use ``setdefault`` so a caller that already
        # threaded feature_id through ``details_json`` wins (the
        # caller's value is the authoritative one).
        details.setdefault("feature_id", feature_id)
        # Stamp the dispatcher's intended ``state="running"`` marker
        # onto ``details``: the schema-allowed ``status`` column does
        # not have a "running" value, so the lifecycle marker lives
        # here. Use ``setdefault`` so an explicit caller-provided
        # marker (e.g. a test seam) wins.
        details.setdefault(
            AUTOBUILD_LIFECYCLE_STATE_KEY, AUTOBUILD_LIFECYCLE_STATE_VALUE
        )

        now: datetime = self._clock()
        entry = StageLogEntry(
            build_id=build_id,
            stage_label=stage.value,
            target_kind=AUTOBUILD_TARGET_KIND,
            target_identifier=feature_id,
            status=AUTOBUILD_RUNNING_STATUS,
            gate_mode=None,
            coach_score=None,
            threshold_applied=None,
            started_at=now,
            completed_at=now,
            duration_secs=0.0,
            details=details,
        )
        self._persistence.record_stage(entry)
        logger.debug(
            "stage_log_recorder: wrote running row build_id=%s "
            "feature_id=%s stage=%s",
            build_id,
            feature_id,
            stage.value,
        )


def _utc_now() -> datetime:
    """Return the current UTC time as an aware :class:`datetime`.

    Pulled out of :class:`_AutobuildStageLogRecorder` so tests can
    inject an alternate clock without subclassing the adapter — the
    factory's default is the only production caller of this helper.
    """
    return datetime.now(UTC)


def build_stage_log_recorder(sqlite_pool: _StageLogWriter) -> StageLogRecorder:
    """Build the production :class:`StageLogRecorder` for autobuild dispatch.

    The factory is the single documented entry point for wiring the
    :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`
    collaborator on
    :func:`~forge.pipeline.dispatchers.autobuild_async.dispatch_autobuild_async`.
    Composition (TASK-FW10-007) calls this function with the daemon's
    shared :class:`~forge.lifecycle.persistence.SqliteLifecyclePersistence`
    facade; tests can call it with any object exposing
    :meth:`record_stage`.

    The returned object satisfies
    :class:`~forge.pipeline.dispatchers.autobuild_async.StageLogRecorder`'s
    ``runtime_checkable`` Protocol — callers that need a structural
    type check can :func:`isinstance` against the Protocol directly.

    Args:
        sqlite_pool: Object exposing
            :meth:`record_stage(entry: StageLogEntry) -> None`. In
            production this is the daemon's
            :class:`SqliteLifecyclePersistence` facade.

    Returns:
        A :class:`StageLogRecorder` Protocol implementation that
        delegates :meth:`record_running` to ``sqlite_pool.record_stage``.

    Raises:
        TypeError: If ``sqlite_pool`` does not expose a callable
            ``record_stage`` attribute. The check is duck-typed
            (``callable(getattr(...))``) so it does not pin the
            argument to :class:`SqliteLifecyclePersistence` — that
            would defeat the test seam.

    Example:
        >>> from forge.lifecycle.persistence import SqliteLifecyclePersistence
        >>> persistence = SqliteLifecyclePersistence(connection=cx)
        >>> recorder = build_stage_log_recorder(persistence)
        >>> from forge.pipeline.stage_taxonomy import StageClass
        >>> recorder.record_running(
        ...     build_id="build-1",
        ...     feature_id="FEAT-X",
        ...     stage=StageClass.AUTOBUILD,
        ...     details_json={"correlation_id": "corr-1", "task_id": None},
        ... )
    """
    record_stage = getattr(sqlite_pool, "record_stage", None)
    if not callable(record_stage):
        raise TypeError(
            "build_stage_log_recorder: sqlite_pool must expose a callable "
            "record_stage(entry: StageLogEntry) -> None method; got "
            f"{type(sqlite_pool).__name__}"
        )
    return _AutobuildStageLogRecorder(sqlite_pool)
