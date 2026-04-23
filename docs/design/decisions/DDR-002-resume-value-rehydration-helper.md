# DDR-002 — `resume_value_as` helper placement + contract

## Status

Accepted

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
