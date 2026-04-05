# Task: Add DA15 (AgentConfig) to the build plan

## File to edit
`docs/research/ideas/architect-agent-finproxy-build-plan.md`

## Change 1: Add DA15 to the decisions table

In the "Key Design Decisions Made" table, add a new row after the DA14 row:

| DA15 | AgentManifest + AgentConfig separation | Manifest = public capabilities (what the agent does), published to fleet. Config = private runtime settings (how the agent runs), local only. Both Pydantic models in nats-core so all agents share the same schema. Prevents config drift across 6+ agents. |

## Change 2: Add AgentConfig note to task B1

In the "B1. nats-core library" section under "PHASE B — Concurrent Build", find the bullet list of key files which ends with:

```
- Key files: `src/nats_core/events/fleet.py`, `src/nats_core/manifest.py`, `src/nats_core/topics.py`, `src/nats_core/client.py`
```

Add this line immediately after it:

```
- Also delivers: `AgentConfig` schema in `src/nats_core/config.py` — shared runtime config model (ModelConfig, GraphitiConfig, NATSConfig, API keys, timeouts). Companion to AgentManifest. Uses pydantic-settings for environment variable override with `AGENT_` prefix.
```

## Change 3: Update nats-core file reference

In the "File Reference — What Lives Where" section, find the nats-core source tree which currently reads:

```
└── src/nats_core/
    ├── manifest.py                             ← NEW: AgentManifest, ToolCapability, IntentCapability
    ├── events/fleet.py                         ← NEW: registration, heartbeat, deregistration
    └── topics.py                               ← UPDATE: add Topics.Agents.Tools
```

Replace it with:

```
└── src/nats_core/
    ├── manifest.py                             ← NEW: AgentManifest, ToolCapability, IntentCapability
    ├── config.py                               ← NEW: AgentConfig, ModelConfig, GraphitiConfig, NATSConfig
    ├── events/fleet.py                         ← NEW: registration, heartbeat, deregistration
    └── topics.py                               ← UPDATE: add Topics.Agents.Tools
```

## Commit message
"Add DA15: AgentConfig companion schema to build plan"
