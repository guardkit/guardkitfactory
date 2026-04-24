---
id: TASK-REV-NF20
title: "Plan: NATS Fleet Integration"
task_type: review
status: backlog
priority: high
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
complexity: 8
tags: [planning, review, nats, fleet, integration, feat-forge-002]
feature_spec: features/nats-fleet-integration/nats-fleet-integration_summary.md
feature_id: FEAT-FORGE-002
upstream_dependencies:
  - FEAT-FORGE-001  # Pipeline State Machine & Configuration
clarification:
  context_a:
    timestamp: 2026-04-24T00:00:00Z
    decisions:
      focus: all
      tradeoff: balanced
      specific_concerns: null
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan NATS Fleet Integration (FEAT-FORGE-002)

## Description

Decision-making review for **FEAT-FORGE-002 — NATS Fleet Integration**. The feature
specifies Forge's role on the shared NATS fleet: self-registration, periodic
heartbeats, graceful deregistration, live watching of fleet lifecycle events, and
capability resolution via a 30-second-TTL discovery cache with degraded-mode
fallback. It also covers the outbound pipeline-event stream (started / progress /
stage-complete / paused / resumed / complete / failed / cancelled) and the inbound
build-queue subscription with terminal-only acknowledgement, duplicate detection,
and path-allowlist refusal.

The review must surface the recommended technical approach, architecture
boundaries, risk analysis, effort estimation, and a subtask breakdown that
downstream `/feature-build` can execute against.

## Scope of Analysis

Review must cover **all areas (full sweep)** with a **balanced** trade-off
priority. No specific concerns pre-flagged — surface concerns organically.

Concrete areas to examine:

1. **Transport choice**: nats-py client selection; JetStream vs Core NATS decision
   for the build-queue (redelivery + terminal-ack semantics) and fleet bus.
2. **Component boundaries**: how fleet integration layers onto the FEAT-FORGE-001
   state machine and SQLite history without coupling state transitions to
   transport availability.
3. **Concurrency & async**: cache-update ordering under racing register/deregister
   events; heartbeat loop independence from registry availability.
4. **Security**: secret-free manifest construction; originator allowlist for
   build-queued messages; path-allowlist refusal pathway.
5. **Performance & reliability**: heartbeat cadence (30s), stale threshold (90s),
   cache TTL (30s), progress cadence (≥60s during RUNNING), intent-fallback
   confidence threshold (0.7).
6. **Data integrity**: at-least-once redelivery idempotency; publish failures must
   not roll back recorded history; crash-recovery re-announcement for paused builds.
7. **Test strategy**: contract/seam tests for bus boundaries; deterministic async
   tests for heartbeats and cache TTL without wall-clock flakiness.

## Acceptance Criteria

- [ ] Technical options analysed with pros/cons and a recommended approach
- [ ] Architecture boundary between fleet integration and FEAT-FORGE-001
      state machine documented
- [ ] Effort estimated with complexity score (1–10) per proposed subtask
- [ ] Risk register produced covering transport failures, redelivery, concurrency
- [ ] Subtask breakdown with dependencies and parallel-wave organisation
- [ ] Integration contracts identified (producer/consumer artifact handshakes)
- [ ] Decision checkpoint presented: [A]ccept / [R]evise / [I]mplement / [C]ancel

## Clarification Context

**Context A — Review Scope** (captured 2026-04-24):

- Review focus: **All areas (full sweep)**
- Trade-off priority: **Balanced**
- Specific concerns: _None pre-flagged_

## Context Files

- `features/nats-fleet-integration/nats-fleet-integration_summary.md`
- `features/nats-fleet-integration/nats-fleet-integration.feature` (33 scenarios)
- `features/nats-fleet-integration/nats-fleet-integration_assumptions.yaml` (5 high-confidence)
- `docs/design/contracts/API-nats-fleet-lifecycle.md`
- `docs/design/contracts/API-nats-pipeline-events.md`
- `docs/design/contracts/API-nats-agent-dispatch.md`
- `docs/design/models/DM-discovery.md`
- `docs/design/models/DM-build-lifecycle.md`

## Next Steps

```bash
/task-review TASK-REV-NF20 --mode=decision --depth=standard
```
