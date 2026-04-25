"""CLI synthetic response injection — Group D ``@edge-case``.

The contract under test (closes risk **F6** by routing CLI steering
through the standard mirror subject):

* ``forge cancel <FEAT-XXX>`` produces a synthetic
  :class:`ApprovalResponsePayload` carrying
  ``decision="reject"``, ``decided_by="rich"``, ``notes="cli cancel"``;
  the standard subscriber dedup gate consumes it and the wrapper
  transitions the paused build to ``CANCELLED`` with the same reason.
* ``forge skip <FEAT-XXX>`` produces a synthetic response carrying
  ``decision="override"``, ``decided_by="rich"``, ``notes="cli skip"``
  and the wrapper marks the **current stage only** as overridden.

The integration seam exercised here is the join between
:func:`forge.gating.wrappers.cli_cancel_build` /
:func:`cli_skip_stage`, the :class:`SyntheticResponseInjector`, and
the in-memory NATS double — every layer the CLI command surface
delegates to.
"""

from __future__ import annotations

import json

import pytest

from forge.adapters.nats.synthetic_response_injector import (
    APPROVAL_SUBJECT_PREFIX,
    REASON_CLI_CANCEL,
    REASON_CLI_SKIP,
    SYNTHETIC_RESPONDER,
)
from forge.gating.identity import derive_request_id
from forge.gating.models import GateMode
from forge.gating.wrappers import (
    PausedBuildSnapshot,
    cli_cancel_build,
    cli_skip_stage,
)

from .conftest import (
    BUILD_ID,
    FEATURE_ID,
    STAGE_LABEL,
    InMemoryNats,
    build_gate_check_deps,
    sample_decision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response_subject(build_id: str = BUILD_ID) -> str:
    return f"{APPROVAL_SUBJECT_PREFIX}.{build_id}.response"


def _seed_paused_build(
    repo, *, attempt_count: int = 4, build_id: str = BUILD_ID
) -> None:
    """Seed an in-memory paused build that the CLI bridge can find."""
    repo.paused.append(
        PausedBuildSnapshot(
            build_id=build_id,
            feature_id=FEATURE_ID,
            stage_label=STAGE_LABEL,
            request_id=derive_request_id(
                build_id=build_id,
                stage_label=STAGE_LABEL,
                attempt_count=attempt_count,
            ),
            attempt_count=attempt_count,
            decision_snapshot=sample_decision(build_id=build_id),
        )
    )


def _decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCliCancelEmitsRejectionWithExpectedReason:
    """``forge cancel`` → synthetic ``decision="reject"`` + ``cli cancel``."""

    @pytest.mark.asyncio
    async def test_cli_cancel_publishes_reject_with_cli_cancel_reason(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, _, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        _seed_paused_build(repo, attempt_count=4)

        await cli_cancel_build(deps, build_id=BUILD_ID)

        # One envelope landed on the canonical mirror subject.
        published = nats.published.get(_response_subject(), [])
        assert len(published) == 1
        envelope = _decode(published[0])
        payload = envelope["payload"]
        assert payload["decision"] == "reject"
        assert payload["decided_by"] == SYNTHETIC_RESPONDER
        assert payload["notes"] == REASON_CLI_CANCEL
        # The synthetic response keys on the **persisted** request_id —
        # if it didn't, the dedup buffer wouldn't recognise it as a
        # duplicate of any concurrent real Rich response.
        expected_rid = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=4
        )
        assert payload["request_id"] == expected_rid


class TestCliSkipEmitsOverrideWithExpectedReason:
    """``forge skip`` → synthetic ``decision="override"`` + ``cli skip``."""

    @pytest.mark.asyncio
    async def test_cli_skip_publishes_override_with_cli_skip_reason(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, _, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        _seed_paused_build(repo, attempt_count=2)

        await cli_skip_stage(deps, build_id=BUILD_ID)

        published = nats.published.get(_response_subject(), [])
        assert len(published) == 1
        payload = _decode(published[0])["payload"]
        assert payload["decision"] == "override"
        assert payload["decided_by"] == SYNTHETIC_RESPONDER
        assert payload["notes"] == REASON_CLI_SKIP
        expected_rid = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=2
        )
        assert payload["request_id"] == expected_rid


class TestCliBridgeRaisesLookupErrorForUnknownBuild:
    """Defensive: cancelling/skipping a build that isn't paused fails loud."""

    @pytest.mark.asyncio
    async def test_unknown_build_cancel_raises_lookup_error(
        self, nats: InMemoryNats
    ) -> None:
        deps, *_ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        with pytest.raises(LookupError, match="no paused build"):
            await cli_cancel_build(deps, build_id="missing-build")

    @pytest.mark.asyncio
    async def test_unknown_build_skip_raises_lookup_error(
        self, nats: InMemoryNats
    ) -> None:
        deps, *_ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        with pytest.raises(LookupError, match="no paused build"):
            await cli_skip_stage(deps, build_id="missing-build")
