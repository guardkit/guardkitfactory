# Data Model — Graphiti Entities

> **Container:** Graphiti Adapter (`forge.adapters.graphiti`)
> **Owners:** `forge.adapters.graphiti` (reads/writes), `forge.adapters.history_parser` (ingestion entry point)
> **Storage:** FalkorDB via Graphiti at `whitestocks:6379` (Tailscale)
> **Related ADRs:** [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-graphiti-fed-learning-loop.md), [ADR-ARCH-006](../../architecture/decisions/ADR-ARCH-006-calibration-corpus.md), [ADR-ARCH-018](../../architecture/decisions/ADR-ARCH-018-calibration-priors-retrievable.md), [ADR-ARCH-022](../../architecture/decisions/ADR-ARCH-022-dual-agent-memory.md)

---

## 1. Purpose

Graphiti stores Forge's long-term memory — outcomes, overrides, and ingested calibration history. Two groups (namespaces):

- `forge_pipeline_history` — everything Forge produces at runtime (gate decisions, resolutions, overrides, calibration adjustments, session outcomes).
- `forge_calibration_history` — everything ingested from Rich's Q&A history files (calibration events).

See [DDR-004-graphiti-group-partitioning.md](../decisions/DDR-004-graphiti-group-partitioning.md) for the group-boundary rationale.

LangGraph Memory Store is a **separate** concern — per-thread recall within a running build (ADR-ARCH-022). Graphiti is cross-build, cross-session.

---

## 2. Entity Types (`forge_pipeline_history`)

### `GateDecisionEntity`

Graphiti representation of `GateDecision` (from [DM-gating.md](DM-gating.md)). Stored as a node; evidence priors become edges.

```
Node: GateDecision
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    target_kind:          str
    target_identifier:    str
    mode:                 str (GateMode value)
    rationale:            str
    coach_score:          float | null
    criterion_breakdown:  json (dict[str, float])
    detection_findings:   json (list[DetectionFinding])
    threshold_applied:    float | null
    degraded_mode:        bool
    decided_at:           datetime (ISO 8601 UTC)

Edges out:
  (GateDecision) -[INFORMED_BY]-> (CalibrationEvent)
  (GateDecision) -[INFORMED_BY]-> (CalibrationAdjustment)
  (GateDecision) -[RESULT_OF]-> (CapabilityResolution)
  (GateDecision) -[OVERRIDDEN_BY]-> (OverrideEvent)           # when Rich overrides
```

### `CapabilityResolutionEntity`

Graphiti representation of `CapabilityResolution` (from [DM-discovery.md](DM-discovery.md)).

```
Node: CapabilityResolution
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    requested_tool:       str
    requested_intent:     str | null
    matched_agent_id:     str | null
    match_source:         str (tool_exact | intent_pattern | unresolved)
    competing_agents:     json (list[str])
    chosen_trust_tier:    str | null
    chosen_confidence:    float | null
    chosen_queue_depth:   int | null
    resolved_at:          datetime

Edges out:
  (CapabilityResolution) -[MATCHED]-> (AgentManifestSnapshot)
  (CapabilityResolution) -[HAD_OUTCOME]-> (GateDecision | StageLogEntry)
```

### `CalibrationAdjustmentEntity`

```
Node: CalibrationAdjustment
  properties:
    entity_id:            str (UUID) — same as CalibrationAdjustment.adjustment_id
    target_capability:    str
    project_scope:        str | null
    observed_pattern:     str
    proposed_bias:        str
    approved_by_rich:     bool
    approved_at:          datetime | null
    expires_at:           datetime | null

Edges out:
  (CalibrationAdjustment) -[SUPERSEDES]-> (CalibrationAdjustment)      # When rev'd
  (CalibrationAdjustment) -[PROPOSED_FROM]-> (OverridePattern)         # Optional — which pattern triggered it
```

### `OverrideEvent`

Raw event produced every time Rich's decision differed from Forge's gate. Input to `forge.learning`.

```
Node: OverrideEvent
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    gate_mode_before:     str (GateMode)
    decision:             str (approve | reject | defer | override)
    rich_reason:          str | null
    coach_score_at_gate:  float | null
    recorded_at:          datetime

Edges out:
  (OverrideEvent) -[OF_DECISION]-> (GateDecision)
  (OverrideEvent) -[BY_RESPONDER]-> (Actor)                  # "rich", jarvis-adapter-id
```

### `SessionOutcomeEntity`

High-level per-build summary node. Linked to every `GateDecision` + `CapabilityResolution` produced during that build.

```
Node: SessionOutcome
  properties:
    entity_id:            str = build_id
    feature_id:           str
    repo:                 str
    project:              str | null
    outcome:              str (COMPLETE | FAILED | CANCELLED | SKIPPED)
    duration_secs:        float
    tasks_completed:      int
    tasks_failed:         int
    pr_url:               str | null
    error:                str | null
    correlation_id:       str
    completed_at:         datetime

Edges out:
  (SessionOutcome) -[CONTAINS]-> (GateDecision)
  (SessionOutcome) -[CONTAINS]-> (CapabilityResolution)
  (SessionOutcome) -[FOR_FEATURE]-> (FeatureRef)
```

---

## 3. Entity Types (`forge_calibration_history`)

### `CalibrationEventEntity`

Graphiti representation of `CalibrationEvent` (from [DM-gating.md §1](DM-gating.md#1-entities) + ingestion described in [DM-calibration.md](DM-calibration.md)).

```
Node: CalibrationEvent
  properties:
    entity_id:            str = sha(source_file + command + stage + question)   # Deterministic — dedupe key
    source_file:          str
    command:              str
    stage:                str
    question:             str
    default_proposed:     str
    response_raw:         str
    response_normalised:  str (ResponseKind value)
    accepted_default:     bool
    custom_content:       str | null
    timestamp:            datetime | null                                       # Parsed from file when available
    ingested_at:          datetime

Edges out:
  (CalibrationEvent) -[FOR_COMMAND]-> (CommandRef)
  (CalibrationEvent) -[AT_STAGE]-> (StageRef)
```

`CommandRef` and `StageRef` are thin reference nodes (just a `name` property), deduplicated, used to accelerate "all events for command=X" retrieval.

---

## 4. Retrieval Patterns

### At build start (`forge.prompts.build_system_prompt`)

| Purpose | Query |
|---|---|
| Similar past builds | `forge_pipeline_history` — `SessionOutcome` nodes matching `feature_id` prefix or `project`; top-K by recency |
| Override history per capability | `forge_pipeline_history` — `OverrideEvent` WHERE `stage_label ≈ X OR target_identifier = Y`; last 20 |
| Approved calibration adjustments | `forge_pipeline_history` — `CalibrationAdjustment` WHERE `approved_by_rich=True` AND (`project_scope IS NULL OR project_scope = <build.project>`) AND (`expires_at IS NULL OR expires_at > NOW()`) |
| Relevant Q&A priors | `forge_calibration_history` — top-K semantic match on question text against current stage's expected prompt |

All queries use Graphiti's native search plus FalkorDB Cypher where needed. Results are injected prose-style into the system prompt (ADR-ARCH-018).

### During a gate evaluation

| Purpose | Query |
|---|---|
| Rich's recent behaviour | `OverrideEvent` on same `target_identifier` in last 30 days, with summary stats (override rate) |
| Adjustments targeting this capability | `CalibrationAdjustment` WHERE `target_capability = X AND approved_by_rich=True` |

### After build completion

`forge.adapters.graphiti.write_session_outcome()` creates the `SessionOutcome` node and links all produced `GateDecision`s, `CapabilityResolution`s, and override events. This is the pattern-mining substrate for future builds.

---

## 5. Write Ordering

Per-build chronological order:

1. On `PREPARING → RUNNING`: no Graphiti writes yet (stage work hasn't happened).
2. Per stage:
   - `CapabilityResolution` written **before** dispatch (see DM-discovery invariant — write-before-send).
   - `GateDecision` written **after** result comes back, before `StageLogEntry` is committed to SQLite (so both stores are consistent).
   - `OverrideEvent` written if Rich's decision diverged from Forge's gate.
3. On terminal state transition: `SessionOutcome` written, edges linked.

Partial failures are tolerated — a write to Graphiti that fails triggers a structured log entry and the build continues (Graphiti is enrichment, not a hard dependency). On next build, `forge.adapters.graphiti.reconcile()` scans SQLite `stage_log` for entries lacking Graphiti counterparts and backfills.

---

## 6. Embedding + Indexing

Embeddings are produced by the Graphiti service using the embedding provider configured in `.guardkit/graphiti.yaml` (currently `nomic-embed-text-v1.5` via vLLM on GB10). Forge does not embed directly — it writes text; Graphiti indexes.

Each entity's searchable text is composed from:

- `GateDecision.rationale` + stringified `criterion_breakdown` + `detection_findings`.
- `CapabilityResolution.requested_tool` + `requested_intent` + chosen `agent_id`.
- `CalibrationEvent.question` + `default_proposed` + `response_raw`.
- `CalibrationAdjustment.observed_pattern` + `proposed_bias`.
- `SessionOutcome.error` (when failed) + `pr_url` (for linking).

---

## 7. Invariants

| Invariant | Enforcement |
|---|---|
| `CalibrationEvent.entity_id` is deterministic — duplicate re-ingestions are no-ops | sha key computed in `forge.adapters.history_parser` |
| Graphiti writes happen after the authoritative SQLite commit (for gate + stage entities) | `forge.adapters.sqlite.record_stage()` returns before `forge.adapters.graphiti.write_gate_decision()` is called |
| `SessionOutcome.outcome` is terminal (no IN_PROGRESS entity ever exists) | Only written on terminal transition |
| `CalibrationAdjustment.approved_by_rich=False` entries are filtered out at retrieval time | `forge.adapters.graphiti.read_adjustments()` WHERE clause |
| Expired `CalibrationAdjustment` entities are ignored on retrieval, not deleted | `expires_at > NOW()` filter; history preserved for audit |

---

## 8. Related

- Ingestion pipeline: [DM-calibration.md](DM-calibration.md)
- Gate entities: [DM-gating.md](DM-gating.md)
- Discovery entities: [DM-discovery.md](DM-discovery.md)
- DDR: [DDR-004-graphiti-group-partitioning.md](../decisions/DDR-004-graphiti-group-partitioning.md)
