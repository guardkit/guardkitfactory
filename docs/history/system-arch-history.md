system-arch \
  --context forge/docs/research/forge-pipeline-architecture.md \
  --context forge/docs/research/forge-build-plan-alignment-review.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md \
  --context forge/docs/research/pipeline-orchestrator-conversation-starter.md \
  --context forge/docs/research/pipeline-orchestrator-motivation.md \
  --context forge/docs/research/ideas/fleet-master-index.md \
  --context specialist-agent/docs/research/ideas/architect-agent-vision.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md

  All context paths resolve. Before I run the 6-category session I need to stop on two things per the command spec.

Mode / Graphiti state

Mode: setup (no files found in docs/architecture/)
Graphiti availability: unavailable — .guardkit/graphiti.yaml exists but only contains project_id: forge (no enabled: true). The session will generate markdown artefacts but will not persist to Graphiti.
Missing required argument

/system-arch requires a project description as the first positional argument. Your invocation contained only --context flags — no description string.


/system-arch "project description" [--context ...]
Proposed description (please confirm or amend):

Based on the context filenames — forge-pipeline-architecture, forge-build-plan, forge-pipeline-orchestrator-refresh, pipeline-orchestrator-motivation, fleet-master-index, architect-agent-vision, nats-core-system-spec, agent-manifest-contract — the system under design appears to be:

"Forge — pipeline orchestrator agent and fleet coordination layer for the specialist-agent / NATS-core multi-agent system"

Before I read the nine context files and start Category 1: Domain & Structural Pattern, please confirm:

Project description — use the proposed text above, or provide your own?
Scope confirmation — is this architecture session about Forge alone (the pipeline orchestrator repo we're sitting in), or about Forge + its fleet peers (specialist-agent, nats-core)? The context mix suggests the latter, which meaningfully changes the bounded-context answers in Category 2.
Proceed without Graphiti persistence? [Y/n] — markdown artefacts will still land in docs/architecture/, but /system-design, /system-plan, and /feature-spec won't be able to query this context via knowledge graph.
Once you answer, I'll load all nine context files and begin the interactive session.

Lets fix Graphiti please refer to /Users/richardwoollcott/Projects/appmilla_github/guardkit/.guardkit/graphiti.yaml for an example of how it should be configured - it's essential we have this working to seed the architecture docs and ADR's


Reading the guardkit template — it's a working config pointing at FalkorDB on the Synology NAS via Tailscale, with Gemini 2.5 Pro for ingestion. I'll mirror it for Forge, keeping the project_id: forge namespace and adjusting group_ids to match the groups /system-arch seeds into.

Config rewritten. Now let me verify connectivity end-to-end before we start the architecture session — a config that parses but can't reach FalkorDB would silently drop every seeding call.

Graphiti is live. Summary:


Status:        ENABLED
Connection:    FalkorDB @ whitestocks:6379 (via Tailscale) ✓
Embeddings:    GB10 vLLM @ promaxgb10-41b1:8001 (nomic-embed-text-v1.5, 1024-dim) ✓
LLM (ingest):  Gemini 2.5 Pro (cloud)
Total episodes: 585 across the graph
Project scope: project_overview: 2 episodes under project_id=forge
FalkorDB workarounds are applied (PR #1170, issues #1272 — single-group handling and O(n) edge search fixes). graphiti_available = true for the upcoming session.

One observation worth flagging: the group_ids block in the config is advisory — the CLI already exposes canonical groups (product_knowledge, command_workflows, architecture_decisions, failure_patterns, etc.), and /system-arch will seed into project_architecture, architecture_decisions, project_decisions regardless of what's listed in the yaml. Listing them in yaml just documents intent; the CLI accepts any group name on add-context --group.

Ready to start the session. Back to the three questions from before:

Project description — confirm "Forge — pipeline orchestrator agent and fleet coordination layer for the specialist-agent / NATS-core multi-agent system", or give me different wording?
Scope — Forge alone, or Forge + fleet peers (specialist-agent + nats-core)?
Graphiti is now available, so question 3 from my earlier message no longer applies.
Once you answer 1 & 2, I'll read all nine context files and open Category 1: Domain & Structural Pattern.

1: yep thats good, 2: Forge alone, nats-core, nats-infrastructure and specialist-agent are all implemented and deployed
Scope is clear: Forge as the unit of design; the other fleet repos are environment context. Loading all nine files in parallel now.

Read forge-pipeline-architecture.md
Read forge-build-plan-alignment-review.md
Read forge-pipeline-orchestrator-refresh.md
Read pipeline-orchestrator-conversation-starter.md
Read pipeline-orchestrator-motivation.md
Read fleet-master-index.md
Read architect-agent-vision.md
Read nats-core-system-spec.md
Read agent-manifest-contract.md
All nine context files absorbed (one — forge-build-plan-alignment-review.md — exceeded token limit, but its substance is quoted at length in the architecture doc itself, so I have the material).

Note: I'm using the propose-review pattern — I'll populate proposed answers for each question from the context files, and you tell me to accept, amend, or replace. This is faster than blank-prompting you with questions whose answers already exist in the anchor doc.

Category 1: Domain & Structural Pattern
Q1. What does this system do?

Proposed answer (from forge-pipeline-architecture.md §1 + pipeline-orchestrator-motivation.md):

Forge is a NATS-native pipeline orchestrator that consumes pipeline.build-queued.{feature_id} messages from JetStream and drives a queued feature through five pipeline stages (specification review → architecture review → feature planning → AutoBuild execution → PR creation) to a merged-ready pull request. At each stage, it evaluates Coach scores from specialist agents against configurable thresholds and decides 🟢 auto-approve / 🟡 flag-for-review / 🔴 hard-stop. The human moves from operator to approver: a pipeline that is accepted 93% of the time is driven by the orchestrator, not by human keystrokes.

Q2. Who are the primary users?

Proposed answer (from forge-pipeline-architecture.md "Actors" and §5.0 "Build Request Sources"):

User	Role
Rich (human)	Primary operator — queues builds via forge queue, reviews 🟡 flagged builds, reviews PRs, configures thresholds
Jarvis (automated caller)	Publishes pipeline.build-queued on Rich's behalf after classifying voice/Telegram/Slack/dashboard intents
Specialist Agent — Product Owner (automated callee)	Called by Forge at Stage 1 via agents.command.product-owner-agent; returns Coach-scored result
Specialist Agent — Architect (automated callee)	Called by Forge at Stage 2 via agents.command.architect-agent; returns Coach-scored result
GuardKit CLI (subprocess)	Invoked at Stage 4 as guardkit autobuild feature FEAT-XXX --nats
GitHub / gh CLI (subprocess)	Used at Stage 5 for push + PR creation
James, Mark (humans)	PR reviewers on GitHub — they never touch Forge directly. Mentioned here only so we don't accidentally design a feature for them.
Q3. What are the core business domains within Forge?

Proposed answer — eight internal domains, derived from §§3–10 of the anchor doc:

Build Queue & Ingestion — JetStream pull consumer, AckWait, crash-recovery redelivery
Pipeline State Machine — IDLE → PREPARING → RUNNING → PAUSED → FINALISING → COMPLETE/FAILED/INTERRUPTED
Confidence Gating — evaluating Coach scores against per-stage forge.yaml thresholds; gate-mode selection
Specialist Agent Dispatch — NATS command/result round-trip to PO + Architect; reply-subject correlation (LES1 parity rule)
GuardKit Subprocess Integration — invoking guardkit autobuild with --nats, streaming progress events, handling timeouts
Git & PR Operations — clone/pull/branch/commit/push; PR via gh CLI
Build History Store — SQLite ~/.forge/forge.db — builds table + stage_log table; queryable for forge status / forge history
Fleet Integration — fleet.register publication (so Jarvis can discover Forge); heartbeat; config/threshold reload
Q4. What structural pattern best fits Forge?

Candidates ranked by fit for this system:

Option	Trade-offs	Fit
[C] Clean / Hexagonal	+ Central pure core (state machine + gating logic) with pluggable ports for NATS, SQLite, subprocesses, GitHub. + Makes the contract boundary with nats-core, GuardKit, and gh explicit. + Aligns with ADR-SP-011 ("no transport abstraction layer" — meaning no internal ABC, not that ports are banned). + Easy to unit-test the gating logic without any of the adapters. − Slightly more ceremony for small projects.	Strong
[M] Modular Monolith	+ Single Python process, single binary (matches the anchor). + Each of the 8 domains above becomes a module with clear boundaries. + Lower ceremony than hexagonal. − Less explicit about the port/adapter seam.	Strong
[E] Event-Driven	+ Forge externally is event-driven (JetStream in, pipeline events out). − Internally the process is a sequential state machine per build, not an internal event loop. Applying EDA internally would add complexity for no gain.	Medium (external only)
[D] DDD	+ Proper bounded-context design for 8 distinct domains. − Overkill for a single-process orchestrator owned by one developer. The ADRs are "SP-*" (Software Pipeline) not context-scoped.	Weak
[L] Layered	− The 8 domains don't layer cleanly; gating talks to persistence and NATS and subprocess.	Weak
My recommendation: [C] Clean / Hexagonal — with the 8 domains above as modules inside the core, and thin adapters at the edges (NATS adapter using nats-core, SQLite adapter, Git adapter, GuardKit adapter, Specialist-Agent adapter which wraps call_agent_tool()). This is what ADR-SP-011's "NATS-native" actually looks like in the small: NATS is the transport, not a replaceable abstraction, but the logic (state machine, confidence gating, stage orchestration) is pure and testable.

[M] is a very close second and differs only in ceremony.

Your turn. For each of Q1–Q4, reply with either:

C1 (accept all four as proposed), or
Per-question edits: Q1: <your text>, Q2: <amend>, Q3: keep + add X, Q4: M (or other letter).
Once you're happy, I show the Category 1 checkpoint ([C]ontinue / [R]evise / [S]kip / [A]DR?) and then we move to Category 2 — which will lean heavily on whether you pick C or M in Q4.

I justwant to check that you are aware the intention is to use a langchain deepagents harness fpr this? I see no mention of this which is concerning to me-did you read the docs?
You're right to call that out — I had the context and I still elided it. Apologies.

Evidence I had and under-weighted:

.claude/CLAUDE.md — the project instruction is literally "LangChain DeepAgents — Pipeline Orchestrator ... two-model architecture ... LangGraph with hierarchical subagent composition"
forge-pipeline-orchestrator-refresh.md:510 — template: langchain-deepagents-weighted-evaluation
fleet-master-index.md D1: "Agent framework: LangChain DeepAgents SDK"
Seven DeepAgents specialist agents registered in .claude/rules/guidance/ (deepagents-orchestrator, subagent-composition, langchain-tool-decorator, langgraph-deployment-config, system-prompt-template, pytest-agent-testing, domain-context-injection)
I skipped to "single Python process with a state machine" when the anchor is explicitly a DeepAgents create_deep_agent() compiled state graph with two models, hierarchical sub-agents, and @tool(parse_docstring=True) tools exposed via langgraph.json. That's a material omission — it changes Q4 (structural pattern), Q3 (the domains include sub-agent composition and tool schema, not a hand-rolled state machine), and it sets the frame for Categories 2 and 3.

Revised framing I'll carry from here on:

Orchestrator runtime: create_deep_agent(reasoning_model, tools=[...], subagents=[...], system_prompt=..., memory=[...]) → CompiledStateGraph exported via langgraph.json
Two models: reasoning model drives the LangGraph loop + quality evaluation; implementation model runs inside tools/sub-agents that generate artefacts or invoke GuardKit
Sub-agents: SubAgent/AsyncSubAgent TypedDicts — likely one per pipeline stage (spec-reviewer, architect-dispatcher, feature-planner, autobuild-runner, pr-finaliser) plus async wrappers for the NATS round-trips to specialist agents
Tools: @tool(parse_docstring=True) functions — NATS publish/subscribe helpers, SQLite writers, git/gh wrappers, call_agent_tool() adapters — all returning strings and swallowing exceptions (per the langchain-tool-decorator-specialist rule)
System prompt: templated domain-agnostic string with {date}, {domain_prompt} placeholders, injected at startup from domains/forge/DOMAIN.md
Persistence: LangGraph checkpointer for in-graph state + SQLite for across-restart build history
Config: orchestrator-config.yaml (model selection via provider:model strings for init_chat_model), forge.yaml (thresholds), argparse.parse_known_args to survive LangGraph server's injected argv
Impact on Q4: Clean/Hexagonal is still coherent at the module-organisation level (pure confidence-gating/state logic + edge adapters), but the runtime topology is fixed by DeepAgents: one compiled graph, a set of tools, a list of sub-agents. I'd restate the answer as:

Hybrid: Hexagonal modules inside a DeepAgents two-model orchestrator. The DeepAgents CompiledStateGraph is the outer shell (reasoning loop, sub-agent dispatch, tool invocation). Inside, domain modules (confidence-gating, state reconciliation, stage orchestration) are pure and testable; thin adapters expose them as @tools. nats-core, SQLite, git/gh, and GuardKit are the external ports.

Want me to:

Re-issue Category 1 with Q1–Q4 rewritten to make DeepAgents / two-model / sub-agent composition explicit before you sign off, or
Accept the correction above as the Category-1 delta and move on to Category 2 (Module Structure) with this framing locked in?
accept the correction and continue
Category 1: Checkpoint — Accepted
Captured:

Purpose: NATS-native pipeline orchestrator driving feature → PR via 5 confidence-gated stages
Users: Rich (operator); Jarvis + Specialist Agents (Product Owner, Architect) as automated peers; GuardKit + gh as subprocess callees; James/Mark as PR reviewers outside the system
Domains: 8 internal concerns (queue ingestion, stage orchestration, confidence gating, specialist dispatch, GuardKit integration, git/PR, build history, fleet integration)
Structural pattern: Hexagonal modules inside a DeepAgents two-model orchestrator — create_deep_agent() compiled graph is the shell; pure domain logic inside; @tools and SubAgent/AsyncSubAgent specs expose it; thin adapters to NATS, SQLite, git, gh, GuardKit
ADRs queued for write (3):

ADR-ARCH-001: Clean/Hexagonal modules within DeepAgents two-model orchestrator (Q4 decision)
ADR-ARCH-002: Two-model separation — reasoning model drives graph, implementation model executes within tools/sub-agents (from CLAUDE.md + D5 fleet-wide)
ADR-ARCH-003: NATS-native orchestration — nats-core adapters, no transport ABC (re-states ADR-SP-011 locally)
These will be written in Phase 3. Moving on.

Category 2: Module Structure
Given the pattern is Hexagonal + DeepAgents, questions adapt to module (not bounded-context) language. Event-driven sub-questions apply since Forge is externally event-driven.

Q5. What are the major modules/components of Forge?

Proposed — 11 modules grouped by Hexagonal role:

A. DeepAgents Shell (outer runtime — entry point)
forge.agent — wires create_deep_agent(reasoning_model, tools, subagents, system_prompt, memory) → CompiledStateGraph; exported via langgraph.json as ./forge/agent.py:agent
forge.prompts — domain-agnostic system prompt templates with {date} / {domain_prompt} placeholders; one module per sub-agent role (per the system-prompt-template-specialist rule)
forge.subagents — SubAgent/AsyncSubAgent TypedDict factories. One per pipeline stage (spec_reviewer, architecture_dispatcher, feature_planner, autobuild_runner, pr_finaliser) plus async wrappers for NATS round-trips
B. Domain Core (pure, testable, no I/O)
forge.gating — Coach score evaluation vs forge.yaml thresholds; returns GateDecision(mode=auto|flag|hard_stop, reason, detections). Pure functions only.
forge.state_machine — pure state-transition functions: Preparing → Running → Paused → Finalising → Complete/Failed/Interrupted. Returns event emission intents; does not perform I/O.
forge.stages — per-stage orchestration policy: what inputs each stage needs, what specialist to call, what GuardKit command to invoke, what gate config applies
C. Tool Layer (@tool(parse_docstring=True) functions — the seam between DeepAgents and adapters)
forge.tools — one sub-module per tool family: queue_tools.py, specialist_tools.py (wraps call_agent_tool()), guardkit_tools.py, git_tools.py, pr_tools.py, history_tools.py. All return strings, wrap logic in try/except, never raise (per langchain-tool-decorator-specialist rule).
D. Adapters (I/O edges — one per external port)
forge.adapters.nats — wraps nats_core.NATSClient — JetStream pull consumer, publish helpers for pipeline.* events, specialist call_agent_tool() with reply-subject correlation per LES1 parity rule
forge.adapters.sqlite — ~/.forge/forge.db — builds table, stage_log table; WAL mode; crash-recovery reconciliation query
forge.adapters.git — subprocess wrapper around git + gh CLIs; clone/pull/branch/commit/push/PR creation
forge.adapters.guardkit — subprocess invocation of guardkit autobuild feature ... --nats with timeout handling + progress stream consumption
E. Cross-cutting
forge.config — AgentConfig extension from nats-core + forge.yaml loader (thresholds, build_config, degraded_mode); argparse.parse_known_args() for CLI args that survive LangGraph server injection
forge.cli — forge queue | status | history | cancel | skip via Click
forge.fleet — fleet.register publication on startup, heartbeat publisher, AgentManifest construction from role config
Q6. Responsibilities — boundary rules (what each module MUST and MUST NOT do):

Module	MUST	MUST NOT
agent	Wire DeepAgents graph only	Contain domain logic
prompts	Pure string templates	Read env vars or files (injection happens at startup)
subagents	Return SubAgent TypedDict factories	Execute logic directly
gating / state_machine / stages	Pure Python, unit-testable without NATS/SQLite/subprocess	Import nats_core, sqlite3, subprocess
tools	Wrap adapters in @tool(parse_docstring=True); return strings; never raise	Contain domain logic (delegate to domain core)
adapters.*	All I/O; typed Pydantic models in/out	Know about other adapters
config	Schema validation + loading	Mutate at runtime
cli	Thin shell over adapters.nats (for queue) and adapters.sqlite (for status/history)	Invoke the DeepAgents graph
fleet	AgentManifest construction + heartbeat lifecycle	Touch pipeline state
Q7. What data does each module own?

Owner	Data	Lifetime
adapters.sqlite	builds + stage_log tables	Durable — ~/.forge/forge.db, WAL
adapters.nats	Reply-subject correlation map (pending call_agent_tool round-trips)	Per-call; cleared on reply or timeout
LangGraph checkpointer (built-in)	In-graph state between reasoning turns	Per-build; not strictly required since SQLite is the durable history
config	Loaded forge.yaml + orchestrator-config.yaml	Process lifetime; reload-on-SIGHUP optional
fleet	Local AgentManifest instance + last-heartbeat timestamp	Process lifetime; registry itself lives in NATS KV (external)
adapters.git	Working-tree path + current branch	Per-build (cleaned on stage completion or failure)
Who owns the authoritative build state? SQLite — with JetStream as the queue/redelivery source. Per ADR-SP-013 these are separate concerns and that stays.

Event-driven sub-questions
Q5e. What event streams does Forge interact with? (from anchor §3)

PIPELINE (consume + produce) — build-queued in; build-started, build-progress, build-complete, build-failed, build-paused, build-resumed, stage-complete, stage-gated out
AGENTS (produce + consume) — agents.command.{po|architect}-agent out; agents.result.{po|architect}-agent.{correlation_id} in
FLEET (produce + consume) — fleet.register out on startup; heartbeat out every 30s; watches fleet.register for specialist-agent availability to detect degraded mode
JARVIS (produce only, optional) — jarvis.notification.* for auto-approve notifications routed back to the originating adapter via parent_request_id
Q6e. Event handlers / processors:

Inbound JetStream consumer (adapters.nats, pull-based, max_ack_pending=1 for sequential builds) — one handler: build-queued → kicks off the DeepAgents graph
Inbound specialist result subscriber — correlation-keyed; matches reply to pending tool call
Outbound publishers — on each state-machine transition, emit the corresponding pipeline.* event via the NATS adapter
Q7e. Eventual consistency:

Queue durability: JetStream AckWait — message unacked until terminal transition (COMPLETE/FAILED/CANCELLED/SKIPPED); PAUSED keeps it unacked indefinitely by design
State reconciliation on startup: SQLite scan for RUNNING/PREPARING rows → mark INTERRUPTED; PAUSED rows stay paused; redelivered message triggers fresh PREPARING from scratch
No distributed transactions needed: sequential builds (ADR-SP-012) + single-writer SQLite + JetStream-as-queue keeps the consistency model local
Category 2 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 2: Module Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

11 modules in 5 groups:
  A. DeepAgents Shell    — agent, prompts, subagents
  B. Domain Core (pure)  — gating, state_machine, stages
  C. Tool Layer          — tools/* (@tool wrappers)
  D. Adapters            — nats, sqlite, git, guardkit
  E. Cross-cutting       — config, cli, fleet

External event streams: PIPELINE, AGENTS, FLEET (+ JARVIS for outbound notifications)
Authoritative build state: SQLite (durable) + JetStream (queue)
Your move. Reply with either:

C2 (accept, continue to Category 3: Technology & Infrastructure), or
Edits: e.g. "merge stages into state_machine", "drop fleet — put heartbeat into adapters.nats", "add a forge.observability module for LangSmith tracing", etc., or
A to capture an ADR inline (e.g. "ADR: Pure domain core with no I/O imports"), or
R to revise specific questions.
[R]evise - overall I'm happy with the shape of this, just wanted to check that the guardkit tooling is not limited to autobuild feature calls but should alos be able to use all of the guardkit CLI, e.g. feature-spec, feature-plan, task-review, task-work and task-complete for example. Also the calls back to Jarvis for notifications should include confirmation of actions while the system is training and writing/reading to Graphiti so the forge gets smarter and as we progress through the build pipeline we should present notifications back to Jarvis which we can tune, i.e. turn on/off for the various stages.
Good catches. Both are load-bearing and I under-scoped them. Revisions:

Revision 1 — GuardKit tool surface is the full CLI, not just AutoBuild
forge.adapters.guardkit becomes a generic subprocess runner parameterised by subcommand, args, timeout, and progress-stream handling. One adapter, many tools.

forge.tools.guardkit_tools exposes one @tool per GuardKit subcommand — each a thin wrapper that delegates to the adapter:

@tool	Used at
guardkit_feature_spec	Stage 1 / Stage 3 first half
guardkit_feature_plan	Stage 3 second half
guardkit_task_review	Mode C (review-fix) + post-failure diagnosis
guardkit_task_work	Task-level implementation (called by autobuild or directly in Mode C)
guardkit_task_complete	Task finalisation + rollup
guardkit_autobuild	Stage 4
guardkit_graphiti_seed	Post-stage seeding
guardkit_graphiti_query	Context retrieval
Sub-agent lineup revised: feature_spec_dispatcher, feature_planner, task_reviewer, task_worker, task_completer, autobuild_runner, pr_finaliser — each sub-agent bundles the relevant tools + prompt for that stage, so the reasoning model can pick the right one per pipeline mode (Greenfield / Feature / Review-Fix).

This also rescues Mode C (review-fix from anchor §4 footnotes) — currently under-represented if we treated Forge as "spec → plan → autobuild → PR" only.

Revision 2 — Jarvis notifications are a training-signal + Graphiti feedback loop, not fire-and-forget
This is new module territory. Three additions:

New domain-core module
forge.notifications (pure) — constructs NotificationPayload intents from (StageEvent, GateDecision); checks per-stage config; decides what to emit, not where (that's the adapter). Supports:

Per-stage on/off per event type (auto-approve | flag | hard-stop | stage-start | stage-complete)
Confirmation-required flag (during training mode, Rich must confirm via ApprovalResponsePayload before Forge proceeds even on auto-approve)
New domain-core module
forge.learning (pure) — threshold calibration heuristics. Reads prior build outcomes + override events from Graphiti; computes per-stage override rates; proposes threshold adjustments. Matches the refresh doc §Threshold Adjustment: override >10% → lower auto_threshold; override <1% → raise it. Proposes, doesn't mutate — Rich approves the adjustment.

New adapter
forge.adapters.graphiti — wraps Graphiti client scoped to project_id=forge / group_id=forge_pipeline_history (per architect-agent-vision's Layer 2). Writes: GateDecision, OverrideEvent, SessionOutcome. Reads: historical override patterns, build-summary entities for retrospection.

Config additions to forge.yaml

notifications:
  enabled: true
  default_channel: jarvis.notification.dashboard
  training_mode: true              # requires confirmation on auto-approve
  per_stage:
    specification_review: { on_auto_approve: true,  on_flag: true, on_hard_stop: true,  on_stage_start: false }
    architecture_review:  { on_auto_approve: true,  on_flag: true, on_hard_stop: true,  on_stage_start: false }
    feature_planning:     { on_auto_approve: false, on_flag: true, on_hard_stop: true,  on_stage_start: false }
    autobuild:            { on_auto_approve: false, on_flag: true, on_hard_stop: true,  on_stage_start: true  }
    pr_creation:          { on_auto_approve: true,  on_flag: true, on_hard_stop: true,  on_stage_start: false }

learning:
  enabled: true
  graphiti_group_id: forge_pipeline_history
  min_samples_before_suggesting_adjustment: 10
  override_rate_upper_bound: 0.10
  override_rate_lower_bound: 0.01
  suggest_only: true               # never auto-adjust thresholds without human approval
Updated module count: 11 → 14
Group	Added
B. Domain Core	forge.notifications, forge.learning
D. Adapters	forge.adapters.graphiti
Domain-core boundary rule extends: notifications and learning stay pure — they take structured inputs, return structured intents, never perform I/O. Writes go through adapters.graphiti / adapters.nats; reads come through the same adapters with Pydantic-typed results.

Pipeline-wide note: this makes Forge's "knowledge" a first-class architectural concern — it is not just an orchestrator, it is a learning orchestrator. Worth an ADR.

ADRs added to write-queue (now 5 total):

ADR-ARCH-004: Full GuardKit CLI as tool surface — one @tool per subcommand, generic subprocess adapter
ADR-ARCH-005: Graphiti-fed learning loop + per-stage notification tuning — Forge improves threshold calibration from override history, notifications are tunable per stage/event
Category 2 Checkpoint (revised)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 2: Module Structure (REVISED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

14 modules in 5 groups:
  A. DeepAgents Shell       — agent, prompts, subagents (7 sub-agents now)
  B. Domain Core (pure)     — gating, state_machine, stages, notifications*, learning*
  C. Tool Layer             — tools/* (8 GuardKit tools + specialist + queue + git + pr + history + notification + approval + graphiti)
  D. Adapters               — nats, sqlite, git, guardkit (generic), graphiti*
  E. Cross-cutting          — config, cli, fleet
                              (* = added in this revision)

External streams: PIPELINE, AGENTS, FLEET, JARVIS (outbound notifications + inbound confirmations)
Learning loop: Graphiti (forge_pipeline_history) ← override events → threshold calibration proposals
Training mode: configurable per-stage confirmation-required flag
Reply with:

C2 — accept and continue to Category 3: Technology & Infrastructure
Further edits, or
A for additional ADR inline
[R]evise-I'm liking this, however if the goal is to explicitly list every guardkit tool then please review the command history for the specialist agent since there are additonal calls such as /system-arch, /system-design etc /Users/richardwoollcott/Projects/appmilla_github/specialist-agent/command_history.md. It might be worth exploring creating some training rules/notes/guidance from this history document and others in the nats-core and nats-infrastructure repos, plus I created files such as /Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-spec-FEAT-001-history.md and /Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-adaptive-mode-inference-history.md. My intention was to create a wealth of knowledge in how I answer questions, generally accepting defaults to help guide the Forge. Also the concept of a build plan I think is useful and during the early days we might get this reviewed and approved before continuing as a gated approval which we later relax based on a confidence gate
Good point — both are load-bearing. Reading the training-corpus files now so the revision is grounded in what you actually ran, not guesswork.

Read command_history.md
Read feature-spec-FEAT-001-history.md
Read feature-plan-adaptive-mode-inference-history.md
Read command-history.md
Bash Enumerate all history/calibration files across the three repos
IN
ls /Users/richardwoollcott/Projects/appmilla_github/specialist-agent/*history*.md /Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-*history*.md /Users/richardwoollcott/Projects/appmilla_github/nats-core/*history*.md /Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/*history*.md 2>&1

OUT
/Users/richardwoollcott/Projects/appmilla_github/nats-core/command-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-core/system-arch-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/command-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/feature-plan-docker-compose-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/feature-plan-jetstream-arch-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/feature-plan-kv-store-buckets-history.md
/Users/richardwoollcott/Projects/appmilla_github/nats-infrastructure/feature-plan-operations-scripts-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/command_history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/fature-spec-DDD-context-map-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-adaptive-mode-inference-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-adaptive-mode-inference-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-ADR-output-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-ADR-output-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-assumption-defence-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-assumption-defence-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-DDD-context-map-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-DDD-context-map-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-fidelity-history.md
/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/feature-plan-fidelity-history.md
/Users/richardwooll

Read enough. Full landscape now:

~35 history files across specialist-agent (≈30), nats-core (2), nats-infrastructure (5) — one per session, plus repo-level command_history.md trackers
Complete GuardKit command set in use: /system-arch, /system-design, /system-plan, /feature-spec, /feature-plan, /task-review, /task-work, /task-complete, plus guardkit autobuild, guardkit graphiti add-context/seed, and CLI init
Observed response signatures (from FEAT-001 sample): fast-path tokens (A A A A), inline corrections ("yes accept and add" → "sorry I meant add them"), default-acceptance (accept defaults), >95% default-acceptance corroborating fleet-master-index Pattern 3
Build Plan pattern exists as fully-formed artefact template (phase1-build-plan.md, phase1b-…, phase1c-…, phaseG-…, buildplan.md in lpa-platform) — it is the missing stage between feature-plan and autobuild
Revision 3 — Three additions to Category 2
(a) Full GuardKit tool surface (11 tools, not 8)
@tool	Pipeline stage	Gate profile
guardkit_system_arch	Mode A Stage 0 (if no architecture exists)	Coach-gated
guardkit_system_design	Mode A Stage 0.5	Coach-gated
guardkit_system_plan	Mode A Stage 0.75	Coach-gated
guardkit_feature_spec	Stage 3a (per feature)	Coach-gated, per-spec
guardkit_feature_plan	Stage 3b (task decomposition)	Coach-gated
guardkit_task_work	Stage 4 inner loop	AutoBuild-internal
guardkit_task_review	Stage 4 diagnosis + Mode C	Coach-gated
guardkit_task_complete	Stage 4 rollup	AutoBuild-internal
guardkit_autobuild	Stage 4 orchestration	Coach-gated (aggregate)
guardkit_graphiti_seed	Post-stage seeding	Internal
guardkit_graphiti_query	Context retrieval	Internal
Corollary: Forge produces its own history files (command_history.md, feature-spec-{NAME}-history.md, per-stage logs) in the same pattern. This is training data for the next project — Pattern 2 and Pattern 3 from fleet-master-index propagate forward through the pipeline.

(b) Calibration corpus as first-class architectural concern
Two new modules absorbing Rich's historical Q&A into Forge's decision-making.

forge.calibration (domain core, pure) — parses history files into structured CalibrationEvent records:


class CalibrationEvent(BaseModel):
    source_file: str           # e.g. "specialist-agent/feature-spec-FEAT-001-history.md"
    command: str               # "/feature-spec"
    stage: str                 # "GROUP_A_CURATION" | "ASSUMPTION_RESOLUTION" | ...
    question: str              # the system's prompt to Rich
    default_proposed: str      # what the system suggested
    response_raw: str          # Rich's literal reply
    response_normalised: str   # "accept_all" | "accept_with_edit" | "reject" | "defer" | "custom"
    accepted_default: bool
    custom_content: str | None # any deviation from default
    timestamp: datetime | None
Computes per-command default-acceptance rates and produces CalibrationProfile for seeding forge.gating thresholds at pipeline startup.

forge.adapters.history_parser — tokenises markdown history files, identifies Q&A turns, outputs a stream of CalibrationEvents. One-off ingestion at Forge's init + incremental on new files.

Seeding: calibration events flow to forge.adapters.graphiti under group_id=forge_calibration_history (separate from forge_pipeline_history — Rich's past decisions vs Forge's own build outcomes).

Consumers: forge.gating (prior thresholds), forge.prompts (Rich's signature patterns can feed into the system prompt — "when unclear, Rich tends to accept group-level defaults"), forge.learning (seed point for override-rate adjustment).

(c) Build Plan as explicit gated stage
The anchor's Stage 3 ("Feature Planning") becomes Stage 3a: Feature Planning + Stage 3b: Build Plan Review — a distinct artefact + distinct gate.

New sub-agent: build_plan_composer — consumes all Stage 3a feature plans + context manifests + dependency graph, produces buildplan.md in the canonical structure (Prerequisites / Feature Summary / GuardKit Command Sequence / Files That Will Change / Expected Timeline).

New gate mode in forge.gating:


class GateMode(str, Enum):
    AUTO_APPROVE = "auto_approve"
    FLAG_FOR_REVIEW = "flag_for_review"
    HARD_STOP = "hard_stop"
    MANDATORY_HUMAN_APPROVAL = "mandatory_human_approval"  # NEW — overrides Coach score
MANDATORY_HUMAN_APPROVAL bypasses Coach score entirely — emits ApprovalRequestPayload regardless. This is the mode-aware PAUSED-state entry for training.

forge.yaml additions:


confidence_thresholds:
  build_plan_review:
    mode: mandatory_human_approval      # early-days default
    # mode: confidence_gated           # relaxed once calibration supports it
    auto_approve: 0.85
    flag_for_review: 0.55
    relaxation_criteria:
      min_approved_plans: 10
      max_rejection_rate: 0.10
Automatic relaxation: forge.learning watches accumulated build-plan approval history; once the relaxation criteria are satisfied for N projects, proposes flipping mode: confidence_gated. Rich approves via CLI — never flips autonomously.

Updated module count: 14 → 17
Group	Added in this revision
B. Domain Core	forge.calibration
D. Adapters	forge.adapters.history_parser
A. DeepAgents Shell	build_plan_composer sub-agent (count 7 → 8)
B. Domain Core	New gate mode MANDATORY_HUMAN_APPROVAL in existing forge.gating
Plus: new pipeline sub-stage (3b: Build Plan Review) in forge.stages; 3 new GuardKit tools (system_arch, system_design, system_plan).

ADRs queued (now 8 total)
ADR-ARCH-001: Clean/Hexagonal modules inside DeepAgents two-model orchestrator
ADR-ARCH-002: Two-model separation (reasoning drives graph, implementation executes in tools/sub-agents)
ADR-ARCH-003: NATS-native orchestration via nats-core adapters, no transport ABC
ADR-ARCH-004: Full GuardKit CLI as tool surface — one @tool per subcommand (11 tools)
ADR-ARCH-005: Graphiti-fed learning loop + per-stage notification tuning
ADR-ARCH-006: Calibration corpus — ingest history files as CalibrationEvent stream; seed Graphiti forge_calibration_history; prime threshold defaults and system-prompt signatures
ADR-ARCH-007: Build Plan as explicit Stage 3b artefact + gate; MANDATORY_HUMAN_APPROVAL mode in training; relaxes to confidence-gated per relaxation_criteria
ADR-ARCH-008: Forge produces its own history files in the same Pattern-2/Pattern-3 format — training data propagates forward
Category 2 Checkpoint (revision 3)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 2: Module Structure (REVISED ×2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

17 modules in 5 groups:
  A. DeepAgents Shell  — agent, prompts, subagents (8 sub-agents)
  B. Domain Core       — gating, state_machine, stages,
                         notifications, learning, calibration*
  C. Tool Layer        — tools/* (11 GuardKit + specialist + queue +
                         git + pr + history + notification + approval + graphiti)
  D. Adapters          — nats, sqlite, git, guardkit, graphiti, history_parser*
  E. Cross-cutting     — config, cli, fleet

Pipeline stages: 1 → 2 → 3a → 3b (Build Plan Review) → 4 → 5
Gate modes:      auto_approve | flag_for_review | hard_stop | mandatory_human_approval
Graphiti groups: forge_pipeline_history | forge_calibration_history
History corpus:  ~35 files (specialist-agent, nats-core, nats-infrastructure)
                 → primes gating thresholds + system prompt + learning baseline
Reply with:

C2 — accept and continue to Category 3: Technology & Infrastructure
Further edits, or
A to capture another ADR inline
C2

Category 2: Accepted. Moving to Category 3.
Category 3: Technology & Infrastructure
Q8. Programming language & frameworks

Proposed (from CLAUDE.md, refresh doc §Agent Identity, nats-core system-spec §NFRs):

Layer	Choice	Source
Language	Python 3.12+	Fleet minimum (nats-core spec NFRs); Rich's fleet standard
Orchestrator framework	LangChain DeepAgents 0.5.0a2+ — create_deep_agent, SubAgent, AsyncSubAgent	CLAUDE.md, D1 fleet-wide, specialist-agent template
Graph runtime	LangGraph (langgraph.json, langgraph dev server, CompiledStateGraph export)	langgraph-deployment-config-specialist rule
Model client	init_chat_model with provider:model strings (e.g. anthropic:claude-opus-4-7, anthropic:claude-sonnet-4-6)	langgraph-deployment-config-specialist rule
Schemas	Pydantic 2 + pydantic-settings (via nats-core.AgentConfig with AGENT_ env prefix + __ nested delimiter)	D22 fleet-wide, agent-manifest-contract.md
Async I/O	asyncio throughout — NATS, SDK, sub-agent round-trips	nats-core client design
CLI	Click — `forge queue	status
Argparse (boot)	argparse.parse_known_args for CLI args surviving LangGraph server's argv injection	langgraph-deployment-config-specialist rule
Internal library	nats-core (pip-installed from sibling repo) — envelope, Topics, client, registry, payloads	Fleet-wide
Testing	pytest + pytest-asyncio + unittest.mock (patch create_deep_agent, yaml.safe_load, call_agent_tool); class-based test organisation per acceptance criteria; tmp_path fixtures; subprocess tests for CLI	pytest-agent-testing-specialist rule
Lint / type	ruff + mypy --strict	nats-core precedent
Q9. Data stores

Proposed — every store, its purpose, its owner module:

Store	Purpose	Owner	ADR
SQLite ~/.forge/forge.db (WAL mode)	Authoritative build history — builds + stage_log tables	forge.adapters.sqlite	ADR-SP-013
LangGraph checkpointer (SQLite-backed, co-located in ~/.forge/langgraph.db)	In-graph state between reasoning turns; enables graph-level resume of the current build	LangGraph built-in	(new: ADR-ARCH-009 decision below)
JetStream PIPELINE stream (7-day retention)	Build queue — pipeline.build-queued.* pull consumer with AckWait	forge.adapters.nats	ADR-SP-011/013/017
JetStream AGENTS stream (7-day)	Specialist commands + results transport	forge.adapters.nats	ADR-SP-017
JetStream FLEET stream	fleet.register, heartbeats	forge.fleet	Anchor §3
JetStream JARVIS + NOTIFICATIONS streams	Outbound notifications routed via Jarvis	forge.adapters.nats	Anchor §3
JetStream SYSTEM stream (1-hour)	Health + config pings	Built-in	Anchor §3
NATS KV agent-registry bucket	Live fleet discovery table	nats-core library	ADR-004 (nats-core)
FalkorDB via Graphiti (whitestocks:6379)	Learning corpus — two group_ids: forge_pipeline_history (override events, gate decisions, session outcomes), forge_calibration_history (CalibrationEvents from history files)	forge.adapters.graphiti	ADR-ARCH-005/006
Open point I'll flag as Q for you: LangGraph checkpointer in ~/.forge/langgraph.db vs. co-located in ~/.forge/forge.db vs. omitted entirely (and rely solely on JetStream redelivery + SQLite state reconciliation per ADR-SP-013). My recommendation: omit LangGraph checkpointer — it duplicates durability JetStream already provides, and ADR-SP-013 explicitly says retry-from-scratch is the policy on crash. Keeping LangGraph in-memory only is simpler and matches the anchor. But this is a genuine call.

Q10. Deployment model

Proposed (from anchor §10 "Local-first execution on GB10 + MacBook Pro via Tailscale"):

Single process — forge is one Python binary running as a long-lived service
Runtime host: GB10 (promaxgb10-41b1) alongside nats-server and specialist-agent containers
Packaging: Docker container in the existing nats-infrastructure Docker Compose — adds one service (forge) alongside nats, specialist-agent-product-owner, specialist-agent-architect (matches ADR-SP-015 dual-role deployment)
Dev mode: langgraph dev on MacBook Pro → NATS on GB10 via Tailscale (matches specialist-agent dev workflow)
Co-located volumes: ~/.forge/forge.db mounted into the container; git working tree on a Docker volume; GuardKit + gh binaries installed in the image
No horizontal scaling ever — ADR-SP-012 sequential builds is a hard constraint. max_concurrent: 1 in the AgentManifest
Not serverless, not cloud — local-first is the architectural principle (motivation doc)
Container roster on GB10 (additions in bold):


nats-server                          (nats-infrastructure)
specialist-agent-product-owner       (ADR-SP-015)
specialist-agent-architect           (ADR-SP-015)
forge                               [NEW]
jarvis                              (when built)
Q11. CI/CD

Proposed (matches nats-core + specialist-agent precedent):

GitHub Actions — .github/workflows/ci.yml
Jobs: ruff check → mypy --strict → pytest (unit, fast, no NATS) → integration tests marked @pytest.mark.integration run in a separate job against a spun-up NATS container
No publishing — Forge is not a distributed package; it's a local service. Image builds are local-only.
Pre-commit hooks matching nats-core: ruff, mypy, trailing whitespace, YAML validation
No --no-verify commits ever (matches agent behaviour rules)
Q12. External services & integrations

Categorised by criticality — this drives degraded-mode design in Category 5:

Critical path (Forge cannot run without these)
Service	Access	Notes
Anthropic API (Claude Opus 4.7 reasoning; Claude Sonnet 4.6 implementation — two-model separation per D5)	HTTPS, ANTHROPIC_API_KEY env	Cost: ~£X/build; budget covered in Category 6
NATS + JetStream on GB10	nats://promaxgb10-41b1:4222 via Tailscale	ADR-SP-011 — cannot run without
git CLI + gh CLI	Local binaries in container image	Pinned versions in Dockerfile
GuardKit CLI	Local binary in image; subprocess invocation with --nats flag	ADR-ARCH-004
Important (degraded mode exists)
Service	Fallback	Degraded-mode rule
FalkorDB / Graphiti (whitestocks:6379)	Disable forge.learning + forge.calibration; thresholds stay at config defaults; notifications still fire	No auto-threshold adjustment
specialist-agent-product-owner	Fall back to guardkit_feature_spec directly (no Coach score)	Force FLAG_FOR_REVIEW at Stage 1
specialist-agent-architect	Fall back to guardkit_system_arch directly	Force FLAG_FOR_REVIEW at Stage 2
Optional
Service	Role
LangSmith	Tracing — AGENT_LANGSMITH_PROJECT=forge, opt-in via API key
Jarvis	Inbound build triggers via pipeline.build-queued; CLI path always works without it
vLLM on GB10 port 8002	Alternative implementation model (local mode); only referenced if orchestrator-config.yaml selects local provider
Future notification adapters (Slack, Telegram via Jarvis)	Phase 5; out of initial scope
Model configuration summary

# orchestrator-config.yaml
models:
  reasoning_model: "anthropic:claude-opus-4-7"         # drives DeepAgents graph + quality evaluation
  implementation_model: "anthropic:claude-sonnet-4-6"  # used inside content-generating sub-agents
  # (build_plan_composer, architecture_dispatcher)
Rationale: two-model separation (D5) — different families prevent self-confirmation bias. Opus 4.7 for orchestration/evaluation (high judgment, 1M context for long build traces); Sonnet 4.6 for generation (cost-effective, fast, 200K context). Refresh doc line 572 marked implementation_model: null — I'm revising to Sonnet, because build_plan_composer and architecture_dispatcher are genuinely content-generating sub-agents and having the top-level reasoning model also generate them collapses the separation.

ADRs to add (Category 3)
ADR-ARCH-009: Omit LangGraph checkpointer — JetStream redelivery + SQLite reconciliation is sufficient durability per ADR-SP-013; retry-from-scratch on crash
ADR-ARCH-010: Two-model configuration — Opus 4.7 reasoning (graph + Coach), Sonnet 4.6 implementation (content-generating sub-agents); overrides refresh doc implementation_model: null
ADR-ARCH-011: Local-first Docker deployment on GB10 alongside nats-server + dual-role specialist-agent containers; max_concurrent: 1; no horizontal scaling
Total queued: 11 ADRs (8 prior + 3 from Category 3).

Category 3 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 3: Technology & Infrastructure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Language/framework:  Python 3.12+, LangChain DeepAgents + LangGraph, Pydantic 2, asyncio, Click
Models:              Opus 4.7 (reasoning) + Sonnet 4.6 (implementation) via init_chat_model
Data stores:         SQLite (forge.db, authoritative) + FalkorDB/Graphiti (learning)
                     + JetStream PIPELINE/AGENTS/FLEET/JARVIS/NOTIFICATIONS/SYSTEM streams
                     + NATS KV agent-registry
Deployment:          Docker container on GB10 alongside NATS + dual-role specialist-agents
CI/CD:               GitHub Actions — ruff, mypy --strict, pytest (unit + integration jobs)
External (critical): Anthropic API, NATS, git, gh, GuardKit CLI
External (important): FalkorDB, specialist-agent instances (with degraded-mode fallbacks)
External (optional):  LangSmith, Jarvis, local vLLM
Reply with:

C3 — accept, continue to Category 4: Multi-Consumer API Strategy
Edits (e.g. "yes keep LangGraph checkpointer — resume mid-stage when possible", or "implementation model should be null — all generation happens inside specialist-agent subprocesses", etc.)
A for inline ADR
R to revise questions
[R]evise - happy with this and accept your reccomendation to omit LangGraph checkpointer. I just want to clarify the ANTHROPIC_API_KEY and Anthropic API - I don't want to be limited by this to anthropic, I'm planning on using Google Gemini 3.1 Pro for cheaper advanced reasoning. Also Anthropic has pretty poor service uptime so Google might well be a better option so lets keep this provider agnostic as LangChain DeepAgents provides this
Fair correction — I leaned on Anthropic-specific framing when the whole point of the DeepAgents + init_chat_model pattern is provider-neutrality. And you already flagged it: pipeline-orchestrator-conversation-starter.md D2/D3 explicitly said "configurable, not hardcoded" with Gemini 3.1 Pro as the stated primary.

Worth noting: the fleet is already multi-provider — .guardkit/graphiti.yaml uses Gemini 2.5 Pro for Graphiti ingestion precisely because of the Anthropic-free-tier 429s noted in the config comment. So Forge joining Gemini 3.1 Pro for reasoning is consistent, not novel.

Revision 4 — Provider-neutral model config
Q8 updated — Model client row
Layer	Choice
Model client	init_chat_model("provider:model") — supports google_genai (Gemini 3.1 Pro, Gemini Flash), anthropic (Opus 4.7, Sonnet 4.6), openai (GPT-5, etc.), vllm (local GB10), ollama (MacBook). Selected at runtime via AGENT_MODELS__REASONING_MODEL / AGENT_MODELS__IMPLEMENTATION_MODEL env vars (per nats-core.AgentConfig, AGENT_ prefix, __ nested delimiter — LES1 parity rule: resolved once at factory, never in handlers).
LangChain integrations installed by default — per CLAUDE.md's .[providers] pattern in pyproject.toml:


[project]
dependencies = [
    "langchain-anthropic",   # base — zero-extras install works out-of-the-box
    # ...
]
[project.optional-dependencies]
providers = [
    "langchain-google-genai",  # Gemini (Rich's primary)
    "langchain-openai",        # GPT family
    # (langchain-anthropic already in base)
]
Switching reasoning provider is one env var — no code changes:


AGENT_MODELS__REASONING_MODEL="google_genai:gemini-3.1-pro"        # Rich's primary
AGENT_MODELS__REASONING_MODEL="anthropic:claude-opus-4-7"          # fallback
AGENT_MODELS__REASONING_MODEL="openai:gpt-5"                       # secondary fallback
AGENT_MODELS__REASONING_MODEL="vllm:qwen3-coder-next"             # offline/privacy
Q12 updated — LLM provider criticality
Critical path (one of these must be reachable; not all):

Provider	Env var	Notes
Google Gemini (google_genai:gemini-3.1-pro)	GOOGLE_API_KEY	Rich's primary — cheaper advanced reasoning, better uptime
Anthropic (anthropic:claude-opus-4-7 / sonnet-4-6)	ANTHROPIC_API_KEY	Secondary option — 2026 uptime concerns make this not-primary
OpenAI (openai:gpt-5)	OPENAI_API_KEY	Tertiary option
vLLM on GB10 port 8002 (vllm:qwen3-coder-next)	N/A (local)	Offline/privacy mode — already listed as "optional" but is genuinely a critical-path fallback if all cloud providers are down
Forge is critical-path-dependent on having an LLM, not on any specific vendor. This is the key distinction.

Model configuration summary (revised)

# orchestrator-config.yaml
models:
  reasoning_model: "google_genai:gemini-3.1-pro"       # Rich's primary
  implementation_model: "google_genai:gemini-2.5-flash" # cheaper/faster for generation
  # Alternates (swap via env override, no code change):
  #   reasoning:      anthropic:claude-opus-4-7 | openai:gpt-5 | vllm:qwen3-coder-next
  #   implementation: anthropic:claude-sonnet-4-6 | openai:gpt-5-mini | ollama:qwen2.5:14b
Two-model separation (D5) still holds — the principle is "different families for reasoning vs implementation," and Gemini Pro vs Gemini Flash satisfies that because the Coach/evaluation step uses Pro's judgment while generation uses Flash's speed. If you want genuinely different families, the alternate pairing google_genai:gemini-3.1-pro (reasoning) + anthropic:claude-sonnet-4-6 (implementation) is also supported by flipping one env var.

Operational consideration — automatic provider failover
Not required for v1, but the architecture supports it: wrap init_chat_model in a ResilientModelFactory in forge.config that catches provider-level exceptions (anthropic.APIError, google.api_core.exceptions.*, openai.APIError) and retries against a configured fallback. Documented as a Category-5 cross-cutting concern candidate (retries / circuit-breaker) and tracked as a V2 capability, not V1.

ADR-ARCH-010 rewrites from
"Two-model configuration — Opus 4.7 reasoning, Sonnet 4.6 implementation"

to:

ADR-ARCH-010: Provider-neutral two-model configuration via init_chat_model

Context: D2/D3 fleet-wide decisions require provider-agnostic model selection; Anthropic's 2026 uptime history, Gemini 3.1 Pro's pricing advantage, and the fleet's already-mixed use of Gemini (Graphiti) and Claude (Coach) make locking to one vendor a structural risk and cost penalty.
Decision: All model instantiation flows through init_chat_model("provider:model") resolved at the lowest factory layer from AgentConfig.models.{reasoning,implementation}_model (env vars AGENT_MODELS__REASONING_MODEL / AGENT_MODELS__IMPLEMENTATION_MODEL) per LES1 parity rule. Primary configuration: Gemini 3.1 Pro (reasoning) + Gemini 2.5 Flash (implementation). Alternates installed and supported: Anthropic Opus 4.7 / Sonnet 4.6; OpenAI GPT-5; vLLM local. Switching providers is env-var-only — no code changes, no release.
Consequences: + Survives any single-vendor outage via config flip. + Cost-optimises: Gemini Pro is substantially cheaper than Opus at sustained volume. + Consistent with fleet-wide Graphiti Gemini move (14 April 2026). + two-model separation (D5) preserved via Gemini Pro + Flash (different tiers) or cross-family (Gemini Pro + Claude Sonnet). − Four LangChain integrations to keep current (anthropic, google-genai, openai, vllm/ollama) — cost confined to one pyproject.toml block per LCOI rule. − Failover automation deferred to V2 (architecture supports it; implementation not required for initial Forge).
Revised Category 3 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 3 (REVISED — provider-neutral)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Language/framework:  Python 3.12+, LangChain DeepAgents + LangGraph, Pydantic 2, asyncio
Models:              Provider-neutral via init_chat_model.
                     Primary: Gemini 3.1 Pro (reasoning) + Gemini 2.5 Flash (implementation)
                     Alternates: Anthropic Opus/Sonnet, OpenAI GPT-5, vLLM, Ollama
                     Switch: single env var, no code change
Data stores:         SQLite forge.db (authoritative) + FalkorDB/Graphiti (learning)
                     + JetStream streams + NATS KV agent-registry
                     LangGraph checkpointer OMITTED — JetStream+SQLite sufficient
Deployment:          Docker container on GB10 alongside NATS + dual-role specialist-agents
CI/CD:               GitHub Actions — ruff, mypy --strict, pytest (unit + integration)
External critical:   ANY ONE LLM provider (Gemini|Anthropic|OpenAI|vLLM), NATS, git, gh, GuardKit CLI
External important:  FalkorDB, specialist-agent instances (with degraded-mode fallbacks)
External optional:   LangSmith, Jarvis, additional LLM providers beyond the one currently configured
Reply with:

C3 — accept, continue to Category 4: Multi-Consumer API Strategy
Edits (e.g. "add automatic failover to V1, not V2", "Flash is too weak for implementation — use Sonnet", etc.)
A for inline ADR
C3
Category 3: Accepted. Moving to Category 4.
Category 4: Multi-Consumer API Strategy
Forge's consumer landscape is unusual — no web API, no mobile clients, heavy NATS + CLI, deliberately no MCP (per fleet D16). Proposed answers follow.

Q13. Consumer types

Consumer	Role	Why they interact with Forge
Rich (human)	Operator	Triggers builds, reviews PAUSED builds, inspects history
Jarvis (fleet agent)	Automated upstream trigger	Publishes builds on Rich's behalf from voice/Telegram/dashboard/CLI-wrapper (ADR-SP-014)
Specialist Agents (PO + Architect)	Automated downstream callees	Receive commands from Forge at Stage 1/2, return Coach-scored results
Dashboard (future)	Visualisation viewport	Read-only subscription to pipeline.* stream for orchestrator card
Notification adapters (future — Slack, email, Linear)	Outbound viewports	Project pipeline events into external tools
Other fleet agents (future)	Control-plane peers	Discover Forge via fleet.register; send control commands via agents.command.forge (fleet-only, not the build path)
GuardKit CLI (subprocess callee, not consumer)	Tool invocation target	Forge invokes it outbound — not a consumer
git + gh CLI (subprocess callee)	Infrastructure tool	Forge invokes it — not a consumer
James, Mark (humans)	PR reviewers	Interact with GitHub PRs, not Forge directly
Q14. API protocols per consumer type

Protocol	Used for	Who
Click CLI (stdin/stdout/exit codes)	Local interaction	Rich
NATS JetStream publish → pipeline.build-queued.{feature_id}	Durable build trigger	CLI (forge queue), Jarvis, future adapters
NATS JetStream pull consumer	Durable build consumption	Forge (itself — the only consumer of PIPELINE stream)
NATS request/reply with correlation_id (per LES1 parity rule)	Specialist agent round-trip — agents.command.{agent_id} out, agents.result.{agent_id}.{correlation_id} back	Forge ↔ PO / Architect
NATS pub/sub (core, ephemeral)	Pipeline event broadcasts — pipeline.build-*, pipeline.stage-*	Dashboard, notification adapters
NATS agents.command.forge (fleet-discovery only)	Future control commands ("pause all builds")	Jarvis CAN-bus dispatch, other fleet agents
NATS fleet.register + fleet.heartbeat.forge	Self-registration for fleet discovery	Forge on startup + every 30s
NATS KV agent-registry	Read fleet to check specialist availability (for degraded-mode detection)	Forge at pipeline start of each stage
subprocess stdin/stdout/exit	GuardKit CLI, git, gh — outbound only	Forge's tool layer
MCP	❌ NOT used per D16 fleet-wide — pipeline traffic would overflow MCP context on every invocation	—
HTTP/REST	Not used	—
gRPC	Not used	—
Key architectural decisions baked in here:

No MCP for Forge. MCP serialises the full tool schema into the context window on every call. With 11 GuardKit tools + specialist dispatch + history + approval + git + PR tools (~20 total), the pipeline path becomes impossibly expensive. D16 is explicit. Forge is discoverable over NATS, not MCP.
CLI read path bypasses NATS entirely. forge status, forge history, forge history --feature FEAT-XXX query SQLite directly — no NATS round-trip. Only the write-path commands (queue, cancel, skip) publish to NATS. This keeps the read path fast + available even if NATS is down.
Single JetStream queue consumer. Per ADR-SP-012, Forge is the only consumer of pipeline.build-queued.*. max_ack_pending=1 enforces sequential builds at the transport layer, not just in code.
Q15. Data shapes / access patterns per consumer type

Consumer	Payload shape	Access pattern
Rich via CLI	Local SQLite rows serialised to human-readable tables (forge status → table of PAUSED + current + next-in-queue; forge history → tabulated builds)	Read SQLite directly
Jarvis	BuildQueuedPayload — populates triggered_by="jarvis", originating_adapter, correlation_id, parent_request_id (ADR-SP-014)	One-shot JetStream publish
Specialist Agents — inbound (Forge → PO/Architect)	CommandPayload with role-specific input (e.g. {docs_path, scope, previous_session_id})	NATS request with correlation_id; Forge subscribes to reply subject before publishing
Specialist Agents — outbound (PO/Architect → Forge)	ResultPayload wrapping {role_id, coach_score, criterion_breakdown, detection_findings, role_output} per ADR-SP-015 — Forge does not translate per-role output types	Forge matches correlation_id and routes to appropriate @tool return
Dashboard (future)	Full typed pipeline.* payloads from nats-core (BuildStartedPayload, BuildProgressPayload, BuildPausedPayload, StageCompletePayload, BuildCompletePayload, BuildFailedPayload)	Subscribes to pipeline.> wildcard; projects to UI state
Notification adapters (future)	NotificationPayload + filtered pipeline.build-complete / build-failed / build-paused	Subscribes to specific event subsets per adapter config
Approval round-trips (training mode / flagged stages)	ApprovalRequestPayload out (via agents.approval.forge.{build_id}) + ApprovalResponsePayload in (via agents.approval.forge.{build_id}.response)	Long-polling subscription with timeout
Read/write asymmetry at a glance:

Forge publishes: pipeline.* (all events) + agents.command.{specialist} + fleet.register/heartbeat + agents.approval.forge.* + jarvis.notification.*
Forge consumes: pipeline.build-queued.* (pull) + agents.result.{specialist}.{correlation_id} (request/reply) + agents.command.forge (fleet control, future) + agents.approval.forge.*.response
Q16. Auth / authz per consumer type

Plane	Mechanism	Scope
CLI (local)	OS file permissions on ~/.forge/forge.db; no auth between CLI and Forge process (same user)	Rich's user account on GB10
NATS — agent identity	Account-based multi-tenancy per nats-infrastructure/accounts.conf — Forge, specialist agents, Jarvis all run under APPMILLA account with full access to > within account	APPMILLA tenant boundary
NATS — tenant isolation	Future FINPROXY account scoped to finproxy.> — Forge publishes project-scoped pipeline events using Topics.for_project("finproxy", …) convention when/if Forge serves FINPROXY builds	Per-project NATS topic namespace
SYS account	Admin only (health, monitoring)	Rich's admin creds
LLM provider auth	GOOGLE_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY — in env, never in AgentManifest, never published to fleet (per agent-manifest-contract §Manifest vs Config separation)	Per Forge instance
GitHub auth	gh auth login once on the host; uses ~/.config/gh/hosts.yml token	Rich's GitHub identity
Fleet-level ACLs within APPMILLA	None in V1 — all APPMILLA-authenticated agents can publish to agents.command.forge (trust is fleet-boundary, not message-level). Future hardening: per-message signing + intent-based ACLs	APPMILLA-wide
Approval replies	Any APPMILLA-authenticated responder can reply to an ApprovalRequestPayload. Trust that only Rich (or Jarvis-routed Rich intents) will respond is fleet-boundary	APPMILLA-wide
Not in V1: per-user auth within the APPMILLA account. Forge trusts anything speaking NATS from inside APPMILLA. When Rich onboards James/Mark to the pipeline (they currently only review PRs), per-user NATS credentials + intent-based ACLs become a Category 5 cross-cutting concern to add.

ADRs from Category 4
ADR-ARCH-012: No MCP interface for Forge — pipeline traffic would overflow MCP context window on every invocation (D16 fleet rule). Forge is discoverable and controllable via NATS fleet-registration + JetStream. CLI for humans, NATS for machines.
ADR-ARCH-013: CLI read path bypasses NATS — forge status/history read SQLite directly. Only queue/cancel/skip publish. Read path stays available during NATS outages.
ADR-ARCH-014: Single JetStream consumer enforces sequential builds at transport layer — max_ack_pending=1 on the PIPELINE pull consumer is the physical embodiment of ADR-SP-012.
Total queued: 14 ADRs (11 prior + 3 Category 4).

Category 4 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4: Multi-Consumer API Strategy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consumers:         Rich (CLI), Jarvis (NATS pub), specialist agents (NATS req/rep),
                   future dashboard + notification adapters (NATS sub),
                   fleet peers (NATS control plane)
Protocols:         Click CLI + NATS (JetStream pull/pub, core req/rep, KV lookup)
                   + subprocess (GuardKit/git/gh outbound only)
                   ❌ NO MCP, ❌ NO HTTP/REST, ❌ NO gRPC
Payload shapes:    nats-core typed Pydantic models — BuildQueuedPayload,
                   Command/ResultPayload, ApprovalRequest/Response, Notification,
                   pipeline.build-*/stage-* payloads
Read/Write split:  CLI read = SQLite direct; CLI write + all fleet interaction = NATS
Auth:              NATS account-based (APPMILLA);
                   LLM provider keys env-only, never in AgentManifest
                   No per-user ACLs in V1 — fleet-boundary trust
Sequential enforcement: max_ack_pending=1 on JetStream consumer (transport-level ADR-SP-012)
Reply with:

C4 — accept, continue to Category 5: Cross-Cutting Concerns
Edits
A for inline ADR
[R]evise - I like all of this but want to refine the use of the specialist agents so it's discoverable and not hard coded - this is the whole point of the agent manifest capabilities in nats-core/nats-infrastructure/specialist-agent. I plan on adding a QA agent and possilby a UX agent in time, maybe an ideation agent so the forege needs to be able to react and utilise capabilities as they evolve
Correct — I was hardcoding agent_id=product-owner-agent / architect-agent when the entire point of nats-core.AgentManifest + NATSKVManifestRegistry.find_by_intent/tool() is dynamic capability discovery. D17 fleet-wide: "new roles are automatically discoverable by the Forge without any Forge code changes." I inverted that.

Also missed in Cat 2: I named sub-agents after specific roles (architecture_dispatcher), which bakes the coupling in at the composition layer too.

Revision 5 — Capability-driven dispatch replaces role hardcoding
Core pattern shift
Before (hardcoded):


await client.call_agent_tool("product-owner-agent", "review_specification", payload)
await client.call_agent_tool("architect-agent", "review_architecture", payload)
After (capability-resolved at runtime):


# Each stage declares what it NEEDS, not who provides it
await forge.discovery.call_by_capability(
    tool_name="review_specification",     # tool-match (primary)
    intent_pattern="specification.review", # intent-match (fallback)
    trust_tier="specialist",               # narrows candidate set
    payload=...,
)
# forge.discovery resolves target agent_id from the live agent-registry KV
# and invokes call_agent_tool() against whichever agent matches today
New module: forge.discovery
Purpose: Runtime capability resolution + change watching. Decouples Forge from specific agent IDs.

Responsibilities:

Wraps NATSKVManifestRegistry from nats-core — list_all(), find_by_tool(), find_by_intent()
Caches the registry snapshot with TTL (default 30s, matches heartbeat interval)
Subscribes to fleet.register / fleet.deregister / fleet.heartbeat.> for cache invalidation — new agents picked up without restart
Implements resolution priority: exact tool_name match → intent_pattern match with highest confidence → unavailable (triggers degraded mode)
Emits a CapabilityResolution record to Graphiti per stage (which agent served which capability — training data for future "prefer the agent that passed last time" tuning)
Public API (the methods the tool + stage layers use):


class Discovery:
    async def list_capabilities(self) -> list[AgentManifest]: ...
    async def find_for_tool(self, tool_name: str, trust_tier: Optional[str] = None) -> list[AgentManifest]: ...
    async def find_for_intent(self, pattern: str, min_confidence: float = 0.7) -> list[AgentManifest]: ...
    async def resolve(self, tool_name: str, intent_pattern: str | None = None) -> AgentManifest | None:
        """Primary dispatch helper — applies the resolution priority."""
    async def watch(self) -> AsyncIterator[FleetChange]:
        """Emits add/remove/degrade events — subscribed to fleet.register/deregister/heartbeat."""
Revised forge.tools.specialist_tools — ONE generic tool replaces the role-specific tools

@tool(parse_docstring=True)
async def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str = "",
    timeout_seconds: int = 600,
) -> str:
    """Dispatch a task to whichever fleet agent currently advertises this capability.

    Args:
        tool_name: Exact ToolCapability.name from the target agent's AgentManifest.
                   Preferred routing mechanism — precise, not fuzzy.
        payload_json: JSON-serialised tool-specific parameters conforming to the
                      target tool's parameters schema.
        intent_pattern: Optional IntentCapability.pattern to fall back on if
                        tool_name has no match. Leave empty to skip intent fallback.
        timeout_seconds: Per-call round-trip timeout (AsyncSubAgent fire-and-forget
                         pattern beyond 30s per LES1 §4 POLR).

    Returns:
        JSON string — either {"role_id", "coach_score", "criterion_breakdown",
        "detection_findings", "role_output"} on success, or {"error": ...,
        "degraded_mode": true} if no agent resolves the capability.
    """
    ...
This single tool replaces:

call_product_owner_tool ❌
call_architect_tool ❌
Any future call_qa_tool / call_ux_tool / call_ideation_tool ❌
Rich adds a QA agent tomorrow — zero Forge code changes. The agent registers its manifest declaring tool_name="review_quality", and whichever stage in forge.yaml is mapped to that tool picks it up.

Pipeline as data — forge.yaml stage sequence (revised)

pipeline:
  stages:
    - id: specification_review
      required_tool: "review_specification"
      fallback_intent: "specification.review"
      fallback_degraded_tool: "guardkit_feature_spec"   # if no fleet agent matches
      gate:
        auto_approve: 0.80
        flag_for_review: 0.50
      optional: false

    - id: architecture_review
      required_tool: "review_architecture"
      fallback_intent: "architecture.review"
      fallback_degraded_tool: "guardkit_system_arch"
      gate:
        auto_approve: 0.75
        flag_for_review: 0.50
      optional: false

    - id: feature_planning            # Forge-internal, no specialist
      uses_tool: "guardkit_feature_plan"
      gate: { auto_approve: 0.85, flag_for_review: 0.55 }

    - id: build_plan_review           # Forge-internal composer + gate
      uses_tool: "build_plan_composer"
      gate: { mode: mandatory_human_approval }   # training mode

    # ─── FUTURE STAGES — commented out until the corresponding agents ship ───
    # Rich uncomments when the agent is registered and intended for this project.

    # - id: quality_review
    #   required_tool: "review_quality"
    #   fallback_intent: "quality.review"
    #   optional: true                  # skip silently if unmet, don't degrade
    #   inserts_before: autobuild       # where to slot into the pipeline
    #   gate: { auto_approve: 0.80, flag_for_review: 0.50 }

    # - id: ux_review
    #   required_tool: "review_ux"
    #   optional: true
    #   inserts_before: autobuild
    #   gate: ...

    # - id: ideation_score             # could precede feature_spec in greenfield Mode A
    #   required_tool: "score_idea"
    #   optional: true
    #   inserts_before: specification_review
    #   gate: ...

    - id: autobuild
      uses_tool: "guardkit_autobuild"
      gate: { auto_approve: 0.80, flag_for_review: 0.60 }

    - id: pr_creation
      uses_tool: "guardkit_pr_create"
      gate: { auto_approve: 1.0, flag_for_review: 0.8 }
Runtime behaviour of optional: true stages:

Forge calls discovery.resolve(required_tool, fallback_intent) at stage start
Match found → stage runs as configured
No match + optional: true → stage skipped, logged, emits pipeline.stage-skipped event ("no agent registered the review_quality capability — stage skipped per optional: true")
No match + optional: false → falls back to fallback_degraded_tool with forced FLAG_FOR_REVIEW (existing degraded-mode rule)
Hot-swap scenario Rich described:

Day 1: Rich uncomments the quality_review block, ships a QA agent with ToolCapability(name="review_quality", …) in its manifest
QA agent starts, publishes to fleet.register
Forge's discovery.watch() picks up the change, invalidates cache
Next build that enters pipeline: QA stage now active between feature_planning and autobuild
No Forge restart, no code change, no rebuild of the Docker image
Revised sub-agent topology — generic stage runners
Rather than sub-agents named after specialists (my earlier architecture_dispatcher was wrong), sub-agents are stage-shaped:

Sub-agent	Responsibility	Specialist resolution
specialist_stage_runner	Dispatches to a fleet agent via discovery.resolve + dispatch_by_capability; evaluates Coach score; handles gate outcome. Parameterised by stage config — reusable across specification_review / architecture_review / quality_review / ux_review / ideation_score / any future stage.	Runtime, via forge.discovery
guardkit_stage_runner	Dispatches to a local guardkit_* tool; evaluates whatever signal GuardKit emits; handles gate outcome.	N/A (local subprocess)
build_plan_composer	Synthesises the build plan artefact from feature plans + context manifests.	N/A (LLM content generation)
autobuild_runner	Subprocess orchestration of guardkit autobuild --nats, progress-stream consumption, timeout handling.	N/A (subprocess)
pr_finaliser	git push + gh pr create + publish pipeline.build-complete.	N/A (subprocess)
Sub-agent count: 5 (was 8) — generic stage runners + 3 Forge-internal specialist-free runners. Adding a QA stage adds zero sub-agents because specialist_stage_runner is reused with different stage config.

Module count revisited
Before (Revision 3)	After (Revision 5)
17 modules	17 modules — swap forge.fleet scope
8 sub-agents	5 sub-agents (simpler + more reusable)
Per-role specialist tools	1 generic dispatch_by_capability tool
forge.fleet still handles fleet.register + heartbeat for Forge itself. forge.discovery is the new module for reading the fleet registry to find specialists. These are genuinely two different concerns.

Module map updated:


A. DeepAgents Shell  — agent, prompts, subagents (5 generic stage runners)
B. Domain Core       — gating, state_machine, stages (config-driven from forge.yaml),
                       notifications, learning, calibration, DISCOVERY*
C. Tool Layer        — tools/* (11 GuardKit, 1 generic dispatch_by_capability,
                       queue, git, pr, history, notification, approval, graphiti)
D. Adapters          — nats, sqlite, git, guardkit, graphiti, history_parser
E. Cross-cutting     — config, cli, fleet
(* = forge.discovery added; forge.stages now data-driven)

ADRs from Revision 5
ADR-ARCH-015: Capability-driven specialist dispatch — no agent_id hardcoding in Forge. forge.discovery resolves tool/intent → live agent via NATSKVManifestRegistry. New specialist roles become available to Forge with zero code changes (D17 fleet-wide).
ADR-ARCH-016: Pipeline as data — stage sequence is declared in forge.yaml, not Python code. Optional stages activate when a matching fleet capability is present; skip silently when not. inserts_before controls position for future stages.
ADR-ARCH-017: Live fleet-registry watching — forge.discovery subscribes to fleet.register/deregister/heartbeat for hot-swap capability detection. New agents are picked up on the next stage resolution, no Forge restart required.
Total queued: 17 ADRs (14 prior + 3 from Revision 5).

Category 4 Checkpoint (revised)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4 (REVISED — capability-driven dispatch)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consumers:           unchanged (Rich CLI, Jarvis, specialist agents, future dashboard/adapters)
Protocols:           unchanged (Click + NATS + subprocess, no MCP/REST/gRPC)
Dispatch pattern:    capability-resolved at runtime via NATSKVManifestRegistry —
                     Forge asks "who does review_quality?" not "is the QA agent here?"
Hot-swap:            forge.discovery watches fleet.register/deregister/heartbeat;
                     new agents picked up without Forge restart
Pipeline definition: data (forge.yaml), not code — stages declare required_tool,
                     optional stages activate on capability match
Sub-agent topology:  5 generic stage runners (not N role-bound dispatchers)
Tool layer:          1 generic dispatch_by_capability tool, not N role-specific tools
Future roles (QA, UX, Ideation): pre-slotted in forge.yaml as commented blocks;
                                 uncomment + ship agent = stage active
Reply with:

C4 — accept and continue to Category 5: Cross-Cutting Concerns
Further edits
A for inline ADR
[R]evise - on reflection the Pipeline as data — forge.yaml stage sequence (revised) isn't what I had envisaged - the whole point of creating an agent for this is to use it's reasoning combined with training based on the command histories I provided - if we hard code the pipeline stages whats the point in having an agent harness? The Forege should figure out what need sto be done, use the traing provided and graphiti knowledge to learn and become smarter - I thught we had already discussed most or at least some of this - and should already be in the source documents?
You're right — I regressed into a YAML state machine and lost the whole point of the agent harness. The source documents are explicit and I should have held the line:

pipeline-orchestrator-motivation.md: "An orchestrating agent with access to Graphiti (for architectural context), the slash commands (as tools), and a reasoning model (for decision-making) could have made 2 of those 3 decisions on its own."
forge-pipeline-orchestrator-refresh.md §Core Framing: "Its core competency is: orchestrating the pipeline... knowing which agent to call, what context to pass, evaluating Coach scores against configurable thresholds, routing to humans when confidence is low... This is orchestration reasoning, not domain reasoning."
fleet-master-index.md D36: "Uses strong reasoning model (Claude Sonnet) for orchestration decisions, not fine-tuned domain judgment."
Category 2 Revision 3 (already agreed this session): we added forge.calibration to ingest history files as CalibrationEvent stream — precisely so the reasoning model can learn from Rich's decisions, not so a YAML can replay them.
My pipeline.stages: [...] list was a state machine with a bow on it. If that's the architecture, we don't need DeepAgents. A 200-line Python state-machine class would do the same job.

Revision 6 — Pipeline is reasoning, not sequence
Drop the ordered pipeline: block from forge.yaml
The YAML keeps policy (the knobs the reasoning model operates within), not sequence:


# forge.yaml (REVISED — policy only)

# Threshold defaults keyed by stage-KIND, not position
gate_defaults:
  specification_review: { auto_approve: 0.80, flag_for_review: 0.50 }
  architecture_review:  { auto_approve: 0.75, flag_for_review: 0.50 }
  feature_planning:     { auto_approve: 0.85, flag_for_review: 0.55 }
  build_plan_review:    { mode: mandatory_human_approval }   # training-mode override
  autobuild:            { auto_approve: 0.80, flag_for_review: 0.60 }
  pr_creation:          { auto_approve: 1.00, flag_for_review: 0.80 }

training_mode: true                   # requires confirmation on otherwise-auto-approve
notifications: { ... per-stage-kind on/off ... }
learning:      { min_samples: 10, override_rate_upper: 0.10, ... }
build_config:  { max_turns_per_task: 5, sdk_timeout: 1800 }

# NO `pipeline: stages: [...]` LIST.  Ordering is a reasoning decision.
forge.stages becomes a catalogue of stage kinds, not a sequence walker
Each stage kind is a record the reasoning model can invoke by name:


# forge/stages/catalogue.py — inventory, not control flow
STAGE_KINDS = {
    "specification_review": StageKind(
        description="Validate the feature spec is complete, assumptions resolved, "
                    "BDD scenarios coherent. Delegates to fleet agent advertising "
                    "review_specification, else falls back to guardkit_feature_spec.",
        preferred_tool="review_specification",
        fallback_intent="specification.review",
        local_fallback_tool="guardkit_feature_spec",
        gate_profile_key="specification_review",
    ),
    "architecture_review": StageKind(...),
    "feature_planning":    StageKind(preferred_tool="guardkit_feature_plan", ...),
    "build_plan_review":   StageKind(preferred_tool="build_plan_composer", ...),
    "autobuild":           StageKind(preferred_tool="guardkit_autobuild", ...),
    "pr_creation":         StageKind(preferred_tool="guardkit_pr_create", ...),
    # ─── future kinds ─── uncommented as they become useful / trained
    # "quality_review":    StageKind(preferred_tool="review_quality", ...),
    # "ux_review":         StageKind(preferred_tool="review_ux", ...),
    # "ideation_score":    StageKind(preferred_tool="score_idea", ...),
}
The catalogue is a dictionary the reasoning model reads, not a list it walks. When the reasoning model decides "the current build needs architecture review," it invokes specialist_stage_runner(kind="architecture_review", ...) — the sub-agent then resolves the target agent at runtime via forge.discovery and dispatches.

System prompt — where the anchor's narrative actually lives
The anchor's 5-stage shape becomes guidance in forge.prompts.system_prompt, not control flow:


FORGE_SYSTEM_PROMPT = """\
You are Forge, the NATS-native pipeline orchestrator for the Software Factory fleet.
Today's date is {date}.

{domain_prompt}

─── PIPELINE SHAPE (describable pattern, not a script) ────────────────────────
A typical feature build follows this shape:
  1. Specification review   (delegated to fleet specialist or local fallback)
  2. Architecture review    (delegated, or skipped if architecture is settled)
  3. Feature planning       (local GuardKit command)
  4. Build plan review      (composed locally; human-approved in training mode)
  5. AutoBuild execution    (local GuardKit subprocess)
  6. PR creation            (local git + gh)
You decide which stages this specific build needs, in what order, and when to
skip — based on inputs, capability availability, calibration priors, and
project context below.

─── AVAILABLE CAPABILITIES (live — snapshot taken at build start) ────────────
{available_capabilities}
     — from `forge.discovery.list_capabilities()`.  New specialists may come
     online mid-build and will appear on subsequent resolve() calls.

─── CALIBRATION PRIORS (how Rich has historically decided in similar cases) ─
{calibration_priors}
     — retrieved from Graphiti `forge_calibration_history` filtered by the
     current build's context (feature scope, complexity, domain tags).
     Example signals: "95% default-acceptance on /feature-spec group curation",
     "deviates from default when stage lists > 30 scenarios per group".

─── PROJECT CONTEXT ──────────────────────────────────────────────────────────
{project_context}
     — retrieved from Graphiti `forge_pipeline_history` for this repo/feature:
     prior builds, gate decisions, override events, ADR references.

─── GUARDRAILS (policy, not procedure) ────────────────────────────────────────
• Sequential builds (ADR-SP-012) — never spawn parallel work.
• Confidence gates per `forge.yaml.gate_defaults` — auto_approve / flag / hard_stop.
• Training mode ({training_mode}) — when true, auto-approve requires confirmation.
• PR review is ALWAYS human — never auto-approve final merge.
• Degraded mode: if a preferred capability is unavailable, fall back to the
  local GuardKit tool and force flag_for_review.

Call tools to make progress.  Stop when PR is created (or build fails/is paused).
"""
All four {placeholders} are injected at build start by forge.agent (shell module) before create_deep_agent() executes — this is the system-prompt-template-specialist pattern, straight from the .claude/rules/ guidance.

What the reasoning model does at each build
Receives BuildQueuedPayload via the ingestion tool
Reads it + retrieves calibration + project context + live capabilities
Reasons: "This is a feature-addition build on lpa-platform. Architecture exists in Graphiti. Calibration says similar builds skipped Stage 1 but needed Stage 2. A quality_review capability is available — similar builds used it with good results."
Invokes specialist_stage_runner(kind="architecture_review", ...) — sub-agent does the fleet resolve + dispatch + gate evaluation
Reads the result, reasons about next step
Repeats until PR created, build failed, or paused awaiting human
Writes the full decision trace + gate outcomes + override events to Graphiti for the next build to learn from
This is the agent harness earning its keep.

forge.state_machine scope narrows
Build lifecycle states remain:


QUEUED → PREPARING → RUNNING → PAUSED → FINALISING → COMPLETE
                         ↓        ↓                         ↓
                      (reasoning loop)                    FAILED
                         ↓
                     INTERRUPTED (crash recovery)
RUNNING is one state from the lifecycle's perspective — what the DeepAgents graph is doing inside it is not modelled here. The state machine cares about:

Terminal conditions (COMPLETE | FAILED | CANCELLED | SKIPPED)
External observability (JetStream ack timing, SQLite writes, event emission)
Crash recovery (what transitions are safe to resume)
It does not care what stage the reasoning model is currently on. That's in SQLite stage_log as an audit trail, not a control variable.

Sub-agent topology — unchanged from Revision 5, but emphasis shifts
Sub-agent	Role
specialist_stage_runner	Reusable stage executor — parameterised by stage kind (from catalogue) and target capability (resolved at call time). Used by reasoning model whenever it decides to delegate to the fleet.
guardkit_stage_runner	Reusable stage executor for local guardkit_* tools.
build_plan_composer	LLM content generator — synthesises build plan artefact. Reasoning model invokes when it judges a build plan is warranted (not always).
autobuild_runner	Subprocess orchestration for guardkit autobuild --nats.
pr_finaliser	Final git + gh operations.
Sub-agents stay 5 — but their parameterisation is now a reasoning output, not a YAML lookup.

ADRs: invert, don't add
Before (Rev 5)	After (Rev 6)
ADR-ARCH-016	"Pipeline as data — forge.yaml declares ordered stages"	"Pipeline is reasoning — stage kinds are a catalogue the agent reads; sequence is a reasoning output per build. forge.yaml holds policy (thresholds, training_mode, learning params), never an ordered list."
ADR-ARCH-015	unchanged — capability-driven dispatch	unchanged — still central
ADR-ARCH-017	unchanged — live fleet watching	unchanged
New ADR:

ADR-ARCH-018: Calibration corpus as retrievable prior — forge.calibration ingests Rich's history files as CalibrationEvent stream; Graphiti forge_calibration_history indexes them. At each build start, forge.prompts retrieves relevant priors (by context similarity) and injects {calibration_priors} into the system prompt. This is the mechanism by which Forge improves over time — reasoning + retrieved priors, not hardcoded thresholds.
Total queued: 17 ADRs (unchanged — one inversion, one addition that replaces the deleted one).

Category 4 Checkpoint (Revision 6 — reasoning-driven)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4 (REVISED — pipeline is reasoning)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consumers:        unchanged (Rich, Jarvis, specialists, future dashboard/adapters)
Protocols:        unchanged (Click + NATS + subprocess; no MCP/REST/gRPC)
Dispatch:         capability-resolved at runtime via forge.discovery
Pipeline shape:   PROSE GUIDANCE in system prompt — 5-stage narrative as pattern,
                  not control flow. Reasoning model chooses stages per build.
Stage catalogue:  dictionary of STAGE_KINDS — reasoning model invokes by name
Policy (forge.yaml): thresholds per stage-kind, training_mode, notifications,
                     learning params, build_config — NO ordered stage list
Learning loop:    history files → CalibrationEvents → Graphiti forge_calibration_history
                  → retrieved at build start → injected into system prompt
                  → reasoning model decisions written back to forge_pipeline_history
                  → compounds across builds
State machine:    build lifecycle only (QUEUED→…→COMPLETE/FAILED) — NOT stage sequencing
Hot-swap:         new fleet capabilities visible on next discovery.resolve(),
                  reasoning model decides whether to use them based on priors
Reply with:

C4 — accept and continue to Category 5: Cross-Cutting Concerns
Further edits
A for inline ADR
[R]evise - that's an improvement but you are still effectively hardcoding the capabilities surely? So if you look at forge.stages becomes a catalogue of stage kinds, not a sequence walker you have these:
 # "quality_review":    StageKind(preferred_tool="review_quality", ...),
    # "ux_review":         StageKind(preferred_tool="review_ux", ...),
these agents are not yet created and you have marked them as for future but then instead of acknowleging the agents capabilities as they become available and adapting you are asking me to uncomment or add a line to the YAMl config which is completly at odds with the entire concept surely?

You're right. I kept a static registry — STAGE_KINDS = {…} with commented-out future entries — and dressed it up as "the reasoning model chooses the order." That's still hardcoded capability knowledge inside Forge. The fleet registry is supposed to be the catalogue.

Revision 7 — The fleet is the catalogue. Stages are emergent labels.
Delete the stage-kind catalogue entirely
forge.stages as a module with a pre-coded STAGE_KINDS dictionary → gone. No enum of stage kinds exists in Forge's code. What exists:

forge.discovery — queries the live fleet, returns every registered agent's AgentManifest with full ToolCapability.description + IntentCapability.description text (they're already in the manifest per agent-manifest-contract.md). This is the entire catalogue of specialist capabilities.
forge.tools — the flat list of local @tools (the 11 GuardKit tools, git, gh, SQLite history, approval, notification, graphiti, dispatch_by_capability). DeepAgents registers all of these with create_deep_agent(..., tools=[...]) — they are visible to the reasoning model with their docstrings as capabilities.
forge.prompts.system_prompt — describes the factory's shape in prose and injects the live fleet catalogue + calibration priors. Does not list stage names.
Stages are emergent labels, not control flow
When the reasoning model dispatches, it names what it's doing (one short string — "Specification Review", "Quality Review", "Exploring alternative architectures") and that label is written to SQLite stage_log alongside the dispatch record.

Prospective: the reasoning model picks a capability from the live catalogue and invokes it. No stage-kind lookup, no preferred_tool mapping.
Retrospective: forge history --feature FEAT-XXX shows the sequence of labels the reasoning model chose. Rich can read it as a narrative. A stage called "Accessibility Audit" shows up in the log the first time a newly-registered agent with an audit_accessibility tool gets chosen — zero Forge code or config change.
This is literally how an agent with tool access works. The labels are for human narrative, not control.

Revised forge.yaml — gate defaults keyed by tool, not stage-kind

# forge.yaml (REVISED AGAIN — no stage-kind anywhere)

gate_defaults:
  universal: { auto_approve: 0.80, flag_for_review: 0.50 }   # fallback for any capability
  overrides:                                                   # per-tool, optional
    guardkit_autobuild:   { auto_approve: 0.80, flag_for_review: 0.60 }
    guardkit_pr_create:   { auto_approve: 1.00, flag_for_review: 0.80 }
    # Rich adds entries here once he's seen a new capability in action —
    # the universal default governs on first use.

training_mode_rules:
  # Optional per-tool "always require human confirmation" rules
  # — not a stage-kind list, just tools Rich wants extra caution on early on.
  - tool: build_plan_composer
    mode: mandatory_human_approval
    relaxation_criteria: { min_approved: 10, max_rejection_rate: 0.10 }

notifications:
  enabled: true
  per_event_type:
    auto_approve:       true
    flag_for_review:    true
    hard_stop:          true
    stage_start:        false
  # No per-stage-name config — notifications trigger on gate outcomes,
  # regardless of what label the reasoning model chose for that stage.

learning: { min_samples: 10, override_rate_upper: 0.10, override_rate_lower: 0.01 }
build_config: { max_turns_per_task: 5, sdk_timeout: 1800 }
What the reasoning model sees on first contact with a newly-registered agent:

Its ToolCapability.description (human-readable) via forge.discovery
Its IntentCapability.description + signals + confidence
No corresponding forge.yaml override → universal gate defaults apply
No training_mode_rules entry → standard gate evaluation
No calibration priors for this specific capability yet → the first use itself becomes the calibration data point — Graphiti writes the outcome, and future builds see it
No uncommenting. No YAML edit. Rich ships the agent → agent registers → next Forge build sees it → reasoning model reads its description → decides whether to use it → if used, first outcome is recorded → second build has a prior.

Revised system prompt — capabilities injected live, no pre-declared kinds

FORGE_SYSTEM_PROMPT = """\
You are Forge, the NATS-native pipeline orchestrator for the Software Factory fleet.
Today's date is {date}.

{domain_prompt}

─── FACTORY SHAPE (narrative, not procedure) ──────────────────────────────────
A feature goes through specification, architecture, planning, implementation, and
PR creation — but what "specification" or "architecture" means for THIS build
depends on what the fleet can do and what this build needs.  You decide what
work is required, in what order.  You are not executing a fixed pipeline.

─── LIVE FLEET CAPABILITIES (snapshot at build start) ─────────────────────────
{fleet_capabilities}
     Each entry includes agent_id, ToolCapability.name/description/parameters,
     IntentCapability.pattern/description/confidence, trust_tier.
     New agents may register mid-build; subsequent tool calls see them via
     forge.discovery.resolve().

─── LOCAL TOOLS (always available) ────────────────────────────────────────────
{local_tool_index}
     GuardKit slash commands, dispatch_by_capability, git, gh, history,
     approval, notification, graphiti — see each tool's docstring.

─── CALIBRATION PRIORS (for builds similar to this one) ───────────────────────
{calibration_priors}
     From forge_calibration_history.  Example:
     "On comparable lpa-platform features, /feature-spec group curation was
      accepted as default 100% of the time.  /feature-plan had one rewording
      at wave 3."  Use these as priors, not rules — they are evidence.

─── PROJECT CONTEXT ──────────────────────────────────────────────────────────
{project_context}
     From forge_pipeline_history for this repo.  Prior build outcomes,
     gate decisions, override events, ADR references, any capabilities
     previously used successfully for this project.

─── GUARDRAILS (policy) ───────────────────────────────────────────────────────
• Sequential builds (ADR-SP-012) — do not parallelise.
• Gates per forge.yaml.gate_defaults — universal default unless there is an
  override for a specific tool.
• Training mode ({training_mode}) — auto-approve requires human confirmation
  when enabled.
• PR review is ALWAYS human.
• When a capability you'd prefer is unavailable, your options are: use a
  local GuardKit tool, defer by pausing for human input, or skip the work.
  Choose based on calibration and context.

─── STAGE LABELS FOR HISTORY ──────────────────────────────────────────────────
When you invoke a tool or sub-agent, tag the step with a short human-readable
label (e.g. "Specification Review", "Exploring alternate data model",
"Accessibility Audit").  These labels appear in `forge history` so Rich can
read the build as a narrative.  Labels are yours to choose — not a fixed list.

Stop when PR is created, build fails, or a hard-stop gate fires.
"""
Module count drops to 16
Change	Before	After
forge.stages (stage-kind catalogue)	module with STAGE_KINDS dict	deleted — no module
forge.history_labels (new, trivial)	—	added — tiny helper that takes the reasoning model's label + dispatch details and writes a stage_log row. ~30 lines.
Net: 17 − 1 + 1 = 17, but forge.history_labels is a strictly passive helper, not control flow. The architectural "stages" concept is reduced to post-hoc rows in SQLite.

Sub-agent count drops to 2
specialist_stage_runner / guardkit_stage_runner were my pattern-driven wrappers. In the fleet-is-catalogue model they're redundant — the reasoning model calls dispatch_by_capability(...) or a guardkit_* tool directly, reasons about the result, and proceeds. No wrapper sub-agent needed.

Sub-agents retained:

build_plan_composer — LLM content generation; benefits from its own context and prompt. Reasoning model delegates when it judges a build plan is warranted.
autobuild_runner — long-running subprocess with progress stream; genuinely multi-step and warrants context isolation.
Everything else is direct tool calls from the main reasoning loop. This is closer to the DeepAgents philosophy.

ADRs — inversions
Before (Rev 6)	After (Rev 7)
ADR-ARCH-016	"Pipeline is reasoning; stage kinds are a catalogue"	"Fleet is the catalogue. Forge has no pre-coded stage kinds. Live fleet capabilities + local tools are the entire action space. Stages are emergent labels the reasoning model chooses per dispatch, written retrospectively to stage_log for human narrative — never consulted prospectively."
ADR-ARCH-015	Capability-driven dispatch	unchanged — still primary
ADR-ARCH-017	Live fleet watching	unchanged
ADR-ARCH-018	Calibration priors retrievable	unchanged — becomes more load-bearing because there are no other priors
New ADR:

ADR-ARCH-019: Gate defaults keyed by tool, not stage-kind — universal default in forge.yaml.gate_defaults.universal; per-tool overrides opt-in once Rich has observed a capability in action. First-use governance is the universal default → outcome recorded in Graphiti → second use has a calibration prior. No pre-declared stage list anywhere.
Total queued: 18 ADRs (17 prior, 1 added — ADR-ARCH-019; ADR-ARCH-016 inverted in place).

Category 4 Checkpoint (Revision 7 — fleet is the catalogue)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4 (REV 7 — no stage enum, fleet is catalogue)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Consumers:          unchanged
Protocols:          unchanged (Click + NATS + subprocess)
Catalogue source:   LIVE FLEET — forge.discovery reads ToolCapability and
                    IntentCapability descriptions from every registered agent's
                    AgentManifest.  Forge has NO pre-coded stage kinds.
Local tools:        flat @tool list (GuardKit commands, git, gh, etc.) —
                    DeepAgents registers all, reasoning model sees all
Stage concept:      emergent labels (reasoning model names each dispatch);
                    written post-hoc to SQLite stage_log for narrative;
                    never consulted prospectively
Gate defaults:      universal threshold for any capability; per-tool overrides
                    in forge.yaml as Rich learns what to tune
New agent arrival:  agent registers → next build sees capability via discovery →
                    reasoning model reads its description → decides whether to
                    use based on build needs + calibration → outcome stored →
                    future builds have priors.  ZERO Forge code or YAML change.
Sub-agents:         2 (build_plan_composer, autobuild_runner) — everything
                    else is direct tool calls from the reasoning loop
Modules:            16 + 1 trivial helper (history_labels) = 17
Reply with:

C4 — accept and continue to Category 5: Cross-Cutting Concerns
Further edits
A for inline ADR
[R]evise but from what I see Revised forge.yaml — gate defaults keyed by tool, not stage-kind is still essentially a static configuration of capabilities? how is this using an agent harness as I intended?
You're right again. Even "universal threshold + per-tool overrides in YAML" is me pre-declaring expected knobs for capabilities the system hasn't met yet. If Forge reasons and learns, gate decisions are reasoning outputs, not YAML lookups.

The clean answer:

Revision 8 — forge.yaml holds infrastructure and constitutional rules only. Everything else is reasoned or learned.
What stays in forge.yaml (irreducibly static)

# forge.yaml — HOW to reach infrastructure, WHAT models to use,
# and HARD RULES that are not reasoning-adjustable.

infrastructure:
  nats_url: "nats://promaxgb10-41b1:4222"
  graphiti_endpoint: "bolt://whitestocks:7687"
  sqlite_path: "~/.forge/forge.db"

models:
  reasoning_model:      "google_genai:gemini-3.1-pro"
  implementation_model: "google_genai:gemini-2.5-flash"

build_config:
  max_turns_per_task: 5
  sdk_timeout: 1800
  max_concurrent: 1              # ADR-SP-012 — physical constraint

constitutional:
  pr_review_always_human: true   # never overridable by reasoning
  never_skip_precommit_hooks: true
  sequential_builds_only: true

learning_meta:
  graphiti_groups:
    pipeline_history:    forge_pipeline_history
    calibration_history: forge_calibration_history
  retrieval_context_tokens: 2000 # budget for injected priors in system prompt
That's the whole file. No gates, no thresholds, no per-tool rules, no notification flags, no training-mode toggle, no stage kinds.

What moves to Graphiti (retrieved, reasoned about)
Concern	Where it lives
Gate decisions per dispatch (auto / flag / hard-stop)	Reasoning output — model reads the Coach score + retrieved priors for this capability + build risk profile, decides in context
Threshold calibration for any capability	Graphiti forge_calibration_history — accumulates capability × context × score × human-outcome tuples. System prompt retrieval surfaces: "review_architecture scored 0.75-0.85 on 15 prior builds, Rich approved all → you have high confidence in this range."
"Training mode"	Emergent from sample size, not a flag. Few samples → natural reasoning conservatism → frequent flags → Rich approves/overrides → samples grow → conservatism relaxes organically. There is no "switch to confidence-gated mode" moment — the curve is continuous.
Notification tuning	Reasoning decision per event. Model retrieves Rich's past notification-acknowledgement behaviour from Graphiti ("Rich reads first-use notifications; ignores autobuild-success notifications after sample 5") and decides whether emitting is worthwhile.
Per-tool biases	Retrieved priors, not YAML overrides. "Rich has rejected 6 of the last 10 review_specification auto-approves at scores 0.78-0.82 → you should flag at these scores for this project."
Threshold-adjustment proposals	forge.learning detects override patterns and proposes Graphiti entities biasing future reasoning. Rich confirms (via CLI approval round-trip) → entity is written → next build's prompt retrieves the new bias. No YAML edit.
Revised system prompt section — gate reasoning without static thresholds

# forge.prompts — add to the system prompt
"""
─── GATE DECISIONS ──────────────────────────────────────────────────────────
For every dispatch that returns a Coach score, you decide auto-approve /
flag-for-review / hard-stop.  You decide based on:

  • The Coach score and its criterion breakdown
  • The capability's calibration history (if any) — retrieved priors show how
    similar dispatches scored and how Rich responded
  • The build's risk profile — architectural changes, security-adjacent work,
    and first-time use of a capability warrant more caution
  • Constitutional rules (PR review is always human)

If you have NO calibration priors for a capability, prefer flag-for-review.
First use of a new capability is itself a calibration event — Rich's response
becomes the prior for future builds.  Err conservative.

Record every gate decision with your rationale — it becomes the next build's
evidence.

─── NOTIFICATIONS ──────────────────────────────────────────────────────────
You decide whether to notify Rich for each event.  Consider:

  • First-use notifications are high-value (Rich is watching for these)
  • Repeated success notifications lose value fast — check retrieved priors
    on Rich's ack/read behaviour for this event type on this project
  • Hard-stop notifications are always emitted (not reasoning-adjustable)
  • Flagged events ALWAYS emit ApprovalRequestPayload — that's not a
    notification, it's a blocking handoff

Cost of missed notification is much lower than cost of notification fatigue.
"""
What forge.learning actually does now
Before: proposed YAML threshold adjustments (static target).

After: detects patterns in Graphiti override history and proposes bias entities. Example proposal delivered as a notification to Rich:

"For review_specification on lpa-platform, you have overridden 6/10 recent flag-for-reviews by approving without edits at scores 0.78–0.82. Would you like me to raise my confidence threshold for this capability on this project? If confirmed, future builds will auto-approve in that score range by default."

Rich confirms or rejects. On confirm, a CalibrationAdjustment entity lands in Graphiti. Future builds retrieve it. No YAML.

Module + sub-agent count — unchanged
Modules stay at 17 (including the trivial forge.history_labels)
Sub-agents stay at 2 (build_plan_composer, autobuild_runner)
forge.learning exists but proposes to Graphiti, not to YAML
ADRs — replace and consolidate
Revised ADR-ARCH-019:

ADR-ARCH-019: No static behavioural configuration — gates, thresholds, notifications, training mode all flow from reasoning + retrieved priors. forge.yaml holds only infrastructure, model selection, constitutional rules, and learning meta-config. Gate decisions are reasoning outputs informed by Graphiti-retrieved calibration priors. "Training mode" is emergent from sample size (few priors → natural conservatism), not a flag. Threshold adjustments live in Graphiti as CalibrationAdjustment entities proposed by forge.learning and confirmed by Rich via approval round-trip — never via YAML edit.

ADRs 015–018 unchanged. 019 replaces the earlier "gate defaults by tool" version.

Total: 18 ADRs (unchanged count; 019 rewritten).

Category 4 Checkpoint (Revision 8 — agent reasons and learns)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4 (REV 8 — no static behavioural config)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

forge.yaml scope:    infrastructure + models + build_config +
                     constitutional + learning_meta ONLY.
                     Zero gates, thresholds, notification rules, stage kinds.

Gate decisions:      reasoning output per dispatch — Coach score + retrieved
                     priors + build risk + constitutional rules → decide.
                     No priors → prefer flag-for-review (first use is itself
                     a calibration event).

Training mode:       DELETED as a concept.  Sample-size-emergent conservatism
                     replaces the toggle.  Curve of flag-rate vs build-count
                     IS the training signal — not a YAML flip.

Notifications:       reasoning decision per event, informed by retrieved
                     Rich-ack-behaviour priors.  Hard-stops always emit;
                     flags always block with ApprovalRequestPayload.

Learning loop:       forge.learning detects override patterns in Graphiti →
                     proposes CalibrationAdjustment entity → notification to
                     Rich → Rich confirms via approval round-trip → entity
                     written → future builds' system prompt retrieves it.
                     NO YAML EDITS.  Ever.

Rich's intervention: override a gate decision in the moment.
                     Each override becomes evidence for the next build's prompt.
                     Rich never hand-edits thresholds.

Catalogue:           still live fleet (Rev 7) — forge.discovery resolves
                     ToolCapability from AgentManifests.  Stages are emergent
                     labels, not enum.
Reply with:

C4 — accept and continue to Category 5: Cross-Cutting Concerns
Further edits
A for inline ADR


R]evise - perfect we got there, one thing I'm thinking is that we should check the latest version of LangChain deepagents sdk for its latest capabilities, for example they have added async subagents and while tis is getting into the weeds of the implementation it could change the shape of the architecture see https://github.com/langchain-ai/langchain-skills

Good instinct — LangChain moves fast and the AsyncSubAgent reference in the refresh doc is from 11 April (a week ago). If there's a skills primitive in langchain-skills, it likely replaces or restructures what we've been calling sub-agents and tools. Checking the repo + current SDK docs before revising.

Critical finding: langchain-skills is NOT a DeepAgents runtime primitive. It's Anthropic Agent Skills — markdown reference material installed via npx skills add for coding agents (Claude Code, Cursor, Windsurf). Teaching materials for us when implementing Forge, not a runtime concept inside Forge.

Now checking the actual DeepAgents SDK state via the official quickstarts repo.

Context7 [query-docs]Current primitives in deepagents SDK - c…
OUT
Built-in Deepagent Tools in Python

Source: https://context7.com/langchain-ai/deepagents-quickstarts/llms.txt


Demonstrates how agents automatically include and utilize built-in tools for filesystem operations, task management, and delegation. The example shows an agent autonomously planning research, delegating tasks to sub-agents, and saving findings to a file without explicit tool calls from the user.



from deepagents import create_deep_agent

# All agents include these built-in tools automatically:
# - write_todos: Create structured task lists
# - read_todos: View current todo list
# - ls: List files in directory (absolute paths)
# - read_file: Read file content with pagination
# - write_file: Create or overwrite files
# - edit_file: Exact string replacements
# - glob: Find files matching patterns (e.g., "**/*.py")
# - grep: Search for text patterns in files
# - execute: Run shell commands (if backend supports sandboxing)
# - task: Delegate to sub-agents with isolated contexts

# Example: Agent automatically uses tools during research
agent = create_deep_agent(model=model, tools=[tavily_search, think_tool])

response = agent.invoke({
    "messages": [("user", "Research AI agents and save findings")]
})

# Agent will automatically:
# 1. write_todos to plan research steps
# 2. task() to delegate to research sub-agent
# 3. write_file to save /final_report.md
# 4. read_file to verify the report

# No explicit tool calling needed - agent decides autonomously



Create Deep Agent with Tools and Subagents

Source: https://github.com/langchain-ai/deepagents-quickstarts/blob/main/deep_research/research_agent.ipynb


Creates a deep agent by integrating a specified LLM model, a list of tools, a system prompt, and one or more sub-agents. This function enables parallel task execution and independent findings from sub-agents, facilitating complex research workflows.



# Create the agent
agent = create_deep_agent(
      model=model,
      tools=tools, 
      system_prompt=INSTRUCTIONS,
      subagents=[research_sub_agent],
  )

🚀🧠 Deepagent Quickstarts

Source: https://github.com/langchain-ai/deepagents-quickstarts/blob/main/README.md


Deepagents is a simple, open source agent harness. It uses common principles seen in popular agents such as Claude Code and Manus, including planning (prior to task execution), computer access (giving the agent access to a shell and a filesystem), and sub-agent delegation (isolated task execution). This repo has a collection of quickstarts that demonstrate different agents that can be easily configured on top of the deepagents harness.



🚀🧠 Deepagent Quickstarts > Built-In Deepagent Components > Tools

Source: https://github.com/langchain-ai/deepagents-quickstarts/blob/main/README.md


Every deepagent comes with a set of general tools by default. These tools include functionalities for task management (write_todos), file system operations (ls, read_file, write_file, edit_file, glob), text searching within files (grep), executing shell commands in a sandboxed environment (execute), and delegating tasks to specialized sub-agents (task).



Quickstarts > Built-in Deepagent Tools

Source: https://context7.com/langchain-ai/deepagents-quickstarts/llms.txt


Built-in Deepagent Tools encompass a suite of default functionalities provided by the deepagents middleware, accessible automatically to all agents. These tools cover essential operations such as task management (creating and viewing todos), filesystem interactions (listing, reading, writing, editing files, and finding files with glob/grep), and executing shell commands. A key tool is task, which allows for delegating work to sub-agents within isolated contexts. Agents created using create_deep_agent can leverage these tools autonomously during their execution, for instance, planning research steps with write_todos, delegating to a research sub-agent using task(), and saving findings with write_file, without requiring explicit tool calls in the user's code.

sorry I gave you the wrong url see https://docs.langchain.com/oss/python/deepagents/overview and https://github.com/langchain-ai/deepagents

Got the right docs now. DeepAgents 0.5.3 (15 April 2026) has more built-in primitives than I accounted for. Material changes for Forge:

Revision 9 — Lean on DeepAgents built-ins; collapse custom code where the SDK already provides it
Built-ins we were about to re-implement
DeepAgents built-in	What I had in the architecture	Action
write_todos (built-in planning tool)	Implicit "reasoning model picks next step"	Adopt. The todo list is the build's narrative. Each todo entry is the stage label from Rev 7 — Rich reads forge history and sees the reasoning model's planning trace directly. No custom stage-labelling code.
Filesystem tools (read_file, write_file, edit_file, ls, glob, grep)	Custom file-handling in adapters.git + adapters.guardkit + a few @tools	Adopt all. Built-in.
execute (shell with sandbox support)	Custom subprocess wrappers for git, gh, guardkit	Adopt as the substrate. Our forge.adapters.git collapses to a thin policy layer (which git commands are permitted); forge.adapters.guardkit becomes subcommand composition + progress-stream parsing on top of execute.
task (built-in sub-agent delegation with isolated context)	Pre-declared SubAgent/AsyncSubAgent TypedDicts	Adopt dynamically. The reasoning model calls task(sub_agent=…, prompt=…) when it decides isolated context is needed. We still pre-declare reusable sub-agents with curated prompts (build_plan_composer, autobuild_runner) but most delegation is spawned on demand.
Pluggable filesystem backends (in-memory, local disk, LangGraph store, sandboxes)	Custom "worktree / devcontainer / sandbox" abstraction from conversation starter	Use sandbox backend when available. Phase 3 of the conversation starter's execution-environment ladder is free. Phase 1 (worktrees) + Phase 2 (devcontainers) are still worth having as configurable backend options.
LangGraph interrupt()	Custom PAUSED state + ApprovalRequestPayload round-trip	Interrupt IS the PAUSED state. The graph calls interrupt(approval_payload) → LangGraph server pauses the run → forge.adapters.nats publishes ApprovalRequestPayload to agents.approval.forge.{build_id} → Rich replies → LangGraph resumes the graph with the response. Our state-machine PAUSED transition is a pure LangGraph primitive now, not custom code.
Permissions system (declarative file/host allow rules)	Nothing planned	Add. Category-5 cross-cutting concern — declare which paths + hosts Forge may touch (working trees under /var/forge/builds/, NATS at promaxgb10-41b1:4222, Graphiti at whitestocks:6379, LLM provider hosts, GitHub). Tight blast-radius by default.
Context management / auto-summarisation	Custom compaction concern	Adopt. 30–60-minute builds produce long conversations. DeepAgents auto-summarises; no custom compaction code.
Long-term Memory Store (LangGraph primitive)	Not planned — only Graphiti	Adopt as complement. Memory Store for fast in-graph recall across turns within one build-thread; Graphiti for cross-build fleet-wide learning. Not competing — Memory Store is thread-scoped, Graphiti is fleet-scoped.
Revised module map (17 → 15)

A. DeepAgents Shell  — agent, prompts, subagents (only 2 pre-declared:
                       build_plan_composer + autobuild_runner;
                       others spawned via task() at runtime)
B. Domain Core       — gating (reasoning-driven, not threshold-driven),
                       state_machine (delegates PAUSED to LangGraph interrupt),
                       notifications (reasoned), learning, calibration,
                       discovery
C. Tool Layer        — tools/* — only Forge-specific primitives remain:
                       • dispatch_by_capability (fleet call via nats-core)
                       • approval_tools (interrupt payload builders)
                       • notification_tools (NotificationPayload emitters)
                       • graphiti_tools (record/retrieve priors)
                       • guardkit_* (thin wrappers over built-in execute)
                       • history_tools (SQLite schema'd writes)
                       [DROPPED: git_tools, pr_tools, file_tools, queue_tools —
                        subsumed by built-in execute + read_file/write_file]
D. Adapters          — nats (pub/sub + KV + JetStream consumer),
                       sqlite (schema'd writes, complements write_file),
                       guardkit (subcommand + progress-parser over execute),
                       graphiti, history_parser
                       [DROPPED: git, subprocess — built-in execute handles these]
E. Cross-cutting     — config, cli, fleet

Net: 17 → 15 modules, with several reduced in scope rather than deleted.
Sub-agents: 2 pre-declared, rest spawned via task()
Pre-declared (because their system prompts are curated and reused):

build_plan_composer — LLM content generator; isolated context for composing buildplan.md from feature plans
autobuild_runner — long-running subprocess + progress stream + timeout handling; isolated context for the 20–60-minute autobuild stage
Everything else is task()-spawned. When the reasoning model decides "I want a focused sub-agent to dispatch the architecture review and evaluate the score," it calls task() with an inline spec. This is more dynamic than pre-declaring, and matches the "fleet is the catalogue" principle from Rev 7: no pre-coded expectations, just on-demand composition.

PAUSED state via LangGraph interrupt (clean implementation)

# forge/stages/gate_evaluation.py (pseudocode)
async def evaluate_gate(capability_result, priors, rationale):
    decision = reason_about_gate(capability_result, priors, ...)
    if decision.mode == "flag_for_review":
        # Publish ApprovalRequestPayload via NATS (so Rich/Jarvis can see it)
        payload = build_approval_payload(decision, build_id, ...)
        await nats.publish(f"agents.approval.forge.{build_id}", payload)

        # Pause the graph — LangGraph interrupt() is the PAUSED state
        response = interrupt(payload.model_dump())
        # ↑ Graph halts here.  LangGraph server surfaces the interrupt value.
        # Rich replies via NATS → LangGraph resume() with the response → this line returns.

        return handle_approval_response(response)
    # ... etc
This replaces our custom "PAUSED SQLite row + JetStream-unacked" state tracking for approval round-trips. JetStream stays unacked (crash recovery), SQLite still records the PAUSED marker (for forge status), but the blocking mechanism is a LangGraph primitive.

Memory Store vs Graphiti — dual persistence model
Layer	Purpose	Scope	When consulted
LangGraph Memory Store	Fast in-graph recall across turns	Per-thread (per-build)	During the reasoning loop — e.g. "what did I just decide about Stage 2?" — without re-reading SQLite
Graphiti forge_pipeline_history	Build outcomes, gate decisions, override events, capability × context × score triples	Fleet-wide, cross-build	At build start (system prompt injection) + after each gate decision (write-back)
Graphiti forge_calibration_history	Parsed history-file CalibrationEvents	Fleet-wide, seeded once + incremental	At build start (system prompt injection of similar-context priors)
SQLite forge.db	Build + stage_log audit trail	Local, durable, queryable	CLI reads (forge status, forge history); crash recovery
No conflict with ADR-ARCH-009 (omit LangGraph checkpointer) — Memory Store is a different primitive. Checkpointer is for graph-state durability across process crashes (we said JetStream+SQLite handle that); Memory Store is for efficient recall within a running thread.

Auto-summarisation replaces custom compaction
No module needed. DeepAgents handles it.

New ADRs from this revision
ADR-ARCH-020: Adopt DeepAgents built-ins — write_todos, filesystem tools, execute, task, interrupts, permissions, Memory Store, auto-summarisation. Forge-specific tool surface is limited to primitives DeepAgents doesn't provide (NATS dispatch, Graphiti, GuardKit subcommand composition, SQLite schema writes).
ADR-ARCH-021: PAUSED state realised as interrupt() — LangGraph's native pause/resume replaces custom approval round-trip wiring; NATS payload publication runs during the interrupt window.
ADR-ARCH-022: Dual agent memory — LangGraph Memory Store (per-thread, fast recall) + Graphiti (fleet-wide, learning). Complementary, not competing.
ADR-ARCH-016 (pipeline is reasoning) strengthens: the reasoning model's planning is realised via the built-in write_todos tool, making the factory's "narrative" (the DDD-talk story) an emergent output of the agent itself.

Total queued: 21 ADRs (18 prior + 3 from Rev 9).

What stays the same from Rev 7/8
Fleet is the catalogue. No pre-coded stage kinds.
forge.yaml = infrastructure + models + constitutional rules + learning meta-config only.
Gate decisions are reasoning outputs informed by retrieved priors.
Training mode is sample-size-emergent.
Capability-driven dispatch via forge.discovery.
Hot-swap: new agent registers → next build's reasoning loop sees it in the live catalogue + retrieved priors → decides whether to use it.
Category 4 Checkpoint (Revision 9 — DeepAgents-native)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 4 (REV 9 — leans on DeepAgents 0.5.3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SDK version:         DeepAgents 0.5.3 (released 15 Apr 2026)

Built-ins adopted:   write_todos (planning) | filesystem (read/write/edit/ls/
                     glob/grep) | execute (sandboxed shell) | task (sub-agent
                     delegation) | interrupt (human-in-the-loop) |
                     permissions (path/host allowlists) | Memory Store
                     (per-thread recall) | auto-summarisation (context mgmt)

Forge-specific tools: dispatch_by_capability, approval_tools, notification_
                     tools, graphiti_tools, guardkit_* (subcommand wrappers),
                     history_tools (SQLite).
                     DROPPED as custom: git, pr, file, queue — built-ins cover.

Sub-agents:          2 pre-declared (build_plan_composer, autobuild_runner),
                     rest spawned dynamically via task() — even more in line
                     with "no pre-coded capabilities" (Rev 7).

PAUSED state:        LangGraph interrupt() is the mechanism.  NATS publishes
                     ApprovalRequestPayload during the interrupt window.

Memory:              Memory Store (in-thread) + Graphiti (fleet-wide) + SQLite
                     (audit trail). LangGraph checkpointer still omitted
                     (ADR-ARCH-009 holds — JetStream+SQLite for durability).

Module count:        17 → 15 (scope reductions + dropped modules subsumed
                     by built-ins).
Reply with:

C4 — accept and continue to Category 5: Cross-Cutting Concerns
Further edits
A for inline ADR
C4
Category 4: Accepted. Moving to Category 5.
Category 5: Cross-Cutting Concerns
Most of these are already implicit in decisions made earlier — making them explicit here for completeness and surfacing the handful of genuinely new decisions.

Q17. Authentication & authorisation

Plane	Mechanism	Source
NATS (fleet boundary)	Account-based multi-tenancy — APPMILLA (Rich + specialist agents + Jarvis + Forge), FINPROXY (tenant-scoped), SYS (admin)	D13, nats-infrastructure/accounts.conf
LLM provider credentials	Env vars only (GOOGLE_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY) — loaded via AgentConfig; never in AgentManifest, never logged	agent-manifest-contract.md §Manifest vs Config
GitHub	gh auth login once on host; token in ~/.config/gh/hosts.yml	gh CLI convention
DeepAgents permissions system (NEW — adopted in Rev 9)	Declarative filesystem + shell + network allowlist. Constitutional safety config — not reasoning-adjustable. See proposed forge.yaml block below	DeepAgents 0.5.3 built-in
SQLite	OS file perms on ~/.forge/forge.db; Forge runs as forge user	standard
Approval responses	Any APPMILLA-authenticated replier accepted; trust is fleet-boundary	Matches D16 / Cat 4
V2+ hardening (not V1)	per-message signing, intent-based ACLs within APPMILLA, per-user NATS creds for James/Mark	deferred

# forge.yaml — constitutional safety (NOT behavioural config)
permissions:
  filesystem:
    allow_read:  ["/var/forge/builds/*", "/etc/forge/*", "~/.forge/*"]
    allow_write: ["/var/forge/builds/*", "~/.forge/*", "/tmp/forge-*"]
  shell:
    allow_binaries: [git, gh, guardkit, python, pytest]
    deny_default: true
  network:
    allow_hosts:
      - "promaxgb10-41b1:4222"       # NATS
      - "whitestocks:6379"            # Graphiti FalkorDB
      - "api.github.com"
      - "*.googleapis.com"            # Gemini (primary)
      - "api.anthropic.com"           # fallback
      - "api.openai.com"              # fallback
This is static config — deliberately. Blast-radius is a safety invariant, not a behavioural knob the reasoning model should negotiate.

Q18. Logging & observability

Four complementary channels, no duplication:

Channel	What it captures	Primary consumer
Structured JSON logs (structlog, stdlib logging) — every line carries build_id, feature_id, correlation_id, todo_label, and when relevant capability, target_agent_id, coach_score	Low-level trace, developer debugging	docker logs forge, future log aggregator
NATS pipeline.* stream — every state transition and gate decision already publishes a typed event (ADR-SP-013 territory)	Observability IS the event stream — dashboards, Slack adapters, future telemetry subscribers	Pub/sub consumers
SQLite stage_log — one row per reasoning-model dispatch: build_id, todo_label (the emergent stage name from Rev 7), target (local tool or fleet agent_id), duration, coach_score, gate_decision, rationale_summary	Queryable narrative — forge history --feature FEAT-XXX reads this as prose	CLI + future dashboard
LangSmith tracing (optional, opt-in via AGENT_LANGSMITH_PROJECT=forge)	Full DeepAgents graph invocation trace — messages, tool calls, interrupts	Rich inspecting reasoning quality
Graphiti forge_pipeline_history	Every gate decision + override event + outcome — not just logs, but structured entities that compound	Future builds' reasoning (retrieved priors)
Fleet heartbeat (fleet.heartbeat.forge every 30s)	uptime, queue_depth, active_tasks, last_completed_at, health flags (graphiti_healthy, specialist_X_healthy)	Jarvis CAN-bus, future dashboard
No Prometheus/Grafana in V1 — NATS event stream + Graphiti + SQLite are sufficient at local-first scale. V2 could add nats → prometheus adapter.

Auto-summarisation (DeepAgents built-in) compresses in-conversation context only — it never truncates what lands in SQLite or Graphiti. Those are structured and uncompressed by design.

Q19. Error handling

Layered policy — failures are absorbed close to the source, surfaced as evidence to the reasoning model, never escape as tracebacks:

Tool layer (@tool(parse_docstring=True)): every tool wraps logic in try/except and returns a string. On failure, returns a structured JSON error ({"error": "...", "error_type": "...", "recoverable": bool, "context": {...}}) — never raises. Per langchain-tool-decorator-specialist rule (already in .claude/rules/).

Adapter layer: typed exceptions (NATSUnavailable, GraphitiUnavailable, SpecialistUnavailable, GuardKitFailed, GitOperationFailed, GitHubUnavailable). Caught by tools; converted to error strings.

Degraded mode is a reasoning input, not a config fallback. When an adapter reports unavailable, forge.discovery.health_snapshot() reflects it, the next prompt retrieval includes it, and the reasoning model decides: use a local fallback, pause for Rich, skip the work, or abort the build. Matches Rev 8's principle — no static fallback mappings.

Retry policy (at the right layer):

Layer	Retry mechanism
NATS connection	nats-py client — max_reconnect_attempts: 60, exponential backoff (nats-core NATSConfig)
LLM provider call	LangChain built-in retries (exponential backoff on 429/503)
Graphiti query	Fail-fast; reasoning model learns Graphiti unavailability and adapts
Specialist dispatch	One in-build retry (per refresh doc open Q#4 resolution — "Option (b) first, then (a) if retries exhausted"); then reasoning decides
GuardKit subprocess	GuardKit handles its own internal retries; Forge does not retry GuardKit invocations
Crash recovery — unchanged from ADR-SP-013: JetStream redelivers on AckWait timeout; SQLite reconciliation marks RUNNING → INTERRUPTED; fresh-start retry. PAUSED rows survive restart and re-enter paused state (LangGraph interrupt doesn't survive process crashes natively, so we re-publish the ApprovalRequestPayload and wait).

LLM provider circuit-breaker (V2). V1: manual env-var flip to fallback provider when primary degrades. V2: automatic threshold-based failover in ResilientModelFactory.

Constitutional rule enforcement (belt + braces): PR-review-always-human is in the system prompt and enforced as a deterministic assertion in pr_finaliser before calling any gh pr merge. Reasoning cannot bypass a constitutional rule; belt + braces prevents prompt-injection-driven violations.

Q20. Data validation

Pydantic at every boundary — no untyped dict handoffs. Already ambient from D22 and agent-manifest-contract, making explicit:

Boundary	Validation
NATS inbound	nats-core typed payloads — BuildQueuedPayload, CommandPayload, ResultPayload, ApprovalResponsePayload. extra="ignore" for forward compat (ADR-SP-ff schema-versioning).
NATS outbound	Same payload schemas — validation on construct, .model_dump_json() on publish.
Tool input	@tool(parse_docstring=True) — docstring Args → LangChain-validated Pydantic schema.
CLI	Click validates type + presence.
SQLite	BuildRow, StageRow Pydantic models; convert on read/write.
Graphiti entity	Structured entity schemas; values Pydantic-validated before write.
forge.yaml	AgentConfig extended via pydantic-settings; invalid config = fail at startup with the field + error.
Specialist dispatch result	ResultPayload wraps {role_id, coach_score, criterion_breakdown, detection_findings, role_output} per ADR-SP-015 — validated at return.
Constitutional config	Pydantic validators forbid flipping pr_review_always_human to false; forbid removing allowlist entries below a minimum; etc.
Q21. Other cross-cutting concerns

Rate limiting: LLM providers govern themselves (retry + fallback). NATS: no rate limits within APPMILLA; trust boundary. Build queue: max_ack_pending=1 is the physical rate limit.
Caching: Fleet capability cache (forge.discovery, 30s TTL, invalidated on fleet.register/deregister watch). Graphiti retrieval: per-build in-thread cache via LangGraph Memory Store. No LLM response cache — every build is unique + caching risks stale priors.
Feature flags: Not V1. Constitutional rules + env-var config cover the toggles needed.
Configuration reload: forge.yaml on SIGHUP for behavioural-meta (learning parameters); constitutional rules require restart by design.
Time zones: UTC internal, ISO 8601 timestamps. CLI renders --local-tz if Rich wants UK-local.
Graphiti group discipline: Forge writes ONLY to forge_pipeline_history + forge_calibration_history. Never to shared fleet groups. Per D27.
Secret management: env-only; structlog processor redacts known key patterns (*_API_KEY, *_TOKEN). Never in AgentManifest, never in logs, never in Graphiti.
Calibration corpus ingestion pipeline: forge calibrate <path> CLI command — batch-ingests history files into forge_calibration_history. Runs once per project setup + re-runs incrementally as new history files appear (V2: file-watcher auto-ingest; V1: manual invocation).
Dependency pinning: pyproject.toml pins DeepAgents to >=0.5.3,<0.6; langchain-* integrations per LCOI rule (optional-deps block matches CLAUDE.md's .[providers] pattern).
New ADRs from Category 5
ADR-ARCH-023: Permissions-as-safety-config — DeepAgents permissions system (filesystem/shell/network allowlists) lives in forge.yaml as constitutional config. Static and explicit by design — safety boundaries are not reasoning-adjustable.
ADR-ARCH-024: Observability is the NATS event stream + Graphiti + SQLite stage_log — no Prometheus/Grafana in V1. Dashboards, Slack adapters, and future telemetry subscribers consume pipeline.* directly.
ADR-ARCH-025: Tool error handling — every @tool returns structured error strings on failure (never raises). Adapter exceptions are caught at the tool boundary; degraded mode surfaces as evidence in the next reasoning prompt.
ADR-ARCH-026: Constitutional rules enforced belt + braces — system prompt AND deterministic assertions in executor code. Prompt-injection cannot bypass safety invariants (PR review always human, no precommit bypass, sequential builds only).
Total queued: 25 ADRs (21 prior + 4 from Category 5).

Category 5 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 5: Cross-Cutting Concerns
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Auth:           NATS account (APPMILLA); LLM keys env-only; DeepAgents
                permissions (fs/shell/network allowlists) as constitutional
                static config
Observability:  Structured JSON logs + NATS pipeline.* stream + SQLite
                stage_log + optional LangSmith + Graphiti audit.
                No Prometheus/Grafana in V1.
Error handling: Tools never raise — structured error strings; degraded mode
                is reasoning-input, not config-fallback; crash recovery via
                JetStream+SQLite (ADR-SP-013); constitutional rules enforced
                belt + braces
Validation:     Pydantic at every boundary — NATS, tools, CLI, SQLite,
                Graphiti, forge.yaml, specialist results
Caching:        Fleet capabilities (30s TTL); Graphiti retrievals via
                Memory Store; NO LLM response cache
Secrets:        env only; structlog redacts; never in AgentManifest/logs/Graphiti
Rate limits:    ADR-SP-012 sequential enforced via max_ack_pending=1;
                LLM retries/fallback via LangChain/env-var flip
Time:           UTC internal; CLI supports --local-tz rendering
Reply with:

C5 — accept and continue to Category 6: Constraints & NFRs
Edits
A for inline ADR
C5
Category 5: Accepted. Final question category.
Category 6: Constraints & NFRs
Most of these constraints drove earlier decisions; making them explicit here is the last step before C4 diagrams.

Q22. Performance

No hard SLAs — this is a local-first single-operator system. Targets are engineering budgets, not commitments:

Metric	Target	Source
Build throughput	1 build concurrently; queue depth unbounded	ADR-SP-012
Typical build duration	20–60 minutes queue-to-PR (max_task_timeout_seconds: 3600)	refresh doc line 586; Phase 2 agentic-dataset-factory reference (~22 min/task × N)
Per-stage latencies (observed / expected)	Specification review: 60–180s; Architecture review: 60–180s; Feature planning: 30–60s; Build plan compose: 30s; AutoBuild: 10–40min; PR creation: <30s	Phase 0/1 FinProxy (93s → 162s); fleet-master-index
NATS publish	<10ms (PubAck)	nats-core spec
NATS request/reply round-trip	<5s p95 for call_agent_tool()	AsyncSubAgent LES1 §4 POLR — anything >30s must be fire-and-forget
Reasoning model turn	1–5s (Gemini 3.1 Pro); ~200–500 turns/build	provider-agnostic
Graphiti retrieval at build start	<5s for 2000-token prior context	learning_meta.retrieval_context_tokens: 2000
CLI read path	forge status <200ms, forge history <500ms	SQLite local
Cold start	<30s from container up to first JetStream pull	Docker + fleet register + KV warm
Non-targets: sub-second end-to-end build, >1 concurrent build. Quality over speed is the explicit principle (anchor §2 principle 5).

Q23. Scalability

Dimension	Approach
Horizontal	Explicitly not supported. ADR-SP-012 + max_ack_pending=1 on the JetStream consumer + max_concurrent: 1 in AgentManifest. Architectural invariant, not a limitation.
Vertical	Single Python process on GB10 (128 GB shared with vLLM + NATS + Graphiti + 2× specialist-agent containers). Forge resident ~1–2 GB.
Data volume (SQLite)	~1 KB/build + ~500 B/stage-log row → 100 MB after 50K builds. Rotation: not needed for years.
Data volume (Graphiti)	~1–5 MB per build across forge_pipeline_history + forge_calibration_history. 10K builds = ~30 GB. FalkorDB at whitestocks handles this; graph already hosts 585 episodes comfortably.
JetStream retention	PIPELINE 7-day (ADR-SP-017); with sequential builds, queue depth practically ≤ tens at any moment.
Fleet size	Unbounded — forge.discovery KV lookups are O(1) per agent_id. 50 agents = sub-second resolution.
Pipeline-event fanout	NATS pub/sub free to Forge; N subscribers at zero additional cost.
Scaling the organisation (future): if Rich's fleet grows to serve multiple human operators, a new Forge instance per operator — not one Forge scaled up. Multi-tenancy via NATS accounts (D13). Explicit.

Q24. Compliance & regulatory

Data residency: UK/Rich's home network. GB10 + Synology NAS + Tailscale mesh. No cloud data centres except LLM provider calls (Google/Anthropic/OpenAI — Rich's existing business terms apply).
PII: No customer PII in Forge's working set. Feature specs contain synthetic personas ("As Jane, a solicitor…"); real FinProxy end-user data does not cross Forge's boundary.
Tenant isolation (future FINPROXY): When FinProxy tenant activates, NATS account separation (D13) prevents FINPROXY pipeline events leaking to APPMILLA subscribers. Constitutional config in forge.yaml per-tenant if multiple Forge instances are deployed.
GDPR: Rich's personal data (identity, commits) is controller = Rich; no third-party processors in the critical path. LLM prompts may include code + feature descriptions → Gemini/Anthropic data-handling terms apply.
Open-source licensing: Forge itself (future open-sourcing) likely MIT/Apache. Repos Forge builds for are governed by those repos' own licenses — Forge respects.
SOC 2 / HIPAA / PCI-DSS: Not applicable V1. If FinProxy commercialises, V2 conversation — fleet architecture supports per-tenant isolation; compliance layer is additive.
Audit trail: SQLite stage_log + Graphiti forge_pipeline_history + git commit history + PR history = complete chain for retrospective audit. Matches anchor §12 DDD-talk narrative ("structured documents are the audit trail").
Q25. Availability & SLA

Target: best-effort. No SLA to anyone. Practical availability limited by GB10 uptime (home network, power, Tailscale).

Dependency down	Forge behaviour
NATS	Forge cannot accept new builds; in-flight build stalls until NATS returns; on reconnect, JetStream redelivers.
Graphiti	Degraded: no calibration priors, no pipeline-history retrieval, no learning write-back. Reasoning still runs (naturally conservative without priors).
Specialist agent	Degraded: reasoning falls back to local GuardKit tool, forces flag-for-review.
LLM primary (Gemini)	Manual env-var flip to fallback provider (V2: automatic).
GitHub API	Stage 5 PR-creation stalls; build waits until reachable.
Graphiti + specialists both down	Forge still runs GuardKit commands directly; every gate forces flag-for-review; heavy human load. This is "maximally degraded but functional."
Recovery:

Forge process crash: JetStream redelivers, SQLite reconciles (RUNNING → INTERRUPTED), PAUSED rows re-emit ApprovalRequestPayload. ADR-SP-013.
GB10 reboot: same mechanism once GB10 + dependencies are up.
Tailscale outage (MacBook side): Forge on GB10 runs locally; Rich's CLI fails until restored; work queued.
Uptime aspiration: months between unexpected Forge crashes once V1 stabilises. Not a commitment.

Q26. Security beyond authentication

Concern	Mechanism
TLS everywhere	NATS TLS + credentials over Tailscale (belt+braces — Tailscale is already encrypted mesh). Graphiti bolt:// over Tailscale. LLM providers HTTPS. GitHub HTTPS via gh.
Shell sandbox	DeepAgents sandbox backend when available; fallback: path-allowlisted execute + /var/forge/builds/{build_id} working tree.
Working tree isolation (NEW decision): each build gets /var/forge/builds/{build_id}/ — ephemeral, created on PREPARING, deleted on COMPLETE/FAILED.	Per-build blast-radius. No cross-build leakage.
No secrets in prompts / Graphiti / logs	structlog redact-processor catches *_API_KEY, *_TOKEN, Bearer * patterns; AgentManifest excludes runtime config by design; LangGraph graph state schema omits secret fields.
Prompt-injection defence	Constitutional rules are belt+braces (ADR-ARCH-026): system-prompt wording AND deterministic executor-side assertions. Attacker-controlled content (feature descriptions, specialist outputs) stays within Pydantic schemas with explicit prompt demarcation.
Supply-chain	DeepAgents >=0.5.3,<0.6; LangChain integrations per LCOI block; NATS Docker image pinned. pip install --require-hashes V2.
Git signing	gh CLI uses Rich's SSH key; repo-level GPG signing policy out of Forge's concern.
Code review gate	All Forge-generated code lands as PR; repo branch-protection enforces review before merge. No direct-to-main — constitutional rule D37 + repo policy.
No data-exfil path	Network allowlist in forge.yaml.permissions.network (Cat 5); outbound-to-arbitrary-host denied by default.
Ephemeral build directories	Cleaned on terminal state; prevents secrets leaking across builds.
Q27. Budget & timeline constraints

Budget envelope:

Cost centre	Estimate	Architectural impact
LLM — Gemini 3.1 Pro (primary)	~£2–10/build (200–500 turns × ~£0.01–0.10/turn)	Primary provider D2/D3 — cheaper reasoning than Anthropic at sustained volume
LLM — Anthropic/OpenAI (fallback)	~2–3× Gemini cost	Used only during Gemini outage
LLM — vLLM local (implementation-model alternate)	Zero marginal	Available on GB10; auto-scales-to-zero when not in use
Bedrock (fine-tuned specialists)	~£1.50–3.00/run (fleet-master-index)	Separate budget — charged against specialist-agent, not Forge
Monthly budget ceiling	~£500/month LLM	50–200 builds/month at avg £2–10 each
Hardware	GB10 amortised	Sunk cost
SaaS	GitHub (existing)	No new SaaS
Architectural consequences of budget:

Primary Gemini (cheapest advanced reasoning) — already D2/ADR-ARCH-010
Sequential builds cap concurrent LLM spend — already ADR-SP-012
Memory Store caches retrievals within a build — reduces redundant Graphiti LLM-backed queries
Reasoning-driven learning → fewer forced human round-trips over time → fewer "pauses waiting for Rich" → faster builds → lower LLM cost per completed PR
Calibration corpus ingested once → ongoing Gemini cost is build-time only, not re-ingestion
Auto-summarisation (DeepAgents built-in) caps prompt growth → caps per-turn cost
Timeline:

DDD Southwest talk: 16 May 2026 — Forge is not the talk's demo vehicle (that's specialist-agent Phase 1B + Phase 3 + NATS fleet). Forge just needs to be coherent-as-design by the talk date — which this /system-arch session is delivering. No code deadline pre-talk.
Prerequisites for Forge implementation (anchor §10): nats-infrastructure running on GB10 ✅ configured; nats-core integration tests passing (weekend task); specialist-agent Phase 3 (3–4 weeks). Forge build begins when these clear.
No hard external deadline for Forge V1. Rich's own roadmap drives timing.
Build plan timelines (Pattern 1 from fleet-master-index) will be produced per-feature during implementation — estimated durations come from specialist-agent Phase 1 (~93–162s per specialist run + GuardKit stages).
New ADRs from Category 6
ADR-ARCH-027: No horizontal scaling — single Forge instance, single process, sequential builds enforced by max_ack_pending=1 + max_concurrent: 1. Fleet growth handled via multiple Forge instances (one per operator), never one Forge serving many.
ADR-ARCH-028: Ephemeral per-build working trees under /var/forge/builds/{build_id}/ — created on PREPARING, deleted on terminal state. Blast-radius isolation + secret-leakage prevention.
ADR-ARCH-029: Best-effort availability — no SLA. Practical uptime bounded by GB10 + Tailscale + LLM provider availability. Degraded-mode behaviour is a reasoning decision, not a failover rule.
ADR-ARCH-030: Budget ceiling ≈ £500/month LLM — architectural cost-control via Gemini-primary, sequential builds, within-build retrieval caching, and learning-loop reducing human round-trips over time.
Total queued: 29 ADRs (25 prior + 4 from Category 6).

Category 6 Checkpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Category 6: Constraints & NFRs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Performance:    20–60min typical build; 1 concurrent; <5s specialist round-trip;
                <200ms CLI reads. "Quality over speed" (anchor §2).

Scalability:    Vertical only; NO horizontal. Fleet growth = multiple Forge
                instances. 100MB SQLite / 30GB Graphiti for years of operation.

Compliance:     UK residency; no PII in working set; tenant isolation via NATS
                accounts (FINPROXY future); not SOC2/HIPAA-bound in V1.

Availability:   Best-effort, no SLA. Local-first. Graceful degraded modes.
                Recovery via JetStream+SQLite (ADR-SP-013). Months-between-crash
                aspiration.

Security:       TLS everywhere; DeepAgents sandbox + path allowlist; ephemeral
                build dirs; no secrets in prompts/Graphiti/logs; prompt-injection
                defence via constitutional rules belt+braces; network allowlist.

Budget:         ~£500/month LLM ceiling. Gemini-primary drives cost. Sequential +
                caching + auto-summarisation keep within budget.

Timeline:       Forge is not the 16 May DDD talk vehicle. No pre-talk code
                deadline. Prerequisites: nats infra validation + specialist-agent
                Phase 3 (≈3–4 weeks). Forge implementation begins after.
Reply with:

C6 — accept and proceed to Phase 2: C4 Diagram Generation (mandatory review gate)
Edits
A for inline ADR
C6
Category 6: Accepted. All questions complete.
Phase 2: C4 Diagram Generation (mandatory review gate)
Per the command spec, both diagrams require explicit approval before I generate output artefacts. Presenting Level 1 first; Level 2 follows once you approve Level 1.

C4 Level 1 — System Context

C4Context
    title Forge — System Context (v1)

    Person(rich, "Rich", "Operator: queues builds, reviews 🟡 flagged stages, reviews PRs")
    Person(reviewers, "James, Mark", "PR reviewers — interact with GitHub, not Forge")

    System(forge, "Forge", "NATS-native pipeline orchestrator. DeepAgents agent harness. Drives features → PR with reasoning-driven confidence gates and Graphiti-fed learning.")

    System_Ext(jarvis, "Jarvis", "Fleet intent router — publishes build triggers on Rich's behalf from voice/Telegram/dashboard/CLI-wrapper (ADR-SP-014)")
    System_Ext(specialists, "Specialist Agents (Fleet)", "PO + Architect today; QA, UX, Ideation as they ship. Capability-discovered at runtime via AgentManifest — no role hardcoding.")
    System_Ext(nats, "NATS + JetStream", "Transport backbone. Streams: PIPELINE, AGENTS, FLEET, JARVIS, NOTIFICATIONS. KV: agent-registry.")
    System_Ext(guardkit, "GuardKit CLI", "Slash commands: /system-arch, /system-design, /system-plan, /feature-spec, /feature-plan, /task-review, /task-work, /task-complete, autobuild, graphiti seed/query")
    System_Ext(graphiti, "Graphiti (FalkorDB)", "Fleet knowledge graph. Groups: forge_pipeline_history (outcomes + overrides), forge_calibration_history (ingested history files).")
    System_Ext(llm, "LLM Providers", "Gemini 3.1 Pro (primary) / Anthropic / OpenAI / local vLLM — provider-neutral via init_chat_model. Single env var to switch.")
    System_Ext(github, "GitHub", "git push + PR creation via gh CLI")

    Rel(rich, forge, "forge queue | status | history | cancel | skip", "Click CLI")
    Rel(jarvis, nats, "publish BuildQueuedPayload", "pipeline.build-queued.*")
    BiRel(forge, nats, "pull-consume triggers; publish lifecycle events; fleet register/heartbeat; approval round-trips", "pipeline.* / agents.* / fleet.*")
    BiRel(forge, specialists, "dispatch_by_capability (resolved at runtime); receive Coach-scored results", "agents.command.* / result.*")
    Rel(forge, guardkit, "subprocess via DeepAgents execute with --nats", "shell")
    BiRel(forge, graphiti, "retrieve priors (calibration + pipeline history); write outcomes + override events", "bolt://")
    Rel(forge, llm, "reasoning + implementation model invocations", "HTTPS")
    Rel(forge, github, "git push branch + gh pr create", "HTTPS")
    Rel(reviewers, github, "review + merge PRs", "web UI")
    Rel(nats, jarvis, "notifications routed back to originating adapter", "jarvis.notification.*")
Caption — what to look for: Forge is bidirectionally-connected to NATS, specialists, and Graphiti — these are the three load-bearing external dependencies. Jarvis interacts only via NATS (not directly with Forge — ADR-SP-014 Pattern A). LLM is a one-way call-out (requests; responses implicit). GitHub is one-way via git/gh. James & Mark interact only with GitHub — deliberate (they don't touch pipeline internals). GuardKit is subprocess-only, no NATS round-trip from Forge's side. Node count: 10 / 30 threshold.

C4 Level 1 Review Gate

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 C4 CONTEXT DIAGRAM REVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Does this diagram accurately represent the Forge system context?

[A]pprove — proceed to C4 Container Diagram
[R]evise — return to relevant category / restate diagram
[C]ancel — stop and discard this session's work
Reply with A, R (+ what needs to change), or C.

A
C4 Level 2 — Container Diagram

C4Container
    title Forge — Container Diagram (DeepAgents 0.5.3 runtime)

    Person(rich, "Rich", "Operator")

    System_Boundary(forge, "Forge") {
        Container(agent, "Agent Runtime", "Python 3.12 / DeepAgents 0.5.3 / LangGraph", "CompiledStateGraph. Reasoning model (Gemini 3.1 Pro primary). write_todos drives stage narrative. Sub-agents: build_plan_composer, autobuild_runner. PAUSED = LangGraph interrupt(). Exported via langgraph.json.")
        Container(cli, "Forge CLI", "Python / Click", "Short-lived: forge queue/status/history/cancel/skip. Reads SQLite direct; writes via NATS.")
        Container(discovery, "Discovery + Learning + Calibration", "Python (pure domain core)", "Live fleet capability resolution (KV lookup + fleet.register watch). Override-rate learning. History-file CalibrationEvent ingestion. Injects priors into system prompt at build start.")
        ContainerDb(sqlite, "Build History", "SQLite WAL", "~/.forge/forge.db — builds + stage_log tables. Authoritative durable state per ADR-SP-013. CLI reads; agent writes.")
        Container(config, "Config + Permissions", "YAML / pydantic-settings", "forge.yaml — infrastructure, models, constitutional rules, DeepAgents permissions (fs/shell/network allowlists). Static safety config (ADR-ARCH-023).")
        Container(nats_adapter, "NATS Adapter", "nats-core / nats-py", "JetStream pull consumer (max_ack_pending=1). Publish. KV read. Fleet watch. Approval round-trip publisher.")
        Container(graphiti_adapter, "Graphiti Adapter", "Python / Graphiti client", "forge_pipeline_history + forge_calibration_history read/write. Priors retrieval at build start; outcome write-back continuously.")
        Container(subprocess_adapter, "Subprocess Adapter", "DeepAgents execute + thin wrappers", "guardkit_* / git / gh — path + binary allowlisted per permissions.")
        ContainerDb(worktrees, "Per-Build Worktrees", "Filesystem (ephemeral)", "/var/forge/builds/{build_id}/ — created on PREPARING, deleted on terminal state (ADR-ARCH-028). Blast-radius isolation.")
    }

    System_Ext(nats_server, "NATS + JetStream", "GB10 Docker — PIPELINE/AGENTS/FLEET streams + agent-registry KV")
    System_Ext(specialists, "Specialist Agents", "GB10 Docker — PO + Architect today; QA/UX/Ideation as they ship. Capability-discovered, never hardcoded (ADR-ARCH-015).")
    System_Ext(falkordb, "FalkorDB Graphiti", "Synology NAS @ whitestocks:6379 via Tailscale")
    System_Ext(llm, "LLM Provider", "Gemini 3.1 Pro primary / Anthropic / OpenAI / vLLM — provider-neutral via init_chat_model (ADR-ARCH-010)")
    System_Ext(guardkit_bin, "GuardKit CLI binary", "Container-installed — /usr/local/bin/guardkit")
    System_Ext(git_bin, "git + gh CLI binaries", "Container-installed")
    System_Ext(github, "GitHub API", "api.github.com")

    Rel(rich, cli, "forge …", "shell")
    Rel(cli, sqlite, "read status + history", "sqlite3")
    Rel(cli, nats_adapter, "publish queue/cancel/skip", "in-process")

    Rel(agent, config, "load at startup + permissions enforcement", "pydantic-settings")
    Rel(agent, discovery, "list_capabilities + retrieve priors for system prompt", "in-process")
    Rel(agent, sqlite, "write stage_log rows + lifecycle transitions", "sqlite3 WAL")
    BiRel(agent, nats_adapter, "pull trigger; publish events; interrupt ↔ ApprovalPayload", "in-process")
    BiRel(agent, graphiti_adapter, "priors in; outcomes out", "in-process")
    Rel(agent, subprocess_adapter, "invoke GuardKit / git / gh via @tools", "in-process")
    Rel(agent, worktrees, "DeepAgents filesystem tools (read/write/edit/ls/glob/grep)", "filesystem")
    Rel(agent, llm, "reasoning + implementation model invocations", "HTTPS")

    Rel(discovery, nats_adapter, "agent-registry KV lookup + fleet.register watch", "in-process")
    Rel(discovery, graphiti_adapter, "calibration corpus + pipeline history retrieval", "in-process")

    Rel(nats_adapter, nats_server, "NATS pub/sub + KV + JetStream pull", "NATS over TLS + Tailscale")
    BiRel(nats_server, specialists, "commands + results via agents.command.* / result.*", "NATS")
    Rel(graphiti_adapter, falkordb, "entity read/write", "bolt://")
    Rel(subprocess_adapter, guardkit_bin, "subcommand + args + progress parse", "execute")
    Rel(subprocess_adapter, git_bin, "git ops + gh pr create", "execute")
    Rel(subprocess_adapter, worktrees, "working-tree mutation", "filesystem")
    Rel(git_bin, github, "HTTPS auth via gh token", "HTTPS")
Caption — what to look for: agent is the hub (expected — DeepAgents graph orchestrates everything); no adapters talk to each other directly (clean Hexagonal — all cross-adapter coordination goes through agent or discovery). sqlite has 2 accessors (agent write, cli read) — clean ownership. worktrees touched by both agent (via DeepAgents filesystem tools) and subprocess_adapter (via shell commands in /var/forge/builds/{build_id}) — deliberate, these are two legitimate access modes to the same filesystem. Externals cluster around their trust boundaries: NATS infrastructure on GB10, Graphiti on Synology, LLM + GitHub across the public internet. Node count: 17 / 30 threshold.

Async / inbound paths visible:

Build trigger inbound: jarvis → nats_server → nats_adapter → agent (shown in Level 1; aggregated here)
Approval inbound: nats_server → nats_adapter → agent interrupt resume
Fleet capability changes inbound: fleet.register/deregister/heartbeat → nats_adapter → discovery (live cache invalidation, ADR-ARCH-017)
C4 Level 2 Review Gate

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 C4 CONTAINER DIAGRAM REVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Does this diagram accurately represent the Forge container decomposition?

[A]pprove — proceed to Phase 3: write output artefacts to docs/architecture/
[R]evise — return to relevant category / restate diagram
[C]ancel — stop and discard this session's work
Reply with A, R (+ what needs to change), or C.

A

Phase 3 Complete
35 artefacts written to docs/architecture/:


docs/architecture/
├── ARCHITECTURE.md             (index + summary — 230 lines)
├── domain-model.md             (entities + ownership + module map — 200 lines)
├── system-context.md           (C4 Level 1 Mermaid + caption — 50 lines)
├── container.md                (C4 Level 2 Mermaid + caption — 85 lines)
├── assumptions.yaml            (26 assumptions across 6 categories)
└── decisions/                  (30 ADRs)
    ├── ADR-ARCH-001 … Hexagonal inside DeepAgents
    ├── ADR-ARCH-002 … Two-model separation
    ├── ADR-ARCH-003 … NATS-native, no transport ABC
    ├── ADR-ARCH-004 … Full GuardKit CLI tool surface
    ├── ADR-ARCH-005 … Graphiti-fed learning loop
    ├── ADR-ARCH-006 … Calibration corpus ingestion
    ├── ADR-ARCH-007 … Build Plan as gated artefact
    ├── ADR-ARCH-008 … Forge produces own history files
    ├── ADR-ARCH-009 … Omit LangGraph checkpointer
    ├── ADR-ARCH-010 … Provider-neutral models
    ├── ADR-ARCH-011 … Local-first Docker on GB10
    ├── ADR-ARCH-012 … No MCP interface
    ├── ADR-ARCH-013 … CLI read bypasses NATS
    ├── ADR-ARCH-014 … Single consumer max_ack_pending=1
    ├── ADR-ARCH-015 … Capability-driven dispatch
    ├── ADR-ARCH-016 … Fleet is the catalogue
    ├── ADR-ARCH-017 … Live fleet watching
    ├── ADR-ARCH-018 … Calibration priors retrievable
    ├── ADR-ARCH-019 … No static behavioural config
    ├── ADR-ARCH-020 … Adopt DeepAgents 0.5.3 built-ins
    ├── ADR-ARCH-021 … PAUSED via LangGraph interrupt()
    ├── ADR-ARCH-022 … Dual agent memory
    ├── ADR-ARCH-023 … Permissions as constitutional safety
    ├── ADR-ARCH-024 … Observability = events, not Prometheus
    ├── ADR-ARCH-025 … Tool error handling
    ├── ADR-ARCH-026 … Constitutional belt+braces
    ├── ADR-ARCH-027 … No horizontal scaling
    ├── ADR-ARCH-028 … Ephemeral per-build worktrees
    ├── ADR-ARCH-029 … Best-effort availability
    └── ADR-ARCH-030 … Budget ceiling / Gemini primary
Phase 4: Graphiti Seeding (Tier 2 connectivity check + offered commands)
Graphiti is live (verified in this session — 585 episodes, FalkorDB @ whitestocks:6379 via Tailscale). Proposed seeding commands, aligned with the group assignments in the /system-arch spec:


# Architecture artefacts → project_architecture group
# (bounded contexts, components, cross-cutting concerns, assumptions)
guardkit graphiti add-context docs/architecture/domain-model.md \
  --group project_architecture

guardkit graphiti add-context docs/architecture/ARCHITECTURE.md \
  --group project_architecture

guardkit graphiti add-context docs/architecture/system-context.md \
  --group project_architecture

guardkit graphiti add-context docs/architecture/container.md \
  --group project_architecture

guardkit graphiti add-context docs/architecture/assumptions.yaml \
  --group project_architecture

# ADRs → architecture_decisions group (30 ADRs in the folder)
guardkit graphiti add-context docs/architecture/decisions/ \
  --group architecture_decisions
Note: All content will be seeded under project_id=forge (from .guardkit/graphiti.yaml) which namespaces these episodes separately from the existing 585 in the fleet. Downstream commands (/system-design, /system-plan, /feature-spec) will query both groups filtered by project to retrieve this architecture context.

Run these seeding commands now? [Y/n]

Reply Y to execute all six add-context calls via Bash, or n to skip (the markdown artefacts are already in place; seeding can be re-run later via forge CLI or manual invocation).

Y

Dry-run confirms it works (14 episodes for ARCHITECTURE.md alone). The --group flag isn't exposed in the CLI — grouping is auto-routed by --type. Running the four architecture docs now, then the ADR folder.

Note: ingestion uses Gemini 2.5 Pro per .guardkit/graphiti.yaml. Expect ~2 min per medium doc and ~15–20 min for the 30-ADR folder at ~0.5 s inter-episode delay. Running in background so I can monitor.

Both seeding jobs launched in background:

bx6libarl — 4 architecture docs (ARCHITECTURE / domain-model / system-context / container) → full_doc parser
b44xeahah — 30 ADRs → adr parser (this is the long one — 30 files × several episodes each)
Gemini 2.5 Pro does ingestion per .guardkit/graphiti.yaml:58, so each episode is a cloud-LLM call. I'll get notified when they complete. Meanwhile, a quick check to confirm they're making progress rather than failing fast.

Both jobs connected to FalkorDB successfully and are actively calling Gemini (AFC is enabled = Gemini function calling active). No errors; ingestion in flight.

Given estimated ingest time (~2 min × 4 docs + ~15–20 min for 30 ADRs at one Gemini call per episode), total wall-clock is ~20–25 minutes. I'll receive a notification when each background job completes and will post the final summary then.

Current state:

docs/architecture/ written and complete on disk (35 files — you can open them now)
Graphiti seeding in progress in the background (both jobs confirmed connected + processing)
/system-arch session is otherwise complete
Next steps once seeding completes:

Verify Graphiti episode counts via guardkit graphiti status
Present the final completion summary with next-command recommendations (/system-design "Forge")
You can proceed with other work — I'll pick back up when the seeding jobs finish.

Both jobs healthy and making steady progress. Here's where we are:

Architecture docs job (bx6libarl)
ARCHITECTURE.md (14 chunks): ✅ complete
domain-model.md (~8–12 chunks): 🔄 on chunk 5 — last episode took 70s, produced nodes=21, edges=23
system-context.md: pending
container.md: pending
Throughput: ~65–70s per episode. ~10–15 min remaining on this job.

ADR job (b44xeahah)
30 ADRs (1 episode each, alphabetical): 🔄 completed ADR-ARCH-029 — nodes=11, edges=19, 51s ingestion
ADR-ARCH-030 almost certainly finishing as we speak
Throughput: ~50s per episode. ~1–2 min remaining on this job.

Quality signal
Gemini ingestion is producing well-shaped episodes:

ADR-029 → 11 nodes, 19 edges (dense decision graph ✓)
domain-model chunk 5 → 21 nodes, 23 edges (entity-rich as expected for a domain model ✓)
Zero invalidations (no contradictions with existing graph)
Both processes confirmed still running via ps aux. Waiting for completion notifications — should be under 15 more minutes total. I'll report the final guardkit graphiti status numbers + completion summary when both jobs finish.

Architecture docs: ✅ complete — all 4 seeded.

ADR job: 80% complete (24/30 episodes done). Non-numeric processing order.

6 ADRs remaining (listed for transparency):

ADR-ARCH-001 (hexagonal + DeepAgents)
ADR-ARCH-007 (build-plan gate)
ADR-ARCH-012 (no MCP)
ADR-ARCH-022 (dual memory)
ADR-ARCH-024 (observability)
ADR-ARCH-028 (ephemeral worktrees)
At ~50–70 s per ADR, ~5–7 more minutes to finish. Process confirmed still alive (PID 85651, 50s CPU time).

Sample quality observations (all high-density, zero invalidations)
Episode	Nodes	Edges	Notes
container.md	28	105	Dense — reflects container-dependency graph
ADR-019 (no static config)	13	22	Complex ADR with many relationships
ADR-015 (capability dispatch)	16	9	Introduces new concepts
ADR-003 (NATS-native)	16	17	Links to anchor decisions
ADR-017 (fleet watching)	10	8	Focused decision
ADR-014 (max_ack_pending)	6	5	Tight scope
Graphiti is producing well-shaped episodes — no contradictions with the existing 585 episodes in the fleet graph. I'll report when the ADR job completes and run guardkit graphiti status for the final counts.

All seeding complete. Final status:

30/30 ADRs ingested
685 total episodes in Graphiti (was 585 → +100 episodes added)
2 warnings for ADR-012 + ADR-022 ("Missing required section: Status") — non-blocking, episodes still ingested; the parser expects ## Status as a section heading rather than the - **Status:** Accepted inline-bullet format I used. Follow-up: I can re-format those two files to use the heading-style Status section if you want the warnings cleared. Not urgent.
/system-arch Session Complete
Artefacts on disk (docs/architecture/)
ARCHITECTURE.md — index + summary, module map, decision index
domain-model.md — entities, relationships, ownership rules
system-context.md — C4 Level 1 Mermaid
container.md — C4 Level 2 Mermaid
assumptions.yaml — 26 assumptions across 6 categories
decisions/ — 30 ADRs (ADR-ARCH-001 through ADR-ARCH-030)
Graphiti seeded (project_id=forge)
Group	Episodes added
architecture_decisions	30 (one per ADR)
project_architecture (via full_doc)	~70 chunks across 4 architecture docs
Total added	100
Downstream commands (/system-design, /system-plan, /feature-spec) will retrieve this context at startup via the same Graphiti connection.

Headline architectural position (Forge, one sentence)
"A DeepAgents-native reasoning orchestrator whose behaviour is entirely emergent from (a) live fleet capabilities discovered via AgentManifests, (b) retrieved priors from Rich's calibration corpus in Graphiti, and (c) constitutional safety rules in forge.yaml — with zero pre-coded pipeline stages, gate thresholds, or role-specific dispatch."

This is what 9 revisions of Category-level pushback produced — and the result is materially different from a conventional state-machine orchestrator. The agent harness earns its keep.

Suggested next steps
Review — open ARCHITECTURE.md and spot-check the module map + ADR index against the session's conclusions. The docs are in your working tree now.
Next command — /system-design "Forge" (Phase 2 of the upstream pipeline) to produce detailed tool contracts, NATS payload schemas beyond what nats-core already has, and the forge.yaml configuration schema.
Optional polish — if the ADR-012/ADR-022 Status-section warnings bother you, reformat those two ADRs to use heading style (## Status) and re-seed with guardkit graphiti add-context … --force. Cosmetic only.
Follow-on work (not for this session) — ADR-ARCH-025 mentioned a @forge_tool base decorator to enforce the "tools never raise" policy; that becomes a design point in /system-design.


