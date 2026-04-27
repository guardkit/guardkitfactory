"""Tests for ``forge.pipeline.forward_context_builder`` (TASK-MAG7-006).

Validates the :class:`ForwardContextBuilder` — the *only* place that crosses
the boundary from "the build's recorded history" to "what gets passed to a
downstream subprocess". The builder must:

- Return :class:`ContextEntry` values matching the
  :data:`forge.pipeline.forward_propagation.PROPAGATION_CONTRACT` recipe for
  the requested consumer stage.
- Read ``stage_log`` rows scoped by ``build_id`` (and by ``feature_id`` for
  per-feature stages) with ``gate_decision='approved'`` *only* — never
  in-progress or flagged-for-review entries.
- Refuse to thread any path that falls outside the build's worktree
  allowlist (defence-in-depth alongside FEAT-FORGE-005), filtering it out
  with a structured warning rather than raising.

Test cases mirror the acceptance criteria of TASK-MAG7-006 one-for-one and
the FEAT-FORGE-007 Group A "forward propagation" scenarios.

Both reader Protocols (``StageLogReader``, ``WorktreeAllowlist``) are
satisfied by in-memory test doubles so the suite runs without SQLite or
the FEAT-FORGE-005 allowlist subsystem.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from forge.lifecycle.modes import BuildMode
from forge.pipeline import forward_context_builder
from forge.pipeline.forward_context_builder import (
    MODE_B_PROPAGATION_CONTRACT,
    ApprovedStageEntry,
    ContextEntry,
    FixTaskRef,
    ForwardContextBuilder,
    ModeBoundaryViolation,
    StageLogReader,
    WorktreeAllowlist,
)
from forge.pipeline.forward_propagation import PROPAGATION_CONTRACT
from forge.pipeline.mode_chains_data import MODE_B_FORBIDDEN_STAGES
from forge.pipeline.stage_taxonomy import PER_FEATURE_STAGES, StageClass

# ---------------------------------------------------------------------------
# Test doubles — in-memory fakes for the two injected Protocols
# ---------------------------------------------------------------------------


@dataclass
class FakeStageLogReader:
    """In-memory :class:`StageLogReader`.

    The fake stores approved stage entries keyed by
    ``(build_id, stage, feature_id)``. ``feature_id`` is ``None`` for
    non-per-feature stages. Any lookup that does not hit a stored entry
    returns ``None`` — modelling either "no row yet" or "row present
    but not yet approved".

    For Mode C's follow-up ``/task-review`` (TASK-MBC8-005 AC-005) the
    builder also needs to enumerate every approved row for a stage
    (typically multiple ``/task-work`` rows in a cycle). The fake stores
    those in :attr:`multi_entries` keyed the same way; an empty / missing
    entry yields an empty sequence.
    """

    entries: dict[tuple[str, StageClass, str | None], ApprovedStageEntry] = field(
        default_factory=dict
    )
    multi_entries: dict[
        tuple[str, StageClass, str | None], list[ApprovedStageEntry]
    ] = field(default_factory=dict)

    def get_approved_stage_entry(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> ApprovedStageEntry | None:
        return self.entries.get((build_id, stage, feature_id))

    def get_all_approved_stage_entries(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> Sequence[ApprovedStageEntry]:
        return tuple(self.multi_entries.get((build_id, stage, feature_id), ()))


@dataclass
class FakeWorktreeAllowlist:
    """In-memory :class:`WorktreeAllowlist`.

    The fake stores the build's worktree root as a string prefix; any
    path that begins with the prefix is allowed, anything else is not.
    Production wires the FEAT-FORGE-005 allowlist; the prefix model is
    sufficient for unit tests because the production check ultimately
    answers the same yes/no question.
    """

    roots_by_build: dict[str, str] = field(default_factory=dict)

    def is_allowed(self, build_id: str, path: str) -> bool:
        root = self.roots_by_build.get(build_id)
        if root is None:
            return False
        return path == root or path.startswith(root.rstrip("/") + "/")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def allowlist() -> FakeWorktreeAllowlist:
    return FakeWorktreeAllowlist(
        roots_by_build={"build-1": "/work/build-1"},
    )


@pytest.fixture
def reader() -> FakeStageLogReader:
    return FakeStageLogReader()


@pytest.fixture
def builder(
    reader: FakeStageLogReader,
    allowlist: FakeWorktreeAllowlist,
) -> ForwardContextBuilder:
    return ForwardContextBuilder(
        stage_log_reader=reader,
        worktree_allowlist=allowlist,
    )


# ---------------------------------------------------------------------------
# AC-001 — class & module location
# ---------------------------------------------------------------------------


class TestForwardContextBuilderExists:
    """AC-001 — class exists at the documented module path."""

    def test_module_path_is_forge_pipeline_forward_context_builder(
        self,
    ) -> None:
        assert (
            forward_context_builder.__name__ == "forge.pipeline.forward_context_builder"
        )

    def test_module_file_lives_under_src_forge_pipeline(self) -> None:
        path = Path(forward_context_builder.__file__)
        assert path.name == "forward_context_builder.py"
        assert path.parent.name == "pipeline"
        assert path.parent.parent.name == "forge"

    def test_class_is_instantiable_with_required_dependencies(
        self,
        reader: FakeStageLogReader,
        allowlist: FakeWorktreeAllowlist,
    ) -> None:
        instance = ForwardContextBuilder(
            stage_log_reader=reader,
            worktree_allowlist=allowlist,
        )
        assert isinstance(instance, ForwardContextBuilder)


# ---------------------------------------------------------------------------
# AC-002 — build_for(...) returns ContextEntry list with right flag/value
# ---------------------------------------------------------------------------


class TestBuildForReturnsContextEntries:
    """AC-002 — ``build_for`` returns the entries to thread into dispatch."""

    def test_text_artefact_produces_single_text_entry(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # ARCHITECT consumes PRODUCT_OWNER's text charter.
        reader.entries[("build-1", StageClass.PRODUCT_OWNER, None)] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="The product charter.",
            )
        )

        entries = builder.build_for(
            stage=StageClass.ARCHITECT,
            build_id="build-1",
            feature_id=None,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="The product charter.",
                kind="text",
            )
        ]

    def test_path_artefact_produces_single_path_entry(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # AUTOBUILD consumes FEATURE_PLAN's single path artefact.
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan.md",),
                artefact_text=None,
            )
        )

        entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/plan.md",
                kind="path",
            )
        ]

    def test_path_list_artefact_expands_to_one_entry_per_path(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # SYSTEM_DESIGN consumes SYSTEM_ARCH's path-list artefact.
        reader.entries[("build-1", StageClass.SYSTEM_ARCH, None)] = ApprovedStageEntry(
            gate_decision="approved",
            artefact_paths=(
                "/work/build-1/arch/a.md",
                "/work/build-1/arch/b.md",
            ),
            artefact_text=None,
        )

        entries = builder.build_for(
            stage=StageClass.SYSTEM_DESIGN,
            build_id="build-1",
            feature_id=None,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/arch/a.md",
                kind="path",
            ),
            ContextEntry(
                flag="--context",
                value="/work/build-1/arch/b.md",
                kind="path",
            ),
        ]


# ---------------------------------------------------------------------------
# AC-003 — only approved gate_decision rows are read
# ---------------------------------------------------------------------------


class TestApprovedOnly:
    """AC-003 / AC-007 — never reads in-progress or flagged-for-review rows."""

    def test_no_prior_entry_returns_empty_context(
        self,
        builder: ForwardContextBuilder,
    ) -> None:
        # Reader has no entry; builder must return [].
        assert (
            builder.build_for(
                stage=StageClass.ARCHITECT,
                build_id="build-1",
                feature_id=None,
            )
            == []
        )

    def test_in_progress_prior_stage_returns_empty_context(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """AC-007 — in-progress prior stage → empty context."""
        # The reader's ``get_approved_stage_entry`` only ever returns
        # rows with gate_decision='approved'. An in-progress row is
        # therefore *invisible* to the builder — modelled here by simply
        # not storing the entry.
        assert reader.entries == {}
        assert (
            builder.build_for(
                stage=StageClass.ARCHITECT,
                build_id="build-1",
                feature_id=None,
            )
            == []
        )

    def test_builder_only_calls_reader_with_no_status_filter_argument(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """The reader Protocol's contract is "approved-only by construction".

        We assert the builder does not try to bypass that by passing
        e.g. an ``include_unapproved=True`` kwarg. The Protocol method
        signature itself enforces this — there is nowhere to put such a
        flag — but we double-check here by asserting the call returns
        ``None`` (no entry present) and the builder respects that.
        """
        reader.entries[("build-1", StageClass.PRODUCT_OWNER, None)] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="t",
            )
        )
        # When we ask for a stage whose producer has *no* approved row,
        # the result is empty.
        assert (
            builder.build_for(
                stage=StageClass.SYSTEM_ARCH,  # producer = ARCHITECT (absent)
                build_id="build-1",
                feature_id=None,
            )
            == []
        )


# ---------------------------------------------------------------------------
# AC-004 — allowlist refuses paths outside the worktree
# ---------------------------------------------------------------------------


class TestAllowlistEnforcement:
    """AC-004 / AC-008 — paths outside the allowlist are filtered with warning."""

    def test_path_outside_allowlist_is_filtered_out(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        reader.entries[("build-1", StageClass.SYSTEM_ARCH, None)] = ApprovedStageEntry(
            gate_decision="approved",
            artefact_paths=(
                "/work/build-1/inside.md",  # allowed
                "/etc/passwd",  # outside — must be filtered
            ),
            artefact_text=None,
        )

        with caplog.at_level(
            logging.WARNING, logger="forge.pipeline.forward_context_builder"
        ):
            entries = builder.build_for(
                stage=StageClass.SYSTEM_DESIGN,
                build_id="build-1",
                feature_id=None,
            )

        # Only the allowed path survives.
        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/inside.md",
                kind="path",
            )
        ]
        # And a structured warning was logged for the rejected path.
        assert any(
            "/etc/passwd" in record.getMessage() and "build-1" in record.getMessage()
            for record in caplog.records
        ), "expected structured warning for path outside allowlist"

    def test_text_artefacts_are_not_subject_to_allowlist(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # No allowlist root configured for this build at all.
        reader.entries[("build-1", StageClass.ARCHITECT, None)] = ApprovedStageEntry(
            gate_decision="approved",
            artefact_paths=(),
            artefact_text="approved architect output",
        )

        entries = builder.build_for(
            stage=StageClass.SYSTEM_ARCH,
            build_id="build-1",
            feature_id=None,
        )

        # Text payloads are inline and have no filesystem path to gate.
        assert entries == [
            ContextEntry(
                flag="--context",
                value="approved architect output",
                kind="text",
            )
        ]

    def test_single_path_outside_allowlist_returns_empty_list(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # FEATURE_PLAN consumes FEATURE_SPEC's single path. If that one
        # path is outside the allowlist, the result is [] — there is
        # nothing safe to thread.
        reader.entries[("build-1", StageClass.FEATURE_SPEC, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/tmp/spec.md",),  # outside /work/build-1
                artefact_text=None,
            )
        )

        with caplog.at_level(
            logging.WARNING, logger="forge.pipeline.forward_context_builder"
        ):
            entries = builder.build_for(
                stage=StageClass.FEATURE_PLAN,
                build_id="build-1",
                feature_id="FEAT-1",
            )

        assert entries == []
        assert any("/tmp/spec.md" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# AC-005 — per-feature stages scope the lookup to that feature
# ---------------------------------------------------------------------------


class TestPerFeatureScoping:
    """AC-005 — per-feature stages scope to that feature's prior entry only."""

    def test_per_feature_consumer_reads_per_feature_producer_for_that_feature(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # Two features each have their own approved FEATURE_PLAN row.
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan-1.md",),
                artefact_text=None,
            )
        )
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-2")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan-2.md",),
                artefact_text=None,
            )
        )

        entries_1 = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
        )
        entries_2 = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-2",
        )

        assert entries_1 == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/plan-1.md",
                kind="path",
            )
        ]
        assert entries_2 == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/plan-2.md",
                kind="path",
            )
        ]

    def test_per_feature_consumer_with_non_per_feature_producer_uses_build_scope(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # FEATURE_SPEC's producer is SYSTEM_DESIGN, which is *not*
        # per-feature; the lookup must not be feature-scoped.
        reader.entries[("build-1", StageClass.SYSTEM_DESIGN, None)] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="catalogue: FEAT-1, FEAT-2",
            )
        )

        entries = builder.build_for(
            stage=StageClass.FEATURE_SPEC,
            build_id="build-1",
            feature_id="FEAT-1",
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="catalogue: FEAT-1, FEAT-2",
                kind="text",
            )
        ]

    def test_per_feature_consumer_without_feature_id_returns_empty(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """Per-feature consumer without ``feature_id`` is a misuse → safe empty.

        Mirrors the ``StageOrderingGuard`` "refuse rather than dispatch
        cross-feature" stance from TASK-MAG7-003.
        """
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan.md",),
                artefact_text=None,
            )
        )

        entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id=None,
        )

        assert entries == []


# ---------------------------------------------------------------------------
# AC-006 — coverage of all seven PROPAGATION_CONTRACT rows
# ---------------------------------------------------------------------------


class TestAllSevenPropagationContractRows:
    """AC-006 — every PROPAGATION_CONTRACT row produces a ContextEntry.

    Parametrised across the seven consumer stages to demonstrate the
    builder is contract-driven, not stage-special-cased.
    """

    @pytest.mark.parametrize("consumer", list(PROPAGATION_CONTRACT.keys()))
    def test_each_contract_row_produces_at_least_one_entry(
        self,
        consumer: StageClass,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        recipe = PROPAGATION_CONTRACT[consumer]
        producer = recipe.producer_stage
        producer_feature_id = "FEAT-1" if producer in PER_FEATURE_STAGES else None
        consumer_feature_id = "FEAT-1" if consumer in PER_FEATURE_STAGES else None

        # Build a synthetic approved entry shaped to match the recipe.
        if recipe.artefact_kind == "text":
            entry = ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text=f"{producer.value} approved output",
            )
        elif recipe.artefact_kind == "path":
            entry = ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(f"/work/build-1/{producer.value}.md",),
                artefact_text=None,
            )
        else:  # path-list
            entry = ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(
                    f"/work/build-1/{producer.value}/a.md",
                    f"/work/build-1/{producer.value}/b.md",
                ),
                artefact_text=None,
            )
        reader.entries[("build-1", producer, producer_feature_id)] = entry

        entries = builder.build_for(
            stage=consumer,
            build_id="build-1",
            feature_id=consumer_feature_id,
        )

        assert entries, f"no context produced for consumer={consumer}"
        for ce in entries:
            assert ce.flag == recipe.context_flag
            assert ce.kind in {"text", "path"}
            assert ce.value  # non-empty


# ---------------------------------------------------------------------------
# Boundary: Protocol shape & exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Public API surface — keep the export list tight."""

    def test_module_exports_required_public_symbols(self) -> None:
        assert set(forward_context_builder.__all__) == {
            "ApprovedStageEntry",
            "ContextEntry",
            "FixTaskRef",
            "ForwardContextBuilder",
            "MODE_B_PROPAGATION_CONTRACT",
            "ModeBoundaryViolation",
            "StageLogReader",
            "WorktreeAllowlist",
        }

    def test_protocols_are_runtime_checkable(
        self,
        reader: FakeStageLogReader,
        allowlist: FakeWorktreeAllowlist,
    ) -> None:
        # The fakes structurally satisfy the Protocols.
        assert isinstance(reader, StageLogReader)
        assert isinstance(allowlist, WorktreeAllowlist)


# ---------------------------------------------------------------------------
# TASK-MBC8-005 — Mode A backward-compat default
# ---------------------------------------------------------------------------


class TestModeADefaultBackwardCompat:
    """TASK-MBC8-005 AC-001 — existing Mode A callers see no change.

    The ``mode`` parameter is additive: callers that omit it continue to
    receive the Mode A behaviour byte-for-byte, exercised here by the
    same per-stage assertions as the Mode A test classes above but
    without ever mentioning ``BuildMode.MODE_A`` at the callsite.
    """

    def test_mode_a_caller_default_matches_explicit_mode_a(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # Mode A path: AUTOBUILD ← FEATURE_PLAN.
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan.md",),
                artefact_text=None,
            )
        )

        default_entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
        )
        explicit_entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
            mode=BuildMode.MODE_A,
        )

        assert default_entries == explicit_entries
        assert default_entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/plan.md",
                kind="path",
            )
        ]

    def test_mode_a_default_does_not_raise_on_pre_feature_spec_stages(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """Mode A still threads context through SYSTEM_DESIGN, ARCHITECT, etc."""
        # Sanity: the four Mode B forbidden stages are perfectly legal in
        # Mode A and must not raise ModeBoundaryViolation when called
        # under the default (Mode A) mode.
        reader.entries[("build-1", StageClass.PRODUCT_OWNER, None)] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="charter",
            )
        )
        # ARCHITECT consumes PRODUCT_OWNER — must succeed under Mode A.
        entries = builder.build_for(
            stage=StageClass.ARCHITECT,
            build_id="build-1",
            feature_id=None,
        )
        assert entries == [ContextEntry(flag="--context", value="charter", kind="text")]


# ---------------------------------------------------------------------------
# TASK-MBC8-005 AC-002 — Mode B contracts
# ---------------------------------------------------------------------------


class TestModeBContracts:
    """TASK-MBC8-005 AC-002 — Mode B propagation rows.

    Three contract rows per FEAT-FORGE-008 Group A:

        1. FEATURE_PLAN ← FEATURE_SPEC artefact paths
        2. AUTOBUILD    ← FEATURE_PLAN artefact paths
        3. PR_REVIEW    ← AUTOBUILD branch ref + commit summary (text)

    Mode B's pre-``feature-spec`` stages
    (:data:`MODE_B_FORBIDDEN_STAGES`) raise :class:`ModeBoundaryViolation`.
    """

    def test_mode_b_feature_plan_receives_feature_spec_artefact_paths(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """FEATURE_PLAN consumes the approved /feature-spec artefact path."""
        reader.entries[("build-1", StageClass.FEATURE_SPEC, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/spec.md",),
                artefact_text=None,
            )
        )

        entries = builder.build_for(
            stage=StageClass.FEATURE_PLAN,
            build_id="build-1",
            feature_id="FEAT-1",
            mode=BuildMode.MODE_B,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/spec.md",
                kind="path",
            )
        ]

    def test_mode_b_autobuild_receives_feature_plan_artefact_paths(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """AUTOBUILD consumes the approved /feature-plan artefact path."""
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/plan.md",),
                artefact_text=None,
            )
        )

        entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
            mode=BuildMode.MODE_B,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/plan.md",
                kind="path",
            )
        ]

    def test_mode_b_pull_request_review_receives_autobuild_text(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        """PULL_REQUEST_REVIEW consumes AUTOBUILD's text (branch ref + summary)."""
        reader.entries[("build-1", StageClass.AUTOBUILD, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="branch=feature/FEAT-1 commits=3",
            )
        )

        entries = builder.build_for(
            stage=StageClass.PULL_REQUEST_REVIEW,
            build_id="build-1",
            feature_id="FEAT-1",
            mode=BuildMode.MODE_B,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="branch=feature/FEAT-1 commits=3",
                kind="text",
            )
        ]

    @pytest.mark.parametrize("forbidden_stage", sorted(MODE_B_FORBIDDEN_STAGES))
    def test_mode_b_forbidden_stages_raise_mode_boundary_violation(
        self,
        forbidden_stage: StageClass,
        builder: ForwardContextBuilder,
    ) -> None:
        """ASSUM-013/ASSUM-014: Mode B refuses to thread context for the
        four pre-``feature-spec`` Mode A stages."""
        with pytest.raises(ModeBoundaryViolation) as excinfo:
            builder.build_for(
                stage=forbidden_stage,
                build_id="build-1",
                feature_id=None,
                mode=BuildMode.MODE_B,
            )
        assert excinfo.value.stage is forbidden_stage
        assert excinfo.value.mode is BuildMode.MODE_B
        # The exception message names both the stage and the mode so
        # operators can grep the log without spelunking the traceback.
        msg = str(excinfo.value)
        assert forbidden_stage.value in msg
        assert BuildMode.MODE_B.value in msg

    def test_mode_b_feature_spec_entry_stage_returns_empty(
        self,
        builder: ForwardContextBuilder,
    ) -> None:
        """FEATURE_SPEC is the Mode B entry stage — no upstream to propagate."""
        entries = builder.build_for(
            stage=StageClass.FEATURE_SPEC,
            build_id="build-1",
            feature_id="FEAT-1",
            mode=BuildMode.MODE_B,
        )
        assert entries == []

    def test_mode_b_contract_map_is_strict_subset_of_mode_a(self) -> None:
        """Mode B's contract is a strict subset of the Mode A suffix.

        Each Mode B row's producer stage must match the matching Mode A
        row's producer stage — the propagation shape is identical, only
        the description differs (``(Mode B) ...`` tag for audit logs).
        """
        for stage, mode_b_recipe in MODE_B_PROPAGATION_CONTRACT.items():
            assert stage in PROPAGATION_CONTRACT, (
                f"Mode B stage {stage!r} is not in the Mode A contract — "
                f"Mode B should be a strict subset"
            )
            mode_a_recipe = PROPAGATION_CONTRACT[stage]
            assert mode_b_recipe.producer_stage == mode_a_recipe.producer_stage
            assert mode_b_recipe.artefact_kind == mode_a_recipe.artefact_kind
            assert mode_b_recipe.context_flag == mode_a_recipe.context_flag


# ---------------------------------------------------------------------------
# TASK-MBC8-005 AC-003 — Mode C contracts (TASK_WORK + follow-up TASK_REVIEW)
# ---------------------------------------------------------------------------


class TestModeCTaskWorkContract:
    """TASK-MBC8-005 AC-004 — Mode C ``/task-work`` dispatch.

    Each ``/task-work`` is dispatched with:

    1. A ``--fix-task`` text entry carrying ``FixTaskRef.to_json()``
       (Group A: "Each /task-work dispatch is supplied with the
       fix-task definition produced by /task-review").
    2. One ``--context`` path entry per allow-listed
       ``/task-review`` artefact path (Group L lineage anchor).
    """

    def test_mode_c_task_work_emits_fix_task_text_entry(
        self,
        builder: ForwardContextBuilder,
    ) -> None:
        fix_task = FixTaskRef(
            fix_task_id="FIX-001",
            task_review_entry_id="task-review-2026-04-27T12:00:00Z",
            review_artefact_paths=(),
        )

        entries = builder.build_for(
            stage=StageClass.TASK_WORK,
            build_id="build-1",
            feature_id=None,
            mode=BuildMode.MODE_C,
            fix_task=fix_task,
        )

        assert entries == [
            ContextEntry(
                flag="--fix-task",
                value=fix_task.to_json(),
                kind="text",
            )
        ]
        # The serialised JSON must be deterministic and parseable so the
        # downstream dispatcher can decode it without ambiguity.
        decoded = json.loads(entries[0].value)
        assert decoded == {
            "fix_task_id": "FIX-001",
            "task_review_entry_id": "task-review-2026-04-27T12:00:00Z",
            "review_artefact_paths": [],
        }

    def test_mode_c_task_work_emits_review_artefact_paths(
        self,
        builder: ForwardContextBuilder,
    ) -> None:
        fix_task = FixTaskRef(
            fix_task_id="FIX-001",
            task_review_entry_id="task-review-2026-04-27T12:00:00Z",
            review_artefact_paths=(
                "/work/build-1/review/findings.md",
                "/work/build-1/review/diff.patch",
            ),
        )

        entries = builder.build_for(
            stage=StageClass.TASK_WORK,
            build_id="build-1",
            feature_id=None,
            mode=BuildMode.MODE_C,
            fix_task=fix_task,
        )

        # First entry: the FixTaskRef JSON. Subsequent entries: the
        # allow-listed review paths in order.
        assert entries[0].flag == "--fix-task"
        assert entries[0].kind == "text"
        assert entries[1:] == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/review/findings.md",
                kind="path",
            ),
            ContextEntry(
                flag="--context",
                value="/work/build-1/review/diff.patch",
                kind="path",
            ),
        ]

    def test_mode_c_task_work_filters_review_paths_outside_allowlist(
        self,
        builder: ForwardContextBuilder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fix_task = FixTaskRef(
            fix_task_id="FIX-001",
            task_review_entry_id="task-review-1",
            review_artefact_paths=(
                "/work/build-1/review/findings.md",  # allowed
                "/etc/passwd",  # outside — must be filtered
            ),
        )

        with caplog.at_level(
            logging.WARNING, logger="forge.pipeline.forward_context_builder"
        ):
            entries = builder.build_for(
                stage=StageClass.TASK_WORK,
                build_id="build-1",
                feature_id=None,
                mode=BuildMode.MODE_C,
                fix_task=fix_task,
            )

        # Only the FixTaskRef text entry plus the allow-listed path
        # survive; the rejected path is filtered with a structured warning.
        assert len(entries) == 2
        assert entries[1].value == "/work/build-1/review/findings.md"
        assert any(
            "/etc/passwd" in record.getMessage() and "FIX-001" in record.getMessage()
            for record in caplog.records
        ), "expected structured warning for path outside allowlist"

    def test_mode_c_task_work_without_fix_task_returns_empty(
        self,
        builder: ForwardContextBuilder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Mode C TASK_WORK without a FixTaskRef is a planner bug → safe empty."""
        with caplog.at_level(
            logging.WARNING, logger="forge.pipeline.forward_context_builder"
        ):
            entries = builder.build_for(
                stage=StageClass.TASK_WORK,
                build_id="build-1",
                feature_id=None,
                mode=BuildMode.MODE_C,
                fix_task=None,
            )
        assert entries == []
        assert any(
            "TASK_WORK" in record.getMessage() and "fix_task" in record.getMessage()
            for record in caplog.records
        ), "expected warning for missing fix_task"


class TestModeCFollowupTaskReviewContract:
    """TASK-MBC8-005 AC-005 — Mode C follow-up ``/task-review`` dispatch.

    Receives the artefact paths from every completed ``/task-work`` in
    the cycle so the reviewer can judge the applied fixes.
    """

    def test_followup_review_receives_paths_from_every_completed_task_work(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
    ) -> None:
        # Three /task-work dispatches all approved in the cycle.
        reader.multi_entries[("build-1", StageClass.TASK_WORK, None)] = [
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/task-work/FIX-001/result.md",),
                artefact_text=None,
            ),
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/task-work/FIX-002/result.md",),
                artefact_text=None,
            ),
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=("/work/build-1/task-work/FIX-003/result.md",),
                artefact_text=None,
            ),
        ]

        entries = builder.build_for(
            stage=StageClass.TASK_REVIEW,
            build_id="build-1",
            feature_id=None,
            mode=BuildMode.MODE_C,
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/task-work/FIX-001/result.md",
                kind="path",
            ),
            ContextEntry(
                flag="--context",
                value="/work/build-1/task-work/FIX-002/result.md",
                kind="path",
            ),
            ContextEntry(
                flag="--context",
                value="/work/build-1/task-work/FIX-003/result.md",
                kind="path",
            ),
        ]

    def test_followup_review_with_no_completed_task_work_returns_empty(
        self,
        builder: ForwardContextBuilder,
    ) -> None:
        """An initial /task-review with zero history yields empty context."""
        entries = builder.build_for(
            stage=StageClass.TASK_REVIEW,
            build_id="build-1",
            feature_id=None,
            mode=BuildMode.MODE_C,
        )
        assert entries == []

    def test_followup_review_filters_task_work_paths_outside_allowlist(
        self,
        reader: FakeStageLogReader,
        builder: ForwardContextBuilder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        reader.multi_entries[("build-1", StageClass.TASK_WORK, None)] = [
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(
                    "/work/build-1/task-work/FIX-001/result.md",  # allowed
                    "/tmp/leaked.md",  # outside
                ),
                artefact_text=None,
            ),
        ]

        with caplog.at_level(
            logging.WARNING, logger="forge.pipeline.forward_context_builder"
        ):
            entries = builder.build_for(
                stage=StageClass.TASK_REVIEW,
                build_id="build-1",
                feature_id=None,
                mode=BuildMode.MODE_C,
            )

        assert entries == [
            ContextEntry(
                flag="--context",
                value="/work/build-1/task-work/FIX-001/result.md",
                kind="path",
            )
        ]
        assert any(
            "/tmp/leaked.md" in record.getMessage() for record in caplog.records
        ), "expected structured warning for path outside allowlist"


# ---------------------------------------------------------------------------
# TASK-MBC8-005 — FixTaskRef serialisation contract
# ---------------------------------------------------------------------------


class TestFixTaskRefSerialisation:
    """``FixTaskRef.to_json()`` is the audit-anchor payload for Group L.

    The serialisation is exercised by the Mode C TASK_WORK tests above,
    but explicit coverage of the contract here makes the byte-stable
    shape easy to grep when downstream code parses the JSON.
    """

    def test_to_json_emits_sorted_keys(self) -> None:
        ref = FixTaskRef(
            fix_task_id="FIX-001",
            task_review_entry_id="task-review-1",
            review_artefact_paths=("/p/a", "/p/b"),
        )
        payload = ref.to_json()
        # sort_keys=True makes the JSON byte-stable so log diffing works.
        assert payload == (
            '{"fix_task_id": "FIX-001", '
            '"review_artefact_paths": ["/p/a", "/p/b"], '
            '"task_review_entry_id": "task-review-1"}'
        )

    def test_to_json_round_trips_through_loads(self) -> None:
        ref = FixTaskRef(
            fix_task_id="FIX-002",
            task_review_entry_id="task-review-7",
            review_artefact_paths=("/work/r1.md", "/work/r2.md"),
        )
        decoded = json.loads(ref.to_json())
        assert decoded == {
            "fix_task_id": "FIX-002",
            "task_review_entry_id": "task-review-7",
            "review_artefact_paths": ["/work/r1.md", "/work/r2.md"],
        }

    def test_fix_task_ref_is_frozen(self) -> None:
        """Value object: must be immutable so it can be safely shared."""
        ref = FixTaskRef(
            fix_task_id="FIX-001",
            task_review_entry_id="task-review-1",
        )
        with pytest.raises((AttributeError, TypeError)):
            ref.fix_task_id = "FIX-XXX"  # type: ignore[misc]
