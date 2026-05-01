"""Static lint tests for the forge-image GitHub Actions workflow.

These tests cover TASK-F009-007 — ``.github/workflows/forge-image.yml``,
the CI workflow that closes binding-shape item 7 (CI builds + smoke-tests
the production image on every PR touching the production-image surface)
and acceptance criteria AC-F (no real provider keys), AC-I (CI gate on
PR), and the image-size budget regression check (B4 / ASSUM-003).

The tests parse the workflow file with PyYAML rather than invoking the
GitHub Actions runtime so they can run as fast unit tests in CI without
needing ``act`` or a real runner. They cover:

1. Workflow YAML validates — syntactically parseable and exposing the
   ``on``, ``jobs``, and ``name`` keys actionlint would also assert.
2. Contract A consumer — workflow invokes ``scripts/build-image.sh``
   and does NOT inline the ``docker buildx build --build-context`` line
   that T6's drift detector enforces.
3. Trigger paths cover all four required surfaces (D5 scenario).
4. Sibling-checkout pattern for ``nats-core`` is wired correctly.
5. Image-size budget gate, smoke-set runner, secret-scan, and
   architecture-mismatch checks are all present.
6. Status-check naming so the workflow can be made a required check on
   ``main``.

These are static assertions on the workflow text/AST. The end-to-end
build-and-smoke run on a real PR is owned by GitHub Actions itself —
that's the whole point of the workflow.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# tests/dockerfile/test_forge_image_workflow.py -> two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "forge-image.yml"

# The literal Contract A invocation. T6's drift detector grep-matches
# this against ``scripts/build-image.sh`` and the runbook; the workflow
# MUST NOT contain it (the workflow is a Contract A *consumer*, not a
# producer). Keeping the forbidden substring narrower than the full
# invocation catches partial copy-paste mistakes too.
FORBIDDEN_INLINE_BUILDX = "docker buildx build --build-context nats-core="

# Required PR-trigger paths per AC (D5 scenario). Listed verbatim so a
# typo in the workflow surfaces here rather than at PR-trigger time.
REQUIRED_TRIGGER_PATHS = (
    "Dockerfile",
    "pyproject.toml",
    "src/forge/**",
    "scripts/build-image.sh",
    ".github/workflows/forge-image.yml",
)

# Image-size budget in bytes (1.0 GB uncompressed per ASSUM-003). The
# workflow must reference this exact integer so a refactor that drifts
# the budget is caught here rather than silently widening the gate.
IMAGE_SIZE_BUDGET_BYTES = 1_073_741_824


@pytest.fixture(scope="module")
def workflow_text() -> str:
    """Return the workflow file contents, failing fast if missing."""
    if not WORKFLOW_PATH.is_file():
        pytest.fail(
            f"Workflow not found at {WORKFLOW_PATH}. TASK-F009-007 "
            "creates .github/workflows/forge-image.yml."
        )
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_yaml(workflow_text: str) -> dict:
    """Return the parsed workflow YAML.

    PyYAML's ``safe_load`` with the workflow's quoted ``"on":`` key is
    sufficient for our needs — we don't need actionlint's full schema,
    just the top-level structure to assert against.
    """
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict), (
        "Workflow YAML must parse to a top-level mapping; got "
        f"{type(parsed).__name__}."
    )
    return parsed


class TestWorkflowYamlValidates:
    """AC: All modified files pass project-configured lint/format checks."""

    def test_workflow_file_exists(self) -> None:
        """The workflow file must exist at the canonical path."""
        assert WORKFLOW_PATH.is_file(), (
            f"{WORKFLOW_PATH} must exist for the CI gate to be wired."
        )

    def test_workflow_yaml_parses(self, workflow_yaml: dict) -> None:
        """Workflow must be syntactically valid YAML."""
        assert workflow_yaml, "Parsed workflow must be a non-empty mapping."

    def test_workflow_has_name(self, workflow_yaml: dict) -> None:
        """Workflow needs a ``name`` so the status check is identifiable."""
        assert "name" in workflow_yaml, (
            "Workflow must declare a top-level ``name`` so the status "
            "check ``<workflow-name> / <job-name>`` resolves."
        )
        # The status-check name registered with GitHub is
        # ``<workflow.name> / <job.name>``. The AC names the required
        # check ``forge-production-image / build-and-smoke-test``.
        assert workflow_yaml["name"] == "forge-production-image", (
            "Workflow name must be ``forge-production-image`` so the "
            "status check ``forge-production-image / "
            "build-and-smoke-test`` can be made a required check on "
            "main."
        )

    def test_workflow_declares_jobs(self, workflow_yaml: dict) -> None:
        """Workflow must declare a ``jobs`` mapping."""
        assert "jobs" in workflow_yaml, "Workflow must declare ``jobs``."
        assert isinstance(workflow_yaml["jobs"], dict)
        assert workflow_yaml["jobs"], "``jobs`` must not be empty."


class TestContractAConsumer:
    """AC: Workflow invokes scripts/build-image.sh — does NOT inline
    the docker buildx build command.

    Mirrors the seam test in the task description for BUILDKIT_INVOCATION
    (Contract A producer = TASK-F009-005 / scripts/build-image.sh).
    """

    @pytest.mark.seam
    @pytest.mark.integration_contract("BUILDKIT_INVOCATION")
    def test_workflow_invokes_build_script(self, workflow_text: str) -> None:
        """Verify the workflow consumes scripts/build-image.sh."""
        assert "scripts/build-image.sh" in workflow_text, (
            "Workflow must invoke scripts/build-image.sh — Contract A "
            "consumer per TASK-F009-005."
        )

    @pytest.mark.seam
    @pytest.mark.integration_contract("BUILDKIT_INVOCATION")
    def test_workflow_does_not_inline_buildx_command(
        self, workflow_text: str
    ) -> None:
        """Workflow must NOT reproduce the docker buildx command inline.

        T6's drift detector enforces this; adding a unit-level grep here
        gives a faster signal than waiting for the BDD tier to fail.
        """
        assert FORBIDDEN_INLINE_BUILDX not in workflow_text, (
            f"Workflow inlines the BuildKit command "
            f"(``{FORBIDDEN_INLINE_BUILDX}``). Replace with a call to "
            f"scripts/build-image.sh to honour Contract A."
        )


class TestTriggerPaths:
    """AC: Workflow triggers on PRs that change any of the four required
    surfaces plus the workflow file itself (D5 scenario / AC-I).
    """

    def test_workflow_triggers_on_pull_request(
        self, workflow_yaml: dict
    ) -> None:
        """Workflow must trigger on ``pull_request`` events."""
        # PyYAML interprets the bare ``on:`` key as the boolean ``True``
        # in some YAML 1.1 dialects. Quoted ``"on":`` avoids this.
        on_block = workflow_yaml.get("on") or workflow_yaml.get(True)
        assert on_block is not None, (
            "Workflow must declare an ``on`` trigger block."
        )
        assert "pull_request" in on_block, (
            "Workflow must trigger on ``pull_request`` (AC-I CI gate)."
        )

    @pytest.mark.parametrize("required_path", REQUIRED_TRIGGER_PATHS)
    def test_pr_trigger_includes_required_path(
        self, workflow_yaml: dict, required_path: str
    ) -> None:
        """Each required surface must appear in ``on.pull_request.paths``."""
        on_block = workflow_yaml.get("on") or workflow_yaml.get(True)
        pr_block = on_block["pull_request"]
        paths = pr_block.get("paths", [])
        assert required_path in paths, (
            f"PR trigger must include path ``{required_path}`` so a PR "
            f"changing it runs the image-build gate (D5 scenario)."
        )


class TestSiblingCheckout:
    """AC: Workflow checks out forge AND nats-core so the BuildKit named
    context ``--build-context nats-core=../nats-core`` resolves.
    """

    def test_workflow_checks_out_forge(self, workflow_text: str) -> None:
        """At least one ``actions/checkout`` step is present."""
        assert re.search(r"actions/checkout@v\d", workflow_text), (
            "Workflow must use ``actions/checkout`` to fetch the forge "
            "working tree."
        )

    def test_workflow_checks_out_nats_core(
        self, workflow_text: str
    ) -> None:
        """A second checkout step targets the ``nats-core`` repository.

        The sibling-checkout pattern is documented in the task
        Implementation Notes: forge at ``$GITHUB_WORKSPACE/forge`` and
        nats-core at ``$GITHUB_WORKSPACE/nats-core`` so
        ``../nats-core`` from the forge directory resolves correctly.
        """
        # Match either the explicit ``repository:`` form or the bare
        # path/owner shorthand, but require an explicit ``nats-core``
        # marker so we know the second checkout is for nats-core, not
        # a duplicate forge checkout.
        assert "nats-core" in workflow_text, (
            "Workflow must reference ``nats-core`` (sibling-checkout "
            "pattern for the BuildKit named context)."
        )
        # The repository spec must be present — the bare path alone is
        # not enough because a forge checkout could legitimately mention
        # nats-core in a comment or env var.
        assert re.search(
            r"repository:\s*[\w./-]*nats-core", workflow_text
        ), (
            "Workflow must use ``actions/checkout`` with "
            "``repository: <owner>/nats-core`` (or similar) to fetch "
            "the sibling working tree."
        )


class TestImageSizeBudget:
    """AC: Image-size check fails the job if the uncompressed image
    exceeds 1.0 GB (B4 scenario, ASSUM-003).
    """

    def test_workflow_inspects_image_size(
        self, workflow_text: str
    ) -> None:
        """Workflow must call ``docker image inspect`` for the size."""
        assert "docker image inspect" in workflow_text, (
            "Workflow must inspect the built image's size via "
            "``docker image inspect`` (ASSUM-003 image-size budget)."
        )

    def test_workflow_references_size_budget_constant(
        self, workflow_text: str
    ) -> None:
        """The 1.0 GB budget must appear verbatim as the byte count.

        Using the explicit byte count rather than ``1GB`` or ``1024MB``
        keeps the comparison unambiguous — bash ``-gt`` compares
        integers, not human-readable units.
        """
        assert str(IMAGE_SIZE_BUDGET_BYTES) in workflow_text, (
            f"Workflow must reference the budget "
            f"``{IMAGE_SIZE_BUDGET_BYTES}`` (1.0 GB in bytes) "
            "verbatim — ASSUM-003."
        )

    def test_workflow_size_failure_message_names_budget_and_actual(
        self, workflow_text: str
    ) -> None:
        """Failure diagnostic must name both the budget and actual size."""
        # The failure path must surface enough information for a
        # developer to act on it without re-running the workflow with
        # debug logging.
        assert "budget" in workflow_text.lower(), (
            "Image-size failure message must mention the budget so the "
            "developer can see what was exceeded."
        )


class TestSmokeRunner:
    """AC: Smoke-set runner runs ``pytest -m smoke tests/bdd/``."""

    def test_workflow_runs_smoke_pytest(self, workflow_text: str) -> None:
        """Workflow must invoke ``pytest -m smoke``."""
        assert re.search(r"pytest\s+(-[A-Za-z0-9 ]+\s+)*-m\s+smoke", workflow_text), (
            "Workflow must run ``pytest -m smoke`` to execute the @smoke "
            "BDD scenarios against the built image."
        )
        assert "tests/bdd" in workflow_text, (
            "Smoke runner must target ``tests/bdd/`` so pytest-bdd "
            "collects the right scenarios."
        )


class TestProviderKeyScan:
    """AC: Provider-key scan covers C1 / AC-F."""

    def test_workflow_scans_for_provider_keys(
        self, workflow_text: str
    ) -> None:
        """Workflow must run a secret-scan step covering provider keys.

        The task Implementation Notes recommend ``gitleaks`` or
        ``trufflehog``. We accept either tool name OR an explicit regex
        for the key prefixes called out by the AC (sk-, AIza, xoxb-).
        """
        scanners = ("gitleaks", "trufflehog", "trivy")
        regex_markers = ("sk-", "AIza", "xoxb-")
        used_scanner = any(
            scanner in workflow_text.lower() for scanner in scanners
        )
        used_regex = any(marker in workflow_text for marker in regex_markers)
        assert used_scanner or used_regex, (
            "Workflow must scan image layers for provider key material "
            "(AC-F / C1). Use gitleaks/trufflehog/trivy or an explicit "
            "regex for sk-/AIza/xoxb- prefixes."
        )


class TestArchitectureMismatchCheck:
    """AC: Architecture-mismatch dry-check (E3.2 scenario).

    The workflow runs on ``ubuntu-latest`` (linux/amd64) and asserts
    the built image's platform metadata matches.
    """

    def test_workflow_runs_on_ubuntu_latest(
        self, workflow_yaml: dict
    ) -> None:
        """Job must declare ``runs-on: ubuntu-latest`` (linux/amd64)."""
        jobs = workflow_yaml["jobs"]
        runs_on = {
            job_name: job_spec.get("runs-on")
            for job_name, job_spec in jobs.items()
        }
        assert any(value == "ubuntu-latest" for value in runs_on.values()), (
            "At least one job must run on ``ubuntu-latest`` (linux/amd64) "
            "so the architecture-mismatch dry-check is meaningful."
        )

    def test_workflow_asserts_image_architecture(
        self, workflow_text: str
    ) -> None:
        """Workflow must inspect the image's declared platform."""
        # ``docker image inspect`` exposes ``.Architecture`` and ``.Os``
        # — checking either is enough to detect a cross-arch build.
        has_arch_check = (
            ".Architecture" in workflow_text
            or "linux/amd64" in workflow_text
        )
        assert has_arch_check, (
            "Workflow must verify the built image's architecture matches "
            "linux/amd64 (E3.2 scenario)."
        )


class TestStatusCheckNaming:
    """AC: Workflow registers status check
    ``forge-production-image / build-and-smoke-test`` so it can be made
    a required check on the main branch.
    """

    def test_job_id_is_build_and_smoke_test(
        self, workflow_yaml: dict
    ) -> None:
        """The job id must be ``build-and-smoke-test``.

        GitHub composes the status-check name as
        ``<workflow.name> / <job.id-or-name>``. With ``workflow.name =
        forge-production-image`` and ``job.id = build-and-smoke-test``
        the resulting check matches the AC.
        """
        jobs = workflow_yaml["jobs"]
        assert "build-and-smoke-test" in jobs, (
            "Workflow must declare a job with id ``build-and-smoke-test`` "
            "so the status check ``forge-production-image / "
            "build-and-smoke-test`` resolves."
        )
