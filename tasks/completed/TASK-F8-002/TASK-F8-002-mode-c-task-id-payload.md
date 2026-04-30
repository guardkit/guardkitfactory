---
id: TASK-F8-002
title: "Add task_id + mode fields to BuildQueuedPayload (cross-repo: forge + nats-core)"
task_type: implementation
status: completed
priority: high
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
previous_state: in_review
completed_location: tasks/completed/TASK-F8-002/
organized_files:
  - TASK-F8-002-mode-c-task-id-payload.md
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 2
implementation_mode: task-work
complexity: 6
dependencies: [TASK-F8-003, TASK-F8-004, TASK-F8-005]
tags: [mode-c, wire-schema, nats-core, cross-repo, assum-004, feat-forge-008, f008-val-002]
related_files:
  - ../../nats-core/src/nats_core/events/_pipeline.py
  - ../../nats-core/tests/events/test_pipeline.py
  - ../../nats-core/pyproject.toml
  - ../../nats-core/src/nats_core/__init__.py
  - src/forge/cli/queue.py
  - tests/forge/test_cli_mode_flag.py
  - tests/integration/test_mode_c_wire_smoke_e2e.py
  - pyproject.toml
test_results:
  status: passed
  coverage: not_measured
  last_run: 2026-04-30T00:00:00Z
  forge_unit_pass: 3853
  forge_unit_skip: 1
  forge_unit_fail: 0
  nats_core_unit_pass: 772
  nats_core_unit_fail: 0
  notes: |
    Forge: 3853 passed, 1 skipped (live-broker integration smoke — opt-in
    via FORGE_NATS_URL), 0 failures.
    nats-core: 772 passed, 0 failures.
acceptance_criteria_status:
  ac_1_task_id_pattern: passed
  ac_2_task_id_field: passed
  ac_3_mode_field: passed
  ac_4_model_validator: passed
  ac_5_six_combination_tests: passed
  ac_6_nats_core_030_tagged: passed_local_only  # local tag, no remote push per session policy
  ac_7_forge_pin_bumped: passed
  ac_8_mode_c_payload_wiring: passed
  ac_9_mode_a_b_unchanged_task_id_none: passed
  ac_10_integration_smoke_test: passed_gated  # skipped unless FORGE_NATS_URL points at live broker
  ac_11_runbook_section_25: deferred  # belongs to TASK-F8-006 per task description
---

# Task: Add `task_id` + `mode` fields to `BuildQueuedPayload` (cross-repo)

## Description

Mode C is currently half-shipped: the forge CLI accepts
`forge queue --mode c TASK-XXX`, but the JetStream wire layer rejects the
payload because `BuildQueuedPayload.feature_id` validates against
`^FEAT-[A-Z0-9]{3,12}$` (see
`../nats-core/src/nats_core/events/_pipeline.py:27`).

The architectural review (`docs/reviews/REVIEW-F008-validation-triage.md`
§2) selected **Option A** — keep `feature_id` strict, add a sibling
`task_id: str | None` field plus a `mode: Literal[...]` field for symmetry
with the v2 SQLite `builds.mode` column.

### Why Option A vs. widening the regex (Option C) or renaming to `subject_id` (Option B)

The `stage_taxonomy.py:35-36` and `supervisor.py:1296-1331` codify Mode C
as feature-scoped builds with per-fix-task sub-identifiers. The topic
`pipeline.build-queued.<feature_id>` stays per-feature (consumers don't
need to widen subject filters). The fix-task is the dispatch target, not
the build's identity.

Per `Q2=Q` (quality/correctness), Option A is the architecturally clean
fix; the cross-repo cost is bounded (additive minor on nats-core 0.3.0)
and avoids the FEAT/TASK conflation that ADR-FB-002 in the knowledge graph
already documented as a recurring failure class.

## Acceptance Criteria

### nats-core (sibling repo) — must land first

- [ ] **AC-1**: `nats-core` adds a `TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]{3,12}$")`
      constant.
- [ ] **AC-2**: `BuildQueuedPayload` adds a `task_id: str | None = None`
      field with a `_validate_task_id` field-validator that enforces the
      `TASK-` regex when non-None.
- [ ] **AC-3**: `BuildQueuedPayload` adds a
      `mode: Literal["mode-a", "mode-b", "mode-c"]` field. Default to
      `"mode-a"` for backwards compatibility with existing v2.2 publishers.
- [ ] **AC-4**: A `model_validator(mode="after")` enforces:
      - `mode == "mode-c"` ⇒ `task_id is not None`
      - `mode in {"mode-a", "mode-b"}` ⇒ `task_id is None`
- [ ] **AC-5**: nats-core unit tests cover all six combinations
      (positive + negative for each mode × task_id pairing).
- [ ] **AC-6**: nats-core 0.3.0 is tagged and reachable from `[tool.uv.sources]` in
      forge's `pyproject.toml`.

### forge

- [ ] **AC-7**: `pyproject.toml` pins `nats-core>=0.3.0,<0.4`.
- [ ] **AC-8**: `forge queue --mode c TASK-XXX` looks up the parent
      `feature_id` from the fix-task YAML (the `parent_feature` field) and
      populates the wire payload with `feature_id=<parent FEAT->`,
      `task_id=<TASK->`, `mode="mode-c"`.
- [ ] **AC-9**: `forge queue --mode {a,b}` continues to populate
      `task_id=None` and `mode=<respective>` — Mode A/B publishers see no
      breaking change.
- [ ] **AC-10**: Forge integration test
      `tests/integration/test_mode_c_smoke_e2e.py` (or new file)
      end-to-end publishes a Mode C `BuildQueuedPayload` carrying both
      `feature_id` and `task_id` against a local NATS, verifies the
      envelope arrives at `pipeline.build-queued.<FEAT->`, and verifies
      the consumer can read both fields.
- [ ] **AC-11**: Runbook §2.5 (gap-folded in TASK-F8-006) shows the new
      Mode C invocation: `forge queue --mode c TASK-TESTMC --feature-yaml ...`.

## Implementation Notes

### nats-core PR sketch

```python
# nats-core/src/nats_core/events/_pipeline.py

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]{3,12}$")

class BuildQueuedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    # ... existing fields ...

    # NEW (FEAT-F8 / F008-VAL-002 — Mode C support per ASSUM-004)
    task_id: str | None = Field(
        default=None,
        description=(
            "Per-fix-task identifier (TASK-XXX) for Mode C dispatches. "
            "MUST be non-None when mode == 'mode-c'; MUST be None for "
            "Mode A and Mode B."
        ),
    )
    mode: Literal["mode-a", "mode-b", "mode-c"] = Field(
        default="mode-a",
        description=(
            "Build mode (mirrors the v2 SQLite builds.mode column). "
            "Determines which planner the supervisor invokes."
        ),
    )

    @field_validator("task_id")
    @classmethod
    def _validate_task_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not TASK_ID_PATTERN.match(v):
            msg = f"task_id must match {TASK_ID_PATTERN.pattern}, got {v!r}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _task_id_required_iff_mode_c(self) -> BuildQueuedPayload:
        if self.mode == "mode-c" and self.task_id is None:
            raise ValueError("task_id is required when mode == 'mode-c'")
        if self.mode in ("mode-a", "mode-b") and self.task_id is not None:
            raise ValueError(
                f"task_id must be None for mode={self.mode!r} (Mode C only)"
            )
        return self
```

### forge CLI sketch

`src/forge/cli/queue.py` — currently does NOT populate `task_id` or
`mode` on the payload (the v2 SQLite column is set on the `builds` row at
consume time). Add:

1. Parse the fix-task YAML when `--mode c` is set; extract `parent_feature` to use as `feature_id`.
2. Populate `task_id=<TASK_ID from CLI args>`, `mode="mode-c"`.
3. For `--mode {a,b}`, populate `mode=<respective>`, `task_id=None` (default).

### Sequencing (cross-repo)

1. Open nats-core PR with AC-1..AC-5.
2. Tag nats-core 0.3.0.
3. Update forge `pyproject.toml` (AC-7).
4. Update forge CLI (AC-8..AC-9).
5. Add forge integration test (AC-10).
6. Coordinate with TASK-F8-006 to update runbook §2.5 (AC-11).

## Out of scope

- Renaming `feature_id` → `subject_id` (rejected as Option B; would be
  a major breaking change on nats-core for marginal benefit).
- Widening the `feature_id` regex (rejected as Option C; would bake in
  FEAT/TASK conflation that ADR-FB-002 already warned against).
- Re-deploying every existing Mode A/B publisher — Option A is
  additive, so existing publishers continue to work without changes.
