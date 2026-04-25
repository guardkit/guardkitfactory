"""Forge ↔ LangGraph adapter — resume-value rehydration helpers (DDR-002).

Per ``API-nats-approval-protocol.md §4.2`` and DDR-002 (closes risk
**R2** — rehydration drift), the value returned by LangGraph's
``interrupt()`` is **not** uniformly typed across runtime modes:

* In **direct-invoke** mode (in-process orchestrator) the value is
  already a Pydantic instance — typed round-trip is preserved.
* Under ``langgraph dev`` / **LangGraph server** mode the same value
  arrives as a plain ``dict`` because the graph is rehydrated from
  serialized checkpoint state.

Direct attribute access on the resume value (e.g. ``raw.decision``,
``raw.responder``) therefore works *only* in direct-invoke mode and
silently regresses to ``AttributeError`` under server mode. To prevent
that regression every ``interrupt()`` consumer in ``forge`` MUST funnel
the resume value through :func:`resume_value_as` before any attribute
access. The CI grep guard in
``tests/forge/adapters/test_resume_value_helper.py`` enforces that rule
across the entire ``src/forge/`` tree.

Module purity (DDR-002):

* No imports from ``nats_core`` or ``nats-py`` — the helper operates on
  plain Pydantic models and dicts.
* The only third-party dependency is ``pydantic`` (for the
  ``BaseModel.model_validate`` round-trip). LangGraph types are *not*
  imported here because the helper is generic over any Pydantic model
  used as an interrupt resume payload, not just LangGraph's own.

See also:

* ``API-nats-approval-protocol.md §4.2`` — runtime-mode dichotomy.
* ``docs/decisions/DDR-002-langgraph-resume-value-rehydration.md`` —
  the DDR that motivates this helper.
* TASK-CGCP-009 (this task) — defines the helper.
* TASK-CGCP-010 — wires the helper into ``forge.gating.wrappers`` at
  every ``interrupt()`` call site.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

#: Generic type variable bound to :class:`pydantic.BaseModel`. The bound
#: is required so the type checker can prove that ``typ.model_validate``
#: is callable on ``typ`` — without the bound it would only know ``typ``
#: is *some* type and reject the ``model_validate`` access.
T = TypeVar("T", bound=BaseModel)


def resume_value_as(typ: type[T], raw: T | dict[str, Any] | Any) -> T:
    """Rehydrate the value returned by ``interrupt()`` into a typed instance.

    This is the **single, mandatory** entry point for every
    ``interrupt()`` consumer in ``forge``. It collapses the runtime-mode
    dichotomy described in the module docstring into one typed value
    so callers can read ``.decision`` / ``.responder`` / ``.notes``
    without branching on whether the graph is running in direct-invoke
    or server mode.

    Behaviour, in order:

    1. **``isinstance`` short-circuit.** If ``raw`` is already an
       instance of ``typ`` (or a subclass), return it **unchanged** —
       this preserves identity in direct-invoke mode and guarantees
       zero validation cost on the hot path (``API §4.2``: "The
       ``isinstance`` short-circuit makes this a no-op in direct-invoke
       mode").
    2. **``dict`` round-trip.** If ``raw`` is a ``dict``, validate it
       through ``typ.model_validate(raw)`` (Pydantic v2). Pydantic
       raises :class:`pydantic.ValidationError` if the dict is missing
       required fields or carries values that violate the model schema —
       that exception is allowed to propagate so server-mode operators
       see the same diagnostic they would get for any other malformed
       message.
    3. **Anything else** — raise :class:`TypeError` with a message that
       names both the expected type and the actual type so operators
       can diagnose without re-running with a debugger.

    Args:
        typ: The Pydantic model class the resume value is supposed to
            be an instance of (e.g.
            ``nats_core.events.ApprovalResponsePayload``). Used both for
            the ``isinstance`` short-circuit and as the validator class
            for the dict round-trip.
        raw: The value returned by ``interrupt()``. May already be a
            ``typ`` instance (direct-invoke mode), a ``dict`` of
            equivalent content (server mode), or — exceptionally —
            something else, in which case ``TypeError`` is raised.

    Returns:
        A ``typ`` instance — the same object as ``raw`` when ``raw``
        was already typed, or a freshly validated instance when ``raw``
        was a dict.

    Raises:
        TypeError: If ``raw`` is neither an instance of ``typ`` nor a
            ``dict``. The message includes the expected type name, the
            actual type name, and a truncated ``repr`` of ``raw`` for
            diagnostics.
        pydantic.ValidationError: Propagated from ``typ.model_validate``
            when ``raw`` is a ``dict`` whose contents do not satisfy the
            model schema. Allowed to propagate so the server-mode
            handler can surface the underlying problem to the operator.

    Examples:
        Direct-invoke mode — typed input is returned by identity::

            payload = ApprovalResponsePayload(
                request_id="r-1", decision="approve", decided_by="rich",
            )
            assert resume_value_as(ApprovalResponsePayload, payload) is payload

        Server mode — dict input is validated into a typed instance::

            raw = {"request_id": "r-1", "decision": "approve",
                   "decided_by": "rich"}
            typed = resume_value_as(ApprovalResponsePayload, raw)
            assert typed.decision == "approve"
    """
    # Step 1 — direct-invoke short-circuit. ``isinstance`` accepts the
    # exact type and any subclass, which matches the contract in
    # ``API §4.2`` and keeps the hot path allocation-free.
    if isinstance(raw, typ):
        return raw

    # Step 2 — server-mode round-trip. We deliberately accept *only*
    # plain ``dict`` here, not arbitrary mappings: LangGraph's
    # checkpoint serializer round-trips through JSON, so the resume
    # value is always a built-in ``dict``. Accepting other mapping
    # types would invite subtle bugs (e.g. a user-defined mapping
    # whose ``__iter__`` does not yield string keys).
    if isinstance(raw, dict):
        return typ.model_validate(raw)

    # Step 3 — neither typed nor dict. Build a clear, bounded ``repr``
    # so operators see the offending value without flooding logs.
    raw_repr = repr(raw)
    if len(raw_repr) > 120:
        raw_repr = raw_repr[:117] + "..."
    raise TypeError(
        f"resume_value_as: expected an instance of "
        f"{typ.__name__} or a dict (got {type(raw).__name__}: {raw_repr})",
    )


__all__ = ["resume_value_as"]
