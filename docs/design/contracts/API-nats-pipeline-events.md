# API Contract — NATS Pipeline Events

> **Type:** Inbound trigger + outbound lifecycle events
> **Transport:** NATS JetStream (`PIPELINE` stream, 7-day retention)
> **Stream:** `PIPELINE` (configured in `nats-infrastructure`)
> **Consumer type:** Durable pull consumer (single) + ephemeral publishers
> **Related ADRs:** [ADR-ARCH-003](../../architecture/decisions/ADR-ARCH-003-nats-native-no-transport-abc.md), [ADR-ARCH-014](../../architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md), [ADR-SP-011](../../research/forge-pipeline-architecture.md), [ADR-SP-013](../../research/forge-pipeline-architecture.md), [ADR-SP-014](../../research/forge-pipeline-architecture.md), [ADR-SP-017](../../research/forge-pipeline-architecture.md)

---

## 1. Purpose

This contract defines Forge's inbound build-queue subscription and outbound lifecycle event stream. Every published event uses `nats-core.MessageEnvelope` as the wire format; payloads are typed Pydantic models already shipped in `nats-core.events.pipeline`.

Forge is both:

- **A consumer** of one subject pattern: `pipeline.build-queued.>` (max_ack_pending=1 pull consumer).
- **A publisher** of eight lifecycle subjects that collectively describe a build's journey from queued → terminal.

---

## 2. Inbound — Build Trigger (Consumed)

### 2.1 Subject

| Template | Resolution example |
|---|---|
| `pipeline.build-queued.{feature_id}` | `pipeline.build-queued.FEAT-A1B2` |
| Project-scoped | `Topics.for_project("finproxy", ...)` → `finproxy.pipeline.build-queued.FEAT-A1B2` |

### 2.2 Consumer configuration

```python
# forge.adapters.nats.pipeline_consumer
await js.pull_subscribe(
    subject="pipeline.build-queued.>",
    durable="forge-consumer",                  # Survives Forge restart
    stream="PIPELINE",
    config=ConsumerConfig(
        max_ack_pending=1,                     # ADR-ARCH-014 — sequential builds enforced at transport
        ack_wait=timedelta(hours=1),           # Covers the longest expected build
        deliver_policy=DeliverPolicy.ALL,      # On first start — replay anything queued pre-boot
        ack_policy=AckPolicy.EXPLICIT,
        max_deliver=-1,                        # Redelivery is infinite until we terminal-ack
        filter_subject="pipeline.build-queued.>",
    ),
)
```

**Acknowledgement rule.** Forge acks the JetStream message **only on a terminal state transition** (`COMPLETE | FAILED | CANCELLED | SKIPPED`). `PAUSED` leaves the message unacked so it holds the queue position; crash + restart triggers redelivery (ADR-SP-013 crash recovery).

### 2.3 Payload — `BuildQueuedPayload`

Defined in `nats-core.events.pipeline`. Forge imports; does not redeclare.

```python
class BuildQueuedPayload(BaseModel):
    feature_id: str
    repo: str
    branch: str
    feature_yaml_path: str
    triggered_by: Literal["cli", "jarvis", "forge-internal", "notification-adapter"]
    originating_adapter: Literal[
        "terminal", "voice-reachy", "telegram", "slack", "dashboard", "cli-wrapper"
    ] | None = None
    originating_user: str | None = None
    correlation_id: str                        # UUID — threaded through all downstream events
    parent_request_id: str | None = None       # Jarvis dispatch ID for progress routing
    max_turns: int = 5
    sdk_timeout: int = 1800
    queued_at: datetime
```

**Validation on consume.**

1. `model_validate(envelope.payload)` — reject if `ValidationError` (log + ack + publish `pipeline.build-failed.{feature_id}` with `failure_reason="malformed BuildQueuedPayload"`).
2. Duplicate detection — check SQLite `builds(feature_id, correlation_id)` unique index; if present, ack and skip (idempotent).
3. Permission check — `feature_yaml_path` must satisfy `forge.config.permissions.filesystem.allowlist`; otherwise publish `pipeline.build-failed` with `failure_reason="path outside allowlist"`.

---

## 3. Outbound — Lifecycle Events (Published)

All outbound events carry the same `correlation_id` from the triggering `BuildQueuedPayload` so downstream subscribers (Jarvis, dashboards, notification adapters) can thread progress.

### 3.1 Subject family

| Stage | Subject template | Payload type | Published when |
|---|---|---|---|
| Build started | `pipeline.build-started.{feature_id}` | `BuildStartedPayload` | `PREPARING → RUNNING` transition |
| Build progress | `pipeline.build-progress.{feature_id}` | `BuildProgressPayload` | At least every 60s during RUNNING; also on wave boundaries from `autobuild_runner` |
| Stage complete | `pipeline.stage-complete.{feature_id}` | `StageCompletePayload` | After each gate-evaluated dispatch commits its `StageLogEntry` to SQLite |
| Build paused | `pipeline.build-paused.{feature_id}` | `BuildPausedPayload` | When `forge.gating` emits `FLAG_FOR_REVIEW` and `interrupt()` is about to fire |
| Build resumed | `pipeline.build-resumed.{feature_id}` | `BuildResumedPayload` | After `ApprovalResponsePayload` rehydrates and graph resumes |
| Build complete | `pipeline.build-complete.{feature_id}` | `BuildCompletePayload` | `FINALISING → COMPLETE` (PR created) |
| Build failed | `pipeline.build-failed.{feature_id}` | `BuildFailedPayload` | `RUNNING/FINALISING → FAILED` (any terminal failure) |
| Build cancelled | `pipeline.build-cancelled.{feature_id}` | `BuildCancelledPayload` | On `forge cancel` CLI command reaching the running build |

**Retention:** 7-day file storage on `PIPELINE` stream; retention policy is `LimitsPolicy` (oldest-first drop), configured by `nats-infrastructure`.

### 3.2 Payloads

All eight payloads ship in `nats-core ≥ 0.2.0` (reconciled + `BuildCancelledPayload` added in `TASK-NCFA-003`, released 2026-04-23). Forge imports from `nats_core.events.pipeline`; no local redeclaration. See [DDR-001](../decisions/DDR-001-reply-subject-correlation.md) for the coordination history.

```python
from nats_core.events.pipeline import (
    StageCompletePayload,
    BuildPausedPayload,
    BuildResumedPayload,
    BuildCancelledPayload,
)

class StageCompletePayload(BaseModel):
    """Emitted after each gate-evaluated dispatch."""
    feature_id: str
    build_id: str
    stage_label: str                       # Reasoning-model-chosen, emergent (ADR-ARCH-016)
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str                 # Tool name / agent_id:tool_name / subagent name
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: Literal["AUTO_APPROVE", "FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"] | None
    coach_score: float | None              # May be None in degraded mode
    duration_secs: float
    completed_at: str                      # ISO-8601 timestamp
    correlation_id: str

class BuildPausedPayload(BaseModel):
    """Emitted when the reasoning model flags a stage for review."""
    feature_id: str
    build_id: str
    stage_label: str
    gate_mode: Literal["FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"]
    coach_score: float | None
    rationale: str                         # Why the gate fired (reasoning-model output)
    approval_subject: str                  # Reply-subject where ApprovalResponsePayload is expected
    paused_at: str                         # ISO-8601 timestamp
    correlation_id: str

class BuildResumedPayload(BaseModel):
    """Emitted after ApprovalResponsePayload rehydrates and the graph resumes."""
    feature_id: str
    build_id: str
    stage_label: str
    decision: Literal["approve", "reject", "defer", "override"]
    responder: str
    resumed_at: str                        # ISO-8601 timestamp
    correlation_id: str

class BuildCancelledPayload(BaseModel):
    """Emitted when the running build sees a cancel command."""
    feature_id: str
    build_id: str
    reason: str                            # e.g. "user_requested", "timeout"
    cancelled_by: str                      # Actor: "rich" / jarvis adapter / "system"
    cancelled_at: str                      # ISO-8601 timestamp
    correlation_id: str
```

**Coordination.** `TASK-NCFA-003` (nats-core) shipped 2026-04-23. The interim carrier `forge.adapters.nats._interim_payloads.py` forecast in earlier revisions of this contract was retired before creation — Forge's scaffold post-dated the nats-core release, so no local payload redeclaration ever landed.

### 3.3 Publish semantics

- **Fire-and-forget** — publish uses `nc.publish(subject, envelope.model_dump_json().encode())`. PubAck is treated as a transport-level receipt, not proof of delivery (LES1 parity rule: PubAck ≠ success).
- **No JetStream ack semantics** — these are not request/reply; subscribers (Jarvis, dashboards) are at-least-once via `PIPELINE` stream replay.
- **`source_id: "forge"`** on every envelope.

---

## 4. Crash-Recovery Contract

On Forge restart, `forge.adapters.nats.pipeline_consumer.reconcile_on_boot()` runs:

1. Pull consumer re-subscribes with `durable="forge-consumer"`. JetStream redelivers any unacked `build-queued` messages.
2. For each redelivered message, `forge.adapters.sqlite.reconcile(feature_id, correlation_id)` checks SQLite:
   - `COMPLETE | FAILED | CANCELLED | SKIPPED` → ack immediately (idempotent — previous run finished before ack).
   - `RUNNING | FINALISING` → mark `INTERRUPTED`, restart from `PREPARING` per anchor §5 retry-from-scratch policy.
   - `PAUSED` → re-enter PAUSED state, re-emit `BuildPausedPayload` + `ApprovalRequestPayload` (idempotent on `correlation_id`; first response wins — ADR-ARCH-021).
   - Unknown build_id → fresh build.

---

## 5. Observability

| Signal | Source | Consumer |
|---|---|---|
| Queue depth | `jsz` / JetStream monitor endpoint | `forge status` (via `forge.cli`) |
| Consumer lag | NATS monitoring | Ops alerting (out of Forge scope) |
| Progress stream | `pipeline.build-progress.{feature_id}` | Jarvis → originating adapter → Rich |
| Terminal state | `pipeline.build-{complete,failed,cancelled}.{feature_id}` | Jarvis, notification adapters, Graphiti `forge_pipeline_history` writer |

---

## 6. Related

- Data model: [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Approval contract: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- DDR: [DDR-001-reply-subject-correlation.md](../decisions/DDR-001-reply-subject-correlation.md)
