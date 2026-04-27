"""Tests for ``forge.pipeline.stage_ordering_guard`` (TASK-MAG7-003).

Covers all seven prerequisite rows from the FEAT-FORGE-007 Group B
Scenario Outline verbatim, plus the multi-feature ``PULL_REQUEST_REVIEW``
case (row 7's "for every feature" clause).

Test cases mirror the acceptance criteria of TASK-MAG7-003 one-for-one:
a failing assertion points straight at the criterion it violates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from forge.pipeline.stage_ordering_guard import (
    StageLogReader,
    StageOrderingGuard,
)
from forge.pipeline.stage_taxonomy import (
    PER_FEATURE_STAGES,
    STAGE_PREREQUISITES,
    StageClass,
)

# ---------------------------------------------------------------------------
# In-memory fake StageLogReader
# ---------------------------------------------------------------------------


@dataclass
class FakeStageLogReader:
    """Minimal in-memory :class:`StageLogReader` for unit tests.

    Approved stages are stored as ``(build_id, stage, feature_id)``
    tuples; ``feature_id`` is ``None`` for non-per-feature stages so a
    single set captures both scopes. The feature catalogue is keyed by
    ``build_id`` to mirror the production SQLite shape.
    """

    approved: set[tuple[str, StageClass, str | None]] = field(default_factory=set)
    catalogues: dict[str, list[str]] = field(default_factory=dict)

    def is_approved(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> bool:
        return (build_id, stage, feature_id) in self.approved

    def feature_catalogue(self, build_id: str) -> list[str]:
        return list(self.catalogues.get(build_id, []))

    # Test helpers --------------------------------------------------------

    def approve(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> None:
        """Record ``stage`` as approved for ``(build_id, feature_id)``."""
        self.approved.add((build_id, stage, feature_id))

    def set_catalogue(self, build_id: str, features: list[str]) -> None:
        self.catalogues[build_id] = list(features)


# ---------------------------------------------------------------------------
# Seam test (from task AC) — verifies the contract with TASK-MAG7-001
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("stage_taxonomy")
def test_stage_taxonomy_contract() -> None:
    """Verify ``StageClass`` enum and ``STAGE_PREREQUISITES`` match contract.

    Contract: 8 stages, 7 prerequisite rows matching Scenario Outline.
    Producer: TASK-MAG7-001.
    """
    from forge.pipeline.stage_taxonomy import STAGE_PREREQUISITES, StageClass

    assert len(StageClass) == 8, "Must have exactly 8 stage classes"
    assert len(STAGE_PREREQUISITES) == 7, "Must have exactly 7 prerequisite rows"
    assert set(STAGE_PREREQUISITES.keys()) == {
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    }


# ---------------------------------------------------------------------------
# StageLogReader Protocol shape — FakeStageLogReader is a structural match
# ---------------------------------------------------------------------------


class TestStageLogReaderProtocol:
    """AC: pure function — no I/O except via the injected Protocol."""

    def test_fake_reader_satisfies_protocol_runtime(self) -> None:
        # ``StageLogReader`` is ``@runtime_checkable``; an empty fake
        # must still satisfy it via duck-typing alone.
        assert isinstance(FakeStageLogReader(), StageLogReader)

    def test_guard_constructs_without_arguments(self) -> None:
        # Pure-function shape: the guard takes no constructor state. The
        # reader is supplied per-call so the same guard can serve many
        # builds.
        guard = StageOrderingGuard()
        assert guard is not None


# ---------------------------------------------------------------------------
# Seven Group B prerequisite rows — verbatim from the Scenario Outline
# ---------------------------------------------------------------------------


BUILD_ID = "build-FEAT-FORGE-007-20260425000000"
FEATURE_A = "FEAT-A"
FEATURE_B = "FEAT-B"


def _seed_chain_up_to(
    reader: FakeStageLogReader,
    *up_to_exclusive: StageClass,
    feature_ids: list[str] | None = None,
) -> None:
    """Approve every stage up to (but not including) ``up_to_exclusive``.

    Per-feature stages are approved against every feature in
    ``feature_ids``. The helper short-circuits at the first stage in
    ``up_to_exclusive`` so callers can express "everything earlier than
    X" in one line.
    """
    feature_ids = feature_ids or [FEATURE_A]
    stop = set(up_to_exclusive)
    for stage in StageClass:
        if stage in stop:
            return
        if stage in PER_FEATURE_STAGES:
            for fid in feature_ids:
                reader.approve(BUILD_ID, stage, feature_id=fid)
        else:
            reader.approve(BUILD_ID, stage)


class TestGroupBPrerequisiteRows:
    """AC: unit tests cover all seven prerequisite rows verbatim.

    The parametrize table is the seven rows of the Group B Scenario
    Outline ("A downstream stage is not dispatched before its
    prerequisite has reached the approved state"):

        | stage         | prerequisite                  |
        | architect     | product-owner                 |
        | system-arch   | architect                     |
        | system-design | system-arch                   |
        | feature-spec  | system-design                 |
        | feature-plan  | feature-spec for that feature |
        | autobuild     | feature-plan for that feature |
        | pull-request  | autobuild for every feature   |
    """

    @pytest.mark.parametrize(
        ("stage", "prerequisite"),
        [
            (StageClass.ARCHITECT, StageClass.PRODUCT_OWNER),
            (StageClass.SYSTEM_ARCH, StageClass.ARCHITECT),
            (StageClass.SYSTEM_DESIGN, StageClass.SYSTEM_ARCH),
            (StageClass.FEATURE_SPEC, StageClass.SYSTEM_DESIGN),
            (StageClass.FEATURE_PLAN, StageClass.FEATURE_SPEC),
            (StageClass.AUTOBUILD, StageClass.FEATURE_PLAN),
            (StageClass.PULL_REQUEST_REVIEW, StageClass.AUTOBUILD),
        ],
    )
    def test_stage_not_dispatchable_when_prerequisite_unapproved(
        self,
        stage: StageClass,
        prerequisite: StageClass,
    ) -> None:
        """Group B: with prerequisite unapproved, ``stage`` is refused."""
        reader = FakeStageLogReader()
        # Set up a single-feature catalogue so the per-feature rows
        # have something to fan out across.
        reader.set_catalogue(BUILD_ID, [FEATURE_A])
        # Seed everything earlier than the prerequisite, but NOT the
        # prerequisite itself.
        _seed_chain_up_to(reader, prerequisite, feature_ids=[FEATURE_A])

        guard = StageOrderingGuard()
        feature_id = FEATURE_A if stage in PER_FEATURE_STAGES else None
        # PR review is special — for the feature_id arg we pass None
        # because PR review is checked at build scope (it fans out
        # internally).
        if stage is StageClass.PULL_REQUEST_REVIEW:
            feature_id = None

        assert (
            guard.is_dispatchable(
                BUILD_ID,
                stage,
                reader,
                feature_id=feature_id,
            )
            is False
        ), (
            f"{stage} must NOT be dispatchable while {prerequisite} "
            "is unapproved (Group B Scenario Outline row)"
        )

    @pytest.mark.parametrize(
        ("stage", "prerequisite"),
        [
            (StageClass.ARCHITECT, StageClass.PRODUCT_OWNER),
            (StageClass.SYSTEM_ARCH, StageClass.ARCHITECT),
            (StageClass.SYSTEM_DESIGN, StageClass.SYSTEM_ARCH),
            (StageClass.FEATURE_SPEC, StageClass.SYSTEM_DESIGN),
            (StageClass.FEATURE_PLAN, StageClass.FEATURE_SPEC),
            (StageClass.AUTOBUILD, StageClass.FEATURE_PLAN),
            (StageClass.PULL_REQUEST_REVIEW, StageClass.AUTOBUILD),
        ],
    )
    def test_stage_dispatchable_once_prerequisite_approved(
        self,
        stage: StageClass,
        prerequisite: StageClass,
    ) -> None:
        """Symmetric positive case — once the prerequisite lands, ``stage`` flips."""
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A])
        # Seed every stage up to AND including the prerequisite.
        for s in StageClass:
            if s in PER_FEATURE_STAGES:
                reader.approve(BUILD_ID, s, feature_id=FEATURE_A)
            else:
                reader.approve(BUILD_ID, s)
            if s is prerequisite:
                break

        guard = StageOrderingGuard()
        feature_id = FEATURE_A if stage in PER_FEATURE_STAGES else None
        if stage is StageClass.PULL_REQUEST_REVIEW:
            feature_id = None

        assert (
            guard.is_dispatchable(
                BUILD_ID,
                stage,
                reader,
                feature_id=feature_id,
            )
            is True
        ), (
            f"{stage} should be dispatchable once {prerequisite} is "
            "approved (Group B Scenario Outline row)"
        )


# ---------------------------------------------------------------------------
# Per-feature scoping — rows 5 and 6 ("for that feature")
# ---------------------------------------------------------------------------


class TestPerFeatureScoping:
    """AC: per-feature stages take a ``feature_id`` and check scoped prereqs."""

    def test_feature_plan_dispatchable_only_for_feature_with_feature_spec(
        self,
    ) -> None:
        """feature-plan ← feature-spec **for that feature** (row 5)."""
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        # Seed the build-scope chain up through SYSTEM_DESIGN.
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        # Approve FEATURE_SPEC only for FEATURE_A.
        reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        assert (
            guard.is_dispatchable(
                BUILD_ID, StageClass.FEATURE_PLAN, reader, feature_id=FEATURE_A
            )
            is True
        )
        assert (
            guard.is_dispatchable(
                BUILD_ID, StageClass.FEATURE_PLAN, reader, feature_id=FEATURE_B
            )
            is False
        )

    def test_autobuild_dispatchable_only_for_feature_with_feature_plan(
        self,
    ) -> None:
        """autobuild ← feature-plan **for that feature** (row 6)."""
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        # Both features get FEATURE_SPEC; only FEATURE_A gets FEATURE_PLAN.
        for fid in (FEATURE_A, FEATURE_B):
            reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=fid)
        reader.approve(BUILD_ID, StageClass.FEATURE_PLAN, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        assert (
            guard.is_dispatchable(
                BUILD_ID, StageClass.AUTOBUILD, reader, feature_id=FEATURE_A
            )
            is True
        )
        assert (
            guard.is_dispatchable(
                BUILD_ID, StageClass.AUTOBUILD, reader, feature_id=FEATURE_B
            )
            is False
        )

    def test_per_feature_stage_without_feature_id_is_refused(self) -> None:
        """Calling per-feature stage without ``feature_id`` is a hard refusal.

        The safe default — the alternative would silently approve a
        cross-feature prerequisite leak.
        """
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        assert guard.is_dispatchable(BUILD_ID, StageClass.FEATURE_PLAN, reader) is False


# ---------------------------------------------------------------------------
# Multi-feature PULL_REQUEST_REVIEW (row 7 "for every feature")
# ---------------------------------------------------------------------------


class TestPullRequestReviewMultiFeature:
    """AC: PR review requires AUTOBUILD approved for *every* feature."""

    def test_pr_review_blocked_when_one_of_several_autobuilds_missing(
        self,
    ) -> None:
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        for fid in (FEATURE_A, FEATURE_B):
            reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=fid)
            reader.approve(BUILD_ID, StageClass.FEATURE_PLAN, feature_id=fid)
        # Only FEATURE_A finished autobuild.
        reader.approve(BUILD_ID, StageClass.AUTOBUILD, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        assert (
            guard.is_dispatchable(BUILD_ID, StageClass.PULL_REQUEST_REVIEW, reader)
            is False
        )

    def test_pr_review_dispatchable_when_every_autobuild_approved(
        self,
    ) -> None:
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        for fid in (FEATURE_A, FEATURE_B):
            reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=fid)
            reader.approve(BUILD_ID, StageClass.FEATURE_PLAN, feature_id=fid)
            reader.approve(BUILD_ID, StageClass.AUTOBUILD, feature_id=fid)

        guard = StageOrderingGuard()
        assert (
            guard.is_dispatchable(BUILD_ID, StageClass.PULL_REQUEST_REVIEW, reader)
            is True
        )

    def test_pr_review_blocked_when_catalogue_is_empty(self) -> None:
        """An empty catalogue → nothing to review → not dispatchable.

        Defends the boundary that TASK-MAG7-005 covers from the other
        side (zero-feature ``SYSTEM_DESIGN`` output must not enter the
        per-feature loop).
        """
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [])  # empty catalogue
        # Even with everything else seeded, an empty catalogue blocks
        # the constitutional terminator.
        for stage in StageClass:
            if stage is not StageClass.PULL_REQUEST_REVIEW:
                if stage in PER_FEATURE_STAGES:
                    continue
                reader.approve(BUILD_ID, stage)

        guard = StageOrderingGuard()
        assert (
            guard.is_dispatchable(BUILD_ID, StageClass.PULL_REQUEST_REVIEW, reader)
            is False
        )


# ---------------------------------------------------------------------------
# next_dispatchable() — set-returning aggregator
# ---------------------------------------------------------------------------


class TestNextDispatchable:
    """AC: ``next_dispatchable`` returns the set of dispatchable stages."""

    def test_empty_log_only_product_owner_dispatchable(self) -> None:
        """With nothing approved, only ``PRODUCT_OWNER`` (no prereqs) qualifies."""
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [])

        guard = StageOrderingGuard()
        assert guard.next_dispatchable(BUILD_ID, reader) == {StageClass.PRODUCT_OWNER}

    def test_after_product_owner_approved_architect_joins_set(self) -> None:
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [])
        reader.approve(BUILD_ID, StageClass.PRODUCT_OWNER)

        guard = StageOrderingGuard()
        result = guard.next_dispatchable(BUILD_ID, reader)
        assert StageClass.ARCHITECT in result
        assert StageClass.PRODUCT_OWNER in result
        # Nothing further yet.
        assert StageClass.SYSTEM_ARCH not in result

    def test_per_feature_stage_in_set_when_any_feature_eligible(self) -> None:
        """``FEATURE_PLAN`` joins the set iff at least one feature is eligible."""
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        # Only FEATURE_A has its FEATURE_SPEC approved.
        reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        result = guard.next_dispatchable(BUILD_ID, reader)
        assert StageClass.FEATURE_PLAN in result
        # FEATURE_B's FEATURE_SPEC is also dispatchable (system-design done).
        assert StageClass.FEATURE_SPEC in result

    def test_pr_review_in_set_only_when_every_feature_autobuilt(self) -> None:
        reader = FakeStageLogReader()
        reader.set_catalogue(BUILD_ID, [FEATURE_A, FEATURE_B])
        _seed_chain_up_to(reader, StageClass.FEATURE_SPEC)
        for fid in (FEATURE_A, FEATURE_B):
            reader.approve(BUILD_ID, StageClass.FEATURE_SPEC, feature_id=fid)
            reader.approve(BUILD_ID, StageClass.FEATURE_PLAN, feature_id=fid)
        # Only one autobuild approved → not yet.
        reader.approve(BUILD_ID, StageClass.AUTOBUILD, feature_id=FEATURE_A)

        guard = StageOrderingGuard()
        assert StageClass.PULL_REQUEST_REVIEW not in guard.next_dispatchable(
            BUILD_ID, reader
        )

        # Add the second autobuild → PR review qualifies.
        reader.approve(BUILD_ID, StageClass.AUTOBUILD, feature_id=FEATURE_B)
        assert StageClass.PULL_REQUEST_REVIEW in guard.next_dispatchable(
            BUILD_ID, reader
        )


# ---------------------------------------------------------------------------
# Pure-function property — the guard never touches I/O outside the Protocol
# ---------------------------------------------------------------------------


class TestPureFunctionProperty:
    """AC: pure function — no I/O except via the injected Protocol."""

    def test_guard_only_calls_protocol_methods(self) -> None:
        """The guard must consult only ``is_approved`` / ``feature_catalogue``.

        We use a recording reader to assert no other attribute access
        occurs. ``__getattr__`` raises so any stray access surfaces as
        ``AttributeError`` rather than passing silently.
        """

        class RecordingReader:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def is_approved(
                self,
                build_id: str,
                stage: StageClass,
                feature_id: str | None = None,
            ) -> bool:
                self.calls.append(f"is_approved:{stage}:{feature_id}")
                return True

            def feature_catalogue(self, build_id: str) -> list[str]:
                self.calls.append("feature_catalogue")
                return [FEATURE_A]

            def __getattr__(self, name: str) -> object:
                raise AttributeError(f"Guard accessed unexpected attribute: {name!r}")

        reader = RecordingReader()
        guard = StageOrderingGuard()
        # Drive both methods to exercise both call paths.
        guard.is_dispatchable(
            BUILD_ID,
            StageClass.AUTOBUILD,
            reader,  # type: ignore[arg-type]
            feature_id=FEATURE_A,
        )
        guard.next_dispatchable(BUILD_ID, reader)  # type: ignore[arg-type]

        # Every recorded call is one of the two protocol methods.
        for call in reader.calls:
            assert call.startswith("is_approved") or call == "feature_catalogue"


# ---------------------------------------------------------------------------
# Sanity: STAGE_PREREQUISITES coverage parity with the seven-row table
# ---------------------------------------------------------------------------


def test_seven_prerequisite_rows_align_with_taxonomy() -> None:
    """Sanity guard against drift: TASK-MAG7-001 still ships seven rows."""
    assert len(STAGE_PREREQUISITES) == 7
