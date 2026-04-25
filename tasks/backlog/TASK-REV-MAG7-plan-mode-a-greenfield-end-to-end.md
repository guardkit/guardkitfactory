---
id: TASK-REV-MAG7
title: "Plan: Mode A Greenfield End-to-End"
task_type: review
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
complexity: 9
tags: [planning, review, mode-a, greenfield, orchestration, capstone, feat-forge-007]
feature_spec: features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md
feature_id: FEAT-FORGE-007
upstream_dependencies:
  - FEAT-FORGE-001  # Pipeline State Machine & Configuration
  - FEAT-FORGE-002  # NATS Fleet Integration
  - FEAT-FORGE-003  # Specialist Agent Delegation
  - FEAT-FORGE-004  # Confidence-Gated Checkpoint Protocol
  - FEAT-FORGE-005  # GuardKit Command Invocation Engine
  - FEAT-FORGE-006  # Infrastructure Coordination
clarification:
  context_a:
    timestamp: 2026-04-25T00:00:00Z
    decisions:
      focus: all
      tradeoff: balanced
      specific_concerns: null
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan Mode A Greenfield End-to-End (FEAT-FORGE-007)

## Description

Decision-making review for **FEAT-FORGE-007 — Mode A Greenfield End-to-End**, the
capstone composition feature for Forge. Specifies how a single one-line product
brief is driven through the eight-stage chain — product-owner delegation,
architect delegation, architecture, system design, per-feature specification,
per-feature planning, autobuild, and pull-request review — under one supervised
build.

This review composes six upstream features (FEAT-FORGE-001 through
FEAT-FORGE-006) without introducing new transitions; it specifies the *order*,
*forward propagation*, *dispatch pattern*, *steering surface*, and *integrity
invariants* that bind them together. It must surface the recommended technical
approach, architecture boundaries, risk analysis, effort estimation, and a
subtask breakdown that downstream `/feature-build` can execute against.

## Scope of Analysis

Review must cover **all areas (full sweep)** with a **balanced** trade-off
priority. No specific concerns pre-flagged — surface highest-risk areas
organically.

Concrete areas to examine:

1. **Stage-ordering invariants**: enforcement that no downstream stage may be
   dispatched before its prerequisite stage's gate has resolved, and how this
   composes with FEAT-FORGE-004's gate-mode taxonomy.
2. **Forward propagation**: how each stage's approved output is threaded into
   the next stage's `--context` flag construction (FEAT-FORGE-005), without
   leaking unapproved or stale artefacts.
3. **Async-subagent dispatch**: the long-running autobuild dispatch pattern
   (AsyncSubAgent + state channel) — supervisor responsiveness during the run,
   live wave/task progress as advisory, and SQLite history as authoritative.
4. **Constitutional belt-and-braces**: pull-request review pinned to mandatory
   human approval at *both* prompt and executor layers; verification that the
   executor refuses to honour an auto-approve directive even if a prompt
   misconfiguration emits one.
5. **Crash recovery**: retry-from-scratch semantics; durable-history precedence
   over the advisory live state channel on resume; per-feature artefact
   attribution preserved across restart.
6. **CLI steering surface**: cancel → synthetic reject mapping, skip honoured
   on non-constitutional stages and refused on PR review, mid-flight directive
   queueing.
7. **Pause isolation**: simultaneous paused builds on independent channels;
   approval routing keyed by build identifier; idempotent first-write-wins on
   duplicate or simultaneous responses.
8. **Per-feature sequencing**: per-feature autobuild ordering within a single
   build; one PR per feature; aggregate session-outcome chain.
9. **Concurrency**: two concurrent builds with isolated channels and task IDs;
   supervisor dispatching second build's stage during first build's autobuild.
10. **Integrity invariants**: correlation-identifier threading queue→terminal;
    calibration-priors snapshot stability for the duration of one build;
    notification-publish failure does not regress approval.
11. **Security**: belt-and-braces against misconfigured prompts; specialist
    override claim ignored at gating; subprocess worktree-allowlist confinement
    (inherited from FEAT-FORGE-005).
12. **Test strategy**: deterministic async tests for the eight-stage chain;
    crash-injection tests for retry-from-scratch; concurrency tests for
    pause isolation; smoke + regression coverage for the four canonical paths.

## Acceptance Criteria

- [ ] Technical approach analysed with explicit composition-vs-extension
      decision for each upstream feature, with pros/cons
- [ ] Stage-ordering invariant enforcement strategy documented (where the
      check lives, how it composes with FEAT-FORGE-004 gate modes)
- [ ] Forward-propagation contract specified per stage transition
      (input artefact → next-stage `--context`)
- [ ] Async-subagent dispatch boundaries documented (supervisor /
      AsyncSubAgent / state-channel responsibilities, history as truth)
- [ ] Constitutional belt-and-braces verification path documented
      (prompt-layer + executor-layer assertions)
- [ ] Crash-recovery semantics specified (retry-from-scratch with durable
      history as authoritative source; advisory live state)
- [ ] CLI-steering matrix documented (cancel/skip per stage class,
      including PR-review refusal)
- [ ] Pause-isolation guarantees specified (per-build channels,
      first-write-wins idempotency)
- [ ] Risk register produced covering composition risks (race conditions,
      stale-context propagation, async-dispatch flakiness, constitutional
      bypass, recovery divergence)
- [ ] Subtask breakdown with dependencies, complexity (1–10), and
      parallel-wave organisation
- [ ] Integration contracts identified for cross-task data dependencies
- [ ] Smoke (4) and regression (4) coverage strategy defined
- [ ] Decision checkpoint presented: [A]ccept / [R]evise / [I]mplement / [C]ancel
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Clarification Context

### Context A — Review Scope (collected at /feature-plan invocation)

- **Focus**: All (full sweep across architecture, technical, performance, security)
- **Trade-off priority**: Balanced (no single dimension dominates)
- **Specific concerns**: None pre-flagged — surface highest-risk areas during analysis

### Context B — Implementation Preferences

To be collected at the [I]mplement decision checkpoint, if user proceeds to
implementation. Will determine:
- Approach selection (which recommended option to follow)
- Execution preference (parallel waves vs sequential, Conductor usage)
- Testing depth (TDD / standard / minimal)

## Implementation Notes

This feature is the *capstone* of the Forge build. It introduces no new
transitions or transport primitives — every capability it relies on already
exists in FEAT-FORGE-001 through FEAT-FORGE-006. The plan therefore must focus
on *composition*: order, propagation, dispatch shape, steering, and invariants.

The review must be careful to preserve the substrate-feature contracts:
- FEAT-FORGE-001's state machine and durable history are *the* source of truth
- FEAT-FORGE-002's NATS channels carry advisory progress, not authoritative state
- FEAT-FORGE-003's specialist delegation has its own degraded-mode behaviour
- FEAT-FORGE-004's confidence gates compose; this feature does not redefine them
- FEAT-FORGE-005's subprocess contract is reused verbatim per stage
- FEAT-FORGE-006's memory/priors/test/PR helpers are inherited

If the review identifies a gap in any substrate feature, it must call this out
explicitly rather than silently extending scope.

## Test Execution Log

[Automatically populated by /task-review and downstream /task-work]
