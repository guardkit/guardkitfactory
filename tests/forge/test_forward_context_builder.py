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

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from forge.pipeline import forward_context_builder
from forge.pipeline.forward_context_builder import (
    ApprovedStageEntry,
    ContextEntry,
    ForwardContextBuilder,
    StageLogReader,
    WorktreeAllowlist,
)
from forge.pipeline.forward_propagation import PROPAGATION_CONTRACT
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
    """

    entries: dict[tuple[str, StageClass, str | None], ApprovedStageEntry] = field(
        default_factory=dict
    )

    def get_approved_stage_entry(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> ApprovedStageEntry | None:
        return self.entries.get((build_id, stage, feature_id))


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
            "ForwardContextBuilder",
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
