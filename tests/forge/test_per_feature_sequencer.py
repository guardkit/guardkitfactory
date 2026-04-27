"""Tests for ``forge.pipeline.per_feature_sequencer`` (TASK-MAG7-005).

Validates the :class:`PerFeatureLoopSequencer` — the pure-function sequencer
that refuses to permit a second feature's autobuild dispatch while any
earlier feature's autobuild remains in a non-terminal lifecycle on the same
build (FEAT-FORGE-007 ASSUM-006).

Test cases mirror the acceptance criteria of TASK-MAG7-005 one-for-one and
the Group D edge-case scenario "Per-feature inner loops are sequenced so
each feature's autobuild completes before the next feature's autobuild
begins". Each failing assertion points at the criterion it violates.

Both reader Protocols (``StageLogReader``, ``AsyncTaskReader``) are
satisfied by in-memory test doubles so the suite runs without SQLite or
the LangGraph state channel — that is the whole point of the
"pure function — no I/O except via injected reader Protocols" criterion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pytest

from forge.pipeline.per_feature_sequencer import (
    NON_TERMINAL_AUTOBUILD_LIFECYCLES,
    TERMINAL_AUTOBUILD_LIFECYCLES,
    AsyncTaskReader,
    PerFeatureLoopSequencer,
    StageLogReader,
)


# ---------------------------------------------------------------------------
# Test doubles — in-memory fakes for the two injected Protocols
# ---------------------------------------------------------------------------


@dataclass
class FakeAutobuildState:
    """Structural stand-in for DDR-006 ``AutobuildState``.

    Only the two fields the sequencer reads (``feature_id``, ``lifecycle``)
    are required by the :class:`AsyncTaskReader` Protocol, so the test
    double stays minimal. Production wires the full Pydantic model from
    ``forge.subagents.autobuild_runner``.
    """

    feature_id: str
    lifecycle: str


@dataclass
class FakeStageLogReader:
    """In-memory :class:`StageLogReader`.

    The fake stores a set of ``(build_id, feature_id)`` tuples that
    represent autobuild stage rows recorded as approved in ``stage_log``.
    The production reader is the FEAT-FORGE-001 SQLite adapter; tests use
    this fake to avoid bringing up SQLite for a pure-function test.
    """

    approved_autobuilds: set[tuple[str, str]] = field(default_factory=set)

    def is_autobuild_approved(self, build_id: str, feature_id: str) -> bool:
        return (build_id, feature_id) in self.approved_autobuilds


@dataclass
class FakeAsyncTaskReader:
    """In-memory :class:`AsyncTaskReader`.

    Stores a list of :class:`FakeAutobuildState` per ``build_id`` so tests
    can shape the live ``async_tasks`` channel however the scenario
    requires. The production reader is the LangGraph
    :class:`AsyncSubAgentMiddleware` ``async_tasks`` state channel.
    """

    states_by_build: dict[str, list[FakeAutobuildState]] = field(
        default_factory=dict
    )

    def list_autobuild_states(
        self, build_id: str
    ) -> Iterable[FakeAutobuildState]:
        return list(self.states_by_build.get(build_id, []))


# ---------------------------------------------------------------------------
# AC-001 — class & module location
# ---------------------------------------------------------------------------


class TestPerFeatureLoopSequencerExists:
    """AC-001 — ``PerFeatureLoopSequencer`` class exists at the right path."""

    def test_class_importable_from_per_feature_sequencer_module(self) -> None:
        from forge.pipeline import per_feature_sequencer

        assert hasattr(per_feature_sequencer, "PerFeatureLoopSequencer")

    def test_class_is_instantiable_with_no_arguments(self) -> None:
        sequencer = PerFeatureLoopSequencer()
        assert isinstance(sequencer, PerFeatureLoopSequencer)


# ---------------------------------------------------------------------------
# AC-002 — non-terminal lifecycles block dispatch
# ---------------------------------------------------------------------------


class TestNonTerminalLifecyclesBlockDispatch:
    """AC-002 — second feature autobuild blocked while prior is non-terminal."""

    @pytest.mark.parametrize(
        "lifecycle",
        [
            "starting",
            "planning_waves",
            "running_wave",
            "awaiting_approval",
            "pushing_pr",
        ],
    )
    def test_prior_feature_in_non_terminal_lifecycle_blocks_second_feature(
        self, lifecycle: str
    ) -> None:
        # Arrange — two-feature catalogue, prior feature is non-terminal.
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle=lifecycle
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        # Act — supervisor asks "may I dispatch autobuild for FEAT-2?".
        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-2",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        # Assert — sequencer refuses; FEAT-1 is still in flight.
        assert permitted is False, (
            f"lifecycle={lifecycle!r} is non-terminal — should block "
            "FEAT-2 dispatch"
        )

    def test_running_wave_lifecycle_blocks_second_feature_two_feature_catalogue(
        self,
    ) -> None:
        """AC-005 — explicit two-feature, ``running_wave`` scenario."""
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="running_wave"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-2",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is False


# ---------------------------------------------------------------------------
# AC-006 — terminal lifecycles permit dispatch
# ---------------------------------------------------------------------------


class TestTerminalLifecyclesPermitDispatch:
    """AC-006 — second autobuild permitted once first reaches a terminal state."""

    @pytest.mark.parametrize(
        "lifecycle",
        ["completed", "cancelled", "failed"],
    )
    def test_prior_feature_in_terminal_lifecycle_permits_second_feature(
        self, lifecycle: str
    ) -> None:
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle=lifecycle
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-2",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True, (
            f"lifecycle={lifecycle!r} is terminal — should permit "
            "FEAT-2 dispatch"
        )

    def test_completed_lifecycle_permits_second_feature_two_feature_catalogue(
        self,
    ) -> None:
        """AC-006 — explicit "first reaches completed" scenario."""
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="completed"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader(
            approved_autobuilds={("build-1", "FEAT-1")},
        )
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-2",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True


# ---------------------------------------------------------------------------
# AC-003 / AC-004 — consults both stage_log AND async_tasks
# ---------------------------------------------------------------------------


class TestStageLogAndAsyncTaskConsultation:
    """AC-003/AC-004 — sequencer consults stage_log AND async_tasks."""

    def test_no_in_flight_autobuilds_permits_dispatch(self) -> None:
        """AC-004 — empty async_tasks + empty stage_log permits dispatch."""
        async_task_reader = FakeAsyncTaskReader()
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-1",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True

    def test_stale_async_task_overridden_by_stage_log_approval(self) -> None:
        """AC-003 — if stage_log says approved, stale non-terminal async_task entry is ignored.

        DDR-006 states the async_tasks channel is *advisory* and SQLite is
        authoritative for terminal state. If async_tasks still shows a
        non-terminal lifecycle but stage_log already records the autobuild
        as approved, the stage_log truth wins and dispatch is permitted.
        """
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="running_wave"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader(
            approved_autobuilds={("build-1", "FEAT-1")},
        )
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-2",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True

    def test_self_feature_id_excluded_from_check(self) -> None:
        """The feature requesting dispatch is not blocked by its own state."""
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="running_wave"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        # The supervisor is asking "may I dispatch FEAT-1's autobuild?"
        # — even though FEAT-1 is shown running, we do not block ourselves.
        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-1",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True


# ---------------------------------------------------------------------------
# Build isolation — concurrent builds (different build_ids) are unaffected
# ---------------------------------------------------------------------------


class TestBuildIsolation:
    """FEAT-FORGE-007 Group F — concurrent *builds* still hold."""

    def test_other_build_in_flight_does_not_block_dispatch(self) -> None:
        """A non-terminal autobuild in build-2 cannot block a feature in build-1."""
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-2": [
                    FakeAutobuildState(
                        feature_id="FEAT-X", lifecycle="running_wave"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader()
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-1",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True


# ---------------------------------------------------------------------------
# Multi-feature catalogue — at least one earlier feature still in flight
# ---------------------------------------------------------------------------


class TestMultiFeatureCatalogue:
    """Three-feature catalogue: any single non-terminal earlier feature blocks."""

    def test_one_completed_one_running_blocks_third_feature(self) -> None:
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="completed"
                    ),
                    FakeAutobuildState(
                        feature_id="FEAT-2", lifecycle="running_wave"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader(
            approved_autobuilds={("build-1", "FEAT-1")},
        )
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-3",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is False

    def test_all_prior_features_completed_permits_third_feature(self) -> None:
        async_task_reader = FakeAsyncTaskReader(
            states_by_build={
                "build-1": [
                    FakeAutobuildState(
                        feature_id="FEAT-1", lifecycle="completed"
                    ),
                    FakeAutobuildState(
                        feature_id="FEAT-2", lifecycle="completed"
                    ),
                ],
            }
        )
        stage_log_reader = FakeStageLogReader(
            approved_autobuilds={
                ("build-1", "FEAT-1"),
                ("build-1", "FEAT-2"),
            },
        )
        sequencer = PerFeatureLoopSequencer()

        permitted = sequencer.may_start_autobuild(
            build_id="build-1",
            feature_id="FEAT-3",
            stage_log_reader=stage_log_reader,
            async_task_reader=async_task_reader,
        )

        assert permitted is True


# ---------------------------------------------------------------------------
# AC-007 — pure function: no I/O except via injected Protocols
# ---------------------------------------------------------------------------


class TestPureFunctionContract:
    """AC-007 — pure function, no I/O except via injected reader Protocols."""

    def test_protocols_are_runtime_checkable(self) -> None:
        """Both readers are :func:`typing.runtime_checkable` Protocols."""
        # The fake doubles structurally satisfy the Protocols; this is the
        # only "I/O" the sequencer is allowed to perform.
        assert isinstance(FakeStageLogReader(), StageLogReader)
        assert isinstance(FakeAsyncTaskReader(), AsyncTaskReader)

    def test_no_module_level_io_imports(self) -> None:
        """The sequencer module imports nothing that would touch I/O.

        Specifically it must not import ``sqlite3``, ``requests``,
        ``aiohttp``, or the ``forge.adapters`` package — anything that
        would open a network or filesystem handle at import time. The
        whole point of the Protocol injection is that the production
        wiring lives elsewhere. We inspect only the module's ``import``
        statements (via :mod:`ast`) so docstring mentions of those
        forbidden names — which are legitimate cross-references — do
        not trip the check.
        """
        import ast
        from pathlib import Path

        import forge.pipeline.per_feature_sequencer as module

        forbidden_prefixes = (
            "sqlite3",
            "requests",
            "aiohttp",
            "forge.adapters",
        )
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_names.append(node.module)

        for name in imported_names:
            for prefix in forbidden_prefixes:
                assert not (name == prefix or name.startswith(prefix + ".")), (
                    f"per_feature_sequencer imports {name!r} which is "
                    f"under the forbidden prefix {prefix!r} — I/O belongs "
                    "behind the injected Protocols"
                )


# ---------------------------------------------------------------------------
# Lifecycle constants — exposed for downstream callers (TASK-MAG7-010)
# ---------------------------------------------------------------------------


class TestLifecycleConstants:
    """``NON_TERMINAL_AUTOBUILD_LIFECYCLES`` mirrors AC-002 verbatim."""

    def test_non_terminal_lifecycles_match_acceptance_criterion(self) -> None:
        assert NON_TERMINAL_AUTOBUILD_LIFECYCLES == frozenset(
            {
                "starting",
                "planning_waves",
                "running_wave",
                "awaiting_approval",
                "pushing_pr",
            }
        )

    def test_terminal_lifecycles_match_ddr006(self) -> None:
        """Terminal lifecycles match DDR-006 ``AutobuildState.lifecycle`` literals."""
        assert TERMINAL_AUTOBUILD_LIFECYCLES == frozenset(
            {"completed", "cancelled", "failed"}
        )

    def test_terminal_and_non_terminal_partition_the_lifecycle_space(
        self,
    ) -> None:
        """The two sets are disjoint and together cover DDR-006's literals."""
        assert (
            NON_TERMINAL_AUTOBUILD_LIFECYCLES
            & TERMINAL_AUTOBUILD_LIFECYCLES
            == frozenset()
        )
        assert (
            NON_TERMINAL_AUTOBUILD_LIFECYCLES
            | TERMINAL_AUTOBUILD_LIFECYCLES
            == frozenset(
                {
                    "starting",
                    "planning_waves",
                    "running_wave",
                    "awaiting_approval",
                    "pushing_pr",
                    "completed",
                    "cancelled",
                    "failed",
                }
            )
        )
