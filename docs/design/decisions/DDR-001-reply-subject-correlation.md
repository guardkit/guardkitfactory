# DDR-001 — Reply-subject correlation for agents.command.* dispatch

## Status

Accepted — interim-carrier clause superseded 2026-04-23

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-015, ADR-ARCH-003, `specialist-agent` LES1 §2 parity rule

> **Resolution (2026-04-23).** `nats-core 0.2.0` shipped the reconciled `StageCompletePayload`/`BuildPausedPayload`/`BuildResumedPayload` + added `BuildCancelledPayload` via `TASK-NCFA-003`. Forge's scaffold post-dated the release, so the `forge.adapters.nats._interim_payloads.py` carrier forecast below was **retired before creation** — no local payload module ever existed. Timestamp fields on all four payloads ship as `str` (ISO-8601), not `datetime` — consumers convert at the edge if a `datetime` is needed. The decision on reply-subject correlation (Convention B) remains in force.

---

## Context

Forge dispatches commands to fleet specialists via `agents.command.{agent_id}` and expects a result back. Two candidate reply conventions:

- **A: Shared reply subject** — all specialists publish on `agents.result.{agent_id}` (one subject per agent). Caller filters by `request_id` in the envelope.
- **B: Per-correlation reply subject** — specialists publish on `agents.result.{agent_id}.{request_id}`. Caller subscribes to the exact correlation-keyed subject before publishing.

Convention A is simpler (fewer subjects), but it creates an observed failure mode: the JetStream `AGENTS` stream intercepts `agents.>` for audit and returns `PubAck` within ~3ms. Operators / simple callers treat PubAck as the reply and exit before the real message arrives. This silently broke the round-trip contract in specialist-agent iterations (LES1 §2, walkthrough §retest-smoke).

Convention B eliminates the ambiguity — the caller subscribes to a one-shot subject keyed by its own `request_id`, so there is no generic subject that JetStream's audit intercept can pre-empt.

Related design concern: Forge's API contract needs four pipeline payload types. Investigation during task creation revealed that `nats-core` already shipped `StageCompletePayload`, `BuildPausedPayload`, and `BuildResumedPayload` in **TASK-NCFA-001 (completed 2026-04-16)** — but with **different field signatures** than what Forge's contract specifies. Only `BuildCancelledPayload` is net-new. Reconciliation + addition is tracked in **`TASK-NCFA-003`** in the nats-core repo (the originally-proposed `TASK-NCFA-002` ID is already taken by the integration-tests task from that earlier wave). Forge must carry the canonical-shape types locally in `forge.adapters.nats._interim_payloads.py` until `nats-core ≥ 0.2.0` reconciles the field sets and adds `BuildCancelledPayload`.

## Decision

**Adopt Convention B.** Reply subjects are `agents.result.{agent_id}.{request_id}`. Forge's `forge.adapters.nats.request_reply_dispatch` subscribes to the exact subject *before* publishing the command and unsubscribes after the first message or timeout.

**PubAck is never treated as success.** The dispatch is complete only when a payload arrives on the correlation-keyed subject, or the local timeout fires.

**Payload reconciliation carried locally until nats-core ships the canonical shapes.** `forge.adapters.nats._interim_payloads.py` defines `StageCompletePayload`, `BuildPausedPayload`, `BuildResumedPayload`, `BuildCancelledPayload` in the field signatures Forge needs, with a TODO pointing to **`TASK-NCFA-003`** (nats-core repo). Drop the interim module when `nats-core ≥ 0.2.0` ships the reconciled types + `BuildCancelledPayload`.

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
