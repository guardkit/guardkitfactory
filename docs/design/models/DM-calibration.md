# Data Model — Calibration (history ingestion + override learning)

> **Container:** Domain Core (`forge.calibration`, `forge.learning`) + adapter (`forge.adapters.history_parser`)
> **Owners:** `forge.adapters.history_parser` (tokenise markdown → stream), `forge.calibration` (pure normalisation), `forge.learning` (pattern detection), `forge.adapters.graphiti` (persist to `forge_calibration_history` + `forge_pipeline_history`)
> **Related ADRs:** [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-graphiti-fed-learning-loop.md), [ADR-ARCH-006](../../architecture/decisions/ADR-ARCH-006-calibration-corpus.md), [ADR-ARCH-018](../../architecture/decisions/ADR-ARCH-018-calibration-priors-retrievable.md), [ADR-ARCH-019](../../architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md), [ADR-ARCH-008](../../architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md)

---

## 1. Purpose

The calibration model is the data substrate of Forge's **learning loop**. It has two paths:

1. **Ingestion path** — Rich's history files (`command_history.md`, `feature-spec-*-history.md`, Forge's own history files per ADR-ARCH-008) are parsed into `CalibrationEvent` entities and seeded into `forge_calibration_history`.
2. **Learning path** — `forge.learning` watches override patterns on `GateDecision` outputs and proposes `CalibrationAdjustment` entities. Rich approves via CLI; approved adjustments land in `forge_pipeline_history` and are retrieved as priors on future builds.

`CalibrationEvent` and `CalibrationAdjustment` are already defined in [DM-gating.md](DM-gating.md). This model adds the ingestion + learning-specific entities.

---

## 2. Entities

### `HistoryFileSnapshot`

Bookkeeping for incremental ingestion.

```python
class HistoryFileSnapshot(BaseModel):
    source_path: Path                                       # Absolute path on disk
    file_sha: str                                           # git-style content hash; change triggers re-parse
    last_parsed_at: datetime
    events_ingested: int                                    # Count at last parse
    partial_ingestion: bool                                 # True if parser hit an incomplete section
```

Stored in SQLite `history_snapshots` table (one row per source file).

```sql
CREATE TABLE IF NOT EXISTS history_snapshots (
    source_path TEXT PRIMARY KEY,
    file_sha TEXT NOT NULL,
    last_parsed_at TEXT NOT NULL,
    events_ingested INTEGER NOT NULL DEFAULT 0,
    partial_ingestion INTEGER NOT NULL DEFAULT 0
) STRICT;
```

### `OverridePatternObservation`

Transient — produced by `forge.learning`, not durable on its own; used to decide whether to emit a `CalibrationAdjustment` proposal.

```python
class OverridePatternObservation(BaseModel):
    target_capability: str                                  # e.g. "review_architecture"
    window_builds: int                                      # e.g. last 10 gated events
    observed_overrides: int                                 # Count of Rich-approved FLAG_FOR_REVIEW decisions in window
    score_range: tuple[float, float]                        # (min, max) coach_score observed in the window
    detected_at: datetime

    recommended_action: Literal["raise_threshold", "lower_threshold", "relax_criterion", "tighten_criterion"]
    proposed_adjustment: str | None                         # Draft text — becomes CalibrationAdjustment.proposed_bias if Rich approves
```

### `CalibrationIngestionResult`

Return value from a batch or incremental parse.

```python
class CalibrationIngestionResult(BaseModel):
    source_path: Path
    events_parsed: int
    events_written: int                                     # To Graphiti
    events_skipped_existing: int                            # Deduped
    duration_secs: float
    errors: list[str]
```

---

## 3. Ingestion Pipeline

```
Rich's history file
        │
        ▼
forge.adapters.history_parser.tokenise()                    # Pure regex + structural parsing
        │
        ▼  stream of CalibrationEvent (pre-normalised — response_raw intact)
        │
forge.calibration.normalise()                               # Pure: response_raw → response_normalised + accepted_default
        │
        ▼
forge.adapters.graphiti.add_calibration_events()            # Bulk add to forge_calibration_history
        │
        ▼
update HistoryFileSnapshot in SQLite
```

**Parser robustness.** History files are markdown; parser is tolerant of:

- Missing trailing sections.
- Mixed response shorthand (`"A A A A"`, `"accept all"`, `"edit Q2 → foo"`).
- Non-ASCII characters.
- Out-of-order question/answer pairs.

Unparseable sections raise a structured error and the file is marked `partial_ingestion=True`; already-parsed events are kept.

**Incremental ingestion.** On every Forge boot and after each completed build, `forge.calibration.refresh()`:

1. Scans the history-file allowlist (`forge.yaml.calibration.sources`).
2. For each file, computes current sha; if unchanged vs `HistoryFileSnapshot.file_sha`, skips.
3. Otherwise re-parses and dedupes against Graphiti by `(source_file, command, stage, question)` composite key.

---

## 4. Learning Pipeline

```
Terminal state transition / gate event
        │
        ▼
forge.learning.on_gate_recorded(gate_decision, responder_decision?)
        │
        ├─► update in-memory rolling window (recent GateDecisions per capability)
        │
        ▼
forge.learning.detect_patterns()                            # Pure — runs after each N events
        │
        ▼  list[OverridePatternObservation]
        │
forge.learning.propose_adjustments()
        │
        ▼  For each observation, build CalibrationAdjustment(approved_by_rich=False)
        │
forge.adapters.graphiti.write_calibration_adjustment()      # Stored pending
        │
        ▼
Forge emits ApprovalRequestPayload to Rich
        │
        ▼
Rich approves/rejects via CLI approval round-trip
        │
        ▼
forge.adapters.graphiti.mark_approved()                     # Sets approved_by_rich=True + approved_at
```

**Pattern detection heuristics** (initial set — refine via priors over time):

| Heuristic | Trigger |
|---|---|
| `raise_threshold` | Rich approved ≥ N of last M flag-for-reviews on a single capability |
| `lower_threshold` | Rich rejected ≥ N of last M auto-approves on a single capability |
| `relax_criterion` | Criterion X scored low on K flagged-then-approved stages |
| `tighten_criterion` | Detection pattern Y fired on K auto-approved-then-reverted stages |

Parameters `(N, M, K)` live in `forge.yaml.learning.*` (learning-meta-config only, not behavioural config — permitted by ADR-ARCH-019 because this governs *when to ask*, not *how to decide*).

---

## 5. Retrieval — Priors at Build Start

At each new build's start, `forge.prompts.build_system_prompt()`:

1. Queries `forge_calibration_history` for events whose `command` + `stage` match the build's expected pipeline steps (top-K by recency + similarity).
2. Queries `forge_pipeline_history` for approved `CalibrationAdjustment` entities whose `target_capability` matches any capability in the current fleet snapshot.
3. Injects both into the system prompt's `{calibration_priors}` placeholder — see [`forge.prompts`](../contracts/API-tool-layer.md#1-purpose) template structure (ADR-ARCH-018).

Reasoning model reads priors prose-style; no structured threshold lookup.

---

## 6. Invariants

| Invariant | Enforcement |
|---|---|
| `CalibrationEvent` is immutable once written | Graphiti entity-level — no update path; supersession via new event |
| `CalibrationAdjustment.approved_by_rich=False` entries are excluded from retrieval | `forge.adapters.graphiti.read_adjustments()` filters at read time |
| Supersession chain (`CalibrationAdjustment.supersedes`) is acyclic | `forge.learning.propose_adjustments()` pre-write — walk chain to detect cycles |
| `HistoryFileSnapshot.file_sha` matches on-disk sha before ingestion is skipped | `forge.calibration.refresh()` pre-check |
| Patterns proposing `raise_threshold` only fire when override count ≥ `min_evidence_count` (≥ 5) | `forge.learning.detect_patterns()` guard — prevents proposals from 1–2 overrides |

---

## 7. Related

- Gating entities (`CalibrationEvent`, `CalibrationAdjustment`): [DM-gating.md](DM-gating.md)
- Storage schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
- Tool layer: [API-tool-layer.md §5](../contracts/API-tool-layer.md#5-graphiti)
