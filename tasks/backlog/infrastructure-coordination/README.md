# Infrastructure Coordination — FEAT-FORGE-006

**Source review:** [TASK-REV-IC8B](../../../.claude/reviews/TASK-REV-IC8B-review-report.md)
**Spec:** [features/infrastructure-coordination/](../../../features/infrastructure-coordination/)
**Implementation guide:** [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md)

## Problem

Forge's pipeline orchestrator needs cross-build memory and infrastructure
plumbing so that:

- Stage decisions, capability resolutions, override events, calibration
  adjustments, and session outcomes accumulate across builds in Graphiti.
- The operator's Q&A history is incrementally ingested so the reasoning
  model can leverage past calibrations.
- At build start, similar past builds and approved adjustments are
  retrieved as priors and injected into the system prompt.
- Test verification and git/gh operations run safely under the
  constitutional subprocess-permissions constraint.

Without this layer, every build starts cold and the long-term memory
substrate (Graphiti, per ADR-ARCH-005 and ADR-ARCH-022) is unused.

## Solution

Five well-bounded sub-systems, all sharing the same async fire-and-forget
write pattern off the critical path:

1. **Memory write path** — typed entities → redact credentials →
   fire-and-forget Graphiti write. SQLite (FEAT-FORGE-001) is authoritative;
   reconcile-backfill at build start heals any gap.
2. **Q&A history ingestion** — on-build-start content-hash scan; only
   changed files are re-parsed and emitted as `CalibrationEvent` entities.
3. **Priors retrieval** — four parallel `asyncio.gather()` sub-queries;
   results assembled into a structured prose block injected into the
   reasoning-model system prompt.
4. **Test verification** — pytest invoked through the DeepAgents `execute`
   tool inside the per-build worktree.
5. **Git/gh operations** — branch, commit, push, PR creation through the
   `execute` tool with allowlist `{git, gh, pytest}` and env-only
   credentials.

## Subtasks (12 across 6 waves)

| Wave | Task ID | Title | Type | Complexity |
|------|---------|-------|------|------------|
| 1 | TASK-IC-001 | Entity model layer and credential redaction | declarative | 4 |
| 1 | TASK-IC-009 | Test verification via DeepAgents execute tool | feature | 3 |
| 2 | TASK-IC-002 | Fire-and-forget Graphiti write wrapper | feature | 5 |
| 2 | TASK-IC-008 | Supersession-cycle detection for CalibrationAdjustment | feature | 4 |
| 2 | TASK-IC-010 | Git/gh operations via DeepAgents execute tool | feature | 4 |
| 3 | TASK-IC-003 | Write-ordering guard (SQLite-first, Graphiti-second) | feature | 3 |
| 3 | TASK-IC-005 | Q&A history ingestion pipeline | feature | 5 |
| 3 | TASK-IC-006 | Priors retrieval and prose injection | feature | 5 |
| 4 | TASK-IC-004 | Reconcile backfill at build start | feature | 6 |
| 4 | TASK-IC-007 | SessionOutcome writer with ordering and idempotency | feature | 5 |
| 5 | TASK-IC-011 | BDD step implementations for all 43 scenarios | testing | 6 |
| 6 | TASK-IC-012 | Security and concurrency scenario hardening | testing | 4 |

**Aggregate complexity:** 8/10 • **Estimated effort:** 40-60 hours

## Open assumptions — resolved

| ID | Resolution |
|----|-----------|
| ASSUM-006 (credential redaction) | Confirm with concrete regex set: bearer tokens, GitHub PATs, generic high-entropy hex |
| ASSUM-007 (split-brain dedupe) | Confirm via SQLite-row UUID as Graphiti `entity_id` (no separate pre-check) |
| ASSUM-008 (GateDecision link order) | Confirm with explicit client-side sort by `decided_at` ascending |

## Upstream dependencies

- **FEAT-FORGE-001** — Pipeline State Machine: provides SQLite `stage_log`
  and the terminal-state callback hook.
- **FEAT-FORGE-002** — NATS Fleet Integration: emits
  `CapabilityResolution` and `OverrideEvent` payloads consumed here.

## How to start

1. Read [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) end-to-end —
   the Data Flow diagram (§1) is required reading.
2. Run Wave 1 in parallel: `/task-work TASK-IC-001` and `/task-work
   TASK-IC-009` (Conductor workspaces recommended).
3. Iterate through waves in order; each wave's tasks are parallel-safe
   within the wave.
4. After Wave 6, run `/feature-complete FEAT-FORGE-006` to merge and
   archive.

## See also

- [Decision review report](../../../.claude/reviews/TASK-REV-IC8B-review-report.md)
- [Feature spec (Gherkin)](../../../features/infrastructure-coordination/infrastructure-coordination.feature)
- [Feature summary](../../../features/infrastructure-coordination/infrastructure-coordination_summary.md)
- [Open assumptions](../../../features/infrastructure-coordination/infrastructure-coordination_assumptions.yaml)
- [AGENTS.md (constitutional constraints)](../../../AGENTS.md)
