---
id: TASK-IC-001
title: Entity model layer and credential redaction
status: in_review
created: 2026-04-25 14:36:00+00:00
updated: 2026-04-25 14:36:00+00:00
priority: high
task_type: declarative
tags:
- models
- scaffolding
- security
complexity: 4
parent_review: TASK-REV-IC8B
feature_id: FEAT-FORGE-006
wave: 1
implementation_mode: task-work
dependencies: []
estimated_minutes: 90
autobuild_state:
  current_turn: 2
  max_turns: 30
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-8D10
  base_branch: main
  started_at: '2026-04-26T13:54:50.487569'
  last_updated: '2026-04-26T14:14:02.128857'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Advisory (non-blocking): task-work produced a report with 2 of 3\
      \ expected agent invocations. Missing phases: 3 (Implementation). Consider invoking\
      \ these agents via the Task tool to strengthen stack-specific quality:\n- Phase\
      \ 3: `python-api-specialist` (Implementation)\n- Not all acceptance criteria\
      \ met:\n  \u2022 All modified files pass project-configured lint/format checks\
      \ with zero errors"
    timestamp: '2026-04-26T13:54:50.487569'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-04-26T14:07:08.359967'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: Entity model layer and credential redaction

## Description

Define the five Pydantic models for entities written to `forge_pipeline_history`,
plus the deterministic-id model for `forge_calibration_history`, and the
`redact_credentials()` utility. These models are the foundation every other
unit in this feature consumes. They establish ASSUM-007's resolution: the SQLite-row
UUID is the Graphiti `entity_id` for every pipeline-history entity.

## Models to define (in `forge/memory/models.py`)

- `GateDecision` — fields: `entity_id` (UUID, sourced from SQLite), `stage_name`,
  `decided_at`, `score`, `criterion_breakdown`, `rationale`.
- `CapabilityResolution` — fields: `entity_id`, `agent_id`, `capability`,
  `selected_at`, `discovery_cache_version`.
- `OverrideEvent` — fields: `entity_id`, `gate_decision_id`, `original_recommendation`,
  `operator_decision`, `operator_rationale`, `decided_at`.
- `CalibrationAdjustment` — fields: `entity_id`, `parameter`, `old_value`,
  `new_value`, `approved` (bool), `supersedes` (Optional[entity_id]),
  `proposed_at`, `expires_at`.
- `SessionOutcome` — fields: `entity_id`, `build_id`, `outcome`
  (success/failure/aborted), `gate_decision_ids` (ordered list, sorted by
  `decided_at` ascending per ASSUM-008 resolution), `closed_at`.

Plus for Q&A (`forge_calibration_history` group):

- `CalibrationEvent` — fields: `entity_id` (deterministic from file path + line
  range hash per `@data-integrity deterministic-qa-identity`), `source_file`,
  `question`, `answer`, `captured_at`, `partial` (bool flag for partial-parse
  tolerance).

## `redact_credentials(text: str) -> str` (in `forge/memory/redaction.py`)

Pattern set MUST cover at minimum:

- `Bearer [A-Za-z0-9._-]{20,}` → `Bearer ***REDACTED***`
- `ghp_[A-Za-z0-9]{36}`, `ghs_[A-Za-z0-9]{36}`, `github_pat_[A-Za-z0-9_]{82,}`
  → `***REDACTED-GITHUB-TOKEN***`
- Hex strings of 40+ chars → `***REDACTED-HEX***`

Function MUST be applied to every `rationale`, `operator_rationale`, `question`,
and `answer` field before any entity is constructed for Graphiti write.
Document each pattern's justification in the module docstring.

## Acceptance Criteria

- [ ] All six entity models defined with Pydantic v2 BaseModel
- [ ] `entity_id` field documented as "MUST be sourced from SQLite UUID, never
      generated at write time" (ASSUM-007 resolution)
- [ ] `gate_decision_ids` on `SessionOutcome` documented as ordered ascending
      by `decided_at` (ASSUM-008 resolution)
- [ ] `CalibrationEvent.entity_id` is deterministic from `(source_file,
      line_range_hash)` so re-ingestion is idempotent
- [ ] `redact_credentials()` function implemented with documented regex set
- [ ] Unit tests for `redact_credentials()` covering each pattern (positive +
      negative cases, including overlapping matches and unicode)
- [ ] Unit tests confirming model validation rejects empty/missing required fields
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- [ ] `tests/unit/test_models.py` — model validation, defaults, ordering invariants
- [ ] `tests/unit/test_redaction.py` — at least 3 cases per pattern (positive,
      negative, edge), plus a fuzz test on random hex strings of varying length

## Implementation Notes

- Use Pydantic v2 (project already on it via `pydantic-settings`).
- `entity_id` should be `UUID` typed (not str) for `GateDecision`,
  `CapabilityResolution`, `OverrideEvent`, `CalibrationAdjustment`, `SessionOutcome`.
- For `CalibrationEvent`, `entity_id` is `str` (deterministic hash format).
- `redact_credentials()` MUST be pure and side-effect-free (no logging the
  original text). Tests should assert no original credential value appears
  in the output even on overlapping matches.
- This unit ships only models and the redaction utility. The Graphiti write
  call itself is unit 2 (TASK-IC-002).
