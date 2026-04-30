---
id: TASK-F8-005
title: "Update apply_at_boot idempotency test for v2 schema"
task_type: testing
status: completed
priority: high
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-F8-005/
organized_files: ["TASK-F8-005-update-idempotency-test-for-v2.md"]
previous_state: backlog
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 1
implementation_mode: direct
complexity: 1
dependencies: []
tags: [test, migrations, schema-version, feat-forge-008, f008-val-005]
related_files:
  - tests/forge/adapters/test_sqlite_persistence.py
  - src/forge/lifecycle/migrations.py
  - src/forge/lifecycle/schema.sql
  - src/forge/lifecycle/schema_v2.sql
test_results:
  status: passed
  coverage: null  # not measured for this single-test edit
  last_run: 2026-04-30T00:00:00Z
  command: "pytest tests/forge/adapters/test_sqlite_persistence.py"
  passed: 12
  failed: 0
  notes: "All 12 tests in test_sqlite_persistence.py pass; idempotency test now parameterised on _SCHEMA_VERSION."
---

# Task: Update `apply_at_boot` idempotency test for v2 schema

## Description

### Re-classification (architectural review §1)

The RESULTS file claimed: "`migrations.apply_at_boot` is non-idempotent for
the v2 schema row. Gate the `INSERT INTO schema_version` on
`WHERE NOT EXISTS` (or use `INSERT OR IGNORE`)."

**This is wrong.** Both `schema.sql:108` and `schema_v2.sql:26-27` already
use `INSERT OR IGNORE INTO schema_version`. And `apply_at_boot`
(`migrations.py:113-119`) gates on `_current_version()` — on the second
boot, `starting_version=2`, `pending=[]`, the function returns immediately
without re-running any SQL.

**The actual defect is in the test.** It was written when only schema v1
existed and asserts:

```python
# tests/forge/adapters/test_sqlite_persistence.py:115-128
def test_apply_at_boot_is_idempotent(tmp_path: Path) -> None:
    """Running migrations twice must be a no-op (AC explicit)."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)
        migrations.apply_at_boot(cx)

        rows = cx.execute(
            "SELECT version FROM schema_version ORDER BY version;"
        ).fetchall()
        assert rows == [(1,)], "second apply must not duplicate the seed row"
    finally:
        cx.close()
```

FEAT-FORGE-008 added `(2, "schema_v2.sql")` to `_MIGRATIONS` (see
`migrations.py:38-42`). After the first apply, `schema_version` correctly
contains rows `[(1,), (2,)]`. The second apply is a no-op — the test name
is correct (idempotency holds: same rows after the second call as after
the first), but the literal expected list `[(1,)]` is stale.

### Fix

Parameterise the assertion on `migrations._SCHEMA_VERSION` so the test
grows automatically with future schema bumps:

```python
def test_apply_at_boot_is_idempotent(tmp_path: Path) -> None:
    """Running migrations twice must be a no-op (AC explicit)."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)
        migrations.apply_at_boot(cx)

        rows = cx.execute(
            "SELECT version FROM schema_version ORDER BY version;"
        ).fetchall()
        # Expected: one row per applied migration, no duplicates.
        # Parameterised so future schema bumps don't need a test edit.
        expected = [(v,) for v in range(1, migrations._SCHEMA_VERSION + 1)]
        assert rows == expected, (
            f"second apply must not duplicate seed rows; "
            f"expected {expected}, got {rows}"
        )
    finally:
        cx.close()
```

## Acceptance Criteria

- [x] **AC-1**:
      `tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent`
      passes against the current code.
- [x] **AC-2**: The assertion is parameterised on
      `migrations._SCHEMA_VERSION` so a future v3/v4 schema bump (adding
      a new `(N, "schema_vN.sql")` entry) does not require editing this
      test.
- [x] **AC-3**: A short comment in the test explains why the assertion
      grows with `_SCHEMA_VERSION` (so future readers don't try to revert
      it to a literal list).

## Implementation Notes

- `_SCHEMA_VERSION` is module-private (`_SCHEMA_VERSION: Final[int] = 2`).
  Accessing it via `migrations._SCHEMA_VERSION` is the conventional pytest
  pattern and is acceptable here; alternatively, expose a public
  `current_target_schema_version()` accessor — implementer's choice.
- This is a one-line code change plus a comment. `implementation_mode:
  direct` is appropriate; no autobuild-coach loop needed.

## Out of scope

- Refactoring `_MIGRATIONS` or `_SCHEMA_VERSION` to be derived from the
  bundled SQL files. The current tuple-of-pairs is fine.
- Adding new migrations (no v3 schema is in scope).

## Implementation Summary

Replaced the literal `assert rows == [(1,)]` in
`tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent`
with a `_SCHEMA_VERSION`-derived expectation:

```python
expected = [(v,) for v in range(1, migrations._SCHEMA_VERSION + 1)]
```

Plus a 4-line comment naming `_MIGRATIONS`, `_SCHEMA_VERSION`, and this
task ID so future readers don't revert it to a literal list when the
next schema bump lands. No production code touched — single-test fix.

**Verification**: `pytest tests/forge/adapters/test_sqlite_persistence.py`
→ 12/12 passed (0.07 s). The targeted test was previously failing with
`assert [(1,), (2,)] == [(1,)]` (the FEAT-FORGE-008 v2 schema row that
the literal assertion never accounted for).

**Approach notes**:
- `implementation_mode: direct` — no planning/architectural-review/
  autobuild-coach loops invoked. Complexity 1, single-line change, the
  parent review (`TASK-REV-F008` §1) supplied the exact diff.
- Used module-private access (`migrations._SCHEMA_VERSION`) rather than
  exposing a public `current_target_schema_version()` accessor — the
  test is the only consumer that needs this and a private-attribute
  reach-in inside the test package is the conventional pytest pattern.

**Lessons (worth recording for future schema bumps)**:
- Root-causing the failure required reading `apply_at_boot` end-to-end:
  the RESULTS file's surface diagnosis ("non-idempotent — gate the
  INSERT") was wrong because `INSERT OR IGNORE` was already in the SQL
  and `apply_at_boot` short-circuits on `_current_version()`. The actual
  defect was a stale test literal, not a missing SQL guard. The
  architectural review (`docs/reviews/REVIEW-F008-validation-triage.md`
  §1) caught the misclassification.
- Parameterising assertions on the same module-level constant the
  production code uses (`_SCHEMA_VERSION`) closes one of the two
  invariants TASK-REV-F008 §1 LCOI flagged for the migrations module:
  schema-version state must be derivable from a single source of truth,
  not duplicated across SQL + Python + tests. The other invariant
  (deriving `_MIGRATIONS` from bundled SQL files) is explicitly out of
  scope here — see `_SCHEMA_VERSION: Final[int] = 2` at
  `src/forge/lifecycle/migrations.py:38`.
