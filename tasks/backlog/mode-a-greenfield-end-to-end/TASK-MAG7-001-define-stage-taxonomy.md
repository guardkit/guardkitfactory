---
id: TASK-MAG7-001
title: Define StageClass enum and stage prerequisite map
task_type: declarative
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
tags: [taxonomy, declarative, stage-ordering, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Define StageClass enum and stage prerequisite map

## Description

Define the eight Mode A stage classes as a Python `StrEnum` and a prerequisite
map that encodes the seven prerequisite rows from FEAT-FORGE-007 Group B
Scenario Outline ("A downstream stage is not dispatched before its prerequisite
has reached the approved state").

This is the canonical taxonomy that every guard, dispatcher, and context
builder downstream relies on. It must match the feature spec verbatim.

## Acceptance Criteria

- [ ] `forge.pipeline.stage_taxonomy` module exists at
      `src/forge/pipeline/stage_taxonomy.py`
- [ ] Exports `StageClass(StrEnum)` with members in order:
      `PRODUCT_OWNER`, `ARCHITECT`, `SYSTEM_ARCH`, `SYSTEM_DESIGN`,
      `FEATURE_SPEC`, `FEATURE_PLAN`, `AUTOBUILD`, `PULL_REQUEST_REVIEW`
- [ ] Exports `STAGE_PREREQUISITES: dict[StageClass, list[StageClass]]` with
      exactly seven entries matching the Group B Scenario Outline:
      `architect ← product-owner`, `system-arch ← architect`,
      `system-design ← system-arch`, `feature-spec ← system-design`,
      `feature-plan ← feature-spec` (per feature),
      `autobuild ← feature-plan` (per feature),
      `pull-request ← autobuild for every feature`
- [ ] Exports `CONSTITUTIONAL_STAGES: frozenset[StageClass]` containing
      `PULL_REQUEST_REVIEW`
- [ ] Exports `PER_FEATURE_STAGES: frozenset[StageClass]` containing
      `FEATURE_SPEC`, `FEATURE_PLAN`, `AUTOBUILD`, `PULL_REQUEST_REVIEW`
- [ ] Module docstring references FEAT-FORGE-007 ASSUM-001 and
      ADR-ARCH-026 (constitutional rule)
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is a declarative module with no runtime behaviour beyond providing the
taxonomy. Keep it free of imports from any other `forge.pipeline` module so it
can be imported by all downstream tasks in Waves 2–4 without a cycle.

The eight stage names map onto the
`features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature`
Background and key-example scenarios. Do not rename them.

## Test Execution Log

[Automatically populated by /task-work]
