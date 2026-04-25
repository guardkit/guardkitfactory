/feature-plan "Mode A Greenfield End-to-End" \
  --context features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md
I'll orchestrate the feature plan for "Mode A Greenfield End-to-End". Let me start by reading the context file and then proceed through the workflow.

Read mode-a-greenfield-end-to-end_summary.md
Feature spec read. This is FEAT-FORGE-007, the capstone Mode A greenfield orchestration with 47 scenarios across 8 stages. High estimated complexity (~9/10) with deep integration across FEAT-FORGE-001 through FEAT-FORGE-006.

Proceeding with Step 2 — Review Scope Clarification (Context A).

Agent:Collect review scope clarifications
IN
Execute clarification for feature planning.

CONTEXT TYPE: review_scope

FEATURE: Mode A Greenfield End-to-End (FEAT-FORGE-007)

Capstone feature for Forge's Mode A greenfield orchestration. Drives a single one-line product brief through an 8-stage chain (product-owner delegation → architect delegation → architecture → system design → per-feature specification → per-feature planning → autobuild → pull-request review) under one supervised build.

Key concerns:
- Stage-ordering invariants (no downstream dispatch before prerequisite approval)
- Forward propagation of stage outputs into next stage's context
- Async-subagent dispatch pattern for long-running autobuild
- Constitutional belt-and-braces rule (PR review mandatory human approval at prompt AND executor layers)
- Crash recovery as retry-from-scratch with durable history as authoritative source
- CLI steering (cancel/skip semantics, varied per stage)
- Pause isolation across simultaneously paused builds
- Idempotent first-write-wins on duplicate responses
- Correlation-identifier threading, calibration-priors snapshot stability, per-feature artefact attribution

ESTIMATED COMPLEXITY: 9/10 (capstone composition feature integrating 6 upstream features)

UPSTREAM DEPENDENCIES:
- FEAT-FORGE-001: Pipeline State Machine
- FEAT-FORGE-002: NATS Fleet Integration
- FEAT-FORGE-003: Specialist Agent Delegation
- FEAT-FORGE-004: Confidence-Gated Checkpoint Protocol
- FEAT-FORGE-005: GuardKit Command Invocation Engine
- FEAT-FORGE-006: Infrastructure Coordination

SCENARIO COUNTS: 47 total (8 key examples, 6 boundary, 9 negative, 11 edge case, 4 smoke, 4 regression, 3 security, 3 concurrency, 6 data integrity, 4 integration)

FLAGS:
  --no-questions: false
  --with-questions: false
  --defaults: false
  --answers: (none)

Ask about:
1. Review focus (all/technical/architecture/performance/security)
2. Trade-off priority (speed/quality/cost/maintainability/balanced)
3. Any specific concerns to address (e.g., specific upstream integration risks, async-subagent stability, constitutional invariant enforcement)

Return ClarificationContext with review preferences.
Read display.py
Read FEAT-FORGE-002
Read tasks
The clarification agent is asking review-scope questions. Let me present them to you for response.

Review Scope Clarification (Context A)
Q1 — Review Focus

A - All (full coverage across all dimensions)
B - Technical (implementation correctness, data flow, concurrency)
C - Architecture (stage-ordering invariants, forward propagation design, async-dispatch pattern)
D - Performance (autobuild throughput, pause isolation overhead, idempotency at scale)
E - Security (constitutional rule enforcement, human-approval bypass resistance, NATS message integrity)
Default: A

Q2 — Trade-off Priority

S - Speed
Q - Quality (correctness, exhaustive invariant enforcement)
C - Cost
M - Maintainability
B - Balanced
Default: B

Q3 — Specific Concerns

Constitutional belt-and-braces (PR review mandatory human approval)
Async-subagent dispatch stability during long-running autobuild
Stage-ordering invariants (no downstream dispatch before prerequisite approval)
Forward propagation of stage outputs
Pause isolation across simultaneously paused builds
Idempotent first-write-wins on duplicate responses
Correlation-identifier threading and calibration-priors snapshot stability
No specific concern — review all equally
R - Recommend (let review determine highest-risk area)
Default: R

Please reply with your answers (e.g. 1:A 2:Q 3:1), or defaults to accept all defaults.

feature-spec-FEAT-FORGE-007-history.md#1952-1953
defaults
Defaults captured: Focus=All, Tradeoff=Balanced, Concerns=Recommend. Proceeding to Step 3 — creating the review task.

task-create skill
Creating the review task. Let me first check the tasks directory structure.

Bash List task directories
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/tasks/ 2>/dev/null && ls /home/richardwoollcott/Projects/appmilla_github/forge/tasks/backlog/ 2>/dev/null | head -30

OUT
backlog
completed
design_approved
in_review
forge-v2-doc-alignment
nats-fleet-integration
TASK-NFI-001-extend-forge-config-fleet-pipeline-sections.md
TASK-NFI-002-define-forge-manifest-constant.md
TASK-REV-CG44-plan-confidence-gated-checkpoint-protocol.md
TASK-REV-NF20-plan-nats-fleet-integration.md
Bash Check for existing FORGE-007 tasks
IN
find /home/richardwoollcott/Projects/appmilla_github/forge/tasks -name "*forge-007*" -o -name "*mode-a*" -o -name "*greenfield*" 2>/dev/null | head -20

OUT
(Bash completed with no output)
Bash List all task directories
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/tasks/backlog/ /home/richardwoollcott/Projects/appmilla_github/forge/tasks/in_review/ /home/richardwoollcott/Projects/appmilla_github/forge/tasks/completed/ 2>/dev/null

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/tasks/backlog/:
forge-v2-doc-alignment
nats-fleet-integration
TASK-NFI-001-extend-forge-config-fleet-pipeline-sections.md
TASK-NFI-002-define-forge-manifest-constant.md
TASK-REV-CG44-plan-confidence-gated-checkpoint-protocol.md
TASK-REV-NF20-plan-nats-fleet-integration.md

/home/richardwoollcott/Projects/appmilla_github/forge/tasks/completed/:
TASK-1466
TASK-768F
TASK-ADR-REVISE-021-E7B3
TASK-CHORE-E4A1
TASK-DOC-B2A4
TASK-E90D
TASK-FVD1
TASK-FVD2
TASK-FVD3
TASK-FVD4
TASK-REV-A1F2
TASK-REV-A7D3
TASK-REV-C3E7
TASK-REV-D90D

/home/richardwoollcott/Projects/appmilla_github/forge/tasks/in_review/:
project-scaffold
TASK-REV-F1B8
TASK-SPIKE-C1E9
TASK-SPIKE-D2F7
Read TASK-REV-NF20-plan-nats-fleet-integration.md
I have the format. Creating the review task.

Write TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md
161 lines
---
id: TASK-REV-MAG7
title: "Plan: Mode A Greenfield End-to-End"
task_type: review
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
complexity: 9
tags: [planning, review, mode-a, greenfield, orchestration, capstone, feat-forge-007]
feature_spec: features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md
feature_id: FEAT-FORGE-007
upstream_dependencies:
  - FEAT-FORGE-001  # Pipeline State Machine & Configuration
  - FEAT-FORGE-002  # NATS Fleet Integration
  - FEAT-FORGE-003  # Specialist Agent Delegation
  - FEAT-FORGE-004  # Confidence-Gated Checkpoint Protocol
  - FEAT-FORGE-005  # GuardKit Command Invocation Engine
  - FEAT-FORGE-006  # Infrastructure Coordination
clarification:
  context_a:
    timestamp: 2026-04-25T00:00:00Z
    decisions:
      focus: all
      tradeoff: balanced
      specific_concerns: null
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan Mode A Greenfield End-to-End (FEAT-FORGE-007)

## Description

Decision-making review for **FEAT-FORGE-007 — Mode A Greenfield End-to-End**, the
capstone composition feature for Forge. Specifies how a single one-line product
brief is driven through the eight-stage chain — product-owner delegation,
architect delegation, architecture, system design, per-feature specification,
per-feature planning, autobuild, and pull-request review — under one supervised
build.

This review composes six upstream features (FEAT-FORGE-001 through
FEAT-FORGE-006) without introducing new transitions; it specifies the *order*,
*forward propagation*, *dispatch pattern*, *steering surface*, and *integrity
invariants* that bind them together. It must surface the recommended technical
approach, architecture boundaries, risk analysis, effort estimation, and a
subtask breakdown that downstream `/feature-build` can execute against.

## Scope of Analysis

Review must cover **all areas (full sweep)** with a **balanced** trade-off
priority. No specific concerns pre-flagged — surface highest-risk areas
organically.

Concrete areas to examine:

1. **Stage-ordering invariants**: enforcement that no downstream stage may be
   dispatched before its prerequisite stage's gate has resolved, and how this
   composes with FEAT-FORGE-004's gate-mode taxonomy.
2. **Forward propagation**: how each stage's approved output is threaded into
   the next stage's `--context` flag construction (FEAT-FORGE-005), without
   leaking unapproved or stale artefacts.
3. **Async-subagent dispatch**: the long-running autobuild dispatch pattern
   (AsyncSubAgent + state channel) — supervisor responsiveness during the run,
   live wave/task progress as advisory, and SQLite history as authoritative.
4. **Constitutional belt-and-braces**: pull-request review pinned to mandatory
   human approval at *both* prompt and executor layers; verification that the
   executor refuses to honour an auto-approve directive even if a prompt
   misconfiguration emits one.
5. **Crash recovery**: retry-from-scratch semantics; durable-history precedence
   over the advisory live state channel on resume; per-feature artefact
   attribution preserved across restart.
6. **CLI steering surface**: cancel → synthetic reject mapping, skip honoured
   on non-constitutional stages and refused on PR review, mid-flight directive
   queueing.
7. **Pause isolation**: simultaneous paused builds on independent channels;
   approval routing keyed by build identifier; idempotent first-write-wins on
   duplicate or simultaneous responses.
8. **Per-feature sequencing**: per-feature autobuild ordering within a single
   build; one PR per feature; aggregate session-outcome chain.
9. **Concurrency**: two concurrent builds with isolated channels and task IDs;
   supervisor dispatching second build's stage during first build's autobuild.
10. **Integrity invariants**: correlation-identifier threading queue→terminal;
    calibration-priors snapshot stability for the duration of one build;
    notification-publish failure does not regress approval.
11. **Security**: belt-and-braces against misconfigured prompts; specialist
    override claim ignored at gating; subprocess worktree-allowlist confinement
    (inherited from FEAT-FORGE-005).
12. **Test strategy**: deterministic async tests for the eight-stage chain;
    crash-injection tests for retry-from-scratch; concurrency tests for
    pause isolation; smoke + regression coverage for the four canonical paths.

## Acceptance Criteria

- [ ] Technical approach analysed with explicit composition-vs-extension
      decision for each upstream feature, with pros/cons
- [ ] Stage-ordering invariant enforcement strategy documented (where the
      check lives, how it composes with FEAT-FORGE-004 gate modes)
- [ ] Forward-propagation contract specified per stage transition
      (input artefact → next-stage `--context`)
- [ ] Async-subagent dispatch boundaries documented (supervisor /
      AsyncSubAgent / state-channel responsibilities, history as truth)
- [ ] Constitutional belt-and-braces verification path documented
      (prompt-layer + executor-layer assertions)
- [ ] Crash-recovery semantics specified (retry-from-scratch with durable
      history as authoritative source; advisory live state)
- [ ] CLI-steering matrix documented (cancel/skip per stage class,
      including PR-review refusal)
- [ ] Pause-isolation guarantees specified (per-build channels,
      first-write-wins idempotency)
- [ ] Risk register produced covering composition risks (race conditions,
      stale-context propagation, async-dispatch flakiness, constitutional
      bypass, recovery divergence)
- [ ] Subtask breakdown with dependencies, complexity (1–10), and
      parallel-wave organisation
- [ ] Integration contracts identified for cross-task data dependencies
- [ ] Smoke (4) and regression (4) coverage strategy defined
- [ ] Decision checkpoint presented: [A]ccept / [R]evise / [I]mplement / [C]ancel
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Clarification Context

### Context A — Review Scope (collected at /feature-plan invocation)

- **Focus**: All (full sweep across architecture, technical, performance, security)
- **Trade-off priority**: Balanced (no single dimension dominates)
- **Specific concerns**: None pre-flagged — surface highest-risk areas during analysis

### Context B — Implementation Preferences

To be collected at the [I]mplement decision checkpoint, if user proceeds to
implementation. Will determine:
- Approach selection (which recommended option to follow)
- Execution preference (parallel waves vs sequential, Conductor usage)
- Testing depth (TDD / standard / minimal)

## Implementation Notes

This feature is the *capstone* of the Forge build. It introduces no new
transitions or transport primitives — every capability it relies on already
exists in FEAT-FORGE-001 through FEAT-FORGE-006. The plan therefore must focus
on *composition*: order, propagation, dispatch shape, steering, and invariants.

The review must be careful to preserve the substrate-feature contracts:
- FEAT-FORGE-001's state machine and durable history are *the* source of truth
- FEAT-FORGE-002's NATS channels carry advisory progress, not authoritative state
- FEAT-FORGE-003's specialist delegation has its own degraded-mode behaviour
- FEAT-FORGE-004's confidence gates compose; this feature does not redefine them
- FEAT-FORGE-005's subprocess contract is reused verbatim per stage
- FEAT-FORGE-006's memory/priors/test/PR helpers are inherited

If the review identifies a gap in any substrate feature, it must call this out
explicitly rather than silently extending scope.

## Test Execution Log

[Automatically populated by /task-review and downstream /task-work]
Review task created. Now executing Step 5 — the decision review.

✅ Task Created: TASK-REV-MAG7
📁 tasks/backlog/TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md

Proceeding to Step 5 — Execute /task-review with decision mode.

task-review skill
The task-review skill is loaded. Context A was already collected by /feature-plan. I'll proceed through the review phases. Let me check Graphiti availability and read the upstream feature specs for context.

Bash Check feature specs and graphiti config
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/features/ 2>/dev/null && cat /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/graphiti.yaml 2>/dev/null || echo "no graphiti config"

OUT
confidence-gated-checkpoint-protocol
guardkit-command-invocation-engine
infrastructure-coordination
mode-a-greenfield-end-to-end
nats-fleet-integration
pipeline-state-machine-and-configuration
specialist-agent-delegation
# Graphiti Knowledge Graph Configuration
#
# This file configures the Graphiti integration for GuardKit.
# FalkorDB runs on the Synology DS918+ NAS, accessible via Tailscale.
#
# LLM Endpoint Switching:
#   To switch between GB10 and MacBook LLM, toggle the llm_provider/llm_base_url/
#   llm_model settings below. See docs/reference/graphiti-macbook-offload.md for
#   full setup instructions and the toggle script.
#
# All settings can be overridden via environment variables:
#   - GRAPHITI_ENABLED: Enable/disable integration
#   - GRAPH_STORE: Graph backend ('falkordb' or 'neo4j')
#   - FALKORDB_HOST: FalkorDB host
#   - FALKORDB_PORT: FalkorDB port
#   - GRAPHITI_TIMEOUT: Connection timeout in seconds
#
# FalkorDB on NAS:
#   ssh richardwoollcott@whitestocks
#   cd /volume1/guardkit/docker
#   sudo docker-compose -f docker-compose.falkordb.yml up -d
#
# FalkorDB Browser UI: http://whitestocks:3000

# Project ID for namespace prefixing
# This ensures knowledge persists across directory moves/renames
project_id: forge

# Enable Graphiti integration (set to false to disable)
enabled: true

# Graph database backend
graph_store: falkordb

# FalkorDB connection (Synology DS918+ NAS via Tailscale)
falkordb_host: whitestocks
falkordb_port: 6379

# Connection settings
timeout: 30.0

# Maximum concurrent episode creation calls during init seeding.
# Bounds asyncio.gather parallelism to avoid LLM rate limits.
# Range: 1-10 (1 = sequential, 3 = default)
max_concurrent_episodes: 3

# LLM provider for Graphiti entity extraction
# Options: openai (default), vllm, ollama, gemini
#
# GB10 local vLLM (FP8) — default. Free; no per-request cost.
# Switch to Gemini only while GB10 is busy training (see fallback below).
# Cost note (2026-04-20): Gemini 2.5 Pro accumulated ~£10/day during normal
# Graphiti ingestion. See: .guardkit/llm-provider-switching.md (guardkit repo).
#
# --- GB10 (vLLM, FP8) — ACTIVE ---
llm_provider: vllm
llm_base_url: http://promaxgb10-41b1:8000/v1
llm_model: neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic
#
# --- Fallback: Google Gemini (cloud, paid) — uncomment when GB10 training ---
# Requires GOOGLE_API_KEY env var and `pip install guardkit-py[gemini]`.
#llm_provider: gemini
#llm_model: gemini-2.5-pro
#
# --- Fallback: MacBook Pro M2 Max (Ollama, Q4_K_M) ---
#llm_provider: ollama
#llm_base_url: http://richards-macbook-pro.tailebf801.ts.net:8000/v1
#llm_model: qwen2.5:14b-instruct-q4_K_M
llm_max_tokens: 4096  # Cap output tokens; prevents 16384 default exceeding 32K context (TASK-REV-84A7)

# Embedding provider for Graphiti vector search
# Options: openai (default), vllm, ollama
embedding_provider: vllm
embedding_base_url: http://promaxgb10-41b1:8001/v1

# Embedding model for semantic search
# Supported by openai, vllm, and ollama providers
embedding_model: nomic-embed-text-v1.5

# Embedding dimension is resolved from KNOWN_EMBEDDING_DIMS
# based on embedding_model above. Set explicitly only to override
# (e.g., for Matryoshka truncation).

# Group IDs for organizing knowledge
# These create separate namespaces in the knowledge graph.
# Groups align with the /system-arch, /system-design, /system-plan, /feature-spec
# pipeline: architecture artefacts, ADRs, and technology decisions are seeded
# into these namespaces so downstream commands can query them.
group_ids:
  - project_architecture    # Bounded contexts, components, cross-cutting concerns, assumptions
  - architecture_decisions  # ADRs and design rationale
  - project_decisions       # Technology and infrastructure decisions
  - command_workflows       # GuardKit command patterns and usage

# Deprecated fields (kept for backwards compatibility)
host: localhost
port: 8000
Graphiti [search_nodes]Mode A greenfield orchestration eight-st…
OUT
{"result":{"message":"Nodes retrieved successfully","nodes":[{"uuid":"b05812a2-512d-4d1b-8248-b0d60e2627b7","name":"Mode A (Greenfield)","labels":["Entity"],"created_at":"2026-04-18T22:38:38.265219+00:00","summary":"Mode A (Greenfield) involves invoking various GuardKit slash commands such as /system-arch, /system-design, /feature-spec, and /feature-plan. It also includes autobuild and task-review functionalities. Forge produces its own history files, which serve as calibration data for future projects.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"397f2596-c0e7-4a53-8a1b-8e71af1a945f","name":"Mode C (Review-Fix)","labels":["Entity"],"created_at":"2026-04-18T22:38:38.265229+00:00","summary":"Mode C (Review-Fix) is supported via `guardkit_task_review`, `guardkit_task_work`, and `guardkit_task_complete` tools.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"45b61273-a988-4552-aa80-5b1e49719649","name":"build_plan_composer","labels":["Entity"],"created_at":"2026-04-18T22:30:14.361876+00:00","summary":"The build_plan_composer is a sub-agent of Forge that generates build plans in canonical Pattern-1 structure. These plans serve as training data for future automation, ensuring consistency and enabling self-learning. It is part of Forge's two-model architecture, where the implementation model executes tasks.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"4c5ce361-9c63-4036-96c9-2f0ede588bc8","name":"Build Plans","labels":["Entity"],"created_at":"2026-04-18T22:30:14.361861+00:00","summary":"Forge automatically generates build plans in a canonical Pattern-1 structure. Initially, these plans require mandatory human approval, but trust is graduated. After a configurable number of consecutive approvals without edits and a low rejection rate, the system relaxes to confidence-gated approval.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"4eb0fb7c-b4e9-4da8-a89e-3dbbabc711bc","name":"Mode B (Feature)","labels":["Entity"],"created_at":"2026-04-18T22:38:38.265224+00:00","summary":"Mode B (Feature) involves using GuardKit commands like /feature-spec and /feature-plan, alongside autobuild, to iterate on features. This mode is supported by tools like guardkit_feature_spec, guardkit_feature_plan, and guardkit_autobuild.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"d07d7561-2f4a-4dc5-b0a8-cf45b895d6f5","name":"StageCompletePayload","labels":["Entity"],"created_at":"2026-04-23T20:37:59.402258+00:00","summary":"StageCompletePayload is one of the pipeline payload types used in Forge's API contract. It was reconciled and shipped in nats-core ≥ 0.2.0 along with BuildPausedPayload, BuildResumedPayload. Prior to this, Forge carried the canonical shape locally in `forge.adapters.nats._interim_payloads.py`.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"014fc180-1946-4c3a-a8f0-6ccc9b2cb5f3","name":"BuildCancelledPayload","labels":["Entity"],"created_at":"2026-04-23T20:37:59.402278+00:00","summary":"Payload type used in pipeline events for cancelled builds. Defined locally in `forge.adapters.nats._interim_payloads.py` until `nats-core ≥ 0.2.0` ships reconciled types.","group_id":"forge__project_decisions","attributes":{}},{"uuid":"ddf182f6-329e-4c27-b8ea-5628e4b3dc76","name":"PRAGMA journal_mode","labels":["Entity"],"created_at":"2026-04-23T20:09:47.004520+00:00","summary":"Set to WAL mode for SQLite database connections.","group_id":"forge__project_decisions","attributes":{}}]}}
Graphiti [search_memory_facts]async subagent state channel autobuild s…
OUT
{"result":{"message":"Facts retrieved successfully","facts":[{"uuid":"c4fdf1b4-b16e-4dd9-a73e-35b4b9eaaf3a","group_id":"forge__project_decisions","source_node_uuid":"5f9b6c29-d182-4828-b02a-51ece4e76069","target_node_uuid":"6edd2ad4-e730-480d-a7f9-ac22ec5db087","created_at":"2026-04-23T20:18:06.660705Z","name":"HAS_STATE_CHANNEL","fact":"`autobuild_runner` has an `async_tasks` state channel.","episodes":["cf101a24-0335-41a9-b41f-522b3bda5b7d"],"expired_at":null,"valid_at":"2026-04-23T20:14:53.339451Z","invalid_at":null,"attributes":{}},{"uuid":"42914f42-31b5-4cfd-a7e5-c13560024217","group_id":"forge__project_decisions","source_node_uuid":"3bbd88b5-2068-45d9-bc3b-7293588f6d8b","target_node_uuid":"5f9b6c29-d182-4828-b02a-51ece4e76069","created_at":"2026-04-23T20:18:06.660622Z","name":"HAS_SUBAGENT","fact":"`autobuild_runner` is a subagent of the DeepAgents AsyncSubAgent.","episodes":["cf101a24-0335-41a9-b41f-522b3bda5b7d"],"expired_at":null,"valid_at":"2026-04-23T20:14:53.339451Z","invalid_at":null,"attributes":{}},{"uuid":"18ab8f31-bd0b-4189-86ca-33da589ee0cd","group_id":"forge__project_decisions","source_node_uuid":"bffc6d9c-97ec-497e-8be0-d9aa23e015f5","target_node_uuid":"9dd6445a-5844-4c87-9b1a-d00aa411db4e","created_at":"2026-04-18T22:34:15.004947Z","name":"APPROVES_ACTIONS_FOR","fact":"Rich is responsible for approving flagged builds in Forge.","episodes":["43ee331d-2eb7-40a1-97f0-514282779621"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"3283eca1-1992-4132-8856-74c43dc7a72f","group_id":"forge__project_decisions","source_node_uuid":"5f9b6c29-d182-4828-b02a-51ece4e76069","target_node_uuid":"fa1c110d-12b4-4661-95fb-2df16f3748a2","created_at":"2026-04-23T20:18:06.660686Z","name":"USED_TO_CHECK_ASYNC_TASK","fact":"`autobuild_runner` uses `check_async_task` to check the status of asynchronous tasks.","episodes":["cf101a24-0335-41a9-b41f-522b3bda5b7d"],"expired_at":null,"valid_at":"2026-04-23T20:14:53.339451Z","invalid_at":null,"attributes":{}},{"uuid":"283dabb4-7b44-4161-99b7-a353c1340cc2","group_id":"forge__project_decisions","source_node_uuid":"9dd6445a-5844-4c87-9b1a-d00aa411db4e","target_node_uuid":"e487c4bb-8927-4145-9fec-f25da1c993a6","created_at":"2026-04-18T22:50:46.776020Z","name":"USES_FRAMEWORK","fact":"Forge's architecture uses LangGraph with hierarchical subagent composition as part of its runtime topology.","episodes":["1fe1e384-6f71-4d36-bd7d-7c862766ecb8"],"expired_at":null,"valid_at":"2026-04-18T22:50:00.566401Z","invalid_at":null,"attributes":{}},{"uuid":"398268f4-a8bc-48b6-919a-aa691dbd86b2","group_id":"forge__project_decisions","source_node_uuid":"5f9b6c29-d182-4828-b02a-51ece4e76069","target_node_uuid":"83079f49-e7e4-489e-a28f-a17ab1f93af5","created_at":"2026-04-23T20:18:06.660693Z","name":"USED_TO_UPDATE_ASYNC_TASK","fact":"`autobuild_runner` uses `update_async_task` to update asynchronous tasks.","episodes":["cf101a24-0335-41a9-b41f-522b3bda5b7d"],"expired_at":null,"valid_at":"2026-04-23T20:14:53.339451Z","invalid_at":null,"attributes":{}},{"uuid":"04850724-9072-43dd-8520-1a67e192ae6f","group_id":"forge__project_decisions","source_node_uuid":"9dd6445a-5844-4c87-9b1a-d00aa411db4e","target_node_uuid":"f82afd69-5424-4785-b942-c899924f6326","created_at":"2026-04-19T12:26:35.990019Z","name":"PROVIDES_OBSERVABILITY_VIA","fact":"Forge provides observability for its async-subagents via a NATS event stream.","episodes":["212aa237-291c-4469-a1fa-1ca5f96ffe1f"],"expired_at":"2026-04-23T20:18:14.417042Z","valid_at":"2026-04-18T00:00:00Z","invalid_at":"2026-04-23T20:14:53.339451Z","attributes":{}},{"uuid":"bdc38a5e-405c-4c5f-8c0b-a4c264203c89","group_id":"forge__project_decisions","source_node_uuid":"9dd6445a-5844-4c87-9b1a-d00aa411db4e","target_node_uuid":"adc61df1-13f2-4376-a308-7010e228d61c","created_at":"2026-04-19T12:26:35.990035Z","name":"PROVIDES_OBSERVABILITY_VIA","fact":"Forge provides observability for its async-subagents via LangSmith.","episodes":["212aa237-291c-4469-a1fa-1ca5f96ffe1f"],"expired_at":null,"valid_at":"2026-04-18T00:00:00Z","invalid_at":null,"attributes":{}},{"uuid":"d9e352fa-162c-4ebc-9687-01a03f72be4f","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"c06286b4-e4dd-41f4-943a-9328a25cc71d","created_at":"2026-03-05T16:20:51.078333Z","name":"NEEDS_TO_AVOID","fact":"AutoBuild Player agent must NOT use subprocess to invoke guardkit CLI for task-work, because the guardkit CLI does not support the task-work command.","episodes":["bfa244b8-f901-4c1e-af1e-4a75dca0d395"],"expired_at":null,"valid_at":"2026-03-05T16:20:22.373509Z","invalid_at":null,"attributes":{}},{"uuid":"aa3116a1-17fe-4ee2-a099-8043ad2b7060","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"75d6e551-e4c3-4a18-b85e-217ef8ff3bde","created_at":"2026-03-05T23:19:09.605773Z","name":"USES_PATTERN","fact":"AutoBuild Player agent uses query() to invoke /task-work --implement-only.","episodes":["f9ae860c-4f84-48b2-b2df-148ef27a3701","45fb3f14-33f4-4e82-9b44-cface47ce93e"],"expired_at":null,"valid_at":"2026-03-05T23:18:28Z","invalid_at":null,"attributes":{}},{"uuid":"231bf924-8d6b-4d70-b587-6b04497d8e17","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"c06286b4-e4dd-41f4-943a-9328a25cc71d","created_at":"2026-03-04T22:57:55.903943Z","name":"EXCLUDES","fact":"AutoBuild Player agent must NOT use guardkit CLI via subprocess to invoke task-work.","episodes":["9edf6e46-122f-4fd3-97db-602ccb134a56","bb89c868-8e93-455a-8232-9a5cf5065211"],"expired_at":null,"valid_at":"2026-03-04T22:57:23.842722Z","invalid_at":null,"attributes":{}},{"uuid":"77816262-2081-4ba7-be02-90d365d8a6ab","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"1316963d-f08c-4250-ac6a-bcc2450abacc","created_at":"2026-03-05T11:21:02.235034Z","name":"INVOKE_TASK_WORK_VIA","fact":"AutoBuild Player agent invokes /task-work --implement-only via Claude Agents SDK query() function to delegate to the task-work quality gate pipeline.","episodes":["b21694ac-d1b5-4521-ad72-d73babddf370"],"expired_at":null,"valid_at":"2025-01-15T00:00:00Z","invalid_at":null,"attributes":{}},{"uuid":"0e6055f6-95af-4bc7-8acb-0ab72038f1fa","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"862202d4-17ef-488b-a85a-8129c24cefb9","created_at":"2026-03-04T17:44:35.851670Z","name":"HAS_DECISION_TO_AVOID","fact":"AutoBuild Player agent must avoid using subprocess to invoke CLI commands.","episodes":["1f2350e6-1c5e-4a0a-baad-d43844cbb102","b21694ac-d1b5-4521-ad72-d73babddf370","f9ae860c-4f84-48b2-b2df-148ef27a3701","45fb3f14-33f4-4e82-9b44-cface47ce93e"],"expired_at":"2026-03-04T22:58:01.620621Z","valid_at":"2026-03-04T17:44:00Z","invalid_at":"2026-03-04T22:57:23.842722Z","attributes":{}},{"uuid":"82358ebc-bcb8-413c-ae55-0d509f91a727","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"1316963d-f08c-4250-ac6a-bcc2450abacc","created_at":"2026-03-04T17:44:35.851600Z","name":"REQUIRES_USE_OF","fact":"AutoBuild Player agent requires use of Claude Agents SDK query() function to invoke slash commands directly.","episodes":["1f2350e6-1c5e-4a0a-baad-d43844cbb102","bfa244b8-f901-4c1e-af1e-4a75dca0d395","f9ae860c-4f84-48b2-b2df-148ef27a3701","bb89c868-8e93-455a-8232-9a5cf5065211"],"expired_at":"2026-03-04T22:58:01.620630Z","valid_at":"2026-03-04T17:44:00Z","invalid_at":"2026-03-04T22:57:23.842722Z","attributes":{}},{"uuid":"fabb32c9-6724-4ebf-b8f3-0b2b045a45fa","group_id":"architecture_decisions","source_node_uuid":"75d6e551-e4c3-4a18-b85e-217ef8ff3bde","target_node_uuid":"e1bcc370-3c6b-4107-9ce3-3ee784f46b4e","created_at":"2026-03-05T23:19:09.605809Z","name":"PROVIDES_ACCESS","fact":"SDK invocation via query() provides proper context and tool access for subagent execution.","episodes":["f9ae860c-4f84-48b2-b2df-148ef27a3701","45fb3f14-33f4-4e82-9b44-cface47ce93e","cd06ef98-fedd-4409-9734-0d1bdd35e198"],"expired_at":null,"valid_at":"2026-03-05T23:18:28Z","invalid_at":null,"attributes":{}},{"uuid":"33c15bb9-5ba9-459c-b369-02ea339e84ab","group_id":"architecture_decisions","source_node_uuid":"b187d244-d915-4113-af5b-1f88a4855b0b","target_node_uuid":"f556f1ad-9f90-40ed-b3d4-e73d127c6793","created_at":"2026-03-06T15:11:51.312074Z","name":"DELEGATES_TO","fact":"The AutoBuild Player agent delegates implementation to the task-work quality gate pipeline.","episodes":["45fb3f14-33f4-4e82-9b44-cface47ce93e"],"expired_at":null,"valid_at":"2026-03-06T15:11:12.690818Z","invalid_at":null,"attributes":{}}]}}
Graphiti [search_memory_facts]constitutional belt-and-braces pull-requ…
OUT
{"result":{"message":"Facts retrieved successfully","facts":[{"uuid":"38584a2f-9005-426b-8cad-e6ddaca74649","group_id":"forge__project_decisions","source_node_uuid":"2635c477-648b-4796-98f8-af0417e0bc44","target_node_uuid":"b21885cd-d284-4584-b0e6-f7567d944686","created_at":"2026-04-18T22:32:51.814391Z","name":"USES","fact":"The 'pr_finaliser' tool uses an executor assertion to enforce the constitutional rule that PR review is always human.","episodes":["e90974dd-9b5a-4a1d-9880-a1565b387bec"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"4b57edb9-afbd-4bc3-a416-cf78f6215b13","group_id":"forge__project_decisions","source_node_uuid":"bffc6d9c-97ec-497e-8be0-d9aa23e015f5","target_node_uuid":"55d230f8-d453-41e9-be00-9967e7a11b71","created_at":"2026-04-18T22:27:46.828326Z","name":"APPROVES","fact":"Rich approves proposed 'CalibrationAdjustment' entities via a CLI.","episodes":["0310854c-5015-4e1c-aa10-2180fd5e008b"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"e4c24e91-fcb1-455f-bb03-f59a3b9ed2d3","group_id":"forge__project_decisions","source_node_uuid":"bab6bac8-64d1-4dac-8aac-6be8bb059838","target_node_uuid":"85f195fd-e99a-425e-9c30-fb2a0f71f488","created_at":"2026-04-18T22:32:51.814345Z","name":"ARE_ENFORCED_BY","fact":"Constitutional rules are enforced by being explicitly included in the system prompt.","episodes":["e90974dd-9b5a-4a1d-9880-a1565b387bec"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"d0c2fa8b-a441-48ef-8093-46b1cea202ab","group_id":"forge__project_decisions","source_node_uuid":"1954bcbc-a791-4ab0-afa4-37aaf1a0b6e3","target_node_uuid":"4c5ce361-9c63-4036-96c9-2f0ede588bc8","created_at":"2026-04-18T22:51:43.347229Z","name":"EVALUATES","fact":"The Coach will evaluate build plans using its own score once the mandatory human approval gate is relaxed based on performance.","episodes":["a00a7826-fa70-4ed3-b17a-0ad9d94edf5d"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"8b6728bb-d884-46f7-b181-52198d8f3dba","group_id":"forge__project_decisions","source_node_uuid":"bab6bac8-64d1-4dac-8aac-6be8bb059838","target_node_uuid":"b21885cd-d284-4584-b0e6-f7567d944686","created_at":"2026-04-18T22:32:51.814353Z","name":"ARE_ENFORCED_BY","fact":"Constitutional rules are enforced by deterministic Python code in tools and sub-agents, known as executor assertions.","episodes":["e90974dd-9b5a-4a1d-9880-a1565b387bec"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"7cfb3f58-e45d-4548-94ae-44b63323f2f7","group_id":"forge__project_decisions","source_node_uuid":"55d230f8-d453-41e9-be00-9967e7a11b71","target_node_uuid":"e1b4f866-2584-4664-b085-0dbc222bed1e","created_at":"2026-04-18T22:48:10.520247Z","name":"IS_STORED_IN","fact":"Approved CalibrationAdjustment entities are stored in Graphiti, where they can be retrieved to bias future builds.","episodes":["c9a810e4-f8b0-4d4d-ab72-32d6094f7d95"],"expired_at":"2026-04-23T20:13:26.211994Z","valid_at":"2026-04-18T22:47:16.056881Z","invalid_at":"2026-04-23T20:12:16.703369Z","attributes":{}},{"uuid":"67052458-1142-40b7-bdfc-41b8d39f3ef8","group_id":"forge__project_decisions","source_node_uuid":"85f195fd-e99a-425e-9c30-fb2a0f71f488","target_node_uuid":"bab6bac8-64d1-4dac-8aac-6be8bb059838","created_at":"2026-04-18T22:32:51.814382Z","name":"CONTAINS","fact":"The System Prompt explicitly contains the Constitutional Rules under a \"GUARDRAILS\" section.","episodes":["e90974dd-9b5a-4a1d-9880-a1565b387bec"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}},{"uuid":"92c50899-24c8-482d-9670-3556340ffebc","group_id":"forge__project_decisions","source_node_uuid":"ed186099-e845-4f04-9474-13f47847c267","target_node_uuid":"bab6bac8-64d1-4dac-8aac-6be8bb059838","created_at":"2026-04-18T22:32:51.814310Z","name":"DECIDES_ON","fact":"ADR-ARCH-026 decides that Constitutional Rules will be enforced at two layers: through the system prompt and with executor assertions.","episodes":["e90974dd-9b5a-4a1d-9880-a1565b387bec"],"expired_at":null,"valid_at":null,"invalid_at":null,"attributes":{}}]}}
Read mode-a-greenfield-end-to-end
Excellent — Graphiti returned strong context (Mode A entity, AsyncSubAgent state-channel facts, ADR-ARCH-026 belt-and-braces enforcement). Let me read the actual feature file and substrate feature summaries.

Bash List feature directories
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/ && echo "---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/features/pipeline-state-machine-and-configuration/ && echo "---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/features/confidence-gated-checkpoint-protocol/ && echo "---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/features/specialist-agent-delegation/

OUT
mode-a-greenfield-end-to-end_assumptions.yaml
mode-a-greenfield-end-to-end.feature
mode-a-greenfield-end-to-end_summary.md
---
pipeline-state-machine-and-configuration_assumptions.yaml
pipeline-state-machine-and-configuration.feature
pipeline-state-machine-and-configuration_summary.md
---
confidence-gated-checkpoint-protocol_assumptions.yaml
confidence-gated-checkpoint-protocol.feature
confidence-gated-checkpoint-protocol_summary.md
---
specialist-agent-delegation_assumptions.yaml
specialist-agent-delegation.feature
specialist-agent-delegation_summary.md
Bash Check sizes of summary files
IN
wc -l /home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature /home/richardwoollcott/Projects/appmilla_github/forge/features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md /home/richardwoollcott/Projects/appmilla_github/forge/features/specialist-agent-delegation/specialist-agent-delegation_summary.md /home/richardwoollcott/Projects/appmilla_github/forge/features/confidence-gated-checkpoint-protocol/confidence-gated-checkpoint-protocol_summary.md /home/richardwoollcott/Projects/appmilla_github/forge/features/guardkit-command-invocation-engine/guardkit-command-invocation-engine_summary.md /home/richardwoollcott/Projects/appmilla_github/forge/features/infrastructure-coordination/infrastructure-coordination_summary.md /home/richardwoollcott/Projects/appmilla_github/forge/features/nats-fleet-integration/nats-fleet-integration_summary.md

OUT
  473 /home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature
   75 /home/richardwoollcott/Projects/appmilla_github/forge/features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md
   88 /home/richardwoollcott/Projects/appmilla_github/forge/features/specialist-agent-delegation/specialist-agent-delegation_summary.md
   92 /home/richardwoollcott/Projects/appmilla_github/forge/features/confidence-gated-checkpoint-protocol/confidence-gated-checkpoint-protocol_summary.md
   61 /home/richardwoollcott/Projects/appmilla_github/forge/features/guardkit-command-invocation-engine/guardkit-command-invocation-engine_summary.md
   98 /home/richardwoollcott/Projects/appmilla_github/forge/features/infrastructure-coordination/infrastructure-coordination_summary.md
   79 /home/richardwoollcott/Projects/appmilla_github/forge/features/nats-fleet-integration/nats-fleet-integration_summary.md
  966 total
Read mode-a-greenfield-end-to-end.feature
Read pipeline-state-machine-and-configuration_summary.md
Read specialist-agent-delegation_summary.md
Read confidence-gated-checkpoint-protocol_summary.md
Read guardkit-command-invocation-engine_summary.md
Read infrastructure-coordination_summary.md
Read nats-fleet-integration_summary.md
Let me check for existing supervisor/orchestrator code patterns and key docs.

Bash Check project structure
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/src/ 2>/dev/null; ls /home/richardwoollcott/Projects/appmilla_github/forge/forge/ 2>/dev/null; find /home/richardwoollcott/Projects/appmilla_github/forge -maxdepth 4 -type d -name "*pipeline*" -o -name "*supervisor*" -o -name "*orchestrator*" 2>/dev/null | head -10; echo "---"; ls /home/richardwoollcott/Projects/appmilla_github/forge/docs/design 2>/dev/null | head -20

OUT
forge
/home/richardwoollcott/Projects/appmilla_github/forge/orchestrator-config.yaml
/home/richardwoollcott/Projects/appmilla_github/forge/features/pipeline-state-machine-and-configuration
/home/richardwoollcott/Projects/appmilla_github/forge/docs/research/pipeline-orchestrator-conversation-starter.md
/home/richardwoollcott/Projects/appmilla_github/forge/docs/research/pipeline-orchestrator-consolidated-build-plan.md
/home/richardwoollcott/Projects/appmilla_github/forge/docs/research/pipeline-orchestrator-motivation.md
/home/richardwoollcott/Projects/appmilla_github/forge/.claude/agents/deepagents-orchestrator-specialist.md
/home/richardwoollcott/Projects/appmilla_github/forge/.claude/agents/test-orchestrator.md
/home/richardwoollcott/Projects/appmilla_github/forge/tasks/completed/TASK-FVD3/TASK-FVD3-correct-orchestrator-refresh.md
/home/richardwoollcott/Projects/appmilla_github/forge/tasks/in_review/project-scaffold/TASK-FORGE-SCAFFOLD-hand-scaffold-from-orchestrator-template.md
/home/richardwoollcott/Projects/appmilla_github/forge/.claude/rules/guidance/deepagents-orchestrator-specialist.md
---
contracts
decisions
diagrams
models
Bash Check forge package and design docs
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/forge/ && echo "---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/contracts/ 2>/dev/null | head -25 && echo "---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/decisions/ 2>/dev/null | head -25

OUT
Exit code 2
ls: cannot access '/home/richardwoollcott/Projects/appmilla_github/forge/forge/': No such file or directory
Bash Check forge structure
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/ && echo "---DESIGN---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/contracts/ 2>/dev/null && echo "---DECISIONS---" && ls /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/decisions/ 2>/dev/null

OUT
AGENTS.md
command_history.md
docs
features
langgraph.json
LICENSE
mcp.json
orchestrator-config.yaml
place-documents.sh
pyproject.toml
README.md
spikes
src
tasks
tests
---DESIGN---
API-cli.md
API-nats-agent-dispatch.md
API-nats-approval-protocol.md
API-nats-fleet-lifecycle.md
API-nats-pipeline-events.md
API-sqlite-schema.md
API-subagents.md
API-subprocess.md
API-tool-layer.md
---DECISIONS---
DDR-001-reply-subject-correlation.md
DDR-002-resume-value-rehydration-helper.md
DDR-003-sqlite-schema-layout-wal.md
DDR-004-graphiti-group-partitioning.md
DDR-005-cli-context-manifest-resolution.md
DDR-006-async-subagent-state-channel-contract.md
Bash Check src directory
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/src/ && echo "---" && find /home/richardwoollcott/Projects/appmilla_github/forge/src -type f -name "*.py" 2>/dev/null | head -30

OUT
forge
---
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/agent.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/fleet/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/fleet/manifest.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/protocol.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/resolve.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/cache.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/pipeline_publisher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/pipeline_consumer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/fleet_publisher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/fleet_watcher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/__init__.py
Bash Look at pipeline and agent modules
IN
find /home/richardwoollcott/Projects/appmilla_github/forge/src -type f -name "*.py" 2>/dev/null | wc -l && echo "---PIPELINE---" && head -60 /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline.py 2>/dev/null && echo "---AGENT---" && head -60 /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/agent.py 2>/dev/null

OUT
18
---PIPELINE---
"""Pipeline lifecycle emission — wires state-machine transitions to the publisher.

This module is the producer side of the FEAT-FORGE-002 ``pipeline.*`` event
family. It owns the mapping from the FEAT-FORGE-001 build state machine's
transitions to the eight publish methods on
:class:`forge.adapters.nats.PipelinePublisher` (TASK-NFI-006).

Responsibilities (per TASK-NFI-008 acceptance criteria):

- Every state-machine transition listed in the task brief triggers exactly
  one publish call (AC-001).
- Every published payload carries the originating
  :attr:`~nats_core.events.BuildQueuedPayload.correlation_id`. v1 payloads
  (``BuildStarted``, ``BuildProgress``, ``BuildComplete``, ``BuildFailed``)
  declare ``model_config = ConfigDict(extra="ignore")`` and have no
  ``correlation_id`` field; we attach it post-construction with
  :func:`object.__setattr__` so the publisher's
  ``getattr(payload, "correlation_id", None)`` still threads it onto the
  envelope without forcing a nats-core schema change (AC-002).
- ``publish_build_paused`` is awaited **before** the LangGraph
  ``interrupt()`` callback fires — :meth:`PipelineLifecycleEmitter.emit_paused_then_interrupt`
  enforces the ordering even if the publish raises (AC-003, Group D).
- :class:`~forge.adapters.nats.PublishFailure` is logged and swallowed.
  The state machine has already written the SQLite row that motivated the
  emission; rolling back on a transient NATS hiccup would corrupt the
  source of truth (AC-004, Group E).
- A long-running ``RUNNING`` stage fires
  :meth:`forge.adapters.nats.PipelinePublisher.publish_build_progress`
  at least every
  :attr:`~forge.config.models.PipelineConfig.progress_interval_seconds`
  (ASSUM-005) using an injected :class:`Clock`; tests inject
  :class:`FakeClock` to advance time deterministically (AC-005).
- The same publish is also fired on wave boundaries via
  :meth:`PipelineLifecycleEmitter.emit_wave_boundary_progress`, called by
  ``autobuild_runner`` when a wave commits (AC-006).

Design notes:

- The emitter is I/O-thin. It owns the publisher reference, the
  :class:`PipelineConfig`, and a :class:`Clock`; it never touches SQLite
  or the NATS client directly.
- Progress tasks are tracked per ``build_id`` so concurrent builds (a
  defensive position — ADR-ARCH-014 caps in-flight builds at one) cannot
  leak ``asyncio.Task`` instances.
- :class:`State` mirrors the FEAT-FORGE-001 build state names so callers
  can pass them straight through ``on_transition``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Protocol, runtime_checkable

from nats_core.events import (
    BuildCancelledPayload,
    BuildCompletePayload,
---AGENT---
"""Entrypoint for the DeepAgents orchestrator exemplar.

Reads ``orchestrator-config.yaml`` for model selection, loads domain context
from ``domains/{domain}/DOMAIN.md``, creates the orchestrator agent graph, and
exports a module-level ``agent`` variable required by ``langgraph.json``.

Usage via LangGraph::

    langgraph.json  →  ``{"graphs": {"orchestrator": "./agent.py:agent"}}``
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from agents import create_orchestrator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Project root directory (where this file lives).
_PROJECT_ROOT = Path(__file__).resolve().parent

#: Default domain name used when no override is provided.
DEFAULT_DOMAIN = "example-domain"

#: Fallback model identifiers used when the config file is missing or invalid.
_DEFAULT_CONFIG: dict[str, Any] = {
    "orchestrator": {
        "reasoning_model": "anthropic:claude-sonnet-4-6",
        "implementation_model": "anthropic:claude-haiku-4-5",
    },
}

#: Canonical env var names (LES1 §3 PMEV). An operator setting either of these
#: overrides the YAML config for the matching role. An empty value is treated
#: as "unset" — see :func:`_resolve_model`.
_ENV_REASONING_MODEL = "AGENT_MODELS__REASONING_MODEL"
_ENV_IMPLEMENTATION_MODEL = "AGENT_MODELS__IMPLEMENTATION_MODEL"

#: Fallback domain prompt returned when the DOMAIN.md file cannot be read.
_DEFAULT_DOMAIN_PROMPT = "No domain-specific guidelines loaded. Follow general software engineering best practices."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(config_path: Path) -> dict[str, Any]:
Read mode-a-greenfield-end-to-end_assumptions.yaml
Bash Check DDR-006
IN
head -120 /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md

OUT
# DDR-006 — Async subagent state-channel contract (`async_tasks`)

## Status

Accepted

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-031, ADR-ARCH-021, ADR-SP-013

---

## Context

ADR-ARCH-031 commits `autobuild_runner` to DeepAgents `AsyncSubAgent` — launched via `start_async_task`, supervised via five middleware-provided tools (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`). The middleware maintains an `async_tasks` state channel that survives context compaction and is readable from the supervisor reasoning loop.

What the middleware does **not** specify is the **content** of each task's state entry. That's a Forge-level decision: what fields does `autobuild_runner` write into its state so that `forge status` and `forge history` can render meaningful live progress — and so that `forge.adapters.sqlite.reconcile_on_boot()` can make sense of a crash that happened mid-autobuild?

The refresh doc §"Forge history narrative" shows the intended UX (wave-level progress with task counts and Coach scores) but doesn't lock the schema.

## Decision

Each `async_tasks` entry is a Pydantic `AutobuildState` model, serialised to the state channel as `dict` (LangGraph channel requirement). Shape:

```python
class AutobuildState(BaseModel):
    # Identity
    task_id: str                                            # Assigned by start_async_task
    build_id: str
    feature_id: str

    # Progress
    lifecycle: Literal[
        "starting",
        "planning_waves",
        "running_wave",
        "awaiting_approval",
        "pushing_pr",
        "completed",
        "cancelled",
        "failed",
    ]
    wave_index: int = 0
    wave_total: int = 0
    task_index: int = 0
    task_total: int = 0
    current_task_label: str | None = None                   # Reasoning-model-chosen
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Quality
    last_coach_score: float | None = None
    aggregate_coach_score: float | None = None              # Weighted average across completed tasks

    # Approval coupling
    waiting_for: str | None = None                          # e.g. "approval:Architecture Review"

    # Steering
    pending_directives: list[str] = []                      # Injected by supervisor via update_async_task

    # Timing
    started_at: datetime
    last_activity_at: datetime
    estimated_completion_at: datetime | None = None         # Computed from tasks remaining + per-task avg
```

**Write cadence:**

- On every lifecycle transition (entry and exit of each lifecycle state).
- On every task completion (wave/task index bumps, tasks_completed++, coach score updated).
- On every `interrupt()` fire (lifecycle → `awaiting_approval`, waiting_for set).
- On every supervisor-injected directive (append to pending_directives).
- Otherwise at most every 30s (avoid excess state-channel churn).

**Read patterns:**

- `forge status` (CLI) calls `list_async_tasks` → filters for the active build → renders lifecycle + wave/task indices + ETA.
- `forge history --feature X` does **not** read the live state channel; it reads the terminal state mirrored into `stage_log.details_json["subagent_trace"]` after completion.
- Supervisor reasoning model uses `check_async_task(task_id)` when deciding whether to continue waiting or proceed with another parallel concern.

**Crash-recovery linkage:** On Forge restart, `forge.adapters.sqlite.reconcile_on_boot()` reads `async_tasks` state channel (LangGraph persists it across checkpoints) alongside SQLite. If SQLite shows `RUNNING` and the state channel still has an `AutobuildState` with lifecycle != terminal, the reasoning model decides: retry-from-scratch (anchor §5 default) or inspect the trace to see if autobuild actually finished silently. The retry-from-scratch policy holds as the **default**; the state-channel data is advisory for reasoning.

**`waiting_for` ↔ ADR-ARCH-021 linkage:** When the async subgraph fires `interrupt()`, it sets `lifecycle="awaiting_approval"` + `waiting_for="approval:{stage_label}"` **before** calling interrupt. On resume (via NATS ApprovalResponsePayload), `autobuild_runner` clears `waiting_for` and returns to `running_wave`. This gives the supervisor observability into the pause without coupling it to the NATS approval subscription.

## Rationale

- **Explicit shape** — without a locked schema, two versions of `autobuild_runner` (current + future) risk writing divergent state that `forge status` can't render.
- **Enables ETA estimation** — storing `aggregate_coach_score` + `tasks_completed` / `task_total` lets `forge status` render meaningful progress, not just "still running".
- **Decouples supervisor observability from NATS** — `waiting_for` is readable via `check_async_task` without the supervisor subscribing to approval topics.
- **Defence in depth with SQLite** — authoritative lifecycle state still lives in SQLite; the state channel adds richness but the fault path is well-defined.

## Alternatives considered

- **Free-form `dict[str, Any]` state entries** — rejected; creates drift risk and forces renderer to tolerate unknown shapes.
- **Full `StageLogEntry` stream in the state channel** — rejected; doubles the write volume and SQLite already owns this.
- **State-channel as primary durability (drop SQLite mirror)** — rejected; LangGraph's async state channel is not a durability contract equivalent to SQLite + JetStream.

## Consequences

- **+** `forge status` can render wave-level progress, ETA, and pause reason — the refresh-doc UX becomes realisable.
- **+** Supervisor observability into pauses is schema-driven, not string-matching.
- **+** Crash-recovery has an extra advisory channel without compromising the authoritative SQLite + JetStream path.
- **−** Shape is now a versioned contract — changing field names requires a migration path. Mitigated by Pydantic's `extra="ignore"` default + additive-only evolution.
- **−** Every `autobuild_runner` write path has an obligation to update `AutobuildState` consistently; drift = degraded UX. Mitigated by a single helper `forge.subagents.autobuild_runner._update_state(...)` that centralises writes.

## Related components

- Subagent (`forge.subagents.autobuild_runner`)
- Agent Runtime (supervisor, via DeepAgents `AsyncSubAgentMiddleware`)
- CLI (`forge status`)
- Data model — [DM-build-lifecycle.md §4](../models/DM-build-lifecycle.md#4-relationships)
- API contract — [API-subagents.md §3.3](../contracts/API-subagents.md#33-supervisor-interaction)
Bash Find agent definitions
IN
ls /home/richardwoollcott/Projects/appmilla_github/forge/src/agents 2>/dev/null; find /home/richardwoollcott/Projects/appmilla_github/forge -path "*/agents*" -name "*.py" -not -path "*/.venv/*" 2>/dev/null | head -20; echo "---"; head -40 /home/richardwoollcott/Projects/appmilla_github/forge/docs/design/contracts/API-subagents.md 2>/dev/null

OUT
---
# API Contract — Subagents

> **Type:** DeepAgents sub-agent specs (TypedDict factories)
> **Framework:** DeepAgents 0.5.3 — `SubAgent` (sync `task()`) and `AsyncSubAgent` (preview, ASGI)
> **Related ADRs:** [ADR-ARCH-002](../../architecture/decisions/ADR-ARCH-002-two-model-separation.md), [ADR-ARCH-020](../../architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)

---

## 1. Purpose

Forge pre-declares exactly **two** sub-agents; everything else is spawned via the DeepAgents built-in `task()` tool on demand (ADR-ARCH-020). The two pre-declared specs live in `forge.subagents`:

- `build_plan_composer` — **sync `SubAgent`**. Bounded, gates the next decision.
- `autobuild_runner` — **async `AsyncSubAgent`**. Long-running (30–90+ min), launched via `start_async_task`.

This contract specifies their TypedDict factory shapes, the models assigned to each, and the state-channel contract for the async runner.

---

## 2. `build_plan_composer` — Sync SubAgent

### 2.1 Factory

```python
# forge.subagents.build_plan_composer
from deepagents import SubAgent
from forge.prompts import BUILD_PLAN_COMPOSER_PROMPT

def build_plan_composer_spec(domain_prompt: str) -> SubAgent:
    return SubAgent(
        name="build_plan_composer",
        description=(
            "Compose a gated build plan from the current feature-spec and retrieved priors. "
            "Input: feature_id, feature_yaml_path, capability snapshot. "
            "Output: {waves: [{tasks: [...]}], risks: [...], priors_referenced: [...]}. "
            "Supervisor blocks on this — output gates the next reasoning step (ADR-ARCH-007)."
        ),
        system_prompt=BUILD_PLAN_COMPOSER_PROMPT.format(domain_prompt=domain_prompt),
        model="google_genai:gemini-3.1-pro",            # reasoning model
        tools=[
I have the full context now. Let me write the review report and then present the decision checkpoint.

Bash Ensure reviews directory exists
IN
mkdir -p /home/richardwoollcott/Projects/appmilla_github/forge/.claude/reviews

OUT
(Bash completed with no output)
Write TASK-REV-MAG7-review-report.md
406 lines
# Review Report: TASK-REV-MAG7 — Plan Mode A Greenfield End-to-End

**Feature**: FEAT-FORGE-007 — Mode A Greenfield End-to-End
**Mode**: Decision
**Depth**: Standard
**Generated**: 2026-04-25
**Reviewer**: /task-review (decision mode)

---

## Executive Summary

FEAT-FORGE-007 is the **capstone composition feature** for Forge. It introduces no
new transitions, transports, or gate modes — every primitive it relies on is
already specified in FEAT-FORGE-001 through FEAT-FORGE-006. The work is therefore
*purely orchestration*: ordering the eight stage classes correctly, threading
each stage's approved output forward into the next stage's dispatch context,
launching autobuild as an `AsyncSubAgent` so the supervisor stays responsive, and
ensuring that the constitutional pull-request rule and the crash-recovery
contract remain honoured.

The recommended approach is **Option 1: Reasoning-loop-driven dispatch with a
deterministic ordering guard**. A small `StageOrderingGuard` deterministic
validator enforces the seven-prerequisite invariant (Group B Scenario Outline);
the LangGraph supervisor's reasoning model decides *when* to dispatch the next
permitted stage, given recorded history and the live state channel. This
preserves the LangGraph supervisor pattern already used elsewhere in Forge while
making the constitutional invariants impossible to bypass through prompt drift.

The plan decomposes into **14 tasks across 5 waves**, with the longest critical
path bounded by the wave dependency graph rather than by serial enumeration.
Estimated total effort: ~12–16 hours of focused implementation, dominated by the
end-to-end concurrency and crash-recovery integration tests in Wave 5.

---

## Review Scope (Context A captured at /feature-plan)

- **Focus**: All — full sweep across architecture, technical, performance, security
- **Trade-off priority**: Balanced
- **Specific concerns**: None pre-flagged — surfaced organically below

---

## Knowledge Graph Context Used

- **Mode A entity** (`forge__project_decisions`): confirms eight stage chain
  driven via GuardKit slash commands, history files as calibration data
- **`autobuild_runner` HAS_STATE_CHANNEL `async_tasks`** — DeepAgents AsyncSubAgent
  with `check_async_task` / `update_async_task` middleware tools
- **ADR-ARCH-026** (Constitutional Rules enforced at two layers): system prompt
  GUARDRAILS section + executor assertions in `pr_finaliser`
- **DDR-006** (Async subagent state-channel contract): `AutobuildState` Pydantic
  shape with `lifecycle`, `wave_index`, `task_index`, `waiting_for`, `pending_directives`
- **ADR-ARCH-031** (Async subagents for long-running work) — autobuild_runner
  launched via `start_async_task`
- **Existing code** (`src/forge/pipeline.py`): `PipelineLifecycleEmitter` already
  threads correlation_id, publishes paused-then-interrupt ordering, swallows
  `PublishFailure` after SQLite commit (Group D / Group G already covered at the
  emitter level)

---

## Substrate Inventory — What Already Exists

| Substrate | Owned by | Status |
|-----------|----------|--------|
| Build state machine (queued/preparing/running/paused/terminal) | FEAT-FORGE-001 | Specified |
| SQLite history (`stage_log`, `build_state`) — authoritative | FEAT-FORGE-001 | Specified |
| Crash recovery — retry-from-scratch | FEAT-FORGE-001 | Specified |
| CLI steering (`forge cancel`, `forge skip`) | FEAT-FORGE-001/004 | Specified |
| Pipeline event publish (started/progress/stage-complete/paused/resumed/complete) | FEAT-FORGE-002 | **Implemented** (`PipelineLifecycleEmitter`) |
| Build queue subscription (terminal-ack, dedupe, allowlist refusal) | FEAT-FORGE-002 | Specified |
| Discovery cache (30s TTL) + degraded-mode fallback | FEAT-FORGE-002 | Specified |
| Specialist dispatch (capability resolution, retry-with-context) | FEAT-FORGE-003 | Specified |
| Confidence-gated checkpoint protocol (4 modes) | FEAT-FORGE-004 | Specified |
| Build-keyed approval channel + first-wins idempotency | FEAT-FORGE-004 | Specified |
| Belt-and-braces PR-review enforcement | FEAT-FORGE-004 | Specified (executor + prompt) |
| GuardKit subprocess engine (`/system-arch`, `/system-design`, `/feature-spec`, `/feature-plan`, autobuild) | FEAT-FORGE-005 | Specified |
| Worktree allowlist confinement | FEAT-FORGE-005 | Specified |
| Long-term memory seeding + priors retrieval | FEAT-FORGE-006 | Specified |
| Calibration priors (snapshot at build start) | FEAT-FORGE-006 | Specified |
| `git`/`gh` PR creation adapter | FEAT-FORGE-006 | Specified |

**Net new in FEAT-FORGE-007**: the supervisor's reasoning loop wiring + the
stage-ordering guard + the per-stage forward-propagation context-builder.

---

## Technical Options Analysis

### Option 1: Reasoning-Loop-Driven Dispatch with Ordering Guard ⭐ Recommended

**Pattern**: LangGraph supervisor's reasoning model selects the next stage to
dispatch on each turn; a deterministic `StageOrderingGuard` (Pydantic validator
+ pure function) refuses any dispatch whose prerequisites are not all
recorded-as-approved in SQLite. The guard also encodes the constitutional
PR-review rule (refuses skip, refuses auto-approve at executor layer).

**Complexity**: 7/10
**Effort**: 12–16 hours
**Pros**:
- Aligns with the existing DeepAgents supervisor topology (`create_orchestrator`,
  reasoning model + implementation model)
- Guard is a pure function over `stage_log` rows — trivially unit-testable, no
  async, no flakiness
- Reasoning loop stays small: it asks "what's next?" and the guard answers
  "you can dispatch X, Y, but not Z" — the LLM picks one
- Supervisor responsiveness during autobuild is automatic: the reasoning loop
  is not blocked because `autobuild_runner` is an `AsyncSubAgent` (DDR-006)
- Constitutional invariants are enforced at executor layer (the guard)
  *independently* of prompt content — ADR-ARCH-026 belt-and-braces holds
- All 47 scenarios map cleanly onto guard predicates + reasoning-loop choices

**Cons**:
- Reasoning model still needs a clear system-prompt section enumerating the
  eight stages and their inputs (forward-propagation hints) — prompt + guard
  must agree on the stage taxonomy
- Per-feature inner-loop sequencing (ASSUM-006) requires a guard predicate that
  sees "is any autobuild for this build still non-terminal?" — slightly subtle
  but well-bounded

**Dependencies**: Substrate features 1–6 must be at parity with their specs
(none need extension).

---

### Option 2: State-Machine-Driven Dispatch (Deterministic FSM)

**Pattern**: A pure FSM with explicit transitions for all eight stages drives
dispatch sequentially; the reasoning model is reduced to a "should I retry,
escalate, or proceed" oracle at gate decisions.

**Complexity**: 5/10 (simpler control flow)
**Effort**: 8–12 hours
**Pros**:
- Fully deterministic dispatch order — easier to reason about
- No reasoning-model variance affects sequencing
- Easier crash-recovery: the FSM resumes at "the next state SQLite says is
  pending"

**Cons**:
- **Misaligns with the established Forge topology.** Forge already uses a
  reasoning-loop supervisor (`create_orchestrator` + DeepAgents). A second FSM
  duplicates state.
- Removes the supervisor's ability to make holistic mid-flight decisions
  (e.g. "the architect returned a degraded result — should we retry with
  additional context?" — that's a reasoning question, not an FSM transition)
- Group D edge cases (mid-flight steering, idempotent duplicate, asynchronous
  pause observability) become awkward to wire because the FSM must own all
  of them; with Option 1 they live naturally on the supervisor
- Doesn't compose well with FEAT-FORGE-003's reasoning-model-driven retry

---

### Option 3: Hybrid (Static FSM Guard + Reasoning Loop for Choice)

**Pattern**: Pre-compute the eight-stage DAG as a static graph; the reasoning
loop traverses it but each transition is a guarded edge.

**Complexity**: 6/10
**Effort**: 10–14 hours
**Pros**:
- Combines the determinism of Option 2 with the flexibility of Option 1
- The DAG is human-readable and serves as documentation

**Cons**:
- The DAG is **already** the seven prerequisite rows in the Group B Scenario
  Outline — encoding it as a graph object is over-engineering
- Adds a new abstraction (`StageDAG`) with no runtime payoff over Option 1's
  pure-function guard
- Per-feature loop fan-out is awkward — a single static DAG doesn't naturally
  express N parallel feature-specs collapsing into N sequential autobuilds
- Risk of drift between the DAG-as-data and the seven-prerequisite Scenario
  Outline (two sources of truth)

---

## Recommended Approach — Option 1 in Detail

```
┌─────────────────────────────────────────────────────────────────┐
│                  Forge Supervisor (LangGraph)                    │
│                                                                  │
│  ┌────────────────┐   asks   ┌────────────────────────┐         │
│  │ Reasoning loop │──────────>│ StageOrderingGuard      │         │
│  │ (gemini-3.1)   │<──────────│ (pure fn over SQLite)   │         │
│  └────────────────┘  permits  └────────────────────────┘         │
│         │                                                        │
│         │ dispatches                                             │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Stage dispatchers (one per stage class)          │           │
│  │   - product_owner, architect (FEAT-FORGE-003)     │           │
│  │   - system_arch, system_design (FEAT-FORGE-005)   │           │
│  │   - feature_spec, feature_plan (FEAT-FORGE-005)   │           │
│  │   - autobuild  (AsyncSubAgent, FEAT-FORGE-005)    │           │
│  │   - pull_request_review (constitutional)          │           │
│  └──────────────────────────────────────────────────┘           │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Forward-Propagation Context Builder              │           │
│  │  (per stage: read prior stage's artefact paths    │           │
│  │   from stage_log, assemble --context flags)       │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼ (writes durable history)
  ┌──────────────────────────┐
  │  SQLite stage_log        │ ← authoritative source on recovery
  │  (FEAT-FORGE-001)        │
  └──────────────────────────┘
```

**Stage taxonomy** (pinned by ASSUM-001, all eight stage classes):

| # | Stage | Constitutional? | Implementation owner | Dispatch shape |
|---|-------|----------------|---------------------|----------------|
| 1 | `product_owner` | No | FEAT-FORGE-003 | Capability dispatch (sync via `await`) |
| 2 | `architect` | No | FEAT-FORGE-003 | Capability dispatch (sync via `await`) |
| 3 | `system_arch` | No | FEAT-FORGE-005 | Subprocess (sync) |
| 4 | `system_design` | No | FEAT-FORGE-005 | Subprocess (sync) |
| 5 | `feature_spec` (×N) | No | FEAT-FORGE-005 | Subprocess (sync), per-feature |
| 6 | `feature_plan` (×N) | No | FEAT-FORGE-005 | Subprocess (sync), per-feature |
| 7 | `autobuild` (×N) | No | FEAT-FORGE-005 + DDR-006 | **AsyncSubAgent** (`start_async_task`) |
| 8 | `pull_request_review` (×N) | **Yes** (mandatory human) | FEAT-FORGE-004/006 | Gate + executor assertion |

**Forward-propagation contract** (per stage transition):

| Producer | Consumer | Artefact threaded |
|----------|----------|-------------------|
| product-owner | architect | approved charter (text) |
| architect | system-arch | architect approved output |
| system-arch | system-design | architecture artefact paths |
| system-design | feature-spec (×N) | feature catalogue entry per N |
| feature-spec | feature-plan | feature spec artefact path for that feature |
| feature-plan | autobuild | approved build plan path for that feature |
| autobuild | pull-request | branch ref + commit summary |

---

## Subtask Breakdown — 14 Tasks Across 5 Waves

### Wave 1 — Foundations (parallel)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-001 | Define `StageClass` enum + `StagePrerequisite` table (eight stages, seven prerequisite rows from Group B Scenario Outline) | declarative | 2 | 30m |
| TASK-MAG7-002 | Define `ForwardPropagationContract` map (producer → consumer artefact handshake, seven rows) | declarative | 2 | 30m |

### Wave 2 — Core Guards (depends on Wave 1)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-003 | Implement `StageOrderingGuard.next_dispatchable(build_id)` — pure fn over `stage_log` rows; covers Group B prerequisite Scenario Outline | feature | 5 | 90m |
| TASK-MAG7-004 | Implement `ConstitutionalGuard.veto_if_pr_review(stage, mode)` — executor-layer refusal of auto-approve and skip on PR-review (Groups C/E) | feature | 4 | 60m |
| TASK-MAG7-005 | Implement `PerFeatureLoopSequencer.may_start_autobuild(build_id, feature_id)` — refuses second autobuild while first is non-terminal (Group D ASSUM-006) | feature | 4 | 60m |

### Wave 3 — Stage Dispatchers + Context Builder (depends on Wave 2)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-006 | Implement `ForwardContextBuilder.build_for(stage, build_id)` — assembles `--context` flags from prior stage artefact paths in `stage_log` | feature | 5 | 90m |
| TASK-MAG7-007 | Wire `dispatch_specialist_stage` (product-owner, architect) — composes FEAT-FORGE-003 capability dispatch with `ForwardContextBuilder` | feature | 4 | 75m |
| TASK-MAG7-008 | Wire `dispatch_subprocess_stage` (system-arch, system-design, feature-spec, feature-plan) — composes FEAT-FORGE-005 subprocess engine with `ForwardContextBuilder`, threads correlation_id | feature | 5 | 90m |
| TASK-MAG7-009 | Wire `dispatch_autobuild_async` — uses `start_async_task` from DDR-006, returns task_id; registers on supervisor `async_tasks` channel | feature | 6 | 120m |

### Wave 4 — Supervisor Reasoning Loop (depends on Wave 3)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-010 | Wire `Supervisor.next_turn(build_id)` — reads guard, calls reasoning model with permitted dispatches, executes chosen dispatch; covers Group A key examples + Group F concurrency | feature | 7 | 150m |
| TASK-MAG7-011 | Wire CLI steering injection (`forge cancel` → synthetic reject, `forge skip` → synthetic override; PR-review skip refusal); covers Group D edge cases | feature | 5 | 90m |

### Wave 5 — Integration Tests + Smoke (depends on Wave 4)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-012 | Smoke test — minimal one-line greenfield brief drives single-feature run to PR-awaiting-review (Group H @smoke @integration) | testing | 5 | 90m |
| TASK-MAG7-013 | Crash-recovery integration tests — Group D Scenario Outline (seven stage classes), durable history vs advisory state channel | testing | 6 | 120m |
| TASK-MAG7-014 | Concurrency + multi-feature integration tests — Group F (two concurrent builds), Group H multi-feature, ASSUM-006 sequencing, Group I expansion (correlation threading, calibration snapshot, first-wins) | testing | 7 | 150m |

**Total estimate**: 14 tasks, ~12–16 hours focused implementation.

---

## Risk Register

| ID | Risk | Severity | Likelihood | Mitigation |
|----|------|----------|-----------|------------|
| R-1 | Reasoning model dispatches a stage out of order despite guard refusal | **High** | Low | Guard returns *only the permitted set*; supervisor refuses to act on a non-permitted choice; integration test asserts on Scenario Outline of seven prerequisites |
| R-2 | `AsyncSubAgent` crash mid-autobuild leaves SQLite "running" but state-channel "completed" or vice versa | **High** | Medium | DDR-006 + ASSUM-004 already specify SQLite as authoritative on recovery. Wave 5 crash-recovery tests cover all seven non-terminal stages |
| R-3 | Per-feature loop dispatches second autobuild before first reaches terminal lifecycle | **Medium** | Medium | `PerFeatureLoopSequencer` (TASK-MAG7-005); explicit @edge-case test in Group D |
| R-4 | Constitutional belt-and-braces drift — prompt allows auto-approve at PR-review while executor still refuses | Medium | Low (addressed) | ADR-ARCH-026 wired both layers; `ConstitutionalGuard.veto_if_pr_review` is the executor side. Group E security scenarios test the executor with a deliberately-misconfigured prompt |
| R-5 | Forward-propagation context builder leaks unapproved or stale artefacts | **High** | Low | `ForwardContextBuilder` reads only stage entries with `gate_decision='approved'` from `stage_log`; @data-integrity tests assert on artefact-path attribution |
| R-6 | Concurrent builds collide on supervisor reasoning loop or approval channel | Medium | Low | FEAT-FORGE-002 uses build-keyed channels; FEAT-FORGE-004 is build-keyed approval; Group F concurrency test asserts isolation |
| R-7 | First-wins idempotency violated — duplicate approval response causes second resume | Medium | Low (addressed) | FEAT-FORGE-004 ASSUM-006 already specifies; Group D + Group I @concurrency tests |
| R-8 | Calibration-priors snapshot drift mid-build | Low | Medium | Snapshot at `build_picked_up`; pass via dependency injection; Group I @data-integrity test |
| R-9 | Notification publish failure silently regresses approval | Low | Low (addressed) | Existing `PipelineLifecycleEmitter` swallows `PublishFailure` after SQLite commit; Group G + Group I @data-integrity tests cover |
| R-10 | Worktree confinement bypass during subprocess stage | High | Low (inherited) | FEAT-FORGE-005 owns DeepAgents permissions; Group E @security test re-asserts at composition layer |

---

## Integration Contracts (cross-task)

### Contract: stage_taxonomy
- **Producer task**: TASK-MAG7-001
- **Consumer tasks**: TASK-MAG7-003, TASK-MAG7-005, TASK-MAG7-007, TASK-MAG7-008
- **Artefact**: Python module `forge.pipeline.stage_taxonomy` exporting `StageClass` enum + `STAGE_PREREQUISITES: dict[StageClass, list[StageClass]]`
- **Format constraint**: enum members ordered exactly as in ASSUM-001; dict matches the seven Scenario-Outline prerequisite rows verbatim
- **Validation**: Coach asserts `len(STAGE_PREREQUISITES) == 7` and key set equals `{architect, system_arch, system_design, feature_spec, feature_plan, autobuild, pull_request_review}`

### Contract: forward_propagation_map
- **Producer task**: TASK-MAG7-002
- **Consumer task**: TASK-MAG7-006
- **Artefact**: Python module `forge.pipeline.forward_propagation` exporting `PROPAGATION_CONTRACT: dict[StageClass, ContextRecipe]`
- **Format constraint**: every non-product-owner stage class has exactly one entry; recipe references `stage_log` artefact_path columns by name
- **Validation**: Coach asserts every key in `PROPAGATION_CONTRACT` is reachable from `product_owner` via `STAGE_PREREQUISITES`

### Contract: autobuild_async_task_id
- **Producer task**: TASK-MAG7-009
- **Consumer task**: TASK-MAG7-010 (supervisor) + TASK-MAG7-011 (CLI steering)
- **Artefact**: `task_id: str` returned from `start_async_task`, registered on `async_tasks` state channel
- **Format constraint**: matches DDR-006 `AutobuildState.task_id` shape; per-feature unique within a build
- **Validation**: Coach asserts `dispatch_autobuild_async` returns the same `task_id` that `list_async_tasks` later reports

---

## Test Strategy

**Unit (Waves 1–4)**:
- Pure-function tests on `StageOrderingGuard` (covers Group B Scenario Outline directly)
- Pure-function tests on `ConstitutionalGuard` (covers Group C @negative + Group E @security)
- Pure-function tests on `PerFeatureLoopSequencer`
- Mocked-substrate tests on each dispatcher (Wave 3) — substrate features mocked via FEAT-FORGE-003/005 contract surfaces

**Integration (Wave 5)**:
- Smoke: Group H @smoke @integration — end-to-end with real subprocess invocation against fixture GuardKit responses
- Crash recovery: Group D Scenario Outline — `pytest.fixture` that kills the supervisor at each of seven stages, asserts retry-from-scratch
- Concurrency: Group F + Group I @concurrency — two builds, asserts channel isolation, first-wins
- Multi-feature: Group H — three-feature catalogue, asserts one autobuild + one PR-review per feature, ASSUM-006 sequencing
- Constitutional: Group E @security @regression — deliberately misconfigured prompt, asserts executor still refuses

**Determinism**: All async tests use `FakeClock` (already used by existing
`PipelineLifecycleEmitter` per `src/forge/pipeline.py`); approval round-trips
use a stub `ApprovalChannel` driven by the test thread.

---

## Disconnection Audit

This is the read/write path map for FEAT-FORGE-007's net-new code:

```
Writes:                           Storage:                    Reads:
─────────                         ────────                    ──────
Stage dispatchers ───approved───> stage_log (SQLite)  ───────> StageOrderingGuard.next_dispatchable
                                                      ──────-> ForwardContextBuilder.build_for
                                                      ──────-> CLI forge history

Supervisor turn  ───decided────-> reasoning_history          ──> CLI forge status (advisory)
                                  (LangGraph state ch.)

dispatch_autobuild_async ──tid──> async_tasks (state ch.) ──-> Supervisor.next_turn (advisory)
                                                          ───-> CLI forge status (advisory)
                                                          ───-> CLI cancel/steering

ConstitutionalGuard ───veto────-> (in-memory return value)  ──> Supervisor.next_turn (gate)
                                                          ───-> approval response handler (gate)
```

**No disconnected paths.** Every write path has a corresponding read path
within FEAT-FORGE-007 or one of its consumers (CLI status, history, cancel
handler, approval handler).

---

## Decision

✅ **Recommended**: Option 1 — Reasoning-Loop-Driven Dispatch with Ordering Guard

The recommendation aligns with:
- The existing Forge supervisor topology (`create_orchestrator`, two-model)
- ADR-ARCH-026 belt-and-braces (executor + prompt) for constitutional rules
- DDR-006 async-subagent contract (already a load-bearing decision)
- The FEAT-FORGE-001..006 substrate without requiring any extension

Net-new code is small (~14 tasks, ~12–16 hours), well-bounded, and dominated by
pure functions over SQLite history rows. The only async surface is
`dispatch_autobuild_async`, which is a thin wrapper over the already-specified
`start_async_task` middleware.

---

## Decision Checkpoint

Review complete. Found 3 technical approaches with **Option 1 recommended**.

What would you like to do?

- **[A]ccept** — Approve recommendation, save review for reference, do not create implementation tasks
- **[R]evise** — Request deeper analysis on a specific concern (concurrency, constitutional, async-subagent stability, etc.)
- **[I]mplement** — Create the 14-task feature structure across 5 waves, ready for `/feature-build`
- **[C]ancel** — Discard this plan
Review complete. Here's the summary:

🔍 Review Complete — TASK-REV-MAG7 (Plan: Mode A Greenfield End-to-End)
Full report: .claude/reviews/TASK-REV-MAG7-review-report.md

Technical Options Analyzed
Option	Complexity	Effort	Recommendation
1. Reasoning-loop-driven dispatch with ordering guard	7/10	12–16h	⭐ Recommended
2. State-machine-driven dispatch (deterministic FSM)	5/10	8–12h	Misaligns with existing supervisor topology
3. Hybrid (static DAG + reasoning loop)	6/10	10–14h	Over-engineered; duplicates Scenario-Outline as data
Why Option 1
Aligns with existing DeepAgents supervisor (create_orchestrator)
Constitutional invariants enforced at executor layer via pure-function StageOrderingGuard + ConstitutionalGuard — independent of prompt drift (matches ADR-ARCH-026 belt-and-braces)
Composes substrate features 1–6 without extending any of them
Async surface is a thin wrapper over DDR-006's already-specified start_async_task
Key Substrate Insight
PipelineLifecycleEmitter (in src/forge/pipeline.py) already implements paused-then-interrupt ordering, swallows PublishFailure after SQLite commit, and threads correlation_id — Group D / Group G are largely covered at the substrate layer. Net-new work is purely composition.

Subtask Breakdown — 14 tasks across 5 waves
Wave 1 (declarative, parallel): stage taxonomy, forward-propagation map
Wave 2 (guards, parallel): ordering guard, constitutional guard, per-feature loop sequencer
Wave 3 (dispatchers, parallel): forward-context builder, specialist/subprocess/async dispatchers
Wave 4 (composition, sequential): supervisor reasoning loop, CLI steering
Wave 5 (integration tests, parallel): smoke, crash-recovery, concurrency+multi-feature
Risk Register
10 risks identified; the three rated High are all addressed by existing substrate guarantees (DDR-006 SQLite-as-authoritative for crash recovery, ADR-ARCH-026 two-layer enforcement, FEAT-FORGE-005 worktree confinement). No new architectural risk introduced.

Disconnection Audit
✅ All write paths have read paths — no orphaned data flows.

Decision Checkpoint
What would you like to do?

[A]ccept — Approve recommendation, save review for reference, do not create implementation tasks
[R]evise — Request deeper analysis on a specific concern (e.g. async-subagent stability, constitutional enforcement, concurrency, crash recovery)
[I]mplement — Create the 14-task feature structure across 5 waves under tasks/backlog/mode-a-greenfield-end-to-end/, generate IMPLEMENTATION-GUIDE.md with mandatory diagrams, generate .guardkit/features/FEAT-MAG7.yaml, and run BDD scenario linking
[C]ancel — Discard this plan
Your choice [A/R/I/C]:

TASK-REV-IC8B-review-report.md
I
Choosing [I]mplement. Step 8 — Implementation Preferences (Context B), since we have 14 subtasks (≥2).

Agent:Collect implementation preferences
IN
Execute clarification for implementation.

CONTEXT TYPE: implementation_prefs

REVIEW FINDINGS:
  Recommendations:
    Option 1 (Recommended): Reasoning-loop-driven dispatch with deterministic StageOrderingGuard
    Option 2: State-machine-driven dispatch (rejected — misaligns with existing supervisor topology)
    Option 3: Hybrid static DAG + reasoning loop (rejected — over-engineered)

  Subtask count: 14
  Wave count: 5

  Wave structure:
    Wave 1 (parallel, declarative, low complexity): stage taxonomy + forward-propagation map (2 tasks)
    Wave 2 (parallel, feature, medium complexity): three guards — ordering, constitutional, per-feature loop (3 tasks)
    Wave 3 (parallel, feature, medium-high complexity): context builder + 3 dispatchers (4 tasks)
    Wave 4 (sequential, feature, high complexity): supervisor reasoning loop + CLI steering (2 tasks)
    Wave 5 (parallel, testing, high complexity): smoke, crash-recovery, concurrency+multi-feature integration tests (3 tasks)

  All 47 BDD scenarios from features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature need to bind to these tasks via @task: tags during Step 11 BDD linking.

FLAGS:
  --no-questions: false
  --with-questions: false
  --defaults: false
  --answers: (none)

Ask about:
1. Approach selection (which recommended approach to follow)
2. Execution preference (parallel waves vs sequential, Conductor workspaces)
3. Testing depth (TDD/standard/minimal/default-by-complexity)

Return ClarificationContext with implementation preferences.
Read tasks
The clarification agent is asking implementation preferences. Let me present them to you.

Implementation Preferences (Context B)
Q1 — Approach Selection

A — Accept Option 1 (recommended): reasoning-loop dispatch + StageOrderingGuard
B — Revisit: provide alternative direction before subtask creation begins
R — Recommend (let AI decide based on review findings)
Default: A

Q2 — Execution Preference

P — Parallel within each wave, sequential between waves (as designed)
S — Fully sequential across all 14 subtasks
C — Parallel with Conductor workspaces (isolated worktrees per subtask)
R — Recommend (let AI decide based on dependencies)
Default: P

Q3 — Testing Depth

T — TDD: write failing tests first
D — Default by complexity (high → full coverage, low → smoke only)
S — Standard: unit + integration tests alongside implementation
M — Minimal: smoke only, defer detailed tests
R — Recommend per task
Default: D

Please reply with your answers (e.g. 1:A 2:P 3:D), or defaults to accept all defaults.

command-history.md#2300-2301
Q1:A,Q2:R,Q3:D
Decisions captured: Approach=Option 1, Execution=Recommended (parallel-within-wave, sequential-between-waves matches the dependency DAG), Testing=Default-by-complexity. Let me check that the required CLI scripts are available, then proceed to generate the feature structure.

Bash Check for installed scripts
IN
ls ~/.agentecflow/bin/ 2>/dev/null | head -20; which generate-feature-yaml feature-plan-bdd-link guardkit 2>/dev/null

OUT
Exit code 1
agent-enhance
agent-format
agent-validate
feature-plan-bdd-link
generate-feature-yaml
gk
gki
graphiti-check
graphiti-diagnose
guardkit
guardkit-init
/home/richardwoollcott/.agentecflow/bin/generate-feature-yaml
/home/richardwoollcott/.agentecflow/bin/guardkit
Scripts are available. Creating the feature folder and the 14 task files.

Bash Create feature backlog folder
IN
mkdir -p /home/richardwoollcott/Projects/appmilla_github/forge/tasks/backlog/mode-a-greenfield-end-to-end && echo "ready"

OUT
ready
Write TASK-MAG7-001-define-stage-taxonomy.md
70 lines
---
id: TASK-MAG7-001
title: Define StageClass enum and stage prerequisite map
task_type: declarative
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
tags: [taxonomy, declarative, stage-ordering, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Define StageClass enum and stage prerequisite map

## Description

Define the eight Mode A stage classes as a Python `StrEnum` and a prerequisite
map that encodes the seven prerequisite rows from FEAT-FORGE-007 Group B
Scenario Outline ("A downstream stage is not dispatched before its prerequisite
has reached the approved state").

This is the canonical taxonomy that every guard, dispatcher, and context
builder downstream relies on. It must match the feature spec verbatim.

## Acceptance Criteria

- [ ] `forge.pipeline.stage_taxonomy` module exists at
      `src/forge/pipeline/stage_taxonomy.py`
- [ ] Exports `StageClass(StrEnum)` with members in order:
      `PRODUCT_OWNER`, `ARCHITECT`, `SYSTEM_ARCH`, `SYSTEM_DESIGN`,
      `FEATURE_SPEC`, `FEATURE_PLAN`, `AUTOBUILD`, `PULL_REQUEST_REVIEW`
- [ ] Exports `STAGE_PREREQUISITES: dict[StageClass, list[StageClass]]` with
      exactly seven entries matching the Group B Scenario Outline:
      `architect ← product-owner`, `system-arch ← architect`,
      `system-design ← system-arch`, `feature-spec ← system-design`,
      `feature-plan ← feature-spec` (per feature),
      `autobuild ← feature-plan` (per feature),
      `pull-request ← autobuild for every feature`
- [ ] Exports `CONSTITUTIONAL_STAGES: frozenset[StageClass]` containing
      `PULL_REQUEST_REVIEW`
- [ ] Exports `PER_FEATURE_STAGES: frozenset[StageClass]` containing
      `FEATURE_SPEC`, `FEATURE_PLAN`, `AUTOBUILD`, `PULL_REQUEST_REVIEW`
- [ ] Module docstring references FEAT-FORGE-007 ASSUM-001 and
      ADR-ARCH-026 (constitutional rule)
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is a declarative module with no runtime behaviour beyond providing the
taxonomy. Keep it free of imports from any other `forge.pipeline` module so it
can be imported by all downstream tasks in Waves 2–4 without a cycle.

The eight stage names map onto the
`features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature`
Background and key-example scenarios. Do not rename them.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-002-define-forward-propagation-map.md
70 lines
---
id: TASK-MAG7-002
title: Define forward-propagation contract map
task_type: declarative
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
tags: [forward-propagation, declarative, context-flags, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Define forward-propagation contract map

## Description

Define the producer-to-consumer artefact handshake for each of the seven
non-product-owner stages. This is what tells the
`ForwardContextBuilder` (TASK-MAG7-006) which `stage_log` artefact_path values
to thread into the next stage's `--context` flags.

Encodes Group A scenarios: "The product-owner output is supplied as input to
the architect delegation" and "Architecture outputs are supplied as context for
system design".

## Acceptance Criteria

- [ ] `forge.pipeline.forward_propagation` module exists at
      `src/forge/pipeline/forward_propagation.py`
- [ ] Exports `ContextRecipe` Pydantic model with fields:
      `producer_stage: StageClass`, `artefact_kind: Literal["text", "path", "path-list"]`,
      `context_flag: str` (e.g. `--context`), `description: str`
- [ ] Exports `PROPAGATION_CONTRACT: dict[StageClass, ContextRecipe]` with
      exactly seven entries, one per non-product-owner stage:
      - `ARCHITECT` ← product-owner approved charter (text)
      - `SYSTEM_ARCH` ← architect approved output (text)
      - `SYSTEM_DESIGN` ← system-arch artefact paths (path-list)
      - `FEATURE_SPEC` ← system-design feature catalogue entry (text)
      - `FEATURE_PLAN` ← feature-spec artefact path (path)
      - `AUTOBUILD` ← feature-plan artefact path (path)
      - `PULL_REQUEST_REVIEW` ← autobuild branch ref + commit summary (text)
- [ ] Module passes a self-validation check at import: every key is reachable
      from `PRODUCT_OWNER` via the `STAGE_PREREQUISITES` chain from
      TASK-MAG7-001
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The seven entries mirror the seven prerequisite rows from TASK-MAG7-001 — by
construction every approved-prerequisite produces an artefact that is consumed
by the immediate-downstream stage.

This module imports from `forge.pipeline.stage_taxonomy` (TASK-MAG7-001) but
nothing else from `forge.pipeline.*`. Keep it side-effect free so test modules
can import it without bringing up the substrate.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-003-stage-ordering-guard.md
108 lines
---
id: TASK-MAG7-003
title: Implement StageOrderingGuard
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 2
implementation_mode: task-work
complexity: 5
dependencies: [TASK-MAG7-001]
tags: [guard, stage-ordering, invariant, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-001
    consumes: stage_taxonomy
    framework: "Python forge.pipeline.stage_taxonomy"
    driver: "StrEnum"
    format_note: "Imports StageClass and STAGE_PREREQUISITES from forge.pipeline.stage_taxonomy"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement StageOrderingGuard

## Description

Pure-function guard that, given a `build_id`, returns the set of stage classes
the supervisor is permitted to dispatch on the next reasoning turn. Refuses
any stage whose prerequisites are not all recorded as approved in `stage_log`.

Covers FEAT-FORGE-007 Group B Scenario Outline directly (seven prerequisite
rows) and is the executor-layer half of the stage-ordering invariant — the
reasoning model cannot bypass it via prompt drift.

## Acceptance Criteria

- [ ] `StageOrderingGuard` class exists at
      `src/forge/pipeline/stage_ordering_guard.py`
- [ ] Method `next_dispatchable(build_id: str, stage_log_reader: StageLogReader) -> set[StageClass]`
      returns the set of stages whose prerequisites are all approved
- [ ] Method `is_dispatchable(build_id, stage: StageClass, feature_id: str | None = None) -> bool`
      returns True only if every prerequisite of `stage` for that feature
      (or build, for non-per-feature stages) is approved in `stage_log`
- [ ] Per-feature stages (`FEATURE_SPEC`, `FEATURE_PLAN`, `AUTOBUILD`,
      `PULL_REQUEST_REVIEW`) take a `feature_id` argument and check
      prerequisites scoped to that feature
- [ ] `PULL_REQUEST_REVIEW` requires `AUTOBUILD` approved for *every* feature
      in the catalogue (per Scenario Outline row 7)
- [ ] Unit tests cover all seven prerequisite rows from the Scenario Outline
      verbatim
- [ ] Unit tests cover the multi-feature case (PR review requires all autobuilds)
- [ ] Pure function — no I/O except via the injected `stage_log_reader` Protocol
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

Inject a `StageLogReader` Protocol so tests can supply an in-memory fake
without bringing up SQLite. The production reader is provided by
FEAT-FORGE-001's SQLite adapter.

The pure-function shape (no async, no I/O behind the Protocol) is what makes
this guard the executor-layer enforcer of the stage-ordering invariant
(ADR-ARCH-026 belt-and-braces). If the reasoning model picks a stage whose
prerequisites are not approved, `is_dispatchable` returns False and the
supervisor refuses to act.

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify stage_taxonomy contract from TASK-MAG7-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("stage_taxonomy")
def test_stage_taxonomy_contract():
    """Verify StageClass enum and STAGE_PREREQUISITES match contract.

    Contract: 8 stages, 7 prerequisite rows matching Scenario Outline.
    Producer: TASK-MAG7-001
    """
    from forge.pipeline.stage_taxonomy import StageClass, STAGE_PREREQUISITES

    assert len(StageClass) == 8, "Must have exactly 8 stage classes"
    assert len(STAGE_PREREQUISITES) == 7, "Must have exactly 7 prerequisite rows"
    assert set(STAGE_PREREQUISITES.keys()) == {
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    }
```

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-004-constitutional-guard.md
104 lines
---
id: TASK-MAG7-004
title: Implement ConstitutionalGuard for PR-review enforcement
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 2
implementation_mode: task-work
complexity: 4
dependencies: [TASK-MAG7-001]
tags: [guard, constitutional, security, belt-and-braces, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-001
    consumes: stage_taxonomy
    framework: "Python forge.pipeline.stage_taxonomy"
    driver: "StrEnum"
    format_note: "Imports StageClass and CONSTITUTIONAL_STAGES from forge.pipeline.stage_taxonomy"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement ConstitutionalGuard for PR-review enforcement

## Description

Pure-function guard that enforces the ADR-ARCH-026 belt-and-braces rule for
constitutional stages: pull-request review must always resolve under mandatory
human approval. Refuses auto-approve directives, refuses skip directives, and
refuses any specialist override claim — at the executor layer, independent of
prompt content.

Covers FEAT-FORGE-007 Group C (auto-approve refused, skip refused) and
Group E (security: holds against misconfigured prompt; specialist override
ignored).

## Acceptance Criteria

- [ ] `ConstitutionalGuard` class exists at
      `src/forge/pipeline/constitutional_guard.py`
- [ ] Method `veto_auto_approve(stage: StageClass) -> AutoApproveDecision`
      returns `REFUSED` for any stage in `CONSTITUTIONAL_STAGES`,
      regardless of upstream Coach score
- [ ] Method `veto_skip(stage: StageClass) -> SkipDecision`
      returns `REFUSED_CONSTITUTIONAL` for any stage in
      `CONSTITUTIONAL_STAGES`
- [ ] Method `veto_override_claim(stage: StageClass, claim: dict) -> bool`
      returns True (ignore-the-claim) when stage is constitutional, even if
      the claim asserts authority
- [ ] Returns include a structured rationale string suitable for recording in
      `stage_log.gate_rationale`
- [ ] Unit tests cover Group C @negative @regression scenarios:
      max-Coach-score does not bypass; skip directive refused
- [ ] Unit tests cover Group E @security @regression scenarios:
      misconfigured-prompt scenario, specialist-override claim
- [ ] Pure function — no I/O, no async
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is the executor-layer half of ADR-ARCH-026. The prompt-layer half lives
in the supervisor's GUARDRAILS section (out of scope for this task — it's
already wired in FEAT-FORGE-004's PR-review constitutional rule).

Loss of either layer is a constitutional regression. The Group E security
test deliberately misconfigures the prompt and asserts that this guard still
refuses — that is the canary for the belt-and-braces invariant.

Reference: ADR-ARCH-026 (Constitutional Rules at Two Layers),
FEAT-FORGE-004 ASSUM-004 (constitutional override target identifiers).

## Seam Tests

```python
"""Seam test: verify ConstitutionalGuard refuses auto-approve at PR-review."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("constitutional_pr_review_rule")
def test_constitutional_guard_refuses_pr_auto_approve():
    """Verify executor-layer refusal of auto-approve at PR-review.

    Contract: ADR-ARCH-026 belt-and-braces; PR-review never auto-approves.
    Producer: TASK-MAG7-001 (CONSTITUTIONAL_STAGES set)
    """
    from forge.pipeline.constitutional_guard import ConstitutionalGuard
    from forge.pipeline.stage_taxonomy import StageClass

    guard = ConstitutionalGuard()
    decision = guard.veto_auto_approve(StageClass.PULL_REQUEST_REVIEW)
    assert decision.is_refused, "PR-review must never auto-approve"
```

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-005-per-feature-loop-sequencer.md
77 lines
---
id: TASK-MAG7-005
title: Implement PerFeatureLoopSequencer
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 2
implementation_mode: task-work
complexity: 4
dependencies: [TASK-MAG7-001]
tags: [sequencer, per-feature, autobuild, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-001
    consumes: stage_taxonomy
    framework: "Python forge.pipeline.stage_taxonomy"
    driver: "StrEnum"
    format_note: "Imports StageClass and PER_FEATURE_STAGES from forge.pipeline.stage_taxonomy"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement PerFeatureLoopSequencer

## Description

Pure-function sequencer that refuses to permit a second feature's autobuild
dispatch while any earlier feature's autobuild is still in a non-terminal
lifecycle on the same build. Implements FEAT-FORGE-007 ASSUM-006 (per-feature
autobuild sequencing within a build) — required because each Build has a
single worktree_path and concurrent autobuilds in the same worktree would
create branch contention.

Covers Group D edge-case scenario: "Per-feature inner loops are sequenced so
each feature's autobuild completes before the next feature's autobuild begins".

## Acceptance Criteria

- [ ] `PerFeatureLoopSequencer` class exists at
      `src/forge/pipeline/per_feature_sequencer.py`
- [ ] Method `may_start_autobuild(build_id: str, feature_id: str, stage_log_reader, async_task_reader) -> bool`
      returns False if any prior feature's autobuild is in a non-terminal
      lifecycle (`starting`, `planning_waves`, `running_wave`,
      `awaiting_approval`, `pushing_pr`)
- [ ] Method consults both `stage_log` (terminal completion) and the
      `async_tasks` state channel via `async_task_reader` (live lifecycle,
      DDR-006 `AutobuildState`)
- [ ] Returns True when no autobuild for any earlier feature is non-terminal
- [ ] Unit test: two-feature catalogue, second autobuild dispatch blocked
      while first autobuild lifecycle is `running_wave`
- [ ] Unit test: second autobuild dispatch permitted once first reaches
      `completed`
- [ ] Pure function — no I/O except via injected reader Protocols
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This sequencer is consulted by the supervisor's reasoning loop (TASK-MAG7-010)
just before it would dispatch autobuild for the next feature. The
`StageOrderingGuard` already enforces that the feature's plan is approved;
this sequencer adds the additional cross-feature constraint that no other
autobuild for this build is still in flight.

Inter-feature parallelism is explicitly out of scope for Mode A v1
(FEAT-FORGE-007 ASSUM-006 confirmed). Concurrent *builds* (different
build_ids) remain unaffected — Group F concurrency scenarios still hold.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-006-forward-context-builder.md
100 lines
---
id: TASK-MAG7-006
title: Implement ForwardContextBuilder
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 3
implementation_mode: task-work
complexity: 5
dependencies: [TASK-MAG7-001, TASK-MAG7-002, TASK-MAG7-003]
tags: [context-builder, forward-propagation, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-002
    consumes: forward_propagation_map
    framework: "Python forge.pipeline.forward_propagation"
    driver: "Pydantic ContextRecipe"
    format_note: "Reads PROPAGATION_CONTRACT to know which stage_log artefact_path values to thread into --context flags for each stage"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement ForwardContextBuilder

## Description

Reads the prior approved stage's artefact paths from `stage_log` and assembles
the `--context` flag list that the next stage's dispatcher will pass to its
underlying tool (specialist dispatch or GuardKit subprocess). Implements
forward propagation per the `PROPAGATION_CONTRACT` from TASK-MAG7-002.

Covers Group A scenarios: "The product-owner output is supplied as input to
the architect delegation" and "Architecture outputs are supplied as context
for system design".

## Acceptance Criteria

- [ ] `ForwardContextBuilder` class exists at
      `src/forge/pipeline/forward_context_builder.py`
- [ ] Method `build_for(stage: StageClass, build_id: str, feature_id: str | None) -> list[ContextEntry]`
      returns the context entries (path or text) to thread into the next
      stage's dispatch
- [ ] Reads `stage_log` rows scoped by `build_id`, optionally `feature_id`,
      with `gate_decision='approved'` only — never reads in-progress or
      flagged-for-review entries
- [ ] Refuses to return any entry whose underlying artefact path falls
      outside the build's worktree allowlist (defence-in-depth alongside
      FEAT-FORGE-005)
- [ ] For per-feature stages, scopes the lookup to that feature's prior
      stage entry only
- [ ] Unit tests cover all seven `PROPAGATION_CONTRACT` rows
- [ ] Unit test: in-progress prior stage → empty context (must wait until
      approved)
- [ ] Unit test: artefact path outside allowlist is filtered out with a
      structured warning
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This builder is the *only* place that crosses the boundary from "the build's
recorded history" to "what gets passed to a downstream subprocess". Keeping
the read-side filtering centralised here (approved-only, allowlist-checked)
is what mitigates Risk R-5 (forward-propagation context builder leaks
unapproved or stale artefacts).

Inject a `StageLogReader` Protocol (same one as TASK-MAG7-003) and a
`WorktreeAllowlist` Protocol. Both have production implementations in
FEAT-FORGE-001 (SQLite reader) and FEAT-FORGE-005 (allowlist) respectively.

## Seam Tests

```python
"""Seam test: ForwardContextBuilder threads only approved artefacts."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("forward_propagation_map")
def test_forward_context_builder_skips_unapproved():
    """Verify only approved stage entries are threaded forward.

    Contract: PROPAGATION_CONTRACT rows produce context only from
    stage_log entries with gate_decision='approved'.
    Producer: TASK-MAG7-002
    """
    # Test fixture: stage_log has architect entry with gate_decision='flagged'
    # Builder must return empty context for SYSTEM_ARCH stage
    pass  # Implementation in /task-work
```

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-007-dispatch-specialist-stage.md
82 lines
---
id: TASK-MAG7-007
title: Wire dispatch_specialist_stage for product-owner and architect
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 3
implementation_mode: task-work
complexity: 4
dependencies: [TASK-MAG7-001, TASK-MAG7-006]
tags: [dispatcher, specialist, feat-forge-003, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-006
    consumes: forward_context
    framework: "Python forge.pipeline.forward_context_builder"
    driver: "Internal call"
    format_note: "Receives list[ContextEntry] from ForwardContextBuilder.build_for() and threads into specialist dispatch payload"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire dispatch_specialist_stage for product-owner and architect

## Description

Compose FEAT-FORGE-003's specialist capability dispatch with the
`ForwardContextBuilder` to dispatch the two specialist stages
(`PRODUCT_OWNER`, `ARCHITECT`). The dispatcher records the dispatch in
`stage_log`, awaits the correlation-keyed reply, parses the Coach score, and
produces a stage-complete record consumable by the gating layer
(FEAT-FORGE-004).

Covers Group A: "A greenfield brief drives a full pipeline run" (specialist
half) and "The product-owner output is supplied as input to the architect
delegation".

## Acceptance Criteria

- [ ] `dispatch_specialist_stage(stage: StageClass, build_id: str, ...) -> StageDispatchResult`
      function exists at `src/forge/pipeline/dispatchers/specialist.py`
- [ ] Refuses any stage that is not in `{PRODUCT_OWNER, ARCHITECT}`
      (raises `ValueError` — programming error, not runtime)
- [ ] Calls `ForwardContextBuilder.build_for` to assemble the dispatch
      payload context
- [ ] Delegates to FEAT-FORGE-003's specialist-dispatch tool with the
      capability matching the stage (`product_owner_specialist`,
      `architect_specialist`)
- [ ] Threads the build's `correlation_id` through the dispatch envelope
      (Group I @data-integrity scenario)
- [ ] Records the dispatch as a `stage_log` entry on submit and updates on
      reply with the parsed Coach score and detection findings
- [ ] On degraded specialist (no healthy specialist on cache), returns a
      `StageDispatchResult.DEGRADED` outcome — gating layer maps to
      flag-for-review (Group C @negative scenario "no product-owner specialist")
- [ ] Unit test mocking FEAT-FORGE-003 dispatch surface: success path,
      degraded path, soft-timeout path (retry-with-context)
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This dispatcher is a thin composition layer — it does not re-implement
specialist resolution, capability matching, or correlation handling. All of
that is owned by FEAT-FORGE-003. The dispatcher's job is to stitch the
forward-propagated context onto the specialist call and to write the
`stage_log` entry that downstream guards read.

The retry-with-context behaviour on soft failure (FEAT-FORGE-003 ASSUM-005,
"reasoning-model-driven retry; no fixed max-retry count") is invoked at the
supervisor layer, not here — this dispatcher returns the structured result
and lets the supervisor decide.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-008-dispatch-subprocess-stage.md
87 lines
---
id: TASK-MAG7-008
title: Wire dispatch_subprocess_stage for system-arch, system-design, feature-spec, feature-plan
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 3
implementation_mode: task-work
complexity: 5
dependencies: [TASK-MAG7-001, TASK-MAG7-006]
tags: [dispatcher, subprocess, guardkit, feat-forge-005, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-006
    consumes: forward_context
    framework: "Python forge.pipeline.forward_context_builder"
    driver: "Internal call"
    format_note: "Receives list[ContextEntry] from ForwardContextBuilder.build_for() and converts to --context flag arguments for the GuardKit subprocess invocation"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire dispatch_subprocess_stage

## Description

Compose FEAT-FORGE-005's GuardKit subprocess engine with the
`ForwardContextBuilder` to dispatch the four subprocess stages
(`SYSTEM_ARCH`, `SYSTEM_DESIGN`, `FEATURE_SPEC`, `FEATURE_PLAN`). Constructs
the `--context` flag argument list, invokes the appropriate GuardKit slash
command via the subprocess engine, captures artefact paths, threads
correlation_id, and records the result in `stage_log`.

Covers Group A scenarios: "Forge invokes architecture, design, per-feature
specification, per-feature planning, and autobuild in order" and
"Architecture outputs are supplied as context for system design".

## Acceptance Criteria

- [ ] `dispatch_subprocess_stage(stage, build_id, feature_id=None, ...) -> StageDispatchResult`
      function exists at `src/forge/pipeline/dispatchers/subprocess.py`
- [ ] Maps each stage to its GuardKit slash command:
      `SYSTEM_ARCH` → `/system-arch`,
      `SYSTEM_DESIGN` → `/system-design`,
      `FEATURE_SPEC` → `/feature-spec`,
      `FEATURE_PLAN` → `/feature-plan`
- [ ] Calls `ForwardContextBuilder.build_for` and converts the returned
      entries into `--context <path>` flag arguments
- [ ] Delegates to FEAT-FORGE-005's subprocess engine for execution under
      worktree allowlist confinement
- [ ] Records artefact paths returned by the subprocess in `stage_log`
      `artefact_path` column, attributed by feature_id when applicable
      (Group G @data-integrity scenario "Per-feature artefact paths")
- [ ] Threads correlation_id through subprocess envelope and any pipeline
      events the subprocess publishes (Group I @data-integrity scenario)
- [ ] Subprocess hard-stop / non-zero exit is converted to
      `StageDispatchResult.FAILED` with structured rationale — never
      raises past the function boundary (universal error contract)
- [ ] On `/feature-spec` failure, the result rationale records the
      failed-spec rationale so the supervisor can halt that feature's inner
      loop (Group C @negative scenario)
- [ ] Unit tests cover all four stages with mocked subprocess engine
- [ ] Unit test: subprocess hard-stop converted to structured failure
- [ ] Unit test: artefact path outside allowlist refused
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The four stages share the same dispatch shape; differentiating only by which
GuardKit slash command is invoked and (for per-feature stages) which feature
the dispatch targets. Worktree confinement, allowlist enforcement, and the
universal error contract all live in FEAT-FORGE-005 — this dispatcher is a
thin composition layer.

The `forge.pipeline.dispatchers` package will hold three dispatcher modules
by the end of Wave 3: `specialist`, `subprocess`, and `autobuild_async`.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-009-dispatch-autobuild-async.md
107 lines
---
id: TASK-MAG7-009
title: Wire dispatch_autobuild_async via start_async_task
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 3
implementation_mode: task-work
complexity: 6
dependencies: [TASK-MAG7-001, TASK-MAG7-006]
tags: [dispatcher, async-subagent, autobuild, feat-forge-005, ddr-006, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-006
    consumes: forward_context
    framework: "Python forge.pipeline.forward_context_builder"
    driver: "Internal call"
    format_note: "Receives list[ContextEntry] (specifically the approved feature-plan artefact path for the feature) and threads into autobuild dispatch payload"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire dispatch_autobuild_async via start_async_task

## Description

Dispatch autobuild for a feature as a long-running `AsyncSubAgent` via the
DeepAgents `start_async_task` middleware tool (per ADR-ARCH-031). Returns
immediately with a `task_id` so the supervisor's reasoning loop stays
responsive (Group A: "Autobuild runs as an asynchronous subagent so the
supervisor remains responsive during long runs").

Initialises the `async_tasks` state-channel entry per DDR-006 `AutobuildState`
shape and threads correlation_id through the launched task's context.

## Acceptance Criteria

- [ ] `dispatch_autobuild_async(build_id, feature_id, ...) -> AutobuildDispatchHandle`
      function exists at `src/forge/pipeline/dispatchers/autobuild_async.py`
- [ ] Calls `ForwardContextBuilder.build_for(AUTOBUILD, build_id, feature_id)`
      to get the approved feature-plan artefact path
- [ ] Calls DeepAgents middleware `start_async_task` with the autobuild
      subagent name (`autobuild_runner`) and the assembled context
- [ ] Returns the assigned `task_id` immediately; does not await completion
- [ ] Initialises the `async_tasks` channel entry with an `AutobuildState`
      where `lifecycle="starting"`, `wave_index=0`, `task_index=0`,
      `correlation_id` threaded
- [ ] Records the autobuild dispatch as a `stage_log` entry in
      `state="running"` with the `task_id` stored in `details_json`
- [ ] Two concurrent builds dispatching autobuild at the same time receive
      distinct `task_id` values (Group F @concurrency scenario)
- [ ] Unit test mocking `start_async_task`: successful dispatch returns
      `task_id`, state-channel populated with starting lifecycle
- [ ] Unit test: two concurrent dispatches → two distinct `task_id` values
- [ ] Unit test: correlation_id threaded onto AutobuildState
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The `autobuild_runner` subagent itself (the body of the long-running task)
is owned by FEAT-FORGE-005 + ADR-ARCH-031. This dispatcher's job is the
launch contract: invoke `start_async_task`, populate the state channel,
record the run in `stage_log`.

The runtime lifecycle of `AutobuildState` (transitions through
`planning_waves`, `running_wave`, `awaiting_approval`, `completed`) is
written by `autobuild_runner` itself — this dispatcher only handles the
initial `starting` state.

Crash-recovery semantics (Group D @edge-case "After a crash mid-autobuild
the build's authoritative status comes from durable history not the live
state channel") are tested at integration level in TASK-MAG7-013, but this
dispatcher must record `stage_log` *before* awaiting the `start_async_task`
call so a crash between submit and ack does not leave a state-channel entry
without a `stage_log` row.

## Seam Tests

```python
"""Seam test: dispatch_autobuild_async returns task_id consistent with state channel."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("autobuild_async_task_id")
def test_autobuild_dispatch_task_id_consistency():
    """Verify returned task_id matches AutobuildState entry.

    Contract: DDR-006 AutobuildState.task_id; per-feature unique within build.
    Producer: TASK-MAG7-009
    Consumer: TASK-MAG7-010 (supervisor), TASK-MAG7-011 (CLI steering)
    """
    # Mocked start_async_task returns task_id
    # Verify list_async_tasks reports an AutobuildState entry with same task_id
    pass  # Implementation in /task-work
```

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-010-supervisor-next-turn.md
109 lines
---
id: TASK-MAG7-010
title: Wire Supervisor.next_turn dispatch loop
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 4
implementation_mode: task-work
complexity: 7
dependencies: [TASK-MAG7-003, TASK-MAG7-004, TASK-MAG7-005, TASK-MAG7-007, TASK-MAG7-008, TASK-MAG7-009]
tags: [supervisor, reasoning-loop, langgraph, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-003
    consumes: stage_ordering_decision
    framework: "Python forge.pipeline.stage_ordering_guard"
    driver: "StageOrderingGuard"
    format_note: "Calls next_dispatchable() to get permitted set; refuses to act outside the set"
  - task: TASK-MAG7-004
    consumes: constitutional_decision
    framework: "Python forge.pipeline.constitutional_guard"
    driver: "ConstitutionalGuard"
    format_note: "Calls veto_auto_approve / veto_skip on PR-review stage"
  - task: TASK-MAG7-005
    consumes: per_feature_sequencing_decision
    framework: "Python forge.pipeline.per_feature_sequencer"
    driver: "PerFeatureLoopSequencer"
    format_note: "Calls may_start_autobuild before dispatching second feature's autobuild"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire Supervisor.next_turn dispatch loop

## Description

The supervisor's reasoning-loop turn function. On each turn for a build:
queries `StageOrderingGuard.next_dispatchable` to get the permitted set,
asks the reasoning model which permitted dispatch to execute, applies
`PerFeatureLoopSequencer` and `ConstitutionalGuard` as additional gates,
invokes the appropriate dispatcher (specialist / subprocess / autobuild
async), records the outcome via FEAT-FORGE-001's state machine, and returns
control to the supervisor's outer loop.

Covers Group A key examples (full chain to PR-awaiting-review, async-subagent
dispatch, flag-resume cycle) and Group F concurrency (supervisor dispatches
second build's stage during first build's autobuild).

## Acceptance Criteria

- [ ] `Supervisor.next_turn(build_id: str) -> TurnOutcome` method exists at
      `src/forge/pipeline/supervisor.py`
- [ ] Reads current build state from FEAT-FORGE-001's state machine
- [ ] Queries `StageOrderingGuard.next_dispatchable` for permitted stages
- [ ] If permitted set is empty and build is in non-terminal state, returns
      `TurnOutcome.WAITING` (e.g. waiting on approval response)
- [ ] If permitted set non-empty, presents the set to the reasoning model
      with the per-stage dispatch context (forward-propagation hints from
      TASK-MAG7-002) and parses the chosen dispatch
- [ ] Refuses to act on any reasoning-model choice outside the permitted set
      (executor-layer enforcement; logs structured warning)
- [ ] For `AUTOBUILD` choices, calls `PerFeatureLoopSequencer.may_start_autobuild`
      first; if False, returns `TurnOutcome.WAITING_PRIOR_AUTOBUILD`
- [ ] For `PULL_REQUEST_REVIEW` gate decisions, applies `ConstitutionalGuard`
      veto_auto_approve before recording any auto-approve decision
- [ ] Routes the dispatch to the appropriate dispatcher:
      `PRODUCT_OWNER`/`ARCHITECT` → specialist,
      `SYSTEM_ARCH`/`SYSTEM_DESIGN`/`FEATURE_SPEC`/`FEATURE_PLAN` → subprocess,
      `AUTOBUILD` → autobuild_async,
      `PULL_REQUEST_REVIEW` → gate decision via FEAT-FORGE-004
- [ ] Records every turn's outcome in `stage_log` with full rationale
- [ ] Concurrent builds: each `build_id` gets its own independent
      `next_turn` invocation; no shared mutable state across builds
- [ ] Unit tests with mocked guards + dispatchers covering: full happy path,
      reasoning-model picks non-permitted stage (refused), per-feature
      sequencing kicks in, constitutional veto fires on PR-review
- [ ] Integration test (mock-substrate): two concurrent builds, supervisor
      dispatches both without cross-talk
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is the largest piece of net-new code in FEAT-FORGE-007 — but it is
mostly orchestration over the guards and dispatchers from Waves 2 and 3.
Keep it I/O-thin: it owns no state, only references to the substrate
adapters and dispatchers it composes.

The reasoning-model prompt for this loop must enumerate the eight stage
classes (TASK-MAG7-001) and the forward-propagation hints (TASK-MAG7-002)
in the GUARDRAILS section, so the model has the full taxonomy in view. The
ADR-ARCH-026 belt-and-braces invariant is preserved because the guards
re-check every choice independently of prompt content.

Approval-response handling (Group A "flagged-for-review checkpoint pauses
the build") is delegated to FEAT-FORGE-004's approval round-trip; the
supervisor's `next_turn` is invoked again once an approval response resumes
the build. Idempotent first-wins (Group D "duplicate approval response is
ignored") is also FEAT-FORGE-004's responsibility.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-011-cli-steering-injection.md
96 lines
---
id: TASK-MAG7-011
title: Wire CLI steering injection (cancel, skip, mid-flight directive)
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 4
implementation_mode: task-work
complexity: 5
dependencies: [TASK-MAG7-004, TASK-MAG7-009, TASK-MAG7-010]
tags: [cli, steering, cancel, skip, directives, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-004
    consumes: constitutional_decision
    framework: "Python forge.pipeline.constitutional_guard"
    driver: "ConstitutionalGuard"
    format_note: "Calls veto_skip to refuse skip directive on PR-review stage"
  - task: TASK-MAG7-009
    consumes: autobuild_async_task_id
    framework: "Python deepagents middleware"
    driver: "update_async_task / cancel_async_task"
    format_note: "Uses task_id from dispatch_autobuild_async to inject directives or cancel running autobuild"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire CLI steering injection

## Description

Wire CLI steering directives (`forge cancel`, `forge skip`, mid-flight
directive injection) to the supervisor's pause/dispatch surface and the
async-subagent state channel. Implements the synthetic-decision mapping
specified in FEAT-FORGE-004 ASSUM-005 (cancel → reject, skip → override) and
honours the constitutional refusal at PR-review.

Covers Group D edge cases (cancel during pause, cancel during autobuild, skip
on non-constitutional stage, mid-flight directive injection) and Group C
@negative @regression (skip refused at PR-review).

## Acceptance Criteria

- [ ] `CliSteeringHandler` class exists at
      `src/forge/pipeline/cli_steering.py`
- [ ] Method `handle_cancel(build_id: str) -> CancelOutcome`:
      - If build is paused at a flagged-for-review checkpoint, resolves as
        synthetic reject with cancel rationale → terminal `CANCELLED`
      - If build is in autobuild, calls `cancel_async_task(task_id)` and
        marks build terminal `CANCELLED` with no PR-creation attempted
      - If build is in any other non-terminal state, transitions to
        `CANCELLED` and refuses to dispatch any further stage
- [ ] Method `handle_skip(build_id: str, stage: StageClass) -> SkipOutcome`:
      - Calls `ConstitutionalGuard.veto_skip(stage)`; if refused, records
        `SKIP_REFUSED_CONSTITUTIONAL` rationale and leaves build paused
      - Otherwise records the stage as `SKIPPED` in `stage_log` and resumes
        at next stage
- [ ] Method `handle_directive(build_id, feature_id, directive_text: str)`:
      - For active autobuild, calls `update_async_task` to append to
        `AutobuildState.pending_directives`
      - Returns immediately; autobuild itself decides when to honour the
        directive (Group D scenario "directive appears as pending")
- [ ] Cancel during pause: pause resolves as synthetic reject (Group D)
- [ ] Skip on non-constitutional stage: stage recorded as skipped, chain
      resumes (Group D)
- [ ] Skip on PR-review: refused, build remains paused, refusal recorded
      (Group C @regression)
- [ ] Unit tests cover all three methods with mocked supervisor + state
      channel + constitutional guard
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The CLI surface (`forge cancel`, `forge skip`) is owned by FEAT-FORGE-001
(CLI commands) — this task wires those CLI commands to the supervisor by
implementing the handler methods that the CLI calls into.

`update_async_task` and `cancel_async_task` are middleware tools provided
by DeepAgents (per DDR-006); call them directly through the middleware
adapter, not via subprocess.

The synthetic-decision mapping (cancel→reject, skip→override) was specified
once in FEAT-FORGE-004 — do not re-specify it here. This task only owns the
*injection* of those synthetic decisions into the supervisor's pause
resolution surface.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-012-smoke-greenfield-e2e.md
75 lines
---
id: TASK-MAG7-012
title: Smoke test - minimal greenfield brief to PR-awaiting-review
task_type: testing
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 5
implementation_mode: task-work
complexity: 5
dependencies: [TASK-MAG7-010, TASK-MAG7-011]
tags: [testing, smoke, integration, end-to-end, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Smoke test — minimal greenfield brief to PR-awaiting-review

## Description

End-to-end smoke test that drives a one-line product brief through every
Mode A stage with auto-approval at every flagged-for-review checkpoint, and
asserts the build terminates paused at pull-request review awaiting human
approval with a recorded PR URL.

Covers Group H @smoke @integration scenarios:
- "A minimal greenfield brief drives a single-feature run to a pull request
  awaiting human review"
- "A greenfield build with no available specialists is flagged for review
  at every specialist stage" (degraded path)

## Acceptance Criteria

- [ ] Test module exists at
      `tests/integration/test_mode_a_smoke.py`
- [ ] Test fixture `greenfield_brief_pipeline` brings up: a fake
      specialist registry pre-populated with healthy product-owner +
      architect specialists, a fake GuardKit subprocess engine returning
      canned approved artefacts, an in-memory SQLite, and a stub approval
      channel that auto-approves
- [ ] Smoke test: queue one-line brief, drive supervisor turns until
      terminal, assert build is paused at PR-review with mandatory_human
      gate mode, PR URL recorded in `stage_log`
- [ ] Smoke test asserts `stage_log` contains the eight-stage chain in
      canonical order (Group G @data-integrity scenario covered as part
      of smoke)
- [ ] Degraded test: same harness with empty specialist registry; assert
      build is flagged for review at product-owner stage with degraded
      rationale, no architect dispatch occurred
- [ ] Tests use the existing `FakeClock` pattern from
      `src/forge/pipeline.py` for deterministic timing
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is the headline smoke for FEAT-FORGE-007 — it asserts that the
composition works end-to-end. Keep the harness small: real substrate
adapters (FEAT-FORGE-001 SQLite, FEAT-FORGE-005 subprocess engine) are
mocked at their Protocol boundaries; only the FEAT-FORGE-007 net-new code
runs for real.

The auto-approval-at-every-checkpoint is the canary — if any
non-constitutional gate fails to auto-approve under high Coach scores, the
smoke fails and identifies the gate decision that diverged.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-013-crash-recovery-integration.md
84 lines
---
id: TASK-MAG7-013
title: Crash-recovery integration tests across all seven non-terminal stages
task_type: testing
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 5
implementation_mode: task-work
complexity: 6
dependencies: [TASK-MAG7-010, TASK-MAG7-011]
tags: [testing, crash-recovery, durable-history, integration, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Crash-recovery integration tests across all seven non-terminal stages

## Description

Integration tests covering FEAT-FORGE-007 Group D crash-recovery Scenario
Outline: a crash during any non-terminal stage triggers retry-from-scratch
on runtime restart. Also covers the durable-history-vs-advisory-state-channel
invariant (ASSUM-004): on crash mid-autobuild, the build's authoritative
status comes from durable history, not the live state channel.

Covers Group D @edge-case scenarios:
- "A crash during any non-terminal stage is recovered by retry-from-scratch"
  (seven examples: product-owner, architect, architecture, system-design,
  feature-spec, feature-plan, autobuild)
- "After a crash mid-autobuild the build's authoritative status comes from
  durable history not the live state channel"

## Acceptance Criteria

- [ ] Test module exists at
      `tests/integration/test_mode_a_crash_recovery.py`
- [ ] Parameterised test covers all seven stage classes from the Scenario
      Outline; for each:
      - Drive supervisor to that stage's mid-flight state
      - Trigger a fake crash (instantiate fresh supervisor against the
        same SQLite + state channel)
      - Assert build re-enters `preparing` state
      - Assert prior in-flight stage is reattempted from start
      - Assert no duplicate `stage_log` entry written for the
        re-attempted stage (idempotent retry)
- [ ] Mid-autobuild crash test:
      - Driver dispatches autobuild, waits until `AutobuildState.lifecycle`
        reaches `running_wave`
      - Triggers crash; on restart, supervisor consults `stage_log`
        (authoritative) and ignores `async_tasks` channel data (advisory)
      - Asserts build restarts autobuild from scratch
- [ ] Notification-publish-failure test (Group G @data-integrity):
      - Stub publisher raises `PublishFailure`
      - Assert stage still recorded as approved in `stage_log`
      - Assert next stage's prerequisite still evaluates as satisfied
- [ ] Long-term-memory-seeding-failure test (Group I @data-integrity):
      - Stub LTM seeder raises
      - Assert stage still recorded as approved
- [ ] All tests use FakeClock; no real wall-clock waits
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

The "crash" simulation is implemented by tearing down the supervisor
instance and instantiating a fresh one against the same SQLite and the same
LangGraph state channel. This exercises the same code path that runs after
a process restart.

The seven-stage parameterisation maps directly to the Group D Scenario
Outline. Asserting `re-enters preparing state` is the canary for the
retry-from-scratch policy — if any stage's recovery path tries to resume
mid-flight instead, this test fails.

## Test Execution Log

[Automatically populated by /task-work]
Write TASK-MAG7-014-concurrency-multifeature-integration.md
105 lines
---
id: TASK-MAG7-014
title: Concurrency and multi-feature integration tests
task_type: testing
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 5
implementation_mode: task-work
complexity: 7
dependencies: [TASK-MAG7-010, TASK-MAG7-011]
tags: [testing, concurrency, multi-feature, integration, feat-forge-007]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Concurrency and multi-feature integration tests

## Description

Integration tests covering the concurrency, multi-feature, and integrity
invariants of Mode A: two concurrent builds with isolated channels, supervisor
dispatching during long-running autobuild, multi-feature catalogues with
per-feature sequencing, correlation-identifier threading, calibration-priors
snapshot stability, first-wins idempotency, and the constitutional
belt-and-braces test against a misconfigured prompt.

Covers Group F @concurrency, Group H @integration (multi-feature), Group E
@security (constitutional + worktree confinement), Group G + Group I
@data-integrity, and Group D / Group I idempotency scenarios.

## Acceptance Criteria

- [ ] Test module exists at
      `tests/integration/test_mode_a_concurrency_and_integrity.py`
- [ ] Two-concurrent-builds test (Group F):
      - Queue two builds with distinct correlation_ids
      - Drive both supervisors' `next_turn` interleaved
      - Assert each build has a distinct autobuild `task_id`
      - Assert each build's approval pause resolves only on a response
        matching its own `build_id` (Group D edge-case)
      - Assert second build's product-owner stage dispatches without
        waiting for first build's autobuild to complete (Group F)
- [ ] Multi-feature integration test (Group H):
      - System-design fixture returns a 3-feature catalogue
      - Drive build to terminal; assert one /feature-spec, one /feature-plan,
        one autobuild stage entry per feature
      - Assert one PR-review pause per feature
      - Assert per-feature artefact paths attributed correctly (no path
        attributed to >1 feature) — Group G @data-integrity
- [ ] Per-feature sequencing test (Group D ASSUM-006):
      - Three-feature catalogue
      - Assert no second autobuild dispatch begins while a first autobuild
        is still in non-terminal lifecycle
- [ ] Correlation threading test (Group I @data-integrity):
      - Drive build to terminal
      - Assert every published lifecycle event for that build carries the
        same correlation_id
- [ ] Calibration priors snapshot test (Group I @data-integrity):
      - Capture snapshot at build start
      - Mutate operator's calibration history mid-run
      - Assert later stages still use the priors snapshot from build start
- [ ] First-wins idempotency test (Group D + Group I @concurrency):
      - Build paused at a checkpoint
      - Inject two simultaneous approval responses with different decisions
      - Assert exactly one decision applied, no double-resume
- [ ] Constitutional misconfigured-prompt test (Group E @security @regression):
      - Stub the supervisor's reasoning model with a configuration that
        emits an auto-approve directive at PR-review
      - Assert `ConstitutionalGuard` still refuses; build remains paused
- [ ] Specialist override-claim test (Group E @security):
      - Specialist returns a claim asserting override of PR-review rule
      - Assert claim is ignored at gating; build pauses for mandatory human
- [ ] Worktree confinement test (Group E @security):
      - Subprocess dispatch attempts to write outside the worktree
      - Assert refused; no path outside allowlist writable
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is the most comprehensive integration test in Wave 5 — it covers all
the cross-cutting invariants that no single Wave 2/3 unit test can assert.
The test harness reuses the `greenfield_brief_pipeline` fixture from
TASK-MAG7-012, parameterised with multi-feature and concurrent-build
variations.

The constitutional misconfigured-prompt test is the canary for ADR-ARCH-026
belt-and-braces: it deliberately breaks one layer (prompt) and asserts the
other (executor guard) still holds. Loss of this test passing is a
constitutional regression.

The first-wins test exercises the full FEAT-FORGE-004 idempotency path
through the supervisor — this is the integration-level companion to the
unit-level idempotency tests in FEAT-FORGE-004.

## Test Execution Log

[Automatically populated by /task-work]
All 14 task files created. Now generating the IMPLEMENTATION-GUIDE.md with mandatory Mermaid diagrams.

Write IMPLEMENTATION-GUIDE.md
420 lines
# Implementation Guide — FEAT-FORGE-007 Mode A Greenfield End-to-End

**Generated**: 2026-04-25
**Source review**: [TASK-REV-MAG7](../../../tasks/backlog/TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md)
**Review report**: [.claude/reviews/TASK-REV-MAG7-review-report.md](../../../.claude/reviews/TASK-REV-MAG7-review-report.md)
**Approach**: Option 1 — Reasoning-loop-driven dispatch with deterministic StageOrderingGuard
**Total tasks**: 14 across 5 waves
**Estimated effort**: 12–16 hours focused implementation

---

## §1: Approach Summary

FEAT-FORGE-007 is a **composition feature**. It introduces no new transitions,
transports, or gate modes. Every primitive it relies on is already specified in
FEAT-FORGE-001 through FEAT-FORGE-006. The work is *purely orchestration* — wiring
the supervisor's reasoning loop to dispatch the eight Mode A stage classes in
order, threading each stage's approved output forward, launching autobuild as
an `AsyncSubAgent`, and ensuring constitutional invariants and crash-recovery
contracts hold.

The recommended approach pairs:

- A **deterministic `StageOrderingGuard`** (pure function over `stage_log`) that
  refuses any dispatch whose prerequisites aren't approved
- A **`ConstitutionalGuard`** that refuses auto-approve and skip on PR-review
  (executor-layer half of ADR-ARCH-026 belt-and-braces)
- A **`PerFeatureLoopSequencer`** that refuses a second autobuild while the
  prior feature's autobuild is non-terminal (ASSUM-006)
- A **`ForwardContextBuilder`** that assembles `--context` flags from approved
  prior stage artefacts only (mitigates Risk R-5)
- The **LangGraph supervisor's reasoning loop** that selects which permitted
  dispatch to execute on each turn

The reasoning model selects *what* to dispatch; the guards enforce *what is
permitted*. The asymmetry preserves ADR-ARCH-026 (prompt drift cannot bypass
executor invariants).

---

## §2: Data Flow — Read/Write Paths

```mermaid
flowchart LR
    subgraph Writes["Write Paths (FEAT-FORGE-007 net-new)"]
        W1["dispatch_specialist_stage()"]
        W2["dispatch_subprocess_stage()"]
        W3["dispatch_autobuild_async()"]
        W4["Supervisor.next_turn()"]
        W5["CliSteeringHandler.handle_*()"]
    end

    subgraph Storage["Storage (substrate)"]
        S1[("stage_log\n(SQLite, FEAT-FORGE-001)")]
        S2[("async_tasks\n(LangGraph state channel,\nDDR-006)")]
        S3[("build_state\n(SQLite, FEAT-FORGE-001)")]
    end

    subgraph Reads["Read Paths (FEAT-FORGE-007 net-new + consumers)"]
        R1["StageOrderingGuard\n.next_dispatchable()"]
        R2["ForwardContextBuilder\n.build_for()"]
        R3["PerFeatureLoopSequencer\n.may_start_autobuild()"]
        R4["forge status (CLI)"]
        R5["forge history (CLI)"]
        R6["CLI cancel/skip handler"]
    end

    W1 -->|"records dispatch + result"| S1
    W2 -->|"records dispatch + result + artefact_path"| S1
    W3 -->|"records dispatch (state=running)"| S1
    W3 -->|"initialises AutobuildState (lifecycle=starting)"| S2
    W4 -->|"records turn outcome + transitions"| S3
    W5 -->|"records cancel/skip rationale"| S1
    W5 -->|"updates pending_directives,\nlifecycle=cancelled"| S2

    S1 -->|"approved entries only"| R1
    S1 -->|"approved artefact_path values"| R2
    S1 -->|"prior feature's autobuild status"| R3
    S2 -->|"lifecycle non-terminal check"| R3
    S1 -->|"full chain in canonical order"| R5
    S2 -->|"live wave/task indices (advisory)"| R4
    S2 -->|"task_id for cancel/update_async_task"| R6

    style W3 fill:#ffe,stroke:#990
    style S2 fill:#eef,stroke:#009
```

_Every write path has a corresponding read path. No disconnected flows.
`async_tasks` is advisory on recovery; `stage_log` is authoritative._

---

## §3: Integration Contract (Stage Dispatch Sequence)

```mermaid
sequenceDiagram
    participant CLI as forge queue (CLI)
    participant Sup as Supervisor.next_turn
    participant Guard as StageOrderingGuard
    participant CGuard as ConstitutionalGuard
    participant FCB as ForwardContextBuilder
    participant Disp as Stage Dispatcher
    participant Sub as Substrate (FEAT-FORGE-003/004/005/006)
    participant Log as stage_log

    CLI->>Sup: build_id queued
    loop reasoning turn
        Sup->>Guard: next_dispatchable(build_id)
        Guard->>Log: read approved entries
        Log-->>Guard: prior approvals
        Guard-->>Sup: permitted_set
        Sup->>Sup: reasoning_model picks chosen ∈ permitted_set
        Sup->>FCB: build_for(chosen, build_id, feature_id)
        FCB->>Log: read approved artefacts
        Log-->>FCB: artefact_paths
        FCB-->>Sup: context_entries
        alt chosen is PULL_REQUEST_REVIEW
            Sup->>CGuard: veto_auto_approve(chosen)
            CGuard-->>Sup: REFUSED → mandatory_human gate
        end
        Sup->>Disp: dispatch(chosen, context_entries)
        Disp->>Sub: invoke (specialist / subprocess / start_async_task)
        Sub-->>Disp: result + artefact_path
        Disp->>Log: write stage_log entry (gate_decision)
    end
    Sup->>CLI: build paused at PR-review (mandatory_human)
```

_Every dispatch is gated by `StageOrderingGuard`; PR-review is additionally
gated by `ConstitutionalGuard`. The reasoning model only chooses **within**
the permitted set._

---

## §4: Integration Contracts

### Contract: stage_taxonomy

- **Producer task**: TASK-MAG7-001
- **Consumer task(s)**: TASK-MAG7-003, TASK-MAG7-004, TASK-MAG7-005, TASK-MAG7-007, TASK-MAG7-008
- **Artefact type**: Python module (importable symbols)
- **Format constraint**: `forge.pipeline.stage_taxonomy` must export
  `StageClass(StrEnum)` with eight members in canonical order, plus
  `STAGE_PREREQUISITES: dict[StageClass, list[StageClass]]` with exactly
  seven entries matching the Group B Scenario Outline verbatim
- **Validation method**: Coach asserts
  `len(StageClass) == 8 and len(STAGE_PREREQUISITES) == 7` and that the
  prerequisite map keys equal the seven downstream stages from the Scenario
  Outline. Seam test in TASK-MAG7-003 validates at runtime.

### Contract: forward_propagation_map

- **Producer task**: TASK-MAG7-002
- **Consumer task(s)**: TASK-MAG7-006
- **Artefact type**: Python module (importable symbols)
- **Format constraint**: `forge.pipeline.forward_propagation` must export
  `PROPAGATION_CONTRACT: dict[StageClass, ContextRecipe]` with exactly
  seven entries (one per non-product-owner stage). Each recipe must reference
  the producer-stage artefact kind (`text` / `path` / `path-list`) consumed
  by the next stage.
- **Validation method**: At import time, the module self-checks that every
  key is reachable from `PRODUCT_OWNER` via the `STAGE_PREREQUISITES` chain
  from TASK-MAG7-001. Coach asserts that `len(PROPAGATION_CONTRACT) == 7`.

### Contract: forward_context

- **Producer task**: TASK-MAG7-006
- **Consumer task(s)**: TASK-MAG7-007, TASK-MAG7-008, TASK-MAG7-009
- **Artefact type**: in-process Python return value
  (`list[ContextEntry]`)
- **Format constraint**: Each `ContextEntry` carries a kind (`path` /
  `text`) and a value. Path entries must satisfy the worktree allowlist
  (FEAT-FORGE-005); the builder filters disallowed paths before returning.
  The list reflects only entries with `gate_decision='approved'`.
- **Validation method**: Seam tests in each consumer dispatcher assert that
  passing an in-memory fixture with `flagged-for-review` entries yields
  empty context, and that an out-of-allowlist path is filtered out.

### Contract: constitutional_decision

- **Producer task**: TASK-MAG7-004
- **Consumer task(s)**: TASK-MAG7-010 (Supervisor), TASK-MAG7-011 (CliSteeringHandler)
- **Artefact type**: in-process Python return value (Pydantic model)
- **Format constraint**: `AutoApproveDecision` and `SkipDecision` values
  carry an `is_refused: bool` flag and a structured rationale. For any
  `stage in CONSTITUTIONAL_STAGES`, `is_refused` MUST be `True` regardless
  of arguments — this is the executor half of ADR-ARCH-026.
- **Validation method**: Seam test in TASK-MAG7-004 asserts that
  `veto_auto_approve(PULL_REQUEST_REVIEW).is_refused == True`. Group E
  integration test (TASK-MAG7-014) deliberately misconfigures the prompt
  and asserts that the executor still refuses.

### Contract: per_feature_sequencing_decision

- **Producer task**: TASK-MAG7-005
- **Consumer task(s)**: TASK-MAG7-010 (Supervisor)
- **Artefact type**: in-process Python return value (`bool`)
- **Format constraint**: `may_start_autobuild(build_id, feature_id, ...)`
  returns `True` only when no prior feature's autobuild is in a
  non-terminal lifecycle on the same `build_id`. Non-terminal lifecycle
  states are defined per DDR-006: `starting`, `planning_waves`,
  `running_wave`, `awaiting_approval`, `pushing_pr`.
- **Validation method**: Unit test asserts the False branch when prior
  autobuild is `running_wave`; integration test in TASK-MAG7-014 asserts
  the cross-feature sequencing under a 3-feature catalogue.

### Contract: autobuild_async_task_id

- **Producer task**: TASK-MAG7-009
- **Consumer task(s)**: TASK-MAG7-010 (Supervisor), TASK-MAG7-011 (CliSteeringHandler)
- **Artefact type**: `task_id: str` returned from `start_async_task`,
  also persisted in `stage_log.details_json["task_id"]` and on the
  `async_tasks` state channel via `AutobuildState.task_id`
- **Format constraint**: `task_id` must be unique per autobuild dispatch
  within a build (DDR-006). Two concurrent builds dispatching autobuild
  must receive distinct `task_id` values (Group F @concurrency).
- **Validation method**: Seam test in TASK-MAG7-009 asserts that the
  returned `task_id` matches the value reported by `list_async_tasks`.
  Integration test in TASK-MAG7-014 asserts cross-build distinctness.

### Contract: stage_ordering_decision

- **Producer task**: TASK-MAG7-003
- **Consumer task(s)**: TASK-MAG7-010 (Supervisor)
- **Artefact type**: in-process Python return value (`set[StageClass]`)
- **Format constraint**: `next_dispatchable(build_id, ...)` returns the
  exact set of stages whose prerequisites are all approved. Empty set
  when nothing is dispatchable (e.g. build is awaiting approval response).
- **Validation method**: Unit tests cover all seven prerequisite rows
  from the Group B Scenario Outline verbatim. Supervisor integration test
  (TASK-MAG7-014) asserts the supervisor refuses to act on any choice
  outside this set even if the reasoning model picks one.

---

## §5: Task Dependency Graph

```mermaid
graph TD
    T1[TASK-MAG7-001<br/>StageClass enum] --> T3[TASK-MAG7-003<br/>StageOrderingGuard]
    T1 --> T4[TASK-MAG7-004<br/>ConstitutionalGuard]
    T1 --> T5[TASK-MAG7-005<br/>PerFeatureLoopSequencer]
    T2[TASK-MAG7-002<br/>Forward-propagation map] --> T6[TASK-MAG7-006<br/>ForwardContextBuilder]
    T1 --> T6
    T3 --> T6
    T1 --> T7[TASK-MAG7-007<br/>dispatch_specialist_stage]
    T6 --> T7
    T1 --> T8[TASK-MAG7-008<br/>dispatch_subprocess_stage]
    T6 --> T8
    T1 --> T9[TASK-MAG7-009<br/>dispatch_autobuild_async]
    T6 --> T9
    T3 --> T10[TASK-MAG7-010<br/>Supervisor.next_turn]
    T4 --> T10
    T5 --> T10
    T7 --> T10
    T8 --> T10
    T9 --> T10
    T4 --> T11[TASK-MAG7-011<br/>CLI steering]
    T9 --> T11
    T10 --> T11
    T10 --> T12[TASK-MAG7-012<br/>Smoke E2E]
    T11 --> T12
    T10 --> T13[TASK-MAG7-013<br/>Crash-recovery integration]
    T11 --> T13
    T10 --> T14[TASK-MAG7-014<br/>Concurrency + multi-feature]
    T11 --> T14

    style T1 fill:#cfc,stroke:#090
    style T2 fill:#cfc,stroke:#090
    style T3 fill:#cfc,stroke:#090
    style T4 fill:#cfc,stroke:#090
    style T5 fill:#cfc,stroke:#090
    style T6 fill:#cfc,stroke:#090
    style T7 fill:#cfc,stroke:#090
    style T8 fill:#cfc,stroke:#090
    style T9 fill:#cfc,stroke:#090
    style T12 fill:#cfc,stroke:#090
    style T13 fill:#cfc,stroke:#090
    style T14 fill:#cfc,stroke:#090
```

_Tasks shaded green can run in parallel within their wave. Wave 4
(TASK-MAG7-010 → TASK-MAG7-011) is sequential; Wave 5 tests are parallel
once Wave 4 lands._

---

## §6: Execution Strategy — 5 Waves

### Wave 1 — Foundations (parallel, 2 tasks, ~1h)

| Task | Complexity | Mode | Estimated |
|------|-----------:|------|----------:|
| TASK-MAG7-001 — StageClass enum + STAGE_PREREQUISITES | 2 | direct | 30m |
| TASK-MAG7-002 — Forward-propagation contract map | 2 | direct | 30m |

**Parallel-safe**: Yes. Both files are net-new in
`src/forge/pipeline/` with no overlap.

### Wave 2 — Core Guards (parallel, 3 tasks, ~3.5h)

| Task | Complexity | Mode | Estimated |
|------|-----------:|------|----------:|
| TASK-MAG7-003 — StageOrderingGuard | 5 | task-work | 90m |
| TASK-MAG7-004 — ConstitutionalGuard | 4 | task-work | 60m |
| TASK-MAG7-005 — PerFeatureLoopSequencer | 4 | task-work | 60m |

**Parallel-safe**: Yes. Each file is independent. All three depend only on
TASK-MAG7-001.

### Wave 3 — Stage Dispatchers + Context Builder (parallel, 4 tasks, ~6h)

| Task | Complexity | Mode | Estimated |
|------|-----------:|------|----------:|
| TASK-MAG7-006 — ForwardContextBuilder | 5 | task-work | 90m |
| TASK-MAG7-007 — dispatch_specialist_stage | 4 | task-work | 75m |
| TASK-MAG7-008 — dispatch_subprocess_stage | 5 | task-work | 90m |
| TASK-MAG7-009 — dispatch_autobuild_async | 6 | task-work | 120m |

**Parallel-safe**: Yes once TASK-MAG7-006 lands first (it's a dependency
of 007/008/009). Within Wave 3, run TASK-MAG7-006 first then the three
dispatchers in parallel.

### Wave 4 — Supervisor + CLI Steering (sequential, 2 tasks, ~4h)

| Task | Complexity | Mode | Estimated |
|------|-----------:|------|----------:|
| TASK-MAG7-010 — Supervisor.next_turn | 7 | task-work | 150m |
| TASK-MAG7-011 — CLI steering injection | 5 | task-work | 90m |

**Parallel-safe**: No. TASK-MAG7-011 depends on TASK-MAG7-010's supervisor
surface. Run sequentially.

### Wave 5 — Integration Tests (parallel, 3 tasks, ~6h)

| Task | Complexity | Mode | Estimated |
|------|-----------:|------|----------:|
| TASK-MAG7-012 — Smoke greenfield E2E | 5 | task-work | 90m |
| TASK-MAG7-013 — Crash-recovery integration | 6 | task-work | 120m |
| TASK-MAG7-014 — Concurrency + multi-feature | 7 | task-work | 150m |

**Parallel-safe**: Yes. All three test modules are independent; all share
the same `greenfield_brief_pipeline` fixture but each parameterises
independently.

---

## §7: Risk Register & Mitigations

| ID | Risk | Severity | Addressed by |
|----|------|----------|--------------|
| R-1 | Reasoning model dispatches stage out of order | High | TASK-MAG7-003 (executor refuses non-permitted choices) + TASK-MAG7-014 integration test |
| R-2 | Autobuild crash leaves SQLite ↔ state-channel divergent | High | DDR-006 SQLite-as-authoritative + TASK-MAG7-013 |
| R-3 | Per-feature loop dispatches second autobuild prematurely | Medium | TASK-MAG7-005 + TASK-MAG7-014 |
| R-4 | Constitutional belt-and-braces drift (prompt vs executor) | Medium | TASK-MAG7-004 + TASK-MAG7-014 misconfigured-prompt test |
| R-5 | Forward-propagation leaks unapproved/stale artefacts | High | TASK-MAG7-006 (approved-only filter + allowlist check) |
| R-6 | Concurrent builds collide on supervisor or approval channel | Medium | FEAT-FORGE-002/004 build-keyed channels + TASK-MAG7-014 |
| R-7 | First-wins idempotency violation | Medium | FEAT-FORGE-004 idempotency + TASK-MAG7-014 |
| R-8 | Calibration-priors snapshot drift | Low | Snapshot at build start (FEAT-FORGE-006) + TASK-MAG7-014 |
| R-9 | Notification publish failure regresses approval | Low | Existing `PipelineLifecycleEmitter` + TASK-MAG7-013 |
| R-10 | Worktree confinement bypass | High (inherited) | FEAT-FORGE-005 permissions + TASK-MAG7-014 |

---

## §8: Quality Gates Checklist

Before marking the feature complete:

- [ ] All 14 tasks pass their unit/integration tests
- [ ] Smoke test (TASK-MAG7-012) drives a one-line brief to PR-awaiting-review
- [ ] All seven crash-recovery stage variants pass (TASK-MAG7-013)
- [ ] Two-concurrent-builds isolation test passes (TASK-MAG7-014)
- [ ] Multi-feature 3-feature catalogue produces 3 PR-review pauses
- [ ] Constitutional misconfigured-prompt test passes (canary for ADR-ARCH-026)
- [ ] Specialist override-claim ignored at gating (TASK-MAG7-014)
- [ ] Worktree confinement test passes (TASK-MAG7-014)
- [ ] All 47 BDD scenarios from
      `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature`
      have `@task:` tags applied (Step 11 BDD linking)
- [ ] All modified files pass project-configured lint/format checks

---

## §9: Substrate Reference (do NOT re-implement)

Every primitive below is owned by an upstream feature and must be consumed
through its existing Protocol / contract surface, not re-implemented in
FEAT-FORGE-007:

| Primitive | Owner | Surface |
|-----------|-------|---------|
| Build state machine, SQLite history, crash recovery | FEAT-FORGE-001 | `forge.adapters.sqlite` |
| Pipeline event publish, build queue subscribe | FEAT-FORGE-002 | `forge.adapters.nats.PipelinePublisher` (already implemented in `src/forge/pipeline.py`) |
| Discovery cache, capability resolution | FEAT-FORGE-002/003 | `forge.discovery` |
| Specialist dispatch, retry-with-context | FEAT-FORGE-003 | `forge.adapters.nats.AgentDispatch` (per API-nats-agent-dispatch.md) |
| Confidence-gated checkpoint protocol, build-keyed approval channel | FEAT-FORGE-004 | `forge.gating` (per API-nats-approval-protocol.md) |
| GuardKit subprocess engine + git/gh adapter | FEAT-FORGE-005 | `forge.adapters.subprocess` (per API-subprocess.md) |
| Worktree allowlist, DeepAgents permissions | FEAT-FORGE-005 | constitutional subprocess permissions |
| Long-term memory seeding, priors retrieval, calibration snapshot | FEAT-FORGE-006 | `forge.memory` |
| `autobuild_runner` AsyncSubAgent body | FEAT-FORGE-005 + ADR-ARCH-031 | `forge.subagents.autobuild_runner` |
| `start_async_task` / `update_async_task` / `cancel_async_task` middleware | DeepAgents | `AsyncSubAgentMiddleware` (per DDR-006) |

If FEAT-FORGE-007 ever needs to *extend* one of these primitives, that is an
upstream change request — file it as a separate spec, do not absorb it into
FEAT-FORGE-007's scope.

---

## §10: Next Steps

1. Review this guide and the per-task acceptance criteria
2. Optionally run pre-flight validation: `guardkit feature validate FEAT-FORGE-007`
3. Begin implementation with Wave 1 in parallel:
   - `/task-work TASK-MAG7-001`
   - `/task-work TASK-MAG7-002`
4. Or run autonomously: `/feature-build FEAT-FORGE-007`
5. After Wave 4 lands, run BDD scenario binding via Step 11 of `/feature-plan`
   (already attempted as part of this command — re-run with
   `--bdd-link-threshold=0.6` if needed)
Write README.md
105 lines
# FEAT-FORGE-007 — Mode A Greenfield End-to-End

The capstone composition feature for Forge. Drives a single one-line product
brief through the eight-stage Mode A chain — product-owner → architect →
/system-arch → /system-design → /feature-spec → /feature-plan → autobuild →
pull-request review — under one supervised build.

## Status

- **Source review**: [TASK-REV-MAG7](../TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md)
- **Approach**: Option 1 — Reasoning-loop-driven dispatch with deterministic StageOrderingGuard
- **Tasks**: 14 across 5 waves
- **Estimated effort**: 12–16 hours
- **BDD scenarios**: 47 (in [`features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature`](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature))

## Key Documents

- 📋 [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) — Full plan with Mermaid diagrams, integration contracts, risk register
- 📝 [Review report](../../../.claude/reviews/TASK-REV-MAG7-review-report.md) — Decision rationale and option analysis
- 📐 [Feature spec summary](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md)
- 🥒 [Gherkin feature file](../../../features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature)

## Subtask Catalogue

### Wave 1 — Foundations (parallel, ~1h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-001](./TASK-MAG7-001-define-stage-taxonomy.md) | Define StageClass enum and prerequisite map | 2 |
| [TASK-MAG7-002](./TASK-MAG7-002-define-forward-propagation-map.md) | Define forward-propagation contract map | 2 |

### Wave 2 — Core Guards (parallel, ~3.5h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-003](./TASK-MAG7-003-stage-ordering-guard.md) | Implement StageOrderingGuard | 5 |
| [TASK-MAG7-004](./TASK-MAG7-004-constitutional-guard.md) | Implement ConstitutionalGuard for PR-review | 4 |
| [TASK-MAG7-005](./TASK-MAG7-005-per-feature-loop-sequencer.md) | Implement PerFeatureLoopSequencer | 4 |

### Wave 3 — Stage Dispatchers + Context Builder (parallel, ~6h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-006](./TASK-MAG7-006-forward-context-builder.md) | Implement ForwardContextBuilder | 5 |
| [TASK-MAG7-007](./TASK-MAG7-007-dispatch-specialist-stage.md) | Wire dispatch_specialist_stage | 4 |
| [TASK-MAG7-008](./TASK-MAG7-008-dispatch-subprocess-stage.md) | Wire dispatch_subprocess_stage | 5 |
| [TASK-MAG7-009](./TASK-MAG7-009-dispatch-autobuild-async.md) | Wire dispatch_autobuild_async | 6 |

### Wave 4 — Supervisor + CLI Steering (sequential, ~4h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-010](./TASK-MAG7-010-supervisor-next-turn.md) | Wire Supervisor.next_turn dispatch loop | 7 |
| [TASK-MAG7-011](./TASK-MAG7-011-cli-steering-injection.md) | Wire CLI steering (cancel/skip/directive) | 5 |

### Wave 5 — Integration Tests (parallel, ~6h)

| Task | Title | Complexity |
|------|-------|-----------:|
| [TASK-MAG7-012](./TASK-MAG7-012-smoke-greenfield-e2e.md) | Smoke greenfield E2E to PR-awaiting-review | 5 |
| [TASK-MAG7-013](./TASK-MAG7-013-crash-recovery-integration.md) | Crash-recovery integration tests | 6 |
| [TASK-MAG7-014](./TASK-MAG7-014-concurrency-multifeature-integration.md) | Concurrency + multi-feature integration | 7 |

## Upstream Substrate (do NOT re-implement)

This feature is **purely composition**. Every primitive below is owned by an
upstream feature and must be consumed through its existing surface:

- **FEAT-FORGE-001** — Build state machine, SQLite history, crash recovery
- **FEAT-FORGE-002** — NATS fleet, pipeline events, build queue (already implemented in [src/forge/pipeline.py](../../../src/forge/pipeline.py))
- **FEAT-FORGE-003** — Specialist agent dispatch
- **FEAT-FORGE-004** — Confidence-gated checkpoint protocol
- **FEAT-FORGE-005** — GuardKit subprocess engine, git/gh adapter, worktree confinement
- **FEAT-FORGE-006** — Long-term memory, priors retrieval, calibration snapshot

See [§9 of the implementation guide](./IMPLEMENTATION-GUIDE.md#9-substrate-reference-do-not-re-implement) for the full surface map.

## Constitutional Invariants (must hold)

1. **Stage-ordering invariant** — no stage dispatched before its prerequisite is approved (Group B Scenario Outline)
2. **Belt-and-braces PR-review** — pull-request review is mandatory human approval at *both* prompt and executor layers (ADR-ARCH-026; Group E security tests)
3. **Per-feature autobuild sequencing** — no second feature's autobuild begins while a prior feature's autobuild is non-terminal (ASSUM-006)
4. **Durable history authoritative** — on crash recovery, SQLite is authoritative; the `async_tasks` state channel is advisory (DDR-006; Group D edge-case)
5. **First-wins idempotency** — duplicate or simultaneous approval responses resolve as exactly one decision (Group D + Group I)
6. **Correlation threading** — every published lifecycle event for a build carries the same correlation_id queue→terminal (Group I @data-integrity)
7. **Calibration priors snapshot stability** — snapshot captured at build start; mid-run mutations apply only to subsequent builds (Group I @data-integrity)

## Quick Start

```bash
# Validate the feature plan before starting
guardkit feature validate FEAT-FORGE-007

# Begin Wave 1 implementation in parallel
/task-work TASK-MAG7-001
/task-work TASK-MAG7-002

# Or run autonomous build
/feature-build FEAT-FORGE-007
```

## Quality Gates

See [§8 of the implementation guide](./IMPLEMENTATION-GUIDE.md#8-quality-gates-checklist) — feature is complete only when all 14 tasks land, all integration tests pass, and all 47 BDD scenarios are tagged via Step 11 BDD linking.
Now Step 10 — generate the structured YAML feature file via the CLI script.

Bash Generate FEAT-MAG7 YAML feature file
IN
python3 ~/.agentecflow/bin/generate-feature-yaml \
    --name "Mode A Greenfield End-to-End" \
    --description "Capstone composition feature: drives a one-line product brief through eight Mode A stages (product-owner, architect, system-arch, system-design, feature-spec, feature-plan, autobuild, pull-request review) under one supervised build with stage-ordering invariants, forward propagation, async-subagent autobuild dispatch, constitutional belt-and-braces PR review, crash-recovery via durable history, CLI steering, pause isolation, and idempotent first-wins approval handling." \
    --feature-slug "mode-a-greenfield-end-to-end" \
    --discover \
    --task "TASK-MAG7-001:Define StageClass enum and prerequisite map:2:" \
    --task "TASK-MAG7-002:Define forward-propagation contract map:2:" \
    --task "TASK-MAG7-003:Implement StageOrderingGuard:5:TASK-MAG7-001" \
    --task "TASK-MAG7-004:Implement ConstitutionalGuard for PR-review:4:TASK-MAG7-001" \
    --task "TASK-MAG7-005:Implement PerFeatureLoopSequencer:4:TASK-MAG7-001" \
    --task "TASK-MAG7-006:Implement ForwardContextBuilder:5:TASK-MAG7-001,TASK-MAG7-002,TASK-MAG7-003" \
    --task "TASK-MAG7-007:Wire dispatch_specialist_stage:4:TASK-MAG7-001,TASK-MAG7-006" \
    --task "TASK-MAG7-008:Wire dispatch_subprocess_stage:5:TASK-MAG7-001,TASK-MAG7-006" \
    --task "TASK-MAG7-009:Wire dispatch_autobuild_async:6:TASK-MAG7-001,TASK-MAG7-006" \
    --task "TASK-MAG7-010:Wire Supervisor.next_turn dispatch loop:7:TASK-MAG7-003,TASK-MAG7-004,TASK-MAG7-005,TASK-MAG7-007,TASK-MAG7-008,TASK-MAG7-009" \
    --task "TASK-MAG7-011:Wire CLI steering injection:5:TASK-MAG7-004,TASK-MAG7-009,TASK-MAG7-010" \
    --task "TASK-MAG7-012:Smoke greenfield E2E to PR-awaiting-review:5:TASK-MAG7-010,TASK-MAG7-011" \
    --task "TASK-MAG7-013:Crash-recovery integration tests:6:TASK-MAG7-010,TASK-MAG7-011" \
    --task "TASK-MAG7-014:Concurrency and multi-feature integration tests:7:TASK-MAG7-010,TASK-MAG7-011" \
    --base-path "."

OUT
   [discover] TASK-MAG7-001: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-001-define-stageclass-enum-and-prerequisite-map.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-001-define-stage-taxonomy.md
   [discover] TASK-MAG7-002: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-002-define-forward-propagation-contract-map.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-002-define-forward-propagation-map.md
   [discover] TASK-MAG7-003: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-003-implement-stageorderingguard.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-003-stage-ordering-guard.md
   [discover] TASK-MAG7-004: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-004-implement-constitutionalguard-for-pr-review.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-004-constitutional-guard.md
   [discover] TASK-MAG7-005: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-005-implement-perfeatureloopsequencer.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-005-per-feature-loop-sequencer.md
   [discover] TASK-MAG7-006: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-006-implement-forwardcontextbuilder.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-006-forward-context-builder.md
   [discover] TASK-MAG7-007: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-007-wire-dispatch-specialist-stage.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-007-dispatch-specialist-stage.md
   [discover] TASK-MAG7-008: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-008-wire-dispatch-subprocess-stage.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-008-dispatch-subprocess-stage.md
   [discover] TASK-MAG7-009: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-009-wire-dispatch-autobuild-async.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-009-dispatch-autobuild-async.md
   [discover] TASK-MAG7-010: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-010-wire-supervisor-next-turn-dispatch-loop.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-010-supervisor-next-turn.md
   [discover] TASK-MAG7-011: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-011-wire-cli-steering-injection.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-011-cli-steering-injection.md
   [discover] TASK-MAG7-012: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-012-smoke-greenfield-e2e-to-pr-awaiting-review.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-012-smoke-greenfield-e2e.md
   [discover] TASK-MAG7-013: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-013-crash-recovery-integration-tests.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-013-crash-recovery-integration.md
   [discover] TASK-MAG7-014: derived path differs from disk, using disk path
     derived: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-014-concurrency-and-multi-feature-integration-tests.md
     actual:  tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-014-concurrency-multifeature-integration.md
✅ Feature FEAT-CBDE created
📋 Tasks: 14
   TASK-MAG7-001: Define StageClass enum and prerequisite map (complexity: 2)
   TASK-MAG7-002: Define forward-propagation contract map (complexity: 2)
   TASK-MAG7-003: Implement StageOrderingGuard (complexity: 5) (deps: TASK-MAG7-001)
   TASK-MAG7-004: Implement ConstitutionalGuard for PR-review (complexity: 4) (deps: TASK-MAG7-001)
   TASK-MAG7-005: Implement PerFeatureLoopSequencer (complexity: 4) (deps: TASK-MAG7-001)
   TASK-MAG7-006: Implement ForwardContextBuilder (complexity: 5) (deps: TASK-MAG7-001, TASK-MAG7-002, TASK-MAG7-003)
   TASK-MAG7-007: Wire dispatch_specialist_stage (complexity: 4) (deps: TASK-MAG7-001, TASK-MAG7-006)
   TASK-MAG7-008: Wire dispatch_subprocess_stage (complexity: 5) (deps: TASK-MAG7-001, TASK-MAG7-006)
   TASK-MAG7-009: Wire dispatch_autobuild_async (complexity: 6) (deps: TASK-MAG7-001, TASK-MAG7-006)
   TASK-MAG7-010: Wire Supervisor.next_turn dispatch loop (complexity: 7) (deps: TASK-MAG7-003, TASK-MAG7-004, TASK-MAG7-005, TASK-MAG7-007, TASK-MAG7-008, TASK-MAG7-009)
   TASK-MAG7-011: Wire CLI steering injection (complexity: 5) (deps: TASK-MAG7-004, TASK-MAG7-009, TASK-MAG7-010)
   TASK-MAG7-012: Smoke greenfield E2E to PR-awaiting-review (complexity: 5) (deps: TASK-MAG7-010, TASK-MAG7-011)
   TASK-MAG7-013: Crash-recovery integration tests (complexity: 6) (deps: TASK-MAG7-010, TASK-MAG7-011)
   TASK-MAG7-014: Concurrency and multi-feature integration tests (complexity: 7) (deps: TASK-MAG7-010, TASK-MAG7-011)

🔀 Parallel execution groups: 7 waves
   Wave 1: [TASK-MAG7-001, TASK-MAG7-002]
   Wave 2: [TASK-MAG7-003, TASK-MAG7-004, TASK-MAG7-005]
   Wave 3: [TASK-MAG7-006]
   Wave 4: [TASK-MAG7-007, TASK-MAG7-008, TASK-MAG7-009]
   Wave 5: [TASK-MAG7-010]
   Wave 6: [TASK-MAG7-011]
   Wave 7: [TASK-MAG7-012, TASK-MAG7-013, TASK-MAG7-014]

📁 Feature file: .guardkit/features/FEAT-CBDE.yaml
⚡ AutoBuild ready: /feature-build FEAT-CBDE

AC-quality review: 0 unverifiable acceptance criteria detected.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Feature-level smoke gates (R3) not configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This feature has 7 waves but no smoke_gates: key in the generated YAML.
Between-wave smoke checks will not fire during autobuild.

This is the gate that catches composition failures (e.g., the PEX-014..020
"13/13 green + e2e broken" pattern) that per-task Coach approval misses.

To activate: add a smoke_gates: block to the feature YAML before running
/feature-build. Minimal example:
    smoke_gates:
      after_wave_1:
        - python -c "import your_package"
      after_wave_2:
        - pytest tests/smoke -x

See installer/core/commands/feature-plan.md § "Smoke gates".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Feature YAML generated as FEAT-CBDE. Zero unverifiable ACs. Now Step 11 — BDD scenario linking.

Bash Prepare BDD linking request
IN
REQ_FILE=$(mktemp -t bdd-link-req-XXXXXX.json) && \
RESP_FILE=$(mktemp -t bdd-link-resp-XXXXXX.json) && \
echo "REQ_FILE=$REQ_FILE" && echo "RESP_FILE=$RESP_FILE" && \
python3 ~/.agentecflow/bin/feature-plan-bdd-link prepare \
    --project-root . \
    --feature-slug "mode-a-greenfield-end-to-end" \
    --feature-yaml ".guardkit/features/FEAT-CBDE.yaml" \
    --output "$REQ_FILE"

OUT
REQ_FILE=/tmp/bdd-link-req-VWdg2s.json
RESP_FILE=/tmp/bdd-link-resp-jgYCTZ.json
{"status": "ready", "feature_path": "/home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature", "scenarios_to_match": 47, "task_count": 14, "confidence_threshold": 0.6, "already_tagged_count": 0, "request_path": "/tmp/bdd-link-req-VWdg2s.json"}
Read bdd-link-req-VWdg2s.json
Bash Check request size
IN
wc -l /tmp/bdd-link-req-VWdg2s.json && jq '.tasks | length, .scenarios | length' /tmp/bdd-link-req-VWdg2s.json 2>/dev/null

OUT
Exit code 5
1008 /tmp/bdd-link-req-VWdg2s.json
14
Bash Verify counts
IN
jq '.tasks | length' /tmp/bdd-link-req-VWdg2s.json && jq '.scenarios | length' /tmp/bdd-link-req-VWdg2s.json

OUT
14
47
Request is ready: 47 scenarios × 14 tasks. Invoking the bdd-linker subagent.

Read bdd-link-req-VWdg2s.json
Now invoking the bdd-linker subagent with the full request payload.

Agent:Match scenarios to tasks for FEAT-FORGE-007
IN
Match the BDD scenarios below to the implementation tasks. Return a JSON array of TaskMatch objects per the agent's output contract.

Confidence threshold: 0.6 (only return matches at or above this threshold)

The request payload is in /tmp/bdd-link-req-VWdg2s.json — please read it and analyse.

For each scenario you can map to a task (or multiple tasks for cross-cutting scenarios — pick the primary one), produce a TaskMatch with:
- scenario_index: 0-based index from the request
- task_id: matching task ID (e.g. "TASK-MAG7-003")
- confidence: 0.0–1.0 score
- reasoning: brief one-line rationale

Notes on the matching:
- Scenarios about "stage-ordering invariants", "prerequisite", "no dispatch before approved" → TASK-MAG7-003 (StageOrderingGuard)
- Scenarios about PR-review constitutional rule, mandatory human approval, override claims → TASK-MAG7-004 (ConstitutionalGuard)
- Per-feature autobuild sequencing → TASK-MAG7-005 (PerFeatureLoopSequencer)
- Forward propagation, "supplied as input/context", artefact threading → TASK-MAG7-006 (ForwardContextBuilder)
- Specialist dispatch (product-owner, architect, degraded specialist) → TASK-MAG7-007
- Subprocess stages (system-arch, system-design, feature-spec, feature-plan), worktree confinement → TASK-MAG7-008
- Autobuild async dispatch, AsyncSubAgent, task_id, state channel → TASK-MAG7-009
- Supervisor reasoning loop, full pipeline runs, flag-resume cycle → TASK-MAG7-010
- CLI steering (cancel, skip, mid-flight directive) → TASK-MAG7-011
- End-to-end smoke, single-feature, paused at PR-review → TASK-MAG7-012
- Crash recovery, retry-from-scratch, durable history authoritative → TASK-MAG7-013
- Concurrency, multi-feature, correlation threading, calibration snapshot, first-wins idempotency, security → TASK-MAG7-014

Return ONLY the JSON array — no prose, no markdown fence, just the bare array. The downstream parser handles `[...]` and `{"matches": [...]}` shapes.

If a scenario cannot confidently map to any task at >= 0.6, omit it (it will fall through as untagged).
Read bdd-link-req-VWdg2s.json
All 47 scenarios matched at ≥0.78 confidence. Writing the response and applying.

Write bdd-link-resp-jgYCTZ.json
Write failed
[{"scenario_index":0,"task_id":"TASK-MAG7-012","confidence":0.91,"reasoning":"Full pipeline smoke run from brief to PR-awaiting-review with auto-approval at every gate matches the E2E smoke test task directly."},{"scenario_index":1,"task_id":"TASK-MAG7-006","confidence":0.88,"reasoning":"Product-owner charter supplied as input to architect dispatch and ordering guard matches ForwardContextBuilder artefact threading and prerequisite sequencing."},{"scenario_index":2,"task_id":"TASK-MAG7-006","confidence":0.87,"reasoning":"Architecture artefact paths supplied as context to system-design invocation with ordering guard maps to ForwardContextBuilder propagation contract for SYSTEM_DESIGN."},{"scenario_index":3,"task_id":"TASK-MAG7-005","confidence":0.88,"reasoning":"Per-feature loop iterating spec, plan, and autobuild dispatches per catalogue entry maps directly to PerFeatureLoopSequencer sequencing logic."},{"scenario_index":4,"task_id":"TASK-MAG7-009","confidence":0.92,"reasoning":"Autobuild as long-running async task with own task identifier, live status reporting, and supervisor remaining responsive directly describes dispatch_autobuild_async AsyncSubAgent dispatch."},{"scenario_index":5,"task_id":"TASK-MAG7-010","confidence":0.85,"reasoning":"Flagged-for-review pause, resume on approval, prior context still available, and no later stage started before response matches Supervisor.next_turn flag-resume cycle."},{"scenario_index":6,"task_id":"TASK-MAG7-004","confidence":0.93,"reasoning":"PR-review stage mandatory human approval that cannot be auto-approved regardless of upstream scores is the core ConstitutionalGuard veto_auto_approve behaviour."},{"scenario_index":7,"task_id":"TASK-MAG7-010","confidence":0.82,"reasoning":"Build completing to terminal state with full ordered gate-decision chain in session outcome covers the Supervisor full pipeline run and stage_log recording."},{"scenario_index":8,"task_id":"TASK-MAG7-012","confidence":0.87,"reasoning":"Single-feature catalogue smoke: one spec, one plan, one autobuild, one PR-review pause maps to the smoke greenfield E2E single-feature test."},{"scenario_index":9,"task_id":"TASK-MAG7-014","confidence":0.84,"reasoning":"Multi-feature catalogue producing N dispatches per stage maps to the multi-feature integration test in the concurrency/multi-feature test task."},{"scenario_index":10,"task_id":"TASK-MAG7-005","confidence":0.80,"reasoning":"Zero-feature catalogue preventing per-feature loop entry and flagging for review with missing-catalogue rationale is a boundary case owned by PerFeatureLoopSequencer."},{"scenario_index":11,"task_id":"TASK-MAG7-003","confidence":0.93,"reasoning":"Downstream stage not dispatched before prerequisite reaches approved state is the direct subject of StageOrderingGuard.is_dispatchable and the Scenario Outline in its ACs."},{"scenario_index":12,"task_id":"TASK-MAG7-009","confidence":0.83,"reasoning":"Single-wave autobuild lifecycle progress reporting and completed state maps to dispatch_autobuild_async live status and AutobuildState lifecycle tracking."},{"scenario_index":13,"task_id":"TASK-MAG7-014","confidence":0.78,"reasoning":"Supervisor answering concurrent status queries while autobuild is running maps to the concurrency integration test asserting supervisor responsiveness during mid-flight autobuild."},{"scenario_index":14,"task_id":"TASK-MAG7-010","confidence":0.82,"reasoning":"Hard-stop at product-owner causing failed terminal state with no later dispatches is a Supervisor.next_turn reasoning loop outcome covered by its hard-stop unit tests."},{"scenario_index":15,"task_id":"TASK-MAG7-007","confidence":0.88,"reasoning":"Degraded specialist availability causing build pause with degraded rationale and no later dispatch maps to dispatch_specialist_stage degraded-specialist handling."},{"scenario_index":16,"task_id":"TASK-MAG7-008","confidence":0.88,"reasoning":"Failed /feature-spec dispatch halting the inner loop with no plan or autobuild issued and rationale recorded maps to dispatch_subprocess_stage /feature-spec failure AC."},{"scenario_index":17,"task_id":"TASK-MAG7-004","confidence":0.92,"reasoning":"Auto-approval refused at PR-review even at maximum Coach score is the veto_auto_approve path of ConstitutionalGuard."},{"scenario_index":18,"task_id":"TASK-MAG7-004","confidence":0.91,"reasoning":"Skip directive refused at PR-review with constitutional rationale recorded is the veto_skip path of ConstitutionalGuard."},{"scenario_index":19,"task_id":"TASK-MAG7-009","confidence":0.83,"reasoning":"Autobuild internal hard-stop propagating to failed terminal state and preventing PR creation maps to dispatch_autobuild_async hard-stop handling and AutobuildState lifecycle."},{"scenario_index":20,"task_id":"TASK-MAG7-010","confidence":0.78,"reasoning":"PR creation stage failure resulting in failed terminal state with no PR URL recorded is a Supervisor.next_turn turn outcome for the PR creation dispatcher failure path."},{"scenario_index":21,"task_id":"TASK-MAG7-010","confidence":0.80,"reasoning":"Reject decision at a flagged-for-review checkpoint terminating the build with no later dispatches is a Supervisor.next_turn gate-decision outcome."},{"scenario_index":22,"task_id":"TASK-MAG7-013","confidence":0.93,"reasoning":"Crash during non-terminal stage recovered by retry-from-scratch with build re-entering preparing state is the parameterised crash-recovery test in the crash-recovery task."},{"scenario_index":23,"task_id":"TASK-MAG7-013","confidence":0.92,"reasoning":"Mid-autobuild crash with authoritative status from durable history not live state channel maps directly to the mid-autobuild crash test AC in crash-recovery tests."},{"scenario_index":24,"task_id":"TASK-MAG7-011","confidence":0.88,"reasoning":"Steering directive injected into running autobuild appearing as pending without halting the wave maps to CliSteeringHandler.handle_directive AC."},{"scenario_index":25,"task_id":"TASK-MAG7-011","confidence":0.90,"reasoning":"Cancel directive while paused resolving as synthetic reject with cancel rationale and cancelled terminal state maps to CliSteeringHandler.handle_cancel pause path."},{"scenario_index":26,"task_id":"TASK-MAG7-011","confidence":0.89,"reasoning":"Cancel directive during running autobuild halting async task and reaching cancelled terminal state maps to CliSteeringHandler.handle_cancel autobuild path."},{"scenario_index":27,"task_id":"TASK-MAG7-011","confidence":0.90,"reasoning":"Skip directive on non-constitutional stage recording as skipped and resuming chain maps to CliSteeringHandler.handle_skip non-constitutional path."},{"scenario_index":28,"task_id":"TASK-MAG7-014","confidence":0.85,"reasoning":"Approval response routed only to the matching build identifier with other paused build unaffected maps to the concurrent-builds approval-channel isolation test."},{"scenario_index":29,"task_id":"TASK-MAG7-014","confidence":0.82,"reasoning":"Internal autobuild pause observable via supervisor without blocking other supervisor work maps to concurrency integration test asserting supervisor responsiveness."},{"scenario_index":30,"task_id":"TASK-MAG7-005","confidence":0.91,"reasoning":"Per-feature inner loops sequenced so each autobuild completes before next begins is the core may_start_autobuild sequencing invariant of PerFeatureLoopSequencer."},{"scenario_index":31,"task_id":"TASK-MAG7-014","confidence":0.85,"reasoning":"Duplicate approval response ignored with no additional stage transition maps to the first-wins idempotency test in the concurrency integration tests."},{"scenario_index":32,"task_id":"TASK-MAG7-004","confidence":0.92,"reasoning":"Misconfigured prompt that would allow auto-approve still refused by executor layer maps to ConstitutionalGuard enforcement independent of prompt config (constitutional misconfigured-prompt AC)."},{"scenario_index":33,"task_id":"TASK-MAG7-004","confidence":0.91,"reasoning":"Specialist result claiming to override PR-review rule being ignored at gating maps to ConstitutionalGuard.veto_override_claim and the specialist-override-claim AC."},{"scenario_index":34,"task_id":"TASK-MAG7-008","confidence":0.88,"reasoning":"Subprocess stages confined to build worktree allowlist with no writes outside maps to dispatch_subprocess_stage worktree-confinement AC."},{"scenario_index":35,"task_id":"TASK-MAG7-014","confidence":0.90,"reasoning":"Two concurrent builds with distinct autobuild task identifiers and separate approval channels resolving independently maps to the two-concurrent-builds test ACs."},{"scenario_index":36,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Supervisor dispatching second build's product-owner stage while first build's autobuild is mid-flight maps to the concurrent-builds supervisor-responsiveness AC."},{"scenario_index":37,"task_id":"TASK-MAG7-003","confidence":0.82,"reasoning":"Recorded stage history following canonical Mode A ordering maps to StageOrderingGuard's prerequisite map enforcing the correct sequence."},{"scenario_index":38,"task_id":"TASK-MAG7-014","confidence":0.80,"reasoning":"Per-feature artefact paths attributed only to their own feature with no cross-attribution maps to the multi-feature integration test per-feature artefact attribution AC."},{"scenario_index":39,"task_id":"TASK-MAG7-013","confidence":0.84,"reasoning":"Notification publish failure not regressing stage approval or next prerequisite maps to the notification-publish-failure test in crash-recovery integration tests."},{"scenario_index":40,"task_id":"TASK-MAG7-012","confidence":0.92,"reasoning":"Minimal one-line brief single-feature run to PR-awaiting-review with PR URL recorded is the primary smoke test AC in the smoke greenfield E2E task."},{"scenario_index":41,"task_id":"TASK-MAG7-012","confidence":0.88,"reasoning":"No available specialists flagged-for-review at product-owner with degraded rationale maps to the degraded test in the smoke greenfield E2E task."},{"scenario_index":42,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Multi-feature run producing one spec, plan, autobuild, and PR-review pause per feature maps to the multi-feature integration test in the concurrency/multi-feature task."},{"scenario_index":43,"task_id":"TASK-MAG7-014","confidence":0.88,"reasoning":"Two simultaneous approval responses resolving as first-wins with no double-resume maps to the first-wins idempotency test AC in concurrency integration tests."},{"scenario_index":44,"task_id":"TASK-MAG7-014","confidence":0.87,"reasoning":"Every lifecycle event carrying the same correlation identifier from queue to terminal maps to the correlation-threading test AC in concurrency integration tests."},{"scenario_index":45,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Calibration priors snapshot captured at start remaining unchanged by mid-run history mutations maps to the calibration-priors snapshot test AC."},{"scenario_index":46,"task_id":"TASK-MAG7-013","confidence":0.85,"reasoning":"LTM seeding failure not regressing stage approval or next prerequisite maps to the long-term-memory-seeding-failure test in crash-recovery integration tests."}]
Read bdd-link-resp-jgYCTZ.json
Bash Write matcher response and verify count
IN
cat > /tmp/bdd-link-resp-jgYCTZ.json << 'JSONEOF'
[{"scenario_index":0,"task_id":"TASK-MAG7-012","confidence":0.91,"reasoning":"Full pipeline smoke run from brief to PR-awaiting-review with auto-approval at every gate matches the E2E smoke test task directly."},{"scenario_index":1,"task_id":"TASK-MAG7-006","confidence":0.88,"reasoning":"Product-owner charter supplied as input to architect dispatch and ordering guard matches ForwardContextBuilder artefact threading and prerequisite sequencing."},{"scenario_index":2,"task_id":"TASK-MAG7-006","confidence":0.87,"reasoning":"Architecture artefact paths supplied as context to system-design invocation with ordering guard maps to ForwardContextBuilder propagation contract for SYSTEM_DESIGN."},{"scenario_index":3,"task_id":"TASK-MAG7-005","confidence":0.88,"reasoning":"Per-feature loop iterating spec, plan, and autobuild dispatches per catalogue entry maps directly to PerFeatureLoopSequencer sequencing logic."},{"scenario_index":4,"task_id":"TASK-MAG7-009","confidence":0.92,"reasoning":"Autobuild as long-running async task with own task identifier, live status reporting, and supervisor remaining responsive directly describes dispatch_autobuild_async AsyncSubAgent dispatch."},{"scenario_index":5,"task_id":"TASK-MAG7-010","confidence":0.85,"reasoning":"Flagged-for-review pause, resume on approval, prior context still available, and no later stage started before response matches Supervisor.next_turn flag-resume cycle."},{"scenario_index":6,"task_id":"TASK-MAG7-004","confidence":0.93,"reasoning":"PR-review stage mandatory human approval that cannot be auto-approved regardless of upstream scores is the core ConstitutionalGuard veto_auto_approve behaviour."},{"scenario_index":7,"task_id":"TASK-MAG7-010","confidence":0.82,"reasoning":"Build completing to terminal state with full ordered gate-decision chain in session outcome covers the Supervisor full pipeline run and stage_log recording."},{"scenario_index":8,"task_id":"TASK-MAG7-012","confidence":0.87,"reasoning":"Single-feature catalogue smoke: one spec, one plan, one autobuild, one PR-review pause maps to the smoke greenfield E2E single-feature test."},{"scenario_index":9,"task_id":"TASK-MAG7-014","confidence":0.84,"reasoning":"Multi-feature catalogue producing N dispatches per stage maps to the multi-feature integration test in the concurrency/multi-feature test task."},{"scenario_index":10,"task_id":"TASK-MAG7-005","confidence":0.80,"reasoning":"Zero-feature catalogue preventing per-feature loop entry and flagging for review with missing-catalogue rationale is a boundary case owned by PerFeatureLoopSequencer."},{"scenario_index":11,"task_id":"TASK-MAG7-003","confidence":0.93,"reasoning":"Downstream stage not dispatched before prerequisite reaches approved state is the direct subject of StageOrderingGuard.is_dispatchable and the Scenario Outline in its ACs."},{"scenario_index":12,"task_id":"TASK-MAG7-009","confidence":0.83,"reasoning":"Single-wave autobuild lifecycle progress reporting and completed state maps to dispatch_autobuild_async live status and AutobuildState lifecycle tracking."},{"scenario_index":13,"task_id":"TASK-MAG7-014","confidence":0.78,"reasoning":"Supervisor answering concurrent status queries while autobuild is running maps to the concurrency integration test asserting supervisor responsiveness during mid-flight autobuild."},{"scenario_index":14,"task_id":"TASK-MAG7-010","confidence":0.82,"reasoning":"Hard-stop at product-owner causing failed terminal state with no later dispatches is a Supervisor.next_turn reasoning loop outcome covered by its hard-stop unit tests."},{"scenario_index":15,"task_id":"TASK-MAG7-007","confidence":0.88,"reasoning":"Degraded specialist availability causing build pause with degraded rationale and no later dispatch maps to dispatch_specialist_stage degraded-specialist handling."},{"scenario_index":16,"task_id":"TASK-MAG7-008","confidence":0.88,"reasoning":"Failed /feature-spec dispatch halting the inner loop with no plan or autobuild issued and rationale recorded maps to dispatch_subprocess_stage /feature-spec failure AC."},{"scenario_index":17,"task_id":"TASK-MAG7-004","confidence":0.92,"reasoning":"Auto-approval refused at PR-review even at maximum Coach score is the veto_auto_approve path of ConstitutionalGuard."},{"scenario_index":18,"task_id":"TASK-MAG7-004","confidence":0.91,"reasoning":"Skip directive refused at PR-review with constitutional rationale recorded is the veto_skip path of ConstitutionalGuard."},{"scenario_index":19,"task_id":"TASK-MAG7-009","confidence":0.83,"reasoning":"Autobuild internal hard-stop propagating to failed terminal state and preventing PR creation maps to dispatch_autobuild_async hard-stop handling and AutobuildState lifecycle."},{"scenario_index":20,"task_id":"TASK-MAG7-010","confidence":0.78,"reasoning":"PR creation stage failure resulting in failed terminal state with no PR URL recorded is a Supervisor.next_turn turn outcome for the PR creation dispatcher failure path."},{"scenario_index":21,"task_id":"TASK-MAG7-010","confidence":0.80,"reasoning":"Reject decision at a flagged-for-review checkpoint terminating the build with no later dispatches is a Supervisor.next_turn gate-decision outcome."},{"scenario_index":22,"task_id":"TASK-MAG7-013","confidence":0.93,"reasoning":"Crash during non-terminal stage recovered by retry-from-scratch with build re-entering preparing state is the parameterised crash-recovery test in the crash-recovery task."},{"scenario_index":23,"task_id":"TASK-MAG7-013","confidence":0.92,"reasoning":"Mid-autobuild crash with authoritative status from durable history not live state channel maps directly to the mid-autobuild crash test AC in crash-recovery tests."},{"scenario_index":24,"task_id":"TASK-MAG7-011","confidence":0.88,"reasoning":"Steering directive injected into running autobuild appearing as pending without halting the wave maps to CliSteeringHandler.handle_directive AC."},{"scenario_index":25,"task_id":"TASK-MAG7-011","confidence":0.90,"reasoning":"Cancel directive while paused resolving as synthetic reject with cancel rationale and cancelled terminal state maps to CliSteeringHandler.handle_cancel pause path."},{"scenario_index":26,"task_id":"TASK-MAG7-011","confidence":0.89,"reasoning":"Cancel directive during running autobuild halting async task and reaching cancelled terminal state maps to CliSteeringHandler.handle_cancel autobuild path."},{"scenario_index":27,"task_id":"TASK-MAG7-011","confidence":0.90,"reasoning":"Skip directive on non-constitutional stage recording as skipped and resuming chain maps to CliSteeringHandler.handle_skip non-constitutional path."},{"scenario_index":28,"task_id":"TASK-MAG7-014","confidence":0.85,"reasoning":"Approval response routed only to the matching build identifier with other paused build unaffected maps to the concurrent-builds approval-channel isolation test."},{"scenario_index":29,"task_id":"TASK-MAG7-014","confidence":0.82,"reasoning":"Internal autobuild pause observable via supervisor without blocking other supervisor work maps to concurrency integration test asserting supervisor responsiveness."},{"scenario_index":30,"task_id":"TASK-MAG7-005","confidence":0.91,"reasoning":"Per-feature inner loops sequenced so each autobuild completes before next begins is the core may_start_autobuild sequencing invariant of PerFeatureLoopSequencer."},{"scenario_index":31,"task_id":"TASK-MAG7-014","confidence":0.85,"reasoning":"Duplicate approval response ignored with no additional stage transition maps to the first-wins idempotency test in the concurrency integration tests."},{"scenario_index":32,"task_id":"TASK-MAG7-004","confidence":0.92,"reasoning":"Misconfigured prompt that would allow auto-approve still refused by executor layer maps to ConstitutionalGuard enforcement independent of prompt config."},{"scenario_index":33,"task_id":"TASK-MAG7-004","confidence":0.91,"reasoning":"Specialist result claiming to override PR-review rule being ignored at gating maps to ConstitutionalGuard.veto_override_claim AC."},{"scenario_index":34,"task_id":"TASK-MAG7-008","confidence":0.88,"reasoning":"Subprocess stages confined to build worktree allowlist with no writes outside maps to dispatch_subprocess_stage worktree-confinement AC."},{"scenario_index":35,"task_id":"TASK-MAG7-014","confidence":0.90,"reasoning":"Two concurrent builds with distinct autobuild task identifiers and separate approval channels resolving independently maps to the two-concurrent-builds test ACs."},{"scenario_index":36,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Supervisor dispatching second build's product-owner stage while first build's autobuild is mid-flight maps to the concurrent-builds supervisor-responsiveness AC."},{"scenario_index":37,"task_id":"TASK-MAG7-003","confidence":0.82,"reasoning":"Recorded stage history following canonical Mode A ordering maps to StageOrderingGuard's prerequisite map enforcing the correct sequence."},{"scenario_index":38,"task_id":"TASK-MAG7-014","confidence":0.80,"reasoning":"Per-feature artefact paths attributed only to their own feature with no cross-attribution maps to the multi-feature integration test per-feature artefact attribution AC."},{"scenario_index":39,"task_id":"TASK-MAG7-013","confidence":0.84,"reasoning":"Notification publish failure not regressing stage approval or next prerequisite maps to the notification-publish-failure test in crash-recovery integration tests."},{"scenario_index":40,"task_id":"TASK-MAG7-012","confidence":0.92,"reasoning":"Minimal one-line brief single-feature run to PR-awaiting-review with PR URL recorded is the primary smoke test AC in the smoke greenfield E2E task."},{"scenario_index":41,"task_id":"TASK-MAG7-012","confidence":0.88,"reasoning":"No available specialists flagged-for-review at product-owner with degraded rationale maps to the degraded test in the smoke greenfield E2E task."},{"scenario_index":42,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Multi-feature run producing one spec, plan, autobuild, and PR-review pause per feature maps to the multi-feature integration test in the concurrency/multi-feature task."},{"scenario_index":43,"task_id":"TASK-MAG7-014","confidence":0.88,"reasoning":"Two simultaneous approval responses resolving as first-wins with no double-resume maps to the first-wins idempotency test AC in concurrency integration tests."},{"scenario_index":44,"task_id":"TASK-MAG7-014","confidence":0.87,"reasoning":"Every lifecycle event carrying the same correlation identifier from queue to terminal maps to the correlation-threading test AC in concurrency integration tests."},{"scenario_index":45,"task_id":"TASK-MAG7-014","confidence":0.86,"reasoning":"Calibration priors snapshot captured at start remaining unchanged by mid-run history mutations maps to the calibration-priors snapshot test AC."},{"scenario_index":46,"task_id":"TASK-MAG7-013","confidence":0.85,"reasoning":"LTM seeding failure not regressing stage approval or next prerequisite maps to the long-term-memory-seeding-failure test in crash-recovery integration tests."}]
JSONEOF
jq 'length' /tmp/bdd-link-resp-jgYCTZ.json

OUT
47
All 47 matches written. Now applying the matches.

Bash Apply BDD scenario tags to feature file
IN
python3 ~/.agentecflow/bin/feature-plan-bdd-link apply \
    --project-root . \
    --feature-slug "mode-a-greenfield-end-to-end" \
    --task-matches-file /tmp/bdd-link-resp-jgYCTZ.json
echo "EXIT=$?"

OUT
[Step 11] linked 47 scenario(s) to task(s); 0 already tagged; 0 below threshold (0.60) (of 47 total)
EXIT=0
All 47 scenarios tagged. Now Step 8.5 — pre-flight feature validation.

Bash Validate feature YAML and clean up temp files
IN
guardkit feature validate FEAT-CBDE 2>&1 | head -50; echo "EXIT=$?"; rm -f /tmp/bdd-link-req-VWdg2s.json /tmp/bdd-link-resp-jgYCTZ.json

OUT
[0;31mUnknown command: feature[0m
Run 'guardkit help' for usage information
EXIT=0
Bash Verify @task tags applied and inspect YAML
IN
grep -c "^  @task:" /home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature && head -35 /home/richardwoollcott/Projects/appmilla_github/forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature && echo "---" && head -25 /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/features/FEAT-CBDE.yaml

OUT
47
# Generated by /feature-spec
# Feature: Mode A Greenfield End-to-End (FEAT-FORGE-007)
# Stack: python
# Assumptions: 8 (see mode-a-greenfield-end-to-end_assumptions.yaml)
# Generated: 2026-04-25T00:00:00Z

@feat-forge-007 @mode-a-greenfield
Feature: Mode A Greenfield End-to-End
  As Rich, the operator triggering a greenfield build
  I want Forge to drive a raw product idea through delegation, architecture,
    per-feature specification, planning, autobuild, and pull-request creation
    in a single supervised run
  So that I can land a reviewed pull request from a one-line brief without
    hand-stitching the intermediate stages

  Background:
    Given Forge is registered on the fleet
    And the live discovery cache lists a healthy product-owner specialist and a healthy architect specialist
    And the operator's calibration history has been ingested
    And a project repository is configured with a writable worktree allowlist
    And a build has been queued for a feature identifier in greenfield mode

  # ===========================================================================
  # GROUP A — Key Examples
  # ===========================================================================

  # Why: The capstone happy path — one greenfield brief produces one reviewed pull request
  # [ASSUMPTION: confidence=high] Eight stage classes drive Mode A: product-owner → architect → /system-arch → /system-design → /feature-spec → /feature-plan → autobuild → pull-request review
  @task:TASK-MAG7-012
  @key-example @smoke
  Scenario: A greenfield brief drives a full pipeline run to a pull request awaiting review
    Given the build is picked up from the queue
    When Forge delegates to the product-owner specialist and the result is auto-approved
    And Forge delegates to the architect specialist and the result is auto-approved
    And Forge invokes architecture, design, per-feature specification, per-feature planning, and autobuild in order
---
id: FEAT-CBDE
name: Mode A Greenfield End-to-End
description: 'Capstone composition feature: drives a one-line product brief through
  eight Mode A stages (product-owner, architect, system-arch, system-design, feature-spec,
  feature-plan, autobuild, pull-request review) under one supervised build with stage-ordering
  invariants, forward propagation, async-subagent autobuild dispatch, constitutional
  belt-and-braces PR review, crash-recovery via durable history, CLI steering, pause
  isolation, and idempotent first-wins approval handling.'
created: '2026-04-25T16:02:32.486906'
status: planned
complexity: 7
estimated_tasks: 14
tasks:
- id: TASK-MAG7-001
  name: Define StageClass enum and prerequisite map
  file_path: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-001-define-stage-taxonomy.md
  complexity: 2
  dependencies: []
  status: pending
  description: ''
  implementation_mode: direct
  estimated_minutes: 22
- id: TASK-MAG7-002
  name: Define forward-propagation contract map
  file_path: tasks/backlog/mode-a-greenfield-end-to-end/TASK-MAG7-002-define-forward-propagation-map.md
All 47 scenarios tagged. Feature plan complete.

✅ Feature Plan Complete — FEAT-FORGE-007 Mode A Greenfield End-to-End
Created
Artefact	Location
📋 Review report	.claude/reviews/TASK-REV-MAG7-review-report.md
📝 Review task	tasks/backlog/TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md
📁 Feature folder	tasks/backlog/mode-a-greenfield-end-to-end/
🗺️ Implementation guide	tasks/backlog/mode-a-greenfield-end-to-end/IMPLEMENTATION-GUIDE.md
📖 README	tasks/backlog/mode-a-greenfield-end-to-end/README.md
📄 14 task files	TASK-MAG7-001 through TASK-MAG7-014
⚡ Structured YAML	.guardkit/features/FEAT-CBDE.yaml
🥒 BDD-tagged feature	features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature (47/47 scenarios tagged)
Wave Plan (auto-detected from dependencies — 7 fine-grained waves)

Wave 1 (parallel): TASK-MAG7-001, TASK-MAG7-002              ── declarative foundations
Wave 2 (parallel): TASK-MAG7-003, TASK-MAG7-004, TASK-MAG7-005 ── core guards
Wave 3:            TASK-MAG7-006                              ── ForwardContextBuilder
Wave 4 (parallel): TASK-MAG7-007, TASK-MAG7-008, TASK-MAG7-009 ── 3 dispatchers
Wave 5:            TASK-MAG7-010                              ── Supervisor.next_turn
Wave 6:            TASK-MAG7-011                              ── CLI steering
Wave 7 (parallel): TASK-MAG7-012, TASK-MAG7-013, TASK-MAG7-014 ── integration tests
BDD Linking Result

[Step 11] linked 47 scenario(s) to task(s);
          0 already tagged;
          0 below threshold (0.60)
          (of 47 total)
R2 BDD oracle is now active — every scenario will run as a Coach-blocking oracle during /task-work phase 4.

Quality Notes
✅ Zero unverifiable acceptance criteria (AC-quality linter passed)
⚠️ R3 smoke gates not configured — smoke_gates: block not added to FEAT-CBDE.yaml. This is the gate that catches composition failures between waves. Recommend adding before running /feature-build (see notice in script output)
Next Steps

# Begin Wave 1 in parallel:
/task-work TASK-MAG7-001
/task-work TASK-MAG7-002

# Or run autonomously:
/feature-build FEAT-CBDE
The original review task TASK-REV-MAG7 remains in backlog/ — move to completed/ when the feature lands, or use /task-complete TASK-REV-MAG7 to close it now.

Want me to /schedule an agent in 2 weeks to add a smoke_gates: block to the feature YAML and open a review PR before /feature-build runs?