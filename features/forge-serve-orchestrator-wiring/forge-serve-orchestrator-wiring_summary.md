# Feature Spec Summary: Wire the production pipeline orchestrator into forge serve

**Feature ID**: FEAT-FORGE-010
**Stack**: python
**Generated**: 2026-05-02T00:00:00Z
**Scenarios**: 31 total (4 smoke, 4 regression)
**Assumptions**: 18 total (13 high / 5 medium / 0 low confidence)
**Review required**: No — every assumption traceable to a supplied ADR, DDR, contract, or the gap-finding doc

## Scope

Specifies the production composition that turns `forge serve` from a
receipt-only daemon (FEAT-FORGE-009) into the canonical host for the full
pipeline orchestrator. Covers the wiring of components that already exist
as un-instantiated capability — `Supervisor`, `PipelineConsumerDeps`,
`PipelineLifecycleEmitter`, `PipelinePublisher`, `ForwardContextBuilder`,
plus the net-new `autobuild_runner` AsyncSubAgent — into a single startup
chain that consumes a `pipeline.build-queued.<feature_id>` envelope,
runs the build through the canonical Mode A stage chain, publishes the
real lifecycle envelope sequence (`build-started`, `stage-complete×N`,
`build-paused`/`build-resumed` if paused, terminal envelope) back to
JetStream with the inbound `correlation_id` threaded through every event,
and survives crash + restart with no lost or duplicated builds.

The feature deliberately stays at the **integration / wiring** layer.
Orchestration semantics (Mode A stage chain, gating policy, pause/resume
rules, per-feature loop, constitutional pull-request review) are already
specified in `features/mode-a-greenfield-end-to-end/`. This feature
verifies the production composition that satisfies those Mode A
scenarios in the running daemon, plus the daemon-process invariants that
came in with FEAT-FORGE-009 (healthz, single shared NATS connection,
durable consumer with `max_ack_pending=1`, terminal-only ack, sequential
builds across replicas).

The feature carries forward the seam-refactor design from the superseded
TASK-FORGE-FRR-001 (`_serve_daemon._process_message` contract change to
`(_MsgLike) -> None`, deferred-ack to the state machine,
`max_ack_pending=1` on the durable) and explicitly drops FRR-001's
synthetic dispatch-stage `stage-complete` placeholder — only real stage
transitions emit `stage-complete` envelopes.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 5 |
| Negative cases (@negative) | 7 |
| Edge cases (@edge-case) | 13 |
| Smoke (@smoke) | 4 |
| Regression (@regression) | 4 |
| Security (@security) | 3 |
| Data integrity (@data-integrity) | 3 |
| Integration (@integration) | 2 |

Note: several scenarios carry multiple tags (e.g. boundary + negative,
edge-case + security, edge-case + data-integrity). Group totals do not
sum to 31.

## Group Layout

| Group | Theme | Scenarios |
|-------|-------|-----------|
| A | Key Examples — full lifecycle envelope sequence end-to-end, daemon-startup chain composition, correlation-id threading, AsyncSubAgent dispatch, real-stage-complete invariant, build-started/terminal bookends, single shared NATS connection | 7 |
| B | Boundary Conditions — `max_ack_pending=1` + canonical durable name, terminal-only ack outline (4 terminal states), paused-not-acked, minimal single-stage envelope sequence, ack_wait covers longest build | 5 |
| C | Negative Cases — receipt-only stub no longer reachable, malformed payload → build-failed, duplicate detection skip, path outside allowlist → build-failed, dispatch error contained, publish failure does not regress recorded transition | 6 |
| D | Edge Cases — crash recovery via paired reconcile_on_boot, paused build survives restart, approval response → build-resumed, two-replica failover, cancel propagates through subagent, SIGTERM leaves message unacked | 6 |
| E | Edge Case Expansion — autobuild_runner worktree confinement, mismatched-correlation approval ignored, lifecycle publish ordering invariant, durable history authoritative on recovery, in-subagent stage-complete carries task_id, fail-fast on NATS unreachable, healthz reflects orchestrator readiness | 7 |

## Deferred Items

None.

## Assumptions Summary

| ID | Confidence | Subject | Response |
|----|------------|---------|----------|
| ASSUM-001 | medium | Feature ID FEAT-FORGE-010 / slug @forge-serve-orchestrator-wiring | confirmed |
| ASSUM-002 | high | Components constructed at daemon startup | confirmed |
| ASSUM-003 | high | autobuild_runner shape (AsyncSubAgent, ASGI, separate graph) | confirmed |
| ASSUM-004 | medium | Synthetic dispatch-stage envelope from FRR-001 not preserved | confirmed |
| ASSUM-005 | high | max_ack_pending=1 on PIPELINE durable | confirmed |
| ASSUM-006 | high | Durable consumer name "forge-serve" | confirmed |
| ASSUM-007 | high | Terminal-only ack (COMPLETE/FAILED/CANCELLED/SKIPPED) | confirmed |
| ASSUM-008 | high | ack_wait approximately one hour | confirmed |
| ASSUM-009 | high | Both reconcile_on_boot routines run at daemon startup | confirmed |
| ASSUM-010 | medium | emit_build_paused / emit_build_resumed in scope | confirmed |
| ASSUM-011 | high | Single shared NATS connection (no second connection) | confirmed |
| ASSUM-012 | medium | Healthz reflects orchestrator readiness, not just NATS | confirmed |
| ASSUM-013 | high | Malformed payload → build-failed + ack | confirmed |
| ASSUM-014 | high | Duplicate detection via SQLite unique index | confirmed |
| ASSUM-015 | high | Path outside allowlist → build-failed | confirmed |
| ASSUM-016 | high | Correlation-keyed approval reply subjects (DDR-001) | confirmed |
| ASSUM-017 | high | Durable history authoritative on recovery (DDR-006, ADR-ARCH-008) | confirmed |
| ASSUM-018 | medium | Stage-complete from autobuild carries subagent task_id | confirmed |

## Upstream Dependencies

This feature is purely composition; it inherits behaviour from prior features.

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration. The build queue,
  state-machine transitions, durable history, crash recovery
  (retry-from-scratch), and CLI steering surface are the substrate this
  feature wires into. No new transitions are added.
- **FEAT-FORGE-002** — NATS Fleet Integration. The pipeline-event
  publishing contract (correlation threading), approval channel, and
  PipelinePublisher class are inherited; this feature constructs the
  publisher and emitter in production.
- **FEAT-FORGE-004** — Confidence-Gated Checkpoint Protocol. Pause/resume
  semantics (`emit_build_paused`, `emit_build_resumed`,
  `ApprovalResponsePayload` round-trip, idempotent first-wins) are
  inherited; this feature wires the publish-back path so subscribers
  observe pause/resume.
- **FEAT-FORGE-007** — Mode A Greenfield End-to-End. **The orchestration
  semantics are already specified there.** This feature does not
  re-spec them; it verifies that the production composition causes those
  scenarios to execute against the wired-in-production stack rather than
  only against unit tests with mocked dispatchers.
- **FEAT-FORGE-009** — Forge Production Image. The daemon process,
  healthz endpoint, JetStream durable attach, and SIGTERM handling are
  inherited; this feature changes `_process_message`'s seam contract,
  switches `max_ack_pending` from default to 1, adds the
  reconcile_on_boot pair, and replaces the receipt-only `_default_dispatch`
  with the real orchestrator dispatch.

## Carried-forward design (from superseded tasks)

The following design elements from the superseded `TASK-FORGE-FRR-001`
and `TASK-FORGE-FRR-001b` remain load-bearing for this feature's plan:

- The `_serve_daemon._process_message` seam-refactor: change `DispatchFn`
  from `(bytes) -> None` to `(_MsgLike) -> None`; remove the
  post-dispatch ack on the success path; ack moves into
  `pipeline_consumer.handle_message`'s deferred `ack_callback`.
- `max_ack_pending=1` on the `forge-serve` durable's `ConsumerConfig`.
  Operational note: changing this on an existing JetStream consumer
  requires recreating it (`nats consumer rm PIPELINE forge-serve` before
  deploying the new image).
- The originator-allowlist finding: jarvis chat REPL's
  `originating_adapter="terminal"` is in `DEFAULT_APPROVED_ORIGINATORS`;
  `triggered_by="jarvis"` is a separate field that the consumer does not
  gate on. No change required.

The following are **not** carried forward:

- The "synthetic dispatch-stage publish to satisfy AC #2 literally"
  recommendation from FRR-001's Phase 2.8 design checkpoint. ASSUM-004
  records this drop explicitly.

## Open scope check (for /feature-plan)

- **Pause/resume publish (ASSUM-010)**: medium-confidence inclusion. If
  implementation discovers the `emit_build_paused` / `emit_build_resumed`
  hookup is materially more than a one-line change at the relevant call
  sites, `/feature-plan` should split it into a follow-up task and drop
  the related Group D and Group E scenarios from this feature's
  acceptance set rather than leave them as silent passes.
- **`stage-complete` from inside the AsyncSubAgent (ASSUM-018)**:
  medium-confidence — the precise mechanism by which the subagent reaches
  the `PipelineLifecycleEmitter` (passing it through dispatcher context
  vs. watching the `async_tasks` state channel from outside) is the open
  architectural question carried over from FRR-001b. `/feature-plan`
  should pick a path and capture it as a DDR or in the implementation
  guide before tasks are created.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Wire the production pipeline orchestrator into forge serve" \
      --context features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_summary.md

`/feature-plan` Step 11 will link `@task:<TASK-ID>` tags back into the
`.feature` file after tasks are created.

## Provenance

This feature was filed as the result of the FEAT-JARVIS-INTERNAL-001
first-real-run on GB10, 2026-05-01, correlation_id
`a58ec9a7-27c6-485a-beac-e18675639a10`, where the runbook's Phase 7 close
criterion ("between-prompt notifications render in the chat REPL, showing
stage-complete events for FEAT-43DE") could not be met because nothing
on the forge side publishes anything back. The investigation that
followed produced `docs/research/forge-orchestrator-wiring-gap.md` —
which is the authoritative scope source for this spec. The original
follow-up tasks `TASK-FORGE-FRR-001` and `TASK-FORGE-FRR-001b` are
marked superseded-by-feature and carried in
`tasks/completed/TASK-FORGE-FRR-001/` and
`tasks/completed/TASK-FORGE-FRR-001b/` as historical context.
