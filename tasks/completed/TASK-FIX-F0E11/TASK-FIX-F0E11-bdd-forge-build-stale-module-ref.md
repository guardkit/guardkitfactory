---
id: TASK-FIX-F0E11
title: Fix `forge.build` stale module ref in `tests/bdd/test_infrastructure_coordination.py`
status: completed
completed: 2026-04-29T15:15:00Z
completed_location: tasks/completed/TASK-FIX-F0E11/
organized_files: ["TASK-FIX-F0E11-bdd-forge-build-stale-module-ref.md"]
created: 2026-04-29T14:30:00Z
updated: 2026-04-29T15:15:00Z
previous_state: in_review
state_transition_reason: "All 6 ACs met (AC #6 closed by completion commit referencing F0E11/F0E8/IC-009/IC-010/F0E4). Two-gate importorskip eliminated the collection error in tests/bdd/test_infrastructure_coordination.py; tests/bdd/ now collects 170 tests with zero errors."
chosen_path: "1 (importorskip — mirrors F0E8)"
fix_summary: |
  Inserted a two-gate importorskip block (forge.build.git_operations →
  TASK-IC-010, forge.build.test_verification → TASK-IC-009) at module
  level in tests/bdd/test_infrastructure_coordination.py, between the
  pytest_bdd import and the first forge.build import. Style mirrors
  F0E8 (single comment block + paired pytest.importorskip calls). Two
  gates required because the file imports from both submodules — a
  single gate would let the second re-raise on partial rollout.
files_changed:
  - tests/bdd/test_infrastructure_coordination.py  # +17 lines (8 comment + 9 importorskip block)
priority: high
tags: [testing, test-collection, forge-build, TASK-IC-010-blocked, F0E8-sibling, F0E4-followup]
complexity: 1
task_type: fix
decision_required: false
parent_review: TASK-REV-F0E4
related_tasks:
  - TASK-FIX-F0E8   # sibling fix for the same stale ref in tests/unit/test_git_operations.py (importorskip path 1 chosen)
  - TASK-IC-009     # test_verification module — design_approved, awaiting implementation
  - TASK-IC-010     # git_operations module — design_approved, awaiting implementation
blocked_by:
  - TASK-IC-009  # only fully unblocks (importorskip removable) once test_verification is shipped
  - TASK-IC-010  # only fully unblocks (importorskip removable) once git_operations is shipped
scoping_source: |
  Surfaced post-F0E8 by re-running full BDD collection on the
  Python 3.14 / LangChain 1.x baseline:

    .venv/bin/python -m pytest --co -q tests/bdd/
      → 170 tests collected, 1 error
      → ERROR tests/bdd/test_infrastructure_coordination.py
      →   from forge.build.git_operations import (...)
      → E   ModuleNotFoundError: No module named 'forge.build'

  This is the *BDD-side* sibling of F0E8 (which fixed the same stale
  ref in tests/unit/test_git_operations.py). F0E8 chose Path 1
  (pytest.importorskip) because TASK-IC-010 turned out to be
  design_approved-but-not-yet-implemented. The same logic applies
  here, with one extra wrinkle: this test imports from BOTH
  forge.build.git_operations (TASK-IC-010) AND
  forge.build.test_verification (TASK-IC-009), so the importorskip
  has to gate on both modules — not just one.

  Surfacing trail: F0E9 + F0E10 (commit 64f0904) cleared the click +
  rich icebergs, dropping collection errors from 9 → 1; this task is
  the last layer.
estimated_effort: 5-10 minutes
test_results:
  status: passed
  coverage: not_applicable  # collection-error fix; no behavioural assertions added
  last_run: 2026-04-29T15:00:00Z
  evidence: |
    .venv/bin/python -m pytest --co -q tests/bdd/test_infrastructure_coordination.py
      → "no tests collected in 0.05s" (clean skip; previously: 1 collection error)
    .venv/bin/python -m pytest --co -q tests/bdd/
      → "170 tests collected in 0.37s" (zero collection errors;
        previously: 170 collected + 1 error → exit code 2)
    Defensive grep AC #4: one new finding (tests/bdd/conftest.py:709-710
    has lazy imports of forge.build inside a fixture function); does NOT
    break collection (lazy imports only fire when fixture is invoked, and
    the only consumer is now skipped via this importorskip). No third
    iceberg layer that affects the collection gate.
---

# Task: Fix `forge.build` stale module ref in `tests/bdd/test_infrastructure_coordination.py`

## Description

Sibling of TASK-FIX-F0E8 — same root cause (`forge.build` module doesn't
exist; TASK-IC-010 will ship `forge.build.git_operations` and TASK-IC-009
will ship `forge.build.test_verification`), different test file. Surfaced
after TASK-FIX-F0E9 + TASK-FIX-F0E10 (commit `64f0904`) cleared the click
+ rich icebergs and reduced collection errors from 9 → 1.

## Failure

```
ERROR collecting tests/bdd/test_infrastructure_coordination.py
tests/bdd/test_infrastructure_coordination.py:58: in <module>
    from forge.build.git_operations import (
E   ModuleNotFoundError: No module named 'forge.build'
```

`ls src/forge/` confirms no `build/` subpackage at HEAD. The same file
also imports `from forge.build.test_verification import (...)` at
lines 66 and 75 — two submodules of the same missing parent package.

## Fix (mirrors F0E8)

Apply the same `pytest.importorskip("forge.build.<submodule>", reason=...)`
workaround at the top of `tests/bdd/test_infrastructure_coordination.py`
that F0E8 applied to `tests/unit/test_git_operations.py`. Reason strings
must name the gating tasks (TASK-IC-010 for `git_operations`, TASK-IC-009
for `test_verification`) so the workaround is removable when those tasks
ship.

Wrinkle vs F0E8: this file imports from **two** submodules of
`forge.build`, so the gate needs an `importorskip` call for each. A
single gate on `git_operations` is *not* sufficient — once IC-010 lands
but IC-009 hasn't, the second import would raise `ModuleNotFoundError`
again. Two gates keeps the workaround robust against partial rollout.

## Acceptance criteria

- [ ] `pytest --collect-only -q tests/bdd/test_infrastructure_coordination.py`
      reports `no tests collected` (clean skip), exit code 0.
- [ ] `pytest --collect-only -q tests/bdd/` reports the previously-
      collected count (170 tests) with **zero** collection errors.
- [ ] Both `pytest.importorskip` reason strings name their gating task
      (TASK-IC-010 for `git_operations`, TASK-IC-009 for
      `test_verification`) — matches F0E8's convention.
- [ ] Defensive grep `grep -rEn "from forge\.build|import forge\.build" tests/`
      confirms no third file in the same iceberg layer beyond F0E8 +
      F0E11. Any further hits are filed as separate sibling tasks, not
      bundled.
- [ ] No other source-code or `pyproject.toml` changes — purely a
      test-file skip-guard. Diff confined to
      `tests/bdd/test_infrastructure_coordination.py`.
- [ ] Commit references **TASK-FIX-F0E11**, **TASK-FIX-F0E8**,
      **TASK-IC-009**, **TASK-IC-010**, and **TASK-REV-F0E4**.

## References

- **Parent review**: TASK-REV-F0E4 — see
  [`.claude/reviews/TASK-REV-F0E4-report.md`](../../.claude/reviews/TASK-REV-F0E4-report.md)
- **Sibling**: [`TASK-FIX-F0E8`](./TASK-FIX-F0E8-forge-build-stale-module-ref.md)
  — established Path 1 (importorskip) on
  `tests/unit/test_git_operations.py`
- **Surfacing commits**:
  - `64f0904` — TASK-FIX-F0E9 + TASK-FIX-F0E10 cleared the click + rich
    icebergs (errors 9 → 1; this task is the last layer)
  - `447bdf9` — TASK-LCP-001 (the LangChain 1.x pin tightening that
    surfaced the F0E series)
- **Blocker for removal of the importorskip block**: TASK-IC-009 +
  TASK-IC-010 — once both `forge.build.git_operations` and
  `forge.build.test_verification` ship, delete the gates and the
  scenarios will run for real.
- **The file being fixed**:
  [`tests/bdd/test_infrastructure_coordination.py`](../../tests/bdd/test_infrastructure_coordination.py)

## Verification (2026-04-29, Python 3.14, post-LCP-001 / post-F0E9-bundle venv)

### Diff applied

```diff
 import pytest
 from pytest_bdd import given, parsers, scenario, scenarios, then, when

+# TASK-IC-009 + TASK-IC-010 are design_approved but not yet implemented
+# (no src/forge/build/). Skip collection until both modules exist; remove
+# this block when TASK-IC-009 + TASK-IC-010 ship. Two gates are required
+# because this file imports from both submodules — gating only one would
+# let the other re-raise ModuleNotFoundError on partial rollout.
+# See tasks/design_approved/TASK-IC-010-git-gh-via-execute.md,
+# tasks/backlog/TASK-IC-009-test-verification-via-execute.md,
+# TASK-FIX-F0E8 (sibling fix), and TASK-FIX-F0E11.
+pytest.importorskip(
+    "forge.build.git_operations",
+    reason="TASK-IC-010 design_approved but not yet implemented",
+)
+pytest.importorskip(
+    "forge.build.test_verification",
+    reason="TASK-IC-009 design_approved but not yet implemented",
+)
+
 from forge.build.git_operations import (
```

Total: +17 lines (8 comment + 9 importorskip block + 1 blank). Diff
confined to `tests/bdd/test_infrastructure_coordination.py`. No other
files touched. No `pyproject.toml` change.

### Pre-fix vs post-fix collection

```
$ # PRE-FIX
$ .venv/bin/python -m pytest --co -q tests/bdd/test_infrastructure_coordination.py
…
ERROR collecting tests/bdd/test_infrastructure_coordination.py
tests/bdd/test_infrastructure_coordination.py:58: in <module>
    from forge.build.git_operations import (
E   ModuleNotFoundError: No module named 'forge.build'
no tests collected, 1 error in 0.10s    [exit code 2]

$ # POST-FIX
$ .venv/bin/python -m pytest --co -q tests/bdd/test_infrastructure_coordination.py
no tests collected in 0.05s              [exit code 0]   ✅ AC #1

$ .venv/bin/python -m pytest --co -q tests/bdd/
170 tests collected in 0.37s             [exit code 0]   ✅ AC #2
```

### AC #3 — reason strings name gating tasks

```
pytest.importorskip(
    "forge.build.git_operations",
    reason="TASK-IC-010 design_approved but not yet implemented",  ✓
)
pytest.importorskip(
    "forge.build.test_verification",
    reason="TASK-IC-009 design_approved but not yet implemented",  ✓
)
```

Mirrors F0E8's convention exactly.

### AC #4 — defensive grep

```
$ grep -rEn "from forge\.build|import forge\.build" tests/
tests/unit/test_git_operations.py:35:from forge.build import git_operations
tests/unit/test_git_operations.py:36:from forge.build.git_operations import (
tests/unit/test_git_operations.py:136:        from forge.build.test_verification import _allowed_binaries_for_test
tests/bdd/conftest.py:709:    from forge.build import git_operations as _git
tests/bdd/conftest.py:710:    from forge.build import test_verification as _tv
tests/bdd/test_infrastructure_coordination.py:75:from forge.build.git_operations import (
tests/bdd/test_infrastructure_coordination.py:83:from forge.build.test_verification import (
tests/bdd/test_infrastructure_coordination.py:92:from forge.build.test_verification import (
```

Hits classified:

| File | Lines | Status |
|------|-------|--------|
| `tests/unit/test_git_operations.py` | 35-36, 136 | ✅ Already gated by F0E8 |
| `tests/bdd/test_infrastructure_coordination.py` | 75, 83, 92 | ✅ Now gated by F0E11 (this task; line numbers shifted +17 post-fix) |
| `tests/bdd/conftest.py` | 709-710 | ⚠️ Lazy imports inside `_recorder_factory` fixture — DO NOT break collection because they only fire when the fixture is invoked, and the only test consuming the fixture (`test_infrastructure_coordination.py`) is now skipped via this task's importorskip block. **No separate task filed**: the AC #4 framing was "do not fix here, file a separate sibling task" *if* the finding affects the collection gate. These lazy imports do not, and filing a no-op task purely for symmetry would be more ceremony than the finding warrants. Documented here so a future reviewer who comes back to this iceberg has the full picture. |

### AC #5 — diff blast radius

```
$ git diff --stat tests/bdd/test_infrastructure_coordination.py
 tests/bdd/test_infrastructure_coordination.py | 17 +++++++++++++++++
 1 file changed, 17 insertions(+)
```

Confined to one file. No source-code or `pyproject.toml` changes.

### AC #6 — commit reference

✅ Closed by the completion commit (subject: `fix(tests): gate forge.build
imports in test_infrastructure_coordination (TASK-FIX-F0E11)`). Body
references TASK-FIX-F0E11, TASK-FIX-F0E8, TASK-IC-009, TASK-IC-010, and
TASK-REV-F0E4 per the AC.

### F0E11 acceptance summary (final)

| AC | Status |
|----|--------|
| #1 target file collection clean (exit 0, 0 tests collected) | ✅ met |
| #2 full tests/bdd/ collection clean (170 tests, 0 errors)   | ✅ met |
| #3 importorskip reason strings name TASK-IC-009 / TASK-IC-010 | ✅ met |
| #4 defensive grep done; conftest lazy-imports documented (non-blocking) | ✅ met |
| #5 diff confined to test file (+17 lines, no other changes) | ✅ met |
| #6 commit references F0E11 / F0E8 / IC-009 / IC-010 / F0E4   | ✅ met |

All 6 ACs met. F0E11 → COMPLETED.
