# FEAT-FORGE-007 — Mode A Greenfield End-to-End

The capstone composition feature for Forge. Drives a single one-line product
brief through the eight-stage Mode A chain — product-owner → architect →
/system-arch → /system-design → /feature-spec → /feature-plan → autobuild →
pull-request review — under one supervised build.

## Status

- **Source review**: [TASK-REV-MAG7](../TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md)
- **Approach**: Option 1 — Reasoning-loop-driven dispatch with deterministic StageOrderingGuard
- **Tasks**: 14 across 5 waves
- **Estimated effort**: 12–16 hours
- **BDD scenarios**: 47 (in [`features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature`](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature))

## Key Documents

- 📋 [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) — Full plan with Mermaid diagrams, integration contracts, risk register
- 📝 [Review report](../../../.claude/reviews/TASK-REV-MAG7-review-report.md) — Decision rationale and option analysis
- 📐 [Feature spec summary](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md)
- 🥒 [Gherkin feature file](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature)

## Subtask Catalogue

### Wave 1 — Foundations (parallel, ~1h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-001](./TASK-MAG7-001-define-stage-taxonomy.md) | Define StageClass enum and prerequisite map | 2 |
| [TASK-MAG7-002](./TASK-MAG7-002-define-forward-propagation-map.md) | Define forward-propagation contract map | 2 |

### Wave 2 — Core Guards (parallel, ~3.5h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-003](./TASK-MAG7-003-stage-ordering-guard.md) | Implement StageOrderingGuard | 5 |
| [TASK-MAG7-004](./TASK-MAG7-004-constitutional-guard.md) | Implement ConstitutionalGuard for PR-review | 4 |
| [TASK-MAG7-005](./TASK-MAG7-005-per-feature-loop-sequencer.md) | Implement PerFeatureLoopSequencer | 4 |

### Wave 3 — Stage Dispatchers + Context Builder (parallel, ~6h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-006](./TASK-MAG7-006-forward-context-builder.md) | Implement ForwardContextBuilder | 5 |
| [TASK-MAG7-007](./TASK-MAG7-007-dispatch-specialist-stage.md) | Wire dispatch_specialist_stage | 4 |
| [TASK-MAG7-008](./TASK-MAG7-008-dispatch-subprocess-stage.md) | Wire dispatch_subprocess_stage | 5 |
| [TASK-MAG7-009](./TASK-MAG7-009-dispatch-autobuild-async.md) | Wire dispatch_autobuild_async | 6 |

### Wave 4 — Supervisor + CLI Steering (sequential, ~4h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-010](./TASK-MAG7-010-supervisor-next-turn.md) | Wire Supervisor.next_turn dispatch loop | 7 |
| [TASK-MAG7-011](./TASK-MAG7-011-cli-steering-injection.md) | Wire CLI steering (cancel/skip/directive) | 5 |

### Wave 5 — Integration Tests (parallel, ~6h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-012](./TASK-MAG7-012-smoke-greenfield-e2e.md) | Smoke greenfield E2E to PR-awaiting-review | 5 |
| [TASK-MAG7-013](./TASK-MAG7-013-crash-recovery-integration.md) | Crash-recovery integration tests | 6 |
| [TASK-MAG7-014](./TASK-MAG7-014-concurrency-multifeature-integration.md) | Concurrency + multi-feature integration | 7 |

## Upstream Substrate (do NOT re-implement)

This feature is **purely composition**. Every primitive below is owned by an
upstream feature and must be consumed through its existing surface:

- **FEAT-FORGE-001** — Build state machine, SQLite history, crash recovery
- **FEAT-FORGE-002** — NATS fleet, pipeline events, build queue (already implemented in [src/forge/pipeline.py](../../../src/forge/pipeline.py))
- **FEAT-FORGE-003** — Specialist agent dispatch
- **FEAT-FORGE-004** — Confidence-gated checkpoint protocol
- **FEAT-FORGE-005** — GuardKit subprocess engine, git/gh adapter, worktree confinement
- **FEAT-FORGE-006** — Long-term memory, priors retrieval, calibration snapshot

See [§9 of the implementation guide](./IMPLEMENTATION-GUIDE.md#9-substrate-reference-do-not-re-implement) for the full surface map.

## Constitutional Invariants (must hold)

1. **Stage-ordering invariant** — no stage dispatched before its prerequisite is approved (Group B Scenario Outline)
2. **Belt-and-braces PR-review** — pull-request review is mandatory human approval at *both* prompt and executor layers (ADR-ARCH-026; Group E security tests)
3. **Per-feature autobuild sequencing** — no second feature's autobuild begins while a prior feature's autobuild is non-terminal (ASSUM-006)
4. **Durable history authoritative** — on crash recovery, SQLite is authoritative; the `async_tasks` state channel is advisory (DDR-006; Group D edge-case)
5. **First-wins idempotency** — duplicate or simultaneous approval responses resolve as exactly one decision (Group D + Group I)
6. **Correlation threading** — every published lifecycle event for a build carries the same correlation_id queue→terminal (Group I @data-integrity)
7. **Calibration priors snapshot stability** — snapshot captured at build start; mid-run mutations apply only to subsequent builds (Group I @data-integrity)

## Quick Start

```bash
# Validate the feature plan before starting
guardkit feature validate FEAT-FORGE-007

# Begin Wave 1 implementation in parallel
/task-work TASK-MAG7-001
/task-work TASK-MAG7-002

# Or run autonomous build
/feature-build FEAT-FORGE-007
```

## Quality Gates

See [§8 of the implementation guide](./IMPLEMENTATION-GUIDE.md#8-quality-gates-checklist) — feature is complete only when all 14 tasks land, all integration tests pass, and all 47 BDD scenarios are tagged via Step 11 BDD linking.
