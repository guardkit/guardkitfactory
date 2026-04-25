"""Crash-recovery re-emission — closes risk **R5**.

Group D ``@regression``. The contract under test: simulate a Forge
restart with a paused build in SQLite; assert that
:func:`forge.gating.wrappers.recover_paused_builds` re-publishes an
:class:`ApprovalRequestPayload` that carries the **persisted**
``request_id`` (not a freshly-derived one).

The persisted ``request_id`` is the wire contract: the responder
deduplicates on it, and a re-emission with a different id would let a
duplicate response slip through and resume the build twice. This is
the boot-time half of the F5 + F6 atomicity story (the runtime half
is exercised by ``test_pause_and_publish_atomicity.py`` and
``test_durable_decision_on_publish_failure.py``).
"""

from __future__ import annotations

import json

import pytest
from nats_core.envelope import EventType, MessageEnvelope

from forge.adapters.nats.approval_publisher import APPROVAL_SUBJECT_TEMPLATE
from forge.gating.models import GateMode
from forge.gating.wrappers import PausedBuildSnapshot, recover_paused_builds

from .conftest import (
    BUILD_ID,
    FEATURE_ID,
    OTHER_BUILD_ID,
    STAGE_LABEL,
    InMemoryNats,
    build_gate_check_deps,
    sample_decision,
)


# ---------------------------------------------------------------------------
# Helpers — decode the published envelope back into a dict for assertions.
# ---------------------------------------------------------------------------


def _decode(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrashRecoveryReEmissionPreservesPersistedRequestId:
    """Re-emit on boot uses the *persisted* ``request_id`` verbatim."""

    @pytest.mark.asyncio
    async def test_persisted_request_id_is_reused_unchanged(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, _, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )

        # Simulate the SQLite ``paused_builds`` view returning one row
        # whose request_id deliberately *cannot* be the value
        # derive_request_id would produce — so the test fails loud if
        # the wrapper re-derives instead of using the persisted value.
        weird_request_id = "PERSISTED-RID-MUST-NOT-BE-RE-DERIVED"
        repo.paused.append(
            PausedBuildSnapshot(
                build_id=BUILD_ID,
                feature_id=FEATURE_ID,
                stage_label=STAGE_LABEL,
                request_id=weird_request_id,
                attempt_count=3,
                decision_snapshot=sample_decision(),
            )
        )

        emitted = await recover_paused_builds(deps)

        assert emitted == [BUILD_ID]
        # Exactly one publish on the canonical request subject.
        subject = APPROVAL_SUBJECT_TEMPLATE.format(
            agent_id="forge", task_id=BUILD_ID
        )
        published = nats.published.get(subject, [])
        assert len(published) == 1
        envelope = _decode(published[0])
        assert envelope["payload"]["request_id"] == weird_request_id

    @pytest.mark.asyncio
    async def test_two_paused_builds_re_emit_independent_persisted_ids(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, _, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        repo.paused.extend(
            [
                PausedBuildSnapshot(
                    build_id=BUILD_ID,
                    feature_id=FEATURE_ID,
                    stage_label=STAGE_LABEL,
                    request_id="rid-A",
                    attempt_count=0,
                    decision_snapshot=sample_decision(build_id=BUILD_ID),
                ),
                PausedBuildSnapshot(
                    build_id=OTHER_BUILD_ID,
                    feature_id=FEATURE_ID,
                    stage_label=STAGE_LABEL,
                    request_id="rid-B",
                    attempt_count=2,
                    decision_snapshot=sample_decision(build_id=OTHER_BUILD_ID),
                ),
            ]
        )

        emitted = await recover_paused_builds(deps)
        assert sorted(emitted) == sorted([BUILD_ID, OTHER_BUILD_ID])

        # Each persisted request_id reaches its own subject.
        subj_a = APPROVAL_SUBJECT_TEMPLATE.format(
            agent_id="forge", task_id=BUILD_ID
        )
        subj_b = APPROVAL_SUBJECT_TEMPLATE.format(
            agent_id="forge", task_id=OTHER_BUILD_ID
        )
        env_a = _decode(nats.published[subj_a][0])
        env_b = _decode(nats.published[subj_b][0])
        assert env_a["payload"]["request_id"] == "rid-A"
        assert env_b["payload"]["request_id"] == "rid-B"

    @pytest.mark.asyncio
    async def test_publish_failure_for_one_build_does_not_block_others(
        self, nats: InMemoryNats
    ) -> None:
        # Operational: one flaky build's publish must not stop the
        # others from re-emitting on boot. The wrapper logs and
        # continues; the SQLite row remains the source of truth and
        # the next restart will retry.
        deps, _, repo, _, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE
        )
        # Inject a publish failure on build A's subject only.
        subj_a = APPROVAL_SUBJECT_TEMPLATE.format(
            agent_id="forge", task_id=BUILD_ID
        )
        nats.publish_failures[subj_a] = [ConnectionError("flaky")]
        repo.paused.extend(
            [
                PausedBuildSnapshot(
                    build_id=BUILD_ID,
                    feature_id=FEATURE_ID,
                    stage_label=STAGE_LABEL,
                    request_id="rid-A",
                    attempt_count=0,
                    decision_snapshot=sample_decision(build_id=BUILD_ID),
                ),
                PausedBuildSnapshot(
                    build_id=OTHER_BUILD_ID,
                    feature_id=FEATURE_ID,
                    stage_label=STAGE_LABEL,
                    request_id="rid-B",
                    attempt_count=0,
                    decision_snapshot=sample_decision(build_id=OTHER_BUILD_ID),
                ),
            ]
        )

        emitted = await recover_paused_builds(deps)
        # Build A failed; build B succeeded.
        assert emitted == [OTHER_BUILD_ID]
