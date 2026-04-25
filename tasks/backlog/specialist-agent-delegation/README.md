# FEAT-FORGE-003 — Specialist Agent Delegation

**Status**: planned · **Complexity**: 8/10 · **Effort**: 26–34h · **Tasks**: 12 · **Waves**: 5

## Problem

Forge needs a single capability-driven dispatch path so that domain
judgement on every gated stage can be delegated to fleet specialist
agents. The path must:

- Resolve a target specialist via the live discovery cache (exact-tool
  match → intent-pattern fallback at 0.7 confidence → tie-break by trust
  tier → confidence → queue depth).
- Subscribe to a correlation-keyed reply channel **before** publishing the
  command (the LES1 invariant).
- Treat PubAck on the audit stream as **not** success — only an authentic
  reply on the correlation channel completes the round-trip.
- Parse the specialist's reply (Coach top-level fields preferred over
  nested) into a stage outcome the gating layer can consume.
- Handle soft failures via reasoning-model-driven retry (no fixed max).
- Surface a degraded outcome to the reasoning loop when no specialist is
  resolvable.
- Preserve sensitive parameters via schema-driven scrub at the persistence
  boundary.

## Approach (Option 1 — recommended by review)

Pure-domain `forge.dispatch` package mirroring the existing
`forge.discovery` (domain) + `forge.adapters.nats` (transport) split. The
dispatch callback seam already exists at
[pipeline_consumer.py](../../../src/forge/adapters/nats/pipeline_consumer.py)
(`DispatchBuild` callable type alias) — this feature provides the missing
callable.

```
src/forge/dispatch/         (new — pure domain)
├── models.py               TASK-SAD-001
├── persistence.py          TASK-SAD-002
├── correlation.py          TASK-SAD-003
├── timeout.py              TASK-SAD-004
├── reply_parser.py         TASK-SAD-005
├── orchestrator.py         TASK-SAD-006
├── retry.py                TASK-SAD-007
├── async_polling.py        TASK-SAD-008
└── outcome.py              TASK-SAD-009

src/forge/adapters/nats/specialist_dispatch.py   TASK-SAD-010 (sole NATS import site)
tests/bdd/test_specialist_agent_delegation.py    TASK-SAD-011
tests/forge/dispatch/test_contract_and_seam.py   TASK-SAD-012
```

## Tasks (12)

| ID | Title | Wave | Complexity | Type |
|---|---|---|---|---|
| [TASK-SAD-001](./TASK-SAD-001-dispatch-package-skeleton.md) | Dispatch package skeleton + models | 1 | 2 | declarative |
| [TASK-SAD-002](./TASK-SAD-002-resolution-record-persistence.md) | Resolution-record persistence + sensitive-param scrub | 1 | 5 | feature |
| [TASK-SAD-003](./TASK-SAD-003-correlation-registry.md) | CorrelationRegistry (subscribe-before-publish, exactly-once, source-auth) | 2 | 7 | feature |
| [TASK-SAD-004](./TASK-SAD-004-timeout-coordinator.md) | Timeout coordinator | 2 | 5 | feature |
| [TASK-SAD-005](./TASK-SAD-005-reply-parser.md) | Reply parser | 2 | 5 | feature |
| [TASK-SAD-006](./TASK-SAD-006-dispatch-orchestrator.md) | Dispatch orchestrator | 3 | 7 | feature |
| [TASK-SAD-007](./TASK-SAD-007-retry-coordinator.md) | Retry coordinator | 3 | 5 | feature |
| [TASK-SAD-008](./TASK-SAD-008-async-mode-polling.md) | Async-mode polling | 4 | 4 | feature |
| [TASK-SAD-009](./TASK-SAD-009-correlate-outcome-and-degraded.md) | correlate_outcome() + degraded synthesis | 4 | 5 | feature |
| [TASK-SAD-010](./TASK-SAD-010-nats-adapter-specialist-dispatch.md) | NATS adapter | 4 | 6 | feature |
| [TASK-SAD-011](./TASK-SAD-011-bdd-smoke-pytest-wiring.md) | BDD smoke + key-example pytest wiring | 5 | 4 | testing |
| [TASK-SAD-012](./TASK-SAD-012-contract-and-seam-tests.md) | Contract & seam tests | 5 | 5 | testing |

## Wave plan

```
Wave 1: SAD-001  SAD-002                              (parallel)
Wave 2: SAD-003  SAD-004  SAD-005                     (parallel)
Wave 3: SAD-006 → SAD-007                             (sequential)
Wave 4: SAD-008  SAD-009  SAD-010                     (parallel)
Wave 5: SAD-011  SAD-012                              (parallel)
```

## Upstream dependencies

- **FEAT-FORGE-001** — Pipeline state machine + SQLite history (substrate
  for `CapabilityResolution` records).
- **FEAT-FORGE-002** — NATS Fleet Integration (live fleet cache, fleet
  lifecycle subscription, pipeline event publishing, dispatch callback
  seam in `pipeline_consumer.py`).

## Downstream surface

- **FEAT-FORGE-004** — Confidence-Gated Checkpoint Protocol consumes
  `DispatchOutcome` and calls `correlate_outcome()` after gate decisions.
  Both are stable contracts declared in `IMPLEMENTATION-GUIDE.md` §4.

## Documents

- [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) — architecture, data
  flow, integration contracts, scenario coverage map
- [Review report](../../../.claude/reviews/TASK-REV-SAD3-review-report.md) — full options analysis, risks, findings
- [Source review task](../../in_review/TASK-REV-SAD3-plan-specialist-agent-delegation.md)
- [Feature spec](../../../features/specialist-agent-delegation/specialist-agent-delegation_summary.md)
- [BDD scenarios](../../../features/specialist-agent-delegation/specialist-agent-delegation.feature)

## Next steps

1. Review [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) and the
   §4 Integration Contracts.
2. Start with Wave 1 (TASK-SAD-001 + TASK-SAD-002 in parallel).
3. Use `/feature-build FEAT-FORGE-003` for autonomous implementation, or
   `/task-work TASK-SAD-001` to start manually.
