"""Tests for ``forge.cli._serve_deps_forward_context`` (TASK-FW10-003).

Validates the production factory ``build_forward_context_builder`` that
binds :class:`forge.pipeline.forward_context_builder.ForwardContextBuilder`
to a SQLite-backed :class:`StageLogReader` and a :class:`WorktreeAllowlist`
sourced from ``forge_config.permissions.filesystem.allowlist``.

Test coverage maps one-to-one onto the TASK-FW10-003 acceptance criteria:

- AC-001 — ``build_forward_context_builder(sqlite_pool, forge_config)``
  returns a Protocol-conforming :class:`ForwardContextBuilder`.
- AC-002 — Allowlist enforcement happens before the builder returns:
  artefact paths inside the configured allowlist are threaded onto
  ``--context`` entries; paths outside are filtered out (defence-in-depth
  rejection that the caller can translate into a ``build-failed``
  envelope per TASK-FW10-009).
- AC-003 — Happy path: the factory wires the SQLite reader through so
  the returned builder round-trips a request against a fixture
  ``StageLogReader`` and returns the expected :class:`ContextEntry`.
- AC-003 — Rejected path: a worktree path outside the allowlist is
  rejected before the builder returns the context (filtered out), even
  when the SQLite reader has the matching approved row.

The SQLite reader is satisfied by an in-memory test double mirroring
the shape used in ``tests/forge/test_forward_context_builder.py`` — the
factory does not care whether its ``sqlite_pool`` argument is a live
pool or a fake, it only requires the :class:`StageLogReader` Protocol
surface (``get_approved_stage_entry``, ``get_all_approved_stage_entries``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from forge.cli._serve_deps_forward_context import (
    build_forward_context_builder,
)
from forge.config.models import (
    FilesystemPermissions,
    ForgeConfig,
    PermissionsConfig,
)
from forge.pipeline.forward_context_builder import (
    ApprovedStageEntry,
    ContextEntry,
    ForwardContextBuilder,
    WorktreeAllowlist,
)
from forge.pipeline.stage_taxonomy import StageClass


# ---------------------------------------------------------------------------
# In-memory fake — mirrors ``tests/forge/test_forward_context_builder.py``
# ---------------------------------------------------------------------------


@dataclass
class FakeStageLogReader:
    """In-memory :class:`StageLogReader` used as the ``sqlite_pool`` argument.

    The factory does not care whether its first argument is a live SQLite
    connection pool or a fake — it only requires the
    :class:`StageLogReader` Protocol surface. Production wires the
    FEAT-FORGE-001 SQLite adapter; this fake stands in so the unit suite
    runs without SQLite. Any lookup that does not hit a stored entry
    returns ``None`` (or the empty sequence for the multi accessor),
    modelling either "no row yet" or "row present but not yet approved".
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_forge_config(allowlist: list[Path]) -> ForgeConfig:
    """Build a minimal :class:`ForgeConfig` with a filesystem allowlist."""
    return ForgeConfig(
        permissions=PermissionsConfig(
            filesystem=FilesystemPermissions(allowlist=allowlist),
        ),
    )


@pytest.fixture
def reader() -> FakeStageLogReader:
    return FakeStageLogReader()


@pytest.fixture
def worktree_root(tmp_path: Path) -> Path:
    """An absolute, real worktree root that sits inside the allowlist."""
    root = tmp_path / "build-1"
    root.mkdir()
    return root


@pytest.fixture
def forge_config(worktree_root: Path) -> ForgeConfig:
    """A :class:`ForgeConfig` with ``worktree_root`` on the filesystem allowlist."""
    return _make_forge_config([worktree_root])


# ---------------------------------------------------------------------------
# AC-001 — Factory shape
# ---------------------------------------------------------------------------


class TestFactoryShape:
    """AC-001 — factory returns a Protocol-conforming :class:`ForwardContextBuilder`."""

    def test_factory_returns_forward_context_builder_instance(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
    ) -> None:
        builder = build_forward_context_builder(reader, forge_config)

        assert isinstance(builder, ForwardContextBuilder)

    def test_factory_signature_accepts_sqlite_pool_and_forge_config(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
    ) -> None:
        # Both positional and keyword forms must work — production
        # callers wire by keyword for clarity, but tests sometimes
        # pass positionally.
        builder_positional = build_forward_context_builder(reader, forge_config)
        builder_keyword = build_forward_context_builder(
            sqlite_pool=reader, forge_config=forge_config
        )

        assert isinstance(builder_positional, ForwardContextBuilder)
        assert isinstance(builder_keyword, ForwardContextBuilder)


# ---------------------------------------------------------------------------
# AC-002 — Worktree allowlist Protocol surface
# ---------------------------------------------------------------------------


class TestAllowlistAdapter:
    """AC-002 — the bound allowlist conforms to :class:`WorktreeAllowlist`."""

    def test_allowlist_attribute_is_worktree_allowlist_protocol(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
    ) -> None:
        builder = build_forward_context_builder(reader, forge_config)

        # ForwardContextBuilder stores the allowlist on a private
        # attribute; we validate via the Protocol contract rather than
        # by name so internal renames don't break the test.
        allowlist = builder._allowlist  # noqa: SLF001 — Protocol assertion
        assert isinstance(allowlist, WorktreeAllowlist)

    def test_path_under_allowlist_root_is_allowed(
        self,
        reader: FakeStageLogReader,
        worktree_root: Path,
        forge_config: ForgeConfig,
    ) -> None:
        builder = build_forward_context_builder(reader, forge_config)

        nested = worktree_root / "plan.md"
        assert builder._allowlist.is_allowed(  # noqa: SLF001
            "build-1", str(nested)
        )

    def test_allowlist_root_itself_is_allowed(
        self,
        reader: FakeStageLogReader,
        worktree_root: Path,
        forge_config: ForgeConfig,
    ) -> None:
        builder = build_forward_context_builder(reader, forge_config)

        assert builder._allowlist.is_allowed(  # noqa: SLF001
            "build-1", str(worktree_root)
        )

    def test_path_outside_allowlist_is_rejected(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
        tmp_path: Path,
    ) -> None:
        builder = build_forward_context_builder(reader, forge_config)

        outside = tmp_path / "other-root" / "leak.md"
        assert not builder._allowlist.is_allowed(  # noqa: SLF001
            "build-1", str(outside)
        )

    def test_empty_allowlist_rejects_every_path(
        self,
        reader: FakeStageLogReader,
        worktree_root: Path,
    ) -> None:
        config = _make_forge_config(allowlist=[])

        builder = build_forward_context_builder(reader, config)

        assert not builder._allowlist.is_allowed(  # noqa: SLF001
            "build-1", str(worktree_root / "plan.md")
        )

    def test_sibling_path_with_shared_prefix_is_not_allowed(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
        worktree_root: Path,
    ) -> None:
        """A sibling whose path string shares the allowlist root's textual
        prefix (``/tmp/.../build-1`` vs ``/tmp/.../build-12345``) must be
        rejected. Naive ``str.startswith`` would let it through; the
        adapter must split on the path boundary.
        """
        builder = build_forward_context_builder(reader, forge_config)

        sibling = worktree_root.parent / (worktree_root.name + "-extra") / "plan.md"
        assert not builder._allowlist.is_allowed(  # noqa: SLF001
            "build-1", str(sibling)
        )


# ---------------------------------------------------------------------------
# AC-003 — Happy path round-trip via SQLite reader fixture
# ---------------------------------------------------------------------------


class TestRoundTripHappyPath:
    """AC-003 — allowed worktree path → context returned to caller."""

    def test_builder_returns_path_entry_when_path_inside_allowlist(
        self,
        reader: FakeStageLogReader,
        worktree_root: Path,
        forge_config: ForgeConfig,
    ) -> None:
        # Approved FEATURE_PLAN row points at a path inside the
        # configured worktree allowlist — the builder must thread it
        # through to the AUTOBUILD dispatch.
        plan_path = worktree_root / "plan.md"
        plan_path.write_text("plan body", encoding="utf-8")
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(str(plan_path),),
                artefact_text=None,
            )
        )

        builder = build_forward_context_builder(reader, forge_config)

        entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
        )

        assert entries == [
            ContextEntry(
                flag="--context",
                value=str(plan_path),
                kind="path",
            )
        ]

    def test_builder_round_trips_text_artefact_through_factory_wired_reader(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
    ) -> None:
        # Text-kind artefacts bypass the allowlist (no path to gate);
        # this exercises the ``sqlite_pool`` path through the factory.
        reader.entries[("build-1", StageClass.PRODUCT_OWNER, None)] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(),
                artefact_text="The product charter.",
            )
        )

        builder = build_forward_context_builder(reader, forge_config)

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


# ---------------------------------------------------------------------------
# AC-003 — Rejected path: outside-allowlist artefact filtered before return
# ---------------------------------------------------------------------------


class TestAllowlistRejection:
    """AC-002 / AC-003 — disallowed worktree path → filtered before return.

    The builder filters outside-allowlist paths individually (rather than
    raising the whole call) and emits a structured warning. The rejection
    happens *before* the context is returned to the caller — a
    downstream caller (TASK-FW10-009) translates an empty / partial
    context into a ``build-failed`` envelope when the dispatch cannot
    proceed without the missing artefact.
    """

    def test_path_outside_allowlist_is_filtered_from_returned_context(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
        tmp_path: Path,
    ) -> None:
        # Approved row whose only artefact path lies outside the
        # configured allowlist root — the builder must NOT thread it.
        outside_path = tmp_path / "other-root" / "evil.md"
        outside_path.parent.mkdir(parents=True)
        outside_path.write_text("not safe to thread", encoding="utf-8")
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(str(outside_path),),
                artefact_text=None,
            )
        )

        builder = build_forward_context_builder(reader, forge_config)

        entries = builder.build_for(
            stage=StageClass.AUTOBUILD,
            build_id="build-1",
            feature_id="FEAT-1",
        )

        # Path filtered out — caller (TASK-FW10-009) translates an empty
        # forward context into a build-failed envelope.
        assert entries == []

    def test_path_outside_allowlist_emits_warning_log(
        self,
        reader: FakeStageLogReader,
        forge_config: ForgeConfig,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        outside_path = tmp_path / "other-root" / "evil.md"
        outside_path.parent.mkdir(parents=True)
        reader.entries[("build-1", StageClass.FEATURE_PLAN, "FEAT-1")] = (
            ApprovedStageEntry(
                gate_decision="approved",
                artefact_paths=(str(outside_path),),
                artefact_text=None,
            )
        )

        builder = build_forward_context_builder(reader, forge_config)

        with caplog.at_level(
            "WARNING", logger="forge.pipeline.forward_context_builder"
        ):
            builder.build_for(
                stage=StageClass.AUTOBUILD,
                build_id="build-1",
                feature_id="FEAT-1",
            )

        assert any(
            "outside worktree allowlist" in record.message
            and str(outside_path) in record.message
            for record in caplog.records
        ), "expected structured WARNING for allowlist-rejected path"

    def test_partial_path_list_filters_only_disallowed_entries(
        self,
        reader: FakeStageLogReader,
        worktree_root: Path,
        forge_config: ForgeConfig,
        tmp_path: Path,
    ) -> None:
        # SYSTEM_ARCH emits a path-list — the builder must keep allowed
        # entries and drop disallowed ones individually (per the
        # ForwardContextBuilder Protocol contract this factory wires up).
        allowed = worktree_root / "arch" / "good.md"
        allowed.parent.mkdir(parents=True)
        allowed.write_text("ok", encoding="utf-8")
        outside = tmp_path / "other-root" / "bad.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("nope", encoding="utf-8")
        reader.entries[("build-1", StageClass.SYSTEM_ARCH, None)] = ApprovedStageEntry(
            gate_decision="approved",
            artefact_paths=(str(allowed), str(outside)),
            artefact_text=None,
        )

        builder = build_forward_context_builder(reader, forge_config)

        entries = builder.build_for(
            stage=StageClass.SYSTEM_DESIGN,
            build_id="build-1",
            feature_id=None,
        )

        assert entries == [
            ContextEntry(flag="--context", value=str(allowed), kind="path"),
        ]


# ---------------------------------------------------------------------------
# Independence — factory does NOT import from ``_serve_deps``
# (TASK-FW10-007 owns composition; FW10 implementation note).
# ---------------------------------------------------------------------------


class TestModuleIndependence:
    """Implementation note — keep Wave 2 tasks free of cross-merge conflicts."""

    def test_module_does_not_import_serve_deps(self) -> None:
        from forge.cli import _serve_deps_forward_context

        source = Path(_serve_deps_forward_context.__file__).read_text(encoding="utf-8")
        assert "from forge.cli._serve_deps " not in source
        assert "import forge.cli._serve_deps " not in source
        # The composition module is owned by TASK-FW10-007.
