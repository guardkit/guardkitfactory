---
id: TASK-F8-004
title: "Restore AC-008 single-ownership of evidence_priors (recovery.py)"
task_type: implementation
status: completed
priority: high
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-F8-004/
organized_files:
  - TASK-F8-004-recovery-evidence-priors-helper.md
previous_state: in_review
state_transition_reason: "Acceptance criteria AC-1..AC-5 satisfied; quality gates green (3769 passed, 0 failed); AC-008 single-ownership static-grep guard restored to green."
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 1
implementation_mode: task-work
complexity: 4
dependencies: []
tags: [refactor, ac-008, single-ownership, recovery, approval-publisher, feat-forge-008, f008-val-004]
related_files:
  - src/forge/lifecycle/recovery.py
  - src/forge/adapters/nats/approval_publisher.py
  - tests/forge/test_approval_publisher.py
test_results:
  status: passed
  coverage: null  # not measured for this targeted refactor
  last_run: 2026-04-30T00:00:00Z
  command: "pytest tests/forge/test_approval_publisher.py + full sweep --ignore=tests/bdd/test_infrastructure_coordination.py"
  passed: 3769
  skipped: 1
  failed: 0
  notes: |
    AC-3 static-grep guard (TestSingleOwnership) green.
    AC-5 helper tests (TestBuildRecoveryApprovalEnvelope, 7 tests) green.
    Removed open-coded `_build_recovery_approval_envelope` from
    src/forge/lifecycle/recovery.py; added public
    `build_recovery_approval_envelope(BuildRow)` to
    src/forge/adapters/nats/approval_publisher.py with private
    `_build_recovery_approval_details` for the twelve-key shape (eleven
    canonical + recovery=True). recovery.py no longer references the
    "evidence_priors" literal anywhere.
---

# Task: Restore AC-008 single-ownership of `evidence_priors` (recovery.py)

## Description

`forge.lifecycle.recovery._build_recovery_approval_envelope` open-codes the
eleven-key `details` dict shape — including the literal `"evidence_priors"`
key (`recovery.py:255-271`). This violates AC-008 from FEAT-FORGE-004,
which states that **only `forge.adapters.nats.approval_publisher` may
construct the `details` dict shape**.

The static-grep guard at
`tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors`
is precisely the failure-class catcher: it scans `src/forge/**.py` for the
literal `"evidence_priors"` and asserts every other module is offender-free.

The test currently fails:

```
FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership
       ::test_no_other_module_in_forge_constructs_evidence_priors
  AssertionError: Other modules reconstruct details shape (AC-008):
    [PosixPath('src/forge/lifecycle/recovery.py')]
```

### Recommended approach (per architectural review §6 SOLID)

**Move `_build_recovery_approval_envelope` itself into the
`approval_publisher` module** — keeps the dict shape under one roof, makes
the recovery flag a parameter rather than two near-duplicate constructors.

Suggested public API on `forge.adapters.nats.approval_publisher`:

```python
def build_recovery_approval_envelope(build: BuildRow) -> MessageEnvelope:
    """Build a recovery-flavoured approval envelope (sc_004 verbatim request_id).

    The recovery envelope re-issues the original
    ``builds.pending_approval_request_id`` and carries a stripped details
    dict with ``recovery=True``. The full details shape is constructed by
    this module so AC-008 single-ownership is preserved.
    """
    ...
```

Recovery.py imports and calls:

```python
from forge.adapters.nats.approval_publisher import build_recovery_approval_envelope

# inside _handle_paused or _build_recovery_approval_envelope's caller:
envelope = build_recovery_approval_envelope(build)
await approval_publisher.publish_request(envelope)
```

The recovery module then has zero references to the literal
`"evidence_priors"`, restoring AC-008.

## Acceptance Criteria

- [ ] **AC-1**: `forge.adapters.nats.approval_publisher` exports a public
      helper that constructs the recovery-flavoured `MessageEnvelope`
      (or just the `details` dict — implementer's choice, but with a
      single-source-of-truth for the eleven-key shape).
- [ ] **AC-2**: `forge.lifecycle.recovery` no longer references the
      literal `"evidence_priors"`. The previous in-module helper
      `_build_recovery_approval_envelope` either delegates entirely to the
      approval_publisher helper or is moved out altogether.
- [ ] **AC-3**:
      `tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors`
      goes green (the static-grep returns an empty `offenders` list).
- [ ] **AC-4**: Crash-recovery scenarios still produce a PAUSED-state
      republish with `details["recovery"] = True` and the same eleven
      keys. Existing test
      `tests/forge/lifecycle/test_recovery.py` (or equivalent) continues
      to pass; if a unit test previously verified the open-coded shape
      against `recovery.py`, point it at the new helper instead.
- [ ] **AC-5**: The new helper has a unit test in
      `tests/forge/adapters/nats/test_approval_publisher.py` (or wherever
      approval_publisher tests live) covering: (a) `recovery=True` flag,
      (b) verbatim `request_id` round-trip, (c) eleven-key shape on
      `details`.

## Implementation Notes

- The eleven keys per the AC-008 `expected_keys` set in
  `tests/forge/test_approval_publisher.py:545-557` are: `build_id`,
  `feature_id`, `stage_label`, `gate_mode`, `coach_score`,
  `criterion_breakdown`, `detection_findings`, `rationale`,
  `evidence_priors`, `artefact_paths`, `resume_options`. The recovery
  flavour adds a twelfth key `recovery: True`.
- Look at the existing `_build_approval_details` helper in
  `approval_publisher.py` (referenced in the test at line 539-544) and
  pattern the recovery variant after it.
- Late imports of `nats_core.envelope` / `nats_core.events` already exist
  in recovery.py for fast-startup reasons. The helper move can keep the
  late-import idiom inside `approval_publisher`, or hoist it module-level
  there since approval_publisher is already a NATS-coupled module.

## Out of scope

- Refactoring the rest of `recovery.py`. Only the open-coded dict shape
  needs to move; the per-state handlers and the boot reconciliation
  flow stay put.
- Changing the `details` dict shape itself (that would be a
  FEAT-FORGE-004 follow-up, not a fix task).
