---
id: TASK-E90D
title: Update fleet master index with D22 AgentConfig standardisation
status: completed
created: 2026-04-05T00:00:00Z
updated: 2026-04-05T00:00:00Z
completed: 2026-04-05T00:00:00Z
completed_location: tasks/completed/TASK-E90D/
priority: normal
tags: [documentation, fleet-index, decisions]
complexity: 2
task_type: feature
previous_state: in_review
state_transition_reason: "All acceptance criteria met, changes verified"
organized_files:
  - TASK-E90D.md
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-05T00:00:00Z
---

# Task: Update fleet master index with D22 AgentConfig standardisation

## Description
Adds D22 (AgentConfig standardisation) to the fleet-wide resolved decisions table in `docs/research/ideas/fleet-master-index.md` and updates the nats-core repository map entry to reflect the AgentConfig addition.

## Source
Task specification: `docs/research/ideas/TASK-update-fleet-index-d22.md`

## Changes Required

### Change 1: Add D22 to Resolved Decisions table
Add the following row to the "Resolved Decisions (Fleet-Wide)" table after the last existing entry:

| D22 | AgentConfig standardisation | Shared Pydantic model in nats-core for runtime config (model endpoints, Graphiti connection, NATS URL, API keys, timeouts). Companion to AgentManifest — manifest is public (what), config is private (how). All agents import from nats-core. Uses pydantic-settings with AGENT_ env prefix. |

### Change 2: Update nats-core entry in Repository Map
Update the nats-core contracts description to reference "AgentManifest + AgentConfig schemas" instead of just AgentManifest.

## Acceptance Criteria
- [x] D22 row added to Resolved Decisions table in correct position
- [x] nats-core repository map entry updated to mention AgentConfig
- [x] No existing entries modified or corrupted

## Commit Message
"Add D22: AgentConfig standardisation to fleet decisions"

## Implementation Notes
- Check current state of fleet-master-index.md to determine where D22 should be inserted
- If D14-D21 already exist, D22 goes after D21; otherwise after D13

## Test Execution Log
- 2026-04-05: Micro-task mode. Both changes applied and verified via file read.
  - D22 inserted after D21 at line 229
  - nats-core contracts description updated at line 53
  - All existing entries intact
