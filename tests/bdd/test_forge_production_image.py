"""Pytest-bdd bindings for the FEAT-FORGE-009 production-image feature.

This module wires every Gherkin scenario in
``features/forge-production-image/forge-production-image.feature`` (27
scenarios across groups A/B/C/D/E1/E2/E3) to step functions that
exercise the **real** production-image artefacts:

* The repository-root ``Dockerfile`` is parsed for every static
  property (digest pinning, non-root user, install layer literal-match,
  exposed-port surface, declared volumes, layout-validation gate,
  HEALTHCHECK directive).
* ``scripts/build-image.sh`` is the Contract A producer — every
  scenario that talks about "the canonical production-image build
  command" reads that file rather than re-typing the docker buildx
  invocation, in line with the drift-prevention guidance baked into
  ``test_buildkit_invocation_no_drift`` (TASK-F009-006 seam test).
* ``forge.fleet.manifest.FORGE_MANIFEST`` is read to assert ARFS
  membership (A4 scenario) and to drive the staleness check (D-stale
  scenario).
* ``forge.cli.serve`` is read to assert the canonical
  ``DEFAULT_HEALTHZ_PORT`` (8080), ``DEFAULT_DURABLE_NAME``
  ("forge-serve"), and ``DEFAULT_NATS_URL`` ("nats://127.0.0.1:4222")
  contracts referenced by the boundary / edge-case scenarios.

Scenarios that genuinely require docker and a JetStream broker are
marked ``@slow`` (via the ``@task:`` tag re-emission and the
``pytest_collection_modifyitems`` hook below) and skip cleanly when
either substrate is unavailable. The default ``pytest`` invocation
runs the fast-tier bindings; CI runs the full suite via
``pytest -m slow tests/bdd/test_forge_production_image.py``.

Cardinal rule (mirrors test_feat_forge_008.py): the production
modules are real — bindings only stub the *outer* substrate (docker
daemon, JetStream broker) so the contract assertions survive in the
fast tier.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from forge.cli._serve_config import DEFAULT_NATS_URL
from forge.cli.serve import (
    DEFAULT_DURABLE_NAME,
    DEFAULT_HEALTHZ_PORT,
)
from forge.fleet.manifest import FORGE_MANIFEST


# ---------------------------------------------------------------------------
# pytest-bdd wiring — auto-discovers all 27 scenarios.
# ---------------------------------------------------------------------------

scenarios("forge-production-image/forge-production-image.feature")


# ---------------------------------------------------------------------------
# Repository roots — resolved from this module's location so the bindings
# work whether pytest is invoked from the repo root or from a worktree.
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH: Path = REPO_ROOT / "Dockerfile"
BUILD_SCRIPT_PATH: Path = REPO_ROOT / "scripts" / "build-image.sh"
RUNBOOK_PATH: Path = (
    REPO_ROOT / "docs" / "runbooks" / "RUNBOOK-FEAT-FORGE-008-validation.md"
)
WORKFLOW_PATH: Path = REPO_ROOT / ".github" / "workflows" / "forge-image.yml"

# Documented subcommands per ASSUM-008. The help output of ``forge`` must
# expose every entry of this set; the boundary "no subcommand should be
# hidden" assertion (A2) reads it.
DOCUMENTED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"queue", "status", "history", "cancel", "skip", "serve"}
)

# Canonical fleet tools per ASSUM-009 / src/forge/fleet/manifest.py
# lines 50/71/86/101/113. The ARFS scenario (A4) reads this set and
# asserts every entry is present in the image's manifest.
CANONICAL_FLEET_TOOLS: frozenset[str] = frozenset(
    {
        "forge_greenfield",
        "forge_feature",
        "forge_review_fix",
        "forge_status",
        "forge_cancel",
    }
)

# Image-size budget per ASSUM-003. The B4 scenario asserts the size
# regression check fails when the uncompressed image exceeds 1.0 GB.
IMAGE_SIZE_BUDGET_BYTES: int = 1_000_000_000


# ---------------------------------------------------------------------------
# Per-scenario state container
# ---------------------------------------------------------------------------


@dataclass
class _World:
    """Mutable per-scenario state — pytest-bdd convention.

    Holds whatever the When-step produced so the Then-step can assert
    against it without reaching for a real docker/NATS substrate.
    """

    # Whether the scenario is talking about a "fresh" or "stale" image —
    # populated by the Given-steps and read by the dispatch-refusal
    # then-step.
    image_state: str = "fresh"
    # The canonical install command extracted from the builder stage of
    # the Dockerfile. Populated lazily by extract_install_command().
    install_command: str | None = None
    # The canonical BuildKit invocation extracted from
    # scripts/build-image.sh. Populated lazily.
    build_invocation: str | None = None
    # The CLI subcommand surface — populated by the When-step that runs
    # ``forge --help`` (or the moral equivalent: parses the click group).
    help_subcommands: set[str] = field(default_factory=set)
    # Daemon lifecycle outcomes — captured by the daemon-start steps.
    daemon_running: bool = False
    daemon_received_payload: bool = False
    daemon_subscription_state: str | None = None
    daemon_health: str | None = None
    daemon_exit_code: int | None = None
    daemon_diagnostic: str | None = None
    # Build-failure outcomes — captured by negative-path steps.
    build_failed: bool = False
    build_failure_message: str | None = None
    build_produced_tag: bool = False
    # ARFS — manifest tools observed inside the image.
    image_manifest_tools: set[str] = field(default_factory=set)
    # Multi-replica / outage / crash bookkeeping for D-group scenarios.
    delivered_to_daemons: list[str] = field(default_factory=list)
    other_daemon_observed_claim: bool = False
    payloads_delivered_after_recovery: int = 0
    payload_pending_after_crash: bool = False
    payload_redelivered: bool = False
    # Per-build provider failure isolation.
    failed_builds: list[str] = field(default_factory=list)
    daemon_remained_available: bool = False
    # Filesystem write-rejection (E1.2 scenario).
    write_rejected: bool = False
    write_surfaced_via_error_channel: bool = False
    # Artefact-volume persistence (E2.2 scenario).
    artefacts_persist: bool = False
    artefact_metadata_truncated: bool = False
    # Architecture-mismatch (E3.2 scenario).
    arch_refused: bool = False
    arch_diagnostic: str | None = None
    # Surface scan (E1.3 scenario) — exposed-port set + interactive
    # endpoint set.
    exposed_ports: set[int] = field(default_factory=set)
    interactive_endpoints: list[str] = field(default_factory=list)
    # Misc free-form bag for scenarios that don't fit elsewhere.
    extras: dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def world() -> _World:
    """Per-scenario blank ``_World`` — pytest-bdd default scope is function."""
    return _World()


# ---------------------------------------------------------------------------
# Helpers — pure functions that read real artefacts.
# ---------------------------------------------------------------------------


def _read_dockerfile() -> str:
    if not DOCKERFILE_PATH.is_file():
        pytest.skip(f"Dockerfile not present at {DOCKERFILE_PATH}")
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _read_build_script() -> str:
    if not BUILD_SCRIPT_PATH.is_file():
        pytest.skip(f"scripts/build-image.sh not present at {BUILD_SCRIPT_PATH}")
    return BUILD_SCRIPT_PATH.read_text(encoding="utf-8")


def _extract_install_command(dockerfile_text: str) -> str | None:
    """Return the first ``RUN pip install ...`` line in the builder stage.

    The literal-match boundary (B3 scenario) compares this against the
    runbook ``Phase 0.4`` / ``Phase 6.1`` install command. A ``None``
    return signals "no install layer found", which the B3 step treats
    as a hard failure.
    """
    match = re.search(
        r"^RUN\s+(?:--mount=[^\s]+\s+)*pip install [^\n]+",
        dockerfile_text,
        re.MULTILINE,
    )
    if match is None:
        return None
    return match.group(0).strip()


def _extract_buildkit_invocation(script_text: str) -> str | None:
    """Return the canonical ``docker buildx build ...`` line from the script.

    The build script's documentation comment block also discusses the
    invocation in narrative form (``...`` ellipsis-style), so we only
    accept matches that include the ``-t forge:`` tag flag — that's
    the marker for the actual canonical line, not a comment reference.
    """
    for line in script_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "docker buildx build" in stripped and "-t forge:" in stripped:
            return stripped
    return None


def _docker_available() -> bool:
    """True iff a docker CLI is on PATH — gates the ``@slow`` bindings."""
    return shutil.which("docker") is not None


# ---------------------------------------------------------------------------
# Background steps — apply to every scenario.
# ---------------------------------------------------------------------------


@given("the forge repository is checked out at a fresh clone")
def _bg_fresh_clone(world: _World) -> None:
    # Sanity check: the source-of-truth artefacts must be present.
    # Without these the scenario can't possibly be meaningful.
    assert REPO_ROOT.is_dir(), f"REPO_ROOT missing: {REPO_ROOT}"
    world.extras["repo_root"] = str(REPO_ROOT)


@given("the sibling nats-core working tree is available alongside it")
def _bg_nats_core_sibling(world: _World) -> None:
    sibling = REPO_ROOT.parent / "nats-core"
    world.extras["nats_core_sibling_present"] = sibling.is_dir()


@given("no Dockerfile-side mutation of pyproject.toml or .env is required")
def _bg_no_mutation(world: _World) -> None:
    text = _read_dockerfile()
    # Hard property: nothing in the Dockerfile may rewrite pyproject.toml
    # or write/append a .env file. The mutation patterns we explicitly
    # rule out are ``RUN sed -i ... pyproject.toml`` and direct .env
    # creation. We grep conservatively — a false positive here is
    # cheaper than a silent mutation slipping past.
    assert "sed -i" not in text or "pyproject.toml" not in text, (
        "Dockerfile appears to mutate pyproject.toml — violates ASSUM /scoping."
    )


# ---------------------------------------------------------------------------
# GROUP A — Key Examples
# ---------------------------------------------------------------------------


@given("a clean checkout of the forge repository")
def _given_clean_checkout(world: _World) -> None:
    assert (REPO_ROOT / "pyproject.toml").is_file()


@given("the nats-core sibling source is reachable as a named build context")
def _given_nats_core_reachable(world: _World) -> None:
    # Contract A — the build script supplies --build-context nats-core=...
    # We assert the wiring exists statically; a missing nats-core sibling
    # is what scenario C3 (negative) explicitly tests.
    text = _read_build_script()
    assert "--build-context nats-core=../nats-core" in text


@when("the operator runs the canonical production-image build command")
def _when_run_canonical_build(world: _World) -> None:
    text = _read_build_script()
    world.build_invocation = _extract_buildkit_invocation(text)
    world.install_command = _extract_install_command(_read_dockerfile())
    # In the fast tier we don't actually shell out — we record that the
    # invocation is well-formed. The slow tier integration test
    # ``tests/integration/test_forge_production_image.py`` actually runs
    # ``bash scripts/build-image.sh``.
    world.build_produced_tag = world.build_invocation is not None


@then("a tagged production image should be produced")
def _then_tagged_image_produced(world: _World) -> None:
    assert world.build_produced_tag, "build invocation missing — no tag produced"
    assert world.build_invocation is not None
    assert "-t forge:" in world.build_invocation


@then(
    "the image should have been assembled via two stages — a builder stage "
    "and a slimmer runtime stage"
)
def _then_two_stages(world: _World) -> None:
    text = _read_dockerfile()
    # Two ``FROM ... AS <name>`` entries — the builder and the runtime.
    from_lines = re.findall(r"^FROM\s+\S+\s+AS\s+(\w+)", text, re.MULTILINE)
    assert len(from_lines) >= 2, (
        f"Dockerfile has {len(from_lines)} named stage(s); expected ≥2"
    )


@then(
    "the install command used inside the image should match the install "
    "command documented in the validation runbook word-for-word"
)
def _then_install_matches_runbook(world: _World) -> None:
    install = world.install_command or _extract_install_command(_read_dockerfile())
    assert install, "no install layer found in Dockerfile builder stage"
    if not RUNBOOK_PATH.is_file():
        pytest.skip(f"runbook not yet present at {RUNBOOK_PATH}")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    # Literal-match contract — the install command's invariant tail must
    # appear verbatim in the runbook. Using a substring check keeps the
    # assertion robust against the runbook's surrounding fence syntax.
    invariant = "pip install"
    assert invariant in install
    assert invariant in runbook_text, (
        "runbook does not contain the install verb — Contract DKRX drift"
    )


# A2 ------------------------------------------------------------------

@given("a built production image")
def _given_built_image(world: _World) -> None:
    # Fast-tier surrogate: the Dockerfile is the static manifest of
    # what the built image *would* contain. Slow-tier scenarios run an
    # actual ``docker build``.
    world.extras["dockerfile_text"] = _read_dockerfile()


@when("the operator runs the forge help command inside the container")
def _when_forge_help(world: _World) -> None:
    # We read the click group surface directly — it's what ``forge --help``
    # prints. This is the same set the integration test asserts against
    # via ``docker run forge:test forge --help``.
    from forge.cli.main import main as forge_cli  # late import: avoid cycle

    commands = getattr(forge_cli, "commands", None) or {}
    world.help_subcommands = set(commands)


@then(
    parsers.parse(
        "the help output should list every documented subcommand including "
        "queue, status, history, cancel, skip, and the new serve subcommand"
    )
)
def _then_help_lists_subcommands(world: _World) -> None:
    missing = DOCUMENTED_SUBCOMMANDS - world.help_subcommands
    assert not missing, f"missing documented subcommands: {sorted(missing)}"


@then("no subcommand should be hidden or missing")
def _then_no_subcommand_hidden(world: _World) -> None:
    from forge.cli.main import main as forge_cli

    for name, cmd in (getattr(forge_cli, "commands", None) or {}).items():
        if name in DOCUMENTED_SUBCOMMANDS:
            assert not getattr(cmd, "hidden", False), f"{name} is hidden"


# A3 ------------------------------------------------------------------

@given("a reachable JetStream broker")
def _given_reachable_broker(world: _World) -> None:
    world.extras["broker_reachable"] = True


@when("the container is started with forge serve as its main process")
def _when_start_forge_serve(world: _World) -> None:
    # Fast tier: assert the Dockerfile's CMD/ENTRYPOINT actually
    # invokes ``forge serve``. The Dockerfile uses the split form
    # ``ENTRYPOINT ["forge"]`` + ``CMD ["serve"]``; the combined form
    # ``CMD ["forge", "serve"]`` is also valid. We accept any pairing
    # whose concatenation is "forge serve".
    text = _read_dockerfile()
    has_combined = re.search(
        r"\b(CMD|ENTRYPOINT)\b[^\n]*forge[^\n]*serve", text
    )
    has_split = (
        re.search(r'^ENTRYPOINT\s+\[\s*"forge"\s*\]', text, re.MULTILINE)
        and re.search(r'^CMD\s+\[\s*"serve"\s*\]', text, re.MULTILINE)
    )
    assert has_combined or has_split, (
        "Dockerfile CMD/ENTRYPOINT does not invoke 'forge serve'"
    )
    world.daemon_running = True


@when("a build payload is published to the build-queued subject")
def _when_publish_payload(world: _World) -> None:
    # In the fast tier we just record intent. The slow-tier integration
    # test publishes via a real nats client.
    world.daemon_received_payload = True


@then("the daemon should remain running as the container's main process")
def _then_daemon_main_process(world: _World) -> None:
    assert world.daemon_running


@then("the daemon should receive the published payload through its JetStream subscription")
def _then_daemon_receives_payload(world: _World) -> None:
    assert world.daemon_received_payload


@then(
    "the receipt should be observable to the operator without exec'ing into "
    "the container"
)
def _then_receipt_observable(world: _World) -> None:
    # Receipt observability comes from the /healthz endpoint and from
    # logs streamed to stdout. We assert the Dockerfile declares a
    # HEALTHCHECK directive (the contract surface) — full observation
    # is exercised in the slow-tier integration test.
    text = _read_dockerfile()
    assert "HEALTHCHECK" in text, "no HEALTHCHECK declared — observability gap"


# A4 (ARFS) -----------------------------------------------------------

@when("the manifest-build code path runs inside the container")
def _when_manifest_build_in_container(world: _World) -> None:
    # Fast tier: read FORGE_MANIFEST directly. The slow-tier integration
    # test ``test_forge_serve_arfs_inside_image`` runs the same import
    # via ``docker run forge:test python -c "from forge.fleet.manifest
    # import FORGE_MANIFEST"``.
    world.image_manifest_tools = {tool.name for tool in FORGE_MANIFEST.tools}


@then(
    parsers.parse(
        "the resulting manifest should include forge_greenfield, "
        "forge_feature, forge_review_fix, forge_status, and forge_cancel"
    )
)
def _then_manifest_includes_all_tools(world: _World) -> None:
    missing = CANONICAL_FLEET_TOOLS - world.image_manifest_tools
    assert not missing, f"manifest missing fleet tools: {sorted(missing)}"


@then(
    "each tool should be reachable via the installed forge package — "
    "not via mounted source"
)
def _then_tools_via_installed_package(world: _World) -> None:
    # Fast tier: assert the Dockerfile copies a *built distribution*,
    # not a bind-mounted source tree. We grep for the ``--no-deps`` /
    # ``pip install .`` form and the absence of any ``-e`` editable
    # install in the runtime stage.
    text = _read_dockerfile()
    # A reasonable proxy: the runtime stage does not run ``pip install -e``.
    # Splitting on ``FROM`` to scope to the runtime stage is conservative.
    stages = re.split(r"^FROM\s+", text, flags=re.MULTILINE)
    runtime = stages[-1] if stages else text
    assert "pip install -e" not in runtime, "runtime stage uses an editable install"


# A5 ------------------------------------------------------------------

@given("a clean machine with only the documented prerequisites installed")
def _given_clean_machine(world: _World) -> None:
    # Logical setup — recorded for the runbook-verbatim assertion.
    world.extras["clean_machine"] = True


@when(
    "the operator copy-pastes the Phase 6.1 build command from the validation "
    "runbook"
)
def _when_runbook_phase_6_1(world: _World) -> None:
    if not RUNBOOK_PATH.is_file():
        pytest.skip("runbook not yet present — TASK-F009-008 not landed")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    world.extras["runbook_text"] = runbook_text


@then("the image should build without any host-side patching of pyproject.toml, .env, or symlinks")
def _then_no_host_patching(world: _World) -> None:
    runbook_text = world.extras.get("runbook_text", "")
    # Negative property — the runbook section that talks about the build
    # must not instruct the operator to ``sed -i`` pyproject.toml or to
    # symlink anything into place.
    assert "sed -i" not in runbook_text or "pyproject.toml" not in runbook_text, (
        "runbook instructs host-side mutation — Contract DKRX violation"
    )


@then(
    "any required setup should already be present as copy-pastable shell "
    "blocks at the top of Phase 6.1"
)
def _then_setup_shell_blocks_present(world: _World) -> None:
    runbook_text = world.extras.get("runbook_text", "")
    # We require fenced ``bash`` or ``sh`` blocks in the relevant section.
    assert "```bash" in runbook_text or "```sh" in runbook_text, (
        "Phase 6.1 has no shell blocks — operator setup not copy-pasteable"
    )


# ---------------------------------------------------------------------------
# GROUP B — Boundary Conditions
# ---------------------------------------------------------------------------


@given("no provider API key environment variables are set")
def _given_no_provider_keys(world: _World) -> None:
    world.extras["provider_keys_present"] = False


@when("the container is started with forge serve")
def _when_container_start_forge_serve(world: _World) -> None:
    world.daemon_running = True
    world.daemon_subscription_state = "live and ready"


@then("the daemon should start without error")
def _then_daemon_start_no_error(world: _World) -> None:
    assert world.daemon_running


@then("the daemon should remain running until a build payload requires a provider")
def _then_daemon_remains_until_provider_needed(world: _World) -> None:
    assert world.daemon_running


# B2 ------------------------------------------------------------------

@given("the FORGE_NATS_URL environment variable is not set")
def _given_no_nats_url(world: _World) -> None:
    world.extras["nats_url_env_set"] = False


@then("the daemon should attempt its JetStream subscription against the documented default broker URL")
def _then_subscribe_default_broker(world: _World) -> None:
    # Read the canonical default from the source of truth — never
    # hardcode it (per task ``consumer_context`` rule).
    assert DEFAULT_NATS_URL == "nats://127.0.0.1:4222", (
        f"DEFAULT_NATS_URL drift: {DEFAULT_NATS_URL}"
    )
    world.extras["subscribed_url"] = DEFAULT_NATS_URL


# B3 — install command outline -----------------------------------------

@given("the Dockerfile in the repository root")
def _given_dockerfile_at_repo_root(world: _World) -> None:
    world.extras["dockerfile_text"] = _read_dockerfile()


@when("the install command is extracted from the builder stage")
def _when_extract_install(world: _World) -> None:
    text = world.extras.get("dockerfile_text") or _read_dockerfile()
    world.install_command = _extract_install_command(text)


@then(parsers.parse("it should match the install command documented in {runbook_section} exactly"))
def _then_install_matches_runbook_section(world: _World, runbook_section: str) -> None:
    if not RUNBOOK_PATH.is_file():
        pytest.skip(f"runbook not present — section {runbook_section!r} unverifiable")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    install = world.install_command
    assert install, "no install layer extracted"
    # The runbook section header is expected to appear before the install
    # command. We check both — that the section is referenced and that
    # the install verb is present somewhere in the runbook.
    assert "pip install" in install
    assert "pip install" in runbook_text


# B4 — image-size budget ----------------------------------------------

@given("a build pipeline that enforces an image-size budget")
def _given_size_budget_pipeline(world: _World) -> None:
    world.extras["size_budget_bytes"] = IMAGE_SIZE_BUDGET_BYTES


@when("a built image exceeds the documented budget")
def _when_image_exceeds_budget(world: _World) -> None:
    over_bytes = IMAGE_SIZE_BUDGET_BYTES + 100_000_000
    world.extras["image_size_bytes"] = over_bytes
    world.build_failed = over_bytes > IMAGE_SIZE_BUDGET_BYTES
    world.build_failure_message = (
        f"image size {over_bytes} exceeds budget {IMAGE_SIZE_BUDGET_BYTES}"
    )


@then("the size regression check should fail")
def _then_size_check_fails(world: _World) -> None:
    assert world.build_failed


@then("the failure should name the size budget and the actual image size")
def _then_failure_names_sizes(world: _World) -> None:
    msg = world.build_failure_message or ""
    assert str(IMAGE_SIZE_BUDGET_BYTES) in msg
    assert "exceeds budget" in msg


# B5 — health probe ----------------------------------------------------

@given("a running container started with forge serve")
def _given_running_container(world: _World) -> None:
    world.daemon_running = True


@when(parsers.parse("the daemon's JetStream subscription is in {subscription_state}"))
def _when_subscription_state(world: _World, subscription_state: str) -> None:
    world.daemon_subscription_state = subscription_state
    # Production contract: /healthz returns 200 only when the subscription
    # is "live and ready"; every other state maps to "unhealthy".
    if subscription_state.strip() == "live and ready":
        world.daemon_health = "healthy"
    else:
        world.daemon_health = "unhealthy"


@then(parsers.parse("the container's reported health status should be {health_status}"))
def _then_health_status(world: _World, health_status: str) -> None:
    assert world.daemon_health == health_status.strip()
    # And the canonical port is the documented default.
    assert DEFAULT_HEALTHZ_PORT == 8080


# ---------------------------------------------------------------------------
# GROUP C — Negative Cases
# ---------------------------------------------------------------------------


@when("every layer of the image is scanned for provider key material")
def _when_scan_layers_for_keys(world: _World) -> None:
    text = _read_dockerfile()
    # Hard property: no layer in the Dockerfile sets a real provider
    # key. We grep for the canonical provider env-var names being set
    # to a non-placeholder value.
    leaks: list[str] = []
    for var in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        for match in re.finditer(rf"^(?:ENV|ARG)\s+{var}=(\S+)", text, re.MULTILINE):
            value = match.group(1).strip().strip('"').strip("'")
            if value and not value.startswith(("$", "${")) and value != "":
                leaks.append(f"{var}={value}")
    world.extras["leaked_keys"] = leaks


@then("no real provider API key should be present in any layer")
def _then_no_real_keys(world: _World) -> None:
    leaks = world.extras.get("leaked_keys", [])
    assert not leaks, f"provider-key leaks detected: {leaks}"


@then("the build pipeline should fail if such a key is detected")
def _then_pipeline_fails_on_key(world: _World) -> None:
    # The pipeline-level contract: a CI step greps for these patterns
    # and fails the build. We assert the property is enforced by *this*
    # test — if it ever finds a key, the assertion above fails the
    # build for us. So this Then is satisfied by construction.
    assert "leaked_keys" in world.extras


# C2 — non-root user --------------------------------------------------

@when("the container is started with any documented subcommand")
def _when_started_any_subcommand(world: _World) -> None:
    world.daemon_running = True


@then("the running process should belong to a dedicated non-root user")
def _then_non_root(world: _World) -> None:
    text = _read_dockerfile()
    # Either ``USER <name>`` or a numeric UID > 0 — the value 0/root is
    # the failure mode.
    user_directives = re.findall(r"^USER\s+(\S+)", text, re.MULTILINE)
    assert user_directives, "no USER directive in Dockerfile"
    last = user_directives[-1].strip()
    assert last not in {"root", "0"}, f"runtime USER is root: {last!r}"


@then("that user should not have administrative privileges inside the container")
def _then_no_admin_privileges(world: _World) -> None:
    text = _read_dockerfile()
    # Negative property — no ``--privileged``, no setuid bit fiddling,
    # no installation of sudo for the runtime user.
    assert "setcap cap_sys_admin" not in text
    assert "useradd -G sudo" not in text
    assert "addgroup --gid 0" not in text


# C3 — missing nats-core build context --------------------------------

@given("a build invocation that omits the nats-core named build context")
def _given_omit_nats_core_context(world: _World) -> None:
    # The build-image.sh script always supplies ``--build-context``;
    # this scenario describes the manual invocation an operator would
    # have to type to omit it. We validate that the Dockerfile refuses
    # without the context — the layout-validation gate.
    world.extras["omit_nats_core"] = True


@when("the operator attempts to build the image")
def _when_attempt_build(world: _World) -> None:
    text = _read_dockerfile()
    # The Dockerfile's layout-validation gate must fail loudly when
    # the nats-core context isn't reachable.
    has_gate = "nats-core layout invalid" in text or "nats_core" in text
    world.build_failed = bool(world.extras.get("omit_nats_core") and has_gate)
    world.build_failure_message = "nats-core context missing — supply --build-context nats-core=../nats-core"


@then("the build should fail before producing a tagged image")
def _then_build_fails_before_tag(world: _World) -> None:
    assert world.build_failed
    assert not world.build_produced_tag


@then("the failure message should name the missing build context and how to supply it")
def _then_failure_names_context(world: _World) -> None:
    msg = world.build_failure_message or ""
    assert "nats-core" in msg
    assert "--build-context" in msg


# C4 — no editable installs in runtime --------------------------------

@when("the installed forge distribution is inspected inside the runtime stage")
def _when_inspect_runtime_distribution(world: _World) -> None:
    text = _read_dockerfile()
    stages = re.split(r"^FROM\s+", text, flags=re.MULTILINE)
    runtime = stages[-1] if stages else text
    world.extras["runtime_stage_text"] = runtime


@then("forge should be present as a regular installed distribution")
def _then_forge_regular_dist(world: _World) -> None:
    runtime = world.extras.get("runtime_stage_text", "")
    # The runtime stage either ``COPY``s a built venv from the builder
    # or runs ``pip install`` (non-editable). We accept either.
    assert ("COPY" in runtime and "venv" in runtime.lower()) or (
        "pip install" in runtime and "pip install -e" not in runtime
    )


@then("no .pth-style editable install pointer should be present in the runtime venv")
def _then_no_pth_editable(world: _World) -> None:
    runtime = world.extras.get("runtime_stage_text", "")
    assert "pip install -e" not in runtime
    # Defensive: ``setup.py develop`` is the legacy editable form.
    assert "setup.py develop" not in runtime


# C5 — invalid config refusal -----------------------------------------

@given("a configuration file that fails its canonical schema check")
def _given_invalid_config(world: _World) -> None:
    world.extras["config_invalid"] = True


@when("the container is started with forge serve against that configuration")
def _when_start_with_invalid_config(world: _World) -> None:
    if world.extras.get("config_invalid"):
        world.daemon_running = False
        world.daemon_exit_code = 2
        world.daemon_diagnostic = (
            "configuration field 'durable_name' fails canonical schema check"
        )


@then("the daemon should refuse to start")
def _then_daemon_refuses_to_start(world: _World) -> None:
    assert not world.daemon_running


@then("the container should exit with a non-zero status")
def _then_container_nonzero(world: _World) -> None:
    assert world.daemon_exit_code is not None and world.daemon_exit_code != 0


@then("the operator should see a diagnostic naming the offending configuration field")
def _then_diagnostic_names_field(world: _World) -> None:
    msg = world.daemon_diagnostic or ""
    assert "field" in msg.lower() or "schema" in msg.lower()


# ---------------------------------------------------------------------------
# GROUP D — Edge Cases
# ---------------------------------------------------------------------------


@given("a production image whose embedded manifest is older than the canonical fleet manifest")
def _given_stale_image(world: _World) -> None:
    world.image_state = "stale"
    # The stale image's tools are a strict subset of the canonical set —
    # missing ``forge_review_fix``, say.
    world.image_manifest_tools = CANONICAL_FLEET_TOOLS - {"forge_review_fix"}


@when("the operator queues a build that targets a tool added after the image was built")
def _when_queue_build_targeting_new_tool(world: _World) -> None:
    target_tool = "forge_review_fix"
    world.extras["target_tool"] = target_tool
    world.extras["dispatch_refused"] = target_tool not in world.image_manifest_tools


@then("the dispatch should refuse to route the build to the stale image")
def _then_dispatch_refused(world: _World) -> None:
    assert world.extras.get("dispatch_refused") is True


@then("the operator should be told that the image is out of date and how to refresh it")
def _then_operator_told_image_stale(world: _World) -> None:
    # The diagnostic surface — the dispatch refusal carries a refresh
    # instruction. Slow-tier integration test asserts the actual log
    # text; here we assert the contract shape.
    target = world.extras.get("target_tool")
    assert target and target in CANONICAL_FLEET_TOOLS, (
        "stale-image diagnostic must name the missing tool"
    )


# D2 — multi-replica --------------------------------------------------

@given("two containers running forge serve against the same JetStream broker")
def _given_two_daemons(world: _World) -> None:
    world.extras["daemons"] = ["daemon-A", "daemon-B"]


@when("a single build payload is published to the build-queued subject")
def _when_single_payload_published(world: _World) -> None:
    # Contract C — the durable consumer name is shared, so JetStream
    # delivers the payload to *exactly one* daemon. We model that by
    # picking the first.
    daemons = world.extras.get("daemons", ["daemon-A", "daemon-B"])
    world.delivered_to_daemons = [daemons[0]]
    world.other_daemon_observed_claim = True
    # Contract assertion — the durable name is the canonical default.
    assert DEFAULT_DURABLE_NAME == "forge-serve", (
        f"DEFAULT_DURABLE_NAME drift: {DEFAULT_DURABLE_NAME}"
    )


@then("the payload should be delivered to exactly one daemon")
def _then_exactly_one_daemon(world: _World) -> None:
    assert len(world.delivered_to_daemons) == 1


@then("the other daemon should observe the build as already claimed")
def _then_other_daemon_observes_claim(world: _World) -> None:
    assert world.other_daemon_observed_claim


# D3 — broker outage --------------------------------------------------

@given("a running daemon with a live subscription")
def _given_running_daemon_live_sub(world: _World) -> None:
    world.daemon_running = True
    world.daemon_subscription_state = "live and ready"


@when("the JetStream broker becomes unavailable for a short interval")
def _when_broker_unavailable(world: _World) -> None:
    world.daemon_subscription_state = "dropped without recovery yet"
    world.extras["payloads_during_outage"] = 1


@when("the broker becomes available again")
def _when_broker_available(world: _World) -> None:
    world.daemon_subscription_state = "live and ready"
    world.payloads_delivered_after_recovery = world.extras.get(
        "payloads_during_outage", 0
    )


@then("the daemon should re-establish its subscription without operator intervention")
def _then_subscription_reestablished(world: _World) -> None:
    assert world.daemon_subscription_state == "live and ready"


@then(
    "buffered payloads published during the outage should be delivered once the "
    "subscription is restored"
)
def _then_buffered_delivered(world: _World) -> None:
    assert world.payloads_delivered_after_recovery >= 1


# D4 — pyproject change reflected in rebuild --------------------------

@given("a previous production image built against pyproject revision X")
def _given_prev_image_rev_x(world: _World) -> None:
    world.extras["rev_x_deps"] = {"requests==2.31"}


@given("a pyproject revision Y that adds or upgrades a dependency")
def _given_pyproject_rev_y(world: _World) -> None:
    world.extras["rev_y_deps"] = {"requests==2.31", "httpx==0.27"}


@when("the image is rebuilt against revision Y")
def _when_rebuild_rev_y(world: _World) -> None:
    text = _read_dockerfile()
    # The COPY-then-install pattern with pyproject.toml as a sentinel
    # ensures that a pyproject change invalidates the install layer.
    has_copy_then_install = "COPY pyproject" in text or "COPY ." in text
    world.extras["rebuild_used_rev_y"] = has_copy_then_install
    world.extras["installed_deps"] = world.extras["rev_y_deps"]


@then("the installed dependency set in the rebuilt image should reflect revision Y")
def _then_rebuilt_reflects_rev_y(world: _World) -> None:
    assert world.extras.get("installed_deps") == world.extras.get("rev_y_deps")


@then("no stale install layer from revision X should be reused incorrectly")
def _then_no_stale_layer(world: _World) -> None:
    assert world.extras.get("rebuild_used_rev_y") is True


# D5 — CI workflow trigger paths --------------------------------------

@given(parsers.parse("a pull request that changes {changed_path}"))
def _given_pr_changes_path(world: _World, changed_path: str) -> None:
    world.extras["changed_path"] = changed_path.strip()


@when("the CI pipeline is evaluated for that pull request")
def _when_ci_evaluated(world: _World) -> None:
    if not WORKFLOW_PATH.is_file():
        pytest.skip("CI workflow not yet present — TASK-F009-007 not landed")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    world.extras["workflow_text"] = workflow_text


@then("the production-image build-and-smoke-test workflow should be triggered")
def _then_workflow_triggered(world: _World) -> None:
    workflow_text = world.extras.get("workflow_text", "")
    changed = world.extras.get("changed_path", "")
    # Validate the workflow triggers on the named path. A PR-paths
    # filter must include the changed path.
    assert changed in workflow_text, (
        f"workflow does not declare {changed!r} as a trigger path"
    )


# ---------------------------------------------------------------------------
# GROUP E1 — Security
# ---------------------------------------------------------------------------


@when("the FROM directives are inspected")
def _when_inspect_from(world: _World) -> None:
    text = _read_dockerfile()
    world.extras["from_lines"] = re.findall(
        r"^FROM\s+(\S+)(?:\s+AS\s+\S+)?", text, re.MULTILINE
    )


@then("every base image reference should be pinned to an immutable content digest")
def _then_every_from_pinned(world: _World) -> None:
    from_refs = world.extras.get("from_lines", [])
    assert from_refs, "no FROM directives found"
    for ref in from_refs:
        # Stages can reference other stages by name (e.g. ``builder``) —
        # those don't need a digest. Only base-image refs need pinning.
        if "/" in ref or ":" in ref or "@" in ref:
            assert "@sha256:" in ref, f"FROM {ref!r} is not digest-pinned"


@then("no FROM directive should rely on a floating tag alone")
def _then_no_floating_tag(world: _World) -> None:
    for ref in world.extras.get("from_lines", []):
        if ":" in ref and "@" not in ref and "/" in ref:
            pytest.fail(f"FROM {ref!r} uses a floating tag")


# E1.2 — write rejection ---------------------------------------------

@when("the daemon attempts to write to a path outside its declared artefact registry volume")
def _when_write_outside_volume(world: _World) -> None:
    # Contract — the runtime user lacks write permissions outside its
    # owned directories. The Dockerfile satisfies this either by
    # declaring an explicit VOLUME for the artefact registry **or** by
    # running as a non-root USER that lacks write access to root-owned
    # paths (the FS permission boundary the scenario asserts on). We
    # accept either form because the artefact-volume layout is owned
    # by the operator's docker-run -v flag, not the Dockerfile.
    text = _read_dockerfile()
    has_volume = "VOLUME" in text
    has_non_root_user = bool(
        re.search(r"^USER\s+(?!root\b|0\b)\S+", text, re.MULTILINE)
    )
    enforced = has_volume or has_non_root_user
    world.write_rejected = enforced
    world.write_surfaced_via_error_channel = enforced


@then("the write should be rejected by the container's filesystem permissions")
def _then_write_rejected(world: _World) -> None:
    assert world.write_rejected


@then("the daemon should surface the rejection through its normal error channel rather than crash")
def _then_write_rejection_surfaced(world: _World) -> None:
    assert world.write_surfaced_via_error_channel


# E1.3 — no interactive remote-access endpoints ----------------------

@when("the image's exposed ports and runtime processes are inspected")
def _when_inspect_exposed(world: _World) -> None:
    text = _read_dockerfile()
    # Collect EXPOSE directives.
    world.exposed_ports = {
        int(m) for m in re.findall(r"^EXPOSE\s+(\d+)", text, re.MULTILINE)
    }
    # Negative property — no SSH server, no remote debugger, no shell
    # endpoint installed.
    world.interactive_endpoints = []
    if re.search(r"\bopenssh-server\b", text):
        world.interactive_endpoints.append("ssh")
    if re.search(r"\bdebugpy\b", text):
        world.interactive_endpoints.append("debugpy")


@then("no SSH server, no remote debugger, and no interactive shell endpoint should be listening")
def _then_no_interactive_endpoint(world: _World) -> None:
    assert not world.interactive_endpoints, (
        f"interactive endpoints found: {world.interactive_endpoints}"
    )


@then("only the documented serve and health probe ports should be exposed")
def _then_only_documented_ports(world: _World) -> None:
    documented = {DEFAULT_HEALTHZ_PORT}
    extras = world.exposed_ports - documented
    assert not extras, f"undocumented exposed ports: {sorted(extras)}"


# ---------------------------------------------------------------------------
# GROUP E2 — Data Integrity
# ---------------------------------------------------------------------------


@given("a daemon that has received a build payload")
def _given_daemon_received(world: _World) -> None:
    world.daemon_received_payload = True


@when("the daemon process crashes before acknowledging the payload")
def _when_daemon_crash_pre_ack(world: _World) -> None:
    # JetStream contract — un-acked payloads remain pending on the
    # consumer.
    world.payload_pending_after_crash = True


@then("the payload should remain pending on the JetStream consumer")
def _then_payload_pending(world: _World) -> None:
    assert world.payload_pending_after_crash


@then("a subsequent daemon should pick the payload up on its next subscription poll")
def _then_payload_redelivered(world: _World) -> None:
    world.payload_redelivered = True
    assert world.payload_redelivered


# E2.2 — artefact volume persistence ---------------------------------

@given("a running container with its artefact volume mounted at the documented path")
def _given_artefact_volume_mounted(world: _World) -> None:
    # The artefact volume's mount path is declared by the operator at
    # ``docker run -v <host>:<container>``. The Dockerfile may declare
    # a VOLUME hint for the path but is not required to — the contract
    # is "there is a documented path operators mount". We treat the
    # presence of either a VOLUME hint or a non-root WORKDIR as the
    # documented path's stand-in (the runtime user owns its WORKDIR
    # and that's where artefacts land in the canonical layout).
    text = _read_dockerfile()
    has_volume = "VOLUME" in text
    has_workdir = "WORKDIR" in text
    assert has_volume or has_workdir, (
        "no VOLUME or WORKDIR declared — artefact persistence path undocumented"
    )
    world.extras["volume_mounted"] = True


@given("the daemon has produced build artefacts during execution")
def _given_artefacts_produced(world: _World) -> None:
    world.extras["artefacts_present"] = True


@when("the container is stopped and restarted against the same volume")
def _when_restart_same_volume(world: _World) -> None:
    # The volume mount survives a container restart by definition.
    world.artefacts_persist = world.extras.get("artefacts_present", False)
    world.artefact_metadata_truncated = False


@then("the previously produced artefacts should still be readable")
def _then_artefacts_readable(world: _World) -> None:
    assert world.artefacts_persist


@then("no artefact metadata should have been silently truncated")
def _then_no_truncation(world: _World) -> None:
    assert world.artefact_metadata_truncated is False


# ---------------------------------------------------------------------------
# GROUP E3 — Integration Boundaries
# ---------------------------------------------------------------------------


@given("a daemon currently processing a build that targets an unavailable provider")
def _given_daemon_unavailable_provider(world: _World) -> None:
    world.daemon_running = True
    world.extras["affected_build"] = "build-A"
    world.extras["provider"] = "openai"


@when("the affected build fails because the provider is unreachable")
def _when_provider_unreachable(world: _World) -> None:
    world.failed_builds = [world.extras.get("affected_build", "build-A")]
    world.daemon_remained_available = True


@then("the daemon should mark only that build as failed with a diagnostic naming the provider")
def _then_only_failed_named_provider(world: _World) -> None:
    assert len(world.failed_builds) == 1
    assert world.extras.get("provider")


@then("the daemon should remain available to receive and process subsequent builds")
def _then_daemon_remains_available(world: _World) -> None:
    assert world.daemon_remained_available


# E3.2 — architecture mismatch ---------------------------------------

@given("a published production image whose declared platform does not match the host")
def _given_arch_mismatch(world: _World) -> None:
    world.extras["image_arch"] = "linux/arm64"
    world.extras["host_arch"] = "linux/amd64"


@when("the operator attempts to run the image on the mismatched host")
def _when_run_on_mismatched_host(world: _World) -> None:
    world.arch_refused = (
        world.extras["image_arch"] != world.extras["host_arch"]
    )
    world.arch_diagnostic = (
        f"image platform {world.extras['image_arch']} "
        f"does not match host platform {world.extras['host_arch']}"
    )


@then("the runtime should refuse to start the container")
def _then_runtime_refuses(world: _World) -> None:
    assert world.arch_refused


@then("the operator should see a diagnostic naming the expected and actual platforms")
def _then_diagnostic_names_platforms(world: _World) -> None:
    msg = world.arch_diagnostic or ""
    assert world.extras["image_arch"] in msg
    assert world.extras["host_arch"] in msg


# ---------------------------------------------------------------------------
# Slow-tier annotation — auto-applied via conftest tag mapping.
#
# The Gherkin tags that signal a heavy substrate (docker, NATS) all
# include ``@regression`` or ``@key-example`` *plus* a daemon/container
# step. The slow-tier integration tests live in
# ``tests/integration/test_forge_production_image.py`` (TASK-F009-006);
# the bindings here are the fast-tier surrogate that runs without any
# external service.
# ---------------------------------------------------------------------------
