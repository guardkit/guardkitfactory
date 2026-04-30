---
id: TASK-F009-008
title: Fold runbook §6 gating callout and append history entry
task_type: documentation
status: backlog
priority: high
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
parent_review: TASK-REV-F009
feature_id: FEAT-FORGE-009
wave: 4
implementation_mode: direct
complexity: 3
dependencies: [TASK-F009-006, TASK-F009-007]
tags: [documentation, runbook, history, gating-callout, feat-forge-009]
consumer_context:
  - task: TASK-F009-005
    consumes: BUILDKIT_INVOCATION
    framework: "Markdown shell-block in runbook §6.1"
    driver: "verbatim copy-paste"
    format_note: "Runbook §6.1 must replace the current 'docker build -t forge:production-validation -f Dockerfile .' with the canonical BuildKit invocation. Operator runs the shell block from forge's parent directory; the runbook must say so."
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Fold runbook §6 gating callout and append history entry

## Description

Close the loop on FEAT-FORGE-009 by removing the gating callout from
`RUNBOOK-FEAT-FORGE-008-validation.md` §6, replacing the bare
`docker build` command in §6.1 with the canonical BuildKit invocation,
and appending a history entry that records the merge.

This task is **strictly sequential** after Wave 3. It must not merge
until T6 and T7 are both green on `main` — otherwise the runbook would
falsely declare Phase 6 reachable.

Files edited:
- EDIT `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` §6:
  - Remove the "🚧 Gated on FEAT-FORGE-009" callout block (lines 757–773)
  - Replace the §6.1 `docker build -t forge:production-validation -f
    Dockerfile .` with the BuildKit invocation (Contract A consumer)
  - Add a one-line note that the §6.1 build must run from forge's
    parent directory
- APPEND `docs/history/command-history.md` — entry recording the
  feature merge with the canonical-freeze marker `[as of commit <sha>]`
- MOVE `tasks/backlog/FEAT-FORGE-009-production-image.md` (the original
  stub) → `tasks/completed/2026-04/` with status updated and a closing
  note pointing at this PR's merge commit

## Acceptance Criteria

- [ ] Gating callout block in `RUNBOOK-FEAT-FORGE-008-validation.md`
      §6 (lines 757–773 of the pre-edit file) is removed (AC-J)
- [ ] §6.1 build command is replaced with:
      `docker buildx build --build-context nats-core=../nats-core
      -t forge:production-validation -f forge/Dockerfile forge/`
      (Contract A; verbatim, drift-tested by T6)
- [ ] §6.1 has a copy-pastable shell block that `cd`s to forge's
      parent directory before invoking buildx (canonical-freeze §3.4
      requirement: no host-side mutation of pyproject/symlinks/.env;
      A5 scenario)
- [ ] §6.1 also documents that the sibling `nats-core` working tree
      must be present at `../nats-core` before the build is invoked
- [ ] `docs/history/command-history.md` has a new entry titled
      "FEAT-FORGE-009 merge" with the merge SHA and a one-paragraph
      summary of what landed
- [ ] `tasks/backlog/FEAT-FORGE-009-production-image.md` is moved
      to `tasks/completed/2026-04/` (or the appropriate completion
      bucket) with a "Closed by FEAT-FORGE-009 merge <sha>" footer
- [ ] No other task in this feature has merged yet that would have
      been blocked by an active gating callout (sanity check)

## Test Requirements

- [ ] Documentation lint: markdown files pass `markdownlint` (if
      configured) or visual inspection
- [ ] Cross-reference test: `grep -n "Gated on FEAT-FORGE-009"
      docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` returns no
      matches after the fold
- [ ] BuildKit invocation literal-match: `grep -F "docker buildx build
      --build-context nats-core=../nats-core" docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`
      returns at least one match (and zero matches for the old `docker
      build -t forge:production-validation -f Dockerfile .` line)

## Seam Tests

```python
"""Seam test: verify BUILDKIT_INVOCATION contract from TASK-F009-005."""
from pathlib import Path

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("BUILDKIT_INVOCATION")
def test_runbook_section6_uses_buildkit_invocation():
    """Verify runbook §6.1 has been folded to use the canonical BuildKit
    invocation.

    Contract: Runbook §6.1 must replace the current 'docker build -t
    forge:production-validation -f Dockerfile .' with the canonical
    BuildKit invocation. Operator runs the shell block from forge's
    parent directory; the runbook must say so.
    Producer: TASK-F009-005
    """
    runbook = Path(
        "docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md"
    )
    assert runbook.exists(), "runbook missing"

    content = runbook.read_text()

    # Format assertion derived from §4 contract constraint:
    canonical = (
        "docker buildx build --build-context nats-core=../nats-core "
        "-t forge:production-validation -f forge/Dockerfile forge/"
    )
    assert canonical in content, (
        f"Runbook §6.1 does not contain the canonical BuildKit "
        f"invocation. Expected substring:\n  {canonical}"
    )

    # The pre-fold gating callout must be gone.
    assert "Gated on FEAT-FORGE-009" not in content, (
        "Gating callout still present — fold not complete"
    )

    # The pre-fold bare-docker invocation must be gone.
    pre_fold = "docker build -t forge:production-validation -f Dockerfile ."
    assert pre_fold not in content, (
        f"Pre-fold invocation still present in runbook:\n  {pre_fold}"
    )
```

## Implementation Notes

This is a documentation-only task (`task_type: documentation`).
CoachValidator skips architectural review and applies the documentation
quality gate profile (markdown lint only).

The history append should follow the existing `command-history.md`
format — see prior entries for tone and structure (one paragraph per
merge, with a `[as of commit <sha>]` marker for canonical-freeze
verification).

Do **not** open this PR until `main` shows T6 and T7 green. Wave 4 is
explicitly sequential precisely so this AC-J fold lands as a true
signal, not a premature one.
