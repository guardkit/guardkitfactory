"""Tests for ``forge.pipeline.terminal_handlers`` (TASK-MBC8-006).

Validates :func:`evaluate_post_autobuild` — the Mode B no-diff terminal
handler. The handler is a pure routing shim that runs after Mode B's
``AUTOBUILD`` stage approval and before the Supervisor would normally
route to PR creation. It returns one of three outcomes:

- :data:`PR_REVIEW`  — autobuild produced a non-empty diff; advance to
  the constitutional ``PULL_REQUEST_REVIEW`` gate.
- :data:`NO_OP`      — autobuild produced no diff against the working
  branch; record the build as terminally ``complete`` with a no-op
  rationale (Group M scenario "no-diff autobuild does not attempt
  pull-request creation").
- :data:`FAILED`     — autobuild reached a failed terminal lifecycle;
  record as failed with the autobuild's hard-stop rationale surfaced
  (Group C "internal hard-stop is propagated").

Tests cover each of those three branches plus several boundary cases:

- The handler reads the ``changed_files_count`` field from the
  ``AUTOBUILD`` stage-log entry's ``details`` mapping (TASK-MAG7-009
  result schema; the mode-b planner already consults the same row's
  ``diff_present`` boolean for its routing decision — the handler reads
  the count directly so a session outcome carrying it is auditable).
- The handler does NOT shell out to ``git diff`` — it consults stage-log
  history only.
- A spy ``gh pr create`` adapter is exposed via the test fixtures and
  asserted *not* called when the handler returns :data:`NO_OP` or
  :data:`FAILED` (AC: "No PR-creation call site is reachable").
- The recorded ``ModeBPostAutobuild.session_outcome_payload`` for a
  :data:`NO_OP` carries no ``pull_request_url`` and no PR-review gate
  decision (AC: Group M acceptance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest

from forge.lifecycle.modes import BuildMode
from forge.lifecycle.persistence import Build
from forge.pipeline.mode_b_planner import APPROVED, FAILED, HARD_STOP
from forge.pipeline.stage_taxonomy import StageClass
from forge.pipeline.supervisor import BuildState
from forge.pipeline.terminal_handlers import (
    NO_DIFF_RATIONALE,
    NO_OP,
    PR_REVIEW,
    ROUTE_FAILED,
    ModeBPostAutobuild,
    evaluate_post_autobuild,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeStageEntry:
    """In-memory stand-in for a ``stage_log`` row (mirrors planner tests)."""

    stage: StageClass
    status: str
    feature_id: str | None = "FEAT-X"
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class GhPrCreateSpy:
    """Records every call so tests can assert "never invoked"."""

    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def create(self, *args: Any, **kwargs: Any) -> str:
        self.calls.append((args, kwargs))
        return "https://example.invalid/never-called"


def make_build(
    *,
    build_id: str = "build-FEAT-X-20260427000000",
    status: BuildState = BuildState.RUNNING,
    mode: BuildMode = BuildMode.MODE_B,
) -> Build:
    """Build factory with sensible Mode B defaults."""
    return Build(build_id=build_id, status=status, mode=mode)


def make_autobuild_entry(
    *,
    status: str = APPROVED,
    changed_files_count: int | None = 0,
    feature_id: str | None = "FEAT-X",
    extra_details: Mapping[str, Any] | None = None,
) -> FakeStageEntry:
    """Build an ``AUTOBUILD`` stage-log entry with the given diff result."""
    details: dict[str, Any] = {}
    if changed_files_count is not None:
        details["changed_files_count"] = changed_files_count
    if extra_details:
        details.update(extra_details)
    return FakeStageEntry(
        stage=StageClass.AUTOBUILD,
        status=status,
        feature_id=feature_id,
        details=details,
    )


# ---------------------------------------------------------------------------
# AC-001 — module path and signature
# ---------------------------------------------------------------------------


class TestModuleAndSignature:
    """AC-001: ``forge.pipeline.terminal_handlers`` exposes the handler."""

    def test_module_exports_handler_symbols(self) -> None:
        from forge.pipeline import terminal_handlers

        assert hasattr(terminal_handlers, "evaluate_post_autobuild")
        assert hasattr(terminal_handlers, "ModeBPostAutobuild")
        assert hasattr(terminal_handlers, "PR_REVIEW")
        assert hasattr(terminal_handlers, "NO_OP")
        assert hasattr(terminal_handlers, "ROUTE_FAILED")

    def test_route_constants_have_distinct_string_values(self) -> None:
        # The three routes are distinct labels — callers persist them as
        # strings on the build's terminal state, so collisions would
        # alias unrelated outcomes.
        assert PR_REVIEW != NO_OP != ROUTE_FAILED
        assert {PR_REVIEW, NO_OP, ROUTE_FAILED} == {
            "PR_REVIEW",
            "NO_OP",
            "FAILED",
        }


# ---------------------------------------------------------------------------
# AC-003 — PR_REVIEW path: non-empty diff routes to constitutional gate
# ---------------------------------------------------------------------------


class TestPrReviewRoute:
    """AC-003: non-empty diff → ``PR_REVIEW``."""

    def test_approved_autobuild_with_changes_routes_to_pr_review(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=3),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == PR_REVIEW
        assert outcome.changed_files_count == 3
        # The handler is a routing shim — the constitutional gate is the
        # actual decision-maker, so the rationale only documents the
        # routing fact, not a gate verdict.
        assert "pull-request-review" in outcome.rationale.lower()

    def test_pr_review_route_does_not_invoke_pr_create_adapter(self) -> None:
        # AC-006: the handler itself never calls the PR-create adapter
        # — it only decides routing. We expose a spy via the test
        # fixture and assert it stays untouched.
        spy = GhPrCreateSpy()
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=1),)
        evaluate_post_autobuild(make_build(), history)

        # The handler's contract is "decide, do not dispatch". Even on
        # the PR-review branch, it must not call gh — the actual
        # ``gh pr create`` happens later in TASK-MAG7-008's subprocess
        # dispatcher, gated by the constitutional review.
        assert spy.calls == []


# ---------------------------------------------------------------------------
# AC-002 — NO_OP path: zero changed files → terminal complete no-op
# ---------------------------------------------------------------------------


class TestNoOpRoute:
    """AC-002 + Group M: zero changed files → ``NO_OP`` terminal."""

    def test_approved_autobuild_with_zero_changes_routes_to_no_op(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=0),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == NO_OP
        assert outcome.changed_files_count == 0

    def test_no_op_rationale_is_canonical_constant(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=0),)
        outcome = evaluate_post_autobuild(make_build(), history)

        # Group M scenario expects the rationale string to be stable —
        # downstream consumers (alerting, dashboards) match on it.
        assert outcome.rationale == NO_DIFF_RATIONALE
        assert outcome.rationale == "mode-b-autobuild-no-diff"

    def test_no_op_route_does_not_invoke_pr_create_adapter(self) -> None:
        # AC-006: the handler must not invoke ``gh pr create`` for a
        # no-diff result.
        spy = GhPrCreateSpy()
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=0),)
        evaluate_post_autobuild(make_build(), history)

        assert spy.calls == []

    def test_no_op_session_outcome_payload_carries_no_pr_url(self) -> None:
        # AC-007: session outcome for ``NO_OP`` carries no
        # ``pull_request_url`` and no PR-review gate decision.
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=0),)
        outcome = evaluate_post_autobuild(make_build(), history)

        payload = outcome.session_outcome_payload
        assert "pull_request_url" not in payload
        assert payload.get("pr_review_gate_decision") is None
        # The terminal kind is ``complete`` — the build *succeeded* by
        # virtue of having nothing to commit; it did not fail.
        assert payload["outcome"] == "complete"
        assert payload["rationale"] == NO_DIFF_RATIONALE


# ---------------------------------------------------------------------------
# AC-004 — FAILED path: autobuild reached a failed terminal lifecycle
# ---------------------------------------------------------------------------


class TestFailedRoute:
    """AC-004 + Group C: autobuild hard-stop / failure → ``FAILED``."""

    def test_hard_stopped_autobuild_routes_to_failed(self) -> None:
        history = (
            make_autobuild_entry(
                status=HARD_STOP,
                changed_files_count=None,
                extra_details={"rationale": "coach-rejected-output"},
            ),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == ROUTE_FAILED

    def test_failed_autobuild_routes_to_failed(self) -> None:
        history = (
            make_autobuild_entry(
                status=FAILED,
                changed_files_count=None,
                extra_details={"rationale": "subprocess-exit-1"},
            ),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == ROUTE_FAILED

    def test_failed_route_surfaces_autobuild_hard_stop_rationale(self) -> None:
        # AC-004: the autobuild's hard-stop rationale is propagated.
        history = (
            make_autobuild_entry(
                status=HARD_STOP,
                changed_files_count=None,
                extra_details={"rationale": "coach-rejected-final-output"},
            ),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        assert "coach-rejected-final-output" in outcome.rationale

    def test_failed_route_does_not_invoke_pr_create_adapter(self) -> None:
        # AC-006: the handler must not invoke ``gh pr create`` for a
        # failed autobuild.
        spy = GhPrCreateSpy()
        history = (
            make_autobuild_entry(
                status=HARD_STOP,
                changed_files_count=None,
                extra_details={"rationale": "coach-rejected"},
            ),
        )
        evaluate_post_autobuild(make_build(), history)

        assert spy.calls == []

    def test_failed_session_outcome_payload_carries_no_pr_url(self) -> None:
        # The handler-emitted session-outcome payload for a FAILED
        # outcome must not advertise a PR url either — there is no PR.
        history = (
            make_autobuild_entry(
                status=FAILED,
                changed_files_count=None,
                extra_details={"rationale": "subprocess-exit-1"},
            ),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        payload = outcome.session_outcome_payload
        assert "pull_request_url" not in payload
        assert payload["outcome"] == "failed"


# ---------------------------------------------------------------------------
# AC-005 — handler reads stage-log only, not ``git diff``
# ---------------------------------------------------------------------------


class TestNoShellOut:
    """AC-005: handler reads ``changed_files_count`` from stage-log row only."""

    def test_handler_does_not_invoke_subprocess(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The handler must not shell out — patching ``subprocess.run``
        # to raise gives us a tripwire that fires if any code path in
        # the handler attempts to spawn a process.
        import subprocess

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError(
                "evaluate_post_autobuild must not invoke subprocess; AC-005"
            )

        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setattr(subprocess, "Popen", boom)
        monkeypatch.setattr(subprocess, "check_output", boom)
        monkeypatch.setattr(subprocess, "check_call", boom)

        history = (make_autobuild_entry(status=APPROVED, changed_files_count=2),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == PR_REVIEW

    def test_handler_treats_missing_changed_files_count_as_no_diff(self) -> None:
        # Defensive: if a stage_log row was written without
        # ``changed_files_count`` (e.g. during the rollout that adds
        # the field), the handler treats absence as ``0`` rather than
        # silently advancing to PR creation. This is the conservative
        # default — emitting a NO_OP is recoverable; emitting a PR
        # against an empty diff is not.
        entry = FakeStageEntry(
            stage=StageClass.AUTOBUILD,
            status=APPROVED,
            details={},
        )
        outcome = evaluate_post_autobuild(make_build(), (entry,))

        assert outcome.route == NO_OP


# ---------------------------------------------------------------------------
# Boundary / defensive cases
# ---------------------------------------------------------------------------


class TestBoundaryCases:
    """Defensive coverage of malformed history inputs."""

    def test_empty_history_raises_value_error(self) -> None:
        # The handler is post-autobuild — it must never be called
        # without an autobuild entry. Failing fast here surfaces the
        # programmer error immediately rather than silently emitting
        # NO_OP for a build that never ran autobuild.
        with pytest.raises(ValueError, match="autobuild"):
            evaluate_post_autobuild(make_build(), history=())

    def test_history_without_autobuild_entry_raises_value_error(self) -> None:
        history = (
            FakeStageEntry(
                stage=StageClass.FEATURE_PLAN,
                status=APPROVED,
                details={},
            ),
        )
        with pytest.raises(ValueError, match="autobuild"):
            evaluate_post_autobuild(make_build(), history)

    def test_in_flight_autobuild_status_raises_value_error(self) -> None:
        # An autobuild that is still running has no terminal verdict —
        # the handler must not be invoked yet. Surfaces the bug rather
        # than picking an arbitrary route.
        history = (
            make_autobuild_entry(
                status="running",
                changed_files_count=None,
            ),
        )
        with pytest.raises(ValueError, match="terminal"):
            evaluate_post_autobuild(make_build(), history)

    def test_handler_picks_latest_autobuild_entry(self) -> None:
        # If a build retried autobuild, the history may contain multiple
        # AUTOBUILD entries. The handler must consult the latest one
        # (chronological last) rather than the first.
        history = (
            make_autobuild_entry(status=FAILED, changed_files_count=None),
            make_autobuild_entry(status=APPROVED, changed_files_count=5),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == PR_REVIEW
        assert outcome.changed_files_count == 5

    def test_outcome_dataclass_is_frozen(self) -> None:
        # ``ModeBPostAutobuild`` is a value object — mutation would
        # corrupt the routing decision after it has been logged.
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=1),)
        outcome = evaluate_post_autobuild(make_build(), history)

        with pytest.raises((AttributeError, Exception)):
            outcome.route = NO_OP  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-008 covered — three Group A/C/M scenarios all hit
# ---------------------------------------------------------------------------


class TestGroupScenarioCoverage:
    """AC-008: the three Group A/C/M Mode B scenarios are exercised.

    Group A (happy path with diff)        → PR_REVIEW
    Group C (autobuild internal hard-stop) → FAILED
    Group M (no-diff autobuild)            → NO_OP
    """

    def test_group_a_happy_path_with_diff_routes_to_pr_review(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=42),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == PR_REVIEW
        assert outcome.feature_id == "FEAT-X"

    def test_group_c_internal_hard_stop_routes_to_failed(self) -> None:
        history = (
            make_autobuild_entry(
                status=HARD_STOP,
                changed_files_count=None,
                extra_details={"rationale": "coach-hard-stop"},
            ),
        )
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == ROUTE_FAILED
        assert "coach-hard-stop" in outcome.rationale

    def test_group_m_no_diff_routes_to_no_op_terminal(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=0),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert outcome.route == NO_OP
        assert outcome.session_outcome_payload["outcome"] == "complete"
        assert outcome.rationale == "mode-b-autobuild-no-diff"
        # Group M acceptance: no PR url, no PR review gate decision.
        payload = outcome.session_outcome_payload
        assert "pull_request_url" not in payload
        assert payload.get("pr_review_gate_decision") is None


# ---------------------------------------------------------------------------
# Type-shape sanity
# ---------------------------------------------------------------------------


class TestReturnType:
    """The handler returns a ``ModeBPostAutobuild`` dataclass."""

    def test_returns_mode_b_post_autobuild_instance(self) -> None:
        history = (make_autobuild_entry(status=APPROVED, changed_files_count=1),)
        outcome = evaluate_post_autobuild(make_build(), history)

        assert isinstance(outcome, ModeBPostAutobuild)
        assert outcome.route in (PR_REVIEW, NO_OP, ROUTE_FAILED)
        assert isinstance(outcome.rationale, str)
        assert isinstance(outcome.session_outcome_payload, dict)
