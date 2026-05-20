---
id: TASK-HMIG-002R
title: Configure LocalShellBackend + FilesystemPermission for AutoBuild's worktree needs
status: backlog
task_type: implementation
created: 2026-05-19T20:30:00Z
updated: 2026-05-19T20:30:00Z
priority: critical
complexity: 4
deadline: 2026-06-15
parent_review: TASK-REV-HMIG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 1
parallel_group: 1B
implementation_mode: task-work
intensity: standard
effort_hours: 6
depends_on:
  - TASK-HMIG-000R   # scaffold
  - TASK-HMIG-001B   # LangGraphHarness must exist to receive the backend
cross_repo:
  notes: Pure guardkitfactory-side work. The output of this task plugs into the LangGraphHarness from TASK-HMIG-001B, which is then consumed by guardkit/orchestrator/agent_invoker.py via TASK-HMIG-006.
falsifier: "Integration test: instantiate LangGraphHarness from TASK-HMIG-001B with the configured LocalShellBackend + permissions from this task; invoke an agent (stub model with canned tool-use responses) against a fixture worktree; assert (a) ls/read_file/write_file/edit_file/glob/grep/execute all succeed inside the worktree, (b) FilesystemPermission deny-rule blocks writes to .git/, .guardkit/state_transitions.json, and tasks/*, (c) execute honours timeout=600 and max_output_bytes=1_000_000, (d) traversal outside root_dir (e.g. ../../../etc/passwd) is blocked by virtual_mode=True."
tags:
  - autobuild
  - deepagents-backend
  - permissions
  - langgraph-migration
---

# Task: Configure LocalShellBackend + FilesystemPermission

## Description

Per parent review Revision 1 (D-03), AutoBuild does NOT write custom
`@tool`-decorated functions for `read_file / write_file / edit_file / bash`.
Instead, it uses DeepAgents' built-in tools through `LocalShellBackend`
(which provides `ls / read_file / write_file / edit_file / glob / grep / execute`)
gated by `FilesystemPermission` rules.

This task ships the factory functions that produce a configured backend + a
configured permissions list, suitable for plugging into the
`LangGraphHarness(backend=..., permissions=...)` constructor from
TASK-HMIG-001B.

## Acceptance Criteria

- [ ] AC-001: New module `src/guardkitfactory/harness/backend_config.py`
      exposing a `build_autobuild_backend(worktree: Path) -> LocalShellBackend`
      factory.
- [ ] AC-002: The factory returns
      `LocalShellBackend(root_dir=worktree, virtual_mode=True, env=<safe-env-dict>, inherit_env=False, timeout=600, max_output_bytes=1_000_000)`.
  - `<safe-env-dict>` minimally: `{"PATH": "/usr/bin:/bin", "HOME": str(worktree), "TMPDIR": str(worktree / ".tmp")}`. Add `PYTHONPATH` to the worktree's venv if present.
  - `inherit_env=False` is deliberate — we control what the agent sees.
- [ ] AC-003: New module `src/guardkitfactory/harness/permissions.py` exposing
      a `build_autobuild_permissions() -> list[FilesystemPermission]` factory
      returning deny-rules for:
  - `.git/**` (deny write and edit)
  - `.guardkit/state_transitions.json` (deny write and edit — orchestrator owns this file)
  - `.guardkit/autobuild/*/coach_*.json` (deny — Coach writes this via orchestrator, not via Player tools)
  - `tasks/**` (deny write and edit — Player should not modify task files directly)
- [ ] AC-004: Integration test at
      `tests/harness/test_backend_config.py` covering the four falsifier
      dimensions:
  - Positive tool flow (all built-in tools succeed in a fixture worktree)
  - Permission denial (write to `.git/HEAD` returns an error, file unchanged)
  - Timeout (`execute("sleep 700")` returns a timeout result within 600s + a small fuzz)
  - Traversal block (`read_file("../../../etc/passwd")` is rejected)
- [ ] AC-005: Documentation block at the top of `backend_config.py` explains:
  - Why `virtual_mode=True` is set even though it "provides no security with shell access enabled" (we rely on it for filesystem-tool path-confinement; the `execute` tool security is operator-trust + worktree boundary)
  - The choice of `inherit_env=False` (explicit env control)
  - Why these specific deny-rules (each is traced to a specific risk: state-bridge consistency, Coach trust boundary, etc.)
- [ ] AC-006: `PolicyWrapper` extension point documented but not implemented.
      A comment in `backend_config.py` notes: "If GuardKit-specific
      atomic-write or backup-on-edit semantics are required later, layer a
      `PolicyWrapper` around the returned backend per the
      [deepagents/backends policy-hook pattern](https://docs.langchain.com/oss/python/deepagents/backends).
      Do NOT fork custom `@tool` implementations."
- [ ] AC-007: `src/guardkitfactory/__init__.py` exposes both factories as
      top-level symbols.

## Implementation Notes

- The deny-rule list (AC-003) is informed by review §3.4 (Tool surface) and
  the path-string-mismatch rule (state_bridge transitions need consistent
  source-of-truth). If during canary validation (TASK-HMIG-009) additional
  paths need denying, add them as a follow-up rather than over-broadening here.
- `LocalShellBackend` docs explicitly note that `virtual_mode=True` provides
  no security with shell access enabled. For AutoBuild's threat model
  (operator-trusted local-vLLM, single-tenant), this is acceptable. If the
  threat model later requires production-grade isolation, decision D-11
  recommends swapping `LocalShellBackend` for a sandbox backend (Modal,
  Daytona, etc.) — that's a one-line change in this module.
- DO NOT define custom `@tool` functions for read/write/edit/bash. The
  built-in tools are battle-tested and the permissions surface only applies
  to the built-ins (per LangChain docs cited in review §14.7).
- The `timeout=600` (10 min) and `max_output_bytes=1_000_000` (1 MB) values
  are bigger than DeepAgents' defaults (120s, 100KB) because AutoBuild's
  Coach often runs full test suites that exceed both. Document the override.

## References

- Parent review §14.7 (Revision 1) — D-03 rewrite to use built-in tools
- Parent review §3.4 — current tool surface mapping
- Parent review §9 R-12 — cross-repo version pinning hazard (relevant because
  this depends on DeepAgents API surface staying stable)
- Decision D-11 (parent review §8) — sandbox backend swap is a one-line change
- DeepAgents backends docs: <https://docs.langchain.com/oss/python/deepagents/backends>
- DeepAgents permissions docs: <https://docs.langchain.com/oss/python/deepagents/permissions>

## Notes

This task is the centrepiece of Revision 1's effort savings. The v1 plan
(TASK-HMIG-002/003/004/005, ~22h of custom-tool implementation) is collapsed
into the ~6h here. If the work runs significantly long (>8h), surface that
as evidence the operator should consider falling back to v1 custom tools per
review §14.6 "If the v1 recommendation is preferred."
