---
id: TASK-FVD3
title: Correct forge-pipeline-orchestrator-refresh.md framing and gaps
status: completed
completed: 2026-04-16T00:00:00Z
task_type: documentation
parent_review: TASK-REV-A1F2
feature_id: FEAT-FVDA
priority: high
tags: [documentation, orchestrator-refresh, v2.2]
complexity: 4
wave: 2
implementation_mode: task-work
dependencies: [TASK-FVD1]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Correct forge-pipeline-orchestrator-refresh.md framing and gaps

## Context

`docs/research/ideas/forge-pipeline-orchestrator-refresh.md` v3 (11 April 2026) materially reframes Forge from "pipeline orchestrator" to "checkpoint manager" and is silent on the build trigger, 5-stage taxonomy, state machine states, and Jarvis integration. Anchor v2.2 is the canonical framing; this doc must align.

## Scope — corrections 8–12 from the alignment review

### 8. Rewrite opening paragraph

Current framing ("Forge is a checkpoint manager that delegates orchestration") → "Forge is the NATS-native pipeline orchestrator; confidence-gated checkpoints are how it decides when to involve Rich". Keep the checkpoint protocol content — it is the strength of this doc. Just re-anchor the identity.

Add a short note at the top: "This document is a supporting design artefact for the checkpoint protocol and specialist-agent delegation model. The canonical architecture is [forge-pipeline-architecture.md](../forge-pipeline-architecture.md) v2.2."

### 9. Map greenfield flow to anchor 5 stages

Lines 291–354 describe a greenfield flow using different stage names than anchor §4. Add a subsection **"Mapping to anchor v2.2 pipeline stages"** with an explicit table:

| This doc's flow block | Anchor v2.2 §4 stage |
|-----------------------|-----------------------|
| Product docs | Stage 1 — Specification Review |
| Architecture | Stage 2 — Architecture Review |
| Feature spec | (part of Stage 3) |
| Feature plan | Stage 3 — Feature Planning |
| AutoBuild | Stage 4 — AutoBuild Execution |
| Verify + PR | Stage 5 — PR Creation |

If any block has no clean mapping, call it out and raise a follow-up correction task against the anchor.

### 10. Name the state machine states

Lines 215–217 mention "state machine between checkpoints" without defining states. Add a subsection listing the anchor §6 states: `IDLE → PREPARING → RUNNING → FINALISING → COMPLETE/FAILED`, plus `PAUSED` for 🟡 gates and `INTERRUPTED` for crash recovery. Reference anchor §6 as the authoritative state machine definition.

### 11. Add Jarvis-as-upstream-trigger subsection

Insert a new subsection (after "What Stays the Same from March" or near the end, before "Do-Not-Reopen Decisions"). Content: 1 paragraph summarising ADR-SP-014 Pattern A + cross-reference to anchor §5.0. Explicit: this doc describes the *runtime* behaviour once a build is in flight; the *trigger path* (Jarvis or CLI publishing `pipeline.build-queued`) lives in the anchor.

### 12. Decide fate of `FeaturePlannedPayload` / `FeatureReadyForBuildPayload`

Lines 453–459 use these in the event table, but anchor v2.2 is silent on them and `nats-core` still exports them. Three options:

1. **Retire both** — delete from this doc, mark `@deprecated` in nats-core (coordinate with TASK-NCFA-001 in nats-core)
2. **Promote both to anchor** — raise a follow-up correction task to add them to anchor §7
3. **Retire `FeaturePlannedPayload`, keep `FeatureReadyForBuildPayload`** if DDR-001 still justifies it as an intermediate event

Recommendation: option 1 (retire) unless the orchestrator-refresh's flow genuinely depends on `FeatureReadyForBuildPayload` as a separate event from `StageCompletePayload` for Stage 3. Document the decision inline.

## Acceptance criteria

- [ ] Opening paragraph re-framed; "checkpoint manager" language removed or subordinated
- [ ] Stage-mapping subsection exists with the table
- [ ] State machine states named explicitly with anchor §6 reference
- [ ] Jarvis-as-upstream-trigger subsection exists
- [ ] `FeaturePlannedPayload` / `FeatureReadyForBuildPayload` decision recorded
- [ ] Grep for `agents.commands.` returns 0 hits
- [ ] Doc header references anchor v2.2 as canonical

## Out of scope

- Rewriting the checkpoint protocol content — it is the doc's strength and is not drifted
- Anchor edits (TASK-FVD1)
- nats-core payload deprecations — those are TASK-NCFA-001 in nats-core, coordinate via cross-reference only
