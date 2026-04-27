---
complexity: 6
created: 2026-04-27 00:00:00+00:00
dependencies:
- TASK-MBC8-008
- TASK-MBC8-009
feature_id: FEAT-FORGE-008
id: TASK-MBC8-012
implementation_mode: task-work
parent_review: TASK-REV-MBC8
priority: high
status: design_approved
tags:
- bdd
- testing
- mode-b
- mode-c
- feat-forge-008
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: BDD step bindings for all 56 Mode B and Mode C scenarios
updated: 2026-04-27 00:00:00+00:00
wave: 6
---

# Task: BDD step bindings for all 56 Mode B and Mode C scenarios

## Description

Bind every scenario in
`features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature`
to executable steps so the BDD oracle (R2) runs them per `@task` tag during
autobuild. This covers all 56 scenarios — 39 Mode B-tagged, 28 Mode C-tagged
(overlap on shared substrate scenarios).

The `@task:<TASK-ID>` tags are written by `/feature-plan` Step 11 (BDD
linker) when this plan is finalised. This task implements the underlying
step definitions; the linker decides which scenarios bind to which task.

## Acceptance Criteria

- [ ] `tests/bdd/test_feat_forge_008.py` (or equivalent pytest-bdd module)
      binds the feature file's `Background` and every scenario in groups
      A–N
- [ ] Step definitions reuse the existing FEAT-FORGE-001..007 fixtures:
  - [ ] Build queue + lifecycle persistence (FEAT-FORGE-001)
  - [ ] In-memory NATS approval channel (FEAT-FORGE-002)
  - [ ] Stubbed subprocess + autobuild dispatchers (FEAT-FORGE-005)
  - [ ] Constitutional + ordering guards (FEAT-FORGE-007)
- [ ] New step definitions cover Mode-specific verbs:
  - [ ] "the build is picked up from the queue in feature mode" / "in
        review-fix mode"
  - [ ] "Forge invokes feature specification, feature planning, and
        autobuild in order"
  - [ ] "Forge invokes the task-review stage and it returns a non-empty
        set of fix tasks"
  - [ ] "no product-owner, architect, architecture, or design dispatch
        should have been recorded"
  - [ ] "exactly one task-work dispatch should be recorded per fix task
        identified"
  - [ ] "the recorded session outcome should reference every gate decision
        from feature specification through pull-request review"
- [ ] Scenario Outlines are bound once with their Examples table
      (Group B "downstream prerequisite", Group B "Mode C dispatches one
      /task-work per fix task identified", Group D Mode B/C crash recovery)
- [ ] All 56 scenarios pass; no scenario is `@skip` or `@wip`
- [ ] Tests run as a coherent suite in under 90 seconds
- [ ] Coverage report shows at least 95% of `mode_b_planner`,
      `mode_c_planner`, `terminal_handlers` is exercised by these
      bindings (the smoke tests in TASK-MBC8-010 / 011 close the rest)
- [ ] All modified files pass project-configured lint/format checks with zero
      errors

## Implementation Notes

Pytest-bdd is the project default; do not introduce a different harness.
Mirror the existing FEAT-FORGE-007 BDD module's organisation
(`tests/bdd/test_feat_forge_007.py` if present) so the two suites can be
read side-by-side.

Some scenarios are tagged `@mode-b @mode-c` because the shared substrate
makes them mode-agnostic (Group D, F, G, H, I scenarios). Bind these once
each — the steps already parameterise on build mode.

The Group B Scenario Outline for Mode C fix-task counts (1 / 3 / 5) is the
key parametric coverage; ensure the harness handles each `count` cleanly
without loop carry-over.

## Test Execution Log

[Automatically populated by /task-work]