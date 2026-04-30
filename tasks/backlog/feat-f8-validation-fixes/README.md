# FEAT-F8 — FEAT-FORGE-008 Validation-Triage Fixes

Eight fix tasks fanning out from `TASK-REV-F008`'s architectural review of the
2026-04-29 Step 6 validation walkthrough. Two of the eight are delegated
hand-offs (NATS provisioning → `nats-infrastructure`; production Dockerfile
→ scoping a sibling forge feature) — the remaining six are forge-internal
implementation tasks ordered into three waves.

## At a glance

| | |
|---|---|
| **Feature ID (docs)** | FEAT-F8-VALIDATION-FIXES |
| **Slug** | `feat-f8-validation-fixes` |
| **Parent review** | [TASK-REV-F008](../TASK-REV-F008-fix-feat-forge-008-validation-failures.md) |
| **Triage report** | [docs/reviews/REVIEW-F008-validation-triage.md](../../../docs/reviews/REVIEW-F008-validation-triage.md) |
| **Tasks** | 8 across 3 waves (6 implementation + 2 delegated) |
| **Aggregate complexity** | 4/10 |
| **Estimated effort** | ~10–14 hours dispatched (~2 days wall, gated on AC-6) |
| **Substrate dependencies** | FEAT-FORGE-007 (Mode A) + FEAT-FORGE-008 (Mode B/C) shipped |

## Problem statement

The Step 6 validation walkthrough hit the runbook's §1.3 hard-stop:

> **If any Mode A test is red, FEAT-FORGE-008 broke `Supervisor.next_turn` — stop and triage.**

It did. `Supervisor._dispatch` raises `TypeError: no routing for stage <StageClass.TASK_REVIEW>` whenever Mode A reaches `task-review`, because `_SUBPROCESS_STAGES` was never extended to include the two FEAT-FORGE-008 stage classes. Plus four other reds, one collection error, one cross-repo wire/CLI contradiction, and ~9 runbook copy-paste gaps.

The architectural review re-classifies the seven `F008-VAL-*` follow-ups, picks Option A (sibling `task_id` on `BuildQueuedPayload`) for the Mode C wire-schema mismatch, and splits Wave 3 (NATS infra → delegated; Dockerfile → sibling feature). See `docs/reviews/REVIEW-F008-validation-triage.md` for the full triage table and design rationale.

## Solution approach (per `Q2=Q` quality/correctness)

Three waves, with an AC-6 go/no-go gate after Wave 1:

```
Wave 1 (forge-internal, parallel-safe)  — ✅ COMPLETE 2026-04-30
  ✅ TASK-F8-003   supervisor _dispatch routing (BLOCKER)        commit 68adba9
  ✅ TASK-F8-004   recovery.py AC-008 single-ownership restore   commit c9503f1
  ✅ TASK-F8-005   stale idempotency-test assertion update       commit 8c06012

  ── AC-6 GATE: PASSED 2026-04-30 — Phase 1 sweep 3804p/0f, Mode A green ──

Wave 2 (parallel-safe; F8-002 cross-repo nats-core 0.3.0)  — ✅ COMPLETE 2026-04-30
  ✅ TASK-F8-002   Mode C task_id field (forge + nats-core)       commit ae20423 (nats-core)
  ✅ TASK-F8-001   forge.build.git_operations + test_verification commit d0c2f81
  ✅ TASK-F8-006   runbook gap-fold (LES1 §8 contract)             commit 35952fd

  ── re-run Phases 1+2+3; declare Step 6 canonical for Phases 0–3 (PENDING OPERATOR) ──

Wave 3 (delegated, parallel-allowed throughout — no gate dependency)
  ▶ TASK-F8-007a  NATS canonical provisioning handoff → nats-infrastructure
  ✅ TASK-F8-007b  production Dockerfile scoping → spawned FEAT-FORGE-009 stub  2026-04-30
```

## Tasks

| ID | Wave | Title | Complexity | Mode | Status |
|---|---|---|---|---|---|
| [TASK-F8-003](TASK-F8-003-supervisor-dispatch-task-review.md) | 1 | Add TASK_REVIEW + TASK_WORK to `_SUBPROCESS_STAGES` (BLOCKER) | 3 | task-work | ✅ `68adba9` |
| [TASK-F8-004](TASK-F8-004-recovery-evidence-priors-helper.md) | 1 | Restore AC-008 single-ownership of `evidence_priors` | 4 | task-work | ✅ `c9503f1` |
| [TASK-F8-005](TASK-F8-005-update-idempotency-test-for-v2.md) | 1 | Update `apply_at_boot` idempotency test for v2 schema | 1 | direct | ✅ `8c06012` |
| [TASK-F8-002](TASK-F8-002-mode-c-task-id-payload.md) | 2 | Add `task_id` + `mode` fields to `BuildQueuedPayload` (cross-repo) | 6 | task-work | ✅ `ae20423` (nats-core) + forge CLI/pin |
| [TASK-F8-001](TASK-F8-001-land-forge-build-modules.md) | 2 | Land `forge.build.git_operations` + `forge.build.test_verification` | 5 | task-work | ✅ `d0c2f81` |
| [TASK-F8-006](TASK-F8-006-runbook-gap-fold-feat-008.md) | 2 | Apply LES1 §8 runbook gap-fold to RUNBOOK-FEAT-FORGE-008-validation.md | 3 | direct | ✅ `35952fd` |
| [TASK-F8-007a](TASK-F8-007a-nats-canonical-provisioning-handoff.md) | 3 | Hand off canonical NATS provisioning to `nats-infrastructure` | 2 | direct | ▶ pending |
| [TASK-F8-007b](../../completed/TASK-F8-007b/TASK-F8-007b-forge-production-dockerfile-spec.md) | 3 | Scope production Dockerfile → sibling FEAT-FORGE-009 | 3 | direct | ✅ 2026-04-30 (scoping doc + FEAT-FORGE-009 stub) |

## Wave structure

```
Wave 1  ▶ TASK-F8-003, 004, 005           (file-disjoint, parallel-safe)
                ↓
        AC-6 gate: re-run pytest -q + Phase 1.x sweep
                ↓
Wave 2  ▶ TASK-F8-002, 001, 006           (file-disjoint within forge;
                                            F8-002 has cross-repo nats-core dep)
                ↓
        re-run Phases 1+2+3 → Step 6 canonical for Phases 0–3
                ↓
Wave 3  ▶ TASK-F8-007a, 007b              (delegated/scoping; no gate)
                ↓
        Phase 6 LES1 gates (after Wave 3 prerequisites land in their repos)
```

## Out of scope

- Implementing the FEAT-FORGE-009 production Dockerfile feature (TASK-F8-007b only **scopes** it).
- Provisioning canonical NATS streams (TASK-F8-007a only **hands off** the spec).
- Re-running the runbook (separate operator action gated on AC-6).
- Step 7 (FinProxy first run) — blocked by Step 6 going canonical.

## Acceptance criteria (rolled up from per-task ACs)

- [x] All Wave 1 tests green; runbook Phase 1 re-run is byte-identical to the
      "what was healthy" section of `RESULTS-FEAT-FORGE-008-validation.md`.
      AC-6 gate ran 2026-04-30: pytest 3804p/1s/0f, Mode A 16/16, BDD 219/219,
      `test_apply_at_boot_is_idempotent` and
      `test_no_other_module_in_forge_constructs_evidence_priors` both green.
- [x] All Wave 2 tasks merged (forge-internal + nats-core 0.3.0). End-to-end
      smoke (`tests/integration/test_mode_c_smoke_e2e.py`) passes 17/17 with
      the new `task_id` + `mode` fields on the wire.
      ⏸ Pending operator: re-run runbook Phases 0–3 verbatim to formally
      declare Step 6 canonical.
- [ ] Wave 3 hand-off documents merged and tracked in their owning repos.
