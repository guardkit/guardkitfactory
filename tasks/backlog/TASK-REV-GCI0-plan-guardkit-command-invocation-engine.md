---
id: TASK-REV-GCI0
title: "Plan: GuardKit Command Invocation Engine"
task_type: review
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
complexity: 7
tags: [planning, review, guardkit, subprocess, adapters, feat-forge-005]
feature_spec: features/guardkit-command-invocation-engine/guardkit-command-invocation-engine_summary.md
feature_id: FEAT-FORGE-005
upstream_dependencies:
  - FEAT-FORGE-001  # Pipeline State Machine & Configuration (forge.yaml + worktrees)
clarification:
  context_a:
    timestamp: 2026-04-25T00:00:00Z
    decisions:
      focus: all
      tradeoff: quality
      specific_concerns:
        - subprocess timeout + cancellation correctness
        - context-resolver depth-2 cycle guard
        - worktree confinement under DeepAgents permissions
        - tolerant parser must never raise
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan GuardKit Command Invocation Engine (FEAT-FORGE-005)

## Description

Decision-making review for **FEAT-FORGE-005 — GuardKit Command Invocation Engine**.
The feature is the subprocess surface that drives every GuardKit subcommand
(`/system-arch`, `/system-design`, `/system-plan`, `/feature-spec`,
`/feature-plan`, `/task-review`, `/task-work`, `/task-complete`, `autobuild`,
and the Graphiti subcommands), plus the git/gh adapter that shares the same
subprocess contract.

The review must surface the recommended technical approach, the adapter →
tool-layer call path, the parallelisable subtask breakdown, and the seam
contracts that downstream `/feature-build` will execute against.

## Scope of Analysis

Review must cover **all areas (full sweep)** with a **quality** trade-off
priority. Specific concerns pre-flagged in `clarification.context_a`:

- subprocess timeout + cancellation correctness (no hung builds, no leaked PIDs)
- context-resolver depth-2 cycle guard (DDR-005)
- worktree confinement under DeepAgents permissions (constitutional, not
  reasoning-adjustable per ADR-ARCH-023)
- tolerant parser that **never raises** past the tool-layer boundary
  (ADR-ARCH-025 universal error contract)

Concrete areas to examine:

1. **Adapter placement.** Where does `forge.adapters.guardkit.run()` live; how
   does it compose with `context_resolver.resolve_context_flags()` (DDR-005)
   and the result parser without circular imports?
2. **Subprocess wrapper.** Single function over DeepAgents `execute`, returning
   `GuardKitResult` (Pydantic), enforcing 600-second default timeout
   (ASSUM-001), 4 KB stdout-tail capture (ASSUM-003), worktree-only `cwd`
   (Scenario "Subprocesses are executed inside the current build's worktree"),
   `--nats` flag injection.
3. **Output parser.** Tolerant — unknown shapes degrade to
   `status="success"` with empty `artefacts` rather than raising (Scenario "An
   unknown GuardKit output shape degrades to success with no artefacts").
4. **Context resolver.** Hardcoded `_COMMAND_CATEGORY_FILTER` per DDR-005 §
   "Decision — Category filter table"; `internal_docs.always_include` prepend;
   depth-2 cycle guard with `context_manifest_cycle_detected` warnings;
   filesystem-allowlist filtering with structured warnings on omitted
   documents; Graphiti subcommand bypass (no `--context` flags assembled).
5. **Tool wrappers.** Eleven `@tool(parse_docstring=True)` async wrappers, one
   per subcommand (API-tool-layer.md §6.1). Each wraps adapter call in
   try/except, returns JSON string, never raises.
6. **Progress streaming.** NATS subscriber to `pipeline.stage-complete.*` runs
   in parallel with the synchronous subprocess; live-status view must reflect
   most recent events even under back-pressure (Scenario "Progress events
   emitted faster than Forge consumes them are still observable…").
7. **Git/gh adapter.** Thin wrappers — `prepare_worktree`, `commit_all`,
   `push`, `create_pr` — sharing the subprocess permission model. Cleanup is
   best-effort (Scenario "A failed worktree cleanup is logged but does not
   prevent build completion"). Missing `GH_TOKEN` returns a structured error
   (Scenario "A pull-request creation without GitHub credentials returns a
   structured error").
8. **Concurrency.** Multiple wrappers may run in parallel within the same
   build (ASSUM-006); two concurrent builds against the same target repo
   resolve context independently (ASSUM-007 — resolver is stateless).
9. **Cancellation.** When the build is cancelled, in-flight subprocess is
   terminated and partial artefacts are not reported as completed work
   (Scenario "A cancelled build terminates its in-flight subprocess
   cleanly").
10. **Test coverage.** All 32 BDD scenarios from the feature spec must be
    addressed by at least one test (BDD scenarios become Coach-blocking
    oracles via the R2 task-level BDD runner once `bdd-linker` tags them).

## Inputs

- `features/guardkit-command-invocation-engine/guardkit-command-invocation-engine.feature`
  — 32 BDD scenarios, 5 groups
- `features/guardkit-command-invocation-engine/guardkit-command-invocation-engine_assumptions.yaml`
  — 7 assumptions, all confirmed (4 high / 3 medium / 0 low confidence)
- `docs/design/contracts/API-subprocess.md` — §2 permissions, §3 GuardKit
  adapter, §4 git/gh, §5 worktree lifecycle, §6 return-value contract
- `docs/design/contracts/API-tool-layer.md` — §6 GuardKit subcommand tools, §2
  universal error contract
- `docs/design/decisions/DDR-005-cli-context-manifest-resolution.md` —
  resolver placement, missing-manifest behaviour, category filter table,
  depth-2 cycle guard
- `docs/research/ideas/forge-build-plan.md` — FEAT-FORGE-005 row in §"GuardKit
  Command Sequence"

## Output

- Recommended technical approach with rationale
- Subtask breakdown with explicit waves, complexity (1–10), implementation
  mode (`direct` for declarative, `task-work` otherwise)
- §4 Integration Contracts where cross-task data flow exists
- Seam-test guidance per consumer task
- BDD-scenario coverage map (which task is the natural home for each scenario
  group; `bdd-linker` runs in Step 11 to lock the per-scenario `@task:` tags)
