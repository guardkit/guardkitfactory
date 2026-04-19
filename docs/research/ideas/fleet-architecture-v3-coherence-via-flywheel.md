# Fleet Architecture v3 — Coherence via Flywheel

> **Version:** 3.0
> **Date:** 19 April 2026
> **Status:** Vision — keystone document for fleet-wide architectural decisions
> **Supersedes:** fleet-master-index v2 (12 April 2026) as the *framing* document; v2 remains valid as the *repo index* document
> **Context:** Produced during the 19 April conversation between Rich and Claude covering the Jarvis/Forge tension, model-routing, selectively ambient behaviour, and the Karpathy Loop parallel

---

## 1. The One-Sentence Thesis

**One reasoning model that knows which reasoning model to use.**

Applied fleet-wide: the Software Factory's superpower is knowing which agent to use, which model within that agent, and which specialist within the fleet — all emergent from reasoning over capability descriptions, not hardcoded anywhere.

This document captures the fleet-level architectural stance that makes that sentence true.

---

## 2. The Three Surfaces

The ecosystem contains three distinct *surfaces of intent*, each with different time horizons and different relationships to the human. All three are DeepAgents. All three sit on the same substrate. They differ in what they reason about and what they delegate to.

| Surface | Intent type | Time horizon | Human role | Primary mechanism |
|---|---|---|---|---|
| **Jarvis** | Life intent — "be useful" | Zero to hours | Attended, always in the loop | DeepAgent with async subagents, dispatch tools, selectively ambient skills |
| **Forge** | Build intent — "ship a feature" | Minutes to hours per build | Approver, not operator | DeepAgent consuming JetStream, confidence-gated, NATS-native |
| **Study Tutor** | Teaching intent — "help me learn" | Session-length | Student in conversation | DeepAgent with fine-tuned role + per-subject RAG |

The asymmetry matters. Forge is a *batch processor* — Rich's attention is elsewhere while it runs; it pauses on `interrupt()` when it needs him. Jarvis is an *attended assistant* — there is always a human in the loop, and the human's attention *is the product*. Study Tutor is *conversational* — sync by default, with async for background work.

This asymmetry determines which DeepAgents SDK features each leans on. Forge leans on the reasoning loop + sync `task()` for bounded delegation + `interrupt()` for gates. Jarvis leans on `AsyncSubAgent` + Memory Store + Skills because those are the features that make an ambient assistant feel ambient. Study Tutor leans on sync `task()` + Memory Store for cross-session recall + async subagents for background paper generation.

**Same SDK. Same pattern. Different leaning.**

---

## 3. Jarvis as "DeepAgent with Dispatch Tools"

The March 2026 Jarvis vision framed Jarvis as a *thin intent router* with a General Purpose Agent as one of its dispatch targets. That framing is now inverted.

**Jarvis IS the General Purpose DeepAgent.** Routing is not its own discipline — it is tool selection, which DeepAgents is already good at. The `AgentManifest` + `NATSKVManifestRegistry` plumbing becomes a *tool catalogue* the reasoning model reads dynamically, exactly the way Forge treats the fleet per ADR-ARCH-015 and ADR-ARCH-016. No pre-coded routing table. No rule-based classifier. No separate "intent router" process. Jarvis's reasoning model reads registered capability descriptions and decides.

Jarvis has **three delegation targets**, each with a different character:

1. **Async subagents (same process, different model).** `AsyncSubAgent` instances declared at Jarvis startup, each pointing to a different LangGraph graph with a different `create_deep_agent(model=...)` configuration. Communication via ASGI (in-process). Use for: model-routing, parallel reasoning workloads, long-running background research, anything where Jarvis is doing the work but wants parallelism or a different brain.

2. **Specialist agents (different process, via NATS).** Architect, Product Owner, Ideation, UX Designer — each a deployment of the `specialist-agent` binary, each registered on `fleet.register`. Communication via `agents.command.{agent_id}` / `agents.result.{agent_id}` singular topics. Use for: fine-tuned domain specialists, work that needs its own Graphiti role group, services that scale independently.

3. **Forge (different process, via JetStream publish).** Specifically for build intent. Jarvis publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per ADR-SP-014 Pattern A. Not a command — a queued job. Different from the other two because of the time horizon and durability guarantee.

One mental pattern (capability-driven dispatch), three registries (async subagent specs declared at startup, NATS fleet discovered live from KV, build queue just writes JetStream).

---

## 4. Model Routing as a Reasoning Decision

The four `AsyncSubAgent` instances Jarvis ships with:

| Name | Graph | Model | Purpose |
|---|---|---|---|
| `deep_reasoner` | `deep_reasoner` graph | `google_genai:gemini-3.1-pro` | Deep reasoning, architectural synthesis, 1M-token context work |
| `adversarial_critic` | `adversarial_critic` graph | `anthropic:claude-opus-4-7` | Coach-style quality evaluation, flaw identification, adversarial review |
| `long_research` | `long_research` graph | `openai:gpt-5.4` | Multi-hour open-ended research, persistent web search, synthesis |
| `quick_local` | `quick_local` graph | `vllm:qwen3-coder-next` (local on GB10) | Quick lookups, privacy-sensitive content, low-stakes reasoning |

Each description is **the contract with the reasoning model**. Descriptions include cost + latency signals so the reasoning model has skin in the decision:

```python
AsyncSubAgent(
    name="adversarial_critic",
    description=(
        "Claude Opus 4.7. For quality evaluation, identifying subtle flaws, "
        "Coach-style adversarial review. Higher cost (~$15/Mtok output) — "
        "reserve for tasks where flaw detection matters more than throughput. "
        "Do not use for routine Q&A or factual lookups."
    ),
    graph_id="adversarial_critic",
)
```

The supervisor's system prompt teaches a preference: **default to cheapest-that-fits; escalate on need.** Local vLLM is the floor; cloud-premium is the escalation. Same pattern as `start_async_task` vs sync `task()` — a learned preference, not a hard rule. This is a reasoning input, not config — consistent with ADR-ARCH-019.

**The learning loop (see §7) refines this over time.** Each routing decision is a data point. Rich's redirections ("actually try that with Opus") are the correction signal. Graphiti compounds the priors per capability, per context, per project.

---

## 5. The Substrate

All three surfaces share one substrate:

```
       ┌─────── Humans: Rich, James, Mark, students, future users ───────┐
       │                                                                 │
       ▼                                                                 ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ Reachy Mini  │   │   Telegram   │   │  Dashboard   │   │     CLI      │
  │   (voice)    │   │              │   │              │   │              │
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                      │
                                      ▼
                 ┌────────────────────────────────────────────┐
                 │     NATS JetStream — the substrate         │
                 │   fleet.register · agent-registry KV       │
                 │   agents.command.*  · agents.result.*      │
                 │   pipeline.build-* · notifications.*       │
                 │   jarvis.* · system.*                      │
                 └─────┬───────────┬───────────┬──────────────┘
                       │           │           │
     ┌─────────────────┘           │           └──────────────────┐
     ▼                             ▼                              ▼
┌─────────────┐        ┌────────────────────────┐         ┌───────────────┐
│   Jarvis    │        │    Specialist Agents   │         │     Forge     │
│  (attended  │◄──────►│   architect · PO ·     │◄────────│   (batch      │
│   DeepAgent)│        │   ideation · ux-des    │         │   DeepAgent)  │
│             │        │  (one binary, roles)   │         │               │
│ • GPA tools │        │                        │         │ • dispatch    │
│ • async     │        └────────────────────────┘         │ • gates       │
│   subagents │                    ▲                      │ • SQLite      │
│ • skills    │                    │                      │ • autobuild   │
│ • memory    │                    └──────────────────────┤   subprocess  │
└─────┬───────┘                                           └───────────────┘
      │                                                           │
      │    ┌────────────────────┐                                 │
      └───►│   Study Tutor      │                                 │
           │   (conversational  │                                 │
           │    DeepAgent)      │                                 │
           │                    │                                 │
           │ • fine-tuned Gemma │                                 │
           │ • per-subject RAG  │                                 │
           │ • async paper-gen  │                                 │
           └────────────────────┘                                 │
                     ▲                                            │
                     │                                            │
                     └── Graphiti / FalkorDB ◄────────────────────┘
                         (per-role, per-project, per-surface)
                         (compounds across sessions)
```

Shared infrastructure the surfaces depend on:

- **NATS JetStream + `nats-core`** — the event substrate, typed payloads, topic registry, KV registry
- **Graphiti + FalkorDB** — knowledge + relationships + learning priors per surface
- **ChromaDB** — per-role RAG (specialist agents, tutor subjects)
- **DeepAgents 0.5.3** — the harness every surface uses
- **Adapter pattern** — every input/output modality is a `nats-asyncio-service` (Reachy voice, Telegram, Slack, dashboard, CLI)
- **Fine-tuning pipeline** — `agentic-dataset-factory` produces training data; Gemma 4 31B per role; Bedrock Custom Model Import for deployment

---

## 6. Selectively Ambient — Three Patterns

"Selectively ambient" is a stance, not a single feature. It decomposes into three patterns:

### Pattern A — Reactive
Jarvis responds when spoken to. This is the baseline DeepAgents behaviour. Always available via adapters. No initiative.

### Pattern B — Triggered
Jarvis has *watchers* — async subagents whose job is to monitor a condition and emit a notification when it fires. "Watch the Forge queue — when FEAT-FORGE-007 completes, nudge me." "Watch my calendar — when I have a free 2-hour block, suggest working on the talk." These are `start_async_task` with an agent whose prompt is "monitor X, return when Y." Stateful threads, async sleeps internally.

### Pattern C — Volitional
Jarvis notices something on its own and proactively speaks. "You haven't committed to forge in 4 days and the DDD talk is in 3 weeks." Requires either a cron-like trigger or a long-lived async subagent that runs on a schedule. This is where the Tony Stark feeling is strongest — and where the risk of being annoying is highest.

### v1 Scope Decision

**Commit to A and B. Prototype C as an opt-in skill ("morning briefing") you can turn off.**

Pattern C skills — when they prove they earn their place — graduate into always-on watchers in v2. The opt-in-skill-first pattern gives you the ability to experiment without committing.

---

## 7. The Flywheel — Coherence via Compounding

Every surface has the same learning shape. This is the coherence architecture.

### The Karpathy Loop applied to attended AI

Andrej Karpathy's March 2026 auto-research pattern (one editable surface, one metric, one time budget, filesystem-traced) and the Meta-Harness / Auto-Agent escalation to harness engineering give us the pattern:

1. Constrain the search space.
2. Record the full reasoning trace.
3. Let a meta-reasoner read the trace and propose changes.
4. Gate via a confirmation loop.
5. Compound the improvements.

Forge's ADR-ARCH-005 and ADR-ARCH-006 already express this pattern over *gate decisions*: every decision + outcome + override writes to `forge_pipeline_history`; `forge.learning` proposes `CalibrationAdjustment` entities; Rich confirms via CLI; entity persists to Graphiti; future builds retrieve it.

**We extend the same pattern fleet-wide, one Graphiti group per surface per learning track.**

### Per-surface learning tracks

| Surface | Graphiti group | Editable surface | Metric | Time budget |
|---|---|---|---|---|
| **Forge gate decisions** | `forge_pipeline_history` | `CalibrationAdjustment` entities | Rich override rate on gate decisions | One build |
| **Jarvis routing** | `jarvis_routing_history` | Routing-preference entities | Rich redirect rate on model/subagent choice | One session |
| **Jarvis ambient** | `jarvis_ambient_history` | Notification-trigger preference entities | Rich dismiss rate on proactive notifications | Daily window |
| **Tutor teaching** | `tutor_teaching_history` | Teaching-pattern entities | Student engagement + success rate | One teaching session |

Each track runs the same learning loop: decision → outcome → pattern detection → proposed adjustment → Rich confirms → persisted prior → future retrieval. Each track has its own module (`forge.learning`, `jarvis.learning`, `tutor.learning`) that detects patterns and proposes `CalibrationAdjustment` entities.

### Why this is coherence, not just consistency

Three things compound:

1. **Per-surface compounding.** Every Forge build makes future Forge builds better. Every Jarvis dispatch makes future Jarvis dispatches better. Every Tutor session makes future sessions better. This is the within-surface flywheel.

2. **Infrastructure compounding.** Improvements to Graphiti (query tools, relationship extraction, temporal reasoning) help *all* surfaces simultaneously. Richer traces help *all* learning loops. Better adapter infrastructure helps *all* user-facing interactions. This is the substrate flywheel.

3. **Pattern compounding.** Adding a new surface (say, a future YouTube Planner v2) means adding a new Graphiti group and a new learning module — zero changes to the pattern, zero changes to any existing surface. The pattern is the asset. This is the architectural flywheel.

### Trace-richness — the cheap-now-expensive-later decision

Meta-Harness's decisive finding is that *what you capture determines how much you can learn*. Their proposer gets 10M tokens of diagnostic context per iteration; every prior method caps at 26K. The 10x quality gain comes specifically from having the full execution trace to diagnose from, not just outcome summaries.

**Applied to our surfaces:** every `*_history` Graphiti group captures, per decision:

- The reasoning model's full tool-call sequence
- The subagent's trace if one was dispatched (task ID, messages, final state)
- The cost and latency of each model call
- The human's response (with reasoning text, not just the button press)
- The environmental context at decision time (which project, which time of day, which recent builds/sessions)

This is a schema expansion on existing Graphiti groups. It costs little now. Retrofitting it later — after you've accumulated thousands of runs with thin traces — would be nearly impossible. The value compounds with every run.

See ADR-FLEET-001 (companion document) for the full trace-richness commitment.

### What is deliberately deferred

Two Karpathy-Loop escalations we are **not** pursuing in v1:

- **Meta-agent / task-agent split.** `*.learning` modules remain *inside* their parent agents for v1. The split (separate DeepAgent that reads traces and proposes changes, following Goose's Auto-Agent pattern) is an option to revisit after 6 months of real runs, if module-based learning shows weakness.

- **Harness auto-rewriting.** The Auto-Agent and Meta-Harness pattern of having a meta-agent autonomously edit the task agent's system prompt, tools, or orchestration logic is **explicitly deferred**. The failure modes (metric gaming, silent degradation, contamination, cascading errors) are too costly at personal-Jarvis scale where the benefit of speed is marginal and the cost of drift is high. Revisit only after (a) multiple agents are in daily production use, (b) trace infrastructure from ADR-FLEET-001 is mature, (c) eval metrics for "good behaviour" are well-defined.

---

## 8. v1 Scope Discipline

Concrete constraints that prevent scope creep while preserving the architectural promise.

### Jarvis v1

- **One Jarvis supervisor.** Single-process, single-container, thread-per-session (where a session is an adapter + time window).
- **Four async subagents at launch:** `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`. Add more later if they earn it.
- **Three NATS dispatch targets at launch:** architect-agent, product-owner-agent, forge. Others appear automatically via CAN-bus as specialist-agent roles ship.
- **Three adapters at launch:** Telegram (quickest feedback loop), CLI-wrapper, Dashboard. Reachy voice when the hardware lands.
- **Pattern A + B ambient only.** One opt-in Pattern C skill ("morning briefing") for experimentation.
- **Three Skills at launch:** morning-briefing, talk-prep (DDD progress tracker), project-status (query forge/specialist-agent fleet state).
- **Jarvis's own Graphiti groups:** `jarvis_routing_history`, `jarvis_ambient_history` — following the flywheel pattern from day one.

### Forge v1

Unchanged from ARCHITECTURE.md + 30 ADRs, with one small amendment:

- **ADR-ARCH-031 (new):** Long-running subagents use `AsyncSubAgent`; short-lived delegations use sync `task()`. `autobuild_runner` is async so that `forge status` reflects live progress; `build_plan_composer` stays sync because its output gates the next stage.

### Study Tutor v1

Unchanged from its `/system-arch` outputs, with two noted future-work items (not requiring `/system-arch` re-run):

- Async subagents for background paper-generation (non-blocking to conversation).
- Memory Store for cross-session recall ("last session we struggled with projectile motion").

### Shared

- **ADR-FLEET-001 (new, companion document):** Trace-richness commitment — fleet-wide schema expansion for `*_history` Graphiti groups, effective from v1 start.
- **Per-surface `*.learning` modules.** Not separate agents. Pattern-detecting modules inside their parent agents.
- **NemoClaw integration hooks named but not built.** When NemoClaw matures, it integrates as (a) a DeepAgents sandbox backend for `execute`, and (b) a NATS-registered fleet participant with `trust_tier: sandboxed`. No architectural change required now.

---

## 9. What This Means for the DDD Southwest Talk

The talk on 16 May 2026 now has a cleaner architectural spine. Two technical pillars:

1. **Context-first delivery** (from fleet-master-index D33-D39) — no kanban, no tickets, structured docs as project management, outcome gates instead of progress tracking.

2. **Coherence via flywheel** (this document) — the Karpathy Loop pattern applied across three surfaces, one substrate, one pattern, compounding learning per surface.

The Karpathy Loop parallel is external corroboration — you're not claiming to have invented a pattern, you're showing the pattern applies broadly. The Meta-Harness paper (Stanford, preprint 2026) validates the direction. You can name what you chose *not* to do (meta-agent split, harness auto-rewriting) and why, which is a sophistication signal rather than a retreat.

See companion doc: `~/Projects/YouTube Channel/ddd-southwest-2026-software-factory-talk-outline.md`.

---

## 10. Relationship to Existing Documents

This document is a **framing refinement**, not a replacement. Relationships:

| Document | Relationship |
|---|---|
| `fleet-master-index.md` v2 | Remains the repo index + decision log. This document is the *framing* companion. Add D40 (three surfaces, one substrate) and D41 (flywheel-via-calibration-loop fleet-wide) to its decision log. |
| `forge/docs/architecture/ARCHITECTURE.md` | Unchanged. ADR-ARCH-031 added as amendment (async subagents). |
| `forge-pipeline-architecture.md` v2.2 | Unchanged. ADR-SP-014 Pattern A remains the Jarvis-to-Forge trigger mechanism. |
| `jarvis-vision.md` | Rewritten this session to reflect GPA-with-dispatch framing. |
| `jarvis-architecture-conversation-starter.md` | Rewritten this session for tomorrow's `/system-arch` run. |
| Specialist-agent architecture | Unchanged. Still the binary with roles per ADR-ARCH-008/009. |
| Study Tutor architecture | Unchanged. Future-work notes added but no `/system-arch` re-run. |

---

## 11. Do-Not-Reopen Decisions (Fleet-Wide, New)

Adding to fleet-master-index's D1-D39 list:

| # | Decision | Resolution |
|---|---|---|
| **D40** | **Three DeepAgents surfaces, one substrate.** Jarvis (attended), Forge (batch), Study Tutor (conversational) are all DeepAgents on the same NATS/Graphiti/adapter substrate. Same SDK, same pattern, different leaning on SDK features. No separate "intent router" process — Jarvis IS the GPA with dispatch as tools. |
| **D41** | **Flywheel-via-calibration-loop fleet-wide.** Every surface has a `*.learning` module and a `*_history` Graphiti group. The Forge calibration pattern (ADR-ARCH-005/006) is the template; Jarvis routing, Jarvis ambient, Tutor teaching each get their own track. Same pattern, parallel compounding. |
| **D42** | **Trace-richness by default.** All `*_history` Graphiti writes capture full reasoning traces (tool-call sequences, subagent traces, cost/latency per call, human responses with text). See ADR-FLEET-001. |
| **D43** | **Model routing is a reasoning decision, not a config decision.** Jarvis's async subagents expose different models, and the supervisor's reasoning model picks which to dispatch to based on capability descriptions + retrieved priors. Same pattern as capability-driven dispatch (ADR-ARCH-015). Defaults to cheapest-that-fits; escalates on need. |
| **D44** | **Selectively ambient, Pattern A + B for v1.** Pattern C (volitional) is an opt-in skill only for v1 experimentation. |
| **D45** | **Meta-agent split and harness auto-rewriting explicitly deferred.** Named as research directions with clear conditions for revisit. Not v1 scope. Not v2 scope unless conditions in §7 are met. |
| **D46** | **NemoClaw integration hooks named but not built.** When/if NemoClaw matures, it integrates as DeepAgents sandbox backend and as NATS-registered fleet participant with `trust_tier: sandboxed`. Zero rework required. |

---

## 12. Source Documents

This document is grounded in the following source materials from the 19 April conversation:

| Source | Contribution |
|---|---|
| `jarvis/docs/research/ideas/jarvis-vision.md` (March 2026) | Original Jarvis vision with six-agent fleet, intent router framing, NATS topic taxonomy. Identified framing shift needed. |
| `jarvis/docs/research/ideas/jarvis-architecture-conversation-starter.md` | ADR-P1-01..06 preferred directions, open questions D11-D17, C4 diagrams. Input for tomorrow's `/system-arch`. |
| `jarvis/docs/research/ideas/general-purpose-agent.md` | GPA tool categories, model routing, co-location question (now resolved in favour of Jarvis-IS-GPA). |
| `jarvis/docs/research/ideas/nemoclaw-assessment.md` | D6 rejection, revisit signals. Informs D46 integration hooks. |
| `forge/docs/architecture/ARCHITECTURE.md` + 30 ADRs | Capability-driven dispatch (ADR-ARCH-015), no pre-coded catalogue (ADR-ARCH-016), no static behavioural config (ADR-ARCH-019), DeepAgents 0.5.3 built-ins (ADR-ARCH-020). Pattern source for fleet-wide adoption. |
| `forge-pipeline-architecture.md` v2.2 | ADR-SP-014 Pattern A (Jarvis→Forge trigger), ADR-SP-015 (dual-role specialist), ADR-SP-016 (singular topics), ADR-SP-017 (stream retention). |
| `fleet-master-index.md` v2 | D1-D39 resolved decisions. This doc adds D40-D46. |
| DeepAgents 0.5.3 docs (fetched 19 April 2026) | Async subagents preview feature, five supervisor tools, ASGI vs HTTP transport, state channel for task metadata, Skills capability, Memory Store. |
| Karpathy Loop video transcript + insights (Nate, 19 April 2026) | Karpathy Triplet, meta-agent/task-agent split, model empathy, traces-everything, emergent behaviours, local hard takeoff, safety concerns. |
| Meta-Harness paper (Stanford, 2026 preprint) | Full-filesystem context for proposer (10M tokens/iter vs 26K baseline), counterfactual diagnosis, same-model pairings for harness optimisation, TerminalBench-2 results. |

---

## 13. Next Actions

Per the 19 April conversation plan:

1. ✅ **This document** — fleet-level vision.
2. ◻ **ADR-FLEET-001 trace-richness** — companion doc (next).
3. ◻ **Jarvis vision rewrite** — reflecting GPA-with-dispatch framing.
4. ◻ **Jarvis conversation-starter rewrite** — for tomorrow's `/system-arch`.
5. ◻ **Forge ADR-ARCH-031** — async subagents amendment.
6. ◻ **Jarvis `.guardkit/context-manifest.yaml`** — cross-repo dependency map.
7. ◻ **Fleet-master-index update** — D40-D46 added to decision log.
8. ◻ **Study Tutor future-work note** — async paper-gen + Memory Store (not a re-run).
9. ◻ **DDD Southwest talk outline** — two-pillar narrative doc.
10. ◻ **Conversation capture doc** — full richness of 19 April conversation (explored, decided, deferred).

---

*"One reasoning model that knows which reasoning model to use."*

*19 April 2026 · Fleet Architecture v3*
