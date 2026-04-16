# Forge — Software Factory Pipeline Architecture

> **Version:** 2.2
> **Date:** 16 April 2026
> **Status:** Architecture Design — Ready to Build
> **Supersedes:** v2.1 (15 April 2026)
> **Supersedes:** dev-pipeline-architecture.md v1.0 (February 2026)
> **Supersedes:** dev-pipeline-system-spec.md v1.0 (February 2026)
> **Supersedes:** dev-pipeline-architecture-v2.md (earlier April 2026 draft)
> **Alignment review:** TASK-REV-A1F2 / docs/research/forge-build-plan-alignment-review.md

---

## Why This Document Exists

The February 2026 architecture was designed around a PM Adapter model: Linear webhooks fired `ready-for-dev` events, a bidirectional PM Adapter bridged NATS and Linear, and the build trigger was "James moves a ticket on a Kanban board." This created a dependency on exactly the kind of coordination tooling that the Software Factory thesis argues is a category error.

An earlier April draft introduced a v0 (subprocess) / v1 (NATS) phasing that assumed NATS infrastructure wouldn't be ready. That assumption is now invalid — NATS infrastructure and nats-core repos are on the GB10 and being stood up. Building a subprocess orchestrator only to replace it with NATS is wasted effort.

This document is the single, buildable architecture for the Forge. There is no phased transport swap. The Forge talks NATS from day one.

### What Changed from v2.1 → v2.2

| Aspect | v2.1 | v2.2 (this revision) |
|--------|------|----------------------|
| **Build trigger sources** | CLI only (`forge queue`) | CLI, Jarvis, future notification adapters (§5.0) |
| **Specialist-agent deployment** | Roles listed, deployment implicit | Explicit dual-role model: PO + Architect as separate instances (§3.1) |
| **Stream list** | 3 streams (PIPELINE, AGENTS, SYSTEM) | 6 streams — adds FLEET, JARVIS, NOTIFICATIONS (§3) |
| **Stream retention** | PIPELINE 30d, SYSTEM 24h | PIPELINE 7d, SYSTEM 1h — matches nats-infrastructure (§3) |
| **Topic naming** | `agents.commands.*` / `agents.results.*` (plural) | `agents.command.*` / `agents.result.*` (singular) — matches nats-core (§7) |
| **`BuildQueuedPayload`** | Minimal (`triggered_by: str`) | Jarvis-aware with `originating_adapter`, `correlation_id`, `parent_request_id` (§7) |
| **ADRs** | SP-010..013 | SP-014..017 added and accepted (§9) |

### What Changed from February 2026

| Aspect | February 2026 | April 2026 (this doc) |
|--------|---------------|------------------------|
| **Build trigger** | Linear webhook → PM Adapter → `ready-for-dev` → Build Agent | CLI publishes `pipeline.build-queued` to JetStream |
| **PM integration** | Critical path — bidirectional Linear sync | **Removed** — optional notification adapter (future) |
| **`ready-for-dev` event** | Core pipeline event | **Removed** — replaced by `pipeline.build-queued` |
| **PM Adapter component** | Required service in Docker Compose | **Removed** |
| **RequireKit NATS** | Publishes `feature-planned` events | **Removed** — RequireKit deprecated |
| **Durable queue** | JetStream via PM Adapter trigger | JetStream via CLI trigger (direct) |
| **Build history** | Not specified | SQLite state journal (`~/.forge/forge.db`) |
| **Orchestrator** | Build Agent (NATS subscriber) | Forge (NATS-native, confidence-gated) |
| **Agent communication** | Not specified (GuardKit subprocess only) | NATS commands to specialist agents |
| **Actors** | Rich, James (Linear), Mark (Linear) | Rich (CLI/Forge), James (PR review), Mark (PR review) |

### What Stayed

- NATS JetStream as the messaging backbone
- Sequential single-threaded builds (ADR-SP-005)
- GuardKit as CLI tool invoked as subprocess (ADR-SP-003)
- Graphiti for knowledge, not orchestration (ADR-SP-004)
- nats-core as shared contract layer
- Local-first execution on GB10
- Multi-tenancy via NATS accounts (future, when needed)

---

## 1. Core Workflow

```
Claude Desktop (ideation + architecture)
    ↓
/feature-spec (Gherkin + assumptions — propose-review cycle)
    ↓  Rich reviews (~5-10 mins, curating not authoring)
    ↓
/feature-plan --from-spec (decomposes into AutoBuild tasks + waves)
    ↓
forge queue FEAT-XXX (publishes to JetStream)
    ↓  sequential execution — one feature at a time
    ↓
Forge consumes from JetStream, runs pipeline stages:
    ↓  specialist agents called via NATS commands
    ↓  confidence-gated checkpoints at each stage
    ↓  🟢 auto-approve | 🟡 flag for review | 🔴 hard stop
    ↓
GuardKit AutoBuild (Player-Coach loop, up to 5 turns per task)
    ↓  Graphiti context retrieval + structured uncertainty handling
    ↓
PR created on GitHub
    ↓
Rich reviews PR, merges
```

There is no Kanban board in this flow. There is no ticket. The feature YAML spec, the Gherkin scenarios, and the assumptions manifest *are* the tracking artefacts. The PR is the outcome gate. James and Mark see PRs, not tickets.

---

## 2. Design Principles

1. **NATS-Native Orchestration.** The Forge is a NATS consumer. Builds are queued by publishing to JetStream. Specialist agents are invoked via NATS commands. No subprocess orchestration layer, no transport abstraction — NATS is the transport.

2. **CLI-Triggered, Event-Driven.** Rich triggers builds via CLI (`forge queue`), which publishes to JetStream. The Forge consumes events and runs the pipeline. No external webhooks in the critical path.

3. **Opt-In Integration.** GuardKit works standalone without NATS or the Forge. `guardkit autobuild feature FEAT-XXX` runs locally with zero infrastructure. The Forge adds orchestration, queuing, and confidence gating on top.

4. **Local-First Execution.** All computation runs on GB10 + MacBook Pro via Tailscale. No cloud bills during development.

5. **Sequential Builds.** One AutoBuild at a time. If the Forge has multiple features queued in JetStream, they execute in order. This avoids rate limit contention (whether using local vLLM or Anthropic API), git operation conflicts, and NATS event interleaving. Higher latency is acceptable; reliability is not negotiable.

6. **Confidence-Gated Checkpoints.** The Forge evaluates Coach scores at each pipeline stage against configurable thresholds. Three modes:
   - 🟢 **Auto-approve** — Coach score above threshold, proceed automatically
   - 🟡 **Flag for review** — Coach score in uncertain range, Rich reviews before proceeding
   - 🔴 **Hard stop** — Coach score below threshold or critical detection pattern triggered

7. **Structured Documents as Project Management.** Feature YAML specs, Gherkin scenarios, assumptions manifests, and PRs replace tickets, boards, and status reports. The coordination layer is emergent from the pipeline, not maintained alongside it.

8. **Composability with Ship's Computer.** The Forge is an agent in the fleet. The `pipeline.*` topic namespace sits alongside `agents.*`. Specialist agents (Architect, Product Owner, Ideation) feed into the Forge; the Forge feeds into GuardKit.

---

## 3. Repository Architecture

### Repository Map

```
guardkit/
├── nats-core           — Shared message schemas, topic registry, Python client
├── nats-infrastructure — NATS server deployment (Docker Compose on GB10)
├── guardkit            — AI software factory CLI (AutoBuild, slash commands)
├── forge               — Pipeline orchestrator (NATS-native, confidence-gated)
└── specialist-agent    — Unified agent harness (Architect, PO, Ideation, UX)
```

**Removed from scope:**
- `requirekit` — deprecated for Rich's workflow; `/feature-spec` in GuardKit replaces it
- PM Adapters — not in critical path; optional future notification adapter only
- `dev-pipeline` as a monolith — split into `forge` (orchestration) and `nats-infrastructure` (deployment)

### Component Responsibilities

#### `nats-core` — Shared Contract Layer

Pydantic message schemas, topic registry, thin NATS client. Every participant depends on this. Slow change velocity, semver versioned.

**Revisions for Forge:** Remove `PMAdapter` base class. Remove `ReadyForDevPayload`. Add `BuildQueuedPayload` (CLI-triggered). Add `BuildPausedPayload` (confidence gate). Remove adapter interface definitions.

#### `nats-infrastructure` — NATS Server Deployment

Docker Compose for NATS with JetStream on GB10. Account configuration, persistence policies, stream definitions. Separated from orchestration logic.

**Key streams:**
- `PIPELINE` — `pipeline.*` events, **7-day retention** (SQLite is the durable build history per ADR-SP-013; JetStream only needs to cover realistic crash-recovery windows)
- `AGENTS` — `agents.*` events, 7-day retention
- `FLEET` — `fleet.*` agent registration and heartbeat events (how `fleet.register` persists; watched by Jarvis for CAN-bus discovery)
- `JARVIS` — `jarvis.*` session, dispatch, and notification events
- `NOTIFICATIONS` — `notifications.*` outbound adapter events (Phase 5 notification adapters)
- `SYSTEM` — `system.*` health and config, **1-hour retention** (ephemeral health pings)

`FINPROXY` is provisioned in `nats-infrastructure` but remains out of this anchor (tenant-specific).

See ADR-SP-017 (§9) for the retention reconciliation decision.

#### `guardkit` — AI Software Factory CLI (existing, evolving)

AutoBuild Player-Coach loop, quality gates, `/system-arch`, `/system-design`, `/feature-spec`, `/feature-plan` commands. Graphiti integration. Template-driven stack patterns.

**Integration with Forge:** Optional `--nats` flag publishes `build-progress`, `build-complete`, `build-failed` events. GuardKit does not subscribe to NATS. Zero regression for standalone use.

#### `forge` — Pipeline Orchestrator (new)

The Forge is the operational heart of the Software Factory. It is a long-running NATS consumer that coordinates the pipeline from feature spec through to PR, applying confidence-gated checkpoints at each stage.

**Core capabilities:**
- Subscribes to JetStream `PIPELINE` stream for `pipeline.build-queued.*` events
- Processes builds sequentially — one at a time, FIFO order
- Calls specialist agents via NATS commands (`agents.command.{agent_id}`)
- Invokes GuardKit AutoBuild as subprocess with `--nats` flag
- Evaluates Coach scores at each stage against configurable thresholds
- Publishes pipeline progress, completion, failure, and pause events
- Manages git operations (clone/pull/branch/push/PR)
- Persists build history and stage log to SQLite (`~/.forge/forge.db`)
- Crash recovery on startup via JetStream redelivery + SQLite state reconciliation

#### `specialist-agent` — Unified Agent Harness (existing)

Single binary, multiple roles via `agent-role.yaml` + fine-tuned model + role-specific RAG. Roles: Architect, Product Owner, Ideation, UX Designer.

Subscribes to NATS commands (`agents.command.{agent_id}`), publishes results to `agents.result.{agent_id}`. The Forge sends commands and awaits results via NATS request-reply or pub-sub with correlation IDs.

### 3.1 Specialist Agent Deployment Model

The Forge's early pipeline stages call two distinct specialist agents by role: **Product Owner** (Stage 1 / Specification Review) and **Architect** (Stage 2 / Architecture Review). Both are deployments of the same `specialist-agent` binary with different `--role` flags and distinct `agent_id`s:

- **Product Owner** — `agent_id=product-owner-agent`
- **Architect** — `agent_id=architect-agent`

The `agent_id` is derived from the role by default (`{role_id}-agent`) or overridable via the `SPECIALIST_AGENT_ID` environment variable for tests and non-standard deployments.

Both register on `fleet.register` independently, subscribe to their own `agents.command.{agent_id}` topic, and publish results to `agents.result.{agent_id}`. Result payloads are wrapped in the Forge-compatible shape at the `specialist-agent` boundary:

```python
{
    "role_id": str,                   # e.g. "product-owner", "architect"
    "coach_score": float,             # 0.0–1.0
    "criterion_breakdown": dict,      # per-criterion scores
    "detection_findings": list,       # structured detection results
    "role_output": dict               # role-specific Pydantic-serialised output
}
```

Forge does not translate per-role output types — the `specialist-agent` is responsible for shaping its result into this contract. This deployment model is the validation target for `specialist-agent` Phase 3.

See ADR-SP-015 (§9) for the full decision record and consequences.

---

## 4. Pipeline Stages and Confidence Gating

The Forge manages a feature through these stages. Each stage has a configurable confidence threshold.

```
QUEUED (in JetStream — awaiting processing)
  ↓
STAGE 1: Specification Review
  Forge verifies /feature-spec outputs exist and are complete
  Gate: Assumptions manifest has no unresolved low-confidence items
  ↓
STAGE 2: Architecture Review (optional — calls Architect Agent via NATS)
  Specialist agent evaluates feasibility, produces ADRs
  Gate: Coach score on architecture output ≥ threshold
  ↓
STAGE 3: Feature Planning
  /feature-plan --from-spec decomposes into tasks + waves
  Gate: Task decomposition passes complexity checks
  ↓
STAGE 4: AutoBuild Execution
  GuardKit autobuild — Player-Coach loop, sequential tasks
  Gate: Per-task Coach validation, structured uncertainty handling
  ↓
STAGE 5: PR Creation
  Push branch, create PR via GitHub CLI
  Gate: All quality gates pass (lint, type check, tests, coverage)
  ↓
COMPLETE → Rich reviews PR
```

### Confidence Threshold Configuration

```yaml
# forge.yaml (per-project or global)
confidence_thresholds:
  specification_review:
    auto_approve: 0.8    # 🟢 Above this: proceed
    flag_for_review: 0.5  # 🟡 Between flag and auto: Rich reviews
    # Below flag_for_review: 🔴 hard stop
  architecture_review:
    auto_approve: 0.75
    flag_for_review: 0.5
  autobuild:
    auto_approve: 0.8
    flag_for_review: 0.6
  quality_gates:
    auto_approve: 1.0    # All gates must pass — no partial approval
    flag_for_review: 0.8

build_config:
  max_concurrent: 1       # Sequential builds only
  max_turns_per_task: 5   # AutoBuild Player-Coach turns before escalation
  sdk_timeout: 1800       # 30 minutes per AutoBuild invocation

degraded_mode:
  no_coach_score: "flag_for_review"  # If Coach unavailable, never auto-approve
  no_specialist: "flag_for_review"   # If specialist agent unavailable, skip stage but flag
```

---

## 5. Build Queue

### 5.0 Build Request Sources

Builds enter JetStream as `pipeline.build-queued.{feature_id}` messages. There are three supported sources:

1. **CLI** — `forge queue FEAT-XXX` publishes directly. The default and simplest path.
2. **Jarvis** — When Rich interacts with Jarvis (voice via Reachy Mini, Telegram, dashboard, CLI wrapper), Jarvis classifies the intent, discovers Forge via the `fleet.register` / `agent-registry` KV, and publishes `BuildQueuedPayload` with `triggered_by="jarvis"` and `originating_adapter=<voice-reachy|telegram|slack|dashboard|cli-wrapper>`. Forge consumes the same topic as for CLI.
3. **Future notification adapters** — Slack, email, GitHub webhook (out of Phase 4 scope).

Forge does not distinguish between sources at the consumer level. The payload carries source metadata (`triggered_by`, `originating_adapter`, `correlation_id`) for history, diagnostics, and routing progress events back to the originator.

Discoverability is handled by Forge registering on `fleet.register` as an agent (`agent_id=forge`, intents: `build.*`, `pipeline.*`, `max_concurrent=1`), so Jarvis's CAN-bus routing can surface it. Registration is for discovery; triggering remains a JetStream publish.

See ADR-SP-014 (§9) for the full decision record and pattern evaluation.

### Trigger Mechanism

Builds are triggered by CLI command, which publishes to JetStream:

```bash
# Queue a single feature (publishes to JetStream)
forge queue FEAT-XXX --repo guardkit/lpa-platform --branch main

# Queue multiple features (each published as separate JetStream message, executed sequentially)
forge queue FEAT-001 FEAT-002 FEAT-003 --repo guardkit/lpa-platform

# Check queue status (current build + pending in JetStream + paused)
forge status

# View build history from SQLite (completed, failed, interrupted)
forge history
forge history --feature FEAT-XXX   # detailed stage log for a specific build

# Cancel a queued (not yet running) build
forge cancel FEAT-XXX

# Skip an interrupted build (acknowledge in JetStream, move to next)
forge skip FEAT-XXX
```

### Queue Architecture

**JetStream owns the queue.** Each `forge queue` command publishes a `pipeline.build-queued.{feature_id}` message to the `PIPELINE` JetStream stream. The Forge runs a pull-based consumer with `AckWait` — it pulls one message, processes the build, and only acknowledges on completion (or explicit skip/cancel). If the Forge crashes, JetStream redelivers the unacknowledged message after the `AckWait` timeout.

**SQLite owns the history.** Build outcomes, per-stage Coach scores, durations, and error details are written to `~/.forge/forge.db`. This serves `forge status`, `forge history`, and future dashboard queries. SQLite is not the queue — JetStream is.

### Build History Schema (SQLite)

```sql
-- Build state and outcomes (one row per feature build attempt)
CREATE TABLE builds (
    build_id      TEXT PRIMARY KEY,   -- Unique per execution attempt
    feature_id    TEXT NOT NULL,
    repo          TEXT NOT NULL,
    branch        TEXT NOT NULL DEFAULT 'main',
    feature_yaml  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'RUNNING',
        -- RUNNING | PAUSED | FINALISING
        -- | COMPLETE | FAILED | INTERRUPTED | CANCELLED | SKIPPED
    current_stage TEXT,               -- Which pipeline stage (1-5)
    coach_score   REAL,              -- Last Coach score (for gating)
    config        TEXT,              -- JSON: max_turns, sdk_timeout, etc.
    started_at    TEXT NOT NULL,      -- ISO 8601
    completed_at  TEXT,
    pr_url        TEXT,
    error         TEXT
);

-- Per-stage log (one row per stage completion)
CREATE TABLE stage_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id      TEXT NOT NULL,
    feature_id    TEXT NOT NULL,
    stage         TEXT NOT NULL,
    status        TEXT NOT NULL,      -- PASSED | FAILED | GATED | SKIPPED
    coach_score   REAL,
    duration_secs REAL,
    details       TEXT,              -- JSON: gate details, Coach feedback
    completed_at  TEXT NOT NULL,
    FOREIGN KEY (build_id) REFERENCES builds(build_id)
);
```

### Crash Recovery

If the Forge process crashes or the GB10 loses power mid-build:

1. **JetStream redelivers.** The unacknowledged `build-queued` message is redelivered after `AckWait` timeout. The Forge receives it again on restart.
2. **SQLite reconciliation.** On startup, the Forge checks SQLite for any build with status RUNNING or PREPARING. These are transitioned to INTERRUPTED.
3. **Fresh start.** When the redelivered message is processed, the Forge detects the INTERRUPTED record in SQLite and starts the feature from scratch (fresh git checkout, stage 1).

Rich can intervene:
- Let it retry automatically (default — JetStream redelivers)
- Skip it: `forge skip FEAT-XXX` (acknowledges the JetStream message, marks as SKIPPED in SQLite)
- Cancel it: `forge cancel FEAT-XXX` (acknowledges and marks as CANCELLED)

**Why retry from scratch rather than resume:** A partially-completed AutoBuild may have written files, created partial commits, or left the working tree dirty. Resuming mid-stage risks building on an inconsistent foundation. Starting fresh is slower but safe — consistent with the factory's "quality over speed" principle.

**PAUSED state survives restart.** If the Forge was paused awaiting human review, the JetStream message remains unacknowledged. On restart, the Forge reads the PAUSED status from SQLite and re-enters the paused state rather than restarting the build.

### Sequential Execution Rationale

Running one AutoBuild at a time is a deliberate constraint, not a limitation:

1. **LLM rate limits.** Whether using local vLLM on GB10 or Anthropic API, concurrent builds risk hitting rate limits or degrading inference throughput. Local vLLM on GB10 serves one model at a time for AutoBuild (port 8002).
2. **Git operation safety.** Concurrent builds against the same repo require complex branch management. Sequential builds keep git operations simple.
3. **Graphiti contention.** The knowledge graph is shared across builds. Concurrent writes during entity extraction could cause conflicts (sequential seeding is already a proven requirement).
4. **Debuggability.** When a build fails, Rich needs clear, isolated logs. Interleaved output from concurrent builds makes diagnosis harder.
5. **Quality over speed.** The factory's value proposition is reliable output, not fast output. A 30-minute build that produces a clean PR is better than two 20-minute builds that produce conflicting changes.

---

## 6. Forge State Machine

```
             ┌──────────────────┐
  ┌──────────│   IDLE           │←──────────────────┐
  │          │   (no pending    │                    │
  │          │    messages)     │                    │
  │          └────────┬─────────┘                    │
  │                   │ JetStream delivers           │
  │                   │ build-queued message          │
  │                   ▼                              │
  │          ┌──────────────────┐                    │
  │          │  PREPARING       │                    │
  │          │  - git clone/pull│                    │
  │          │  - validate YAML │                    │
  │          │  - create branch │                    │
  │          │  - write SQLite  │                    │
  │          └────────┬─────────┘                    │
  │                   │                              │
  │                   ▼                              │
  │          ┌──────────────────┐                    │
  │          │  RUNNING         │                    │
  │          │  - pipeline      │                    │
  │          │    stages 1-5    │                    │
  │          │  - confidence    │                    │
  │          │    gating        │                    │
  │          │  - NATS commands │                    │
  │          │    to specialists│                    │
  │          └────────┬─────────┘                    │
  │                   │                              │
  │          ┌────────┴─────────┐                    │
  │          ▼                  ▼                    │
  │  ┌──────────────┐  ┌───────────────┐            │
  │  │ FINALISING   │  │ PAUSED        │            │
  │  │ - push branch│  │ - awaiting    │            │
  │  │ - create PR  │  │   human review│            │
  │  │ - publish    │  │ - 🟡 flagged  │            │
  │  │   complete   │  │ - JetStream   │            │
  │  │ - ACK msg    │  │   msg un-acked│            │
  │  └──────┬───────┘  └───────┬───────┘            │
  │         │                  │ Rich approves       │
  │         │                  │ or rejects          │
  │         ▼                  ▼                     │
  │  ┌──────────────┐  ┌───────────────┐            │
  │  │ COMPLETE     │  │ FAILED        │            │
  │  │ - PR created │  │ - hard stop   │            │
  │  │ - SQLite     │  │ - 🔴 rejected │            │
  │  │   updated    │  │ - ACK msg     │            │
  │  │ - ACK msg    │  │ - SQLite      │            │
  │  └──────┬───────┘  └───────┬───────┘            │
  │         │                  │                     │
  │         └──────────────────┘                     │
  │                   │                              │
  │                   │ pull next from JetStream?    │
  │                   ├── message available ──────────┘
  │                   │        (loop to PREPARING)
  │                   └── no messages ──→ IDLE
  │
  └── (FAILED also transitions to next/IDLE)


  CRASH RECOVERY (on Forge startup):

  ┌──────────────────┐
  │  JetStream       │  Message unacknowledged → redelivered after AckWait
  │  redelivery      │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  SQLite check    │  Any build in RUNNING? → mark INTERRUPTED
  │                  │  Any build in PAUSED?  → re-enter PAUSED
  └────────┬─────────┘
           │
           ▼
  INTERRUPTED → retries from PREPARING (fresh git checkout)
  PAUSED → re-enters pause, awaits Rich's decision
  Rich can also: forge skip | forge cancel
```

The **PAUSED** state is key to the confidence gating model. When a gate fires 🟡, the Forge publishes `pipeline.build-paused`, writes the PAUSED status to SQLite, and waits. The JetStream message remains unacknowledged. Rich reviews the Coach's concerns and either approves (Forge resumes) or rejects (Forge fails the build and acknowledges the message). In future, this notification could come via dashboard, Slack, or any NATS subscriber.

---

## 7. NATS Topic Hierarchy

```python
class Topics:
    class Pipeline:
        # Removed: READY_FOR_DEV (was PM Adapter webhook)
        # Removed: FEATURE_PLANNED (was RequireKit publishing)
        # Removed: TICKET_UPDATED (was PM Adapter output)

        BUILD_QUEUED = "pipeline.build-queued.{feature_id}"
        BUILD_STARTED = "pipeline.build-started.{feature_id}"
        BUILD_PROGRESS = "pipeline.build-progress.{feature_id}"
        BUILD_COMPLETE = "pipeline.build-complete.{feature_id}"
        BUILD_FAILED = "pipeline.build-failed.{feature_id}"
        BUILD_PAUSED = "pipeline.build-paused.{feature_id}"
        BUILD_RESUMED = "pipeline.build-resumed.{feature_id}"

        STAGE_COMPLETE = "pipeline.stage-complete.{feature_id}"
        STAGE_GATED = "pipeline.stage-gated.{feature_id}"

        ALL = "pipeline.>"
        ALL_BUILDS = "pipeline.build-*.>"

    class Agents:
        """Ship's Computer agent events."""
        STATUS = "agents.status.{agent_id}"
        COMMAND = "agents.command.{agent_id}"            # was COMMANDS (plural) in v2.1
        RESULT = "agents.result.{agent_id}"              # was RESULTS (plural) in v2.1
        COMMAND_BROADCAST = "agents.command.broadcast"    # was COMMANDS_BROADCAST in v2.1
        STATUS_ALL = "agents.status.>"

    class System:
        HEALTH = "system.health"
        CONFIG = "system.config"
```

### Key Message Schemas

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional

class BuildQueuedPayload(BaseModel):
    feature_id: str
    repo: str                           # e.g., "guardkit/lpa-platform"
    branch: str = "main"
    feature_yaml_path: str
    max_turns: int = 5                  # Per-task AutoBuild turns
    sdk_timeout: int = 1800
    wave_gating: bool = False
    triggered_by: Literal["cli", "jarvis", "forge-internal", "notification-adapter"]
    originating_adapter: Optional[Literal[
        "terminal", "voice-reachy", "telegram",
        "slack", "dashboard", "cli-wrapper"
    ]] = None                           # Required when triggered_by == "jarvis"
    originating_user: Optional[str] = None
    correlation_id: str                 # Stable ID for tracing across stages and streams
    parent_request_id: Optional[str] = None  # Jarvis dispatch ID for progress routing
    queued_at: datetime

class BuildPausedPayload(BaseModel):
    feature_id: str
    build_id: str
    stage: str                          # Which pipeline stage paused
    coach_score: float                  # Score that triggered the gate
    threshold: float                    # What the threshold was
    gate_mode: Literal["flag_for_review", "hard_stop"]
    details: str                        # What the Coach flagged
    paused_at: datetime

class BuildCompletePayload(BaseModel):
    feature_id: str
    build_id: str
    repo: str
    branch: str
    pr_url: str
    stages_passed: int
    total_duration_secs: float
    completed_at: datetime

class StageCompletePayload(BaseModel):
    feature_id: str
    build_id: str
    stage: str
    status: Literal["passed", "failed", "gated", "skipped"]
    coach_score: Optional[float] = None
    duration_secs: float
    completed_at: datetime
```

> **Implementation spec:** The full `BuildQueuedPayload` Pydantic model with validators, correlation flow, forward/backward compatibility notes, and test list is in [forge-build-plan-alignment-review.md Appendix C](forge-build-plan-alignment-review.md#appendix-c--buildqueuedpayload-full-design-jarvis-aware). The schema above is the summary; Appendix C is the implementation target for `nats-core`.

---

## 8. Data Flows

1. **Build Trigger Flow:** Rich runs `forge queue FEAT-XXX` → CLI validates feature YAML exists → publishes `pipeline.build-queued` to JetStream `PIPELINE` stream
2. **Build Execution Flow:** Forge pulls next message from JetStream → git clone/pull/branch → runs pipeline stages with confidence gating → calls specialist agents via NATS (`agents.command.{agent_id}`, results on `agents.result.{agent_id}`) → invokes `guardkit autobuild` as subprocess with `--nats` flag → GuardKit publishes `pipeline.build-progress`
3. **Confidence Gate Flow:** Stage completes → Forge evaluates Coach score against threshold → 🟢 proceed (publishes `pipeline.stage-complete`) / 🟡 pause (publishes `pipeline.build-paused`, awaits Rich) / 🔴 fail build (publishes `pipeline.build-failed`)
4. **Completion Flow:** All stages pass → push branch → create PR via GitHub CLI → publish `pipeline.build-complete` with PR URL → acknowledge JetStream message → Rich reviews PR
5. **Failure Flow:** AutoBuild fails or hard stop triggered → logs preserved to SQLite → publish `pipeline.build-failed` → acknowledge JetStream message → Forge pulls next from queue
6. **Knowledge Capture Flow:** GuardKit AutoBuild → Graphiti knowledge graph (within subprocess, unchanged) — happens at GuardKit level, NOT via NATS events

---

## 9. Architecture Decisions

### ADR-SP-010: Remove PM Adapter from Critical Path

- **Date:** 2026-04
- **Status:** Accepted (supersedes PM Adapter sections of February architecture)
- **Context:** The February architecture placed a Linear PM Adapter in the critical path as the build trigger mechanism. This contradicts the Software Factory thesis that PM tooling represents a category error — digitising coordination overhead rather than eliminating it. The `ready-for-dev` event required someone to move a Linear ticket, reintroducing manual coordination.
- **Decision:** Remove the PM Adapter from the critical build path. Builds are triggered by CLI commands (`forge queue`) which publish directly to JetStream. A notification-only adapter (Linear, Slack, email) is a future option for visibility but never gates execution.
- **Consequences:** +Pipeline operates without any PM tool dependency, +Consistent with Software Factory thesis, +Simpler implementation (fewer services), +No webhook infrastructure needed, -James/Mark lose Kanban board visibility (replaced by PR-based workflow and future dashboard), -No automatic Linear ticket creation from feature plans

### ADR-SP-011: NATS-Native Forge from Day One

- **Date:** 2026-04
- **Status:** Accepted (supersedes earlier v0/v1 phasing)
- **Context:** An earlier draft proposed a v0 subprocess orchestrator (no NATS) with a v1 NATS upgrade via a `PipelineTransport` ABC. This assumed NATS infrastructure wouldn't be ready. With nats-infrastructure and nats-core repos now on the GB10 and being stood up, building a subprocess orchestrator only to replace it is wasted effort.
- **Decision:** The Forge is NATS-native from day one. No subprocess transport layer, no `PipelineTransport` ABC, no phased swap. JetStream is the durable queue. NATS commands are the agent communication mechanism. The build sequence is: NATS infrastructure → integration test → specialist agent on NATS → Forge on NATS.
- **Consequences:** +No throwaway code, +JetStream durability from day one (crash recovery, power cut resilience), +Specialist agents are fleet-integrated from the start, +Simpler codebase (no transport abstraction layer), -Forge cannot run without NATS infrastructure (acceptable — GB10 is the target environment), -NATS infrastructure must be validated before Forge development begins

### ADR-SP-012: Sequential Build Queue

- **Date:** 2026-04
- **Status:** Accepted (strengthens ADR-SP-005)
- **Context:** The original ADR-SP-005 decided on single-threaded builds. This ADR makes the rationale explicit: LLM rate limits (local vLLM and Anthropic API), git operation safety, Graphiti sequential seeding requirement, and debuggability all favour sequential execution.
- **Decision:** The Forge processes one AutoBuild at a time. Multiple queued features execute in FIFO order via JetStream pull consumer. No per-project parallelism in the foreseeable future.
- **Consequences:** +Simple, reliable, debuggable, +No rate limit contention, +No Graphiti write conflicts, -Sequential latency when queue is deep (acceptable — quality over speed)

### ADR-SP-013: JetStream Queue + SQLite History

- **Date:** 2026-04
- **Status:** Accepted
- **Context:** The Forge needs a durable build queue that survives process crashes and power cuts, plus a queryable build history for diagnostics and future dashboard use. JetStream provides the durable queue natively via consumer AckWait. SQLite provides a lightweight local store for build outcomes and stage-level detail that JetStream isn't designed to serve.
- **Decision:** JetStream owns the queue (pending builds, delivery, redelivery on crash). SQLite owns the history (build outcomes, per-stage Coach scores, durations, errors). The Forge writes to SQLite at each state transition. On crash recovery, JetStream redelivers unacknowledged messages; the Forge reconciles with SQLite to determine whether to retry from scratch (INTERRUPTED) or re-enter a pause (PAUSED).
- **Consequences:** +Queue durability is a JetStream feature, not custom code, +Build history is queryable for `forge status`, `forge history`, and future dashboard, +Crash recovery is deterministic (JetStream redelivery + SQLite state reconciliation), +SQLite WAL mode allows concurrent reads during builds, -Two persistence mechanisms to maintain (acceptable — they serve different purposes)

---

### ADR-SP-014: Jarvis as Upstream Build Trigger (Pattern A)

- **Date:** 2026-04
- **Status:** Accepted (proposed via TASK-REV-A1F2 alignment review; accepted 16 April 2026)
- **Context:** v2.1 documents `forge queue` as the only build trigger. Rich has since stated that Jarvis is the human-facing entry point — the place he actually interacts with the fleet via voice (Reachy Mini), Telegram, dashboard, or CLI wrappers. The `jarvis` repo's vision doc already designs a CAN-bus-style intent router that discovers agents via `fleet.register` and dispatches commands. The `nats-infrastructure` repo has already provisioned the matching `FLEET` stream and `agent-registry` KV bucket. The integration pattern is effectively sketched but not committed. Four options were evaluated during TASK-REV-A1F2:
  - **A.** Jarvis publishes `pipeline.build-queued.{feature_id}` directly to JetStream. Forge consumes the same topic as it does for CLI.
  - **B.** Jarvis invokes Forge as a fleet agent via `agents.command.forge`. Forge re-enqueues on its own JetStream consumer.
  - **C.** Jarvis shells out to the `forge queue` CLI.
  - **D.** A thin Forge NATS API layer (new subject) that Jarvis speaks to.
- **Decision:** Adopt **Pattern A**. Jarvis publishes `BuildQueuedPayload` (with `triggered_by="jarvis"` and `originating_adapter=<voice-reachy|telegram|slack|dashboard|cli-wrapper>`) to `pipeline.build-queued.{feature_id}`. Forge consumes without distinguishing sources at the consumer level — the payload carries source metadata for history and correlation. To support discovery, Forge *also* registers on `fleet.register` as an agent (`agent_id=forge`, intents: `build.*`, `pipeline.*`, `max_concurrent=1`), so Jarvis's CAN-bus routing can surface it. Registration is for discovery; triggering remains a JetStream publish.
- **Consequences:** +One topic, many sources — CLI, Jarvis, and future notification adapters all publish the same payload to the same topic; Forge is agnostic, +Preserves v2.1's "Forge is a JetStream consumer" contract (no double-hop via an agent-command handler), +Correlation IDs and `parent_request_id` in `BuildQueuedPayload` let Jarvis stream progress back to the originating session without Forge knowing anything about Jarvis internals, +The `fleet.register` + `agent-registry` KV plumbing needed for discovery already exists in `nats-infrastructure`, -Forge must now produce and publish an `AgentManifest` (small new file), adding a sliver of Ship's-Computer coupling to a previously standalone service, -`BuildQueuedPayload` gains Jarvis-specific fields (`originating_adapter`, `parent_request_id`) that CLI publishers don't populate — they are `Optional` and validated per-source so cost is confined to the schema, -Pattern B is foregone; if a synchronous "start a build and wait" pattern ever becomes desirable it can be added on top

### ADR-SP-015: Specialist-Agent Dual-Role Deployment Model

- **Date:** 2026-04
- **Status:** Accepted (proposed via TASK-REV-A1F2 alignment review; accepted 16 April 2026)
- **Context:** v2.1 §3 lists the specialist-agent roles (Architect, Product Owner, Ideation, UX Designer) but does not describe how multiple roles are deployed. Rich has committed to the first two real specialist-agent runs being **Product Owner (Stage 1 / Specification Review) + Architect (Stage 2 / Architecture Review)**, invoked by the Forge as two concurrent deployments of the same `specialist-agent` binary. The `specialist-agent` repo has YAMLs, handlers, and Graphiti wiring for both roles, but the `--role` CLI flag is parsed and ignored: the manifest is hardcoded to `architect-agent`, so two concurrent instances would collide on fleet registration.
- **Decision:** The Forge's early pipeline stages call two distinct specialist agents by role: **Product Owner** (`agent_id=product-owner-agent`) and **Architect** (`agent_id=architect-agent`). Both are deployments of the same `specialist-agent` binary with different `--role` flags. `agent_id` is derived from the role by default (`{role_id}-agent`) or overridable via `SPECIALIST_AGENT_ID` env var for tests. Both register on `fleet.register` independently, subscribe to `agents.command.{agent_id}`, and publish results to `agents.result.{agent_id}`. Result payloads are wrapped in the Forge-compatible shape `{role_id, coach_score, criterion_breakdown, detection_findings, role_output}` at the `specialist-agent` boundary — Forge does not translate per-role output types.
- **Consequences:** +Makes the deployment model explicit and anchored — before this ADR the dual-role deployment was a verbal commitment with no artefact, +Drives concrete changes in `specialist-agent` (role-parameterised manifest factory, role-aware command router, result payload wrapper — see alignment review appendix D), +Forge's `call_agent_tool()` becomes simpler: one expected result shape regardless of which role answered, +Architect-only "degraded mode" fallback remains valid — Forge can still delegate to architect alone if PO is unavailable, -Role YAMLs and Python handlers now have a contract (`role_output` must be Pydantic-serialisable) they did not previously have; Ideation and UX Designer will inherit it, -A thin `result_wrapper.py` module introduces one more place where role-specific evaluation data gets flattened into the NATS payload (alternative of Forge-side translation was rejected), -Two extra containers in the Docker Compose topology — acceptable, they are lightweight wrappers around the same binary

### ADR-SP-016: Singular Topic Convention (`agents.command.*`, `agents.result.*`)

- **Date:** 2026-04
- **Status:** Accepted (proposed via TASK-REV-A1F2 alignment review; accepted 16 April 2026)
- **Context:** v2.1 §7 originally specified agent command/result topics as `agents.commands.{agent_id}` and `agents.results.{agent_id}` (plural). The `nats-core` library (98% test coverage, shipping) uses `Topics.Agents.COMMAND = "agents.command.{agent_id}"` and `Topics.Agents.RESULT = "agents.result.{agent_id}"` (singular). The `fleet-master-index.md` agrees with `nats-core`. The `specialist-agent` NATS adapter already subscribes to `agents.command.*`. TASK-REV-A1F2 surfaced this as a blocking naming mismatch.
- **Decision:** Adopt the **singular** convention fleet-wide. All forge repo docs (anchor, refresh, build-plan, fleet-master-index) use `agents.command.{agent_id}` / `agents.result.{agent_id}`. `nats-core` and `specialist-agent` are unchanged. A note in `nats-core`'s topic registry docstring records that the convention is singular and briefly explains why (historical precedence of shipping code + installed tests). §7 of this document has been updated to match (v2.2).
- **Consequences:** +Avoids rewriting a 98%-covered library with shipping integration tests and a live `specialist-agent` subscriber, +The anchor update is a cheap find-and-replace across three files, +Consistent with the existing `agents.status.{agent_id}` topic which is also singular, -Minor aesthetic loss — the plural form reads more naturally in English; subordinate to not rewriting working code, -Anchor v2.2 becomes the canonical form; anyone referencing v2.1 topics in recent documentation will need to update (scope is small)

### ADR-SP-017: PIPELINE / AGENTS / SYSTEM Stream Retention Reconciliation

- **Date:** 2026-04
- **Status:** Accepted (proposed via TASK-REV-A1F2 alignment review; accepted 16 April 2026)
- **Context:** v2.1 §3 specifies three JetStream streams with specific retentions: `PIPELINE` 30 days, `AGENTS` 7 days, `SYSTEM` 24 hours. The installed `nats-infrastructure` provisions these streams (plus four others — `FLEET`, `JARVIS`, `NOTIFICATIONS`, `FINPROXY` — which are not in the anchor) with different retentions: `PIPELINE` 7 days, `SYSTEM` 1 hour. The `nats-infrastructure` system-spec was reasoned through independently of the anchor v2.1, and the retention values reflect that independent analysis. TASK-REV-A1F2 surfaced this as a blocking mismatch that must be resolved before Phase 2 (`nats-core` revision) begins.
- **Decision:** Update the anchor to match the installed `nats-infrastructure` reality: `PIPELINE` **7 days** (was 30; SQLite is the durable build history per ADR-SP-013 so PIPELINE only needs to cover realistic crash-recovery windows), `AGENTS` **7 days**, `SYSTEM` **1 hour** (was 24; ephemeral health and config pings). Promote `FLEET`, `JARVIS`, `NOTIFICATIONS` streams into §3 with one-line descriptions since they are real and Ship's-Computer-relevant. `FINPROXY` remains out of the anchor (tenant-specific). This ADR does **not** resolve the `pipeline-state` NATS KV bucket question (it competes with SQLite for runtime Forge state) — that needs its own ADR once Rich has decided, tracked as TASK-PSKV-001 in nats-infrastructure.
- **Consequences:** +Anchor and installed infrastructure agree, unblocking Phase 1 validation, +SQLite's role as the durable history store is strengthened — JetStream becomes exactly what it is (durable queue, short-to-medium retention for crash recovery), +Anchor v2.2 documents `FLEET`, `JARVIS`, `NOTIFICATIONS` as first-class streams, closing the "what stream does Jarvis session state live in" gap, -Lose the ability to replay a build's events from 8+ days ago directly off JetStream (mitigated by SQLite history + per-build structured logs), -One more decision deferred (`pipeline-state` KV bucket fate) — tracked separately

---

## 10. Implementation Roadmap — Build Sequence

This is the actual build order. Each phase validates before the next begins.

### Phase 1: NATS Infrastructure (in progress)

**Goal:** NATS server with JetStream running on GB10, streams configured, integration tests passing.

- [ ] Docker Compose for NATS server with JetStream on GB10
- [ ] Configure NATS accounts (APPMILLA at minimum, FINPROXY when needed)
- [ ] Define JetStream streams: PIPELINE (7-day), AGENTS (7-day), FLEET, JARVIS, NOTIFICATIONS, SYSTEM (1-hour)
- [ ] Integration tests: publish/subscribe, JetStream persistence, consumer AckWait behaviour
- [ ] Verify Tailscale connectivity from MacBook Pro

**Validation:** Publish a message to `pipeline.build-queued.test` from MacBook Pro → message persisted in JetStream on GB10 → consumer pulls and acknowledges → message gone from stream. Kill consumer mid-processing → message redelivered after AckWait.

### Phase 2: nats-core Revision

- [ ] Remove `PMAdapter` base class and `ReadyForDevPayload`
- [ ] Add `BuildQueuedPayload`, `BuildPausedPayload`, `BuildCompletePayload`, `StageCompletePayload`
- [ ] Add revised topic registry (pipeline.build-queued, pipeline.build-paused, pipeline.build-resumed, pipeline.stage-complete, pipeline.stage-gated)
- [ ] Verify existing schemas (BuildStarted, BuildProgress, BuildFailed) still valid
- [ ] Integration tests against live NATS on GB10

**Validation:** Python client publishes typed `BuildQueuedPayload` → consumer deserialises → schema validation passes.

### Phase 3: Specialist Agent on NATS

**Goal:** At least one specialist agent role (Architect) subscribing to NATS commands and publishing results.

- [ ] Specialist agent subscribes to `agents.command.architect-agent`
- [ ] Receives structured command, runs Agent harness, publishes result to `agents.result.architect-agent`
- [ ] Agent manifest published to `fleet.register` on startup
- [ ] Integration test: send command via NATS → receive result → validate output structure

**Validation:** Publish architecture review command → Architect Agent produces output → result appears on `agents.result.architect-agent` with Coach score.

### Phase 4: Forge — Core Pipeline

**Goal:** Forge consumes from JetStream, orchestrates pipeline, produces PRs.

- [ ] Create `forge` repository
- [ ] JetStream pull consumer for `pipeline.build-queued.*`
- [ ] Pipeline state machine (PREPARING → RUNNING → FINALISING → COMPLETE/FAILED)
- [ ] PAUSED state for confidence gate 🟡 (publishes `pipeline.build-paused`, awaits approval)
- [ ] Confidence-gated checkpoints with configurable thresholds (`forge.yaml`)
- [ ] NATS command invocation of specialist agents (Stage 2: Architecture Review)
- [ ] Subprocess invocation of GuardKit AutoBuild with `--nats` flag (Stage 4)
- [ ] Git operations (clone/pull/branch/push/PR via GitHub CLI)
- [ ] SQLite build history and stage log (`~/.forge/forge.db`)
- [ ] Crash recovery: reconcile JetStream redelivery with SQLite INTERRUPTED/PAUSED state
- [ ] CLI commands: `forge queue`, `forge status`, `forge history`, `forge cancel`, `forge skip`
- [ ] `forge.yaml` configuration (thresholds, build config, degraded mode)
- [ ] Publish pipeline events: build-started, stage-complete, build-complete, build-failed, build-paused, build-resumed

**Validation:** `forge queue FEAT-XXX` → JetStream message published → Forge consumes → specialist agent called via NATS → GuardKit AutoBuild runs → PR created → `forge status` shows COMPLETE → `forge history` shows stage-by-stage log. Kill the Forge process mid-build → restart → JetStream redelivers → `forge status` shows INTERRUPTED → build retries from scratch.

### Phase 5: Optional Notification Adapters (future, if needed)

- [ ] Slack adapter — subscribes to `pipeline.build-complete`, `pipeline.build-failed`, posts to channel
- [ ] Email adapter — sends digest of daily build activity
- [ ] Linear adapter — creates/updates tickets for visibility only (never gates execution)

These are explicitly not in the critical path and should only be built when there's a real demand signal.

---

## 11. Components Removed from Scope

| Component | Was In February Architecture | Why Removed |
|-----------|------------------------------|-------------|
| **PM Adapter (Linear)** | Critical path — bidirectional sync, webhook receiver | Contradicts Software Factory thesis. Coordination tool in a system that eliminates coordination. |
| **PM Adapter (GitHub Projects)** | Future critical-path option | Same reason. |
| **RequireKit NATS integration** | Published `feature-planned` events | RequireKit deprecated. `/feature-spec` in GuardKit replaces it. |
| **`ready-for-dev` event/payload** | Core pipeline trigger | Replaced by `build-queued` via CLI → JetStream. |
| **`feature-planned` event** | Published by RequireKit | Removed with RequireKit. Feature planning is a GuardKit command, not a NATS event. |
| **`ticket-updated` event** | PM Adapter output | No tickets to update. |
| **Linear webhook receiver** | HTTP endpoint in dev-pipeline | No webhooks needed. CLI-driven. |
| **NATS account for James** | Scoped Linear access | James reviews PRs on GitHub, not pipeline events. |
| **PipelineTransport ABC** | v0/v1 transport swap mechanism | No phased swap — NATS-native from day one. |
| **Subprocess transport** | v0 fallback when NATS unavailable | NATS infrastructure is being stood up now. No fallback needed. |

---

## 12. Relationship to DDD Southwest Talk

This is the architecture being presented on 16 May 2026 at Engine Shed, Bristol. The key narrative points it supports:

1. **"Why are we still using tickets?"** — The factory has no tickets. Feature YAML + Gherkin + assumptions manifest + PR = the complete audit trail.
2. **"The coordination layer is the bottleneck"** — Removing PM tooling from the critical path is the architectural embodiment of collapsing the coordination layer.
3. **"Outcome gates, not progress tracking"** — Confidence-gated checkpoints evaluate output quality, not task completion status.
4. **"The human is the approver, not the operator"** — Rich gives direction and reviews when the Coach has specific concerns (🟡). The factory runs autonomously otherwise.
5. **"Electrifying the steam engine"** — The February architecture (Linear + PM Adapter + NATS) was electrifying the steam engine. This revision eliminates the engine.

---

*"The Forge doesn't mine the ore or design the blueprint — it does the making. And it knows when to ask for help."*
