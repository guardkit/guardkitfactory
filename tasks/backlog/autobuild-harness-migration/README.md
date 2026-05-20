# Feature: AutoBuild Harness Migration — `guardkitfactory` side

> **Feature ID**: FEAT-HMIG
> **Parent review**: TASK-REV-HMIG (in sibling repo `guardkit`)
> **Sibling feature folder**: `~/Projects/appmilla_github/guardkit/tasks/backlog/autobuild-harness-migration/`
> **Review report**: `~/Projects/appmilla_github/guardkit/.claude/reviews/TASK-REV-HMIG-review-report.md` (with Revision 1 + Revision 2 in §14)
> **Deadline**: 2026-06-15 (Anthropic enforces API-key validation)
> **Cutover target**: 2026-06-10 (5-day validation margin)

## Why this folder exists

This is the `guardkitfactory` half of the AutoBuild harness migration. The
migration's "home base" is in the sibling repo `guardkit`
(see the sibling README link above). Tasks that touch source code in *this*
repo live here; tasks that touch source code in `guardkit` live in the sibling
folder. Each task file declares the cross-repo work in its acceptance criteria.

## Role of `guardkitfactory` in the migration

Per Revision 2 / D-01 of the parent review, `guardkitfactory` is the new sibling
repo housing the LangGraph/DeepAgents-based replacement for the Claude Agents
SDK harness. It was initialised from the `langchain-deepagents` template
(`guardkit init langchain-deepagents`) and provides:

- `LangGraphHarness` (implementation of the `HarnessAdapter` interface defined in `guardkit`)
- DeepAgents backend + permissions configuration for AutoBuild's worktree needs
- The `BDDPlugin` interface + `PytestBDDPlugin` (Python's BDD plugin implementation)

`guardkit` (this repo's sibling) installs `guardkitfactory` as a runtime
dependency and dispatches through the `HarnessAdapter` interface to either
the legacy `ClaudeSDKHarness` or the new `LangGraphHarness` based on
`GUARDKIT_HARNESS=sdk|langgraph` env var.

## Cross-repo coordination

| In `guardkit` (sibling repo) | In `guardkitfactory` (this repo) |
|---|---|
| TASK-HMIG-001A (HarnessAdapter ABC) | TASK-HMIG-000R (complete source scaffold) |
| TASK-HMIG-006 (agent_invoker dispatch refactor) | TASK-HMIG-001B (LangGraphHarness skeleton) |
| **TASK-HMIG-008R** *(Revision 3: LLM Coach primary + evidence-supplier refactor)* | TASK-HMIG-002R (LocalShellBackend + permissions) |
| TASK-HMIG-009 (canary validation) | TASK-HMIG-007 (BDD plugin interface + PytestBDDPlugin) |
| TASK-HMIG-010 (full feature autobuild) | — |

> **Revision 3 (2026-05-20)**: TASK-HMIG-008 was expanded from a 4h honesty-Layer-1 wiring task to a 12h architectural correction (TASK-HMIG-008R). The Coach is now restored to LLM-primary per the Block adversarial-cooperation paper; the existing deterministic `CoachValidator` is refactored into a `CoachEvidenceBundle` supplier. The `guardkitfactory`-side change: the LLM Coach is invoked through `LangGraphHarness` with read-only tools — same harness as the Player, different tool surface. See sibling repo's `TASK-HMIG-008R-*.md` and main report §14.9 for the full architectural rationale.

## Task summary

| ID | Title | Wave | Effort | Status |
|---|---|---|---|---|
| TASK-HMIG-000R | Complete `guardkitfactory` source scaffold (pyproject + lib/ + src/ + CI) | 1 | 4h | backlog |
| TASK-HMIG-001B | Implement `LangGraphHarness` skeleton | 1 | 2h | backlog |
| TASK-HMIG-002R | Configure `LocalShellBackend` + `FilesystemPermission` for AutoBuild | 1 | 6h | backlog |
| TASK-HMIG-007 | Implement BDDPlugin interface + PytestBDDPlugin + C1-C6 contract tests | 2 | 8h | backlog |

Total in `guardkitfactory`: **4 tasks, ~20h**. See the sibling repo's README for the additional ~28h of guardkit-side work.

> **TASK-HMIG-000 was already partially completed by the operator**: they have run
> `guardkit init langchain-deepagents` to set up the `.claude/` + `tasks/` GuardKit
> workflow surface. **TASK-HMIG-000R** picks up from there to render the template's
> Python source scaffold (lib/, src/, pyproject.toml, CI) which `guardkit init`
> alone did not produce.

## Next steps

1. Read the sibling `IMPLEMENTATION-GUIDE.md` for wave-by-wave execution across both repos.
2. Start with TASK-HMIG-000R (here) — it unblocks all other guardkitfactory tasks.
3. Once TASK-HMIG-000R lands, TASK-HMIG-001B + TASK-HMIG-002R can proceed in parallel.
4. TASK-HMIG-007 (BDD plugin) is independent of the others; can start as soon as TASK-HMIG-000R is done.

## See also

- Parent review report: `~/Projects/appmilla_github/guardkit/.claude/reviews/TASK-REV-HMIG-review-report.md`
- Implementation guide: `~/Projects/appmilla_github/guardkit/tasks/backlog/autobuild-harness-migration/IMPLEMENTATION-GUIDE.md`
- LangChain DeepAgents docs: <https://docs.langchain.com/oss/python/deepagents/overview>
- DeepAgents backends (the surface this repo wraps): <https://docs.langchain.com/oss/python/deepagents/backends>
- The deploy-coding-agent example that informed this design: <https://github.com/langchain-ai/deepagents/tree/main/examples/deploy-coding-agent>
