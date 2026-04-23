/system-design \
  --context forge/docs/architecture/ARCHITECTURE.md \
  --context <ADR files produced by Step 1> \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md


I'll execute /system-design starting with the prerequisite gate and context loading.

Read graphiti.yaml
Globpattern: "docs/architecture/**/*.md"
Found 35 files
Bash List sibling repos to locate nats-core
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/ 2>/dev/null | head -40

OUT
total 63048
drwxr-xr-x  160 richardwoollcott  staff      5120 Apr 21 10:22 .
drwxr-xr-x   28 richardwoollcott  staff       896 Mar 26 11:19 ..
-rw-r--r--@   1 richardwoollcott  staff    141316 Apr 23 17:56 .DS_Store
drwxr-xr-x   13 richardwoollcott  staff       416 Aug 19  2025 agent-os
drwxr-xr-x   60 richardwoollcott  staff      1920 Oct  9  2025 agentecflow_platform
drwxr-xr-x   48 richardwoollcott  staff      1536 Apr 17 12:19 agentic-dataset-factory
drwxr-xr-x   54 richardwoollcott  staff      1728 Dec  4 12:13 ai-engineer
drwxr-xr-x@  15 richardwoollcott  staff       480 Jan 11  2024 amity-client-test
drwxr-xr-x@  16 richardwoollcott  staff       512 Jan 11  2024 amity-kotlin-openapi-generator
drwxr-xr-x@  13 richardwoollcott  staff       416 Jul 21  2023 AndroidForAI
drwxr-xr-x    7 richardwoollcott  staff       224 Nov 17  2023 andy
drwxr-xr-x@  32 richardwoollcott  staff      1024 May 21  2023 appmilla-test-explore
drwxr-xr-x   31 richardwoollcott  staff       992 Apr 10 11:51 architect-agent_delete_me
drwxr-xr-x   17 richardwoollcott  staff       544 Apr 15 21:24 architecture_books
drwxr-xr-x   10 richardwoollcott  staff       320 Feb 23  2025 AspNetCoreWebApiFundamentals
drwxr-xr-x   12 richardwoollcott  staff       384 Sep  5  2025 BarcodeScanning.Native.Maui
drwxr-xr-x   12 richardwoollcott  staff       384 Apr 26  2023 basic_keycloak
drwxr-xr-x    5 richardwoollcott  staff       160 May 16  2025 CertifyDatabase
drwxr-xr-x   12 richardwoollcott  staff       384 Mar 31  2025 CertifyMobileApplications
drwx------@  16 richardwoollcott  staff       512 Sep 24  2023 Circuit-Compose-App
drwxr-xr-x   12 richardwoollcott  staff       384 Jul 21  2025 cite-saul-ollama-setup
drwxr-xr-x@  28 richardwoollcott  staff       896 Sep 19  2023 ClearAccept.Android
drwxrwxrwx   10 richardwoollcott  staff       320 Sep  6  2023 ClearAccept.TerminalApi.Protobuff
drwxr-xr-x   19 richardwoollcott  staff       608 Jul  3  2024 CMPNavigationDemo
drwxr-xr-x@  19 richardwoollcott  staff       608 Jan  8  2024 ComposablePresenterCounter
drwxr-xr-x@  17 richardwoollcott  staff       544 Dec 30  2023 ComposablePresenterCounter_template_expanded
drwxr-xr-x@  23 richardwoollcott  staff       736 Jul 26  2023 ComposeMultiplatformDemo
drwxr-xr-x@  15 richardwoollcott  staff       480 Jul 22  2023 composeWebApp
drwxr-xr-x@   2 richardwoollcott  staff        64 Jun 27  2023 cryptopofthepops
drwxr-xr-x   34 richardwoollcott  staff      1088 Jun 27  2024 CSharp_Markup_PeopleInSpace_MAUI
drwxr-xr-x@  24 richardwoollcott  staff       768 Oct 17  2023 decompose_starter_template
drwxr-xr-x   53 richardwoollcott  staff      1696 Apr 21 13:41 DeCUK.Mobile.MyDrive
drwxr-xr-x   17 richardwoollcott  staff       544 Mar 30 14:14 deepagents
drwxr-xr-x   30 richardwoollcott  staff       960 Mar 30 21:00 deepagents-orchestrator-exemplar
drwxr-xr-x   28 richardwoollcott  staff       896 Apr 17 12:19 deepagents-player-coach-exemplar
drwxr-xr-x@  25 richardwoollcott  staff       800 Mar 16 10:34 deepagents-player-coach-exemplar-original
drwxr-xr-x   51 richardwoollcott  staff      1632 Dec  4 12:13 dev-tasker
drwxr-xr-x@  47 richardwoollcott  staff      1504 Oct 27 19:02 devtasker-temp
drwxr-xr-x   21 richardwoollcott  staff       672 Nov 21 19:35 DLR.Certify.API.Legacy
Globpattern: "/Users/richardwoollcott/Projects/appmilla_github/nats-core/**/*.md"
Found 101 files
Architecture context present. Loading the specified context files in parallel.

Read ARCHITECTURE.md
Read container.md
Read domain-model.md
Read system-context.md
Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify bounded contexts / containers to design

Confirm scope + protocols with Rich (interactive)

Design API contracts per context (NATS subjects, tool schemas, CLI surfaces, payloads)

Design data models per context

Run contradiction detection against existing ADRs

Generate output artefacts (contracts, models, DDRs, C4 L3 diagrams)

C4 L3 review gate with Rich

Validate OpenAPI spec if applicable + offer Graphiti seeding
Now loading the remaining context files in parallel.

Read nats-core-system-spec.md
Read agent-manifest-contract.md
Read forge-pipeline-orchestrator-refresh.md
Bash Check for existing design directory
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/ 2>/dev/null

OUT
Exit code 1
Bash Inspect docs tree
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/forge/docs/ 2>/dev/null

OUT
total 0
drwxr-xr-x   9 richardwoollcott  staff  288 Apr 19 12:20 .
drwxr-xr-x  25 richardwoollcott  staff  800 Apr 20 06:44 ..
drwxr-xr-x@  3 richardwoollcott  staff   96 Apr 18 12:45 adr
drwxr-xr-x   8 richardwoollcott  staff  256 Apr 19 13:24 architecture
drwxr-xr-x   5 richardwoollcott  staff  160 Apr 23 18:07 history
drwxr-xr-x@  4 richardwoollcott  staff  128 Apr 15 09:27 product
drwxr-xr-x  11 richardwoollcott  staff  352 Apr 16 11:13 research
drwxr-xr-x   3 richardwoollcott  staff   96 Apr 19 12:20 reviews
drwxr-xr-x@  3 richardwoollcott  staff   96 Apr 18 12:45 state
Bash List adr + research dirs
IN
ls /Users/richardwoollcott/Projects/appmilla_github/forge/docs/adr/ /Users/richardwoollcott/Projects/appmilla_github/forge/docs/research/ 2>/dev/null

OUT
/Users/richardwoollcott/Projects/appmilla_github/forge/docs/adr/:
0001-adopt-agentic-flow.md

/Users/richardwoollcott/Projects/appmilla_github/forge/docs/research/:
c4-build-order.svg
c4-component-map.svg
c4-system-context.svg
forge-build-plan-alignment-review.md
forge-pipeline-architecture.md
ideas
pipeline-orchestrator-consolidated-build-plan.md
pipeline-orchestrator-conversation-starter.md
pipeline-orchestrator-motivation.md
Read ADR-ARCH-012-no-mcp-interface.md
Read ADR-ARCH-015-capability-driven-dispatch.md
Read ADR-ARCH-021-paused-via-langgraph-interrupt.md
Read ADR-ARCH-013-cli-read-bypasses-nats.md
Read ADR-ARCH-014-single-consumer-max-ack-pending.md
Read ADR-ARCH-031-async-subagents-for-long-running-work.md
Context loaded. Before generating ~10+ artefacts, let me surface scope + protocol decisions to confirm with you.

Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Design API contracts per unit (NATS subjects, tool schemas, CLI surfaces, payloads)

Design data models per unit

Run contradiction detection against existing ADRs

Generate output artefacts (contracts, models, DDRs, C4 L3 diagrams)

C4 L3 review gate with Rich

Offer Graphiti seeding commands

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏗️ ARCHITECTURE LOADED — design scope proposal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Architecture is NOT DDD (ARCHITECTURE.md §2 + domain-model.md §"Structural Pattern"):
  "not DDD (no bounded contexts, no aggregates, no domain events).
   It's a single-responsibility orchestrator with clean module boundaries."

So /system-design's "bounded context" abstraction doesn't cleanly apply. Proposing to
design per **container** (C4 L2 — 8 containers) plus cross-cutting groups:
#	Design unit	Container(s)	Modules
1	Agent Runtime	agent	forge.agent, forge.prompts, forge.subagents (sync + async)
2	Domain Core	discovery (logical group)	forge.gating, forge.state_machine, forge.notifications, forge.learning, forge.calibration, forge.discovery, forge.history_labels
3	Tool Layer	agent (inside)	dispatch_by_capability, approval/notification/graphiti/guardkit/history tools + AsyncSubAgent supervisor tools
4	NATS Adapter	nats_adapter	forge.adapters.nats, forge.fleet
5	SQLite Adapter	sqlite	forge.adapters.sqlite + schema
6	Graphiti Adapter	graphiti_adapter	forge.adapters.graphiti, forge.adapters.history_parser
7	Subprocess Adapter	subprocess_adapter	forge.adapters.guardkit + execute wrappers
8	LangGraph Adapter	(new, per ADR-021 Rev 10)	forge.adapters.langgraph — resume_value_as helper
9	Forge CLI	cli	forge.cli (Click)
10	Config + Permissions	config	forge.config + forge.yaml
Protocol surfaces proposed (per ADR-ARCH-003, 012, 013, 014, 015):

Protocol	Status	Rationale
REST / OpenAPI	❌ NOT applicable	ADR-ARCH-012 excludes HTTP/REST. No OpenAPI artefact.
GraphQL	❌ NOT applicable	Same
MCP	❌ NOT applicable	ADR-ARCH-012 explicitly excludes MCP
A2A / ACP	❌ NOT applicable	Fleet uses NATS request/reply, not A2A protocol
NATS (JetStream + Core + KV)	✅ Primary transport	ADR-ARCH-003, 014
Click CLI	✅ Rich's interface	ADR-ARCH-013
SQLite schema	✅ Internal contract	ADR-SP-013
DeepAgents @tool functions	✅ Agent-internal	ADR-ARCH-004, 020
Graphiti entity contracts	✅ Data contract	ADR-ARCH-005
subprocess / filesystem	✅ Outbound	ADR-ARCH-011
Proposed output artefact set (deviates from template to match reality):


docs/design/
├── contracts/
│   ├── API-nats-pipeline-events.md     (inbound BuildQueued + outbound pipeline.*)
│   ├── API-nats-agent-dispatch.md      (agents.command.*/result.* with LES1 correlation)
│   ├── API-nats-approval-protocol.md   (agents.approval.forge.{build_id} + .response)
│   ├── API-nats-fleet-lifecycle.md     (fleet.register/heartbeat/deregister + KV watch)
│   ├── API-cli.md                      (forge queue/status/history/cancel/skip)
│   ├── API-sqlite-schema.md            (builds + stage_log — read/write contract)
│   ├── API-tool-layer.md               (all @tool functions — schemas via docstrings)
│   ├── API-subagents.md                (build_plan_composer sync + autobuild_runner async)
│   └── API-subprocess.md               (GuardKit + git + gh via execute)
├── models/
│   ├── DM-build-lifecycle.md           (Build, StageLogEntry, BuildStatus transitions)
│   ├── DM-gating.md                    (GateDecision, GateMode, evidence)
│   ├── DM-calibration.md               (CalibrationEvent, CalibrationAdjustment)
│   ├── DM-discovery.md                 (CapabilityResolution + AgentManifest reference)
│   └── DM-graphiti-entities.md         (Graphiti entity schemas per group)
├── diagrams/
│   ├── agent-runtime.md                (C4 L3 — Agent Runtime container, ~7 components)
│   └── domain-core.md                  (C4 L3 — Domain Core, ~7 components)
└── decisions/
    ├── DDR-001-reply-subject-correlation.md
    ├── DDR-002-resume-value-rehydration-helper.md
    ├── DDR-003-sqlite-schema-layout-wal.md
    ├── DDR-004-graphiti-group-partitioning.md
    ├── DDR-005-cli-context-manifest-resolution.md
    └── DDR-006-async-subagent-state-channel-contract.md
NOT generated:

openapi.yaml — no REST surface
mcp-tools.json — no MCP (ADR-ARCH-012)
a2a-schemas.yaml — no A2A protocol
Questions before I proceed:

Scope: Accept this 10-unit breakdown? Or focus on a subset (e.g. NATS contracts + CLI + SQLite only — defer Tool Layer + DDRs to follow-up)?
OpenAPI gate: Confirm skipping OpenAPI/MCP/A2A artefacts (per ADRs). If you want a "virtual" OpenAPI for documentation purposes anyway, say so.
C4 L3 coverage: Agent Runtime + Domain Core have >3 components each → L3 diagrams warranted. NATS Adapter is borderline (2–3 concerns). Generate L3 for NATS Adapter too?
DDR set: The 6 DDRs above are my candidates. Accept as-is, or call out others you want recorded (e.g. topic template resolution strategy, degraded-mode precedence)?
Reply with [A]ccept proposal to proceed with all 10 units and 6 DDRs, or list adjustments. This is a large generation pass — I want to confirm shape before writing.

system-design-history.md
A
Proceeding with the full generation pass. Starting with directory structure + all 9 API contracts.

Bash Create design subdirectories
IN
mkdir -p /Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/{contracts,models,diagrams,decisions}

OUT
(Bash completed with no output)
Write API-nats-pipeline-events.md
192 lines
# API Contract — NATS Pipeline Events

> **Type:** Inbound trigger + outbound lifecycle events
> **Transport:** NATS JetStream (`PIPELINE` stream, 7-day retention)
> **Stream:** `PIPELINE` (configured in `nats-infrastructure`)
> **Consumer type:** Durable pull consumer (single) + ephemeral publishers
> **Related ADRs:** [ADR-ARCH-003](../../architecture/decisions/ADR-ARCH-003-nats-native-no-transport-abc.md), [ADR-ARCH-014](../../architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md), [ADR-SP-011](../../research/forge-pipeline-architecture.md), [ADR-SP-013](../../research/forge-pipeline-architecture.md), [ADR-SP-014](../../research/forge-pipeline-architecture.md), [ADR-SP-017](../../research/forge-pipeline-architecture.md)

---

## 1. Purpose

This contract defines Forge's inbound build-queue subscription and outbound lifecycle event stream. Every published event uses `nats-core.MessageEnvelope` as the wire format; payloads are typed Pydantic models already shipped in `nats-core.events.pipeline`.

Forge is both:

- **A consumer** of one subject pattern: `pipeline.build-queued.>` (max_ack_pending=1 pull consumer).
- **A publisher** of eight lifecycle subjects that collectively describe a build's journey from queued → terminal.

---

## 2. Inbound — Build Trigger (Consumed)

### 2.1 Subject

| Template | Resolution example |
|---|---|
| `pipeline.build-queued.{feature_id}` | `pipeline.build-queued.FEAT-A1B2` |
| Project-scoped | `Topics.for_project("finproxy", ...)` → `finproxy.pipeline.build-queued.FEAT-A1B2` |

### 2.2 Consumer configuration

```python
# forge.adapters.nats.pipeline_consumer
await js.pull_subscribe(
    subject="pipeline.build-queued.>",
    durable="forge-consumer",                  # Survives Forge restart
    stream="PIPELINE",
    config=ConsumerConfig(
        max_ack_pending=1,                     # ADR-ARCH-014 — sequential builds enforced at transport
        ack_wait=timedelta(hours=1),           # Covers the longest expected build
        deliver_policy=DeliverPolicy.ALL,      # On first start — replay anything queued pre-boot
        ack_policy=AckPolicy.EXPLICIT,
        max_deliver=-1,                        # Redelivery is infinite until we terminal-ack
        filter_subject="pipeline.build-queued.>",
    ),
)
```

**Acknowledgement rule.** Forge acks the JetStream message **only on a terminal state transition** (`COMPLETE | FAILED | CANCELLED | SKIPPED`). `PAUSED` leaves the message unacked so it holds the queue position; crash + restart triggers redelivery (ADR-SP-013 crash recovery).

### 2.3 Payload — `BuildQueuedPayload`

Defined in `nats-core.events.pipeline`. Forge imports; does not redeclare.

```python
class BuildQueuedPayload(BaseModel):
    feature_id: str
    repo: str
    branch: str
    feature_yaml_path: str
    triggered_by: Literal["cli", "jarvis", "forge-internal", "notification-adapter"]
    originating_adapter: Literal[
        "terminal", "voice-reachy", "telegram", "slack", "dashboard", "cli-wrapper"
    ] | None = None
    originating_user: str | None = None
    correlation_id: str                        # UUID — threaded through all downstream events
    parent_request_id: str | None = None       # Jarvis dispatch ID for progress routing
    max_turns: int = 5
    sdk_timeout: int = 1800
    queued_at: datetime
```

**Validation on consume.**

1. `model_validate(envelope.payload)` — reject if `ValidationError` (log + ack + publish `pipeline.build-failed.{feature_id}` with `failure_reason="malformed BuildQueuedPayload"`).
2. Duplicate detection — check SQLite `builds(feature_id, correlation_id)` unique index; if present, ack and skip (idempotent).
3. Permission check — `feature_yaml_path` must satisfy `forge.config.permissions.filesystem.allowlist`; otherwise publish `pipeline.build-failed` with `failure_reason="path outside allowlist"`.

---

## 3. Outbound — Lifecycle Events (Published)

All outbound events carry the same `correlation_id` from the triggering `BuildQueuedPayload` so downstream subscribers (Jarvis, dashboards, notification adapters) can thread progress.

### 3.1 Subject family

| Stage | Subject template | Payload type | Published when |
|---|---|---|---|
| Build started | `pipeline.build-started.{feature_id}` | `BuildStartedPayload` | `PREPARING → RUNNING` transition |
| Build progress | `pipeline.build-progress.{feature_id}` | `BuildProgressPayload` | At least every 60s during RUNNING; also on wave boundaries from `autobuild_runner` |
| Stage complete | `pipeline.stage-complete.{feature_id}` | `StageCompletePayload` | After each gate-evaluated dispatch commits its `StageLogEntry` to SQLite |
| Build paused | `pipeline.build-paused.{feature_id}` | `BuildPausedPayload` | When `forge.gating` emits `FLAG_FOR_REVIEW` and `interrupt()` is about to fire |
| Build resumed | `pipeline.build-resumed.{feature_id}` | `BuildResumedPayload` | After `ApprovalResponsePayload` rehydrates and graph resumes |
| Build complete | `pipeline.build-complete.{feature_id}` | `BuildCompletePayload` | `FINALISING → COMPLETE` (PR created) |
| Build failed | `pipeline.build-failed.{feature_id}` | `BuildFailedPayload` | `RUNNING/FINALISING → FAILED` (any terminal failure) |
| Build cancelled | `pipeline.build-cancelled.{feature_id}` | `BuildCancelledPayload` | On `forge cancel` CLI command reaching the running build |

**Retention:** 7-day file storage on `PIPELINE` stream; retention policy is `LimitsPolicy` (oldest-first drop), configured by `nats-infrastructure`.

### 3.2 Payloads

`BuildStartedPayload`, `BuildProgressPayload`, `BuildCompletePayload`, `BuildFailedPayload` already exist in `nats-core`. Forge contributes **three new payload types** to `nats-core` — see DDR-001 for the dependency decision:

```python
class StageCompletePayload(BaseModel):
    """Emitted after each gate-evaluated dispatch."""
    feature_id: str
    build_id: str
    stage_label: str                       # Reasoning-model-chosen, emergent (ADR-ARCH-016)
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str                 # Tool name / agent_id:tool_name / subagent name
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: Literal["AUTO_APPROVE", "FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"] | None
    coach_score: float | None              # May be None in degraded mode
    duration_secs: float
    completed_at: datetime
    correlation_id: str

class BuildPausedPayload(BaseModel):
    """Emitted when the reasoning model flags a stage for review."""
    feature_id: str
    build_id: str
    stage_label: str
    gate_mode: Literal["FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"]
    coach_score: float | None
    rationale: str                         # Why the gate fired (reasoning-model output)
    approval_subject: str                  # Reply-subject where ApprovalResponsePayload is expected
    paused_at: datetime
    correlation_id: str

class BuildResumedPayload(BaseModel):
    """Emitted after ApprovalResponsePayload rehydrates and the graph resumes."""
    feature_id: str
    build_id: str
    stage_label: str
    decision: Literal["approve", "reject", "defer", "override"]
    responder: str
    resumed_at: datetime
    correlation_id: str

class BuildCancelledPayload(BaseModel):
    """Emitted when the running build sees a cancel command."""
    feature_id: str
    build_id: str
    reason: str                            # e.g. "user_requested", "timeout"
    cancelled_by: str                      # Actor: "rich" / jarvis adapter / "system"
    cancelled_at: datetime
    correlation_id: str
```

**Coordination.** These three payload additions are tracked under `TASK-NCFA-002` in `nats-core` (sibling task to the `FeaturePlannedPayload`/`FeatureReadyForBuildPayload` retirement captured in TASK-NCFA-001). Until the additions ship in `nats-core ≥ 0.2.0`, Forge carries them locally in `forge.adapters.nats._interim_payloads.py` with a TODO pointing to the sibling task.

### 3.3 Publish semantics

- **Fire-and-forget** — publish uses `nc.publish(subject, envelope.model_dump_json().encode())`. PubAck is treated as a transport-level receipt, not proof of delivery (LES1 parity rule: PubAck ≠ success).
- **No JetStream ack semantics** — these are not request/reply; subscribers (Jarvis, dashboards) are at-least-once via `PIPELINE` stream replay.
- **`source_id: "forge"`** on every envelope.

---

## 4. Crash-Recovery Contract

On Forge restart, `forge.adapters.nats.pipeline_consumer.reconcile_on_boot()` runs:

1. Pull consumer re-subscribes with `durable="forge-consumer"`. JetStream redelivers any unacked `build-queued` messages.
2. For each redelivered message, `forge.adapters.sqlite.reconcile(feature_id, correlation_id)` checks SQLite:
   - `COMPLETE | FAILED | CANCELLED | SKIPPED` → ack immediately (idempotent — previous run finished before ack).
   - `RUNNING | FINALISING` → mark `INTERRUPTED`, restart from `PREPARING` per anchor §5 retry-from-scratch policy.
   - `PAUSED` → re-enter PAUSED state, re-emit `BuildPausedPayload` + `ApprovalRequestPayload` (idempotent on `correlation_id`; first response wins — ADR-ARCH-021).
   - Unknown build_id → fresh build.

---

## 5. Observability

| Signal | Source | Consumer |
|---|---|---|
| Queue depth | `jsz` / JetStream monitor endpoint | `forge status` (via `forge.cli`) |
| Consumer lag | NATS monitoring | Ops alerting (out of Forge scope) |
| Progress stream | `pipeline.build-progress.{feature_id}` | Jarvis → originating adapter → Rich |
| Terminal state | `pipeline.build-{complete,failed,cancelled}.{feature_id}` | Jarvis, notification adapters, Graphiti `forge_pipeline_history` writer |

---

## 6. Related

- Data model: [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Approval contract: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- DDR: [DDR-001-reply-subject-correlation.md](../decisions/DDR-001-reply-subject-correlation.md)
Write API-nats-agent-dispatch.md
191 lines
# API Contract — NATS Agent Dispatch (Request/Reply)

> **Type:** Outbound request/reply to fleet specialist agents
> **Transport:** NATS core request/reply (not JetStream — replies are ephemeral, correlation-keyed)
> **Stream:** `AGENTS` (for observability/audit; actual reply routing uses core NATS inbox pattern)
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md), [ADR-SP-017](../../research/forge-pipeline-architecture.md)
> **Parity rule:** LES1 §2 — PubAck ≠ success; the real reply arrives separately on the reply subject.

---

## 1. Purpose

Forge delegates domain judgment to fleet specialist agents (Product Owner, Architect, QA, UX, Ideation — present and future) via capability-driven dispatch. This contract specifies:

- **How Forge selects** an agent for a capability (via `forge.discovery` → `NATSKVManifestRegistry`).
- **How Forge publishes** the command (`agents.command.{agent_id}`).
- **How the reply is correlated** (LES1 parity rule: reply on `agents.result.{agent_id}.{correlation_id}`, not on the publish ack).
- **How timeouts and degraded mode** are handled.

This contract governs the single generic `@tool` `dispatch_by_capability` — there are **no per-role dispatch tools** (ADR-ARCH-015).

---

## 2. Resolution

`forge.discovery.resolve(tool_name, intent_pattern=None, min_confidence=0.7)` returns the target `agent_id` using:

1. **Exact tool match** — any agent whose `AgentManifest.tools` contains a `ToolCapability.name == tool_name`.
2. **Intent-pattern match** — if no tool match and `intent_pattern` is provided, any agent whose `AgentManifest.intents` contains a matching `IntentCapability.pattern` with `confidence ≥ min_confidence`.
3. **Tie-break** — highest `trust_tier` (`core > specialist > extension`), then highest `confidence`, then lowest `AgentHeartbeatPayload.queue_depth`.
4. **Unresolved** — returns `None`; caller falls back to degraded mode (see §6).

Registry access is cached for 30 seconds; cache invalidated live by `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>` subscription (ADR-ARCH-017, see [API-nats-fleet-lifecycle.md](API-nats-fleet-lifecycle.md)).

---

## 3. Request Publish

### 3.1 Subject

| Template | Resolution example |
|---|---|
| `agents.command.{agent_id}` | `agents.command.product-owner-agent` |
| Project-scoped | `Topics.for_project("finproxy", "agents.command.architect-agent")` → `finproxy.agents.command.architect-agent` |

### 3.2 Request envelope

Reuses `nats-core.MessageEnvelope` with `event_type=EventType.COMMAND` and payload = `CommandPayload` (already in `nats-core`):

```python
class CommandPayload(BaseModel):
    request_id: str                        # UUID; matches reply subject suffix
    tool_name: str                         # e.g. "review_specification"
    params: dict[str, Any]                 # JSON-Schema-validated per ToolCapability.parameters
    async_mode: bool = False               # Matches ToolCapability.async_mode
    timeout_seconds: int = 600             # Forge-side timeout; not authoritative for the agent
```

**Envelope fields Forge sets:**

- `source_id = "forge"`
- `correlation_id` = the `request_id` (so the full call chain can be reconstructed from envelope threading)
- `project` = build's repo scope (from `BuildQueuedPayload`) or `None` for fleet-wide commands

### 3.3 Reply-subject contract (LES1 parity)

**Forge publishes with an explicit `reply_subject` set via NATS request/reply:**

```python
reply_subject = f"agents.result.{agent_id}.{request_id}"

# The specialist agent's NATS harness is expected to publish its reply to
# `reply_subject` (not to the generic agents.result.{agent_id} topic).
# Forge subscribes to the exact correlation-keyed subject before publishing.
sub = await nc.subscribe(reply_subject, max_msgs=1)
await nc.publish(
    subject=f"agents.command.{agent_id}",
    payload=envelope.model_dump_json().encode(),
    reply=reply_subject,
)

try:
    msg = await sub.next_msg(timeout=command_timeout_seconds)
finally:
    await sub.unsubscribe()
```

**Why per-correlation subjects, not `agents.result.{agent_id}`:**

Per LES1 §2 observation — `nats request` against `agents.>` returned PubAck in ~3ms and exited without waiting; the real reply arrived separately on `agents.result.<role>`. Operators silently read PubAck as success and the round-trip contract was broken for iterations. A correlation-keyed subject:

- Removes ambiguity ("which reply is mine?" when the agent serves concurrent requests).
- Prevents silent swallowing when JetStream AGENTS stream ack-intercepts the generic pattern.
- Makes every dispatch independently auditable.

### 3.4 `PubAck ≠ success` rule

The JetStream AGENTS stream intercepts `agents.>` for audit/observability and returns PubAck within ~3ms. Forge MUST NOT treat the PubAck as the specialist's answer. The dispatch is complete only when:

- A message is received on `reply_subject`, OR
- `command_timeout_seconds` elapses.

---

## 4. Reply

### 4.1 Reply envelope

Reuses `nats-core.MessageEnvelope` with `event_type=EventType.RESULT` and payload = `ResultPayload`:

```python
class ResultPayload(BaseModel):
    request_id: str                        # Echoes CommandPayload.request_id
    status: Literal["success", "error", "degraded", "timeout"]
    result: dict[str, Any]                 # Generic container — see §4.2
    coach_score: float | None = None       # Convention: specialist includes Coach output here
    criterion_breakdown: dict[str, float] | None = None
    detection_findings: list[dict[str, Any]] | None = None
    duration_secs: float
    error_message: str | None = None
```

### 4.2 Coach-score convention

Per the pipeline orchestrator refresh doc §"Forge Tool Inventory" Open Question 6, specialist agents **SHOULD** include Coach output in `result`:

```python
result = {
    "output": { ... },                              # tool-specific payload
    "coach_score": 0.78,
    "criterion_breakdown": {"fidelity": 0.8, ...},
    "detection_findings": [
        {"pattern": "PHANTOM", "severity": "high", "evidence": "..."},
    ],
}
```

Top-level fields on `ResultPayload` mirror these for convenience; either location is acceptable, with top-level preferred for new specialist versions. Forge reads top-level first, falls back to nested.

### 4.3 Gate input

The reasoning model feeds `(coach_score, criterion_breakdown, detection_findings, tool_name, retrieved_priors)` into `forge.gating.evaluate_gate()`. Output is a `GateDecision` (see [DM-gating.md](../models/DM-gating.md)).

---

## 5. Timeouts

| Knob | Source | Default | Notes |
|---|---|---|---|
| `CommandPayload.timeout_seconds` | Caller sets | `600` (10 min) | Advisory to the agent; not enforced remotely |
| Forge-side subscribe timeout | `forge.yaml.dispatch.default_timeout_seconds` | `900` (15 min; 50% headroom) | Hard cut-off; on breach → `status="timeout"` |
| Long-running async dispatch | Per-tool override if `ToolCapability.async_mode=True` | `ToolCapability.metadata.max_seconds` | Agent returns fast with `run_id`; Forge polls via `{tool_name}_status` |

**Timeout outcome.** On hard timeout Forge:

1. Writes `StageLogEntry(status="FAILED", gate_decision=HARD_STOP, details_json={"reason": "dispatch_timeout"})`.
2. Publishes `pipeline.stage-complete` with `status="FAILED"`.
3. Emits a `ResultPayload(status="timeout", …)` back into the reasoning loop so the model can decide next step (retry, degraded-mode fallback, or HARD_STOP the build).

---

## 6. Degraded Mode

If `forge.discovery.resolve(...)` returns `None`:

1. `ResultPayload(status="degraded", error_message="no agent registered for tool=X intent=Y")` is synthesised in-process.
2. The reasoning model sees the degraded result and decides:
   - **Fall back to GuardKit CLI** — e.g. no `architect-agent` → invoke `/system-arch` directly via `guardkit_*` tool.
   - **Skip the stage** — emit `StageCompletePayload(status="SKIPPED")` and continue.
   - **HARD_STOP** — if the capability is essential.
3. When a specialist is unavailable and an equivalent local tool runs, the resulting gate defaults to `FLAG_FOR_REVIEW` (no Coach score → no auto-approve — refresh doc §"Degraded Mode").

---

## 7. Telemetry

| Event | Subject | Purpose |
|---|---|---|
| Dispatch requested | `pipeline.stage-complete.{feature_id}` (emitted after reply) | End-to-end timing visible on `PIPELINE` stream |
| Capability resolution | written to Graphiti `forge_pipeline_history` via `forge.adapters.graphiti.write_capability_resolution()` | Future prior: "when two agents advertised the same capability, prefer the one that passed last time" |
| Dispatch failure / timeout | `pipeline.build-failed.{feature_id}` only if build-terminal; otherwise `StageLogEntry` only | Build continues unless the gate escalates |

---

## 8. Related

- Discovery lifecycle: [API-nats-fleet-lifecycle.md](API-nats-fleet-lifecycle.md)
- Approval round-trip: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- Data model: [DM-discovery.md](../models/DM-discovery.md), [DM-gating.md](../models/DM-gating.md)
- DDR: [DDR-001-reply-subject-correlation.md](../decisions/DDR-001-reply-subject-correlation.md)
Write API-nats-approval-protocol.md
172 lines
# API Contract — NATS Approval Protocol (interrupt round-trip)

> **Type:** Bidirectional — Forge publishes approval requests; Rich's client publishes responses
> **Transport:** NATS core pub/sub on `AGENTS` stream (captured for audit)
> **Related ADRs:** [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md) (Revision 10), [ADR-ARCH-026](../../architecture/decisions/ADR-ARCH-026-constitutional-rules-belt-and-braces.md)

---

## 1. Purpose

When `forge.gating.evaluate_gate()` returns `FLAG_FOR_REVIEW`, `HARD_STOP`, or `MANDATORY_HUMAN_APPROVAL`, the graph halts via LangGraph `interrupt()` and a parallel NATS protocol carries the request to Rich's client (Jarvis → notification adapter → Rich's phone/terminal) and carries the response back.

Under `langgraph dev` / LangGraph server mode (Forge's canonical deployment), the resume value arrives as `dict`, not as a typed Pydantic instance — **every call site MUST rehydrate via `forge.adapters.langgraph.resume_value_as(ApprovalResponsePayload, raw)` before attribute access** (ADR-ARCH-021 Revision 10). See [DDR-002-resume-value-rehydration-helper.md](../decisions/DDR-002-resume-value-rehydration-helper.md).

---

## 2. Subjects

| Direction | Template | Resolution example |
|---|---|---|
| Forge → Rich | `agents.approval.forge.{build_id}` | `agents.approval.forge.build-FEAT-A1B2-20260423170501` |
| Rich → Forge | `agents.approval.forge.{build_id}.response` | `agents.approval.forge.build-FEAT-A1B2-20260423170501.response` |
| Project-scoped | `Topics.for_project("finproxy", "agents.approval.forge.{build_id}")` | `finproxy.agents.approval.forge.…` |

**Why `agents.approval.forge.{build_id}` not `agents.approval.forge.{task_id}`:**

Forge's "task" in the pause sense is always the current build. Keying by `build_id` aligns with SQLite `builds.build_id` (the crash-recovery anchor) and keeps the subject stable across re-emissions if `interrupt()` re-fires after restart.

---

## 3. Approval Request (Forge → Rich)

### 3.1 Envelope + payload

Reuses `nats-core.MessageEnvelope` (`event_type=EventType.APPROVAL_REQUEST`) + `nats-core.ApprovalRequestPayload`:

```python
class ApprovalRequestPayload(BaseModel):
    request_id: str                        # correlation_id threaded back on response
    agent_id: str = "forge"                # Always "forge" for gating pauses
    action_description: str                # One-line summary for Rich: "Architecture review flagged 0.52"
    risk_level: Literal["low", "medium", "high"]
    details: dict[str, Any]                # See §3.2 — Forge convention
    timeout_seconds: int = 300
```

### 3.2 `details` convention

Forge populates `details` with a consistent shape so notification adapters can render it:

```python
details = {
    "build_id": "build-FEAT-A1B2-20260423170501",
    "feature_id": "FEAT-A1B2",
    "stage_label": "Architecture Review",                 # Emergent label
    "gate_mode": "FLAG_FOR_REVIEW",                       # | "HARD_STOP" | "MANDATORY_HUMAN_APPROVAL"
    "coach_score": 0.52,
    "criterion_breakdown": {"fidelity": 0.4, "rigour": 0.6, ...},
    "detection_findings": [
        {"pattern": "SCOPE_CREEP", "severity": "medium", "evidence": "..."},
    ],
    "rationale": "Reasoning model explanation of why this flagged",
    "evidence_priors": [                                  # Which retrieved priors informed the call
        {"entity_id": "...", "summary": "..."},
    ],
    "artefact_paths": [
        "/var/forge/builds/build-FEAT-A1B2-20260423170501/docs/architecture/..."
    ],
    "resume_options": ["approve", "reject", "defer", "override"],
}
```

### 3.3 Risk-level derivation

| Gate mode | `risk_level` |
|---|---|
| `FLAG_FOR_REVIEW` | `"low"` if `coach_score ≥ 0.65`; else `"medium"` |
| `HARD_STOP` | `"high"` |
| `MANDATORY_HUMAN_APPROVAL` | `"medium"` (unconditional human review, not an emergency) |

Published by Forge with `source_id="forge"` and `correlation_id` = the build's correlation_id from `BuildQueuedPayload`.

---

## 4. Approval Response (Rich → Forge)

### 4.1 Envelope + payload

```python
class ApprovalResponsePayload(BaseModel):
    request_id: str                        # Must echo ApprovalRequestPayload.request_id
    decision: Literal["approve", "reject", "defer", "override"]
    responder: str                         # "rich" / jarvis adapter id
    reason: str | None = None
    # Optional Forge-specific extension — passed through without mandatory validation
    override_context: dict[str, Any] | None = None
```

### 4.2 Rehydration contract

Under `langgraph dev` / server mode, the value returned by `interrupt()` is `dict`. The adapter MUST:

```python
from forge.adapters.langgraph import resume_value_as

raw = interrupt({...})                    # See API-tool-layer.md "approval_tools.request_approval"
response = resume_value_as(ApprovalResponsePayload, raw)
# Now safe to access response.decision, response.responder, etc.
```

The `isinstance` short-circuit in `resume_value_as` makes this a no-op in direct-invoke mode (where typed round-trip already holds) — no call-site churn if the deferred Option B serde fix lands later (ADR-ARCH-021 Revision 10).

---

## 5. Consumer Implementation — Response Subscriber

```python
# forge.adapters.nats.approval_subscriber
async def await_approval(build_id: str, timeout_seconds: int = 3600) -> ApprovalResponsePayload:
    subject = f"agents.approval.forge.{build_id}.response"
    sub = await nc.subscribe(subject, max_msgs=1)
    try:
        msg = await sub.next_msg(timeout=timeout_seconds)
        envelope = MessageEnvelope.model_validate_json(msg.data)
        return ApprovalResponsePayload.model_validate(envelope.payload)
    finally:
        await sub.unsubscribe()
```

This subscriber runs inside the NATS approval consumer that the LangGraph runtime uses to feed `interrupt()` resume values. In server mode, the runtime's resume API delivers a `dict` to the `interrupt()` call-site, which then goes through `resume_value_as`.

---

## 6. Idempotency (Crash Recovery)

Per ADR-ARCH-021:

- On Forge crash during PAUSED state, the in-graph `interrupt()` is lost but SQLite marks `PAUSED` and the `ApprovalRequestPayload` was already published.
- On restart, Forge re-enters PAUSED for that build and **re-emits** `ApprovalRequestPayload`. This is deliberate — it guarantees Rich sees the request even if the first one was missed.
- **Responders MUST be idempotent on `request_id`** — first response wins; duplicates are discarded.
- Rich's client / Jarvis adapter enforces this via a short-TTL `processed_request_ids` set in memory.

---

## 7. Timeout Handling

| Scenario | Behaviour |
|---|---|
| `timeout_seconds` elapses (default 300 for initial request; refresh up to `forge.yaml.approval.max_wait_seconds` ≈ 3600) | Forge emits a repeat `ApprovalRequestPayload` with incremented attempt count; continues waiting. |
| Rich runs `forge cancel FEAT-XXX` while paused | NATS `agents.command.forge` receives cancel; resume subscriber injects synthetic `ApprovalResponsePayload(decision="reject", responder="rich", reason="cli cancel")`; graph resumes, state → CANCELLED. |
| Rich runs `forge skip FEAT-XXX` | Synthetic `ApprovalResponsePayload(decision="override", responder="rich", reason="cli skip")`; graph resumes, specific stage skipped. |

---

## 8. Constitutional Rule — PR Review

Per ADR-ARCH-026 belt+braces:

- **Prompt**: system-prompt template `SAFETY_CONSTITUTION` asserts PR review is always human (never auto-approved).
- **Executor**: `forge.gating.evaluate_gate()` has a hardcoded branch — any `tool_name in {"review_pr", "create_pr_after_review"}` → `GateMode.MANDATORY_HUMAN_APPROVAL` regardless of score or priors.

Both must be wired independently. Loss of either is a constitutional regression.

---

## 9. Related

- Data model: [DM-gating.md](../models/DM-gating.md)
- Pipeline events: [API-nats-pipeline-events.md](API-nats-pipeline-events.md)
- Tool layer: [API-tool-layer.md](API-tool-layer.md) (`approval_tools.request_approval`)
- DDR: [DDR-002-resume-value-rehydration-helper.md](../decisions/DDR-002-resume-value-rehydration-helper.md)
Write API-nats-fleet-lifecycle.md
235 lines
# API Contract — NATS Fleet Lifecycle (registration + discovery)

> **Type:** Bidirectional — Forge publishes its own registration/heartbeat; subscribes to fleet changes; reads KV registry
> **Transport:** NATS pub/sub on `FLEET` stream + NATS KV bucket `agent-registry`
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md), [ADR-ARCH-016](../../architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md)
> **External contract:** [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md) (nats-core; source of truth for schemas)

---

## 1. Purpose

Forge participates in the fleet CAN-bus:

1. **As an agent** — registers its own `AgentManifest` on startup, heartbeats periodically, deregisters on graceful shutdown. This makes Forge discoverable to Jarvis (control-plane commands) and operators (dashboards).
2. **As a consumer** — subscribes to `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>` for live cache invalidation, and reads `agent-registry` KV for capability resolution.

---

## 2. Forge Self-Registration

### 2.1 Manifest

```python
# forge.fleet.manifest
from nats_core.manifest import AgentManifest, IntentCapability, ToolCapability

FORGE_MANIFEST = AgentManifest(
    agent_id="forge",
    name="Forge",
    version="0.1.0",
    template="deepagents-pipeline-orchestrator",
    trust_tier="core",
    status="ready",
    max_concurrent=1,                       # ADR-SP-012 — sequential builds
    intents=[
        IntentCapability(
            pattern="build.*",
            signals=["build", "develop", "implement", "create", "make", "ship"],
            confidence=0.90,
            description="Run a feature through the software factory pipeline to PR",
        ),
        IntentCapability(
            pattern="pipeline.*",
            signals=["pipeline", "stages", "progress", "status", "deploy"],
            confidence=0.85,
            description="Operate the build pipeline — queue, inspect, cancel, resume",
        ),
        IntentCapability(
            pattern="feature.*",
            signals=["feature", "add feature", "new capability", "requirement"],
            confidence=0.80,
            description="Add a new feature to an existing project",
        ),
    ],
    tools=[
        ToolCapability(
            name="forge_greenfield",
            description="Start a full greenfield pipeline run. Returns pipeline_id immediately (fire-and-forget). Poll forge_status, cancel with forge_cancel.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "feature_yaml_path": {"type": "string"},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo", "feature_yaml_path"],
            },
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
            requires_approval=False,
        ),
        ToolCapability(
            name="forge_feature",
            description="Add a feature to an existing project. Returns pipeline_id immediately.",
            parameters={"type": "object", "properties": {
                "repo": {"type": "string"}, "feature_id": {"type": "string"},
            }, "required": ["repo", "feature_id"]},
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
        ),
        ToolCapability(
            name="forge_review_fix",
            description="Run a review-and-fix cycle on existing code. Returns pipeline_id immediately.",
            parameters={"type": "object", "properties": {
                "repo": {"type": "string"}, "subject": {"type": "string"},
            }, "required": ["repo", "subject"]},
            returns="{pipeline_id: str, queued_at: datetime}",
            risk_level="mutating",
            async_mode=True,
        ),
        ToolCapability(
            name="forge_status",
            description="Read current pipeline status (all running/paused builds, or a specific pipeline_id).",
            parameters={"type": "object", "properties": {
                "pipeline_id": {"type": "string"},
            }},
            returns="list[BuildStatus]",
            risk_level="read_only",
        ),
        ToolCapability(
            name="forge_cancel",
            description="Cancel an in-flight pipeline run.",
            parameters={"type": "object", "properties": {
                "pipeline_id": {"type": "string"},
                "reason": {"type": "string"},
            }, "required": ["pipeline_id"]},
            returns="{cancelled: bool, at: datetime}",
            risk_level="mutating",
        ),
    ],
    required_permissions=[
        "graphiti:read", "graphiti:write",
        "filesystem:read", "filesystem:write",
        "shell:execute",
        "nats:publish", "nats:subscribe",
        "network:github.com",
    ],
)
```

### 2.2 Registration call

```python
# forge.fleet.register_on_boot()
await nats_client.register_agent(FORGE_MANIFEST)
# nats-core internals:
#   1. Publish MessageEnvelope(event_type=AGENT_REGISTER, payload=manifest.model_dump())
#      to fleet.register
#   2. Put manifest.model_dump() into NATS KV bucket agent-registry, key=agent_id
```

Registration is idempotent — re-registering overwrites the KV entry (version-bumped manifest supersedes older).

### 2.3 Heartbeat

Every `forge.yaml.fleet.heartbeat_interval_seconds` (default 30):

```python
await nats_client.heartbeat(AgentHeartbeatPayload(
    agent_id="forge",
    status=current_status,                           # "ready" | "busy" | "degraded" | "draining"
    queue_depth=jetstream_pending_count,             # From JetStream consumer info
    active_tasks=1 if build_in_flight else 0,        # max_concurrent=1 so this is 0 or 1
    uptime_seconds=...,
    last_task_completed_at=...,
    active_workflow_states={build_id: lifecycle_state} if build_in_flight else {},
))
# → publishes to fleet.heartbeat.forge
```

### 2.4 Deregistration

On graceful shutdown (SIGTERM handler):

```python
await nats_client.deregister_agent("forge", reason="shutdown")
# → publishes AgentDeregistrationPayload to fleet.deregister + removes KV entry
```

On crash, no deregistration is sent; Jarvis detects via missed heartbeats (default 90s timeout).

---

## 3. Forge as Consumer — Live Fleet Watch

### 3.1 Subscriptions

```python
# forge.adapters.nats.fleet_watcher
await nats_client.watch_fleet(callback=on_fleet_change)
# nats-core internals subscribe to:
#   fleet.register               → AgentRegistrationPayload (uses AgentManifest directly per nats-core DDR-002)
#   fleet.deregister             → AgentDeregistrationPayload
#   fleet.heartbeat.>            → AgentHeartbeatPayload per agent
```

### 3.2 Cache invalidation rules

`forge.discovery` owns a 30-second TTL cache of `agent-registry` KV. Events invalidate as follows:

| Event | Cache action |
|---|---|
| `fleet.register` (agent manifest appears/changes) | Upsert cache entry for `agent_id`; bump TTL |
| `fleet.deregister` | Remove `agent_id` from cache |
| `fleet.heartbeat.{agent_id}` with status change (`ready`↔`busy`↔`degraded`↔`draining`) | Update cache `status` + `queue_depth` only |
| `fleet.heartbeat.{agent_id}` routine (no status change) | Refresh last-seen timestamp only; do not re-read KV |
| Missed heartbeat > `forge.yaml.fleet.stale_heartbeat_seconds` (default 90) | Mark cache entry `status="degraded"`; subsequent `resolve()` excludes from primary selection |

### 3.3 KV reads

On cache miss or manual invalidation:

```python
registry_snapshot: dict[str, AgentManifest] = await nats_client.get_fleet_registry()
# Returns a dict of all registered agents from the agent-registry KV bucket.
```

---

## 4. Resolution Read Path

`forge.discovery.resolve(tool_name, intent_pattern=None)`:

1. If cache age > 30s, query `nats_client.find_by_tool(tool_name)` via `NATSKVManifestRegistry` → returns `list[AgentManifest]` matching the tool name.
2. If empty and `intent_pattern` is set, query `nats_client.find_by_intent(intent_pattern, min_confidence=0.7)`.
3. Filter out `status="degraded"` (excluded from primary resolution — per domain-model.md).
4. Tie-break (see [API-nats-agent-dispatch.md §2](API-nats-agent-dispatch.md#2-resolution)).
5. Return `agent_id` or `None`.

Every resolution writes a `CapabilityResolution` entity to Graphiti `forge_pipeline_history` for future priors (see [DM-discovery.md](../models/DM-discovery.md)).

---

## 5. Topic Summary

| Direction | Template | Payload | Published / Consumed by |
|---|---|---|---|
| Publish | `fleet.register` | `AgentManifest` (full) | Forge on boot |
| Publish | `fleet.deregister` | `AgentDeregistrationPayload` | Forge on graceful shutdown |
| Publish | `fleet.heartbeat.forge` | `AgentHeartbeatPayload` | Forge every 30s |
| Subscribe | `fleet.register` | `AgentManifest` | `forge.discovery` cache invalidation |
| Subscribe | `fleet.deregister` | `AgentDeregistrationPayload` | `forge.discovery` cache eviction |
| Subscribe | `fleet.heartbeat.>` | `AgentHeartbeatPayload` | `forge.discovery` status / queue-depth refresh |
| KV read | `agent-registry` bucket | full manifests | `forge.discovery` cache refill |

---

## 6. Related

- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Data model: [DM-discovery.md](../models/DM-discovery.md)
- nats-core schemas: [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md)
Write API-cli.md
214 lines
# API Contract — Forge CLI (Click)

> **Type:** Human-facing command-line interface
> **Framework:** Click
> **Process model:** Short-lived (runs, reads/writes, exits — not a daemon)
> **Related ADRs:** [ADR-ARCH-013](../../architecture/decisions/ADR-ARCH-013-cli-read-bypasses-nats.md), [ADR-ARCH-012](../../architecture/decisions/ADR-ARCH-012-no-mcp-interface.md)

---

## 1. Purpose

`forge` is Rich's primary interface to the pipeline. It is intentionally small: five commands covering queue (write), status + history (read), cancel (write), skip (write). Everything else goes through Jarvis or NATS directly.

**Split IO:**

- **Read path** → SQLite direct. No NATS round-trip, no Forge process required (ADR-ARCH-013).
- **Write path** → NATS publish to the appropriate subject. The running Forge process consumes.

---

## 2. Command Inventory

| Command | Read/Write | Subject (if write) | Purpose |
|---|---|---|---|
| `forge queue` | Write (NATS) | `pipeline.build-queued.{feature_id}` | Enqueue a new build |
| `forge status` | Read (SQLite) | — | Show current + recent builds |
| `forge history` | Read (SQLite) | — | Show build + stage history |
| `forge cancel` | Write (NATS) | `agents.command.forge` with tool=`forge_cancel` | Cancel running/paused build |
| `forge skip` | Write (NATS) | `agents.command.forge` with tool=`forge_skip` | Skip a single flagged stage, continue build |

---

## 3. `forge queue`

### 3.1 Synopsis

```bash
forge queue <feature_id> --repo <path> [--branch <name>] \
    [--feature-yaml <path>] [--max-turns N] [--timeout SECONDS]
```

### 3.2 Flags

| Flag | Required | Default | Notes |
|---|---|---|---|
| `feature_id` (positional) | ✓ | — | e.g. `FEAT-A1B2` |
| `--repo` | ✓ | — | Absolute or `~/…` path to local clone |
| `--branch` | — | `main` | Base branch for build worktree |
| `--feature-yaml` | — | `<repo>/features/<feature_id>/feature.yaml` | Validated against allowlist |
| `--max-turns` | — | from `forge.yaml.defaults.max_turns` (5) | Passed through to `BuildQueuedPayload` |
| `--timeout` | — | from `forge.yaml.defaults.sdk_timeout` (1800) | Passed through |
| `--correlation-id` | — | auto-generated UUID | Override only for reruns |

### 3.3 Behaviour

1. Build `BuildQueuedPayload` with `triggered_by="cli"`, `originating_adapter="terminal"`, `originating_user=os.getlogin()`, `queued_at=datetime.now(UTC)`.
2. Wrap in `MessageEnvelope(source_id="forge-cli", event_type=EventType.BUILD_QUEUED, ...)`.
3. Publish to `pipeline.build-queued.{feature_id}` (via `nats-core.NATSClient`).
4. Write placeholder row to SQLite `builds` (status=`QUEUED`) so `forge status` shows it even before Forge picks it up.
5. Print `Queued FEAT-A1B2 (build pending) correlation_id=<uuid>` and exit 0.

**Exit codes:** `0` success, `1` NATS publish failure, `2` path outside allowlist, `3` duplicate feature_id already QUEUED/RUNNING/PAUSED.

---

## 4. `forge status`

### 4.1 Synopsis

```bash
forge status [<feature_id>] [--json] [--watch] [--full]
```

### 4.2 Behaviour

- Queries SQLite `builds` directly via `forge.adapters.sqlite.read_status()`.
- Default view: active builds (status IN `QUEUED`, `PREPARING`, `RUNNING`, `PAUSED`, `FINALISING`) + last 5 terminal ones.
- With `<feature_id>`: shows all builds for that feature, most recent first.
- `--watch`: polls every 2s, re-renders (uses `rich.live`).
- `--json`: emits JSON array of build rows (for piping into tooling).
- `--full`: includes `stage_log` entries per build (default: last 5 stages).

### 4.3 Output fields

```
BUILD                                            STATUS      STAGE                      STARTED        ELAPSED  SCORE
build-FEAT-A1B2-20260423170501                   RUNNING     Architecture Review        17:05:01       00:12:33 0.78
build-FEAT-C3D4-20260423140200  (paused)         PAUSED      Awaiting approval          14:02:00       03:18:12 0.52
```

### 4.4 Live autobuild progress

When the active build is running an `AsyncSubAgent` (autobuild_runner), `forge status` reads the `async_tasks` state channel via `list_async_tasks` per ADR-ARCH-031 and surfaces "Wave 2/4, 8/12 tasks done, est. 20 min remaining" as part of the STAGE cell.

---

## 5. `forge history`

### 5.1 Synopsis

```bash
forge history [--feature <feature_id>] [--limit N] [--since DATE] [--format table|json|md]
```

### 5.2 Behaviour

- `forge history` → last 50 builds.
- `forge history --feature FEAT-A1B2` → all builds for that feature, with `stage_log` expanded.
- `forge history --format md --since 2026-04-20` → markdown report suitable for Rich to paste into notes.

### 5.3 Markdown format

```markdown
# Forge history — FEAT-A1B2

## build-FEAT-A1B2-20260423170501 — COMPLETE (0h 42m)
Started: 2026-04-23 17:05:01 UTC
Finished: 2026-04-23 17:47:12 UTC
PR: https://github.com/appmilla/finproxy/pull/142

### Stages
- 17:05:03 — Retrieved priors (14 entities)            PASSED
- 17:05:47 — Build plan composed                       PASSED   score=0.84
- 17:06:15 — Architecture Review (architect-agent)     GATED    score=0.78  FLAG_FOR_REVIEW → approved by rich
- 17:12:04 — /feature-spec "login flow"                PASSED   score=0.82
- …
```

---

## 6. `forge cancel`

### 6.1 Synopsis

```bash
forge cancel <feature_id|build_id> [--reason "text"]
```

### 6.2 Behaviour

1. Resolve to a `build_id` via SQLite (pick the most recent non-terminal build for that feature).
2. Publish `CommandPayload(tool_name="forge_cancel", params={build_id, reason})` to `agents.command.forge`.
3. Subscribe to `agents.result.forge.{request_id}` with a short timeout (default 30s).
4. If reply received with `status="success"`, print confirmation.
5. If paused, Forge treats this as synthetic `ApprovalResponsePayload(decision="reject", responder="rich", reason="cli cancel")` — see [API-nats-approval-protocol.md §7](API-nats-approval-protocol.md#7-timeout-handling).

---

## 7. `forge skip`

### 7.1 Synopsis

```bash
forge skip <feature_id> [--reason "text"]
```

### 7.2 Behaviour

Only meaningful when the build is PAUSED on a `FLAG_FOR_REVIEW` gate. Publishes synthetic `ApprovalResponsePayload(decision="override", responder="rich", reason="cli skip")` to `agents.approval.forge.{build_id}.response` — graph resumes, specific stage is skipped, build continues.

If the build is not PAUSED, exits with error code and no NATS publish.

---

## 8. Shared Behaviour

### 8.1 Config loading

All commands load `forge.yaml` via `forge.config.load()`:

```python
@click.group()
@click.option("--config", default=None, help="Override forge.yaml path")
@click.pass_context
def forge(ctx, config):
    ctx.obj = AgentConfig.load(config)      # pydantic-settings; env vars override
```

### 8.2 Connection handling

- Read commands use `forge.adapters.sqlite.read_only_connect()` — no NATS connection at all.
- Write commands use `nats-core.NATSClient(config=AgentConfig.nats)` — connects, publishes, disconnects; exits cleanly.

### 8.3 Error presentation

CLI errors use Click's `ClickException` with `rich` formatting. Stack traces suppressed unless `--debug` flag is present.

### 8.4 Shell completion

Generated via `click.utils.get_app_dir` + `forge --install-completion`. Installs into shell rc file.

---

## 9. Multi-Tenancy

Project scoping is inferred from repo path:

```python
# forge.cli — project resolution
project = resolve_project_from_repo(repo_path)        # e.g. "finproxy"
topic = Topics.for_project(project, Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id))
```

`forge status`/`history` filter SQLite rows by project when `--repo` is passed (default: all projects).

---

## 10. Related

- Pipeline events (what `forge queue` publishes): [API-nats-pipeline-events.md](API-nats-pipeline-events.md)
- SQLite schema (what reads consume): [API-sqlite-schema.md](API-sqlite-schema.md)
- Agent tools (what `forge_cancel`/`forge_skip` map to): [API-tool-layer.md](API-tool-layer.md)
- DDR: [DDR-005-cli-context-manifest-resolution.md](../decisions/DDR-005-cli-context-manifest-resolution.md)
Write API-sqlite-schema.md
196 lines
# API Contract — SQLite Schema (`~/.forge/forge.db`)

> **Type:** Internal data contract — authoritative build history
> **Engine:** SQLite 3, WAL mode
> **Path:** `~/.forge/forge.db` (configurable via `forge.yaml.sqlite.path`)
> **Related ADRs:** [ADR-ARCH-009](../../architecture/decisions/ADR-ARCH-009-omit-langgraph-checkpointer.md), [ADR-ARCH-013](../../architecture/decisions/ADR-ARCH-013-cli-read-bypasses-nats.md), [ADR-SP-013](../../research/forge-pipeline-architecture.md)

---

## 1. Purpose

SQLite is Forge's durable authoritative state store. Two tables:

- `builds` — one row per build attempt, lifecycle-tracked.
- `stage_log` — many rows per build, one per reasoning-model-chosen stage dispatch.

Concurrency model: **single writer (the agent runtime) + multiple readers (CLI)**, enforced by WAL mode. The CLI never writes; the agent never blocks reads.

LangGraph checkpointer is deliberately **not** used (ADR-ARCH-009) — SQLite + JetStream is authoritative for Forge's recovery story.

---

## 2. DDL

### 2.1 `builds` table

```sql
CREATE TABLE IF NOT EXISTS builds (
    build_id TEXT PRIMARY KEY,                       -- build-{feature_id}-{YYYYMMDDHHMMSS}
    feature_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    branch TEXT NOT NULL,
    feature_yaml_path TEXT NOT NULL,
    project TEXT,                                    -- NULL = fleet-wide; else "finproxy", "guardkit", etc.

    status TEXT NOT NULL CHECK (status IN (
        'QUEUED', 'PREPARING', 'RUNNING', 'PAUSED', 'FINALISING',
        'COMPLETE', 'FAILED', 'INTERRUPTED', 'CANCELLED', 'SKIPPED'
    )),

    triggered_by TEXT NOT NULL CHECK (triggered_by IN (
        'cli', 'jarvis', 'forge-internal', 'notification-adapter'
    )),
    originating_adapter TEXT,                        -- nullable
    originating_user TEXT,                           -- nullable
    correlation_id TEXT NOT NULL,
    parent_request_id TEXT,                          -- Jarvis dispatch ID

    queued_at TEXT NOT NULL,                         -- ISO 8601 UTC
    started_at TEXT,                                 -- PREPARING transition
    completed_at TEXT,                               -- terminal state transition

    worktree_path TEXT,                              -- /var/forge/builds/{build_id}/
    pr_url TEXT,
    error TEXT,                                      -- structured reason on FAILED/INTERRUPTED/CANCELLED

    max_turns INTEGER NOT NULL DEFAULT 5,
    sdk_timeout_seconds INTEGER NOT NULL DEFAULT 1800
) STRICT;

CREATE INDEX IF NOT EXISTS idx_builds_feature ON builds (feature_id, queued_at DESC);
CREATE INDEX IF NOT EXISTS idx_builds_status ON builds (status, queued_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_builds_feature_correlation ON builds (feature_id, correlation_id);
```

### 2.2 `stage_log` table

```sql
CREATE TABLE IF NOT EXISTS stage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL REFERENCES builds(build_id),

    stage_label TEXT NOT NULL,                       -- Reasoning-model-chosen (ADR-ARCH-016)
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'local_tool', 'fleet_capability', 'subagent'
    )),
    target_identifier TEXT NOT NULL,                 -- tool name / agent_id:tool_name / subagent name

    status TEXT NOT NULL CHECK (status IN (
        'PASSED', 'FAILED', 'GATED', 'SKIPPED'
    )),
    gate_mode TEXT CHECK (gate_mode IN (
        'AUTO_APPROVE', 'FLAG_FOR_REVIEW', 'HARD_STOP', 'MANDATORY_HUMAN_APPROVAL'
    )),                                              -- NULL for PASSED stages that didn't gate

    coach_score REAL,                                -- 0.0–1.0; NULL if degraded / not applicable
    threshold_applied REAL,                          -- NULL when reasoning-driven (no static threshold)

    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_secs REAL NOT NULL,

    details_json TEXT NOT NULL                       -- JSON blob — rationale + breakdown + detections
) STRICT;

CREATE INDEX IF NOT EXISTS idx_stage_log_build ON stage_log (build_id, started_at);
CREATE INDEX IF NOT EXISTS idx_stage_log_gated ON stage_log (build_id, gate_mode)
    WHERE gate_mode IS NOT NULL;
```

### 2.3 `schema_version` table

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
) STRICT;

-- Seed row on first boot
INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'));
```

Migrations are explicit and sequential; see [DDR-003-sqlite-schema-layout-wal.md](../decisions/DDR-003-sqlite-schema-layout-wal.md) for rationale.

---

## 3. WAL + pragmas

Set on every connection in `forge.adapters.sqlite.connect()`:

```python
cx.execute("PRAGMA journal_mode = WAL;")
cx.execute("PRAGMA synchronous = NORMAL;")           # WAL is safe with NORMAL
cx.execute("PRAGMA foreign_keys = ON;")
cx.execute("PRAGMA busy_timeout = 5000;")            # 5s; CLI readers handle contention
```

**Write connection:** single, held by the agent runtime for the lifetime of the process. Serialised writes via `forge.adapters.sqlite._write_lock` (asyncio lock).

**Read connections:** per-CLI-invocation. `forge.adapters.sqlite.read_only_connect()` opens with `mode=ro` URI filename.

---

## 4. Write API (agent side)

```python
# forge.adapters.sqlite.writer
async def create_build(payload: BuildQueuedPayload) -> None: ...
async def transition_build(build_id: str, to_status: BuildStatus, **fields) -> None: ...
async def record_stage(entry: StageLogEntry) -> None: ...
async def mark_paused(build_id: str, approval_payload: ApprovalRequestPayload) -> None: ...
async def reconcile_on_boot() -> list[Build]: ...    # Returns builds needing recovery
```

All methods:

1. Accept typed Pydantic inputs (no raw dicts at this boundary).
2. Validate status transitions against the state machine (`forge.state_machine.valid_transitions`).
3. Emit a structured log entry (`structlog`) with `build_id`, `transition`, and duration.
4. Raise `ForgeSQLiteError` (subclass of `RuntimeError`) on constraint violations — caught at the tool boundary and converted to a structured error string per ADR-ARCH-025.

---

## 5. Read API (CLI side)

```python
# forge.adapters.sqlite.reader
def read_status(feature_id: str | None = None) -> list[BuildStatusView]: ...
def read_history(limit: int = 50, feature_id: str | None = None) -> list[BuildRow]: ...
def read_stages(build_id: str) -> list[StageLogEntry]: ...
def read_paused_builds() -> list[Build]: ...
```

Reads run synchronously (Click is sync); no coroutines involved.

---

## 6. Crash-Recovery Semantics

On boot, `reconcile_on_boot()` returns builds whose status is not terminal:

| SQLite status on boot | Recovery action |
|---|---|
| `QUEUED` | Wait for JetStream redelivery; no-op |
| `PREPARING` | Mark `INTERRUPTED`, publish `pipeline.build-failed` with `recoverable=True`, JetStream will redeliver → restart |
| `RUNNING` | Mark `INTERRUPTED` (retry-from-scratch policy per anchor §5) |
| `PAUSED` | Re-enter PAUSED; re-emit `ApprovalRequestPayload`; re-fire `interrupt()` when graph reruns |
| `FINALISING` | Mark `INTERRUPTED` with warning — PR creation may have succeeded; operator reconciles manually |
| `COMPLETE`/`FAILED`/`CANCELLED`/`SKIPPED` | Ack any residual JetStream message; no-op |

---

## 7. Backup + Retention

- WAL auto-checkpoints at 1000 frames (SQLite default).
- `~/.forge/forge.db` is backed up weekly via host cron to `~/.forge/backups/forge-YYYYMMDD.db.gz` (out of Forge scope; documented in `ops/backup.md`).
- Retention: indefinite. `builds` grows at ≤ 1 row/build (sequential execution caps this at ≤ a few hundred/year); `stage_log` grows at ~30 rows/build. `VACUUM` advisable quarterly; no automatic pruning.

---

## 8. Related

- Data model: [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
- CLI read path: [API-cli.md](API-cli.md)
- DDR: [DDR-003-sqlite-schema-layout-wal.md](../decisions/DDR-003-sqlite-schema-layout-wal.md)
Write API-tool-layer.md
392 lines
# API Contract — Tool Layer (`@tool(parse_docstring=True)`)

> **Type:** DeepAgents tool functions — schema-from-docstrings
> **Framework:** LangChain `@tool` decorator, DeepAgents 0.5.3 tool-layer conventions
> **Related ADRs:** [ADR-ARCH-004](../../architecture/decisions/ADR-ARCH-004-full-guardkit-cli-tool-surface.md), [ADR-ARCH-020](../../architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md), [ADR-ARCH-025](../../architecture/decisions/ADR-ARCH-025-tool-error-handling.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)
> **Specialist rule:** langchain-tool-decorator-specialist — every tool wraps logic in try/except, returns a string, never raises.

---

## 1. Purpose

Every Forge-specific `@tool` is declared in this contract. DeepAgents built-ins (`write_todos`, `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`, `task`, `interrupt`, Memory Store) are used as-is from DeepAgents 0.5.3 and not redeclared here (ADR-ARCH-020).

**Five tool groups:**

1. **Capability dispatch** — one generic tool for all fleet calls (ADR-ARCH-015).
2. **Approval + notification** — approval round-trip + notification emission.
3. **Graphiti** — learning-loop reads and writes.
4. **GuardKit** — one tool per GuardKit subcommand (ADR-ARCH-004).
5. **History** — SQLite writes.

Plus the five **AsyncSubAgent supervisor tools** exposed by DeepAgents middleware (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` — ADR-ARCH-031). These are surfaced by DeepAgents and need no Forge declaration.

---

## 2. Universal Error Contract (ADR-ARCH-025)

Every `@tool` function:

- Returns `str` (JSON-encoded where structured — reasoning model parses).
- Wraps its entire body in `try / except Exception as exc:`.
- On failure, returns `f'{{"status":"error","error":"{type(exc).__name__}: {exc}"}}'`.
- NEVER raises. Adapter exceptions are converted at the tool boundary.
- Logs via `structlog` with `tool_name`, `duration_ms`, `status`.

This is asserted in the langchain-tool-decorator-specialist rule and the specialist-agent LES1 parity patterns.

---

## 3. Capability Dispatch

### 3.1 `dispatch_by_capability`

```python
@tool(parse_docstring=True)
async def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 900,
) -> str:
    """Resolve a fleet specialist for a capability and dispatch a typed command.

    The generic replacement for per-role dispatch tools (ADR-ARCH-015). Resolution
    uses exact tool-name match first, then intent-pattern fallback. Returns the
    specialist's ResultPayload as JSON, or a structured error if no agent
    resolves / the call times out.

    Args:
        tool_name: The ToolCapability.name the Forge wants invoked, e.g.
            "review_specification" or "generate_conversation_starter".
        payload_json: JSON string matching the target ToolCapability.parameters
            schema. Reasoning model assembles this from build context.
        intent_pattern: Optional intent pattern for fallback resolution when no
            exact tool match exists. Minimum confidence 0.7 required.
        timeout_seconds: Hard cut-off for the reply. Defaults to 900 (15 min).
            On breach, returns status=timeout and the caller decides what next.

    Returns:
        JSON string: ResultPayload on success; {"status":"error","error":"..."}
        on resolution or call failure.
    """
```

Implementation flow documented in [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md).

---

## 4. Approval + Notification

### 4.1 `request_approval`

```python
@tool(parse_docstring=True)
async def request_approval(
    build_id: str,
    stage_label: str,
    gate_mode: str,                                    # FLAG_FOR_REVIEW | HARD_STOP | MANDATORY_HUMAN_APPROVAL
    coach_score: float | None,
    rationale: str,
    details_json: str,
) -> str:
    """Pause the build and request Rich's approval via NATS + LangGraph interrupt().

    Publishes ApprovalRequestPayload to agents.approval.forge.{build_id}, marks
    the build PAUSED in SQLite, then calls LangGraph interrupt(). On resume, the
    value arrives as dict under server mode — this function rehydrates it via
    forge.adapters.langgraph.resume_value_as before returning.

    Args:
        build_id: The running build's ID (from SQLite builds.build_id).
        stage_label: Reasoning-model-chosen label for the stage being gated.
        gate_mode: One of FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL.
        coach_score: Score from the dispatched specialist, or None in degraded mode.
        rationale: Reasoning-model's explanation of why this gate fired.
        details_json: JSON blob matching ApprovalRequestPayload.details convention
            (see API-nats-approval-protocol.md §3.2).

    Returns:
        JSON string with decision, responder, reason — the rehydrated
        ApprovalResponsePayload as dict.
    """
```

### 4.2 `emit_notification`

```python
@tool(parse_docstring=True)
async def emit_notification(
    channel: str,                                      # e.g. "jarvis.notification.telegram"
    subject: str,
    body: str,
    metadata_json: str = "{}",
) -> str:
    """Publish a NotificationPayload to a jarvis.notification.* channel.

    Used for AUTO_APPROVE stages — informational, not a gate. Reasoning model
    decides whether to notify based on retrieved Rich-ack-behaviour priors
    (ADR-ARCH-019 — no static notification config).

    Args:
        channel: Full NATS subject, e.g. "jarvis.notification.slack".
        subject: Short human-readable subject line.
        body: Longer body (markdown). Adapter renders per-transport.
        metadata_json: JSON blob of adapter-specific hints (priority, link, etc.).

    Returns:
        JSON string: {"status":"published","at":"<iso8601>"}.
    """
```

---

## 5. Graphiti

### 5.1 `record_override`

```python
@tool(parse_docstring=True)
async def record_override(
    build_id: str,
    stage_label: str,
    gate_mode_before: str,
    decision: str,
    rich_reason: str | None,
) -> str:
    """Record a human override on a gated stage in forge_pipeline_history.

    Used by learning loop to detect override patterns (e.g. "Rich overrode 6/10
    recent flag-for-reviews on review_architecture"). The CalibrationAdjustment
    entity is proposed separately — this tool only records the raw event.

    Args:
        build_id: The build where the override happened.
        stage_label: Reasoning-model-chosen label.
        gate_mode_before: What Forge chose (FLAG_FOR_REVIEW / HARD_STOP / …).
        decision: Rich's decision — approve / reject / defer / override.
        rich_reason: Optional reason text from ApprovalResponsePayload.reason.

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

### 5.2 `write_gate_decision`

```python
@tool(parse_docstring=True)
async def write_gate_decision(
    build_id: str,
    stage_label: str,
    decision_json: str,
) -> str:
    """Write a GateDecision (with evidence priors) to forge_pipeline_history.

    Every gate evaluation records why — the retrieved priors that informed it,
    the Coach score, the detection findings, and the chosen mode. This is the
    raw training data for future threshold calibration.

    Args:
        build_id: The build.
        stage_label: Reasoning-model-chosen label.
        decision_json: GateDecision.model_dump_json().

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

### 5.3 `read_override_history`

```python
@tool(parse_docstring=True)
async def read_override_history(
    capability: str,
    limit: int = 20,
    project_scope: str | None = None,
) -> str:
    """Retrieve recent override events for a capability from forge_pipeline_history.

    Reasoning model calls this to check "has Rich been overriding my gates on
    this capability lately?" — informs whether to auto-approve vs flag.

    Args:
        capability: e.g. "review_specification", "review_architecture".
        limit: How many recent overrides to return.
        project_scope: Filter to a project; None means fleet-wide.

    Returns:
        JSON array of {build_id, stage_label, gate_mode_before, decision,
        coach_score, timestamp}.
    """
```

### 5.4 `write_session_outcome`

```python
@tool(parse_docstring=True)
async def write_session_outcome(
    build_id: str,
    outcome: str,                                      # COMPLETE | FAILED | CANCELLED | SKIPPED
    summary_json: str,
) -> str:
    """Finalise the Graphiti record for a build — cross-references stage log.

    Called on terminal state transitions. Writes the high-level outcome node
    linking all the build's GateDecision + CapabilityResolution entities,
    plus PR URL and duration for future pattern mining.

    Args:
        build_id: The terminal build.
        outcome: Terminal status.
        summary_json: Build summary — duration, task counts, pr_url, error.

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

---

## 6. GuardKit Subcommand Tools

One `@tool` per GuardKit subcommand (ADR-ARCH-004). Each is a thin wrapper over DeepAgents `execute` that:

1. Assembles the subcommand + flags.
2. Reads `.guardkit/context-manifest.yaml` from the target repo to auto-derive `--context` flags (see [DDR-005](../decisions/DDR-005-cli-context-manifest-resolution.md)).
3. Pipes through `--nats` so GuardKit emits progress on `pipeline.stage-complete.*` directly.
4. Parses the GuardKit progress stream and surfaces artefact paths in the return value.

### 6.1 Tool list

| Tool | Wraps | Parameters |
|---|---|---|
| `guardkit_system_arch` | `guardkit system-arch` | repo, feature_id, scope |
| `guardkit_system_design` | `guardkit system-design` | repo, focus, protocols |
| `guardkit_system_plan` | `guardkit system-plan` | repo, feature_description |
| `guardkit_feature_spec` | `guardkit feature-spec` | repo, feature_description, context_paths |
| `guardkit_feature_plan` | `guardkit feature-plan` | repo, feature_id |
| `guardkit_task_review` | `guardkit task-review` | repo, task_id |
| `guardkit_task_work` | `guardkit task-work` | repo, task_id |
| `guardkit_task_complete` | `guardkit task-complete` | repo, task_id |
| `guardkit_autobuild` | `guardkit autobuild` | repo, feature_id |
| `guardkit_graphiti_add_context` | `guardkit graphiti add-context` | doc_path, group |
| `guardkit_graphiti_query` | `guardkit graphiti query` | query, group |

All share a common docstring pattern:

```python
@tool(parse_docstring=True)
async def guardkit_feature_spec(
    repo: str,
    feature_description: str,
    context_paths: list[str] | None = None,
) -> str:
    """Run `guardkit feature-spec` in the target repo with NATS streaming.

    Args:
        repo: Absolute path to the target repo (worktree root).
        feature_description: One-line description for the /feature-spec session.
        context_paths: Optional explicit --context overrides. When None, the
            context-manifest resolver picks them automatically.

    Returns:
        JSON: {"status":"success|failed","artefacts":["..."],"coach_score":...,
        "duration_secs":...,"stderr":"..."} — see API-subprocess.md §4 for
        the full result schema.
    """
```

---

## 7. History Tools

### 7.1 `record_build_transition`

```python
@tool(parse_docstring=True)
async def record_build_transition(
    build_id: str,
    to_status: str,
    fields_json: str = "{}",
) -> str:
    """Transition a build's status in SQLite and validate against state machine.

    Thin wrapper — the reasoning model uses this when it's making an explicit
    lifecycle transition (PREPARING → RUNNING, RUNNING → FINALISING, etc.).
    Terminal transitions trigger forge.adapters.nats to ack the JetStream message.

    Args:
        build_id: Build to transition.
        to_status: One of the BuildStatus enum values.
        fields_json: Extra fields to update (pr_url, error, worktree_path, etc.).

    Returns:
        JSON: {"status":"transitioned","from":"RUNNING","to":"FINALISING"}.
    """
```

### 7.2 `record_stage`

```python
@tool(parse_docstring=True)
async def record_stage(
    build_id: str,
    stage_label: str,
    target_kind: str,
    target_identifier: str,
    status: str,
    coach_score: float | None,
    gate_mode: str | None,
    duration_secs: float,
    details_json: str,
) -> str:
    """Write a StageLogEntry to SQLite after a dispatch completes.

    The reasoning model calls this after every dispatch — the emergent stage_label
    is what Rich reads in `forge history`. target_kind is one of:
    local_tool / fleet_capability / subagent.

    Args:
        build_id: Build that produced this stage.
        stage_label: Reasoning-model-chosen human-readable label.
        target_kind: local_tool | fleet_capability | subagent.
        target_identifier: tool name, agent_id:tool_name, or subagent name.
        status: PASSED | FAILED | GATED | SKIPPED.
        coach_score: Score if produced; None in degraded mode.
        gate_mode: Gate mode if gated; None for plain PASSED/FAILED stages.
        duration_secs: Wall-clock duration.
        details_json: Rationale + priors + findings as JSON.

    Returns:
        JSON: {"status":"recorded","stage_id":123}.
    """
```

---

## 8. Async-Subagent Supervisor Tools (DeepAgents)

Per ADR-ARCH-031, exposed by DeepAgents `AsyncSubAgentMiddleware` — not redeclared here. Usage contracts:

| Tool | Called by Forge when |
|---|---|
| `start_async_task` | Launching `autobuild_runner` for a build |
| `check_async_task` | Deciding "should I continue waiting or proceed?" |
| `update_async_task` | Rich injects "stop after current wave" via approval override |
| `cancel_async_task` | Responding to `forge cancel` CLI command |
| `list_async_tasks` | Serving `forge status` live progress view |

The `async_tasks` state channel is the contract boundary — see [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md).

---

## 9. Related

- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Approval contract: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- Subagents: [API-subagents.md](API-subagents.md)
- Subprocess wrapper: [API-subprocess.md](API-subprocess.md)
- Data models: [DM-gating.md](../models/DM-gating.md), [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files) — 6 of 9 done

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Offer Graphiti seeding commands
Write API-subagents.md
174 lines
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
            "read_file", "write_file", "ls", "grep",    # DeepAgents built-ins
            "write_todos",
            "guardkit_feature_spec",
            "guardkit_feature_plan",
            "read_override_history",
            "dispatch_by_capability",                    # May call architect-agent for feasibility
        ],
    )
```

### 2.2 Invocation contract

```python
# Invoked via DeepAgents built-in task() — sync, supervisor blocks until return
result_json = await task(
    subagent_name="build_plan_composer",
    task_description=f"Compose build plan for {feature_id}",
    context={...},
)
# Return value is a JSON string; reasoning model parses and decides next step.
```

**Gate.** Per ADR-ARCH-007, the output is always gated — the reasoning model evaluates the build plan score against retrieved priors and either auto-approves, flags for review, or hard-stops before `autobuild_runner` is dispatched.

---

## 3. `autobuild_runner` — Async SubAgent

### 3.1 Separate graph

Per ADR-ARCH-031, `autobuild_runner` is its own LangGraph graph registered in `langgraph.json`:

```json
{
  "graphs": {
    "forge":             "./src/forge/agent.py:graph",
    "autobuild_runner":  "./src/forge/subagents/autobuild_runner.py:graph"
  }
}
```

Both graphs run in the same process under `langgraph dev` (ASGI transport, co-deployed — ADR-ARCH-031 "Transport choice"). Zero network latency; no separate auth.

### 3.2 Factory

```python
# forge.subagents.autobuild_runner_spec
from deepagents import AsyncSubAgent
from forge.prompts import AUTOBUILD_RUNNER_PROMPT

def autobuild_runner_spec(domain_prompt: str) -> AsyncSubAgent:
    return AsyncSubAgent(
        name="autobuild_runner",
        description=(
            "Execute a build plan wave-by-wave, running /task-work per task and gating each. "
            "Long-running (30–90+ min). Launched via start_async_task. Supervisor polls "
            "check_async_task / list_async_tasks for live status. Mid-flight steering via "
            "update_async_task; cancellation via cancel_async_task. Internal approvals "
            "use interrupt() independently of the supervisor graph."
        ),
        system_prompt=AUTOBUILD_RUNNER_PROMPT.format(domain_prompt=domain_prompt),
        model="google_genai:gemini-2.5-flash",           # implementation model
        tools=[
            "read_file", "write_file", "edit_file", "ls", "glob", "grep",
            "execute",                                    # DeepAgents built-in — shells to /usr/local/bin/guardkit
            "write_todos",
            "interrupt",                                  # For gate-driven pauses inside waves
            "guardkit_task_work",
            "guardkit_task_review",
            "guardkit_task_complete",
            "guardkit_autobuild",
            "dispatch_by_capability",                     # For QA/UX/Ideation mid-build
            "record_stage",
            "emit_notification",
            "request_approval",
        ],
        transport="asgi",                                 # Co-deployed; ADR-ARCH-031
    )
```

### 3.3 Supervisor interaction

Exposed automatically by `AsyncSubAgentMiddleware`:

| Supervisor tool | Shape | Use |
|---|---|---|
| `start_async_task` | `(name, task_description, context) → task_id` | Dispatch autobuild |
| `check_async_task` | `(task_id) → {status, last_activity, async_tasks snapshot}` | Poll during long waits |
| `update_async_task` | `(task_id, directive) → ack` | Mid-flight steering |
| `cancel_async_task` | `(task_id, reason) → {cancelled: bool}` | Honour CLI cancel |
| `list_async_tasks` | `() → [{task_id, state, ...}]` | Populate `forge status` |

The `async_tasks` state channel is a first-class LangGraph channel and survives context compaction per DeepAgents 0.5.3 docs. See [DDR-006](../decisions/DDR-006-async-subagent-state-channel-contract.md) for Forge's contract over what lives in each task's state entry.

### 3.4 Interaction with `interrupt()`

When a gate inside `autobuild_runner` fires `interrupt()`:

- The **async subgraph** halts; the supervisor is **not** blocked.
- NATS `ApprovalRequestPayload` is published normally (see [API-nats-approval-protocol.md](API-nats-approval-protocol.md)).
- The NATS resume subscriber resumes the **specific subgraph** (not the supervisor) via the graph's resume API, passing the rehydrated `ApprovalResponsePayload`.
- The supervisor observes the pause via `check_async_task`/`list_async_tasks` — the task state includes `waiting_for="approval:{stage_label}"`.

---

## 4. Model Assignment Rationale

| Subagent | Model | Why |
|---|---|---|
| Supervisor (Forge graph) | `google_genai:gemini-3.1-pro` | Reasoning — makes all gate decisions, composes system prompts, decides stage ordering (ADR-ARCH-002, ADR-ARCH-010) |
| `build_plan_composer` | `google_genai:gemini-3.1-pro` | Reasoning — plan composition requires priors retrieval + risk reasoning |
| `autobuild_runner` | `google_genai:gemini-2.5-flash` | Implementation — task execution, file edits, shell ops; cheaper + faster for per-task loops |

All three are overridable via `forge.yaml.models.*` — provider-neutral via `init_chat_model("provider:model")` (ADR-ARCH-010).

---

## 5. Testing Contract

Per `pytest-agent-testing-specialist` rule:

- Unit tests patch `create_deep_agent`, `yaml.safe_load`, and the `SubAgent`/`AsyncSubAgent` factories.
- `tmp_path` fixtures stand in for `forge.yaml` and domain files.
- Async tests use `pytest-asyncio`; no real NATS/LangGraph server required.
- Integration tests against real NATS + real LangGraph server sit in `tests/integration/` and require `docker-compose up` of the GB10 stack.

---

## 6. Related

- ADRs: ADR-ARCH-031 (async-vs-sync rationale), ADR-ARCH-020 (DeepAgents built-ins)
- Tool layer: [API-tool-layer.md](API-tool-layer.md)
- Async state contract: [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md)
Write API-subprocess.md
180 lines
# API Contract — Subprocess (GuardKit + git + gh via DeepAgents `execute`)

> **Type:** Outbound shell calls
> **Transport:** DeepAgents built-in `execute` tool + thin wrappers
> **Related ADRs:** [ADR-ARCH-004](../../architecture/decisions/ADR-ARCH-004-full-guardkit-cli-tool-surface.md), [ADR-ARCH-020](../../architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md), [ADR-ARCH-023](../../architecture/decisions/ADR-ARCH-023-permissions-constitutional-safety.md), [ADR-ARCH-028](../../architecture/decisions/ADR-ARCH-028-ephemeral-per-build-worktrees.md)

---

## 1. Purpose

Every shell call Forge makes goes through DeepAgents `execute`, wrapped by one of three adapter sets:

- **`forge.adapters.guardkit`** — GuardKit CLI subcommands, with NATS streaming and progress parsing.
- **git / gh** — version control and PR operations, called directly from `autobuild_runner` via thin wrappers.
- **Arbitrary shell** — the reasoning model can invoke `execute` directly for build-specific commands (test runners, linters), constrained by `forge.yaml.permissions.shell.allowlist`.

All shell calls run within the build's worktree (`/var/forge/builds/{build_id}/`) — ephemeral, allowlisted path (ADR-ARCH-028).

---

## 2. Permissions Constraint (ADR-ARCH-023)

`forge.yaml.permissions` governs every `execute` call. The config schema:

```yaml
permissions:
  shell:
    allowlist:                             # Binary names or absolute paths
      - /usr/local/bin/guardkit
      - /usr/bin/git
      - /usr/bin/gh
      - python
      - pytest
      - pre-commit
      - npm
      - yarn
    working_directory_allowlist:
      - /var/forge/builds/*                # Glob allowlist — ephemeral worktrees only
    timeout_default_seconds: 600
  filesystem:
    read_allowlist:
      - /var/forge/builds/*
      - ~/.forge/cache/**
    write_allowlist:
      - /var/forge/builds/*
      - ~/.forge/forge.db
      - ~/.forge/logs/**
  network:
    allowlist:
      - api.github.com
      - objects.githubusercontent.com
      - *.googleapis.com                   # For Gemini + Graphiti embeddings
      - *.tail*.ts.net                     # Tailscale (Graphiti on NAS)
```

These permissions are **constitutional** — not reasoning-adjustable (ADR-ARCH-023). Violations are enforced by DeepAgents' permissions system; Forge relies on the framework, does not re-check at the adapter layer.

---

## 3. GuardKit Adapter

### 3.1 `execute` invocation shape

```python
# forge.adapters.guardkit.run()
async def run(
    subcommand: str,                       # e.g. "feature-spec"
    args: list[str],                       # positional + flags
    repo_path: Path,
    timeout_seconds: int = 600,
    with_nats_streaming: bool = True,
) -> GuardKitResult:
    cmd = [
        "/usr/local/bin/guardkit",
        subcommand,
        *args,
        *(["--nats"] if with_nats_streaming else []),
    ]
    raw = await execute(
        command=cmd,
        cwd=str(repo_path),
        timeout=timeout_seconds,
    )
    return parse_guardkit_output(raw, subcommand=subcommand)
```

### 3.2 Progress stream integration

When `--nats` is passed, GuardKit emits progress events on `pipeline.stage-complete.*` subjects directly (see [API-nats-pipeline-events.md §3.1](API-nats-pipeline-events.md#31-subject-family)). Forge subscribes in parallel to pick up interim progress for `forge status`.

The synchronous `execute` call still blocks on GuardKit exit; the NATS stream is just telemetry — the authoritative result is the parsed stdout/exit-code.

### 3.3 Context manifest resolution

Before every GuardKit invocation, `forge.adapters.guardkit.resolve_context_flags()` reads `.guardkit/context-manifest.yaml` from `repo_path` and adds `--context <path>` flags according to the command type:

| GuardKit command | Manifest categories loaded |
|---|---|
| `system-arch` | architecture + decisions |
| `system-design` | specs + decisions + contracts |
| `feature-spec` | specs + contracts + source |
| `feature-plan` | specs + decisions + architecture |
| `autobuild` | contracts + source |
| (any) | `internal_docs.always_include` |

See [DDR-005-cli-context-manifest-resolution.md](../decisions/DDR-005-cli-context-manifest-resolution.md) for the resolution algorithm and fallback for missing manifests.

### 3.4 Result schema

```python
class GuardKitResult(BaseModel):
    status: Literal["success", "failed", "timeout"]
    subcommand: str
    artefacts: list[str]                   # Absolute paths emitted by GuardKit
    coach_score: float | None              # Extracted from stdout when present
    criterion_breakdown: dict[str, float] | None
    detection_findings: list[dict[str, Any]] | None
    duration_secs: float
    stdout_tail: str                       # Last 4 KB for logging
    stderr: str | None
    exit_code: int
```

Parser is tolerant — unknown GuardKit output shapes degrade to `status="success"` with empty `artefacts` rather than failing the whole call. Reasoning model decides whether the stage actually produced useful output.

---

## 4. Git + gh Adapters

Thin wrappers under `forge.adapters.git`:

```python
async def prepare_worktree(build_id: str, repo: Path, branch: str) -> Path: ...
async def commit_all(worktree: Path, message: str) -> str: ...     # returns sha
async def push(worktree: Path, remote_branch: str) -> None: ...
async def create_pr(
    worktree: Path,
    title: str,
    body: str,
    base: str = "main",
    draft: bool = False,
) -> str: ...                                                     # returns PR URL
```

All methods:

- Use `execute` under the hood; respect permissions allowlist.
- Run inside the build's worktree path.
- Return structured errors on failure (ADR-ARCH-025 — never raise past the adapter boundary).

### 4.1 gh authentication

Uses `gh auth token` from `GH_TOKEN` env var (set by Docker deployment — not stored in `forge.yaml`). Forge does not manage GitHub credentials; credentials leave the container via subprocess only.

---

## 5. Worktree Lifecycle

Per ADR-ARCH-028:

1. **On `PREPARING`** — `forge.adapters.git.prepare_worktree(build_id, repo, branch)` creates `/var/forge/builds/{build_id}/`, initialises a fresh `git worktree`.
2. **On RUNNING** — all reads/writes/executes constrained to this path.
3. **On terminal state transition** — `forge.adapters.git.cleanup_worktree(build_id)` deletes the path. Forge retains SQLite + Graphiti history; source is reproducible from the PR.

Worktree cleanup is best-effort: failure to delete is logged but does not block state transition.

---

## 6. Return-value Contract

Every subprocess wrapper returns a typed Pydantic result (`GuardKitResult`, `GitOpResult`, etc.) and raises only at the adapter's internal edges. Tool-layer functions catch exceptions, convert to structured error strings, and return them as JSON (ADR-ARCH-025). The reasoning model sees `status: "error"` + message, never a raised exception.

---

## 7. Related

- Tool layer: [API-tool-layer.md](API-tool-layer.md) (`guardkit_*` wrapper tools)
- Subagents: [API-subagents.md](API-subagents.md) (`autobuild_runner` is the primary subprocess consumer)
- DDR: [DDR-005-cli-context-manifest-resolution.md](../decisions/DDR-005-cli-context-manifest-resolution.md)
9 contracts done. Writing 5 data models now.

Write DM-build-lifecycle.md
203 lines
# Data Model — Build Lifecycle

> **Container:** SQLite + Agent Runtime
> **Owners:** `forge.adapters.sqlite` (persistence), `forge.state_machine` (transition rules)
> **Related ADRs:** [ADR-SP-013](../../research/forge-pipeline-architecture.md), [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)

---

## 1. Entities

### `Build`

Authoritative record of a feature-to-PR attempt. One row per attempt.

```python
class Build(BaseModel):
    build_id: str                          # build-{feature_id}-{YYYYMMDDHHMMSS}
    feature_id: str
    repo: str                              # Absolute path or URI
    branch: str
    feature_yaml_path: str
    project: str | None                    # Multi-tenancy scope — NULL means fleet-wide

    status: BuildStatus                    # See §2

    triggered_by: TriggerSource            # cli | jarvis | forge-internal | notification-adapter
    originating_adapter: str | None
    originating_user: str | None
    correlation_id: str                    # UUID — threaded through all events
    parent_request_id: str | None          # Jarvis dispatch ID

    queued_at: datetime                    # UTC
    started_at: datetime | None            # PREPARING transition
    completed_at: datetime | None          # terminal state

    worktree_path: Path | None             # Ephemeral — /var/forge/builds/{build_id}/
    pr_url: str | None
    error: str | None

    max_turns: int = 5
    sdk_timeout_seconds: int = 1800
```

### `StageLogEntry`

One row per reasoning-model dispatch. **Stage labels are emergent** (ADR-ARCH-016) — no controlled vocabulary.

```python
class StageLogEntry(BaseModel):
    id: int                                # Auto-increment PK
    build_id: str                          # FK → builds
    stage_label: str                       # Reasoning-model-chosen, e.g. "Architecture Review"
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str                 # tool name / agent_id:tool_name / subagent name

    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: GateMode | None             # NULL for non-gated stages
    coach_score: float | None              # 0.0–1.0; NULL in degraded mode
    threshold_applied: float | None        # NULL when reasoning-driven (no static threshold)

    started_at: datetime
    completed_at: datetime
    duration_secs: float
    details_json: dict[str, Any]           # Serialised at write time; see §3
```

### `BuildQueuedPayload` (imported — `nats-core`)

Already defined in `nats-core.events.pipeline`. See [nats-core spec §Feature 2](../../../../nats-core/docs/design/specs/nats-core-system-spec.md).

---

## 2. Lifecycle State Machine

```
                       ┌─── redelivery from JetStream ───┐
                       │                                 │
  QUEUED ──► PREPARING ──► RUNNING ──► FINALISING ──► COMPLETE
     ▲          │            │  ▲           │            │
     │          │            │  │           │            │
     │          │            ▼  │           │            │
     │          │          PAUSED           │            │
     │          │            │              │            │
     │          │  (interrupt() halt;       │            │
     │          │   ApprovalResponse        │            │
     │          │   resumes)                │            │
     │          │                           │            │
     │          ▼                           ▼            │
     │      FAILED ◄───────────────────────────────────── │
     │          ▲                                         │
     │          │                                         │
     ├── on crash ──► INTERRUPTED ──► (re-enter PREPARING)│
     │                                                    │
     └─────────── CANCELLED ◄── forge cancel (any non-terminal state)
                                                          │
                      SKIPPED ◄── forge skip (single stage)
```

### 2.1 Valid transitions

| From | To | Trigger |
|---|---|---|
| `QUEUED` | `PREPARING` | JetStream delivery accepted, worktree creation begins |
| `QUEUED` | `CANCELLED` | `forge cancel` before pickup |
| `PREPARING` | `RUNNING` | Worktree ready, first stage dispatch |
| `PREPARING` | `FAILED` | Worktree creation / feature.yaml validation failure |
| `PREPARING` | `INTERRUPTED` | Crash recovery |
| `RUNNING` | `PAUSED` | `FLAG_FOR_REVIEW` / `HARD_STOP` / `MANDATORY_HUMAN_APPROVAL` gate fires |
| `RUNNING` | `FINALISING` | All stages passed, PR creation begins |
| `RUNNING` | `FAILED` | `HARD_STOP` with no retry path |
| `RUNNING` | `INTERRUPTED` | Crash recovery |
| `RUNNING` | `CANCELLED` | `forge cancel` during active build |
| `PAUSED` | `RUNNING` | `ApprovalResponsePayload(decision="approve")` rehydrates |
| `PAUSED` | `FAILED` | `ApprovalResponsePayload(decision="reject")` |
| `PAUSED` | `CANCELLED` | `forge cancel` while paused |
| `PAUSED` | `SKIPPED` | `ApprovalResponsePayload(decision="override")` via `forge skip` — stage skipped, build continues as RUNNING |
| `FINALISING` | `COMPLETE` | PR URL confirmed, JetStream ack sent |
| `FINALISING` | `FAILED` | PR creation failed |
| `FINALISING` | `INTERRUPTED` | Crash during finalisation (rare) |
| `INTERRUPTED` | `PREPARING` | On restart — retry from scratch (anchor §5) |

### 2.2 Terminal states (ack JetStream)

`COMPLETE`, `FAILED`, `CANCELLED`, `SKIPPED`. `PAUSED` is explicitly **not** terminal — leaves the message unacked so the queue position is held.

`INTERRUPTED` is a transitional state used only on recovery; the message is re-queued via JetStream redelivery rather than being acked.

---

## 3. `details_json` Conventions

The `stage_log.details_json` blob is reasoning-model-authored. Forge's writer does not impose a schema but **recommends** these keys (indexed by `forge history` renderer):

```python
{
    "rationale": "Why the reasoning model chose this target for this stage",
    "priors_referenced": [                             # IDs of retrieved Graphiti entities
        "forge_pipeline_history/prior-abc123",
    ],
    "coach_breakdown": {
        "criteria": {"fidelity": 0.8, "rigour": 0.6, ...},
        "detections": [
            {"pattern": "SCOPE_CREEP", "severity": "medium", "evidence": "..."},
        ],
    },
    "approval": {                                      # Only present when gate_mode fired
        "request_id": "...",
        "response": {"decision": "approve", "responder": "rich", "reason": "..."},
        "wait_duration_secs": 127.3,
    },
    "artefacts": ["/var/forge/builds/build-.../docs/.../file.md"],
    "subagent_task_id": "autobuild-a3f2",              # Link to async subagent state
}
```

---

## 4. Relationships

```
Build (1) ─── (many) StageLogEntry                        # FK build_id; cascade delete
Build (1) ─── (1) BuildQueuedPayload                      # Origin payload — stored in JetStream, not duplicated in SQLite
Build (1) ─── (0..N) GateDecision                         # One per gated StageLogEntry; see DM-gating
Build (1) ─── (0..1) async_tasks state entry              # See DDR-006 — linked by subagent_task_id
Build (1) ─── (0..N) CapabilityResolution                 # One per fleet-dispatch StageLogEntry; see DM-discovery
```

---

## 5. Invariants

| Invariant | Enforcement |
|---|---|
| `build_id` is unique across all time | PK constraint + `build_id` includes timestamp |
| `(feature_id, correlation_id)` unique | SQLite unique index (`uq_builds_feature_correlation`) |
| `status` transitions only follow §2.1 table | `forge.state_machine.validate_transition()` pre-write check |
| Terminal `status` ⇒ `completed_at` is set | Writer pre-write assertion |
| `PAUSED` ⇒ corresponding `ApprovalRequestPayload` was published | `forge.adapters.nats.mark_paused()` is the only entry point; it publishes then writes |
| `stage_log.build_id` references a live `builds` row | FK constraint |
| Coach score, if present, is in `[0.0, 1.0]` | Pydantic validator on write |
| `gate_mode` is NULL iff `status != "GATED"` | SQL CHECK constraint (not enforced by engine, validated in `record_stage`) |

---

## 6. Query patterns (CLI)

| Purpose | Query |
|---|---|
| `forge status` active | `SELECT * FROM builds WHERE status IN ('QUEUED','PREPARING','RUNNING','PAUSED','FINALISING') ORDER BY queued_at DESC` |
| `forge status <feature>` | `SELECT * FROM builds WHERE feature_id = ? ORDER BY queued_at DESC` |
| `forge history` default | `SELECT * FROM builds ORDER BY queued_at DESC LIMIT 50` |
| `forge history --feature X` | `SELECT * FROM builds WHERE feature_id = ? ORDER BY queued_at DESC` + `SELECT * FROM stage_log WHERE build_id IN (...) ORDER BY started_at` |
| `forge status --full` detail | joins above with `stage_log` last 5 rows per build |

---

## 7. Related

- Schema + pragmas: [API-sqlite-schema.md](../contracts/API-sqlite-schema.md)
- Gating: [DM-gating.md](DM-gating.md)
- Discovery: [DM-discovery.md](DM-discovery.md)
- Async state: [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md)
Write DM-gating.md
212 lines
# Data Model — Gating

> **Container:** Domain Core (`forge.gating`)
> **Owners:** `forge.gating` (pure, no I/O), `forge.adapters.graphiti` (persistence to `forge_pipeline_history`), `forge.adapters.sqlite` (mirror in `stage_log`)
> **Related ADRs:** [ADR-ARCH-007](../../architecture/decisions/ADR-ARCH-007-build-plan-as-gated-artefact.md), [ADR-ARCH-019](../../architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md), [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md), [ADR-ARCH-026](../../architecture/decisions/ADR-ARCH-026-constitutional-rules-belt-and-braces.md)

---

## 1. Entities

### `GateMode`

```python
class GateMode(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    HARD_STOP = "HARD_STOP"
    MANDATORY_HUMAN_APPROVAL = "MANDATORY_HUMAN_APPROVAL"    # Unconditional — PR review, early build plans
```

### `PriorReference`

Records which Graphiti entity informed a gate decision.

```python
class PriorReference(BaseModel):
    entity_id: str                                          # Graphiti UUID / natural key
    group_id: str                                           # forge_pipeline_history | forge_calibration_history
    summary: str                                            # Short recap of what the prior says
    relevance_score: float | None                           # Optional; reasoning model's rating
```

### `DetectionFinding`

Shape mirrors specialist-agent Coach output.

```python
class DetectionFinding(BaseModel):
    pattern: str                                            # e.g. "PHANTOM", "SCOPE_CREEP", "UNGROUNDED"
    severity: Literal["low", "medium", "high", "critical"]
    evidence: str                                           # Human-readable excerpt or file reference
    criterion: str | None = None                            # Optional link to criterion breakdown
```

### `GateDecision`

The output of `forge.gating.evaluate_gate()`. Captured in `stage_log.details_json["gate"]` **and** written to Graphiti as a standalone entity.

```python
class GateDecision(BaseModel):
    build_id: str
    stage_label: str
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str

    mode: GateMode
    rationale: str                                          # Reasoning-model's explanation

    coach_score: float | None                               # None in degraded mode
    criterion_breakdown: dict[str, float] = {}
    detection_findings: list[DetectionFinding] = []

    evidence: list[PriorReference] = []                     # What priors informed it
    threshold_applied: float | None = None                  # Only when a threshold was used

    auto_approve_override: bool = False                     # True if ADR-ARCH-026 belt+braces forced MANDATORY
    degraded_mode: bool = False                             # True when no Coach score available

    decided_at: datetime
```

### `CalibrationEvent`

Parsed turn from Rich's history files. Stored in `forge_calibration_history`.

```python
class CalibrationEvent(BaseModel):
    source_file: str                                        # e.g. command_history.md
    command: str                                            # /feature-spec, /feature-plan, …
    stage: str                                              # GROUP_A_CURATION | ASSUMPTION_RESOLUTION | …

    question: str                                           # Prompt shown to Rich
    default_proposed: str                                   # What the system suggested
    response_raw: str                                       # Rich's literal reply
    response_normalised: ResponseKind                       # See §2

    accepted_default: bool
    custom_content: str | None

    timestamp: datetime | None                              # Parsed from history file when present
```

### `CalibrationAdjustment`

Proposed bias entity — `forge.learning` generates; Rich approves; entity lands in `forge_pipeline_history`.

```python
class CalibrationAdjustment(BaseModel):
    adjustment_id: str                                      # UUID

    target_capability: str                                  # e.g. "review_specification"
    project_scope: str | None                               # None = fleet-wide

    observed_pattern: str                                   # "6 of 10 flag-for-reviews overridden at scores 0.78-0.82"
    proposed_bias: str                                      # Human-readable adjustment

    approved_by_rich: bool = False
    approved_at: datetime | None = None
    expires_at: datetime | None = None                      # Optional time-bounded bias

    supersedes: str | None = None                           # adjustment_id of prior adjustment this replaces
```

---

## 2. `ResponseKind` enum

```python
class ResponseKind(str, Enum):
    ACCEPT_ALL = "ACCEPT_ALL"                               # "A A A A" / "accept defaults"
    ACCEPT_WITH_EDIT = "ACCEPT_WITH_EDIT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    CUSTOM = "CUSTOM"
```

Normalisation is done by `forge.adapters.history_parser` during ingestion — raw response kept verbatim in `response_raw`.

---

## 3. Gate Evaluation — Pure Reasoning (ADR-ARCH-019)

`forge.gating.evaluate_gate()` is a **pure function** (no I/O) called by tool-layer gate-checking wrappers:

```python
def evaluate_gate(
    *,
    target_kind: str,
    target_identifier: str,
    stage_label: str,
    coach_score: float | None,
    criterion_breakdown: dict[str, float],
    detection_findings: list[DetectionFinding],
    retrieved_priors: list[PriorReference],
    calibration_adjustments: list[CalibrationAdjustment],
    constitutional_rules: list[ConstitutionalRule],
) -> GateDecision:
    ...
```

**No static thresholds** (ADR-ARCH-019). The function assembles a reasoning-model prompt from inputs and parses the model's structured response into a `GateDecision`. No `forge.yaml.gate_defaults` — thresholds emerge from priors.

**Constitutional overrides** (ADR-ARCH-026 belt+braces):

1. **Prompt-layer**: the `SAFETY_CONSTITUTION` block in the system prompt asserts "PR review is ALWAYS human".
2. **Executor-layer**: `evaluate_gate()` has a hard-coded first check:

```python
if target_identifier in {"review_pr", "create_pr_after_review"}:
    return GateDecision(mode=GateMode.MANDATORY_HUMAN_APPROVAL, auto_approve_override=True, ...)
```

Both must be independently wired. Loss of either is a constitutional regression.

---

## 4. Relationships

```
Build (1) ─── (0..N) GateDecision                          # One per gated stage
StageLogEntry (0..1) ─── (1) GateDecision                  # 1:1 for gated stages; NULL for non-gated
GateDecision (1) ─── (many) PriorReference                 # Evidence
GateDecision (1) ─── (many) DetectionFinding
CalibrationEvent (many) ─── (informs) GateDecision         # Indirect — via retrieved priors
CalibrationAdjustment (many) ─── (informs) GateDecision
CalibrationAdjustment (0..1) ─── (supersedes) CalibrationAdjustment   # Evolving biases
```

---

## 5. Storage

| Entity | Primary store | Mirror / derived |
|---|---|---|
| `GateDecision` | Graphiti `forge_pipeline_history` | Summary embedded in `stage_log.details_json["gate"]` |
| `CalibrationEvent` | Graphiti `forge_calibration_history` | Source file on disk (`command_history.md` etc.) |
| `CalibrationAdjustment` | Graphiti `forge_pipeline_history` | None — Graphiti is authoritative |
| `DetectionFinding` | Embedded inside `GateDecision` | Not stored separately |
| `PriorReference` | Embedded inside `GateDecision` | Not stored separately; `entity_id` refers to the source entity |

---

## 6. Invariants

| Invariant | Enforcement |
|---|---|
| `mode == MANDATORY_HUMAN_APPROVAL` ⇒ `auto_approve_override` is `True` OR `threshold_applied` is NULL | Pydantic validator |
| `coach_score is None` ⇒ `mode in {FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL}` | `forge.gating.evaluate_gate()` post-condition check — degraded mode cannot auto-approve |
| `criterion_breakdown` values in `[0.0, 1.0]` | Pydantic validator |
| `PriorReference.group_id in {forge_pipeline_history, forge_calibration_history}` | Literal type |
| `CalibrationAdjustment.approved_by_rich is False` ⇒ adjustment is not retrieved by `evaluate_gate()` | `forge.adapters.graphiti.read_adjustments()` filters on approval |
| `CalibrationAdjustment.supersedes` points to an existing adjustment_id | `forge.learning.propose_adjustment()` pre-write |

---

## 7. Related

- Approval wire format: [API-nats-approval-protocol.md](../contracts/API-nats-approval-protocol.md)
- Calibration ingestion: [DM-calibration.md](DM-calibration.md) (overlapping; distinct concerns of parsing + learning)
- Graphiti entity schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
- Tool layer: [API-tool-layer.md §5](../contracts/API-tool-layer.md#5-graphiti)
Write DM-calibration.md
188 lines
# Data Model — Calibration (history ingestion + override learning)

> **Container:** Domain Core (`forge.calibration`, `forge.learning`) + adapter (`forge.adapters.history_parser`)
> **Owners:** `forge.adapters.history_parser` (tokenise markdown → stream), `forge.calibration` (pure normalisation), `forge.learning` (pattern detection), `forge.adapters.graphiti` (persist to `forge_calibration_history` + `forge_pipeline_history`)
> **Related ADRs:** [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-graphiti-fed-learning-loop.md), [ADR-ARCH-006](../../architecture/decisions/ADR-ARCH-006-calibration-corpus.md), [ADR-ARCH-018](../../architecture/decisions/ADR-ARCH-018-calibration-priors-retrievable.md), [ADR-ARCH-019](../../architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md), [ADR-ARCH-008](../../architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md)

---

## 1. Purpose

The calibration model is the data substrate of Forge's **learning loop**. It has two paths:

1. **Ingestion path** — Rich's history files (`command_history.md`, `feature-spec-*-history.md`, Forge's own history files per ADR-ARCH-008) are parsed into `CalibrationEvent` entities and seeded into `forge_calibration_history`.
2. **Learning path** — `forge.learning` watches override patterns on `GateDecision` outputs and proposes `CalibrationAdjustment` entities. Rich approves via CLI; approved adjustments land in `forge_pipeline_history` and are retrieved as priors on future builds.

`CalibrationEvent` and `CalibrationAdjustment` are already defined in [DM-gating.md](DM-gating.md). This model adds the ingestion + learning-specific entities.

---

## 2. Entities

### `HistoryFileSnapshot`

Bookkeeping for incremental ingestion.

```python
class HistoryFileSnapshot(BaseModel):
    source_path: Path                                       # Absolute path on disk
    file_sha: str                                           # git-style content hash; change triggers re-parse
    last_parsed_at: datetime
    events_ingested: int                                    # Count at last parse
    partial_ingestion: bool                                 # True if parser hit an incomplete section
```

Stored in SQLite `history_snapshots` table (one row per source file).

```sql
CREATE TABLE IF NOT EXISTS history_snapshots (
    source_path TEXT PRIMARY KEY,
    file_sha TEXT NOT NULL,
    last_parsed_at TEXT NOT NULL,
    events_ingested INTEGER NOT NULL DEFAULT 0,
    partial_ingestion INTEGER NOT NULL DEFAULT 0
) STRICT;
```

### `OverridePatternObservation`

Transient — produced by `forge.learning`, not durable on its own; used to decide whether to emit a `CalibrationAdjustment` proposal.

```python
class OverridePatternObservation(BaseModel):
    target_capability: str                                  # e.g. "review_architecture"
    window_builds: int                                      # e.g. last 10 gated events
    observed_overrides: int                                 # Count of Rich-approved FLAG_FOR_REVIEW decisions in window
    score_range: tuple[float, float]                        # (min, max) coach_score observed in the window
    detected_at: datetime

    recommended_action: Literal["raise_threshold", "lower_threshold", "relax_criterion", "tighten_criterion"]
    proposed_adjustment: str | None                         # Draft text — becomes CalibrationAdjustment.proposed_bias if Rich approves
```

### `CalibrationIngestionResult`

Return value from a batch or incremental parse.

```python
class CalibrationIngestionResult(BaseModel):
    source_path: Path
    events_parsed: int
    events_written: int                                     # To Graphiti
    events_skipped_existing: int                            # Deduped
    duration_secs: float
    errors: list[str]
```

---

## 3. Ingestion Pipeline

```
Rich's history file
        │
        ▼
forge.adapters.history_parser.tokenise()                    # Pure regex + structural parsing
        │
        ▼  stream of CalibrationEvent (pre-normalised — response_raw intact)
        │
forge.calibration.normalise()                               # Pure: response_raw → response_normalised + accepted_default
        │
        ▼
forge.adapters.graphiti.add_calibration_events()            # Bulk add to forge_calibration_history
        │
        ▼
update HistoryFileSnapshot in SQLite
```

**Parser robustness.** History files are markdown; parser is tolerant of:

- Missing trailing sections.
- Mixed response shorthand (`"A A A A"`, `"accept all"`, `"edit Q2 → foo"`).
- Non-ASCII characters.
- Out-of-order question/answer pairs.

Unparseable sections raise a structured error and the file is marked `partial_ingestion=True`; already-parsed events are kept.

**Incremental ingestion.** On every Forge boot and after each completed build, `forge.calibration.refresh()`:

1. Scans the history-file allowlist (`forge.yaml.calibration.sources`).
2. For each file, computes current sha; if unchanged vs `HistoryFileSnapshot.file_sha`, skips.
3. Otherwise re-parses and dedupes against Graphiti by `(source_file, command, stage, question)` composite key.

---

## 4. Learning Pipeline

```
Terminal state transition / gate event
        │
        ▼
forge.learning.on_gate_recorded(gate_decision, responder_decision?)
        │
        ├─► update in-memory rolling window (recent GateDecisions per capability)
        │
        ▼
forge.learning.detect_patterns()                            # Pure — runs after each N events
        │
        ▼  list[OverridePatternObservation]
        │
forge.learning.propose_adjustments()
        │
        ▼  For each observation, build CalibrationAdjustment(approved_by_rich=False)
        │
forge.adapters.graphiti.write_calibration_adjustment()      # Stored pending
        │
        ▼
Forge emits ApprovalRequestPayload to Rich
        │
        ▼
Rich approves/rejects via CLI approval round-trip
        │
        ▼
forge.adapters.graphiti.mark_approved()                     # Sets approved_by_rich=True + approved_at
```

**Pattern detection heuristics** (initial set — refine via priors over time):

| Heuristic | Trigger |
|---|---|
| `raise_threshold` | Rich approved ≥ N of last M flag-for-reviews on a single capability |
| `lower_threshold` | Rich rejected ≥ N of last M auto-approves on a single capability |
| `relax_criterion` | Criterion X scored low on K flagged-then-approved stages |
| `tighten_criterion` | Detection pattern Y fired on K auto-approved-then-reverted stages |

Parameters `(N, M, K)` live in `forge.yaml.learning.*` (learning-meta-config only, not behavioural config — permitted by ADR-ARCH-019 because this governs *when to ask*, not *how to decide*).

---

## 5. Retrieval — Priors at Build Start

At each new build's start, `forge.prompts.build_system_prompt()`:

1. Queries `forge_calibration_history` for events whose `command` + `stage` match the build's expected pipeline steps (top-K by recency + similarity).
2. Queries `forge_pipeline_history` for approved `CalibrationAdjustment` entities whose `target_capability` matches any capability in the current fleet snapshot.
3. Injects both into the system prompt's `{calibration_priors}` placeholder — see [`forge.prompts`](../contracts/API-tool-layer.md#1-purpose) template structure (ADR-ARCH-018).

Reasoning model reads priors prose-style; no structured threshold lookup.

---

## 6. Invariants

| Invariant | Enforcement |
|---|---|
| `CalibrationEvent` is immutable once written | Graphiti entity-level — no update path; supersession via new event |
| `CalibrationAdjustment.approved_by_rich=False` entries are excluded from retrieval | `forge.adapters.graphiti.read_adjustments()` filters at read time |
| Supersession chain (`CalibrationAdjustment.supersedes`) is acyclic | `forge.learning.propose_adjustments()` pre-write — walk chain to detect cycles |
| `HistoryFileSnapshot.file_sha` matches on-disk sha before ingestion is skipped | `forge.calibration.refresh()` pre-check |
| Patterns proposing `raise_threshold` only fire when override count ≥ `min_evidence_count` (≥ 5) | `forge.learning.detect_patterns()` guard — prevents proposals from 1–2 overrides |

---

## 7. Related

- Gating entities (`CalibrationEvent`, `CalibrationAdjustment`): [DM-gating.md](DM-gating.md)
- Storage schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
- Tool layer: [API-tool-layer.md §5](../contracts/API-tool-layer.md#5-graphiti)
Write DM-discovery.md
189 lines
# Data Model — Discovery (capability resolution)

> **Container:** Domain Core (`forge.discovery`) + NATS Adapter (`forge.adapters.nats.fleet_watcher`)
> **Owners:** `forge.discovery` (cache + resolution logic, pure domain), `forge.adapters.nats` (KV + fleet subscription)
> **Related ADRs:** [ADR-ARCH-015](../../architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md), [ADR-ARCH-016](../../architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md), [ADR-ARCH-017](../../architecture/decisions/ADR-ARCH-017-live-fleet-watching.md)

---

## 1. Purpose

Discovery is the live capability layer. It keeps a 30-second TTL cache of the fleet's `AgentManifest`s (read from NATS KV `agent-registry`), invalidated by live `fleet.*` events, and exposes resolution to the reasoning-model-facing `dispatch_by_capability` tool.

Every resolution produces a `CapabilityResolution` entity that lands in `forge_pipeline_history` — over time this becomes a prior: *"when two agents advertised the same capability, prefer the one that passed last time"*.

---

## 2. Entities

### `AgentManifest` (imported from `nats-core`)

Full schema lives in [agent-manifest-contract.md](../../../../nats-core/docs/design/contracts/agent-manifest-contract.md). Forge's discovery layer reads:

- `agent_id` — identifier used in `agents.command.{agent_id}` dispatch.
- `tools: list[ToolCapability]` — precise name-level match.
- `intents: list[IntentCapability]` — pattern + confidence for fallback match.
- `trust_tier: core | specialist | extension` — tie-break priority.
- `status: ready | starting | degraded` — degraded excluded from primary resolution.
- `max_concurrent` + latest heartbeat's `queue_depth` + `active_tasks` — capacity signal.

### `CapabilityResolution`

Output of `forge.discovery.resolve()`. One per dispatch attempt.

```python
class CapabilityResolution(BaseModel):
    resolution_id: str                                      # UUID
    build_id: str
    stage_label: str

    requested_tool: str
    requested_intent: str | None

    matched_agent_id: str | None                            # None → degraded mode
    match_source: Literal["tool_exact", "intent_pattern", "unresolved"]
    competing_agents: list[str]                             # Other agents that also matched

    chosen_trust_tier: Literal["core", "specialist", "extension"] | None
    chosen_confidence: float | None                         # IntentCapability.confidence when match_source=intent_pattern
    chosen_queue_depth: int | None                          # From heartbeat at resolution time

    resolved_at: datetime
    outcome_correlated: bool = False                        # True once the downstream ResultPayload is linked back
```

### `DiscoveryCacheEntry`

In-memory only; never persisted.

```python
class DiscoveryCacheEntry(BaseModel):
    manifest: AgentManifest
    last_heartbeat_at: datetime
    last_heartbeat_status: Literal["ready", "busy", "degraded", "draining"]
    last_queue_depth: int
    last_active_tasks: int
    cached_at: datetime                                     # For TTL check
```

The cache is a `dict[str, DiscoveryCacheEntry]` keyed by `agent_id` and guarded by an asyncio lock for concurrent mutation from the fleet watcher callback.

---

## 3. Resolution Algorithm

```python
async def resolve(
    tool_name: str,
    intent_pattern: str | None = None,
    min_confidence: float = 0.7,
) -> tuple[str | None, CapabilityResolution]:
    snapshot = await ensure_cache_fresh()                   # re-read KV if cache_age > 30s

    # 1. Exact tool-name match
    candidates = [
        e for e in snapshot.values()
        if e.last_heartbeat_status != "degraded"
        and any(t.name == tool_name for t in e.manifest.tools)
    ]
    match_source = "tool_exact"

    # 2. Intent fallback
    if not candidates and intent_pattern:
        candidates = [
            e for e in snapshot.values()
            if e.last_heartbeat_status != "degraded"
            and any(
                _pattern_matches(i.pattern, intent_pattern) and i.confidence >= min_confidence
                for i in e.manifest.intents
            )
        ]
        match_source = "intent_pattern"

    # 3. Unresolved
    if not candidates:
        return None, CapabilityResolution(
            ..., matched_agent_id=None, match_source="unresolved",
        )

    # 4. Tie-break: trust_tier (core > specialist > extension), then confidence, then queue_depth
    candidates.sort(
        key=lambda e: (
            _trust_tier_rank(e.manifest.trust_tier),         # lower = higher priority
            -_best_confidence(e.manifest, tool_name, intent_pattern),
            e.last_queue_depth,
        )
    )
    chosen = candidates[0]

    return chosen.manifest.agent_id, CapabilityResolution(
        ...,
        matched_agent_id=chosen.manifest.agent_id,
        match_source=match_source,
        competing_agents=[c.manifest.agent_id for c in candidates[1:]],
        chosen_trust_tier=chosen.manifest.trust_tier,
        chosen_confidence=_best_confidence(chosen.manifest, tool_name, intent_pattern),
        chosen_queue_depth=chosen.last_queue_depth,
        resolved_at=datetime.now(UTC),
    )
```

**Trust-tier ranking:** `core=0, specialist=1, extension=2`. Core beats specialist beats extension.

---

## 4. Cache Invalidation

Registered via `nats_client.watch_fleet(callback=_on_fleet_event)`:

| Event | Cache action |
|---|---|
| `fleet.register` (new or version-bumped manifest) | Upsert entry: `manifest`, `last_heartbeat_status="ready"`, `cached_at=now` |
| `fleet.deregister` | Delete entry |
| `fleet.heartbeat.{agent_id}` with status change | Update `last_heartbeat_status`, `last_queue_depth`, `last_active_tasks`, `last_heartbeat_at` |
| `fleet.heartbeat.{agent_id}` routine | Update `last_heartbeat_at` only; TTL timer for staleness starts from here |
| TTL expiry (30s since `cached_at`, no heartbeat in last 90s) | Mark entry `last_heartbeat_status="degraded"`; next `ensure_cache_fresh()` re-reads KV |

---

## 5. Write-back Correlation

Once the downstream `ResultPayload` returns, `forge.discovery.correlate_outcome(resolution_id, result)`:

- Writes a Graphiti relationship: `(CapabilityResolution) -[HAD_OUTCOME]-> (GateDecision or StageLogEntry)`.
- Updates `outcome_correlated=True`.
- If the outcome was a Rich override on a flagged gate, Graphiti also records `(CapabilityResolution) -[OVERRIDDEN_BY_RICH]-> (OverrideEvent)` — the raw input for `forge.learning`.

---

## 6. Relationships

```
Build (1) ─── (many) CapabilityResolution                   # One per fleet-dispatch stage
CapabilityResolution (1) ─── (1) AgentManifest              # Snapshot reference — matched_agent_id + manifest version
CapabilityResolution (1) ─── (0..1) GateDecision            # Linked after outcome correlation
CapabilityResolution (1) ─── (0..1) StageLogEntry           # Direct link via stage_label + build_id
DiscoveryCacheEntry (1) ─── (1) AgentManifest               # In-memory only
```

---

## 7. Invariants

| Invariant | Enforcement |
|---|---|
| `matched_agent_id is None` iff `match_source == "unresolved"` | Pydantic validator |
| Agents with `status="degraded"` excluded from primary resolution | `resolve()` filter |
| Cache age ≤ 30s OR stale-heartbeat > 90s (per ADR-ARCH-017) | `ensure_cache_fresh()` guard |
| `competing_agents` list excludes the chosen agent | `resolve()` slicing |
| `CapabilityResolution` persisted before downstream dispatch is published | `dispatch_by_capability` ordering — write-before-send |
| `outcome_correlated` cannot regress from True to False | Graphiti append-only — never update in place; new entity supersedes if needed |

---

## 8. Related

- Fleet lifecycle: [API-nats-fleet-lifecycle.md](../contracts/API-nats-fleet-lifecycle.md)
- Dispatch contract: [API-nats-agent-dispatch.md](../contracts/API-nats-agent-dispatch.md)
- Graphiti entity schemas: [DM-graphiti-entities.md](DM-graphiti-entities.md)
Write DM-graphiti-entities.md
250 lines
# Data Model — Graphiti Entities

> **Container:** Graphiti Adapter (`forge.adapters.graphiti`)
> **Owners:** `forge.adapters.graphiti` (reads/writes), `forge.adapters.history_parser` (ingestion entry point)
> **Storage:** FalkorDB via Graphiti at `whitestocks:6379` (Tailscale)
> **Related ADRs:** [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-graphiti-fed-learning-loop.md), [ADR-ARCH-006](../../architecture/decisions/ADR-ARCH-006-calibration-corpus.md), [ADR-ARCH-018](../../architecture/decisions/ADR-ARCH-018-calibration-priors-retrievable.md), [ADR-ARCH-022](../../architecture/decisions/ADR-ARCH-022-dual-agent-memory.md)

---

## 1. Purpose

Graphiti stores Forge's long-term memory — outcomes, overrides, and ingested calibration history. Two groups (namespaces):

- `forge_pipeline_history` — everything Forge produces at runtime (gate decisions, resolutions, overrides, calibration adjustments, session outcomes).
- `forge_calibration_history` — everything ingested from Rich's Q&A history files (calibration events).

See [DDR-004-graphiti-group-partitioning.md](../decisions/DDR-004-graphiti-group-partitioning.md) for the group-boundary rationale.

LangGraph Memory Store is a **separate** concern — per-thread recall within a running build (ADR-ARCH-022). Graphiti is cross-build, cross-session.

---

## 2. Entity Types (`forge_pipeline_history`)

### `GateDecisionEntity`

Graphiti representation of `GateDecision` (from [DM-gating.md](DM-gating.md)). Stored as a node; evidence priors become edges.

```
Node: GateDecision
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    target_kind:          str
    target_identifier:    str
    mode:                 str (GateMode value)
    rationale:            str
    coach_score:          float | null
    criterion_breakdown:  json (dict[str, float])
    detection_findings:   json (list[DetectionFinding])
    threshold_applied:    float | null
    degraded_mode:        bool
    decided_at:           datetime (ISO 8601 UTC)

Edges out:
  (GateDecision) -[INFORMED_BY]-> (CalibrationEvent)
  (GateDecision) -[INFORMED_BY]-> (CalibrationAdjustment)
  (GateDecision) -[RESULT_OF]-> (CapabilityResolution)
  (GateDecision) -[OVERRIDDEN_BY]-> (OverrideEvent)           # when Rich overrides
```

### `CapabilityResolutionEntity`

Graphiti representation of `CapabilityResolution` (from [DM-discovery.md](DM-discovery.md)).

```
Node: CapabilityResolution
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    requested_tool:       str
    requested_intent:     str | null
    matched_agent_id:     str | null
    match_source:         str (tool_exact | intent_pattern | unresolved)
    competing_agents:     json (list[str])
    chosen_trust_tier:    str | null
    chosen_confidence:    float | null
    chosen_queue_depth:   int | null
    resolved_at:          datetime

Edges out:
  (CapabilityResolution) -[MATCHED]-> (AgentManifestSnapshot)
  (CapabilityResolution) -[HAD_OUTCOME]-> (GateDecision | StageLogEntry)
```

### `CalibrationAdjustmentEntity`

```
Node: CalibrationAdjustment
  properties:
    entity_id:            str (UUID) — same as CalibrationAdjustment.adjustment_id
    target_capability:    str
    project_scope:        str | null
    observed_pattern:     str
    proposed_bias:        str
    approved_by_rich:     bool
    approved_at:          datetime | null
    expires_at:           datetime | null

Edges out:
  (CalibrationAdjustment) -[SUPERSEDES]-> (CalibrationAdjustment)      # When rev'd
  (CalibrationAdjustment) -[PROPOSED_FROM]-> (OverridePattern)         # Optional — which pattern triggered it
```

### `OverrideEvent`

Raw event produced every time Rich's decision differed from Forge's gate. Input to `forge.learning`.

```
Node: OverrideEvent
  properties:
    entity_id:            str (UUID)
    build_id:             str
    stage_label:          str
    gate_mode_before:     str (GateMode)
    decision:             str (approve | reject | defer | override)
    rich_reason:          str | null
    coach_score_at_gate:  float | null
    recorded_at:          datetime

Edges out:
  (OverrideEvent) -[OF_DECISION]-> (GateDecision)
  (OverrideEvent) -[BY_RESPONDER]-> (Actor)                  # "rich", jarvis-adapter-id
```

### `SessionOutcomeEntity`

High-level per-build summary node. Linked to every `GateDecision` + `CapabilityResolution` produced during that build.

```
Node: SessionOutcome
  properties:
    entity_id:            str = build_id
    feature_id:           str
    repo:                 str
    project:              str | null
    outcome:              str (COMPLETE | FAILED | CANCELLED | SKIPPED)
    duration_secs:        float
    tasks_completed:      int
    tasks_failed:         int
    pr_url:               str | null
    error:                str | null
    correlation_id:       str
    completed_at:         datetime

Edges out:
  (SessionOutcome) -[CONTAINS]-> (GateDecision)
  (SessionOutcome) -[CONTAINS]-> (CapabilityResolution)
  (SessionOutcome) -[FOR_FEATURE]-> (FeatureRef)
```

---

## 3. Entity Types (`forge_calibration_history`)

### `CalibrationEventEntity`

Graphiti representation of `CalibrationEvent` (from [DM-gating.md §1](DM-gating.md#1-entities) + ingestion described in [DM-calibration.md](DM-calibration.md)).

```
Node: CalibrationEvent
  properties:
    entity_id:            str = sha(source_file + command + stage + question)   # Deterministic — dedupe key
    source_file:          str
    command:              str
    stage:                str
    question:             str
    default_proposed:     str
    response_raw:         str
    response_normalised:  str (ResponseKind value)
    accepted_default:     bool
    custom_content:       str | null
    timestamp:            datetime | null                                       # Parsed from file when available
    ingested_at:          datetime

Edges out:
  (CalibrationEvent) -[FOR_COMMAND]-> (CommandRef)
  (CalibrationEvent) -[AT_STAGE]-> (StageRef)
```

`CommandRef` and `StageRef` are thin reference nodes (just a `name` property), deduplicated, used to accelerate "all events for command=X" retrieval.

---

## 4. Retrieval Patterns

### At build start (`forge.prompts.build_system_prompt`)

| Purpose | Query |
|---|---|
| Similar past builds | `forge_pipeline_history` — `SessionOutcome` nodes matching `feature_id` prefix or `project`; top-K by recency |
| Override history per capability | `forge_pipeline_history` — `OverrideEvent` WHERE `stage_label ≈ X OR target_identifier = Y`; last 20 |
| Approved calibration adjustments | `forge_pipeline_history` — `CalibrationAdjustment` WHERE `approved_by_rich=True` AND (`project_scope IS NULL OR project_scope = <build.project>`) AND (`expires_at IS NULL OR expires_at > NOW()`) |
| Relevant Q&A priors | `forge_calibration_history` — top-K semantic match on question text against current stage's expected prompt |

All queries use Graphiti's native search plus FalkorDB Cypher where needed. Results are injected prose-style into the system prompt (ADR-ARCH-018).

### During a gate evaluation

| Purpose | Query |
|---|---|
| Rich's recent behaviour | `OverrideEvent` on same `target_identifier` in last 30 days, with summary stats (override rate) |
| Adjustments targeting this capability | `CalibrationAdjustment` WHERE `target_capability = X AND approved_by_rich=True` |

### After build completion

`forge.adapters.graphiti.write_session_outcome()` creates the `SessionOutcome` node and links all produced `GateDecision`s, `CapabilityResolution`s, and override events. This is the pattern-mining substrate for future builds.

---

## 5. Write Ordering

Per-build chronological order:

1. On `PREPARING → RUNNING`: no Graphiti writes yet (stage work hasn't happened).
2. Per stage:
   - `CapabilityResolution` written **before** dispatch (see DM-discovery invariant — write-before-send).
   - `GateDecision` written **after** result comes back, before `StageLogEntry` is committed to SQLite (so both stores are consistent).
   - `OverrideEvent` written if Rich's decision diverged from Forge's gate.
3. On terminal state transition: `SessionOutcome` written, edges linked.

Partial failures are tolerated — a write to Graphiti that fails triggers a structured log entry and the build continues (Graphiti is enrichment, not a hard dependency). On next build, `forge.adapters.graphiti.reconcile()` scans SQLite `stage_log` for entries lacking Graphiti counterparts and backfills.

---

## 6. Embedding + Indexing

Embeddings are produced by the Graphiti service using the embedding provider configured in `.guardkit/graphiti.yaml` (currently `nomic-embed-text-v1.5` via vLLM on GB10). Forge does not embed directly — it writes text; Graphiti indexes.

Each entity's searchable text is composed from:

- `GateDecision.rationale` + stringified `criterion_breakdown` + `detection_findings`.
- `CapabilityResolution.requested_tool` + `requested_intent` + chosen `agent_id`.
- `CalibrationEvent.question` + `default_proposed` + `response_raw`.
- `CalibrationAdjustment.observed_pattern` + `proposed_bias`.
- `SessionOutcome.error` (when failed) + `pr_url` (for linking).

---

## 7. Invariants

| Invariant | Enforcement |
|---|---|
| `CalibrationEvent.entity_id` is deterministic — duplicate re-ingestions are no-ops | sha key computed in `forge.adapters.history_parser` |
| Graphiti writes happen after the authoritative SQLite commit (for gate + stage entities) | `forge.adapters.sqlite.record_stage()` returns before `forge.adapters.graphiti.write_gate_decision()` is called |
| `SessionOutcome.outcome` is terminal (no IN_PROGRESS entity ever exists) | Only written on terminal transition |
| `CalibrationAdjustment.approved_by_rich=False` entries are filtered out at retrieval time | `forge.adapters.graphiti.read_adjustments()` WHERE clause |
| Expired `CalibrationAdjustment` entities are ignored on retrieval, not deleted | `expires_at > NOW()` filter; history preserved for audit |

---

## 8. Related

- Ingestion pipeline: [DM-calibration.md](DM-calibration.md)
- Gate entities: [DM-gating.md](DM-gating.md)
- Discovery entities: [DM-discovery.md](DM-discovery.md)
- DDR: [DDR-004-graphiti-group-partitioning.md](../decisions/DDR-004-graphiti-group-partitioning.md)
Models done. Running contradiction detection against the ADRs before writing DDRs.

Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files)

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Offer Graphiti seeding commands
Contradiction check against 31 ADRs completed. Findings:


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 CONTRADICTION DETECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ No contradictions detected with 31 existing ADRs.

⚠️  Two soft flags (design calls, not ADR conflicts):

1. New nats-core payload additions exceed the refresh doc scope
   - Refresh doc §"Pipeline Event Publishing" introduced 2 new:
     StageCompletePayload, BuildPausedPayload
   - My API-nats-pipeline-events adds 2 more:
     BuildResumedPayload, BuildCancelledPayload
   - Alternatives:
     • BuildResumed → reuse StageCompletePayload with gate_mode=None
     • BuildCancelled → reuse BuildFailedPayload(failure_reason="cancelled", recoverable=False)
   Recommend adding all 4 for clean downstream filtering; will note in DDR-001.

2. One typo in API-nats-pipeline-events §3.2: "three new" should read "four new".
   Fixing inline.
Fixing the typo then proceeding to DDRs.

Edit API-nats-pipeline-events.md
Modified
Writing 6 DDRs now.

Write DDR-001-reply-subject-correlation.md
57 lines
# DDR-001 — Reply-subject correlation for agents.command.* dispatch

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-015, ADR-ARCH-003, `specialist-agent` LES1 §2 parity rule

---

## Context

Forge dispatches commands to fleet specialists via `agents.command.{agent_id}` and expects a result back. Two candidate reply conventions:

- **A: Shared reply subject** — all specialists publish on `agents.result.{agent_id}` (one subject per agent). Caller filters by `request_id` in the envelope.
- **B: Per-correlation reply subject** — specialists publish on `agents.result.{agent_id}.{request_id}`. Caller subscribes to the exact correlation-keyed subject before publishing.

Convention A is simpler (fewer subjects), but it creates an observed failure mode: the JetStream `AGENTS` stream intercepts `agents.>` for audit and returns `PubAck` within ~3ms. Operators / simple callers treat PubAck as the reply and exit before the real message arrives. This silently broke the round-trip contract in specialist-agent iterations (LES1 §2, walkthrough §retest-smoke).

Convention B eliminates the ambiguity — the caller subscribes to a one-shot subject keyed by its own `request_id`, so there is no generic subject that JetStream's audit intercept can pre-empt.

Related design concern: `nats-core` already introduced four new pipeline payload types in Forge's design (`StageCompletePayload`, `BuildPausedPayload`, `BuildResumedPayload`, `BuildCancelledPayload`). Two are from the refresh doc; two are additive. They need to land in `nats-core ≥ 0.2.0` via `TASK-NCFA-002` before Forge can stop carrying them locally.

## Decision

**Adopt Convention B.** Reply subjects are `agents.result.{agent_id}.{request_id}`. Forge's `forge.adapters.nats.request_reply_dispatch` subscribes to the exact subject *before* publishing the command and unsubscribes after the first message or timeout.

**PubAck is never treated as success.** The dispatch is complete only when a payload arrives on the correlation-keyed subject, or the local timeout fires.

**Payload additions carried locally until nats-core ships them.** `forge.adapters.nats._interim_payloads.py` defines `StageCompletePayload`, `BuildPausedPayload`, `BuildResumedPayload`, `BuildCancelledPayload` with a TODO pointing to `TASK-NCFA-002`. Drop the interim module when `nats-core ≥ 0.2.0` releases.

## Rationale

- **Eliminates the observed silent-break mode** — per-correlation subjects are invisible to the `AGENTS` audit stream's blanket intercept.
- **Composes with existing nats-core patterns** — `nats-core.NATSClient.call_agent_tool()` already supports the pattern per the refresh doc; Forge aligns rather than inventing.
- **Simplifies timeout logic** — caller subscribes to exactly one message, then unsubscribes. No fan-out filtering, no dedupe.
- **Payload additions made visible now** — catching the dependency early avoids Forge stalling behind a sibling-repo release.

## Alternatives considered

- **A: Shared `agents.result.{agent_id}`** — rejected per LES1 observation.
- **C: Embed reply-subject in envelope metadata** — reinvents NATS native `reply` field; no benefit.
- **Defer payload additions** — rejected because Forge needs to publish `StageCompletePayload` and `BuildPausedPayload` from day one; inventing a different-shape local type would create a migration burden later.

## Consequences

- **+** Round-trip contract is unambiguous and auditable.
- **+** Clean forward path: `nats-core ≥ 0.2.0` drops the interim payload file with a single module deletion.
- **−** Brief subject churn per dispatch — negligible under sequential builds (`max_ack_pending=1`).
- **−** Contract requires specialist agents to honour the reply-subject convention. Mitigated: the specialist-agent harness already reads `msg.reply` per nats-py idiom and publishes there.

## Related components

- Agent Runtime (`forge.adapters.nats`)
- Tool Layer (`dispatch_by_capability` — [API-tool-layer.md](../contracts/API-tool-layer.md))
- Pipeline events contract — [API-nats-pipeline-events.md](../contracts/API-nats-pipeline-events.md)
- Dispatch contract — [API-nats-agent-dispatch.md](../contracts/API-nats-agent-dispatch.md)
Write DDR-002-resume-value-rehydration-helper.md
94 lines
# DDR-002 — `resume_value_as` helper placement + contract

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-021 Revision 10 (2026-04-20), TASK-SPIKE-D2F7, TASK-ADR-REVISE-021-E7B3

---

## Context

ADR-ARCH-021 Rev 10 concluded (after TASK-SPIKE-D2F7) that under `langgraph dev` / server mode — Forge's canonical deployment target — the value returned by `interrupt()` is a plain `dict`, not the typed Pydantic instance the producer published. Direct-invoke mode preserves types; server mode does not.

Rev 10 mandates Option C (hybrid): every `interrupt()` call site MUST rehydrate the resume value before attribute access or `isinstance` checks. To prevent copy-paste drift, the rehydration logic lives in a single helper:

```python
def resume_value_as(model_cls, raw):
    return raw if isinstance(model_cls, model_cls) else model_cls.model_validate(raw)
```

The ADR states the helper's **expected home is `forge.adapters.langgraph`** but defers the implementation and contract to `/system-design` to avoid re-litigating the module location.

## Decision

Create module `forge/src/forge/adapters/langgraph.py`. It contains **only** the `resume_value_as` helper and any future LangGraph-server-specific adapter functions (e.g. `resume_graph(thread_id, value)` for the NATS approval subscriber).

**Contract:**

```python
def resume_value_as(
    model_cls: type[BaseModelT],
    raw: BaseModelT | dict | Mapping[str, Any],
) -> BaseModelT:
    """Rehydrate a LangGraph interrupt resume value into a typed Pydantic instance.

    Under `langgraph dev` / LangGraph server, interrupt() returns dict. Direct-invoke
    mode returns the typed Pydantic instance. This helper normalises both paths
    via an isinstance() short-circuit — the caller writes the same code regardless.

    Args:
        model_cls: The Pydantic model class to coerce into (e.g. ApprovalResponsePayload).
        raw: Either a typed instance (direct-invoke) or a dict (server mode).

    Returns:
        A typed instance of model_cls. Pydantic validation errors propagate as-is.
    """
    if isinstance(raw, model_cls):
        return raw
    return model_cls.model_validate(raw)
```

**Usage contract at call sites:**

```python
from forge.adapters.langgraph import resume_value_as
from nats_core.events.agent import ApprovalResponsePayload

raw = interrupt({...})
response = resume_value_as(ApprovalResponsePayload, raw)
# Safe to access response.decision, response.responder, etc. from here.
```

**Test discipline** — every `interrupt()` call site has a dedicated unit test asserting the helper is invoked before attribute access. This is enforced via:

- A ruff custom rule (`forge.lint.no_raw_interrupt`) that flags `interrupt(...).<attribute>` and `isinstance(interrupt(...), ...)` chains without an intervening `resume_value_as` call.
- pytest integration tests in `tests/adapters/test_langgraph.py` covering the three cases: typed passthrough, dict → model, invalid dict → ValidationError.

## Rationale

- **Single placement** — `forge.adapters.langgraph` is the natural home for LangGraph-specific adapter code. Co-locating with the NATS resume subscriber keeps the serde boundary in one module.
- **Single entry point** — all call sites import the same helper; no drift across revisions.
- **Forward-compatible** — if the deferred Option B spike (ADR-021 Rev 10 §"Deferred follow-up") lands and resume values arrive typed, the `isinstance` short-circuit makes the helper a no-op. No call-site churn; the helper can stay defensively or be deleted.
- **Test-enforceable** — the ruff custom rule + unit tests make the serde obligation mechanical rather than reliant on reviewer memory.

## Alternatives considered

- **Put the helper in `forge.state_machine`** — rejected; state machine is pure domain, shouldn't carry LangGraph-specific runtime concerns.
- **Put it in `forge.adapters.nats`** — rejected; the serde issue is LangGraph's, not NATS's.
- **Call `model_validate` directly at each site** — rejected by ADR-021 Rev 10 (drift risk).
- **Ruff rule only, no helper** — rejected; the rule is easier to write against a canonical helper-name.

## Consequences

- **+** One-line idiom at every `interrupt()` site; serde obligation mechanical rather than documentary.
- **+** Option B spike (if it succeeds) cleanly demotes the helper without call-site churn.
- **−** `forge.adapters.langgraph` starts as a single-function module — light cost, clear home.
- **−** New linter rule requires test + rollout — manageable; one-time expense.

## Related components

- Agent Runtime (every `interrupt()` caller)
- NATS Adapter (`approval_subscriber` publishes the resume value via the graph's resume API)
- API contract — [API-nats-approval-protocol.md §4.2](../contracts/API-nats-approval-protocol.md#42-rehydration-contract)
Write DDR-003-sqlite-schema-layout-wal.md
63 lines
# DDR-003 — SQLite schema layout + WAL + STRICT tables

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-009 (omit LangGraph checkpointer), ADR-ARCH-013 (CLI read bypasses NATS), ADR-SP-013

---

## Context

Forge uses SQLite as the authoritative build-history store. Concurrency is asymmetric:

- Single writer — the agent runtime — inside a single process.
- Multiple readers — every `forge status` / `forge history` invocation from the CLI, potentially concurrent with the writer.

The schema has two core tables (`builds`, `stage_log`) plus a small `history_snapshots` table for calibration ingestion bookkeeping. Options for durability + concurrency:

- **Default rollback journal + synchronous=FULL** — strongest durability, but readers block during writes.
- **WAL + synchronous=NORMAL** — readers never block; writes fsync at checkpoint boundaries; crash-safe with modern OS fsync semantics.
- **WAL + synchronous=FULL** — unnecessary cost for Forge's workload (sequential builds, ~100 stage writes/build).

SQLite 3.37+ supports `STRICT` tables that enforce typed columns; important because Forge serialises Pydantic models in and expects types on the way back out.

## Decision

- **`PRAGMA journal_mode = WAL`** + **`PRAGMA synchronous = NORMAL`** set on every connection open.
- **`PRAGMA foreign_keys = ON`** + **`PRAGMA busy_timeout = 5000`**.
- All tables declared `STRICT`.
- Single persistent write connection held by the agent runtime, serialised by an asyncio lock. Readers open new connections in `mode=ro` on every CLI invocation.
- Schema versioned via `schema_version` table; migrations are additive and run at boot before any domain writes.

Schema DDL, write API, and read API captured in [API-sqlite-schema.md](../contracts/API-sqlite-schema.md).

## Rationale

- **WAL is industry-standard for this exact workload** — single writer, many short-lived readers. Readers see a consistent snapshot from the last commit; writes append to the WAL file without blocking readers.
- **`synchronous = NORMAL` is safe with WAL** — durability loss bound to the most recent uncommitted transaction on power loss; this is acceptable because SQLite is not the only durability layer — JetStream holds the unacked message for redelivery.
- **STRICT tables catch serialisation bugs early** — Forge writes Pydantic-validated payloads but the conversion to SQLite storage is where type drift typically appears. STRICT rejects it at write time.
- **Single persistent write connection** avoids connection-pool overhead for a process that writes on the order of 100 rows per build. The asyncio lock makes the serialisation explicit rather than relying on SQLite's busy-timeout dance.
- **Readers open short-lived `mode=ro` connections** — consistent with ADR-ARCH-013; the CLI is short-lived, no connection to manage.

## Alternatives considered

- **Default rollback journal** — rejected; blocks readers during writes, inconsistent with sub-200ms `forge status` target.
- **PostgreSQL / DuckDB** — rejected; SQLite is sufficient, requires no separate server, runs in-container with zero ops.
- **STRICT off** — rejected; the cost of silent type drift at the storage boundary outweighs the minor schema-authoring constraint.
- **Separate write connection per transaction** — rejected; connection setup is non-trivial for SQLite with WAL + pragmas; a held connection is simpler.

## Consequences

- **+** `forge status` and `forge history` remain fast and non-blocking throughout a build.
- **+** Crash safety is bounded and well-understood; reconciliation at boot uses the unacked-message path to rebuild state.
- **+** STRICT tables surface Pydantic-model drift as explicit errors.
- **−** Requires SQLite ≥ 3.37 for STRICT; the GB10 Docker base image already provides this.
- **−** WAL creates additional files (`-wal`, `-shm`) alongside `forge.db`; backup scripts include them.

## Related components

- SQLite Adapter (`forge.adapters.sqlite`)
- CLI Read path (`forge.cli`)
- Build lifecycle data model — [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
Write DDR-004-graphiti-group-partitioning.md
64 lines
# DDR-004 — Graphiti group partitioning (`forge_pipeline_history` + `forge_calibration_history`)

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-005, ADR-ARCH-006, ADR-ARCH-018, ADR-ARCH-022

---

## Context

Forge writes three kinds of durable "memory" to Graphiti:

1. **Runtime outcomes** — every `GateDecision`, `CapabilityResolution`, `OverrideEvent`, `SessionOutcome` produced during a build.
2. **Approved adjustments** — `CalibrationAdjustment` entities Rich confirmed via CLI approval round-trip.
3. **Ingested Q&A history** — `CalibrationEvent` nodes parsed from Rich's markdown history files (command_history.md, feature-spec-*-history.md, Forge's own history files per ADR-ARCH-008).

All three are retrievable as priors at build start to inform the reasoning model's gate decisions. Options for Graphiti group partitioning:

- **A: One group for everything** — `forge_history`. Simple but mixes ingestion-provenance data with runtime-provenance data; retrieval queries must discriminate.
- **B: Two groups** — `forge_pipeline_history` (runtime + adjustments) + `forge_calibration_history` (ingested Q&A only).
- **C: Three groups** — split adjustments out into `forge_calibration_adjustments`.

The existing architecture (ARCHITECTURE.md §9, ADR-ARCH-005) already names two groups — `forge_pipeline_history` and `forge_calibration_history`. This DDR formalises the boundary between them and specifies retrieval queries.

## Decision

**Adopt Option B — two groups:**

| Group | Written by | Contents | Reads |
|---|---|---|---|
| `forge_pipeline_history` | `forge.adapters.graphiti.write_gate_decision`, `write_capability_resolution`, `record_override`, `write_calibration_adjustment`, `write_session_outcome` | `GateDecisionEntity`, `CapabilityResolutionEntity`, `OverrideEvent`, `CalibrationAdjustmentEntity`, `SessionOutcomeEntity` | System-prompt priors retrieval; learning-loop pattern detection |
| `forge_calibration_history` | `forge.adapters.history_parser` via `forge.calibration.refresh` | `CalibrationEventEntity`, `CommandRef`, `StageRef` | System-prompt priors retrieval (semantic match on question/prompt) |

Each group is an independent Graphiti namespace (separate group_id). Cross-group relationships are allowed (e.g. `GateDecision -[INFORMED_BY]-> CalibrationEvent`) — Graphiti supports this natively.

**Why not Option C:** `CalibrationAdjustment` is Forge's runtime-produced output (not Rich's ingested Q&A); it belongs with other runtime entities in `forge_pipeline_history`. The "adjustments are a separate concern" intuition is handled by entity-type filtering in retrieval queries, not by group split.

## Rationale

- **Provenance clarity** — `forge_pipeline_history` is "what Forge did"; `forge_calibration_history` is "what Rich has historically done". Different write paths, different retention/audit concerns, different scales.
- **Query simplicity** — "priors from similar past builds" queries only `forge_pipeline_history`; "Q&A priors for current stage" queries only `forge_calibration_history`. No entity-type WHERE clauses needed at the group boundary.
- **Retention + backup differentiation** — if Rich ever wants to purge runtime history (e.g. for privacy/compliance) without losing ingested Q&A, that's a single-group clear rather than a filtered delete.
- **Aligns with existing architecture** — `forge.yaml.graphiti.default_group_ids` already lists these two groups per the refresh doc; the split was implicit. This DDR makes it explicit and documents the entity-to-group mapping.

## Alternatives considered

- **A: One group** — rejected for provenance clarity and retention asymmetry.
- **C: Three groups with separate adjustments group** — rejected; adjustments share write semantics with other runtime entities, and edges from `CalibrationAdjustment` → `GateDecision` cross a group boundary that adds no value.

## Consequences

- **+** Clean mental model: two data sources, two groups, explicit boundary.
- **+** Retention / purge operations are single-group and orthogonal.
- **+** Retrieval queries are simpler at the group boundary.
- **−** Cross-group edges (e.g. `GateDecision -[INFORMED_BY]-> CalibrationEvent`) require cross-namespace support from Graphiti, which it has, but must be exercised in tests.
- **−** Adding a future Graphiti group (e.g. `forge_fleet_health` for capacity telemetry) will be a separate DDR — boundary decisions tend to compound.

## Related components

- Graphiti Adapter (`forge.adapters.graphiti`)
- History Parser (`forge.adapters.history_parser`)
- Data models — [DM-graphiti-entities.md](../models/DM-graphiti-entities.md), [DM-calibration.md](../models/DM-calibration.md)
Write DDR-005-cli-context-manifest-resolution.md
95 lines
# DDR-005 — `.guardkit/context-manifest.yaml` resolution for GuardKit tool wrappers

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-004, refresh doc §"Context Manifest Convention"

---

## Context

Every GuardKit subcommand (11 of them — see ADR-ARCH-004) takes zero or more `--context <path>` flags pointing to markdown docs that seed the session. Previously these flags were assembled by hand inside Claude Desktop sessions and captured retrospectively in build plans. Forge needs to assemble them automatically when invoking `guardkit_*` tools.

The refresh doc §"Context Manifest Convention" established `.guardkit/context-manifest.yaml` at the target repo root as the discovery source:

```yaml
repo: forge
dependencies:
  nats-core:
    path: ../nats-core
    relationship: "Why this repo depends on nats-core"
    key_docs:
      - path: docs/design/specs/nats-core-system-spec.md
        category: specs
        description: "What this doc provides"
internal_docs:
  always_include:
    - docs/architecture/ARCHITECTURE.md
    - docs/design/DESIGN.md
```

Plus a filter-by-command-type rule (e.g. `/system-arch` wants architecture + decisions; `/feature-spec` wants specs + contracts + source).

Three open questions for Forge's wrapper layer:

1. **Where does the resolver live?** Inside `forge.adapters.guardkit` or as a separate library?
2. **What happens when a manifest is missing?** Fail the dispatch? Degrade silently?
3. **How are categories filtered per GuardKit command?** Hardcoded dict in Forge? Read from manifest? From GuardKit itself?

## Decision

**Placement.** The resolver lives in `forge.adapters.guardkit.context_resolver`. It's adapter-layer code (reads filesystem, composes CLI arguments) and has no domain concerns.

**Missing-manifest behaviour.** If `.guardkit/context-manifest.yaml` is absent, the resolver returns an empty context-flag list and logs a structured warning (`context_manifest_missing`). The GuardKit invocation proceeds without `--context` flags. The reasoning model sees the warning in the tool's return JSON and decides whether to retry with explicit flags or HARD_STOP.

**Category filter table.** Hardcoded in `forge.adapters.guardkit.context_resolver` — a single dict keyed by GuardKit subcommand name mapping to allowed categories:

```python
_COMMAND_CATEGORY_FILTER: dict[str, set[str]] = {
    "system-arch":    {"architecture", "decisions"},
    "system-design":  {"specs", "decisions", "contracts", "architecture"},
    "system-plan":    {"architecture", "decisions", "specs"},
    "feature-spec":   {"specs", "contracts", "source", "decisions"},
    "feature-plan":   {"specs", "decisions", "architecture"},
    "task-review":    {"contracts", "source"},
    "task-work":      {"contracts", "source"},
    "task-complete":  {"contracts", "source"},
    "autobuild":      {"contracts", "source"},
    # GuardKit graphiti subcommands don't take --context; skip resolution entirely.
}
# Always-included docs (manifest.internal_docs.always_include) prepend regardless of filter.
```

**Circular dependency guard.** The resolver detects cycles when chasing `dependencies` recursively and stops at depth 2 with a warning (`context_manifest_cycle_detected`).

**Path resolution.** All paths are resolved relative to the target repo root, then converted to absolute paths before being passed to GuardKit. Symlinks are followed; paths outside the repo's allowed-read list (`forge.yaml.permissions.filesystem.read_allowlist`) are omitted with a warning.

## Rationale

- **Adapter-layer placement** — the resolver touches the filesystem and composes shell arguments; neither is a domain concern. Co-locating with `forge.adapters.guardkit.run` keeps the call path short.
- **Missing-manifest degrades gracefully** — Forge should be able to drive repos that don't yet have a manifest; forcing one as a hard precondition would block early adoption.
- **Hardcoded filter table in Forge** — the mapping is stable and belongs with the caller; pushing it into the manifest would require every repo to restate the same rules, and pushing it into GuardKit couples GuardKit to category vocabulary it doesn't care about.
- **Depth-2 cycle guard** — realistic dependency graphs are narrow (e.g. forge → nats-core → ∅). If Rich later needs deeper, this DDR can be superseded.

## Alternatives considered

- **Fail-hard on missing manifest** — rejected; blocks early adoption.
- **Per-repo filter override in `context-manifest.yaml`** — rejected; adds configurability that will rarely be used and duplicates the stable rule across repos.
- **Ask GuardKit for category hints** — rejected; unnecessary coupling.
- **Depth-unlimited cycle traversal** — rejected; no realistic benefit, high risk of O(n²) traversal on bad manifests.

## Consequences

- **+** GuardKit invocations are deterministic from manifest + subcommand — no hand-assembly.
- **+** Repos without manifests still work; Forge emits a structured warning into the reasoning loop instead of failing.
- **+** Filter logic is local and testable.
- **−** Hardcoded filter table requires editing Forge source when a new GuardKit subcommand appears. Manageable — new subcommands come with a new `@tool` anyway (ADR-ARCH-004 pattern).
- **−** Depth-2 cycle cap may feel restrictive; easy to revisit via a follow-up DDR.

## Related components

- GuardKit Adapter (`forge.adapters.guardkit`)
- Tool Layer (`guardkit_*` tools — [API-tool-layer.md §6](../contracts/API-tool-layer.md#6-guardkit-subcommand-tools))
- Subprocess contract — [API-subprocess.md §3.3](../contracts/API-subprocess.md#33-context-manifest-resolution)
Write DDR-006-async-subagent-state-channel-contract.md
110 lines
# DDR-006 — Async subagent state-channel contract (`async_tasks`)

- **Status:** Accepted
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
DDRs done. Writing the two C4 L3 diagrams now.

Write agent-runtime.md
129 lines
# C4 Level 3 — Agent Runtime (Component Diagram)

> **Generated:** 2026-04-23 via `/system-design`
> **Container:** `Agent Runtime` (from [container.md](../../architecture/container.md))
> **Components inside:** 9 (7 modules + supervisor state + subgraph reference)
> **Status:** Awaiting Rich's approval (C4 L3 review gate)

---

## Purpose

The Agent Runtime is Forge's DeepAgents shell — the reasoning loop, the tool layer, and the two sub-agents (`build_plan_composer` sync, `autobuild_runner` async). This diagram decomposes it into its internal components and shows how they cooperate at runtime.

Why this container warrants an L3 (ADR-ARCH-031 threshold): 7+ internal modules plus the AsyncSubAgent separate-graph pattern creates enough structural complexity that a single L2 node obscures more than it reveals.

---

## Diagram

```mermaid
C4Component
    title Component diagram for Agent Runtime (Forge DeepAgents shell)

    Container_Boundary(runtime, "Agent Runtime") {
        Component(agent, "forge.agent", "Python / DeepAgents 0.5.3", "create_deep_agent(...) wiring. Exports the CompiledStateGraph as `graph`. Entry point in langgraph.json.")
        Component(prompts, "forge.prompts", "Python / string templates", "System prompt templates with {date}, {domain_prompt}, {available_capabilities}, {calibration_priors}, {project_context} placeholders. Assembled at build start.")
        Component(subagents_mod, "forge.subagents", "Python", "SubAgent + AsyncSubAgent spec factories. Two pre-declared: build_plan_composer (sync) + autobuild_runner (async).")
        Component(tools_dispatch, "dispatch_by_capability", "Python / @tool(parse_docstring)", "Single generic dispatch tool. Resolves via forge.discovery, publishes to NATS agents.command.*, waits on correlation-keyed reply subject.")
        Component(tools_approval, "approval + notification tools", "Python / @tool", "request_approval (interrupt() + NATS) and emit_notification (jarvis.notification.*).")
        Component(tools_graphiti, "graphiti_tools", "Python / @tool", "record_override, write_gate_decision, read_override_history, write_session_outcome.")
        Component(tools_guardkit, "guardkit_* tools (11)", "Python / @tool over execute", "One wrapper per GuardKit subcommand with context-manifest resolution.")
        Component(tools_history, "history_tools", "Python / @tool over SQLite", "record_build_transition, record_stage.")
        Component(async_middleware, "AsyncSubAgentMiddleware", "DeepAgents 0.5.3 preview", "Exposes 5 supervisor tools: start/check/update/cancel/list_async_task. Maintains async_tasks state channel.")
    }

    Container_Boundary(subagents_boundary, "Subagents") {
        Component(bpc, "build_plan_composer", "LangGraph SubAgent (sync)", "Composes waves+tasks from feature-spec + retrieved priors. Supervisor blocks on output — gates the next reasoning step.")
        Component(abr, "autobuild_runner", "LangGraph graph (AsyncSubAgent, ASGI co-deployed)", "Executes waves via /task-work + /task-review + /task-complete. Long-running (30-90+ min). Internal interrupt() pauses independently of supervisor.")
    }

    ContainerDb_Ext(state_channel, "async_tasks state channel", "LangGraph channel", "AutobuildState entries per running async subagent (DDR-006 schema).")

    Container_Ext(discovery, "Discovery + Learning + Calibration", "Python", "forge.discovery, .learning, .calibration")
    Container_Ext(nats_adapter, "NATS Adapter", "forge.adapters.nats", "JetStream + core + KV")
    Container_Ext(sqlite_adapter, "SQLite Adapter", "forge.adapters.sqlite", "~/.forge/forge.db WAL")
    Container_Ext(graphiti_adapter, "Graphiti Adapter", "forge.adapters.graphiti", "forge_pipeline_history + forge_calibration_history")
    Container_Ext(subprocess_adapter, "Subprocess Adapter", "forge.adapters.guardkit / git / execute", "/usr/local/bin/guardkit + git + gh")
    Container_Ext(langgraph_adapter, "LangGraph Adapter", "forge.adapters.langgraph", "resume_value_as helper (DDR-002)")
    Container_Ext(llm, "LLM Provider", "Gemini 3.1 Pro / Gemini 2.5 Flash", "Reasoning + implementation models")

    Rel(agent, prompts, "assemble system prompt at build start")
    Rel(agent, subagents_mod, "register sub-agent specs")
    Rel(agent, tools_dispatch, "tool surface")
    Rel(agent, tools_approval, "tool surface")
    Rel(agent, tools_graphiti, "tool surface")
    Rel(agent, tools_guardkit, "tool surface")
    Rel(agent, tools_history, "tool surface")
    Rel(agent, async_middleware, "wraps for supervisor")
    Rel(async_middleware, state_channel, "read/write async_tasks entries")
    Rel(async_middleware, abr, "start/check/update/cancel via ASGI")
    Rel(subagents_mod, bpc, "factory produces spec")
    Rel(subagents_mod, abr, "factory produces spec")

    Rel(prompts, discovery, "query live fleet capabilities for {available_capabilities}")
    Rel(prompts, graphiti_adapter, "query priors for {calibration_priors} + {project_context}")

    Rel(tools_dispatch, discovery, "resolve(tool_name, intent_pattern)")
    Rel(tools_dispatch, nats_adapter, "publish agents.command.*; subscribe reply")
    Rel(tools_approval, nats_adapter, "publish ApprovalRequestPayload")
    Rel(tools_approval, sqlite_adapter, "mark_paused + transition on resume")
    Rel(tools_approval, langgraph_adapter, "resume_value_as(ApprovalResponsePayload, raw)")
    Rel(tools_graphiti, graphiti_adapter, "write gate/override/session entities")
    Rel(tools_guardkit, subprocess_adapter, "run guardkit subcommand with --nats + --context")
    Rel(tools_history, sqlite_adapter, "write builds + stage_log rows")

    Rel(bpc, tools_guardkit, "invokes /feature-spec + /feature-plan")
    Rel(bpc, tools_graphiti, "read_override_history for priors")
    Rel(bpc, tools_dispatch, "may call architect-agent for feasibility")

    Rel(abr, tools_guardkit, "invokes /task-work + /task-review + /task-complete")
    Rel(abr, tools_history, "record_stage per task")
    Rel(abr, tools_approval, "internal gate interrupts")
    Rel(abr, tools_graphiti, "record_override + write_gate_decision")

    Rel(agent, llm, "reasoning invocations", "HTTPS")
    Rel(bpc, llm, "reasoning invocations", "HTTPS")
    Rel(abr, llm, "implementation invocations", "HTTPS")
```

---

## What to look for

- **`forge.agent` is the hub** — expected; it's the entry point that wires everything.
- **No direct module-to-module I/O** — every adapter call goes through a `@tool`, and every adapter is crossed via one explicit arrow.
- **Two distinct subagent patterns** — sync `build_plan_composer` sits inside the same graph; async `autobuild_runner` is its own graph linked via the `async_tasks` state channel (ADR-ARCH-031).
- **ApprovalRequestPayload path is wide but explicit** — `tools_approval` talks to NATS (publish), SQLite (mark paused), and LangGraph (rehydrate resume). Three collaborators for a single tool, all justified by the round-trip contract.
- **Tool-layer breadth** — 5 tool-module clusters. Could compress further but each group has a distinct semantic home (dispatch vs approval vs graphiti vs guardkit vs history).

Node count: 16 / 30 threshold.

---

## Module mapping

| Diagram component | Source module(s) |
|---|---|
| `forge.agent` | `src/forge/agent.py` |
| `forge.prompts` | `src/forge/prompts/__init__.py` + per-role templates |
| `forge.subagents` | `src/forge/subagents/__init__.py` (spec factories) |
| `dispatch_by_capability` | `src/forge/tools/dispatch.py` |
| `approval + notification tools` | `src/forge/tools/approval.py`, `notification.py` |
| `graphiti_tools` | `src/forge/tools/graphiti.py` |
| `guardkit_* tools` | `src/forge/tools/guardkit/*.py` (11 files) |
| `history_tools` | `src/forge/tools/history.py` |
| `AsyncSubAgentMiddleware` | DeepAgents `deepagents.middleware.async_subagent` |
| `build_plan_composer` | `src/forge/subagents/build_plan_composer.py` |
| `autobuild_runner` | `src/forge/subagents/autobuild_runner.py` (separate graph entry) |

---

## Related

- C4 L2: [container.md](../../architecture/container.md)
- ADRs: ADR-ARCH-001, ADR-ARCH-002, ADR-ARCH-020, ADR-ARCH-031
- Adjacent L3: [domain-core.md](domain-core.md)
- Subagent contract: [API-subagents.md](../contracts/API-subagents.md)
- Async state contract: [DDR-006](../decisions/DDR-006-async-subagent-state-channel-contract.md)
Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files)

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Offer Graphiti seeding commands
Write domain-core.md
109 lines
# C4 Level 3 — Domain Core (Component Diagram)

> **Generated:** 2026-04-23 via `/system-design`
> **Container:** `Discovery + Learning + Calibration` (from [container.md](../../architecture/container.md))
> **Components inside:** 7 pure domain modules
> **Status:** Awaiting Rich's approval (C4 L3 review gate)

---

## Purpose

The Domain Core is the pure-reasoning layer of Forge: no I/O imports, every function is testable without a NATS / SQLite / Graphiti stand-up. It owns gating logic, state-machine transition rules, notification reasoning, learning-pattern detection, calibration normalisation, live capability resolution, and history labelling.

All I/O is delegated to adapters (NATS, SQLite, Graphiti, subprocess) — the Domain Core invokes them via injected interfaces, never imports them directly.

Why this container warrants an L3 (>3 components): 7 modules with non-trivial relationships between them (gating consumes calibration priors, learning observes gate decisions, discovery feeds capability lists into prompt assembly). A single L2 node hides the flows.

---

## Diagram

```mermaid
C4Component
    title Component diagram for Domain Core (pure, no I/O)

    Container_Boundary(core, "Domain Core") {
        Component(gating, "forge.gating", "Python (pure)", "evaluate_gate() — takes coach_score, priors, detections, constitutional rules; returns GateDecision. No static thresholds (ADR-ARCH-019); reasoning-driven.")
        Component(state_machine, "forge.state_machine", "Python (pure)", "Valid BuildStatus transitions. Validates writer intents before SQLite commit.")
        Component(notifications, "forge.notifications", "Python (pure)", "Decides whether to emit a NotificationPayload based on retrieved Rich-ack-behaviour priors. No static config (ADR-ARCH-019).")
        Component(learning, "forge.learning", "Python (pure)", "Detects override patterns across recent gate decisions. Produces OverridePatternObservation + proposed CalibrationAdjustment.")
        Component(calibration, "forge.calibration", "Python (pure)", "Normalises raw history events (response_raw → ResponseKind + accepted_default). Triggers incremental refresh cycle.")
        Component(discovery, "forge.discovery", "Python (pure-ish; holds in-memory cache)", "30s TTL cache of agent manifests. resolve(tool_name, intent_pattern) selects target agent per ADR-ARCH-015 algorithm.")
        Component(history_labels, "forge.history_labels", "Python (pure)", "Thin helper — formats reasoning-model-chosen stage_label for SQLite persistence + forge history rendering.")
    }

    Container_Ext(prompts, "forge.prompts", "Python", "System prompt templates — consumes output of discovery + calibration + learning to fill placeholders.")

    Container_Ext(nats_adapter, "NATS Adapter", "forge.adapters.nats", "Publishes, subscribes, watches KV, feeds discovery callbacks.")
    Container_Ext(sqlite_adapter, "SQLite Adapter", "forge.adapters.sqlite", "Only writes via transitions validated by state_machine.")
    Container_Ext(graphiti_adapter, "Graphiti Adapter", "forge.adapters.graphiti", "Persists GateDecision + CapabilityResolution + CalibrationAdjustment; retrieves priors.")
    Container_Ext(history_parser, "History Parser Adapter", "forge.adapters.history_parser", "Tokenises markdown → CalibrationEvent stream; calibration normalises output.")
    Container_Ext(tools_approval, "approval_tools", "Python @tool", "Calls gating.evaluate_gate; on FLAG/HARD_STOP/MANDATORY, invokes request_approval tool.")
    Container_Ext(tools_history, "history_tools", "Python @tool", "Uses state_machine.validate_transition before record_build_transition writes.")
    Container_Ext(tools_dispatch, "dispatch_by_capability", "Python @tool", "Resolution via discovery; publishes via NATS.")

    Rel(gating, calibration, "read CalibrationEvent priors (in-process structs; reads from graphiti_adapter)")
    Rel(gating, learning, "query approved CalibrationAdjustment list")
    Rel(gating, graphiti_adapter, "retrieve PriorReference evidence + OverrideEvent history", "injected")
    Rel(gating, tools_approval, "return GateDecision; tool turns it into interrupt() + NATS publish")

    Rel(state_machine, sqlite_adapter, "validate_transition() called before commit", "injected")
    Rel(state_machine, tools_history, "transition validation")

    Rel(notifications, graphiti_adapter, "retrieve Rich-ack-behaviour priors", "injected")
    Rel(notifications, tools_approval, "decide emit_notification vs skip")

    Rel(learning, graphiti_adapter, "read OverrideEvent stream + CalibrationAdjustment chain; write propose_adjustments", "injected")
    Rel(learning, gating, "observation output feeds future evaluate_gate runs via priors")

    Rel(calibration, history_parser, "consume parsed CalibrationEvent stream", "injected")
    Rel(calibration, graphiti_adapter, "bulk add_calibration_events", "injected")
    Rel(calibration, sqlite_adapter, "update HistoryFileSnapshot bookkeeping", "injected")

    Rel(discovery, nats_adapter, "watch_fleet callback + KV read", "injected")
    Rel(discovery, graphiti_adapter, "persist CapabilityResolution after each dispatch", "injected")
    Rel(discovery, tools_dispatch, "resolve(tool_name, intent_pattern) → agent_id")

    Rel(history_labels, tools_history, "format stage_label on record_stage write")

    Rel(prompts, discovery, "list_capabilities for {available_capabilities}")
    Rel(prompts, calibration, "retrieved CalibrationEvent priors for {calibration_priors}")
    Rel(prompts, learning, "approved CalibrationAdjustment list")
```

---

## What to look for

- **No domain → adapter direct imports** — every line from a Domain Core component into an adapter is marked `injected`. The modules take adapters as constructor arguments (Hexagonal ports-and-adapters), never reach for them directly.
- **`gating` is central** — expected; it's the reasoning pivot. Input from calibration + learning + graphiti (priors); output into approval_tools (gate decisions). Four collaborators, all justified.
- **`learning` ↔ `gating` is indirect** — learning writes adjustments to Graphiti; gating retrieves them as priors. No circular import. Clean read-write-read cycle through the graph store.
- **`state_machine` has one caller** — `tools_history` via validate_transition. Tight and easy to test.
- **`discovery` is the odd one out** — it holds an in-memory cache, so it's "pure-ish" rather than strictly stateless. The cache is a defensible exception because it's the performance-critical hot path during dispatch resolution.

Node count: 15 / 30 threshold.

---

## Module mapping

| Diagram component | Source module |
|---|---|
| `forge.gating` | `src/forge/gating.py` |
| `forge.state_machine` | `src/forge/state_machine.py` |
| `forge.notifications` | `src/forge/notifications.py` |
| `forge.learning` | `src/forge/learning.py` |
| `forge.calibration` | `src/forge/calibration.py` |
| `forge.discovery` | `src/forge/discovery.py` |
| `forge.history_labels` | `src/forge/history_labels.py` |

---

## Related

- C4 L2: [container.md](../../architecture/container.md)
- ADRs: ADR-ARCH-001 (hexagonal), ADR-ARCH-015 (capability dispatch), ADR-ARCH-016 (fleet catalogue), ADR-ARCH-019 (no static behavioural config)
- Adjacent L3: [agent-runtime.md](agent-runtime.md)
- Data models: [DM-gating.md](../models/DM-gating.md), [DM-calibration.md](../models/DM-calibration.md), [DM-discovery.md](../models/DM-discovery.md), [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
Both C4 L3 diagrams written. Now the mandatory review gate.

Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files)

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Offer Graphiti seeding commands

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 C4 COMPONENT DIAGRAM REVIEW GATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Two C4 Level 3 diagrams require explicit approval.
Diagrams not approved will be excluded from the design output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 DIAGRAM 1/2 — Agent Runtime
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Preview: docs/design/diagrams/agent-runtime.md
Nodes: 16 / 30 threshold
Components: 7 modules + AsyncSubAgentMiddleware + 2 sub-agents + async_tasks state channel

Key relationships depicted:
  • forge.agent as hub for 5 tool clusters (dispatch, approval, graphiti,
    guardkit, history)
  • Sync build_plan_composer inside the supervisor graph
  • Async autobuild_runner as separate LangGraph graph via ASGI (ADR-ARCH-031)
  • async_tasks state channel linking middleware ↔ autobuild_runner
    (DDR-006)
  • tools_approval → NATS + SQLite + LangGraph adapter trio for pause round-trip

Look for:
  - Too many dependencies on any one module? (forge.agent is the expected hub)
  - Missing persistence or concerns? (adapters are shown as Container_Ext edges)
  - Unclear separation between sync and async subagent patterns?

Diagram rendering (Mermaid) lives in agent-runtime.md — render in an MD
preview or browser to see it laid out.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 DIAGRAM 2/2 — Domain Core
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Preview: docs/design/diagrams/domain-core.md
Nodes: 15 / 30 threshold
Components: 7 pure domain modules + 7 external collaborators (adapters + tools + prompts)

Key relationships depicted:
  • gating is central (consumes calibration priors + learning adjustments +
    graphiti evidence; outputs GateDecision into approval tool)
  • learning ↔ gating is intentionally indirect (write-through-Graphiti)
  • state_machine is the transition validator; one caller (history_tools)
  • discovery has the in-memory cache — marked "pure-ish" as a deliberate exception
  • Every domain → adapter edge is marked "injected" (Hexagonal ports-and-adapters)

Look for:
  - Any domain → adapter import that should be inverted?
  - Unclear why discovery holds state when everything else is pure?
  - Missing cross-module relationships (e.g. should notifications → learning)?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Per-diagram options:** `[A]pprove` | `[R]evise` | `[K]ill (reject)` 

Reply with your decisions — e.g. `agent-runtime: A, domain-core: A` to approve both, or flag specific revisions. Unapproved diagrams will be removed from the output.
[A]pprove both
Both diagrams approved. Running final validation + generating Graphiti seeding commands.

Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files)

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Offer Graphiti seeding commands
Bash Verify all artefact files exist
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/{contracts,models,decisions,diagrams}/ 2>/dev/null

OUT
/Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/contracts/:
total 192
drwxr-xr-x  11 richardwoollcott  staff    352 Apr 23 18:30 .
drwxr-xr-x   6 richardwoollcott  staff    192 Apr 23 18:15 ..
-rw-r--r--   1 richardwoollcott  staff   8091 Apr 23 18:20 API-cli.md
-rw-r--r--   1 richardwoollcott  staff   9371 Apr 23 18:17 API-nats-agent-dispatch.md
-rw-r--r--   1 richardwoollcott  staff   8237 Apr 23 18:18 API-nats-approval-protocol.md
-rw-r--r--   1 richardwoollcott  staff   9819 Apr 23 18:19 API-nats-fleet-lifecycle.md
-rw-r--r--   1 richardwoollcott  staff  10408 Apr 23 18:30 API-nats-pipeline-events.md
-rw-r--r--   1 richardwoollcott  staff   8036 Apr 23 18:21 API-sqlite-schema.md
-rw-r--r--   1 richardwoollcott  staff   7922 Apr 23 18:23 API-subagents.md
-rw-r--r--   1 richardwoollcott  staff   7296 Apr 23 18:24 API-subprocess.md
-rw-r--r--   1 richardwoollcott  staff  14692 Apr 23 18:22 API-tool-layer.md

/Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/decisions/:
total 96
drwxr-xr-x  8 richardwoollcott  staff   256 Apr 23 18:33 .
drwxr-xr-x  6 richardwoollcott  staff   192 Apr 23 18:15 ..
-rw-r--r--  1 richardwoollcott  staff  4287 Apr 23 18:31 DDR-001-reply-subject-correlation.md
-rw-r--r--  1 richardwoollcott  staff  4921 Apr 23 18:31 DDR-002-resume-value-rehydration-helper.md
-rw-r--r--  1 richardwoollcott  staff  4177 Apr 23 18:32 DDR-003-sqlite-schema-layout-wal.md
-rw-r--r--  1 richardwoollcott  staff  4785 Apr 23 18:32 DDR-004-graphiti-group-partitioning.md
-rw-r--r--  1 richardwoollcott  staff  5731 Apr 23 18:33 DDR-005-cli-context-manifest-resolution.md
-rw-r--r--  1 richardwoollcott  staff  6631 Apr 23 18:33 DDR-006-async-subagent-state-channel-contract.md

/Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/diagrams/:
total 40
drwxr-xr-x  4 richardwoollcott  staff   128 Apr 23 18:35 .
drwxr-xr-x  6 richardwoollcott  staff   192 Apr 23 18:15 ..
-rw-r--r--  1 richardwoollcott  staff  8366 Apr 23 18:35 agent-runtime.md
-rw-r--r--  1 richardwoollcott  staff  7559 Apr 23 18:35 domain-core.md

/Users/richardwoollcott/Projects/appmilla_github/forge/docs/design/models/:
total 112
drwxr-xr-x  7 richardwoollcott  staff    224 Apr 23 18:28 .
drwxr-xr-x  6 richardwoollcott  staff    192 Apr 23 18:15 ..
-rw-r--r--  1 richardwoollcott  staff   9634 Apr 23 18:25 DM-build-lifecycle.md
-rw-r--r--  1 richardwoollcott  staff   8576 Apr 23 18:27 DM-calibration.md
-rw-r--r--  1 richardwoollcott  staff   8053 Apr 23 18:27 DM-discovery.md
-rw-r--r--  1 richardwoollcott  staff   9018 Apr 23 18:26 DM-gating.md
-rw-r--r--  1 richardwoollcott  staff  10442 Apr 23 18:28 DM-graphiti-entities.md
All 22 artefact files confirmed. Checking Graphiti connectivity before generating seed commands.

Bash Test FalkorDB reachability on port 6379
IN
timeout 5 nc -zv whitestocks 6379 2>&1 || echo "connectivity-check-failed"

OUT
Connection to whitestocks port 6379 [tcp/*] succeeded!
Bash Check guardkit CLI availability
IN
which guardkit 2>/dev/null && guardkit --version 2>&1 | head -3

OUT
/Users/richardwoollcott/.agentecflow/bin/guardkit
GuardKit version 1.0.0
Installation: /Users/richardwoollcott/.agentecflow
Graphiti reachable at whitestocks:6379, GuardKit CLI present. Presenting final summary + seeding commands.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEM DESIGN COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Created: docs/design/
  ├── contracts/            (9 files, ~80 KB)
  │   ├── API-nats-pipeline-events.md
  │   ├── API-nats-agent-dispatch.md
  │   ├── API-nats-approval-protocol.md
  │   ├── API-nats-fleet-lifecycle.md
  │   ├── API-cli.md
  │   ├── API-sqlite-schema.md
  │   ├── API-tool-layer.md
  │   ├── API-subagents.md
  │   └── API-subprocess.md
  ├── models/               (5 files, ~46 KB)
  │   ├── DM-build-lifecycle.md
  │   ├── DM-gating.md
  │   ├── DM-calibration.md
  │   ├── DM-discovery.md
  │   └── DM-graphiti-entities.md
  ├── diagrams/             (2 files, ~16 KB) — both approved
  │   ├── agent-runtime.md  (C4 L3, 16 nodes)
  │   └── domain-core.md    (C4 L3, 15 nodes)
  └── decisions/            (6 DDRs, ~31 KB)
      ├── DDR-001-reply-subject-correlation.md
      ├── DDR-002-resume-value-rehydration-helper.md
      ├── DDR-003-sqlite-schema-layout-wal.md
      ├── DDR-004-graphiti-group-partitioning.md
      ├── DDR-005-cli-context-manifest-resolution.md
      └── DDR-006-async-subagent-state-channel-contract.md

NOT generated (deliberately — per ADRs):
  ✗ openapi.yaml           — ADR-ARCH-012 excludes HTTP/REST
  ✗ mcp-tools.json         — ADR-ARCH-012 excludes MCP
  ✗ a2a-schemas.yaml       — ADR-ARCH-003 fleet uses NATS request/reply

Contradiction detection: ✓ No conflicts with 31 existing ADRs

Soft flags:
  • 4 new nats-core payload types proposed (2 from refresh doc + 2 additive) —
    tracked in DDR-001 as TASK-NCFA-002 dependency on nats-core ≥ 0.2.0
Graphiti seeding — ready to run (FalkorDB reachable):


# API contracts → project_design group
guardkit graphiti add-context docs/design/contracts/API-nats-pipeline-events.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-nats-agent-dispatch.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-nats-approval-protocol.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-nats-fleet-lifecycle.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-cli.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-sqlite-schema.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-tool-layer.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-subagents.md --group project_design
guardkit graphiti add-context docs/design/contracts/API-subprocess.md --group project_design

# Data models → project_design group
guardkit graphiti add-context docs/design/models/DM-build-lifecycle.md --group project_design
guardkit graphiti add-context docs/design/models/DM-gating.md --group project_design
guardkit graphiti add-context docs/design/models/DM-calibration.md --group project_design
guardkit graphiti add-context docs/design/models/DM-discovery.md --group project_design
guardkit graphiti add-context docs/design/models/DM-graphiti-entities.md --group project_design

# DDRs → architecture_decisions group
guardkit graphiti add-context docs/design/decisions/DDR-001-reply-subject-correlation.md --group architecture_decisions
guardkit graphiti add-context docs/design/decisions/DDR-002-resume-value-rehydration-helper.md --group architecture_decisions
guardkit graphiti add-context docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md --group architecture_decisions
guardkit graphiti add-context docs/design/decisions/DDR-004-graphiti-group-partitioning.md --group architecture_decisions
guardkit graphiti add-context docs/design/decisions/DDR-005-cli-context-manifest-resolution.md --group architecture_decisions
guardkit graphiti add-context docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md --group architecture_decisions
Run these seeding commands now? [Y/n]

(20 commands total. Diagrams are not seeded — they're visual + already referenced by the L2 container doc.)

Next steps regardless of seeding:

Review key design calls — especially the 4-payload addition to nats-core (DDR-001) and the forge.adapters.langgraph helper placement (DDR-002).
Raise TASK-NCFA-002 in the nats-core repo for the payload additions.
Feed these artefacts into /feature-spec / /feature-plan sessions when you're ready to carve Forge into implementable features.
If you want me to also append an entry to docs/history/system-design-history.md, say so.
<task-notification>
<task-id>baf5q9l80</task-id>
<tool-use-id>toolu_01CYy1yuRc7nosmuusopThKS</tool-use-id>
<output-file>/private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-forge/4d1fa0ca-0a86-48c7-a060-6bad55a2b68e/tasks/baf5q9l80.output</output-file>
<status>completed</status>
<summary>Background command "Seed all 20 design artefacts into Graphiti sequentially" completed (exit code 0)</summary>
</task-notification>
Y - run seeding commands and use the task tool to invoke /task-create for TASK-NCFA-002 in the nats-core repo for the payload additions.
Kicking off both in parallel — seeding in background, agent for task creation.

Bash Seed all 20 design artefacts into Graphiti sequentially
IN
{
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] SEED-START"
  for f in docs/design/contracts/*.md docs/design/models/*.md; do
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] seeding: $f (group=project_design)"
    guardkit graphiti add-context "$f" --group project_design 2>&1
  done
  for f in docs/design/decisions/DDR-*.md; do
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] seeding: $f (group=architecture_decisions)"
    guardkit graphiti add-context "$f" --group architecture_decisions 2>&1
  done
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] SEED-DONE"
} > /tmp/forge-design-seed.log 2>&1

OUT
Command running in background with ID: baf5q9l80. Output is being written to: /private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-forge/4d1fa0ca-0a86-48c7-a060-6bad55a2b68e/tasks/baf5q9l80.output
Agent:Create TASK-NCFA-002 in nats-core
IN
Create a new task `TASK-NCFA-002` in the `nats-core` sibling repo to track the payload-type additions that Forge's `/system-design` pass surfaced.

**Repo path:** `/Users/richardwoollcott/Projects/appmilla_github/nats-core`

**Why this task exists.** Forge's `/system-design` session today produced an API contract (`forge/docs/design/contracts/API-nats-pipeline-events.md`) that requires 4 new pipeline-event payload types in `nats-core`. Two were already mandated by the Forge pipeline-orchestrator refresh doc (`StageCompletePayload`, `BuildPausedPayload`); two are additive refinements Forge needs for clean downstream filtering (`BuildResumedPayload`, `BuildCancelledPayload`). Until these land in `nats-core ≥ 0.2.0`, Forge will carry them locally in `forge.adapters.nats._interim_payloads.py` with a TODO pointing here. See Forge's `docs/design/decisions/DDR-001-reply-subject-correlation.md` for the full dependency decision.

There's a sibling task already tracked — `TASK-NCFA-001` covers the **retirement** of `FeaturePlannedPayload` + `FeatureReadyForBuildPayload` per the Forge refresh doc "correction 12". `TASK-NCFA-002` is the complementary addition task. They should both land together in the same `nats-core ≥ 0.2.0` release.

**Task content to capture:**

Title: `Add 4 pipeline-event payload types required by Forge orchestrator`

Scope (what must ship):
1. `StageCompletePayload` — emitted after each gate-evaluated dispatch. Fields: `feature_id, build_id, stage_label, target_kind (Literal["local_tool","fleet_capability","subagent"]), target_identifier, status (Literal["PASSED","FAILED","GATED","SKIPPED"]), gate_mode (Literal["AUTO_APPROVE","FLAG_FOR_REVIEW","HARD_STOP","MANDATORY_HUMAN_APPROVAL"] | None), coach_score (float | None), duration_secs, completed_at, correlation_id`
2. `BuildPausedPayload` — emitted when a gate flags a stage for review. Fields: `feature_id, build_id, stage_label, gate_mode (subset of the literal above), coach_score (float | None), rationale (str), approval_subject (str), paused_at, correlation_id`
3. `BuildResumedPayload` — emitted after `ApprovalResponsePayload` rehydrates and the graph resumes. Fields: `feature_id, build_id, stage_label, decision (Literal["approve","reject","defer","override"]), responder, resumed_at, correlation_id`
4. `BuildCancelledPayload` — emitted when the running build sees a cancel command. Fields: `feature_id, build_id, reason, cancelled_by, cancelled_at, correlation_id`

Also:
- Add matching entries to the `EventType` enum (e.g. `STAGE_COMPLETE`, `BUILD_PAUSED`, `BUILD_RESUMED`, `BUILD_CANCELLED`).
- Add matching topic templates under `Topics.Pipeline` (`STAGE_COMPLETE = "pipeline.stage-complete.{feature_id}"`, etc.).
- Register the payload classes in whatever EventType→payload registry nats-core maintains.
- Add unit tests in `tests/test_events.py` covering each new payload's validation + serde round-trip.
- Bump `nats-core` minor version to 0.2.0 (these are additive but warrant a minor).

**Acceptance criteria:**
- `from nats_core.events.pipeline import StageCompletePayload, BuildPausedPayload, BuildResumedPayload, BuildCancelledPayload` works.
- Each payload validates required fields and rejects malformed inputs (tested).
- `Topics.Pipeline.STAGE_COMPLETE` etc. resolve via `Topics.resolve(..., feature_id="FEAT-XXX")`.
- `EventType` enum additions don't break existing callers (extras are additive).
- Version bumped to 0.2.0 in `pyproject.toml`.

**Dependency note to include in the task file:**
- Depends on nothing in the Forge repo — this is a pure nats-core library change.
- Forge's `forge.adapters.nats._interim_payloads.py` will be deleted once this ships and Forge bumps its `nats-core` dependency pin.
- Should ship alongside `TASK-NCFA-001` (the Feature*Payload retirement) in the same release.

**Relationship to existing work:**
- Sibling to `TASK-NCFA-001` (retirement task already tracked).
- Referenced by Forge `DDR-001-reply-subject-correlation.md`.
- Consumed by Forge API contract `forge/docs/design/contracts/API-nats-pipeline-events.md` §3.2.

**How to create the task:**

Investigate first — look at `/Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/` to understand the existing task-file convention (front-matter shape, ID scheme, location relative to a feature folder). Also check if there's a `TASK-NCFA-001` already, and if so, follow its structure exactly. There may be a `guardkit task-create` CLI you can invoke from the nats-core root (`cd /Users/richardwoollcott/Projects/appmilla_github/nats-core && guardkit task-create …`) — use it if it matches their convention; otherwise write the task file manually following the existing pattern.

**Important:** do not modify any nats-core source code, tests, or ADRs — this is task creation only, not implementation. The task file is the single deliverable.

**Report back:** path to the task file you created, plus any discoveries about NCFA feature scope (is it an already-created feature folder? what does TASK-NCFA-001 look like?).
Bash List nats-core root directory
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/ 2>/dev/null || echo "Directory not found"

OUT
command-history.md
coverage.json
docs
features
LICENSE
migrations
pyproject.toml
README.md
src
system-arch-history.md
tasks
tests
Bash List nats-core features directory
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/features/ 2>/dev/null || echo "No features directory"

OUT
event-type-schemas
fleet-registration
message-envelope
nats-client
nats-configuration
topic-registry
Bash Investigate TASK-B527 structure and full backlog listing
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/backlog/TASK-B527/ 2>/dev/null || echo "Not a dir" && ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/backlog/ -la

OUT
Exit code 1
Not a dir
ls: -la: No such file or directory
/Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/backlog/:
forge-v2-alignment
TASK-7448-review-forge-v2-alignment-tasks.md
Bash List all task files and directories with details
IN
ls -la /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/backlog/ && ls -la /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/completed/ && ls -la /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/blocked/

OUT
total 24
drwxr-xr-x  4 richardwoollcott  staff   128 Apr 16 07:38 .
drwxr-xr-x@ 5 richardwoollcott  staff   160 Apr 17 11:36 ..
drwxr-xr-x  4 richardwoollcott  staff   128 Apr 17 10:52 forge-v2-alignment
-rw-r--r--  1 richardwoollcott  staff  8275 Apr 16 07:38 TASK-7448-review-forge-v2-alignment-tasks.md
total 0
drwxr-xr-x@ 10 richardwoollcott  staff  320 Apr 16 12:10 .
drwxr-xr-x@  5 richardwoollcott  staff  160 Apr 17 11:36 ..
drwxr-xr-x  10 richardwoollcott  staff  320 Apr 11 18:30 event-type-schemas
drwxr-xr-x  11 richardwoollcott  staff  352 Apr 11 18:30 fleet-registration
drwxr-xr-x@  4 richardwoollcott  staff  128 Apr 17 11:36 forge-v2-alignment
drwxr-xr-x   8 richardwoollcott  staff  256 Apr 11 18:30 message-envelope
drwxr-xr-x  14 richardwoollcott  staff  448 Apr 11 18:30 nats-client
drwxr-xr-x  10 richardwoollcott  staff  320 Apr 11 18:30 nats-configuration
drwxr-xr-x   3 richardwoollcott  staff   96 Apr 11 18:31 TASK-B527
drwxr-xr-x   7 richardwoollcott  staff  224 Apr 11 18:30 topic-registry
total 0
drwxr-xr-x@ 2 richardwoollcott  staff   64 Apr  3 23:07 .
drwxr-xr-x@ 5 richardwoollcott  staff  160 Apr 17 11:36 ..
Bash List TASK-B527 completed task files
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/completed/TASK-B527/

OUT
TASK-B527.md
Read TASK-NCFA-002-integration-tests-new-payloads.md
Read README.md
Bash Check TASK-B527 structure for ID convention clues
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/tasks/completed/TASK-B527/

OUT
TASK-B527.md
Bash Check nats-core docs design and architecture directories
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/docs/design/ 2>/dev/null && ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/docs/architecture/ 2>/dev/null

OUT
contracts
decisions
diagrams
mcp-tools.json
models
specs
ARCHITECTURE.md
assumptions.yaml
container.md
decisions
domain-model.md
system-context.md
Bash Check ADR/decision directories in nats-core docs
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/docs/design/decisions/ && ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/docs/architecture/decisions/

OUT
ADR-001-nats-as-event-bus.md
ADR-002-schema-versioning.md
ADR-003-nats-py-vs-faststream.md
ADR-004-dynamic-fleet-registration.md
DDR-001-feature-ready-for-build.md
DDR-002-publish-full-manifest.md
ADR-ARCH-001-modular-monolith-pattern.md
ADR-ARCH-002-python-312-minimum.md
ADR-ARCH-003-minimal-runtime-dependencies.md
Bash List nats-core design contracts
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/docs/design/contracts/

OUT
agent-manifest-contract.md
API-fleet-registration.md
API-message-contracts.md
API-nats-client.md
API-topic-registry.md
Read IMPLEMENTATION-GUIDE.md
Write TASK-NCFA-003-add-forge-system-design-pipeline-payloads.md
264 lines
---
id: TASK-NCFA-003
title: Add 4 pipeline-event payload types required by Forge orchestrator
status: backlog
created: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
task_type: implementation
feature_id: FEAT-NCFA
priority: high
tags: [nats-core, payloads, topics, forge-system-design, pipeline-events]
complexity: 4
wave: 3
implementation_mode: task-work
dependencies: []
sibling_tasks: [TASK-NCFA-001]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Add 4 pipeline-event payload types required by Forge orchestrator

## Context

Forge's `/system-design` session (2026-04-23) produced an API contract
(`forge/docs/design/contracts/API-nats-pipeline-events.md`) that requires four
pipeline-event payload types that nats-core does not yet expose. Two were already
referenced by the Forge pipeline-orchestrator refresh doc (`StageCompletePayload`,
`BuildPausedPayload`); two are additive refinements Forge needs for clean downstream
filtering (`BuildResumedPayload`, `BuildCancelledPayload`).

Note: `StageCompletePayload` and `BuildPausedPayload` were added by TASK-NCFA-001
as part of the forge-v2.2 wave, but with a different field signature. This task
supersedes those definitions with the canonical field sets specified in the Forge
`/system-design` API contract — the two tasks should be reconciled during
implementation review. `BuildResumedPayload` and `BuildCancelledPayload` are net-new
additions not covered by TASK-NCFA-001.

Until this task ships, Forge carries these four payloads locally in
`forge/forge/adapters/nats/_interim_payloads.py` with a TODO pointing here. That
interim module will be deleted once Forge bumps its `nats-core` dependency pin to
`>= 0.2.0`.

The full dependency decision is recorded in
`forge/docs/design/decisions/DDR-001-reply-subject-correlation.md`.

## Authoritative specs

- **Forge API contract:** `forge/docs/design/contracts/API-nats-pipeline-events.md` §3.2
- **Forge dependency decision:** `forge/docs/design/decisions/DDR-001-reply-subject-correlation.md`

## Scope

### 1. Add / reconcile payloads in `src/nats_core/events/_pipeline.py`

All four payloads use `ConfigDict(extra="allow")` for forward compatibility
(consistent with the forward-compat decision from TASK-7448). Every payload carries
`correlation_id: str` as a required field.

#### `StageCompletePayload`

Reconcile with the version added in TASK-NCFA-001. The canonical field set
per the Forge API contract:

```python
class StageCompletePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature_id: str
    build_id: str
    stage_label: str
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: Literal[
        "AUTO_APPROVE", "FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"
    ] | None
    coach_score: float | None
    duration_secs: float
    completed_at: str  # ISO 8601
    correlation_id: str
```

#### `BuildPausedPayload`

Reconcile with the version added in TASK-NCFA-001. The canonical field set:

```python
class BuildPausedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature_id: str
    build_id: str
    stage_label: str
    gate_mode: Literal[
        "FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"
    ]
    coach_score: float | None
    rationale: str
    approval_subject: str
    paused_at: str  # ISO 8601
    correlation_id: str
```

Note: `gate_mode` here is a subset of the full literal — `AUTO_APPROVE` is excluded
because a build only pauses when a gate requires human action.

#### `BuildResumedPayload` (net-new)

```python
class BuildResumedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature_id: str
    build_id: str
    stage_label: str
    decision: Literal["approve", "reject", "defer", "override"]
    responder: str
    resumed_at: str  # ISO 8601
    correlation_id: str
```

Emitted after `ApprovalResponsePayload` rehydrates and the LangGraph graph resumes.

#### `BuildCancelledPayload` (net-new)

```python
class BuildCancelledPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature_id: str
    build_id: str
    reason: str
    cancelled_by: str
    cancelled_at: str  # ISO 8601
    correlation_id: str
```

Emitted when the running build sees a cancel command on the pipeline.

### 2. Add topic constants to `src/nats_core/topics.py`

`STAGE_COMPLETE` and `BUILD_PAUSED` were added by TASK-NCFA-001; confirm they match
the Forge contract and are already present. Add the two net-new entries to
`Topics.Pipeline`:

```python
BUILD_RESUMED   = "pipeline.build-resumed.{feature_id}"
BUILD_CANCELLED = "pipeline.build-cancelled.{feature_id}"
```

`BUILD_RESUMED` may already be present from TASK-NCFA-001 — confirm and skip if so.

### 3. Add `EventType` enum members in `src/nats_core/envelope.py`

Confirm or add:

```python
STAGE_COMPLETE  = "stage_complete"
BUILD_PAUSED    = "build_paused"
BUILD_RESUMED   = "build_resumed"
BUILD_CANCELLED = "build_cancelled"
```

`STAGE_COMPLETE`, `BUILD_PAUSED`, and `BUILD_RESUMED` were added by TASK-NCFA-001.
Only `BUILD_CANCELLED` is guaranteed net-new.

### 4. Register payloads in `_EVENT_TYPE_REGISTRY`

Confirm or add entries in `envelope.py`:

```python
EventType.STAGE_COMPLETE:  StageCompletePayload,
EventType.BUILD_PAUSED:    BuildPausedPayload,
EventType.BUILD_RESUMED:   BuildResumedPayload,
EventType.BUILD_CANCELLED: BuildCancelledPayload,
```

### 5. Export the symbols

Update `src/nats_core/events/__init__.py` so that:

```python
from nats_core.events.pipeline import (
    StageCompletePayload,
    BuildPausedPayload,
    BuildResumedPayload,
    BuildCancelledPayload,
)
```

works. Add all four to the import list and `__all__`. (Some may already be exported
from TASK-NCFA-001 — confirm and add only what is missing.)

### 6. Unit tests in `tests/test_events.py`

Add unit tests covering each new or reconciled payload. For each payload, add at
minimum:

- Field validation — required fields are enforced, missing fields raise `ValidationError`
- Serde round-trip — `model.model_dump()` followed by `Payload.model_validate(...)` returns an equal instance
- Literal rejection — invalid literal values raise `ValidationError`
- Forward-compat — extra fields are accepted without error (`ConfigDict(extra="allow")`)

Suggested test names:

- `test_stage_complete_payload_validates_required_fields`
- `test_stage_complete_payload_rejects_invalid_status_literal`
- `test_stage_complete_payload_rejects_invalid_target_kind`
- `test_stage_complete_payload_accepts_null_gate_mode_and_coach_score`
- `test_stage_complete_payload_serde_round_trip`
- `test_build_paused_payload_validates_required_fields`
- `test_build_paused_payload_rejects_auto_approve_gate_mode`
- `test_build_paused_payload_serde_round_trip`
- `test_build_resumed_payload_validates_required_fields`
- `test_build_resumed_payload_rejects_invalid_decision_literal`
- `test_build_resumed_payload_serde_round_trip`
- `test_build_cancelled_payload_validates_required_fields`
- `test_build_cancelled_payload_serde_round_trip`
- `test_all_four_payloads_accept_extra_fields` (forward-compat for all four)

### 7. Bump version to 0.2.0

In `pyproject.toml`, bump the `version` field from its current value to `0.2.0`.
These additions are additive (no breaking changes) but warrant a minor bump per
semver given they add a net-new public API surface.

## Acceptance criteria

- [ ] `from nats_core.events.pipeline import StageCompletePayload, BuildPausedPayload, BuildResumedPayload, BuildCancelledPayload` works without error
- [ ] Each payload validates required fields and raises `ValidationError` on malformed inputs (tested)
- [ ] `Topics.Pipeline.STAGE_COMPLETE`, `Topics.Pipeline.BUILD_PAUSED`, `Topics.Pipeline.BUILD_RESUMED`, `Topics.Pipeline.BUILD_CANCELLED` all resolve via `Topics.resolve(..., feature_id="FEAT-XXX")`
- [ ] `EventType.STAGE_COMPLETE`, `EventType.BUILD_PAUSED`, `EventType.BUILD_RESUMED`, `EventType.BUILD_CANCELLED` present in enum
- [ ] `_EVENT_TYPE_REGISTRY` maps all four `EventType` values to their payload classes
- [ ] `BuildPausedPayload` rejects `gate_mode="AUTO_APPROVE"` (that value is excluded from its literal)
- [ ] All four payloads accept unknown extra fields without error
- [ ] All four payloads serde round-trip cleanly
- [ ] Existing callers are not broken — `EventType` additions are additive, no existing member removed
- [ ] `pyproject.toml` version is `0.2.0`
- [ ] `pytest --cov` reports >= 98% coverage (matching existing baseline)
- [ ] No existing tests broken

## Out of scope

- Integration tests against live NATS (separate follow-up if needed, per TASK-NCFA-002 precedent)
- Deleting `FeaturePlannedPayload` or `FeatureReadyForBuildPayload` (retirement is TASK-NCFA-001 scope)
- Any `MessageEnvelope` or `NATSClient` changes
- Forge-side deletion of `forge/forge/adapters/nats/_interim_payloads.py` — that is a Forge task once this ships
- Any `jarvis.*` or `fleet.*` topic additions
- Load or stress testing

## Dependencies

- No upstream nats-core tasks block this — it is a pure library addition.
- Should ship alongside or immediately after TASK-NCFA-001's retirement items in the same `nats-core >= 0.2.0` release.

## Cross-repo references

- **Sibling task:** TASK-NCFA-001 (Feature*Payload retirement — should land in same release)
- **Forge dependency decision:** `forge/docs/design/decisions/DDR-001-reply-subject-correlation.md`
- **Forge API contract:** `forge/docs/design/contracts/API-nats-pipeline-events.md` §3.2
- **Forge interim payloads:** `forge/forge/adapters/nats/_interim_payloads.py` (deleted once this ships and Forge bumps pin)
Seeding finished. Checking results.

Bash Inspect seed log for completion + errors
IN
tail -30 /tmp/forge-design-seed.log && echo "---" && grep -cE "^\[" /tmp/forge-design-seed.log && echo "---errors---" && grep -iE "error|fail|traceback" /tmp/forge-design-seed.log | head -20

OUT
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:19Z] seeding: docs/design/decisions/DDR-002-resume-value-rehydration-helper.md (group=architecture_decisions)
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:20Z] seeding: docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md (group=architecture_decisions)
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:20Z] seeding: docs/design/decisions/DDR-004-graphiti-group-partitioning.md (group=architecture_decisions)
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:20Z] seeding: docs/design/decisions/DDR-005-cli-context-manifest-resolution.md (group=architecture_decisions)
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:20Z] seeding: docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md (group=architecture_decisions)
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
[2026-04-23T18:14:21Z] SEED-DONE
---
22
---errors---
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Error: No such option: --group
Every seed failed — --group isn't the right flag. Checking the actual CLI.

Bash Get actual guardkit add-context options
IN
guardkit graphiti add-context --help 2>&1 | head -40

OUT
Usage: guardkit-py graphiti add-context [OPTIONS] PATH

  Add context from files to Graphiti.

  Adds content from markdown files to the Graphiti knowledge graph. Supports
  single files or directories with glob patterns.

  Examples:
      guardkit graphiti add-context docs/ADR-001.md
      guardkit graphiti add-context docs/architecture/
      guardkit graphiti add-context docs/ --pattern "**/*.md"
      guardkit graphiti add-context docs/ADR-001.md --type adr
      guardkit graphiti add-context docs/ --dry-run
      guardkit graphiti add-context docs/ --delay 1.0
      guardkit graphiti add-context docs/ --delay 0

  Supported parser types:
      - adr: Architecture Decision Records
      - feature_spec: Feature specifications
      - full_doc: Full document capture (entire markdown content)
      - project_overview: Project overview documents
      - project_doc: General project documentation (CLAUDE.md, README.md)

Options:
  --type TEXT           Force parser type (adr, feature-spec, project-
                        overview)
  -f, --force           Overwrite existing context
  --dry-run             Show what would be added without adding
  --pattern TEXT        Glob pattern for directory (default: **/*.md)
  -v, --verbose         Show detailed processing output
  -q, --quiet           Suppress non-error output
  --delay FLOAT         Inter-episode delay in seconds (default: 0.5, 0 to
                        disable)
  --chunk-size INTEGER  Force chunking for docs above this size in bytes
                        (default: 10240). Use 0 to always chunk.
  --timeout FLOAT       Per-episode timeout in seconds (overrides auto-
                        detected timeout). Use for slow vLLM instances.
  --help                Show this message and exit.
Bash Check graphiti subcommand surface
IN
guardkit graphiti --help 2>&1 | head -40

OUT
Usage: guardkit-py graphiti [OPTIONS] COMMAND [ARGS]...

  Graphiti knowledge graph management commands.

  Manage the Graphiti knowledge graph that provides persistent memory for
  GuardKit sessions.

Options:
  --help  Show this message and exit.

Commands:
  add-context  Add context from files to Graphiti.
  capture      Capture project knowledge through interactive Q&A.
  clear        Clear Graphiti knowledge graph data.
  list         List all knowledge in a category.
  search       Search for knowledge across all categories.
  seed         Seed system context into Graphiti.
  seed-adrs    Seed feature-build ADRs into Graphiti.
  seed-system  Seed template and system content into Graphiti.
  show         Show details of specific knowledge by ID.
  stats        Show graph topology statistics for performance analysis.
  status       Show Graphiti connection and seeding status.
  verify       Verify seeded knowledge with test queries.
Bash Check seed + seed-adrs commands for group control
IN
guardkit graphiti seed --help 2>&1 | head -30 && echo "---" && guardkit graphiti seed-adrs --help 2>&1 | head -30

OUT
Usage: guardkit-py graphiti seed [OPTIONS]

  Seed system context into Graphiti.

  Seeds comprehensive GuardKit knowledge into the Graphiti knowledge graph.
  This includes product knowledge, command workflows, quality gate phases,
  technology stack information, and more.

  Use --template to only seed template-specific categories (templates, agents,
  rules) for the specified template plus 'default'. Without --template, auto-
  detects from manifest.json or seeds all templates.

  Use --force to re-seed even if seeding has already been completed.

  Performance: Local LLMs (e.g., MacBook Pro) are typically ~2x slower
  than GB10 vLLM. Use --timeout to increase the per-episode timeout if
  you see timeout warnings during seeding.

Options:
  -f, --force          Force re-seeding even if already seeded
  -t, --template TEXT  Template to seed (auto-detected if not specified)
  --timeout FLOAT      Per-episode timeout in seconds (overrides auto-detected
                       timeout). Local LLMs are typically ~2x slower than GB10
                       vLLM; try --timeout 300.
  --help               Show this message and exit.
---
Usage: guardkit-py graphiti seed-adrs [OPTIONS]

  Seed feature-build ADRs into Graphiti.

  Seeds critical Architecture Decision Records (ADRs) for feature-build
  workflow. These ADRs encode lessons learned from feature-build failures to
  prevent future sessions from repeating the same mistakes.

  ADRs seeded: - ADR-FB-001: Use SDK query() for task-work invocation - ADR-
  FB-002: Use FEAT-XXX paths in feature mode - ADR-FB-003: Pre-loop must
  invoke real task-work

  Use --force to re-seed even if ADRs have already been seeded.

Options:
  -f, --force  Force re-seeding even if already seeded
  --help       Show this message and exit.
Bash Dry-run a DDR seed to see parser mapping
IN
guardkit graphiti add-context docs/design/decisions/DDR-001-reply-subject-correlation.md --type adr --dry-run 2>&1 | head -30

OUT
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

  ✓ docs/design/decisions/DDR-001-reply-subject-correlation.md (adr)

Dry run complete - Would add:
  1 file, 1 episode

Warnings:
  Warning: docs/design/decisions/DDR-001-reply-subject-correlation.md: Missing 
required section: Status
Bash Dry-run a contract with no --type — check auto-detect
IN
guardkit graphiti add-context docs/design/contracts/API-cli.md --dry-run 2>&1 | head -20

OUT
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

  ✓ docs/design/contracts/API-cli.md (full_doc)

Dry run complete - Would add:
  1 file, 1 episode
Bash Check existing ADR format for Status section shape
IN
head -15 /Users/richardwoollcott/Projects/appmilla_github/forge/docs/architecture/decisions/ADR-ARCH-012-no-mcp-interface.md

OUT
# ADR-ARCH-012: No MCP interface for Forge

## Status

Accepted

- **Date:** 2026-04-18
- **Session:** `/system-arch` Category 4

## Context

Fleet D16 documents that MCP adapters are used for *human-facing* specialist-agent interaction (Claude Desktop), and that *"MCP must NOT carry pipeline traffic — serialises full tool schema into context window on every invocation."* This is an observed cost problem at scale — every MCP tool invocation re-injects the entire tool inventory + schemas into context.

Forge has 11 GuardKit tools + `dispatch_by_capability` + approval + notification + graphiti + history tools (~17–20 tools). Exposing Forge over MCP would send all of these schemas into every tool call's context window. At Forge's build-length scale (200–500 turns), this is catastrophic.
DDRs missing ## Status section header (inline format doesn't satisfy ADR parser). Fixing all 6.

Bash Insert ## Status section at the top of each DDR
IN
python3 - <<'EOF'
import re, pathlib
for p in pathlib.Path("docs/design/decisions").glob("DDR-*.md"):
    txt = p.read_text()
    # Transform "- **Status:** Accepted" inline → "## Status\n\nAccepted\n" section
    new = re.sub(
        r"^(# DDR-[^\n]+\n)\n- \*\*Status:\*\* (\S+)\n",
        r"\1\n## Status\n\n\2\n\n",
        txt,
        count=1,
        flags=re.MULTILINE,
    )
    if new == txt:
        print(f"NO-OP {p}")
        continue
    p.write_text(new)
    print(f"FIXED {p}")
EOF

OUT
FIXED docs/design/decisions/DDR-004-graphiti-group-partitioning.md
FIXED docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md
FIXED docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
FIXED docs/design/decisions/DDR-001-reply-subject-correlation.md
FIXED docs/design/decisions/DDR-005-cli-context-manifest-resolution.md
FIXED docs/design/decisions/DDR-002-resume-value-rehydration-helper.md
All 6 DDRs updated. Retrying seeding with the correct flags.

Bash Re-seed with corrected parser types (full_doc for contracts/models, adr for DDRs)
IN
{
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] SEED-V2-START"
  for f in docs/design/contracts/*.md docs/design/models/*.md; do
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] seeding: $f (type=full_doc)"
    guardkit graphiti add-context "$f" 2>&1
    echo "---end-file---"
  done
  for f in docs/design/decisions/DDR-*.md; do
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] seeding: $f (type=adr)"
    guardkit graphiti add-context "$f" --type adr 2>&1
    echo "---end-file---"
  done
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] SEED-V2-DONE"
} > /tmp/forge-design-seed-v2.log 2>&1

OUT
Command running in background with ID: b9u3j6twg. Output is being written to: /private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-forge/4d1fa0ca-0a86-48c7-a060-6bad55a2b68e/tasks/b9u3j6twg.output
Agent surfaced important detail: 3 of the 4 payloads already exist in nats-core (TASK-NCFA-001) with different signatures — the new task is TASK-NCFA-003 (not 002), and scope is reconciliation + 1 net-new. Updating DDR-001 and API-nats-pipeline-events to reflect this.

Edit DDR-001-reply-subject-correlation.md
Modified
Edit DDR-001-reply-subject-correlation.md
Modified
Edit API-nats-pipeline-events.md
Modified
Edit API-nats-pipeline-events.md
Modified
Waiting on seed completion (ETA ~15–20 min for 20 docs × ~45s each via vLLM).

Bash Check current seed progress
IN
wc -l /tmp/forge-design-seed-v2.log && echo "---" && tail -20 /tmp/forge-design-seed-v2.log && echo "---files-seeded:" && grep -c "^  ✓" /tmp/forge-design-seed-v2.log || true

OUT
      11 /tmp/forge-design-seed-v2.log
---
[2026-04-23T18:18:10Z] SEED-V2-START
[2026-04-23T18:18:10Z] seeding: docs/design/contracts/API-cli.md (type=full_doc)
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

---files-seeded:
0
Meanwhile the seed is in-flight. Providing a clean status:


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 /system-design — FINAL STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artefacts written:         22 files (9 contracts + 5 models + 6 DDRs + 2 C4 L3 diagrams)
Contradiction check:       ✓ No ADR conflicts
C4 L3 review gate:         ✓ Both diagrams approved
nats-core task creation:   ✓ TASK-NCFA-003 created
                              path: nats-core/tasks/backlog/forge-v2-alignment/
                                    TASK-NCFA-003-add-forge-system-design-pipeline-payloads.md
Graphiti seeding:          🔄 IN FLIGHT — background job b9u3j6twg
                              log: /tmp/forge-design-seed-v2.log
                              ETA ~20 min (20 files × ~60s via vLLM)
Key correction from sub-agent's investigation (already applied to docs):

Originally referenced TASK-NCFA-002 in DDR-001 + API-nats-pipeline-events — that ID was already taken (a completed integration-tests task from wave 2 of forge-v2-alignment). Actual new task is TASK-NCFA-003.
Three of the four payloads I specified (StageCompletePayload, BuildPausedPayload, BuildResumedPayload) already exist in nats-core from TASK-NCFA-001 (completed 2026-04-16), but with different field signatures. Only BuildCancelledPayload is truly net-new.
Scope of TASK-NCFA-003: reconcile 3 existing payloads + add 1 new one. Forge carries canonical-shape interim types locally until nats-core ≥ 0.2.0 ships the reconciled shapes.
First seeding attempt failed silently — used a non-existent --group flag from the command template. Corrected to --type adr for DDRs, auto-detect (full_doc) for contracts/models. Groups in .guardkit/graphiti.yaml are inferred from parser type, not a direct CLI option. Also added ## Status section headers to all 6 DDRs so the ADR parser accepts them.

I'll report back with the final seed log once the background job notifies completion.

Rich fast-tracked the nats-core 0.2.0 release — interim carrier retired before creation. Checking seed log.

Bash Summarize seed v2 outcome
IN
echo "---files-seeded:" && grep -c "^  ✓" /tmp/forge-design-seed-v2.log
echo "---final-line:"
tail -5 /tmp/forge-design-seed-v2.log
echo "---errors:"
grep -iE "error|fail|traceback|warning" /tmp/forge-design-seed-v2.log | grep -viE "handle_multiple_group_ids|build_fulltext_query|edge_fulltext_search|edge_bfs_search|WARNING" | head -20
echo "---ok-markers:"
grep -E "✓|Added|episode" /tmp/forge-design-seed-v2.log | head -30

OUT
---files-seeded:
18
---final-line:

Summary:
  Added 1 file, 1 episode
---end-file---
[2026-04-23T20:18:43Z] SEED-V2-DONE
---errors:
  ⚠ docs/design/contracts/API-subagents.md (full_doc) — 1 episode(s) failed
  Failed: 1 episode
Errors:
  Error: docs/design/contracts/API-subagents.md: Episode creation returned None 
(possible silent failure)
episode(s) failed
  Failed: 1 episode
Errors:
  Error: docs/design/decisions/DDR-001-reply-subject-correlation.md: Episode 
creation returned None (possible silent failure)
---ok-markers:
INFO:graphiti_core.graphiti:Completed add_episode in 128337.26572990417 ms
  ✓ docs/design/contracts/API-cli.md (full_doc)
  Added 1 file, 1 episode
INFO:graphiti_core.graphiti:Completed add_episode in 344507.21287727356 ms
  ✓ docs/design/contracts/API-nats-agent-dispatch.md (full_doc)
  Added 1 file, 1 episode
INFO:graphiti_core.graphiti:Completed add_episode in 89977.25081443787 ms
  ✓ docs/design/contracts/API-nats-approval-protocol.md (full_doc)
  Added 1 file, 1 episode
INFO:graphiti_core.graphiti:Completed add_episode in 125122.34592437744 ms
  ✓ docs/design/contracts/API-nats-fleet-lifecycle.md (full_doc)
  Added 1 file, 1 episode
INFO:graphiti_core.graphiti:Completed add_episode in 82546.06890678406 ms
INFO:graphiti_core.graphiti:Completed add_episode in 94540.63963890076 ms
INFO:graphiti_core.graphiti:Completed add_episode in 180718.78623962402 ms
INFO:graphiti_core.graphiti:Completed add_episode in 147333.0271244049 ms
INFO:graphiti_core.graphiti:Completed add_episode in 114758.86797904968 ms
INFO:graphiti_core.graphiti:Completed add_episode in 154782.7010154724 ms
INFO:graphiti_core.graphiti:Completed add_episode in 118007.42793083191 ms
  ✓ docs/design/contracts/API-nats-pipeline-events.md (full_doc)
  Added 1 file, 7 episodes
INFO:graphiti_core.graphiti:Completed add_episode in 253687.10589408875 ms
  ✓ docs/design/contracts/API-sqlite-schema.md (full_doc)
  Added 1 file, 1 episode
  ⚠ docs/design/contracts/API-subagents.md (full_doc) — 1 episode(s) failed
  Added 1 file, 0 episodes
  Failed: 1 episode
INFO:graphiti_core.graphiti:Completed add_episode in 303654.1430950165 ms
  ✓ docs/design/contracts/API-subprocess.md (full_doc)
  Added 1 file, 1 episode
18/20 seeded cleanly. Two failed (API-subagents.md + DDR-001) with "Episode creation returned None" — likely vLLM flakiness. Also API-nats-pipeline-events.md needs re-seeding since Rich edited it post-initial-seed. Retrying the three with --force.

Bash Reseed 2 failed files + 1 Rich-edited file with --force
IN
{
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] RESEED-START"
  guardkit graphiti add-context docs/design/contracts/API-subagents.md --force 2>&1
  echo "---end-file---"
  guardkit graphiti add-context docs/design/contracts/API-nats-pipeline-events.md --force 2>&1
  echo "---end-file---"
  guardkit graphiti add-context docs/design/decisions/DDR-001-reply-subject-correlation.md --type adr --force 2>&1
  echo "---end-file---"
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] RESEED-DONE"
} > /tmp/forge-design-reseed.log 2>&1

OUT
Command running in background with ID: bp6m2pbd0. Output is being written to: /private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-forge/4d1fa0ca-0a86-48c7-a060-6bad55a2b68e/tasks/bp6m2pbd0.output
While reseed runs, noting Rich's key corrections for the record:

DDR-001 supersession banner (2026-04-23):

nats-core 0.2.0 shipped TASK-NCFA-003's work same-day — reconciled + BuildCancelledPayload added.
forge.adapters.nats._interim_payloads.py retired before creation — module never existed.
Payload timestamps ship as str (ISO-8601), not datetime — consumers convert at the edge.
Convention B (per-correlation reply subject) still in force.
API-nats-pipeline-events §3.2 matched — imports directly from nats_core.events.pipeline; str timestamp fields on all four new payloads.

Forge-internal types (Build, StageLogEntry, GateDecision in the data models) still use datetime — those are in-process, not wire payloads — so no changes needed there.

Waiting for reseed completion notification.

Bash Check reseed outcomes
IN
grep -E "^\[|✓|⚠|Error|Added|Failed" /tmp/forge-design-reseed.log | head -30

OUT
[2026-04-23T20:19:18Z] RESEED-START
  ✓ docs/design/contracts/API-subagents.md (full_doc)
  Added 1 file, 1 episode
  ✓ docs/design/contracts/API-nats-pipeline-events.md (full_doc)
  Added 1 file, 7 episodes
  ✓ docs/design/decisions/DDR-001-reply-subject-correlation.md (adr)
  Added 1 file, 1 episode
[2026-04-23T20:40:28Z] RESEED-DONE
All three reseeded cleanly.

Update Todos

Load context files (forge arch + nats-core spec/contract + refresh idea)

Identify design units (containers, not DDD bounded contexts) to design

Confirm scope + protocols with Rich (interactive)

Write API contracts (9 files)

Write data models (5 files)

Run contradiction detection against existing ADRs

Write DDRs (6 files)

Write C4 L3 diagrams (Agent Runtime + Domain Core)

C4 L3 review gate with Rich

Seed 20 artefacts into Graphiti (18+3 retries = 20 unique + 1 Rich-edited refresh)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ /system-design — DONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Artefacts:       22 files in docs/design/ — all clean on disk
Graphiti:        20/20 seeded ✓ (retry pass recovered 2 vLLM flakes;
                 API-nats-pipeline-events re-seeded with your 0.2.0 edit)
Total episodes:  ~27 (API-nats-pipeline-events chunked into 7)
nats-core task:  TASK-NCFA-003 in nats-core/tasks/backlog/forge-v2-alignment/
                 — already shipped same-day via your 0.2.0 release
                 → DDR-001 supersession banner + API-nats-pipeline-events §3.2
                   reflect reality: no interim carrier needed.
State of the repo right now (docs/design/):

9 API contracts + 5 data models queryable via guardkit graphiti search on project_design / architecture_decisions groups.
6 DDRs with ## Status section headers (ADR-parser-compatible).
2 C4 L3 diagrams approved + on disk (not seeded — visual, linked from C4 L2).
Forge-internal types continue to use datetime; only the four nats-core 0.2.0 wire payloads use str ISO-8601.
Suggested next moves:

Commit the docs/design/ tree + the history file change when ready.
Feed this into /feature-plan when you're ready to carve Forge into implementable features.
The only documentary gap I noticed: docs/history/system-design-history.md (opened in your IDE) — I didn't append a session entry. Say the word if you want one.
command-history.md
please commit
Bash Show working tree status
IN
git status

OUT
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   .guardkit/graphiti-query-log.jsonl
	modified:   docs/architecture/assumptions.yaml
	modified:   docs/history/command-history.md
	modified:   pyproject.toml

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/design/
	docs/history/system-design-history.md

no changes added to commit (use "git add" and/or "git commit -a")
Bash Show changed-file summary
IN
git diff --stat

OUT
 .guardkit/graphiti-query-log.jsonl |   52 ++
 docs/architecture/assumptions.yaml |    4 +-
 docs/history/command-history.md    | 1746 ++++++++++++++++++++++++++++++++++++
 pyproject.toml                     |    1 +
 4 files changed, 1801 insertions(+), 2 deletions(-)
Bash Show recent commit message style
IN
git log --oneline -10

OUT
79589c5 chore(tasks): complete TASK-ADR-REVISE-021-E7B3 — ADR-021 Revision 10 shipped
37a4e48 updated config
0a40b25 docs(adr-021): Revision 10 — server-mode interrupt rehydration (Option C)
f387ca6 spike(deepagents-053): close ASSUM-009 server-mode gap — FAIL verdict, spawn ADR-021 revision
a0f7053 chore(tasks): complete TASK-CHORE-E4A1 — pyproject pin alignment
64f2f4f chore(pyproject): align deepagents pin with ADR-ARCH-020 (TASK-CHORE-E4A1)
70e6d21 spike(deepagents-053): verify ASSUM-008 permissions + ASSUM-009 interrupt round-trip (TASK-SPIKE-C1E9)
3a6babc docs/tasks: close TASK-REV-A7D3 §1–§4; spawn TASK-SPIKE-C1E9; archive TASK-DOC-B2A4
7bcc7da review and refinements of architecture
9f41e22 Ran system-arch
Bash Inspect tracked file diffs
IN
git diff pyproject.toml docs/architecture/assumptions.yaml

OUT
diff --git a/docs/architecture/assumptions.yaml b/docs/architecture/assumptions.yaml
index 325309a..4ebd419 100644
--- a/docs/architecture/assumptions.yaml
+++ b/docs/architecture/assumptions.yaml
@@ -35,9 +35,9 @@ assumptions:
 
   - id: ASSUM-004
     category: fleet
-    description: "nats-core library (v0.1+) published and pip-installable from sibling repo with AgentManifest, NATSKVManifestRegistry, typed payloads, Topics registry"
+    description: "nats-core library (v0.2.0) published and pip-installable from sibling repo with AgentManifest, NATSKVManifestRegistry, typed payloads (incl. reconciled StageComplete/BuildPaused/BuildResumed + BuildCancelledPayload, all with ISO-8601 str timestamps), Topics registry"
     confidence: high
-    source: nats-core repo at 98% test coverage
+    source: nats-core repo — TASK-NCFA-003 shipped 2026-04-23, 761/761 tests passing, 98% coverage
     related_adr: ADR-ARCH-015
 
   - id: ASSUM-005
diff --git a/pyproject.toml b/pyproject.toml
index ccf0814..eb890a0 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -14,6 +14,7 @@ dependencies = [
     "langgraph>=0.2",
     "langchain-community>=0.3",
     "langchain-anthropic>=0.2",
+    "nats-core>=0.2.0,<0.3",
     "python-dotenv>=1.0",
     "pyyaml>=6.0",
 ]
Bash Inspect new history file
IN
head -20 docs/history/system-design-history.md && echo "----" && wc -l docs/history/system-design-history.md

OUT
----
       0 docs/history/system-design-history.md
Bash Sample of command-history diff
IN
git diff docs/history/command-history.md | head -40

OUT
diff --git a/docs/history/command-history.md b/docs/history/command-history.md
index b522cbe..9192191 100644
--- a/docs/history/command-history.md
+++ b/docs/history/command-history.md
@@ -256,3 +256,1749 @@ docs/tasks: close TASK-REV-A7D3 §1–§4; spawn TASK-SPIKE-C1E9; archive TASK-D
 Run TASK-SPIKE-C1E9 when you want to unblock /system-design. It's ~1–2 hours, fully scoped, and has a self-contained execution checklist in .claude/reviews/TASK-REV-A7D3-review-report.md §5.
 Do not run /system-design until TASK-SPIKE-C1E9 lands its findings file at docs/research/ideas/deepagents-053-verification.md.
 
+/task-work TASK-SPIKE-C1E9
+
+TASK-SPIKE-D2F7 is done. Summary:
+
+Verdict: FAIL on type fidelity, PASS on control flow. Under langgraph dev, pause + resume mechanics work end-to-end, but the node observes the resumed value as a plain dict — isinstance(..., ApprovalDecision) is False, nested Pydantic/UUID/datetime fields do not survive the HTTP/msgpack layer.
+
+What changed:
+
+spikes/deepagents-053/langgraph.json + module-level graph export on interrupt_graph.py:134
+New driver spikes/deepagents-053/interrupt_server_drive.py
+Full row-for-row comparison in deepagents-053-verification.md §Server-mode closeout
+ADR-ARCH-021 References line flags the FAIL + links the revision task
+New backlog task TASK-ADR-REVISE-021-E7B3 with three option paths (A: explicit .model_validate; B: allowed_msgpack_modules; C: hybrid)
+D2F7 moved to in_review with Implementation Notes populated
+Committed as f387ca6
+Next: /system-design remains blocked on TASK-ADR-REVISE-021-E7B3, not on this spike.
+
+/task-review TASK-ADR-REVISE-021-E7B3
+
+
+Review Report: TASK-ADR-REVISE-021-E7B3
+Mode: decision (task carries decision_required: true)
+Depth: standard
+Scope: choose between Option A / B / C for ADR-ARCH-021 revision, and confirm the ADR edits the revision must carry.
+
+Situation recap
+D2F7 established that under langgraph dev (the canonical Forge deployment per ADR-021 itself), interrupt()'s return value is a plain dict, not the typed ApprovalResponsePayload the ADR's code snippet assumes. Control-flow is fine; type fidelity is not. The ADR's snippet is wrong-as-written and must be revised before /system-design proceeds.
+
+Option evaluation
+Criterion	A: explicit rehydrate	B: allowed_msgpack_modules	C: Hybrid (A now, B later)
+Unblocks /system-design today	✅	❌ (needs re-spike)	✅
+New infra	None	Serde registration module	None now
Bash Check history directory layout
IN
ls -la docs/history/

OUT
total 560
drwxr-xr-x   5 richardwoollcott  staff     160 Apr 23 18:07 .
drwxr-xr-x  10 richardwoollcott  staff     320 Apr 23 18:15 ..
-rw-r--r--   1 richardwoollcott  staff  108554 Apr 23 20:52 command-history.md
-rw-r--r--   1 richardwoollcott  staff  174238 Apr 19 12:05 system-arch-history.md
-rw-r--r--   1 richardwoollcott  staff       0 Apr 23 18:07 system-design-history.md
system-design-history.md is an empty placeholder (0 bytes). Excluding it from the commit — empty files are messy. Staging everything else.

Bash Stage 22 design artefacts + 4 related files; show what's staged
IN
git add \
  docs/design/contracts/API-cli.md \
  docs/design/contracts/API-nats-agent-dispatch.md \
  docs/design/contracts/API-nats-approval-protocol.md \
  docs/design/contracts/API-nats-fleet-lifecycle.md \
  docs/design/contracts/API-nats-pipeline-events.md \
  docs/design/contracts/API-sqlite-schema.md \
  docs/design/contracts/API-subagents.md \
  docs/design/contracts/API-subprocess.md \
  docs/design/contracts/API-tool-layer.md \
  docs/design/models/DM-build-lifecycle.md \
  docs/design/models/DM-calibration.md \
  docs/design/models/DM-discovery.md \
  docs/design/models/DM-gating.md \
  docs/design/models/DM-graphiti-entities.md \
  docs/design/decisions/DDR-001-reply-subject-correlation.md \
  docs/design/decisions/DDR-002-resume-value-rehydration-helper.md \
  docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md \
  docs/design/decisions/DDR-004-graphiti-group-partitioning.md \
  docs/design/decisions/DDR-005-cli-context-manifest-resolution.md \
  docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md \
  docs/design/diagrams/agent-runtime.md \
  docs/design/diagrams/domain-core.md \
  docs/architecture/assumptions.yaml \
  docs/history/command-history.md \
  pyproject.toml \
  .guardkit/graphiti-query-log.jsonl
git status --short

OUT
M  .guardkit/graphiti-query-log.jsonl
M  docs/architecture/assumptions.yaml
A  docs/design/contracts/API-cli.md
A  docs/design/contracts/API-nats-agent-dispatch.md
A  docs/design/contracts/API-nats-approval-protocol.md
A  docs/design/contracts/API-nats-fleet-lifecycle.md
A  docs/design/contracts/API-nats-pipeline-events.md
A  docs/design/contracts/API-sqlite-schema.md
A  docs/design/contracts/API-subagents.md
A  docs/design/contracts/API-subprocess.md
A  docs/design/contracts/API-tool-layer.md
A  docs/design/decisions/DDR-001-reply-subject-correlation.md
A  docs/design/decisions/DDR-002-resume-value-rehydration-helper.md
A  docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
A  docs/design/decisions/DDR-004-graphiti-group-partitioning.md
A  docs/design/decisions/DDR-005-cli-context-manifest-resolution.md
A  docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md
A  docs/design/diagrams/agent-runtime.md
A  docs/design/diagrams/domain-core.md
A  docs/design/models/DM-build-lifecycle.md
A  docs/design/models/DM-calibration.md
A  docs/design/models/DM-discovery.md
A  docs/design/models/DM-gating.md
A  docs/design/models/DM-graphiti-entities.md
M  docs/history/command-history.md
M  pyproject.toml
?? docs/history/system-design-history.md
Bash Commit and verify success
IN
git commit -m "$(cat <<'EOF'
docs(design): /system-design pass 1 — 22 artefacts + nats-core 0.2.0 alignment

First /system-design pass for Forge. Generated against ARCHITECTURE.md +
ADR set + nats-core spec + agent-manifest contract + pipeline-orchestrator
refresh. NOT DDD — design is per-container (C4 L2), not per-bounded-context.

Artefacts (docs/design/):
  - 9 API contracts: NATS pipeline events / agent dispatch / approval
    protocol / fleet lifecycle, plus CLI, SQLite schema, tool layer,
    subagents, subprocess.
  - 5 data models: build lifecycle, gating, calibration, discovery,
    Graphiti entities.
  - 6 DDRs: reply-subject correlation, resume_value_as helper placement,
    SQLite WAL+STRICT, Graphiti group partitioning, context-manifest
    resolution, async-subagent state-channel contract.
  - 2 C4 L3 diagrams: Agent Runtime + Domain Core (both reviewed +
    approved).

Skipped (per ADRs): no OpenAPI / MCP / A2A — Forge is NATS-native,
  CLI for human ops, no HTTP surface (ADR-ARCH-012, -ARCH-003).

Coupling changes:
  - pyproject.toml: pin nats-core>=0.2.0,<0.3
  - assumptions.yaml ASSUM-004: nats-core 0.2.0 + TASK-NCFA-003 shipped
    (reconciled StageComplete/BuildPaused/BuildResumed + new
    BuildCancelledPayload — all timestamps str ISO-8601). Interim
    payload-carrier module retired before creation; DDR-001 supersession
    banner records the resolution.

Persistence:
  - All 20 design artefacts seeded into Graphiti (project_design +
    architecture_decisions groups). Diagrams not seeded (visual; linked
    from C4 L2).

Sibling task: nats-core TASK-NCFA-003 (created via task-manager agent).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git status

OUT
[main b40365c] docs(design): /system-design pass 1 — 22 artefacts + nats-core 0.2.0 alignment
 26 files changed, 5515 insertions(+), 2 deletions(-)
 create mode 100644 docs/design/contracts/API-cli.md
 create mode 100644 docs/design/contracts/API-nats-agent-dispatch.md
 create mode 100644 docs/design/contracts/API-nats-approval-protocol.md
 create mode 100644 docs/design/contracts/API-nats-fleet-lifecycle.md
 create mode 100644 docs/design/contracts/API-nats-pipeline-events.md
 create mode 100644 docs/design/contracts/API-sqlite-schema.md
 create mode 100644 docs/design/contracts/API-subagents.md
 create mode 100644 docs/design/contracts/API-subprocess.md
 create mode 100644 docs/design/contracts/API-tool-layer.md
 create mode 100644 docs/design/decisions/DDR-001-reply-subject-correlation.md
 create mode 100644 docs/design/decisions/DDR-002-resume-value-rehydration-helper.md
 create mode 100644 docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
 create mode 100644 docs/design/decisions/DDR-004-graphiti-group-partitioning.md
 create mode 100644 docs/design/decisions/DDR-005-cli-context-manifest-resolution.md
 create mode 100644 docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md
 create mode 100644 docs/design/diagrams/agent-runtime.md
 create mode 100644 docs/design/diagrams/domain-core.md
 create mode 100644 docs/design/models/DM-build-lifecycle.md
 create mode 100644 docs/design/models/DM-calibration.md
 create mode 100644 docs/design/models/DM-discovery.md
 create mode 100644 docs/design/models/DM-gating.md
 create mode 100644 docs/design/models/DM-graphiti-entities.md
On branch main
Your branch is ahead of 'origin/main' by 2 commits.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/history/system-design-history.md

nothing added to commit but untracked files present (use "git add" to track)
Committed as b40365c — 26 files, +5515 lines. Branch now 2 ahead of origin/main.

Left untracked: docs/history/system-design-history.md (empty placeholder you opened in the IDE). Say if you want me to populate + amend, or just git add it as-is.