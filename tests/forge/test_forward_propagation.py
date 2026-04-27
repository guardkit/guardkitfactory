"""Tests for ``forge.pipeline.forward_propagation`` (TASK-MAG7-002).

Validates the seven-row forward-propagation contract that wires upstream
producer artefacts to downstream consumer ``--context`` flags. Test cases
mirror the acceptance criteria of TASK-MAG7-002 one-for-one so a failing
assertion points straight at the criterion it violates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from forge.pipeline import forward_propagation
from forge.pipeline.forward_propagation import (
    PROPAGATION_CONTRACT,
    ContextRecipe,
    _validate_propagation_contract,
)
from forge.pipeline.stage_taxonomy import STAGE_PREREQUISITES, StageClass


class TestModuleStructure:
    """AC-001 — module exists at the documented path with exports."""

    def test_module_path_is_forge_pipeline_forward_propagation(self) -> None:
        assert (
            forward_propagation.__name__
            == "forge.pipeline.forward_propagation"
        )

    def test_module_file_lives_under_src_forge_pipeline(self) -> None:
        path = Path(forward_propagation.__file__)
        assert path.name == "forward_propagation.py"
        assert path.parent.name == "pipeline"
        assert path.parent.parent.name == "forge"

    def test_module_exports_required_public_symbols(self) -> None:
        assert set(forward_propagation.__all__) == {
            "ContextRecipe",
            "PROPAGATION_CONTRACT",
        }


class TestContextRecipeModel:
    """AC-002 — ``ContextRecipe`` Pydantic model with required fields."""

    def test_context_recipe_is_pydantic_basemodel_subclass(self) -> None:
        assert issubclass(ContextRecipe, BaseModel)

    def test_context_recipe_has_all_four_required_fields(self) -> None:
        expected = {
            "producer_stage",
            "artefact_kind",
            "context_flag",
            "description",
        }
        assert set(ContextRecipe.model_fields.keys()) == expected

    def test_producer_stage_field_type_is_stageclass(self) -> None:
        assert (
            ContextRecipe.model_fields["producer_stage"].annotation
            is StageClass
        )

    def test_artefact_kind_accepts_text_path_and_path_list(self) -> None:
        for kind in ("text", "path", "path-list"):
            recipe = ContextRecipe(
                producer_stage=StageClass.PRODUCT_OWNER,
                artefact_kind=kind,  # type: ignore[arg-type]
                context_flag="--context",
                description="x",
            )
            assert recipe.artefact_kind == kind

    def test_artefact_kind_rejects_unknown_literal(self) -> None:
        with pytest.raises(ValidationError):
            ContextRecipe(
                producer_stage=StageClass.PRODUCT_OWNER,
                artefact_kind="binary-blob",  # type: ignore[arg-type]
                context_flag="--context",
                description="bogus",
            )

    def test_context_flag_must_be_non_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            ContextRecipe(
                producer_stage=StageClass.PRODUCT_OWNER,
                artefact_kind="text",
                context_flag="",
                description="x",
            )

    def test_description_must_be_non_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            ContextRecipe(
                producer_stage=StageClass.PRODUCT_OWNER,
                artefact_kind="text",
                context_flag="--context",
                description="",
            )

    def test_context_recipe_is_frozen(self) -> None:
        recipe = ContextRecipe(
            producer_stage=StageClass.PRODUCT_OWNER,
            artefact_kind="text",
            context_flag="--context",
            description="x",
        )
        with pytest.raises(ValidationError):
            recipe.context_flag = "--other"  # type: ignore[misc]


class TestPropagationContractContents:
    """AC-003..AC-010 — seven entries, one per non-product-owner stage."""

    def test_contract_has_exactly_seven_entries(self) -> None:
        assert len(PROPAGATION_CONTRACT) == 7

    def test_contract_excludes_product_owner_key(self) -> None:
        assert StageClass.PRODUCT_OWNER not in PROPAGATION_CONTRACT

    def test_contract_keys_cover_every_non_product_owner_stage(self) -> None:
        # The Mode A propagation contract has one entry per
        # non-PRODUCT_OWNER Mode A stage (AC-003..AC-010 of TASK-MAG7-005).
        # FEAT-FORGE-008 / TASK-MBC8-001 appended ``TASK_REVIEW`` and
        # ``TASK_WORK`` to the enum for Mode C; those have their own
        # propagation rules on the Mode C cycle planner (TASK-MBC8-005)
        # and are intentionally not entries in this Mode A contract.
        mode_a_non_po_stages = {
            StageClass.ARCHITECT,
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
            StageClass.FEATURE_SPEC,
            StageClass.FEATURE_PLAN,
            StageClass.AUTOBUILD,
            StageClass.PULL_REQUEST_REVIEW,
        }
        assert set(PROPAGATION_CONTRACT.keys()) == mode_a_non_po_stages

    @pytest.mark.parametrize(
        ("consumer", "producer", "kind", "description"),
        [
            (
                StageClass.ARCHITECT,
                StageClass.PRODUCT_OWNER,
                "text",
                "product-owner approved charter",
            ),
            (
                StageClass.SYSTEM_ARCH,
                StageClass.ARCHITECT,
                "text",
                "architect approved output",
            ),
            (
                StageClass.SYSTEM_DESIGN,
                StageClass.SYSTEM_ARCH,
                "path-list",
                "system-arch artefact paths",
            ),
            (
                StageClass.FEATURE_SPEC,
                StageClass.SYSTEM_DESIGN,
                "text",
                "system-design feature catalogue entry",
            ),
            (
                StageClass.FEATURE_PLAN,
                StageClass.FEATURE_SPEC,
                "path",
                "feature-spec artefact path",
            ),
            (
                StageClass.AUTOBUILD,
                StageClass.FEATURE_PLAN,
                "path",
                "feature-plan artefact path",
            ),
            (
                StageClass.PULL_REQUEST_REVIEW,
                StageClass.AUTOBUILD,
                "text",
                "autobuild branch ref + commit summary",
            ),
        ],
    )
    def test_each_contract_row_matches_task_brief(
        self,
        consumer: StageClass,
        producer: StageClass,
        kind: str,
        description: str,
    ) -> None:
        recipe = PROPAGATION_CONTRACT[consumer]
        assert recipe.producer_stage == producer
        assert recipe.artefact_kind == kind
        assert recipe.description == description

    def test_every_contract_row_uses_context_flag(self) -> None:
        for recipe in PROPAGATION_CONTRACT.values():
            assert recipe.context_flag == "--context"

    def test_contract_keys_are_all_stageclass_members(self) -> None:
        for key in PROPAGATION_CONTRACT:
            assert isinstance(key, StageClass)

    def test_contract_values_are_all_context_recipe_instances(self) -> None:
        for value in PROPAGATION_CONTRACT.values():
            assert isinstance(value, ContextRecipe)


class TestSelfValidationAtImport:
    """AC-011 — every key reachable from PRODUCT_OWNER via STAGE_PREREQUISITES."""

    def test_every_producer_stage_is_an_immediate_prerequisite_of_consumer(
        self,
    ) -> None:
        for consumer, recipe in PROPAGATION_CONTRACT.items():
            assert recipe.producer_stage in STAGE_PREREQUISITES[consumer], (
                f"Recipe for {consumer!r} has producer "
                f"{recipe.producer_stage!r} which is not an immediate "
                f"prerequisite ({STAGE_PREREQUISITES[consumer]!r})."
            )

    def test_every_contract_key_walks_back_to_product_owner(self) -> None:
        for consumer in PROPAGATION_CONTRACT:
            seen: set[StageClass] = set()
            cursor = consumer
            while cursor != StageClass.PRODUCT_OWNER:
                assert cursor not in seen, (
                    f"Cycle in prerequisites starting at {consumer!r}"
                )
                seen.add(cursor)
                prereqs = STAGE_PREREQUISITES.get(cursor)
                assert prereqs, (
                    f"{cursor!r} on the path from {consumer!r} has no "
                    "prerequisites — not reachable from PRODUCT_OWNER."
                )
                cursor = prereqs[0]
            # Loop terminated at PRODUCT_OWNER.
            assert cursor == StageClass.PRODUCT_OWNER

    def test_validator_accepts_canonical_contract(self) -> None:
        # Should not raise.
        _validate_propagation_contract(
            PROPAGATION_CONTRACT, STAGE_PREREQUISITES
        )

    def test_validator_rejects_contract_with_unknown_consumer(self) -> None:
        bogus = {
            StageClass.PRODUCT_OWNER: ContextRecipe(
                producer_stage=StageClass.ARCHITECT,
                artefact_kind="text",
                context_flag="--context",
                description="bogus reverse edge",
            )
        }
        with pytest.raises(ValueError, match="STAGE_PREREQUISITES"):
            _validate_propagation_contract(bogus, STAGE_PREREQUISITES)

    def test_validator_rejects_recipe_with_wrong_producer(self) -> None:
        bogus = dict(PROPAGATION_CONTRACT)
        bogus[StageClass.ARCHITECT] = ContextRecipe(
            producer_stage=StageClass.AUTOBUILD,  # not a prerequisite
            artefact_kind="text",
            context_flag="--context",
            description="wrong producer",
        )
        with pytest.raises(ValueError, match="not listed in"):
            _validate_propagation_contract(bogus, STAGE_PREREQUISITES)

    def test_validator_rejects_orphaned_consumer(self) -> None:
        truncated_prereqs = dict(STAGE_PREREQUISITES)
        # Break the chain — ARCHITECT no longer points to PRODUCT_OWNER.
        del truncated_prereqs[StageClass.ARCHITECT]
        bogus = {
            StageClass.SYSTEM_ARCH: PROPAGATION_CONTRACT[StageClass.SYSTEM_ARCH]
        }
        with pytest.raises(ValueError, match="reachable from PRODUCT_OWNER"):
            _validate_propagation_contract(bogus, truncated_prereqs)


class TestImportSideEffects:
    """The module must be side-effect free apart from self-validation."""

    def test_module_imports_no_other_forge_pipeline_submodule(self) -> None:
        source = Path(forward_propagation.__file__).read_text(
            encoding="utf-8"
        )
        forbidden = [
            "from forge.pipeline.lifecycle",
            "from forge.pipeline.forward_propagation",
            "import forge.pipeline.lifecycle",
        ]
        for needle in forbidden:
            assert needle not in source, (
                f"forward_propagation must not contain {needle!r}; only "
                "stage_taxonomy is an allowed sibling import."
            )

    def test_module_only_imports_stage_taxonomy_from_pipeline_pkg(self) -> None:
        source = Path(forward_propagation.__file__).read_text(
            encoding="utf-8"
        )
        # The only forge.pipeline.* import allowed is stage_taxonomy.
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                ("from forge.pipeline", "import forge.pipeline")
            ):
                assert "stage_taxonomy" in stripped, (
                    f"Unexpected forge.pipeline import: {stripped!r}"
                )
