---
id: TASK-FVD1
title: Apply v2.2 anchor additions to forge-pipeline-architecture.md
status: completed
completed: 2026-04-16T00:00:00Z
task_type: documentation
parent_review: TASK-REV-A1F2
feature_id: FEAT-FVDA
priority: high
tags: [documentation, architecture, anchor, v2.2, jarvis, dual-role, nats]
complexity: 5
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Apply v2.2 anchor additions to forge-pipeline-architecture.md

## Context

TASK-REV-A1F2 produced [docs/research/forge-build-plan-alignment-review.md](../../../docs/research/forge-build-plan-alignment-review.md), which identified that the v2.1 anchor is internally sound but silent on two things Rich has committed to (Jarvis as human-facing trigger, specialist-agent dual-role deployment) and diverges from the installed `nats-infrastructure` reality on two others (stream retention, topic naming). Four draft ADRs (SP-014..017) are already present in §9 of the anchor with status **Proposed**. This task lands the supporting body-text changes and promotes the ADRs to **Accepted** once Rich signs off.

## Scope

### 1. Add §5.0 Build Request Sources

Insert a new subsection at the top of §5 "Build Queue", before "Trigger Mechanism". Use the text in the alignment review §3 ("Cross-cutting: Jarvis → Forge integration gap") verbatim. The subsection must:

- List the three supported trigger sources (CLI, Jarvis, future notification adapters)
- State that Forge does not distinguish sources at the consumer level
- Describe Forge's `fleet.register` registration as the discovery mechanism for Jarvis
- Cross-reference ADR-SP-014

### 2. Add §3.1 Specialist Agent Deployment Model

Insert a new subsection after §3 "Repository Architecture". Use the text from the alignment review §4 ("Cross-cutting: Specialist-agent dual-role wiring"). The subsection must:

- Document the `{role_id}-agent` naming (`product-owner-agent`, `architect-agent`)
- Note the `SPECIALIST_AGENT_ID` env-var override
- Describe the fleet.register + `agents.command.{agent_id}` + `agents.result.{agent_id}` topology
- State the Forge-compatible result payload shape (`role_id, coach_score, criterion_breakdown, detection_findings, role_output`)
- Cross-reference ADR-SP-015

### 3. Stream retention + new streams (§3 "Key streams")

Replace the existing three-line stream list with the reconciled set per ADR-SP-017:

- `PIPELINE` — `pipeline.*` events, **7-day retention**
- `AGENTS` — `agents.*` events, 7-day retention
- `FLEET` — `fleet.*` agent registration and heartbeat events (promoted from nats-infrastructure)
- `JARVIS` — `jarvis.*` session, dispatch, and notification events (promoted from nats-infrastructure)
- `NOTIFICATIONS` — `notifications.*` outbound adapter events (promoted from nats-infrastructure)
- `SYSTEM` — `system.*` health and config, **1-hour retention**

`FINPROXY` remains out of the anchor (tenant-specific).

### 4. Topic naming singular (§7)

Replace every occurrence of `agents.commands.{agent_id}` with `agents.command.{agent_id}` and `agents.results.{agent_id}` with `agents.result.{agent_id}` in §7 "NATS Topic Hierarchy" per ADR-SP-016. Update the `Topics.Agents` class block:

```python
class Agents:
    STATUS = "agents.status.{agent_id}"
    COMMAND = "agents.command.{agent_id}"          # was COMMANDS
    RESULT = "agents.result.{agent_id}"            # was RESULTS
    COMMAND_BROADCAST = "agents.command.broadcast" # was COMMANDS_BROADCAST
    STATUS_ALL = "agents.status.>"
```

Also update §8 "Data Flows" step 2 (specialist-agent call).

### 5. `BuildQueuedPayload` field additions (§7)

Update `BuildQueuedPayload` to match the design in [alignment review Appendix C](../../../docs/research/forge-build-plan-alignment-review.md#appendix-c--buildqueuedpayload-full-design-jarvis-aware). At minimum add:

- `triggered_by: Literal["cli", "jarvis", "forge-internal", "notification-adapter"]` (replaces `triggered_by: str`)
- `originating_adapter: Optional[Literal[...]]` with the six adapter values
- `originating_user: Optional[str]`
- `correlation_id: str`
- `parent_request_id: Optional[str]`

Keep the full Pydantic model in Appendix C as the implementation spec — cite it rather than duplicating the code in the anchor.

### 6. Promote ADRs SP-014..017 to Accepted

If Rich has signed off on the alignment review before this task runs, change the **Status** line on each of the four ADRs in §9 from `Proposed (added via TASK-REV-A1F2 alignment review — pending acceptance)` to `Accepted`. If Rich has revisions, update the ADR bodies in place before accepting.

### 7. Version bump

- Header: `**Version:** 2.1` → `**Version:** 2.2`
- Header: `**Date:** 15 April 2026` → `**Date:** <date of landing>`
- Add to the header block: `**Supersedes:** v2.1 (15 April 2026)` and `**Alignment review:** TASK-REV-A1F2 / docs/research/forge-build-plan-alignment-review.md`
- Update §"What Changed from February 2026" table header to "What Changed from v2.1 → v2.2" for the new-row additions (optional cosmetic)

## Acceptance criteria

- [ ] §5.0 "Build Request Sources" exists and cites ADR-SP-014
- [ ] §3.1 "Specialist Agent Deployment Model" exists and cites ADR-SP-015
- [ ] §3 "Key streams" lists the six streams with corrected retentions
- [ ] Every `agents.commands.` reference is now `agents.command.` (grep returns 0 hits in the anchor for the plural form, except in the "what changed" note)
- [ ] `BuildQueuedPayload` in §7 includes `triggered_by`, `originating_adapter`, `correlation_id`, `parent_request_id`
- [ ] ADRs SP-014..017 have been either promoted to Accepted or updated in place per Rich's feedback
- [ ] Version header shows v2.2
- [ ] No unrelated sections are edited
- [ ] The alignment review itself is not modified

## Out of scope

- Editing `forge-build-plan.md`, `forge-pipeline-orchestrator-refresh.md`, or `fleet-master-index.md` (covered by TASK-FVD2/3/4)
- Any code changes in sibling repos (tracked separately)
- Resolving the `pipeline-state` NATS KV bucket decision — that is TASK-PSKV-001 in nats-infrastructure
