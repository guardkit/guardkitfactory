# FEAT-FORGE-004 — Confidence-Gated Checkpoint Protocol

Implementation structure for the confidence-gated checkpoint protocol.

- **Parent review**: [TASK-REV-CG44](../TASK-REV-CG44-plan-confidence-gated-checkpoint-protocol.md)
- **Review report**: [.claude/reviews/TASK-REV-CG44-review-report.md](../../../.claude/reviews/TASK-REV-CG44-review-report.md)
- **Feature spec**: [confidence-gated-checkpoint-protocol.feature](../../../features/confidence-gated-checkpoint-protocol/confidence-gated-checkpoint-protocol.feature)
- **Implementation guide**: [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md)

## Problem

Forge runs unattended pipelines that touch real artefacts (PRs, tests,
docs). Some stages are confidently-supported by past evidence and should
proceed without bothering Rich; some are clearly unsafe and must halt;
the rest sit in the middle and need Rich's judgment. The same protocol
must:

- Halt loudly on poor evidence (so unsafe work doesn't burn turns)
- Pause cleanly on ambiguous evidence (so Rich can review)
- Auto-approve on confident evidence (so safe work doesn't wait)
- **Always** require human approval for PR review and PR creation,
  regardless of evidence (constitutional rule, ADR-ARCH-026)
- Be traceable — every decision records its rationale, the priors that
  shaped it, and the findings considered

## Solution

A pure-domain `forge.gating` package containing the four gate modes
(`AUTO_APPROVE`, `FLAG_FOR_REVIEW`, `HARD_STOP`, `MANDATORY_HUMAN_APPROVAL`)
and a pure `evaluate_gate()` function that assembles a reasoning-model
prompt from priors, findings, and approved calibration adjustments —
**no static thresholds** (ADR-ARCH-019). A thin NATS approval adapter
publishes `ApprovalRequestPayload` on `agents.approval.forge.{build_id}`
and consumes `ApprovalResponsePayload` on the `.response` mirror, with
short-TTL idempotency on a deterministic `request_id`. CLI steering
(`forge cancel`, `forge skip`) injects synthetic responses through the
same dedup queue. SQLite is the source of truth: decisions are persisted
before bus publishes, and a publish failure does not roll back the
recorded decision.

## Subtasks (12 across 5 waves)

### Wave 1 — Foundation (parallel-safe)

- **TASK-CGCP-001** — Define `forge.gating` module structure (models, pure-function shell)
- **TASK-CGCP-002** — Add `forge.config.approval` settings (default 300s, max 3600s)
- **TASK-CGCP-003** — Define `request_id` derivation helper (deterministic, pure)

### Wave 2 — Pure evaluator + CLI injector (parallel-safe)

- **TASK-CGCP-004** — Implement constitutional override branch in `evaluate_gate` (ADR-ARCH-026 belt-and-braces)
- **TASK-CGCP-005** — Implement reasoning-model assembly + post-condition checks
- **TASK-CGCP-008** — Implement `synthetic_response_injector` for `forge cancel`/`forge skip` CLI steering

### Wave 3 — NATS approval adapter (parallel-safe)

- **TASK-CGCP-006** — Implement `approval_publisher` (publish ApprovalRequestPayload + details builder)
- **TASK-CGCP-007** — Implement `approval_subscriber` with short-TTL dedup buffer (first-response-wins)
- **TASK-CGCP-009** — Wire `resume_value_as` helper at every `interrupt()` consumer (DDR-002)

### Wave 4 — State-machine integration

- **TASK-CGCP-010** — Wire `gate_check` wrapper into FEAT-FORGE-001 state machine (pause-and-publish atomicity)

### Wave 5 — Tests + BDD activation (parallel-safe)

- **TASK-CGCP-011** — Contract and seam tests for the approval round-trip across NATS
- **TASK-CGCP-012** — BDD scenario→task linking and pytest-bdd wiring (R2 oracle activation)

## Aggregate

- **Estimated effort**: 22–28 focused hours
- **Aggregate complexity**: 8/10
- **Total scenarios under coverage**: 32 BDD scenarios across 4 gate modes, security, concurrency, data integrity, idempotency, crash-recovery
- **Highest-stakes test**: Group E `@security @regression` two-layer constitutional regression (TASK-CGCP-011)

## Upstream dependencies

This feature depends on the prior three Forge features being in place
before Wave 4 starts:

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration (paused state, crash recovery, SQLite substrate)
- **FEAT-FORGE-002** — NATS Fleet Integration (approval channel rides on fleet message bus)
- **FEAT-FORGE-003** — Specialist Agent Delegation (Coach scores, criterion breakdowns, detection findings — degraded-mode if absent)

## Next steps

1. Review [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md)
2. Confirm upstream dependency gates (FEAT-FORGE-001/002/003) are met before Wave 4
3. Start with Wave 1 — three parallel-safe declarative tasks
4. Use `/feature-build FEAT-FORGE-004` for autonomous execution, or
   `/task-work TASK-CGCP-001` to begin manually
