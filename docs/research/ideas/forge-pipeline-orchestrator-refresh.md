# GuardKit Factory — Pipeline Orchestrator Agent Refresh
## Conversation Starter for Strategic Re-Alignment
## Date: 11 April 2026
## Status: Exploration — captures how the ecosystem has evolved since March 2026
## Repo: `guardkit/guardkitfactory`
## Related: `specialist-agent` unified harness (Phase 1B), fleet master index

---

## Purpose of this document

The pipeline orchestrator conversation starter (`pipeline-orchestrator-conversation-starter.md`) was written in March 2026. Since then, significant architectural decisions and implementations have changed the landscape. This document captures what's different and how the orchestrator should evolve to take advantage of the specialist agent fleet rather than doing everything itself.

**This is not a replacement for the original conversation starter.** It's an addendum that should be read alongside it. The original captures the correct motivation, modes, and checkpoint protocol. This document captures the new inter-agent collaboration patterns.

---

## What's Changed Since March 2026

### 1. The Specialist Agent Harness Exists

The architect-agent codebase (being renamed to `specialist-agent`) has been proven in Phase 0:
- Player-Coach adversarial loop: 0.75 score, 93 seconds, 1006 tests green
- Weighted evaluation with 6 criteria and 4 detection patterns
- Configurable LLM provider (Claude, GPT, Gemini, local vLLM)

Phase 1B (in progress) refactors it into a unified harness with role-based configuration:
- `--role architect` → conversation starters with C4 diagrams, ADRs
- `--role product-owner` → product documents with user stories, acceptance criteria
- Same generation loop, scoring engine, session lifecycle
- Different prompts, criteria, output types per role

**Implication for the orchestrator:** The orchestrator doesn't need to embed architectural reasoning or product documentation logic. It delegates to specialist agents via NATS and consumes their output.

### 2. The Product Owner Agent Is No Longer Separate

The `guardkit/product-owner-agent` repo has been deleted. The product owner is now a role within the specialist-agent harness. The orchestrator calls `specialist-agent --role product-owner` (or via NATS `agents.command.product-owner-agent`) rather than a separate service.

### 3. NATS Fleet Integration Is Designed (Phase 3 of specialist-agent)

The specialist-agent's Phase 3 defines:
- `AgentManifest` with intent patterns and tool capabilities per role
- Command/result messaging via `agents.command.{agent_id}` / `agents.result.{agent_id}`
- Direct tool calls via `agents.{agent_id}.tools.{tool_name}`
- Feasibility assessments as a first-class agent-to-agent capability
- Heartbeat lifecycle (register → heartbeat → deregister)

**Implication:** The orchestrator can discover and call specialist agents dynamically via NATS, rather than invoking CLI commands as subprocesses. The tool inventory for the orchestrator shifts from "invoke GuardKit slash commands" to "dispatch to fleet agents + invoke GuardKit slash commands for implementation."

### 4. Fine-Tuned Models Are Per-Role

Phase F of the specialist-agent defines per-role fine-tuning:
- `architect-gemma4-31b` — fine-tuned on architecture books (Ousterhout, Ford, Farley)
- `product-owner-gemma4-31b` — fine-tuned on product management books (Cagan, Patton)
- Deployed to AWS Bedrock CMI (serverless, pay-per-use)

**Implication:** The orchestrator doesn't need to be fine-tuned itself — it's a coordinator, not a specialist. It uses a strong reasoning model (Claude, Gemini) for orchestration decisions and delegates domain judgment to fine-tuned specialists.

### 5. The `/feature-spec` Command Uses Propose-Review Methodology

The `/feature-spec` v2 command (FEAT-008 in the guardkit repo) uses Specification by Example — the AI proposes Gherkin scenarios, the human curates. This is a fundamentally different interaction model from the original conversation starter's assumption that slash commands are simple tool invocations.

**Implication:** Some pipeline stages are interactive (feature-spec requires human curation of scenarios). The orchestrator needs to handle both autonomous stages (system-arch → system-design) and interactive stages (feature-spec with propose-review cycle).

---

## The Agent Name Question

The pipeline orchestrator needs a short, distinctive name for fleet identity and daily use. "Pipeline Orchestrator" is descriptive but verbose.

### Candidates

| Name | Rationale | Feel |
|------|-----------|------|
| **Forge** | Where raw materials become finished products. Ties to DDD talk "software factory" theme. Short, strong, distinctive | Industrial, purposeful |
| **Shipwright** | The builder of the ship. Ties to "Ship's Computer" metaphor. A shipwright builds and maintains the vessel | Nautical, craftsmanlike |
| **Quartermaster** | The officer who manages supplies and logistics. Coordinates resources without being any single specialist | Military, systematic |
| **Conductor** | Orchestrates the orchestra. Each musician (agent) is a specialist; the conductor coordinates timing and dynamics | Musical, elegant |
| **Anvil** | Where things are hammered into shape. The forge's working surface | Industrial, minimal |
| **Foundry** | Where raw metal is cast into components. Factory metaphor | Industrial, solid |

**Recommendation: Forge.** It's short (5 letters, one syllable), ties directly to the "software factory" DDD talk narrative, and the metaphor is precise — raw materials (product docs, conversation starters) go in, finished products (deployed code) come out. The forge doesn't mine the ore (that's the product owner) or design the blueprint (that's the architect) — it does the making.

`forge build finproxy` reads better than `pipeline-orchestrator build finproxy`.

Fleet identity: `agent_id: "forge"`, NATS topic: `agents.command.forge`.

---

## Revised Architecture: Forge as Fleet Coordinator

### The Old Model (March 2026)

The orchestrator invokes GuardKit slash commands as tools, doing everything itself:

```
Forge Agent
  ├── tool: system_arch        (invoke /system-arch directly)
  ├── tool: system_design      (invoke /system-design directly)
  ├── tool: feature_spec       (invoke /feature-spec directly)
  ├── tool: feature_plan       (invoke /feature-plan directly)
  ├── tool: autobuild          (invoke autobuild directly)
  ├── tool: graphiti_seed      (invoke graphiti add-context)
  └── tool: verify             (run tests)
```

### The New Model (April 2026)

The Forge delegates domain judgment to specialist agents via NATS, and uses GuardKit slash commands for implementation stages that don't have a specialist agent:

```
Forge Agent
  │
  ├── DELEGATE to specialist agents (via NATS)
  │   ├── product-owner-agent: "Generate product documentation from these raw inputs"
  │   │   → returns ProductDocument (user stories, acceptance criteria, backlog)
  │   ├── architect-agent: "Generate architecture from these product docs"
  │   │   → returns ConversationStarter (C4, ADRs, open questions)
  │   ├── architect-agent: "Is this feature feasible given our architecture?"
  │   │   → returns FeasibilityAssessment
  │   └── (future) ux-designer-agent: "Design the user flows for this feature"
  │       → returns UX spec
  │
  ├── INVOKE GuardKit commands (for implementation stages)
  │   ├── /system-arch      (consumes architect-agent output as conversation starter)
  │   ├── /system-design    (consumes /system-arch output)
  │   ├── /feature-spec     (consumes product-owner output + architecture)
  │   ├── /feature-plan     (consumes /feature-spec output)
  │   ├── autobuild         (implements tasks from /feature-plan)
  │   └── /task-review      (reviews issues, creates fix tasks)
  │
  ├── COORDINATE
  │   ├── graphiti_seed     (seed outputs into knowledge graph after each stage)
  │   ├── verify            (run tests, integration checks)
  │   ├── git operations    (branch, commit, PR)
  │   └── ci_trigger        (GitHub Actions)
  │
  └── CHECKPOINT (human approval via NATS agents.approval.*)
      ├── After product documentation (James reviews)
      ├── After architecture (Rich reviews)
      ├── After feature specs (propose-review cycle)
      └── After build (verification)
```

### What This Changes

1. **The Forge doesn't need architectural judgment.** It delegates to the architect-agent. The architect-agent has fine-tuned domain knowledge (Phase F) — the Forge's reasoning model doesn't need it.

2. **The Forge doesn't need product management judgment.** It delegates to the product-owner-agent. James's review checkpoint is after the product-owner-agent produces documentation, not after the Forge produces it.

3. **The Forge IS the pipeline coordinator.** Its core competency is: knowing what stage comes next, which agent to call, what context to pass, when to checkpoint with a human, and how to recover from failures. This is orchestration reasoning, not domain reasoning.

4. **The Forge discovers agents dynamically.** Via NATS fleet registration, the Forge finds which agents are available, what tools they offer, and routes work accordingly. If the architect-agent isn't running, the Forge can fall back to invoking `/system-arch` directly (degraded mode).

5. **The Forge handles interactive stages differently.** `/feature-spec` with propose-review is not a simple tool invocation — it's a multi-turn interaction. The Forge either passes through to the human for the curation phase, or (future) uses the product-owner-agent to do the curation.

---

## Revised Pipeline Flow

### Mode A: Greenfield (with specialist agents)

```
Raw input (idea, brief, product concept)
    │
    ▼
Forge dispatches to product-owner-agent (via NATS)
    → ProductDocument (user stories, acceptance criteria, backlog)
    │
    ▼
🔴 CHECKPOINT: James reviews product document
    │
    ▼
Forge dispatches to architect-agent (via NATS)
    → ConversationStarter (C4, ADRs, open questions, constraints)
    │
    ▼
🔴 CHECKPOINT: Rich reviews architecture
    │
    ▼
Forge invokes /system-arch (consumes ConversationStarter as input)
    → ARCHITECTURE.md, ADRs, C4 diagrams (full resolution)
    │
    ▼
Forge invokes /system-design
    → DESIGN.md, API contracts, data models
    │
    ▼
Forge seeds outputs to Graphiti
    │
    ▼
Forge invokes /feature-spec × N (with propose-review cycle)
    → BDD feature files, assumptions manifests
    │
    ▼
🔴 CHECKPOINT: Human curates feature specs (propose-review)
    │
    ▼
Forge invokes /feature-plan × N
    → Task breakdowns per feature
    │
    ▼
Forge invokes autobuild × N (sequential on GB10, parallel on Bedrock)
    → Implemented features
    │
    ▼
Forge invokes verify (tests, integration checks)
    │
    ▼
Forge triggers CI/CD (git push, PR, GitHub Actions)
    │
    ▼
🔴 CHECKPOINT: Human reviews PR
```

### Key Difference from March Version

The first two stages (product documentation and architecture) are now **agent-to-agent delegations**, not slash command invocations. The specialist agents bring fine-tuned domain judgment that the Forge doesn't have. The Forge brings pipeline coordination that the specialists don't have.

The specialist agents produce intermediate artifacts (ProductDocument, ConversationStarter) that feed into the GuardKit slash commands. The slash commands do the detailed implementation work (/system-arch resolves open questions, /system-design produces API contracts, etc.). The specialists provide the strategic input; the slash commands provide the tactical execution.

---

## Forge Tool Inventory (Revised)

### Fleet Agent Tools (via NATS)

| Tool | Target Agent | Input | Output | Async |
|------|-------------|-------|--------|-------|
| `delegate_product_docs` | product-owner-agent | Raw input, product brief | ProductDocument | Yes |
| `delegate_architecture` | architect-agent | ProductDocument, scope | ConversationStarter | Yes |
| `check_feasibility` | architect-agent | Feature summary, constraints | FeasibilityAssessment | No (30s) |
| `discover_agents` | fleet registry | — | Available AgentManifests | No |

### GuardKit Command Tools (direct invocation)

| Tool | Input | Output |
|------|-------|--------|
| `system_arch` | ConversationStarter path | ARCHITECTURE.md, ADRs |
| `system_design` | ARCHITECTURE.md path | DESIGN.md, contracts |
| `feature_spec` | Architecture + feature description | BDD feature file |
| `feature_plan` | Feature spec path | Task breakdown |
| `autobuild` | Feature ID | Build result |
| `task_review` | Subject path | Review report |

### Infrastructure Tools

| Tool | Input | Output |
|------|-------|--------|
| `graphiti_seed` | Document paths, type | Seed confirmation |
| `graphiti_query` | Query string | Retrieved context |
| `verify` | Project path, test command | Pass/fail |
| `git_operations` | Branch/commit/PR params | Git result |
| `nats_publish` | Topic, payload | Delivery confirmation |

### Degraded Mode

If a specialist agent is unavailable (not registered in fleet), the Forge falls back:
- No product-owner-agent → Forge uses `/feature-spec` directly with raw input (lower quality product docs)
- No architect-agent → Forge uses `/system-arch` directly with a basic conversation starter (no fine-tuned architectural judgment)
- Both available → Full pipeline with specialist delegation (best quality)

This degradation is automatic — the Forge checks the fleet registry at pipeline start and adapts its tool selection.

---

## Forge Agent Identity

```yaml
agent_id: forge
name: Forge
description: "Pipeline orchestrator — coordinates specialist agents and GuardKit commands to produce verified, deployable code from raw ideas"
template: langchain-deepagents-weighted-evaluation  # or future adversarial template

intents:
  - pattern: "build.*"
    signals: [build, develop, implement, create, make, ship]
    confidence: 0.90
  - pattern: "pipeline.*"
    signals: [pipeline, stages, progress, status, deploy]
    confidence: 0.85
  - pattern: "feature.*"
    signals: [feature, add feature, new capability, requirement]
    confidence: 0.80

tools:
  - name: forge_greenfield
    description: "Run full greenfield pipeline from raw input to deployed code"
    risk_level: mutating
    async_mode: true
  - name: forge_feature
    description: "Add a feature to an existing project"
    risk_level: mutating
    async_mode: true
  - name: forge_review_fix
    description: "Review and fix issues in existing code"
    risk_level: mutating
    async_mode: true
  - name: forge_status
    description: "Get current pipeline status for a project"
    risk_level: read_only
    async_mode: false

max_concurrent: 3  # one pipeline per project, up to 3 projects
trust_tier: core    # infrastructure-level agent, not specialist
nats_topic: agents.command.forge
```

---

## What Stays the Same from March

These aspects of the original conversation starter are unchanged and should be carried forward:

1. **Three orchestration modes** — Greenfield (Mode A), Feature (Mode B), Review-Fix (Mode C)
2. **Human-in-the-loop checkpoint protocol** — via NATS `agents.approval.*`
3. **Multi-project parallel execution** — NATS topic prefix isolation per project
4. **Execution environment abstraction** — worktrees (Phase 1) → devcontainers (Phase 2) → sandboxes (Phase 3)
5. **CI/CD integration** — self-healing loop on CI failures
6. **Dashboard UX** — orchestrator card per active project
7. **Provider-agnostic execution** — cloud or local, configurable
8. **Pipeline state persistence** — resume after crash
9. **The motivation** — 93% defaults accepted, 3 high-impact decisions, 4:1 leverage ratio

---

## What's New or Changed

| Topic | March 2026 | April 2026 |
|-------|-----------|-----------|
| Upstream stages | Forge invokes slash commands for everything | Forge delegates to specialist agents for product docs and architecture |
| Agent discovery | Static tool inventory | Dynamic via NATS fleet registry |
| Product documentation | Not addressed — assumed human provides | Product-owner-agent generates from raw input |
| Architectural judgment | Forge does it via `/system-arch` | Architect-agent provides conversation starter, Forge feeds it to `/system-arch` |
| Feasibility checks | Not addressed | Architect-agent provides via NATS tool call |
| Fine-tuned models | Not applicable (Forge uses API models) | Specialist agents use fine-tuned models; Forge uses reasoning API |
| Degraded mode | Not addressed | Automatic fallback if specialist agents unavailable |
| Agent name | "Pipeline Orchestrator" | **Forge** |
| `/feature-spec` interaction | Simple tool invocation | Interactive propose-review cycle (needs special handling) |
| Specialist agent repo | Separate repos (architect-agent, product-owner-agent) | Single repo (`specialist-agent`) with role configs |

---

## Open Questions (New)

1. **Should the Forge itself be a role in the specialist-agent harness?** No — the Forge is a coordinator, not a specialist. It doesn't have weighted evaluation criteria for its own output. It doesn't need a Player-Coach loop. It's a different kind of agent (orchestrator vs evaluator). Keep it in its own repo using the future `langchain-deepagents-adversarial` template.

2. **How does the Forge handle the `/feature-spec` propose-review cycle?** Options: (a) Forge passes through to human for curation (checkpoint), (b) Forge uses the product-owner-agent to do the curation (automated), (c) Forge uses a dedicated spec-reviewer agent. Option (a) is simplest and correct for v1.

3. **Does the Forge need its own Graphiti context?** Yes — the Forge needs pipeline history (what was built, what failed, what was approved) across sessions. This is different from the architect's architectural context or the product owner's product context. The Forge's Graphiti group_id is `forge_pipeline_history`.

4. **When does the Forge call the architect vs invoke `/system-arch` directly?** The architect-agent produces a conversation starter (strategic input). `/system-arch` resolves it into full architecture (tactical output). Both are needed in the greenfield pipeline. The Forge calls the architect first, then feeds the conversation starter to `/system-arch`.

5. **What happens when a specialist agent disagrees with the Forge?** Example: the architect-agent scores a conversation starter at 0.55 (below threshold, won't accept). The Forge can either: (a) pass the feedback to the human, (b) provide additional context to the architect for retry, (c) skip the specialist and use `/system-arch` directly. Option (b) first, then (a) if retries exhausted.

---

## Suggested Research Topics

- **Anthropic Agent SDK evaluation** — their March 2026 article uses the Claude Agent SDK. Worth comparing to LangChain DeepAgents for orchestrator-level coordination (compaction, context resets, sprint contracts)
- **AsyncSubAgent for non-blocking specialist calls** — DeepAgents 0.5.0a2 has `AsyncSubAgent` which allows the Forge to launch specialist agent calls without blocking the orchestration loop
- **Sprint contract pattern** — the Anthropic article's "generator and evaluator negotiate what done looks like" maps to the Forge negotiating stage completion criteria with each specialist
- **Degraded mode testing** — how does pipeline quality change when specialist agents aren't available vs when they are? This quantifies the value of the specialist fleet

---

## Build Sequence (Updated)

The Forge build depends on:
1. ✅ Phase 0 — GuardKit CLI, AutoBuild, Graphiti (all working)
2. ▶ Specialist-agent Phase 1 — output quality
3. ◻ Specialist-agent Phase 1B — unified harness (architect + product owner roles)
4. ◻ Specialist-agent Phase 3 — NATS fleet integration (agent manifests, command handling)
5. ◻ nats-core library — message contracts, topic registry
6. ◻ nats-infrastructure — NATS server deployment
7. ◻ **Forge v1** — orchestrator with fleet delegation + GuardKit command invocation

The Forge is the capstone. It's the last major agent to build because it coordinates everything else. But it's also the highest-leverage: once it works, the "software factory" is real.

---

*Conversation starter refresh: 11 April 2026*
*"The Forge doesn't mine the ore or design the blueprint — it does the making."*
