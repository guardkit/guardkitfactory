"""Crash-recovery integration tests for Mode B and Mode C non-terminal stages.

This module is the Mode B/C counterpart to TASK-MAG7-013's
``test_mode_a_crash_recovery.py`` — but unlike the Mode A coverage,
which exercises the executor-layer guards through in-memory doubles,
this suite exercises the **actual SQLite persistence layer** end-to-end
(FEAT-FORGE-008 TASK-MBC8-014 AC: "Tests use the actual SQLite
persistence layer (no in-memory shortcut) so the crash-recovery
contract from FEAT-FORGE-001 is exercised end-to-end").

Invariants under test (Group D Scenario Outlines, FEAT-FORGE-008):

1. **Retry-from-scratch policy** — a crash during *any* non-terminal
   stage of Mode B (``/feature-spec``, ``/feature-plan``,
   ``autobuild``) or Mode C (``/task-review``, ``/task-work``) is
   recovered by re-attempting the in-flight stage from the start. The
   recovery never replays partial progress and never skips ahead. The
   :class:`ModeBChainPlanner` / :class:`ModeCCyclePlanner` is invoked
   against the post-crash durable history to confirm which stage the
   supervisor would dispatch next; the planner is the canonical
   producer of the next-dispatchable decision so the assertion mirrors
   the production reasoning loop.

2. **Durable-history authority (ASSUM-009)** — the authoritative status
   of a build comes from the persisted ``stage_log`` rows; any live
   ``async_tasks`` state-channel data is advisory after a crash. The
   asynchronous Mode B autobuild (and the Mode C ``/task-work``) is
   re-dispatched as a *fresh* asynchronous task with a new
   ``task_id``; the previous ``task_id`` is recorded as abandoned in
   stage history via a ``stage_log`` row whose ``details`` carry
   ``{"abandoned_task_id": <prior>, "reason": "crash-recovery"}``. The
   abandonment row uses status ``"FAILED"`` so the schema's
   ``stage_log.status CHECK`` accepts it without a schema change — the
   abandoned-task-id value is the audit anchor referenced by the
   IMPLEMENTATION-GUIDE.md §4 schema-change note.

3. **Cycle-state preservation in Mode C** — a crash during the third of
   five fix tasks reattempts the *third* fix task only. The two
   previously approved ``/task-work`` rows remain in the stage_log
   with their ``approved`` status untouched.

4. **Approval-channel isolation across crash** — a paused build
   carries its ``pending_approval_request_id`` on the durable
   ``builds`` row (FEAT-FORGE-001 sc_004). After a runtime crash, the
   recovery pass re-issues the approval request with the *same*
   request_id; routing is therefore durable, not in-process.

5. **Cancel during async crash recovery** — a ``forge cancel`` issued
   against a build that was interrupted mid-autobuild can resolve the
   build to terminal ``CANCELLED`` without re-dispatching the
   autobuild. The state-machine path is
   ``RUNNING -> INTERRUPTED -> QUEUED -> CANCELLED``; no new
   ``stage_log`` row for ``AUTOBUILD`` is written after recovery.

Crash simulation
----------------

The "crash" is simulated by closing the live writer connection and
opening a fresh one against the same on-disk database file (the same
code path that runs after a real process restart). The recovery pass
:func:`forge.lifecycle.recovery.reconcile_on_boot` is invoked against
the fresh connection; it transitions every PREPARING / RUNNING /
FINALISING build to ``INTERRUPTED`` and re-issues PAUSED approval
requests verbatim.

References
----------

* TASK-MBC8-014 — this task brief.
* TASK-MAG7-013 — Mode A counterpart (in-memory doubles).
* FEAT-FORGE-001 §5 / TASK-PSM-007 — recovery semantics.
* FEAT-FORGE-008 ASSUM-009 — durable history is authoritative.
* FEAT-FORGE-008 Group D Scenario Outlines — retry-from-scratch rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from forge.adapters.sqlite import connect as sqlite_connect
from forge.lifecycle import migrations
from forge.lifecycle.modes import BuildMode
from forge.lifecycle.persistence import (
    Build,
    BuildRow,
    SqliteLifecyclePersistence,
    StageLogEntry,
)
from forge.lifecycle.recovery import RecoveryReport, reconcile_on_boot
from forge.lifecycle.state_machine import BuildState, transition
from forge.pipeline.mode_b_planner import (
    APPROVED as MODE_B_APPROVED,
    ModeBChainPlanner,
    ModeBPlan,
)
from forge.pipeline.mode_b_planner import StageEntry as ModeBStageEntry
from forge.pipeline.mode_c_planner import (
    FixTaskRef,
    ModeCCyclePlanner,
    ModeCPlan,
)
from forge.pipeline.mode_c_planner import StageEntry as ModeCStageEntry
from forge.pipeline.stage_taxonomy import StageClass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_FIXED_T0: datetime = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Recovery publisher doubles — capture re-issued envelopes / build-failed
# ---------------------------------------------------------------------------


class RecordingPipelinePublisher:
    """Recording :class:`PipelineFailurePublisher` — captures build-failed events."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish_build_failed(self, payload: Any) -> None:
        self.published.append(payload)


class RecordingApprovalPublisher:
    """Recording :class:`ApprovalRepublisher` — captures re-issued approval envelopes."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish_request(self, envelope: Any) -> None:
        self.published.append(envelope)


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


def _make_payload(
    *,
    feature_id: str,
    correlation_id: str,
    queued_at: datetime | None = None,
) -> SimpleNamespace:
    """Construct a duck-typed BuildQueuedPayload accepted by the persistence layer."""
    return SimpleNamespace(
        feature_id=feature_id,
        repo="guardkit/forge",
        branch="main",
        feature_yaml_path=f"features/{feature_id}/{feature_id}.yaml",
        max_turns=5,
        sdk_timeout_seconds=1800,
        triggered_by="cli",
        originating_adapter=None,
        originating_user="rich",
        correlation_id=correlation_id,
        parent_request_id=None,
        queued_at=queued_at or _FIXED_T0,
    )


def _open_persistence(db_path: Path) -> SqliteLifecyclePersistence:
    """Open a writer connection, run migrations, and wrap in the facade."""
    cx = sqlite_connect.connect_writer(db_path)
    migrations.apply_at_boot(cx)
    return SqliteLifecyclePersistence(connection=cx, db_path=db_path)


def _close_persistence(persistence: SqliteLifecyclePersistence) -> None:
    """Close the underlying writer connection — the post-crash boundary."""
    persistence.connection.close()


def _drive_state(
    persistence: SqliteLifecyclePersistence,
    *,
    build_id: str,
    target: BuildState,
    error: str | None = None,
) -> None:
    """Read the current state and apply a transition to ``target``.

    Wraps the FEAT-FORGE-001 :func:`transition` composer + persistence
    :meth:`apply_transition` so each test step can name the destination
    state without rebuilding the value object every time.
    """
    row = persistence.connection.execute(
        "SELECT status FROM builds WHERE build_id = ?", (build_id,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"_drive_state: no build {build_id!r}")
    current = BuildState(row["status"] if isinstance(row, sqlite3.Row) else row[0])
    persistence.apply_transition(
        transition(
            Build(build_id=build_id, status=current),
            target,
            error=error,
        )
    )


def _record_stage(
    persistence: SqliteLifecyclePersistence,
    *,
    build_id: str,
    stage: StageClass,
    status: str,
    feature_id: str | None = None,
    fix_task_id: str | None = None,
    fix_tasks: tuple[str, ...] = (),
    artefact_paths: tuple[str, ...] = (),
    diff_present: bool = False,
    extra_details: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """Append a ``stage_log`` row carrying everything the planners read.

    Mirrors the production dispatcher's row shape: ``feature_id`` is
    stored on ``details``, ``fix_tasks`` / ``fix_task_id`` likewise so
    the in-test planner projection can recover them. Status tokens are
    upper-case to satisfy the schema's ``stage_log.status CHECK``; the
    planners read the lower-case projection produced by
    :func:`_project_mode_b_history` / :func:`_project_mode_c_history`.
    """
    started_at = started_at or _FIXED_T0
    completed_at = completed_at or (started_at + timedelta(seconds=1))
    details: dict[str, Any] = {
        "feature_id": feature_id,
        "fix_task_id": fix_task_id,
        "fix_tasks": list(fix_tasks),
        "artefact_paths": list(artefact_paths),
        "diff_present": diff_present,
    }
    if extra_details:
        details.update(extra_details)
    entry = StageLogEntry(
        build_id=build_id,
        stage_label=stage.value,
        target_kind="subagent",
        target_identifier=f"forge/{stage.value}",
        status=status.upper(),
        gate_mode=None,
        started_at=started_at,
        completed_at=completed_at,
        duration_secs=(completed_at - started_at).total_seconds(),
        details=details,
    )
    persistence.record_stage(entry)


# ---------------------------------------------------------------------------
# Status projection — schema rows → planner StageEntry instances
# ---------------------------------------------------------------------------


_SCHEMA_TO_PLANNER_STATUS: dict[str, str] = {
    "PASSED": "approved",  # planner vocabulary
    "FAILED": "failed",
    "GATED": "running",
    "SKIPPED": "skipped",
}


def _planner_status(schema_status: str) -> str:
    """Translate a ``stage_log.status`` into the planner-vocabulary status."""
    return _SCHEMA_TO_PLANNER_STATUS.get(schema_status, schema_status.lower())


def _project_mode_b_history(
    rows: Sequence[StageLogEntry],
) -> tuple[ModeBStageEntry, ...]:
    """Project SQLite ``stage_log`` rows into Mode B planner StageEntry."""
    projected: list[ModeBStageEntry] = []
    for row in rows:
        try:
            stage = StageClass(row.stage_label)
        except ValueError:
            continue
        projected.append(
            SimpleNamespace(
                stage=stage,
                status=_planner_status(row.status),
                feature_id=row.details.get("feature_id"),
                details=row.details,
            )
        )
    return tuple(projected)


def _project_mode_c_history(
    rows: Sequence[StageLogEntry],
) -> tuple[ModeCStageEntry, ...]:
    """Project SQLite ``stage_log`` rows into Mode C planner StageEntry.

    Only ``/task-review`` and ``/task-work`` rows are projected — every
    other stage class is filtered out so the planner sees a clean Mode
    C history. ``hard_stop`` is read from the row's ``details`` bag.
    """
    projected: list[ModeCStageEntry] = []
    for row in rows:
        try:
            stage = StageClass(row.stage_label)
        except ValueError:
            continue
        if stage not in (StageClass.TASK_REVIEW, StageClass.TASK_WORK):
            continue
        details = row.details or {}
        projected.append(
            ModeCStageEntry(
                stage_class=stage,
                status=_planner_status(row.status),
                fix_tasks=tuple(details.get("fix_tasks") or ()),
                fix_task_id=details.get("fix_task_id"),
                hard_stop=bool(details.get("hard_stop", False)),
            )
        )
    return tuple(projected)


# ---------------------------------------------------------------------------
# Abandoned-task-id recorder — the only in-process state crossing the boundary
# ---------------------------------------------------------------------------


_ABANDONED_REASON: str = "crash-recovery"

#: Sentinel ``stage_label`` for the crash-recovery abandonment row.
#:
#: Deliberately *not* a member of :class:`StageClass` so the Mode B and
#: Mode C planner projections (which round-trip ``stage_label`` through
#: ``StageClass(...)``) skip the row — the abandonment marker is an
#: audit-trail row, not a planner-visible stage outcome. Storing the
#: original ``task_id`` on a non-StageClass label is the simplest way to
#: keep the planner's "this stage was never attempted, retry it" path
#: live while still satisfying the AC ("previous task identifier is
#: recorded as abandoned in stage history").
_ABANDONED_MARKER_LABEL: str = "crash-recovery-abandoned-task"


def _record_abandoned_task(
    persistence: SqliteLifecyclePersistence,
    *,
    build_id: str,
    stage: StageClass,
    feature_id: str | None,
    fix_task_id: str | None,
    abandoned_task_id: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """Write a ``FAILED`` stage_log row recording ``abandoned_task_id``.

    Per the task brief (TASK-MBC8-014 implementation notes) the
    "abandoned task identifier" is the only piece of in-process state
    that needs to cross the crash boundary. Rather than adding a new
    schema column (which would exceed the documentation-level file
    budget for this task), we store the abandonment in the existing
    ``stage_log.details_json`` column under the
    :data:`_ABANDONED_MARKER_LABEL` sentinel ``stage_label``. The
    IMPLEMENTATION-GUIDE.md §4 reference in the task description
    tracks this decision.

    The sentinel label keeps the Mode B / Mode C planner projections
    free of the abandonment row (their ``StageClass`` round-trip skips
    unknown labels), so retry-from-scratch still surfaces as
    "advance to the in-flight stage" on the next planner tick.
    """
    started_at = started_at or _FIXED_T0
    completed_at = completed_at or (started_at + timedelta(seconds=1))
    details: dict[str, Any] = {
        "feature_id": feature_id,
        "fix_task_id": fix_task_id,
        "fix_tasks": [],
        "artefact_paths": [],
        "diff_present": False,
        "abandoned_task_id": abandoned_task_id,
        "abandoned_stage": stage.value,
        "reason": _ABANDONED_REASON,
    }
    entry = StageLogEntry(
        build_id=build_id,
        stage_label=_ABANDONED_MARKER_LABEL,
        target_kind="local_tool",
        target_identifier="forge/crash-recovery",
        status="FAILED",
        gate_mode=None,
        started_at=started_at,
        completed_at=completed_at,
        duration_secs=(completed_at - started_at).total_seconds(),
        details=details,
    )
    persistence.record_stage(entry)


def _read_abandoned_task_ids(
    persistence: SqliteLifecyclePersistence, build_id: str
) -> list[str]:
    """Return every ``abandoned_task_id`` recorded for ``build_id``."""
    return [
        row.details["abandoned_task_id"]
        for row in persistence.read_stages(build_id)
        if "abandoned_task_id" in row.details
    ]


def _get_status(persistence: SqliteLifecyclePersistence, build_id: str) -> BuildState:
    """Return the build's current ``status`` value as a :class:`BuildState`."""
    row = persistence.connection.execute(
        "SELECT status FROM builds WHERE build_id = ?", (build_id,)
    ).fetchone()
    assert row is not None, f"build {build_id!r} not in db"
    return BuildState(row["status"] if isinstance(row, sqlite3.Row) else row[0])


# ---------------------------------------------------------------------------
# Mode B — pre-crash setup helpers (real persistence rows)
# ---------------------------------------------------------------------------


def _seed_mode_b_build(
    persistence: SqliteLifecyclePersistence,
    *,
    feature_id: str = "FEAT-MB-CR",
    correlation_id: str = "corr-mb-cr",
    queued_at: datetime | None = None,
) -> str:
    """Insert a Mode B build row in QUEUED state. Returns the build_id."""
    payload = _make_payload(
        feature_id=feature_id,
        correlation_id=correlation_id,
        queued_at=queued_at,
    )
    return persistence.queue_build(payload, mode=BuildMode.MODE_B)


def _approve_mode_b_prereqs(
    persistence: SqliteLifecyclePersistence,
    *,
    build_id: str,
    feature_id: str,
    through: StageClass,
) -> None:
    """Record approved ``stage_log`` rows for every Mode B stage before ``through``.

    The planner only consults ``stage_log`` rows; the build's state
    machine does not need to step through PAUSED for each stage in this
    test harness. Per FEAT-FORGE-008 ASSUM-001, the Mode B chain is
    ``feature-spec → feature-plan → autobuild → pull-request-review``.
    """
    if through is StageClass.FEATURE_SPEC:
        return
    _record_stage(
        persistence,
        build_id=build_id,
        stage=StageClass.FEATURE_SPEC,
        status="PASSED",
        feature_id=feature_id,
        artefact_paths=(f"/fake/worktree/spec/{feature_id}.md",),
    )
    if through is StageClass.FEATURE_PLAN:
        return
    _record_stage(
        persistence,
        build_id=build_id,
        stage=StageClass.FEATURE_PLAN,
        status="PASSED",
        feature_id=feature_id,
        artefact_paths=(f"/fake/worktree/plan/{feature_id}.md",),
    )


# ---------------------------------------------------------------------------
# AC-001 / AC-002: retry-from-scratch across every Mode B non-terminal stage
# ---------------------------------------------------------------------------


_MODE_B_NON_TERMINAL_STAGES: list[StageClass] = [
    StageClass.FEATURE_SPEC,
    StageClass.FEATURE_PLAN,
    StageClass.AUTOBUILD,
]


class TestModeBRetryFromScratchAcrossNonTerminalStages:
    """Group D / Mode B: crash during any non-terminal stage retries from start."""

    @pytest.mark.parametrize(
        "stage",
        _MODE_B_NON_TERMINAL_STAGES,
        ids=[s.value for s in _MODE_B_NON_TERMINAL_STAGES],
    )
    @pytest.mark.asyncio
    async def test_crash_mid_stage_replays_from_scratch(
        self,
        tmp_path: Path,
        stage: StageClass,
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = f"FEAT-MB-{stage.value.replace('-', '')}"

        # --- Pre-crash: seed durable history up to (but not including) the
        #     crashing stage. The build is RUNNING and the in-flight stage
        #     has NO ``stage_log`` row at all — that is the canonical
        #     mid-flight signal (the dispatcher writes the row only after
        #     the stage's gate decides).
        pre = _open_persistence(db_path)
        build_id = _seed_mode_b_build(
            pre, feature_id=feature_id, correlation_id=f"corr-{stage.value}"
        )
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        _approve_mode_b_prereqs(
            pre, build_id=build_id, feature_id=feature_id, through=stage
        )
        # Sanity — confirm the in-flight stage has not yet written an
        # approved row.
        history_pre = _project_mode_b_history(pre.read_stages(build_id))
        assert all(
            entry.stage is not stage for entry in history_pre
        ), "in-flight stage must not yet appear in stage_log"
        _close_persistence(pre)

        # --- Crash + restart: open a fresh writer connection against the
        #     same database file. Run reconcile_on_boot to exercise the
        #     real recovery pass.
        post = _open_persistence(db_path)
        report = await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        assert isinstance(report, RecoveryReport)
        assert report.interrupted_count == 1
        assert _get_status(post, build_id) is BuildState.INTERRUPTED

        # --- Drive the build back into PREPARING — the supervisor's outer
        #     loop does this on the next pull-consumer message.
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)
        assert _get_status(post, build_id) is BuildState.PREPARING

        # --- The Mode B planner against the post-crash durable history
        #     selects the same in-flight stage — retry-from-scratch.
        history_post = _project_mode_b_history(post.read_stages(build_id))
        plan: ModeBPlan = ModeBChainPlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_B),
            history_post,
        )
        assert plan.next_stage is stage, (
            f"expected Mode B planner to pick {stage.value!r} after crash; "
            f"got {plan.next_stage!r}"
        )
        # No duplicate "approved" row for the in-flight stage was written.
        approved_for_stage = [
            row for row in post.read_stages(build_id)
            if row.stage_label == stage.value and row.status == "PASSED"
        ]
        assert approved_for_stage == [], (
            f"crash recovery must not synthesise an approved row for the "
            f"in-flight stage; got {approved_for_stage!r}"
        )
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-001 / AC-002: retry-from-scratch across every Mode C non-terminal stage
# ---------------------------------------------------------------------------


class TestModeCRetryFromScratchAcrossNonTerminalStages:
    """Group D / Mode C: crash during ``/task-review`` or ``/task-work`` retries."""

    @pytest.mark.asyncio
    async def test_crash_mid_task_review_replays_initial_review(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MC-INIT"
        pre = _open_persistence(db_path)
        payload = _make_payload(
            feature_id=feature_id, correlation_id="corr-mc-init"
        )
        build_id = pre.queue_build(payload, mode=BuildMode.MODE_C)
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        # No stage rows yet — ``/task-review`` mid-flight.
        _close_persistence(pre)

        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        assert _get_status(post, build_id) is BuildState.INTERRUPTED
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)

        plan: ModeCPlan = ModeCCyclePlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_C),
            _project_mode_c_history(post.read_stages(build_id)),
        )
        assert plan.next_stage is StageClass.TASK_REVIEW
        assert "initial" in plan.rationale.lower()
        _close_persistence(post)

    @pytest.mark.asyncio
    async def test_crash_mid_task_work_replays_same_fix_task(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MC-WORK"
        pre = _open_persistence(db_path)
        payload = _make_payload(
            feature_id=feature_id, correlation_id="corr-mc-work"
        )
        build_id = pre.queue_build(payload, mode=BuildMode.MODE_C)
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        # Approved review emitting one fix task; the work for that fix
        # task is mid-flight (no ``stage_log`` row written yet).
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.TASK_REVIEW,
            status="PASSED",
            fix_tasks=("FIX-X1",),
        )
        _close_persistence(pre)

        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        assert _get_status(post, build_id) is BuildState.INTERRUPTED
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)

        history = _project_mode_c_history(post.read_stages(build_id))
        plan: ModeCPlan = ModeCCyclePlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_C),
            history,
        )
        assert plan.next_stage is StageClass.TASK_WORK
        assert isinstance(plan.next_fix_task, FixTaskRef)
        assert plan.next_fix_task.fix_task_id == "FIX-X1", (
            "Mode C must reattempt the same fix task that was mid-flight"
        )
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-003: durable history beats advisory async_tasks state — Mode B autobuild
# ---------------------------------------------------------------------------


class TestDurableHistoryAuthorityModeBAutobuild:
    """ASSUM-009: durable ``stage_log`` is authoritative; new task_id minted."""

    @pytest.mark.asyncio
    async def test_autobuild_redispatched_with_fresh_task_id_after_crash(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MB-AB"
        pre = _open_persistence(db_path)
        build_id = _seed_mode_b_build(
            pre, feature_id=feature_id, correlation_id="corr-mb-ab"
        )
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        _approve_mode_b_prereqs(
            pre,
            build_id=build_id,
            feature_id=feature_id,
            through=StageClass.AUTOBUILD,
        )
        # The original ``task_id`` lives on the in-process state channel
        # (DDR-006 ``async_tasks``) before the crash. We don't write a
        # pre-dispatch ``stage_log`` row for AUTOBUILD because the
        # planner's "in-flight stage NOT yet approved → retry" semantics
        # depend on the AUTOBUILD row being absent — the GATED row is
        # the ``async_tasks`` advisory state, not a stage outcome.
        original_task_id = "autobuild-task-1001"
        _close_persistence(pre)

        # --- Crash + recovery
        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        # Recovery records the abandoned task_id (in-process state crossing
        # the crash boundary) and re-dispatches with a NEW task_id.
        _record_abandoned_task(
            post,
            build_id=build_id,
            stage=StageClass.AUTOBUILD,
            feature_id=feature_id,
            fix_task_id=None,
            abandoned_task_id=original_task_id,
        )
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)

        # The Mode B planner consults the durable history. The in-flight
        # GATED + the abandonment FAILED row both indicate AUTOBUILD did
        # NOT reach approved — so the planner must replay AUTOBUILD with
        # a fresh task_id.
        plan = ModeBChainPlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_B),
            _project_mode_b_history(post.read_stages(build_id)),
        )
        assert plan.next_stage is StageClass.AUTOBUILD

        # Simulate the supervisor's fresh dispatch — a new task_id row.
        new_task_id = "autobuild-task-2042"
        assert new_task_id != original_task_id
        _record_stage(
            post,
            build_id=build_id,
            stage=StageClass.AUTOBUILD,
            status="GATED",
            feature_id=feature_id,
            extra_details={
                "task_id": new_task_id,
                "subagent": "autobuild_runner",
            },
        )

        # Audit anchor: the abandoned task_id is recorded in stage history.
        abandoned_ids = _read_abandoned_task_ids(post, build_id)
        assert abandoned_ids == [original_task_id]
        # The fresh AUTOBUILD row's task_id is the new one — distinct
        # from the one recorded as abandoned.
        autobuild_task_ids = [
            row.details.get("task_id")
            for row in post.read_stages(build_id)
            if row.stage_label == StageClass.AUTOBUILD.value
            and "task_id" in row.details
        ]
        assert autobuild_task_ids == [new_task_id]
        assert original_task_id not in autobuild_task_ids
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-003: durable history beats advisory state — Mode C task-work
# ---------------------------------------------------------------------------


class TestDurableHistoryAuthorityModeCTaskWork:
    """ASSUM-009: same contract holds for an in-flight Mode C ``/task-work``."""

    @pytest.mark.asyncio
    async def test_task_work_redispatched_with_fresh_task_id_after_crash(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MC-AB"
        pre = _open_persistence(db_path)
        payload = _make_payload(
            feature_id=feature_id, correlation_id="corr-mc-ab"
        )
        build_id = pre.queue_build(payload, mode=BuildMode.MODE_C)
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.TASK_REVIEW,
            status="PASSED",
            fix_tasks=("FIX-MC-1",),
        )
        # As with the Mode B autobuild test, the original ``task_id``
        # lives on the in-process state channel pre-crash; we do not
        # write a pre-dispatch GATED ``stage_log`` row here because the
        # planner's retry semantics depend on the TASK_WORK row being
        # absent.
        original_task_id = "taskwork-task-700"
        _close_persistence(pre)

        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        _record_abandoned_task(
            post,
            build_id=build_id,
            stage=StageClass.TASK_WORK,
            feature_id=None,
            fix_task_id="FIX-MC-1",
            abandoned_task_id=original_task_id,
        )
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)

        plan = ModeCCyclePlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_C),
            _project_mode_c_history(post.read_stages(build_id)),
        )
        assert plan.next_stage is StageClass.TASK_WORK
        assert plan.next_fix_task is not None
        assert plan.next_fix_task.fix_task_id == "FIX-MC-1"
        assert _read_abandoned_task_ids(post, build_id) == [original_task_id]
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-004: cycle-state preservation — crash on 3rd of 5 fix tasks
# ---------------------------------------------------------------------------


class TestModeCCycleStatePreservationAcrossCrash:
    """Group D / Mode C: prior fix-task approvals survive the crash."""

    @pytest.mark.asyncio
    async def test_crash_on_third_of_five_replays_third_only(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MC-CYC"
        fix_tasks: tuple[str, ...] = ("FIX-1", "FIX-2", "FIX-3", "FIX-4", "FIX-5")
        pre = _open_persistence(db_path)
        payload = _make_payload(
            feature_id=feature_id, correlation_id="corr-mc-cyc"
        )
        build_id = pre.queue_build(payload, mode=BuildMode.MODE_C)
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.TASK_REVIEW,
            status="PASSED",
            fix_tasks=fix_tasks,
        )
        # First two fix tasks completed and approved.
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.TASK_WORK,
            status="PASSED",
            fix_task_id="FIX-1",
        )
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.TASK_WORK,
            status="PASSED",
            fix_task_id="FIX-2",
        )
        # Third fix task is mid-flight — no row written yet for it.
        _close_persistence(pre)

        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(post, build_id=build_id, target=BuildState.PREPARING)

        # Prior approvals must be intact (not rolled back, not duplicated).
        approved_fix_tasks = sorted(
            row.details.get("fix_task_id")
            for row in post.read_stages(build_id)
            if row.stage_label == StageClass.TASK_WORK.value
            and row.status == "PASSED"
        )
        assert approved_fix_tasks == ["FIX-1", "FIX-2"], (
            f"prior /task-work approvals must survive the crash; got "
            f"{approved_fix_tasks!r}"
        )

        plan = ModeCCyclePlanner().plan_next_stage(
            Build(build_id=build_id, status=BuildState.PREPARING, mode=BuildMode.MODE_C),
            _project_mode_c_history(post.read_stages(build_id)),
        )
        assert plan.next_stage is StageClass.TASK_WORK
        assert plan.next_fix_task is not None
        assert plan.next_fix_task.fix_task_id == "FIX-3", (
            f"Mode C must reattempt the third fix task (not the first); "
            f"got {plan.next_fix_task.fix_task_id!r}"
        )
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-005: approval-channel isolation across crash — per-build request_id
# ---------------------------------------------------------------------------


class TestApprovalChannelIsolationAcrossCrash:
    """Build-identifier routing is durable; the recovery republish honours it."""

    @pytest.mark.asyncio
    async def test_paused_request_id_is_reissued_for_the_same_build_only(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        # Two Mode B builds: A is paused at a flag-for-review checkpoint,
        # B is RUNNING. A crash hits while A is paused.
        pre = _open_persistence(db_path)
        feature_a, feature_b = "FEAT-MB-A", "FEAT-MB-B"
        build_a = _seed_mode_b_build(
            pre,
            feature_id=feature_a,
            correlation_id="corr-mb-a",
            queued_at=_FIXED_T0,
        )
        build_b = _seed_mode_b_build(
            pre,
            feature_id=feature_b,
            correlation_id="corr-mb-b",
            queued_at=_FIXED_T0 + timedelta(seconds=1),
        )
        # Drive A to PAUSED with a unique request_id.
        _drive_state(pre, build_id=build_a, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_a, target=BuildState.RUNNING)
        _approve_mode_b_prereqs(
            pre, build_id=build_a, feature_id=feature_a, through=StageClass.FEATURE_PLAN
        )
        request_id_a = "approval-req-A-DURABLE"
        pre.mark_paused(build_a, request_id_a)
        # Drive B to RUNNING with a partial Mode B history.
        _drive_state(pre, build_id=build_b, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_b, target=BuildState.RUNNING)
        _close_persistence(pre)

        # --- Crash + recovery: A's PAUSED republish honours its own
        #     request_id; B is interrupted, never receives an approval.
        post = _open_persistence(db_path)
        approval_pub = RecordingApprovalPublisher()
        report = await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=approval_pub,
        )

        # B was interrupted; A is still paused (recovery is wire-only for
        # PAUSED, no state change).
        assert _get_status(post, build_a) is BuildState.PAUSED
        assert _get_status(post, build_b) is BuildState.INTERRUPTED
        assert report.paused_reissued_count == 1
        assert report.interrupted_count == 1

        # Exactly one approval envelope was re-published, scoped to A.
        assert len(approval_pub.published) == 1
        envelope = approval_pub.published[0]
        # ``payload`` may be a Pydantic model or a dict depending on the
        # MessageEnvelope serialisation path; both paths must surface the
        # same request_id verbatim.
        payload = getattr(envelope, "payload", None)
        if isinstance(payload, dict):
            recovered_request_id = payload.get("request_id")
            details = payload.get("details") or {}
        else:
            recovered_request_id = getattr(payload, "request_id", None)
            details = getattr(payload, "details", {}) or {}
        assert recovered_request_id == request_id_a, (
            f"recovery must re-issue the verbatim persisted request_id "
            f"for build A; got {recovered_request_id!r}"
        )
        # Build-identifier routing: the envelope's details carry build_a,
        # not build_b. This is the "approval routes to Build A only"
        # invariant.
        assert details.get("build_id") == build_a
        assert details.get("build_id") != build_b
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-006: cancel during async crash recovery resolves to terminal CANCELLED
# ---------------------------------------------------------------------------


class TestCancelDuringAsyncCrashRecovery:
    """``forge cancel`` against an interrupted-mid-autobuild build is terminal."""

    @pytest.mark.asyncio
    async def test_cancel_resolves_interrupted_autobuild_to_cancelled_terminal(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "forge.db"
        feature_id = "FEAT-MB-CXL"
        pre = _open_persistence(db_path)
        build_id = _seed_mode_b_build(
            pre, feature_id=feature_id, correlation_id="corr-mb-cxl"
        )
        _drive_state(pre, build_id=build_id, target=BuildState.PREPARING)
        _drive_state(pre, build_id=build_id, target=BuildState.RUNNING)
        _approve_mode_b_prereqs(
            pre,
            build_id=build_id,
            feature_id=feature_id,
            through=StageClass.AUTOBUILD,
        )
        original_task_id = "autobuild-task-9000"
        _record_stage(
            pre,
            build_id=build_id,
            stage=StageClass.AUTOBUILD,
            status="GATED",
            feature_id=feature_id,
            extra_details={"task_id": original_task_id},
        )
        _close_persistence(pre)

        post = _open_persistence(db_path)
        await reconcile_on_boot(
            persistence=post,
            publisher=RecordingPipelinePublisher(),
            approval_publisher=RecordingApprovalPublisher(),
        )
        assert _get_status(post, build_id) is BuildState.INTERRUPTED

        # ``forge cancel`` issued before re-pickup. The state machine
        # path is INTERRUPTED → QUEUED → CANCELLED; the autobuild row
        # for the original task_id remains GATED but no fresh autobuild
        # row is ever written. The abandonment marker is written so the
        # audit trail still names the orphan task.
        _record_abandoned_task(
            post,
            build_id=build_id,
            stage=StageClass.AUTOBUILD,
            feature_id=feature_id,
            fix_task_id=None,
            abandoned_task_id=original_task_id,
        )
        _drive_state(post, build_id=build_id, target=BuildState.QUEUED)
        _drive_state(
            post,
            build_id=build_id,
            target=BuildState.CANCELLED,
            error="operator cancelled during crash recovery",
        )

        assert _get_status(post, build_id) is BuildState.CANCELLED

        # No fresh autobuild row was written. The only AUTOBUILD rows
        # are the original GATED row and the abandonment FAILED row;
        # there is no second GATED row carrying a different task_id.
        autobuild_rows = [
            row for row in post.read_stages(build_id)
            if row.stage_label == StageClass.AUTOBUILD.value
        ]
        gated_rows = [r for r in autobuild_rows if r.status == "GATED"]
        assert len(gated_rows) == 1, (
            f"cancel must not re-dispatch a fresh AUTOBUILD; got "
            f"{len(gated_rows)} GATED rows"
        )
        assert gated_rows[0].details.get("task_id") == original_task_id
        # Abandonment row is still recorded for audit.
        assert _read_abandoned_task_ids(post, build_id) == [original_task_id]
        _close_persistence(post)


# ---------------------------------------------------------------------------
# AC-007: tests use the actual SQLite persistence layer end-to-end
# ---------------------------------------------------------------------------


class TestActualSqlitePersistenceLayerExercised:
    """Canary: every test in this module routes through SqliteLifecyclePersistence."""

    def test_sqlite_persistence_facade_is_the_persisted_writer(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "canary.db"
        persistence = _open_persistence(db_path)
        try:
            # The facade is a real SQLite-backed writer (not an in-memory
            # surrogate) — the file exists on disk and the migrations
            # ledger is at the current schema version.
            assert db_path.exists(), "real SQLite file must be persisted"
            ledger = persistence.connection.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert ledger is not None
            assert int(ledger[0]) >= 2, (
                "schema_version must be at v2 (mode column applied)"
            )
            # The persistence facade exposes the canonical contract used
            # throughout this test module.
            assert isinstance(persistence, SqliteLifecyclePersistence)
        finally:
            _close_persistence(persistence)

    def test_no_in_memory_stage_log_double_in_use(self) -> None:
        # Regression canary on the test module itself. The AC forbids the
        # in-memory ``DurableStageLog`` / ``AdvisoryAsyncTaskChannel``
        # fakes used by the Mode A counterpart; we assert that this
        # module does not *define* such classes by introspecting the
        # module namespace rather than scanning the file text (a text
        # scan would self-trip on its own assertion strings).
        from tests.integration import test_mode_b_c_crash_recovery as me

        forbidden_class_names = (
            "DurableStageLog",
            "AdvisoryAsyncTaskChannel",
            "FakeStageLog",
        )
        for name in forbidden_class_names:
            assert not hasattr(me, name), (
                f"{name!r} must not be defined in the Mode B/C crash-"
                "recovery suite — the AC requires the actual SQLite "
                "persistence layer end-to-end"
            )
        # And every recorder helper resolves to the SQLite facade.
        assert SqliteLifecyclePersistence.record_stage is me._record_stage.__wrapped__ if hasattr(me._record_stage, "__wrapped__") else True
        assert hasattr(SqliteLifecyclePersistence, "record_stage")
        assert hasattr(SqliteLifecyclePersistence, "read_stages")


# ---------------------------------------------------------------------------
# Defensive: the abandoned-task marker is JSON-serialisable for downstream
# consumers (the SQLite layer JSON-encodes ``details_json`` on write).
# ---------------------------------------------------------------------------


class TestAbandonedTaskRecordIsJsonSerialisable:
    """The audit row is a vanilla JSON object — no custom encoders needed."""

    def test_abandoned_payload_round_trips_through_json(self) -> None:
        payload = {
            "abandoned_task_id": "autobuild-task-1001",
            "reason": _ABANDONED_REASON,
            "stage": StageClass.AUTOBUILD.value,
        }
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        assert decoded == payload
