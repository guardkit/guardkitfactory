# FEAT-FORGE-010 — Wire the production pipeline orchestrator into `forge serve`

**Feature ID:** FEAT-FORGE-010
**Slug:** `forge-serve-orchestrator-wiring`
**Parent review:** [TASK-REV-FW10](../../in_review/TASK-REV-FW10-plan-forge-serve-orchestrator-wiring.md)
**Spec:** [features/forge-serve-orchestrator-wiring/](../../../features/forge-serve-orchestrator-wiring/)
**Architectural anchor:** [DDR-007](../../../docs/design/decisions/DDR-007-pipeline-lifecycle-emitter-wiring-path.md) (Option A — emitter through dispatcher context)

## What this feature does

Closes the structural gap between `forge serve`'s shipped daemon
process (FEAT-FORGE-009) and the un-instantiated pipeline orchestrator
chain. After this feature lands, a `pipeline.build-queued.<feature_id>`
envelope routed to `forge serve` runs end-to-end through the canonical
Mode A stage chain (FEAT-FORGE-007), publishes the full lifecycle
envelope sequence (`build-started`, `stage-complete×N`,
`build-paused` / `build-resumed` if paused, terminal envelope) back to
JetStream with the inbound `correlation_id` threaded through every
event, and survives crash + restart with no lost or duplicated builds.

This is **production composition**, not new orchestration semantics.
The orchestration semantics already exist as fully unit-tested
components in `src/forge/pipeline/` and `src/forge/adapters/nats/`;
they just have no production caller. This feature gives them one.

## Wave plan

| Wave | Tasks | Theme |
|---|---|---|
| 1 | [TASK-FW10-001](TASK-FW10-001-refactor-serve-daemon-seam-and-reconcile-on-boot.md) | Foundation: seam refactor, `max_ack_pending=1`, paired `reconcile_on_boot`. |
| 2 | [TASK-FW10-002](TASK-FW10-002-implement-autobuild-runner-async-subagent.md) · [003](TASK-FW10-003-forward-context-builder-factory.md) · [004](TASK-FW10-004-stage-log-recorder-binding.md) · [005](TASK-FW10-005-autobuild-state-initialiser-binding.md) · [006](TASK-FW10-006-pipeline-publisher-and-emitter-constructors.md) | Five net-new components (parallel; one Conductor workspace per task). |
| 3 | [TASK-FW10-007](TASK-FW10-007-compose-pipeline-consumer-deps.md) · [008](TASK-FW10-008-wire-async-subagent-middleware-into-supervisor.md) | Composition: `_serve_deps` factory + supervisor wiring. |
| 4 | [TASK-FW10-009](TASK-FW10-009-validation-surface-and-build-failed-paths.md) · [010](TASK-FW10-010-pause-resume-publish-round-trip.md) · [011](TASK-FW10-011-end-to-end-lifecycle-integration-test.md) | Validation, pause/resume, end-to-end proof. |

**Smoke gates:** after Waves 1, 2, and 3. See `IMPLEMENTATION-GUIDE.md` §6.

## Quick references

- [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) — diagrams, integration contracts, run order.
- [TASK-REV-FW10 review report](../../../.claude/reviews/TASK-REV-FW10-review-report.md) — decision-mode analysis.
- [Gap-finding doc](../../../docs/research/forge-orchestrator-wiring-gap.md) — why this feature exists.
- [DDR-007](../../../docs/design/decisions/DDR-007-pipeline-lifecycle-emitter-wiring-path.md) — emitter wiring path.
- [API-nats-pipeline-events.md §3](../../../docs/design/contracts/API-nats-pipeline-events.md) — the eight lifecycle subjects this feature publishes.
- Superseded historical context: `tasks/completed/TASK-FORGE-FRR-001/` and `tasks/completed/TASK-FORGE-FRR-001b/`.

## Provenance

This feature was filed after the FEAT-JARVIS-INTERNAL-001 first-real-run
on GB10 (2026-05-01, `correlation_id a58ec9a7-27c6-485a-beac-e18675639a10`)
where the runbook's Phase 7 close criterion failed because nothing on
the forge side publishes anything back. The investigation in
`docs/research/forge-orchestrator-wiring-gap.md` surfaced the gap as
structural, not a single-wire fix.
