# DDR-004 — Graphiti group partitioning (`forge_pipeline_history` + `forge_calibration_history`)

## Status

Accepted

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-005, ADR-ARCH-006, ADR-ARCH-018, ADR-ARCH-022

---

## Context

Forge writes three kinds of durable "memory" to Graphiti:

1. **Runtime outcomes** — every `GateDecision`, `CapabilityResolution`, `OverrideEvent`, `SessionOutcome` produced during a build.
2. **Approved adjustments** — `CalibrationAdjustment` entities Rich confirmed via CLI approval round-trip.
3. **Ingested Q&A history** — `CalibrationEvent` nodes parsed from Rich's markdown history files (command_history.md, feature-spec-*-history.md, Forge's own history files per ADR-ARCH-008).

All three are retrievable as priors at build start to inform the reasoning model's gate decisions. Options for Graphiti group partitioning:

- **A: One group for everything** — `forge_history`. Simple but mixes ingestion-provenance data with runtime-provenance data; retrieval queries must discriminate.
- **B: Two groups** — `forge_pipeline_history` (runtime + adjustments) + `forge_calibration_history` (ingested Q&A only).
- **C: Three groups** — split adjustments out into `forge_calibration_adjustments`.

The existing architecture (ARCHITECTURE.md §9, ADR-ARCH-005) already names two groups — `forge_pipeline_history` and `forge_calibration_history`. This DDR formalises the boundary between them and specifies retrieval queries.

## Decision

**Adopt Option B — two groups:**

| Group | Written by | Contents | Reads |
|---|---|---|---|
| `forge_pipeline_history` | `forge.adapters.graphiti.write_gate_decision`, `write_capability_resolution`, `record_override`, `write_calibration_adjustment`, `write_session_outcome` | `GateDecisionEntity`, `CapabilityResolutionEntity`, `OverrideEvent`, `CalibrationAdjustmentEntity`, `SessionOutcomeEntity` | System-prompt priors retrieval; learning-loop pattern detection |
| `forge_calibration_history` | `forge.adapters.history_parser` via `forge.calibration.refresh` | `CalibrationEventEntity`, `CommandRef`, `StageRef` | System-prompt priors retrieval (semantic match on question/prompt) |

Each group is an independent Graphiti namespace (separate group_id). Cross-group relationships are allowed (e.g. `GateDecision -[INFORMED_BY]-> CalibrationEvent`) — Graphiti supports this natively.

**Why not Option C:** `CalibrationAdjustment` is Forge's runtime-produced output (not Rich's ingested Q&A); it belongs with other runtime entities in `forge_pipeline_history`. The "adjustments are a separate concern" intuition is handled by entity-type filtering in retrieval queries, not by group split.

## Rationale

- **Provenance clarity** — `forge_pipeline_history` is "what Forge did"; `forge_calibration_history` is "what Rich has historically done". Different write paths, different retention/audit concerns, different scales.
- **Query simplicity** — "priors from similar past builds" queries only `forge_pipeline_history`; "Q&A priors for current stage" queries only `forge_calibration_history`. No entity-type WHERE clauses needed at the group boundary.
- **Retention + backup differentiation** — if Rich ever wants to purge runtime history (e.g. for privacy/compliance) without losing ingested Q&A, that's a single-group clear rather than a filtered delete.
- **Aligns with existing architecture** — `forge.yaml.graphiti.default_group_ids` already lists these two groups per the refresh doc; the split was implicit. This DDR makes it explicit and documents the entity-to-group mapping.

## Alternatives considered

- **A: One group** — rejected for provenance clarity and retention asymmetry.
- **C: Three groups with separate adjustments group** — rejected; adjustments share write semantics with other runtime entities, and edges from `CalibrationAdjustment` → `GateDecision` cross a group boundary that adds no value.

## Consequences

- **+** Clean mental model: two data sources, two groups, explicit boundary.
- **+** Retention / purge operations are single-group and orthogonal.
- **+** Retrieval queries are simpler at the group boundary.
- **−** Cross-group edges (e.g. `GateDecision -[INFORMED_BY]-> CalibrationEvent`) require cross-namespace support from Graphiti, which it has, but must be exercised in tests.
- **−** Adding a future Graphiti group (e.g. `forge_fleet_health` for capacity telemetry) will be a separate DDR — boundary decisions tend to compound.

## Related components

- Graphiti Adapter (`forge.adapters.graphiti`)
- History Parser (`forge.adapters.history_parser`)
- Data models — [DM-graphiti-entities.md](../models/DM-graphiti-entities.md), [DM-calibration.md](../models/DM-calibration.md)
