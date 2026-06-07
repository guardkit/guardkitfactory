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
import warnings
from contextlib import suppress
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
from guardkitfactory.harness.extractors import (
    extract_last_ai_message,
    extract_last_ai_reasoning,
)

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


# ---------------------------------------------------------------------------
# TASK-HMIG-002R-MODEL-PROFILE — known operator models get profile injected
# before reaching ``create_deep_agent``. This is what makes deepagents'
# summarisation middleware switch from the no-profile fallback trigger
# (``("tokens", 170000)``) to the fraction-based trigger
# (``("fraction", 0.85)``) and start firing before sub-Sonnet contexts
# overflow. See ``autobuild-FEAT-AOF-run-2.md`` line 350.
# ---------------------------------------------------------------------------


def _fake_resolve_model(_spec: str) -> Any:
    """Stand-in for deepagents' ``resolve_model`` — no real provider deps.

    The dev venv may not have ``langchain-openai`` installed (production
    installs it via ``.[providers]``). Patching ``resolve_model`` at the
    model_config import site decouples these tests from that dependency.
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    return FakeListChatModel(responses=["ok"])


class TestModelProfileInjection:
    def test_known_model_string_is_resolved_with_profile_before_create_deep_agent(
        self,
    ) -> None:
        """qwen36-workhorse resolves to a BaseChatModel carrying max_input_tokens.

        The resolved model — not the original string — must be what reaches
        ``create_deep_agent``. We assert by inspecting the patched
        ``create_deep_agent``'s kwargs.
        """
        from langchain_core.language_models import BaseChatModel

        harness = LangGraphHarness(model="openai:qwen36-workhorse")
        fake_agent = _make_fake_agent()

        with (
            patch(
                "guardkitfactory.harness.model_config.resolve_model",
                side_effect=_fake_resolve_model,
            ),
            patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ) as create_mock,
        ):
            _drain(harness)

        passed_model = create_mock.call_args.kwargs["model"]
        assert isinstance(passed_model, BaseChatModel), (
            f"expected resolved BaseChatModel, got {type(passed_model)}"
        )
        assert passed_model.profile == {"max_input_tokens": 131_072}

    def test_unresolvable_model_string_passes_through_unchanged(self) -> None:
        """Resolution failures must not crash the harness.

        The harness preserves the original model so the downstream
        ``create_deep_agent`` call surfaces the failure with the existing
        attribution shape. This protects sentinel strings used by other
        tests (``"ignored"``, ``"ignored-stub-model"``) and any future
        provider misconfiguration.
        """
        harness = LangGraphHarness(model="ignored-stub-model")
        fake_agent = _make_fake_agent()

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ) as create_mock:
            _drain(harness)

        # Sentinel falls through as-is — no profile injection attempted.
        assert create_mock.call_args.kwargs["model"] == "ignored-stub-model"

    def test_self_model_is_not_mutated_by_invoke(self) -> None:
        """The cached ``self.model`` stays the original input shape.

        Resolution happens per-invoke and produces a fresh BaseChatModel
        each time; ``self.model`` itself is unchanged. AC-002
        (``test_constructor_stores_model_backend_permissions``) depends on
        this stability.
        """
        harness = LangGraphHarness(model="openai:qwen36-workhorse")
        fake_agent = _make_fake_agent()
        with (
            patch(
                "guardkitfactory.harness.model_config.resolve_model",
                side_effect=_fake_resolve_model,
            ),
            patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ),
        ):
            _drain(harness)

        assert harness.model == "openai:qwen36-workhorse"


# ---------------------------------------------------------------------------
# TASK-FIX-COACHBUDG01 — hybrid-reasoning-model handling. Per-role max_tokens
# injection AND ``AssistantMessageEvent.reasoning_text`` surfacing alongside
# the canonical ``text`` field. Substrate parity with sdk_harness.py's
# ``ThinkingBlock.thinking`` extraction.
# ---------------------------------------------------------------------------


def _make_fake_agent_with_reasoning(
    final_text: str = "all done",
    reasoning: str = "thinking step by step...",
) -> MagicMock:
    """Build a fake agent whose final AI message carries reasoning_content.

    Mirrors what langchain-openai produces when llama.cpp serves a hybrid-
    reasoning model under ``--reasoning auto`` — the message's
    ``additional_kwargs`` dict carries the ``reasoning_content`` key.
    """
    from langchain_core.messages import AIMessage

    ai_msg = AIMessage(
        content=final_text,
        additional_kwargs={"reasoning_content": reasoning},
    )
    fake = MagicMock(name="fake_deep_agent_with_reasoning")
    fake.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {"role": "user", "content": "irrelevant"},
                ai_msg,
            ]
        }
    )
    return fake


class TestReasoningTextSurfacing:
    def test_reasoning_content_lands_in_assistant_message_event(self) -> None:
        """ADR FB-004 substrate parity: hybrid-reasoning models route their
        chain-of-thought into ``reasoning_content``. The LangGraph harness
        MUST surface this on ``AssistantMessageEvent.reasoning_text`` so the
        orchestrator-side ``coach_output_parser`` can fall through to it
        when the canonical ``text`` field contains no fenced JSON block.

        Without this, hybrid-reasoning Coach models with narrow max_tokens
        budgets squeeze content out entirely and the F17 failure mode
        persists. This test pins the wire (the field IS populated when the
        model emitted reasoning).
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent_with_reasoning(
            final_text='```json\n{"decision": "approve"}\n```',
            reasoning="The Player's report mentions tests pass, so I should approve.",
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert "approve" in events[0].text
        assert events[0].reasoning_text == (
            "The Player's report mentions tests pass, so I should approve."
        )

    def test_no_reasoning_yields_empty_reasoning_text(self) -> None:
        """When the model didn't emit reasoning, ``reasoning_text`` defaults
        to ``""`` (per ``AssistantMessageEvent.reasoning_text: str = ""``).

        Backwards-compat: existing tests that mock agents without
        ``additional_kwargs`` MUST keep working without modification — and
        downstream consumers (``coach_output_parser``) see the same
        behaviour for non-reasoning models as before this task landed.
        """
        harness = LangGraphHarness(model="ignored")
        # _make_fake_agent uses plain dict messages with no additional_kwargs
        fake_agent = _make_fake_agent(final_text="approve")

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].text == "approve"
        assert events[0].reasoning_text == ""

    def test_role_is_threaded_to_resolve_autobuild_model(self) -> None:
        """The ``role`` invoke kwarg must reach ``resolve_autobuild_model``
        so per-role max_tokens budgets (16384 for Coach, 8192 for Player)
        are applied. Without this thread, hybrid-reasoning Coach turns
        squeeze content under the SDK default budget.
        """
        harness = LangGraphHarness(model="openai:qwen36-workhorse")
        fake_agent = _make_fake_agent()

        captured: dict[str, Any] = {}

        def _capture_resolve(model: Any, role: str | None = None) -> Any:
            captured["model"] = model
            captured["role"] = role
            return _fake_resolve_model(model if isinstance(model, str) else "")

        with (
            patch(
                "guardkitfactory.harness.langgraph_harness.resolve_autobuild_model",
                side_effect=_capture_resolve,
            ),
            patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ),
        ):
            # _drain defaults to role="player"
            _drain(harness)

        assert captured["role"] == "player", (
            "role kwarg must be threaded from invoke to resolve_autobuild_model"
        )


# ---------------------------------------------------------------------------
# TASK-FIX-COACHBUDG01-LG: reasoning recovery on the OpenAI Responses API path
# ---------------------------------------------------------------------------


def _responses_api_agent(
    content: Any,
    additional_kwargs: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a fake agent whose final AI message mimics an OpenAI Responses API
    (``POST /v1/responses``) ``AIMessage`` — the transport deepagents' default
    model resolution uses.

    ``content`` may be a plain string or a list of typed content blocks (the
    Responses API form). ``additional_kwargs`` carries the alternate
    ``reasoning`` dict shape when present. Faithful to what langchain-core
    1.4.0 materialises (verified by probing the installed client).
    """
    from langchain_core.messages import AIMessage

    ai_msg = AIMessage(content=content, additional_kwargs=additional_kwargs or {})
    fake = MagicMock(name="fake_responses_api_agent")
    fake.ainvoke = AsyncMock(
        return_value={
            "messages": [
                {"role": "user", "content": "evaluate the player report"},
                ai_msg,
            ]
        }
    )
    return fake


class TestResponsesApiReasoningExtraction:
    """TASK-FIX-COACHBUDG01-LG: deepagents' default model resolution routes the
    LangGraph harness through the OpenAI Responses API (``POST /v1/responses``),
    which structures reasoning differently from chat-completions. These tests
    pin each shape variant the installed ``langchain-openai`` can produce so
    reasoning reaches ``AssistantMessageEvent.reasoning_text`` (AC-001/002/003/
    005) without regressing the canonical-text path (AC-004). No live network —
    the agent is faked exactly as ``TestReasoningTextSurfacing`` fakes the
    chat-completions path.
    """

    def test_reasoning_summary_blocks_surface_on_reasoning_text(self) -> None:
        """AC-001/AC-003: the canonical OpenAI Responses API shape — a
        content-list ``reasoning`` block carrying a ``summary`` list of
        ``summary_text`` blocks — surfaces the joined plaintext summary on
        ``reasoning_text``. This is the shape that drove run-9's
        ``0 chars reasoning_content``.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            [
                {
                    "type": "reasoning",
                    "id": "rs_1",
                    "summary": [
                        {"type": "summary_text", "text": "The Player reports tests pass."},
                        {
                            "type": "summary_text",
                            "text": "Coverage meets the gate, so approve.",
                        },
                    ],
                },
                {
                    "type": "output_text",
                    "text": '```json\n{"decision": "approve"}\n```',
                    "annotations": [],
                },
            ]
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].reasoning_text == (
            "The Player reports tests pass.\nCoverage meets the gate, so approve."
        )
        assert len(events[0].reasoning_text) > 0

    def test_reasoning_summary_canonical_text_excludes_reasoning(self) -> None:
        """AC-004: with list content, ``text`` carries the visible
        ``output_text`` verdict — and never the reasoning-as-text. A naive
        flatten-all-blocks extractor would leak the chain-of-thought into the
        canonical text; this pins that it does not.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            [
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "secret chain of thought"}],
                },
                {
                    "type": "output_text",
                    "text": '```json\n{"decision": "approve"}\n```',
                    "annotations": [],
                },
            ]
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert "approve" in events[0].text
        assert "secret chain of thought" not in events[0].text

    def test_reasoning_text_key_block_surfaces_on_reasoning_text(self) -> None:
        """AC-001: an alternate adapter shape carries the reasoning plaintext
        directly under the block's ``text`` key (rather than a ``summary``
        list). The canonical ``text`` block still yields the verdict.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            [
                {"type": "reasoning", "text": "Reasoning via the text key on the block."},
                {"type": "text", "text": '```json\n{"decision": "reject"}\n```'},
            ]
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].reasoning_text == "Reasoning via the text key on the block."
        assert "reject" in events[0].text

    def test_additional_kwargs_reasoning_dict_surfaces_on_reasoning_text(self) -> None:
        """AC-001/AC-002: reasoning carried on ``additional_kwargs['reasoning']``
        (a dict with a ``summary`` list and an opaque ``encrypted_content``),
        with the canonical verdict on a plain ``content`` string. The summary
        surfaces; the ciphertext never does.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            content='```json\n{"decision": "approve"}\n```',
            additional_kwargs={
                "reasoning": {
                    "summary": [
                        {
                            "type": "summary_text",
                            "text": "Reasoning carried on additional_kwargs.",
                        }
                    ],
                    "encrypted_content": "ENCRYPTED-OPAQUE-BLOB",
                }
            },
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].reasoning_text == "Reasoning carried on additional_kwargs."
        assert "ENCRYPTED" not in events[0].reasoning_text
        assert "approve" in events[0].text

    def test_encrypted_content_only_yields_empty_reasoning_text(self) -> None:
        """AC-002: when the Responses-API ``reasoning`` dict carries *only*
        ``encrypted_content`` (no plaintext summary/text), ``reasoning_text``
        is empty — the opaque ciphertext is never surfaced to the parser.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            content="a plain answer with no fenced json block",
            additional_kwargs={"reasoning": {"encrypted_content": "ENCRYPTED-ONLY-NO-PLAINTEXT"}},
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].reasoning_text == ""

    def test_reasoning_content_list_surfaces_on_reasoning_text(self) -> None:
        """TASK-FIX-AC006SMOKE-LG: pins the **live gemma4-coach** shape
        observed against llama-swap's ``/v1/responses`` substrate via
        ``langchain-openai 1.2.2``. The reasoning block's plaintext lives on
        ``block["content"] = [{"type": "reasoning_text", "text": ...}]`` while
        every other plaintext key (``reasoning`` / ``text`` / ``summary``) is
        empty and ``encrypted_content`` is opaque/empty. A future
        ``langchain-openai`` bump that relocates the plaintext would fail
        this test loudly. Probe evidence:
        ``docs/state/TASK-FIX-AC006SMOKE-LG/captured_aimessage_probe_c.json``.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _responses_api_agent(
            [
                {
                    "type": "reasoning",
                    "id": "rs_live_shape",
                    "summary": [],
                    "encrypted_content": "",
                    "status": "completed",
                    "content": [
                        {
                            "type": "reasoning_text",
                            "text": "Step 1: verify the delta. Step 2: approve.",
                        }
                    ],
                },
                {
                    "type": "text",
                    "text": '```json\n{"decision": "approve"}\n```',
                    "annotations": [],
                },
            ]
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].reasoning_text == ("Step 1: verify the delta. Step 2: approve.")
        assert "approve" in events[0].text
        # The reasoning plaintext must not leak into the canonical text path.
        assert "Step 1" not in events[0].text

    def test_reasoning_extras_content_list_surfaces_on_reasoning_text(self) -> None:
        """TASK-FIX-AC006SMOKE-LG: pins the **langchain-core normalised**
        view of the same live shape, where the v1 normaliser moves provider-
        specific keys (``content``, ``encrypted_content``, ``status``) under
        ``extras``. The plaintext now lives on
        ``block["extras"]["content"] = [{"type": "reasoning_text", ...}]``;
        the extractor must consult it after the raw path misses. This shape
        is what ``msg.content_blocks`` (the normalised property) surfaces —
        probe evidence in
        ``docs/state/TASK-FIX-AC006SMOKE-LG/captured_aimessage_probe_c.json``
        under ``content_blocks_property``.
        """
        msg = _FakeMessage(
            content="canonical verdict only, no reasoning inline",
            content_blocks=[
                {
                    "type": "reasoning",
                    "id": "rs_normalised",
                    "extras": {
                        "content": [
                            {
                                "type": "reasoning_text",
                                "text": "normalised extras content reasoning",
                            }
                        ],
                        "encrypted_content": "",
                        "status": "completed",
                    },
                },
                {
                    "type": "text",
                    "text": "canonical verdict only, no reasoning inline",
                },
            ],
        )
        result = {"messages": [msg]}
        assert extract_last_ai_reasoning(result) == "normalised extras content reasoning"


class _FakeMessage:
    """Duck-typed stand-in for a LangChain message *object* (not a dict).

    Lets the extractor unit tests exercise object-shaped branches —
    notably the typed ``content_blocks`` property fallback — that a plain
    dict message cannot reach. Mirrors the duck-typing the extractor relies
    on (``.content`` / ``.additional_kwargs`` / ``.content_blocks``).
    """

    def __init__(
        self,
        content: Any = "",
        additional_kwargs: dict[str, Any] | None = None,
        content_blocks: list[Any] | None = None,
    ) -> None:
        self.content = content
        self.additional_kwargs = additional_kwargs or {}
        # Only set the attribute when provided, so ``getattr(msg,
        # "content_blocks", None)`` returns None (property absent) otherwise.
        if content_blocks is not None:
            self.content_blocks = content_blocks


class TestExtractorShapeUnits:
    """TASK-FIX-COACHBUDG01-LG: direct unit coverage of the extractor shape
    branches that the harness-driven tests above do not reach — the typed
    ``content_blocks`` fallback (AC-001 third bullet), the multi-fragment join
    (AC-003), the dict-message list-content path, and the role gate.
    """

    def test_typed_content_blocks_form_surfaces_reasoning(self) -> None:
        """AC-001 (typed ``content_blocks`` form): when raw ``content`` is a
        string but the typed ``content_blocks`` property exposes a reasoning
        block, the reasoning is still recovered (defensive fallback for client
        versions that surface reasoning only on the typed view).
        """
        msg = _FakeMessage(
            content="verdict text only, no reasoning inline",
            content_blocks=[
                {"type": "reasoning", "reasoning": "typed content_blocks reasoning"},
                {"type": "text", "text": "verdict text only, no reasoning inline"},
            ],
        )
        result = {"messages": [msg]}
        assert extract_last_ai_reasoning(result) == "typed content_blocks reasoning"

    def test_multiple_reasoning_blocks_join_with_newline(self) -> None:
        """AC-003: multiple reasoning fragments on one message join with a
        single newline; the canonical text path ignores them all.
        """
        msg = _FakeMessage(
            content=[
                {"type": "reasoning", "text": "first fragment"},
                {"type": "reasoning", "text": "second fragment"},
                {"type": "output_text", "text": "the verdict"},
            ]
        )
        result = {"messages": [msg]}
        assert extract_last_ai_reasoning(result) == "first fragment\nsecond fragment"
        assert extract_last_ai_message(result) == "the verdict"

    def test_dict_message_list_content_text_and_reasoning(self) -> None:
        """A plain *dict* assistant message (not an object) with list content
        is handled on both paths: ``extract_last_ai_message`` returns the
        ``output_text`` verdict, ``extract_last_ai_reasoning`` returns the
        ``summary`` reasoning.
        """
        result = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "reasoning",
                            "summary": [{"type": "summary_text", "text": "dict-list reasoning"}],
                        },
                        {"type": "output_text", "text": "dict-list verdict"},
                    ],
                }
            ]
        }
        assert extract_last_ai_message(result) == "dict-list verdict"
        assert extract_last_ai_reasoning(result) == "dict-list reasoning"

    def test_top_level_dict_reasoning_content_surfaces(self) -> None:
        """The pre-existing chat-completions dict variant — ``reasoning_content``
        at the top level of a plain dict message — still surfaces (precedence
        rung 5).
        """
        result = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "top-level reasoning",
                }
            ]
        }
        assert extract_last_ai_reasoning(result) == "top-level reasoning"

    def test_non_ai_dict_message_never_leaks_reasoning(self) -> None:
        """The role gate holds: a ``user`` dict message carrying a
        ``reasoning_content`` key yields no reasoning (it is not an AI turn).
        """
        result = {
            "messages": [
                {
                    "role": "user",
                    "content": "hi",
                    "reasoning_content": "must never be surfaced",
                }
            ]
        }
        assert extract_last_ai_reasoning(result) == ""


# ---------------------------------------------------------------------------
# TASK-FIX-CTOUT01: cooperative cancellation under LangGraph substrate
# ---------------------------------------------------------------------------


class TestCancelLangGraphHarness:
    """Verifies LangGraphHarness.cancel() unblocks the in-flight ainvoke.

    Under SDK substrate the cancellation contract is honoured by
    SIGTERM-ing the Claude CLI subprocess (TASK-FIX-ASPF-004); under
    LangGraph there is no subprocess — the LLM HTTP request is made
    directly from the Python process via langchain_anthropic /
    langchain_openai. The only way to abort the in-flight call is to
    cancel the asyncio Task wrapping ``agent.ainvoke``.

    These tests use mocked ``agent.ainvoke`` so we control the suspend
    behaviour deterministically without crossing the substrate
    boundary.
    """

    def test_cancel_is_noop_when_no_active_invoke(self) -> None:
        """A fresh harness with no in-flight invoke has nothing to cancel."""
        harness = LangGraphHarness(model="ignored")

        # Synchronous (no event-loop) call to confirm safe defaults.
        async def _run() -> None:
            assert harness._ainvoke_task is None
            await harness.cancel()
            assert harness._ainvoke_task is None

        asyncio.run(_run())

    def test_cancel_propagates_to_in_flight_ainvoke_task(self) -> None:
        """When ainvoke is hanging, cancel() makes it raise CancelledError
        which the harness re-raises so the orchestrator sees the
        cancellation verbatim (matching SDK harness behaviour)."""
        harness = LangGraphHarness(model="ignored")

        # ainvoke that hangs forever — simulates the LLM HTTP request
        # the orchestrator is timing out on.
        ainvoke_started = asyncio.Event()

        async def hanging_ainvoke(input_data: dict) -> dict:
            ainvoke_started.set()
            # Wait for cancellation. Any long sleep would do; using
            # Future().wait would be equivalent.
            await asyncio.sleep(3600)
            return {"messages": []}

        fake_agent = MagicMock(name="hanging_deep_agent")
        fake_agent.ainvoke = hanging_ainvoke

        async def _scenario() -> tuple[BaseException | None, bool]:
            with patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ):

                async def _drain_invoke() -> None:
                    async for _ in harness.invoke(
                        prompt="hi",
                        role="player",
                        tools=[],
                        cwd=Path.cwd(),
                        timeout_seconds=30,
                    ):
                        pass

                invoke_task = asyncio.create_task(_drain_invoke())
                # Wait until ainvoke is actually suspended so
                # _ainvoke_task is set.
                await ainvoke_started.wait()
                # Give the generator one more loop tick to assign.
                await asyncio.sleep(0)
                # cancel() must observe a live task and cancel it.
                assert harness._ainvoke_task is not None
                assert not harness._ainvoke_task.done()
                cancelled_task = harness._ainvoke_task

                await harness.cancel()

                # invoke() should exit via the CancelledError re-raise
                # path within the deadline; we cap at 5s to keep CI
                # snappy independent of the 30s default deadline.
                try:
                    await asyncio.wait_for(invoke_task, timeout=5.0)
                    caught = None
                except asyncio.CancelledError as exc:
                    caught = exc
                except Exception as exc:  # noqa: BLE001
                    caught = exc
                return caught, cancelled_task.cancelled()

        caught, was_cancelled = asyncio.run(_scenario())

        # The cancelled ainvoke task must be in a cancelled state.
        assert was_cancelled is True
        # invoke() must propagate the cancellation as CancelledError —
        # not wrap it into a LangGraphHarnessError, since the
        # orchestrator dispatches on the bare CancelledError type
        # (matches SDK harness behaviour at sdk_harness.py:410-419).
        assert isinstance(caught, asyncio.CancelledError), (
            f"Expected CancelledError to propagate to the consumer of "
            f"invoke(), got {type(caught).__name__ if caught else 'None'}: "
            f"{caught}"
        )
        # Instance handle cleared after invoke()'s finally runs.
        assert harness._ainvoke_task is None

    def test_cancel_logs_warning_when_task_ignores_cancellation(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If the in-flight task ignores cancel for longer than the
        deadline, cancel() logs a WARNING and returns rather than
        hanging the orchestrator forever.

        Driven at the cancel()-API level rather than through invoke():
        we build a Task whose coroutine catches CancelledError and
        keeps running, assign it to ``harness._ainvoke_task`` directly,
        and call ``cancel()``. This exercises the deadline-then-warn
        branch deterministically without coupling to invoke()'s
        unwind path (which the stubborn task would prevent from ever
        completing).
        """
        # Tighten the deadline to 0.1s so the test wallclock-cost is
        # bounded. Implementation parses the env var as float, so
        # sub-second deadlines are valid; production uses integer
        # seconds (default 30).
        monkeypatch.setenv("GUARDKIT_HARNESS_CANCEL_DEADLINE", "0.1")

        harness = LangGraphHarness(model="ignored")

        async def _scenario() -> list[Any]:
            # stubborn_coro: ignore the FIRST cancellation (the one
            # cancel() triggers via task.cancel()), then exit on the
            # second so asyncio.run()'s shutdown sweep can complete.
            # This shape exercises the cancel() deadline-expiry branch
            # without leaving a task on the event loop that prevents
            # clean shutdown.
            ignore_count = 0

            async def stubborn_coro() -> None:
                nonlocal ignore_count
                while True:
                    try:
                        await asyncio.sleep(3600)
                    except asyncio.CancelledError:
                        ignore_count += 1
                        if ignore_count >= 2:
                            # Second cancel — give up so the loop
                            # shutdown can complete.
                            raise
                        continue

            harness._ainvoke_task = asyncio.create_task(stubborn_coro())
            # Yield so the task starts running.
            await asyncio.sleep(0)

            with caplog.at_level(
                "WARNING",
                logger="guardkitfactory.harness.langgraph_harness",
            ):
                await harness.cancel()

            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            # Final cancel + await: stubborn_coro raises CancelledError
            # on the second attempt, so the task settles cleanly here.
            task = harness._ainvoke_task
            harness._ainvoke_task = None
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
            return warnings

        warnings = asyncio.run(_scenario())

        deadline_warnings = [w for w in warnings if "did not honour cancellation" in w.message]
        assert deadline_warnings, (
            "Expected a WARNING from LangGraphHarness.cancel when the "
            "in-flight task ignores the cancellation past the deadline. "
            f"Got warnings: {[w.message for w in warnings]}"
        )


# ---------------------------------------------------------------------------
# TASK-FIX-LGACLOSE: async-generator finalisation on cancel
#
# CTOUT01 wrapped ``agent.ainvoke`` in an asyncio.Task so :meth:`cancel`
# could propagate ``CancelledError`` — but it left ``invoke``'s own
# async generator un-finalised on the cancel path: a consumer abandoned
# mid-iteration left an orphaned ``async_generator_athrow`` / pending
# ainvoke task that the GC tried to close at interpreter shutdown
# ("coroutine method 'aclose' of 'LangGraphHarness.invoke' was never
# awaited" RuntimeWarning + "Task was destroyed but it is pending"). The
# defensive outer try/finally in ``invoke`` now finalises the in-flight
# task on EVERY exit, including ``GeneratorExit`` thrown by a consumer's
# ``aclose()``. Pairs with the consumer-side ``aclosing()`` wrap in
# guardkit ``agent_invoker`` (AC-1); these tests cover the harness half
# (AC-2) and the falsifier (AC-3).
# ---------------------------------------------------------------------------


class TestAcloseFinalisation:
    def test_aclose_midstream_clears_handle_and_leaves_no_lingering_task(
        self,
    ) -> None:
        """AC-2/AC-3: closing the generator mid-stream finalises it.

        Drive ``invoke`` to its first yield (so the generator is
        suspended at a ``yield``), then ``aclose()`` it as the
        consumer-side ``aclosing()`` does on cancel. The instance handle
        must be cleared and no pending task may linger on the loop.
        """
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent(final_text="hi")

        async def _scenario() -> tuple[Any, list[Any]]:
            with patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ):
                stream = harness.invoke(
                    prompt="hi",
                    role="player",
                    tools=[],
                    cwd=Path.cwd(),
                    timeout_seconds=30,
                )
                # Suspend the generator at its first yield.
                first = await stream.__anext__()
                assert isinstance(first, AssistantMessageEvent)

                # Finalise mid-stream — the GeneratorExit path the
                # consumer's aclosing() exercises on cancel.
                await stream.aclose()

                lingering = [
                    t
                    for t in asyncio.all_tasks()
                    if t is not asyncio.current_task() and not t.done()
                ]
                return harness._ainvoke_task, lingering

        handle, lingering = asyncio.run(_scenario())

        assert handle is None
        assert lingering == [], f"aclose() mid-stream left lingering tasks: {lingering}"

    def test_aclose_midstream_emits_no_never_awaited_warning(self) -> None:
        """AC-3 falsifier: no 'aclose ... never awaited' RuntimeWarning."""
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent(final_text="hi")

        async def _scenario() -> None:
            with patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ):
                stream = harness.invoke(
                    prompt="hi",
                    role="player",
                    tools=[],
                    cwd=Path.cwd(),
                    timeout_seconds=30,
                )
                await stream.__anext__()
                await stream.aclose()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asyncio.run(_scenario())

        never_awaited = [
            w
            for w in caught
            if "never awaited" in str(w.message) or "async_generator_athrow" in str(w.message)
        ]
        assert not never_awaited, (
            "Expected no 'aclose was never awaited' RuntimeWarning after a "
            f"mid-stream aclose; got: {[str(w.message) for w in never_awaited]}"
        )

    def test_consumer_cancel_during_ainvoke_cancels_inflight_task(self) -> None:
        """AC-2: consumer cancelled mid-``await ainvoke`` cancels the task.

        This exercises the outer ``finally``'s pending-task branch via the
        real trigger from the bug report — the consumer (guardkit
        ``agent_invoker``) iterating the generator is cancelled by the
        feature timeout while ``agent.ainvoke`` is still in flight. The
        in-flight task must end cancelled and the handle cleared, with no
        lingering task on the loop.
        """
        harness = LangGraphHarness(model="ignored")
        ainvoke_started = asyncio.Event()

        async def hanging_ainvoke(_input: dict) -> dict:
            ainvoke_started.set()
            await asyncio.sleep(3600)
            return {"messages": []}

        fake_agent = MagicMock(name="hanging_deep_agent")
        fake_agent.ainvoke = hanging_ainvoke

        async def _scenario() -> tuple[Any, Any, list[Any]]:
            with patch(
                "guardkitfactory.harness.langgraph_harness.create_deep_agent",
                return_value=fake_agent,
            ):
                stream = harness.invoke(
                    prompt="hi",
                    role="player",
                    tools=[],
                    cwd=Path.cwd(),
                    timeout_seconds=30,
                )

                async def _consume() -> None:
                    async for _ in stream:
                        pass

                consumer = asyncio.create_task(_consume())
                await ainvoke_started.wait()
                await asyncio.sleep(0)

                inner = harness._ainvoke_task
                assert inner is not None and not inner.done()

                consumer.cancel()
                with suppress(asyncio.CancelledError):
                    await consumer

                # Let the cancelled in-flight task settle.
                for _ in range(5):
                    await asyncio.sleep(0)

                lingering = [
                    t
                    for t in asyncio.all_tasks()
                    if t is not asyncio.current_task() and not t.done()
                ]
                return inner, harness._ainvoke_task, lingering

        inner, handle, lingering = asyncio.run(_scenario())

        assert inner.cancelled(), (
            "The in-flight ainvoke task should have been cancelled by "
            "invoke()'s defensive finally when the consumer was cancelled "
            "mid-await."
        )
        assert handle is None
        assert lingering == [], f"consumer-cancel left lingering tasks: {lingering}"
