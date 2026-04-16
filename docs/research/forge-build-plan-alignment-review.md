# Forge Build Plan — Alignment Review

> **Task:** TASK-REV-A1F2
> **Mode:** Architectural (comprehensive)
> **Anchor:** [forge-pipeline-architecture.md](forge-pipeline-architecture.md) v2.1, 15 April 2026
> **Date:** 15 April 2026
> **Reviewer:** `/task-review` (architectural-reviewer + six Explore audits)

---

## Executive summary

**Verdict: ⚠️ Ready to start Phase 1 (NATS infra) — but Phase 2 (`nats-core` revision), Phase 3 (specialist-agent NATS) and the Forge build plan itself must be updated before code is written.**

The anchor v2.1 is internally sound. The two biggest alignment problems are:

1. **The in-repo forge docs (`forge-build-plan.md`, `forge-pipeline-orchestrator-refresh.md`, `fleet-master-index.md`) precede v2.1 and still carry the old "Forge as checkpoint-manager + fleet agent receiving `agents.command.forge`" framing.** They are not wrong about confidence gates or specialist delegation, but they are silent on v2.1's CLI + JetStream trigger path, the 5-stage state machine, and several payload/topic contracts. Every one of them needs edits before `/system-arch` is run against them as context.
2. **Jarvis is entirely absent from the anchor and only partially represented in the fleet docs.** Rich's stated position — *Jarvis is the human-facing entry point; it discovers Forge on the fleet and sends build requests* — is not yet reflected anywhere in forge repo docs. This is the highest-leverage documentation gap.

Reality check across the sibling repos:

| Repo | State today | Blocking the build plan? |
|---|---|---|
| `nats-infrastructure` | **Ready** — JetStream configured, streams provisioned, KV buckets (incl. `agent-registry`, `jarvis-session`) in place, dual-role-deployable, Phase 1 complete | No, but **stream retention mismatches** the anchor — reconcile |
| `nats-core` | **Partial** — 98% test coverage on what exists, but missing 4 v2.1-critical payloads and at least 5 topics; topic naming diverges (`agents.command` vs anchor's `agents.commands`); stale `FeaturePlanned*` still exported | **Yes** — Forge cannot be built against current `nats-core` |
| `specialist-agent` | **Partial** — harness, architect + product-owner + ideation role YAMLs and handlers all present, Graphiti wired. But `--role` flag is parsed and ignored; manifest is hardcoded to `architect-agent`; dual deployment would collide on `agent_id`; result payload does not wrap in `coach_score`/`criterion_breakdown`/`detection_findings` | **Yes** — PO + Architect dual-role milestone cannot happen until the role is actually routed to manifest/command-router/agent_id |
| `jarvis` | **Skeleton** — vision + CAN-bus design doc only, zero source code. Already designs `fleet.register`/KV-watch discovery, intent classification → dispatch, adapter pattern for voice/CLI/Telegram/dashboard | **Yes** for "Jarvis triggers Forge builds" narrative; No for "Forge can still run from CLI on day one" |

This review recommends Rich proceed with **Phase 1 (NATS infrastructure validation) immediately**, treat Phase 2 (nats-core revision) as a real piece of work rather than a documentation update, and explicitly **add Jarvis integration as a first-class section of the build plan** using Pattern A (Jarvis publishes `pipeline.build-queued` directly) — with Forge still registering on `fleet.register` for discoverability.

A full file-scoped correction list and follow-up task backlog are at the end.

---

## 1. Per-document findings (forge repo)

### 1.1 `docs/research/forge-pipeline-architecture.md` (v2.1) — anchor

**Verdict:** Internally consistent. Treated as source of truth. Two gaps to flag on the anchor itself, independent of drift elsewhere:

- **Gap A — Jarvis is not mentioned at all.** §1 ("Core Workflow") begins at `/feature-spec` in Claude Desktop and treats `forge queue` as the sole trigger. Rich's position is that Jarvis is upstream of that. The anchor needs a new §5.0 ("Build Request Sources") or an explicit note under §5 ("Build Queue") saying: builds may be triggered by (a) `forge queue` CLI, (b) Jarvis publishing `pipeline.build-queued` after intent routing, (c) future notification adapters (out of scope). This is not a contradiction — it is a silent gap that Rich has verbally filled.
- **Gap B — Specialist-agent dual-role deployment is implicit.** §3 names "Architect, Product Owner, Ideation, UX Designer" as specialist-agent roles and §4 Stage 2 calls out an Architect call. But the anchor doesn't spell out that the first two runs will be *two concurrent deployments of the same binary*, one as PO and one as Architect, both invoked from the Forge. This is an operational detail Rich has committed to and that the build plan should surface, because it drives a concrete change in `specialist-agent` (role-parameterised manifest + distinct `agent_id`s).

Both gaps are *additions*, not corrections — the existing text is not wrong.

### 1.2 `docs/research/ideas/forge-build-plan.md` (12 April 2026)

**Verdict:** DRIFTS. Written against the pre-v2.1 "Forge as checkpoint manager + fleet agent" framing.

**Key drift:**

- **Line 415 (`nats_topic: agents.command.forge`, singular).** Anchor v2.1 uses `agents.commands.{agent_id}` (plural). Even if `nats-core` settles on singular, the anchor must win — or the anchor must change. Pick one. (See §2.1 for the `nats-core` reality.)
- **Line 38–47 (Hard Prerequisites): "nats-core library implemented — 97% test coverage, all event payloads…"** This overstates reality. `nats-core` is 98% covered on what it has, but **`BuildQueuedPayload`, `BuildPausedPayload`, `StageCompletePayload`, `StageGatedPayload`, and the matching topics are absent today** (see §2.1). The build plan's "nats-core ✅" checkbox should be *conditionally* ticked against a v2.1-aligned revision, not the current snapshot.
- **Feature set (lines 104–115) does not map cleanly to anchor roadmap Phase 4.** The anchor's §10 Phase 4 lists core pipeline capabilities (JetStream pull consumer, state machine, confidence gates, specialist calls, GuardKit subprocess with `--nats`, git/PR, SQLite history, crash recovery, CLI commands `forge queue|status|history|cancel|skip`, `forge.yaml` config). The build plan's `FEAT-FORGE-001..008` cover much of this but use different names (modes A/B/C, NATS Fleet Integration, Infrastructure Coordination) and introduce concepts (`greenfield`/`feature`/`review-fix` modes, session persistence via NATS KV, `.guardkit/context-manifest.yaml` cross-repo dependency filtering) that v2.1 is silent on. None of these are *wrong*, but they are not anchored. They should either be promoted into v2.1 or dropped from the build plan.
- **Lines 300–338 (Validation + FinProxy first-run) use the wrong CLI surface.** They assume `python -m forge.cli greenfield --project finproxy …` — a mode-based CLI. v2.1 §5 specifies the CLI as `forge queue FEAT-XXX`, `forge status`, `forge history`, `forge cancel`, `forge skip`. Pick one. Recommended: keep the `queue` surface and demote `greenfield`/`feature`/`review-fix` to optional higher-level wrappers if they earn their place.
- **Line 453–491 (`forge-pipeline-config.yaml` example) uses a per-project checkpoint layout with reviewer/channel fields (`reviewer: rich`, `escalation_channel: "jarvis.notification.slack"`).** The anchor's `forge.yaml` example (§4) uses per-stage `auto_approve`/`flag_for_review` pairs plus a `build_config` and `degraded_mode` block. These are two different schemas. The build plan's is richer (reviewer assignment, critical detections, escalation). Either promote that richness into the anchor or drop it from the plan.
- **Line 87–96 ("Context Documents Available" + "Dev pipeline architecture / system spec" project-knowledge entries).** These reference documents the anchor has explicitly superseded. Remove or mark SUPERSEDED BY v2.1.
- **Line 616–629 ("Source Documents" table).** Same issue — "Dev pipeline architecture / system spec" should be removed from the context inputs to `/system-arch`. The anchor should be the primary context, with the refresh doc and fleet-master-index as supporting.

**No stale PM Adapter / Kanban / ready-for-dev references found** — the build plan post-dates those removals. ✅

### 1.3 `docs/research/ideas/forge-pipeline-orchestrator-refresh.md` (v3, 11 April 2026)

**Verdict:** DRIFTS. Materially reframes Forge from *pipeline orchestrator* to *checkpoint manager*. That reframing is useful but not canonical under v2.1.

- **Structural drift — identity reframing (§"Revised Architecture", lines 208–217).** Presents Forge as "checkpoint manager" that delegates orchestration to specialists. Anchor v2.1 presents Forge as the *pipeline orchestrator* that happens to apply confidence gates. These are compatible, but the emphasis diverges. Recommendation: update the refresh doc's opening paragraph to explicitly align with v2.1's framing ("Forge is the NATS-native pipeline orchestrator; confidence-gated checkpoints are how it decides when to involve Rich").
- **Missing 5-stage taxonomy.** Anchor §4 names five stages; refresh doc (lines 291–354) describes a flow that uses different vocabulary ("product docs → architecture → feature spec → feature plan → autobuild → verify → PR") and conflates stages. Add a subsection mapping the greenfield flow blocks onto the five anchor stages.
- **State machine not named.** Anchor §6 names states (IDLE → PREPARING → RUNNING → FINALISING/PAUSED → COMPLETE/FAILED). Refresh doc mentions "state machine between checkpoints" but never names the states. Add.
- **Build trigger entry point not addressed.** Silent on `forge queue` and JetStream `pipeline.build-queued`. Add.
- **Jarvis coverage — partial.** Mentions `jarvis.notification.{adapter}` as the *downstream* notification target but does not cover Jarvis as the *upstream* trigger. Add a new subsection.
- **Specialist-agent dual-role — well-covered.** Lines 27–32 and 38 correctly describe `--role architect` / `--role product-owner` as two deployments of the same binary. This text is the best existing treatment and should be reused when adding the same section to the anchor. ✅
- **`FeaturePlannedPayload` / `FeatureReadyForBuildPayload` (lines 453–459).** These are used in the refresh's event table but the anchor doesn't mention them. Either retire them (align with anchor's `BuildQueuedPayload`) or explain the intermediate events.
- **No stale PM Adapter / Kanban references.** ✅

### 1.4 `docs/research/ideas/fleet-master-index.md` (v2, 12 April 2026)

**Verdict:** CONTRADICTS on build trigger and STALE on repo inventory (per `TASK-update-fleet-index-d22.md`).

- **Line 10 — Jarvis described as "intent router dispatching requests to specialist agents".** Anchor position (Rich's addition): Jarvis also dispatches *build requests* to the Forge. Fleet index frames Jarvis only as a specialist-agent dispatcher. Expand the Jarvis section to include Forge discovery + build-request dispatch.
- **Lines 146–148 — "`feature_ready_for_build` event is emitted by the Forge…not by a webhook from a kanban card state change."** Describes the *output* of the planning phase, not the *input* that triggers a build. Anchor v2.1 specifies CLI `forge queue` → JetStream `pipeline.build-queued`. Fleet index is silent on this input entirely. Add.
- **Lines 472–535 (The Forge — Pipeline Orchestrator section).** Shows `agents.command.forge` (singular) and `max_concurrent: 3`. The singular/plural conflict must be resolved (see §2.1). `max_concurrent: 3` contradicts anchor ADR-SP-012 (sequential builds, one at a time). Correct to `max_concurrent: 1`.
- **Lines 43–47 — specialist-agent dual-role coverage is correct** (all three roles as deployments of same binary). ✅
- **Correctly identifies PM tools as optional visibility adapters (lines 140–148), matches anchor §11.** ✅
- **`TASK-update-fleet-index-d22.md` in the same folder already lists known repo-inventory drift** (architect-agent → specialist-agent rename, ideation-agent archived, product-owner-agent absorbed, lpa-platform added). This task is unexecuted. Either execute it inline during the correction pass or keep it as a separate follow-up — but do not let both sources of truth exist in parallel.

### 1.5 `docs/product/roadmap.md` + `docs/product/feature_spec_inputs/FEAT-PO-001..006`

**Verdict:** MATCHES. These documents cover operational gaps around the Forge (prerequisites validation, build-plan governance, context manifest validation, Graphiti optionality, confidence-gate calibration, pipeline status queries). They are correctly scoped — they do not attempt to restate the pipeline, so the v2.1 anchor positions are out of scope for them. No corrections needed.

Note for later: FEAT-PO-001 (pipeline prerequisites) references `forge-build-plan.md` as its input. When the build plan is corrected, FEAT-PO-001's acceptance criteria should be re-checked so it validates the corrected prerequisites, not the pre-v2.1 ones.

### 1.6 Other `docs/research/ideas/` files — spot check

- `big-picture-vision-and-durability.md` — matches. ✅
- `conversation-starter-gap-analysis.md` — matches. Jarvis absent (out of scope). ✅
- `forge-ideas-overhaul-conversation-starter.md` — matches. Silent on build trigger but not contradictory. ✅
- `architect-agent-finproxy-build-plan.md` — marked SUPERSEDED in its own header. ✅
- `TASK-update-build-plan-da15.md` — coordination task, no pipeline claims of its own.
- `TASK-update-fleet-index-d22.md` — identifies repo-inventory drift in fleet-master-index (see §1.4).

---

## 2. Per-repo findings (sibling repos)

### 2.1 `nats-core`

**State:** PARTIAL — ready for the events that exist, missing the events v2.1 needs. Build plan's "✅ nats-core implemented" is optimistic.

**Present and v2.1-aligned:**
- `BuildStartedPayload`, `BuildProgressPayload`, `BuildCompletePayload`, `BuildFailedPayload` — `src/nats_core/events/_pipeline.py` (109, 127, 161, 202)
- `Topics.Pipeline.BUILD_STARTED|PROGRESS|COMPLETE|FAILED` — `src/nats_core/topics.py` (81–84)
- `AgentManifest`, `ToolCapability`, `IntentCapability` — `src/nats_core/manifest.py` (81–166)
- `NATSKVManifestRegistry` — `src/nats_core/client.py` (380–510)
- `NATSClient` wrapper + `MessageEnvelope` with versioning + correlation IDs
- Test coverage: pytest reports **98%** (755 passed, 698 stmts, 16 missed)

**Missing — these are the blocking gaps for Forge:**
- `BuildQueuedPayload` — **CRITICAL**, anchor §7. Without this, there is no trigger.
- `BuildPausedPayload` — **CRITICAL**, anchor §7. Without this, there is no 🟡 gate.
- `StageCompletePayload` — **CRITICAL**, anchor §7.
- Topic `pipeline.build-queued.{feature_id}` — CRITICAL.
- Topic `pipeline.build-paused.{feature_id}` — CRITICAL.
- Topic `pipeline.build-resumed.{feature_id}` — HIGH.
- Topic `pipeline.stage-complete.{feature_id}` — HIGH.
- Topic `pipeline.stage-gated.{feature_id}` — HIGH.
- Topic `agents.commands.broadcast` — MEDIUM.

**Naming mismatch (decide once, everywhere):**
- `nats-core` uses `Topics.Agents.COMMAND` / `RESULT` (singular) → `agents.command.{agent_id}` / `agents.result.{agent_id}`.
- Anchor v2.1 §7 uses `agents.commands.{agent_id}` / `agents.results.{agent_id}` (plural).
- Fleet-master-index agrees with `nats-core` (singular).
- **Recommendation:** the anchor is wrong or `nats-core` is wrong, not both. Since `nats-core` has shipping code and tests, and `Topics.Agents.COMMAND` is the installed reality, **update the anchor** to `agents.command.{agent_id}` / `agents.result.{agent_id}`. Cheaper than rewriting `nats-core`. Add a one-line ADR noting the singular convention.

**Stale items to remove or deprecate:**
- `FeaturePlannedPayload` — `events/_pipeline.py:56`. Anchor §11 lists `feature-planned` as removed. Delete or mark `deprecated=True` with a migration note.
- Topic `pipeline.feature-planned.{feature_id}` — `topics.py:79`. Same.
- `FeatureReadyForBuildPayload` (events/_pipeline.py:84) and its topic (`topics.py:80`) — **NOT** in anchor but may be legitimate intermediate event per DDR-001. Decision needed: either promote into the anchor (add §7 entry) or retire.

**Extras worth keeping (already in `nats-core`, silent in anchor):**
- `ApprovalRequestPayload` / `ApprovalResponsePayload` (`events/_agent.py:58–130`) — useful for the 🟡 pause/resume flow. The anchor currently describes the PAUSE/RESUME via `BuildPausedPayload`/`BuildResumedPayload` events on the PIPELINE stream; nats-core already has a general human-in-the-loop shape on the AGENT side. Rich needs to decide which one Forge uses. Recommendation: use `BuildPausedPayload` on `pipeline.build-paused` for Forge's own state, and `ApprovalRequestPayload` on the AGENT stream only if/when the approval originates with a specialist agent rather than the Forge itself.
- `CommandPayload` / `ResultPayload` generic agent messaging (`events/_agent.py:133–189`) — this is what `NATSClient.call_agent_tool()` uses today, and what the build plan's FEAT-FORGE-003 depends on.

**Test coverage reality check:** 98% is real, the "97% coverage" claim in `forge-build-plan.md:38–39` is accurate *for what exists*, but the sentence reads as if `nats-core` is done. It isn't. Caveat the claim.

### 2.2 `nats-infrastructure`

**State:** READY. Phase 1 can be validated today. Docker Compose boots, JetStream is enabled, streams and KV buckets are provisioned, fleet-aware, zero legacy PM Adapter residue.

**Stream reality vs anchor §3 assumptions:**

| Stream | Anchor v2.1 | Actual config | File:line | Decision needed |
|---|---|---|---|---|
| PIPELINE | 30-day retention | **7 days** | `streams/stream-definitions.json:7` | Reconcile |
| AGENTS | 7-day retention | **24 hours** (per audit) / 7d per spec | `streams/stream-definitions.json:15-24` | Reconcile |
| SYSTEM | 24-hour retention | **1 hour** | `streams/stream-definitions.json:48-57` | Reconcile |
| JARVIS | (not in anchor) | Present | `streams/stream-definitions.json:26-35` | Promote to anchor — Jarvis is real |
| NOTIFICATIONS | (not in anchor) | Present | `streams/stream-definitions.json:37-46` | Promote to anchor when Phase 5 adapters come |
| FLEET | (not in anchor) | Present | `streams/stream-definitions.json:59-68` | Promote — this is how `fleet.register` persists |
| FINPROXY | (not in anchor) | Present | `streams/stream-definitions.json:70-79` | Fine — tenant stream |

**KV buckets (all present, anchor silent):**
- `agent-status` — last-known agent status (heartbeats)
- `agent-registry` — agent manifests, watched by Jarvis for routing
- `pipeline-state` — Forge pipeline state (this is interesting — may compete with SQLite)
- `jarvis-session` — Jarvis session context

**Items to reconcile:**
1. **Retention mismatch.** Either update the anchor to match the installed config (7d/24h/1h) or change the config. *Recommendation:* the installed config was thought through by whoever wrote the nats-infrastructure system-spec; prefer it. Update the anchor to match. 30-day retention for PIPELINE is overkill for a single-developer factory with SQLite history as the durable record.
2. **`pipeline-state` KV bucket.** The anchor's ADR-SP-013 says "JetStream owns the queue; SQLite owns the history." A `pipeline-state` KV bucket implies there's a third owner in play. Rich needs to decide what this bucket is for — is it Forge runtime state (session, current stage, coach score) that could equally live in SQLite? If so, delete the KV bucket and consolidate on SQLite. If not (e.g. it's for cross-process visibility during a live build so `forge status` on another machine can read it), the anchor should be updated to reflect the three-store model.
3. **Promote `FLEET`, `JARVIS`, `NOTIFICATIONS` streams into the anchor** as part of the "composability with Ship's Computer" story (§3 §8).
4. **Phase 1 validation is blocked on nothing in this repo** — but it is blocked on `nats-core` payloads (see §2.1) if Rich wants to validate the full `BuildQueuedPayload` round-trip. If the Phase 1 validation is just "can I publish/consume a message to JetStream on GB10", it can happen today.

### 2.3 `specialist-agent`

**State:** PARTIAL — harness and role configs exist; NATS adapter exists; but the `--role` flag is parsed and ignored, blocking the PO + Architect dual-deployment milestone.

**Present:**
- Unified harness (ADR-ARCH-008 Accepted, 11 April 2026)
- Role YAMLs: `architect` (186 lines), `product-owner` (254 lines), `ideation` (30 lines). UX Designer not configured.
- Role-specific Python packages under `src/specialist_agent/roles/{role_id}/` with types, formatter, handler (ADR-ARCH-009 two-layer pattern)
- NATS adapter (`adapters/nats_adapter.py`), command router (`adapters/command_router.py`)
- `NATSAdapter.start()` → `client.register_agent(manifest)` (nats_adapter.py:84)
- Graphiti query at startup, write-back after runs, configured per-role in YAML

**Blocking bugs / gaps for dual-role deployment (Rich's stated milestone):**

| Gap | Evidence | Severity |
|---|---|---|
| `--role` CLI flag accepted but ignored — manifest always hardcoded to `get_architect_agent_manifest()` | `cli/main.py:2168` | CRITICAL |
| No `get_product_owner_manifest()` builder; no role-parameterised manifest factory | `adapters/manifest.py:13–222`, hardcoded `agent_id="architect-agent"` (26) | CRITICAL |
| `agent_id` not derivable from role — two deployments would collide on `"architect-agent"` | same | CRITICAL |
| Command router hardcoded to architect `TOOL_TO_COMMAND` — can't route PO commands | `adapters/command_router.py` | HIGH |
| Result payload does not wrap outputs in Forge's expected `coach_score` + `criterion_breakdown` + `detection_findings` shape — instead publishes role-specific types (ConversationStarter, ProductRoadmap) | `adapters/command_router.py:~220`, `evaluation/types.py` | HIGH |
| No run instructions / shell script / compose fragment for launching two instances | — | MEDIUM |
| No e2e test covering "start architect + PO concurrently, Forge calls both over NATS" | — | MEDIUM |
| Phase 3 status (per repo's own `phase3-build-plan.md`, 9 April 2026) is "in progress", FEAT-011/012/013/014 feature-specs done, implementation incomplete | `docs/phase3-*.md` | Context |

**Stale concepts (PM Adapter, Linear, Kanban, ready-for-dev, feature-planned, ticket-updated):** none found. ✅

**Build plan's "soft prerequisite" wording is right:** `forge-build-plan.md:50–55` already describes the "Forge can delegate to architect role only (single-role degraded mode)" fallback. That fallback *does* work against the current specialist-agent state — but only because it hardcodes the architect. Rich's new "PO + Architect dual-run" milestone is a strictly harder ask and is currently blocked on the five CRITICAL/HIGH items above.

### 2.4 `jarvis`

**State:** SKELETON — `jarvis-vision.md` is a well-developed design artefact; there is zero source code and no running agents. Last commit is 5c04d12 (31 March 2026), "Initial ideas docs".

**What the design already commits to:**
- CAN-bus-style fleet discovery — subscribe to `fleet.register` / `fleet.deregister` / `fleet.heartbeat.>`, maintain routing table in `agent-registry` KV (`jarvis-vision.md:104–132`). **This is exactly the `FLEET` stream + `agent-registry` KV bucket that `nats-infrastructure` has already provisioned.** The plumbing matches.
- Intent classification → dynamic routing → dispatch to `jarvis.dispatch.{agent}` (`jarvis-vision.md:104–132`).
- Adapter pattern for voice (Reachy Mini), Telegram, Slack, Dashboard (WebSocket), CLI (`jarvis-vision.md:216–220`).
- Heartbeat every 30s including `queue_depth` + `active_tasks` for load-balancing; 90s timeout marks agents unavailable (`jarvis-vision.md:156–169`).
- Dependency on `nats-core` for message models and topic constants (`jarvis-vision.md:34`).

**What's missing vs Rich's stated position ("Jarvis discovers Forge and sends build requests"):**
1. No source code at all — cannot trigger anything today.
2. No explicit statement that Jarvis is Rich's *primary* interface to Forge — the vision treats all entry points symmetrically.
3. No build-request payload schema — the vision doesn't define how a "build this feature" intent turns into `feature_id` + context.
4. No reference to Forge by name or to `pipeline.build-queued`.
5. Zero cross-references with `forge` repo docs in either direction.
6. Intent classification mechanism still open (D11: local Nemotron Nano vs cloud API vs rule-based + LLM fallback).
7. Jarvis has no declared agent manifest yet — it can't register itself on `fleet.register`.

**Recommended integration pattern — Pattern A (with one addition):**

> Jarvis publishes `pipeline.build-queued.{feature_id}` directly to the JetStream `PIPELINE` stream. Forge consumes it. CLI `forge queue` publishes to the same topic. Both are valid triggers.
>
> **Addition:** Forge also registers on `fleet.register` as an agent (`agent_id: forge`, intents: `build.*`, `pipeline.*`) so that Jarvis's CAN-bus discovery can surface it. Registration is for *discovery* (how Jarvis knows which agent handles "build a feature"); the *actual dispatch* is still a JetStream publish to `pipeline.build-queued`, not an `agents.command.forge` request/reply.

**Why Pattern A beats B/C/D:**
- **B (Jarvis → `agents.command.forge`):** requires Forge to implement incoming agent-command handlers and then re-enqueue on its own JetStream consumer — a double-hop. It also blurs the "Forge is a JetStream consumer" contract in the anchor.
- **C (Jarvis shells out to `forge queue` CLI):** trivial to implement but loses all NATS metadata (no correlation IDs, no heartbeat, no originating adapter). Acceptable as a day-one fallback, not as the target.
- **D (new Forge NATS API layer):** unnecessary complexity — `pipeline.build-queued` already *is* the API.

**Minimum wiring for Pattern A (when Jarvis gets source code):**

1. **In `nats-core`:** add `BuildQueuedPayload` (see §2.1) with fields `feature_id`, `repo`, `branch`, `feature_yaml_path`, `max_turns`, `sdk_timeout`, `wave_gating`, `triggered_by: Literal["cli", "jarvis", "forge"]`, `originating_adapter: Optional[str]`, `user_id: Optional[str]`, `queued_at: datetime`. Anchor §7 already sketches this — just add `originating_adapter` + `user_id` to cover Jarvis's multi-modal reality.
2. **In `forge`:** one JetStream pull consumer on `pipeline.build-queued.>`. It does not distinguish CLI from Jarvis — both push `BuildQueuedPayload`, both end up in PREPARING. `forge history` can surface `triggered_by` so Rich can see which builds came from which source.
3. **In `jarvis`:** when intent classification resolves to "build", publish `BuildQueuedPayload` to the topic. No call/reply — fire-and-forget, then watch `pipeline.build-progress.*` for status streaming back to the originating adapter.
4. **Forge's agent manifest** — new file. `agent_id: forge`, intents: `build.*` / `pipeline.*`. Register on startup via `NATSKVManifestRegistry.register_agent()`. `max_concurrent: 1` (matches ADR-SP-012, contradicts `forge-build-plan.md:415`).

---

## 3. Cross-cutting: Jarvis → Forge integration gap

**This is the single biggest missing piece in the anchor and the build plan.** Nothing in the forge repo today tells Rich (or a future implementer) how human-originated build requests get into JetStream when they come from anywhere other than a terminal.

**Proposed anchor addition (§5.0, before current §5 Build Queue):**

> ### 5.0 Build Request Sources
>
> Builds enter JetStream as `pipeline.build-queued.{feature_id}` messages. There are three supported sources:
>
> 1. **CLI** — `forge queue FEAT-XXX` publishes directly. The default and simplest path.
> 2. **Jarvis** — When Rich interacts with Jarvis (voice via Reachy Mini, Telegram, dashboard, CLI wrapper), Jarvis classifies the intent, discovers Forge via the `fleet.register` / `agent-registry` KV, and publishes `BuildQueuedPayload` with `triggered_by="jarvis"` and `originating_adapter=<voice|telegram|dashboard|cli>`. Forge consumes the same topic as for CLI.
> 3. **Future notification adapters** — Slack, email, GitHub webhook (out of Phase 4 scope).
>
> Forge does not distinguish between sources at the consumer level. Discoverability is handled by Forge registering on `fleet.register` as an agent with intents `build.*` and `pipeline.*`; triggering is handled by anyone publishing to `pipeline.build-queued`.

This closes Gap A from §1.1 and resolves the integration question in one stroke.

---

## 4. Cross-cutting: Specialist-agent dual-role wiring

**This is the second biggest gap** — Rich has committed to PO + Architect as the first two real runs, but the specialist-agent repo cannot deploy two instances of the same binary without code changes.

**Proposed anchor addition (§4 Stage 2 clarification + new §3.1 subsection):**

> ### 3.1 Specialist Agent Deployment Model
>
> The Forge's early pipeline stages call two distinct specialist agents by role: **Product Owner** (Stage 1 / Specification Review) and **Architect** (Stage 2 / Architecture Review). Both are deployments of the same `specialist-agent` binary with different `--role` flags and distinct `agent_id`s (`product-owner-agent`, `architect-agent`). Both register on `fleet.register` independently, subscribe to their own `agents.command.{agent_id}` topic, and publish results to `agents.result.{agent_id}`.
>
> This deployment model is the validation target for `specialist-agent` Phase 3.

**Required changes in `specialist-agent` before this milestone can run** (detailed in §2.3):

1. Refactor `adapters/manifest.py` into a role-parameterised builder: `get_manifest(role_id: str) -> AgentManifest`. Derive `agent_id` from `role_id` (default) or from `SPECIALIST_AGENT_ID` env var (override for tests).
2. Create `get_product_owner_manifest()` with PO-specific intents (`product.*`, `roadmap.*`, `prioritization.*`) and tools from `roles/product-owner/role.yaml`.
3. Wire `--role` → manifest builder in `cli/main.py:2168`.
4. Make `CommandRouter.TOOL_TO_COMMAND` role-aware or instantiate a different router per role.
5. Align result payload shape with Forge's expected structure (`coach_score`, `criterion_breakdown`, `detection_findings`) — either wrap role output inside this shape or update Forge's expectation.
6. Write a `docker-compose.specialist-agents.yml` fragment (or run-script) that launches two containers with different `--role` and verifies both appear in `agent-registry` KV.
7. Add an e2e test that publishes a command to each `agents.command.{architect,product-owner}-agent` and asserts both respond.

Until step 5 is resolved (result payload shape), the Forge's `call_agent_tool()` in FEAT-FORGE-003 will need a translation layer, which is wasted effort. Fix it at source.

---

## 5. Correction list (file-scoped punch list)

Ordered by blocking severity. Format: `<file>:<section>` → `<what to change>` → `<why>`.

### Anchor additions (high leverage — update v2.1 to v2.2)

1. `forge/docs/research/forge-pipeline-architecture.md:§5` → Insert new subsection §5.0 "Build Request Sources" per text in §3 above → Closes the Jarvis integration gap that is currently only carried verbally.
2. `forge/docs/research/forge-pipeline-architecture.md:§3` → Insert new subsection §3.1 "Specialist Agent Deployment Model" per text in §4 above → Makes the PO + Architect dual-role operational reality explicit.
3. `forge/docs/research/forge-pipeline-architecture.md:§7 Topics` → Replace `agents.commands.{agent_id}` / `agents.results.{agent_id}` with `agents.command.{agent_id}` / `agents.result.{agent_id}` (singular) → Match shipping `nats-core`; avoid rewriting a 98%-covered library.
4. `forge/docs/research/forge-pipeline-architecture.md:§3 Key streams` → Update retention to match `nats-infrastructure` reality (PIPELINE 7d, AGENTS 7d or 24h per decision, SYSTEM 1h) → Either the anchor or the infra is wrong; the infra is installed.
5. `forge/docs/research/forge-pipeline-architecture.md:§3` → Add `FLEET`, `JARVIS`, `NOTIFICATIONS` streams to the key streams list → They exist in `nats-infrastructure`, are Ship's-Computer-relevant, and should be anchored.
6. `forge/docs/research/forge-pipeline-architecture.md:§3 + ADR-SP-013` → Decide the role of the `pipeline-state` NATS KV bucket. Either delete it from `nats-infrastructure` and keep SQLite as the single source of runtime state, or document it as the third store and clarify what lives where → Today there are three potential stores (JetStream, SQLite, pipeline-state KV) and only two are documented.
7. `forge/docs/research/forge-pipeline-architecture.md:§7 Payloads` → Add `originating_adapter: Optional[str]` and `user_id: Optional[str]` to `BuildQueuedPayload`; change `triggered_by` type to `Literal["cli", "jarvis", "forge"]` → Supports multi-modal Jarvis triggering.

### `forge-pipeline-orchestrator-refresh.md` corrections

8. `forge-pipeline-orchestrator-refresh.md:§"Revised Architecture"` → Rewrite opening paragraph to align framing with v2.1 ("Forge is the NATS-native pipeline orchestrator; confidence gates are how it decides when to involve Rich") → Remove the "checkpoint manager" reframe that contradicts v2.1 emphasis.
9. `forge-pipeline-orchestrator-refresh.md:§"Revised Pipeline Flow"` → Add subsection mapping the greenfield flow blocks to anchor §4 five stages → Reconcile taxonomy.
10. `forge-pipeline-orchestrator-refresh.md:lines 215–217` → Name the state machine states (IDLE / PREPARING / RUNNING / FINALISING / PAUSED / COMPLETE / FAILED) → Currently referenced but not defined.
11. `forge-pipeline-orchestrator-refresh.md:~line 590` → Add new "Jarvis as upstream trigger" subsection referencing anchor §5.0 → Close the Jarvis gap.
12. `forge-pipeline-orchestrator-refresh.md:lines 453–459` → Decide the fate of `FeaturePlannedPayload` / `FeatureReadyForBuildPayload`. Either promote into anchor §7 or retire → Currently orphaned between nats-core (present) and anchor (absent).

### `forge-build-plan.md` corrections

13. `forge-build-plan.md:lines 38–47 (Hard Prerequisites)` → Caveat the "nats-core implemented" checkbox: change to "implemented at 98% coverage; v2.1 payloads (`BuildQueuedPayload`, `BuildPausedPayload`, `StageCompletePayload`, `pipeline.build-queued/-paused/-resumed/-stage-complete/-stage-gated`) must be added in Phase 2" → Honest prerequisite.
14. `forge-build-plan.md:lines 104–115 (Feature Summary)` → Reconcile `FEAT-FORGE-001..008` with anchor §10 Phase 4 capability list. Either map each feature to anchor items or rewrite the feature list → The two decompositions currently differ in vocabulary and scope.
15. `forge-build-plan.md:line 415` → Change `nats_topic: agents.command.forge` — and set `max_concurrent: 1` not `3` → Fleet-index agrees on singular; ADR-SP-012 mandates sequential.
16. `forge-build-plan.md:lines 300–338 (Validation + FinProxy)` → Replace `python -m forge.cli greenfield --project …` with `forge queue FEAT-XXX --repo … --branch …` as the canonical CLI surface → Match anchor §5.
17. `forge-build-plan.md:lines 453–491 (`forge-pipeline-config.yaml` example)` → Reconcile the schema with anchor §4 `forge.yaml`. Either promote reviewer/critical_detections/escalation_channel into the anchor or strip them from the build plan → Two schemas in flight.
18. `forge-build-plan.md:lines 87–96 + 616–629 (Context Documents Available / Source Documents)` → Remove references to "Dev pipeline architecture" and "Dev pipeline system spec" (project knowledge). Add `forge/docs/research/forge-pipeline-architecture.md` as primary context → Make v2.1 the anchor for `/system-arch`.
19. `forge-build-plan.md:lines 409–446 (Forge Agent Manifest)` → Add intent patterns for `build.*` / `pipeline.*` visibility via Jarvis's CAN-bus discovery (already partly there). Update `max_concurrent: 1`. Add `triggered_by` support → Aligns with anchor §5.0.
20. `forge-build-plan.md:prerequisites` → Add: "Specialist-agent `--role` flag is wired to manifest builder, `get_product_owner_manifest()` exists, `agent_id` is derived from role or overridable, PO + Architect can run concurrently without collision" → Required for Rich's "PO + Architect first run" milestone.
21. `forge-build-plan.md (new section)` → Add "Jarvis Integration" subsection (1–2 paragraphs + Pattern A wiring) → Close the human-facing-entry-point gap.

### `fleet-master-index.md` corrections

22. `fleet-master-index.md:line 10 + Jarvis section` → Expand Jarvis description to include "dispatches build requests to the Forge after CAN-bus discovery" → Currently only describes specialist-agent dispatch.
23. `fleet-master-index.md:lines 146–148` → Add explicit build trigger mechanism: "Builds enter JetStream via `forge queue` CLI, Jarvis CAN-bus dispatch, or future notification adapters. All publish `pipeline.build-queued.{feature_id}`." → Currently describes output event, not input trigger.
24. `fleet-master-index.md:lines 472–535 (The Forge — Pipeline Orchestrator)` → `max_concurrent: 3` → `max_concurrent: 1`; keep `agents.command.forge` (singular, matches nats-core); add build-queue subscription description → Contradicts ADR-SP-012.
25. `fleet-master-index.md (repo inventory)` → Execute `TASK-update-fleet-index-d22.md` inline: rename architect-agent → specialist-agent, mark ideation-agent archived, product-owner-agent absorbed, architect-agent-mcp superseded, add lpa-platform → Repo inventory is stale by Rich's own task.

### `nats-core` corrections (codebase, not docs)

26. `nats-core/src/nats_core/events/_pipeline.py` → Add `BuildQueuedPayload`, `BuildPausedPayload`, `BuildResumedPayload`, `StageCompletePayload`, `StageGatedPayload` Pydantic models → Anchor §7 requires them.
27. `nats-core/src/nats_core/topics.py` → Add topics `BUILD_QUEUED`, `BUILD_PAUSED`, `BUILD_RESUMED`, `STAGE_COMPLETE`, `STAGE_GATED` on `Topics.Pipeline`; add `COMMAND_BROADCAST` on `Topics.Agents` → Required by §7.
28. `nats-core/src/nats_core/events/_pipeline.py:56` → Delete or `@deprecated` `FeaturePlannedPayload` and its topic `topics.py:79` → Anchor §11 removes it. Provide migration shim for any existing consumers.
29. `nats-core/src/nats_core/events/_pipeline.py:84` → Decide on `FeatureReadyForBuildPayload` (promote or retire) → Currently orphaned from anchor.
30. `nats-core/tests` → Add tests for the new payloads + topics to maintain ≥98% coverage → Build plan quality gate.

### `nats-infrastructure` corrections

31. `nats-infrastructure/streams/stream-definitions.json` → Reconcile retention values with the updated anchor (after correction 4). If the anchor is updated to 7d/7d/1h there is no change needed here → Prefer updating the anchor.
32. `nats-infrastructure/docs/design/specs/nats-infrastructure-system-spec.md` → Cross-reference `forge-pipeline-architecture.md` v2.1 in the stream-definitions rationale → Currently no cross-reference.

### `specialist-agent` corrections (codebase + docs)

33. `specialist-agent/src/specialist_agent/adapters/manifest.py:13–222` → Refactor `get_architect_agent_manifest()` into `get_manifest(role_id: str)` or add `get_product_owner_manifest()` etc. Derive `agent_id` from `role_id` or accept env-var override → Enables dual deployment.
34. `specialist-agent/src/specialist_agent/cli/main.py:2168` → Wire `--role` flag to manifest builder → Today the flag is ignored.
35. `specialist-agent/src/specialist_agent/adapters/command_router.py` → Make `TOOL_TO_COMMAND` and handler dispatch role-aware (or instantiate one router per role) → Today hardcoded to architect.
36. `specialist-agent/src/specialist_agent/adapters/nats_adapter.py (result publishing)` → Wrap role output in `{coach_score, criterion_breakdown, detection_findings, output}` shape compatible with Forge's `call_agent_tool()` expectation → Removes the need for a Forge-side translation layer.
37. `specialist-agent/docs/deployment` (new) → Add dual-role run instructions: example `docker compose` fragment or systemd unit launching two containers with different `--role` and `SPECIALIST_AGENT_ID`, asserting both land in `agent-registry` KV → Required to validate Rich's milestone.
38. `specialist-agent/tests/integration/test_dual_role.py` (new) → e2e test: two binaries, two agent_ids, Forge command to each, both respond with correctly-shaped results → Regression protection for the dual-deployment model.

### `jarvis` corrections

39. `jarvis/docs/research/ideas/jarvis-vision.md` → Add explicit section "Jarvis as Forge trigger" referencing `pipeline.build-queued` topic and Forge's `fleet.register` manifest → Close the bidirectional documentation gap.
40. `jarvis (new files when source begins)` → Implement Pattern A wiring per §2.4: Pydantic import from `nats-core`, publish `BuildQueuedPayload` when intent classification resolves to build, subscribe to `pipeline.build-progress.*` for status streaming back to originating adapter → Makes the integration real.

---

## 6. Build-readiness verdict

**⚠️ Ready to start Phase 1 after applying a subset of the correction list.**

**What can start immediately (Phase 1 — NATS infrastructure validation on GB10):**
- `nats-infrastructure` boots cleanly, streams provisioned, KV buckets in place.
- The anchor's Phase 1 validation test (publish a test message → JetStream persistence → AckWait redelivery behaviour) can run today using generic byte payloads.

**What must be done before Phase 2 (`nats-core` revision):**
- Resolve the singular/plural topic decision (correction 3).
- Decide retention values (correction 4).
- Decide fate of `pipeline-state` KV bucket (correction 6).
- Decide fate of `FeaturePlannedPayload` / `FeatureReadyForBuildPayload` (correction 28/29).

**What must be done before Phase 3 (Specialist-agent PO + Architect dual run):**
- Corrections 33–38 in `specialist-agent` (refactor manifest, wire `--role`, role-aware command router, result payload shape, deployment docs, e2e test).

**What must be done before Phase 4 (Forge core pipeline build):**
- Corrections 1–7 to the anchor.
- Corrections 26–30 to `nats-core`.
- Corrections 13–21 to `forge-build-plan.md` (before `/system-arch` is run with it as context).
- Corrections 8–12 to `forge-pipeline-orchestrator-refresh.md` (same reason).
- Corrections 22–25 to `fleet-master-index.md`.

**What is not yet blocking but should be added to the backlog:**
- Jarvis source-code work (correction 40) — not on the critical path for Forge-via-CLI, but required for "Rich talks to Jarvis, Jarvis queues a build."

**Biggest risks if Rich starts building immediately without corrections:**
1. `/system-arch` for the Forge will absorb the orchestrator-refresh's "checkpoint manager" framing and produce an architecture that doesn't match v2.1.
2. The Forge implementation will assume `nats-core` has `BuildQueuedPayload` and discover mid-build that it doesn't.
3. The PO + Architect dual run will collide on `agent_id` and fail to register both.
4. Jarvis integration will be bolted on post-hoc with an ad-hoc topic that isn't in the anchor.

---

## 7. Recommended follow-up tasks

After this review is accepted, create these tasks via `/task-create`. Ordered by dependency.

**Wave 1 — Doc correction pass (no code) — blocking everything else**

```
/task-create "Apply v2.2 anchor additions (Jarvis §5.0, specialist dual-role §3.1, retention reconcile, topic naming)" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[docs,architecture,anchor]
```

```
/task-create "Correct forge-build-plan.md to match anchor v2.2 (feature map, CLI surface, prerequisites, context docs, Jarvis section)" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[docs,forge-build-plan]
```

```
/task-create "Correct forge-pipeline-orchestrator-refresh.md framing, 5-stage map, state machine states, Jarvis section" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[docs,forge-orchestrator-refresh]
```

```
/task-create "Correct fleet-master-index.md build-trigger description + execute pending TASK-update-fleet-index-d22 inline" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[docs,fleet-index]
```

**Wave 2 — nats-core revision (Phase 2 of anchor roadmap)**

```
/task-create "nats-core: add BuildQueuedPayload, BuildPausedPayload, BuildResumedPayload, StageCompletePayload, StageGatedPayload + topics; retire FeaturePlannedPayload" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[nats-core,payloads,anchor-v2.2]
```

```
/task-create "nats-core: add integration tests for new pipeline payloads against live NATS on GB10" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[nats-core,integration-tests]
```

**Wave 3 — specialist-agent dual-role enablement (Phase 3 of anchor roadmap)**

```
/task-create "specialist-agent: refactor manifest.py to role-parameterised builder; derive agent_id from role_id or env" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[specialist-agent,dual-role]
```

```
/task-create "specialist-agent: wire --role CLI flag to manifest builder; add get_product_owner_manifest()" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[specialist-agent,dual-role]
```

```
/task-create "specialist-agent: role-aware CommandRouter; Forge-shaped result payload (coach_score/criterion_breakdown/detection_findings wrapper)" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[specialist-agent,dual-role]
```

```
/task-create "specialist-agent: docker-compose fragment + e2e test for concurrent architect + product-owner deployment" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[specialist-agent,dual-role,e2e]
```

**Wave 4 — nats-infrastructure hygiene (non-blocking)**

```
/task-create "nats-infrastructure: decide fate of pipeline-state KV bucket (consolidate with SQLite or document as third store)" \
  task_type:review decision_required:true related_to:TASK-REV-A1F2 tags:[nats-infrastructure,storage-decision]
```

**Wave 5 — Jarvis integration (after Forge core exists)**

```
/task-create "Jarvis: bootstrap repo with agent manifest + nats-core client + build-queue dispatch (Pattern A)" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[jarvis,integration,forge-trigger]
```

**Wave 6 — Graphiti seeding (close the empty-graph loop)**

```
/task-create "Seed Graphiti with v2.2 anchor decisions, Jarvis→Forge integration pattern, specialist dual-role rationale, PM Adapter removal history" \
  task_type:implementation related_to:TASK-REV-A1F2 tags:[graphiti,knowledge-graph,seed]
```

---

## Appendix A — Graphiti query results

All Graphiti queries (`search_nodes`, `search_memory_facts`, `get_episodes`) returned **empty** for Forge, Jarvis, specialist-agent, NATS, PM Adapter, dual-role, and general episodes. The knowledge graph is not seeded with any of this project's history.

**Finding:** Graphiti is silent on decisions the docs assert strongly (NATS-native, PM Adapter removal, RequireKit deprecation, Jarvis's role, dual-role deployment). This is a gap in the graph, not a contradiction in the docs. Wave 6 follow-up task above addresses it.

## Appendix B — Review scope honoured

- [x] Anchor doc read end-to-end.
- [x] Graphiti queried (`search_nodes`, `search_memory_facts`, `get_episodes`) — empty; gap noted.
- [x] All `docs/research/ideas/` files covered (audited or spot-checked).
- [x] `docs/product/roadmap.md` + `feature_spec_inputs/` covered.
- [x] `nats-core` inspected (README, src, tests, topic registry, schemas, client, manifests).
- [x] `nats-infrastructure` inspected (docker-compose, NATS config, streams, KV buckets, scripts, docs).
- [x] `specialist-agent` inspected (roles, harness, NATS adapter, command router, manifest, Graphiti wiring, phase docs).
- [x] `jarvis` inspected (vision doc — the only artefact that exists).
- [x] Every removed concept (Kanban, Linear, PM Adapter, `ready-for-dev`, RequireKit NATS, `feature-planned`, `ticket-updated`, v0 subprocess, `PipelineTransport`) checked — no live references found; `FeaturePlannedPayload` still exists in `nats-core` and is the last loose end.
- [x] Jarvis upstream role explicitly addressed (§3, §2.4, correction list).
- [x] PO + Architect dual-role deployment explicitly addressed (§4, §2.3, correction list).
- [x] Build-readiness verdict recorded with justification (§6).
- [x] No code written. No doc edits made outside this alignment report.

---

## Appendix C — `BuildQueuedPayload` full design (Jarvis-aware)

This is the concrete Pydantic model to add to `nats-core` in correction 26. It expands anchor §7's sketch to cover Jarvis multi-modal metadata, correlation tracing, retry semantics, and per-build config overrides — without bloating the payload beyond what Forge actually needs.

### Design principles

1. **One topic, many sources.** CLI, Jarvis, and future notification adapters all publish the same payload to `pipeline.build-queued.{feature_id}`. Forge does not branch on source at the consumer level. Source is carried in the payload for history and diagnostics.
2. **Forward-compatible.** New trigger sources (e.g. GitHub webhook adapter) add values to `triggered_by` and `originating_adapter` literals; they do not add fields.
3. **Correlation first.** Jarvis fires and forgets, but streams progress back to its originating adapter. Every build-queued message carries the correlation identifiers needed to route `pipeline.build-progress.*` and `pipeline.build-complete.*` back to the originating voice/Telegram/dashboard session.
4. **No config smuggling.** Thresholds live in `forge.yaml`, not in the payload. A narrow `config_overrides` field exists for per-build exceptions (e.g. "this one build gets 10 turns not 5") but is explicitly a thin override, not a second config surface.
5. **Deserialisation-safe.** All fields Forge *consumes* are validated at publish time. Extra fields from future callers are allowed via Pydantic `ConfigDict(extra='allow')` so old Forge versions don't crash on newer payloads.

### The model

```python
# nats-core/src/nats_core/events/_pipeline.py

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re

FEATURE_ID_PATTERN = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

TriggerSource = Literal["cli", "jarvis", "forge-internal", "notification-adapter"]
OriginatingAdapter = Literal[
    "terminal",       # forge queue typed at a shell
    "voice-reachy",   # Reachy Mini voice interface
    "telegram",       # Telegram bot
    "slack",          # Slack slash command or DM
    "dashboard",      # Jarvis web dashboard
    "cli-wrapper",    # programmatic CLI invocation (scripts, CI)
]


class BuildQueuedPayload(BaseModel):
    """Published to pipeline.build-queued.{feature_id} to trigger a Forge build.

    Any trigger source (CLI, Jarvis, future adapters) publishes this payload to
    the same JetStream topic. Forge consumes without distinguishing sources at
    the consumer level; the triggered_by / originating_adapter fields are for
    history, diagnostics, and routing progress events back to the originator.
    """

    model_config = ConfigDict(extra="allow")  # forward-compatible

    # --- identity ---
    feature_id: str = Field(..., description="FEAT-XXX identifier")
    repo: str = Field(..., description="GitHub org/repo, e.g. guardkit/lpa-platform")
    branch: str = Field(default="main", description="Base branch to branch from")
    feature_yaml_path: str = Field(
        ..., description="Path to feature YAML spec, relative to repo root"
    )

    # --- build config (narrow overrides only) ---
    max_turns: int = Field(
        default=5, ge=1, le=20,
        description="Max AutoBuild Player-Coach turns per task before escalation",
    )
    sdk_timeout_seconds: int = Field(
        default=1800, ge=60, le=7200,
        description="Max seconds per GuardKit autobuild subprocess invocation",
    )
    wave_gating: bool = Field(
        default=False,
        description="If true, Forge pauses between waves for explicit approval",
    )
    config_overrides: Optional[dict] = Field(
        default=None,
        description=(
            "Narrow per-build overrides of forge.yaml thresholds. "
            "Keys must match forge.yaml top-level keys. Use sparingly."
        ),
    )

    # --- provenance ---
    triggered_by: TriggerSource = Field(
        ..., description="Which layer originated this build-queued message"
    )
    originating_adapter: Optional[OriginatingAdapter] = Field(
        default=None,
        description=(
            "Which Jarvis adapter the human interacted with. "
            "Required when triggered_by == 'jarvis'. None for CLI."
        ),
    )
    originating_user: Optional[str] = Field(
        default=None,
        description="User identifier (e.g. 'rich'). Free-form for now.",
    )

    # --- correlation & tracing ---
    correlation_id: str = Field(
        ..., description="Stable ID for tracing this build across stages and streams"
    )
    parent_request_id: Optional[str] = Field(
        default=None,
        description=(
            "For Jarvis-triggered builds, the ID of the jarvis.dispatch.* message "
            "that spawned this build. Lets Jarvis correlate progress events back "
            "to the originating conversation/session."
        ),
    )

    # --- retry semantics (populated by JetStream, not by publishers) ---
    retry_count: int = Field(
        default=0, ge=0,
        description=(
            "Incremented by Forge on crash-recovery redelivery. Publishers "
            "should leave this at 0; Forge updates it in SQLite, not in the "
            "JetStream message (JetStream redelivery carries its own metadata)."
        ),
    )

    # --- timing ---
    requested_at: datetime = Field(
        ..., description="When the request was made at the originating layer"
    )
    queued_at: datetime = Field(
        ..., description="When the message was published to JetStream"
    )

    # --- validators ---
    @field_validator("feature_id")
    @classmethod
    def _validate_feature_id(cls, v: str) -> str:
        if not FEATURE_ID_PATTERN.match(v):
            raise ValueError(
                f"feature_id must match {FEATURE_ID_PATTERN.pattern}, got {v!r}"
            )
        return v

    @field_validator("repo")
    @classmethod
    def _validate_repo(cls, v: str) -> str:
        if not REPO_PATTERN.match(v):
            raise ValueError(f"repo must be 'org/name' format, got {v!r}")
        return v

    @field_validator("originating_adapter")
    @classmethod
    def _adapter_required_for_jarvis(cls, v, info):
        triggered_by = info.data.get("triggered_by")
        if triggered_by == "jarvis" and v is None:
            raise ValueError(
                "originating_adapter is required when triggered_by == 'jarvis'"
            )
        if triggered_by == "cli" and v not in (None, "terminal", "cli-wrapper"):
            raise ValueError(
                "CLI trigger must use originating_adapter 'terminal', 'cli-wrapper', or None"
            )
        return v
```

### Example payloads

**CLI trigger (simplest — Rich at a terminal):**

```json
{
  "feature_id": "FEAT-LPA-042",
  "repo": "guardkit/lpa-platform",
  "branch": "main",
  "feature_yaml_path": "specs/FEAT-LPA-042.yaml",
  "max_turns": 5,
  "sdk_timeout_seconds": 1800,
  "wave_gating": false,
  "config_overrides": null,
  "triggered_by": "cli",
  "originating_adapter": "terminal",
  "originating_user": "rich",
  "correlation_id": "bld-2026-04-15T16-30-12-a7f2",
  "parent_request_id": null,
  "retry_count": 0,
  "requested_at": "2026-04-15T16:30:12.147Z",
  "queued_at": "2026-04-15T16:30:12.189Z"
}
```

**Jarvis voice trigger (Rich says "Jarvis, build FEAT-LPA-042 with extra turns"):**

```json
{
  "feature_id": "FEAT-LPA-042",
  "repo": "guardkit/lpa-platform",
  "branch": "main",
  "feature_yaml_path": "specs/FEAT-LPA-042.yaml",
  "max_turns": 10,
  "sdk_timeout_seconds": 1800,
  "wave_gating": false,
  "config_overrides": {
    "confidence_thresholds": {
      "autobuild": {"flag_for_review": 0.7}
    }
  },
  "triggered_by": "jarvis",
  "originating_adapter": "voice-reachy",
  "originating_user": "rich",
  "correlation_id": "bld-2026-04-15T16-31-04-b9c1",
  "parent_request_id": "jarvis-dispatch-2026-04-15T16-31-02-9e44",
  "retry_count": 0,
  "requested_at": "2026-04-15T16:31:02.512Z",
  "queued_at": "2026-04-15T16:31:04.073Z"
}
```

### Serialisation and topic

- **Topic:** `pipeline.build-queued.{feature_id}` (e.g. `pipeline.build-queued.FEAT-LPA-042`)
- **Stream:** `PIPELINE` (7-day retention per nats-infrastructure — see ADR-SP-017 below)
- **Encoding:** Pydantic `model_dump_json()` wrapped in the `nats-core` `MessageEnvelope` with `schema_version`, `envelope_id`, `correlation_id`.
- **Consumer:** Forge pull consumer `forge-build-queue`, `AckWait=60m`, durable, max-deliveries configurable (default 3 for crash recovery, then fail to DLQ).

### Compatibility notes

- **Forward compat:** `model_config = ConfigDict(extra="allow")` means a future Jarvis can add `session_context: dict` without breaking older Forge builds.
- **Backward compat:** `originating_adapter` is `Optional` with per-source validation, so a CLI publisher that predates Jarvis integration does not need to supply it.
- **Migration from FeaturePlanned:** Correction 28 retires `FeaturePlannedPayload`. Any callers still publishing `pipeline.feature-planned.*` should be pointed at `pipeline.build-queued.*` with `triggered_by="forge-internal"` or `"cli"`. Publish a `MigrationGuide.md` in `nats-core/docs/design/migrations/` when the deprecation lands.

### Correlation flow back to Jarvis

When Jarvis publishes `BuildQueuedPayload` with `parent_request_id="jarvis-dispatch-…"`, Forge carries the `correlation_id` forward into every `BuildStarted`, `BuildProgress`, `StageComplete`, `BuildPaused`, `BuildComplete`, and `BuildFailed` payload it emits. Jarvis subscribes to `pipeline.build-*.{feature_id}` filtered by `correlation_id` and streams human-readable status back to the originating adapter (voice feedback, Telegram message, dashboard update).

This gives Rich end-to-end visibility ("Jarvis, what happened to that build?" → Jarvis queries its own correlation table → replies with last known stage + coach score) without Forge needing to know anything about Jarvis sessions.

### Tests to add in `nats-core`

1. `test_build_queued_payload_validates_feature_id_format` — rejects `BAD-ID`, accepts `FEAT-LPA-042`
2. `test_build_queued_payload_validates_repo_format` — rejects `lpa-platform`, accepts `guardkit/lpa-platform`
3. `test_build_queued_payload_adapter_required_for_jarvis` — `triggered_by="jarvis"` with `originating_adapter=None` raises
4. `test_build_queued_payload_cli_rejects_voice_adapter` — `triggered_by="cli"` with `originating_adapter="voice-reachy"` raises
5. `test_build_queued_payload_round_trip_through_envelope` — serialise through `MessageEnvelope`, publish to test NATS, consume, deserialise, assert field equality
6. `test_build_queued_payload_forward_compat_extra_fields` — add unknown field, assert deserialise does not raise
7. `test_build_queued_payload_correlation_id_required` — missing `correlation_id` raises
8. `test_config_overrides_accepts_forge_yaml_shape` — a valid `forge.yaml` sub-tree parses; invalid keys do not need to (free-form dict)

---

## Appendix D — `specialist-agent` manifest refactor design (surgical)

This is the concrete plan for corrections 33–38. Goal: make `specialist-agent` deployable as two concurrent instances (Product Owner + Architect) with distinct `agent_id`s, role-aware command routing, and a result-payload shape that matches Forge's `call_agent_tool()` expectation — without disturbing anything else.

### Current state (diagnosis)

```
cli/main.py:2168          →  NATSAdapter(manifest=get_architect_agent_manifest(), ...)
                              # ignores --role flag entirely

adapters/manifest.py:13–222
                          →  get_architect_agent_manifest() -> AgentManifest
                              # hardcoded agent_id="architect-agent"
                              # hardcoded intents, tools, patterns
                              # no sibling function for product-owner, ideation

adapters/command_router.py:114–126
                          →  TOOL_TO_COMMAND = {"architect_greenfield": …, …}
                              # architect-only dispatch table
                              # no role parameterisation

adapters/nats_adapter.py  →  CommandRouter fixed at instantiation time

evaluation/types.py       →  Evaluation(criterion_scores, detection_findings, ...)
                              # exists internally but NEVER reaches the NATS ResultPayload
                              # the NATS result wraps raw role output (ConversationStarter, ProductRoadmap)
                              # Forge's call_agent_tool() expects coach_score/criterion_breakdown/detection_findings
```

Net effect: you can start a second instance with `--role product-owner` and it will run the PO role *internally* (loader resolves the right YAML and handler), but on the NATS side it registers as `architect-agent`, subscribes to `agents.command.architect-agent`, and publishes PO output shaped like architect output. **Two instances collide on fleet registration; Forge cannot tell them apart.**

### Target state

```
cli/main.py               →  NATSAdapter(manifest=build_manifest_for_role(role_id), ...)

roles/registry.py (new)   →  ROLE_REGISTRY: dict[str, RoleConfig]
                              # single source of truth: role_id -> manifest factory,
                              # command map, default agent_id

adapters/manifest.py      →  build_manifest_for_role(role_id, agent_id_override=None)
                              # factory that reads ROLE_REGISTRY
                              # agent_id = override or registry default

adapters/command_router.py
                          →  CommandRouter.for_role(role_id)
                              # instantiates with role-specific TOOL_TO_COMMAND

adapters/result_wrapper.py (new)
                          →  wrap_role_output(role_id, raw_output, evaluation)
                              -> {coach_score, criterion_breakdown,
                                  detection_findings, role_output}
                              # single place that shapes the NATS ResultPayload
                              # for Forge compatibility
```

### Refactor plan (surgical, 6 steps)

Each step is independently committable and independently testable. Feature-flagged behind `--role` flag being non-default — existing architect deployments keep working unchanged until the final commit flips the default path.

#### Step 1 — Introduce the role registry (no behaviour change)

**New file:** `src/specialist_agent/roles/registry.py`

```python
from dataclasses import dataclass
from typing import Callable
from nats_core.manifest import AgentManifest

@dataclass(frozen=True)
class RoleConfig:
    role_id: str
    default_agent_id: str
    manifest_factory: Callable[[str], AgentManifest]  # takes agent_id, returns manifest
    tool_to_command: dict[str, str]                    # for CommandRouter
    output_handler_import_path: str                    # "roles.architect.handler.ArchitectOutputHandler"

ROLE_REGISTRY: dict[str, RoleConfig] = {}

def register_role(config: RoleConfig) -> None:
    if config.role_id in ROLE_REGISTRY:
        raise ValueError(f"Role {config.role_id!r} already registered")
    ROLE_REGISTRY[config.role_id] = config

def get_role(role_id: str) -> RoleConfig:
    if role_id not in ROLE_REGISTRY:
        raise KeyError(
            f"Unknown role {role_id!r}. Registered roles: {list(ROLE_REGISTRY)}"
        )
    return ROLE_REGISTRY[role_id]
```

**Tests:** `tests/roles/test_registry.py` — register, lookup, duplicate rejection, unknown rejection.

**Behaviour change:** none yet. Registry is introduced but nothing uses it.

#### Step 2 — Refactor `manifest.py` to a factory (architect unchanged)

**Edit:** `src/specialist_agent/adapters/manifest.py`

```python
# Keep the existing get_architect_agent_manifest() untouched for now — it will
# be wrapped by the factory below.

def build_manifest_for_role(
    role_id: str, agent_id_override: str | None = None
) -> AgentManifest:
    """Produce an AgentManifest for the given role.

    agent_id is taken from the env var SPECIALIST_AGENT_ID if set, else
    agent_id_override, else the role registry default.
    """
    from specialist_agent.roles.registry import get_role
    import os

    role = get_role(role_id)
    agent_id = (
        os.environ.get("SPECIALIST_AGENT_ID")
        or agent_id_override
        or role.default_agent_id
    )
    return role.manifest_factory(agent_id)


def get_architect_agent_manifest() -> AgentManifest:
    """Legacy entrypoint — kept for backward compatibility, will be removed in
    a follow-up task once nothing calls it."""
    return build_manifest_for_role("architect")
```

**Then** add the architect's `manifest_factory` — a function that takes an `agent_id` and returns the existing hardcoded manifest with that `agent_id` substituted in:

```python
def _architect_manifest_factory(agent_id: str) -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,  # was hardcoded "architect-agent"
        # ... rest of existing get_architect_agent_manifest() body
    )
```

**Register it** in `src/specialist_agent/roles/architect/__init__.py`:

```python
from specialist_agent.roles.registry import register_role, RoleConfig
from specialist_agent.adapters.manifest import _architect_manifest_factory

register_role(RoleConfig(
    role_id="architect",
    default_agent_id="architect-agent",
    manifest_factory=_architect_manifest_factory,
    tool_to_command={
        "architect_greenfield": "greenfield",
        "architect_feature": "feature",
        # ... existing architect tool map
    },
    output_handler_import_path=(
        "specialist_agent.roles.architect.handler.ArchitectOutputHandler"
    ),
))
```

**Tests:**
- `test_architect_manifest_factory_respects_env_override` — set `SPECIALIST_AGENT_ID=weird-architect-1`, assert manifest `agent_id` matches
- `test_architect_manifest_factory_default_agent_id` — no env, no override → `architect-agent`
- `test_get_architect_agent_manifest_still_works` — legacy path still produces a working manifest

**Behaviour change:** still none for existing deployments.

#### Step 3 — Create the Product Owner manifest + registry entry

**New:** `_product_owner_manifest_factory(agent_id)` in `adapters/manifest.py`, producing a manifest with PO-specific intents and tools. Pull intent patterns from `roles/product-owner/role.yaml`:

```python
def _product_owner_manifest_factory(agent_id: str) -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,
        name="Product Owner Agent",
        description=(
            "Extracts product requirements, prioritises features, produces "
            "roadmaps and feature briefs. Runs on the specialist-agent unified "
            "harness with the product-owner role."
        ),
        trust_tier="core",
        nats_topic=f"agents.command.{agent_id}",
        max_concurrent=1,
        intents=[
            IntentCapability(
                pattern="product.*",
                signals=["product", "roadmap", "feature", "prioritise", "brief"],
                confidence=0.90,
            ),
            IntentCapability(
                pattern="roadmap.*",
                signals=["roadmap", "priorities", "backlog", "planning"],
                confidence=0.85,
            ),
            IntentCapability(
                pattern="prioritization.*",
                signals=["prioritise", "rank", "ordering", "trade-off"],
                confidence=0.80,
            ),
        ],
        tools=[
            ToolCapability(
                name="po_extract",
                description="Extract product requirements from raw input",
                risk_level="read_only",
                async_mode=True,
            ),
            ToolCapability(
                name="po_evolve",
                description="Evolve an existing roadmap with new priorities",
                risk_level="read_only",
                async_mode=True,
            ),
            ToolCapability(
                name="po_feature_brief",
                description="Produce a feature brief for downstream architect/spec work",
                risk_level="read_only",
                async_mode=True,
            ),
        ],
    )
```

Register in `src/specialist_agent/roles/product_owner/__init__.py`:

```python
register_role(RoleConfig(
    role_id="product-owner",
    default_agent_id="product-owner-agent",
    manifest_factory=_product_owner_manifest_factory,
    tool_to_command={
        "po_extract": "extract",
        "po_evolve": "evolve",
        "po_feature_brief": "feature_brief",
    },
    output_handler_import_path=(
        "specialist_agent.roles.product_owner.handler.ProductOwnerOutputHandler"
    ),
))
```

**Tests:**
- `test_product_owner_manifest_factory_default_agent_id` → `product-owner-agent`
- `test_product_owner_intents_match_role_yaml` — load YAML, assert intent patterns match

**Behaviour change:** PO is now *registerable* but nothing in the CLI path uses it yet.

#### Step 4 — Role-aware command router

**Edit:** `src/specialist_agent/adapters/command_router.py`

Replace the module-level `TOOL_TO_COMMAND` with an instance attribute:

```python
class CommandRouter:
    def __init__(self, tool_to_command: dict[str, str], ...):
        self.tool_to_command = tool_to_command
        # ... existing init

    @classmethod
    def for_role(cls, role_id: str, ...) -> "CommandRouter":
        from specialist_agent.roles.registry import get_role
        role = get_role(role_id)
        return cls(tool_to_command=role.tool_to_command, ...)
```

Callers that previously used the module-level dict now go through `CommandRouter.for_role(role_id)`.

**Tests:**
- `test_command_router_for_role_architect` → dispatches `architect_greenfield` → `greenfield` command
- `test_command_router_for_role_product_owner` → dispatches `po_extract` → `extract` command
- `test_command_router_for_role_rejects_unknown_tool` — PO router gets `architect_greenfield` → raises `UnknownToolError`

#### Step 5 — Wire `--role` flag in `cli/main.py`

**Edit:** `src/specialist_agent/cli/main.py:2168`

```python
# BEFORE
manifest = get_architect_agent_manifest()

# AFTER
from specialist_agent.adapters.manifest import build_manifest_for_role
from specialist_agent.adapters.command_router import CommandRouter

manifest = build_manifest_for_role(role_id=args.role)
command_router = CommandRouter.for_role(role_id=args.role)
nats_adapter = NATSAdapter(
    manifest=manifest,
    command_router=command_router,
    # ... existing args
)
```

Also ensure the startup banner logs `agent_id` derived from the manifest, not the hardcoded string.

**Tests (integration):**
- `test_serve_nats_with_role_architect_registers_as_architect_agent`
- `test_serve_nats_with_role_product_owner_registers_as_product_owner_agent`
- `test_serve_nats_with_role_and_env_override_uses_env_agent_id` — `SPECIALIST_AGENT_ID=test-po-1` → fleet register uses `test-po-1`

#### Step 6 — Forge-shaped result wrapper

**New file:** `src/specialist_agent/adapters/result_wrapper.py`

```python
from typing import Any
from specialist_agent.evaluation.types import Evaluation

def wrap_role_output(
    role_id: str,
    raw_output: Any,
    evaluation: Evaluation,
) -> dict:
    """Shape a role's output + evaluation into the dict Forge's call_agent_tool()
    expects.

    Forge expects these top-level keys in ResultPayload.result:
      - coach_score: float
      - criterion_breakdown: list[{criterion, score, rationale}]
      - detection_findings: list[{pattern, severity, evidence}]
      - role_output: dict  (role-specific shape, passed through)
      - role_id: str       (which role produced this — for Forge routing)
    """
    return {
        "role_id": role_id,
        "coach_score": evaluation.overall_score,
        "criterion_breakdown": [
            {
                "criterion": cs.criterion,
                "score": cs.score,
                "rationale": cs.rationale,
            }
            for cs in evaluation.criterion_scores
        ],
        "detection_findings": [
            {
                "pattern": df.pattern,
                "severity": df.severity,
                "evidence": df.evidence,
            }
            for df in evaluation.detection_findings
        ],
        "role_output": _serialise_role_output(raw_output),
    }


def _serialise_role_output(raw_output: Any) -> dict:
    """Convert role-specific output types (ConversationStarter, ProductRoadmap,
    etc.) into a JSON-safe dict. Defers to the type's own model_dump() if it's
    a Pydantic model."""
    if hasattr(raw_output, "model_dump"):
        return raw_output.model_dump()
    if isinstance(raw_output, dict):
        return raw_output
    raise TypeError(
        f"Cannot serialise role output of type {type(raw_output).__name__}"
    )
```

**Edit:** `adapters/command_router.py` (or wherever the NATS `ResultPayload` is published) to call `wrap_role_output(role_id, raw, eval)` instead of publishing raw output directly.

**Tests:**
- `test_wrap_architect_output` — ConversationStarter + Evaluation → dict with all five keys, Forge can deserialise
- `test_wrap_product_owner_output` — ProductRoadmap + Evaluation → same shape
- `test_wrap_raises_on_non_serialisable` — plain string input raises
- Integration: `test_nats_result_payload_matches_forge_schema` — publish a result, subscribe, assert keys present

### Agent-id derivation rules (spelled out)

Order of precedence (highest first):

1. **`SPECIALIST_AGENT_ID` env var** — for tests and non-standard deployments (`test-po-1`, `weird-architect-42`).
2. **`--agent-id` CLI flag** — optional, not currently present; add if step 5 needs it for ergonomics.
3. **Role registry default** — `architect-agent`, `product-owner-agent`, `ideation-agent`.

Rationale: env var wins so integration tests can spin up arbitrary named agents without code changes; CLI flag is the ergonomic "I want a custom name for this one run"; registry default is the production norm.

### Deployment: dual-role run script

**New file:** `specialist-agent/docker-compose.dual-role.yml`

```yaml
services:
  architect-agent:
    image: specialist-agent:latest
    command: serve-nats --role architect
    environment:
      SPECIALIST_AGENT_ID: architect-agent
      NATS_URL: nats://host.docker.internal:4222
    depends_on:
      - nats-infra

  product-owner-agent:
    image: specialist-agent:latest
    command: serve-nats --role product-owner
    environment:
      SPECIALIST_AGENT_ID: product-owner-agent
      NATS_URL: nats://host.docker.internal:4222
    depends_on:
      - nats-infra
```

Launching with `docker compose -f docker-compose.dual-role.yml up` should result in two entries in the `agent-registry` KV bucket, both responding to their own `agents.command.{id}` topic.

### E2E test (the one that proves it works)

**New file:** `tests/integration/test_dual_role_deployment.py`

```python
@pytest.mark.integration
async def test_dual_role_registration_and_routing(nats_client, running_compose):
    """Start architect + product-owner; verify both land in agent-registry,
    both accept a command addressed to their agent_id, both publish correctly
    Forge-shaped results, neither collides."""

    await running_compose.start("docker-compose.dual-role.yml")
    await wait_for_registration(nats_client, {"architect-agent", "product-owner-agent"})

    # Architect round-trip
    arch_result = await nats_client.request(
        "agents.command.architect-agent",
        architect_greenfield_command_payload(),
        timeout=30,
    )
    assert arch_result["role_id"] == "architect"
    assert "coach_score" in arch_result
    assert "criterion_breakdown" in arch_result
    assert "detection_findings" in arch_result

    # PO round-trip
    po_result = await nats_client.request(
        "agents.command.product-owner-agent",
        po_extract_command_payload(),
        timeout=30,
    )
    assert po_result["role_id"] == "product-owner"
    assert "coach_score" in po_result

    # Cross-routing rejection: architect must NOT respond to po_extract
    with pytest.raises(TimeoutError):
        await nats_client.request(
            "agents.command.architect-agent",
            po_extract_command_payload(),
            timeout=5,
        )
```

### Migration risk

- **Low.** The architect path is left intact through step 4. Step 5 (the CLI wire-up) is the only breaking commit, and it still routes `--role architect` (the default) to the same manifest. Any existing deployment that doesn't pass `--role` continues to behave identically.
- **Rollback:** each step is a single small commit; revert is surgical.
- **Biggest hazard:** step 6 (result wrapper) changes the on-the-wire `ResultPayload.result` shape. Any existing Forge code that unpacks the raw architect output will break. But Forge doesn't exist yet — that's the point. Landing this *before* Forge is implemented is exactly the right time.

---

## Appendix E — Draft ADRs for anchor v2.2

Four draft ADRs ready to paste into `forge/docs/research/forge-pipeline-architecture.md` under §9. Each is written in the same format as the existing ADR-SP-010..013. All four are independent and can be accepted individually.

### ADR-SP-014: Jarvis as Upstream Build Trigger (Pattern A)

- **Date:** 2026-04
- **Status:** Proposed (pending Rich's acceptance of TASK-REV-A1F2)
- **Context:** v2.1 documents `forge queue` as the only build trigger. Rich has since stated that Jarvis is the human-facing entry point — the place he actually interacts with the fleet via voice (Reachy Mini), Telegram, dashboard, or CLI wrappers. The `jarvis` repo's vision doc already designs a CAN-bus-style intent router that discovers agents via `fleet.register` and dispatches commands. The `nats-infrastructure` repo has already provisioned the matching `FLEET` stream and `agent-registry` KV bucket. The integration pattern is effectively sketched but not committed. Four options were evaluated during TASK-REV-A1F2:
  - **A.** Jarvis publishes `pipeline.build-queued.{feature_id}` directly to JetStream. Forge consumes the same topic as it does for CLI.
  - **B.** Jarvis invokes Forge as a fleet agent via `agents.command.forge`. Forge re-enqueues on its own JetStream consumer.
  - **C.** Jarvis shells out to the `forge queue` CLI.
  - **D.** A thin Forge NATS API layer (new subject) that Jarvis speaks to.
- **Decision:** Adopt **Pattern A**. Jarvis publishes `BuildQueuedPayload` (with `triggered_by="jarvis"` and `originating_adapter=<voice-reachy|telegram|slack|dashboard|cli-wrapper>`) to `pipeline.build-queued.{feature_id}`. Forge consumes without distinguishing sources at the consumer level — the payload carries source metadata for history and correlation. To support discovery, Forge *also* registers on `fleet.register` as an agent (`agent_id=forge`, intents: `build.*`, `pipeline.*`, `max_concurrent=1`), so Jarvis's CAN-bus routing can surface it. Registration is for discovery; triggering remains a JetStream publish.
- **Consequences:**
  - +One topic, many sources. CLI, Jarvis, and future notification adapters all publish the same payload to the same topic. Forge is agnostic.
  - +Pattern A preserves v2.1's "Forge is a JetStream consumer" contract — no double-hop via an agent-command handler.
  - +Correlation IDs and `parent_request_id` in `BuildQueuedPayload` let Jarvis stream progress back to the originating voice/Telegram/dashboard session without Forge knowing anything about Jarvis sessions.
  - +The `fleet.register` + `agent-registry` KV plumbing needed for discovery already exists in `nats-infrastructure`.
  - −Forge must now produce and publish an `AgentManifest` (small new file), which adds a sliver of Ship's-Computer coupling to a previously standalone service.
  - −The `BuildQueuedPayload` gains Jarvis-specific fields (`originating_adapter`, `parent_request_id`) that CLI publishers don't populate. These are `Optional` and validated per-source, so the cost is confined to the schema.
  - −Pattern B (treating Forge as a fleet agent end-to-end) is foregone. If that ever becomes desirable — e.g. Jarvis wanting a synchronous "start a build and wait" pattern — it can be added on top without removing Pattern A.

### ADR-SP-015: Specialist-Agent Dual-Role Deployment Model

- **Date:** 2026-04
- **Status:** Proposed (pending Rich's acceptance of TASK-REV-A1F2)
- **Context:** v2.1 §3 lists the specialist-agent roles (Architect, Product Owner, Ideation, UX Designer) but does not describe how multiple roles are deployed. Rich has committed to the first two real specialist-agent runs being **Product Owner (Stage 1 / Specification Review) + Architect (Stage 2 / Architecture Review)**, invoked by the Forge as two concurrent deployments of the same `specialist-agent` binary. The `specialist-agent` repo has YAMLs, handlers, and Graphiti wiring for both roles, but the `--role` CLI flag is parsed and ignored: manifest is hardcoded to `architect-agent`, so two concurrent instances would collide on fleet registration.
- **Decision:** The Forge's early pipeline stages call two distinct specialist agents by role: **Product Owner** (`agent_id=product-owner-agent`) and **Architect** (`agent_id=architect-agent`). Both are deployments of the same `specialist-agent` binary with different `--role` flags. `agent_id` is derived from the role by default (`{role_id}-agent`) or overridable via `SPECIALIST_AGENT_ID` env var for tests. Both register on `fleet.register` independently, subscribe to `agents.command.{agent_id}`, and publish results to `agents.result.{agent_id}`. Result payloads are wrapped in the Forge-compatible shape `{role_id, coach_score, criterion_breakdown, detection_findings, role_output}` at the `specialist-agent` boundary — Forge does not translate per-role output types.
- **Consequences:**
  - +Makes the deployment model explicit and anchored. Before this ADR, the dual-role deployment was a verbal commitment with no artefact.
  - +Drives concrete changes in `specialist-agent` (role-parameterised manifest factory, role-aware command router, result payload wrapper) — see TASK-REV-A1F2 appendix D for the surgical refactor plan.
  - +Forge's `call_agent_tool()` implementation becomes simpler: one expected result shape regardless of which role answered.
  - +The architect-only "degraded mode" fallback described in `forge-build-plan.md` remains valid — Forge can still delegate to architect alone if PO is unavailable.
  - −Role YAMLs and Python handlers now have a contract (`role_output` must be Pydantic-serialisable) they did not previously have. Ideation and UX Designer roles will inherit this contract when they come online.
  - −A thin `result_wrapper.py` module introduces one more place where role-specific evaluation data gets flattened into the NATS payload. The alternative (Forge-side translation) was rejected as pushing complexity to the wrong layer.
  - −Two extra containers in the Docker Compose topology (one per role). Acceptable — they are lightweight wrappers around the same binary.

### ADR-SP-016: Singular Topic Convention (`agents.command.*`, `agents.result.*`)

- **Date:** 2026-04
- **Status:** Proposed (pending Rich's acceptance of TASK-REV-A1F2)
- **Context:** v2.1 §7 specifies agent command/result topics as `agents.commands.{agent_id}` and `agents.results.{agent_id}` (plural). The `nats-core` library (98% test coverage, shipping) uses `Topics.Agents.COMMAND = "agents.command.{agent_id}"` and `Topics.Agents.RESULT = "agents.result.{agent_id}"` (singular). The `fleet-master-index.md` agrees with `nats-core`. The `specialist-agent` NATS adapter already subscribes to `agents.command.*`. TASK-REV-A1F2 surfaced this as a blocking naming mismatch — pick one, apply everywhere.
- **Decision:** Adopt the **singular** convention. All forge repo docs (anchor, refresh, build-plan, fleet-master-index) are updated to `agents.command.{agent_id}` / `agents.result.{agent_id}`. `nats-core` and `specialist-agent` are unchanged. A note in `nats-core`'s topic registry docstring records that the convention is singular and briefly explains why (historical precedence of shipping code + installed tests).
- **Consequences:**
  - +Avoids rewriting a 98%-covered library with shipping integration tests and a live `specialist-agent` subscriber.
  - +The anchor update is a cheap find-and-replace across three files.
  - +Consistent with the existing `agents.status.{agent_id}` topic which is also singular.
  - −Minor aesthetic loss — the plural form reads more naturally in English ("commands for agent X"). This is subordinate to not rewriting working code.
  - −Anchor v2.2 becomes the canonical form; anyone referencing v2.1 topics in documentation they wrote recently will need to update. Scope is small.

### ADR-SP-017: PIPELINE / AGENTS / SYSTEM Stream Retention Reconciliation

- **Date:** 2026-04
- **Status:** Proposed (pending Rich's acceptance of TASK-REV-A1F2)
- **Context:** v2.1 §3 specifies three JetStream streams with specific retentions: `PIPELINE` 30 days, `AGENTS` 7 days, `SYSTEM` 24 hours. The installed `nats-infrastructure` provisions these streams (plus four others — `FLEET`, `JARVIS`, `NOTIFICATIONS`, `FINPROXY` — which are not in the anchor) with different retentions: `PIPELINE` 7 days, `SYSTEM` 1 hour. The `nats-infrastructure` system-spec was reasoned through independently of the anchor v2.1 and the retention values reflect that independent analysis. TASK-REV-A1F2 surfaced this as a blocking mismatch that must be resolved before Phase 2 (`nats-core` revision) begins.
- **Decision:** Update the anchor to match the installed `nats-infrastructure` reality:
  - `PIPELINE`: **7 days** (was 30). Rationale: SQLite (`~/.forge/forge.db`) is the durable build-history store per ADR-SP-013. JetStream PIPELINE retention only needs to cover realistic crash-recovery windows (hours to days), not historical queries. 30 days was overkill.
  - `AGENTS`: **7 days** (unchanged in intent; infra may vary — align to 7d in both).
  - `SYSTEM`: **1 hour** (was 24). Rationale: `SYSTEM` carries ephemeral health and config pings. 24 hours was overkill.
  - Add `FLEET`, `JARVIS`, `NOTIFICATIONS` streams to the anchor's §3 key streams list, with one-line descriptions, since they are real and Ship's-Computer-relevant.
  - `FINPROXY` remains out of the anchor (tenant-specific, covered separately).
- **Consequences:**
  - +The anchor and the installed infrastructure agree, which unblocks Phase 1 validation.
  - +SQLite's role as the durable history store is strengthened — JetStream becomes exactly what it is, a durable queue with short-to-medium retention for crash recovery, nothing more.
  - +Anchor v2.2 documents `FLEET`, `JARVIS`, `NOTIFICATIONS` as first-class streams, closing the "what stream does Jarvis session state live in" gap.
  - −Lose the ability to replay a build's events from 8+ days ago directly off JetStream. Mitigated by SQLite history and per-build structured logs.
  - −One more decision to make on the side: the `pipeline-state` NATS KV bucket (provisioned in `nats-infrastructure`) competes with SQLite for the "runtime Forge state" role. This ADR does not resolve that — correction 6 in TASK-REV-A1F2 raises it as a separate decision that needs its own ADR once Rich has picked a direction.

---

*End of alignment review.*
