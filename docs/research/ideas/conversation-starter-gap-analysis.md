# Ship's Computer / Jarvis — Conversation Starter & Gap Analysis

## For: Sanity check, gap analysis, and onboarding context · April 2026

---

## How to Use This Document

This is the single document that explains the entire Ship's Computer / Jarvis project.
Read it to understand what we're building, why, where all the documentation lives, and
what gaps still need addressing. It consolidates a long ideation session (April 2026)
into a structured brief.

---

## 1. The Problem Statement

### What we're solving

A solo software engineer (Rich, 52, Appmilla) with 25+ years of systems experience is
navigating the transition to AI-augmented development. The daily workflow involves:

- **Ideation** in Claude Desktop — freeform back-and-forth exploring concepts
- **Product documentation** — manually synthesising brain dumps into structured docs
- **Architecture** — manually writing C4 diagrams, ADRs, and conversation starters
- **Implementation** — driving GuardKit slash commands (`/system-arch` → `autobuild`)
- **Content creation** — planning YouTube videos about the journey
- **General tasks** — research, drafting, scheduling, chores

Each of these is currently a separate manual workflow. Context is lost between sessions.
Architecture decisions get re-learned. The human is the orchestrator, the context carrier,
and the bottleneck.

### What Jarvis replaces

The human-as-orchestrator role. Jarvis is an intent router backed by NATS JetStream that
dispatches natural language requests to specialist agents, each handling a stage of the
lifecycle. The human moves from operator to approver — giving direction, reviewing output,
making decisions at checkpoints.

---

## 2. Motivations (Why Build This?)

### 2.1 Learning Vehicle

The system is a vehicle for learning AI-augmented development hands-on:
- Fine-tuning small language models (Unsloth QLoRA, Nemotron Nano)
- RAG with knowledge graphs (Graphiti, FalkorDB, ChromaDB)
- Agent harness design (Claude Agents SDK, LangChain DeepAgents SDK)
- Adversarial cooperation (Player-Coach, weighted evaluation)
- Local inference (vLLM on DGX Spark GB10)
- Multi-agent orchestration (NATS JetStream, CAN bus registration)
- Container-based agent deployment (Docker Compose fleet)

The combination of these skills is genuinely rare. The war stories from building are
the durable asset — 180+ review reports, the FB01-FB28 cascading fix series, the
NemoClaw saga, the C4 validation discovery.

### 2.2 YouTube Content

Every problem solved is a video. Every honest failure builds audience trust.
70% browse (story-driven) / 30% search (tutorials). The Rory Sutherland insight:
sell how you think, not what you do. The system IS the content.

Key content arcs:
- "I'm Building My Own Jarvis" — the vision
- "Why I'm Not Using NemoClaw (Yet)" — marketing vs reality
- "What I Learned from 180 Review Reports" — methodology
- "2026: The Year of the Software Factory" — DDD Southwest talk (May 16)

### 2.3 DDD Southwest Talk

Submitted for May 16, 2026, Engine Shed, Bristol. 30-minute session contrasting
vibe coding with engineering-first software factory methodology. The adversarial
cooperation pattern and GuardKit pipeline are the centrepiece.

### 2.4 Practical Productivity

Beyond learning and content — this genuinely makes Rich more productive:
- FinProxy proof point: 14 product docs (310 KB) in one weekend, James approved
- AutoBuild proof point: 43 tasks, 3 human decisions, 93% defaults accepted
- Ideation proof point: every Claude Desktop session is a manual version of this

### 2.5 Durability

Three-layer durability analysis (see big-picture doc):
- **Permanent:** Methodology, domain knowledge, war stories
- **2-3+ years:** Architectural patterns (NATS, intent routing, CAN bus, adapters)
- **12-18 months:** Specific tools and templates (designed to be replaceable)

---

## 3. What We're Building

### 3.1 The Full Pipeline

```
Ideation Agent → Product Owner Agent → Architect Agent → GuardKit Factory
(explore)        (document)             (architect)       (implement)
     ↑                                                        ↓
     └──────────── General Purpose Agent ─────────────────────┘
                   (everything else)

YouTube Planner ← (content ideas about the above)

                    ┌─────────────────┐
All agents ←───────→│  NATS JetStream  │←── nats-infrastructure
All adapters ←─────→│  (nats-core)     │
                    └─────────────────┘
                           ↑
                    Jarvis Intent Router
                    (CAN bus discovery)
                           ↑
              ┌────────────┼────────────┐
              │            │            │
         Reachy Mini   Telegram     Dashboard
         (voice)       (text)       (web UI)
```

### 3.2 Agent Fleet (8 Agents)

| Agent | Repo | Template | Purpose | Proof Point |
|-------|------|----------|---------|-------------|
| **Intent Router** | `jarvis` | Custom | Classify intent, dispatch via CAN bus registration | — |
| **General Purpose** | `jarvis` | `langchain-deepagents` | Everything else — research, drafts, chores | Every "quick question" in Claude Desktop |
| **Ideation** | `ideation-agent` | `weighted-evaluation` | Structured brainstorming with scored criteria | Every ideation session in Claude Desktop |
| **Product Owner** | `product-owner-agent` | `weighted-evaluation` | Raw info → structured product docs | FinProxy: 14 docs, 310 KB, James approved |
| **Architect** | `architect-agent` | `weighted-evaluation` | Product docs → C4/ADRs → `/system-arch` input | Every conversation starter doc |
| **GuardKit Factory** | `guardkitfactory` | `orchestrator` | Autonomous software dev pipeline | TASK-REV-F5F5: 43 tasks, 93% auto-accepted |
| **YouTube Planner** | `youtube-planner` | `weighted-evaluation` | Content planning: idea → filmable script | Twin AI Paradoxes video plan |
| **GCSE Tutor** | (future) | TBD | Fine-tuned Nemotron Nano via Reachy "Scholar" | Dataset factory: 2,500 targets generated |

### 3.3 Infrastructure (2 Repos)

| Component | Repo | Type | Purpose |
|-----------|------|------|---------|
| **nats-core** | `nats-core` | Python library | Message schemas, topic constants, fleet registration, typed NATS client |
| **NATS Server** | `nats-infrastructure` | Config/ops | Docker Compose deployment, accounts, streams, fleet compose, monitoring |

### 3.4 Key Architectural Patterns

| Pattern | What It Does | Where Documented |
|---------|-------------|-----------------|
| **CAN bus registration** | Agents self-announce capabilities; Jarvis builds routing table dynamically | `jarvis-vision.md`, `nats-core ADR-004` |
| **Weighted evaluation** | Subjective quality → gradable scores via Player-Coach with criteria | All agent vision docs |
| **Two-model separation** | Reasoning model ≠ implementation model (prevents self-confirmation) | D5, fleet master index |
| **Adversarial cooperation** | Coach evaluates Player output with calibrated scepticism | Templates, big picture doc |
| **Provider independence** | Cloud/local switchable via config (no vendor lock-in) | `agent-config.yaml` pattern |
| **Container lifecycle = agent lifecycle** | Container starts → agent registers; stops → deregisters | `nats-infrastructure` fleet compose |

---

## 4. Document Map

### Strategic Documents

| Document | Location | What It Covers |
|----------|----------|---------------|
| **Big Picture Vision & Durability** | `guardkitfactory/docs/research/ideas/big-picture-vision-and-durability.md` | Why we're building, three goals, durability analysis, containerisation strategy, compounding flywheel |
| **Fleet Master Index** | `guardkitfactory/docs/research/ideas/fleet-master-index.md` | Technical inventory: all 10 repos, all agents, all templates, 11-phase build sequence, hardware topology, port allocation |
| **This Document** | `guardkitfactory/docs/research/ideas/conversation-starter-gap-analysis.md` | Sanity check, gap analysis, onboarding |

### Agent Vision Documents (one per repo, feeds `/system-arch`)

| Document | Location |
|----------|----------|
| Jarvis Vision (intent router + CAN bus) | `jarvis/docs/research/ideas/jarvis-vision.md` |
| General Purpose Agent | `jarvis/docs/research/ideas/general-purpose-agent.md` |
| Reachy Mini Integration | `jarvis/docs/research/ideas/reachy-mini-integration.md` |
| NemoClaw Assessment | `jarvis/docs/research/ideas/nemoclaw-assessment.md` |
| Ideation Agent Vision | `ideation-agent/docs/research/ideas/ideation-agent-vision.md` |
| Product Owner Agent Vision | `product-owner-agent/docs/research/ideas/product-owner-agent-vision.md` |
| Architect Agent Vision | `architect-agent/docs/research/ideas/architect-agent-vision.md` |
| YouTube Planner Vision | `youtube-planner/docs/research/ideas/youtube-planner-vision.md` |

### System Specifications (feed `/feature-spec` or `/feature-plan`)

| Document | Location | Slash Command |
|----------|----------|--------------|
| nats-core System Spec (6 features, BDD) | `nats-core/docs/design/specs/nats-core-system-spec.md` | `/feature-spec` |
| nats-core Fleet Registration Addendum | `nats-core/docs/design/specs/nats-core-spec-addendum-fleet-registration.md` | Merge into main spec |
| nats-infrastructure System Spec (6 features, 26 tasks) | `nats-infrastructure/docs/design/specs/nats-infrastructure-system-spec.md` | `/feature-plan` |
| nats-infrastructure Fleet Compose Addendum | `nats-infrastructure/docs/design/specs/nats-infrastructure-spec-addendum-fleet-compose.md` | Merge into main spec |
| Pipeline Orchestrator Conversation Starter | `guardkitfactory/docs/research/pipeline-orchestrator-conversation-starter.md` | `/system-arch` |
| Pipeline Orchestrator Build Plan | `guardkitfactory/docs/research/pipeline-orchestrator-consolidated-build-plan.md` | Reference |

### Architecture Decision Records

| ADR | Location | Decision |
|-----|----------|---------|
| ADR-001: NATS as Event Bus | `nats-core/docs/design/decisions/` | NATS JetStream over Kafka/Redis |
| ADR-002: Schema Versioning | `nats-core/docs/design/decisions/` | version field + extra="ignore" + semver |
| ADR-003: nats-py vs FastStream | `nats-core/docs/design/decisions/` | nats-py for library, FastStream for services |
| ADR-004: Dynamic Fleet Registration | `nats-core/docs/design/decisions/` | CAN bus pattern via NATS |
| ADR-001: Standalone Infra Repo | `nats-infrastructure/docs/design/decisions/` | Backbone middleware, not coupled to any consumer |
| ADR-002: Account Multi-Tenancy | `nats-infrastructure/docs/design/decisions/` | NATS accounts per project |

### Templates

| Template | Status | Location |
|----------|--------|----------|
| `langchain-deepagents` | Production (built-in) | `guardkit/installer/core/templates/` |
| `langchain-deepagents-weighted-evaluation` | Production (built-in) | `guardkit/installer/core/templates/` |
| `langchain-deepagents-orchestrator` | Built (pending review → built-in) | `~/.agentecflow/templates/` |
| `python-library` | Built (pending review → built-in) | `~/.agentecflow/templates/` |
| `nats-asyncio-service` | Built (pending review → built-in) | `~/.agentecflow/templates/` |

### Template Specs

| Spec | Location |
|------|----------|
| python-library spec | `guardkit/docs/research/dark_factory/template-spec-python-library.md` |
| nats-asyncio-service spec | `guardkit/docs/research/dark_factory/template-spec-nats-asyncio-service.md` |
| Template creation session guide | `guardkit/docs/research/dark_factory/template-creation-session.md` |

### YouTube Content Documents

| Document | Location |
|----------|----------|
| YouTube Planner conversation starters (×3) | `youtube-planner/docs/research/conversation-starters/` |
| Channel project briefing | `~/Projects/YouTube Channel/youtube-channel-project-briefing.md` |
| Feature specs (×5) | `~/Projects/YouTube Channel/feature-01` through `feature-05` |
| DDD Southwest talk material | `~/Projects/YouTube Channel/ddd-southwest-adversarial-cooperation-talk.md` |
| Video plans | `~/Projects/YouTube Channel/video-plans/` |

### Proof Points

| Document | Location |
|----------|----------|
| FinProxy product docs (14 docs, 310 KB) | `finproxy-docs/` |
| GCSE dataset factory output | `agentic-dataset-factory/output/` |
| AutoBuild review reports | `guardkit/` (various TASK-REV files) |

---

## 5. Resolved Decisions (Fleet-Wide, Do NOT Reopen)

| # | Decision | Resolution |
|---|----------|-----------|
| D1 | Agent framework | LangChain DeepAgents SDK |
| D2 | Reasoning model | Gemini 3.1 Pro API or Claude API (configurable) |
| D3 | Implementation model | Claude Code SDK (cloud) or vLLM on GB10 (local) |
| D4 | Event bus | NATS JetStream |
| D5 | Two-model separation | Orchestration model ≠ implementation model |
| D6 | NemoClaw | Rejected — not production-ready. Revisit Q3-Q4 2026 |
| D7 | Tool interface stability | Signatures identical across cloud and local modes |
| D8 | Multi-project | Concurrent pipelines with NATS topic prefix isolation |
| D9 | Template strategy | Exemplar-first: build → prove → extract template |
| D10 | ChromaDB over NVIDIA RAG | ChromaDB PersistentClient for vector storage |
| D11 | nats-core uses nats-py | Library uses nats-py; services use FastStream |
| D12 | NATS infrastructure standalone | Own repo — backbone middleware |
| D13 | Account-based multi-tenancy | NATS accounts per project (APPMILLA, FINPROXY) |
| D14 | Containerisation | Phase 2 — containers for lifecycle, concurrency, fleet scaling |
| D15 | Agent discovery | Dynamic CAN bus registration via NATS fleet.register |

---

## 6. Build Sequence (11 Phases)

| Phase | What | Status |
|-------|------|--------|
| **0** | GuardKit CLI, 3 templates, Graphiti, vLLM, dataset factory, FinProxy docs | Done |
| **1** | python-library + nats-asyncio-service templates; review task for built-ins | Templates created, review pending |
| **2** | nats-core library + nats-infrastructure deployment + fleet compose | `guardkit init` done, specs ready |
| **3** | GuardKit Factory (primary deliverable) | Conversation starter ready |
| **4** | Jarvis intent router (CAN bus registration, KV-backed routing) | Vision doc ready |
| **5** | General Purpose Agent (ReAct + broad tools) | Vision doc ready |
| **6** | Ideation Agent (weighted eval, divergent reasoning) | Vision doc ready |
| **7** | Product Owner Agent (raw info → structured docs) | Vision doc ready |
| **8** | Architect Agent (product docs → C4/ADRs → /system-arch) | Vision doc ready |
| **9** | YouTube Planner (transcript map → research → planning) | Vision doc + 3 starters ready |
| **10** | Adapters (Telegram, Dashboard, CLI, Reachy Mini) | Designed in jarvis-vision.md |
| **11** | Template harvest (toolbox pattern from GP Agent) | Future |

---

## 7. Gap Analysis — Known Gaps & Open Questions

### 7.1 Graphiti Integration Strategy (Gap: HIGH)

Graphiti is referenced throughout as the knowledge graph for persistent memory, but
there's no unified spec for how each agent connects to it:
- Which agents read from Graphiti? Which write?
- What entity types exist? (ADRs, architectural patterns, project knowledge, ideas, evaluation results)
- How is Graphiti seeded for new projects?
- What's the schema evolution strategy for Graphiti entities?
- Does every agent get its own Graphiti namespace, or is it shared?
- The Graphiti vector dimension mismatch (768 vs 1024) was under investigation — is it resolved?

**Action needed:** A Graphiti integration spec, probably as a feature of nats-core or
a separate shared doc. The Architect Agent vision doc mentions Graphiti most heavily
but it's a fleet-wide concern.

### 7.2 Monitoring & Observability Dashboard (Gap: MEDIUM)

A dashboard is mentioned in multiple docs (Ship's Computer v1.0, Jarvis vision, fleet
master index) but no spec exists:
- What does the dashboard show? Fleet status, agent queues, build progress, approval queue?
- Is it a React app subscribing to NATS via WebSocket?
- Does it use the NATS monitoring endpoint (port 8222) or its own data pipeline?
- Who's the primary user? Rich during development, or James for project oversight?

**Action needed:** Dashboard feature spec, probably as an adapter in `nats-infrastructure`
or a standalone repo.

### 7.3 Error Handling & Dead Letter Queues (Gap: MEDIUM)

What happens when things go wrong at the fleet level:
- Agent fails mid-task — does the task retry? Go to dead letter queue? Alert the human?
- NATS message processing fails — ack/nak/redelivery strategy not specified per stream
- Agent crashes during a multi-stage pipeline — how is partial state recovered?
- Build failures in GuardKit Factory — retry logic, escalation path?

**Action needed:** Error handling section in nats-core spec or a fleet-wide error
handling ADR.

### 7.4 End-to-End Testing Strategy (Gap: MEDIUM)

Individual agents are testable (TestNatsBroker for services, mocked nats-py for library).
But multi-agent workflows need integration testing:
- How do you test "Ideation → Product Owner → Architect → Factory" end-to-end?
- Is there a fleet-level test harness?
- Can you replay NATS messages for debugging?
- How do you test the CAN bus registration lifecycle?

**Action needed:** Testing strategy doc, possibly in nats-infrastructure alongside
the fleet compose.

### 7.5 GCSE Tutor Integration (Gap: LOW-MEDIUM)

The GCSE Tutor is listed as "future/TBD" in the fleet but it's actually an active
project with real deliverables:
- Agentic dataset factory has completed production runs (~2,500 targets)
- Docling is working on GB10 for both digital and scanned PDFs
- Multi-subject expansion is planned (maths, science, French, Spanish, history)
- Reachy Mini "Scholar" is the intended interface

The gap is: how does the tutor integrate with the Jarvis fleet? Is it a NATS agent
that registers with the fleet? Or is it a standalone Open WebUI deployment with
Reachy as a separate interface?

**Action needed:** GCSE Tutor vision doc in a new repo, or a decision that it stays
outside the Jarvis fleet.

### 7.6 API Cost Management (Gap: LOW)

Six agents using Gemini 3.1 Pro for weighted evaluation, plus Claude API for content
generation and implementation. No cost tracking or budget alerting exists:
- What's the estimated monthly API cost at steady-state?
- Should there be a cost budget per agent or per project?
- The local vLLM path eliminates marginal costs but is slower — when to prefer it?

**Action needed:** Cost estimation in the big picture doc or a simple cost tracking
mechanism in the orchestrator.

### 7.7 Migration Path from Current Workflow (Gap: LOW)

How do we incrementally adopt Jarvis while remaining productive:
- Phase 2 (NATS) doesn't change daily workflow at all
- Phase 3 (GuardKit Factory) replaces the manual pipeline operator role
- Phase 4+ (Jarvis + agents) requires all agents to be containerised and registered

Is there a "Jarvis lite" that works before the full fleet? Perhaps Jarvis router +
General Purpose Agent + one specialist, with the rest added incrementally?

**Action needed:** Migration plan section in the build sequence, or acceptance that
Phase 4 is the minimum viable Jarvis.

### 7.8 Adapter Priority & Telegram Bot (Gap: LOW)

Telegram is listed as "quickest to test" but no spec exists:
- Bot token setup, command structure, message formatting
- How does Telegram handle multi-turn conversations? (Different from voice)
- Does Rich want Telegram primarily for mobile access while away from desk?
- Is there a Telegram-specific UX consideration?

**Action needed:** Telegram adapter feature spec when Phase 10 approaches.

### 7.9 Security: Agent-to-Agent Trust (Gap: LOW)

NATS accounts handle project isolation (APPMILLA vs FINPROXY). But within the
APPMILLA account, all agents can publish to all topics. Questions:
- Can the Product Owner Agent accidentally trigger a build?
- Should agents have scoped permissions within the account?
- Is the fleet.register topic protected (could a rogue agent register with confidence 1.0 for everything)?

**Action needed:** Per-agent NATS permissions, probably deferred until fleet is larger.

### 7.10 Merge Addendum Specs (Gap: IMMEDIATE)

Two addendum spec files need merging into their parent specs before `/feature-spec`
or `/feature-plan` runs:
- `nats-core-spec-addendum-fleet-registration.md` → merge into `nats-core-system-spec.md`
- `nats-infrastructure-spec-addendum-fleet-compose.md` → merge into `nats-infrastructure-system-spec.md`

**Action needed:** Merge before next Claude Code session.

---

## 8. Hardware Topology

| Machine | Role | Ports |
|---------|------|-------|
| **Dell DGX Spark GB10 (128GB)** | NATS server, vLLM (3 models), Graphiti (FalkorDB), Docker host, agent execution, Reachy USB | 4222, 8222, 8000, 8001, 8002 |
| **MacBook Pro M2 Max** | Planning/research, dashboard client, CLI adapter, cloud API calls | — |
| **Synology DS918+ NAS (32TB)** | FalkorDB persistence, JetStream backup, shared storage | — |
| **Reachy Mini ×2** (on order) | Scholar (tutoring) + Bridge (Jarvis voice interface) | USB |

Connected via Tailscale mesh VPN.

---

## 9. What We're NOT Building

- Not a product for others (yet) — personal/Appmilla system
- Not a replacement for Claude Desktop — agents jumpstart, humans deep-dive
- Not a competitor to Cursor/Windsurf — full lifecycle, not just coding
- Not an enterprise platform — single developer + small team
- Not using NemoClaw — rejected, revisit Q3-Q4 2026

---

## 10. Next Actions (Immediate)

1. **Merge addendum specs** into parent nats-core and nats-infrastructure specs
2. **Review task** in GuardKit: add orchestrator + python-library + nats-asyncio-service as built-in templates
3. **Run `/feature-spec`** on nats-core with merged spec (BDD scenarios for message contracts)
4. **Run `/feature-plan`** on nats-infrastructure with merged spec (deployment tasks)
5. **Transfer YouTube conversation starters:** `bash transfer-starters.sh` in youtube-planner repo
6. **Commit all repos** — 10 repos with vision docs, specs, and decisions ready
7. **Start building nats-core** — the foundation everything else depends on
