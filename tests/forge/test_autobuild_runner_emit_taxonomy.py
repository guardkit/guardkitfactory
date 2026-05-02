"""Stage-complete envelope taxonomy tests for ``autobuild_runner`` (TASK-FW10-002).

DDR-007 / FEAT-FORGE-010 ASSUM-018 commits ``autobuild_runner`` to a
specific shape for ``stage_complete`` envelopes emitted from inside the
subagent: ``target_kind="subagent"`` and ``target_identifier`` equal to
the subagent's own ``task_id`` (the value returned by
``start_async_task``).

The supervisor's emits for stages dispatched *outside* the subagent
retain the existing taxonomy (``target_kind`` ∈
``{"local_tool", "fleet_capability"}``) — these tests only constrain
the subagent's emit path.
"""

from __future__ import annotations

from typing import Any

import pytest
from nats_core.events import StageCompletePayload

from forge.subagents.autobuild_runner import (
    AutobuildState,
    build_stage_complete_kwargs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(task_id: str = "task-A1B2", **overrides: Any) -> AutobuildState:
    """Construct an :class:`AutobuildState` for taxonomy assertions."""
    base: dict[str, Any] = {
        "task_id": task_id,
        "build_id": "build-FEAT-X-20260502120000",
        "feature_id": "FEAT-X",
        "lifecycle": "running_wave",
        "correlation_id": "corr-001",
    }
    base.update(overrides)
    return AutobuildState(**base)


def _stage_complete_payload(state: AutobuildState, **overrides: Any) -> StageCompletePayload:
    """Build a real :class:`StageCompletePayload` using the helper.

    Threads through the runner's :func:`build_stage_complete_kwargs`
    helper so the test asserts the *real* call shape, not a paraphrase.
    """
    base_kwargs: dict[str, Any] = {
        "feature_id": state.feature_id,
        "build_id": state.build_id,
        "stage_label": "autobuild",
        "status": "PASSED",
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": 12.5,
        "completed_at": "2026-05-02T12:34:56Z",
        "correlation_id": state.correlation_id or "corr-001",
    }
    base_kwargs.update(build_stage_complete_kwargs(state))
    base_kwargs.update(overrides)
    return StageCompletePayload(**base_kwargs)


# ---------------------------------------------------------------------------
# AC: target_kind == "subagent" for stage_complete from inside the subagent
# ---------------------------------------------------------------------------


class TestStageCompleteTaxonomy:
    """ASSUM-018: ``target_kind="subagent"`` and ``target_identifier=task_id``."""

    def test_target_kind_is_subagent(self) -> None:
        """Helper sets ``target_kind="subagent"`` always."""
        state = _make_state(task_id="task-A1B2")

        kwargs = build_stage_complete_kwargs(state)

        assert kwargs["target_kind"] == "subagent", (
            "ASSUM-018: stage_complete from inside autobuild_runner must "
            "set target_kind='subagent'"
        )

    def test_target_identifier_is_task_id(self) -> None:
        """Helper sets ``target_identifier`` to the runner's ``task_id``."""
        state = _make_state(task_id="autobuild-task-XYZ-001")

        kwargs = build_stage_complete_kwargs(state)

        assert kwargs["target_identifier"] == "autobuild-task-XYZ-001", (
            "ASSUM-018: target_identifier must be the runner's own task_id"
        )

    @pytest.mark.parametrize(
        "task_id",
        [
            "task-001",
            "autobuild-task-FEAT-X-1700000000",
            "uuid-style-71f4c1a8-9e2b-4c1f-a3e5-9d2b1f4c5a6e",
        ],
    )
    def test_target_identifier_round_trips_arbitrary_task_ids(
        self, task_id: str
    ) -> None:
        """The ``task_id`` is propagated verbatim regardless of format."""
        state = _make_state(task_id=task_id)

        kwargs = build_stage_complete_kwargs(state)

        assert kwargs == {
            "target_kind": "subagent",
            "target_identifier": task_id,
        }

    def test_empty_task_id_is_rejected(self) -> None:
        """An empty ``task_id`` raises — the envelope would be ambiguous."""
        state = _make_state(task_id="x")  # construct first to bypass model validation
        # Pydantic accepts any non-None str including empty if no constraint;
        # bypass via model_copy to exercise the helper's own guard.
        bad = state.model_copy(update={"task_id": ""})

        with pytest.raises(ValueError, match="task_id must be non-empty"):
            build_stage_complete_kwargs(bad)


# ---------------------------------------------------------------------------
# AC: real StageCompletePayload accepts the helper's output
# ---------------------------------------------------------------------------


class TestStageCompletePayloadIntegration:
    """The helper's output is splat-compatible with the real payload model."""

    def test_payload_constructed_with_helper_kwargs(self) -> None:
        """Splatting the helper into the real payload validates cleanly."""
        state = _make_state(task_id="task-A1B2")

        payload = _stage_complete_payload(state)

        assert payload.target_kind == "subagent"
        assert payload.target_identifier == "task-A1B2"
        # Sibling fields are unchanged — the helper does not bleed into
        # the rest of the payload shape.
        assert payload.stage_label == "autobuild"
        assert payload.feature_id == "FEAT-X"
        assert payload.correlation_id == "corr-001"

    def test_payload_target_kind_literal_set_includes_subagent(self) -> None:
        """The nats-core literal set permits the ``"subagent"`` value.

        This guards against an upstream nats-core schema change that
        drops ``"subagent"`` from the ``target_kind`` literal — the
        helper would silently start producing schema-invalid envelopes.
        """
        from typing import get_args

        target_kind_field = StageCompletePayload.model_fields["target_kind"]
        # Pydantic stores the Literal under ``annotation``.
        permitted = set(get_args(target_kind_field.annotation))

        assert "subagent" in permitted, (
            "API-nats-pipeline-events §3.2: target_kind literal must "
            "include 'subagent' for FEAT-FORGE-010 ASSUM-018 to be valid"
        )

    def test_payload_status_unchanged_for_failed_subagent_emits(self) -> None:
        """Failed-status emits keep the subagent target taxonomy unchanged."""
        state = _make_state(task_id="task-A1B2")

        payload = _stage_complete_payload(state, status="FAILED")

        assert payload.status == "FAILED"
        assert payload.target_kind == "subagent"
        assert payload.target_identifier == "task-A1B2"
