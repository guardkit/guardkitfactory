---
id: TASK-FIX-DEA8-001
title: "Drop tests/cli from FEAT-DEA8 smoke_gates.command (Layer 1 fix from TASK-REV-DEA8)"
status: in_review
created: 2026-05-02T13:30:00Z
updated: 2026-05-02T13:30:00Z
priority: high
task_type: fix
implementation_mode: direct
tags:
  - autobuild
  - smoke-gate
  - feature-spec
  - quick-fix
  - FEAT-DEA8
  - feat-forge-010-followup
  - review-implementation
complexity: 1
estimated_minutes: 5
parent_review: TASK-REV-DEA8
parent_feature: FEAT-DEA8
related_tasks:
  - TASK-REV-DEA8        # the decision-mode review that selected this fix
  - TASK-FW10-001        # Wave 1 task; sound, do not re-run
context_files:
  - .guardkit/features/FEAT-DEA8.yaml
  - .guardkit/worktrees/FEAT-DEA8/                 # preserved worktree, gate verified inside it
  - .claude/reviews/TASK-REV-DEA8-review-report.md
  - docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md
test_results:
  status: passed
  last_run: 2026-05-02T13:30:00Z
  passed: 434
  failed: 0
  duration_seconds: 2.95
---

# Task: Drop `tests/cli` from FEAT-DEA8 `smoke_gates.command`

## Description

Layer 1 of the fix bundle selected by **TASK-REV-DEA8** (full diagnosis
in [.claude/reviews/TASK-REV-DEA8-review-report.md](../../.claude/reviews/TASK-REV-DEA8-review-report.md)).

The smoke gate command in
[.guardkit/features/FEAT-DEA8.yaml](../../.guardkit/features/FEAT-DEA8.yaml)
listed `tests/cli tests/forge` as positional pytest arguments, but
`tests/cli/` does not exist in the forge repository (it is a
guardkit-shaped path that the `/feature-plan` Plan agent invented and
hand-injected; see review §F3). pytest exited 4 ("file or directory
not found"), and the orchestrator treated the non-zero exit as a hard
fail, blocking the remaining 10 tasks of FEAT-DEA8.

This task drops `tests/cli` from the gate command so `--resume`
proceeds.

## Acceptance Criteria

- [x] **Edit applied.** `.guardkit/features/FEAT-DEA8.yaml`
      `smoke_gates.command` now reads:
      `set -e\npytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"\n`
      (no `tests/cli`).
- [x] **YAML still parses.** Verified via
      `python3 -c "import yaml; yaml.safe_load(open('.guardkit/features/FEAT-DEA8.yaml'))"`.
- [x] **Gate runs green from the worktree.** Verbatim command from
      [.guardkit/worktrees/FEAT-DEA8/](../../.guardkit/worktrees/FEAT-DEA8/):
      ```
      cd .guardkit/worktrees/FEAT-DEA8
      set -e
      pytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
      ```
      → **434 passed, 1590 deselected, 0 failed, exit 0, 2.95 s**.
- [ ] **Resume succeeds to ≥ Wave 2.** Run
      `guardkit autobuild feature FEAT-DEA8 --resume` and verify the
      orchestrator reaches at least Wave 2 without the prior exit-4
      smoke-gate failure. Full feature green is **not** a precondition
      of this task; only that the smoke-gate defect is gone.

## Test Requirements

- [x] Worktree gate command exits 0 with ≥1 test selected. Verified.
- [ ] `--resume` orchestration starts Wave 2 tasks (per the wave plan in
      [.guardkit/features/FEAT-DEA8.yaml](../../.guardkit/features/FEAT-DEA8.yaml)
      `orchestration.parallel_groups[1]` =
      `[TASK-FW10-002, TASK-FW10-003, TASK-FW10-004, TASK-FW10-005, TASK-FW10-006]`).

## Implementation Notes

- **Do NOT re-run TASK-FW10-001.** It was Coach-approved on turn 1
  (run-2 transcript line 230, checkpoint `628a4f81`). The four
  task-written tests
  (`tests/forge/test_cli_serve_daemon.py`,
  `test_cli_serve_logging.py`, `test_cli_serve_skeleton.py`,
  `test_serve_healthz.py`) are part of the 434 passing tests above.
- **Use `--resume`, not `--fresh`.** Preserves the TASK-FW10-001
  checkpoint, the bootstrapped venv, and 17 minutes of SDK work.
- **Edit lives in the main repo's feature spec, not the worktree.**
  The orchestrator loads
  `/Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/features/FEAT-DEA8.yaml`
  (run-2 transcript line 15), then runs `smoke_gates.command` with the
  worktree as cwd.
- **Do not edit any other field of the YAML.** `smoke_gates.after_wave`,
  `expected_exit`, `timeout`, `exit5_is_hard_fail`, the task list, the
  orchestration `parallel_groups`, and the execution metadata all
  remain unchanged.

## Cross-Repo Follow-Ups (out of scope here)

This task is the forge half of TASK-REV-DEA8's decision. The guardkit
half — preventing the same `/feature-plan`-emitted-stale-path bug from
reappearing on the next forge feature — is captured in:

- `appmilla_github/guardkit/tasks/backlog/feature-plan-smoke-gate-validation/`
  (5 subtasks: L3a, L3b, L3c, L3d, L4)

Those edits land in the guardkit repo via its own task workflow and
are explicitly **out of scope** for this task per TASK-REV-DEA8's
"Boundary check" note.

## Test Execution Log

```
$ cd /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8
$ set -e
$ pytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
... 434 passed, 1590 deselected, 4 warnings in 2.95s ...
EXIT_CODE=0
```

(Full output saved to `/tmp/dea8_gate_verify.txt` during the
implementation session.)
