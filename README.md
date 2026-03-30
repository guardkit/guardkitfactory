# GuardKit Factory

Software factory using GuardKit's primitives and AutoBuild.

## What This Is

An autonomous Pipeline Orchestrator agent that drives the GuardKit slash command lifecycle — from architecture through to verified, deployable code. Uses a two-model architecture where a reasoning model (Gemini/Claude) orchestrates and validates, while an implementation model (Claude Code SDK or local vLLM) executes.

Built using the LangChain DeepAgents SDK with `AsyncSubAgent` for non-blocking long-running builds.

## Architecture

See `docs/research/` for full architecture documents:

- **[Consolidated Build Plan](docs/research/pipeline-orchestrator-consolidated-build-plan.md)** — What exists, what needs building, and the dependency sequence (Phase 0-5)
- **[Motivation](docs/research/pipeline-orchestrator-motivation.md)** — The observation that started this: 3 decisions across 43 tasks, 93% defaults accepted
- **[Conversation Starter](docs/research/pipeline-orchestrator-conversation-starter.md)** — Context brief for `/system-arch` + `/system-design` session

### C4 Diagrams

- [System Context (L1)](docs/research/c4-system-context.svg) — How the orchestrator fits in the Ship's Computer fleet
- [Component Map](docs/research/c4-component-map.svg) — What exists vs what needs building
- [Build Order](docs/research/c4-build-order.svg) — Dependency sequence across phases

## Approach

This project follows the **exemplar-first methodology** proven in the original template creation:

1. **Exemplar** (`guardkit/deepagents-orchestrator-exemplar`) — Combine `nvidia_deep_agent` + `deepagents-player-coach-exemplar` + `AsyncSubAgent` patterns
2. **Validate** — TASK-REV on the exemplar (3 reviews)
3. **Build** — `/system-arch` → `/system-design` → AutoBuild from validated exemplar
4. **Prove** — Run in production
5. **Harvest** — Extract `langchain-deepagents-adversarial` template back into GuardKit

## Related Repos

| Repo | Purpose |
|------|---------|
| [guardkit/guardkit](https://github.com/guardkit/guardkit) | CLI tool with slash commands and AutoBuild |
| [guardkit/deepagents-orchestrator-exemplar](https://github.com/guardkit/deepagents-orchestrator-exemplar) | Exemplar that feeds this project |
| [guardkit/agentic-dataset-factory](https://github.com/guardkit/agentic-dataset-factory) | Working Player-Coach pipeline (first project built with templates) |
| [guardkit/deepagents-player-coach-exemplar](https://github.com/guardkit/deepagents-player-coach-exemplar) | Original exemplar that produced the base template |

## Domain

**guardkitfactory.ai** (available)

## License

MIT
