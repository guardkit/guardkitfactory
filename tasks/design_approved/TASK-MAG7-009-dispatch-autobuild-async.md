---
complexity: 6
consumer_context:
- consumes: forward_context
  driver: Internal call
  format_note: Receives list[ContextEntry] (specifically the approved feature-plan
    artefact path for the feature) and threads into autobuild dispatch payload
  framework: Python forge.pipeline.forward_context_builder
  task: TASK-MAG7-006
created: 2026-04-25 00:00:00+00:00
dependencies:
- TASK-MAG7-001
- TASK-MAG7-006
feature_id: FEAT-FORGE-007
id: TASK-MAG7-009
implementation_mode: task-work
parent_review: TASK-REV-MAG7
priority: high
status: design_approved
tags:
- dispatcher
- async-subagent
- autobuild
- feat-forge-005
- ddr-006
- feat-forge-007
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Wire dispatch_autobuild_async via start_async_task
updated: 2026-04-25 00:00:00+00:00
wave: 3
---

# Task: Wire dispatch_autobuild_async via start_async_task

## Description

Dispatch autobuild for a feature as a long-running `AsyncSubAgent` via the
DeepAgents `start_async_task` middleware tool (per ADR-ARCH-031). Returns
immediately with a `task_id` so the supervisor's reasoning loop stays
responsive (Group A: "Autobuild runs as an asynchronous subagent so the
supervisor remains responsive during long runs").

Initialises the `async_tasks` state-channel entry per DDR-006 `AutobuildState`
shape and threads correlation_id through the launched task's context.

## Acceptance Criteria

- [ ] `dispatch_autobuild_async(build_id, feature_id, ...) -> AutobuildDispatchHandle`
      function exists at `src/forge/pipeline/dispatchers/autobuild_async.py`
- [ ] Calls `ForwardContextBuilder.build_for(AUTOBUILD, build_id, feature_id)`
      to get the approved feature-plan artefact path
- [ ] Calls DeepAgents middleware `start_async_task` with the autobuild
      subagent name (`autobuild_runner`) and the assembled context
- [ ] Returns the assigned `task_id` immediately; does not await completion
- [ ] Initialises the `async_tasks` channel entry with an `AutobuildState`
      where `lifecycle="starting"`, `wave_index=0`, `task_index=0`,
      `correlation_id` threaded
- [ ] Records the autobuild dispatch as a `stage_log` entry in
      `state="running"` with the `task_id` stored in `details_json`
- [ ] Two concurrent builds dispatching autobuild at the same time receive
      distinct `task_id` values (Group F @concurrency scenario)
- [ ] Unit test mocking `start_async_task`: successful dispatch returns
      `task_id`, state-channel populated with starting lifecycle
- [ ] Unit test: two concurrent dispatches → two distinct `task_id` values
- [ ] Unit test: correlation_id threaded onto AutobuildState
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The `autobuild_runner` subagent itself (the body of the long-running task)
is owned by FEAT-FORGE-005 + ADR-ARCH-031. This dispatcher's job is the
launch contract: invoke `start_async_task`, populate the state channel,
record the run in `stage_log`.

The runtime lifecycle of `AutobuildState` (transitions through
`planning_waves`, `running_wave`, `awaiting_approval`, `completed`) is
written by `autobuild_runner` itself — this dispatcher only handles the
initial `starting` state.

Crash-recovery semantics (Group D @edge-case "After a crash mid-autobuild
the build's authoritative status comes from durable history not the live
state channel") are tested at integration level in TASK-MAG7-013, but this
dispatcher must record `stage_log` *before* awaiting the `start_async_task`
call so a crash between submit and ack does not leave a state-channel entry
without a `stage_log` row.

## Seam Tests

```python
"""Seam test: dispatch_autobuild_async returns task_id consistent with state channel."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("autobuild_async_task_id")
def test_autobuild_dispatch_task_id_consistency():
    """Verify returned task_id matches AutobuildState entry.

    Contract: DDR-006 AutobuildState.task_id; per-feature unique within build.
    Producer: TASK-MAG7-009
    Consumer: TASK-MAG7-010 (supervisor), TASK-MAG7-011 (CLI steering)
    """
    # Mocked start_async_task returns task_id
    # Verify list_async_tasks reports an AutobuildState entry with same task_id
    pass  # Implementation in /task-work
```

## Test Execution Log

[Automatically populated by /task-work]