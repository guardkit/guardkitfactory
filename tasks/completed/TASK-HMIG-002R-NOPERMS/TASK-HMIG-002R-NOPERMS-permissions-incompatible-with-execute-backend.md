---
id: TASK-HMIG-002R-NOPERMS
title: build_autobuild_permissions() must return [] until DeepAgents supports permissions on execute-capable backends
task_type: implementation
status: completed
created: 2026-06-03T11:15:00Z
updated: 2026-06-03T12:30:00Z
completed: 2026-06-03T12:30:00Z
completed_location: tasks/completed/TASK-HMIG-002R-NOPERMS/
priority: critical
complexity: 1
effort_hours: 0.5
parent_task: TASK-HMIG-002R   # Completed 2026-05-20 in this repo; this is a follow-on adjustment
deadline: 2026-06-15
landed_in_commit: 5d6fd31   # Implementation shipped alongside TASK-HMIG-007F (deepagents 0.6.7 bump)
followon_tasks:
  - TASK-HMIG-002R-TRAILING-NL   # Triages 2 pre-existing LocalShellBackend trailing-newline test failures surfaced during verification
cross_repo:
  notes: |
    Surfaced by guardkit-side TASK-HMIG-009A AC-001D run 4 (2026-06-03)
    — see ../guardkit/docs/reviews/autobuild-migration/TASK-FIX-A7D3-langraph-run-4.md
    for the verbatim DeepAgents error. The guardkit-side consumer
    (TASK-FIX-002R-CONSUME in ../guardkit/tasks/backlog/autobuild-harness-migration/)
    is wired correctly; the limitation is in DeepAgents itself. The fix lives
    in this factory rather than in guardkit's consumer so the choice stays
    centralised in the harness layer (correct cross-repo split).
related_tasks:
  - TASK-HMIG-002R   # ✅ completed 2026-05-20 — this is a follow-on; the factory shipped permissions, then upstream rejected the combo
tags:
  - bug-fix
  - deepagents-upstream-limitation
  - permissions
  - autobuild
  - langgraph-migration
  - pre-canary-blocker
falsifier: "After fix: invoking LangGraphHarness with the output of build_autobuild_backend(worktree) and build_autobuild_permissions() no longer raises 'LangGraphHarnessError: _PermissionMiddleware does not yet support backends with command execution'. Concretely: AC-001D run 5 in guardkit reaches at least Coach turn 1 with non-empty files_modified, no DeepAgents construction error."
---

# Task: Drop permissions from build_autobuild_permissions() pending DeepAgents upstream

## Surfaced by AC-001D run 4 (guardkit, 2026-06-03)

The guardkit-side wiring task TASK-FIX-002R-CONSUME landed and started calling our `build_autobuild_backend` + `build_autobuild_permissions` factories from `selector.py`. DeepAgents rejected the combination at construction:

```
LangGraphHarnessError: failed to construct DeepAgent for role='coach'
model='openai:qwen36-workhorse':
_PermissionMiddleware does not yet support backends with command execution
(SandboxBackendProtocol). Tool-level permissions for the execute tool are
not implemented. Either remove permissions or use a backend without
execution support.
```

**Cross-repo log reference**: `../guardkit/docs/reviews/autobuild-migration/TASK-FIX-A7D3-langraph-run-4.md`.

This is a **DeepAgents library limitation**: the permission middleware does not yet gate execute-capable backends. AutoBuild needs `execute` (Coach runs pytest, Player runs scripts) so we cannot switch to a non-execute backend like `FilesystemBackend`. The forced choice is permissions OR execute — for the canary, we accept losing permissions.

**Upstream status (verified 2026-06-03)**: still present at `deepagents==0.6.7` HEAD (the 0.6.0 refactor moved the guard from `_PermissionMiddleware` in `permissions.py` to `FilesystemMiddleware.__init__` in `middleware/filesystem.py:697`, but the constraint and its `NotImplementedError` are unchanged). Upstream issue [langchain-ai/deepagents#2894](https://github.com/langchain-ai/deepagents/issues/2894) — *"Extend `PermissionMiddleware` to support execute and task tool restrictions"* — was **closed by upstream** with the response *"We're not ready to add this to the SDK at the moment. You can use custom middleware for now to enforce execute permissions in this manner."* A contributor had already implemented a working fix (29 new tests, `ExecutePermission` + `TaskPermission` dataclasses) and the maintainer declined to merge. **Upstream is unlikely to land this without coordinated push** — see follow-on task `TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE` for the custom-middleware path that is now the only realistic route to restoring enforcement.

## Fix (literally ~5 LOC)

In `src/guardkitfactory/harness/permissions.py`, `build_autobuild_permissions()` should return `[]` (empty list) with a comment + log line explaining the upstream limitation. Pseudocode:

```python
def build_autobuild_permissions() -> list[Any]:
    """Build FilesystemPermission rules for AutoBuild's worktree needs.

    TEMPORARY (2026-06-03): returns []. DeepAgents' _PermissionMiddleware
    does not yet support backends with command execution
    (SandboxBackendProtocol — LocalShellBackend qualifies). AutoBuild needs
    execute (Coach runs pytest, Player runs scripts), so permissions are
    dropped pending upstream support. Worktree boundary still enforced by
    LocalShellBackend(root_dir=cwd, virtual_mode=True) — no security
    regression vs current SDK reality.

    Upstream issue: https://github.com/langchain-ai/deepagents/issues/2894
    — closed/declined ("not ready to add this to the SDK at the moment;
    use custom middleware"). Restoring permissions therefore requires a
    guardkitfactory-local custom middleware (tracked separately in
    TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE), not just a version bump.

    Surfaced by: guardkit-side TASK-HMIG-009A AC-001D run 4 (2026-06-03).
    See: ../guardkit/docs/reviews/autobuild-migration/TASK-FIX-A7D3-langraph-run-4.md
    """
    logger.debug(
        "TASK-HMIG-002R-NOPERMS: returning [] — DeepAgents upstream does not "
        "yet support permissions on execute-capable backends; revisit when "
        "upstream lands the support."
    )
    return []
```

Keep the **original deny-rule code commented out below the return statement** (not deleted) so the restore work is mechanical when DeepAgents upstream catches up.

## Acceptance Criteria

- [x] **AC-001** — `build_autobuild_permissions()` returns `[]` with the documented rationale + log line. Verified at `src/guardkitfactory/harness/permissions.py:77-105`.
- [x] **AC-002** — Original deny-rule construction code preserved as a commented block immediately below the `return []`, labelled "RESTORE WHEN ..." with the upstream issue link. Verified at `src/guardkitfactory/harness/permissions.py:108-143`.
- [x] **AC-003** — Existing integration deny-rule tests in `tests/harness/test_backend_config.py` are marked `@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)` (lines 226-307). Seven tests skip with the consolidated `_NOPERMS_SKIP_REASON` pointing back to this task and `permissions.py`. Confirmed by pytest run: `7 skipped`.
- [x] **AC-004** — Regression test `test_build_autobuild_permissions_is_empty_until_upstream_lands_or_custom_middleware_ships` (line 217) asserts `build_autobuild_permissions() == []`. PASSES.
- [x] **AC-005** — Upstream issue already exists and was **closed/declined**: [langchain-ai/deepagents#2894](https://github.com/langchain-ai/deepagents/issues/2894) ("Extend `PermissionMiddleware` to support execute and task tool restrictions"). Maintainer @eyurtsev: *"We're not ready to add this to the SDK at the moment. You can use custom middleware for now to enforce execute permissions in this manner."* Cross-linked from the docstring in `permissions.py`. Because upstream declined, the "Restoring permissions when upstream lands" follow-on is reframed as `TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE` (custom middleware in-tree).
- [ ] **AC-006** — Cross-repo falsifier: guardkit-side TASK-HMIG-009A AC-001D run 5 smoke (same command as run 4 but post-fix) no longer fails with `_PermissionMiddleware does not yet support backends with command execution`. Reaches at least Coach turn 1 with non-empty `files_modified`. **Pending guardkit-side verification** — implementation in this repo is complete; cross-repo smoke run owns this AC.

## Trade-off worth being explicit about

Without the FilesystemPermission deny-rules from the original 002R design, the LangGraph Coach + specialists have unrestricted write access to the worktree filesystem (within the `LocalShellBackend(root_dir=cwd, virtual_mode=True)` boundary). The original deny rules (no writes to `.git/`, `.guardkit/state_transitions.json`, `tasks/**`) are not enforced.

For AutoBuild's threat model (operator-trusted single-tenant local-vLLM per parent-review §14.7 D-11), this is **acceptable for the canary**. The SDK harness has equivalent unrestricted access today via `permission_mode="acceptEdits"` + `cwd=worktree`. No security regression vs current reality — just a missed opportunity to do better than the SDK pending upstream support.

If the threat model later requires production-grade isolation (multi-tenant or untrusted-model deployment), parent-review D-11 applies: swap `LocalShellBackend` for a sandbox backend (Modal/Daytona/E2B).

## Out of scope

- **Modifying guardkit's `selector.py`** — the consumer is wired correctly (TASK-FIX-002R-CONSUME). The fix is in this factory; guardkit keeps calling `build_autobuild_permissions()` unchanged and now gets `[]`.
- **Custom permission middleware** — out of scope for the canary; tracked as `TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE` (parked). Note: upstream has explicitly told consumers to do exactly this (see AC-005), so "wait for upstream" is no longer a realistic restore path.
- **Switching backend** — `FilesystemBackend` has no `execute`; defeats AutoBuild's purpose.
- **Restoring permissions** — see `TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE` for the custom-middleware route. The previously-named "TASK-HMIG-002R-PERMS-RESTORE" placeholder is obsolete (upstream isn't coming).

## References

- **Surfacing log (cross-repo)**: `../guardkit/docs/reviews/autobuild-migration/TASK-FIX-A7D3-langraph-run-4.md` — verbatim DeepAgents error
- **Predecessor (this repo's wiring task)**: `tasks/completed/TASK-HMIG-002R/TASK-HMIG-002R-configure-localshellbackend-and-permissions.md`
- **Cross-repo consumer task (guardkit-side)**: `../guardkit/tasks/backlog/autobuild-harness-migration/TASK-FIX-002R-CONSUME-wire-guardkitfactory-backend-permissions-into-selector.md`
- **DeepAgents upstream issue (closed/declined)**: https://github.com/langchain-ai/deepagents/issues/2894
- **DeepAgents permissions docs**: https://docs.langchain.com/oss/python/deepagents/permissions
- **DeepAgents 0.6.7 source confirming guard still in place**: `libs/deepagents/deepagents/middleware/filesystem.py:697` at tag `deepagents==0.6.7`
- **Follow-on (custom middleware path)**: `tasks/backlog/autobuild-harness-migration/TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE-port-declined-upstream-pr-locally.md`
- **Parent-review threat model**: `../guardkit/.claude/reviews/TASK-REV-HMIG-review-report.md` §14.7 D-03 + §8 D-11

## Implementation Summary

The implementation landed in commit `5d6fd31` (folded into TASK-HMIG-007F's deepagents 0.6.7 bump), not in a dedicated commit. Verification via `/task-work TASK-HMIG-002R-NOPERMS` on 2026-06-03 confirmed all five in-repo ACs (001–005) are satisfied by the on-disk source:

- `src/guardkitfactory/harness/permissions.py:77-105` — `build_autobuild_permissions()` returns `[]` with a debug log line and the documented rationale (AC-001).
- `src/guardkitfactory/harness/permissions.py:108-143` — the original FilesystemPermission deny-rule construction is preserved verbatim as a commented `RESTORE WHEN ...` block, with the upstream issue link (AC-002).
- `tests/harness/test_backend_config.py:226-307` — seven existing deny-rule tests are decorated with `@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)` pointing back to this task and `permissions.py` (AC-003). Pytest reports `7 skipped` as expected.
- `tests/harness/test_backend_config.py:217` — new regression test `test_build_autobuild_permissions_is_empty_until_upstream_lands_or_custom_middleware_ships` PASSES, catching any accidental restoration of deny-rules before upstream support exists (AC-004).
- The `permissions.py` module docstring cross-links the declined upstream issue [langchain-ai/deepagents#2894](https://github.com/langchain-ai/deepagents/issues/2894) and the follow-on custom-middleware task (AC-005).

## Cross-Repo AC-006 Status

AC-006 (guardkit-side AC-001D run 5 smoke) is **not satisfied by this repo's work** and is **transferred to the cross-repo consumer task** `TASK-FIX-002R-CONSUME` in `../guardkit/tasks/backlog/autobuild-harness-migration/`. The in-repo work is complete and is the *enabler* of AC-006, but the smoke run itself must execute against guardkit's selector wiring. Closing this task does **not** close AC-006.

## Follow-on Work Surfaced

Verification surfaced **2 pre-existing test failures unrelated to permissions** (`test_positive_tool_flow_write_then_read_round_trips`, `test_positive_tool_flow_edit_replaces_existing_content`) — `LocalShellBackend.read()` now strips a trailing `\n` from `file_data["content"]` against `deepagents==0.6.7` where it didn't against the 0.5.x line at the time TASK-HMIG-002R landed. Triage is tracked in [`TASK-HMIG-002R-TRAILING-NL`](../../backlog/autobuild-harness-migration/TASK-HMIG-002R-TRAILING-NL-localshellbackend-read-edit-strip-trailing-newline.md) (parented to TASK-HMIG-002R, related to TASK-HMIG-007F).

## Lessons

- **Don't trust frontmatter status against on-disk source.** This task sat in `backlog/` while the implementation had already landed in a sibling task's commit (TASK-HMIG-007F's deepagents 0.6.7 bump rolled in the `permissions.py` rewrite). The verification-first workflow (read the source, then check ACs) caught it; an implement-first workflow would have re-implemented working code.
- **Cross-repo ACs belong to whoever can falsify them.** AC-006 stays open against the guardkit-side smoke run because that's where the falsifier executes. Closing this task on the strength of AC-001–005 is correct; conflating in-repo completion with cross-repo verification would have been wrong.
- **Verification often surfaces orthogonal regressions.** The trailing-newline failures had nothing to do with permissions but would have been masked indefinitely if the verification run hadn't gone broad enough to include falsifier dimension (a). Worth filing a follow-on the moment you spot it, rather than narrowing the test scope.

