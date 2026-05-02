---
id: TASK-FORGE-FRR-001b
title: Publish pipeline lifecycle events (build-started, stage-complete×N, build-complete) from the autobuild orchestrator
status: superseded
created: 2026-05-02T00:00:00Z
updated: 2026-05-02T00:00:00Z
closed_at: 2026-05-02T00:00:00Z
closed_reason: superseded-by-feature
superseded_by: docs/research/forge-orchestrator-wiring-gap.md  # the new feature's spec/plan are pending /feature-spec + /feature-plan
priority: high
task_type: feature
tags:
  - forge-serve
  - jetstream
  - autobuild
  - stage-complete
  - pipeline-lifecycle-emitter
  - feat-forge-009-followup
  - first-real-run-followup
  - frr-001-sibling
  - superseded-by-feature
complexity: 7
estimated_minutes: 720
estimated_effort: "~3 days (emitter wiring into autobuild subagent + per-stage publish + tests) — see SUPERSESSION below"
parent_feature: FEAT-FORGE-009
related_tasks:
  - TASK-FORGE-FRR-001       # also superseded — sibling
  - TASK-MAG7-009            # the dispatch_autobuild_async layer the new feature plumbs the emitter through
correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10  # same root signal: GB10 first-real-run 2026-05-01
discovered_on:
  date: 2026-05-02
  machine: GB10 (promaxgb10-41b1)
  context: "split out of TASK-FORGE-FRR-001 during Phase 2.8 design checkpoint after investigation surfaced that PipelineLifecycleEmitter is never constructed in production"
test_results:
  status: not-applicable
  coverage: null
  last_run: null
---

> ## ⚠ SUPERSEDED BY FEATURE (2026-05-02)
>
> This task was created as a sibling of TASK-FORGE-FRR-001 to carry
> the per-stage `pipeline.stage-complete.<feature_id>` publishing that
> the FRR-001 design (Option 2 + scope-split-γ) deferred. Hours after
> filing, the FRR-001 implementation phase discovered that the
> entire orchestration chain (`Supervisor`, the three dispatchers,
> `PipelineConsumerDeps`, `ForwardContextBuilder`, the
> `autobuild_runner` AsyncSubAgent itself) is unwired in production.
> The "wire the emitter into the autobuild_runner subagent" scope of
> this task presupposes the autobuild_runner exists. It does not.
>
> Both FRR-001 and FRR-001b are being subsumed into a new feature
> being scoped through `/feature-spec` + `/feature-plan` against
> `docs/research/forge-orchestrator-wiring-gap.md` (the findings
> document) and
> `docs/research/forge-orchestrator-wiring-feature-context.md` (the
> `--context` evaluation for the two commands).
>
> When the new feature's ID lands, this file's `superseded_by`
> frontmatter field should be updated from the findings-doc pointer
> to the feature ID.
>
> **Still load-bearing from this task**:
> - The component inventory (`PipelineLifecycleEmitter` exists with
>   eight emit methods; `dispatch_autobuild_async` doesn't accept a
>   publisher; the `autobuild_runner` AsyncSubAgent has no production
>   path back to the publisher). Captured in the findings doc and
>   re-used by the new feature's spec.
> - The two architectural options (a) "pass emitter through subagent
>   context" vs (b) "watch async_tasks state-channel and emit from
>   outside" — surfaced here for the first time, carried forward as
>   open question #5 in the `--context` doc.
>
> **No longer load-bearing**:
> - The "depends on FRR-001's daemon wire" framing. The new feature
>   handles both layers as one composition.
>
> The task's original Description, Why-this-matters, Acceptance
> Criteria, Out-of-Scope, Implementation Notes, and References
> sections are preserved below as historical context.
>
> ---


# Task: Publish pipeline lifecycle events from the autobuild orchestrator

## Description

`forge.pipeline.PipelineLifecycleEmitter` (`src/forge/pipeline/__init__.py:273`)
exposes the eight lifecycle emit methods (`emit_build_started`,
`emit_build_progress`, `emit_stage_complete`, `emit_build_paused`,
`emit_build_resumed`, `emit_build_complete`, `emit_build_failed`,
`emit_build_cancelled`) and a generic `on_transition` dispatcher. It is the
canonical surface for publishing every event in the
`pipeline.{event}.{feature_id}` family per
`docs/design/contracts/API-nats-pipeline-events.md §3`.

**It is never constructed in production.** A repository-wide grep for
`PipelineLifecycleEmitter(` returns zero matches outside of tests. The
autobuild dispatcher (`src/forge/pipeline/dispatchers/autobuild_async.py:292`,
`dispatch_autobuild_async`) takes `forward_context_builder`,
`async_task_starter`, `stage_log_recorder`, `state_channel` — but **no
publisher and no emitter** — and launches a DeepAgents subagent via
`start_async_task` that has no path back to publish lifecycle events as it
progresses.

This task wires the emitter into the autobuild flow so every real stage
transition publishes the matching `pipeline.{event}.{feature_id}` envelope
to JetStream with the originating build's `correlation_id` threaded
through. Once this lands, downstream subscribers (jarvis's
`forge_subscriber`, the dashboard, the chat REPL via DDR-030) can render
real per-stage progress instead of just the synthetic dispatch-stage
acknowledgement that TASK-FORGE-FRR-001 emits.

## Why this matters (carried from FRR-001)

During the FEAT-JARVIS-INTERNAL-001 first-real-run on GB10
(correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`, 2026-05-01), the
runbook's Phase 7 close criterion ("between-prompt notifications render in
the chat REPL, showing stage-complete events for FEAT-43DE") could not be
met. FRR-001 closes the literal AC by emitting one synthetic dispatch-stage
envelope per inbound build-queued. **This task closes the spirit** —
real per-stage progress that operators can use to follow long-running
builds in flight.

## Source code references

- **Unwired emitter**:
  [`src/forge/pipeline/__init__.py:273`](../../../src/forge/pipeline/__init__.py)
  (`PipelineLifecycleEmitter`).
- **Per-stage emit method**:
  [`src/forge/pipeline/__init__.py:354`](../../../src/forge/pipeline/__init__.py)
  (`emit_stage_complete`).
- **Generic transition dispatcher**:
  [`src/forge/pipeline/__init__.py:594`](../../../src/forge/pipeline/__init__.py)
  (`on_transition`).
- **Autobuild dispatcher (where the emitter must reach)**:
  [`src/forge/pipeline/dispatchers/autobuild_async.py:292`](../../../src/forge/pipeline/dispatchers/autobuild_async.py)
  (`dispatch_autobuild_async`).
- **Autobuild subagent layer**: see `forge.pipeline.supervisor` and
  whichever runner backs `AUTOBUILD_RUNNER_NAME` — exact module location
  to confirm during implementation.
- **Outbound publisher to bind into the emitter**:
  [`src/forge/adapters/nats/pipeline_publisher.py`](../../../src/forge/adapters/nats/pipeline_publisher.py).
- **FRR-001 daemon wire (the prerequisite this task depends on)**:
  `src/forge/cli/_serve_dispatcher.py` (created by FRR-001) and
  `src/forge/cli/_serve_deps.py` (created by FRR-001 — already constructs
  `PipelinePublisher` once, which this task should re-use).

## Goal

Wire `PipelineLifecycleEmitter` into the autobuild orchestrator so that the
real stage transitions inside an in-flight autobuild publish their matching
lifecycle envelopes to JetStream — at minimum `build-started` once on
dispatch, one `stage-complete` per stage transition, and `build-complete`
or `build-failed` on terminal — all carrying the originating build's
`correlation_id`.

The architectural surface to settle in this task:

1. **Where the emitter is constructed.** Likely the same place FRR-001's
   `_serve_deps.build_pipeline_consumer_deps` constructs `PipelinePublisher`
   — a single emitter per daemon process, shared across all in-flight
   autobuilds, sharing the daemon's NATS client.
2. **How the emitter reaches the autobuild subagent.** The subagent runs
   in a different control flow from the dispatcher. Two plausible paths:
   - **(a) Pass the emitter through the dispatcher's context payload**:
     `dispatch_autobuild_async` accepts an additional `lifecycle_emitter`
     parameter and threads it into the `start_async_task` context payload;
     the subagent picks it up from context.
   - **(b) Watch the `async_tasks` state-channel and emit from outside**:
     a separate task reads `async_tasks` rows for the active autobuild and
     publishes lifecycle events as the persisted state advances. Decouples
     the publish path from the subagent but adds polling latency.
   Pick one (or a justified alternative) and capture in Implementation
   Notes once decided.
3. **Stage-class → `stage_label` mapping.** The autobuild's internal stage
   identifiers (`StageClass.AUTOBUILD`, `StageClass.PLAN`, etc.) need a
   stable mapping to the `stage_label` field on `StageCompletePayload`.
   Confirm against the existing stage taxonomy (`forge.pipeline.stage_taxonomy`).

## Acceptance Criteria

- [ ] **Architectural choice documented**: pick (a), (b), or a justified
      alternative for how the emitter reaches the autobuild subagent;
      capture in Implementation Notes.
- [ ] **Emitter constructed in production exactly once per daemon process**,
      sharing FRR-001's `PipelinePublisher` instance and its NATS client.
      No second connection.
- [ ] **`build-started` published on autobuild dispatch**: one envelope on
      `pipeline.build-started.<feature_id>`, fired before
      `dispatch_autobuild_async` returns its handle, with the inbound
      `correlation_id` threaded.
- [ ] **One `stage-complete` per real stage transition** inside the
      autobuild: each transition the orchestrator currently records in
      `stage_log` produces one envelope on
      `pipeline.stage-complete.<feature_id>` with the correct
      `stage_label`, `target_kind`, `target_identifier`, `status`, and the
      threaded `correlation_id`. The synthetic dispatch-stage envelope
      from FRR-001 is **retained** — it acknowledges dispatch before the
      first real stage completes.
- [ ] **`build-complete` or `build-failed` on terminal**: the autobuild's
      terminal transition publishes the matching envelope; this is also
      the trigger that finally fires the deferred `ack_callback` from
      `pipeline_consumer.handle_message` (the build queue slot is only
      released on terminal).
- [ ] **Correlation-id round-trip preserved through every envelope** in
      the build's lifecycle: every published event for a given build
      carries the same `correlation_id` as the inbound `build-queued`.
      Verifiable in the e2e test via subject pattern matching.
- [ ] **End-to-end test on the canonical layout**: jarvis chat REPL
      invokes `queue_build` against a feature with a real (non-trivial)
      autobuild path; `forge serve` consumes; the autobuild runs through
      ≥2 stages; the chat REPL renders the full sequence of envelopes
      (`build-started`, `stage-complete×N`, `build-complete`) in order.
- [ ] **Publish failures do not corrupt the build**: if a publish raises,
      the autobuild continues and the corresponding envelope is logged at
      WARNING. The build's truth lives in SQLite (per the
      `pipeline_publisher.py` docstring's LES1 parity rule); the bus is
      a derived projection. A dropped envelope is acceptable; a crashed
      build is not.
- [ ] **No double-publishing of the dispatch-stage envelope**: FRR-001's
      synthetic dispatch-stage publish stays separate from this task's
      per-stage publishes. The first real `stage-complete` envelope must
      not also have `stage_label="dispatch"`.

## Out of Scope

- **The daemon wire itself** — owned by TASK-FORGE-FRR-001.
- **Renaming or consolidating the `forge-consumer` / `forge-serve` durable
  pair** — separate cleanup task.
- **Building new lifecycle events not in the existing eight-method
  catalogue**: this task wires the existing emitter; it does not add new
  envelope types.
- **Approval / pause-resume flow** (`emit_build_paused`,
  `emit_build_resumed`): the emitter methods exist but the autobuild
  flow's pause hooks may need their own follow-up. Wire them if it's a
  one-line addition; otherwise track separately.

## Implementation Notes

### Investigation to do first

- **Confirm where the autobuild subagent runs.** `start_async_task`
  launches a DeepAgents subagent named `AUTOBUILD_RUNNER_NAME` — find
  the runner module and understand whether the subagent receives the
  full DeepAgents context (in which case option a is straightforward) or
  whether it runs in an isolated process (in which case option b becomes
  more attractive).
- **Find the existing per-stage transition site inside the autobuild.**
  This is where the `emit_stage_complete` calls land. The
  `forge.pipeline.stage_log` writer is the most likely indicator —
  whichever code calls it on stage transitions is the integration point.
- **Confirm the `stage_label` taxonomy.** `forge.pipeline.stage_taxonomy`
  defines the canonical stage identifiers; confirm the
  `StageCompletePayload.stage_label` field accepts those identifiers
  verbatim or whether a mapping is needed.

### Coordinate with FRR-001's `_serve_deps.py`

FRR-001 already constructs `PipelinePublisher` once at daemon startup. This
task should:
- Add an `emitter: PipelineLifecycleEmitter` field to whatever container
  FRR-001 settles on (likely a new dataclass alongside `PipelineConsumerDeps`).
- Have `_serve_deps.build_pipeline_consumer_deps` (or a sibling factory)
  also construct the emitter against the same publisher.
- Make the emitter available to `dispatch_autobuild_async` via whichever
  parameter shape option (a) settles on.

### Logging coordination

Same note as FRR-001: assumes TASK-FORGE-FRR-002 (`logging.basicConfig`)
has landed or is in flight, otherwise the per-stage emit logs disappear
into `docker logs forge-prod`.

### Testing strategy

- **Unit tests against the emitter wiring**: substitute a fake
  `PipelinePublisher`, run `dispatch_autobuild_async` with mocked
  collaborators, assert the expected envelope sequence.
- **Integration test against an embedded NATS**: drive a real autobuild
  through ≥2 stages with mocked subagent work, assert the published
  envelope sequence matches.
- **E2E test** (the AC-7 test): docker-compose with `forge serve` + the
  jarvis chat REPL + a real autobuild; assert the operator sees the full
  per-stage notification sequence.

## References

- **Sibling task**: TASK-FORGE-FRR-001 (the daemon wire that this task
  builds on).
- **RESULTS file that motivated both tasks**:
  [/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../../jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **FRR-001 implementation plan** (which captures the design decisions
  that anchor this split):
  `docs/state/TASK-FORGE-FRR-001/implementation_plan.md`
- **API contract**: `docs/design/contracts/API-nats-pipeline-events.md §3`
  (the eight lifecycle subjects).

## Test Execution Log

[Automatically populated by /task-work and downstream test runs]
