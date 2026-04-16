---
id: TASK-FVD2
title: Correct forge-build-plan.md to match anchor v2.2
status: completed
completed: 2026-04-16T00:00:00Z
task_type: documentation
parent_review: TASK-REV-A1F2
feature_id: FEAT-FVDA
priority: high
tags: [documentation, forge-build-plan, v2.2]
complexity: 5
wave: 2
implementation_mode: task-work
dependencies: [TASK-FVD1]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Correct forge-build-plan.md to match anchor v2.2

## Context

`docs/research/ideas/forge-build-plan.md` predates anchor v2.1 and carries "Forge-as-checkpoint-manager / fleet-agent-receiving-agents.command.forge" framing from the pre-v2.1 orchestrator refresh. Before `/system-arch` is run with this file as context, the drift must be removed. The alignment review lists the corrections; this task applies them.

## Scope — corrections 13–21 from the alignment review

Apply each correction by line reference:

### 13. Hard Prerequisites (lines 38–47)

Caveat the "nats-core library implemented — 97% test coverage" claim:

> - [~] **nats-core library implemented** — shipping at 98% coverage, but v2.2-critical payloads (`BuildQueuedPayload`, `BuildPausedPayload`, `BuildResumedPayload`, `StageCompletePayload`, `StageGatedPayload`) and their topics must be added in Phase 2 (nats-core/tasks/backlog/forge-v2-alignment/TASK-NCFA-001)

### 14. Feature Summary (lines 104–115)

Reconcile `FEAT-FORGE-001..008` with anchor v2.2 §10 Phase 4 capability list. Options:

1. Re-map each existing feature to the anchor's Phase 4 bullet list as a "maps to" column, OR
2. Rewrite the feature list to mirror the anchor's Phase 4 bullets

Prefer option 1 — less churn. Add a new "Anchor §10 Phase 4 coverage" column showing which bullets each feature satisfies. Flag any bullets that aren't covered by any feature.

### 15. Forge Agent Manifest (lines 409–446)

- `nats_topic: agents.command.forge` (singular, already correct — verify)
- `max_concurrent: 3` → **`max_concurrent: 1`** (ADR-SP-012 sequential builds)
- Add intent patterns aligned with ADR-SP-014 Jarvis discovery (retain existing `build.*`, `pipeline.*`, `feature.*` — they are compatible)

### 16. Validation + FinProxy (lines 300–338)

Replace `python -m forge.cli greenfield --project finproxy …` with the canonical CLI surface from anchor §5:

```bash
forge queue FEAT-FINPROXY-001 --repo guardkit/finproxy --branch main
forge status
forge history --feature FEAT-FINPROXY-001
```

Drop the `greenfield`/`feature`/`review-fix` mode-based CLI unless Rich decides to promote it into the anchor. A note: "Mode-based wrappers (`forge greenfield`, `forge feature`, `forge review-fix`) are optional higher-level wrappers around `forge queue` and may be added later if they earn their place."

### 17. Pipeline Configuration Schema (lines 453–491)

Reconcile the `forge-pipeline-config.yaml` schema with anchor §4's `forge.yaml`. The build plan's schema is richer (reviewer assignment, critical detections, escalation channels). Two options:

1. Promote the richness into the anchor as a v2.3 amendment (new correction task)
2. Strip the build plan's schema down to match the anchor's `confidence_thresholds` + `build_config` + `degraded_mode` shape

Recommendation: promote. The reviewer/channel/detection fields are operationally useful. Open a TASK-FVD5 (new, follow-up) to amend the anchor; for now leave both schemas in the build plan with a note that the fuller schema is pending anchor ratification.

### 18. Context Documents Available + Source Documents (lines 87–96, 616–629)

Remove any entry referencing "Dev pipeline architecture" or "Dev pipeline system spec" (project knowledge — both explicitly superseded by v2.1/v2.2). Add:

- `forge/docs/research/forge-pipeline-architecture.md` (v2.2) — **primary context for /system-arch**
- `forge/docs/research/forge-build-plan-alignment-review.md` — drift history / supporting context

### 19. Update (same as #15)

Covered above.

### 20. Prerequisites — specialist-agent dual-role

Add to Hard Prerequisites:

> - [ ] **Specialist-agent dual-role deployment** — `--role` flag wired to manifest builder; `get_product_owner_manifest()` exists; `agent_id` derived from role or overridable via `SPECIALIST_AGENT_ID`; PO + Architect can run concurrently on the same NATS without fleet registration collision. Tracked in `specialist-agent/tasks/backlog/dual-role-deployment/`.

### 21. Jarvis Integration subsection

Add a new section (placement: after "Pipeline Configuration Schema", before "Risks & Mitigations") titled **Jarvis Integration**. Content: 1–2 paragraphs summarising ADR-SP-014 Pattern A, with a pointer to the alignment review Appendix C for the `BuildQueuedPayload` fields. Explicit: `forge queue` CLI publishes the same payload to the same topic as Jarvis does — the build plan does not require Jarvis to function; Jarvis just adds the voice/Telegram/dashboard entry points.

## Acceptance criteria

- [ ] All seven corrections (13–21) applied
- [ ] No references to "Dev pipeline architecture" or "Dev pipeline system spec" remain
- [ ] `max_concurrent: 3` → `1`
- [ ] CLI surface uses `forge queue`
- [ ] New Jarvis Integration section exists
- [ ] Grep for `agents.commands.` returns 0 hits in this file
- [ ] Grep for `PM Adapter`, `Kanban`, `ready-for-dev` returns 0 hits outside any explicit "removed" note
- [ ] The file's header "Status" line is updated to reference anchor v2.2

## Out of scope

- Changes to the anchor (TASK-FVD1)
- Any code changes
- Rewriting the feature waves themselves — only renames/remaps
