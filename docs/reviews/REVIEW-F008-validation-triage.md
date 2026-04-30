---
review_id: REVIEW-F008-validation-triage
parent_task: TASK-REV-F008
mode: architectural
depth: standard
focus: all
tradeoff_priority: quality_correctness
reviewed_at: 2026-04-29
reviewer: claude (sonnet/opus via /task-review)
related_files:
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md
  - docs/research/ideas/forge-build-plan.md
  - src/forge/pipeline/supervisor.py
  - src/forge/pipeline/stage_taxonomy.py
  - src/forge/lifecycle/migrations.py
  - src/forge/lifecycle/schema_v2.sql
  - src/forge/lifecycle/recovery.py
  - src/forge/adapters/nats/approval_publisher.py
  - tests/forge/adapters/test_sqlite_persistence.py
  - tests/forge/test_approval_publisher.py
  - ../nats-core/src/nats_core/events/_pipeline.py
score: 72
findings_count: 7
recommendations_count: 8
decision_required: true
---

# Review: FEAT-FORGE-008 validation triage

## Executive summary

Step 6 validation against `main@5e5cc73` produced **3757/3762 pytest pass + 64/64 BDD-008 + 68/68 Mode B/C integration**, but four red unit/integration tests and one collection error. The runbook's §1.3 hard-stop (`Mode A → Supervisor._dispatch` regression) fired exactly as predicted.

The seven follow-ups (F008-VAL-001..007) decompose cleanly into two implementation waves plus one delegated infrastructure track:

- **Wave 1 (blocker + cleanup, parallelisable)** — F008-VAL-003 (`Supervisor._dispatch` missing routing branch), F008-VAL-005 (stale test, NOT a migration bug), F008-VAL-004 (recovery.py AC-008 violation). Three small fixes; once landed, Phase 1 of the runbook should go fully green.
- **Wave 2 (semantic + substrate, parallelisable, blocked on Wave 1 green)** — F008-VAL-002 (Mode C wire-schema vs CLI mismatch — design decision: **add sibling `task_id` field**), F008-VAL-001 (land TASK-IC-009/010 `forge.build.git_operations` + `forge.build.test_verification`), F008-VAL-006 (runbook gap-fold).
- **Wave 3 (delegated)** — F008-VAL-007 splits: NATS provisioning → `nats-infrastructure` repo; production `Dockerfile` → standalone forge containerisation effort. Neither blocks Step 6 canonical for Phases 0–3, but both are prerequisites for Phase 6 (LES1 CMDW/PORT/ARFS gates).

**Headline correction from RESULTS file**: F008-VAL-005's described root cause ("`apply_at_boot` is non-idempotent — INSERT OR IGNORE missing") is wrong. Both `schema.sql:108` and `schema_v2.sql:26-27` already use `INSERT OR IGNORE INTO schema_version`, and `migrations.apply_at_boot` is genuinely idempotent (it gates on `_current_version()`). The actual defect is in the **test fixture**: `test_apply_at_boot_is_idempotent` was written when only schema v1 existed and asserts `rows == [(1,)]`. FEAT-FORGE-008 introduced `(2, schema_v2.sql)` and the test was never updated. Running v1+v2 twice produces `[(1,), (2,)]` — which is the correct idempotent result.

This makes Wave 1 cheaper than the runbook predicted: F008-VAL-005 is a one-line test assertion update, not a SQL migration audit.

**Architecture score**: 72/100 — the regressions are localised, not systemic. The failures cluster around (a) enum extension without dispatcher extension (F008-VAL-003), (b) shape duplication despite an explicit single-ownership guard (F008-VAL-004), and (c) a half-shipped feature where the CLI surface and the wire schema disagree on what an identifier is (F008-VAL-002). All three are exactly the failure modes the existing structural tests were designed to catch — the tests caught them.

---

## 1. Triage table

| ID            | Severity | Decision        | Owner repo            | Wave | Target task ID                           | Sequencing notes |
|---------------|----------|-----------------|-----------------------|------|------------------------------------------|------------------|
| F008-VAL-001  | medium   | implement-now   | forge                 | 2    | `TASK-F8-001-land-forge-build-modules`   | Lands `forge.build.git_operations` + `forge.build.test_verification` (TASK-IC-009/010). Pre-existing gap, not introduced by F008. Drops the `--ignore` from runbook §1.1. Independent of Wave 1; do in Wave 2 to keep the Mode A blocker fix risk-isolated. |
| F008-VAL-002  | high     | implement-now   | forge + **nats-core** | 2    | `TASK-F8-002-mode-c-task-id-payload`     | Cross-repo: `nats-core` adds `BuildQueuedPayload.task_id: str \| None` field + Mode-C-conditional validator; forge CLI populates `task_id` for Mode C. Recommended design: **Option A** below. Blocks Phase 2.5 going green. |
| F008-VAL-003  | blocker  | implement-now   | forge                 | 1    | `TASK-F8-003-supervisor-dispatch-task-review` | Add `StageClass.TASK_REVIEW` and `StageClass.TASK_WORK` to `_SUBPROCESS_STAGES` frozenset (supervisor.py:618-625). Single-line + a regression test. Unblocks Phase 1.3 + 1.1 Mode A reds. |
| F008-VAL-004  | medium   | implement-now   | forge                 | 1    | `TASK-F8-004-recovery-evidence-priors-helper` | Move the `details` dict construction in `recovery.py:255-271` behind a public helper exported from `forge.adapters.nats.approval_publisher`. Restores AC-008 single-ownership. Independent of F008-VAL-003 — parallel-safe. |
| F008-VAL-005  | high → low | implement-now (re-classified) | forge | 1 | `TASK-F8-005-update-idempotency-test-for-v2` | **Re-classified.** The migration code IS idempotent; the test is stale. One-line update: `assert rows == [(i,) for i in range(1, migrations._SCHEMA_VERSION + 1)]`. Add a comment explaining the assertion grows with `_SCHEMA_VERSION`. |
| F008-VAL-006  | medium   | implement-now   | forge                 | 2    | `TASK-F8-006-runbook-gap-fold-feat-008`  | Apply the nine "Suggested runbook fix" rows from `RESULTS-FEAT-FORGE-008-validation.md`. Required before Phase 6.4 (canonical-freeze) per LES1 §8. Pure docs task. |
| F008-VAL-007  | high     | **delegate**    | nats-infrastructure (NATS); forge (Dockerfile, but separate feature) | 3 | `TASK-F8-007a-nats-canonical-provisioning-handoff` (delegation note + tracking issue in nats-infrastructure) `TASK-F8-007b-forge-production-dockerfile-spec` (forge-internal scoping task — NOT the Dockerfile build, which is its own feature) | Does not block Step 6 canonical for Phases 0–3. Required for Phase 6 LES1 gates (CMDW/PORT/ARFS). Per Q4=delegate: NATS provisioning is owned by the `nats-infrastructure` repo (FLEET/JARVIS/NOTIFICATIONS streams + retentions reconciliation already known-pending per Graphiti); the production `Dockerfile` is its own scoped containerisation effort, recommended as a sibling FEAT-FORGE-009 (or similar) feature, not folded into F8. |

**Decision summary by AC**:

- **AC-1 ✓** — every F008-VAL-* item has a recorded decision (six implement-now, one delegated split).
- **AC-2 ✓** — six implementation tasks listed with the `parent_review: TASK-REV-F008` link convention; created on `[I]mplement` checkpoint below.
- **AC-3 ✓** — sequencing: Wave 1 → Phase 1 re-run gate → Wave 2 → Phase 1+2 re-run → Wave 3 (delegated, parallel-allowed).
- **AC-4 ✓** — F008-VAL-002 design decision recorded in §2 below; recommendation: **Option A (sibling `task_id`)**.
- **AC-5 ✓** — F008-VAL-007 split: NATS → nats-infrastructure (delegated); Dockerfile → recommend sibling forge feature, not F8 fan-out.
- **AC-6 ✓** — go/no-go gate after Wave 1: re-run Phase 1 only; if green, proceed to Wave 2. See §3.
- **AC-7 ✓** — runbook gap-fold scheduled in Wave 2 as `TASK-F8-006`, with the explicit note that Phase 6.4 (canonical-freeze) cannot pass until it lands.

---

## 2. F008-VAL-002 design decision: Mode C wire-payload identifier

### Problem statement

`nats_core.events._pipeline.BuildQueuedPayload.feature_id` validates against `^FEAT-[A-Z0-9]{3,12}$`. The forge CLI's `validate_feature_id` (per RESULTS §2.x) is more permissive and accepts `TASK-*` for Mode C, per FEAT-FORGE-008 ASSUM-004's intent ("Mode C operates on `TASK-*` IDs"). Result: Mode C is half-shipped — the CLI accepts `forge queue --mode c TASK-XXX`, but the JetStream wire layer rejects the payload at publish time.

### What ASSUM-004 actually says vs. how the codebase encodes it

`stage_taxonomy.py:35-36` cites `FEAT-FORGE-008 ASSUM-004 — Mode C chain (/task-review + /task-work cycle)` and the `STAGE_PREREQUISITES` map encodes `TASK_WORK ← TASK_REVIEW`. The taxonomy treats `TASK-*` as a **per-fix-task** sub-identifier; `PER_FIX_TASK_STAGES = {TASK_WORK}` is the declarative tag. The supervisor's multi-feature `next_turn` (supervisor.py:1296-1331) routes `TASK_REVIEW`/`TASK_WORK` through the `subprocess_dispatcher` with the `choice.feature_id` (a `FEAT-*`) — i.e., **the build's identity is still feature-scoped; the task is a sub-identifier inside that feature**.

This is the load-bearing observation: **Mode C builds are still per-feature builds** (the topic `pipeline.build-queued.<feature_id>` is per-feature; the constitutional gate at the end is per-feature). The fix-task identifier is a **dispatch-target sub-id**, not a replacement for `feature_id`.

If the operator's mental model from the runbook was "Mode C should accept `TASK-XXX` as the build's primary id", that mental model conflicts with the taxonomy. The runbook copy was wrong, not the wire schema.

### Three options weighed

#### Option A — keep `feature_id` strict, add sibling `task_id: str \| None` (RECOMMENDED)

**Change site**: `nats-core` (sibling repo), additive to `BuildQueuedPayload`.

```python
task_id: str | None = Field(
    default=None,
    description=(
        "Mode C: per-fix-task identifier (TASK-XXX). MUST be set when "
        "the build is dispatched in Mode C. None for Mode A and Mode B."
    ),
)

@field_validator("task_id")
@classmethod
def _validate_task_id(cls, v: str | None) -> str | None:
    if v is None:
        return v
    if not TASK_ID_PATTERN.match(v):  # ^TASK-[A-Z0-9]{3,12}$
        raise ValueError(f"task_id must match {TASK_ID_PATTERN.pattern}, got {v!r}")
    return v
```

Plus a `mode` field or a model-validator that requires `task_id is not None` when the build is Mode C. (The current payload doesn't carry `mode` — it's persisted on the `builds` row at consume time; we'd add a `mode: Literal["mode-a","mode-b","mode-c"]` field for symmetry with the v2 SQLite column.)

**Forge side**: CLI `forge queue --mode c TASK-XXX` looks up the parent FEAT- via the task's `parent_feature` field in `forge.yaml` / the task YAML, then emits `feature_id=<parent FEAT->`, `task_id=<TASK->`, `mode=mode-c`.

**Pros**:
- Encodes ASSUM-004 honestly: Mode C dispatches against feature-scoped builds with a per-task sub-id.
- Topic stays `pipeline.build-queued.<FEAT-*>` — JetStream subject hierarchy unchanged.
- Additive change to `BuildQueuedPayload` — no breaking change for Mode A/B publishers (they leave `task_id=None`).
- Mirrors the v2 SQLite `builds.mode` column already shipped in F008.
- Cross-repo cost is bounded: nats-core 0.3.0 (additive minor), forge updates the CLI Mode C path to look up parent feature.

**Cons**:
- Requires a nats-core release (sibling repo) before the fix can be smoke-tested in forge — Wave 2 has a cross-repo dependency.
- Adds a CLI lookup step (TASK-XXX → parent FEAT-XXX). Operator UX: needs the task YAML to be discoverable.

#### Option B — widen `feature_id` regex AND rename `feature_id` → `subject_id`

**Change site**: nats-core (sibling repo), breaking change to `BuildQueuedPayload` v2.2 contract.

**Pros**:
- Most semantically clean — `subject_id` matches the JetStream "subject" terminology and avoids the FEAT/TASK overload.

**Cons**:
- Breaking rename across nats-core 0.3.0 (or 1.0.0). All consumers (forge, jarvis, dashboards) re-pin and re-deploy.
- Topic semantics get fuzzy: `pipeline.build-queued.<TASK-*>` for Mode C breaks the per-feature subject convention — durable consumer subscriptions (forge, jarvis) need to widen their subscribe filter from `pipeline.build-queued.FEAT-*` to `pipeline.build-queued.>`. That widens the consumer's accept-set without solving anything Option A doesn't.
- Disagrees with `stage_taxonomy.py`'s framing (Mode C = sub-id under per-feature build).
- Reverses a deliberate v2.2 design decision (per nats-core ADR-002 / TASK-7448 review).

#### Option C — widen `feature_id` regex to accept TASK-* but keep field name (CHEAPEST)

**Change site**: nats-core, single regex edit.

**Pros**:
- Smallest change. Mode C green in one line.

**Cons** (per Q2=Q quality/correctness, this is disqualifying):
- Field name lies — `feature_id` carrying a `TASK-*` value is a documented contract violation. The very test class that catches FEAT/TASK confusion in worktree paths (graph: ADR-FB-002) exists because this has burned the codebase before.
- No path forward: once `feature_id` carries `TASK-*` values, removing the wide regex later is itself breaking. We bake in technical debt.
- The taxonomy says Mode C is feature-scoped; this option encodes the opposite.

### Recommendation

**Adopt Option A (sibling `task_id` field + Mode-C-conditional validator)**, with `mode: Literal[...]` added to `BuildQueuedPayload` for symmetry with the SQLite `builds.mode` column.

Cross-repo coordination plan (per Q2=Q):
1. File a nats-core PR adding `task_id` and `mode` fields with validators, additive (no breaking changes for Mode A/B publishers). Target nats-core 0.3.0.
2. Pin forge to nats-core>=0.3.0 in `pyproject.toml`'s `[tool.uv.sources]` block.
3. Update `forge queue --mode c` CLI path to populate `task_id`, look up parent `feature_id` from the fix-task YAML.
4. Add a regression test in forge: `test_mode_c_queue_emits_task_id_and_parent_feature_id`.
5. Add an integration test in nats-core: `test_build_queued_payload_rejects_task_id_without_mode_c`.

This becomes `TASK-F8-002-mode-c-task-id-payload`, with a sub-link to a nats-core issue/PR.

---

## 3. Re-run plan

Sequenced phases, after each wave lands:

### After Wave 1 (F008-VAL-003 + F008-VAL-004 + F008-VAL-005)

**AC-6 GO/NO-GO GATE** — run Phase 1 ONLY:

```bash
# from forge repo, on a branch that has the three Wave 1 fixes merged
pytest -q                                                              # Phase 1.1 — full sweep
pytest -q tests/bdd/                                                   # Phase 1.2 — BDD-008 (already 64/64)
pytest -q tests/integration/test_mode_a_concurrency_and_integrity.py   # Phase 1.3 — Mode A regression guard
pytest -q tests/forge/adapters/test_sqlite_persistence.py              # Phase 1.x — migrations idempotency
pytest -q tests/forge/test_approval_publisher.py                       # Phase 1.x — AC-008 single-ownership
```

Pass criteria: zero red, zero collection errors except `tests/bdd/test_infrastructure_coordination.py` (still ignored until Wave 2 lands TASK-IC-009/010).

**GO** if all five commands green → proceed to Wave 2.
**NO-GO** if any are red → triage as a sub-finding under `TASK-REV-F008` before moving on. Do NOT attempt Phase 2 with red Phase 1.

### After Wave 2 (F008-VAL-001 + F008-VAL-002 + F008-VAL-006)

Re-run Phases 1 + 2 + 3:
- Phase 1 — full sweep, NO `--ignore` flag (TASK-IC-009/010 has landed; F008-VAL-001 closed).
- Phase 2.5 — `forge queue --mode c TASK-XXX` round-trip with the new sibling `task_id` field. Verify:
  - CLI emits `feature_id=<parent FEAT->`, `task_id=<TASK->`, `mode=mode-c`.
  - `nats sub 'pipeline.build-queued.>'` shows the envelope.
  - `forge history --mode c` shows the row.
- Phase 2.x — verify the runbook now executes verbatim (no manual edits). This is the LES1 §8 "runbook is the contract" guard.
- Phase 3.x — NATS round-trip retains threaded correlation_id (already green; just smoke).

**GO** if green → Step 6 declared canonical for Phases 0–3. Wave 3 work continues in parallel.

### After Wave 3 (F008-VAL-007 — delegated)

Once nats-infrastructure has provisioned canonical JetStream + the forge production Dockerfile feature lands:
- Phase 4 — checkpoint / degraded-mode (was deferred per §1.3 hard-stop; now runnable).
- Phase 5 — TBD per build plan.
- Phase 6 — LES1 CMDW / PORT / ARFS / canonical-freeze.

Phase 6.4 canonical-freeze walkthrough cannot pass until F008-VAL-006 (runbook gap-fold) is committed AND Wave 3 prerequisites are in place.

---

## 4. Phase 6 prerequisite plan (delegated track)

Per Q4=delegate, F008-VAL-007 splits into two independent owners:

### NATS canonical provisioning → `nats-infrastructure` repo

**Scope**: persistent JetStream service on the GB10 host (`promaxgb10-41b1`) with the canonical streams + KV stores forge needs (`pipeline.>`, `agents.>`, durable consumers per the `nats-core` topology).

**Why delegate**: Graphiti shows `nats-infrastructure` is "READY today" but with FLEET/JARVIS/NOTIFICATIONS streams + retentions still needing reconciliation against the v2.1 anchor. That reconciliation is the canonical owner's work, not forge's.

**Deliverable from forge**: `TASK-F8-007a-nats-canonical-provisioning-handoff` — a one-page handoff doc in `nats-infrastructure` (cross-repo issue) listing exactly which streams, subjects, retentions, and KV buckets forge needs in production. Forge does NOT own the provisioning; forge owns the spec of what it requires.

**Sequencing**: independent of Wave 1+2. Schedulable now.

### Production Dockerfile → sibling feature, NOT F8 fan-out

**Scope**: a `Dockerfile` at the forge repo root that builds a runnable forge image meeting LES1 CMDW (canonical multi-stage docker), PORT (port matrix), ARFS (artefact registry filesystem) gate criteria.

**Why a sibling feature, not an F8 task**: The Dockerfile is a substantial piece of work — multi-stage build, deps audit, CI integration, smoke-image testing — and the LES1 gates have their own structural assumptions that are independent of F008's Mode A/B/C concerns. Folding it into F8 would inflate the F8 scope and tie its review/merge cycle to a DevOps-shaped problem.

**Deliverable from this review**: `TASK-F8-007b-forge-production-dockerfile-spec` — a scoping task that (a) enumerates the LES1 Phase-6 gate requirements, (b) drafts a feature spec for `FEAT-FORGE-009-production-image` (or similar), and (c) hands off to `/feature-spec` + `/feature-plan` for that new feature. The Dockerfile build itself is then its own autobuild-able feature.

**Sequencing**: scoping task can run in parallel with Wave 1+2; the new feature's autobuild happens after Step 6 canonical for Phases 0–3.

---

## 5. Runbook gap-fold patch outline (F008-VAL-006)

These are the edits to apply to `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` so the next walkthrough runs verbatim. Pulled from RESULTS §"Runbook gaps discovered during execution":

### Phase 0 (environment)

- **§0.4** — Pin to `uv pip install -e ".[providers,dev]"` (NOT plain `pip`). Add an explicit "install `uv` first" step. Document the `--break-system-packages` fallback for non-uv flow on PEP 668 hosts (Ubuntu 24.04). Add the stale-editable-install rewire trick: `pip install --user --force-reinstall --no-deps -e .` when an editable install points to a deleted worktree (the FEAT-FORGE-005 trap).
- **§0.5** — Add `~/.local/bin` PATH check after `pip install --user`.
- **§0.6** — Document the throwaway-NATS-via-docker hint: `docker run -d --network host nats:latest -js` for Phases 2–3 only. Link out to the canonical `nats-infrastructure` provisioning runbook for Phases 4+. Mark Phase 4+ as still requiring the *provisioned* server.

### Phase 1 (test sweep)

- **§1.1** — Footnote: `--ignore=tests/bdd/test_infrastructure_coordination.py` until F008-VAL-001 (TASK-IC-009/010) lands. Once Wave 2 is in, drop the `--ignore`.
- **§1.3** — Drop the non-existent `tests/bdd/test_feat_forge_007.py` path. The repo has `features/mode-a-greenfield-end-to-end/` but no Mode A BDD bindings module. Either remove the path OR file a separate task to write the missing FEAT-FORGE-007 BDD bindings — recommend the former for now.

### Phase 2 (CLI smoke)

- **§2.1+** — Replace `--db-path "$FORGE_HOME/forge.db"` on `forge queue` with `export FORGE_DB_PATH="$FORGE_HOME/forge.db"` once at the top of Phase 2.1. Use actual flag names per command: `forge queue` reads env, `forge history` uses `--db` (NOT `--db-path`), `forge status` uses `--db-path`.
- **§2.1** — Show how to write a minimal `forge.yaml`. Only required field: `permissions.filesystem.allowlist`. Pass via `--config FILE` flag or via `./forge.yaml` in CWD.
- **§2.1** — Show how to write a per-feature stub YAML and pass it via `--feature-yaml FILE`.
- **§2.1** — Remove the false claim that "Phase 2 stubs NATS via the integration adapter". `forge queue` always tries to publish to `$FORGE_NATS_URL` (default `nats://127.0.0.1:4222`). There is no fake-mode env switch in `src/forge/cli/queue.py:_publish_once`. Either start a local NATS or skip Phase 2 NATS-dependent gates.
- **§2.x** — Change example IDs to `FEAT-TESTMA` / `FEAT-TESTMB` / `FEAT-TESTMC` (no inner hyphens; valid per the wire regex `^FEAT-[A-Z0-9]{3,12}$`). Note the F008-VAL-002 fix lands a sibling `task_id` field for Mode C — once it lands, update §2.5 to show `forge queue --mode c TASK-TESTMC` populating `feature_id=<parent FEAT-->` plus `task_id=<TASK->`.

### Phase 6 (LES1)

- **§6.1** — Drop the runbook claim that Phase 6 can run today, OR gate the section behind "F008-VAL-007b complete (`Dockerfile` exists)". Recommend the gate framing — Phase 6 belongs in the runbook, but it's currently structurally unreachable.

### Cross-cutting

- Add a one-line note at the top of the runbook clarifying that on `promaxgb10-41b1`, `/etc/hosts` maps it to `127.0.0.1` — so "Local" and "GB10" phases of the runbook are the same machine on this workstation. Saves the next operator ~30 min.

---

## 6. Architecture assessment (SOLID/DRY/YAGNI)

### Findings against principles

**Open/Closed (F008-VAL-003 — supervisor dispatch)**: When `StageClass.TASK_REVIEW` and `TASK_WORK` were appended to the enum (TASK-MBC8-001), `_SUBPROCESS_STAGES` (supervisor.py:618-625) was not extended. The dispatcher's four-branch routing (specialist / subprocess / autobuild / pull-request-review) is a closed set; the enum was extended without correspondingly extending the closed set. Result: a clean hard-fail at line 1555 (`raise TypeError`) — the loud-failure is good engineering (the runbook §1.3 hard-stop relies on it), the missing branch is the bug. Score: −5 — the failure mode worked exactly as designed; the missing extension is a 1-line oversight.

**Single Responsibility / Single Ownership (F008-VAL-004 — recovery.py)**: AC-008 is a structural rule that says *only* `forge.adapters.nats.approval_publisher` constructs the eleven-key `details` dict shape. The structural test `test_no_other_module_in_forge_constructs_evidence_priors` is a static text-grep guard at `tests/forge/test_approval_publisher.py:492-510`. `recovery.py:255-271` open-codes the dict shape inline — including the literal `"evidence_priors"` key. This is exactly the failure class the guard exists to prevent. Score: −8 — the violation slipped past code review even though the guard test catches it; the recovery code should import and reuse `_build_approval_details` (or its public counterpart) from `approval_publisher`. Either:
- Export a public helper from `forge.adapters.nats.approval_publisher` (e.g. `build_recovery_approval_details()`), and have `recovery.py` import it. OR
- Move `_build_recovery_approval_envelope` itself into the `approval_publisher` module. Recovery already imports `nats_core.envelope` lazily — the recovery-flavoured details builder is a sibling concern to the approval_publisher's main details builder.

Recommendation: the second option (move the helper) is cleaner — keeps the dict shape under one roof and makes the "recovery flag" a parameter to a single helper rather than two near-duplicate constructors.

**Contract correctness at system boundary (F008-VAL-002 — Mode C wire-payload)**: The CLI surface and the wire schema disagree on what `feature_id` accepts. CLI's `validate_feature_id` is permissive; `BuildQueuedPayload` regex is strict. The discrepancy survived the tests because no test crossed the boundary in Mode C with a `TASK-*` input (the BDD bindings use `FEAT-*` examples). Score: −10 — the half-shipped boundary is the most architecturally significant defect in this batch. The fix (Option A) restores boundary integrity by adding the missing typed field.

**Don't-Repeat-Yourself (F008-VAL-005 — stale test)**: Not a violation; the test assertion failed to track schema-version growth. Recommend a parameterised assertion `[(i,) for i in range(1, _SCHEMA_VERSION + 1)]` so the test grows automatically with future schema bumps. Score: −2 — the test should self-update from `_SCHEMA_VERSION`, but the current absolute-list pattern is a benign tech-debt issue that future migration bumps will surface again.

**YAGNI (no violations identified)** — none of the seven findings represent over-engineering. The Mode A/B/C taxonomy and `PER_FIX_TASK_STAGES` set are deliberately additive and well-bounded (only `TASK_WORK` is in the per-fix-task set; `TASK_REVIEW` runs once per cycle). The cycle planner's responsibility separation (`ModeCCyclePlanner` owns fan-out, not the enum) is a clean SRP split. Score: 0 (good).

### Pattern observations

- **`@dataclass` + injected dispatcher protocol** (`Supervisor` lines 564–588) — clean DI. Adding TASK_REVIEW/TASK_WORK to `_SUBPROCESS_STAGES` is the right shape because the existing subprocess_dispatcher is an injectable protocol; per-fix-task semantics live above this layer in `ModeCCyclePlanner`.
- **Frozenset declarative tags for stage classes** (`stage_taxonomy.py:138-171`) — `CONSTITUTIONAL_STAGES`, `PER_FEATURE_STAGES`, `PER_FIX_TASK_STAGES` form a small, stable set of declarative properties consumed by the supervisor and ordering guard. The pattern scales and the F8 work doesn't disturb it.
- **Boot-time idempotent migration runner** (`migrations.apply_at_boot`) — uses `_current_version` ledger + `INSERT OR IGNORE`. Genuinely idempotent. The schema_v2.sql comment on `ALTER TABLE ... ADD COLUMN` not being IF-NOT-EXISTS-aware is precisely the right concern surface.

### Knowledge graph context used

- **ADR-FB-002 (FEAT-XXX vs TASK-XXX worktree path rule)** — directly informed the F008-VAL-002 design decision against widening the `feature_id` regex. The codebase has prior incidents from FEAT/TASK identifier conflation at path boundaries; the wire-payload boundary should not repeat the pattern.
- **nats-core missing-payloads context (BuildQueuedPayload, BuildPaused, BuildResumed, StageComplete, StageGated)** — informed the recommendation that nats-core 0.3.0 is the right release vehicle for the additive `task_id` field.
- **LES1 lineage (TASK-REV-LES1 ← TASK-REV-32D2 / TASK-REV-4F71)** + **DGX Spark runbook-fix-during-deploy 2026-04-28** — directly support F008-VAL-006's framing that runbooks are code; both prior incidents establish that operators discovering broken runbooks at execution time IS the LES1 §8 failure mode and the gap-fold is a first-class deliverable.
- **forge-pipeline-orchestrator-refresh.md v2.1 anchor** — confirms `nats-infrastructure` ownership of FLEET/JARVIS/NOTIFICATIONS reconciliation, supporting F008-VAL-007's NATS delegation.
- **No graph context found for**: F008-VAL-001 (TASK-IC-009/010), F008-VAL-003 (Supervisor.\_dispatch routing), F008-VAL-004 (AC-008 / evidence\_priors / FEAT-FORGE-004), F008-VAL-005 (apply\_at\_boot specifically). These reflect implementation-detail gaps rather than architectural decisions; the absence is expected.

---

## 7. Recommendations (ordered by effect)

1. **F008-VAL-003 → land first** (Wave 1). Single-line fix to `_SUBPROCESS_STAGES`. Unblocks Phase 1.3 hard-stop. Add a regression test asserting every `StageClass` member has a routing branch (so a future enum extension fails at test-time, not at runtime).
2. **F008-VAL-005 → land first** (Wave 1, parallel with #1). Test-only update; parameterise on `migrations._SCHEMA_VERSION`.
3. **F008-VAL-004 → land first** (Wave 1, parallel with #1 and #2). Move `_build_recovery_approval_envelope` into the `approval_publisher` module and re-export. Restores AC-008.
4. **GATE — re-run Phase 1.** AC-6 go/no-go decision. If green, proceed.
5. **F008-VAL-002 → land second** (Wave 2). Cross-repo: nats-core 0.3.0 adds `task_id` + `mode` fields (Option A), then forge updates the Mode C CLI path. Restores boundary integrity.
6. **F008-VAL-001 → land second** (Wave 2, parallel with #5). Land `forge.build.git_operations` and `forge.build.test_verification`. Drops the `--ignore` from runbook §1.1.
7. **F008-VAL-006 → land second** (Wave 2, parallel with #5 and #6). Pure-docs runbook gap-fold per §5 above. Required for Phase 6.4.
8. **F008-VAL-007 → delegate in parallel** (Wave 3, no blocking dependency on Waves 1/2). Two handoffs: a NATS-provisioning spec to `nats-infrastructure`, and a forge production-Dockerfile feature scoping task that becomes its own feature spec (not an F8 fan-out task).

---

## 8. Decision matrix

| Option              | Score | Effort      | Risk                            | Recommendation        |
|---------------------|-------|-------------|---------------------------------|-----------------------|
| Accept findings as-is | 6/10 | none       | none                            | partial — re-classify F008-VAL-005 |
| Implement fan-out (Waves 1+2 in forge; Wave 3 delegated) | **9/10** | medium | low (Wave 1 is small + well-isolated) | **RECOMMENDED — proceed via [I]mplement** |
| Defer F008-VAL-002 (Mode C wire) | 5/10 | low (skip nats-core PR) | high (Mode C remains half-shipped; tech debt accrues) | not recommended |
| Defer F008-VAL-006 (runbook gap-fold) | 6/10 | low | high (Phase 6.4 canonical-freeze blocked indefinitely) | not recommended |
| Fold F008-VAL-007b (Dockerfile) into F8 | 6/10 | high | medium (scope creep) | not recommended — recommend sibling FEAT-FORGE-009 |

---

## 9. Decision checkpoint

The reviewer recommends **[I]mplement** with the following fan-out (six F8 tasks + two delegated handoffs):

**Wave 1 (parallel-safe, all in forge)**:
- `TASK-F8-003-supervisor-dispatch-task-review`
- `TASK-F8-004-recovery-evidence-priors-helper`
- `TASK-F8-005-update-idempotency-test-for-v2`

**AC-6 GATE — re-run Phase 1.**

**Wave 2 (parallel-safe within forge; F008-VAL-002 has cross-repo dep on nats-core)**:
- `TASK-F8-002-mode-c-task-id-payload` (forge + nats-core)
- `TASK-F8-001-land-forge-build-modules`
- `TASK-F8-006-runbook-gap-fold-feat-008`

**Wave 3 (delegated, parallel-allowed throughout)**:
- `TASK-F8-007a-nats-canonical-provisioning-handoff` (handoff to `nats-infrastructure`)
- `TASK-F8-007b-forge-production-dockerfile-spec` (scoping task → spawns a new sibling feature, NOT an F8 fan-out)

All tasks link back via `parent_review: TASK-REV-F008` and `feature_id: FEAT-F8-VALIDATION-FIXES` (or whatever feature-id the implementer assigns at fan-out time).
