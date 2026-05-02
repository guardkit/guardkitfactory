---
id: TASK-REV-DEA8
title: "Diagnose & fix FEAT-DEA8 autobuild smoke-gate failure (run 2)"
status: completed
completed: 2026-05-02T13:30:00Z
previous_state: review_complete
completed_location: tasks/completed/TASK-REV-DEA8/
implementation_tasks:
  forge:
    - TASK-FIX-DEA8-001  # Layer 1 — applied + verified (in_review pending --resume)
  guardkit:
    - feature-plan-smoke-gate-validation/TASK-FPSG-001  # L3a
    - feature-plan-smoke-gate-validation/TASK-FPSG-002  # L3b
    - feature-plan-smoke-gate-validation/TASK-FPSG-003  # L3c
    - feature-plan-smoke-gate-validation/TASK-FPSG-004  # L3d
    - feature-plan-smoke-gate-validation/TASK-FPSG-005  # L4
created: 2026-05-02T00:00:00Z
updated: 2026-05-02T13:30:00Z
priority: high
task_type: review
review_mode: decision
review_depth: standard
tags: [review, autobuild, smoke-gate, pytest-exit-4, feature-spec, FEAT-DEA8, forge-serve-orchestrator-wiring]
complexity: 5
feature_id: FEAT-DEA8
related_tasks:
  - TASK-FW10-001  # Wave 1 task; succeeded + Coach-approved before the gate failed
  - TASK-FW10-002  # First of 10 downstream tasks blocked by the failed smoke gate
context_files:
  - docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md
  - .guardkit/features/FEAT-DEA8.yaml
  - .guardkit/autobuild/FEAT-DEA8/review-summary.md
  - .guardkit/worktrees/FEAT-DEA8/                       # preserved worktree from the failed run
  - tasks/backlog/forge-serve-orchestrator-wiring/       # 11-task wave plan
review_results:
  mode: decision
  depth: standard
  revision: v2  # revised after user direction to fix /feature-plan + /generate-feature-yaml
  diagnosis_confirmed: true
  root_cause: "/feature-plan agent invented tests/cli/ paths in §6 and per-task notes (no path verification), then hand-injected the same paths into smoke_gates.command after generate-feature-yaml ran. generate-feature-yaml does not validate hand-injected smoke-gates; guardkit feature validate doesn't check smoke-gate paths and is unreachable from the installed wrapper. /feature-spec is innocent (Appendix C)."
  layer_decisions:
    L1_spec_fix: implement                       # forge, ship now
    L2_audit_other_specs: closed                 # only FEAT-DEA8 affected; audit done in F4
    L3a_feature_plan_prompt: implement_cross_repo  # require path verification
    L3b_generate_feature_yaml_validator: implement_cross_repo  # post-edit smoke-gate path validator + Step 8.6
    L3c_smoke_gates_nudge_grounding: implement_cross_repo  # inject actual tests/ subdirs into the nudge
    L3d_feature_validate_extension: implement_cross_repo  # extend validator + fix installed wrapper
    L4_feature_loader_preflight: implement_cross_repo  # pre-flight at load time (defense-in-depth)
    L5_exit4_softwarn: rejected                  # would silently mask path typos
  findings_count: 9
  recommendations_count: 3
  decision: refactor
  report_path: .claude/reviews/TASK-REV-DEA8-review-report.md
  completed_at: 2026-05-02T13:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Diagnose & fix FEAT-DEA8 autobuild smoke-gate failure (run 2)

## Description

Decision-mode review to analyse, diagnose, and select a fix for the
GuardKit autobuild orchestration failure observed on
**FEAT-DEA8 — "Wire the production pipeline orchestrator into forge serve"**,
Run 2, 2026-05-02. Full transcript:
[docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md](docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md).

### Symptom (verbatim)

Wave 1 — `TASK-FW10-001` — completed cleanly:

- Player implementation succeeded (53 SDK turns, 20 created / 14 modified, 4 tests passing).
- Coach validation **approved** on turn 1 (independent test rerun: 1.5s, all green).
- Worktree checkpoint created (`628a4f81`).

Immediately after wave 1, the orchestrator ran the configured smoke gate:

```
pytest tests/cli tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
```

…and the gate failed:

```
WARNING:guardkit.orchestrator.smoke_gates:Smoke gate failed after wave 1 (exit=4, expected=0)
✗ Smoke gate failed after wave 1 (exit=4, expected=0). Subsequent waves not started; worktree preserved.
```

Final feature status: **FAILED — 1/11 tasks completed**, the remaining 10
tasks (TASK-FW10-002 … TASK-FW10-011) never started.

### Initial root-cause hypothesis (to be confirmed by the review)

Reproducing the smoke-gate command inside the preserved worktree
(`.guardkit/worktrees/FEAT-DEA8`) yields:

```
ERROR: file or directory not found: tests/cli
collected 0 items
```

— pytest **exit code 4** = "command line usage error" (a path argument
does not exist). The forge repo's test tree is `tests/forge/` (plus a
small number of others), but **`tests/cli/` does not exist** in this
repo.

Three intersecting facts produce the failure:

1. **`.guardkit/features/FEAT-DEA8.yaml` `smoke_gates.command`** lists
   `tests/cli tests/forge` as positional pytest arguments (lines 1-9 of
   the `smoke_gates:` block).
2. The forge repository never had a `tests/cli/` directory — likely a
   stale path inherited from a feature-spec template / generator.
3. The smoke gate runs under `set -e` and treats any non-zero pytest
   exit as a hard fail (`expected_exit: 0`, with `exit5_is_hard_fail:
   false` already special-cased for "no tests collected" but **no
   carve-out for exit 4**).

Net effect: a single typo in the feature spec masquerades as a
production-code failure and bricks an otherwise-green feature run after
the very first wave.

## Acceptance Criteria

The review is complete when each item below has a documented decision +
recorded outcome (Accept / Implement / Revise / Cancel).

### A. Diagnosis confirmed

- [ ] Confirm pytest exit 4 is reproducible from
      `.guardkit/worktrees/FEAT-DEA8` with the exact gate command, and
      that removing `tests/cli` from the argv makes the gate green.
- [ ] Confirm `tests/cli/` is absent from `main` and from the worktree,
      and identify where the path was introduced (feature-spec
      generator? hand edit? template?).
- [ ] Confirm TASK-FW10-001's implementation itself is sound — i.e. the
      gate failure is a config defect, not a regression from the wave-1
      task. Cross-check Coach approval + the four task-written tests
      (`tests/forge/test_cli_serve_daemon.py`,
      `test_cli_serve_logging.py`, `test_cli_serve_skeleton.py`,
      `test_serve_healthz.py`).

### B. Fix layers selected (decision)

Pick one or more layers and justify the choice in the review report:

- [ ] **Layer 1 — Spec fix (immediate, ship-now):** edit
      `.guardkit/features/FEAT-DEA8.yaml` `smoke_gates.command` to drop
      `tests/cli` (or replace with the correct path if one exists) so
      `guardkit autobuild feature FEAT-DEA8 --resume` can proceed
      through waves 2–5.
- [ ] **Layer 2 — Audit other feature specs:** grep
      `.guardkit/features/*.yaml` for `tests/cli` (and other suspect
      stock paths) and patch any that reference non-existent
      directories.
- [ ] **Layer 3 — Generator / template fix:** if the bad path came from
      a feature-spec template or scaffolder, fix the source so future
      `feature-spec` runs cannot reintroduce it. (Cross-repo if it
      lives in guardkit; in-repo if it lives in forge.)
- [ ] **Layer 4 — Orchestrator robustness (optional):** evaluate
      whether `smoke_gates` should treat pytest exit 4 (and/or missing
      paths) the same way it already treats exit 5 — i.e. promote the
      existing `exit5_is_hard_fail: false` carve-out into a more
      general "config-shaped failure ≠ feature-killing failure"
      contract, or pre-flight-check that every path in the gate
      command exists before invoking pytest.

### C. Outcome recorded + downstream unblocked

- [ ] Layer 1 landed and verified by re-running the exact smoke-gate
      command from the worktree (exit 0, ≥1 test selected).
- [ ] `guardkit autobuild feature FEAT-DEA8 --resume` reaches **at
      least Wave 2** without the same exit-4 failure (full feature
      green is not a precondition of this review — only that the
      smoke-gate defect is gone).
- [ ] Decision report written to
      `.claude/reviews/TASK-REV-DEA8-review-report.md` listing chosen
      layers, rejected layers (with reasons), and any follow-up tasks
      created (Layer 2/3/4 may spawn separate `TASK-FIX-…` items).

## Test Requirements

This is a review/decision task — no production code is added by the
review itself. Test requirements apply to whichever fix layer(s) ship:

- [ ] **Layer 1 fix:** smoke-gate command, run from the preserved
      worktree, exits 0 and selects ≥1 test.
- [ ] **Layer 2 fix (if landed):** every `smoke_gates.command` path in
      `.guardkit/features/*.yaml` resolves to an existing directory at
      the time of the audit; capture the audit output in the report.
- [ ] **Layer 3 fix (if cross-repo):** spawn a follow-up task in the
      owning repo (do not stub a guardkit edit from this review).
- [ ] **Layer 4 fix (if landed):** add an orchestrator unit/contract
      test that demonstrates exit-4 (file-not-found) behaves
      identically to the existing exit-5 carve-out per whatever
      contract is chosen.

## Implementation Notes

- **Do not re-run TASK-FW10-001.** It was Coach-approved on turn 1; the
  worktree checkpoint (`628a4f81`) and `task_work_results.json` are the
  source of truth. Any re-run risks polluting them.
- **The 11-task wave plan is intact.** `forge-serve-orchestrator-wiring/`
  still contains the full task set; only TASK-FW10-001 has moved to
  `design_approved` inside the worktree. Waves 2–5 are still pending in
  `.guardkit/features/FEAT-DEA8.yaml`.
- **Resume vs. fresh.** Prefer `--resume` after the Layer 1 fix so the
  TASK-FW10-001 checkpoint and bootstrapped venv are reused; reserve
  `--fresh` for the case where the worktree itself is suspected.
- **Boundary check.** If Layer 3 turns out to live in
  `appmilla_github/guardkit/` (e.g. the feature-spec generator
  template), this review's deliverable is the **decision + cross-repo
  follow-up task**, not the cross-repo edit itself.

## Test Execution Log

[Automatically populated by `/task-review` and `/task-work`]
