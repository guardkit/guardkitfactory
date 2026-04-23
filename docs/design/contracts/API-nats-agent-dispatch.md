# API Contract — NATS Agent Dispatch (Request/Reply)

> **Type:** Outbound request/reply to fleet specialist agents
> **Transport:** NATS core request/reply (not JetStream — replies are ephemeral, correlation-keyed)
> **Stream:** `AGENTS` (for observability/audit; actual reply routing uses core NATS inbox pattern)
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md), [ADR-SP-017](../../research/forge-pipeline-architecture.md)
> **Parity rule:** LES1 §2 — PubAck ≠ success; the real reply arrives separately on the reply subject.

---

## 1. Purpose

Forge delegates domain judgment to fleet specialist agents (Product Owner, Architect, QA, UX, Ideation — present and future) via capability-driven dispatch. This contract specifies:

- **How Forge selects** an agent for a capability (via `forge.discovery` → `NATSKVManifestRegistry`).
- **How Forge publishes** the command (`agents.command.{agent_id}`).
- **How the reply is correlated** (LES1 parity rule: reply on `agents.result.{agent_id}.{correlation_id}`, not on the publish ack).
- **How timeouts and degraded mode** are handled.

This contract governs the single generic `@tool` `dispatch_by_capability` — there are **no per-role dispatch tools** (ADR-ARCH-015).

---

## 2. Resolution

`forge.discovery.resolve(tool_name, intent_pattern=None, min_confidence=0.7)` returns the target `agent_id` using:

1. **Exact tool match** — any agent whose `AgentManifest.tools` contains a `ToolCapability.name == tool_name`.
2. **Intent-pattern match** — if no tool match and `intent_pattern` is provided, any agent whose `AgentManifest.intents` contains a matching `IntentCapability.pattern` with `confidence ≥ min_confidence`.
3. **Tie-break** — highest `trust_tier` (`core > specialist > extension`), then highest `confidence`, then lowest `AgentHeartbeatPayload.queue_depth`.
4. **Unresolved** — returns `None`; caller falls back to degraded mode (see §6).

Registry access is cached for 30 seconds; cache invalidated live by `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>` subscription (ADR-ARCH-017, see [API-nats-fleet-lifecycle.md](API-nats-fleet-lifecycle.md)).

---

## 3. Request Publish

### 3.1 Subject

| Template | Resolution example |
|---|---|
| `agents.command.{agent_id}` | `agents.command.product-owner-agent` |
| Project-scoped | `Topics.for_project("finproxy", "agents.command.architect-agent")` → `finproxy.agents.command.architect-agent` |

### 3.2 Request envelope

Reuses `nats-core.MessageEnvelope` with `event_type=EventType.COMMAND` and payload = `CommandPayload` (already in `nats-core`):

```python
class CommandPayload(BaseModel):
    request_id: str                        # UUID; matches reply subject suffix
    tool_name: str                         # e.g. "review_specification"
    params: dict[str, Any]                 # JSON-Schema-validated per ToolCapability.parameters
    async_mode: bool = False               # Matches ToolCapability.async_mode
    timeout_seconds: int = 600             # Forge-side timeout; not authoritative for the agent
```

**Envelope fields Forge sets:**

- `source_id = "forge"`
- `correlation_id` = the `request_id` (so the full call chain can be reconstructed from envelope threading)
- `project` = build's repo scope (from `BuildQueuedPayload`) or `None` for fleet-wide commands

### 3.3 Reply-subject contract (LES1 parity)

**Forge publishes with an explicit `reply_subject` set via NATS request/reply:**

```python
reply_subject = f"agents.result.{agent_id}.{request_id}"

# The specialist agent's NATS harness is expected to publish its reply to
# `reply_subject` (not to the generic agents.result.{agent_id} topic).
# Forge subscribes to the exact correlation-keyed subject before publishing.
sub = await nc.subscribe(reply_subject, max_msgs=1)
await nc.publish(
    subject=f"agents.command.{agent_id}",
    payload=envelope.model_dump_json().encode(),
    reply=reply_subject,
)

try:
    msg = await sub.next_msg(timeout=command_timeout_seconds)
finally:
    await sub.unsubscribe()
```

**Why per-correlation subjects, not `agents.result.{agent_id}`:**

Per LES1 §2 observation — `nats request` against `agents.>` returned PubAck in ~3ms and exited without waiting; the real reply arrived separately on `agents.result.<role>`. Operators silently read PubAck as success and the round-trip contract was broken for iterations. A correlation-keyed subject:

- Removes ambiguity ("which reply is mine?" when the agent serves concurrent requests).
- Prevents silent swallowing when JetStream AGENTS stream ack-intercepts the generic pattern.
- Makes every dispatch independently auditable.

### 3.4 `PubAck ≠ success` rule

The JetStream AGENTS stream intercepts `agents.>` for audit/observability and returns PubAck within ~3ms. Forge MUST NOT treat the PubAck as the specialist's answer. The dispatch is complete only when:

- A message is received on `reply_subject`, OR
- `command_timeout_seconds` elapses.

---

## 4. Reply

### 4.1 Reply envelope

Reuses `nats-core.MessageEnvelope` with `event_type=EventType.RESULT` and payload = `ResultPayload`:

```python
class ResultPayload(BaseModel):
    request_id: str                        # Echoes CommandPayload.request_id
    status: Literal["success", "error", "degraded", "timeout"]
    result: dict[str, Any]                 # Generic container — see §4.2
    coach_score: float | None = None       # Convention: specialist includes Coach output here
    criterion_breakdown: dict[str, float] | None = None
    detection_findings: list[dict[str, Any]] | None = None
    duration_secs: float
    error_message: str | None = None
```

### 4.2 Coach-score convention

Per the pipeline orchestrator refresh doc §"Forge Tool Inventory" Open Question 6, specialist agents **SHOULD** include Coach output in `result`:

```python
result = {
    "output": { ... },                              # tool-specific payload
    "coach_score": 0.78,
    "criterion_breakdown": {"fidelity": 0.8, ...},
    "detection_findings": [
        {"pattern": "PHANTOM", "severity": "high", "evidence": "..."},
    ],
}
```

Top-level fields on `ResultPayload` mirror these for convenience; either location is acceptable, with top-level preferred for new specialist versions. Forge reads top-level first, falls back to nested.

### 4.3 Gate input

The reasoning model feeds `(coach_score, criterion_breakdown, detection_findings, tool_name, retrieved_priors)` into `forge.gating.evaluate_gate()`. Output is a `GateDecision` (see [DM-gating.md](../models/DM-gating.md)).

---

## 5. Timeouts

| Knob | Source | Default | Notes |
|---|---|---|---|
| `CommandPayload.timeout_seconds` | Caller sets | `600` (10 min) | Advisory to the agent; not enforced remotely |
| Forge-side subscribe timeout | `forge.yaml.dispatch.default_timeout_seconds` | `900` (15 min; 50% headroom) | Hard cut-off; on breach → `status="timeout"` |
| Long-running async dispatch | Per-tool override if `ToolCapability.async_mode=True` | `ToolCapability.metadata.max_seconds` | Agent returns fast with `run_id`; Forge polls via `{tool_name}_status` |

**Timeout outcome.** On hard timeout Forge:

1. Writes `StageLogEntry(status="FAILED", gate_decision=HARD_STOP, details_json={"reason": "dispatch_timeout"})`.
2. Publishes `pipeline.stage-complete` with `status="FAILED"`.
3. Emits a `ResultPayload(status="timeout", …)` back into the reasoning loop so the model can decide next step (retry, degraded-mode fallback, or HARD_STOP the build).

---

## 6. Degraded Mode

If `forge.discovery.resolve(...)` returns `None`:

1. `ResultPayload(status="degraded", error_message="no agent registered for tool=X intent=Y")` is synthesised in-process.
2. The reasoning model sees the degraded result and decides:
   - **Fall back to GuardKit CLI** — e.g. no `architect-agent` → invoke `/system-arch` directly via `guardkit_*` tool.
   - **Skip the stage** — emit `StageCompletePayload(status="SKIPPED")` and continue.
   - **HARD_STOP** — if the capability is essential.
3. When a specialist is unavailable and an equivalent local tool runs, the resulting gate defaults to `FLAG_FOR_REVIEW` (no Coach score → no auto-approve — refresh doc §"Degraded Mode").

---

## 7. Telemetry

| Event | Subject | Purpose |
|---|---|---|
| Dispatch requested | `pipeline.stage-complete.{feature_id}` (emitted after reply) | End-to-end timing visible on `PIPELINE` stream |
| Capability resolution | written to Graphiti `forge_pipeline_history` via `forge.adapters.graphiti.write_capability_resolution()` | Future prior: "when two agents advertised the same capability, prefer the one that passed last time" |
| Dispatch failure / timeout | `pipeline.build-failed.{feature_id}` only if build-terminal; otherwise `StageLogEntry` only | Build continues unless the gate escalates |

---

## 8. Related

- Discovery lifecycle: [API-nats-fleet-lifecycle.md](API-nats-fleet-lifecycle.md)
- Approval round-trip: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- Data model: [DM-discovery.md](../models/DM-discovery.md), [DM-gating.md](../models/DM-gating.md)
- DDR: [DDR-001-reply-subject-correlation.md](../decisions/DDR-001-reply-subject-correlation.md)
