guardkit feature-spec FEAT-FORGE-008 \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
  --context forge/docs/design/models/DM-build-lifecycle.md

  I'll start Phase 1 — silent context gathering. Let me locate the context files and scan the codebase.

Bash Detect stack and check existing features
IN
ls -la pyproject.toml requirements.txt go.mod Cargo.toml package.json 2>/dev/null; echo "---"; ls features/ 2>/dev/null; echo "---"; ls docs/design/ 2>/dev/null

OUT
-rw-rw-r-- 1 richardwoollcott richardwoollcott 5214 Apr 27 14:41 pyproject.toml
---
confidence-gated-checkpoint-protocol
guardkit-command-invocation-engine
infrastructure-coordination
mode-a-greenfield-end-to-end
nats-fleet-integration
pipeline-state-machine-and-configuration
specialist-agent-delegation
---
contracts
decisions
diagrams
models
Bash Locate the context feature files
IN
ls forge/features/mode-a-greenfield-end-to-end/ 2>/dev/null; echo "---"; ls features/mode-a-greenfield-end-to-end/ 2>/dev/null; echo "---"; find . -maxdepth 4 -name "mode-a-greenfield*" 2>/dev/null | head -20

OUT
---
mode-a-greenfield-end-to-end_assumptions.yaml
mode-a-greenfield-end-to-end.feature
mode-a-greenfield-end-to-end_summary.md
---
./features/mode-a-greenfield-end-to-end
./tasks/backlog/mode-a-greenfield-end-to-end
./features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_assumptions.yaml
./features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature
./features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md
Bash Locate the context design files
IN
find . -maxdepth 5 -name "API-cli.md" -o -name "API-nats-approval-protocol.md" -o -name "DM-build-lifecycle.md" 2>/dev/null | head -20

OUT
./docs/design/contracts/API-nats-approval-protocol.md
./docs/design/contracts/API-cli.md
./docs/design/models/DM-build-lifecycle.md
Bash Find references to FEAT-FORGE-008
IN
grep -rln "FEAT-FORGE-008" --include="*.md" --include="*.yaml" --include="*.feature" 2>/dev/null | head -20

OUT
docs/product/roadmap.md
docs/research/ideas/forge-build-plan.md
docs/history/feature-plan-FEAT-FORGE-001-history.md
docs/history/command-history.md
docs/history/feature-spec-FEAT-FORGE-004-history.md
docs/history/feature-spec-FEAT-FORGE-007-history.md
Bash Check for FEAT-FORGE-008 task structure
IN
ls features/mode-a-greenfield-end-to-end/ tasks/backlog/mode-a-greenfield-end-to-end/ 2>/dev/null

OUT
features/mode-a-greenfield-end-to-end/:
mode-a-greenfield-end-to-end_assumptions.yaml
mode-a-greenfield-end-to-end.feature
mode-a-greenfield-end-to-end_summary.md

tasks/backlog/mode-a-greenfield-end-to-end/:
IMPLEMENTATION-GUIDE.md
README.md
TASK-MAG7-001-define-stage-taxonomy.md
TASK-MAG7-002-define-forward-propagation-map.md
TASK-MAG7-003-stage-ordering-guard.md
TASK-MAG7-004-constitutional-guard.md
TASK-MAG7-005-per-feature-loop-sequencer.md
TASK-MAG7-006-forward-context-builder.md
TASK-MAG7-007-dispatch-specialist-stage.md
TASK-MAG7-008-dispatch-subprocess-stage.md
TASK-MAG7-009-dispatch-autobuild-async.md
TASK-MAG7-010-supervisor-next-turn.md
TASK-MAG7-011-cli-steering-injection.md
TASK-MAG7-012-smoke-greenfield-e2e.md
TASK-MAG7-013-crash-recovery-integration.md
TASK-MAG7-014-concurrency-multifeature-integration.md
Bash List features and find feature IDs
IN
ls features/ | sort; echo "---FEAT IDS---"; grep -rh "FEAT-FORGE-" features/ 2>/dev/null | grep -oE "FEAT-FORGE-[0-9]+" | sort -u

OUT
confidence-gated-checkpoint-protocol
guardkit-command-invocation-engine
infrastructure-coordination
mode-a-greenfield-end-to-end
nats-fleet-integration
pipeline-state-machine-and-configuration
specialist-agent-delegation
---FEAT IDS---
FEAT-FORGE-001
FEAT-FORGE-002
FEAT-FORGE-003
FEAT-FORGE-004
FEAT-FORGE-005
FEAT-FORGE-006
FEAT-FORGE-007
Bash Find FEAT-FORGE-008 spec in roadmap
IN
grep -A 30 "FEAT-FORGE-008" docs/product/roadmap.md docs/research/ideas/forge-build-plan.md 2>/dev/null | head -100

OUT
docs/product/roadmap.md:The existing build plan already covers the core Forge implementation roadmap with FEAT-FORGE-001 through FEAT-FORGE-008, so this evolve roadmap does not re-propose those items. Instead, it adds six next-step features around the edges of that plan: FEAT-PO-001 introduces a prerequisite readiness gate before `/system-arch`; FEAT-PO-002 operationalises placeholder cleanup and history-file discipline after architecture, design, and feature-spec sessions; FEAT-PO-003 adds safe validation and degraded fallback for cross-repo context manifests; FEAT-PO-004 makes Graphiti-optional operation visible rather than implicit; FEAT-PO-005 adds checkpoint override telemetry for threshold calibration; and FEAT-PO-006 turns the documented 'where are we?' promise into a queryable status capability. Priority has shifted toward execution safety, degraded-mode visibility, and calibration feedback because the biggest current gap is not missing core Forge features on paper, but the operational glue needed to start and run that plan with confidence.
docs/product/roadmap.md-
docs/product/roadmap.md-## Epics
docs/product/roadmap.md-
docs/product/roadmap.md-### EPIC-001: Forge foundation execution readiness
docs/product/roadmap.md-
docs/product/roadmap.md-**Bounded Context:** Pipeline Orchestration
docs/product/roadmap.md-
docs/product/roadmap.md-This epic closes the immediate gaps between the existing Forge build plan and the documented readiness requirements that still block execution. It focuses on prerequisite verification, architecture-session hygiene, and the operational scaffolding needed to start and sustain the Forge build with less manual drift.
docs/product/roadmap.md-
docs/product/roadmap.md-**Features:**
docs/product/roadmap.md-  - FEAT-PO-001: Prerequisite readiness gate for Forge build start
docs/product/roadmap.md-  - FEAT-PO-002: Build plan placeholder resolution and command-history enforcement
docs/product/roadmap.md-
docs/product/roadmap.md-### EPIC-002: Cross-repo context assembly and degraded delivery operations
docs/product/roadmap.md-
docs/product/roadmap.md-**Bounded Context:** Context Resolution
docs/product/roadmap.md-
docs/product/roadmap.md-This epic extends the existing command invocation and degraded-mode concepts into operationally complete capabilities that the current build plan references but does not yet cover fully. It strengthens how Forge assembles context from manifests and how it behaves when specialist or Graphiti capabilities are absent.
docs/product/roadmap.md-
docs/product/roadmap.md-**Features:**
docs/product/roadmap.md-  - FEAT-PO-003: Context manifest validation and missing-manifest fallback policy
docs/product/roadmap.md-  - FEAT-PO-004: Graphiti-optional coordination with explicit knowledge-compounding status
docs/product/roadmap.md-
docs/product/roadmap.md-### EPIC-003: Outcome visibility and calibration feedback
docs/product/roadmap.md-
docs/product/roadmap.md-**Bounded Context:** Checkpoint Management
docs/product/roadmap.md-
docs/product/roadmap.md-This epic adds the next layer of operational feedback needed once the initial Forge feature set exists on paper. It turns the confidence-gated model into an observable and calibratable system, grounded in the product docs' emphasis on outcome gates, override learning, and proactive signals.
docs/product/roadmap.md-
docs/product/roadmap.md-**Features:**
--
docs/product/roadmap.md:The current build plan already defines the core Forge implementation sequence through FEAT-FORGE-001 to FEAT-FORGE-008, so the next roadmap should not restate those features. The highest-value additions are the gaps that sit around that plan: proving readiness before the build starts, preventing placeholder drift after architecture and design sessions, making context-manifest automation safe when dependencies are incomplete, and improving visibility into degraded operation and checkpoint calibration. These features come next because they reduce execution risk for the existing plan and make the confidence-gated model operationally trustworthy once the main Forge build begins.
docs/product/roadmap.md-
docs/product/roadmap.md-## Constraints and Dependencies
docs/product/roadmap.md-
docs/product/roadmap.md:- The existing Forge feature set FEAT-FORGE-001 through FEAT-FORGE-008 remains the current core build plan and is treated as existing planned coverage.
docs/product/roadmap.md-- Hard prerequisites from the build plan still block execution: live NATS infrastructure, nats-core integration tests, specialist-agent Phase 3, and at least one NATS-callable specialist agent.
docs/product/roadmap.md-- Graphiti runtime remains optional but must be surfaced explicitly when absent.
docs/product/roadmap.md-- Context manifest automation depends on manifests existing in target repos and following the documented category convention.
docs/product/roadmap.md-- PR review remains always human and must not be auto-approved.
docs/product/roadmap.md-
docs/product/roadmap.md-## Open Questions
docs/product/roadmap.md-
docs/product/roadmap.md-- Should the readiness gate live as a standalone preflight command, part of `forge_status`, or an automatic first stage of every pipeline run?
docs/product/roadmap.md-- What exact machine-readable format should be used for placeholder-resolution checks and command-history enforcement?
docs/product/roadmap.md-- Should degraded context assembly stop the pipeline entirely for some command types, or always continue with a forced review?
docs/product/roadmap.md-- Which stakeholder-facing surface should be the canonical status output first: CLI, NATS notification stream, or dashboard adapter?
docs/product/roadmap.md-
docs/product/roadmap.md-## Coverage Score
docs/product/roadmap.md-
docs/product/roadmap.md-**100%** of document sections have at least one mapped feature.
docs/product/roadmap.md-
docs/product/roadmap.md-Raw score: 1.0
docs/product/roadmap.md-
docs/product/roadmap.md-## Feature Spec Inputs
docs/product/roadmap.md-
docs/product/roadmap.md-### FEAT-PO-001: Prerequisite readiness gate for Forge build start
docs/product/roadmap.md-
docs/product/roadmap.md-**Bounded Context:** Pipeline Orchestration
docs/product/roadmap.md-
docs/product/roadmap.md-**Description:**
docs/product/roadmap.md-Forge should provide an explicit readiness gate that validates all hard prerequisites before `/system-arch` can begin, rather than relying on the build plan checklist being interpreted manually. The gate should verify NATS infrastructure availability, live nats-core integration status, specialist-agent Phase 3 completion, and at least one NATS-callable specialist role, then produce a machine-readable readiness report that explains which blocking conditions remain and why the build cannot start.
docs/product/roadmap.md-
docs/product/roadmap.md-**Source Documents:** forge-build-plan.md, conversation-starter-gap-analysis.md, fleet-master-index.md
docs/product/roadmap.md-
docs/product/roadmap.md-**Constraints:**
--
docs/product/roadmap.md:| ASM-001 | constraints | The existing FEAT-FORGE-001 through FEAT-FORGE-008 roadmap in `forge-build-plan.md` represents the current planned implementation baseline and should count toward documentation coverage. | high | If those features are not considered active planned coverage, the coverage score would fall and this roadmap would need to restate or replace the core Forge features. |
docs/product/roadmap.md-| ASM-002 | integration | The Forge repository does not yet have completed operational features for readiness gating, manifest validation, and calibration telemetry beyond what is described in planning documents. | medium | If some of these capabilities already exist in code or another plan, parts of this roadmap may duplicate work and should be converted into enhancement or hardening features. |
docs/product/roadmap.md-| ASM-003 | technology | Graphiti query results were unavailable or empty for this planning pass, so historical grounding relied primarily on the provided documentation set. | high | If relevant Graphiti facts exist but were not retrieved, some dependency or decision nuances may be missing from the roadmap rationale. |
docs/product/roadmap.md-| ASM-004 | scope | A product documentation section is counted as covered if it is addressed either by the existing Forge build-plan features or by one of the newly proposed roadmap features. | high | Coverage scoring and gap analysis would need recalculation. |
docs/research/ideas/forge-build-plan.md:## Status: `/system-arch` ✅ · `/system-design` ✅ · `/feature-spec` 🟡 **7 / 8 complete** (FEAT-FORGE-001..007 ✅; 008 pending) · `/feature-plan` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · `autobuild` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · **Next: `/feature-spec FEAT-FORGE-008`**
docs/research/ideas/forge-build-plan.md-## Repo: `guardkit/forge`
docs/research/ideas/forge-build-plan.md-## Agent ID: `forge`
docs/research/ideas/forge-build-plan.md-## Target: Post specialist-agent Phase 3 completion
docs/research/ideas/forge-build-plan.md-## Depends On: nats-core (✅ v0.2.0 inc. TASK-NCFA-003), nats-infrastructure (✅ configured, ◻ running), specialist-agent Phase 3 (◻)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Progress log
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-| Step | Command | Status | Date | Commit | Artefacts |
docs/research/ideas/forge-build-plan.md-|---|---|---|---|---|---|
docs/research/ideas/forge-build-plan.md-| 1 | `/system-arch` | ✅ complete | 2026-04-18 | `9f41e22` (seeded by later refinements) | `docs/architecture/ARCHITECTURE.md`, `system-context.md`, `container.md`, `domain-model.md`, `assumptions.yaml`, **31 ADRs** (`ADR-ARCH-001`..`031`) |
docs/research/ideas/forge-build-plan.md-| 2 | `/system-design` | ✅ complete | 2026-04-23 | `b40365c` | `docs/design/` — **9 API contracts + 5 data models + 6 DDRs + 2 C4 L3 diagrams**; 20 artefacts seeded into Graphiti (`project_design` + `architecture_decisions`) |
docs/research/ideas/forge-build-plan.md:| 3 | `/feature-spec × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | various | FEAT-FORGE-001..007 ✅ (see Step 3 for per-feature details); FEAT-FORGE-008 ◻ |
docs/research/ideas/forge-build-plan.md-| 4 | `/feature-plan × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | `6a29ed3`, `065b73d`, FEAT-FORGE-001 plan | FEAT-FORGE-001..007 ✅ — task breakdowns under `tasks/backlog/<slug>/`. 001 was re-planned post-001-gap-context with `forge-001-gap-context.md` to scope to the unbuilt slice (CLI + lifecycle persistence + state machine + recovery — 13 tasks). 008 ◻ |
docs/research/ideas/forge-build-plan.md-| 5 | `autobuild × 8` (Waves 1–6) | 🟡 in progress (7 / 8) | 2026-04-25..26 | `91f4de5`, `f63bcf5`, `9774351`, `042b83e`, `0361c21`, `6e5c577`, `ea7e60b` | FEAT-FORGE-002 (`91f4de5`), 003 (`f63bcf5`), 004 (`9774351`), 005 (`042b83e`), 006 (=`FEAT-8D10`, `0361c21`), 007 (=`FEAT-CBDE`, `6e5c577`), 001 (`ea7e60b`, 13/13 tasks across 5 waves, 0 ceiling hits) ✅. 008 ◻ |
docs/research/ideas/forge-build-plan.md-| 6 | Validation | ◻ pending | — | — | — |
docs/research/ideas/forge-build-plan.md-| 7 | FinProxy first real run | ◻ pending | — | — | — |
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md----
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-## Purpose
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-This build plan captures the full GuardKit command sequence to build the Forge — the
docs/research/ideas/forge-build-plan.md-pipeline orchestrator and checkpoint manager that coordinates the specialist agent fleet.
docs/research/ideas/forge-build-plan.md-The Forge is the capstone of the Software Factory: once it works, the pipeline from raw
docs/research/ideas/forge-build-plan.md-idea to deployed code runs end-to-end with confidence-gated human engagement.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Scope document:** `forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md`
Bash Find FEAT-FORGE-008 description in build plan
IN
grep -B 2 -A 40 "FEAT-FORGE-008" docs/research/ideas/forge-build-plan.md | head -150

OUT
# Forge Build Plan — Pipeline Orchestrator & Checkpoint Manager

## Status: `/system-arch` ✅ · `/system-design` ✅ · `/feature-spec` 🟡 **7 / 8 complete** (FEAT-FORGE-001..007 ✅; 008 pending) · `/feature-plan` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · `autobuild` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · **Next: `/feature-spec FEAT-FORGE-008`**
## Repo: `guardkit/forge`
## Agent ID: `forge`
## Target: Post specialist-agent Phase 3 completion
## Depends On: nats-core (✅ v0.2.0 inc. TASK-NCFA-003), nats-infrastructure (✅ configured, ◻ running), specialist-agent Phase 3 (◻)

### Progress log

| Step | Command | Status | Date | Commit | Artefacts |
|---|---|---|---|---|---|
| 1 | `/system-arch` | ✅ complete | 2026-04-18 | `9f41e22` (seeded by later refinements) | `docs/architecture/ARCHITECTURE.md`, `system-context.md`, `container.md`, `domain-model.md`, `assumptions.yaml`, **31 ADRs** (`ADR-ARCH-001`..`031`) |
| 2 | `/system-design` | ✅ complete | 2026-04-23 | `b40365c` | `docs/design/` — **9 API contracts + 5 data models + 6 DDRs + 2 C4 L3 diagrams**; 20 artefacts seeded into Graphiti (`project_design` + `architecture_decisions`) |
| 3 | `/feature-spec × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | various | FEAT-FORGE-001..007 ✅ (see Step 3 for per-feature details); FEAT-FORGE-008 ◻ |
| 4 | `/feature-plan × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | `6a29ed3`, `065b73d`, FEAT-FORGE-001 plan | FEAT-FORGE-001..007 ✅ — task breakdowns under `tasks/backlog/<slug>/`. 001 was re-planned post-001-gap-context with `forge-001-gap-context.md` to scope to the unbuilt slice (CLI + lifecycle persistence + state machine + recovery — 13 tasks). 008 ◻ |
| 5 | `autobuild × 8` (Waves 1–6) | 🟡 in progress (7 / 8) | 2026-04-25..26 | `91f4de5`, `f63bcf5`, `9774351`, `042b83e`, `0361c21`, `6e5c577`, `ea7e60b` | FEAT-FORGE-002 (`91f4de5`), 003 (`f63bcf5`), 004 (`9774351`), 005 (`042b83e`), 006 (=`FEAT-8D10`, `0361c21`), 007 (=`FEAT-CBDE`, `6e5c577`), 001 (`ea7e60b`, 13/13 tasks across 5 waves, 0 ceiling hits) ✅. 008 ◻ |
| 6 | Validation | ◻ pending | — | — | — |
| 7 | FinProxy first real run | ◻ pending | — | — | — |

---

## Purpose

This build plan captures the full GuardKit command sequence to build the Forge — the
pipeline orchestrator and checkpoint manager that coordinates the specialist agent fleet.
The Forge is the capstone of the Software Factory: once it works, the pipeline from raw
idea to deployed code runs end-to-end with confidence-gated human engagement.

**Scope document:** `forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md`
(v3, 11 April 2026) — defines the Forge's architecture, tool inventory, checkpoint
protocol, and NATS integration. Read that document first.

**Fleet context:** `forge/docs/research/ideas/fleet-master-index.md` (v2, 12 April
2026) — decisions D33–D38 govern the Forge's coordination model.

---

## Prerequisites

All prerequisites must be met before starting Step 1 (`/system-arch`).

### Hard Prerequisites (blocking)

- [x] **nats-core library implemented** — v0.2.0 shipped 2026-04-23 with **TASK-NCFA-003**: reconciled `StageCompletePayload`, `BuildPausedPayload`, `BuildResumedPayload` and added `BuildCancelledPayload` (all ISO-8601 `str` timestamps); `BuildQueuedPayload` already present. All topics registered. 761/761 tests passing, 98% coverage. Forge pins `nats-core>=0.2.0,<0.3` in `pyproject.toml`. Interim payload-carrier module was retired before creation (see DDR-001).
- [ ] **nats-infrastructure running on GB10** — NATS server up, JetStream enabled,
      accounts configured, `docker compose up -d` executed **and provisioning
      scripts run**: `provision-streams.sh` (creates AGENTS + PIPELINE + SYSTEM
      streams per anchor v2.2) and `provision-kv.sh` (creates `agent-registry`,
      `pipeline-state`, and other KV buckets). `verify-nats.sh` is read-only and
      does **not** self-heal a fresh volume. Per TASK-MDF-PRVS / TASK-NI-PSBUG
      (specialist-agent LES1 §7): a fresh-volume NATS without explicit
      provisioning will accept publishes (PubAck) but not retain or deliver them
      — exactly the MacBook failure mode. Scripts may require a `set +u`
      workaround on unset-var-strict shells until the ttl_opts bug is patched
--
| FEAT-FORGE-006 | Infrastructure Coordination | 001, 002 | 2-3 days | Graphiti seeding after each pipeline stage, Graphiti querying for cross-project context, test verification, git operations (clone/pull/branch/push/PR via `gh`) | Git operations, SQLite build history and stage log |
| FEAT-FORGE-007 | Mode A Greenfield End-to-End | 003, 004, 005, 006 | 3-5 days | Full integration: raw input → delegate to PO agent → checkpoint → delegate to architect → checkpoint → /system-arch → /system-design → /feature-spec × N → /feature-plan × N → autobuild × N → verify → git/PR → hard checkpoint (PR review). The primary pipeline mode. | Full end-to-end pipeline validation |
| FEAT-FORGE-008 | Mode B Feature & Mode C Review-Fix | 007 | 2-3 days | Mode B: add feature to existing project (skip PO/architect delegation, start from /feature-spec). Mode C: review and fix issues (/task-review → /task-work cycle). Both use checkpoint protocol. | *(optional modes — not in anchor §10 Phase 4)* |

**Anchor §10 Phase 4 bullets not yet covered by a feature:**
- CLI commands: `forge queue`, `forge status`, `forge history`, `forge cancel`, `forge skip` — folded into FEAT-FORGE-001 (CLI entrypoint)
- SQLite build history schema — folded into FEAT-FORGE-006 (infrastructure coordination)

**Estimated total: 4-6 weeks** (includes iteration time, integration testing, and the
inevitable debugging of subprocess orchestration + async NATS patterns)

---

## GuardKit Command Sequence

### Step 1: /system-arch ✅ COMPLETE (2026-04-18)

Produced the Forge's system architecture — ARCHITECTURE.md, ADRs, C4 diagrams,
component boundaries.

```bash
cd ~/Projects/appmilla_github/forge

guardkit system-arch \
  --context forge/docs/research/forge-pipeline-architecture.md \
  --context forge/docs/research/forge-build-plan-alignment-review.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md \
  --context forge/docs/research/pipeline-orchestrator-conversation-starter.md \
  --context forge/docs/research/pipeline-orchestrator-motivation.md \
  --context forge/docs/research/ideas/fleet-master-index.md \
  --context specialist-agent/docs/research/ideas/architect-agent-vision.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md
```

**Actual outputs (on disk):**
- [`forge/docs/architecture/ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md) — module map, stack, gates, relationship to anchor v2.2, decision index (31 ADRs)
- [`forge/docs/architecture/system-context.md`](../../architecture/system-context.md) — C4 Level 1
- [`forge/docs/architecture/container.md`](../../architecture/container.md) — C4 Level 2 (approved)
- [`forge/docs/architecture/domain-model.md`](../../architecture/domain-model.md) — core concepts, lifecycle, ownership
- [`forge/docs/architecture/assumptions.yaml`](../../architecture/assumptions.yaml) — tracked assumptions (updated 2026-04-23 for nats-core v0.2.0)
- [`forge/docs/architecture/decisions/ADR-ARCH-001`..`031`](../../architecture/decisions/) — 31 ADRs across structural / tool layer / learning / gating / state / API / fleet / deployment / security / cost / implementation

--

**Pending:**
- ◻ **FEAT-FORGE-008** — Mode B Feature & Mode C Review-Fix. Not yet specced. **This is the immediate next action** (see Step 3 command block below — `<feat-forge-008-slug>` placeholders resolve once the spec runs).

> **Context-flag resolution (post-`/system-design`):** placeholders from the original
> build plan resolve as follows. `DESIGN.md` / `forge-system-spec.md` were not produced
> as monolithic files (see Step 2 deviation note); instead each `/feature-spec` pulls
> the relevant per-container contract + data model. The GuardKit context-manifest
> resolver (DDR-005) can drive most of this automatically once
> `.guardkit/context-manifest.yaml` is populated.

```bash
# FEAT-FORGE-001: Pipeline State Machine & Configuration  ✅ COMPLETE (2026-04-24)
# Output: forge/features/pipeline-state-machine-and-configuration/
guardkit feature-spec FEAT-FORGE-001 \
  --context forge/docs/design/models/DM-build-lifecycle.md \
  --context forge/docs/design/contracts/API-sqlite-schema.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md

# FEAT-FORGE-002: NATS Fleet Integration  ✅ COMPLETE (2026-04-24)
# Output: forge/features/nats-fleet-integration/
guardkit feature-spec FEAT-FORGE-002 \
  --context forge/docs/design/contracts/API-nats-pipeline-events.md \
  --context forge/docs/design/contracts/API-nats-fleet-lifecycle.md \
  --context forge/docs/design/models/DM-discovery.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md

# FEAT-FORGE-003: Specialist Agent Delegation  ✅ COMPLETE (2026-04-24)
# Output: forge/features/specialist-agent-delegation/
guardkit feature-spec FEAT-FORGE-003 \
  --context forge/docs/design/contracts/API-nats-agent-dispatch.md \
  --context forge/docs/design/models/DM-discovery.md \
  --context forge/docs/design/decisions/DDR-001-reply-subject-correlation.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md

# FEAT-FORGE-004: Confidence-Gated Checkpoint Protocol  ✅ COMPLETE (2026-04-24)
# Output: forge/features/confidence-gated-checkpoint-protocol/
guardkit feature-spec FEAT-FORGE-004 \
  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
  --context forge/docs/design/models/DM-gating.md \
  --context forge/docs/design/decisions/DDR-002-resume-value-rehydration-helper.md
--
  --context forge/features/infrastructure-coordination/infrastructure-coordination_summary.md

# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix  ◻ NEXT
# Mode B reuses everything from /feature-spec onward (no PO/architect delegation).
# Mode C is the /task-review → /task-work cycle on existing code.
# Pull the FEAT-FORGE-007 spec for capstone composition patterns, the CLI surface
Bash Find FEAT-FORGE-008 detailed spec command
IN
grep -B 2 -A 30 "FEAT-FORGE-008: Mode B Feature & Mode C" docs/research/ideas/forge-build-plan.md | head -100

OUT
  --context forge/features/infrastructure-coordination/infrastructure-coordination_summary.md

# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix  ◻ NEXT
# Mode B reuses everything from /feature-spec onward (no PO/architect delegation).
# Mode C is the /task-review → /task-work cycle on existing code.
# Pull the FEAT-FORGE-007 spec for capstone composition patterns, the CLI surface
# for the queue/status/history commands these modes piggyback on, and the
# checkpoint protocol so the pause/resume flow stays consistent.
guardkit feature-spec FEAT-FORGE-008 \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
  --context forge/docs/design/models/DM-build-lifecycle.md
```

**Validation per feature spec:**
- BDD scenarios cover happy path, error cases, and edge cases
- Acceptance groups are reviewable (Rich will likely accept defaults ~95% based on
  observed pattern, but the Forge is the capstone — expect more manual review here)
- Each feature spec references the nats-core payloads it uses (no invented types)
- FEAT-FORGE-007 integration spec covers the full greenfield flow end-to-end

**Record Rich's responses:** Create `feature-spec-FEAT-FORGE-XXX-history.md` for each
spec session (following Pattern 3 from the fleet-master-index).

### Step 4: /feature-plan × 8 — 🟡 IN PROGRESS (7 / 8)

Produces task breakdowns for each feature. Run sequentially — dependencies must be
respected. Each invocation takes the matching `/feature-spec` summary as `--context`
so the plan is grounded in the curated scenarios and resolved assumptions (see
`installer/core/commands/feature-plan.md` §"Step 11: Link BDD scenarios to tasks").

--
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md

# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix (depends on 007)  ◻ BLOCKED on /feature-spec FEAT-FORGE-008
# Slug will resolve once /feature-spec FEAT-FORGE-008 runs. Likely candidate:
# `mode-b-feature-and-mode-c-review-fix` (kebab-case of the feature name).
# Re-run the command below with the real slug once the spec completes.
guardkit feature-plan FEAT-FORGE-008 \
  --context forge/features/<feat-forge-008-slug>/<feat-forge-008-slug>_summary.md
```

> **Note on slugs:** `/feature-spec` writes output under a kebab-cased slug of the
> feature **name**, not the `FEAT-FORGE-NNN` ID. Resolved slugs so far:
> `pipeline-state-machine-and-configuration` (001), `nats-fleet-integration` (002),
> `specialist-agent-delegation` (003), `confidence-gated-checkpoint-protocol` (004),
> `guardkit-command-invocation-engine` (005), `infrastructure-coordination` (006),
> `mode-a-greenfield-end-to-end` (007). FEAT-FORGE-008's slug resolves when its
> spec runs — replace the placeholder above with the real one at that point.

**Validation:**
- Task wave structure respects feature dependencies
- Each task has clear inputs, outputs, and acceptance criteria
- Integration tasks (FEAT-FORGE-007) are in later waves

### Step 5: Build (autobuild × 8) — 🟡 IN PROGRESS (7 / 8)

Build features in dependency order. Run sequentially on GB10 (or Bedrock when available).

> **Actual ordering deviated from the wave plan below.** The autobuild scheduler
> assigned new opaque feature IDs to capstone features (FEAT-FORGE-006 →
> `FEAT-8D10`; FEAT-FORGE-007 → `FEAT-CBDE`) — see `.guardkit/features/*.yaml`.
> FEAT-FORGE-001 was built **last in dependency order, first in scope priority**
> (the gap-closure pass): 13 tasks across 5 waves, 100% clean executions, 0/7
> SDK ceiling hits, 1h 44m wall time. Review summary at
Read mode-a-greenfield-end-to-end_summary.md
Read mode-a-greenfield-end-to-end.feature
Read API-cli.md
Read API-nats-approval-protocol.md
Read DM-build-lifecycle.md
Bash Check related feature specs
IN
ls features/confidence-gated-checkpoint-protocol/ features/guardkit-command-invocation-engine/ 2>/dev/null; echo "---"; head -40 features/confidence-gated-checkpoint-protocol/confidence-gated-checkpoint-protocol.feature 2>/dev/null

OUT
features/confidence-gated-checkpoint-protocol/:
confidence-gated-checkpoint-protocol_assumptions.yaml
confidence-gated-checkpoint-protocol.feature
confidence-gated-checkpoint-protocol_summary.md

features/guardkit-command-invocation-engine/:
guardkit-command-invocation-engine_assumptions.yaml
guardkit-command-invocation-engine.feature
guardkit-command-invocation-engine_summary.md
---
# Generated by /feature-spec
# Feature: Confidence-Gated Checkpoint Protocol (FEAT-FORGE-004)
# Stack: python
# Assumptions: 7 (see confidence-gated-checkpoint-protocol_assumptions.yaml)
# Generated: 2026-04-24T00:00:00Z

@feat-forge-004 @confidence-gated-checkpoint-protocol
Feature: Confidence-Gated Checkpoint Protocol
  As Rich, the sole operator of Forge
  I want each gated pipeline stage to be evaluated against the evidence from past builds,
    and for any stage Forge cannot confidently approve on its own to pause and ask me first
  So that safe work continues automatically, uncertain work waits for my review,
    unsafe work halts loudly, and every gating decision is traceable back to the priors
    and findings that produced it

  Background:
    Given Forge is configured from the project configuration file
    And Forge is connected to the fleet message bus
    And the specialist-agent delegation layer is able to return Coach scores and detection findings for gated stages

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP A — Key Examples
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Core happy path — when the evidence confidently supports the work, the pipeline continues without human engagement.
  @task:TASK-CGCP-005
  @key-example @smoke
  Scenario: A confidently-supported stage is auto-approved and the build continues
    Given a gated stage has just completed with a strong Coach score, a clean set of detection findings, and priors that concur
    When Forge evaluates the gate for that stage
    Then the gate decision should be recorded as auto-approve
    And the rationale, the priors consulted, and the findings considered should all be recorded on the decision
    And the build should continue to the next stage without pausing

  # Why: Core uncertain path — when the evidence is ambiguous, the build pauses and asks Rich to decide.
  @task:TASK-CGCP-006
  @key-example @smoke
  Scenario: A stage with ambiguous evidence pauses and requests human review
    Given a gated stage has just completed with evidence that is neither clearly positive nor clearly negative
    When Forge evaluates the gate for that stage
Bash Find more FEAT-FORGE-008 detail
IN
grep -B 2 -A 80 "FEAT-FORGE-008.*Mode B" docs/research/ideas/forge-build-plan.md 2>/dev/null | head -150

OUT
| FEAT-FORGE-006 | Infrastructure Coordination | 001, 002 | 2-3 days | Graphiti seeding after each pipeline stage, Graphiti querying for cross-project context, test verification, git operations (clone/pull/branch/push/PR via `gh`) | Git operations, SQLite build history and stage log |
| FEAT-FORGE-007 | Mode A Greenfield End-to-End | 003, 004, 005, 006 | 3-5 days | Full integration: raw input → delegate to PO agent → checkpoint → delegate to architect → checkpoint → /system-arch → /system-design → /feature-spec × N → /feature-plan × N → autobuild × N → verify → git/PR → hard checkpoint (PR review). The primary pipeline mode. | Full end-to-end pipeline validation |
| FEAT-FORGE-008 | Mode B Feature & Mode C Review-Fix | 007 | 2-3 days | Mode B: add feature to existing project (skip PO/architect delegation, start from /feature-spec). Mode C: review and fix issues (/task-review → /task-work cycle). Both use checkpoint protocol. | *(optional modes — not in anchor §10 Phase 4)* |

**Anchor §10 Phase 4 bullets not yet covered by a feature:**
- CLI commands: `forge queue`, `forge status`, `forge history`, `forge cancel`, `forge skip` — folded into FEAT-FORGE-001 (CLI entrypoint)
- SQLite build history schema — folded into FEAT-FORGE-006 (infrastructure coordination)

**Estimated total: 4-6 weeks** (includes iteration time, integration testing, and the
inevitable debugging of subprocess orchestration + async NATS patterns)

---

## GuardKit Command Sequence

### Step 1: /system-arch ✅ COMPLETE (2026-04-18)

Produced the Forge's system architecture — ARCHITECTURE.md, ADRs, C4 diagrams,
component boundaries.

```bash
cd ~/Projects/appmilla_github/forge

guardkit system-arch \
  --context forge/docs/research/forge-pipeline-architecture.md \
  --context forge/docs/research/forge-build-plan-alignment-review.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md \
  --context forge/docs/research/pipeline-orchestrator-conversation-starter.md \
  --context forge/docs/research/pipeline-orchestrator-motivation.md \
  --context forge/docs/research/ideas/fleet-master-index.md \
  --context specialist-agent/docs/research/ideas/architect-agent-vision.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md
```

**Actual outputs (on disk):**
- [`forge/docs/architecture/ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md) — module map, stack, gates, relationship to anchor v2.2, decision index (31 ADRs)
- [`forge/docs/architecture/system-context.md`](../../architecture/system-context.md) — C4 Level 1
- [`forge/docs/architecture/container.md`](../../architecture/container.md) — C4 Level 2 (approved)
- [`forge/docs/architecture/domain-model.md`](../../architecture/domain-model.md) — core concepts, lifecycle, ownership
- [`forge/docs/architecture/assumptions.yaml`](../../architecture/assumptions.yaml) — tracked assumptions (updated 2026-04-23 for nats-core v0.2.0)
- [`forge/docs/architecture/decisions/ADR-ARCH-001`..`031`](../../architecture/decisions/) — 31 ADRs across structural / tool layer / learning / gating / state / API / fleet / deployment / security / cost / implementation

**Key revisions since initial session:**
- ADR-ARCH-021 Revision 10 (2026-04-20) — server-mode rehydration contract (Option C hybrid) recorded after TASK-SPIKE-D2F7
- ADR-ARCH-031 (2026-04-19) — async subagents for `autobuild_runner`
- Commits: `9f41e22` (initial `/system-arch`) + `7bcc7da` (review + refinements) + `0a40b25` (ADR-021 Rev 10) + `79589c5` (TASK-ADR-REVISE completion)

**Validation (all green):**
- ✅ Architecture captures all three modes (greenfield, feature, review-fix)
- ✅ Confidence-gated checkpoint protocol is a first-class architectural component (see §8 + domain model `GateDecision`)
- ✅ Specialist agent delegation via NATS `call_agent_tool()` clearly bounded — ADR-ARCH-015
- ✅ GuardKit command invocation is subprocess-based — ADR-ARCH-004, ADR-ARCH-020
- ✅ Degraded mode is documented structural capability — ARCHITECTURE.md §7 + refresh-doc §"Degraded Mode"
- ✅ Pipeline event publishing uses nats-core payloads only (no new types invented here; v0.2.0 ships them)
- ✅ State persistence uses **SQLite + JetStream** (not NATS KV per the earlier draft — ADR-ARCH-009 explicitly omits the LangGraph checkpointer; ADR-SP-013 makes SQLite authoritative; builds KV is intentionally unused as a state store)
- ◻ **ADR trailer** (`**Decision facts as of commit:** <sha>`) — **not yet applied** to the 31 ADRs. Low-priority backfill task; consider a follow-up commit after /feature-spec.

**Noted deviation from the expected shape:**
- Build plan predicted ADRs under `forge/docs/decisions/ADR-FORGE-001-*`. Actual location is `forge/docs/architecture/decisions/ADR-ARCH-*`. References updated throughout this document accordingly.

### Step 2: /system-design ✅ COMPLETE (2026-04-23)

Produced detailed design — API contracts per container, data models, DDRs, C4 L3 diagrams.

```bash
guardkit system-design \
  --context forge/docs/architecture/ARCHITECTURE.md \
  --context forge/docs/architecture/decisions/ADR-ARCH-001..031.md  # all 31 ADRs loaded
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md
```

**Actual outputs (on disk — commit `b40365c`):**

Nine API contracts ([`forge/docs/design/contracts/`](../../design/contracts/)):
- [`API-nats-pipeline-events.md`](../../design/contracts/API-nats-pipeline-events.md) — inbound `pipeline.build-queued.>` pull consumer + 8 outbound lifecycle subjects
- [`API-nats-agent-dispatch.md`](../../design/contracts/API-nats-agent-dispatch.md) — specialist dispatch with LES1 per-correlation reply subject
- [`API-nats-approval-protocol.md`](../../design/contracts/API-nats-approval-protocol.md) — `interrupt()` round-trip with rehydration contract
- [`API-nats-fleet-lifecycle.md`](../../design/contracts/API-nats-fleet-lifecycle.md) — Forge self-registration + KV watch
- [`API-cli.md`](../../design/contracts/API-cli.md) — `forge queue/status/history/cancel/skip`
- [`API-sqlite-schema.md`](../../design/contracts/API-sqlite-schema.md) — `builds` + `stage_log` DDL + WAL
--

**Pending:**
- ◻ **FEAT-FORGE-008** — Mode B Feature & Mode C Review-Fix. Not yet specced. **This is the immediate next action** (see Step 3 command block below — `<feat-forge-008-slug>` placeholders resolve once the spec runs).

> **Context-flag resolution (post-`/system-design`):** placeholders from the original
> build plan resolve as follows. `DESIGN.md` / `forge-system-spec.md` were not produced
> as monolithic files (see Step 2 deviation note); instead each `/feature-spec` pulls
> the relevant per-container contract + data model. The GuardKit context-manifest
> resolver (DDR-005) can drive most of this automatically once
> `.guardkit/context-manifest.yaml` is populated.

```bash
# FEAT-FORGE-001: Pipeline State Machine & Configuration  ✅ COMPLETE (2026-04-24)
# Output: forge/features/pipeline-state-machine-and-configuration/
guardkit feature-spec FEAT-FORGE-001 \
  --context forge/docs/design/models/DM-build-lifecycle.md \
  --context forge/docs/design/contracts/API-sqlite-schema.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md

# FEAT-FORGE-002: NATS Fleet Integration  ✅ COMPLETE (2026-04-24)
# Output: forge/features/nats-fleet-integration/
guardkit feature-spec FEAT-FORGE-002 \
  --context forge/docs/design/contracts/API-nats-pipeline-events.md \
  --context forge/docs/design/contracts/API-nats-fleet-lifecycle.md \
  --context forge/docs/design/models/DM-discovery.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md

# FEAT-FORGE-003: Specialist Agent Delegation  ✅ COMPLETE (2026-04-24)
# Output: forge/features/specialist-agent-delegation/
guardkit feature-spec FEAT-FORGE-003 \
  --context forge/docs/design/contracts/API-nats-agent-dispatch.md \
  --context forge/docs/design/models/DM-discovery.md \
  --context forge/docs/design/decisions/DDR-001-reply-subject-correlation.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md

# FEAT-FORGE-004: Confidence-Gated Checkpoint Protocol  ✅ COMPLETE (2026-04-24)
# Output: forge/features/confidence-gated-checkpoint-protocol/
guardkit feature-spec FEAT-FORGE-004 \
  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
  --context forge/docs/design/models/DM-gating.md \
  --context forge/docs/design/decisions/DDR-002-resume-value-rehydration-helper.md

# FEAT-FORGE-005: GuardKit Command Invocation Engine  ✅ COMPLETE (2026-04-24)
# Output: forge/features/guardkit-command-invocation-engine/
guardkit feature-spec FEAT-FORGE-005 \
  --context forge/docs/design/contracts/API-tool-layer.md \
  --context forge/docs/design/contracts/API-subprocess.md \
  --context forge/docs/design/decisions/DDR-005-cli-context-manifest-resolution.md

# FEAT-FORGE-006: Infrastructure Coordination  ✅ COMPLETE (2026-04-24)
# Output: forge/features/infrastructure-coordination/
guardkit feature-spec FEAT-FORGE-006 \
  --context forge/docs/design/models/DM-graphiti-entities.md \
  --context forge/docs/design/models/DM-calibration.md \
  --context forge/docs/design/contracts/API-subprocess.md \
  --context forge/docs/design/decisions/DDR-004-graphiti-group-partitioning.md

# FEAT-FORGE-007: Mode A Greenfield End-to-End
# Design context: async-subagent stack (subagents API + both C4 L3 diagrams + DDR-006)
# plus the state machine (DM-build-lifecycle) and checkpoint protocol
# (API-nats-approval-protocol) that the mode threads through every stage.
# Prior-feature context: `.feature` + `_summary.md` for FEAT-FORGE-001..006
# (assumptions.yaml omitted — already echoed inside each summary).
guardkit feature-spec FEAT-FORGE-007 \
Bash Find Mode B/C definitions in build plan and architecture
IN
grep -B 2 -A 30 "Mode B\|Mode C\|review-fix\|task-review" docs/research/ideas/forge-build-plan.md docs/architecture/ARCHITECTURE.md 2>/dev/null | head -200

OUT
docs/research/ideas/forge-build-plan.md-| FEAT-FORGE-003 | Specialist Agent Delegation | 002 | 2-3 days | `call_agent_tool()` for product-owner and architect roles (ADR-SP-015), result parsing (Coach score + criterion breakdown + detection findings from `ResultPayload.result` dict), timeout handling, retry with additional context on failure | NATS command invocation of specialist agents (Stage 2) |
docs/research/ideas/forge-build-plan.md-| FEAT-FORGE-004 | Confidence-Gated Checkpoint Protocol | 003 | 2-3 days | Score evaluation against per-stage thresholds, critical detection pattern override, 🟢 auto-approve, 🟡 flag for review (PAUSED state), 🔴 hard stop. Configurable thresholds per anchor §4 | Confidence-gated checkpoints with configurable thresholds |
docs/research/ideas/forge-build-plan.md:| FEAT-FORGE-005 | GuardKit Command Invocation Engine | 001 | 2-3 days | Subprocess calls to `/system-arch`, `/system-design`, `/feature-spec`, `/feature-plan`, `autobuild`, `/task-review`. Context flag construction from pipeline state + `.guardkit/context-manifest.yaml`. Output capture and artifact path tracking. Error handling and retry. | Subprocess invocation of GuardKit AutoBuild with `--nats` flag (Stage 4) |
docs/research/ideas/forge-build-plan.md-| FEAT-FORGE-006 | Infrastructure Coordination | 001, 002 | 2-3 days | Graphiti seeding after each pipeline stage, Graphiti querying for cross-project context, test verification, git operations (clone/pull/branch/push/PR via `gh`) | Git operations, SQLite build history and stage log |
docs/research/ideas/forge-build-plan.md-| FEAT-FORGE-007 | Mode A Greenfield End-to-End | 003, 004, 005, 006 | 3-5 days | Full integration: raw input → delegate to PO agent → checkpoint → delegate to architect → checkpoint → /system-arch → /system-design → /feature-spec × N → /feature-plan × N → autobuild × N → verify → git/PR → hard checkpoint (PR review). The primary pipeline mode. | Full end-to-end pipeline validation |
docs/research/ideas/forge-build-plan.md:| FEAT-FORGE-008 | Mode B Feature & Mode C Review-Fix | 007 | 2-3 days | Mode B: add feature to existing project (skip PO/architect delegation, start from /feature-spec). Mode C: review and fix issues (/task-review → /task-work cycle). Both use checkpoint protocol. | *(optional modes — not in anchor §10 Phase 4)* |
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Anchor §10 Phase 4 bullets not yet covered by a feature:**
docs/research/ideas/forge-build-plan.md-- CLI commands: `forge queue`, `forge status`, `forge history`, `forge cancel`, `forge skip` — folded into FEAT-FORGE-001 (CLI entrypoint)
docs/research/ideas/forge-build-plan.md-- SQLite build history schema — folded into FEAT-FORGE-006 (infrastructure coordination)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Estimated total: 4-6 weeks** (includes iteration time, integration testing, and the
docs/research/ideas/forge-build-plan.md-inevitable debugging of subprocess orchestration + async NATS patterns)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md----
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-## GuardKit Command Sequence
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Step 1: /system-arch ✅ COMPLETE (2026-04-18)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Produced the Forge's system architecture — ARCHITECTURE.md, ADRs, C4 diagrams,
docs/research/ideas/forge-build-plan.md-component boundaries.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-```bash
docs/research/ideas/forge-build-plan.md-cd ~/Projects/appmilla_github/forge
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-guardkit system-arch \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/forge-pipeline-architecture.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/forge-build-plan-alignment-review.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/pipeline-orchestrator-conversation-starter.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/pipeline-orchestrator-motivation.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/ideas/fleet-master-index.md \
docs/research/ideas/forge-build-plan.md-  --context specialist-agent/docs/research/ideas/architect-agent-vision.md \
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/specs/nats-core-system-spec.md \
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/contracts/agent-manifest-contract.md
--
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Validation (all green):**
docs/research/ideas/forge-build-plan.md:- ✅ Architecture captures all three modes (greenfield, feature, review-fix)
docs/research/ideas/forge-build-plan.md-- ✅ Confidence-gated checkpoint protocol is a first-class architectural component (see §8 + domain model `GateDecision`)
docs/research/ideas/forge-build-plan.md-- ✅ Specialist agent delegation via NATS `call_agent_tool()` clearly bounded — ADR-ARCH-015
docs/research/ideas/forge-build-plan.md-- ✅ GuardKit command invocation is subprocess-based — ADR-ARCH-004, ADR-ARCH-020
docs/research/ideas/forge-build-plan.md-- ✅ Degraded mode is documented structural capability — ARCHITECTURE.md §7 + refresh-doc §"Degraded Mode"
docs/research/ideas/forge-build-plan.md-- ✅ Pipeline event publishing uses nats-core payloads only (no new types invented here; v0.2.0 ships them)
docs/research/ideas/forge-build-plan.md-- ✅ State persistence uses **SQLite + JetStream** (not NATS KV per the earlier draft — ADR-ARCH-009 explicitly omits the LangGraph checkpointer; ADR-SP-013 makes SQLite authoritative; builds KV is intentionally unused as a state store)
docs/research/ideas/forge-build-plan.md-- ◻ **ADR trailer** (`**Decision facts as of commit:** <sha>`) — **not yet applied** to the 31 ADRs. Low-priority backfill task; consider a follow-up commit after /feature-spec.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Noted deviation from the expected shape:**
docs/research/ideas/forge-build-plan.md-- Build plan predicted ADRs under `forge/docs/decisions/ADR-FORGE-001-*`. Actual location is `forge/docs/architecture/decisions/ADR-ARCH-*`. References updated throughout this document accordingly.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Step 2: /system-design ✅ COMPLETE (2026-04-23)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Produced detailed design — API contracts per container, data models, DDRs, C4 L3 diagrams.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-```bash
docs/research/ideas/forge-build-plan.md-guardkit system-design \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/architecture/ARCHITECTURE.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/architecture/decisions/ADR-ARCH-001..031.md  # all 31 ADRs loaded
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/specs/nats-core-system-spec.md \
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/contracts/agent-manifest-contract.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md
docs/research/ideas/forge-build-plan.md-```
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Actual outputs (on disk — commit `b40365c`):**
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Nine API contracts ([`forge/docs/design/contracts/`](../../design/contracts/)):
docs/research/ideas/forge-build-plan.md-- [`API-nats-pipeline-events.md`](../../design/contracts/API-nats-pipeline-events.md) — inbound `pipeline.build-queued.>` pull consumer + 8 outbound lifecycle subjects
docs/research/ideas/forge-build-plan.md-- [`API-nats-agent-dispatch.md`](../../design/contracts/API-nats-agent-dispatch.md) — specialist dispatch with LES1 per-correlation reply subject
docs/research/ideas/forge-build-plan.md-- [`API-nats-approval-protocol.md`](../../design/contracts/API-nats-approval-protocol.md) — `interrupt()` round-trip with rehydration contract
--
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Pending:**
docs/research/ideas/forge-build-plan.md:- ◻ **FEAT-FORGE-008** — Mode B Feature & Mode C Review-Fix. Not yet specced. **This is the immediate next action** (see Step 3 command block below — `<feat-forge-008-slug>` placeholders resolve once the spec runs).
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-> **Context-flag resolution (post-`/system-design`):** placeholders from the original
docs/research/ideas/forge-build-plan.md-> build plan resolve as follows. `DESIGN.md` / `forge-system-spec.md` were not produced
docs/research/ideas/forge-build-plan.md-> as monolithic files (see Step 2 deviation note); instead each `/feature-spec` pulls
docs/research/ideas/forge-build-plan.md-> the relevant per-container contract + data model. The GuardKit context-manifest
docs/research/ideas/forge-build-plan.md-> resolver (DDR-005) can drive most of this automatically once
docs/research/ideas/forge-build-plan.md-> `.guardkit/context-manifest.yaml` is populated.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-```bash
docs/research/ideas/forge-build-plan.md-# FEAT-FORGE-001: Pipeline State Machine & Configuration  ✅ COMPLETE (2026-04-24)
docs/research/ideas/forge-build-plan.md-# Output: forge/features/pipeline-state-machine-and-configuration/
docs/research/ideas/forge-build-plan.md-guardkit feature-spec FEAT-FORGE-001 \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/models/DM-build-lifecycle.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-sqlite-schema.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-cli.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-# FEAT-FORGE-002: NATS Fleet Integration  ✅ COMPLETE (2026-04-24)
docs/research/ideas/forge-build-plan.md-# Output: forge/features/nats-fleet-integration/
docs/research/ideas/forge-build-plan.md-guardkit feature-spec FEAT-FORGE-002 \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-nats-pipeline-events.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-nats-fleet-lifecycle.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/models/DM-discovery.md \
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/specs/nats-core-system-spec.md \
docs/research/ideas/forge-build-plan.md-  --context nats-core/docs/design/contracts/agent-manifest-contract.md
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-# FEAT-FORGE-003: Specialist Agent Delegation  ✅ COMPLETE (2026-04-24)
docs/research/ideas/forge-build-plan.md-# Output: forge/features/specialist-agent-delegation/
docs/research/ideas/forge-build-plan.md-guardkit feature-spec FEAT-FORGE-003 \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-nats-agent-dispatch.md \
--
docs/research/ideas/forge-build-plan.md-  --context forge/features/infrastructure-coordination/infrastructure-coordination_summary.md
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md:# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix  ◻ NEXT
docs/research/ideas/forge-build-plan.md:# Mode B reuses everything from /feature-spec onward (no PO/architect delegation).
docs/research/ideas/forge-build-plan.md:# Mode C is the /task-review → /task-work cycle on existing code.
docs/research/ideas/forge-build-plan.md-# Pull the FEAT-FORGE-007 spec for capstone composition patterns, the CLI surface
docs/research/ideas/forge-build-plan.md-# for the queue/status/history commands these modes piggyback on, and the
docs/research/ideas/forge-build-plan.md-# checkpoint protocol so the pause/resume flow stays consistent.
docs/research/ideas/forge-build-plan.md-guardkit feature-spec FEAT-FORGE-008 \
docs/research/ideas/forge-build-plan.md-  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
docs/research/ideas/forge-build-plan.md-  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-cli.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
docs/research/ideas/forge-build-plan.md-  --context forge/docs/design/models/DM-build-lifecycle.md
docs/research/ideas/forge-build-plan.md-```
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Validation per feature spec:**
docs/research/ideas/forge-build-plan.md-- BDD scenarios cover happy path, error cases, and edge cases
docs/research/ideas/forge-build-plan.md-- Acceptance groups are reviewable (Rich will likely accept defaults ~95% based on
docs/research/ideas/forge-build-plan.md-  observed pattern, but the Forge is the capstone — expect more manual review here)
docs/research/ideas/forge-build-plan.md-- Each feature spec references the nats-core payloads it uses (no invented types)
docs/research/ideas/forge-build-plan.md-- FEAT-FORGE-007 integration spec covers the full greenfield flow end-to-end
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Record Rich's responses:** Create `feature-spec-FEAT-FORGE-XXX-history.md` for each
docs/research/ideas/forge-build-plan.md-spec session (following Pattern 3 from the fleet-master-index).
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Step 4: /feature-plan × 8 — 🟡 IN PROGRESS (7 / 8)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Produces task breakdowns for each feature. Run sequentially — dependencies must be
docs/research/ideas/forge-build-plan.md-respected. Each invocation takes the matching `/feature-spec` summary as `--context`
docs/research/ideas/forge-build-plan.md-so the plan is grounded in the curated scenarios and resolved assumptions (see
docs/research/ideas/forge-build-plan.md-`installer/core/commands/feature-plan.md` §"Step 11: Link BDD scenarios to tasks").
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-> **FEAT-FORGE-001 was re-planned post-002–007** against
docs/research/ideas/forge-build-plan.md-> [`forge-001-gap-context.md`](./forge-001-gap-context.md), which maps every one of
--
docs/research/ideas/forge-build-plan.md-  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md:# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix (depends on 007)  ◻ BLOCKED on /feature-spec FEAT-FORGE-008
docs/research/ideas/forge-build-plan.md-# Slug will resolve once /feature-spec FEAT-FORGE-008 runs. Likely candidate:
docs/research/ideas/forge-build-plan.md:# `mode-b-feature-and-mode-c-review-fix` (kebab-case of the feature name).
docs/research/ideas/forge-build-plan.md-# Re-run the command below with the real slug once the spec completes.
docs/research/ideas/forge-build-plan.md-guardkit feature-plan FEAT-FORGE-008 \
docs/research/ideas/forge-build-plan.md-  --context forge/features/<feat-forge-008-slug>/<feat-forge-008-slug>_summary.md
docs/research/ideas/forge-build-plan.md-```
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-> **Note on slugs:** `/feature-spec` writes output under a kebab-cased slug of the
docs/research/ideas/forge-build-plan.md-> feature **name**, not the `FEAT-FORGE-NNN` ID. Resolved slugs so far:
docs/research/ideas/forge-build-plan.md-> `pipeline-state-machine-and-configuration` (001), `nats-fleet-integration` (002),
docs/research/ideas/forge-build-plan.md-> `specialist-agent-delegation` (003), `confidence-gated-checkpoint-protocol` (004),
docs/research/ideas/forge-build-plan.md-> `guardkit-command-invocation-engine` (005), `infrastructure-coordination` (006),
docs/research/ideas/forge-build-plan.md-> `mode-a-greenfield-end-to-end` (007). FEAT-FORGE-008's slug resolves when its
docs/research/ideas/forge-build-plan.md-> spec runs — replace the placeholder above with the real one at that point.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Validation:**
docs/research/ideas/forge-build-plan.md-- Task wave structure respects feature dependencies
docs/research/ideas/forge-build-plan.md-- Each task has clear inputs, outputs, and acceptance criteria
docs/research/ideas/forge-build-plan.md-- Integration tasks (FEAT-FORGE-007) are in later waves
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Step 5: Build (autobuild × 8) — 🟡 IN PROGRESS (7 / 8)
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Build features in dependency order. Run sequentially on GB10 (or Bedrock when available).
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-> **Actual ordering deviated from the wave plan below.** The autobuild scheduler
docs/research/ideas/forge-build-plan.md-> assigned new opaque feature IDs to capstone features (FEAT-FORGE-006 →
docs/research/ideas/forge-build-plan.md-> `FEAT-8D10`; FEAT-FORGE-007 → `FEAT-CBDE`) — see `.guardkit/features/*.yaml`.
docs/research/ideas/forge-build-plan.md-> FEAT-FORGE-001 was built **last in dependency order, first in scope priority**
docs/research/ideas/forge-build-plan.md-> (the gap-closure pass): 13 tasks across 5 waves, 100% clean executions, 0/7
docs/research/ideas/forge-build-plan.md-> SDK ceiling hits, 1h 44m wall time. Review summary at
docs/research/ideas/forge-build-plan.md-> `.guardkit/autobuild/FEAT-FORGE-001/review-summary.md`.
docs/research/ideas/forge-build-plan.md-
--
docs/research/ideas/forge-build-plan.md-   specialist-agent canonical guide at retest time).
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md:> **Note:** Mode-based wrappers (`forge greenfield`, `forge feature`, `forge review-fix`) are optional higher-level wrappers around `forge queue` and may be added later if they earn their place. The canonical CLI surface is `forge queue`.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-### Step 7: First Real Run — FinProxy
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-Once validation passes, run the Forge on FinProxy as the first real pipeline:
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-```bash
docs/research/ideas/forge-build-plan.md-forge queue FEAT-FINPROXY-001 --repo guardkit/finproxy --branch main
docs/research/ideas/forge-build-plan.md-forge status
docs/research/ideas/forge-build-plan.md-forge history --feature FEAT-FINPROXY-001
docs/research/ideas/forge-build-plan.md-```
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-**Expected outcome:** The pipeline delegates to specialist agents, evaluates Coach
docs/research/ideas/forge-build-plan.md-scores, auto-approves or flags as appropriate, invokes GuardKit commands, produces a PR.
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md----
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-## Files That Will Change
docs/research/ideas/forge-build-plan.md-
docs/research/ideas/forge-build-plan.md-| File | Feature | Change Type |
docs/research/ideas/forge-build-plan.md-|------|---------|-------------|
Bash Find docs that mention Mode B or Mode C
IN
grep -l "Mode B\|Mode C\|review-fix\|task-review" docs/architecture/*.md docs/design/contracts/*.md docs/design/models/*.md 2>/dev/null | head -10

OUT
docs/architecture/system-context.md
docs/design/contracts/API-tool-layer.md
Bash Find Mode B/C details in architecture and tool-layer docs
IN
grep -B 1 -A 15 "Mode B\|Mode C\|review-fix\|task-review" docs/architecture/system-context.md docs/design/contracts/API-tool-layer.md 2>/dev/null | head -100

OUT
docs/architecture/system-context.md-    System_Ext(nats, "NATS + JetStream", "Transport backbone. Streams: PIPELINE, AGENTS, FLEET, JARVIS, NOTIFICATIONS. KV: agent-registry.")
docs/architecture/system-context.md:    System_Ext(guardkit, "GuardKit CLI", "Slash commands: /system-arch, /system-design, /system-plan, /feature-spec, /feature-plan, /task-review, /task-work, /task-complete, autobuild, graphiti seed/query")
docs/architecture/system-context.md-    System_Ext(graphiti, "Graphiti (FalkorDB)", "Fleet knowledge graph. Groups: forge_pipeline_history (outcomes + overrides), forge_calibration_history (ingested history files).")
docs/architecture/system-context.md-    System_Ext(llm, "LLM Providers", "Gemini 3.1 Pro (primary) / Anthropic / OpenAI / local vLLM — provider-neutral via init_chat_model. Single env var to switch.")
docs/architecture/system-context.md-    System_Ext(github, "GitHub", "git push + PR creation via gh CLI")
docs/architecture/system-context.md-
docs/architecture/system-context.md-    Rel(rich, forge, "forge queue | status | history | cancel | skip", "Click CLI")
docs/architecture/system-context.md-    Rel(jarvis, nats, "publish BuildQueuedPayload", "pipeline.build-queued.*")
docs/architecture/system-context.md-    BiRel(forge, nats, "pull-consume triggers; publish lifecycle events; fleet register/heartbeat; approval round-trips", "pipeline.* / agents.* / fleet.*")
docs/architecture/system-context.md-    BiRel(forge, specialists, "dispatch_by_capability (resolved at runtime); receive Coach-scored results", "agents.command.* / result.*")
docs/architecture/system-context.md-    Rel(forge, guardkit, "subprocess via DeepAgents execute with --nats", "shell")
docs/architecture/system-context.md-    BiRel(forge, graphiti, "retrieve priors (calibration + pipeline history); write outcomes + override events", "bolt://")
docs/architecture/system-context.md-    Rel(forge, llm, "reasoning + implementation model invocations", "HTTPS")
docs/architecture/system-context.md-    Rel(forge, github, "git push branch + gh pr create", "HTTPS")
docs/architecture/system-context.md-    Rel(reviewers, github, "review + merge PRs", "web UI")
docs/architecture/system-context.md-    Rel(nats, jarvis, "notifications routed back to originating adapter", "jarvis.notification.*")
docs/architecture/system-context.md-```
docs/design/contracts/API-tool-layer.md-| `guardkit_feature_plan` | `guardkit feature-plan` | repo, feature_id |
docs/design/contracts/API-tool-layer.md:| `guardkit_task_review` | `guardkit task-review` | repo, task_id |
docs/design/contracts/API-tool-layer.md-| `guardkit_task_work` | `guardkit task-work` | repo, task_id |
docs/design/contracts/API-tool-layer.md-| `guardkit_task_complete` | `guardkit task-complete` | repo, task_id |
docs/design/contracts/API-tool-layer.md-| `guardkit_autobuild` | `guardkit autobuild` | repo, feature_id |
docs/design/contracts/API-tool-layer.md-| `guardkit_graphiti_add_context` | `guardkit graphiti add-context` | doc_path, group |
docs/design/contracts/API-tool-layer.md-| `guardkit_graphiti_query` | `guardkit graphiti query` | query, group |
docs/design/contracts/API-tool-layer.md-
docs/design/contracts/API-tool-layer.md-All share a common docstring pattern:
docs/design/contracts/API-tool-layer.md-
docs/design/contracts/API-tool-layer.md-```python
docs/design/contracts/API-tool-layer.md-@tool(parse_docstring=True)
docs/design/contracts/API-tool-layer.md-async def guardkit_feature_spec(
docs/design/contracts/API-tool-layer.md-    repo: str,
docs/design/contracts/API-tool-layer.md-    feature_description: str,
docs/design/contracts/API-tool-layer.md-    context_paths: list[str] | None = None,
docs/design/contracts/API-tool-layer.md-) -> str:
Bash Find Mode descriptions in ARCHITECTURE.md
IN
grep -B 1 -A 20 "Mode A\|Mode B\|Mode C\|three modes\|greenfield\|review-fix" docs/architecture/ARCHITECTURE.md 2>/dev/null | head -120

OUT
(Bash completed with no output)
Bash Find mode references in ARCHITECTURE.md
IN
grep -B 1 -A 10 "mode\|Mode" docs/architecture/ARCHITECTURE.md 2>/dev/null | head -80

OUT
**The human moves from operator to approver.** The reasoning model makes decisions the human was making (module decomposition, context assembly, stage ordering) using calibration priors learned from Rich's past sessions; Rich reviews when confidence is low.

**Forge is not a specialist.** It is a coordinator. Domain judgment is delegated to fleet specialist agents via runtime-discovered capabilities. Forge uses a strong reasoning model (Gemini 3.1 Pro primary) for orchestration decisions — not fine-tuned domain knowledge.

---

## 2. Structural Pattern

**Hexagonal modules inside a DeepAgents two-model orchestrator.**

- The `create_deep_agent(...)` compiled state graph is the shell — reasoning loop, built-in tools (`write_todos`, filesystem, `execute`, `task`, `interrupt`), sub-agent dispatch.
- Inside: pure domain modules (gating, state machine, notifications, learning, calibration, discovery) with no I/O imports.
- Thin adapters at the edges: NATS (via `nats-core`), SQLite, Graphiti, subprocess. Forge-specific `@tool` functions wrap adapters at the DeepAgents tool-layer boundary.
- No transport abstraction (ADR-ARCH-003) — NATS is the transport, not a replaceable plugin.

See [system-context.md](system-context.md) for C4 Level 1 and [container.md](container.md) for C4 Level 2.

---

--
- `forge.discovery` — runtime fleet capability resolution via `NATSKVManifestRegistry` with live watch (ADR-ARCH-015, ADR-ARCH-017)
- `forge.history_labels` — trivial helper writing reasoning-model's stage labels to SQLite `stage_log`

### C. Tool Layer (`@tool(parse_docstring=True)` functions — Forge-specific only)
- `dispatch_by_capability` — single generic tool for all fleet dispatch; replaces role-specific tools
- `approval_tools` — build `ApprovalRequestPayload`s for `interrupt()` return values
- `notification_tools` — emit `NotificationPayload` via NATS
- `graphiti_tools` — `record_override`, `write_gate_decision`, `read_override_history`, `write_session_outcome`
- `guardkit_*` — thin wrappers over DeepAgents `execute` for the full GuardKit CLI (11 commands — ADR-ARCH-004)
- `history_tools` — SQLite schema'd writes (`BuildRow`, `StageRow`)

**Not needed:** `git_tools`, `pr_tools`, `file_tools`, `queue_tools` — subsumed by DeepAgents built-ins (`execute`, `read_file`/`write_file`, etc.) per ADR-ARCH-020.
--
### E. Cross-cutting
- `forge.config` — `AgentConfig` + `forge.yaml` loader; infrastructure + models + constitutional rules + learning meta-config only (ADR-ARCH-019, ADR-ARCH-023)
- `forge.cli` — Click CLI (`queue | status | history | cancel | skip`); reads SQLite direct, writes via NATS (ADR-ARCH-013)
- `forge.fleet` — Forge's own `fleet.register` publication + heartbeat lifecycle

---

## 4. Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
--
| Graph runtime | LangGraph — `langgraph.json` / `langgraph dev` / `CompiledStateGraph` |
| Model client | `init_chat_model("provider:model")` — provider-neutral (ADR-ARCH-010) |
| Reasoning model (primary) | `google_genai:gemini-3.1-pro` |
| Implementation model (primary) | `google_genai:gemini-2.5-flash` |
| Fallback providers | Anthropic Opus 4.7/Sonnet 4.6, OpenAI GPT-5, local vLLM |
| Schemas | Pydantic 2 + pydantic-settings (via `nats-core.AgentConfig`) |
| CLI | Click |
| Async I/O | `asyncio` |
| Testing | pytest, pytest-asyncio, `unittest.mock` (per `pytest-agent-testing-specialist` rule) |
| Lint / type | ruff, mypy `--strict` |
| Internal library | `nats-core` (pip-installed from sibling repo) |

---

--

Forge has **no pre-coded stage catalogue** (ADR-ARCH-016). The reasoning model:

1. Receives a build and retrieves priors (calibration + project context + live fleet capabilities) into the system prompt.
2. Uses DeepAgents' built-in `write_todos` to plan the build's todo list — these todos ARE the emergent stage labels Rich reads in `forge history`.
3. Invokes local `@tool`s (GuardKit commands, etc.) and fleet specialists (via `dispatch_by_capability`) in whatever order makes sense for this build, guided by:
   - The capability descriptions in each registered agent's `AgentManifest`
   - The typical factory shape (spec → arch → plan → build → PR) as prose guidance in the system prompt
   - Retrieved priors from similar prior builds
   - Policy guardrails in `forge.yaml`
4. Evaluates each Coach-scored result and decides auto-approve / flag-for-review / hard-stop in context — no static thresholds (ADR-ARCH-019).
5. Writes every decision + outcome to Graphiti `forge_pipeline_history` — compounds into priors for future builds.

**Training mode is emergent, not a flag.** Few priors → natural reasoning conservatism → frequent flags → Rich approves → priors grow → conservatism relaxes organically.

---

## 8. Confidence Gates
Bash Find Mode B/C details in refresh doc
IN
grep -B 1 -A 15 "task-review\|task-work\|review-fix\|Mode B\|Mode C\|Mode A" docs/research/ideas/forge-pipeline-orchestrator-refresh.md 2>/dev/null | head -200

OUT
Early in a project (greenfield FinProxy), you probably want lower auto_threshold values — more human eyes on everything while the architecture is being established. Once the architecture is stable and you're in feature mode (Mode B), the Coach has enough context and the thresholds can rise.

The Forge could even learn this automatically: track the rate at which humans override auto-approved outputs. If the override rate is above 10%, lower the auto_threshold. If it's consistently 0%, raise it. This is a future optimisation — start with manual threshold configuration.

### Detection Pattern Override

Some detection patterns are critical regardless of overall score. If the Coach detects PHANTOM (architecture references that don't exist), the stage goes to 🔴 HARD STOP even if the aggregate score is 0.85. This is configured via `critical_detections` per stage.

### What This Means for the Pipeline

Most pipeline runs will flow end-to-end with zero human interruption. The human gets a stream of notifications: "Product docs scored 0.83 — auto-approved ✅", "Architecture scored 0.78 — auto-approved ✅", "Feature spec #3 scored 0.52, SCOPE_CREEP detected — flagged for review 🟡". The human only engages when the Coach has specific concerns.

The final PR review remains a hard human checkpoint — this is the one gate that should never auto-approve. Everything else is confidence-gated.

### DDD Southwest Narrative

--
  │   ├── autobuild         (implements tasks from /feature-plan)
  │   └── /task-review      (reviews issues, creates fix tasks)
  │
  ├── COORDINATE
  │   ├── graphiti_seed     (seed outputs into knowledge graph after each stage)
  │   ├── verify            (run tests, integration checks)
  │   ├── git operations    (branch, commit, PR)
  │   └── ci_trigger        (GitHub Actions)
  │
  └── HARD CHECKPOINT (always human, never auto-approved)
      └── PR review — final gate before merge
```

### What This Changes

1. **The Forge doesn't need architectural judgment.** It delegates to the architect-agent. The architect-agent has fine-tuned domain knowledge (Phase F) — the Forge's reasoning model doesn't need it.

--

### Mode A: Greenfield (with confidence-gated checkpoints)

```
Raw input (idea, brief, product concept)
    │
    ▼
Forge dispatches to product-owner-agent (via NATS call_agent_tool)
    → ProductDocument (user stories, acceptance criteria, backlog)
    → Coach score: 0.83, no critical detections
    │
    ▼
Confidence gate: score 0.83 ≥ auto_threshold 0.80
    🟢 AUTO-APPROVE → NotificationPayload to James, pipeline continues
    │
    ▼
Forge dispatches to architect-agent (via NATS call_agent_tool)
--

1. **Three orchestration modes** — Greenfield (Mode A), Feature (Mode B), Review-Fix (Mode C)
2. **Multi-project parallel execution** — NATS topic prefix isolation per project (using `Topics.for_project()`)
3. **Execution environment abstraction** — worktrees (Phase 1) → devcontainers (Phase 2) → sandboxes (Phase 3)
4. **CI/CD integration** — self-healing loop on CI failures
5. **Dashboard UX** — orchestrator card per active project
6. **Provider-agnostic execution** — cloud or local, configurable
7. **Pipeline state persistence** — resume after crash (NATS KV for state)
8. **The motivation** — 93% defaults accepted, 3 high-impact decisions, 4:1 leverage ratio

---

## What's New or Changed

| Topic | March 2026 | April 2026 v3 |
|-------|-----------|--------------|
| Upstream stages | Forge invokes slash commands for everything | Forge delegates to specialist agents via NATS `call_agent_tool()` |
Bash Find Mode B and Mode C complete definitions
IN
grep -B 2 -A 60 "### Mode B\|### Mode C" docs/research/ideas/forge-pipeline-orchestrator-refresh.md 2>/dev/null | head -250

OUT
(Bash completed with no output)
Bash Find positions of Mode B/C
IN
grep -n "Mode B\|Mode C\|Greenfield\|Feature mode\|Review-Fix" docs/research/ideas/forge-pipeline-orchestrator-refresh.md 2>/dev/null | head -30

OUT
189:Early in a project (greenfield FinProxy), you probably want lower auto_threshold values — more human eyes on everything while the architecture is being established. Once the architecture is stable and you're in feature mode (Mode B), the Coach has enough context and the thresholds can rise.
292:### Mode A: Greenfield (with confidence-gated checkpoints)
614:1. **Three orchestration modes** — Greenfield (Mode A), Feature (Mode B), Review-Fix (Mode C)
Bash Read Mode A section context for Mode B/C inferences
IN
sed -n '290,500p' docs/research/ideas/forge-pipeline-orchestrator-refresh.md 2>/dev/null

OUT
## Revised Pipeline Flow

### Mode A: Greenfield (with confidence-gated checkpoints)

```
Raw input (idea, brief, product concept)
    │
    ▼
Forge dispatches to product-owner-agent (via NATS call_agent_tool)
    → ProductDocument (user stories, acceptance criteria, backlog)
    → Coach score: 0.83, no critical detections
    │
    ▼
Confidence gate: score 0.83 ≥ auto_threshold 0.80
    🟢 AUTO-APPROVE → NotificationPayload to James, pipeline continues
    │
    ▼
Forge dispatches to architect-agent (via NATS call_agent_tool)
    → ConversationStarter (C4, ADRs, open questions, constraints)
    → Coach score: 0.78, no critical detections
    │
    ▼
Confidence gate: score 0.78 ≥ auto_threshold 0.80? NO (0.78 < 0.80)
    🟡 FLAG FOR REVIEW → ApprovalRequestPayload to Rich with criterion breakdown
    Rich reviews → ApprovalResponsePayload (decision: approve)
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
Forge invokes /feature-spec × N
    → BDD feature files, assumptions manifests
    → Coach score per feature spec
    │
    ▼
Confidence gate per feature spec:
    🟢 Spec #1 scored 0.82 → auto-approve
    🟢 Spec #2 scored 0.79 → auto-approve (threshold 0.75 for specs)
    🟡 Spec #3 scored 0.52, SCOPE_CREEP detected → flag for review
    │
    ▼
Forge invokes /feature-plan × N (for approved specs)
    → Task breakdowns per feature
    │
    ▼
Forge invokes autobuild × N (sequential on GB10, parallel on Bedrock)
    → Implemented features
    │
    ▼
Forge invokes verify (tests, integration checks)
    → All tests pass? Continue. Any failure? 🔴 HARD STOP
    │
    ▼
Forge triggers CI/CD (git push, PR, GitHub Actions)
    │
    ▼
🔴 HARD CHECKPOINT: Human reviews PR (always human, never auto-approved)
```

### Mapping to Anchor v2.2 Pipeline Stages

The greenfield flow above uses finer-grained steps than anchor v2.2 §4's five stages. This mapping shows the correspondence:

| This doc's flow block | Anchor v2.2 §4 Stage | Notes |
|-----------------------|-----------------------|-------|
| product-owner-agent delegation | Stage 1 — Specification Review | Anchor verifies spec completeness; this doc generates product docs from raw input |
| architect-agent delegation | Stage 2 — Architecture Review | Specialist evaluates feasibility, produces ADRs |
| /system-arch + /system-design | (between Stage 2 and Stage 3) | Tactical resolution of architect's strategic output — not a separate anchor stage |
| /feature-spec × N | Stage 3 — Feature Planning (first half) | Per-spec confidence gating |
| /feature-plan × N | Stage 3 — Feature Planning (second half) | Task decomposition from approved specs |
| autobuild × N | Stage 4 — AutoBuild Execution | Per-task Coach validation |
| verify + git/PR | Stage 5 — PR Creation | Quality gates + PR creation |

The anchor's Stage 1 ("Specification Review") is broader than just product-owner delegation — it also verifies that `/feature-spec` outputs exist and assumptions are resolved. The mapping is approximate; the anchor is authoritative for stage definitions.

### Key Differences from Previous Versions

1. **Confidence-gated checkpoints replace hard checkpoints.** The Coach score determines whether a human needs to engage, not a fixed pipeline stage. Most stages auto-approve.

2. **The first two stages are agent-to-agent delegations via NATS**, using `NATSClient.call_agent_tool()` which already supports request-reply with timeout. The specialist agents bring fine-tuned domain judgment. The Forge brings pipeline coordination.

3. **Per-spec gating.** Feature specs are evaluated individually. Spec #1 might auto-approve while spec #3 gets flagged. The pipeline doesn't block on *all* specs — just the ones the Coach is worried about.

4. **PR review is the only unconditional hard checkpoint.** Everything else is conditional on Coach confidence.

5. **Specialist agents return Coach scores as part of their result payload.** The Forge doesn't re-evaluate — it reads the score the specialist's own Coach produced. This means the specialist's domain-specific criteria (not the Forge's generic reasoning) determine confidence.

---

## Forge Tool Inventory (Revised)

### Fleet Agent Tools (via NATS)

**Reply-subject convention (LES1 parity rule).** `call_agent_tool()` publishes
commands to `agents.command.<agent_id>` and subscribes to
`agents.result.<agent_id>.<correlation_id>` (or the convention nats-core's
`NATSClient.call_agent_tool()` sets) for the real reply. The JetStream AGENTS
stream intercepts `agents.>` and returns `PubAck` within ~3ms — **do not treat
PubAck as success**. Per specialist-agent LES1 §2 (walkthrough §retest-smoke):
`nats request` against `agents.>` returned PubAck and exited ~3ms later; the real
reply arrived separately on `agents.result.<role>`. Operators read PubAck as
success and the round-trip contract was silently broken for iterations.
Document publishers/subscribers per role in one table before go-live.

| Tool | Target Agent | NATS Method | Input | Output |
|------|-------------|-------------|-------|--------|
| `delegate_product_docs` | product-owner-agent | `call_agent_tool()` | Raw input, product brief | ProductDocument + CoachScore |
| `delegate_architecture` | architect-agent | `call_agent_tool()` | ProductDocument, scope | ConversationStarter + CoachScore |
| `check_feasibility` | architect-agent | `call_agent_tool()` | Feature summary, constraints | FeasibilityAssessment |
| `discover_agents` | fleet registry | `NATSKVManifestRegistry.list_all()` | — | Available AgentManifests |
| `find_agent_for_intent` | fleet registry | `NATSKVManifestRegistry.find_by_intent()` | Intent string | Matching AgentManifests |

### GuardKit Command Tools (direct invocation)

| Tool | Input | Output |
|------|-------|--------|
| `system_arch` | ConversationStarter path | ARCHITECTURE.md, ADRs |
| `system_design` | ARCHITECTURE.md path | DESIGN.md, contracts |
| `feature_spec` | Architecture + feature description | BDD feature file + CoachScore |
| `feature_plan` | Feature spec path | Task breakdown |
| `autobuild` | Feature ID | Build result |
| `task_review` | Subject path | Review report |

### Context Manifest Convention

The Forge reads `.guardkit/context-manifest.yaml` from each target repo to discover
cross-repo dependencies and assemble `--context` flags automatically. This eliminates
the manual context flag selection that previously required a Claude Desktop conversation
to identify the right docs for each command invocation.

Manifest format:
```yaml
repo: forge
dependencies:
  nats-core:
    path: ../nats-core
    relationship: "Why this repo depends on nats-core"
    key_docs:
      - path: docs/design/specs/nats-core-system-spec.md
        category: specs          # specs | contracts | decisions | source | product | architecture
        description: "What this doc provides"
internal_docs:
  always_include:               # Included in every GuardKit command for this repo
    - docs/architecture/ARCHITECTURE.md
    - docs/design/DESIGN.md
```

Category filtering by command type:
- `/system-arch` → architecture + decisions
- `/system-design` → specs + decisions + contracts
- `/feature-spec` → specs + contracts + source
- `autobuild` → contracts + source
- `internal_docs.always_include` → every command

This convention replaces the manual `--context` flag assembly that was previously done
in Claude Desktop sessions and captured in build plans. The build plans remain as
the authoritative record of what was actually run, but the Forge uses manifests for
automated invocations.

### Checkpoint Tools (using nats-core event payloads)

| Tool | NATS Payload | Topic Pattern | Purpose |
|------|-------------|---------------|---------|
| `auto_approve_notify` | `NotificationPayload` | `jarvis.notification.{adapter}` | Inform human of auto-approved stage |
| `request_approval` | `ApprovalRequestPayload` | `agents.approval.{agent_id}.{task_id}` | Flag or hard-stop for human review |
| `await_approval` | subscribe `ApprovalResponsePayload` | `agents.approval.{agent_id}.{task_id}.response` | Wait for human decision |
| `record_override` | custom payload | `forge.telemetry.overrides` | Track human override rate for threshold learning |

### Infrastructure Tools

| Tool | Input | Output |
|------|-------|--------|
| `graphiti_seed` | Document paths, type | Seed confirmation |
| `graphiti_query` | Query string | Retrieved context |
| `verify` | Project path, test command | Pass/fail |
| `git_operations` | Branch/commit/PR params | Git result |
| `publish_pipeline_event` | Pipeline event payload | Delivery confirmation |

### Pipeline Event Publishing

The Forge publishes pipeline lifecycle events using the nats-core payloads that already exist:

| Pipeline Stage | Event Published | Payload |
|---------------|----------------|---------|
| Build queued | `pipeline.build-queued.{feature_id}` | `BuildQueuedPayload` (feature_id, repo, triggered_by, correlation_id — see anchor v2.2 §7) |
| Build starts | `pipeline.build-started.{feature_id}` | `BuildStartedPayload` (build_id, wave_total) |
| Build progress | `pipeline.build-progress.{feature_id}` | `BuildProgressPayload` (wave, overall_progress_pct, elapsed_seconds) |
| Stage complete | `pipeline.stage-complete.{feature_id}` | `StageCompletePayload` (stage, status, coach_score) |
| Build paused | `pipeline.build-paused.{feature_id}` | `BuildPausedPayload` (stage, coach_score, gate_mode) |
| Build completes | `pipeline.build-complete.{feature_id}` | `BuildCompletePayload` (tasks_completed, tasks_failed, pr_url, summary) |
| Build fails | `pipeline.build-failed.{feature_id}` | `BuildFailedPayload` (failure_reason, recoverable, failed_task_id) |

> **Decision (TASK-FVD3, correction 12):** `FeaturePlannedPayload` and `FeatureReadyForBuildPayload` are **retired** from this document. Anchor v2.2 §7 does not include them, and their function is covered by `StageCompletePayload` (for Stage 3 completion) and `BuildQueuedPayload` (for build readiness). The payloads still exist in `nats-core` and should be marked `@deprecated` there — coordinated via TASK-NCFA-001 in the nats-core repo.

### Degraded Mode

If a specialist agent is unavailable (not registered in `NATSKVManifestRegistry`), the Forge falls back:
- No product-owner-agent → Forge uses `/feature-spec` directly with raw input (lower quality product docs, no Coach score — defaults to 🟡 FLAG FOR REVIEW)
- No architect-agent → Forge uses `/system-arch` directly with a basic conversation starter (no fine-tuned architectural judgment, no Coach score — defaults to 🟡 FLAG FOR REVIEW)
- Both available → Full pipeline with specialist delegation and confidence-gated checkpoints (best quality)

This degradation is automatic — the Forge queries the registry at pipeline start and adapts its tool selection. In degraded mode, the absence of a Coach score means the Forge cannot auto-approve — it always flags for human review. This is the correct behaviour: less confidence in the output → more human oversight.
Phase 1 is complete. Stack=python; FEAT-FORGE-008 is "Mode B Feature & Mode C Review-Fix" — Mode B skips the PO/architect/system-arch/system-design upfront stages and starts at /feature-spec; Mode C is the /task-review → /task-work cycle. Both inherit the FEAT-FORGE-001..007 substrate (CLI, state machine, async-subagent autobuild, checkpoint protocol, constitutional PR rule).

Context loaded: stack=python, 7 existing .feature files (FEAT-FORGE-001..007), 5 context files read (Mode A spec + summary, CLI contract, approval protocol, build-lifecycle data model). FEAT-FORGE-008 traced via build plan as "Mode B Feature & Mode C Review-Fix" with depends-on FEAT-FORGE-007.

Now Phase 2 — the proposal.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Mode B Feature & Mode C Review-Fix (FEAT-FORGE-008)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@feat-forge-008 @mode-b-feature @mode-c-review-fix
Feature: Mode B Feature & Mode C Review-Fix
  As Rich, the operator triggering a non-greenfield build
  I want Forge to drive (Mode B) a single new feature on an existing project
    from /feature-spec through autobuild to a pull-request review, or
    (Mode C) a review-fix loop on an existing subject through /task-review
    and /task-work in a single supervised run
  So that I can land a reviewed pull request — or a clean review pass —
    without re-running the upfront delegation and architecture stages each time

  Background:
    Given Forge is registered on the fleet
    And the project repository already contains an architecture and design baseline
    And a writable worktree allowlist is configured for the project
    And the operator's calibration history has been ingested
    And a build has been queued for a feature identifier with a non-greenfield mode

━━ GROUP A: Key Examples (9 scenarios) ━━

  # Why: Mode B's capstone happy path — no PO/architect/system-arch/system-design upfront; start at /feature-spec
  # [ASSUMPTION: confidence=high] Mode B chain is /feature-spec → /feature-plan → autobuild → pull-request review (skipping product-owner, architect, /system-arch, and /system-design)
  @mode-b @key-example @smoke
  Scenario: A Mode B build drives a single new feature from specification to pull-request review
    Given the build is picked up from the queue in feature mode
    When Forge invokes feature specification, feature planning, and autobuild in order for that feature
    And every gated stage along the way is auto-approved
    And the pull request is created on the working branch
    Then the build should pause at pull-request review for mandatory human approval
    And no product-owner, architect, architecture, or design dispatch should have been recorded
    And the recorded stage history should contain feature specification, feature planning, autobuild, and pull-request review in order

  # Why: Mode B forward propagation — the spec output drives the plan, the plan drives autobuild
  @mode-b @key-example
  Scenario: The approved feature specification is supplied as input to feature planning and the approved plan is supplied to autobuild
    Given the feature specification stage has produced approved spec artefacts
    When Forge invokes feature planning
    Then the planning dispatch should be supplied with the spec artefact paths as context
    And feature planning should not be invoked before the specification is recorded as approved
    And once planning is approved, autobuild should be supplied with the plan artefact paths as context

  # Why: Mode B autobuild uses the inherited async-subagent pattern so the supervisor stays responsive
  # [ASSUMPTION: confidence=high] Mode B autobuild dispatch reuses the AsyncSubAgent pattern with the async_tasks state channel exposing wave and task indices (inherited from FEAT-FORGE-007)
  @mode-b @key-example @smoke
  Scenario: Mode B autobuild runs as an asynchronous subagent so the supervisor remains responsive during the run
    Given the feature has an approved build plan
    When Forge dispatches autobuild for that feature
    Then the dispatch should be a long-running asynchronous task with its own task identifier
    And the live status view should report wave and task progress for the running autobuild
    And the supervisor should remain available to answer status queries while the autobuild is in flight

  # Why: PR review is constitutionally pinned in Mode B, just as in Mode A — never auto-approve
  # [ASSUMPTION: confidence=high] Pull-request review is constitutionally pinned to mandatory human approval in every mode, enforced both at the prompt and the executor layer (belt-and-braces)
  @mode-b @key-example @regression
  Scenario: A Mode B pull-request review is mandatory human approval regardless of upstream Coach scores
    Given every preceding Mode B stage has been auto-approved with high Coach scores
    When Forge reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to be auto-approved

  # Why: A flag-for-review at any non-constitutional Mode B stage suspends the build and the next stage waits
  @mode-b @key-example
  Scenario: A flagged-for-review checkpoint in Mode B pauses the build and the next stage waits on the response
    Given Mode B is in the feature-planning stage and that stage has been flagged for review
    When the operator responds with approve
    Then the build should resume from autobuild
    And the prior approved spec and plan artefacts should still be available as context
    And no autobuild dispatch should have been recorded before the response was received

  # Why: Successful Mode B build records a session outcome with the chain of gate decisions for the inherited stages only
  @mode-b @key-example
  Scenario: Completing the Mode B pull-request review writes a session outcome that links every gate decision in order
    Given a Mode B build is paused at pull-request review
    When the operator approves the pull request
    Then the build should reach a complete terminal state
    And the recorded session outcome should reference every gate decision from feature specification through pull-request review
    And the recorded gate decisions should be linked in chronological order

  # Why: Mode C's capstone happy path — review identifies fix tasks; work cycles through them under gating
  # [ASSUMPTION: confidence=high] Mode C chain is /task-review → /task-work × N (one /task-work dispatch per fix task identified by /task-review), with optional pull-request review at the end if changes are pushed
  @mode-c @key-example @smoke
  Scenario: A Mode C build runs the review-fix cycle from an initial review through one work dispatch per identified fix task
    Given the build is picked up from the queue in review-fix mode
    When Forge invokes the task-review stage and it returns a non-empty set of fix tasks
    And every fix task is auto-approved at its gate
    And Forge dispatches a task-work invocation for each fix task in turn
    Then exactly one task-work dispatch should be recorded per fix task identified
    And no task-work dispatch should occur before its corresponding fix task is approved

  # Why: Mode C forward propagation — the /task-review output supplies fix-task definitions to /task-work
  @mode-c @key-example
  Scenario: Each /task-work dispatch is supplied with the fix-task definition produced by /task-review
    Given the task-review stage has produced fix-task definitions
    When Forge dispatches task-work for a given fix task
    Then the task-work dispatch context should include the fix-task definition produced by task-review
    And no task-work dispatch should be issued for a fix task before its review entry is recorded as approved

  # Why: Mode C may produce a pull request once fixes are applied — the constitutional rule still pins review to a human
  # [ASSUMPTION: confidence=medium] Mode C may culminate in a pull-request review when fixes change the working branch; the constitutional pull-request rule applies in Mode C exactly as in Modes A and B
  @mode-c @key-example @regression
  Scenario: A Mode C build that produces changes ends with a pull-request review pinned to mandatory human approval
    Given a Mode C build has applied changes through one or more task-work dispatches
    When Forge reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to be auto-approved

━━ GROUP B: Boundary Conditions (6 scenarios) ━━

  # Why: Single-feature Mode B is the only valid scope shape — there is no system-design catalogue iteration
  # [ASSUMPTION: confidence=high] Mode B operates on exactly one feature per build; multi-feature catalogues belong to Mode A only
  @mode-b @boundary @smoke
  Scenario: A Mode B build operates on exactly one feature and culminates in exactly one pull-request review pause
    Given a Mode B build is queued for a single feature identifier
    When the build progresses through every Mode B stage with auto-approval at every flagged-for-review checkpoint
    Then exactly one feature-specification dispatch and one feature-planning dispatch and one autobuild dispatch should be recorded
    And the chain should culminate in a single pull-request review pause

  # Why: Stage-ordering invariant for Mode B — every downstream stage waits on its prerequisite
  @mode-b @boundary
  Scenario Outline: A downstream Mode B stage is not dispatched before its prerequisite has reached the approved state
    Given the prerequisite "<prerequisite>" has not yet been approved
    When the build's reasoning loop considers the next dispatch
    Then no dispatch should be issued for "<stage>"

    Examples:
      | stage         | prerequisite                |
      | feature-plan  | feature-spec for the feature |
      | autobuild     | feature-plan for the feature |
      | pull-request  | autobuild for the feature    |

  # Why: Just-outside boundary — Mode B with no spec output cannot proceed to planning
  @mode-b @boundary @negative
  Scenario: A Mode B feature-specification stage that produces no spec artefacts cannot enter feature planning
    Given the feature-specification stage has produced no spec artefacts
    When the next-stage decision is reached
    Then the build should not issue a feature-planning dispatch
    And the build should be flagged for review with the missing-spec rationale recorded

  # Why: Just-inside boundary — Mode C with zero fix tasks completes without dispatching task-work
  # [ASSUMPTION: confidence=high] If /task-review returns an empty set of fix tasks, the Mode C build completes without dispatching /task-work and records the clean-review outcome
  @mode-c @boundary
  Scenario: A Mode C task-review that returns no fix tasks completes the build without dispatching any task-work
    Given the task-review stage has returned an empty set of fix tasks
    When the build evaluates the review outcome
    Then no task-work dispatch should be issued
    And the build should reach a complete terminal state with a clean-review outcome recorded

  # Why: Mode C scales with the number of identified fix tasks — exercises the iteration boundary
  @mode-c @boundary
  Scenario Outline: Mode C dispatches one /task-work per fix task identified by /task-review
    Given the task-review stage has returned <count> fix tasks
    When the build progresses through the fix-task loop
    Then <count> task-work dispatches should be recorded
    And every dispatched task-work should reference exactly one fix task identifier

    Examples:
      | count |
      | 1     |
      | 3     |
      | 5     |

  # Why: Stage-ordering invariant for Mode C — task-work waits on its review entry's approval
  @mode-c @boundary
  Scenario Outline: A Mode C downstream stage is not dispatched before its prerequisite has reached the approved state
    Given the prerequisite "<prerequisite>" has not yet been approved
    When the build's reasoning loop considers the next dispatch
    Then no dispatch should be issued for "<stage>"

    Examples:
      | stage        | prerequisite                       |
      | task-work    | task-review entry for the fix task |
      | pull-request | task-work for every fix task       |

━━ GROUP C: Negative Cases (8 scenarios) ━━

  # Why: A hard-stop at the first stage of Mode B terminates the build; no later dispatch should occur
  @mode-b @negative
  Scenario: A hard-stop at the Mode B feature-specification stage prevents any later stage from being dispatched
    Given the feature-specification stage returns a result that causes a hard-stop gate
    When the build evaluates the result
    Then the build should reach a failed terminal state
    And no feature-planning, autobuild, or pull-request dispatch should have been recorded

  # Why: A failed feature-spec dispatch must not cascade into a planning attempt
  @mode-b @negative
  Scenario: A failed Mode B feature-specification dispatch halts the build before planning
    Given the build is in the feature-specification stage
    When the feature-specification dispatch returns a failed result
    Then the build should not issue a feature-planning dispatch
    And the build should not issue an autobuild dispatch
    And the failed-spec rationale should be recorded against the build

  # Why: Constitutional override — Mode B PR review can never be auto-approved by upstream score alone
  @mode-b @negative @regression
  Scenario: Auto-approval is refused at the Mode B pull-request review stage even when the upstream Coach score is at the maximum
    Given the upstream Mode B stages have all returned the maximum Coach score
    When the build reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to resolve without a human decision

  # Why: Skip steering must not bypass the constitutional PR-review gate in Mode B
  @mode-b @negative @regression
  Scenario: A skip directive issued against the Mode B pull-request review stage is refused
    Given the Mode B build is paused at pull-request review
    When the operator issues a skip directive for that stage
    Then the build should remain paused for mandatory human approval
    And the skip should be recorded as refused with a constitutional rationale

  # Why: Mode B autobuild internal hard-stop must surface to the build and prevent PR creation
  @mode-b @negative
  Scenario: A Mode B autobuild internal hard-stop is propagated to the build and prevents pull-request creation
    Given Mode B autobuild is in flight
    When an internal task hits a hard-stop gate
    Then the autobuild lifecycle should reach a failed terminal state
    And no pull-request creation dispatch should be issued
    And the build's stage history should record the autobuild failure with the hard-stop rationale

  # Why: Reject decision at any pre-PR pause is terminal — there is no implicit retry
  @mode-b @mode-c @negative
  Scenario: A reject decision at a flagged-for-review checkpoint before pull-request review terminates the build
    Given the build is paused at any flagged-for-review checkpoint before pull-request review
    When the operator responds with reject
    Then the build should reach a failed terminal state
    And no later stage should be dispatched

  # Why: A hard-stop at the Mode C task-review stage terminates the build; no fix work should run
  @mode-c @negative
  Scenario: A hard-stop at the Mode C task-review stage prevents any task-work from being dispatched
    Given the task-review stage returns a result that causes a hard-stop gate
    When the build evaluates the review outcome
    Then the build should reach a failed terminal state
    And no task-work dispatch should have been recorded

  # Why: A failed /task-work for a fix task is recorded and prevents that fix task from being marked as completed
  # [ASSUMPTION: confidence=medium] A failed /task-work for a fix task halts that fix task's progression but does not implicitly cancel later fix tasks; the build's continuation is decided at the gate
  @mode-c @negative
  Scenario: A failed Mode C task-work dispatch records the failure against its fix task and blocks pull-request creation when no fix task has succeeded
    Given a Mode C fix task is in flight under task-work
    When the task-work dispatch returns a failed result
    Then the failure should be recorded against that fix task on the build's stage history
    And no pull-request creation dispatch should be issued for that fix task

━━ GROUP D: Edge Cases (9 scenarios) ━━

  # Why: Crash mid-stage triggers anchor §5 retry-from-scratch in Mode B as in Mode A
  @mode-b @edge-case
  Scenario Outline: A crash during any non-terminal Mode B stage is recovered by retry-from-scratch
    Given the Mode B build is in the "<stage>" stage
    When the runtime restarts after an unexpected interruption
    Then the build should re-enter the preparing state
    And the prior in-flight stage should be reattempted from the start

    Examples:
      | stage         |
      | feature-spec  |
      | feature-plan  |
      | autobuild     |

  # Why: Crash mid-stage triggers retry-from-scratch in Mode C as well
  @mode-c @edge-case
  Scenario Outline: A crash during any non-terminal Mode C stage is recovered by retry-from-scratch
    Given the Mode C build is in the "<stage>" stage
    When the runtime restarts after an unexpected interruption
    Then the build should re-enter the preparing state
    And the prior in-flight stage should be reattempted from the start

    Examples:
      | stage       |
      | task-review |
      | task-work   |

  # Why: Async subagent state channel is advisory on recovery — durable history is authoritative
  # [ASSUMPTION: confidence=high] On crash recovery during Mode B autobuild or Mode C task-work, durable history is authoritative and any live async-subagent state channel is advisory (inherited from FEAT-FORGE-007)
  @mode-b @mode-c @edge-case
  Scenario: After a crash during an asynchronous Mode B autobuild or Mode C task-work, durable history is the authoritative status source
    Given an asynchronous stage was in flight when the runtime crashed
    When the runtime restarts
    Then the build's authoritative status should be read from the durable history
    And any live state channel data should be treated as advisory

  # Why: Cancel during a paused stage produces a synthetic reject and terminates the build (CLI cancel mapping)
  @mode-b @mode-c @edge-case
  Scenario: A cancel directive while paused at a Mode B or Mode C checkpoint terminates the build with a synthetic reject
    Given the build is paused at a flagged-for-review checkpoint
    When the operator issues a cancel directive
    Then the pause should resolve as a synthetic reject with a cancel rationale
    And the build should reach a cancelled terminal state

  # Why: Cancel during an asynchronous stage halts the async task and terminates the build
  @mode-b @mode-c @edge-case
  Scenario: A cancel directive during an asynchronous Mode B autobuild or Mode C task-work halts the asynchronous task and terminates the build
    Given an asynchronous stage is in flight
    When the operator issues a cancel directive for the build
    Then the asynchronous task's live state should reach the cancelled lifecycle
    And the build should reach a cancelled terminal state with no pull-request creation attempted

  # Why: Skip on a non-constitutional stage records the skip and continues the chain
  @mode-b @mode-c @edge-case
  Scenario: A skip directive on a non-constitutional stage marks that stage skipped and resumes the chain
    Given the build is paused at a flagged-for-review checkpoint that is not pull-request review
    When the operator issues a skip directive
    Then the stage should be recorded as skipped on the build's stage history
    And the build should resume at the next stage in the chain

  # Why: Approval responses are routed by build identifier — concurrent paused builds remain isolated
  @mode-b @mode-c @edge-case
  Scenario: An approval response is routed to the Mode B or Mode C build whose identifier matches the response channel
    Given two builds are simultaneously paused at flagged-for-review checkpoints
    When an approval response is received that matches one build's identifier
    Then only that build should resume
    And the other paused build should remain awaiting its own approval

  # Why: Repeat approval for the same request is idempotent — first response wins (CLI replay safety)
  @mode-b @mode-c @edge-case
  Scenario: A duplicate approval response for the same paused stage is ignored
    Given the build has resumed after an approval response was honoured
    When a duplicate response with the same request identifier arrives
    Then the build should not re-resume
    And no additional stage transition should be recorded for the duplicate

  # Why: Mode C terminates the cycle when /task-review returns a clean review after a fix iteration
  # [ASSUMPTION: confidence=medium] Mode C terminates the review-fix cycle when a follow-up /task-review returns no further fix tasks; iteration count is bounded by reviewer judgement, not a fixed numeric ceiling
  @mode-c @edge-case
  Scenario: A follow-up Mode C task-review that returns no further fix tasks terminates the review-fix cycle
    Given the Mode C build has completed every dispatched task-work
    When Forge invokes a follow-up task-review
    And the follow-up review returns no further fix tasks
    Then no further task-work dispatch should be issued
    And the build should advance to the next stage in the chain or to a clean terminal outcome

━━ GROUP E: Security (3 scenarios) ━━

  # Why: Constitutional pull-request rule is enforced at both the prompt layer and the executor layer in every mode
  # [ASSUMPTION: confidence=high] Constitutional pull-request enforcement is mode-agnostic — the executor-side hardcoded branch fires for any tool resembling pull-request creation or review regardless of mode
  @mode-b @mode-c @security @regression
  Scenario: Mode B and Mode C pull-request review enforcement holds even if a misconfigured prompt would have allowed auto-approve
    Given the system prompt is configured incorrectly so that pull-request review appears auto-approvable
    When the build reaches the pull-request review stage in either mode
    Then the executor layer should still enforce mandatory human approval

  # Why: Subprocess results cannot escalate beyond their delegated authority at the gating layer
  @mode-b @mode-c @security
  Scenario: A subprocess result that asserts an override of constitutional rules is ignored at gating
    Given a subprocess stage returns a result claiming to override the pull-request review rule
    When the build reaches the pull-request review stage
    Then the override claim should be ignored
    And the build should pause for mandatory human approval

  # Why: Each build runs only inside its ephemeral worktree allowlist — no cross-build leakage in either mode
  @mode-b @mode-c @security
  Scenario: Mode B and Mode C subprocess stages run only against the build's ephemeral worktree path
    Given the build has a configured worktree path
    When any subprocess stage is dispatched
    Then the working directory used by the subprocess should fall under the build's worktree allowlist
    And no path outside that allowlist should be writable by the dispatched subprocess

━━ GROUP F: Concurrency (3 scenarios) ━━

  # Why: Two concurrent Mode B builds run with isolated approval channels and isolated autobuild task identifiers
  @mode-b @concurrency
  Scenario: Two concurrent Mode B builds use separate approval channels and separate autobuild task identifiers
    Given two distinct Mode B builds are dispatched at approximately the same time
    When both builds reach autobuild and both later reach a flagged-for-review pause
    Then each build should have a distinct autobuild task identifier
    And each build's approval pause should resolve only on a response matching its own build identifier

  # Why: Mode B and Mode C can run concurrently — different stage chains over the same checkpoint substrate
  @mode-b @mode-c @concurrency
  Scenario: A Mode B and a Mode C build run concurrently with isolated approval channels and stage chains
    Given a Mode B build is in flight at autobuild
    And a Mode C build is in flight at task-work
    When each build reaches a flagged-for-review pause
    Then each build's approval pause should resolve only on a response matching its own build identifier
    And the supervisor should be able to dispatch the next stage of either build without waiting on the other

  # Why: A long-running asynchronous stage does not block the supervisor's reasoning loop for unrelated builds
  @mode-b @mode-c @concurrency
  Scenario: The supervisor can dispatch a different build's stage while another build's asynchronous stage is mid-flight
    Given a first build's asynchronous stage is in the running lifecycle
    When a second build is queued and picked up
    Then the second build's first stage should be dispatched without waiting for the first build's asynchronous stage to complete

━━ GROUP G: Data Integrity (4 scenarios) ━━

  # Why: Mode B canonical stage-history ordering — the chain reflects the actual order without PO/architect/system-arch/system-design entries
  @mode-b @data-integrity
  Scenario: The recorded stage history of a successful Mode B build follows the canonical Mode B ordering
    Given a Mode B build has reached the complete terminal state
    When the operator inspects the build's stage history
    Then the stage entries should appear in the order feature-specification, feature-planning, autobuild, then pull-request review
    And no product-owner, architect, architecture, or system-design entries should appear

  # Why: Mode C canonical stage-history ordering — review entries precede the corresponding work entries
  @mode-c @data-integrity
  Scenario: The recorded stage history of a successful Mode C build follows the canonical Mode C ordering
    Given a Mode C build has reached the complete terminal state
    When the operator inspects the build's stage history
    Then a task-review entry should precede every task-work entry it produced
    And task-work entries for distinct fix tasks should each reference the fix task identifier they implemented

  # Why: Per-fix-task artefact attribution — Mode C work products belong to the fix task that produced them
  @mode-c @data-integrity
  Scenario: Per-fix-task artefact paths are recorded against the fix task that produced them
    Given the task-review stage has produced two or more fix tasks
    When task-work completes for each fix task
    Then each task-work stage entry should record the artefact paths produced for its fix task only
    And no artefact path should be attributed to more than one fix task

  # Why: A failed outbound notification publish must not regress an authoritative durable approval
  @mode-b @mode-c @data-integrity
  Scenario: A notification publish failure does not regress a Mode B or Mode C build's recorded stage progress
    Given a stage has been approved
    When the outbound notification publish for that approval fails
    Then the stage should still be recorded as approved on the build's history
    And the next stage's prerequisite should still evaluate as satisfied

━━ GROUP H: Integration Boundaries (4 scenarios) ━━

  # Why: End-to-end smoke for Mode B — minimal queue → PR-awaiting-review
  @mode-b @integration @smoke
  Scenario: A minimal Mode B build for a single feature drives to a pull request awaiting human review
    Given the operator queues a Mode B build for a single feature identifier
    When the build proceeds through every Mode B stage with auto-approval at every flagged-for-review checkpoint
    Then the terminal state should be paused at pull-request review awaiting human approval
    And a pull-request URL should be recorded against the build

  # Why: End-to-end smoke for Mode C — minimal queue → clean-review terminal
  @mode-c @integration @smoke
  Scenario: A minimal Mode C build with a single fix task completes through one task-review and one task-work dispatch
    Given the operator queues a Mode C build
    And the initial task-review will return exactly one fix task
    When the build proceeds with auto-approval at every flagged-for-review checkpoint
    Then exactly one task-review and one task-work stage entry should be recorded
    And the build should reach a complete or pull-request-review terminal outcome consistent with the changes applied

  # Why: An internal asynchronous pause must be observable through the supervisor without blocking other supervisor work
  @mode-b @mode-c @integration
  Scenario: An internal asynchronous-stage pause is observable through the supervisor without blocking other supervisor work
    Given an asynchronous stage's internal task fires a flagged-for-review pause
    When the operator queries live status
    Then the asynchronous stage's live state should report awaiting-approval with the stage label
    And the supervisor should remain free to perform other work for other builds

  # Why: Mode B/C inherit the correlation-threading audit anchor — every lifecycle event for one build carries one correlation id
  @mode-b @mode-c @integration @data-integrity
  Scenario: Every published lifecycle event for a Mode B or Mode C build threads the same correlation identifier from queue to terminal
    Given the build has been queued with a correlation identifier
    When the build progresses to a terminal state
    Then every lifecycle event published for that build should carry that same correlation identifier

━━ GROUP I: Expansion (3 scenarios) ━━

  # Why: First-write-wins discipline survives at the integration level even when two operators respond simultaneously
  @mode-b @mode-c @concurrency @edge-case
  Scenario: Two simultaneous approval responses for the same paused build resolve as first-wins
    Given the build is paused at a flagged-for-review checkpoint
    When two approval responses arrive simultaneously for the same paused stage with different decisions
    Then the build should resolve under exactly one of those decisions
    And no second resume should be applied for the duplicate response

  # Why: Calibration snapshot stability — a long-running build sees a consistent priors view, not a moving target
  # [ASSUMPTION: confidence=medium] Calibration priors are snapshotted at build start and remain stable for the duration of that build (inherited from FEAT-FORGE-007)
  @mode-b @mode-c @data-integrity
  Scenario: Calibration priors captured at the start of a Mode B or Mode C build remain the snapshot used by every stage of that build
    Given a build is picked up and a calibration-priors snapshot is captured at start
    When the operator's calibration history is updated while the build is mid-run
    Then later stages of the in-flight build should still use the priors snapshot captured at start

  # Why: Long-term memory seeding is best-effort and must never regress an authoritative approval in either mode
  @mode-b @mode-c @integration @data-integrity
  Scenario: A long-term-memory seeding failure for one stage does not regress that stage's recorded approval
    Given a stage has been approved by gating
    When the long-term-memory seeding for that stage's gate decision fails
    Then the stage should still be recorded as approved on the build's history
    And the next stage's prerequisite should still evaluate as satisfied

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 49 scenarios across 9 groups (A:9 / B:6 / C:8 / D:9 / E:3 / F:3 / G:4 / H:4 / I:3)
Inferred assumptions: 8 (will be resolved in Phase 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each group, you may:
  [A] Accept   [R] Reject   [M] Modify   [+] Add   [?] Defer

Fast path: type "A A A A A A A A A" to accept all nine groups.

GROUP A — Key Examples         (9 scenarios): _
GROUP B — Boundary Conditions  (6 scenarios): _
GROUP C — Negative Cases       (8 scenarios): _
GROUP D — Edge Cases           (9 scenarios): _
GROUP E — Security             (3 scenarios): _
GROUP F — Concurrency          (3 scenarios): _
GROUP G — Data Integrity       (4 scenarios): _
GROUP H — Integration Bounds   (4 scenarios): _
GROUP I — Expansion            (3 scenarios): _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reply with curation choices (e.g. A A A A A A A A A for accept-all, or per-group [A/R/M/+/?] with notes for M/+).

A A A A A A A A A
All nine groups accepted. Now Phase 4 — edge case expansion offer.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Beyond the 49 already accepted, I've identified 7 additional scenarios
that probe distinctive Mode-B/Mode-C boundaries the proposal hasn't yet
nailed down. Sample on offer:

Security (1):
  - A Mode B build refuses to dispatch /system-arch or /system-design even
    if a misconfigured manifest tries to inject those stages

Concurrency (1):
  - Three concurrent builds (one Mode A, one Mode B, one Mode C) hold
    isolated approval channels and isolated stage chains

Data integrity (2):
  - Mode B records no degraded-mode rationale because it never dispatches
    to a specialist (asserts the spec's "no PO/architect" axiom positively)
  - Mode C records the fix-task lineage from the originating /task-review
    entry to each /task-work entry it produced

Integration boundaries (1):
  - Mode B that produces no diff (autobuild succeeds but the worktree
    is unchanged) does not attempt pull-request creation and records a
    no-op terminal outcome

Mode-interaction (2):
  - A Mode A build that converts to Mode-B-style continuation (e.g. for
    a single follow-up feature) is treated as a fresh Mode B build, not
    a continuation of the prior build's history
  - A Mode C run that produces no commits ends in a clean-review terminal
    outcome with no pull-request creation attempt and no PR URL

[Y] Yes — show all 7 and curate them
[S] Sample — already shown above; pick which to include
[N] No — skip and proceed to Phase 5

Your choice [Y/S/N]:
Y
Here are the 7 expansion scenarios in full Gherkin for curation.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION — full scenarios
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ GROUP J: Security expansion (1 scenario) ━━

  # Why: Mode B's stage chain is bounded — a misconfigured manifest cannot trick the supervisor into running upstream Mode A stages
  # [ASSUMPTION: confidence=medium] The supervisor's mode-aware planning refuses to dispatch /system-arch or /system-design in Mode B even if a context manifest references those stages
  @mode-b @security
  Scenario: A Mode B build refuses to dispatch /system-arch or /system-design even when a context manifest references those stages
    Given a Mode B build is queued
    And the project's context manifest references /system-arch and /system-design as available stages
    When the build's reasoning loop plans the stage chain
    Then no /system-arch or /system-design dispatch should be issued
    And the recorded stage history should contain only Mode B stages

━━ GROUP K: Concurrency expansion (1 scenario) ━━

  # Why: Three-way mode interleave — proves the substrate isolates approval channels and stage chains across all modes
  @mode-b @mode-c @concurrency
  Scenario: Three concurrent builds — one Mode A, one Mode B, one Mode C — hold isolated approval channels and isolated stage chains
    Given a Mode A build, a Mode B build, and a Mode C build are dispatched at approximately the same time
    When each build reaches a flagged-for-review pause on its own chain
    Then each build's approval pause should resolve only on a response matching its own build identifier
    And each build's recorded stage history should reflect only the stages of its own mode

━━ GROUP L: Data Integrity expansion (2 scenarios) ━━

  # Why: Positive assertion that Mode B never dispatches to specialists — there is no degraded rationale to record because there is no specialist stage
  # [ASSUMPTION: confidence=high] Mode B does not dispatch to product-owner or architect specialists, so specialist-availability outages do not gate or pause a Mode B build
  @mode-b @data-integrity
  Scenario: A Mode B build does not record a degraded-specialist rationale because no specialist dispatch is attempted
    Given no product-owner or architect specialist is reachable on the fleet
    When a Mode B build is queued and picked up
    Then no specialist dispatch should be attempted
    And no degraded-specialist rationale should appear on the build's stage history
    And the build should proceed into the feature-specification stage

  # Why: Mode C's fix-task lineage is the audit anchor for review-fix — every work entry traces back to its originating review
  @mode-c @data-integrity
  Scenario: Each Mode C task-work stage entry records the fix-task lineage back to its originating task-review entry
    Given the task-review stage has produced two or more fix tasks
    When task-work completes for each fix task
    Then each task-work stage entry should record the fix-task identifier it implemented
    And each fix-task identifier should reference the task-review stage entry that produced it

━━ GROUP M: Integration Boundaries expansion (1 scenario) ━━

  # Why: A successful autobuild that produces no diff cannot create a pull request — the constitutional rule has nothing to gate, and the build records that as a no-op
  # [ASSUMPTION: confidence=medium] When a Mode B autobuild succeeds without producing a diff against the working branch, no pull-request creation is attempted and the build terminates with a no-op outcome rather than pausing at pull-request review
  @mode-b @integration
  Scenario: A Mode B build whose autobuild produces no diff does not attempt pull-request creation
    Given the Mode B autobuild has reached the completed lifecycle with no changes against the working branch
    When the build evaluates the next stage
    Then no pull-request creation dispatch should be issued
    And the build should reach a terminal state with a no-op rationale recorded
    And no pull-request URL should be recorded against the build

━━ GROUP N: Mode-interaction expansion (2 scenarios) ━━

  # Why: Mode boundaries are per-build — a follow-up feature on a previously-built project starts a fresh Mode B build, not a continuation
  # [ASSUMPTION: confidence=high] Each queued build is its own lifecycle; a follow-up feature added after a Mode A run starts a fresh Mode B build with its own build identifier and its own correlation identifier
  @mode-b @edge-case
  Scenario: A follow-up feature added after a prior Mode A build is treated as a fresh Mode B build with its own identifiers
    Given a prior Mode A build for the same project has reached a terminal state
    When the operator queues a follow-up feature on that project
    Then the follow-up should be dispatched as a fresh Mode B build with its own build identifier and correlation identifier
    And the follow-up's stage history should not be appended to the prior Mode A build's stage history

  # Why: A Mode C run that finds nothing to fix and produces no commits has nothing to push — the build closes cleanly without invoking the constitutional gate
  # [ASSUMPTION: confidence=medium] A Mode C run that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt and no PR URL
  @mode-c @integration
  Scenario: A Mode C build that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt
    Given a Mode C build has completed every dispatched task-work without producing commits
    When the build evaluates the next stage
    Then no pull-request creation dispatch should be issued
    And the build should reach a complete terminal state with a clean-review outcome recorded
    And no pull-request URL should be recorded against the build

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total expansion: 7 scenarios across 5 groups (J:1 / K:1 / L:2 / M:1 / N:2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CURATION:
GROUP J — Security expansion          (1 scenario):  _
GROUP K — Concurrency expansion       (1 scenario):  _
GROUP L — Data Integrity expansion    (2 scenarios): _
GROUP M — Integration Bounds expand.  (1 scenario):  _
GROUP N — Mode-interaction expansion  (2 scenarios): _

Fast path: type "A A A A A" to accept all five expansion groups.
A A A A A
Now Phase 5 — assumption resolution. 17 inferred values were surfaced across the proposal and expansion. Each has a proposed default with confidence and basis.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (17 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press Enter (or send "A" / "accept all") to accept everything as-is, or
override individual items by id, e.g. "5: medium → high; reword to ..."

[1] Mode B chain composition
    Proposed: /feature-spec → /feature-plan → autobuild → pull-request review
              (skipping product-owner, architect, /system-arch, /system-design)
    Confidence: high
    Basis: forge-build-plan.md FEAT-FORGE-008 row — "skip PO/architect delegation, start from /feature-spec"

[2] Mode B autobuild dispatch pattern
    Proposed: AsyncSubAgent + async_tasks state channel (wave + task indices)
    Confidence: high
    Basis: Inherited from FEAT-FORGE-007 ASSUM-002 (Mode A confirmed)

[3] Constitutional pull-request rule applies to every mode
    Proposed: Pull-request review is mandatory human approval, enforced at both prompt
              and executor layer (belt-and-braces)
    Confidence: high
    Basis: API-nats-approval-protocol.md §8 + ADR-ARCH-026; FEAT-FORGE-007 ASSUM-005 confirmed

[4] Mode C chain composition
    Proposed: /task-review → /task-work × N (one /task-work per fix task), with
              optional pull-request review when fixes change the working branch
    Confidence: high
    Basis: forge-build-plan.md FEAT-FORGE-008 row — "/task-review → /task-work cycle"

[5] Mode C terminal step when changes are applied
    Proposed: Culminates in pull-request review pause (constitutional rule applies)
    Confidence: medium
    Basis: Build plan says "Both use checkpoint protocol"; PR review is the terminal
           gate of any flow that pushes commits — not stated explicitly for Mode C

[6] Mode B is single-feature per build
    Proposed: Mode B operates on exactly one feature per build; multi-feature
              catalogues belong to Mode A only (no /system-design step in Mode B)
    Confidence: high
    Basis: Mode B starts at /feature-spec — there is no /system-design stage to
           produce a multi-feature catalogue

[7] /task-review with no fix tasks
    Proposed: If /task-review returns an empty set, Mode C completes the build
              without any /task-work dispatch and records a clean-review outcome
    Confidence: high
    Basis: Direct consequence of "review-fix cycle" semantics — no fixes to apply

[8] Failed /task-work behaviour within Mode C cycle
    Proposed: A failed /task-work halts that fix task's progression but does not
              implicitly cancel later fix tasks; continuation is decided at the gate
    Confidence: medium
    Basis: Policy inference — the build plan does not specify cascade semantics for
           per-fix-task failure; mirrors Mode A's per-feature isolation pattern

[9] Crash recovery: durable history authoritative
    Proposed: On crash during an asynchronous stage, durable history is authoritative;
              live async-subagent state channel is advisory
    Confidence: high
    Basis: Inherited from FEAT-FORGE-007 ASSUM-004; DM-build-lifecycle §2.1 (INTERRUPTED
           → PREPARING retry-from-scratch); ADR-ARCH-021

[10] Mode C cycle termination
    Proposed: Cycle terminates when a follow-up /task-review returns no further fix
              tasks; iteration count is bounded by reviewer judgement, not a fixed ceiling
    Confidence: medium
    Basis: Policy inference — the build plan does not specify a numeric iteration cap

[11] Constitutional PR enforcement is mode-agnostic
    Proposed: The executor-side hardcoded branch fires for any tool resembling
              pull-request creation/review regardless of mode (Mode A, B, or C)
    Confidence: high
    Basis: API-nats-approval-protocol.md §8 — executor-side branch is unconditional

[12] Calibration priors snapshot stability
    Proposed: Calibration priors are snapshotted at build start and remain stable for
              the duration of that build (mid-run history changes apply only to later builds)
    Confidence: medium
    Basis: Inherited from FEAT-FORGE-007 ASSUM-007

[13] Mode-aware planning refuses upstream Mode A stages in Mode B
    Proposed: The supervisor refuses to dispatch /system-arch or /system-design in
              Mode B even if a context manifest references those stages
    Confidence: medium
    Basis: Security inference from the "Mode B starts at /feature-spec" boundary;
           not explicitly stated as a planning-layer guard

[14] Mode B never dispatches to PO/architect specialists
    Proposed: Mode B does not dispatch to product-owner or architect specialists,
              so specialist-availability outages do not gate or pause a Mode B build
    Confidence: high
    Basis: Direct consequence of assumption [1]

[15] Mode B no-diff autobuild outcome
    Proposed: A Mode B autobuild that succeeds without producing a diff does not
              attempt pull-request creation; the build terminates with a no-op outcome
              instead of pausing at pull-request review
    Confidence: medium
    Basis: Natural inference — gh-CLI cannot create an empty PR; build plan does not
           specify the exact terminal label for this case

[16] Each queued build is its own lifecycle
    Proposed: A follow-up feature added after a prior Mode A build starts a fresh
              Mode B build with its own build identifier and correlation identifier
    Confidence: high
    Basis: DM-build-lifecycle §1 + §5 invariants — every Build row is independent

[17] Mode C with no commits
    Proposed: A Mode C run that produces no commits ends in a complete terminal
              state with a clean-review outcome recorded; no pull-request creation
              is attempted and no PR URL is recorded
    Confidence: medium
    Basis: Symmetric to [15]; no commits means nothing to push to a PR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reply "A" / "accept all" to accept defaults, or list overrides by id.
accept all
All 17 assumptions accepted. Now Phase 6 — writing the three output files.

Bash Create the output directory for FEAT-FORGE-008
IN
mkdir -p features/mode-b-feature-and-mode-c-review-fix && ls features/mode-b-feature-and-mode-c-review-fix/

OUT
(Bash completed with no output)
Write mode-b-feature-and-mode-c-review-fix.feature
584 lines
# Generated by /feature-spec
# Feature: Mode B Feature & Mode C Review-Fix (FEAT-FORGE-008)
# Stack: python
# Assumptions: 17 (see mode-b-feature-and-mode-c-review-fix_assumptions.yaml)
# Generated: 2026-04-27T00:00:00Z

@feat-forge-008 @mode-b-feature @mode-c-review-fix
Feature: Mode B Feature & Mode C Review-Fix
  As Rich, the operator triggering a non-greenfield build
  I want Forge to drive (Mode B) a single new feature on an existing project
    from /feature-spec through autobuild to a pull-request review, or
    (Mode C) a review-fix loop on an existing subject through /task-review
    and /task-work in a single supervised run
  So that I can land a reviewed pull request — or a clean review pass —
    without re-running the upfront delegation and architecture stages each time

  Background:
    Given Forge is registered on the fleet
    And the project repository already contains an architecture and design baseline
    And a writable worktree allowlist is configured for the project
    And the operator's calibration history has been ingested
    And a build has been queued for a feature identifier with a non-greenfield mode

  # ===========================================================================
  # GROUP A — Key Examples
  # ===========================================================================

  # Why: Mode B's capstone happy path — no PO/architect/system-arch/system-design upfront; start at /feature-spec
  # [ASSUMPTION: confidence=high] Mode B chain is /feature-spec → /feature-plan → autobuild → pull-request review (skipping product-owner, architect, /system-arch, and /system-design)
  @mode-b @key-example @smoke
  Scenario: A Mode B build drives a single new feature from specification to pull-request review
    Given the build is picked up from the queue in feature mode
    When Forge invokes feature specification, feature planning, and autobuild in order for that feature
    And every gated stage along the way is auto-approved
    And the pull request is created on the working branch
    Then the build should pause at pull-request review for mandatory human approval
    And no product-owner, architect, architecture, or design dispatch should have been recorded
    And the recorded stage history should contain feature specification, feature planning, autobuild, and pull-request review in order

  # Why: Mode B forward propagation — the spec output drives the plan, the plan drives autobuild
  @mode-b @key-example
  Scenario: The approved feature specification is supplied as input to feature planning and the approved plan is supplied to autobuild
    Given the feature specification stage has produced approved spec artefacts
    When Forge invokes feature planning
    Then the planning dispatch should be supplied with the spec artefact paths as context
    And feature planning should not be invoked before the specification is recorded as approved
    And once planning is approved, autobuild should be supplied with the plan artefact paths as context

  # Why: Mode B autobuild uses the inherited async-subagent pattern so the supervisor stays responsive
  # [ASSUMPTION: confidence=high] Mode B autobuild dispatch reuses the AsyncSubAgent pattern with the async_tasks state channel exposing wave and task indices (inherited from FEAT-FORGE-007)
  @mode-b @key-example @smoke
  Scenario: Mode B autobuild runs as an asynchronous subagent so the supervisor remains responsive during the run
    Given the feature has an approved build plan
    When Forge dispatches autobuild for that feature
    Then the dispatch should be a long-running asynchronous task with its own task identifier
    And the live status view should report wave and task progress for the running autobuild
    And the supervisor should remain available to answer status queries while the autobuild is in flight

  # Why: PR review is constitutionally pinned in Mode B, just as in Mode A — never auto-approve
  # [ASSUMPTION: confidence=high] Pull-request review is constitutionally pinned to mandatory human approval in every mode, enforced both at the prompt and the executor layer (belt-and-braces)
  @mode-b @key-example @regression
  Scenario: A Mode B pull-request review is mandatory human approval regardless of upstream Coach scores
    Given every preceding Mode B stage has been auto-approved with high Coach scores
    When Forge reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to be auto-approved

  # Why: A flag-for-review at any non-constitutional Mode B stage suspends the build and the next stage waits
  @mode-b @key-example
  Scenario: A flagged-for-review checkpoint in Mode B pauses the build and the next stage waits on the response
    Given Mode B is in the feature-planning stage and that stage has been flagged for review
    When the operator responds with approve
    Then the build should resume from autobuild
    And the prior approved spec and plan artefacts should still be available as context
    And no autobuild dispatch should have been recorded before the response was received

  # Why: Successful Mode B build records a session outcome with the chain of gate decisions for the inherited stages only
  @mode-b @key-example
  Scenario: Completing the Mode B pull-request review writes a session outcome that links every gate decision in order
    Given a Mode B build is paused at pull-request review
    When the operator approves the pull request
    Then the build should reach a complete terminal state
    And the recorded session outcome should reference every gate decision from feature specification through pull-request review
    And the recorded gate decisions should be linked in chronological order

  # Why: Mode C's capstone happy path — review identifies fix tasks; work cycles through them under gating
  # [ASSUMPTION: confidence=high] Mode C chain is /task-review → /task-work × N (one /task-work dispatch per fix task identified by /task-review), with optional pull-request review at the end if changes are pushed
  @mode-c @key-example @smoke
  Scenario: A Mode C build runs the review-fix cycle from an initial review through one work dispatch per identified fix task
    Given the build is picked up from the queue in review-fix mode
    When Forge invokes the task-review stage and it returns a non-empty set of fix tasks
    And every fix task is auto-approved at its gate
    And Forge dispatches a task-work invocation for each fix task in turn
    Then exactly one task-work dispatch should be recorded per fix task identified
    And no task-work dispatch should occur before its corresponding fix task is approved

  # Why: Mode C forward propagation — the /task-review output supplies fix-task definitions to /task-work
  @mode-c @key-example
  Scenario: Each /task-work dispatch is supplied with the fix-task definition produced by /task-review
    Given the task-review stage has produced fix-task definitions
    When Forge dispatches task-work for a given fix task
    Then the task-work dispatch context should include the fix-task definition produced by task-review
    And no task-work dispatch should be issued for a fix task before its review entry is recorded as approved

  # Why: Mode C may produce a pull request once fixes are applied — the constitutional rule still pins review to a human
  # [ASSUMPTION: confidence=medium] Mode C may culminate in a pull-request review when fixes change the working branch; the constitutional pull-request rule applies in Mode C exactly as in Modes A and B
  @mode-c @key-example @regression
  Scenario: A Mode C build that produces changes ends with a pull-request review pinned to mandatory human approval
    Given a Mode C build has applied changes through one or more task-work dispatches
    When Forge reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to be auto-approved

  # ===========================================================================
  # GROUP B — Boundary Conditions
  # ===========================================================================

  # Why: Single-feature Mode B is the only valid scope shape — there is no system-design catalogue iteration
  # [ASSUMPTION: confidence=high] Mode B operates on exactly one feature per build; multi-feature catalogues belong to Mode A only
  @mode-b @boundary @smoke
  Scenario: A Mode B build operates on exactly one feature and culminates in exactly one pull-request review pause
    Given a Mode B build is queued for a single feature identifier
    When the build progresses through every Mode B stage with auto-approval at every flagged-for-review checkpoint
    Then exactly one feature-specification dispatch and one feature-planning dispatch and one autobuild dispatch should be recorded
    And the chain should culminate in a single pull-request review pause

  # Why: Stage-ordering invariant for Mode B — every downstream stage waits on its prerequisite
  @mode-b @boundary
  Scenario Outline: A downstream Mode B stage is not dispatched before its prerequisite has reached the approved state
    Given the prerequisite "<prerequisite>" has not yet been approved
    When the build's reasoning loop considers the next dispatch
    Then no dispatch should be issued for "<stage>"

    Examples:
      | stage         | prerequisite                 |
      | feature-plan  | feature-spec for the feature |
      | autobuild     | feature-plan for the feature |
      | pull-request  | autobuild for the feature    |

  # Why: Just-outside boundary — Mode B with no spec output cannot proceed to planning
  @mode-b @boundary @negative
  Scenario: A Mode B feature-specification stage that produces no spec artefacts cannot enter feature planning
    Given the feature-specification stage has produced no spec artefacts
    When the next-stage decision is reached
    Then the build should not issue a feature-planning dispatch
    And the build should be flagged for review with the missing-spec rationale recorded

  # Why: Just-inside boundary — Mode C with zero fix tasks completes without dispatching task-work
  # [ASSUMPTION: confidence=high] If /task-review returns an empty set of fix tasks, the Mode C build completes without dispatching /task-work and records the clean-review outcome
  @mode-c @boundary
  Scenario: A Mode C task-review that returns no fix tasks completes the build without dispatching any task-work
    Given the task-review stage has returned an empty set of fix tasks
    When the build evaluates the review outcome
    Then no task-work dispatch should be issued
    And the build should reach a complete terminal state with a clean-review outcome recorded

  # Why: Mode C scales with the number of identified fix tasks — exercises the iteration boundary
  @mode-c @boundary
  Scenario Outline: Mode C dispatches one /task-work per fix task identified by /task-review
    Given the task-review stage has returned <count> fix tasks
    When the build progresses through the fix-task loop
    Then <count> task-work dispatches should be recorded
    And every dispatched task-work should reference exactly one fix task identifier

    Examples:
      | count |
      | 1     |
      | 3     |
      | 5     |

  # Why: Stage-ordering invariant for Mode C — task-work waits on its review entry's approval
  @mode-c @boundary
  Scenario Outline: A Mode C downstream stage is not dispatched before its prerequisite has reached the approved state
    Given the prerequisite "<prerequisite>" has not yet been approved
    When the build's reasoning loop considers the next dispatch
    Then no dispatch should be issued for "<stage>"

    Examples:
      | stage        | prerequisite                       |
      | task-work    | task-review entry for the fix task |
      | pull-request | task-work for every fix task       |

  # ===========================================================================
  # GROUP C — Negative Cases
  # ===========================================================================

  # Why: A hard-stop at the first stage of Mode B terminates the build; no later dispatch should occur
  @mode-b @negative
  Scenario: A hard-stop at the Mode B feature-specification stage prevents any later stage from being dispatched
    Given the feature-specification stage returns a result that causes a hard-stop gate
    When the build evaluates the result
    Then the build should reach a failed terminal state
    And no feature-planning, autobuild, or pull-request dispatch should have been recorded

  # Why: A failed feature-spec dispatch must not cascade into a planning attempt
  @mode-b @negative
  Scenario: A failed Mode B feature-specification dispatch halts the build before planning
    Given the build is in the feature-specification stage
    When the feature-specification dispatch returns a failed result
    Then the build should not issue a feature-planning dispatch
    And the build should not issue an autobuild dispatch
    And the failed-spec rationale should be recorded against the build

  # Why: Constitutional override — Mode B PR review can never be auto-approved by upstream score alone
  @mode-b @negative @regression
  Scenario: Auto-approval is refused at the Mode B pull-request review stage even when the upstream Coach score is at the maximum
    Given the upstream Mode B stages have all returned the maximum Coach score
    When the build reaches the pull-request review stage
    Then the build should pause for mandatory human approval
    And the pause should not be eligible to resolve without a human decision

  # Why: Skip steering must not bypass the constitutional PR-review gate in Mode B
  @mode-b @negative @regression
  Scenario: A skip directive issued against the Mode B pull-request review stage is refused
    Given the Mode B build is paused at pull-request review
    When the operator issues a skip directive for that stage
    Then the build should remain paused for mandatory human approval
    And the skip should be recorded as refused with a constitutional rationale

  # Why: Mode B autobuild internal hard-stop must surface to the build and prevent PR creation
  @mode-b @negative
  Scenario: A Mode B autobuild internal hard-stop is propagated to the build and prevents pull-request creation
    Given Mode B autobuild is in flight
    When an internal task hits a hard-stop gate
    Then the autobuild lifecycle should reach a failed terminal state
    And no pull-request creation dispatch should be issued
    And the build's stage history should record the autobuild failure with the hard-stop rationale

  # Why: Reject decision at any pre-PR pause is terminal — there is no implicit retry
  @mode-b @mode-c @negative
  Scenario: A reject decision at a flagged-for-review checkpoint before pull-request review terminates the build
    Given the build is paused at any flagged-for-review checkpoint before pull-request review
    When the operator responds with reject
    Then the build should reach a failed terminal state
    And no later stage should be dispatched

  # Why: A hard-stop at the Mode C task-review stage terminates the build; no fix work should run
  @mode-c @negative
  Scenario: A hard-stop at the Mode C task-review stage prevents any task-work from being dispatched
    Given the task-review stage returns a result that causes a hard-stop gate
    When the build evaluates the review outcome
    Then the build should reach a failed terminal state
    And no task-work dispatch should have been recorded

  # Why: A failed /task-work for a fix task is recorded and prevents that fix task from being marked as completed
  # [ASSUMPTION: confidence=medium] A failed /task-work for a fix task halts that fix task's progression but does not implicitly cancel later fix tasks; the build's continuation is decided at the gate
  @mode-c @negative
  Scenario: A failed Mode C task-work dispatch records the failure against its fix task and blocks pull-request creation when no fix task has succeeded
    Given a Mode C fix task is in flight under task-work
    When the task-work dispatch returns a failed result
    Then the failure should be recorded against that fix task on the build's stage history
    And no pull-request creation dispatch should be issued for that fix task

  # ===========================================================================
  # GROUP D — Edge Cases
  # ===========================================================================

  # Why: Crash mid-stage triggers anchor §5 retry-from-scratch in Mode B as in Mode A
  @mode-b @edge-case
  Scenario Outline: A crash during any non-terminal Mode B stage is recovered by retry-from-scratch
    Given the Mode B build is in the "<stage>" stage
    When the runtime restarts after an unexpected interruption
    Then the build should re-enter the preparing state
    And the prior in-flight stage should be reattempted from the start

    Examples:
      | stage        |
      | feature-spec |
      | feature-plan |
      | autobuild    |

  # Why: Crash mid-stage triggers retry-from-scratch in Mode C as well
  @mode-c @edge-case
  Scenario Outline: A crash during any non-terminal Mode C stage is recovered by retry-from-scratch
    Given the Mode C build is in the "<stage>" stage
    When the runtime restarts after an unexpected interruption
    Then the build should re-enter the preparing state
    And the prior in-flight stage should be reattempted from the start

    Examples:
      | stage       |
      | task-review |
      | task-work   |

  # Why: Async subagent state channel is advisory on recovery — durable history is authoritative
  # [ASSUMPTION: confidence=high] On crash recovery during Mode B autobuild or Mode C task-work, durable history is authoritative and any live async-subagent state channel is advisory (inherited from FEAT-FORGE-007)
  @mode-b @mode-c @edge-case
  Scenario: After a crash during an asynchronous Mode B autobuild or Mode C task-work, durable history is the authoritative status source
    Given an asynchronous stage was in flight when the runtime crashed
    When the runtime restarts
    Then the build's authoritative status should be read from the durable history
    And any live state channel data should be treated as advisory

  # Why: Cancel during a paused stage produces a synthetic reject and terminates the build (CLI cancel mapping)
  @mode-b @mode-c @edge-case
  Scenario: A cancel directive while paused at a Mode B or Mode C checkpoint terminates the build with a synthetic reject
    Given the build is paused at a flagged-for-review checkpoint
    When the operator issues a cancel directive
    Then the pause should resolve as a synthetic reject with a cancel rationale
    And the build should reach a cancelled terminal state

  # Why: Cancel during an asynchronous stage halts the async task and terminates the build
  @mode-b @mode-c @edge-case
  Scenario: A cancel directive during an asynchronous Mode B autobuild or Mode C task-work halts the asynchronous task and terminates the build
    Given an asynchronous stage is in flight
    When the operator issues a cancel directive for the build
    Then the asynchronous task's live state should reach the cancelled lifecycle
    And the build should reach a cancelled terminal state with no pull-request creation attempted

  # Why: Skip on a non-constitutional stage records the skip and continues the chain
  @mode-b @mode-c @edge-case
  Scenario: A skip directive on a non-constitutional stage marks that stage skipped and resumes the chain
    Given the build is paused at a flagged-for-review checkpoint that is not pull-request review
    When the operator issues a skip directive
    Then the stage should be recorded as skipped on the build's stage history
    And the build should resume at the next stage in the chain

  # Why: Approval responses are routed by build identifier — concurrent paused builds remain isolated
  @mode-b @mode-c @edge-case
  Scenario: An approval response is routed to the Mode B or Mode C build whose identifier matches the response channel
    Given two builds are simultaneously paused at flagged-for-review checkpoints
    When an approval response is received that matches one build's identifier
    Then only that build should resume
    And the other paused build should remain awaiting its own approval

  # Why: Repeat approval for the same request is idempotent — first response wins (CLI replay safety)
  @mode-b @mode-c @edge-case
  Scenario: A duplicate approval response for the same paused stage is ignored
    Given the build has resumed after an approval response was honoured
    When a duplicate response with the same request identifier arrives
    Then the build should not re-resume
    And no additional stage transition should be recorded for the duplicate

  # Why: Mode C terminates the cycle when /task-review returns a clean review after a fix iteration
  # [ASSUMPTION: confidence=medium] Mode C terminates the review-fix cycle when a follow-up /task-review returns no further fix tasks; iteration count is bounded by reviewer judgement, not a fixed numeric ceiling
  @mode-c @edge-case
  Scenario: A follow-up Mode C task-review that returns no further fix tasks terminates the review-fix cycle
    Given the Mode C build has completed every dispatched task-work
    When Forge invokes a follow-up task-review
    And the follow-up review returns no further fix tasks
    Then no further task-work dispatch should be issued
    And the build should advance to the next stage in the chain or to a clean terminal outcome

  # ===========================================================================
  # GROUP E — Security
  # ===========================================================================

  # Why: Constitutional pull-request rule is enforced at both the prompt layer and the executor layer in every mode
  # [ASSUMPTION: confidence=high] Constitutional pull-request enforcement is mode-agnostic — the executor-side hardcoded branch fires for any tool resembling pull-request creation or review regardless of mode
  @mode-b @mode-c @security @regression
  Scenario: Mode B and Mode C pull-request review enforcement holds even if a misconfigured prompt would have allowed auto-approve
    Given the system prompt is configured incorrectly so that pull-request review appears auto-approvable
    When the build reaches the pull-request review stage in either mode
    Then the executor layer should still enforce mandatory human approval

  # Why: Subprocess results cannot escalate beyond their delegated authority at the gating layer
  @mode-b @mode-c @security
  Scenario: A subprocess result that asserts an override of constitutional rules is ignored at gating
    Given a subprocess stage returns a result claiming to override the pull-request review rule
    When the build reaches the pull-request review stage
    Then the override claim should be ignored
    And the build should pause for mandatory human approval

  # Why: Each build runs only inside its ephemeral worktree allowlist — no cross-build leakage in either mode
  @mode-b @mode-c @security
  Scenario: Mode B and Mode C subprocess stages run only against the build's ephemeral worktree path
    Given the build has a configured worktree path
    When any subprocess stage is dispatched
    Then the working directory used by the subprocess should fall under the build's worktree allowlist
    And no path outside that allowlist should be writable by the dispatched subprocess

  # ===========================================================================
  # GROUP F — Concurrency
  # ===========================================================================

  # Why: Two concurrent Mode B builds run with isolated approval channels and isolated autobuild task identifiers
  @mode-b @concurrency
  Scenario: Two concurrent Mode B builds use separate approval channels and separate autobuild task identifiers
    Given two distinct Mode B builds are dispatched at approximately the same time
    When both builds reach autobuild and both later reach a flagged-for-review pause
    Then each build should have a distinct autobuild task identifier
    And each build's approval pause should resolve only on a response matching its own build identifier

  # Why: Mode B and Mode C can run concurrently — different stage chains over the same checkpoint substrate
  @mode-b @mode-c @concurrency
  Scenario: A Mode B and a Mode C build run concurrently with isolated approval channels and stage chains
    Given a Mode B build is in flight at autobuild
    And a Mode C build is in flight at task-work
    When each build reaches a flagged-for-review pause
    Then each build's approval pause should resolve only on a response matching its own build identifier
    And the supervisor should be able to dispatch the next stage of either build without waiting on the other

  # Why: A long-running asynchronous stage does not block the supervisor's reasoning loop for unrelated builds
  @mode-b @mode-c @concurrency
  Scenario: The supervisor can dispatch a different build's stage while another build's asynchronous stage is mid-flight
    Given a first build's asynchronous stage is in the running lifecycle
    When a second build is queued and picked up
    Then the second build's first stage should be dispatched without waiting for the first build's asynchronous stage to complete

  # ===========================================================================
  # GROUP G — Data Integrity
  # ===========================================================================

  # Why: Mode B canonical stage-history ordering — the chain reflects the actual order without PO/architect/system-arch/system-design entries
  @mode-b @data-integrity
  Scenario: The recorded stage history of a successful Mode B build follows the canonical Mode B ordering
    Given a Mode B build has reached the complete terminal state
    When the operator inspects the build's stage history
    Then the stage entries should appear in the order feature-specification, feature-planning, autobuild, then pull-request review
    And no product-owner, architect, architecture, or system-design entries should appear

  # Why: Mode C canonical stage-history ordering — review entries precede the corresponding work entries
  @mode-c @data-integrity
  Scenario: The recorded stage history of a successful Mode C build follows the canonical Mode C ordering
    Given a Mode C build has reached the complete terminal state
    When the operator inspects the build's stage history
    Then a task-review entry should precede every task-work entry it produced
    And task-work entries for distinct fix tasks should each reference the fix task identifier they implemented

  # Why: Per-fix-task artefact attribution — Mode C work products belong to the fix task that produced them
  @mode-c @data-integrity
  Scenario: Per-fix-task artefact paths are recorded against the fix task that produced them
    Given the task-review stage has produced two or more fix tasks
    When task-work completes for each fix task
    Then each task-work stage entry should record the artefact paths produced for its fix task only
    And no artefact path should be attributed to more than one fix task

  # Why: A failed outbound notification publish must not regress an authoritative durable approval
  @mode-b @mode-c @data-integrity
  Scenario: A notification publish failure does not regress a Mode B or Mode C build's recorded stage progress
    Given a stage has been approved
    When the outbound notification publish for that approval fails
    Then the stage should still be recorded as approved on the build's history
    And the next stage's prerequisite should still evaluate as satisfied

  # ===========================================================================
  # GROUP H — Integration Boundaries
  # ===========================================================================

  # Why: End-to-end smoke for Mode B — minimal queue → PR-awaiting-review
  @mode-b @integration @smoke
  Scenario: A minimal Mode B build for a single feature drives to a pull request awaiting human review
    Given the operator queues a Mode B build for a single feature identifier
    When the build proceeds through every Mode B stage with auto-approval at every flagged-for-review checkpoint
    Then the terminal state should be paused at pull-request review awaiting human approval
    And a pull-request URL should be recorded against the build

  # Why: End-to-end smoke for Mode C — minimal queue → clean-review terminal
  @mode-c @integration @smoke
  Scenario: A minimal Mode C build with a single fix task completes through one task-review and one task-work dispatch
    Given the operator queues a Mode C build
    And the initial task-review will return exactly one fix task
    When the build proceeds with auto-approval at every flagged-for-review checkpoint
    Then exactly one task-review and one task-work stage entry should be recorded
    And the build should reach a complete or pull-request-review terminal outcome consistent with the changes applied

  # Why: An internal asynchronous pause must be observable through the supervisor without blocking other supervisor work
  @mode-b @mode-c @integration
  Scenario: An internal asynchronous-stage pause is observable through the supervisor without blocking other supervisor work
    Given an asynchronous stage's internal task fires a flagged-for-review pause
    When the operator queries live status
    Then the asynchronous stage's live state should report awaiting-approval with the stage label
    And the supervisor should remain free to perform other work for other builds

  # Why: Mode B/C inherit the correlation-threading audit anchor — every lifecycle event for one build carries one correlation id
  @mode-b @mode-c @integration @data-integrity
  Scenario: Every published lifecycle event for a Mode B or Mode C build threads the same correlation identifier from queue to terminal
    Given the build has been queued with a correlation identifier
    When the build progresses to a terminal state
    Then every lifecycle event published for that build should carry that same correlation identifier

  # ===========================================================================
  # GROUP I — Expansion (additional integration-level scenarios)
  # ===========================================================================

  # Why: First-write-wins discipline survives at the integration level even when two operators respond simultaneously
  @mode-b @mode-c @concurrency @edge-case
  Scenario: Two simultaneous approval responses for the same paused build resolve as first-wins
    Given the build is paused at a flagged-for-review checkpoint
    When two approval responses arrive simultaneously for the same paused stage with different decisions
    Then the build should resolve under exactly one of those decisions
    And no second resume should be applied for the duplicate response

  # Why: Calibration snapshot stability — a long-running build sees a consistent priors view, not a moving target
  # [ASSUMPTION: confidence=medium] Calibration priors are snapshotted at build start and remain stable for the duration of that build (inherited from FEAT-FORGE-007)
  @mode-b @mode-c @data-integrity
  Scenario: Calibration priors captured at the start of a Mode B or Mode C build remain the snapshot used by every stage of that build
    Given a build is picked up and a calibration-priors snapshot is captured at start
    When the operator's calibration history is updated while the build is mid-run
    Then later stages of the in-flight build should still use the priors snapshot captured at start

  # Why: Long-term memory seeding is best-effort and must never regress an authoritative approval in either mode
  @mode-b @mode-c @integration @data-integrity
  Scenario: A long-term-memory seeding failure for one stage does not regress that stage's recorded approval
    Given a stage has been approved by gating
    When the long-term-memory seeding for that stage's gate decision fails
    Then the stage should still be recorded as approved on the build's history
    And the next stage's prerequisite should still evaluate as satisfied

  # ===========================================================================
  # GROUP J — Security expansion
  # ===========================================================================

  # Why: Mode B's stage chain is bounded — a misconfigured manifest cannot trick the supervisor into running upstream Mode A stages
  # [ASSUMPTION: confidence=medium] The supervisor's mode-aware planning refuses to dispatch /system-arch or /system-design in Mode B even if a context manifest references those stages
  @mode-b @security
  Scenario: A Mode B build refuses to dispatch /system-arch or /system-design even when a context manifest references those stages
    Given a Mode B build is queued
    And the project's context manifest references /system-arch and /system-design as available stages
    When the build's reasoning loop plans the stage chain
    Then no /system-arch or /system-design dispatch should be issued
    And the recorded stage history should contain only Mode B stages

  # ===========================================================================
  # GROUP K — Concurrency expansion
  # ===========================================================================

  # Why: Three-way mode interleave — proves the substrate isolates approval channels and stage chains across all modes
  @mode-b @mode-c @concurrency
  Scenario: Three concurrent builds — one Mode A, one Mode B, one Mode C — hold isolated approval channels and isolated stage chains
    Given a Mode A build, a Mode B build, and a Mode C build are dispatched at approximately the same time
    When each build reaches a flagged-for-review pause on its own chain
    Then each build's approval pause should resolve only on a response matching its own build identifier
    And each build's recorded stage history should reflect only the stages of its own mode

  # ===========================================================================
  # GROUP L — Data Integrity expansion
  # ===========================================================================

  # Why: Positive assertion that Mode B never dispatches to specialists — there is no degraded rationale to record because there is no specialist stage
  # [ASSUMPTION: confidence=high] Mode B does not dispatch to product-owner or architect specialists, so specialist-availability outages do not gate or pause a Mode B build
  @mode-b @data-integrity
  Scenario: A Mode B build does not record a degraded-specialist rationale because no specialist dispatch is attempted
    Given no product-owner or architect specialist is reachable on the fleet
    When a Mode B build is queued and picked up
    Then no specialist dispatch should be attempted
    And no degraded-specialist rationale should appear on the build's stage history
    And the build should proceed into the feature-specification stage

  # Why: Mode C's fix-task lineage is the audit anchor for review-fix — every work entry traces back to its originating review
  @mode-c @data-integrity
  Scenario: Each Mode C task-work stage entry records the fix-task lineage back to its originating task-review entry
    Given the task-review stage has produced two or more fix tasks
    When task-work completes for each fix task
    Then each task-work stage entry should record the fix-task identifier it implemented
    And each fix-task identifier should reference the task-review stage entry that produced it

  # ===========================================================================
  # GROUP M — Integration Boundaries expansion
  # ===========================================================================

  # Why: A successful autobuild that produces no diff cannot create a pull request — the constitutional rule has nothing to gate, and the build records that as a no-op
  # [ASSUMPTION: confidence=medium] When a Mode B autobuild succeeds without producing a diff against the working branch, no pull-request creation is attempted and the build terminates with a no-op outcome rather than pausing at pull-request review
  @mode-b @integration
  Scenario: A Mode B build whose autobuild produces no diff does not attempt pull-request creation
    Given the Mode B autobuild has reached the completed lifecycle with no changes against the working branch
    When the build evaluates the next stage
    Then no pull-request creation dispatch should be issued
    And the build should reach a terminal state with a no-op rationale recorded
    And no pull-request URL should be recorded against the build

  # ===========================================================================
  # GROUP N — Mode-interaction expansion
  # ===========================================================================

  # Why: Mode boundaries are per-build — a follow-up feature on a previously-built project starts a fresh Mode B build, not a continuation
  # [ASSUMPTION: confidence=high] Each queued build is its own lifecycle; a follow-up feature added after a Mode A run starts a fresh Mode B build with its own build identifier and its own correlation identifier
  @mode-b @edge-case
  Scenario: A follow-up feature added after a prior Mode A build is treated as a fresh Mode B build with its own identifiers
    Given a prior Mode A build for the same project has reached a terminal state
    When the operator queues a follow-up feature on that project
    Then the follow-up should be dispatched as a fresh Mode B build with its own build identifier and correlation identifier
    And the follow-up's stage history should not be appended to the prior Mode A build's stage history

  # Why: A Mode C run that finds nothing to fix and produces no commits has nothing to push — the build closes cleanly without invoking the constitutional gate
  # [ASSUMPTION: confidence=medium] A Mode C run that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt and no PR URL
  @mode-c @integration
  Scenario: A Mode C build that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt
    Given a Mode C build has completed every dispatched task-work without producing commits
    When the build evaluates the next stage
    Then no pull-request creation dispatch should be issued
    And the build should reach a complete terminal state with a clean-review outcome recorded
    And no pull-request URL should be recorded against the build
Write mode-b-feature-and-mode-c-review-fix_assumptions.yaml
129 lines
# Assumptions manifest for mode-b-feature-and-mode-c-review-fix.feature
# Generated by /feature-spec

feature: "Mode B Feature & Mode C Review-Fix"
feature_id: "FEAT-FORGE-008"
generated: "2026-04-27T00:00:00Z"
stack: "python"
review_required: false

assumptions:
  - id: "ASSUM-001"
    scenario: "A Mode B build drives a single new feature from specification to pull-request review"
    assumption: "Mode B chain is /feature-spec → /feature-plan → autobuild → pull-request review (skipping product-owner, architect, /system-arch, and /system-design)"
    confidence: high
    basis: "forge-build-plan.md FEAT-FORGE-008 row — 'Mode B: add feature to existing project (skip PO/architect delegation, start from /feature-spec)'"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Mode B autobuild runs as an asynchronous subagent so the supervisor remains responsive during the run"
    assumption: "Mode B autobuild dispatch reuses the AsyncSubAgent pattern with the async_tasks state channel exposing wave and task indices (inherited from FEAT-FORGE-007)"
    confidence: high
    basis: "Inherited from FEAT-FORGE-007 ASSUM-002; ADR-ARCH-031 (async subagents); DDR-006 (async-subagent state channel contract)"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "A Mode B pull-request review is mandatory human approval regardless of upstream Coach scores"
    assumption: "Pull-request review is constitutionally pinned to mandatory human approval in every mode, enforced both at the prompt and the executor layer (belt-and-braces)"
    confidence: high
    basis: "API-nats-approval-protocol.md §8 (Constitutional Rule — PR Review); ADR-ARCH-026; FEAT-FORGE-007 ASSUM-005 confirmed"
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "A Mode C build runs the review-fix cycle from an initial review through one work dispatch per identified fix task"
    assumption: "Mode C chain is /task-review → /task-work × N (one /task-work dispatch per fix task identified by /task-review), with optional pull-request review at the end if changes are pushed"
    confidence: high
    basis: "forge-build-plan.md FEAT-FORGE-008 row — 'Mode C: review and fix issues (/task-review → /task-work cycle)'"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "A Mode C build that produces changes ends with a pull-request review pinned to mandatory human approval"
    assumption: "Mode C may culminate in a pull-request review when fixes change the working branch; the constitutional pull-request rule applies in Mode C exactly as in Modes A and B"
    confidence: medium
    basis: "Build plan states 'Both use checkpoint protocol'; pull-request review is the terminal gate of any flow that pushes commits — not stated explicitly for Mode C but follows from constitutional rule in API-nats-approval-protocol.md §8"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "A Mode B build operates on exactly one feature and culminates in exactly one pull-request review pause"
    assumption: "Mode B operates on exactly one feature per build; multi-feature catalogues belong to Mode A only (no /system-design step in Mode B)"
    confidence: high
    basis: "Mode B starts at /feature-spec — there is no /system-design stage to produce a multi-feature catalogue; multi-feature scope is Mode A's role per FEAT-FORGE-007"
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "A Mode C task-review that returns no fix tasks completes the build without dispatching any task-work"
    assumption: "If /task-review returns an empty set of fix tasks, the Mode C build completes without dispatching /task-work and records the clean-review outcome"
    confidence: high
    basis: "Direct consequence of 'review-fix cycle' semantics in build plan FEAT-FORGE-008 row — no fixes to apply means no work to dispatch"
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "A failed Mode C task-work dispatch records the failure against its fix task and blocks pull-request creation when no fix task has succeeded"
    assumption: "A failed /task-work for a fix task halts that fix task's progression but does not implicitly cancel later fix tasks; the build's continuation is decided at the gate"
    confidence: medium
    basis: "Policy inference — the build plan does not specify cascade semantics for per-fix-task failure; mirrors Mode A's per-feature isolation pattern in FEAT-FORGE-007"
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "After a crash during an asynchronous Mode B autobuild or Mode C task-work, durable history is the authoritative status source"
    assumption: "On crash recovery during Mode B autobuild or Mode C task-work, durable history is authoritative and any live async-subagent state channel is advisory (inherited from FEAT-FORGE-007)"
    confidence: high
    basis: "Inherited from FEAT-FORGE-007 ASSUM-004; DM-build-lifecycle.md §2.1 INTERRUPTED → PREPARING retry-from-scratch; ADR-ARCH-021"
    human_response: "confirmed"

  - id: "ASSUM-010"
    scenario: "A follow-up Mode C task-review that returns no further fix tasks terminates the review-fix cycle"
    assumption: "Mode C terminates the review-fix cycle when a follow-up /task-review returns no further fix tasks; iteration count is bounded by reviewer judgement, not a fixed numeric ceiling"
    confidence: medium
    basis: "Policy inference — the build plan does not specify a numeric iteration cap; the natural termination signal is a clean follow-up review"
    human_response: "confirmed"

  - id: "ASSUM-011"
    scenario: "Mode B and Mode C pull-request review enforcement holds even if a misconfigured prompt would have allowed auto-approve"
    assumption: "Constitutional pull-request enforcement is mode-agnostic — the executor-side hardcoded branch fires for any tool resembling pull-request creation or review regardless of mode"
    confidence: high
    basis: "API-nats-approval-protocol.md §8 — executor-side branch is unconditional ('any tool_name in {review_pr, create_pr_after_review} → MANDATORY_HUMAN_APPROVAL regardless of score or priors')"
    human_response: "confirmed"

  - id: "ASSUM-012"
    scenario: "Calibration priors captured at the start of a Mode B or Mode C build remain the snapshot used by every stage of that build"
    assumption: "Calibration priors are snapshotted at build start and remain stable for the duration of that build (mid-run history changes apply only to subsequent builds)"
    confidence: medium
    basis: "Inherited from FEAT-FORGE-007 ASSUM-007"
    human_response: "confirmed"

  - id: "ASSUM-013"
    scenario: "A Mode B build refuses to dispatch /system-arch or /system-design even when a context manifest references those stages"
    assumption: "The supervisor's mode-aware planning refuses to dispatch /system-arch or /system-design in Mode B even if a context manifest references those stages"
    confidence: medium
    basis: "Security inference from the 'Mode B starts at /feature-spec' boundary; not explicitly stated as a planning-layer guard but required to honour the mode boundary"
    human_response: "confirmed"

  - id: "ASSUM-014"
    scenario: "A Mode B build does not record a degraded-specialist rationale because no specialist dispatch is attempted"
    assumption: "Mode B does not dispatch to product-owner or architect specialists, so specialist-availability outages do not gate or pause a Mode B build"
    confidence: high
    basis: "Direct consequence of ASSUM-001"
    human_response: "confirmed"

  - id: "ASSUM-015"
    scenario: "A Mode B build whose autobuild produces no diff does not attempt pull-request creation"
    assumption: "When a Mode B autobuild succeeds without producing a diff against the working branch, no pull-request creation is attempted and the build terminates with a no-op outcome rather than pausing at pull-request review"
    confidence: medium
    basis: "Natural inference — the gh CLI cannot create an empty PR; build plan does not specify the exact terminal label for this case but the constitutional gate has nothing to fire on"
    human_response: "confirmed"

  - id: "ASSUM-016"
    scenario: "A follow-up feature added after a prior Mode A build is treated as a fresh Mode B build with its own identifiers"
    assumption: "Each queued build is its own lifecycle; a follow-up feature added after a Mode A run starts a fresh Mode B build with its own build identifier and its own correlation identifier"
    confidence: high
    basis: "DM-build-lifecycle.md §1 (Build entity) + §5 invariants ('build_id is unique across all time'; '(feature_id, correlation_id) unique')"
    human_response: "confirmed"

  - id: "ASSUM-017"
    scenario: "A Mode C build that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt"
    assumption: "A Mode C run that produces no commits ends in a clean-review terminal outcome with no pull-request creation attempt and no PR URL"
    confidence: medium
    basis: "Symmetric to ASSUM-015; no commits means nothing to push to a PR"
    human_response: "confirmed"
Write mode-b-feature-and-mode-c-review-fix_summary.md
138 lines
# Feature Spec Summary: Mode B Feature & Mode C Review-Fix

**Feature ID**: FEAT-FORGE-008
**Stack**: python
**Generated**: 2026-04-27T00:00:00Z
**Scenarios**: 56 total (6 smoke, 5 regression)
**Assumptions**: 17 total (10 high / 7 medium / 0 low confidence)
**Review required**: No — all assumptions traceable to supplied context files and inherited from FEAT-FORGE-007

## Scope

Specifies Forge's two non-greenfield orchestration modes built on the FEAT-FORGE-001..007
substrate. **Mode B (Feature)** drives a single new feature on an existing project
through `/feature-spec → /feature-plan → autobuild → pull-request review`, deliberately
skipping the product-owner / architect / `/system-arch` / `/system-design` upstream
stages that Mode A performs — the project's existing architecture and design baseline
are taken as given. **Mode C (Review-Fix)** runs the `/task-review → /task-work` cycle
on an existing subject, dispatching one `/task-work` per fix task identified by the
review, optionally culminating in a pull-request review when the cycle has pushed
commits and otherwise terminating with a clean-review outcome. Both modes inherit the
async-subagent dispatch pattern, the LangGraph interrupt round-trip with build-keyed
approval channel, durable-history-authoritative crash recovery (retry-from-scratch),
CLI steering (cancel → synthetic reject; skip honoured on non-constitutional stages
and refused on pull-request review), idempotent first-write-wins on duplicate
responses, correlation-identifier threading from queue to terminal, calibration-priors
snapshot stability, and the constitutional belt-and-braces rule that pins
pull-request review to mandatory human approval at both prompt and executor layers.
Behaviour is described in domain terms; the AsyncSubAgent state channel, NATS
approval channel, SQLite history, and worktree allowlist surface only as capability
observations.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 9 |
| Boundary conditions (@boundary) | 6 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 11 |
| Smoke (@smoke) | 6 |
| Regression (@regression) | 5 |
| Security (@security) | 4 |
| Concurrency (@concurrency) | 4 |
| Data integrity (@data-integrity) | 7 |
| Integration (@integration) | 6 |
| Mode B scope (@mode-b) | 39 |
| Mode C scope (@mode-c) | 28 |

Note: many scenarios carry multiple tags (e.g. @mode-b + @mode-c when behaviour is
shared, @boundary + @negative for just-outside boundaries, @edge-case + @concurrency
for cross-cutting expansion). Group totals and tag totals do not sum to 56.

## Group Layout

| Group | Theme | Scenarios |
|-------|-------|-----------|
| A | Key Examples — Mode B full chain to PR-awaiting-review, forward propagation, async-subagent dispatch, constitutional PR-review pin, flag/resume cycle, session-outcome chain; Mode C full review-fix cycle, fix-task forward propagation, optional PR-review pin | 9 |
| B | Boundary Conditions — Mode B single-feature, Mode B stage-ordering invariant outline, Mode B empty-spec rejection, Mode C empty-fix-task short-circuit, Mode C fix-task count outline (1, 3, 5), Mode C stage-ordering invariant outline | 6 |
| C | Negative Cases — Mode B feature-spec hard-stop, Mode B failed feature-spec halts inner loop, max-score does not auto-approve PR review, skip refused at PR review, Mode B autobuild internal hard-stop blocks PR creation, reject decision is terminal, Mode C task-review hard-stop, Mode C failed task-work isolation | 8 |
| D | Edge Cases — Mode B crash-recovery outline, Mode C crash-recovery outline, durable-history authority on async crash, cancel during pause, cancel during async, skip on non-constitutional stage, approval routed by build identifier, duplicate response idempotent, Mode C cycle terminates on follow-up clean review | 9 |
| E | Security — Mode B/C constitutional belt-and-braces holds against misconfigured prompt, subprocess override claim ignored at gating, Mode B/C subprocess worktree-allowlist confinement | 3 |
| F | Concurrency — two concurrent Mode B builds with isolated channels and task IDs, Mode B and Mode C concurrent with isolated chains, supervisor dispatches second build's stage during first build's async stage | 3 |
| G | Data Integrity — Mode B canonical stage-history ordering (no PO/architect/arch/design entries), Mode C canonical stage-history ordering (review precedes work), per-fix-task artefact attribution, notification publish failure does not regress approval | 4 |
| H | Integration Boundaries — minimal Mode B E2E smoke, minimal Mode C E2E smoke, internal async-stage pause observable via supervisor, correlation threading queue→terminal | 4 |
| I | Expansion — first-wins on simultaneous approvals, calibration-priors snapshot stability, memory-seeding failure does not regress approval | 3 |
| J | Security expansion — Mode B refuses to dispatch /system-arch or /system-design even if manifest references them | 1 |
| K | Concurrency expansion — three concurrent builds (Mode A + Mode B + Mode C) with isolated channels and stage chains | 1 |
| L | Data Integrity expansion — Mode B records no degraded-specialist rationale (positive assertion of no-PO/no-architect axiom), Mode C fix-task lineage from review to work | 2 |
| M | Integration Boundaries expansion — Mode B no-diff autobuild does not attempt PR creation | 1 |
| N | Mode-interaction expansion — follow-up feature after Mode A is fresh Mode B build, Mode C with no commits ends in clean-review terminal | 2 |

## Deferred Items

None.

## Assumptions Summary

| ID | Confidence | Subject | Response |
|----|------------|---------|----------|
| ASSUM-001 | high | Mode B chain composition (skip PO/architect/arch/design) | confirmed |
| ASSUM-002 | high | Mode B autobuild reuses AsyncSubAgent pattern | confirmed |
| ASSUM-003 | high | Constitutional PR rule applies in every mode | confirmed |
| ASSUM-004 | high | Mode C chain composition (/task-review → /task-work × N) | confirmed |
| ASSUM-005 | medium | Mode C culminates in PR review when changes are pushed | confirmed |
| ASSUM-006 | high | Mode B is single-feature per build | confirmed |
| ASSUM-007 | high | Empty /task-review → no /task-work, clean-review terminal | confirmed |
| ASSUM-008 | medium | Failed /task-work isolated to its fix task | confirmed |
| ASSUM-009 | high | Crash-recovery: durable history authoritative | confirmed |
| ASSUM-010 | medium | Mode C terminates on follow-up clean review (no numeric cap) | confirmed |
| ASSUM-011 | high | Constitutional PR enforcement is mode-agnostic | confirmed |
| ASSUM-012 | medium | Calibration-priors snapshot stability for build duration | confirmed |
| ASSUM-013 | medium | Mode-aware planning refuses upstream Mode A stages in Mode B | confirmed |
| ASSUM-014 | high | Mode B does not dispatch to PO/architect specialists | confirmed |
| ASSUM-015 | medium | Mode B no-diff autobuild → no PR attempt, no-op terminal | confirmed |
| ASSUM-016 | high | Each queued build is its own lifecycle (fresh build IDs) | confirmed |
| ASSUM-017 | medium | Mode C with no commits → clean-review terminal, no PR | confirmed |

## Upstream Dependencies

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration. The build queue,
  state-machine transitions, durable history, crash recovery (retry-from-scratch),
  and CLI steering surface are referenced as the substrate every Mode B and Mode C
  stage rides on. FEAT-FORGE-008 adds no new transitions; it composes them.
- **FEAT-FORGE-002** — NATS Fleet Integration. The pipeline-event publishing
  (correlation threading) and approval channel are inherited; FEAT-FORGE-008
  specifies how the supervisor sequences Mode B and Mode C dispatches over them.
  Mode B and Mode C do not exercise the live discovery cache for specialists
  because they do not dispatch to specialist agents.
- **FEAT-FORGE-004** — Confidence-Gated Checkpoint Protocol. The auto-approve /
  flag-for-review / hard-stop / mandatory-human-approval gate modes, the
  build-keyed approval round-trip, idempotent first-wins, max-wait refresh, CLI
  cancel/skip mapping, and the constitutional PR-review rule are inherited;
  FEAT-FORGE-008 specifies how those gates compose across the two non-greenfield
  chains.
- **FEAT-FORGE-005** — GuardKit Command Invocation Engine. The subprocess contract
  for /feature-spec, /feature-plan, autobuild, /task-review, and /task-work —
  including context-flag construction and worktree confinement — is inherited;
  FEAT-FORGE-008 specifies the order and inputs for Mode B and Mode C.
- **FEAT-FORGE-006** — Infrastructure Coordination. Long-term-memory seeding,
  priors retrieval at build start, test verification, and git/gh PR creation are
  inherited; FEAT-FORGE-008 specifies how their failure modes interact with the
  build's authoritative recorded progress in Mode B and Mode C.
- **FEAT-FORGE-007** — Mode A Greenfield End-to-End. The capstone composition
  patterns, async-subagent dispatch shape, constitutional belt-and-braces, and
  per-feature artefact attribution conventions are inherited; FEAT-FORGE-008 adapts
  these to the shorter Mode B chain (no upstream delegation/architecture stages)
  and the cyclic Mode C chain (review → work iteration with optional PR review).

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Mode B Feature & Mode C Review-Fix" \
      --context features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md

`/feature-plan` Step 11 will link `@task:<TASK-ID>` tags back into the
`.feature` file after tasks are created.
Bash Verify outputs and count scenarios
IN
ls -la features/mode-b-feature-and-mode-c-review-fix/ && echo "---" && grep -c "^  Scenario" features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature

OUT
total 72
drwxrwxr-x  2 richardwoollcott richardwoollcott  4096 Apr 27 15:16 .
drwxrwxr-x 10 richardwoollcott richardwoollcott  4096 Apr 27 15:11 ..
-rw-rw-r--  1 richardwoollcott richardwoollcott  9204 Apr 27 15:15 mode-b-feature-and-mode-c-review-fix_assumptions.yaml
-rw-rw-r--  1 richardwoollcott richardwoollcott 39098 Apr 27 15:14 mode-b-feature-and-mode-c-review-fix.feature
-rw-rw-r--  1 richardwoollcott richardwoollcott  9770 Apr 27 15:16 mode-b-feature-and-mode-c-review-fix_summary.md
---
56
All three files written. 56 scenarios in the .feature file, 17 assumptions in the YAML manifest.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Mode B Feature & Mode C Review-Fix
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
  features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature
  features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_assumptions.yaml
  features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md

Scenarios: 56 total
  @key-example: 9    @boundary: 6
  @negative: 8       @edge-case: 11
  @smoke: 6          @regression: 5
  @security: 4       @concurrency: 4
  @data-integrity: 7 @integration: 6
  @mode-b: 39        @mode-c: 28

Assumptions: 17 total
  high: 10  (auto-proceed)
  medium: 7 (Coach review recommended; all traceable to inherited FEAT-FORGE-007 patterns or natural inferences from the build plan)
  low: 0    (no human re-verification required)

Deferred: 0 scenario groups

Next steps:
  Review: features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature
  Update build plan: replace `<feat-forge-008-slug>` placeholder with
    `mode-b-feature-and-mode-c-review-fix` in docs/research/ideas/forge-build-plan.md
  Pass to feature-plan:
    /feature-plan "Mode B Feature & Mode C Review-Fix" \
      --context features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Want me to update the <feat-forge-008-slug> placeholder in docs/research/ideas/forge-build-plan.md to the resolved slug mode-b-feature-and-mode-c-review-fix while it's fresh?

yes
Bash Find slug placeholders to replace
IN
grep -n "feat-forge-008-slug" docs/research/ideas/forge-build-plan.md

OUT
312:- ◻ **FEAT-FORGE-008** — Mode B Feature & Mode C Review-Fix. Not yet specced. **This is the immediate next action** (see Step 3 command block below — `<feat-forge-008-slug>` placeholders resolve once the spec runs).
476:  --context forge/features/<feat-forge-008-slug>/<feat-forge-008-slug>_summary.md
Read forge-build-plan.md (lines 306-325)
Read forge-build-plan.md (lines 469-488)
Edit forge-build-plan.md
Added 4 lines
Edit forge-build-plan.md
Removed 3 lines
Edit forge-build-plan.md
Removed 1 line
Bash Verify all placeholders are gone and check status lines
IN
grep -n "feat-forge-008-slug\|FEAT-FORGE-008" docs/research/ideas/forge-build-plan.md | head -20

OUT
3:## Status: `/system-arch` ✅ · `/system-design` ✅ · `/feature-spec` 🟡 **7 / 8 complete** (FEAT-FORGE-001..007 ✅; 008 pending) · `/feature-plan` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · `autobuild` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · **Next: `/feature-spec FEAT-FORGE-008`**
15:| 3 | `/feature-spec × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | various | FEAT-FORGE-001..007 ✅ (see Step 3 for per-feature details); FEAT-FORGE-008 ◻ |
133:| FEAT-FORGE-008 | Mode B Feature & Mode C Review-Fix | 007 | 2-3 days | Mode B: add feature to existing project (skip PO/architect delegation, start from /feature-spec). Mode C: review and fix issues (/task-review → /task-work cycle). Both use checkpoint protocol. | *(optional modes — not in anchor §10 Phase 4)* |
312:- ✅ **FEAT-FORGE-008** — Mode B Feature & Mode C Review-Fix (2026-04-27)
399:# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix  ◻ NEXT
405:guardkit feature-spec FEAT-FORGE-008 \
475:# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix (depends on 007)  ◻ READY (slug resolved 2026-04-27)
476:guardkit feature-plan FEAT-FORGE-008 \
523:guardkit autobuild FEAT-FORGE-008   # ◻ BLOCKED on /feature-spec + /feature-plan FEAT-FORGE-008
868:   - Replace `<FEAT-FORGE-007 feature spec>` in FEAT-FORGE-008 with actual path
915:*Updated: 25 April 2026 — Steps 3–5 in flight: 7/8 specs, 6/8 plans, 6/8 autobuilds. FEAT-FORGE-001 absorbed into 002–007. Next: `/feature-spec FEAT-FORGE-008`.*
916:*Updated: 25 April 2026 (later) — FEAT-FORGE-001 gap closed: re-planned against `forge-001-gap-context.md` (13 tasks), autobuilt in one pass (commit `ea7e60b`, 13/13 clean, 0 ceiling hits, 1h 44m). 7/8 specs, 7/8 plans, 7/8 autobuilds. Next: `/feature-spec FEAT-FORGE-008`.*
917:*Status: Mode B/C (FEAT-FORGE-008) is the only outstanding feature — spec → plan → autobuild → Step 6 validation gates → Step 7 FinProxy run.*
Read forge-build-plan.md (lines 271-320)
Edit forge-build-plan.md
Added 1 line
Bash Confirm no stale placeholders remain
IN
grep -n "feat-forge-008-slug" docs/research/ideas/forge-build-plan.md

OUT
(Bash completed with no output)
All <feat-forge-008-slug> placeholders gone. Edits to docs/research/ideas/forge-build-plan.md:

Step 3 §"Pending" — moved FEAT-FORGE-008 from ◻ placeholder into the completed list with full scenario/assumption rollup matching the FEAT-FORGE-001..007 entry style; added explicit (none — all 8 feature specs complete) so the Pending header doesn't read as empty.
Step 4 — replaced the placeholder feature-plan command with the resolved-slug version and flipped the marker from ◻ BLOCKED to ◻ READY.
Slug index — appended mode-b-feature-and-mode-c-review-fix (008) and removed the "resolves when its spec runs" caveat.
The top-of-file Status line (line 3) and the Step 3 progress row (line 15) still read 7/8 complete for /feature-spec — left them alone since rolling those counters is a related but separate edit. Want me to bump those to 8/8 (and likewise update lines 399, 915–917) in one follow-up?

yes
Read forge-build-plan.md (lines 2-21)
Read forge-build-plan.md (lines 396-410)
Read forge-build-plan.md (lines 909-923)
Edit forge-build-plan.md
Modified
Edit forge-build-plan.md
Modified
Edit forge-build-plan.md
Added 1 line
Edit forge-build-plan.md
Added 1 line
Bash Verify no stale 7/8-spec or 008-pending markers remain on spec rollup
IN
grep -n "7 / 8\|7/8\|FEAT-FORGE-008.*◻\|008 pending\|008 ◻" docs/research/ideas/forge-build-plan.md | head -30

OUT
3:## Status: `/system-arch` ✅ · `/system-design` ✅ · `/feature-spec` ✅ **8 / 8 complete** (FEAT-FORGE-001..008 ✅) · `/feature-plan` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · `autobuild` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · **Next: `/feature-plan FEAT-FORGE-008`**
16:| 4 | `/feature-plan × 8` | 🟡 in progress (7 / 8) | 2026-04-24..25 | `6a29ed3`, `065b73d`, FEAT-FORGE-001 plan | FEAT-FORGE-001..007 ✅ — task breakdowns under `tasks/backlog/<slug>/`. 001 was re-planned post-001-gap-context with `forge-001-gap-context.md` to scope to the unbuilt slice (CLI + lifecycle persistence + state machine + recovery — 13 tasks). 008 ◻ |
17:| 5 | `autobuild × 8` (Waves 1–6) | 🟡 in progress (7 / 8) | 2026-04-25..26 | `91f4de5`, `f63bcf5`, `9774351`, `042b83e`, `0361c21`, `6e5c577`, `ea7e60b` | FEAT-FORGE-002 (`91f4de5`), 003 (`f63bcf5`), 004 (`9774351`), 005 (`042b83e`), 006 (=`FEAT-8D10`, `0361c21`), 007 (=`FEAT-CBDE`, `6e5c577`), 001 (`ea7e60b`, 13/13 tasks across 5 waves, 0 ceiling hits) ✅. 008 ◻ |
260:### Step 3: /feature-spec × 8 — 🟡 IN PROGRESS (7 / 8)
425:### Step 4: /feature-plan × 8 — 🟡 IN PROGRESS (7 / 8)
477:# FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix (depends on 007)  ◻ READY (slug resolved 2026-04-27)
494:### Step 5: Build (autobuild × 8) — 🟡 IN PROGRESS (7 / 8)
525:guardkit autobuild FEAT-FORGE-008   # ◻ BLOCKED on /feature-spec + /feature-plan FEAT-FORGE-008
917:*Updated: 25 April 2026 — Steps 3–5 in flight: 7/8 specs, 6/8 plans, 6/8 autobuilds. FEAT-FORGE-001 absorbed into 002–007. Next: `/feature-spec FEAT-FORGE-008`.*
918:*Updated: 25 April 2026 (later) — FEAT-FORGE-001 gap closed: re-planned against `forge-001-gap-context.md` (13 tasks), autobuilt in one pass (commit `ea7e60b`, 13/13 clean, 0 ceiling hits, 1h 44m). 7/8 specs, 7/8 plans, 7/8 autobuilds. Next: `/feature-spec FEAT-FORGE-008`.*
919:*Updated: 27 April 2026 — `/feature-spec FEAT-FORGE-008` complete (Mode B Feature & Mode C Review-Fix; 56 scenarios, 17 assumptions, 0 low-confidence). 8/8 specs, 7/8 plans, 7/8 autobuilds. Next: `/feature-plan FEAT-FORGE-008`.*
Read forge-build-plan.md (lines 259-266)
Edit forge-build-plan.md
Modified
Bash Final check for stale markers
IN
grep -n "feat-forge-008-slug\|/feature-spec.*7 / 8\|/feature-spec.*7/8 specs" docs/research/ideas/forge-build-plan.md | head -10

OUT
3:## Status: `/system-arch` ✅ · `/system-design` ✅ · `/feature-spec` ✅ **8 / 8 complete** (FEAT-FORGE-001..008 ✅) · `/feature-plan` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · `autobuild` 🟡 **7 / 8 complete** (001..007 ✅; 008 pending) · **Next: `/feature-plan FEAT-FORGE-008`**
All /feature-spec rollup counters are now 8/8 ✅. The /feature-plan and autobuild rollups still read 7/8 correctly since FEAT-FORGE-008's plan and autobuild have not yet run. Historical "Updated:" dated entries on lines 917–918 left untouched as they record the state at that date.

Summary of edits to docs/research/ideas/forge-build-plan.md:

Line 3 — top status: /feature-spec flipped to ✅ 8/8 complete; Next advanced to /feature-plan FEAT-FORGE-008
Line 15 — Step 3 progress row: ✅ complete (8/8) with date range extended to 2026-04-24..27
Line 260 — Step 3 section header: ✅ COMPLETE (8/8, 2026-04-27)
Line 400 — feature-spec command block marker for FEAT-FORGE-008: ◻ NEXT → ✅ COMPLETE (2026-04-27) with output path
Line 919 — appended fresh Updated: 27 April 2026 line with the 56-scenario / 17-assumption rollup
Line 920 — bottom status sentence: now scopes the only outstanding work to plan + autobuild
command-history.md
is this the full command to use next? /feature-plan "Mode B Feature & Mode C Review-Fix" \
      --context features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md
Almost — two refinements vs. the build-plan canonical version at docs/research/ideas/forge-build-plan.md:477:


guardkit feature-plan FEAT-FORGE-008 \
  --context forge/features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md
Differences:

FEAT-FORGE-008, not "Mode B Feature & Mode C Review-Fix". Established convention across FEAT-FORGE-001..007 plans. The _summary.md template suggests the name form, but every actual /feature-plan invocation in the build plan uses the FEAT-ID — and your prior /feature-spec FEAT-FORGE-008 invocation used the ID too.
Path prefix forge/... to match the previous /feature-spec invocation in this session, which used forge/features/.... If you're running from inside the forge repo (cwd /home/richardwoollcott/Projects/appmilla_github/forge), drop the forge/ prefix — but match whichever cwd your guardkit invocation expects. The skill documentation example used features/...; your last command used forge/features/....
Per the matching FEAT-FORGE-007 invocation, summary-only context is enough — /feature-plan Step 11 will read the .feature file directly to do the BDD-task linking. No extra --context flags needed.