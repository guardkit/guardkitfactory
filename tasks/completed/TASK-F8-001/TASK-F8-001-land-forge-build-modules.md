---
id: TASK-F8-001
title: "Land forge.build.git_operations + forge.build.test_verification (TASK-IC-009/010)"
task_type: implementation
status: completed
priority: medium
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-F8-001/
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 2
implementation_mode: task-work
complexity: 5
dependencies: [TASK-F8-003, TASK-F8-004, TASK-F8-005]
tags: [forge-build, git-operations, test-verification, infrastructure-coordination, feat-forge-008, f008-val-001]
related_files:
  - src/forge/build/__init__.py
  - src/forge/build/git_operations.py
  - src/forge/build/test_verification.py
  - tests/forge/build/
  - tests/bdd/test_infrastructure_coordination.py
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
test_results:
  status: passed
  coverage:
    line: 89
    branch: 97
  last_run: 2026-04-30T00:00:00Z
  full_suite: 3851/3851 passed (no --ignore)
  bdd_test: tests/bdd/test_infrastructure_coordination.py 49/49 passed
  unit_tests:
    new: tests/forge/build/ 43/43 passed
    activated: tests/unit/test_git_operations.py 33/33 passed
---

# Task: Land `forge.build.git_operations` + `forge.build.test_verification`

## Description

`tests/bdd/test_infrastructure_coordination.py` cannot collect:

```
ModuleNotFoundError: No module named 'forge.build'
```

The two missing modules — `forge.build.git_operations` and
`forge.build.test_verification` — were specified by TASK-IC-009/010 in the
`infrastructure-coordination` feature folder but never landed in
`src/forge/`. This pre-existed FEAT-FORGE-008 (the runbook §1.1 sweep just
surfaced it because Phase 1 went broader), but it now blocks the runbook
from running verbatim.

The architectural review re-classified this as **implement-now** per the
operator's `Q3=I` choice — instead of deferring or splitting into a
separate feature.

## Acceptance Criteria

- [x] **AC-1**: `src/forge/build/__init__.py` exists and exports the public
      surface of both submodules.
- [x] **AC-2**: `src/forge/build/git_operations.py` exists and implements
      the public API specified by TASK-IC-010 (allowlist single-source-of-truth,
      basename-validated allowlist, env-only credentials, auth-failure soft-None,
      RuntimeError on genuine non-zero, URL-shape PR parser).
- [x] **AC-3**: `src/forge/build/test_verification.py` exists and
      implements the public API specified by TASK-IC-009
      (`TestVerificationResult` TypedDict, `TIMEOUT_MARKER`, `verify_tests`,
      pytest-summary parsing with exit-code fallback, identity-preserving
      `_allowed_binaries_for_test`).
- [x] **AC-4**: `tests/bdd/test_infrastructure_coordination.py` collects
      and passes against the new modules (49/49 scenarios green).
- [x] **AC-5**: `pytest -q` (no `--ignore=tests/bdd/test_infrastructure_coordination.py`)
      reports zero collection errors (3851/3851 passed).
- [x] **AC-6**: Verified consistency — full sweep is green without the
      `--ignore` flag, so the runbook can drop it. The doc-side edit
      lands in TASK-F8-006 per the wave plan.
- [x] **AC-7**: New unit tests in `tests/forge/build/` cover the public
      surface of both modules (AAA pattern; 89% line / 97% branch on
      the new package, exceeding the 80%/75% thresholds).

## Implementation Notes

### Discover the spec

1. Check `tasks/backlog/infrastructure-coordination/` for
   `TASK-IC-009*.md` and `TASK-IC-010*.md` task files. If they exist,
   read them as the source of truth for the public API.
2. If they are missing or stale, read
   `tests/bdd/test_infrastructure_coordination.py` to extract the
   expected public surface from the step definitions / fixtures.

### Module boundaries

- `git_operations` is the lower-level: branch / commit / push / status
  primitives wrapped over `subprocess.run(["git", ...])` or `pygit2`.
- `test_verification` is the higher-level: runs `pytest` (or the
  configured test runner) and parses results into a structured outcome
  the supervisor can consume.

### Test strategy

Follow the existing project pattern: `tests/forge/build/` mirrors
`src/forge/build/`. Use AAA pattern, mock external dependencies (git,
pytest invocations), include both happy path and error cases.

## Implementation Summary

Landed the two modules per the BDD-bindings contract in
`tests/bdd/test_infrastructure_coordination.py` and the activated unit
suite in `tests/unit/test_git_operations.py` (which had been gated on
`pytest.importorskip("forge.build.git_operations")`).

**Approach**

1. Reverse-engineered the public surface from the BDD imports + the
   `execute_seam_recorder` fixture in `tests/bdd/conftest.py`. Confirmed
   against the TASK-IC-009 / TASK-IC-010 task specs.
2. Made `forge.build.git_operations` the owner of the `ALLOWED_BINARIES`
   constant (single source of truth — TASK-IC-010 §4) and
   `forge.build.test_verification` import it. The seam-test invariant
   `_allowed_binaries_for_test() is ALLOWED_BINARIES` proves no
   accidental duplication.
3. Both modules expose a module-level `_execute_via_deepagents` seam
   matching the recorder signature
   `(*, command: list[str], cwd: str, timeout: int) -> tuple[str, str, int, float, bool]`,
   so a single `monkeypatch.setattr` replaces both at once for tests.
4. Reconciled with the activated TASK-IC-010 test contract:
   - basename-based allowlist (`/usr/local/bin/git` accepted,
     `/usr/bin/rm` refused);
   - empty-arg validation on `branch_name` / `message` / `title`;
   - non-zero git/gh exits → `RuntimeError` with diagnostic context;
   - PR creation has two soft-fail paths (missing/empty creds OR
     auth-failure stderr → return `None`) but raises on genuine failures;
   - PR URL parser only returns lines that start with `http(s)://`.

**Verification**

- `tests/bdd/test_infrastructure_coordination.py`: 49/49 pass
- `tests/unit/test_git_operations.py` (activated): 33/33 pass
- New `tests/forge/build/`: 43/43 pass
- Full sweep: 3851/3851 pass with no `--ignore`
- Coverage on `src/forge/build/`: 89% line, 97% branch

**Lessons / non-obvious decisions**

- The `_execute_via_deepagents` default body is intentionally
  uncovered by unit tests — it's the production fallback that gets
  patched out everywhere else. Covering it would need real-subprocess
  integration tests, which are out of scope (the BDD harness validates
  the contract; the unit tests prove parsing/validation/orchestration).
- `DisallowedBinaryError` subclasses `ValueError` so existing
  `except ValueError` boundaries continue to catch it. The BDD scenario
  catches `(ValueError, DisallowedBinaryError)` defensively.
- `test_verification`'s seam delegates to `git_operations._execute_via_deepagents`
  by default but BDD/unit tests patch each module independently, so the
  delegation is only used in the rare "patch only one seam" case.

## Out of scope

- Refactoring the BDD bindings themselves (they are the contract — make
  the modules conform to them, not vice versa).
- Wiring `forge.build.*` into the supervisor pipeline (the supervisor
  already knows how to call subprocess-style stages; this task lands the
  module surface, not the dispatch wiring).
- Changing `infrastructure-coordination` feature scope or status.
