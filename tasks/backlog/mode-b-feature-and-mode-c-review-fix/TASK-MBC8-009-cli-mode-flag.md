---
id: TASK-MBC8-009
title: Add forge queue --mode {a|b|c} CLI surface and mode-aware queue picker
task_type: feature
status: in_review
priority: high
created: 2026-04-27 00:00:00+00:00
updated: 2026-04-27 00:00:00+00:00
parent_review: TASK-REV-MBC8
feature_id: FEAT-FORGE-008
wave: 5
implementation_mode: task-work
complexity: 4
dependencies:
- TASK-MBC8-008
tags:
- cli
- queue
- mode-b
- mode-c
- feat-forge-008
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 2
  max_turns: 30
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-008
  base_branch: main
  started_at: '2026-04-27T19:09:24.789105'
  last_updated: '2026-04-27T19:38:52.097037'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Advisory (non-blocking): task-work produced a report with 2 of 3\
      \ expected agent invocations. Missing phases: 3 (Implementation). Consider invoking\
      \ these agents via the Task tool to strengthen stack-specific quality:\n- Phase\
      \ 3: `python-api-specialist` (Implementation)\n- Not all acceptance criteria\
      \ met:\n  \u2022 `forge queue` accepts `--mode {a|b|c}` (default `a` for backwards\n\
      \  \u2022 `forge queue --mode b <FEAT-ID>` requires exactly one feature\n  \u2022\
      \ `forge queue --mode c <SUBJECT-ID>` accepts a subject identifier (e.g.\n \
      \ \u2022 `forge status` displays the mode column (default-rendered as `mode-a`\n\
      \  \u2022 `forge history --mode b` and `--mode c` filter the history view by\n\
      \  (5 more)"
    timestamp: '2026-04-27T19:09:24.789105'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-04-27T19:29:32.735371'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: Add forge queue --mode {a|b|c} CLI surface and mode-aware queue picker

## Description

Expose `BuildMode` on the `forge queue` CLI so operators must explicitly opt
into Mode B or Mode C (ASSUM-016: each queued build is its own lifecycle).
Implicit mode detection from inputs is rejected — explicit operator intent is
the only reliable signal that distinguishes "follow-up feature on a built
project" (Mode B) from "fresh greenfield run" (Mode A).

The queue picker must round-trip the mode through the SQLite layer so crash
recovery (FEAT-FORGE-001) and the supervisor wiring from TASK-MBC8-008 see the
correct mode after a restart.

## Acceptance Criteria

- [ ] `forge queue` accepts `--mode {a|b|c}` (default `a` for backwards
      compatibility); the mode is mapped to `BuildMode` and persisted on the
      `Build` row via `SqliteLifecyclePersistence.queue_build`
- [ ] `forge queue --mode b <FEAT-ID>` requires exactly one feature
      identifier and rejects multi-feature inputs at parse time (ASSUM-006:
      single feature per Mode B build)
- [ ] `forge queue --mode c <SUBJECT-ID>` accepts a subject identifier (e.g.
      task ID or PR ID) and persists it via the existing build feature-id
      column (subject is feature-id-shaped per the existing schema)
- [ ] `forge status` displays the mode column (default-rendered as `mode-a`
      for legacy rows) so the operator can disambiguate concurrent builds
      (Group F scenarios)
- [ ] `forge history --mode b` and `--mode c` filter the history view by
      mode; default is no filter
- [ ] Queue picker (`SqliteLifecyclePersistence.pick_next_pending`) returns
      builds in their original FIFO order regardless of mode; no mode-based
      priority (every build is its own lifecycle)
- [ ] Constitutional gate cannot be bypassed by mode flag (Group E "skip
      refused at PR review"); `forge skip` against a `PULL_REQUEST_REVIEW`
      pause is refused with constitutional rationale in every mode
- [ ] Help text for `--mode` references the FEAT-FORGE-008 chain shapes
      verbatim so operators do not need to read source code to choose
- [ ] Unit tests cover the CLI surface; smoke tests in TASK-MBC8-010 and
      TASK-MBC8-011 will exercise the end-to-end queue → terminal flow
- [ ] All modified files pass project-configured lint/format checks with zero
      errors

## Implementation Notes

`--mode a` is the default so existing callers (test fixtures, scripts) keep
working unchanged.

Validation that Mode B is single-feature happens at the CLI parser, not the
persistence layer — if the schema accepts multi-feature input later (e.g. for
Mode A-style catalogue iteration), Mode B will still reject it.

Do not add an `auto` mode that detects mode from project state. Detection
heuristics are a future feature with their own risk profile.

## Test Execution Log

[Automatically populated by /task-work]
