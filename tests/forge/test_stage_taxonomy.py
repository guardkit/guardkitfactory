"""Tests for ``forge.pipeline.stage_taxonomy`` (TASK-MAG7-001).

Validates the eight Mode A stage classes, the prerequisite map, and the
constitutional / per-feature stage frozensets that the rest of the
FEAT-FORGE-007 pipeline depends on.

The test cases mirror the acceptance criteria of TASK-MAG7-001 one-for-one
so a failing assertion points straight at the criterion it violates.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from forge.pipeline import stage_taxonomy
from forge.pipeline.stage_taxonomy import (
    CONSTITUTIONAL_STAGES,
    PER_FEATURE_STAGES,
    STAGE_PREREQUISITES,
    StageClass,
)


class TestStageClassEnum:
    """AC-002 — ``StageClass(StrEnum)`` member names, order, and values."""

    def test_stageclass_is_strenum_subclass(self) -> None:
        assert issubclass(StageClass, StrEnum)

    def test_stageclass_member_names_in_dispatch_order(self) -> None:
        expected = [
            "PRODUCT_OWNER",
            "ARCHITECT",
            "SYSTEM_ARCH",
            "SYSTEM_DESIGN",
            "FEATURE_SPEC",
            "FEATURE_PLAN",
            "AUTOBUILD",
            "PULL_REQUEST_REVIEW",
        ]
        assert [m.name for m in StageClass] == expected

    def test_stageclass_has_exactly_eight_members(self) -> None:
        assert len(list(StageClass)) == 8

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (StageClass.PRODUCT_OWNER, "product-owner"),
            (StageClass.ARCHITECT, "architect"),
            (StageClass.SYSTEM_ARCH, "system-arch"),
            (StageClass.SYSTEM_DESIGN, "system-design"),
            (StageClass.FEATURE_SPEC, "feature-spec"),
            (StageClass.FEATURE_PLAN, "feature-plan"),
            (StageClass.AUTOBUILD, "autobuild"),
            (StageClass.PULL_REQUEST_REVIEW, "pull-request-review"),
        ],
    )
    def test_stageclass_string_values_match_feature_file(
        self, member: StageClass, value: str
    ) -> None:
        assert member.value == value
        assert member == value  # StrEnum equality with raw str


class TestStagePrerequisites:
    """AC-003 — prerequisite map encodes the seven Group B rows."""

    def test_stage_prerequisites_has_exactly_seven_entries(self) -> None:
        assert len(STAGE_PREREQUISITES) == 7

    def test_product_owner_has_no_prerequisites_entry(self) -> None:
        # PRODUCT_OWNER is the entry stage; it must NOT appear as a key.
        assert StageClass.PRODUCT_OWNER not in STAGE_PREREQUISITES

    @pytest.mark.parametrize(
        ("stage", "prereqs"),
        [
            (StageClass.ARCHITECT, [StageClass.PRODUCT_OWNER]),
            (StageClass.SYSTEM_ARCH, [StageClass.ARCHITECT]),
            (StageClass.SYSTEM_DESIGN, [StageClass.SYSTEM_ARCH]),
            (StageClass.FEATURE_SPEC, [StageClass.SYSTEM_DESIGN]),
            (StageClass.FEATURE_PLAN, [StageClass.FEATURE_SPEC]),
            (StageClass.AUTOBUILD, [StageClass.FEATURE_PLAN]),
            (StageClass.PULL_REQUEST_REVIEW, [StageClass.AUTOBUILD]),
        ],
    )
    def test_each_prerequisite_row_matches_group_b_scenario_outline(
        self, stage: StageClass, prereqs: list[StageClass]
    ) -> None:
        assert STAGE_PREREQUISITES[stage] == prereqs

    def test_stage_prerequisites_keys_are_stageclass_members(self) -> None:
        for key in STAGE_PREREQUISITES:
            assert isinstance(key, StageClass)

    def test_stage_prerequisites_values_are_lists_of_stageclass(self) -> None:
        for value in STAGE_PREREQUISITES.values():
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, StageClass)


class TestConstitutionalStages:
    """AC-004 — ``CONSTITUTIONAL_STAGES`` frozenset (ADR-ARCH-026)."""

    def test_constitutional_stages_is_frozenset(self) -> None:
        assert isinstance(CONSTITUTIONAL_STAGES, frozenset)

    def test_constitutional_stages_contains_pull_request_review(self) -> None:
        assert StageClass.PULL_REQUEST_REVIEW in CONSTITUTIONAL_STAGES

    def test_constitutional_stages_is_exactly_pull_request_review(self) -> None:
        assert CONSTITUTIONAL_STAGES == frozenset({StageClass.PULL_REQUEST_REVIEW})


class TestPerFeatureStages:
    """AC-005 — ``PER_FEATURE_STAGES`` frozenset."""

    def test_per_feature_stages_is_frozenset(self) -> None:
        assert isinstance(PER_FEATURE_STAGES, frozenset)

    @pytest.mark.parametrize(
        "stage",
        [
            StageClass.FEATURE_SPEC,
            StageClass.FEATURE_PLAN,
            StageClass.AUTOBUILD,
            StageClass.PULL_REQUEST_REVIEW,
        ],
    )
    def test_per_feature_stages_contains_each_per_feature_stage(
        self, stage: StageClass
    ) -> None:
        assert stage in PER_FEATURE_STAGES

    def test_per_feature_stages_excludes_pipeline_wide_stages(self) -> None:
        for stage in (
            StageClass.PRODUCT_OWNER,
            StageClass.ARCHITECT,
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
        ):
            assert stage not in PER_FEATURE_STAGES

    def test_per_feature_stages_is_exactly_the_four_per_feature_members(
        self,
    ) -> None:
        assert PER_FEATURE_STAGES == frozenset(
            {
                StageClass.FEATURE_SPEC,
                StageClass.FEATURE_PLAN,
                StageClass.AUTOBUILD,
                StageClass.PULL_REQUEST_REVIEW,
            }
        )


class TestModuleDocstring:
    """AC-006 — module docstring references FEAT-FORGE-007 ASSUM-001 and ADR-ARCH-026."""

    def test_module_docstring_present(self) -> None:
        assert stage_taxonomy.__doc__ is not None
        assert stage_taxonomy.__doc__.strip() != ""

    def test_module_docstring_references_feat_forge_007_assum_001(self) -> None:
        assert "FEAT-FORGE-007" in stage_taxonomy.__doc__
        assert "ASSUM-001" in stage_taxonomy.__doc__

    def test_module_docstring_references_adr_arch_026(self) -> None:
        assert "ADR-ARCH-026" in stage_taxonomy.__doc__


class TestModuleStructure:
    """AC-001 — module exists and exports required symbols.

    AC-007 — module has no imports from other ``forge.pipeline`` submodules
    (TASK-MAG7-001 implementation note: "Keep it free of imports from any
    other ``forge.pipeline`` module so it can be imported by all downstream
    tasks in Waves 2–4 without a cycle").
    """

    def test_module_path_is_forge_pipeline_stage_taxonomy(self) -> None:
        assert stage_taxonomy.__name__ == "forge.pipeline.stage_taxonomy"

    def test_module_exports_all_public_symbols(self) -> None:
        assert set(stage_taxonomy.__all__) == {
            "StageClass",
            "STAGE_PREREQUISITES",
            "CONSTITUTIONAL_STAGES",
            "PER_FEATURE_STAGES",
        }

    def test_module_has_no_forge_pipeline_internal_imports(self) -> None:
        """No cycle-risking imports from sibling ``forge.pipeline.*`` modules."""
        from pathlib import Path

        source = Path(stage_taxonomy.__file__).read_text(encoding="utf-8")
        # The module must not import from any other forge.pipeline submodule.
        forbidden_substrings = [
            "from forge.pipeline.",
            "from forge.pipeline import",
            "import forge.pipeline.",
        ]
        for forbidden in forbidden_substrings:
            assert forbidden not in source, (
                f"stage_taxonomy must not contain {forbidden!r} "
                "(would create an import cycle for Waves 2–4)."
            )
