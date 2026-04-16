# Task: Add D22 (AgentConfig standardisation) to fleet master index — COMPLETED

> **Status:** COMPLETED — D22 already present in fleet-master-index.md (line 605). Executed inline as part of TASK-FVD4 (16 April 2026).

## File to edit
`docs/research/ideas/fleet-master-index.md`

## Change 1: Add D22 to the Resolved Decisions table

In the "Resolved Decisions (Fleet-Wide)" table, find the last row (currently D13 or later if the fleet master index update task has already run). Add this new row at the end of the table:

| D22 | AgentConfig standardisation | Shared Pydantic model in nats-core for runtime config (model endpoints, Graphiti connection, NATS URL, API keys, timeouts). Companion to AgentManifest — manifest is public (what), config is private (how). All agents import from nats-core. Uses pydantic-settings with AGENT_ env prefix. |

Note: If the previous fleet master index update task has already run, the table will have D14 through D21 already. D22 goes after D21. If it hasn't run yet, add D22 after D13 and it will be reordered when the other task runs.

## Change 2: Update nats-core entry in the Repository Map

Find the nats-core entry in the Repository Map. If it has already been updated by the previous fleet master index task, it will have a contracts directory listed. Add `config.py` to the description comment. If it still shows the original format, update it to:

```
├── nats-core                 ← Shared contract layer (pip-installable library)
│   └── docs/design/
│       ├── contracts/
│       │   └── agent-manifest-contract.md        ← AgentManifest + AgentConfig schemas
│       ├── specs/
│       │   └── nats-core-system-spec.md          ← 6 features, BDD acceptance criteria
│       └── decisions/
│           ├── ADR-001-nats-as-event-bus.md
│           ├── ADR-002-schema-versioning.md
│           ├── ADR-003-nats-py-vs-faststream.md
│           └── ADR-004-dynamic-fleet-registration.md
```

The key change is the contracts line: it should say "AgentManifest + AgentConfig schemas" (not just "AgentManifest, ToolCapability, IntentCapability schemas").

## Commit message
"Add D22: AgentConfig standardisation to fleet decisions"
