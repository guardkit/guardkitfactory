# Data Model — Build Lifecycle

> **Container:** SQLite + Agent Runtime
> **Owners:** `forge.adapters.sqlite` (persistence), `forge.state_machine` (transition rules)
> **Related ADRs:** [ADR-SP-013](../../research/forge-pipeline-architecture.md), [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)

---

## 1. Entities

### `Build`

Authoritative record of a feature-to-PR attempt. One row per attempt.

```python
class Build(BaseModel):
    build_id: str                          # build-{feature_id}-{YYYYMMDDHHMMSS}
    feature_id: str
    repo: str                              # Absolute path or URI
    branch: str
    feature_yaml_path: str
    project: str | None                    # Multi-tenancy scope — NULL means fleet-wide

    status: BuildStatus                    # See §2

    triggered_by: TriggerSource            # cli | jarvis | forge-internal | notification-adapter
    originating_adapter: str | None
    originating_user: str | None
    correlation_id: str                    # UUID — threaded through all events
    parent_request_id: str | None          # Jarvis dispatch ID

    queued_at: datetime                    # UTC
    started_at: datetime | None            # PREPARING transition
    completed_at: datetime | None          # terminal state

    worktree_path: Path | None             # Ephemeral — /var/forge/builds/{build_id}/
    pr_url: str | None
    error: str | None

    max_turns: int = 5
    sdk_timeout_seconds: int = 1800
```

### `StageLogEntry`

One row per reasoning-model dispatch. **Stage labels are emergent** (ADR-ARCH-016) — no controlled vocabulary.

```python
class StageLogEntry(BaseModel):
    id: int                                # Auto-increment PK
    build_id: str                          # FK → builds
    stage_label: str                       # Reasoning-model-chosen, e.g. "Architecture Review"
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str                 # tool name / agent_id:tool_name / subagent name

    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: GateMode | None             # NULL for non-gated stages
    coach_score: float | None              # 0.0–1.0; NULL in degraded mode
    threshold_applied: float | None        # NULL when reasoning-driven (no static threshold)

    started_at: datetime
    completed_at: datetime
    duration_secs: float
    details_json: dict[str, Any]           # Serialised at write time; see §3
```

### `BuildQueuedPayload` (imported — `nats-core`)

Already defined in `nats-core.events.pipeline`. See [nats-core spec §Feature 2](../../../../nats-core/docs/design/specs/nats-core-system-spec.md).

---

## 2. Lifecycle State Machine

```
                       ┌─── redelivery from JetStream ───┐
                       │                                 │
  QUEUED ──► PREPARING ──► RUNNING ──► FINALISING ──► COMPLETE
     ▲          │            │  ▲           │            │
     │          │            │  │           │            │
     │          │            ▼  │           │            │
     │          │          PAUSED           │            │
     │          │            │              │            │
     │          │  (interrupt() halt;       │            │
     │          │   ApprovalResponse        │            │
     │          │   resumes)                │            │
     │          │                           │            │
     │          ▼                           ▼            │
     │      FAILED ◄───────────────────────────────────── │
     │          ▲                                         │
     │          │                                         │
     ├── on crash ──► INTERRUPTED ──► (re-enter PREPARING)│
     │                                                    │
     └─────────── CANCELLED ◄── forge cancel (any non-terminal state)
                                                          │
                      SKIPPED ◄── forge skip (single stage)
```

### 2.1 Valid transitions

| From | To | Trigger |
|---|---|---|
| `QUEUED` | `PREPARING` | JetStream delivery accepted, worktree creation begins |
| `QUEUED` | `CANCELLED` | `forge cancel` before pickup |
| `PREPARING` | `RUNNING` | Worktree ready, first stage dispatch |
| `PREPARING` | `FAILED` | Worktree creation / feature.yaml validation failure |
| `PREPARING` | `INTERRUPTED` | Crash recovery |
| `RUNNING` | `PAUSED` | `FLAG_FOR_REVIEW` / `HARD_STOP` / `MANDATORY_HUMAN_APPROVAL` gate fires |
| `RUNNING` | `FINALISING` | All stages passed, PR creation begins |
| `RUNNING` | `FAILED` | `HARD_STOP` with no retry path |
| `RUNNING` | `INTERRUPTED` | Crash recovery |
| `RUNNING` | `CANCELLED` | `forge cancel` during active build |
| `PAUSED` | `RUNNING` | `ApprovalResponsePayload(decision="approve")` rehydrates |
| `PAUSED` | `FAILED` | `ApprovalResponsePayload(decision="reject")` |
| `PAUSED` | `CANCELLED` | `forge cancel` while paused |
| `PAUSED` | `SKIPPED` | `ApprovalResponsePayload(decision="override")` via `forge skip` — stage skipped, build continues as RUNNING |
| `FINALISING` | `COMPLETE` | PR URL confirmed, JetStream ack sent |
| `FINALISING` | `FAILED` | PR creation failed |
| `FINALISING` | `INTERRUPTED` | Crash during finalisation (rare) |
| `INTERRUPTED` | `PREPARING` | On restart — retry from scratch (anchor §5) |

### 2.2 Terminal states (ack JetStream)

`COMPLETE`, `FAILED`, `CANCELLED`, `SKIPPED`. `PAUSED` is explicitly **not** terminal — leaves the message unacked so the queue position is held.

`INTERRUPTED` is a transitional state used only on recovery; the message is re-queued via JetStream redelivery rather than being acked.

---

## 3. `details_json` Conventions

The `stage_log.details_json` blob is reasoning-model-authored. Forge's writer does not impose a schema but **recommends** these keys (indexed by `forge history` renderer):

```python
{
    "rationale": "Why the reasoning model chose this target for this stage",
    "priors_referenced": [                             # IDs of retrieved Graphiti entities
        "forge_pipeline_history/prior-abc123",
    ],
    "coach_breakdown": {
        "criteria": {"fidelity": 0.8, "rigour": 0.6, ...},
        "detections": [
            {"pattern": "SCOPE_CREEP", "severity": "medium", "evidence": "..."},
        ],
    },
    "approval": {                                      # Only present when gate_mode fired
        "request_id": "...",
        "response": {"decision": "approve", "responder": "rich", "reason": "..."},
        "wait_duration_secs": 127.3,
    },
    "artefacts": ["/var/forge/builds/build-.../docs/.../file.md"],
    "subagent_task_id": "autobuild-a3f2",              # Link to async subagent state
}
```

---

## 4. Relationships

```
Build (1) ─── (many) StageLogEntry                        # FK build_id; cascade delete
Build (1) ─── (1) BuildQueuedPayload                      # Origin payload — stored in JetStream, not duplicated in SQLite
Build (1) ─── (0..N) GateDecision                         # One per gated StageLogEntry; see DM-gating
Build (1) ─── (0..1) async_tasks state entry              # See DDR-006 — linked by subagent_task_id
Build (1) ─── (0..N) CapabilityResolution                 # One per fleet-dispatch StageLogEntry; see DM-discovery
```

---

## 5. Invariants

| Invariant | Enforcement |
|---|---|
| `build_id` is unique across all time | PK constraint + `build_id` includes timestamp |
| `(feature_id, correlation_id)` unique | SQLite unique index (`uq_builds_feature_correlation`) |
| `status` transitions only follow §2.1 table | `forge.state_machine.validate_transition()` pre-write check |
| Terminal `status` ⇒ `completed_at` is set | Writer pre-write assertion |
| `PAUSED` ⇒ corresponding `ApprovalRequestPayload` was published | `forge.adapters.nats.mark_paused()` is the only entry point; it publishes then writes |
| `stage_log.build_id` references a live `builds` row | FK constraint |
| Coach score, if present, is in `[0.0, 1.0]` | Pydantic validator on write |
| `gate_mode` is NULL iff `status != "GATED"` | SQL CHECK constraint (not enforced by engine, validated in `record_stage`) |

---

## 6. Query patterns (CLI)

| Purpose | Query |
|---|---|
| `forge status` active | `SELECT * FROM builds WHERE status IN ('QUEUED','PREPARING','RUNNING','PAUSED','FINALISING') ORDER BY queued_at DESC` |
| `forge status <feature>` | `SELECT * FROM builds WHERE feature_id = ? ORDER BY queued_at DESC` |
| `forge history` default | `SELECT * FROM builds ORDER BY queued_at DESC LIMIT 50` |
| `forge history --feature X` | `SELECT * FROM builds WHERE feature_id = ? ORDER BY queued_at DESC` + `SELECT * FROM stage_log WHERE build_id IN (...) ORDER BY started_at` |
| `forge status --full` detail | joins above with `stage_log` last 5 rows per build |

---

## 7. Related

- Schema + pragmas: [API-sqlite-schema.md](../contracts/API-sqlite-schema.md)
- Gating: [DM-gating.md](DM-gating.md)
- Discovery: [DM-discovery.md](DM-discovery.md)
- Async state: [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md)
