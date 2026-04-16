---
id: TASK-FVD4
title: Correct fleet-master-index.md and execute pending d22 repo-inventory task
status: completed
completed: 2026-04-16T00:00:00Z
task_type: documentation
parent_review: TASK-REV-A1F2
feature_id: FEAT-FVDA
priority: high
tags: [documentation, fleet-master-index, v2.2, repo-inventory]
complexity: 4
wave: 2
implementation_mode: task-work
dependencies: [TASK-FVD1]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Correct fleet-master-index.md and execute pending d22 repo-inventory task

## Context

`docs/research/ideas/fleet-master-index.md` v2 (12 April 2026) describes Jarvis only as a specialist-agent dispatcher, is silent on the CLI build trigger, has `max_concurrent: 3` for Forge (contradicts ADR-SP-012), and lists stale repo inventory per the already-open `docs/research/ideas/TASK-update-fleet-index-d22.md`. This task applies corrections 22–25 from the alignment review and executes d22 inline to collapse two sources of truth into one.

## Scope

### 22. Expand Jarvis description (line 10 + Jarvis section)

Current: "intent router (Jarvis) dispatching requests to specialist agents".

Update to: "intent router (Jarvis) dispatching requests to specialist agents **and to the Forge for build requests**. Jarvis discovers Forge via the `fleet.register` + `agent-registry` KV plumbing and publishes `pipeline.build-queued` per ADR-SP-014 Pattern A."

Expand the Jarvis subsection (around lines 9–12 and 259–264) to include:

- Adapter list (voice/Reachy Mini, Telegram, Slack, dashboard, CLI-wrapper) — already partly there
- Forge discovery mechanism (CAN-bus via `fleet.register`)
- Forge trigger path (publishes `BuildQueuedPayload` with `triggered_by="jarvis"`)

### 23. Document the build trigger mechanism (around lines 146–148)

Current text describes `feature_ready_for_build` as the Forge's *output*. Add explicit text about the *input*:

> Builds enter the Forge pipeline via JetStream `pipeline.build-queued.{feature_id}` messages. The three supported trigger sources are:
>
> 1. **CLI** — `forge queue FEAT-XXX` publishes directly
> 2. **Jarvis** — per ADR-SP-014, after intent classification and CAN-bus discovery
> 3. **Future notification adapters** — out of Phase 4 scope
>
> Forge consumes the same topic regardless of source. See anchor v2.2 §5.0 "Build Request Sources".

### 24. Forge Agent Manifest corrections (lines 472–535)

- `max_concurrent: 3` → **`max_concurrent: 1`** (ADR-SP-012)
- Verify `nats_topic: agents.command.forge` (singular, correct)
- Add a sentence describing the JetStream pull consumer on `pipeline.build-queued.>` — this is how Forge actually receives work, the `agents.command.forge` subject is for fleet-discovery-only commands (e.g. a future "pause all builds" broadcast), not build requests

### 25. Execute TASK-update-fleet-index-d22 inline (repo inventory)

Open `docs/research/ideas/TASK-update-fleet-index-d22.md` and apply its changes to `fleet-master-index.md` directly. Specifically:

- Rename `architect-agent` → `specialist-agent` across the repo map, component tables, and any cross-references
- Mark `ideation-agent` as archived (absorbed into specialist-agent)
- Mark `product-owner-agent` as archived (absorbed into specialist-agent)
- Mark `architect-agent-mcp` as superseded
- Add `lpa-platform` (exists per context manifest in `forge-build-plan.md:73`)
- Update the Agent Fleet Summary table (lines 333–349 area) to reflect the post-consolidation state

After landing, mark `TASK-update-fleet-index-d22.md` as completed (or delete it) with a commit message pointing at this task as the executor.

## Acceptance criteria

- [ ] Jarvis description expanded to include Forge-trigger role
- [ ] Build trigger mechanism section exists with explicit CLI + Jarvis path
- [ ] Forge manifest shows `max_concurrent: 1`
- [ ] Repo inventory matches current reality (specialist-agent, not architect-agent; ideation-agent archived; product-owner-agent archived; lpa-platform added)
- [ ] `TASK-update-fleet-index-d22.md` is marked completed or deleted, with reference to this task
- [ ] Grep for `agents.commands.` returns 0 hits
- [ ] Document header or change log references anchor v2.2

## Out of scope

- Anchor edits (TASK-FVD1)
- Adding new ADRs beyond those referenced from the anchor
- Rewriting decision entries D1–D38 — only updating them where they contradict v2.2
