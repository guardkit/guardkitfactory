# Data Model — Discovery (capability resolution)

> **Container:** Domain Core (`forge.discovery`) + NATS Adapter (`forge.adapters.nats.fleet_watcher`)
> **Owners:** `forge.discovery` (cache + resolution logic, pure domain), `forge.adapters.nats` (KV + fleet subscription)
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-016](../../architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md)

---

## 1. Purpose

Discovery is the live capability layer. It keeps a 30-second TTL cache of the fleet's `AgentManifest`s (read from NATS KV `agent-registry`), invalidated by live `fleet.*` events, and exposes resolution to the reasoning-model-facing `dispatch_by_capability` tool.

Every resolution produces a `CapabilityResolution` entity that lands in `forge_pipeline_history` — over time this becomes a prior: *"when two agents advertised the same capability, prefer the one that passed last time"*.

---

## 2. Entities

### `AgentManifest` (imported from `nats-core`)

Full schema lives in [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md). Forge's discovery layer reads:

- `agent_id` — identifier used in `agents.command.{agent_id}` dispatch.
- `tools: list[ToolCapability]` — precise name-level match.
- `intents: list[IntentCapability]` — pattern + confidence for fallback match.
- `trust_tier: core | specialist | extension` — tie-break priority.
- `status: ready | starting | degraded` — degraded excluded from primary resolution.
- `max_concurrent` + latest heartbeat's `queue_depth` + `active_tasks` — capacity signal.

### `CapabilityResolution`

Output of `forge.discovery.resolve()`. One per dispatch attempt.

```python
class CapabilityResolution(BaseModel):
    resolution_id: str                                      # UUID
    build_id: str
    stage_label: str

    requested_tool: str
    requested_intent: str | None

    matched_agent_id: str | None                            # None → degraded mode
    match_source: Literal["tool_exact", "intent_pattern", "unresolved"]
    competing_agents: list[str]                             # Other agents that also matched

    chosen_trust_tier: Literal["core", "specialist", "extension"] | None
    chosen_confidence: float | None                         # IntentCapability.confidence when match_source=intent_pattern
    chosen_queue_depth: int | None                          # From heartbeat at resolution time

    resolved_at: datetime
    outcome_correlated: bool = False                        # True once the downstream ResultPayload is linked back
```

### `DiscoveryCacheEntry`

In-memory only; never persisted.

```python
class DiscoveryCacheEntry(BaseModel):
    manifest: AgentManifest
    last_heartbeat_at: datetime
    last_heartbeat_status: Literal["ready", "busy", "degraded", "draining"]
    last_queue_depth: int
    last_active_tasks: int
    cached_at: datetime                                     # For TTL check
```

The cache is a `dict[str, DiscoveryCacheEntry]` keyed by `agent_id` and guarded by an asyncio lock for concurrent mutation from the fleet watcher callback.

---

## 3. Resolution Algorithm

```python
async def resolve(
    tool_name: str,
    intent_pattern: str | None = None,
    min_confidence: float = 0.7,
) -> tuple[str | None, CapabilityResolution]:
    snapshot = await ensure_cache_fresh()                   # re-read KV if cache_age > 30s

    # 1. Exact tool-name match
    candidates = [
        e for e in snapshot.values()
        if e.last_heartbeat_status != "degraded"
        and any(t.name == tool_name for t in e.manifest.tools)
    ]
    match_source = "tool_exact"

    # 2. Intent fallback
    if not candidates and intent_pattern:
        candidates = [
            e for e in snapshot.values()
            if e.last_heartbeat_status != "degraded"
            and any(
                _pattern_matches(i.pattern, intent_pattern) and i.confidence >= min_confidence
                for i in e.manifest.intents
            )
        ]
        match_source = "intent_pattern"

    # 3. Unresolved
    if not candidates:
        return None, CapabilityResolution(
            ..., matched_agent_id=None, match_source="unresolved",
        )

    # 4. Tie-break: trust_tier (core > specialist > extension), then confidence, then queue_depth
    candidates.sort(
        key=lambda e: (
            _trust_tier_rank(e.manifest.trust_tier),         # lower = higher priority
            -_best_confidence(e.manifest, tool_name, intent_pattern),
            e.last_queue_depth,
        )
    )
    chosen = candidates[0]

    return chosen.manifest.agent_id, CapabilityResolution(
        ...,
        matched_agent_id=chosen.manifest.agent_id,
        match_source=match_source,
        competing_agents=[c.manifest.agent_id for c in candidates[1:]],
        chosen_trust_tier=chosen.manifest.trust_tier,
        chosen_confidence=_best_confidence(chosen.manifest, tool_name, intent_pattern),
        chosen_queue_depth=chosen.last_queue_depth,
        resolved_at=datetime.now(UTC),
    )
```

**Trust-tier ranking:** `core=0, specialist=1, extension=2`. Core beats specialist beats extension.

---

## 4. Cache Invalidation

Registered via `nats_client.watch_fleet(callback=_on_fleet_event)`:

| Event | Cache action |
|---|---|
| `fleet.register` (new or version-bumped manifest) | Upsert entry: `manifest`, `last_heartbeat_status="ready"`, `cached_at=now` |
| `fleet.deregister` | Delete entry |
| `fleet.heartbeat.{agent_id}` with status change | Update `last_heartbeat_status`, `last_queue_depth`, `last_active_tasks`, `last_heartbeat_at` |
| `fleet.heartbeat.{agent_id}` routine | Update `last_heartbeat_at` only; TTL timer for staleness starts from here |
| TTL expiry (30s since `cached_at`, no heartbeat in last 90s) | Mark entry `last_heartbeat_status="degraded"`; next `ensure_cache_fresh()` re-reads KV |

---

## 5. Write-back Correlation

Once the downstream `ResultPayload` returns, `forge.discovery.correlate_outcome(resolution_id, result)`:

- Writes a Graphiti relationship: `(CapabilityResolution) -[HAD_OUTCOME]-> (GateDecision or StageLogEntry)`.
- Updates `outcome_correlated=True`.
- If the outcome was a Rich override on a flagged gate, Graphiti also records `(CapabilityResolution) -[OVERRIDDEN_BY_RICH]-> (OverrideEvent)` — the raw input for `forge.learning`.

---

## 6. Relationships

```
Build (1) ─── (many) CapabilityResolution                   # One per fleet-dispatch stage
CapabilityResolution (1) ─── (1) AgentManifest              # Snapshot reference — matched_agent_id + manifest version
CapabilityResolution (1) ─── (0..1) GateDecision            # Linked after outcome correlation
CapabilityResolution (1) ─── (0..1) StageLogEntry           # Direct link via stage_label + build_id
DiscoveryCacheEntry (1) ─── (1) AgentManifest               # In-memory only
```

---

## 7. Invariants

| Invariant | Enforcement |
|---|---|
| `matched_agent_id is None` iff `match_source == "unresolved"` | Pydantic validator |
| Agents with `status="degraded"` excluded from primary resolution | `resolve()` filter |
| Cache age ≤ 30s OR stale-heartbeat > 90s (per ADR-ARCH-017) | `ensure_cache_fresh()` guard |
| `competing_agents` list excludes the chosen agent | `resolve()` slicing |
| `CapabilityResolution` persisted before downstream dispatch is published | `dispatch_by_capability` ordering — write-before-send |
| `outcome_correlated` cannot regress from True to False | Graphiti append-only — never update in place; new entity supersedes if needed |

---

## 8. Related

- Fleet lifecycle: [API-nats-fleet-lifecycle.md](../contracts/API-nats-fleet-lifecycle.md)
- Dispatch contract: [API-nats-agent-dispatch.md](../contracts/API-nats-agent-dispatch.md)
- Graphiti entity schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
