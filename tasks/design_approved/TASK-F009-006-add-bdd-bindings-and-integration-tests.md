---
complexity: 6
consumer_context:
- consumes: BUILDKIT_INVOCATION
  driver: subprocess.run
  format_note: Tests must invoke scripts/build-image.sh — never reproduce the docker
    buildx command inline (drift-prevention)
  framework: pytest fixtures invoking subprocess
  task: TASK-F009-005
- consumes: HEALTHZ_PORT
  driver: httpx
  format_note: Test client must read forge.cli.serve.DEFAULT_HEALTHZ_PORT — never
    hardcode 8080
  framework: httpx HTTP client probing the running container
  task: TASK-F009-001
- consumes: JETSTREAM_DURABLE_NAME
  driver: nats-core (sibling editable)
  format_note: Multi-replica test (D2) must read forge.cli.serve.DEFAULT_DURABLE_NAME
    and assert JetStream consumer_info() reports the same name
  framework: nats-core JetStream client used in test fixtures
  task: TASK-F009-001
created: 2026-04-30 00:00:00+00:00
dependencies:
- TASK-F009-003
- TASK-F009-004
- TASK-F009-005
feature_id: FEAT-FORGE-009
id: TASK-F009-006
implementation_mode: task-work
parent_review: TASK-REV-F009
priority: high
status: design_approved
tags:
- testing
- bdd
- pytest-bdd
- integration
- feat-forge-009
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: Add BDD bindings and integration tests for the production image
updated: 2026-04-30 00:00:00+00:00
wave: 3
---

# Task: Add BDD bindings and integration tests for the production image

## Description

Bind the 27 scenarios in `features/forge-production-image/forge-production-image.feature`
to pytest-bdd step implementations and add image-build integration
tests that exercise the full production image (not the dev install).

This task is the validation layer for everything Wave 1 and 2 produced.
It also surfaces the ARFS structural assertion (A4 — the manifest must
list every fleet tool) by running the manifest-build code path *inside*
the built image.

Files created:
- NEW `tests/bdd/test_forge_production_image.py` — pytest-bdd step
  implementations for all 27 scenarios (A1–E3.2)
- NEW `tests/integration/test_forge_serve_image.py` — integration tests
  that build the image via `scripts/build-image.sh`, run it, and exercise
  the daemon end-to-end against a Testcontainers NATS broker
- NEW `tests/integration/test_forge_serve_arfs.py` — ARFS gate test
  that runs `docker run forge:test python -c "from forge.fleet.manifest
  import build_manifest; ..."` inside the image and asserts every tool
  is present
- NEW `tests/integration/test_buildkit_invocation_drift.py` — Contract A
  drift detector (greps `scripts/build-image.sh`, `.github/workflows/
  forge-image.yml`, and `RUNBOOK-FEAT-FORGE-008-validation.md` for the
  literal BuildKit invocation; fails if any diverge)

## Acceptance Criteria

- [ ] All 27 scenarios in `features/forge-production-image/forge-production-image.feature`
      have pytest-bdd step bindings; `pytest tests/bdd/test_forge_production_image.py`
      runs all 27 (some may skip on hosts without docker/NATS)
- [ ] `@smoke` set (6 scenarios: A1, A2, A3, C1, C2, E1.1) runs in
      under 5 min on a host with docker + NATS available
- [ ] `@regression` set (4 scenarios: D1, D5, E2.1) plus the smoke set
      runs in under 15 min
- [ ] ARFS test asserts every tool from `src/forge/fleet/manifest.py`
      lines 50, 71, 86, 101, 113 (per ASSUM-009) is present in the image's
      manifest: `forge_greenfield`, `forge_feature`, `forge_review_fix`,
      `forge_status`, `forge_cancel` (A4 scenario, AC-D)
- [ ] D2 multi-replica test starts two daemon containers against the
      same NATS broker, publishes one payload, asserts exactly-once
      delivery using the durable consumer name from
      `forge.cli.serve.DEFAULT_DURABLE_NAME`
- [ ] D3 broker-outage test stops the broker for ~5 s, restarts it,
      publishes during outage, asserts delivery on recovery
- [ ] BuildKit invocation drift test (Contract A literal-match) compares
      the canonical string across all three consumer files and fails on
      drift
- [ ] Test markers `@smoke`, `@regression`, `@key-example`, `@boundary`,
      `@negative`, `@edge-case` map to pytest marks `smoke`, `regression`,
      etc. — selectable via `pytest -m smoke`

## Test Requirements

This task IS the test suite — it has no upstream test requirement
beyond pytest-bdd's own conventions. Coach validates that scenario
bindings exist for all 27 scenarios.

## Seam Tests

The Contract drift detector below is itself a seam test — it lives in
this task because no other task is well-positioned to catch
cross-file Contract A drift.

```python
"""Seam test: verify BUILDKIT_INVOCATION contract from TASK-F009-005."""
from pathlib import Path

import pytest

CANONICAL_INVOCATION = (
    "docker buildx build --build-context nats-core=../nats-core "
    "-t forge:production-validation -f forge/Dockerfile forge/"
)


@pytest.mark.seam
@pytest.mark.integration_contract("BUILDKIT_INVOCATION")
def test_buildkit_invocation_no_drift():
    """Verify BUILDKIT_INVOCATION matches across all consumers.

    Contract: Tests must invoke scripts/build-image.sh — never reproduce
    the docker buildx command inline (drift-prevention).
    Producer: TASK-F009-005

    Consumers checked:
      1. scripts/build-image.sh (T5 producer)
      2. .github/workflows/forge-image.yml (T7 consumer)
      3. docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md (T8 consumer)
    """
    paths = [
        Path("scripts/build-image.sh"),
        Path(".github/workflows/forge-image.yml"),
        Path("docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md"),
    ]

    for p in paths:
        assert p.exists(), f"{p} missing — Contract A consumer not yet wired"
        content = p.read_text()
        assert CANONICAL_INVOCATION in content, (
            f"{p} does not contain the canonical BUILDKIT_INVOCATION. "
            f"Drift detected — re-align with scripts/build-image.sh."
        )
```

## Implementation Notes

The image-build integration tests are slow. Tag them `@pytest.mark.slow`
and gate the default `pytest` invocation to skip them; CI runs them via
`pytest -m slow` in T7's workflow.

ARFS test must run **inside** the built image, not against the dev
install — the failure mode it's catching is "manifest-build code path
broken because forge wasn't installed as a proper distribution".

For the multi-replica D2 test, use Testcontainers' NATS image and start
two `docker run` instances of `forge:production-validation` against
the same broker.

T6 must not modify `Dockerfile`, `scripts/`, or `src/forge/` — it
only adds tests. If a test failure surfaces a bug in T3/T4/T5, file
a fix as a Wave-2 follow-up rather than patching here.