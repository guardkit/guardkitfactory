# FEAT-FORGE-008 — Mode B Feature & Mode C Review-Fix

Two non-greenfield orchestration modes built on the FEAT-FORGE-001..007
substrate. Mode B drives a single new feature on an existing project
(`/feature-spec → /feature-plan → autobuild → pull-request review`). Mode C
runs a review-fix cycle on existing code (`/task-review → /task-work × N`
with optional pull-request review when commits are pushed).

## At a glance

| | |
|---|---|
| **Feature ID** | FEAT-FORGE-008 |
| **Slug** | `mode-b-feature-and-mode-c-review-fix` |
| **Tasks** | 14 across 7 waves |
| **Aggregate complexity** | 6/10 |
| **Estimated effort** | 16–20 hours dispatched (~2–3 days wall) |
| **BDD scenarios** | 56 (39 @mode-b · 28 @mode-c · overlap on shared substrate) |
| **Confirmed assumptions** | 17 (10 high · 7 medium · 0 open) |
| **Substrate dependencies** | FEAT-FORGE-001..007 (all shipped) |

## Tasks

| ID | Wave | Title | Complexity | Mode |
|---|---|---|---|---|
| TASK-MBC8-001 | 1 | Add BuildMode enum and extend StageClass with TASK_REVIEW + TASK_WORK | 3 | direct |
| TASK-MBC8-002 | 1 | Define Mode B and Mode C stage chains and prerequisite maps | 2 | direct |
| TASK-MBC8-003 | 2 | Implement ModeBChainPlanner that refuses upstream Mode A stages | 5 | task-work |
| TASK-MBC8-004 | 2 | Implement ModeCCyclePlanner with review→work iteration and clean-review terminal | 6 | task-work |
| TASK-MBC8-005 | 2 | Extend ForwardContextBuilder for Mode B and Mode C contracts | 4 | task-work |
| TASK-MBC8-006 | 3 | Implement Mode B no-diff terminal handler | 3 | task-work |
| TASK-MBC8-007 | 3 | Implement Mode C terminal handlers (empty review and no commits) | 4 | task-work |
| TASK-MBC8-008 | 4 | Wire mode-aware dispatch into Supervisor.next_turn | 6 | task-work |
| TASK-MBC8-009 | 5 | Add forge queue --mode {a\|b\|c} CLI surface and mode-aware queue picker | 4 | task-work |
| TASK-MBC8-010 | 6 | Mode B smoke E2E (queue to PR-awaiting-review terminal) | 5 | task-work |
| TASK-MBC8-011 | 6 | Mode C smoke E2E (queue through clean-review and PR-awaiting-review terminals) | 5 | task-work |
| TASK-MBC8-012 | 6 | BDD step bindings for all 56 Mode B and Mode C scenarios | 6 | task-work |
| TASK-MBC8-013 | 7 | Cross-mode concurrency integration tests (Mode A + B + C in flight together) | 6 | task-work |
| TASK-MBC8-014 | 7 | Crash-recovery integration tests for Mode B and Mode C non-terminal stages | 6 | task-work |

## Wave structure

```
Wave 1  ▶ TASK-MBC8-001, 002              (declarative foundations)
Wave 2  ▶ TASK-MBC8-003, 004, 005         (planners + context)
Wave 3  ▶ TASK-MBC8-006, 007              (terminal handlers)
Wave 4  ▶ TASK-MBC8-008                   (supervisor wiring)
Wave 5  ▶ TASK-MBC8-009                   (CLI surface)
Wave 6  ▶ TASK-MBC8-010, 011, 012         (smoke + BDD)
Wave 7  ▶ TASK-MBC8-013, 014              (concurrency + crash recovery)
```

## Read this first

- [`IMPLEMENTATION-GUIDE.md`](IMPLEMENTATION-GUIDE.md) — load-bearing
  planning document with diagrams, integration contracts, substrate reuse
  map, and feature-level acceptance.
- [`../../../features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature`](../../../features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature)
  — the 56-scenario BDD spec this feature implements.
- [`../../../features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md`](../../../features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md)
  — summary used as `--context` to `/feature-plan`.

## Next steps

```bash
# Run the full feature autonomously
guardkit feature-build FEAT-FORGE-008

# Or work tasks individually starting with Wave 1
guardkit task-work TASK-MBC8-001
guardkit task-work TASK-MBC8-002

# Check progress
guardkit task-status --filter=feature:FEAT-FORGE-008
```

## Substrate notes

This feature is **composition-only**:
- No new state-machine transitions (FEAT-FORGE-001 substrate is sufficient)
- No new dispatchers (`dispatch_subprocess_stage` and
  `dispatch_autobuild_async` are mode-agnostic)
- No changes to `ConstitutionalGuard` (mode-agnostic by ASSUM-011)
- Mode A behaviour must remain byte-identical (FEAT-FORGE-007 regression
  suite must stay green)

If a task adds a new state-machine transition or modifies Mode A's dispatch
branch, stop and re-plan — that's outside the FEAT-FORGE-008 boundary.
