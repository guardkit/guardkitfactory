# ADR-FLEET-001: Trace-Richness by Default

- **Status:** Accepted
- **Date:** 2026-04-19
- **Scope:** Fleet-wide — applies to Forge, Jarvis, Study Tutor, and all specialist-agent roles
- **Related:** D42 in fleet-architecture-v3-coherence-via-flywheel.md; ADR-ARCH-005, ADR-ARCH-006 (Forge)

## Context

The Forge architecture committed to a Graphiti-fed learning loop: decisions + outcomes + overrides write to `forge_pipeline_history`; `forge.learning` detects patterns and proposes `CalibrationAdjustment` entities; Rich confirms; future builds retrieve priors. This is a Karpathy-Loop-shaped system — constrain the surface, record the trace, let meta-reasoning propose changes, gate via confirmation.

The Meta-Harness paper (Stanford, 2026 preprint) makes a decisive finding that reshapes how we should capture traces: **the quality of the optimisation loop scales with the context the proposer can see.** Their table of prior methods caps at 26K tokens per iteration (compressed summaries, scalar scores, windowed histories). Meta-Harness gives its proposer 10M tokens/iter — the full source code, scores, and execution traces of every prior candidate — via a filesystem the proposer reads with `grep`, `cat`, and normal tools. The result is a 10× iteration efficiency gain attributed specifically to the proposer's ability to trace failures back to the specific harness decision that caused them.

The Karpathy Loop video (Nate, 2026) reinforces this: *"An optimization loop that only sees outcomes produces somewhat random improvements. An optimization loop that sees the full reasoning chain makes much more surgical, logical edits."* Same mechanism.

Applied to our fleet: Forge currently records gate decisions and outcomes to Graphiti, but the *reasoning* that led to each decision — the supervisor's tool-call sequence, the dispatched subagent's trace, the cost and latency, the human's textual response — is only partially captured. The future `jarvis.learning` and `tutor.learning` modules will face the same question.

**This is a schema decision that is cheap to make now and nearly impossible to retrofit.** Once thousands of runs are accumulated with thin traces, the accumulated data is permanently low-resolution. The learning quality ceiling is set by the trace richness.

## Decision

Fleet-wide: every `*_history` Graphiti group captures, per decision, a **trace-rich schema**:

### Required fields for every decision record

1. **Decision identity**
   - `decision_id` — unique per decision event
   - `surface` — which agent made this decision (forge, jarvis, tutor, architect, etc.)
   - `session_id` — session or build correlation ID
   - `timestamp` — ISO 8601

2. **Reasoning context**
   - `supervisor_tool_call_sequence` — full ordered list of tool calls + arguments + results leading to this decision
   - `priors_retrieved` — which Graphiti entities were retrieved into the system prompt (with entity IDs, not just summaries)
   - `capability_snapshot` — the `{available_capabilities}` rendering at decision time (hash reference if large)

3. **Subagent delegation (if applicable)**
   - `subagent_type` — async subagent name, specialist agent ID, or sync `task()` invocation
   - `subagent_task_id` — for async subagents, the thread ID
   - `subagent_trace_ref` — reference to LangSmith trace or dispatched agent's result payload
   - `subagent_final_state` — success, error, cancelled, timeout

4. **Resource cost**
   - `model_calls` — list of {model_id, input_tokens, output_tokens, latency_ms, cost_usd}
   - `wall_clock_ms` — end-to-end time for this decision
   - `total_cost_usd` — summed across all model calls

5. **Outcome**
   - `outcome_type` — approved, rejected, redirected, timed-out, cancelled
   - `outcome_detail` — structured outcome (e.g. Coach score, gate mode, user redirect target)

6. **Human response (when applicable)**
   - `human_response_type` — confirm, reject, redirect, ignore, override
   - `human_response_text` — **free text when provided**, not just button presses. Captured as-is.
   - `human_response_latency_ms` — time from notification/pause to response

7. **Environmental context**
   - `project_id` — which project this decision was for
   - `local_time_of_day` — for time-pattern detection
   - `recent_session_refs` — last N session IDs (for sequence-pattern detection)
   - `concurrent_workload` — what else was running (helps diagnose degraded-mode edge cases)

### Storage model

Trace records are written to Graphiti groups using existing `add_memory` and entity-edge primitives:

| Group | Records | Used by |
|---|---|---|
| `forge_pipeline_history` | Gate decisions, dispatch decisions, override outcomes | `forge.learning`; future Forge builds retrieve priors |
| `forge_calibration_history` | CalibrationEvent stream from history files | `forge.learning`; system prompt retrieval |
| `jarvis_routing_history` | Subagent/specialist/build-queue dispatch decisions | `jarvis.learning`; future Jarvis sessions retrieve priors |
| `jarvis_ambient_history` | Watcher trigger firings, proactive notification outcomes | `jarvis.learning`; refines Pattern B thresholds |
| `tutor_teaching_history` | Teaching-pattern decisions per session | `tutor.learning`; per-subject + per-student priors |
| `role:{role_id}` | Per-specialist-role decisions (existing) | `specialist-agent` per-role learning |

Each group's schema extends the base trace schema above with group-specific fields (e.g. `forge_pipeline_history` includes `coach_score` and `gate_mode`; `jarvis_routing_history` includes `chosen_subagent_name` and `alternatives_considered`).

### Large traces

The `supervisor_tool_call_sequence` and `subagent_trace_ref` fields may be large. For any trace component that exceeds reasonable Graphiti entity size:

- Store the trace in a flat file under `~/.{surface}/traces/{date}/{decision_id}.json`
- Store only a reference path + content hash in the Graphiti entity
- The filesystem pattern mirrors Meta-Harness's approach: meta-reasoning can `grep`, `cat`, and `ls` through the trace archive on demand

This gives future meta-reasoning the Meta-Harness-style 10M-token-per-iteration context budget without bloating Graphiti.

### Privacy and redaction

Trace records may contain sensitive content (API keys, user PII, internal project details). Before write:

- Apply `structlog` redact-processor at the trace-capture boundary (consistent with fleet-wide ADR-ARCH-023 pattern)
- Redact patterns: API keys, JWT tokens, NATS credentials, email addresses, personal identifiers in free-text responses
- Never store raw secrets in Graphiti or trace files
- Redaction is applied at capture time; it cannot be reversed

## Consequences

**Positive:**

- **Future-proofs the learning loops.** When `jarvis.learning`, `tutor.learning`, or any future meta-reasoning layer needs better priors, the trace data is already there at high resolution.
- **Enables the Meta-Harness pattern later without retrofit.** If the deferred meta-agent split (D45) ever proves valuable, the proposer's filesystem already exists.
- **Improves per-surface debugging.** Rich can `grep` through traces to diagnose a specific decision's failure, not just see that it failed.
- **Compounds across surfaces.** Better trace-capture tooling in one surface improves all surfaces.
- **Supports DDD Southwest talk narrative.** "We capture full reasoning chains, not just outcomes" is a concrete technical differentiator with external validation (Meta-Harness paper).

**Negative:**

- **Storage cost.** Traces can be large. Mitigated by filesystem offload for oversize entities, and by retention policies (below).
- **Write latency.** Capturing full tool-call sequences adds per-decision write overhead. Mitigated by async writes where possible and by batching within a session.
- **Privacy surface.** Richer traces mean more potential for accidental sensitive-data capture. Redaction must be disciplined.
- **Schema complexity.** More fields per entity means more careful schema versioning. Mitigated by using existing Pydantic validation pattern from `nats-core`.

## Retention policy

- **`forge_pipeline_history`, `jarvis_routing_history`, `tutor_teaching_history`:** retained indefinitely. These are the learning substrate.
- **Trace filesystem archive (`~/.{surface}/traces/`):** retained 12 months, rolled quarterly. Older archives compressed and moved to NAS backup per fleet-wide backup strategy.
- **Explicitly purged on user request.** A `forge purge-traces` / `jarvis purge-traces` CLI must exist for any project or session Rich wants removed — GDPR-style cleanliness.

## Implementation sequencing

This ADR is **effective from v1 start** for every surface being built after 19 April 2026. Specifically:

- **Forge:** `forge.adapters.graphiti` implementation (FEAT-FORGE-006) writes trace-rich schema from day one. Forge's existing Phase 1 runs pre-date this ADR and are exempt — they remain at their original resolution.
- **Jarvis:** Trace-rich schema is a prerequisite for `jarvis.learning`. Build it alongside the learning module in whatever feature covers that (likely FEAT-JARVIS-XXX pending `/system-arch`).
- **Study Tutor:** When `tutor.learning` is added as future work, it adopts this schema.
- **Specialist-agent:** Phase G (Graphiti runtime) already writes decision records. Extend the schema to match this ADR during Phase G implementation.

## Do-not-reopen

Once the trace-rich schema is shipping in any surface, any future decision to *reduce* trace richness requires an explicit ADR and sign-off. The compounding value is in continuity — we should not accidentally degrade trace quality via well-meaning "simplifications" later.

## References

- fleet-architecture-v3-coherence-via-flywheel.md §7 (this ADR is the companion)
- Meta-Harness paper, yoonholee.com/meta-harness, 2026 preprint
- The Karpathy Loop video transcript (Nate, 2026-04-19)
- Forge ADR-ARCH-005 (Graphiti-fed learning loop)
- Forge ADR-ARCH-006 (Calibration corpus)
- Forge ADR-ARCH-024 (Observability via events + Graphiti + SQLite)
