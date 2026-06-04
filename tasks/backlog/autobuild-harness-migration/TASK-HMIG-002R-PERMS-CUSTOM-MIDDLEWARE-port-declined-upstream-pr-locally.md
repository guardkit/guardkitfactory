---
id: TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE
title: Port the declined upstream permission middleware (NinaadRao / #2894) into guardkitfactory
task_type: investigation_then_implementation
status: parked
created: 2026-06-03T12:00:00Z
updated: 2026-06-03T12:00:00Z
priority: medium
complexity: 3
effort_hours: 8
parent_task: TASK-HMIG-002R-NOPERMS
deadline: null   # not blocking the cutover — see "Why parked"
related_tasks:
  - TASK-HMIG-002R          # ✅ completed 2026-05-20 — original wiring
  - TASK-HMIG-002R-NOPERMS  # ✅ completed 2026-06-03 — current workaround (returns [])
  - TASK-HMIG-002R-NOVMODE  # ✅ completed 2026-06-03 — sibling fix (virtual_mode=False)
tags:
  - permissions
  - deepagents-upstream-declined
  - custom-middleware
  - autobuild
  - langgraph-migration
  - parked
falsifier: |
  After implementation: a guardkitfactory-local middleware (e.g.
  guardkitfactory.harness.permissions_middleware.AutoBuildPermissionsMiddleware)
  is wired into LangGraphHarness alongside the LocalShellBackend, and:

  1. AutoBuild AC-001D batch (12 runs) reaches Coach turn 1 on every run
     with no NotImplementedError raised by DeepAgents middleware.
  2. A round-trip integration test confirms the middleware blocks the same
     paths the original deny-rules did: writes to /**/.git/**,
     /**/.guardkit/state_transitions.json,
     /**/.guardkit/autobuild/*/coach_*.json, /**/tasks/** all return a
     denial via the middleware's hook (not via DeepAgents' built-in guard).
  3. build_autobuild_permissions() can be re-pointed to construct the new
     local rules and the previously-skipped deny-rule tests in
     tests/harness/test_backend_config.py pass.
---

# Task: Port the declined upstream permission middleware locally

## Why this exists

`TASK-HMIG-002R-NOPERMS` drops permissions to `[]` because DeepAgents'
`FilesystemMiddleware` raises `NotImplementedError` when given permission
rules alongside an execute-capable backend (`SandboxBackendProtocol`).

Upstream issue
[`langchain-ai/deepagents#2894`](https://github.com/langchain-ai/deepagents/issues/2894)
was closed by maintainer `@eyurtsev`:

> "We're not ready to add this to the SDK at the moment. You can use
> custom middleware for now to enforce execute permissions in this
> manner."

Contributor `@NinaadRao` had already implemented a working fix
(filesystem-rule compatibility with execute backends, plus new
`ExecutePermission` / `TaskPermission` dataclasses, 29 new unit tests,
`wcmatch.fnmatch` with the `BRACE` flag for `{git,npm}` patterns).
Upstream declined; the code remains on a fork.

**That declined PR is now the most realistic source of a restore path
for our deny-rules**. Waiting for upstream is no longer a credible plan.

## Why parked

- AutoBuild's canary threat model accepts the workaround (parent review
  §14.7 D-11). No security regression vs the SDK harness today.
- Cutover deadline pressure on `TASK-HMIG-002R-NOPERMS` (2026-06-15)
  dominates. A custom middleware is ~8 h of work; the workaround is ~30 min.
- Upstream stance may shift (a stronger community case in #2894 or a
  successor issue could reopen the door). Worth a quick re-check before
  doing the port.

## Investigation phase (do this first)

1. Re-check `#2894` and any successor issues every 2-4 weeks. If upstream
   reopens with a "happy to take a PR" comment, this task becomes
   "submit @NinaadRao's branch as a PR ourselves" instead.
2. Pull the declined PR's diff (likely from `@NinaadRao`'s fork — find the
   commit referenced in the `#2894` thread) and confirm:
   - License compatibility with our project (MIT — same family).
   - The `ExecutePermission` / `TaskPermission` shape is a superset of the
     existing `FilesystemPermission` and doesn't depend on private
     DeepAgents internals we'd have to vendor.
   - The fix path is "remove the `NotImplementedError` guard + add hooks";
     not "rewrite middleware base class". Easier to port if it's the former.
3. Estimate the surface area: number of files touched, whether it needs
   `wcmatch` (already a transitive dep), whether it can live as a
   subclass-and-override of `FilesystemMiddleware` or needs a parallel
   middleware.

## Implementation sketch (only after investigation)

Two viable shapes:

**(A) Subclass override (preferred if `NotImplementedError` is the only
real blocker).** Subclass `FilesystemMiddleware`, override `__init__` to
skip the execute-backend guard, and wire the existing `FilesystemPermission`
rules through. Keep the new `ExecutePermission` / `TaskPermission` out of
scope for v1 — we only need filesystem deny-rules to come back.

```python
# src/guardkitfactory/harness/permissions_middleware.py
class AutoBuildFilesystemMiddleware(FilesystemMiddleware):
    """FilesystemMiddleware subclass that allows filesystem permissions
    alongside execute-capable backends.

    DeepAgents upstream's guard (filesystem.py:697 at 0.6.7) raises
    NotImplementedError for this combination. Upstream issue #2894 was
    declined; this subclass is the in-tree replacement.
    """
    def __init__(self, *, permissions=None, ...):
        # Bypass the upstream guard, then call super().__init__ with
        # permissions=None and re-attach the rules ourselves on the
        # filesystem hooks only (no execute-tool gating in v1).
        ...
```

Wire it into `LangGraphHarness.invoke` via the `middleware=[...]` kwarg of
`create_deep_agent` instead of the `permissions=` shortcut.

**(B) Parallel middleware (if (A) hits library-private state).** Write a
fresh `BeforeToolMiddleware`-style hook that intercepts `write_file` /
`edit_file` tool calls, evaluates the deny patterns with `wcmatch`, and
returns a denial result. More code, more independent of DeepAgents
internals, more brittle to tool-name changes.

## Acceptance Criteria

- [ ] **AC-001** — `#2894` thread re-checked within the last 30 days of
  starting implementation. If reopened, abort port and submit the upstream
  PR instead (close this task with a pointer to the new upstream PR URL).
- [ ] **AC-002** — `guardkitfactory.harness.permissions_middleware` module
  exists with a custom middleware class that gates filesystem writes per
  the patterns currently commented out in `permissions.py`.
- [ ] **AC-003** — `LangGraphHarness` wires the new middleware into
  `create_deep_agent` via the `middleware=[...]` kwarg (not the
  `permissions=` shortcut, which still hits the upstream guard).
- [ ] **AC-004** — `build_autobuild_permissions()` either reverts to the
  original deny-rule construction (preserved as a commented block in
  `permissions.py`) **or** is repurposed as a constructor argument for
  the new middleware. Either way the four deny patterns from the parent
  review §3.4 are enforced.
- [ ] **AC-005** — The previously-skipped tests in
  `tests/harness/test_backend_config.py` (search for
  `TASK-HMIG-002R-NOPERMS` skip markers) are un-skipped and pass against
  the new middleware. The AC-004 "must equal `[]`" regression test from
  the NOPERMS task is removed.
- [ ] **AC-006** — Cross-repo falsifier: guardkit-side AutoBuild AC-001D
  batch (12 runs) completes with no `NotImplementedError` from DeepAgents
  middleware on construction.
- [ ] **AC-007** — Docstring on the new middleware class cross-references
  `#2894` and the declined-PR commit (if locatable).

## Out of scope

- **`ExecutePermission` / `TaskPermission`** — `@NinaadRao`'s declined PR
  added these as new dataclasses. AutoBuild's deny-rules are filesystem-
  only; gating `execute` per-command is a much bigger surface and unneeded
  for the canary. File a future task if needed.
- **Submitting our own upstream PR** — different question, different
  task. This task is about getting permissions back inside guardkitfactory
  without waiting on upstream.

## References

- **Upstream issue (closed/declined)**: https://github.com/langchain-ai/deepagents/issues/2894
- **DeepAgents 0.6.7 guard location**: `libs/deepagents/deepagents/middleware/filesystem.py:697` at tag `deepagents==0.6.7`
- **Parent / predecessor task**: `TASK-HMIG-002R-NOPERMS-permissions-incompatible-with-execute-backend.md`
- **Original 002R rationale**: `tasks/completed/TASK-HMIG-002R/TASK-HMIG-002R-configure-localshellbackend-and-permissions.md`
- **Parent-review threat model**: `../guardkit/.claude/reviews/TASK-REV-HMIG-review-report.md` §3.4 + §14.7 D-03 + §8 D-11
