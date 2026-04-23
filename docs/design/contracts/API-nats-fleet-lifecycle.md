# API Contract — NATS Fleet Lifecycle (registration + discovery)

> **Type:** Bidirectional — Forge publishes its own registration/heartbeat; subscribes to fleet changes; reads KV registry
> **Transport:** NATS pub/sub on `FLEET` stream + NATS KV bucket `agent-registry`
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md), [ADR-ARCH-016](../../architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md)
> **External contract:** [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md) (nats-core; source of truth for schemas)

---

## 1. Purpose

Forge participates in the fleet CAN-bus:

1. **As an agent** — registers its own `AgentManifest` on startup, heartbeats periodically, deregisters on graceful shutdown. This makes Forge discoverable to Jarvis (control-plane commands) and operators (dashboards).
2. **As a consumer** — subscribes to `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>` for live cache invalidation, and reads `agent-registry` KV for capability resolution.

---

## 2. Forge Self-Registration

### 2.1 Manifest

```python
# forge.fleet.manifest
from nats_core.manifest import AgentManifest, IntentCapability, ToolCapability

FORGE_MANIFEST = AgentManifest(
    agent_id="forge",
    name="Forge",
    version="0.1.0",
    template="deepagents-pipeline-orchestrator",
    trust_tier="core",
    status="ready",
    max_concurrent=1,                       # ADR-SP-012 — sequential builds
    intents=[
        IntentCapability(
            pattern="build.*",
            signals=["build", "develop", "implement", "create", "make", "ship"],
            confidence=0.90,
            description="Run a feature through the software factory pipeline to PR",
        ),
        IntentCapability(
            pattern="pipeline.*",
            signals=["pipeline", "stages", "progress", "status", "deploy"],
            confidence=0.85,
            description="Operate the build pipeline — queue, inspect, cancel, resume",
        ),
        IntentCapability(
            pattern="feature.*",
            signals=["feature", "add feature", "new capability", "requirement"],
            confidence=0.80,
            description="Add a new feature to an existing project",
        ),
    ],
    tools=[
        ToolCapability(
            name="forge_greenfield",
            description="Start a full greenfield pipeline run. Returns pipeline_id immediately (fire-and-forget). Poll forge_status, cancel with forge_cancel.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "feature_yaml_path": {"type": "string"},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo", "feature_yaml_path"],
            },
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
            requires_approval=False,
        ),
        ToolCapability(
            name="forge_feature",
            description="Add a feature to an existing project. Returns pipeline_id immediately.",
            parameters={"type": "object", "properties": {
                "repo": {"type": "string"}, "feature_id": {"type": "string"},
            }, "required": ["repo", "feature_id"]},
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
        ),
        ToolCapability(
            name="forge_review_fix",
            description="Run a review-and-fix cycle on existing code. Returns pipeline_id immediately.",
            parameters={"type": "object", "properties": {
                "repo": {"type": "string"}, "subject": {"type": "string"},
            }, "required": ["repo", "subject"]},
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
        ),
        ToolCapability(
            name="forge_status",
            description="Read current pipeline status (all running/paused builds, or a specific pipeline_id).",
            parameters={"type": "object", "properties": {
                "pipeline_id": {"type": "string"},
            }},
            returns="list[BuildStatus]",
            risk_level="read_only",
        ),
        ToolCapability(
            name="forge_cancel",
            description="Cancel an in-flight pipeline run.",
            parameters={"type": "object", "properties": {
                "pipeline_id": {"type": "string"},
                "reason": {"type": "string"},
            }, "required": ["pipeline_id"]},
            returns="{cancelled: bool, at: datetime}",
            risk_level="mutating",
        ),
    ],
    required_permissions=[
        "graphiti:read", "graphiti:write",
        "filesystem:read", "filesystem:write",
        "shell:execute",
        "nats:publish", "nats:subscribe",
        "network:github.com",
    ],
)
```

### 2.2 Registration call

```python
# forge.fleet.register_on_boot()
await nats_client.register_agent(FORGE_MANIFEST)
# nats-core internals:
#   1. Publish MessageEnvelope(event_type=AGENT_REGISTER, payload=manifest.model_dump())
#      to fleet.register
#   2. Put manifest.model_dump() into NATS KV bucket agent-registry, key=agent_id
```

Registration is idempotent — re-registering overwrites the KV entry (version-bumped manifest supersedes older).

### 2.3 Heartbeat

Every `forge.yaml.fleet.heartbeat_interval_seconds` (default 30):

```python
await nats_client.heartbeat(AgentHeartbeatPayload(
    agent_id="forge",
    status=current_status,                           # "ready" | "busy" | "degraded" | "draining"
    queue_depth=jetstream_pending_count,             # From JetStream consumer info
    active_tasks=1 if build_in_flight else 0,        # max_concurrent=1 so this is 0 or 1
    uptime_seconds=...,
    last_task_completed_at=...,
    active_workflow_states={build_id: lifecycle_state} if build_in_flight else {},
))
# → publishes to fleet.heartbeat.forge
```

### 2.4 Deregistration

On graceful shutdown (SIGTERM handler):

```python
await nats_client.deregister_agent("forge", reason="shutdown")
# → publishes AgentDeregistrationPayload to fleet.deregister + removes KV entry
```

On crash, no deregistration is sent; Jarvis detects via missed heartbeats (default 90s timeout).

---

## 3. Forge as Consumer — Live Fleet Watch

### 3.1 Subscriptions

```python
# forge.adapters.nats.fleet_watcher
await nats_client.watch_fleet(callback=on_fleet_change)
# nats-core internals subscribe to:
#   fleet.register               → AgentRegistrationPayload (uses AgentManifest directly per nats-core DDR-002)
#   fleet.deregister             → AgentDeregistrationPayload
#   fleet.heartbeat.>            → AgentHeartbeatPayload per agent
```

### 3.2 Cache invalidation rules

`forge.discovery` owns a 30-second TTL cache of `agent-registry` KV. Events invalidate as follows:

| Event | Cache action |
|---|---|
| `fleet.register` (agent manifest appears/changes) | Upsert cache entry for `agent_id`; bump TTL |
| `fleet.deregister` | Remove `agent_id` from cache |
| `fleet.heartbeat.{agent_id}` with status change (`ready`↔`busy`↔`degraded`↔`draining`) | Update cache `status` + `queue_depth` only |
| `fleet.heartbeat.{agent_id}` routine (no status change) | Refresh last-seen timestamp only; do not re-read KV |
| Missed heartbeat > `forge.yaml.fleet.stale_heartbeat_seconds` (default 90) | Mark cache entry `status="degraded"`; subsequent `resolve()` excludes from primary selection |

### 3.3 KV reads

On cache miss or manual invalidation:

```python
registry_snapshot: dict[str, AgentManifest] = await nats_client.get_fleet_registry()
# Returns a dict of all registered agents from the agent-registry KV bucket.
```

---

## 4. Resolution Read Path

`forge.discovery.resolve(tool_name, intent_pattern=None)`:

1. If cache age > 30s, query `nats_client.find_by_tool(tool_name)` via `NATSKVManifestRegistry` → returns `list[AgentManifest]` matching the tool name.
2. If empty and `intent_pattern` is set, query `nats_client.find_by_intent(intent_pattern, min_confidence=0.7)`.
3. Filter out `status="degraded"` (excluded from primary resolution — per domain-model.md).
4. Tie-break (see [API-nats-agent-dispatch.md §2](API-nats-agent-dispatch.md#2-resolution)).
5. Return `agent_id` or `None`.

Every resolution writes a `CapabilityResolution` entity to Graphiti `forge_pipeline_history` for future priors (see [DM-discovery.md](../models/DM-discovery.md)).

---

## 5. Topic Summary

| Direction | Template | Payload | Published / Consumed by |
|---|---|---|---|
| Publish | `fleet.register` | `AgentManifest` (full) | Forge on boot |
| Publish | `fleet.deregister` | `AgentDeregistrationPayload` | Forge on graceful shutdown |
| Publish | `fleet.heartbeat.forge` | `AgentHeartbeatPayload` | Forge every 30s |
| Subscribe | `fleet.register` | `AgentManifest` | `forge.discovery` cache invalidation |
| Subscribe | `fleet.deregister` | `AgentDeregistrationPayload` | `forge.discovery` cache eviction |
| Subscribe | `fleet.heartbeat.>` | `AgentHeartbeatPayload` | `forge.discovery` status / queue-depth refresh |
| KV read | `agent-registry` bucket | full manifests | `forge.discovery` cache refill |

---

## 6. Related

- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Data model: [DM-discovery.md](../models/DM-discovery.md)
- nats-core schemas: [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md)
