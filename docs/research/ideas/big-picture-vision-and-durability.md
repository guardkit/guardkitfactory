# Ship's Computer — Big Picture: What We're Building and Why

## The Strategic Vision Behind the Jarvis Agent Fleet

**Date:** April 2026
**Author:** Rich (Appmilla)

---

## What This Document Is

This captures the strategic thinking behind the entire Ship's Computer / Jarvis project.
Not the technical specs (those live in each repo's vision docs and the fleet master index)
but the *why* — the goals, the learning journey, the durability analysis, and the honest
assessment of what's at risk and what's permanent.

Read this first. Then read `fleet-master-index.md` for the technical inventory.

---

## The Big Picture

We're building a personal AI assistant system — a fleet of specialist agents orchestrated
through NATS JetStream, accessible via voice (Reachy Mini), messaging (Telegram/Slack),
dashboard, and CLI. The fleet handles the full lifecycle from ideation through to deployed
code:

```
Ideation → Product Owner → Architect → GuardKit Factory
(explore)   (document)      (architect)   (implement)
```

Plus a General Purpose Agent for everything else, a YouTube Planner for content creation,
and a GCSE English Tutor for a family member.

But the system is not the point. **The system is a vehicle for learning.** The real goals
are deeper.

---

## The Three Goals

### 1. Learn AI-Augmented Development by Doing It

Every software engineer is trying to figure out how to work effectively with AI. Most
are reading blog posts and watching demos. We're building real systems, hitting real
problems, and documenting real solutions.

The war stories are the asset:
- **180+ review reports** across AutoBuild runs, revealing patterns in how AI agents fail
- **FB01–FB28 cascading fix series** — a single root cause that propagated through 28
  fixes, teaching us about the stochastic development problem
- **The NemoClaw saga** — where NVIDIA's marketing promised one thing and the community
  forums revealed another, teaching us about due diligence with new platforms
- **The C4 validation discovery** — that forcing C4 diagramming changes root cause
  analysis approximately 9/10 times vs verbal analysis alone
- **The self-evaluation failure** — that AI agents confidently fill specification gaps
  rather than acknowledging uncertainty, and that adversarial evaluation (Coach) catches
  what self-evaluation misses

These insights don't become obsolete when tools change. They're transferable knowledge
about how to work with AI systems, period.

### 2. Learn Fine-Tuning, RAG, and Agentic AI Hands-On

The technology stack we're working with is genuinely at the frontier:

- **Fine-tuning small language models** — Unsloth QLoRA on Nemotron 3 Nano 30B-A3B,
  learning that fine-tuning teaches behaviour while RAG teaches facts (two independently
  updatable layers)
- **Knowledge graphs for agent memory** — Graphiti (FalkorDB-backed) providing persistent
  architectural memory across sessions, solving the "stochastic development problem"
  where agents re-learn architecture every session
- **Agent harness design** — both Claude Agents SDK and LangChain DeepAgents SDK,
  understanding the model/runtime/harness primitives that every coding agent shares
- **Adversarial cooperation** — Player-Coach pattern, weighted evaluation, the Anthropic
  insight that making evaluators sceptical is more tractable than making generators
  self-critical
- **Local inference** — vLLM on DGX Spark GB10, three simultaneous models, the reality
  of running AI locally vs the marketing promises

Each of these is a skill that compounds. The combination — someone who can fine-tune
models AND build agentic systems AND design knowledge graph architectures AND has 25
years of systems engineering — is genuinely rare.

### 3. Build Content from the Journey

The YouTube channel isn't a side project — it's the documentation layer for goals 1 and 2.
Every problem solved is a potential video. Every honest failure is content that resonates
with the target audience: mid-career engineers navigating the AI transition.

The Rory Sutherland insight applies: **sell how you think, not what you do.** A video about
"how to use AutoBuild" has a shelf life. A video about "what I learned from 180 review
reports about why AI agents fail" is evergreen. The tool might change; the insight is permanent.

The one-of-one test: could 100 other creators make this video? If the content is grounded
in specific, lived experience (the FB28 fix series, the NemoClaw forums, the moment James
reviewed 14 FinProxy docs and had almost no feedback), the answer is no.

---

## Durability Analysis

Not everything we're building has the same shelf life. Understanding which layers are
durable and which are replaceable is critical for making good investment decisions.

### Layer 1: Methodology & Domain Knowledge (Permanent)

These survive any tool or framework change:

| Asset | Why It's Durable |
|-------|-----------------|
| C4 validation as root cause analysis | Architectural pattern, tool-independent |
| Adversarial evaluation beats self-evaluation | Fundamental AI insight, validated by Anthropic independently |
| Fine-tuning teaches behaviour, RAG teaches facts | Model-agnostic principle |
| Weighted criteria for subjective quality grading | Evaluation methodology, domain-independent |
| Review-before-fix workflow | Engineering discipline |
| Specification by Example (BDD/Gherkin) | Decades-old, tool-independent methodology |
| "Stay at altitude" architectural practice | Engineering wisdom |
| Autonomy bias detection in frontier models | Structural AI insight |
| The 180+ review reports and lessons learned | Historical evidence, permanently valuable |
| Template seeding into knowledge graphs | Context engineering pattern |

**Risk of obsolescence: Near zero.** These are ways of thinking, not tools.

### Layer 2: Architectural Patterns (2-3+ Years)

These are durable patterns that may shift in specific implementation but the concepts persist:

| Asset | Why It's Durable | What Might Change |
|-------|-----------------|-------------------|
| NATS event bus for multi-agent orchestration | Event-driven architecture is standard | Specific message broker might change |
| Intent router dispatching to specialist agents | The industry is converging on this pattern | Router implementation might simplify |
| Adapter pattern (stateless protocol translators) | Classic integration pattern | Adapters may become unnecessary if platforms standardise |
| Two-model separation (reasoning ≠ implementation) | Prevents self-confirmation bias | May become unnecessary as models improve |
| Human-in-the-loop checkpoints via approval topics | Essential for trust in autonomous systems | Checkpoint frequency may decrease over time |
| Provider-agnostic execution (cloud/local switchable) | Avoids vendor lock-in | The "local" option may become less relevant if cloud costs drop |
| Multi-tenancy via topic prefix isolation | Standard multi-tenant pattern | Account model may evolve |
| Graphiti for persistent architectural memory | Knowledge graphs for agent context is growing | Specific KG technology may change |
| CAN bus dynamic registration pattern | Self-announcing agents is becoming standard | Protocol details may simplify |

**Risk of obsolescence: Low-medium.** The patterns are sound. Specific technologies
(NATS, Graphiti, DeepAgents SDK) may be superseded, but migration is bounded — swap
the implementation, keep the interface.

### Layer 3: Templates & Agent Implementations (12-18 Months)

These are the most replaceable — and that's by design:

| Asset | What Might Replace It | Mitigation |
|-------|----------------------|-----------|
| `langchain-deepagents` templates | Better agent frameworks, native SDK templates | Templates are extractable patterns — the methodology transfers |
| AutoBuild Player-Coach loop | Better AI coding agents (Claude native, Cursor improvements) | Tool interface stability (D7) — swap implementation, keep interface |
| Specific agent implementations | End-to-end platforms that do it all | Heterogeneous fleet means adopt best-of-breed per agent |
| vLLM local inference setup | NVIDIA stack improvements, NemoClaw maturity | Provider-agnostic config — switch providers via YAML |
| DeepAgents SDK | Framework consolidation, new entrants | Orchestrator template captures patterns above the framework |

**Risk of obsolescence: Medium-high.** But this is the *designed-to-be-replaceable* layer.
The architecture explicitly supports swapping these components:

- Tool interface stability (D7): signatures identical across implementations
- Provider independence: `agent-config.yaml` switches cloud/local
- NATS backbone: agents are independent — replace one without touching others
- Template harvest pattern: build → prove → extract template → rebuild from better template

### The "Good Enough Kills Great" Risk

The biggest strategic risk isn't that individual tools get replaced. It's that a big
player ships an integrated end-to-end platform that's *good enough* across the whole
pipeline — ideation through deployment — making the overhead of maintaining a custom
multi-agent fleet not worth it.

**Why we're protected against this:**

1. **Heterogeneous fleet** — If Cursor ships a great coding agent, we swap our
   implementation model. If Google ships a great ideation tool, we swap our ideation
   agent. The intent router doesn't care what's behind each dispatch.

2. **Domain-specific knowledge** — No generic platform will encode Rich's architectural
   patterns, Appmilla's project knowledge, or the specific evaluation criteria for
   FinProxy regulatory compliance. The domain layer is ours.

3. **Graphiti compounds** — Every project the Architect Agent processes adds to the
   knowledge graph. After 10 projects, the system knows patterns a generic tool can't.
   This is a moat that grows with use.

4. **The learning was the point** — Even if every tool is replaced, the skills and
   insights gained from building the system are permanent personal assets.

---

## What We're NOT Building

Clarity on scope prevents scope creep:

- **Not a product for others** (yet) — This is a personal/Appmilla system. Open-sourcing
  methodology (not data/tools) is the future strategy if it proves valuable.
- **Not a replacement for Claude Desktop** — The agents jumpstart and structure work.
  Deep back-and-forth ideation still happens in Claude Desktop. The Ideation Agent does
  the first 30 minutes of warm-up, not the whole session.
- **Not a competitor to Cursor/Windsurf/etc.** — Those are coding tools. This is a
  full-lifecycle system from ideation through deployment. Different scope.
- **Not an enterprise platform** — Single developer (Rich) + small team (James, Mark).
  Designed for personal productivity, not multi-team enterprise deployment.

---

## The Compounding Flywheel

The system is designed to compound across multiple dimensions:

```
Build agents with GuardKit Factory
    → Agents produce YouTube content ideas
    → Content documents the building process
    → Content attracts community
    → Community feedback improves methodology
    → Methodology improves agent templates
    → Better templates build better agents
    → Agents produce better content...
```

**Graphiti compounds:** Every project adds architectural knowledge. The tenth project
benefits from lessons in the first nine.

**Templates compound:** Every bug found updates the template. The TRF-12 review found
84% of bugs were template-preventable — those fixes now benefit every future project.

**Content compounds:** Every failure story is a video. Every honest assessment builds
trust. The channel grows while the system improves.

**Skills compound:** Fine-tuning + RAG + knowledge graphs + agent harnesses + systems
engineering + content creation. Each skill makes the others more valuable.

---

## Containerisation Strategy: Phase 2, Driven by Concurrency

### The Question

Should agents run in containers (Docker/Podman) for safety, isolation, and portability?
Google's SCION project (April 2026) takes this approach — wrapping coding agents (Gemini CLI,
Claude Code, Codex) in OCI containers with isolated credentials, workspaces, and lifecycle
management. NemoClaw uses OpenShell sandboxes with kernel-level isolation. Is this something
we need?

### The Assessment: Yes, and Sooner Than Originally Planned

The original decision deferred containers to Phase 10+. Two architectural insights
changed this:

1. **CAN bus registration pattern** — With dynamic agent discovery, containers become
   the natural lifecycle management unit. `docker compose up` brings agents online,
   they auto-register with Jarvis, `docker compose down` triggers graceful deregistration.
   The container IS the agent lifecycle.

2. **Concurrency requires isolation** — Running multiple agent instances in parallel
   (e.g., two GuardKit Factory instances for concurrent project builds) requires process
   isolation. Without containers, you're managing 6-8 Python processes manually — venvs,
   port conflicts, mixed log files, no clean start/stop per agent. With containers,
   `docker compose up --scale guardkitfactory=2` gives you parallel builds immediately.

**Containers move to Phase 2** — alongside NATS infrastructure. The `nats-asyncio-service`
template already produces a Dockerfile. NATS infrastructure is already Docker Compose.
Adding agent containers to the same compose network is natural, not additional overhead.

**Why containers matter for agents:**
- **Blast radius** — An agent with filesystem and network access can damage the host if it
  goes wrong. A container limits the damage to the container.
- **Credential isolation** — Each agent gets its own API keys, preventing one compromised
  agent from accessing another's credentials.
- **Reproducibility** — Same Python version, same dependencies, every time. No "works on
  my machine" across GB10 and MacBook.
- **Multi-tenant trust** — When Mark runs agents against FinProxy, a container boundary
  means his agent can't accidentally access Appmilla-internal files.
- **Always-on safety** — Agents running autonomously overnight need a stronger safety net
  than agents you're actively watching.

**Risks to manage (not blockers):**
- **GPU passthrough complexity** — Agents that need local vLLM inference require GPU access
  inside the container. On DGX Spark with ARM64, this needs testing (similar to NemoClaw's
  cgroup issues — see nemoclaw-assessment.md). However, most agents call vLLM via HTTP API,
  not direct GPU access, so this only affects the vLLM service itself (already containerised).
- **Image rebuild cycle** — Templates and agent configurations are still changing. Pin to
  `docker compose build` + volume mounts for config, not baked-in images, during development.
- **Debugging overhead** — Mitigated by `docker compose logs -f {agent}` and NATS monitoring
  on port 8222. The fleet-status.sh script provides a quick overview.

### When to Add Containers

The trigger is a shift in risk profile, not a technology choice:

| Trigger | Why It Matters |
|---------|---------------|
| Agents run autonomously overnight | No human watching → need automated safety boundary |
| Agents have write access to production systems | Sending emails, deploying code, modifying databases |
| Multi-tenant with external collaborators | Mark or client teams running agents on shared infrastructure |
| Reproducible CI/CD for agent pipelines | Agent builds should be deterministic across environments |
| FinProxy goes into production | Real client data requires real isolation |

**Timing: Phase 2** — alongside NATS infrastructure deployment. The `nats-asyncio-service`
template produces Dockerfiles. The `nats-infrastructure` repo contains fleet compose files.
Every agent built from Phase 3 onward starts containerised from day one.

### What SCION Gets Right (and Wrong for Us)

**Right:**
- Container-per-agent with isolated credentials and workspaces is a sound pattern
- Harness abstraction (same lifecycle commands regardless of underlying agent) is elegant
- Agent state model (phase × activity × detail) is well-designed
- Support for multiple container runtimes (Docker, Podman, Apple Container, K8s)

**Wrong for us:**
- SCION orchestrates off-the-shelf coding agents (Gemini CLI, Claude Code). Our agents
  are custom DeepAgents SDK agents with adversarial evaluation — fundamentally different
- SCION's orchestration is manager-worker (start container, give task, watch). Ours is
  event-driven via NATS with weighted evaluation, human-in-the-loop, and Graphiti context
- SCION's Hub is GCP-oriented (OAuth, K8s, remote brokers). We're local-first on GB10
- SCION is experimental/testbed. We need production stability

**The pattern we're adopting:** Container-per-agent with the `nats-asyncio-service`
template producing a Dockerfile alongside the service code. Fleet compose files in
`nats-infrastructure/compose/`. NATS infrastructure is already Docker-based so agents
join the same Docker network. Container lifecycle maps directly to fleet registration:
container starts → agent registers, container stops → agent deregisters.

### The Architecture Already Supports It

Nothing about our current design prevents containerisation. The key properties are already
in place:

- **NATS communication** — Agents talk via network (NATS), not filesystem. Moving them
  into containers doesn't change communication patterns.
- **Provider-agnostic config** — `agent-config.yaml` already externalises connection
  strings, API keys, and model endpoints. These map directly to Docker environment
  variables or mounted secrets.
- **Stateless adapters** — Adapters are thin NATS translators. Trivially containerisable.
- **Template-based scaffolding** — Adding a `Dockerfile.template` to `nats-asyncio-service`
  means every bootstrapped service gets containerisation for free.

The containerisation step is additive — add Dockerfiles, add compose services, add
credential volume mounts. No architectural changes needed.

### Decision

**D14: Containerisation** — Phase 2. Agents run in Docker containers for lifecycle
management (CAN bus registration pattern), concurrency (parallel builds via `--scale`),
and operational sanity (clean start/stop/logs per agent). The `nats-asyncio-service`
template produces Dockerfiles. Fleet compose in `nats-infrastructure` repo.

---

## How to Read the Rest

| Document | What It Covers | Where |
|----------|---------------|-------|
| **Fleet Master Index** | Technical inventory: all repos, agents, templates, build sequence | `guardkitfactory/docs/research/ideas/fleet-master-index.md` |
| **Jarvis Vision** | Intent router architecture, CAN bus registration, agent fleet details | `jarvis/docs/research/ideas/jarvis-vision.md` |
| **Individual Agent Visions** | Per-agent architecture, weighted criteria, interaction flows | `{agent-repo}/docs/research/ideas/{agent}-vision.md` |
| **nats-core System Spec** | Message schemas, topic registry, fleet registration, BDD criteria | `nats-core/docs/design/specs/nats-core-system-spec.md` |
| **nats-infrastructure System Spec** | Server deployment, accounts, streams, fleet compose | `nats-infrastructure/docs/design/specs/nats-infrastructure-system-spec.md` |
| **NemoClaw Assessment** | Evidence-based rejection of NemoClaw with revisit signals | `jarvis/docs/research/ideas/nemoclaw-assessment.md` |
| **Pipeline Orchestrator Conversation Starter** | GuardKit Factory `/system-arch` input | `guardkitfactory/docs/research/pipeline-orchestrator-conversation-starter.md` |

---

## The Honest Bottom Line

We're building a system that might look different in 18 months as tools evolve. But the
methodology, the architectural patterns, the domain knowledge, and the skills gained from
building it are permanent. The repos are the evidence. The war stories are the content.
The journey is the product.

The worst case isn't that the tools change — it's that we stop learning. As long as we're
building, failing honestly, documenting what happened, and sharing the stories, every hour
invested produces durable value regardless of what the technology landscape does next.
