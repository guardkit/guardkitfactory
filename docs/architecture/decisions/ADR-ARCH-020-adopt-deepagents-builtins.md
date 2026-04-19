# ADR-ARCH-020: Adopt DeepAgents 0.5.3 built-ins — `write_todos`, filesystem, `execute`, `task`, `interrupt`, Memory Store, permissions, auto-summarisation

- **Status:** Accepted
- **Date:** 2026-04-18
- **Session:** `/system-arch` Category 4 Revision 9

## Context

Rich flagged that the architecture was missing the latest DeepAgents SDK capabilities. Inspection of `docs.langchain.com/oss/python/deepagents/overview` and `github.com/langchain-ai/deepagents` (current release: **0.5.3, 2026-04-15**) revealed built-ins we were about to re-implement:

- `write_todos` — built-in planning tool
- Filesystem tools — `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`
- `execute` — shell with sandbox support
- `task` — sub-agent delegation with isolated context
- LangGraph `interrupt()` — native human-in-the-loop pause
- Permissions system — declarative filesystem/shell/network allowlists
- Long-term Memory Store — LangGraph primitive for per-thread recall
- Context management — auto-summarisation when conversations grow

Initial design had custom `git_tools`, `pr_tools`, `file_tools`, `queue_tools` — redundant with the built-ins.

## Decision

Adopt the full set of DeepAgents 0.5.3 built-ins:

| Built-in | Use in Forge |
|---|---|
| `write_todos` | The reasoning model's planning tool — todo items are the emergent stage labels (ADR-ARCH-016) |
| Filesystem tools | Reading project files, context manifests, writing stage outputs; replaces custom file tools |
| `execute` | Substrate for all subprocess invocation (GuardKit, git, gh); replaces custom subprocess wrappers |
| `task` | Dynamic sub-agent spawning; 2 pre-declared sub-agents (`build_plan_composer`, `autobuild_runner`), everything else spawned on demand |
| `interrupt()` | PAUSED state mechanism — ADR-ARCH-021 |
| Permissions system | Safety constraints — ADR-ARCH-023 |
| Memory Store | Per-thread recall — ADR-ARCH-022 complements Graphiti (not replaces) |
| Auto-summarisation | Long build conversations (30–60 min, 200–500 turns) handled natively — no custom compaction |

**Forge-specific `@tool`s** are limited to primitives DeepAgents doesn't provide:
- `dispatch_by_capability` (NATS fleet call)
- `approval_tools` (ApprovalRequestPayload builders)
- `notification_tools` (NotificationPayload emitters)
- `graphiti_tools` (record/retrieve priors)
- `guardkit_*` (subcommand composition on top of `execute`)
- `history_tools` (SQLite schema'd writes)

**Dropped as custom modules** (subsumed by built-ins): `git_tools`, `pr_tools`, `file_tools`, `queue_tools`, custom subprocess wrapper, custom compaction module.

## Consequences

- **+** Net reduction in Forge source — less custom code to maintain, test, and debug.
- **+** Inherits DeepAgents' ongoing improvements — future 0.6/0.7 features land without Forge re-architecture.
- **+** Planning via `write_todos` neatly pairs with the "emergent stage labels" idea (ADR-ARCH-016) — the todo list IS the build's narrative.
- **+** Auto-summarisation caps prompt growth on long builds — caps per-turn cost (ADR-ARCH-030 budget).
- **+** Sandbox support via `execute`'s pluggable backends is free when Rich wants Phase-3 isolation from the conversation starter.
- **−** Pinned to DeepAgents `>=0.5.3, <0.6`. Major-version upgrades require compatibility review.
- **−** Built-in behaviour assumed (e.g. `interrupt()` semantics) — validated by this session's WebFetch but needs implementation-time verification.

---

**Amendment — 2026-04-19:** The sync-vs-async split for the two pre-declared sub-agents (`build_plan_composer` sync; `autobuild_runner` async via `AsyncSubAgent`) is refined in [ADR-ARCH-031](./ADR-ARCH-031-async-subagents-for-long-running-work.md). This is additive; the Context and Decision sections above are unchanged.
