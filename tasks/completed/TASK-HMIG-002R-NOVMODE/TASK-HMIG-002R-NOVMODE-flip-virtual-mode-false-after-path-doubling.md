---
id: TASK-HMIG-002R-NOVMODE
title: Flip LocalShellBackend(virtual_mode) to False after run-5 path-doubling failure
task_type: implementation
status: completed
created: 2026-06-03T13:30:00Z
updated: 2026-06-03T15:30:00Z
completed: 2026-06-03T15:30:00Z
completed_location: tasks/completed/TASK-HMIG-002R-NOVMODE/
priority: critical
complexity: 1
effort_hours: 1
parent_task: TASK-HMIG-002R   # Completed 2026-05-20 in this repo
sibling_task: TASK-HMIG-002R-NOPERMS   # Same surfacing chain, different layer
deadline: 2026-06-15
cross_repo:
  notes: |
    Surfaced by guardkit-side TASK-HMIG-009A AC-001D run 5 (2026-06-03)
    — see ../guardkitfactory/docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md
    for the verbatim failure (Coach decision not found at expected path
    because the Coach's write_file call with an absolute OS path was
    silently rewritten into a worktree-nested twin path).
related_tasks:
  - TASK-HMIG-002R           # ✅ completed 2026-05-20 — original wiring
  - TASK-HMIG-002R-NOPERMS   # ✅ completed 2026-06-03 — sibling layer (permissions guard)
tags:
  - bug-fix
  - localshellbackend
  - virtual-mode
  - path-resolution
  - autobuild
  - langgraph-migration
  - pre-canary-blocker
falsifier: "After fix: AC-001D re-run (run 6) reaches Coach turn 1, the Coach writes its decision file at the orchestrator-expected real-FS absolute path (not a worktree-nested doubled path), and reaches decision=accept|reject|feedback. Concretely: no 'Coach decision not found' error tied to LocalShellBackend's virtual_mode path interpretation."
---

# Task: Flip `LocalShellBackend(virtual_mode)` to `False` after run-5 path-doubling failure

## Surfaced by AC-001D run 5 (guardkit, 2026-06-03)

Sibling task `TASK-HMIG-002R-NOPERMS` cleared the DeepAgents construction-error layer in run 4. Run 5 (post-NOPERMS) reached Coach turn 1 cleanly but failed with:

```
Coach decision not found:
  /Users/.../.guardkit/worktrees/TASK-FIX-A7D3/.guardkit/autobuild/TASK-FIX-A7D3/coach_turn_1.json
```

Inspection of the worktree found the file had been written — at the **doubly-nested path**:

```
<worktree>/Users/.../.guardkit/worktrees/TASK-FIX-A7D3/.guardkit/autobuild/TASK-FIX-A7D3/coach_turn_1.json
```

The Coach's verdict content (`decision: "feedback"`, 5 detailed issues) was correct. Only the path was wrong.

**Root cause**: `LocalShellBackend(virtual_mode=True, root_dir=<worktree>)` interprets every path argument — including absolute OS paths — as virtual paths rooted at `root_dir`. The Coach's `write_file` was called with the absolute OS path that guardkit's orchestrator prompt provides (e.g. `/Users/.../coach_turn_1.json`), and the backend silently prefixed the entire absolute string onto the worktree. No error, no audit — the file landed inside the worktree at a worktree-prefixed twin path. The same mechanism that blocks `../../../etc/passwd` rewrote the Coach's absolute path.

**Cross-repo log reference**: `docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md`.

## Fix (literally one line + test updates)

In `src/guardkitfactory/harness/backend_config.py`, change:

```python
return LocalShellBackend(
    root_dir=worktree,
    virtual_mode=True,   # ← was True
    ...
)
```

to:

```python
return LocalShellBackend(
    root_dir=worktree,
    virtual_mode=False,  # TASK-HMIG-002R-NOVMODE — see module docstring
    ...
)
```

Plus a substantial docstring update in the same module explaining the run-5 path-doubling failure and the threat-model justification for accepting the loss of `virtual_mode`'s path-confinement.

## Why this is acceptable (threat-model)

- **No security regression vs the SDK harness.** The SDK harness uses `permission_mode="acceptEdits"` + `cwd=worktree`, which does not sandbox path resolution at all. Filesystem-tool path-confinement was something we *added* in `TASK-HMIG-002R` on top of the SDK harness baseline; flipping it off returns us to SDK-parity, not below it.
- **Upstream docs already note** `virtual_mode=True` *"provides NO security with shell access enabled, since commands can access any path on the system"*. AutoBuild requires `execute` (shell access). The flag was only ever filesystem-tool theatre.
- **Permission deny-rules already removed** by sibling task `TASK-HMIG-002R-NOPERMS` (DeepAgents upstream limitation). The previously-claimed falsifier-(d) guarantee from the original 002R was already partially weakened.
- **Production-grade isolation** (multi-tenant or untrusted-model) is parent-review D-11's domain: swap `LocalShellBackend` for a sandbox backend (Modal/Daytona/E2B). That's a one-line change in the same factory.

## Acceptance Criteria

- [x] **AC-001** — `build_autobuild_backend()` constructs `LocalShellBackend(virtual_mode=False, ...)`. Verified at `src/guardkitfactory/harness/backend_config.py:155-162`.
- [x] **AC-002** — Module docstring's `virtual_mode` section rewritten as `virtual_mode=False` (TASK-HMIG-002R-NOVMODE, 2026-06-03), including the run-5 path-doubling diagram and the threat-model rationale (operator-trust + parent-review §14.7 D-11). Verified at `src/guardkitfactory/harness/backend_config.py:22-67`.
- [x] **AC-003** — Test `test_build_autobuild_backend_enables_virtual_mode` renamed to `test_build_autobuild_backend_disables_virtual_mode` and asserts `backend.virtual_mode is False`. Verified at `tests/harness/test_backend_config.py:82-92`. PASSES.
- [x] **AC-004** — Positive tool-flow tests rewritten to use real absolute paths under `tmp_path` instead of virtual paths rooted at `/` (was `/sample.txt`, now `str(tmp_path / "sample.txt")`). The test contract verified is now "absolute paths the orchestrator hands the LLM are interpreted literally" — exactly the run-6 path-resolution shape. Verified at `tests/harness/test_backend_config.py:142-218`. ALL PASS.
- [x] **AC-005** — Regression test `test_absolute_path_no_longer_doubled_under_worktree` directly asserts the run-5 failure mode is gone (absolute path lands at the absolute path, NOT at the doubled path). Verified at `tests/harness/test_backend_config.py:208-228`. PASSES.
- [x] **AC-006** — `test_traversal_above_worktree_is_blocked` marked `@pytest.mark.skip` with a full pointer-to-D-11 (sandbox-backend swap) for the restore path. Verified at `tests/harness/test_backend_config.py:325-352`. Skipped intentionally.
- [x] **AC-007** — Cross-repo falsifier **MET** in AC-001D run 6 (2026-06-03, post-NOVMODE): Coach approved, `decision=APPROVED`, Coach wrote its file at the orchestrator-expected real-FS path. Also: secondary win — code-reviewer specialist dropped from 870s+ (run 5) → ~250s (run 6) because its own `read_file` calls were also being silently rewritten under `virtual_mode=True`. Log: [`docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-6-success.md`](../../../docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-6-success.md).

## Trade-off worth being explicit about

Flipping `virtual_mode=False` removes the layer that rejected `../../../etc/passwd` at the backend boundary. Under the new configuration, an LLM that emits an absolute path outside the worktree (e.g. `/etc/passwd`) gets it interpreted literally. Mitigations in place:

1. **Operator-trust model** — single-tenant, local-vLLM, operator-supervised runs (parent-review §14.7 D-11). Same trust assumptions as the SDK harness today.
2. **`inherit_env=False`** — environment leakage from the operator's shell is stripped. No `AWS_PROFILE` / `OPENAI_API_KEY` / etc. reach the agent's subprocess.
3. **Prompt-side grounding** — guardkit's orchestrator prompts all reference paths inside the worktree. An out-of-bounds write would require the LLM to ignore both the prompt and the worktree context.
4. **`cwd=worktree`** — relative paths still default to the worktree.

If the threat model later moves to multi-tenant or untrusted-model deployment, the correct response is **swap the backend**, not re-enable `virtual_mode`. Parent-review D-11 covers this explicitly.

## Out of scope

- **Sandbox backend (Modal/Daytona/E2B) integration** — parent-review D-11, file a fresh task if/when needed.
- **Prompt-side virtual-path migration** — possible (teach the orchestrator to feed virtual paths to the LangGraph harness only) but heavy, and would only swap the trade-off back without changing the threat-model position. Not pursued.
- **Re-enabling `virtual_mode` if `LocalShellBackend` upstream changes behaviour** — unlikely worth doing; would require a regression test cycle to re-establish run-6 parity.

## References

- **Surfacing log (failure)**: [`docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md`](../../../docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md) — Coach decision not found; verdict written at doubled path
- **Falsifier log (success)**: [`docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-6-success.md`](../../../docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-6-success.md) — Coach approved end-to-end
- **Predecessor (original wiring)**: [`tasks/completed/TASK-HMIG-002R/TASK-HMIG-002R-configure-localshellbackend-and-permissions.md`](../TASK-HMIG-002R/TASK-HMIG-002R-configure-localshellbackend-and-permissions.md)
- **Sibling (permissions layer)**: [`tasks/completed/TASK-HMIG-002R-NOPERMS/TASK-HMIG-002R-NOPERMS-permissions-incompatible-with-execute-backend.md`](../TASK-HMIG-002R-NOPERMS/TASK-HMIG-002R-NOPERMS-permissions-incompatible-with-execute-backend.md)
- **DeepAgents `LocalShellBackend` docs (`virtual_mode` semantics)**: https://docs.langchain.com/oss/python/deepagents/backends
- **Parent-review threat model**: `../guardkit/.claude/reviews/TASK-REV-HMIG-review-report.md` §14.7 D-11
