# TASK-REV-IC8B: Decision-Mode Review Report
## FEAT-FORGE-006 — Infrastructure Coordination

**Mode:** decision
**Depth:** standard
**Reviewer:** software-architect agent
**Completed:** 2026-04-25
**Score:** 78/100 (recommended for implementation; 3 open assumptions resolved with clarifications)

---

## 1. Executive Summary

FEAT-FORGE-006 specifies five tightly integrated sub-systems: post-stage seeding of five entity types into `forge_pipeline_history`, incremental Q&A ingestion into `forge_calibration_history`, build-start priors retrieval injected as reasoning-model narrative, test verification inside an ephemeral worktree, and git/`gh` operations driven through the DeepAgents `execute` tool. The feature has 43 BDD scenarios across a mature spec with no deferred items. The recommended approach is async fire-and-forget memory writes (off the critical path), on-build-start file-hash scan for Q&A ingestion, parallel sub-queries by group for priors retrieval, subprocess via the `execute` tool for test and git operations, and entity-id-level deduplication for split-brain safety. Complexity is 8/10. The dominant risk is the Graphiti write path under Tailscale/FalkorDB latency causing silent data loss if the tolerance/reconciliation loop is not carefully implemented.

---

## 2. Scope Assessment

**In-scope for FEAT-FORGE-006:**
- Writing `GateDecision`, `CapabilityResolution`, `OverrideEvent`, `CalibrationAdjustment`, and `SessionOutcome` to `forge_pipeline_history`.
- Ingesting operator Q&A history files into `forge_calibration_history` with content-hash incremental refresh.
- Priors retrieval at build start; injection into the reasoning model as prose.
- Test verification via the configured test command in the ephemeral worktree.
- Git branch, commit, push, and PR creation via the `execute` tool.
- Reconcile backfill of entries that failed to reach long-term memory (`@edge-case reconcile-backfill`).

**Strictly upstream (do not re-implement):**
- FEAT-FORGE-001 owns the SQLite `stage_log` schema, the state machine transitions, and the durable build-history store. FEAT-FORGE-006 reads from that store as its authoritative source for reconciliation; it must not add columns, change schema, or alter transition logic.
- FEAT-FORGE-002 owns the NATS KV pipeline-state bucket, discovery cache, and CapabilityResolution selection logic. FEAT-FORGE-006 records the resolved capability after selection is complete; it must not touch the resolution algorithm.
- The NATS approval round-trip that flips the `approved` flag on a `CalibrationAdjustment` (`@integration approved-adjustment-visibility`) is FEAT-FORGE-002 territory for the transport layer. FEAT-FORGE-006 only reads the resulting state.

**Scope creep risk:** The reconcile-backfill path (`@edge-case reconcile-backfill`) requires querying both the SQLite store and Graphiti to diff missing entries. This risks pulling in FEAT-FORGE-001 SQLite schema details. The implementation must access the SQLite store read-only through a repository abstraction, not by duplicating schema knowledge.

**Async Graphiti write overlap:** The knowledge graph context flags a planned "Async Graphiti write" feature in the `project_decisions` group. If that feature lands as a shared library before FEAT-FORGE-006 is implemented, the memory-write path in §3.1 should delegate to it rather than re-implement async queuing. Verify timing with the project roadmap before implementation starts.

---

## 3. Technical Options Analysis

### 3.1 Memory Write Path

**Option A — Synchronous on-stage write.** Every stage records entities to Graphiti inline before returning. Simple. Directly contradicts the hard lesson from knowledge graph context: a post-acceptance Graphiti write failure caused wasted LLM token spend because correct work was discarded. If Graphiti is unreachable over Tailscale (FalkorDB on Synology), this blocks the build.

**Option B — Async fire-and-forget.** Write is dispatched as a non-awaited coroutine or pushed to `asyncio.ensure_future`. The build continues immediately. Failures are caught in the fire-and-forget task, logged, and the authoritative SQLite entry is already committed (write-ordering invariant satisfied by §3.1's sequencing rule). Reconcile-backfill at next build start covers the gap. This is the pattern `_write_to_graphiti()` in `run_greenfield()` uses for the success path.

**Option C — Write-ahead queue with reconciliation.** A persistent queue (e.g. SQLite table) buffers pending writes; a background worker drains it. Stronger durability than B, but adds a separate storage layer and complicates the codebase significantly.

**Recommendation: Option B.** Fire-and-forget satisfies the `@negative memory-write-failure-tolerated` scenario and the `@edge-case write-ordering` scenario (SQLite commits first, Graphiti write is enqueued second). Option C's durability advantage is already provided by the existing SQLite durable store acting as the reconcile source; a second queue is redundant. The reconcile-backfill at build start covers the gap with zero added infrastructure.

### 3.2 Q&A History Ingestion

**Option A — File-watcher (inotify/watchdog).** Continuous, low-latency. Adds a background thread/task that must survive process signals. Overkill for a sole-operator tool where history files change infrequently.

**Option B — On-build-start scan.** At each build start, scan all configured history files, compare content hashes against the stored snapshot, re-parse changed files only. Deterministic, no background state. Directly covers `@boundary boundary-history-file-hash-change` and `@negative negative-re-ingestion-idempotency`. Also aligned with `@edge-case post-build-ingestion-refresh` (run again after each completed build).

**Option C — Scheduled job (cron-style).** Periodic scan on a timer. Adds clock dependency and doesn't align with build lifecycle events.

**Recommendation: Option B.** On-build-start scan triggered at boot and after each completed build. This matches both the boot scenario (`@key-example history-ingestion`) and the post-build scenario (`@edge-case post-build-ingestion-refresh`). Hash comparison implements `@boundary boundary-history-file-hash-change`. No background threads needed.

### 3.3 Priors Retrieval at Build Start

**Option A — Single bulk query.** One Graphiti search across all groups with a broad query string. Cheap in round-trips. Results are hard to sort into distinct prior categories (session outcomes vs override patterns vs calibration adjustments vs Q&A priors).

**Option B — Parallel sub-queries by group_id.** Four concurrent queries: `forge_pipeline_history` for session outcomes, `forge_pipeline_history` for override behaviour, `forge_pipeline_history` for calibration adjustments, `forge_calibration_history` for Q&A priors. Results are structured and addressable. Directly models the four categories named in `@key-example priors-retrieval-runtime` and `@key-example priors-retrieval-qa`. `asyncio.gather()` keeps wall-clock cost to one round-trip's latency.

**Option C — Lazy on-demand.** Retrieve priors only when the reasoning model requests them via a tool call. Reduces startup cost but adds latency mid-build and complicates the narrative injection contract.

**Recommendation: Option B.** Parallel sub-queries via `asyncio.gather()`. This satisfies both `@key-example key-priors-retrieval-runtime` and `@key-example key-priors-retrieval-qa` without the ambiguity of a single bulk query. The four-category structure maps cleanly to the four injected prose sections. Empty results satisfy `@edge-case empty-priors-representation` naturally.

### 3.4 Test Verification in Ephemeral Worktree

**Option A — DeepAgents `execute` tool with `pytest` in the binary allowlist.** Subprocess is spawned via the `execute_command` tool with the worktree path as the working directory. Output is captured and structured. Satisfies the constitutional subprocess-permissions constraint. The Implementer already calls `verify_output` after every `execute_command`.

**Option B — Direct Python pytest API (`pytest.main()`).** Avoids subprocess; runs in-process. However, it shares the current interpreter's state, potentially polluting it with test-suite imports. More critically, it bypasses the constitutional execute-tool path, which AGENTS.md requires for side-effecting work in the worktree.

**Option C — Containerised test runner.** Strongest isolation. Requires Docker available in the worktree environment, far beyond what the spec mandates, and adds significant complexity.

**Recommendation: Option A.** The `execute` tool with `pytest` allowlisted. This is the only option compatible with the AGENTS.md constitutional constraints and the `@negative negative-disallowed-binary-refused` scenario. The result dictionary shape (pass/fail counts, failing identifiers, captured output tail) satisfies ASSUM-004.

### 3.5 Git / gh Operations

**Option A — DeepAgents `execute` tool with explicit allowlist.** `git` and `gh` binaries are added to the subprocess-permissions allowlist. Working directory is confined to the per-build worktree. Credentials come from environment variables only. This is mandated by `@security security-working-directory-allowlist` and `@security security-env-only-credentials`.

**Option B — Shell wrapper module.** A Python module assembles commands and calls `subprocess.run()` directly. Bypasses the constitutional `execute` tool layer; the subprocess invocation is no longer monitored by the permissions check.

**Option C — PyGithub or similar library.** Can handle PR creation but not `git` operations (clone, branch, commit, push). A hybrid approach (library for GitHub API, subprocess for git) splits the allowlist management and adds a new dependency that requires team evaluation before adoption.

**Recommendation: Option A.** The `execute` tool is the sole permitted path. Allowlisted binaries: `git`, `gh`, `pytest`. Working-directory constraint: the per-build worktree directory (under the allowlisted builds directory). Environment-only credentials enforced at the credential-read layer. This satisfies `@security security-working-directory-allowlist`, `@security security-env-only-credentials`, `@negative negative-disallowed-binary-refused`, and the end-to-end `@integration integration-end-to-end-build`.

---

## 4. Resolution of Open Assumptions

**ASSUM-006 — Credential redaction in rationale fields.**
Scenario: `@edge-case @security secrets-appearing-in-rationale-text-are-redacted`.
Position: **Confirm with modification.** A pattern-based filter is correct as the mechanism, but the assumption understates implementation risk. The recommended position is: implement a dedicated `redact_credentials(text: str) -> str` function applied to every `rationale` field before any entity is constructed for Graphiti write. The regex set should cover at minimum: bearer tokens (`Bearer [A-Za-z0-9._-]{20,}`), GitHub tokens (`ghp_/ghs_/github_pat_` prefixes), and generic high-entropy strings of 40+ hex characters. This function must be unit-tested in isolation. The assumption's "pattern-based filter" framing is accepted; the gap is that no concrete pattern set was specified. Implementation must define and document the pattern set rather than deferring it.

**ASSUM-007 — Split-brain dedupe for mirror writes.**
Scenario: `@edge-case @concurrency split-brain-mirror-dedupe`.
Position: **Confirm, with clarification on GateDecision.** For `CalibrationEvent`, the deterministic `entity_id` pattern means Graphiti's upsert semantics handle deduplication naturally — a second write with the same `entity_id` is a no-op at the storage level. For `GateDecision` (which uses a UUID assigned at creation by FEAT-FORGE-001), the UUID is generated once and stored in SQLite; a second Forge instance reading the same SQLite row gets the same UUID. Therefore, the pre-check is not a "separate" check but a consequence of using the SQLite-assigned UUID as the Graphiti `entity_id`. The implementation must use the SQLite-row UUID as the Graphiti entity identifier, not generate a new UUID at write time. This resolves the assumption cleanly.

**ASSUM-008 — GateDecision link ordering in SessionOutcome.**
Scenario: `@concurrency gate-decisions-in-close-succession`.
Position: **Confirm.** Chronological ordering by `decided_at` ascending is the correct and only sensible interpretation. The implementation must: (a) collect all `GateDecision` entity references at terminal state, (b) sort by their `decided_at` timestamp ascending before constructing the `CONTAINS` edge list, (c) write the edges in that order. The ordering is a client-side responsibility (the write happens in FEAT-FORGE-006 code) because Graphiti/FalkorDB does not guarantee insertion-order edge retrieval. The `@concurrency gate-decisions-in-close-succession` scenario must assert on the order of links in the retrieved `SessionOutcome`, which requires the sort to be explicit in the write path. No ambiguity remains.

---

## 5. Cross-cutting Concerns

**Idempotency.** Three mechanisms cover all five sub-systems: (1) content-hash comparison for Q&A ingestion (`@boundary boundary-history-file-hash-change`, `@negative negative-re-ingestion-idempotency`, `@data-integrity deterministic-qa-identity`); (2) SQLite-UUID-as-Graphiti-entity-id for pipeline history entities (`@edge-case @concurrency split-brain-mirror-dedupe`); (3) terminal-state guard for `SessionOutcome` (`@edge-case @data-integrity session-outcome-retry-idempotency`). The `SessionOutcome` guard must check for an existing entity before writing, not rely on downstream deduplication.

**Security and secrets.** Env-only credentials (`@security security-env-only-credentials`): no credentials read from `forge.yaml`. Rationale redaction (`@edge-case @security secrets-appearing-in-rationale-text-are-redacted`): applied before every entity write. Working-directory allowlist (`@security security-working-directory-allowlist`): validated at `execute` tool layer before process spawn. Binary allowlist (`@negative negative-disallowed-binary-refused`): `git`, `gh`, `pytest` only. Retrieved priors are never passed as subprocess arguments (`@edge-case @security priors-as-argument-refusal`). Filesystem read allowlist (`@edge-case @security filesystem-read-allowlist`) mirrors the subprocess working-directory constraint.

**Concurrency.** Three `@concurrency` scenarios: `gate-decisions-in-close-succession` (ordering of concurrent writes), `split-brain-mirror-dedupe` (two Forge instances), and `recency-horizon-bound` (counting override events). Shared state at risk: the Graphiti write queue (fire-and-forget tasks must not race on the same entity_id), and the SQLite read for reconciliation (read-only, WAL mode from FEAT-FORGE-001 handles concurrent reads safely).

**Data integrity.** Four `@data-integrity` scenarios: `deterministic-qa-identity`, `re-scan-zero-writes`, `supersession-cycle-rejection`, `session-outcome-retry-idempotency`. The supersession-cycle check must walk the `supersedes` chain before proposing any new `CalibrationAdjustment` and reject on cycle detection.

**Failure tolerance.** Graphiti writes are off the critical path (fire-and-forget). The authoritative SQLite entry is always committed first (`@edge-case write-ordering`). Reconcile-backfill at build start detects and heals any gap (`@edge-case reconcile-backfill`). Worktree cleanup failures are logged but do not block terminal state (`@edge-case worktree-cleanup-best-effort`). PR creation failures record the reason on `SessionOutcome` without crashing (`@negative negative-missing-credentials`).

---

## 6. Integration Contracts

**FEAT-FORGE-001 → FEAT-FORGE-006:** The `stage_log` SQLite table is the authoritative source for `GateDecision` and `CapabilityResolution` entities to mirror. Format: SQLite rows with a UUID primary key, `decided_at` timestamp, `stage_name`, `score`, `criterion_breakdown` (JSON column), and `rationale` text. Validation: FEAT-FORGE-006 reads these rows via a read-only repository interface; it must not access the SQLite file directly. Terminal-state signal: the state machine transition callback (owned by FEAT-FORGE-001) invokes the `SessionOutcome` writer once on first terminal transition.

**FEAT-FORGE-002 → FEAT-FORGE-006:** `CapabilityResolution` payloads arrive after the discovery cache selects a specialist; FEAT-FORGE-006 writes the resolved entity to `forge_pipeline_history` before dispatch (`@key-example capability-resolution-recorded-before-dispatch`). `OverrideEvent` payloads arrive when the operator's NATS approval response diverges from the gate recommendation; FEAT-FORGE-006 writes the override entity and links it to the originating `GateDecision`. Format: typed Pydantic models emitted by FEAT-FORGE-002. Validation: the FEAT-FORGE-006 writer asserts that the `gate_decision_id` on an `OverrideEvent` resolves to an existing `GateDecision` entity before writing.

**FEAT-FORGE-006 → reasoning model (priors injection):** A structured prose block with four named sections: `recent_similar_builds`, `recent_override_behaviour`, `approved_calibration_adjustments`, `qa_priors`. Empty sections use an explicit `(none)` marker, not omission (`@edge-case empty-priors-representation`, ASSUM-005). Format: plain prose injected into the system prompt via the `{domain_prompt}` placeholder. Validation: the prose generator has unit tests for each empty-section variant.

**FEAT-FORGE-006 → autobuild Coach (test-verification result):** A dict with keys: `passed` (bool), `pass_count` (int), `fail_count` (int), `failing_tests` (list of str identifiers), `output_tail` (str, last N lines of captured output). Format: Python dict returned from the test-verification function. Validation: the result dict is validated against a typed schema (TypedDict or Pydantic model) before delivery to the reasoning model.

---

## 7. Risk Analysis

**Risk 1 — Graphiti/FalkorDB unavailability over Tailscale (High likelihood, High impact).**
FalkorDB runs on a Synology NAS accessible only via Tailscale. Network partitions are more likely than for a local or cloud-hosted store. If the fire-and-forget write fails silently and the reconcile-backfill is not implemented correctly, data loss is permanent. Mitigation: implement reconcile-backfill as a first-class task unit (not an afterthought), add structured logging for every write failure, and test the failure-tolerance scenario (`@negative memory-write-failure-tolerated`) with an actual unreachable endpoint in CI if possible.

**Risk 2 — Async Graphiti write overlap with planned shared library (Medium likelihood, Medium impact).**
The knowledge graph context confirms an "Async Graphiti write" feature is planned for Phase 1. If it ships concurrently, FEAT-FORGE-006's fire-and-forget implementation may be duplicated or incompatible. Mitigation: confirm the roadmap before implementation starts; if the shared library is imminent, stub the write path behind an interface so it can be swapped without touching business logic.

**Risk 3 — Reconcile-backfill introducing FEAT-FORGE-001 schema coupling (Medium likelihood, High impact).**
The backfill diff requires comparing SQLite stage_log rows with Graphiti entities. If the implementation queries SQLite directly, any FEAT-FORGE-001 schema change breaks FEAT-FORGE-006. Mitigation: access the SQLite store exclusively through the repository interface defined by FEAT-FORGE-001; treat any deviation as an integration contract violation.

**Risk 4 — Supersession-cycle walk on CalibrationAdjustment (Low likelihood, High impact).**
If the supersession-cycle check (`@edge-case @data-integrity supersession-cycle-rejection`) is omitted or incorrectly implemented, an infinite loop in the chain walk could hang the build. Mitigation: implement cycle detection with a visited-set, cap chain depth at a configurable limit (default 10), and unit-test the cycle-rejection scenario explicitly.

**Risk 5 — execute-tool allowlist drift (Low likelihood, Medium impact).**
As new pipeline stages are added, additional binaries may be needed. If they are added to the allowlist without a corresponding review, the security guarantee degrades. Mitigation: the allowlist (`git`, `gh`, `pytest`) must be defined in a single named constant, documented with justification for each entry. Any addition must go through an ADR or an explicit allowlist-change review. The `@negative negative-disallowed-binary-refused` test must enumerate the allowlist to catch silent additions.

---

## 8. Effort and Complexity

| Sub-system | Complexity (1-10) |
|---|---|
| Memory write path (5 entity types, fire-and-forget, reconcile) | 7 |
| Q&A history ingestion (parse, hash, incremental, idempotency) | 5 |
| Priors retrieval (parallel queries, 4 categories, prose injection) | 5 |
| Test verification (execute tool, result structuring) | 3 |
| Git/gh operations (execute tool, allowlist, env credentials) | 4 |
| Cross-cutting (redaction, cycle detection, supersession, ordering) | 6 |

**Aggregate complexity: 8/10.** The feature is technically complex due to the combination of async write coordination, split-brain safety, data integrity invariants, and the constitutional subprocess constraint, not due to any single hard algorithm.

**Estimated implementation effort: 40–60 hours.** The BDD suite provides strong acceptance criteria; implementation effort is bounded by the scenario count rather than design ambiguity.

**Recommended task breakdown count: 10–12 tasks** (see §10).

---

## 9. Extensibility Assessment

**Future entity types.** The five entity types are written through a shared write function that accepts a typed entity and a `group_id`. Adding a sixth entity type requires: a new Pydantic/TypedDict model, a new caller at the relevant pipeline hook, and extension of the fire-and-forget error handler. No structural change to the write path. This is the correct extensibility surface.

**Future Graphiti groups.** `forge_pipeline_history` and `forge_calibration_history` are named constants. A third group (e.g. for a future domain-specific corpus) requires adding a constant and a corresponding priors-retrieval sub-query. The parallel `asyncio.gather()` pattern in §3.3 extends naturally: add a coroutine, add it to the gather call, add a prose section to the injector.

**Future pipeline stages.** Each new stage that produces a `GateDecision` triggers the existing write path automatically if it emits the standard typed result. No changes to FEAT-FORGE-006 infrastructure are needed for additional stages, only for the stage itself (FEAT-FORGE-001 territory).

**Future binaries in the execute allowlist.** The allowlist is a named constant in one module. Additions are one-line changes plus a review step. The `@negative negative-disallowed-binary-refused` test guards against accidental omissions. The design is intentionally conservative: any new binary must be explicitly justified.

**Long-term: the content-hash ingestion pattern is generalisable.** If operator history files expand (new formats, new Q&A sources), the incremental scan is already parameterised by file path and hash. New sources register their paths in the config; the ingestion loop picks them up without structural change.

---

## 10. Recommended Approach

Build the memory write path as a fire-and-forget async layer over a SQLite-first authoritative store (§3.1 Option B), with a reconcile-backfill pass at build start. Q&A ingestion runs on-build-start and post-build via content-hash scan (§3.2 Option B). Priors are retrieved in four parallel group-specific sub-queries assembled into structured prose (§3.3 Option B). Test verification and all git/`gh` operations route through the DeepAgents `execute` tool with an explicit, documented allowlist of `git`, `gh`, and `pytest` only (§3.4 Option A, §3.5 Option A). The three open assumptions are all confirmed with the clarifications in §4. Every Graphiti write is preceded by a `redact_credentials()` pass on all text fields.

**Implementation Breakdown:**

1. **Entity model layer** — Define the five entity TypedDicts/Pydantic models (`GateDecision`, `CapabilityResolution`, `OverrideEvent`, `CalibrationAdjustment`, `SessionOutcome`) and the `redact_credentials()` function with documented regex set. Complexity 4. Dependencies: none. Type: scaffolding.

2. **Fire-and-forget Graphiti write wrapper** — Implement the async write function: entity → redact → Graphiti write, wrapped in try/except with structured failure logging. Implement the fire-and-forget dispatcher. Complexity 5. Dependencies: unit 1. Type: feature.

3. **Write-ordering guard** — Implement the SQLite-first / Graphiti-second sequencing: SQLite commit happens synchronously; fire-and-forget write is dispatched after. Covers `@edge-case write-ordering`. Complexity 3. Dependencies: unit 2. Type: feature.

4. **Reconcile-backfill** — At build start, diff SQLite `stage_log` rows against Graphiti `forge_pipeline_history` entities by entity_id; backfill missing entries. Covers `@edge-case reconcile-backfill`. Complexity 6. Dependencies: units 2, 3. Type: feature.

5. **Q&A ingestion pipeline** — File-hash scan, parser, `CalibrationEvent` writer with deterministic entity_id, partial-parse tolerance with `partial` snapshot flag. Covers `@key-example history-ingestion`, `@boundary boundary-history-file-hash-change`, `@negative negative-re-ingestion-idempotency`, `@data-integrity deterministic-qa-identity`. Complexity 5. Dependencies: unit 2. Type: feature.

6. **Priors retrieval and prose injection** — Four parallel Graphiti sub-queries assembled into a four-section prose block; empty-section handling. Covers `@key-example key-priors-retrieval-runtime`, `@key-example key-priors-retrieval-qa`, `@boundary boundary-expired-adjustments`, `@edge-case empty-priors-representation`. Complexity 5. Dependencies: unit 2. Type: feature.

7. **SessionOutcome writer with ordering and idempotency** — Terminal-state callback collects all `GateDecision` references, sorts by `decided_at` ascending, checks for existing entity before write. Covers `@key-example session-outcome-written`, `@concurrency gate-decisions-in-close-succession`, `@data-integrity session-outcome-retry-idempotency`. Complexity 5. Dependencies: units 1, 3. Type: feature.

8. **Supersession-cycle detection** — Walk the `CalibrationAdjustment` supersession chain with visited-set and depth cap; reject cyclic proposals. Covers `@edge-case @data-integrity supersession-cycle-rejection`. Complexity 4. Dependencies: unit 1. Type: feature.

9. **Test verification via execute tool** — Invoke `pytest` through the `execute_command` tool in the worktree; parse output into the typed verification result dict. Covers `@key-example test-verification`, `@negative negative-failing-tests-reported`, ASSUM-003/004. Complexity 3. Dependencies: none. Type: feature.

10. **Git/gh operations via execute tool** — Implement branch, commit, push, and PR creation calls through `execute_command`; env-only credential reads; allowlist validation. Covers `@key-example pr-opened`, `@integration integration-end-to-end-build`, `@security security-env-only-credentials`, `@security security-working-directory-allowlist`, `@negative negative-missing-credentials`. Complexity 4. Dependencies: unit 9. Type: feature.

11. **BDD step implementations** — Wire all 43 scenarios to step functions in `tests/bdd/`. Prioritise the 6 `@smoke` scenarios first. Complexity 6. Dependencies: units 1–10. Type: testing.

12. **Security and concurrency scenario hardening** — Explicit tests for allowlist refusal, rationale redaction, filesystem read allowlist, split-brain dedupe, priors-not-as-arguments, recency-horizon bound. Covers remaining `@security`, `@concurrency`, `@data-integrity` scenarios. Complexity 4. Dependencies: unit 11. Type: testing.

---

## 11. Decision-Checkpoint Summary

- **What is being decided:** Whether to proceed with implementing FEAT-FORGE-006 (Infrastructure Coordination) as a 12-task, 40–60 hour effort using the recommended async-write / parallel-priors / execute-tool architectural approach.
- **All three open assumptions resolved:** ASSUM-006 (confirm with concrete regex set), ASSUM-007 (confirm via SQLite UUID as Graphiti entity_id), ASSUM-008 (confirm with explicit client-side sort by `decided_at` ascending).
- **No deferred scope:** All 43 scenarios are in-scope; no dependency on not-yet-implemented FEAT-FORGE-001/002 features beyond read-only consumption of their outputs.
- **Primary risk:** Graphiti/FalkorDB Tailscale availability; mitigated by fire-and-forget writes and reconcile-backfill, both of which must be implemented as first-class tasks (units 2 and 4).
- **Options are [A]ccept this report and proceed to /feature-plan, [R]evise with additional guidance, [I]mplement directly from this report, or [C]ancel the feature.**
