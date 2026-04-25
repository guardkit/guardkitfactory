"""Tests for ``forge.dispatch.retry`` (TASK-SAD-007).

The retry coordinator is **reasoning-model-driven**: there is no fixed
max-retry at this layer. The coordinator's job is to forward exactly
one retry decision into the orchestrator with three transformations:

1. A fresh correlation key (orchestrator-issued — distinct from the
   prior attempt's key).
2. ``attempt_no = previous_outcome.attempt_no + 1``.
3. ``retry_of = previous_outcome.resolution_id`` stamped onto the
   persisted sibling resolution row (the original row is **not**
   overwritten — both rows exist after retry).

Acceptance criteria coverage map:

* AC-001: ``RetryCoordinator`` with ``retry_with_context()`` is
  exported from :mod:`forge.dispatch.retry` — see
  :class:`TestRetryCoordinatorSurface`.
* AC-002: No fixed max-retry at this layer; documented in the module
  docstring — see :class:`TestNoFixedMaxRetryDocumented`.
* AC-003 (A.retry-with-additional-context): the retry's outcome
  carries ``attempt_no = previous + 1`` and the new resolution row's
  ``retry_of`` field equals the previous ``resolution_id`` — see
  :class:`TestRetryWithAdditionalContext`.
* AC-004 (fresh correlation): the retry's correlation key is distinct
  from the previous attempt's correlation key, verified via the
  registry's binding map (``transport.subscribed_keys`` is the
  registry's binding-map projection in tests) — see
  :class:`TestFreshCorrelationKey`.
* AC-005 (sibling not overwrite): after retry, both resolution
  records exist in persistence, the original is unchanged — see
  :class:`TestSiblingResolutionRecord`.
* AC-006 (additional context propagation): parameters list passed to
  ``orchestrator.dispatch()`` is ``original + additional_context`` in
  order; original parameters are not mutated — see
  :class:`TestAdditionalContextPropagation`.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from typing import Any

import pytest

from forge.dispatch.models import DispatchAttempt, SyncResult
from forge.dispatch.persistence import DispatchParameter
from forge.dispatch.retry import RetryCoordinator

# Reuse the orchestrator test scaffolding — the same in-memory transport,
# publisher, registry, timeout, and SQLite history writer wiring used by
# TASK-SAD-006's tests. Re-implementing the wiring here would duplicate
# ~250 lines of fakes for no behavioural benefit.
from tests.forge.dispatch.test_orchestrator import (
    FakePublisher,
    FakeReplyChannel,
    _build_orchestrator,
    _populate_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _drive_one_dispatch(
    orchestrator: Any,
    transport: FakeReplyChannel,
    *,
    capability: str = "review",
    parameters: list[DispatchParameter] | None = None,
    source_agent_id: str = "specialist-a",
    payload: dict[str, Any] | None = None,
) -> Any:
    """Run one ``orchestrator.dispatch()`` and feed an authentic reply."""
    parameters = parameters if parameters is not None else []
    payload = payload if payload is not None else {"agent_id": source_agent_id}
    dispatch_task = asyncio.create_task(
        orchestrator.dispatch(capability=capability, parameters=parameters)
    )
    # Wait until the orchestrator subscribes, then synthesise a reply.
    for _ in range(100):
        await asyncio.sleep(0)
        if transport.subscribed_keys:
            break
    assert transport.subscribed_keys, "orchestrator never bound a subscription"
    key = transport.subscribed_keys[-1]
    transport.emit_reply(
        key, source_agent_id=source_agent_id, payload=payload
    )
    return await dispatch_task


async def _drive_retry(
    coordinator: RetryCoordinator,
    transport: FakeReplyChannel,
    *,
    previous_outcome: Any,
    capability: str,
    original_parameters: list[DispatchParameter],
    additional_context: list[DispatchParameter],
    source_agent_id: str = "specialist-a",
    payload: dict[str, Any] | None = None,
) -> Any:
    """Run one ``retry_with_context()`` and feed an authentic reply.

    The retry path goes through the orchestrator's normal dispatch, so
    we drive a fresh subscribe/reply pair the same way as a first
    dispatch.
    """
    payload = payload if payload is not None else {"agent_id": source_agent_id}
    keys_before = len(transport.subscribed_keys)
    retry_task = asyncio.create_task(
        coordinator.retry_with_context(
            previous_outcome=previous_outcome,
            capability=capability,
            original_parameters=original_parameters,
            additional_context=additional_context,
        )
    )
    for _ in range(100):
        await asyncio.sleep(0)
        if len(transport.subscribed_keys) > keys_before:
            break
    assert len(transport.subscribed_keys) > keys_before, (
        "retry never produced a fresh subscribe — fresh-correlation "
        "invariant cannot be verified"
    )
    new_key = transport.subscribed_keys[-1]
    transport.emit_reply(
        new_key, source_agent_id=source_agent_id, payload=payload
    )
    return await retry_task


# ---------------------------------------------------------------------------
# AC-001 — module surface
# ---------------------------------------------------------------------------


class TestRetryCoordinatorSurface:
    """AC-001 — ``RetryCoordinator.retry_with_context`` exists, async."""

    def test_module_defines_retry_coordinator_class(self) -> None:
        from forge.dispatch import retry as module

        assert hasattr(module, "RetryCoordinator")

    def test_retry_with_context_is_async(self) -> None:
        assert inspect.iscoroutinefunction(
            RetryCoordinator.retry_with_context
        )


# ---------------------------------------------------------------------------
# AC-002 — no fixed max-retry; documented in module docstring
# ---------------------------------------------------------------------------


class TestNoFixedMaxRetryDocumented:
    """AC-002 — module docstring records the no-max-retry invariant."""

    def test_module_docstring_documents_no_max_retry(self) -> None:
        from forge.dispatch import retry as module

        assert module.__doc__ is not None
        # Search for an explicit acknowledgement of the policy seam — we
        # don't pin to a single phrase, but the docstring MUST mention
        # both "max-retry" (the missing concept) and that the reasoning
        # loop owns retry policy. Without this, future maintainers may
        # silently re-introduce a counter at this layer.
        text = module.__doc__.lower()
        assert "max-retry" in text or "max retry" in text, (
            "docstring must document the absence of a fixed max-retry"
        )
        assert "reasoning" in text, (
            "docstring must call out that the reasoning loop owns "
            "retry policy"
        )


# ---------------------------------------------------------------------------
# AC-003 — A.retry-with-additional-context
# ---------------------------------------------------------------------------


class TestRetryWithAdditionalContext:
    """AC-003 — attempt_no incremented and retry_of linkage persisted."""

    @pytest.mark.asyncio
    async def test_retry_outcome_attempt_no_is_previous_plus_one(
        self,
    ) -> None:
        orch, cache, _r, transport, _publisher, _db = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        assert isinstance(first, SyncResult)
        assert first.attempt_no == 1

        retry = await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=[],
            additional_context=[],
        )
        assert isinstance(retry, SyncResult)
        assert retry.attempt_no == first.attempt_no + 1 == 2

    @pytest.mark.asyncio
    async def test_retry_persists_retry_of_link_to_previous_resolution(
        self,
    ) -> None:
        orch, cache, _r, transport, _p, db_writer = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=[],
            additional_context=[],
        )
        rows = db_writer.read_resolutions()
        # Two resolution rows: original + sibling.
        assert len(rows) == 2
        siblings = [row for row in rows if row.retry_of == first.resolution_id]
        assert len(siblings) == 1, (
            "exactly one sibling row must carry retry_of=previous.resolution_id"
        )


# ---------------------------------------------------------------------------
# AC-004 — fresh correlation key (registry binding-map projection)
# ---------------------------------------------------------------------------


class TestFreshCorrelationKey:
    """AC-004 — retry's correlation key is distinct from the original."""

    @pytest.mark.asyncio
    async def test_retry_uses_fresh_correlation_key_not_previous_one(
        self,
    ) -> None:
        orch, cache, _r, transport, publisher, _db = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        first_key = publisher.published[-1].attempt.correlation_key

        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=[],
            additional_context=[],
        )
        retry_key = publisher.published[-1].attempt.correlation_key

        assert first_key != retry_key, (
            "retry MUST issue a fresh correlation key — got identical keys"
        )
        # Both keys are 32-lowercase-hex per the CorrelationKey contract.
        assert re.fullmatch(r"[0-9a-f]{32}", first_key)
        assert re.fullmatch(r"[0-9a-f]{32}", retry_key)
        # Registry binding-map projection — the transport saw both keys
        # subscribed. (Verifies the key wasn't reused at the registry
        # bind() level either.)
        assert first_key in transport.subscribed_keys
        assert retry_key in transport.subscribed_keys
        assert transport.subscribed_keys.count(first_key) == 1
        assert transport.subscribed_keys.count(retry_key) == 1


# ---------------------------------------------------------------------------
# AC-005 — sibling resolution record (NOT an overwrite)
# ---------------------------------------------------------------------------


class TestSiblingResolutionRecord:
    """AC-005 — both rows exist after retry; original is unchanged."""

    @pytest.mark.asyncio
    async def test_retry_creates_sibling_record_and_preserves_original(
        self,
    ) -> None:
        orch, cache, _r, transport, _p, db_writer = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        rows_before = db_writer.read_resolutions()
        assert len(rows_before) == 1
        original_row_before = rows_before[0]

        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=[],
            additional_context=[],
        )

        rows_after = db_writer.read_resolutions()
        assert len(rows_after) == len(rows_before) + 1, (
            "retry must add a sibling row, not replace the original"
        )

        # Original row identity preserved.
        original_row_after = next(
            row for row in rows_after
            if row.resolution_id == first.resolution_id
        )
        # Persisted row stable across the retry — equality is defined
        # by Pydantic's structural compare on every field.
        assert original_row_after == original_row_before
        # Original's retry_of remains None — the original is not
        # retroactively re-pointed at anything.
        assert original_row_after.retry_of is None


# ---------------------------------------------------------------------------
# AC-006 — additional context propagation
# ---------------------------------------------------------------------------


class TestAdditionalContextPropagation:
    """AC-006 — parameters = original + additional_context, in order."""

    @pytest.mark.asyncio
    async def test_orchestrator_receives_original_then_additional_in_order(
        self,
    ) -> None:
        orch, cache, _r, transport, publisher, _db = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        original = [
            DispatchParameter(name="goal", value="ship"),
            DispatchParameter(name="repo", value="forge"),
        ]
        extra = [
            DispatchParameter(name="hint", value="check tests"),
            DispatchParameter(name="severity", value="high"),
        ]
        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=original,
            additional_context=extra,
        )

        # The publisher records every call. The retry is the most recent.
        retry_record = publisher.published[-1]
        published_param_pairs = [
            (param.name, param.value) for param in retry_record.parameters
        ]
        expected = [
            ("goal", "ship"),
            ("repo", "forge"),
            ("hint", "check tests"),
            ("severity", "high"),
        ]
        assert published_param_pairs == expected, (
            "retry parameters MUST be original + additional_context, in order"
        )

    @pytest.mark.asyncio
    async def test_retry_does_not_mutate_caller_provided_lists(
        self,
    ) -> None:
        orch, cache, _r, transport, _p, _db = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        original = [DispatchParameter(name="goal", value="ship")]
        extra = [DispatchParameter(name="hint", value="retry")]

        # Snapshot identity + length before the call.
        original_id_before = id(original)
        extra_id_before = id(extra)
        original_len_before = len(original)
        extra_len_before = len(extra)

        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=original,
            additional_context=extra,
        )

        # The caller's lists are untouched: same identity, same length,
        # same elements.
        assert id(original) == original_id_before
        assert id(extra) == extra_id_before
        assert len(original) == original_len_before == 1
        assert len(extra) == extra_len_before == 1
        assert original[0].name == "goal"
        assert extra[0].name == "hint"


# ---------------------------------------------------------------------------
# Constructor wiring smoke test
# ---------------------------------------------------------------------------


class TestRetryCoordinatorConstruction:
    """Constructor accepts a :class:`DispatchOrchestrator` and stores it."""

    @pytest.mark.asyncio
    async def test_retry_coordinator_holds_injected_orchestrator(
        self,
    ) -> None:
        orch, _cache, _r, _t, _p, _db = await _build_orchestrator()
        coordinator = RetryCoordinator(orch)
        # Coordinator forwards to the injected orchestrator — verified
        # indirectly by the AC tests above; this is the explicit
        # surface check that ``retry_with_context`` is bound and
        # callable on a constructed instance.
        assert callable(coordinator.retry_with_context)


# ---------------------------------------------------------------------------
# Seam test (verbatim contract from TASK-SAD-007 spec)
# ---------------------------------------------------------------------------


class TestSeamCapabilityResolutionSiblingContract:
    """Seam: CapabilityResolution.retry_of from TASK-SAD-001."""

    @pytest.mark.asyncio
    @pytest.mark.integration_contract("CapabilityResolution")  # type: ignore[misc]
    async def test_retry_creates_sibling_record_not_overwrite(
        self,
    ) -> None:
        orch, cache, _r, transport, _p, db_writer = await _build_orchestrator()
        await _populate_cache(cache)
        coordinator = RetryCoordinator(orch)

        first = await _drive_one_dispatch(orch, transport)
        rows_before = len(db_writer.read_resolutions())

        await _drive_retry(
            coordinator,
            transport,
            previous_outcome=first,
            capability="review",
            original_parameters=[],
            additional_context=[],
        )
        rows_after = len(db_writer.read_resolutions())
        assert rows_after == rows_before + 1
        siblings = [
            row for row in db_writer.read_resolutions()
            if row.retry_of == first.resolution_id
        ]
        assert len(siblings) == 1


# Suppress unused-import lint by re-exporting the FakePublisher class
# alias — kept here so a future refactor that drops the helper still
# fails noisily (rather than silently changing the test surface).
_ = FakePublisher
_ = DispatchAttempt
