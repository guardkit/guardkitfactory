---
id: TASK-F8-003
title: "Add TASK_REVIEW + TASK_WORK to Supervisor _SUBPROCESS_STAGES (BLOCKER)"
task_type: implementation
status: completed
priority: critical
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-F8-003/
organized_files:
  - TASK-F8-003-supervisor-dispatch-task-review.md
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 1
implementation_mode: task-work
complexity: 3
dependencies: []
tags: [supervisor, dispatch, mode-a, regression, blocker, feat-forge-008, f008-val-003]
related_files:
  - src/forge/pipeline/supervisor.py
  - src/forge/pipeline/stage_taxonomy.py
  - tests/integration/test_mode_a_concurrency_and_integrity.py
  - tests/forge/test_supervisor.py
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-30T00:00:00Z
  scope:
    - tests/forge/test_supervisor.py::TestDispatchRouting (7/7 incl. new meta-test)
    - tests/integration/test_mode_a_concurrency_and_integrity.py (13/13)
    - "broader sweep tests/forge/ + tests/integration/: 2076 passed, 0 failed"
---

# Task: Add TASK_REVIEW + TASK_WORK to Supervisor `_SUBPROCESS_STAGES` (BLOCKER)

## Description

This is the FEAT-FORGE-008 Mode A hard regression that the runbook §1.3
called out by name:

> **All Mode A tests green. If any are red, FEAT-FORGE-008 broke the Mode A branch in `Supervisor.next_turn` — stop and triage.**

Two Mode A integration tests are red with the exact signature §1.3 predicts:

```
TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>
  src/forge/pipeline/supervisor.py:1555
```

### Root cause (confirmed)

`StageClass.TASK_REVIEW` and `TASK_WORK` were appended to the canonical
enum in TASK-MBC8-001 (see `src/forge/pipeline/stage_taxonomy.py:87-88`).
The supervisor's multi-feature `next_turn` variant correctly routes both
through `subprocess_dispatcher` at `supervisor.py:1296-1331`.

But `_dispatch` (`supervisor.py:1473-1558`) — the per-turn router — checks
membership in four sets in order: `_SPECIALIST_STAGES`,
`_SUBPROCESS_STAGES`, `is AUTOBUILD`, `is PULL_REQUEST_REVIEW`. The two
new stages are in **none** of these, so the dispatcher falls off the end
and raises the loud `TypeError` at line 1555.

`_SUBPROCESS_STAGES` is defined at `supervisor.py:618-625` and currently
only contains `SYSTEM_ARCH, SYSTEM_DESIGN, FEATURE_SPEC, FEATURE_PLAN`.
Both `TASK_REVIEW` and `TASK_WORK` belong in this frozenset (the
multi-feature `next_turn` already routes them via `subprocess_dispatcher`,
so the routing target is correct).

### Why the missing-feature_id check at supervisor.py:1501 is safe

`PER_FEATURE_STAGES` (defined in `stage_taxonomy.py:150-157`) does NOT
include `TASK_REVIEW` or `TASK_WORK`. So the
`if stage in PER_FEATURE_STAGES and feature_id is None` check at
supervisor.py:1501 won't misfire for the new stages — `TASK_WORK` is in
`PER_FIX_TASK_STAGES` instead, and the cycle planner upstream is the
component that enforces fix-task identity.

## Acceptance Criteria

- [ ] **AC-1**: `_SUBPROCESS_STAGES` (`supervisor.py:618-625`) is extended
      to include `StageClass.TASK_REVIEW` and `StageClass.TASK_WORK`.
- [ ] **AC-2**: A new meta-test (e.g.
      `tests/forge/test_supervisor.py::test_dispatch_covers_every_stage_class`)
      asserts that **every member of `StageClass` has a routing branch in
      `_dispatch`** — i.e., constructs a `DispatchChoice` for each member
      and confirms `_dispatch` does NOT raise `TypeError`. This protects
      against future enum extensions silently falling off the end.
- [ ] **AC-3**:
      `tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each`
      goes green.
- [ ] **AC-4**:
      `tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id`
      goes green.
- [ ] **AC-5**: `pytest -q` reports zero red caused by `_dispatch` routing
      (other reds may persist due to F8-004 / F8-005 and are scoped to
      their own tasks).
- [ ] **AC-6**: The loud-fail `raise TypeError(...)` branch at
      `supervisor.py:1555-1558` is preserved unchanged — it remains the
      defensive guard for future enum extensions.

## Implementation Notes

```python
# src/forge/pipeline/supervisor.py — around line 618
_SUBPROCESS_STAGES: frozenset[StageClass] = field(
    default=frozenset(
        {
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
            StageClass.FEATURE_SPEC,
            StageClass.FEATURE_PLAN,
            StageClass.TASK_REVIEW,   # NEW (FEAT-FORGE-008 + F008-VAL-003)
            StageClass.TASK_WORK,     # NEW (FEAT-FORGE-008 + F008-VAL-003)
        }
    )
)
```

Order TDD-style: write the meta-test from AC-2 first, watch it fail with
the same `TypeError`, then add the two enum members and watch all three
tests go green.

## Out of scope

- Per-fix-task identity enforcement (handled by `ModeCCyclePlanner` —
  TASK-MBC8-004, already shipped).
- Refactoring `_dispatch` to use a stage-class → handler dict (cleaner
  but out of scope for a fix task; existing four-branch structure is
  intentional).
