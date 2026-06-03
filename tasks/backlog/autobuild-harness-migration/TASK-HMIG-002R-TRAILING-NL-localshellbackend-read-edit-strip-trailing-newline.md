---
id: TASK-HMIG-002R-TRAILING-NL
title: Triage LocalShellBackend.read/edit trailing-newline regression introduced by deepagents 0.6.7
task_type: bug-fix
status: backlog
created: 2026-06-03T12:15:00Z
updated: 2026-06-03T12:15:00Z
priority: normal
complexity: 2
effort_hours: 1
parent_task: TASK-HMIG-002R   # Owns the positive-tool-flow falsifier dimension (a)
related_tasks:
  - TASK-HMIG-007F   # Bumped deepagents to 0.6.7 — likely regression source (commit 5d6fd31)
  - TASK-HMIG-002R-NOPERMS   # Surfaced these failures while verifying the permissions ACs
surfaced_in_commit: 5d6fd31   # deepagents 0.6.7 bump
tags:
  - bug-fix
  - test-regression
  - deepagents-upstream
  - localshellbackend
  - autobuild
  - langgraph-migration
falsifier: "After fix (or test update): pytest tests/harness/test_backend_config.py reports 0 failures. Specifically test_positive_tool_flow_write_then_read_round_trips and test_positive_tool_flow_edit_replaces_existing_content pass against deepagents==0.6.7."
---

# Task: Triage LocalShellBackend.read/edit trailing-newline regression

## Background

While verifying TASK-HMIG-002R-NOPERMS (2026-06-03), the full `tests/harness/test_backend_config.py` suite reported **2 failures unrelated to permissions**:

```
FAILED tests/harness/test_backend_config.py::test_positive_tool_flow_write_then_read_round_trips
FAILED tests/harness/test_backend_config.py::test_positive_tool_flow_edit_replaces_existing_content
```

Both are falsifier dimension (a) — positive tool flow — for parent TASK-HMIG-002R. Neither touches `build_autobuild_permissions()`.

## Failure shape

Both assertions fail on a single trailing-newline character:

```
test_positive_tool_flow_write_then_read_round_trips
    assert read_result.file_data["content"] == "hello world\n"
    AssertionError: assert 'hello world' == 'hello world\n'

test_positive_tool_flow_edit_replaces_existing_content
    assert read_result.file_data["content"] == "hello there\n"
    AssertionError: assert 'hello there' == 'hello there\n'
```

The test writes `"hello world\n"` (with trailing `\n`), then `backend.read()` returns `"hello world"` (no trailing `\n`). The edit test is the same shape downstream of `backend.edit()`.

## Likely cause

These tests passed at the time TASK-HMIG-002R landed (2026-05-20 — commit `75f61e4`). They failed after commit `5d6fd31` (TASK-HMIG-007F) bumped `deepagents` from the 0.5.x line to `0.6.7`. The 0.6.0 refactor that moved the permission guard out of `_PermissionMiddleware` into `FilesystemMiddleware.__init__` (see TASK-HMIG-002R-NOPERMS rationale) is the most likely surface area for a parallel change to `LocalShellBackend.read()`'s `file_data["content"]` serialization.

Working hypothesis: 0.6.x's `LocalShellBackend.read()` now strips a single trailing `\n` from `file_data["content"]` before returning, mirroring how POSIX tools display files. The tests were written against 0.5.x's verbatim byte-for-byte behaviour.

## Triage steps

1. **Confirm hypothesis** — run the failing tests against `deepagents==0.5.x` (last good version before 5d6fd31's bump) to confirm the regression is upstream-versioned, not local.
2. **Find the upstream change** — grep `deepagents` 0.5.x→0.6.x source for `file_data` / `content` / `rstrip` / `strip` around `LocalShellBackend.read` and `LocalShellBackend.edit`. Note: 0.6.x's filesystem module is `deepagents/backends/local_shell.py` at the renamed import path used in `tests/harness/test_backend_config.py:38`.
3. **Decide policy** — pick one of:
   - **(A) Update tests** to match new upstream behaviour (`assert content == "hello world"`). Cheapest. Right answer if upstream's strip is documented/intentional.
   - **(B) File upstream bug** if the strip is undocumented and silently destructive. Then either skip the tests with `@pytest.mark.skip(reason="upstream issue #NNNN")` until fixed, or write a thin adapter that re-attaches the trailing newline when present in the write payload.
   - **(C) Add a regression test** for the round-trip invariant if (A) is chosen, so any future upstream change back to verbatim is caught.
4. **Document the decision** in `tests/harness/test_backend_config.py` near the affected tests so the next reader doesn't waste cycles re-triaging.

## Acceptance Criteria

- [ ] **AC-001** — Root cause confirmed (upstream 0.6.x behaviour change vs local bug). One-paragraph note added to this task's body under "Resolution".
- [ ] **AC-002** — Policy choice (A / B / C above) made and recorded with rationale.
- [ ] **AC-003** — After fix or test update: `pytest tests/harness/test_backend_config.py` reports `0 failed` against `deepagents==0.6.7` (currently pinned). The 7 NOPERMS skips remain skipped — they are owned by TASK-HMIG-002R-NOPERMS, not this task.
- [ ] **AC-004** — If policy (A) chosen: tests updated to assert the post-strip content, and a comment near the assertion explains the upstream behaviour.
- [ ] **AC-005** — If policy (B) chosen: upstream issue link recorded here and in the test file's skip reason.

## Out of scope

- **Permissions** — owned by TASK-HMIG-002R-NOPERMS / TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE.
- **deepagents version downgrade** — 0.6.7 is required by TASK-HMIG-007F's BDD plugin work; don't undo that.
- **Other LocalShellBackend tests** — only the two listed failures are in scope. If triage uncovers further `file_data` regressions, file separately.

## References

- **Surfacing run**: TASK-HMIG-002R-NOPERMS verification (2026-06-03). Full pytest output in that task's completion notes.
- **Parent task**: `tasks/completed/TASK-HMIG-002R/TASK-HMIG-002R-configure-localshellbackend-and-permissions.md` — defines the positive-tool-flow falsifier dimension (a) these tests cover.
- **deepagents bump commit**: `5d6fd31` (TASK-HMIG-007F).
- **Failing tests**: `tests/harness/test_backend_config.py:141` (`test_positive_tool_flow_write_then_read_round_trips`) and `tests/harness/test_backend_config.py:181` (`test_positive_tool_flow_edit_replaces_existing_content`).

## Resolution

_(To be filled in when AC-001 lands.)_
