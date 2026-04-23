# Data Model — Gating

> **Container:** Domain Core (`forge.gating`)
> **Owners:** `forge.gating` (pure, no I/O), `forge.adapters.graphiti` (persistence to `forge_pipeline_history`), `forge.adapters.sqlite` (mirror in `stage_log`)
> **Related ADRs:** [ADR-ARCH-007](../../architecture/decisions/ADR-ARCH-007-build-plan-as-gated-artefact.md), [ADR-ARCH-019](../../architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md), [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md), [ADR-ARCH-026](../../architecture/decisions/ADR-ARCH-026-constitutional-rules-belt-and-braces.md)

---

## 1. Entities

### `GateMode`

```python
class GateMode(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    HARD_STOP = "HARD_STOP"
    MANDATORY_HUMAN_APPROVAL = "MANDATORY_HUMAN_APPROVAL"    # Unconditional — PR review, early build plans
```

### `PriorReference`

Records which Graphiti entity informed a gate decision.

```python
class PriorReference(BaseModel):
    entity_id: str                                          # Graphiti UUID / natural key
    group_id: str                                           # forge_pipeline_history | forge_calibration_history
    summary: str                                            # Short recap of what the prior says
    relevance_score: float | None                           # Optional; reasoning model's rating
```

### `DetectionFinding`

Shape mirrors specialist-agent Coach output.

```python
class DetectionFinding(BaseModel):
    pattern: str                                            # e.g. "PHANTOM", "SCOPE_CREEP", "UNGROUNDED"
    severity: Literal["low", "medium", "high", "critical"]
    evidence: str                                           # Human-readable excerpt or file reference
    criterion: str | None = None                            # Optional link to criterion breakdown
```

### `GateDecision`

The output of `forge.gating.evaluate_gate()`. Captured in `stage_log.details_json["gate"]` **and** written to Graphiti as a standalone entity.

```python
class GateDecision(BaseModel):
    build_id: str
    stage_label: str
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str

    mode: GateMode
    rationale: str                                          # Reasoning-model's explanation

    coach_score: float | None                               # None in degraded mode
    criterion_breakdown: dict[str, float] = {}
    detection_findings: list[DetectionFinding] = []

    evidence: list[PriorReference] = []                     # What priors informed it
    threshold_applied: float | None = None                  # Only when a threshold was used

    auto_approve_override: bool = False                     # True if ADR-ARCH-026 belt+braces forced MANDATORY
    degraded_mode: bool = False                             # True when no Coach score available

    decided_at: datetime
```

### `CalibrationEvent`

Parsed turn from Rich's history files. Stored in `forge_calibration_history`.

```python
class CalibrationEvent(BaseModel):
    source_file: str                                        # e.g. command_history.md
    command: str                                            # /feature-spec, /feature-plan, …
    stage: str                                              # GROUP_A_CURATION | ASSUMPTION_RESOLUTION | …

    question: str                                           # Prompt shown to Rich
    default_proposed: str                                   # What the system suggested
    response_raw: str                                       # Rich's literal reply
    response_normalised: ResponseKind                       # See §2

    accepted_default: bool
    custom_content: str | None

    timestamp: datetime | None                              # Parsed from history file when present
```

### `CalibrationAdjustment`

Proposed bias entity — `forge.learning` generates; Rich approves; entity lands in `forge_pipeline_history`.

```python
class CalibrationAdjustment(BaseModel):
    adjustment_id: str                                      # UUID

    target_capability: str                                  # e.g. "review_specification"
    project_scope: str | None                               # None = fleet-wide

    observed_pattern: str                                   # "6 of 10 flag-for-reviews overridden at scores 0.78-0.82"
    proposed_bias: str                                      # Human-readable adjustment

    approved_by_rich: bool = False
    approved_at: datetime | None = None
    expires_at: datetime | None = None                      # Optional time-bounded bias

    supersedes: str | None = None                           # adjustment_id of prior adjustment this replaces
```

---

## 2. `ResponseKind` enum

```python
class ResponseKind(str, Enum):
    ACCEPT_ALL = "ACCEPT_ALL"                               # "A A A A" / "accept defaults"
    ACCEPT_WITH_EDIT = "ACCEPT_WITH_EDIT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    CUSTOM = "CUSTOM"
```

Normalisation is done by `forge.adapters.history_parser` during ingestion — raw response kept verbatim in `response_raw`.

---

## 3. Gate Evaluation — Pure Reasoning (ADR-ARCH-019)

`forge.gating.evaluate_gate()` is a **pure function** (no I/O) called by tool-layer gate-checking wrappers:

```python
def evaluate_gate(
    *,
    target_kind: str,
    target_identifier: str,
    stage_label: str,
    coach_score: float | None,
    criterion_breakdown: dict[str, float],
    detection_findings: list[DetectionFinding],
    retrieved_priors: list[PriorReference],
    calibration_adjustments: list[CalibrationAdjustment],
    constitutional_rules: list[ConstitutionalRule],
) -> GateDecision:
    ...
```

**No static thresholds** (ADR-ARCH-019). The function assembles a reasoning-model prompt from inputs and parses the model's structured response into a `GateDecision`. No `forge.yaml.gate_defaults` — thresholds emerge from priors.

**Constitutional overrides** (ADR-ARCH-026 belt+braces):

1. **Prompt-layer**: the `SAFETY_CONSTITUTION` block in the system prompt asserts "PR review is ALWAYS human".
2. **Executor-layer**: `evaluate_gate()` has a hard-coded first check:

```python
if target_identifier in {"review_pr", "create_pr_after_review"}:
    return GateDecision(mode=GateMode.MANDATORY_HUMAN_APPROVAL, auto_approve_override=True, ...)
```

Both must be independently wired. Loss of either is a constitutional regression.

---

## 4. Relationships

```
Build (1) ─── (0..N) GateDecision                          # One per gated stage
StageLogEntry (0..1) ─── (1) GateDecision                  # 1:1 for gated stages; NULL for non-gated
GateDecision (1) ─── (many) PriorReference                 # Evidence
GateDecision (1) ─── (many) DetectionFinding
CalibrationEvent (many) ─── (informs) GateDecision         # Indirect — via retrieved priors
CalibrationAdjustment (many) ─── (informs) GateDecision
CalibrationAdjustment (0..1) ─── (supersedes) CalibrationAdjustment   # Evolving biases
```

---

## 5. Storage

| Entity | Primary store | Mirror / derived |
|---|---|---|
| `GateDecision` | Graphiti `forge_pipeline_history` | Summary embedded in `stage_log.details_json["gate"]` |
| `CalibrationEvent` | Graphiti `forge_calibration_history` | Source file on disk (`command_history.md` etc.) |
| `CalibrationAdjustment` | Graphiti `forge_pipeline_history` | None — Graphiti is authoritative |
| `DetectionFinding` | Embedded inside `GateDecision` | Not stored separately |
| `PriorReference` | Embedded inside `GateDecision` | Not stored separately; `entity_id` refers to the source entity |

---

## 6. Invariants

| Invariant | Enforcement |
|---|---|
| `mode == MANDATORY_HUMAN_APPROVAL` ⇒ `auto_approve_override` is `True` OR `threshold_applied` is NULL | Pydantic validator |
| `coach_score is None` ⇒ `mode in {FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL}` | `forge.gating.evaluate_gate()` post-condition check — degraded mode cannot auto-approve |
| `criterion_breakdown` values in `[0.0, 1.0]` | Pydantic validator |
| `PriorReference.group_id in {forge_pipeline_history, forge_calibration_history}` | Literal type |
| `CalibrationAdjustment.approved_by_rich is False` ⇒ adjustment is not retrieved by `evaluate_gate()` | `forge.adapters.graphiti.read_adjustments()` filters on approval |
| `CalibrationAdjustment.supersedes` points to an existing adjustment_id | `forge.learning.propose_adjustment()` pre-write |

---

## 7. Related

- Approval wire format: [API-nats-approval-protocol.md](../contracts/API-nats-approval-protocol.md)
- Calibration ingestion: [DM-calibration.md](DM-calibration.md) (overlapping; distinct concerns of parsing + learning)
- Graphiti entity schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
- Tool layer: [API-tool-layer.md §5](../contracts/API-tool-layer.md#5-graphiti)
