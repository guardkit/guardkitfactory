"""Unit tests for :class:`guardkitfactory.harness.LangGraphHarness` (TASK-HMIG-001B).

Covers AC-008 + the cross-repo subclass relation from AC-001:

* Happy path: stub model + empty tool list + ``invoke()`` returns a final
  assistant message in the event stream.
* Dual-system-message input raises ``ValueError`` via the
  :func:`lib.factory_guards.assert_no_system_messages` guard
  (TASK-REV-R2A1 mitigation).
* Unknown model surfaces an attributable ``LangGraphHarnessError`` rather
  than a generic langchain failure.
* The :meth:`LangGraphHarness.invoke` return value is an async iterator.
* :class:`LangGraphHarness` is a true subclass of the cross-repo
  :class:`guardkit.orchestrator.harness.HarnessAdapter` ABC.

Async tests are driven via ``asyncio.run()`` because ``pytest-asyncio``
is not (yet) a declared dev dependency — keeping the test file
dependency-free.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    HarnessAdapter,
    ResultMessageEvent,
)

from guardkitfactory import LangGraphHarness, LangGraphHarnessError

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _drain(harness: LangGraphHarness, prompt: str = "hi") -> list[Any]:
    """Drive ``harness.invoke(...)`` to completion and return the collected events."""

    async def _collect() -> list[Any]:
        events: list[Any] = []
        async for event in harness.invoke(
            prompt=prompt,
            role="player",
            tools=[],
            cwd=Path.cwd(),
            timeout_seconds=30,
        ):
            events.append(event)
        return events

    return asyncio.run(_collect())


def _make_fake_agent(final_text: str = "all done") -> MagicMock:
    """Build a MagicMock that mimics what ``create_deep_agent`` returns.

    The skeleton only touches ``agent.ainvoke``, so an ``AsyncMock`` for
    that single attribute is enough. The return shape mirrors a real
    LangGraph result dict containing a final AI-style message dict.
    """
    fake = MagicMock(name="fake_deep_agent")
    fake.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {"role": "user", "content": "irrelevant"},
                {"role": "assistant", "content": final_text},
            ]
        }
    )
    return fake


# ---------------------------------------------------------------------------
# AC-001 + falsifier: cross-repo subclass relation
# ---------------------------------------------------------------------------


class TestSubclassRelation:
    def test_langgraph_harness_subclasses_cross_repo_adapter(self) -> None:
        """LangGraphHarness MUST be a real subclass of the guardkit ABC."""
        assert issubclass(LangGraphHarness, HarnessAdapter)

    def test_session_id_default_is_none(self) -> None:
        """AC-006: ``session_id`` returns None for the skeleton."""
        harness = LangGraphHarness(model="ignored")
        assert harness.session_id is None

    def test_supports_resume_default_is_false(self) -> None:
        """AC-007: ``supports_resume`` returns False for the skeleton."""
        harness = LangGraphHarness(model="ignored")
        assert harness.supports_resume is False

    def test_constructor_stores_model_backend_permissions(self) -> None:
        """AC-002: __init__ stores the three documented parameters."""
        sentinel_backend = object()
        sentinel_perms = [object()]
        harness = LangGraphHarness(
            model="openai:gpt-4o-mini",
            backend=sentinel_backend,
            permissions=sentinel_perms,
        )
        assert harness.model == "openai:gpt-4o-mini"
        assert harness.backend is sentinel_backend
        assert harness.permissions is sentinel_perms


# ---------------------------------------------------------------------------
# AC-008.1: happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_invoke_yields_assistant_then_result(self) -> None:
        """A stub agent's final AIMessage surfaces as an AssistantMessageEvent.

        We patch ``create_deep_agent`` at the point of use inside the
        harness module so the real DeepAgents constructor never runs.
        """
        harness = LangGraphHarness(model="ignored-stub-model")

        fake_agent = _make_fake_agent(final_text="hello from stub")

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ) as create_mock:
            events = _drain(harness, prompt="say hi")

        # The DeepAgent constructor was called with the harness-bound
        # parameters — confirms AC-003 wiring.
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == "ignored-stub-model"
        assert kwargs["tools"] == []
        assert kwargs["backend"] is None
        assert kwargs["permissions"] is None
        assert kwargs["system_prompt"] == "player"

        # The ainvoke call shape matches the AC-003 contract: a single
        # user-role message carrying the prompt.
        fake_agent.ainvoke.assert_awaited_once_with(
            {"messages": [{"role": "user", "content": "say hi"}]}
        )

        # Stream taxonomy: one assistant message + one terminal result.
        assert len(events) == 2
        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].text == "hello from stub"
        assert isinstance(events[1], ResultMessageEvent)
        assert events[1].session_id is None
        assert events[1].stop_reason == "end_turn"

    def test_invoke_with_empty_assistant_yields_empty_text(self) -> None:
        """If the agent returns no AI message, AssistantMessageEvent.text == ''."""
        harness = LangGraphHarness(model="ignored")

        fake_agent = MagicMock()
        fake_agent.ainvoke = AsyncMock(return_value={"messages": []})

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert len(events) == 2
        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].text == ""


# ---------------------------------------------------------------------------
# AC-008.2: dual-system-message guard (TASK-REV-R2A1)
# ---------------------------------------------------------------------------


class TestDualSystemMessageGuard:
    def test_input_with_system_message_raises_value_error(self) -> None:
        """If a system message somehow lands in the ainvoke input, fail loudly.

        The harness builds its own input dict from the prompt in
        production, so the only way to inject a ``system`` role payload is
        to override ``_build_input``. The test does exactly that to prove
        the :func:`assert_no_system_messages` guard is wired.
        """

        class SystemMessageHarness(LangGraphHarness):
            def _build_input(self, prompt: str) -> dict[str, Any]:
                return {
                    "messages": [
                        {"role": "system", "content": "stowaway system msg"},
                        {"role": "user", "content": prompt},
                    ]
                }

        harness = SystemMessageHarness(model="ignored")

        # The guard must fire BEFORE create_deep_agent runs — patch the
        # constructor too so a real construction can't accidentally
        # succeed and mask the assertion.
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        ) as create_mock:
            with pytest.raises(ValueError, match="system messages"):
                _drain(harness)
            create_mock.assert_not_called()


# ---------------------------------------------------------------------------
# AC-008.3: unknown model surfaces an attributable error
# ---------------------------------------------------------------------------


class TestUnknownModelError:
    def test_construction_failure_wraps_into_langgraph_harness_error(self) -> None:
        """A ValueError from create_deep_agent surfaces as LangGraphHarnessError.

        Uses a deliberately bogus provider-prefixed model string so
        ``init_chat_model`` (called inside ``create_deep_agent``) raises
        ``ValueError: Unable to infer model provider …``. The harness
        must catch and re-raise with role/model context so callers see
        an attributable error rather than a generic langchain message.
        """
        harness = LangGraphHarness(model="nonexistent-provider:fake-model")

        with pytest.raises(LangGraphHarnessError) as excinfo:
            _drain(harness)

        msg = str(excinfo.value)
        assert "LangGraphHarness" in msg
        assert "nonexistent-provider:fake-model" in msg
        assert "player" in msg  # the role tag is part of the attribution

        # The original ValueError must be preserved on __cause__.
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_ainvoke_failure_wraps_into_langgraph_harness_error(self) -> None:
        """A failure during ``agent.ainvoke`` is also wrapped attributably."""
        harness = LangGraphHarness(model="ignored")

        fake_agent = MagicMock()
        fake_agent.ainvoke = AsyncMock(side_effect=RuntimeError("backend exploded"))

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            with pytest.raises(LangGraphHarnessError) as excinfo:
                _drain(harness)

        assert "agent.ainvoke failed" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, RuntimeError)


# ---------------------------------------------------------------------------
# AC-008.4: stream is async-iterable
# ---------------------------------------------------------------------------


class TestStreamIsAsyncIterable:
    def test_invoke_returns_async_iterator(self) -> None:
        """``invoke(...)`` returns an async iterator (not a coroutine)."""
        harness = LangGraphHarness(model="ignored")

        stream = harness.invoke(
            prompt="hi",
            role="player",
            tools=[],
            cwd=Path.cwd(),
            timeout_seconds=30,
        )

        # Async-generator function => calling it returns an async
        # iterator immediately, without entering the body.
        assert inspect.isasyncgen(stream)
        assert hasattr(stream, "__aiter__")
        assert hasattr(stream, "__anext__")

        # Close the generator to avoid a "coroutine was never awaited"
        # style warning on the unawaited body.
        asyncio.run(stream.aclose())
