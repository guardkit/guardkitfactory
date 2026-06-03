---
id: TASK-HMIG-007F
title: Close BDD plugin gaps — preflight glue/env checks + end-to-end C3/C4
status: completed
task_type: implementation
created: 2026-06-02T00:00:00Z
updated: 2026-06-03T00:00:00Z
completed: 2026-06-03T00:00:00Z
completed_location: tasks/completed/TASK-HMIG-007F/
previous_state: in_review
state_transition_reason: "All AC-001 — AC-008 satisfied; 87/87 fast tests pass; 2/2 slow tests pass against real pytest-bdd."
priority: high
complexity: 4
deadline: 2026-06-30
parent_review: TASK-REV-HMIG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 2
parallel_group: 2B
implementation_mode: task-work
intensity: strict
effort_hours: 4
depends_on:
  - TASK-HMIG-007
falsifier: |
  All four gaps below are closed:
  (a) PytestBDDPlugin.preflight() returns False when the per-task glue file
      `test_<slug>__<TASK_ID>.py` is absent from the worktree's features/
      directory, and True when present.
  (b) PytestBDDPlugin.preflight() / run() honour the GUARDKIT_BDD_TASK_ID
      env-var contract — verifiable by capturing the `env=` kwarg passed to
      subprocess.run and asserting the key/value is present.
  (c) C3 has at least one test that exercises pytest-bdd against a feature
      with two task-tagged scenarios and asserts the two marker filters
      produce disjoint scenario sets — not just disjoint argv strings.
  (d) C4 has at least one test that renames a .feature file between two
      run() invocations and asserts the second run resolves the new file
      via features/ directory re-discovery — not just an argv inspection.
  Task body §References explicitly resolves the AC-008 reinterpretation
  introduced in TASK-HMIG-007's 2026-05-20 implementation note (either
  amend AC-008 with explicit approval, or strengthen contracts to match
  the original wording).
tags:
  - autobuild
  - bdd
  - plugin
  - followup
  - hmig-007-gap
---

# Task: Close BDD plugin gaps — preflight glue/env checks + end-to-end C3/C4

## Description

TASK-HMIG-007 landed the `BDDPlugin` interface, `PytestBDDPlugin`, and the
contract-gated loader. Review of the implementation surfaced three concrete
gaps where the shipped code is measurably weaker than the original
acceptance criteria. This follow-up task closes them.

The gaps fall into two buckets:

1. **AC-006 not met in `preflight()`.** The shipped method only checks
   sanitisation shape + worktree existence. It does NOT verify the per-task
   glue file exists on disk or that the `GUARDKIT_BDD_TASK_ID` env-var
   contract is honoured by `run()`.

2. **C3 and C4 contract tests are mechanism-checks, not property-checks.**
   They patch `subprocess.run` and inspect argv. They would still pass if
   pytest-bdd's marker filter or directory re-discovery were broken,
   because nothing actually invokes the runner.

A third concern — TASK-HMIG-007's `Implementation note (2026-05-20)`
unilaterally reinterpreted AC-008 from "minimal .feature + per-task glue
setup" to "synthetic JUnit XML + mocked subprocess" — needs an explicit
resolution: either record the §6.7 split as an approved AC amendment, or
strengthen the contracts to match the original AC wording. The end-to-end
additions below give us the second option; the first requires a separate
sign-off note in TASK-REV-HMIG.

## Acceptance Criteria

### Preflight

- [ ] AC-001: `PytestBDDPlugin.preflight(task_id, worktree)` returns `False`
      when `<worktree>/features/test_<slug>__<TASK_ID>.py` is missing for
      every `<slug>` derivable from the worktree's `.feature` files in
      `features/`. Returns `True` when at least one matching glue file
      exists.
- [ ] AC-002: `preflight()` is covered by tests that exercise both branches
      (no glue file present → False; glue file present → True) using
      `tmp_path` to lay out a minimal `features/` directory.
- [ ] AC-003: `PytestBDDPlugin.run()` passes `GUARDKIT_BDD_TASK_ID=<task_id>`
      via the `env=` kwarg on `subprocess.run`. A new test captures the
      kwargs dict (via `unittest.mock.patch("subprocess.run")` with a
      side-effect that records `kwargs`) and asserts the env var is
      present with the unsanitised `task_id` as the value (per
      `bdd-per-task-glue.md` — env var carries the raw ID; sanitisation is
      a marker-shape concern only).
- [ ] AC-004: AC-003's assertion is duplicated as a `preflight()`-side
      check OR documented in code as "env-var honour is verified at
      `run()` boundary; `preflight()` only verifies shape" with a
      reference back to this task. (Author's choice — both satisfy the
      AC-006 spirit; pick whichever keeps the code simpler.)

### C3 — parallel disjoint scenarios (end-to-end)

- [ ] AC-005: Add `tests/bdd/test_pytest_bdd_plugin_end_to_end.py` with a
      `TestC3DisjointScenarios` class that:
  - Writes a minimal `features/parallel.feature` with two scenarios, each
    tagged `@task_TASK_C3_A` and `@task_TASK_C3_B` respectively.
  - Writes a `features/conftest.py` that wires the per-task pytest mark.
  - Writes two per-task glue files: `test_parallel__TASK_C3_A.py` and
    `test_parallel__TASK_C3_B.py`, each binding only its own scenarios via
    `@scenario`.
  - Invokes `PytestBDDPlugin.run(...)` twice (once per task_id) — either
    via real subprocess or `pytest.main(...)` in-process; author's choice.
  - Asserts each run reports `scenarios_attempted == 1` and that the
    sets of attempted scenarios are disjoint.
- [ ] AC-006: The end-to-end test is `@pytest.mark.slow` so the default
      fast suite is unaffected, but CI runs the slow tests on the
      `tests/bdd/` path.

### C4 — identity-bounded resolution survives rename (end-to-end)

- [ ] AC-007: In the same `test_pytest_bdd_plugin_end_to_end.py`, add a
      `TestC4SurvivesRename` class that:
  - Writes `features/original.feature` with one task-tagged scenario.
  - Invokes `PytestBDDPlugin.run(...)` and asserts
    `scenarios_attempted >= 1, scenarios_errored == 0`.
  - Renames `features/original.feature` → `features/renamed.feature`
    (filesystem move, not git mv — keep test hermetic).
  - Re-invokes `PytestBDDPlugin.run(...)` and asserts the second run
    still reports `scenarios_attempted >= 1, scenarios_errored == 0`.
      The renamed file is re-discovered via `features/` directory glob.

### AC-008 reinterpretation — explicit resolution

- [ ] AC-008: Add a short subsection to TASK-HMIG-007's task file (in
      `tasks/completed/TASK-HMIG-007/`) titled
      "AC-008 reinterpretation: resolution" that either:
  - Confirms the §6.7 interface-vs-implementation split was discussed
    and approved (cite the discussion), and amends AC-008 prose to match
    what was actually built; OR
  - Records that the original AC-008 wording stands, the
    `Implementation note (2026-05-20)` was a scope-narrowing the agent
    took unilaterally, and TASK-HMIG-007F (this task) is the remedial
    work. Pick one — do not leave it ambiguous.

## Implementation Notes

- The end-to-end tests need `pytest-bdd` installed. Add it to the dev
  extras in `pyproject.toml` if it is not already there. (It IS expected
  in the runtime environment per AC-005 of TASK-HMIG-007, so this is
  belt-and-braces.)
- `pytest.main(...)` in-process is faster than a real subprocess but does
  not exercise the full `subprocess.run` argv path. If you choose
  in-process, keep ONE subprocess-based smoke test that exercises argv
  composition end-to-end so the C5 timeout / argv-leak guards are not
  reduced to mocks.
- The C3 end-to-end test is the canonical proof that the parent review's
  §5 Pattern 3 ("coach-gate-short-circuit-cascades when parallel tasks
  share features") is structurally guarded. Don't skip it. The C3
  argv-inspection unit test from TASK-HMIG-007 can stay — it is the fast
  guard; the end-to-end test is the truth guard.

## References

- Parent review §6 — BDD plugin interface
- Parent review §5 — failure-pattern guards (Patterns 2-5)
- `~/Projects/appmilla_github/guardkit/.claude/rules/bdd-per-task-glue.md`
  — env-var contract + sanitisation rules
- `~/Projects/appmilla_github/guardkit/.claude/rules/absence-of-failure-is-not-success.md`
  — zero-cardinality precondition
- `~/Projects/appmilla_github/guardkit/.claude/rules/path-string-mismatch-is-not-dishonesty.md`
  — identity-bounded resolution (C4)
- TASK-HMIG-007 implementation note (2026-05-20) — the AC-008
  reinterpretation this task either ratifies or remediates

## Notes

The shipped TASK-HMIG-007 is not a useless stub — `plugin.py`, `loader.py`,
the registration gate, the JUnit parser, the timeout structured-return,
and the C1/C2/C5/C6 interpretation tests are all real working code. The
gaps closed here are specifically the places where the implementation
was weaker than the AC. Treat this task as completion-of-AC, not as a
rewrite.
