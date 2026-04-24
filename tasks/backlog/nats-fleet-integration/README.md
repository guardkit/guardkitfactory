# NATS Fleet Integration (FEAT-FORGE-002)

Forge's participation on the shared NATS fleet — registration, heartbeats,
live discovery cache, outbound pipeline lifecycle events, and inbound
build-queue subscription with terminal-only ack.

## Quick links

- **Review report**: [.claude/reviews/TASK-REV-NF20-review-report.md](../../../.claude/reviews/TASK-REV-NF20-review-report.md)
- **Implementation guide**: [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) *(diagrams + Integration Contracts)*
- **Feature spec**: [features/nats-fleet-integration/nats-fleet-integration.feature](../../../features/nats-fleet-integration/nats-fleet-integration.feature) *(33 scenarios, 3 smoke)*
- **Feature summary**: [features/nats-fleet-integration/nats-fleet-integration_summary.md](../../../features/nats-fleet-integration/nats-fleet-integration_summary.md)
- **Assumptions**: [features/nats-fleet-integration/nats-fleet-integration_assumptions.yaml](../../../features/nats-fleet-integration/nats-fleet-integration_assumptions.yaml) *(5 high-confidence, all confirmed)*

## Problem

Forge must be discoverable to Jarvis, dashboards, and operators as a
first-class fleet agent, and must broadcast every pipeline lifecycle
event so downstream listeners can thread progress. It must also *route
work* by knowing which specialist agents are actually available, falling
back cleanly to "flag for review" when no match exists. The inbound
build-queue must honour at-least-once redelivery with strict terminal-
only acknowledgement so a crashed Forge can resume from the same message
on restart.

## Approach — Option 1 (Thin Adapter Layer over nats-core)

Selected at the review decision checkpoint. Pure-domain `forge.discovery`
package with no NATS imports; thin `forge.adapters.nats.*` adapters for
the five boundary responsibilities (fleet publish, fleet watch, pipeline
publish, pipeline consume, crash reconcile); state-machine hooks wire
lifecycle emissions from FEAT-FORGE-001's state transitions into the
publisher.

Why not the alternatives:

- **Monolithic `forge.nats` module** — violates ADR-ARCH-017 separation
  between domain and transport; hard to test; blends concerns.
- **`EventBus` protocol + in-memory impl** — violates ADR-ARCH-003 (no
  transport ABC); YAGNI because no second transport is planned.

## Execution — 5 waves, 11 subtasks

| Wave | Tasks | Mode |
|---|---|---|
| 1 | [TASK-NFI-001](./TASK-NFI-001-extend-forge-config-fleet-pipeline-sections.md), [TASK-NFI-002](./TASK-NFI-002-define-forge-manifest-constant.md) | Parallel (Conductor) |
| 2 | [TASK-NFI-003](./TASK-NFI-003-implement-discovery-domain.md) | Single |
| 3 | [TASK-NFI-004](./TASK-NFI-004-fleet-publisher.md), [TASK-NFI-005](./TASK-NFI-005-fleet-watcher.md), [TASK-NFI-006](./TASK-NFI-006-pipeline-publisher.md), [TASK-NFI-007](./TASK-NFI-007-pipeline-consumer.md) | Parallel (Conductor) |
| 4 | [TASK-NFI-008](./TASK-NFI-008-wire-state-machine-lifecycle-emission.md) → [TASK-NFI-009](./TASK-NFI-009-reconcile-on-boot-crash-recovery.md) | Sequential |
| 5 | [TASK-NFI-010](./TASK-NFI-010-contract-and-seam-tests.md), [TASK-NFI-011](./TASK-NFI-011-bdd-scenario-pytest-wiring.md) | Parallel (Conductor) |

## Upstream gate

**Wave 3 cannot start** until FEAT-FORGE-001 provides:

- `builds` SQLite table + `uq_builds_feature_correlation` unique index
- `BuildStatus` enum per DM-build-lifecycle §2
- State-machine transition hooks
- Existing `ForgeConfig` loader for TASK-NFI-001 to extend

Waves 1 and 2 can proceed independently (pure declarative + pure domain).

## Key risks

1. Terminal-only ack invariant (ack fires only on COMPLETE/FAILED/CANCELLED/SKIPPED)
2. Cache consistency under racing register/deregister events
3. Heartbeat loop independence from registry reachability
4. Publish failures must not roll back SQLite history
5. Secret-free manifest (no API keys in published `AgentManifest`)
6. Timing-sensitive tests must use injected `Clock` — no wall-clock sleeps

Full risk register: [review report §Risk Register](../../../.claude/reviews/TASK-REV-NF20-review-report.md#risk-register).

## Testing posture

Standard quality gates (from Context B):
- Unit tests per module
- Contract + seam tests at the `nats_client` boundary (TASK-NFI-010)
- BDD scenario coverage, `@smoke` + `@key-example` priority (TASK-NFI-011)
- Clock injection everywhere time matters
- 80% line coverage target for `forge.adapters.nats.*` and `forge.discovery.*`

## Start here

```bash
# Wave 1 (parallel)
/task-work TASK-NFI-001
/task-work TASK-NFI-002

# Wave 2
/task-work TASK-NFI-003

# Wave 3 (parallel) — only after FEAT-FORGE-001 upstream gate cleared
/task-work TASK-NFI-004
/task-work TASK-NFI-005
/task-work TASK-NFI-006
/task-work TASK-NFI-007

# Wave 4 (sequential)
/task-work TASK-NFI-008
/task-work TASK-NFI-009

# Wave 5 (parallel)
/task-work TASK-NFI-010
/task-work TASK-NFI-011
```

Or use AutoBuild:

```bash
/feature-build FEAT-FORGE-002
```
