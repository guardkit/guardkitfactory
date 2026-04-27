"""Tests for ``forge.pipeline.mode_chains_data`` (TASK-MBC8-002).

Validates the Mode B and Mode C declarative chain data:

- :data:`MODE_B_CHAIN` — strict suffix of the Mode A chain
  (FEAT-FORGE-008 ASSUM-001).
- :data:`MODE_C_CHAIN` — cyclic chain
  (FEAT-FORGE-008 ASSUM-004).
- :data:`MODE_B_FORBIDDEN_STAGES`,
  :data:`MODE_C_FORBIDDEN_STAGES` — boundary enforcement
  (ASSUM-013, ASSUM-014).
- :data:`CHAIN_BY_MODE` — exhaustive map keyed by
  :class:`BuildMode`.
- :data:`MODE_B_PREREQUISITES`,
  :data:`MODE_C_PREREQUISITES` — same shape as
  :data:`STAGE_PREREQUISITES`.

Test cases mirror the acceptance criteria of TASK-MBC8-002 one-for-one
so a failing assertion points straight at the criterion it violates.
"""

from __future__ import annotations

import pytest

from forge.lifecycle.modes import BuildMode
from forge.pipeline import mode_chains_data
from forge.pipeline.mode_chains_data import (
    CHAIN_BY_MODE,
    MODE_A_CHAIN,
    MODE_B_CHAIN,
    MODE_B_FORBIDDEN_STAGES,
    MODE_B_PREREQUISITES,
    MODE_C_CHAIN,
    MODE_C_FORBIDDEN_STAGES,
    MODE_C_PREREQUISITES,
)
from forge.pipeline.stage_taxonomy import StageClass


class TestModuleStructure:
    """AC-001 — module exists at ``forge.pipeline.mode_chains_data`` and
    exports the required public symbols."""

    def test_module_path_is_forge_pipeline_mode_chains_data(self) -> None:
        assert (
            mode_chains_data.__name__ == "forge.pipeline.mode_chains_data"
        )

    def test_module_exports_all_required_symbols(self) -> None:
        required = {
            "MODE_A_CHAIN",
            "MODE_B_CHAIN",
            "MODE_C_CHAIN",
            "MODE_B_FORBIDDEN_STAGES",
            "MODE_C_FORBIDDEN_STAGES",
            "CHAIN_BY_MODE",
            "MODE_B_PREREQUISITES",
            "MODE_C_PREREQUISITES",
        }
        assert required.issubset(set(mode_chains_data.__all__))

    def test_module_has_no_sibling_pipeline_internal_imports(self) -> None:
        """The module is consumed by every Wave 2 planner; it must not
        introduce an import cycle.

        The only ``forge.pipeline`` import allowed is from
        :mod:`forge.pipeline.stage_taxonomy` (the canonical
        :class:`StageClass` enum, which itself is import-cycle-free).
        """
        from pathlib import Path

        source = Path(mode_chains_data.__file__).read_text(encoding="utf-8")
        forbidden = [
            "from forge.pipeline.stage_ordering_guard",
            "from forge.pipeline.constitutional_guard",
            "from forge.pipeline.supervisor",
            "from forge.pipeline.per_feature_sequencer",
            "from forge.pipeline.forward_propagation",
            "from forge.pipeline.forward_context_builder",
            "from forge.pipeline.cli_steering",
            "from forge.pipeline.dispatchers",
        ]
        for pattern in forbidden:
            assert pattern not in source, (
                f"mode_chains_data must not contain {pattern!r}"
            )


class TestModeBChain:
    """AC-002 — ``MODE_B_CHAIN`` matches FEAT-FORGE-008 ASSUM-001."""

    def test_mode_b_chain_is_a_tuple(self) -> None:
        assert isinstance(MODE_B_CHAIN, tuple)

    def test_mode_b_chain_exact_sequence(self) -> None:
        assert MODE_B_CHAIN == (
            StageClass.FEATURE_SPEC,
            StageClass.FEATURE_PLAN,
            StageClass.AUTOBUILD,
            StageClass.PULL_REQUEST_REVIEW,
        )

    def test_mode_b_chain_is_strict_suffix_of_mode_a(self) -> None:
        # ASSUM-001: Mode B is the Mode A chain starting at /feature-spec.
        spec_index = MODE_A_CHAIN.index(StageClass.FEATURE_SPEC)
        assert MODE_B_CHAIN == MODE_A_CHAIN[spec_index:]

    def test_mode_b_chain_excludes_pre_feature_spec_stages(self) -> None:
        for stage in (
            StageClass.PRODUCT_OWNER,
            StageClass.ARCHITECT,
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
        ):
            assert stage not in MODE_B_CHAIN

    def test_mode_b_chain_members_are_stageclass(self) -> None:
        for stage in MODE_B_CHAIN:
            assert isinstance(stage, StageClass)


class TestModeCChain:
    """AC-003 — ``MODE_C_CHAIN`` matches FEAT-FORGE-008 ASSUM-004."""

    def test_mode_c_chain_is_a_tuple(self) -> None:
        assert isinstance(MODE_C_CHAIN, tuple)

    def test_mode_c_chain_exact_sequence(self) -> None:
        assert MODE_C_CHAIN == (
            StageClass.TASK_REVIEW,
            StageClass.TASK_WORK,
            StageClass.PULL_REQUEST_REVIEW,
        )

    def test_mode_c_chain_is_length_three(self) -> None:
        # Per the implementation note, MODE_C_CHAIN is intentionally
        # length-3, not length-2: the per-fix-task fan-out of TASK_WORK
        # belongs to the cycle controller (TASK-MBC8-004), not the chain.
        assert len(MODE_C_CHAIN) == 3

    def test_mode_c_chain_members_are_stageclass(self) -> None:
        for stage in MODE_C_CHAIN:
            assert isinstance(stage, StageClass)

    def test_mode_c_chain_starts_with_task_review(self) -> None:
        assert MODE_C_CHAIN[0] is StageClass.TASK_REVIEW

    def test_mode_c_chain_terminates_at_pull_request_review(self) -> None:
        assert MODE_C_CHAIN[-1] is StageClass.PULL_REQUEST_REVIEW


class TestModeBForbiddenStages:
    """AC-004 — ``MODE_B_FORBIDDEN_STAGES`` is a frozenset of the four
    pre-feature-spec Mode A stages (ASSUM-013, ASSUM-014)."""

    def test_mode_b_forbidden_stages_is_frozenset(self) -> None:
        assert isinstance(MODE_B_FORBIDDEN_STAGES, frozenset)

    def test_mode_b_forbidden_stages_exact_membership(self) -> None:
        assert MODE_B_FORBIDDEN_STAGES == frozenset(
            {
                StageClass.PRODUCT_OWNER,
                StageClass.ARCHITECT,
                StageClass.SYSTEM_ARCH,
                StageClass.SYSTEM_DESIGN,
            }
        )

    def test_mode_b_forbidden_stages_disjoint_from_mode_b_chain(self) -> None:
        assert MODE_B_FORBIDDEN_STAGES.isdisjoint(MODE_B_CHAIN)


class TestModeCForbiddenStages:
    """AC-005 — ``MODE_C_FORBIDDEN_STAGES`` includes every Mode A
    pre-feature-spec stage plus FEATURE_SPEC, FEATURE_PLAN and
    AUTOBUILD (Mode C operates on existing artefacts)."""

    def test_mode_c_forbidden_stages_is_frozenset(self) -> None:
        assert isinstance(MODE_C_FORBIDDEN_STAGES, frozenset)

    def test_mode_c_forbidden_stages_exact_membership(self) -> None:
        assert MODE_C_FORBIDDEN_STAGES == frozenset(
            {
                StageClass.PRODUCT_OWNER,
                StageClass.ARCHITECT,
                StageClass.SYSTEM_ARCH,
                StageClass.SYSTEM_DESIGN,
                StageClass.FEATURE_SPEC,
                StageClass.FEATURE_PLAN,
                StageClass.AUTOBUILD,
            }
        )

    def test_mode_c_forbidden_stages_does_not_forbid_pull_request_review(
        self,
    ) -> None:
        # Mode C may culminate in PR review (ASSUM-005, ASSUM-011).
        assert StageClass.PULL_REQUEST_REVIEW not in MODE_C_FORBIDDEN_STAGES

    def test_mode_c_forbidden_stages_disjoint_from_mode_c_chain(self) -> None:
        assert MODE_C_FORBIDDEN_STAGES.isdisjoint(MODE_C_CHAIN)


class TestChainByMode:
    """AC-006 — ``CHAIN_BY_MODE`` maps every BuildMode to its chain."""

    def test_chain_by_mode_covers_every_build_mode(self) -> None:
        assert set(CHAIN_BY_MODE) == set(BuildMode)

    @pytest.mark.parametrize(
        ("mode", "expected_chain"),
        [
            (BuildMode.MODE_A, MODE_A_CHAIN),
            (BuildMode.MODE_B, MODE_B_CHAIN),
            (BuildMode.MODE_C, MODE_C_CHAIN),
        ],
    )
    def test_chain_by_mode_returns_expected_chain(
        self,
        mode: BuildMode,
        expected_chain: tuple[StageClass, ...],
    ) -> None:
        assert CHAIN_BY_MODE[mode] == expected_chain

    def test_chain_by_mode_mode_a_uses_existing_eight_stage_chain(
        self,
    ) -> None:
        # Mode A's chain remains the canonical eight-stage chain.
        assert CHAIN_BY_MODE[BuildMode.MODE_A] == (
            StageClass.PRODUCT_OWNER,
            StageClass.ARCHITECT,
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
            StageClass.FEATURE_SPEC,
            StageClass.FEATURE_PLAN,
            StageClass.AUTOBUILD,
            StageClass.PULL_REQUEST_REVIEW,
        )


class TestModeBPrerequisites:
    """AC-007 — ``MODE_B_PREREQUISITES`` is the Mode B subset of the
    Mode A prerequisite map."""

    def test_mode_b_prerequisites_is_a_dict(self) -> None:
        assert isinstance(MODE_B_PREREQUISITES, dict)

    def test_mode_b_prerequisites_has_three_entries(self) -> None:
        # Three downstream stages: feature-plan, autobuild,
        # pull-request-review. feature-spec is the entry stage.
        assert len(MODE_B_PREREQUISITES) == 3

    def test_mode_b_entry_stage_is_not_a_key(self) -> None:
        assert StageClass.FEATURE_SPEC not in MODE_B_PREREQUISITES

    @pytest.mark.parametrize(
        ("stage", "prereqs"),
        [
            (StageClass.FEATURE_PLAN, [StageClass.FEATURE_SPEC]),
            (StageClass.AUTOBUILD, [StageClass.FEATURE_PLAN]),
            (StageClass.PULL_REQUEST_REVIEW, [StageClass.AUTOBUILD]),
        ],
    )
    def test_mode_b_prerequisite_rows_match_chain(
        self,
        stage: StageClass,
        prereqs: list[StageClass],
    ) -> None:
        assert MODE_B_PREREQUISITES[stage] == prereqs

    def test_mode_b_prerequisites_keys_are_stageclass_in_chain(self) -> None:
        for key in MODE_B_PREREQUISITES:
            assert isinstance(key, StageClass)
            assert key in MODE_B_CHAIN

    def test_mode_b_prerequisites_values_are_lists_of_stageclass(self) -> None:
        for value in MODE_B_PREREQUISITES.values():
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, StageClass)


class TestModeCPrerequisites:
    """AC-008 — ``MODE_C_PREREQUISITES`` covers Mode C's three stage
    classes."""

    def test_mode_c_prerequisites_is_a_dict(self) -> None:
        assert isinstance(MODE_C_PREREQUISITES, dict)

    def test_mode_c_prerequisites_has_two_entries(self) -> None:
        # task-review is the entry stage; only task-work and
        # pull-request-review have prerequisites.
        assert len(MODE_C_PREREQUISITES) == 2

    def test_mode_c_entry_stage_is_not_a_key(self) -> None:
        assert StageClass.TASK_REVIEW not in MODE_C_PREREQUISITES

    @pytest.mark.parametrize(
        ("stage", "prereqs"),
        [
            (StageClass.TASK_WORK, [StageClass.TASK_REVIEW]),
            (StageClass.PULL_REQUEST_REVIEW, [StageClass.TASK_WORK]),
        ],
    )
    def test_mode_c_prerequisite_rows_match_acceptance_criteria(
        self,
        stage: StageClass,
        prereqs: list[StageClass],
    ) -> None:
        assert MODE_C_PREREQUISITES[stage] == prereqs

    def test_mode_c_prerequisites_keys_are_stageclass_in_chain(self) -> None:
        for key in MODE_C_PREREQUISITES:
            assert isinstance(key, StageClass)
            assert key in MODE_C_CHAIN

    def test_mode_c_prerequisites_values_are_lists_of_stageclass(self) -> None:
        for value in MODE_C_PREREQUISITES.values():
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, StageClass)


class TestModuleDocstring:
    """AC-009 — module docstring references FEAT-FORGE-008 ASSUM-001
    (Mode B chain), ASSUM-004 (Mode C chain), ASSUM-013 (mode-aware
    planning refuses upstream Mode A stages) and ASSUM-014 (Mode B does
    not dispatch to specialists)."""

    def test_module_docstring_present(self) -> None:
        assert mode_chains_data.__doc__ is not None
        assert mode_chains_data.__doc__.strip() != ""

    @pytest.mark.parametrize(
        "reference",
        [
            "FEAT-FORGE-008",
            "ASSUM-001",
            "ASSUM-004",
            "ASSUM-013",
            "ASSUM-014",
        ],
    )
    def test_module_docstring_references_required_anchor(
        self, reference: str
    ) -> None:
        assert mode_chains_data.__doc__ is not None
        assert reference in mode_chains_data.__doc__


class TestBuildModeEnum:
    """Sanity checks on :class:`BuildMode` consumed by this module."""

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (BuildMode.MODE_A, "mode-a"),
            (BuildMode.MODE_B, "mode-b"),
            (BuildMode.MODE_C, "mode-c"),
        ],
    )
    def test_build_mode_string_values(
        self, member: BuildMode, value: str
    ) -> None:
        assert member.value == value
        assert member == value  # StrEnum equality with raw str

    def test_build_mode_has_exactly_three_members(self) -> None:
        assert len(list(BuildMode)) == 3
