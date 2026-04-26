"""Pytest-bdd wiring for FEAT-FORGE-005 / TASK-GCI-007 scenarios.

This module is the executable surface for the BDD oracle of the
gh-adapter task. It binds the two ``@task:TASK-GCI-007`` Gherkin
scenarios in
``features/guardkit-command-invocation-engine/guardkit-command-invocation-engine.feature``
to step functions that drive the real
:func:`forge.adapters.gh.operations.create_pr` adapter through a mocked
subprocess seam (``operations._execute``) — no ``gh`` binary is invoked
and no network call is made.

Scope
-----

Wired here:

- ``@key-example`` — *Forge opens a pull request for the build through
  the version-control adapter*. Drives ``create_pr`` with ``GH_TOKEN``
  set, asserts the returned :class:`PRResult` is ``status="success"``
  with ``pr_url`` populated and that the subprocess command targeted the
  configured base branch.
- ``@negative`` — *A pull-request creation without GitHub credentials
  returns a structured error*. Drives ``create_pr`` with ``GH_TOKEN``
  unset, asserts the returned :class:`PRResult` carries
  ``error_code="missing_credentials"`` and that ``operations._execute``
  was never invoked (i.e. no pull request was ever created).

Other ``@task:TASK-GCI-XXX`` scenarios in the same feature file belong
to sibling tasks (TASK-GCI-003 / 004 / 005 / 006 / 008 / 009 / 010);
their step bindings live with those tasks. Only the TASK-GCI-007 pair
is collected here.

Background steps
----------------

The feature-level Background ("Forge is running inside an ephemeral
build worktree" / "a project configuration file defines …" / "a context
manifest is available …") is a no-op for the gh adapter — none of those
preconditions affect ``create_pr`` behaviour. They are still bound to
inert ``given`` steps so pytest-bdd can resolve every step in the
scenario without Background-step errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenario, then, when

from forge.adapters.gh import operations
from forge.adapters.git.models import PRResult


FEATURE_FILE = (
    "guardkit-command-invocation-engine/guardkit-command-invocation-engine.feature"
)


# ---------------------------------------------------------------------------
# Scenario decorators — only the @task:TASK-GCI-007 pair
# ---------------------------------------------------------------------------


@pytest.mark.key_example
@scenario(
    FEATURE_FILE,
    "Forge opens a pull request for the build through the version-control adapter",
)
def test_key_example_create_pr_success() -> None:
    """@key-example — TASK-GCI-007 happy-path PR creation."""


@pytest.mark.negative
@scenario(
    FEATURE_FILE,
    "A pull-request creation without GitHub credentials returns a structured error",
)
def test_negative_create_pr_missing_credentials() -> None:
    """@negative — TASK-GCI-007 missing-credential structured error."""


# ---------------------------------------------------------------------------
# Per-scenario world fixture (kept local so the GCI suite does not
# collide with the FEAT-FORGE-002 ``world`` fixture in conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def gci_world() -> dict[str, Any]:
    """Mutable scratch dict threading state across Given/When/Then steps."""
    return {}


# ---------------------------------------------------------------------------
# Background — inert bindings (preconditions don't affect create_pr)
# ---------------------------------------------------------------------------


@given("Forge is running inside an ephemeral build worktree")
def _bg_forge_in_worktree(gci_world: dict[str, Any]) -> None:
    # The worktree is represented as a Path string handed to create_pr.
    # We use a plausible path matching the ADR-ARCH-028 convention.
    gci_world["worktree"] = Path("/var/forge/builds/B-bdd")


@given(
    "a project configuration file defines the shell, filesystem, "
    "and network permissions"
)
def _bg_permissions_defined(gci_world: dict[str, Any]) -> None:
    # ADR-ARCH-023 makes permissions constitutional and enforced by the
    # framework, not by the adapter — no-op for create_pr.
    gci_world["permissions_defined"] = True


@given(
    "a context manifest is available at the repo root describing documents "
    "grouped by category"
)
def _bg_manifest_available(gci_world: dict[str, Any]) -> None:
    # gh adapter does not consult the context manifest — no-op.
    gci_world["manifest_available"] = True


# ---------------------------------------------------------------------------
# @key-example: Forge opens a pull request through the version-control adapter
# ---------------------------------------------------------------------------


@given("a build has committed and pushed its work to a remote branch")
def _given_build_pushed(
    gci_world: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pre-conditions for the happy path: GH_TOKEN must be set, and the
    # subprocess seam returns gh's canonical PR-URL stdout.
    monkeypatch.setenv("GH_TOKEN", "ghp_bdd-token")
    pr_url = "https://github.com/owner/repo/pull/77"
    gci_world["expected_pr_url"] = pr_url
    gci_world["execute_mock"] = AsyncMock(return_value=(0, pr_url + "\n", ""))
    gci_world["base_branch"] = "main"
    monkeypatch.setattr(operations, "_execute", gci_world["execute_mock"])


@when("Forge asks the version-control adapter to open a pull request")
def _when_open_pr(gci_world: dict[str, Any]) -> None:
    # Drive the real adapter; both scenarios share this When-step.
    # ``asyncio.run`` creates and closes a fresh event loop per call —
    # safe inside synchronous pytest-bdd step bodies and avoids the
    # ``get_event_loop`` deprecation in 3.12+.
    import asyncio

    base = gci_world.get("base_branch", "main")
    gci_world["result"] = asyncio.run(
        operations.create_pr(
            worktree=gci_world["worktree"],
            title="BDD oracle: open a PR",
            body="Driven by pytest-bdd against the real adapter.",
            base=base,
        )
    )


@then("the adapter should create the pull request against the configured base branch")
def _then_pr_created_against_base(gci_world: dict[str, Any]) -> None:
    execute_mock: AsyncMock = gci_world["execute_mock"]
    execute_mock.assert_awaited_once()
    args, kwargs = execute_mock.call_args
    command = list(kwargs.get("command") or args[0])
    assert command[0] == "gh"
    assert command[1:3] == ["pr", "create"]
    assert "--base" in command
    base_idx = command.index("--base")
    assert command[base_idx + 1] == gci_world["base_branch"]
    # Worktree confinement: subprocess cwd is the build's worktree.
    cwd = kwargs.get("cwd") or args[1]
    assert cwd == str(gci_world["worktree"])


@then("the invocation should return the pull-request URL as a structured result")
def _then_returns_pr_url_structured(gci_world: dict[str, Any]) -> None:
    result: PRResult = gci_world["result"]
    assert isinstance(result, PRResult)
    assert result.status == "success"
    assert result.pr_url == gci_world["expected_pr_url"]
    assert result.pr_number == 77
    assert result.error_code is None
    assert result.stderr is None


# ---------------------------------------------------------------------------
# @negative: missing-credential structured error
# ---------------------------------------------------------------------------


@given("the runtime has no GitHub access credentials available")
def _given_no_gh_credentials(
    gci_world: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both unset and empty must short-circuit identically; the scenario
    # phrasing covers both. Use ``delenv`` for the unset variant.
    monkeypatch.delenv("GH_TOKEN", raising=False)
    # Install an execute spy so the Then-step can assert non-invocation.
    spy = AsyncMock()
    gci_world["execute_mock"] = spy
    monkeypatch.setattr(operations, "_execute", spy)


@then("the adapter should return a structured error explaining the credential is missing")
def _then_structured_missing_credential_error(gci_world: dict[str, Any]) -> None:
    result: PRResult = gci_world["result"]
    assert isinstance(result, PRResult)
    assert result.status == "failed"
    assert result.error_code == "missing_credentials"
    # Stable, machine-readable explanation lives on the stderr field.
    assert result.stderr == "GH_TOKEN not set in environment"
    # Successful-path fields stay None on the structured failure.
    assert result.pr_url is None
    assert result.pr_number is None


@then("no pull request should be created")
def _then_no_pr_created(gci_world: dict[str, Any]) -> None:
    execute_mock: AsyncMock = gci_world["execute_mock"]
    # The pre-flight check must short-circuit before the subprocess
    # seam — gh is never invoked, so no PR can have been created.
    execute_mock.assert_not_called()
    execute_mock.assert_not_awaited()
