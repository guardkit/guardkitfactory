---
complexity: 5
consumer_context:
- consumes: BUILDKIT_INVOCATION
  driver: bash via actions/checkout + docker buildx-action
  format_note: Workflow must invoke scripts/build-image.sh — never reproduce the docker
    buildx command inline. T6's drift detector will fail CI if the workflow embeds
    the BuildKit string directly.
  framework: GitHub Actions YAML invoking scripts/build-image.sh
  task: TASK-F009-005
created: 2026-04-30 00:00:00+00:00
dependencies:
- TASK-F009-005
feature_id: FEAT-FORGE-009
id: TASK-F009-007
implementation_mode: task-work
parent_review: TASK-REV-F009
priority: high
status: design_approved
tags:
- ci
- github-actions
- image-build
- image-size
- secret-scan
- feat-forge-009
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Add GitHub Actions workflow that builds and smoke-tests the production image
updated: 2026-04-30 00:00:00+00:00
wave: 3
---

# Task: Add GitHub Actions workflow that builds and smoke-tests the production image

## Description

Create the CI workflow that closes binding-shape item 7 (CI builds +
smoke-tests the image on every PR touching the production-image surface)
and acceptance criteria AC-F (no real provider keys), AC-I (CI gate on
PR), and the image-size budget regression check (B4 / ASSUM-003).

The workflow:
1. Triggers on pull requests touching `Dockerfile`, `pyproject.toml`,
   `src/forge/**`, `scripts/build-image.sh`, or itself (D5 scenario)
2. Checks out forge AND its sibling `nats-core` working tree (so
   `--build-context nats-core=../nats-core` resolves)
3. Runs `scripts/build-image.sh` (Contract A consumer — does NOT
   reproduce the BuildKit command inline)
4. Asserts the resulting image's uncompressed size ≤ 1.0 GB
   (`docker image inspect | jq '.[0].Size'`; ASSUM-003)
5. Runs the `@smoke` BDD scenario set (T6) against the built image
6. Scans every layer for real provider key material (regex for
   `sk-...`, `AIza...`, etc.); fails if any matches a non-allowlisted
   pattern (C1 scenario, AC-F)
7. Runs an architecture-mismatch dry-check by inspecting the image's
   declared platform (E3.2 scenario)

Files created:
- NEW `.github/workflows/forge-image.yml`

## Acceptance Criteria

- [ ] Workflow triggers on PRs that change any of: `Dockerfile`,
      `pyproject.toml`, `src/forge/**`, `scripts/build-image.sh`,
      `.github/workflows/forge-image.yml` (D5 scenario; AC-I)
- [ ] Workflow checks out forge AND `nats-core` (using
      `actions/checkout@vN` twice, one with `repository:
      appmilla/nats-core` and `path: ../nats-core`)
- [ ] Workflow invokes `scripts/build-image.sh` — does NOT inline the
      `docker buildx build --build-context ...` command (Contract A
      consumer; T6's drift detector enforces this)
- [ ] Image-size check fails the job if the uncompressed image exceeds
      1.0 GB; failure message names both the budget and the actual size
      (B4 scenario, ASSUM-003)
- [ ] Smoke-set runner: `pytest -m smoke tests/bdd/` runs against the
      built image and must pass (uses T6's bindings)
- [ ] Provider-key scan: scans every image layer for `sk-`, `AIza`,
      `xoxb-`, etc. — fails the build if any are found outside an
      allowlist (e.g. `EXAMPLE_KEY_FOR_TESTING`); covers C1 / AC-F
- [ ] Architecture-mismatch check: workflow runs on `ubuntu-latest`
      (linux/amd64) and asserts the built image's platform metadata
      matches; documents the cross-arch failure mode for ARM runners
      (E3.2 scenario)
- [ ] Workflow registers a status check named
      `forge-production-image / build-and-smoke-test` so it can be made
      a required check on the `main` branch
- [ ] All modified files pass project-configured lint/format checks
      with zero errors (yamllint for the workflow file)

## Test Requirements

- [ ] Workflow YAML validates against `actionlint` (or equivalent)
- [ ] Workflow file does NOT contain the literal string
      `docker buildx build` — Contract A drift detector would catch
      this in T6, but adding a unit-level grep here gives a faster
      signal
- [ ] A representative dry-run via `act` (or local YAML inspection)
      confirms the trigger paths cover the four required surfaces

## Seam Tests

```python
"""Seam test: verify BUILDKIT_INVOCATION contract from TASK-F009-005."""
from pathlib import Path

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("BUILDKIT_INVOCATION")
def test_workflow_does_not_inline_buildx_command():
    """Verify the CI workflow consumes scripts/build-image.sh and never
    inlines the docker buildx command.

    Contract: Workflow must invoke scripts/build-image.sh — never
    reproduce the docker buildx command inline. T6's drift detector
    will fail CI if the workflow embeds the BuildKit string directly.
    Producer: TASK-F009-005
    """
    workflow = Path(".github/workflows/forge-image.yml")
    assert workflow.exists(), "forge-image.yml must exist"

    content = workflow.read_text()

    # Format assertion derived from §4 contract constraint:
    # The workflow must call the script, not inline the buildx command.
    assert "scripts/build-image.sh" in content, (
        "Workflow must invoke scripts/build-image.sh"
    )
    # Catch the failure mode the contract is designed to prevent:
    forbidden_inline = "docker buildx build --build-context nats-core="
    assert forbidden_inline not in content, (
        f"Workflow inlines the BuildKit command. Replace with a call "
        f"to scripts/build-image.sh to honour Contract A."
    )
```

## Implementation Notes

The image-size budget is **uncompressed** (per ASSUM-003). Use:

```bash
SIZE=$(docker image inspect forge:production-validation \
    --format '{{.Size}}')
BUDGET=1073741824  # 1.0 GB in bytes
if [ "$SIZE" -gt "$BUDGET" ]; then
    echo "::error::Image size $SIZE exceeds budget $BUDGET" >&2
    exit 1
fi
```

For the secret-scan, prefer `gitleaks` or `trufflehog` over a regex
roll-your-own — both have well-tuned allowlists and avoid the false-
positive trap.

Sibling-checkout pattern for `nats-core`: GitHub Actions' default
checkout puts the main repo at `$GITHUB_WORKSPACE`. To get
`../nats-core` resolvable from the forge directory, check forge out at
`$GITHUB_WORKSPACE/forge` and nats-core at `$GITHUB_WORKSPACE/nats-core`,
then `cd $GITHUB_WORKSPACE` before invoking `scripts/build-image.sh`.