"""Unit tests for :class:`guardkitfactory.harness.LangGraphHarness` (TASK-HMIG-001B).

Covers AC-008 + the cross-repo subclass relation from AC-001:

* Happy path: stub model + empty tool list + ``invoke()`` returns a final
  assistant message in the event stream.
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
import json
import warnings
from contextlib import suppress
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import langchain_openai
import pytest
from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    HarnessAdapter,
    ResultMessageEvent,
    ToolResultEvent,
    ToolUseEvent,
)

from guardkitfactory import LangGraphHarness, LangGraphHarnessError
from guardkitfactory.harness.backend_config import build_autobuild_backend
from guardkitfactory.harness.extractors import (
    extract_last_ai_message,
    extract_last_ai_reasoning,
)
from guardkitfactory.harness.langgraph_harness import (
    _player_context_prompt,
    _system_prompt_for_role,
)
from guardkitfactory.harness.player_config import build_player_config

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _drain(harness: LangGraphHarness, prompt: str = "hi") -> list[Any]:
    """Drive ``harness.invoke(...)`` to completion and return the collected events."""

    async def _collect() -> list[Any]:
        events: list[Any] = []
        async for event in harness.invoke(
            prompt=prompt,
            role="coach",
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

        # Without the pinned search programs, as on GitHub's runner: where
        # they are installed the Coach also gets the code search tools.
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ) as create_mock, patch(
            "guardkitfactory.code_search.available",
            return_value=(False, "not installed in this test"),
        ):
            events = _drain(harness, prompt="say hi")

        # The DeepAgent constructor was called with the harness-bound
        # parameters — confirms AC-003 wiring.
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs
        assert kwargs["model"] == "ignored-stub-model"
        assert kwargs["tools"] == []
        assert kwargs["backend"] is None
        assert kwargs["permissions"] is None
        assert "write_todos" in kwargs["system_prompt"]
        assert "Review the implementation independently" in kwargs["system_prompt"]
        assert len(kwargs["middleware"]) == 1
        assert type(kwargs["middleware"][0]).__name__ == "TodoListMiddleware"

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

    def test_player_context_uses_declared_project_inputs_without_layout_defaults(
        self, tmp_path: Path
    ) -> None:
        worktree = tmp_path / "task worktree with spaces"
        (worktree / "docs").mkdir(parents=True)
        (worktree / "docs" / "WORKFLOW.md").write_text("# Repository workflow\n")
        (worktree / "verification").mkdir()
        profile = tmp_path / "dcode-profile"
        profile.mkdir()
        config = build_player_config(
            cwd=worktree,
            dcode_home=profile,
            repository_instructions=["docs/WORKFLOW.md"],
            declared_commands=[("test", "./checks/run-all --exact")],
            protected_paths=["verification"],
        )

        prompt = _player_context_prompt(config)

        assert f"assigned task worktree is exactly: {worktree}" in prompt
        assert "# Repository workflow" in prompt
        assert "./checks/run-all --exact" in prompt
        assert "verification" in prompt
        assert "src/example.py" not in prompt
        assert "tests/acceptance" not in prompt

    def test_coach_prompt_is_unchanged_and_has_no_player_worktree_addition(
        self, tmp_path: Path
    ) -> None:
        worktree = tmp_path / "coach worktree with spaces"
        worktree.mkdir()
        harness = LangGraphHarness(model="ignored-stub-model")

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        ) as create_mock:
            harness._create_agent(
                role="coach", cwd=worktree, resolved_model="ignored-stub-model"
            )

        system_prompt = create_mock.call_args.kwargs["system_prompt"]
        assert system_prompt == _system_prompt_for_role("coach")
        assert "assigned task worktree is exactly" not in system_prompt
        assert str(worktree) not in system_prompt

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
        assert "coach" in msg  # the role tag is part of the attribution

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
            role="coach",
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


def _fake_resolve_model(*_args: Any, **_kwargs: Any) -> Any:
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
                "langchain_openai.ChatOpenAI",
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
                "langchain_openai.ChatOpenAI",
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
            # _drain defaults to role="coach"
            _drain(harness)

        assert captured["role"] == "coach", (
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
                        role="coach",
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
                    role="coach",
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
                    role="coach",
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
                    role="coach",
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


# ---------------------------------------------------------------------------
# TASK-FIX-SPECINVOKE01: substrate-aware model-activity callback
# ---------------------------------------------------------------------------


class TestModelActivityCallback:
    """``on_model_activity`` is surfaced as a LangChain callback.

    The orchestrator's no-model-activity specialist watchdog
    (``guardkit.orchestrator.specialist_invocations``) keys on an activity
    clock that the consumer loop only refreshes when a ``HarnessEvent`` is
    *yielded* — but this harness awaits the whole ``agent.ainvoke()`` before
    yielding any event, so the clock froze for the entire run and the watchdog
    false-killed live, model-active specialists at 150 s (FEAT-9DDE run 3).
    Threading ``on_model_activity`` into ``ainvoke``'s ``config["callbacks"]``
    restores a faithful signal: every LLM/tool boundary pings the sink.
    """

    def test_constructor_stores_on_model_activity(self) -> None:
        cb = lambda: None  # noqa: E731
        harness = LangGraphHarness(model="ignored", on_model_activity=cb)
        assert harness.on_model_activity is cb

    def test_default_on_model_activity_is_none_and_config_is_none(self) -> None:
        """Unset → ``None`` config so the single-arg ``ainvoke`` shape (and the
        happy-path test that asserts it) is preserved byte-for-byte."""
        harness = LangGraphHarness(model="ignored")
        assert harness.on_model_activity is None
        assert harness._build_invoke_config() is None

    def test_invoke_threads_callback_handler_into_ainvoke_config(self) -> None:
        pings: list[int] = []
        harness = LangGraphHarness(
            model="ignored", on_model_activity=lambda: pings.append(1)
        )
        fake_agent = _make_fake_agent()

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            _drain(harness, prompt="run tests")

        config = fake_agent.ainvoke.await_args.kwargs.get("config")
        assert config is not None, "ainvoke must receive a config when a sink is set"
        assert "callbacks" in config
        handler = config["callbacks"][0]
        assert type(handler).__name__ == "_ModelActivityCallbackHandler"

        # Every model/tool boundary pings the sink — this is the substrate-
        # aware activity signal the watchdog consumes.
        handler.on_chat_model_start()
        handler.on_llm_start()
        handler.on_llm_new_token()
        handler.on_llm_end()
        handler.on_tool_start()
        handler.on_tool_end()
        assert len(pings) == 6

    def test_callback_handler_swallows_sink_exceptions(self) -> None:
        """A misbehaving activity sink must never abort the agent run."""
        from guardkitfactory.harness.langgraph_harness import (
            _ModelActivityCallbackHandler,
        )

        def boom() -> None:
            raise RuntimeError("activity sink is down")

        handler = _ModelActivityCallbackHandler(boom)
        # Must not raise.
        handler.on_chat_model_start()
        handler.on_llm_end()
        handler.on_tool_start()


# ---------------------------------------------------------------------------
# TASK-FIX-COACHTRES01: ToolMessage → ToolResultEvent (substrate parity)
# ---------------------------------------------------------------------------


def _make_fake_agent_with_tool_result(
    tool_content: Any = "45 passed in 0.13s",
    status: str = "success",
    tool_call_id: str = "tc-1",
    final_text: str = "done",
) -> MagicMock:
    """Fake agent whose result history contains a ToolMessage.

    Mirrors a real DeepAgents run where the agent calls a tool (e.g. the
    execute/Bash tool running pytest) and the tool's output lands in the
    message history as a ToolMessage before the final AIMessage.
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    fake = MagicMock(name="fake_deep_agent_tool_result")
    fake.ainvoke = AsyncMock(
        return_value={
            "messages": [
                HumanMessage(content="run the tests"),
                AIMessage(
                    content="I'll run pytest.",
                    tool_calls=[
                        {"name": "execute", "args": {"cmd": "pytest"}, "id": tool_call_id}
                    ],
                ),
                ToolMessage(
                    content=tool_content,
                    tool_call_id=tool_call_id,
                    status=status,
                ),
                AIMessage(content=final_text),
            ]
        }
    )
    return fake


class TestToolResultParity:
    """The LangGraph harness surfaces ToolMessage output as ToolResultEvent.

    Closes the FEAT-HARV narration-capture defect on the LangGraph substrate
    so the Coach independent-test path captures real pytest stdout, matching
    the SDK harness's UserMessage/ToolResultBlock emission.
    """

    def test_tool_message_yields_tool_result_event(self) -> None:
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent_with_tool_result(
            tool_content="45 passed in 0.13s", status="success", tool_call_id="tc-7"
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness, prompt="run tests")

        results = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(results) == 1
        assert results[0].content == "45 passed in 0.13s"
        assert results[0].is_error is False
        assert results[0].tool_use_id == "tc-7"

        # ToolResultEvent precedes the terminal ResultMessageEvent so the
        # Coach consumer (which breaks on ResultMessageEvent) captures it.
        idx_result = next(
            i for i, e in enumerate(events) if isinstance(e, ToolResultEvent)
        )
        idx_terminal = next(
            i for i, e in enumerate(events) if isinstance(e, ResultMessageEvent)
        )
        assert idx_result < idx_terminal

    def test_tool_message_error_status_maps_to_is_error(self) -> None:
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent_with_tool_result(
            tool_content="boom: command not found", status="error"
        )

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        results = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(results) == 1
        assert results[0].is_error is True

    def test_no_tool_message_yields_no_tool_result_event(self) -> None:
        """The plain happy-path agent (no ToolMessage) emits no ToolResultEvent."""
        harness = LangGraphHarness(model="ignored")
        fake_agent = _make_fake_agent(final_text="approve")

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            events = _drain(harness)

        assert not [e for e in events if isinstance(e, ToolResultEvent)]


# ---------------------------------------------------------------------------
# Deep Agents 0.7.14 real graph with deterministic Chat Completions transport
# ---------------------------------------------------------------------------


def test_real_graph_uses_chat_completions_prompt_and_runtime_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the compiled graph and its tools without model or network I/O."""
    target = tmp_path / "runtime.txt"
    calls = [
        (
            "write_todos",
            {"todos": [{"content": "exercise runtime tools", "status": "in_progress"}]},
        ),
        ("write_file", {"file_path": str(target), "content": "alpha\n"}),
        ("read_file", {"file_path": str(target), "offset": 0, "limit": 20}),
        (
            "edit_file",
            {
                "file_path": str(target),
                "old_string": "alpha",
                "new_string": "beta",
                "replace_all": False,
            },
        ),
        (
            "grep",
            {
                "pattern": "beta",
                "path": str(tmp_path),
                "glob": "*.txt",
                "output_mode": "content",
            },
        ),
        ("glob", {"pattern": "*.txt", "path": str(tmp_path)}),
        ("ls", {"path": str(tmp_path)}),
        ("execute", {"command": "printf runtime-ok"}),
        ("delete", {"file_path": str(target)}),
    ]
    requests: list[tuple[str, dict[str, Any]]] = []

    def _response(message: dict[str, Any], finish_reason: str) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-{len(requests)}",
                "object": "chat.completion",
                "created": 1,
                "model": "flash-next-t06",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            },
        )

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        index = len(requests) - 1
        if index < len(calls):
            name, arguments = calls[index]
            return _response(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call-{index}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return _response(
            {
                "role": "assistant",
                "content": '{"verdict":"approve","findings":[]}',
            },
            "stop",
        )

    transport = httpx.MockTransport(_handler)
    real_constructor = langchain_openai.ChatOpenAI

    def _chat_model(**kwargs: Any) -> Any:
        for key in ("http_client", "http_async_client", "http_socket_options"):
            kwargs.pop(key, None)
        return real_constructor(
            **kwargs,
            http_client=httpx.Client(transport=transport),
            http_async_client=httpx.AsyncClient(transport=transport),
            http_socket_options=(),
            max_retries=0,
        )

    monkeypatch.setenv("OPENAI_BASE_URL", "http://model.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")
    harness = LangGraphHarness(
        model="openai:flash-next-t06",
        backend=build_autobuild_backend(tmp_path),
        recursion_limit=80,
    )

    async def _collect() -> list[Any]:
        events: list[Any] = []
        with patch("langchain_openai.ChatOpenAI", side_effect=_chat_model):
            async for event in harness.invoke(
                prompt="Exercise each runtime tool, then return the coach verdict JSON.",
                role="coach",
                tools=[],
                cwd=tmp_path,
                timeout_seconds=30,
            ):
                events.append(event)
        return events

    events = asyncio.run(_collect())

    assert len(requests) == len(calls) + 1
    assert {path for path, _ in requests} == {"/v1/chat/completions"}
    assert all("/responses" not in path for path, _ in requests)
    assert all(body["model"] == "flash-next-t06" for _, body in requests)

    first_body = requests[0][1]
    tool_names = {tool["function"]["name"] for tool in first_body["tools"]}
    assert {
        "write_todos",
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "glob",
        "grep",
        "execute",
        "task",
    } <= tool_names
    system_text = json.dumps(first_body["messages"][0]["content"])
    assert "write_todos" in system_text
    assert "project-declared protected paths" in system_text
    assert "tests/acceptance" not in system_text
    assert "structured verdict" in system_text

    use_events = [event for event in events if isinstance(event, ToolUseEvent)]
    assert [event.name for event in use_events] == [name for name, _ in calls]
    result_text = "\n".join(
        str(event.content)
        for event in events
        if isinstance(event, ToolResultEvent)
    )
    assert "beta" in result_text
    assert "runtime-ok" in result_text
    assert not target.exists()

    assistant = next(
        event for event in events if isinstance(event, AssistantMessageEvent)
    )
    assert json.loads(assistant.text) == {"verdict": "approve", "findings": []}


def test_deep_agent_temporary_checkpoint_recovers_prior_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pinned LangGraph checkpointing restores messages for one thread."""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware
    from langgraph.checkpoint.memory import InMemorySaver

    requests: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        turn = len(requests)
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-checkpoint-{turn}",
                "object": "chat.completion",
                "created": 1,
                "model": "flash-next-t06",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"remembered-turn-{turn}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "total_tokens": 7,
                },
            },
        )

    transport = httpx.MockTransport(_handler)
    model = langchain_openai.ChatOpenAI(
        model="flash-next-t06",
        api_key="local-test-key",
        base_url="http://model.test/v1",
        use_responses_api=False,
        http_client=httpx.Client(transport=transport),
        http_async_client=httpx.AsyncClient(transport=transport),
        http_socket_options=(),
        max_retries=0,
    )
    graph = create_deep_agent(
        model=model,
        tools=[],
        middleware=[TodoListMiddleware()],
        system_prompt="Remember prior turns in this temporary test thread.",
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "checkpoint-test"}}

    async def _run() -> Any:
        await graph.ainvoke(
            {"messages": [{"role": "user", "content": "first-turn-marker"}]},
            config=config,
        )
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": "second-turn-marker"}]},
            config=config,
        )
        state = await graph.aget_state(config)
        return result, state

    result, state = asyncio.run(_run())

    assert len(requests) == 2
    second_request = json.dumps(requests[1]["messages"])
    assert "first-turn-marker" in second_request
    assert "remembered-turn-1" in second_request
    assert "second-turn-marker" in second_request
    assert result["messages"][-1].content == "remembered-turn-2"
    state_text = "\n".join(str(message.content) for message in state.values["messages"])
    assert "first-turn-marker" in state_text
    assert "remembered-turn-2" in state_text


def test_real_graph_compaction_uses_chat_completions_and_worktree_offload(
    tmp_path: Path,
) -> None:
    """Actual compaction uses the local transport and writes history under root."""
    from deepagents import create_deep_agent
    from deepagents.middleware.summarization import SummarizationMiddleware

    requests: list[tuple[str, dict[str, Any]]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        content = "compact summary" if len(requests) == 1 else "final answer"
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-compact-{len(requests)}",
                "object": "chat.completion",
                "created": 1,
                "model": "flash-next-t06",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        )

    transport = httpx.MockTransport(_handler)
    model = langchain_openai.ChatOpenAI(
        model="flash-next-t06",
        api_key="local-test-key",
        base_url="http://model.test/v1",
        use_responses_api=False,
        http_client=httpx.Client(transport=transport),
        http_async_client=httpx.AsyncClient(transport=transport),
        http_socket_options=(),
        max_retries=0,
    )
    backend = build_autobuild_backend(tmp_path)
    compaction = SummarizationMiddleware(
        model=model,
        backend=backend,
        trigger=("messages", 10),
        keep=("messages", 2),
    )
    graph = create_deep_agent(
        model=model,
        tools=[],
        middleware=[compaction],
        backend=backend,
        system_prompt="Complete the task after compacting old context.",
    )
    messages: list[dict[str, str]] = []
    for index in range(12):
        messages.extend(
            [
                {
                    "role": "user",
                    "content": f"user-{index}-marker " + ("x" * 80),
                },
                {
                    "role": "assistant",
                    "content": f"assistant-{index}-marker " + ("y" * 80),
                },
            ]
        )

    result = asyncio.run(graph.ainvoke({"messages": messages}))

    assert result["messages"][-1].content == "final answer"
    assert len(requests) == 2
    assert [path for path, _ in requests] == [
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]
    assert "Context Extraction Assistant" in json.dumps(requests[0][1]["messages"])
    assert "compact summary" in json.dumps(requests[1][1]["messages"])

    # Offloaded to the private folder, never into the worktree (14 October 2026).
    assert not (tmp_path / "conversation_history").exists()
    history_files = list(
        (Path(backend.artifacts_root) / "conversation_history").glob("session_*.md")
    )
    assert len(history_files) == 1
    history = history_files[0].read_text()
    assert "user-0-marker" in history
    assert "assistant-0-marker" in history
    assert not history_files[0].is_relative_to(tmp_path)


def test_prebuilt_responses_model_uses_chat_completions_for_synthesis(
    tmp_path: Path,
) -> None:
    """Injected local synthesis models retain grammar on Chat Completions."""
    requests: list[tuple[str, dict[str, Any]]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-synthesis",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "{}"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 1,
                    "total_tokens": 6,
                },
            },
        )

    transport = httpx.MockTransport(_handler)
    model = langchain_openai.ChatOpenAI(
        model="local-coach-adapter",
        api_key="local-test-key",
        base_url="http://model.test/v1",
        use_responses_api=True,
        temperature=0.27,
        max_tokens=777,
        http_client=httpx.Client(transport=transport),
        http_async_client=httpx.AsyncClient(transport=transport),
        http_socket_options=(),
        max_retries=0,
    )
    harness = LangGraphHarness(model=model)

    async def _collect() -> list[Any]:
        return [
            event
            async for event in harness.invoke_synthesis(
                prompt="Return a verdict.",
                role="coach",
                grammar='root ::= "{}"',
                cwd=tmp_path,
                timeout_seconds=5,
            )
        ]

    events = asyncio.run(_collect())

    assert {path for path, _ in requests} == {"/v1/chat/completions"}
    body = requests[0][1]
    assert body["model"] == "local-coach-adapter"
    assert body["grammar"] == 'root ::= "{}"'
    assert body["temperature"] == 0.27
    assert body.get("max_completion_tokens", body.get("max_tokens")) == 777
    assert "tools" not in body
    assert any(
        isinstance(event, AssistantMessageEvent) and event.text == "{}"
        for event in events
    )


# ---------------------------------------------------------------------------
# 13 October 2026 (proof defect 5): a read-only request binds only the
# requested read and search tools. Real compiled graph, scripted model over a
# fake HTTP transport that records the tool schemas sent on every request and
# plays back chosen tool calls, whether or not they were offered.
# ---------------------------------------------------------------------------

_FULL_COACH_TOOLS = {
    "write_todos",
    "ls",
    "read_file",
    "write_file",
    "edit_file",
    "delete",
    "glob",
    "grep",
    "execute",
    "task",
}
_REFUSED_PATH = Path("/tmp/count-check/build.mjs")


def _available_code_search_tools() -> set[str]:
    """The code tools a worktree binding offers with no language server
    declaration passed (code_references needs one)."""
    from guardkitfactory import code_search
    from guardkitfactory.harness.code_search_tools import DECLARATION_TOOL_NAMES, TOOL_NAMES

    ready, _why = code_search.available()
    return set(TOOL_NAMES) - set(DECLARATION_TOOL_NAMES) if ready else set()


def _review_worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "counter.mjs").write_text(
        "export function countCreated(rows) {\n"
        "  return rows.filter((row) => row.created).length;\n"
        "}\n"
    )
    return worktree


def _run_scripted_graph(
    monkeypatch: pytest.MonkeyPatch,
    worktree: Path,
    *,
    tools: list[str],
    calls: list[tuple[str, dict[str, Any]]],
    role: str = "coach",
    backend: Any = None,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Run one real graph turn; return (request bodies, harness events)."""

    bodies: list[dict[str, Any]] = []

    def _response(message: dict[str, Any], finish_reason: str) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-{len(bodies)}",
                "object": "chat.completion",
                "created": 1,
                "model": "flash-next-t06",
                "choices": [
                    {"index": 0, "message": message, "finish_reason": finish_reason}
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            },
        )

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        index = len(bodies) - 1
        if index < len(calls):
            name, arguments = calls[index]
            return _response(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call-{index}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return _response(
            {"role": "assistant", "content": '{"verdict":"approve","findings":[]}'},
            "stop",
        )

    transport = httpx.MockTransport(_handler)
    real_constructor = langchain_openai.ChatOpenAI

    def _chat_model(**kwargs: Any) -> Any:
        for key in ("http_client", "http_async_client", "http_socket_options"):
            kwargs.pop(key, None)
        return real_constructor(
            **kwargs,
            http_client=httpx.Client(transport=transport),
            http_async_client=httpx.AsyncClient(transport=transport),
            http_socket_options=(),
            max_retries=0,
        )

    monkeypatch.setenv("OPENAI_BASE_URL", "http://model.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")
    harness = LangGraphHarness(
        model="openai:flash-next-t06",
        backend=backend if backend is not None else build_autobuild_backend(worktree),
        recursion_limit=80,
    )

    async def _collect() -> list[Any]:
        events: list[Any] = []
        with patch("langchain_openai.ChatOpenAI", side_effect=_chat_model):
            async for event in harness.invoke(
                prompt="Review the change and return the verdict JSON.",
                role=role,
                tools=tools,
                cwd=worktree,
                timeout_seconds=30,
            ):
                events.append(event)
        return events

    events = asyncio.run(_collect())
    return bodies, events


def _bound(body: dict[str, Any]) -> set[str]:
    return {tool["function"]["name"] for tool in body.get("tools", [])}


def _results_by_call(events: list[Any]) -> dict[str, Any]:
    return {
        event.tool_use_id: event
        for event in events
        if isinstance(event, ToolResultEvent)
    }


def test_read_only_request_binds_only_the_requested_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _review_worktree(tmp_path)
    bodies, _events = _run_scripted_graph(
        monkeypatch,
        worktree,
        tools=["Read", "Search", "Grep"],
        calls=[("read_file", {"file_path": str(worktree / "counter.mjs")})],
    )

    assert len(bodies) == 2
    expected = {"ls", "read_file", "glob", "grep"} | _available_code_search_tools()
    for body in bodies:
        bound = _bound(body)
        assert bound == expected
        assert not bound & {"write_file", "edit_file", "delete", "execute", "write_todos", "task"}
    system_text = json.dumps(bodies[0]["messages"][0]["content"])
    assert "read-only" in system_text
    assert "use write_todos" not in system_text


def test_read_only_reviewer_can_still_read_and_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _review_worktree(tmp_path)
    _bodies, events = _run_scripted_graph(
        monkeypatch,
        worktree,
        tools=["Read", "Search", "Grep"],
        calls=[
            ("read_file", {"file_path": str(worktree / "counter.mjs")}),
            (
                "grep",
                {
                    "pattern": "row.created",
                    "path": str(worktree),
                    "output_mode": "content",
                },
            ),
            ("glob", {"pattern": "*.mjs", "path": str(worktree)}),
            ("ls", {"path": str(worktree)}),
        ],
    )

    results = _results_by_call(events)
    assert not any(result.is_error for result in results.values())
    assert "export function countCreated" in str(results["call-0"].content)
    assert "rows.filter((row) => row.created)" in str(results["call-1"].content)
    assert "counter.mjs" in str(results["call-2"].content)
    assert "counter.mjs" in str(results["call-3"].content)


def test_read_only_reviewer_cannot_write_run_or_delegate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _review_worktree(tmp_path)
    marker = tmp_path / "process-started"
    refused_existed = _REFUSED_PATH.exists()
    calls = [
        ("write_file", {"file_path": str(_REFUSED_PATH), "content": "console.log(1)\n"}),
        ("write_file", {"file_path": str(worktree / "build.mjs"), "content": "x\n"}),
        (
            "edit_file",
            {
                "file_path": str(worktree / "counter.mjs"),
                "old_string": "created",
                "new_string": "removed",
            },
        ),
        ("execute", {"command": f"node --version; touch {marker}"}),
        ("task", {"description": "write a scratch script", "subagent_type": "general-purpose"}),
        ("write_todos", {"todos": [{"content": "plan", "status": "in_progress"}]}),
        ("run_shell", {"command": f"touch {marker}"}),
    ]
    # The backend is the ordinary one: the tool allowlist alone refuses.
    bodies, events = _run_scripted_graph(
        monkeypatch,
        worktree,
        tools=["Read", "Search", "Grep"],
        calls=calls,
    )

    # Nothing was written, edited or started.
    assert not (worktree / "build.mjs").exists()
    assert "row.created" in (worktree / "counter.mjs").read_text()
    assert _REFUSED_PATH.exists() == refused_existed
    assert not marker.exists()
    # Each call came back as a refusal the model can read.
    assert len(bodies) == len(calls) + 1
    results = _results_by_call(events)
    for index, (name, _arguments) in enumerate(calls):
        result = results[f"call-{index}"]
        assert result.is_error, (name, result.content)
        assert "not available" in str(result.content), (name, result.content)
    # The model keeps being offered only the read tools after each refusal.
    assert all(not _bound(body) & {"write_file", "execute", "task"} for body in bodies)


def test_player_and_tool_using_coach_graphs_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _review_worktree(tmp_path)
    # The tool-using Coach asks for Bash, so its graph is today's full graph,
    # the same as a caller that gives no restriction at all.
    unrestricted, _ = _run_scripted_graph(monkeypatch, worktree, tools=[], calls=[])
    tool_using, _ = _run_scripted_graph(
        monkeypatch, worktree, tools=["Read", "Bash", "Grep", "Glob"], calls=[]
    )
    full = _FULL_COACH_TOOLS | _available_code_search_tools()
    assert _bound(unrestricted[0]) == full
    assert _bound(tool_using[0]) == full
    assert unrestricted[0]["messages"][0] == tool_using[0]["messages"][0]
    assert "write_todos" in json.dumps(tool_using[0]["messages"][0]["content"])

    # Writing, unknown or non-string requests, and every Player request, are
    # not read-only.
    player_tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
    for request, role in (
        (player_tools, "player"),
        (["Read", "Grep"], "player"),
        (player_tools, "coach"),
        (["Read", "Task"], "coach"),
        (["Read", "Fetch"], "coach"),
        ([], "coach"),
        ([object()], "coach"),
    ):
        harness = LangGraphHarness(model="ignored")
        with patch.object(
            LangGraphHarness, "_create_agent", return_value=_make_fake_agent()
        ) as create, patch.object(
            LangGraphHarness, "_resolve_model_for_invoke", return_value="ignored"
        ):

            async def _collect(
                harness: LangGraphHarness = harness,
                tools: list[Any] = request,
                role: str = role,
            ) -> None:
                async for _event in harness.invoke(
                    prompt="hi", role=role, tools=tools, cwd=worktree, timeout_seconds=5
                ):
                    pass

            asyncio.run(_collect())
        assert "allowed_tools" not in create.call_args.kwargs, (request, role)


def test_read_only_allowlist_table() -> None:
    from guardkitfactory.harness.code_search_tools import TOOL_NAMES
    from guardkitfactory.harness.langgraph_harness import read_only_allowlist

    assert read_only_allowlist(["Read"], "coach") == {"read_file", "ls"}
    assert read_only_allowlist(["Glob"], "coach") == {"glob"}
    assert read_only_allowlist(["Read", "Search", "Grep"], "coach") == {
        "read_file",
        "ls",
        "glob",
        "grep",
        *TOOL_NAMES,
    }
    assert read_only_allowlist(["Read", "Search"], "specialist") == {
        "read_file",
        "ls",
        "glob",
        "grep",
    }
    for request in (
        ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
        ["Read", "Bash", "Grep", "Glob"],
        ["Read", "Task"],
        ["Read", "Fetch"],
        ["read"],
        [],
        None,
        "Read",
        [object()],
    ):
        assert read_only_allowlist(request, "coach") is None, request


def test_read_only_coach_graph_gets_code_search_but_no_todo_list(
    tmp_path: Path,
) -> None:
    from langchain.agents.middleware import TodoListMiddleware
    from langchain_core.tools import StructuredTool

    from guardkitfactory.harness.code_search_tools import TOOL_NAMES
    from guardkitfactory.harness.langgraph_harness import (
        _AllowedToolsMiddleware,
        read_only_allowlist,
    )

    fake_tools = [
        StructuredTool.from_function(func=lambda: "{}", name=name, description=name)
        for name in TOOL_NAMES
    ]
    harness = LangGraphHarness(model="ignored", backend=object())
    allowed = read_only_allowlist(["Read", "Search", "Grep"], "coach")
    with patch(
        "guardkitfactory.harness.code_search_tools.code_search_tools",
        return_value=(fake_tools, ""),
    ), patch(
        "guardkitfactory.harness.langgraph_harness.create_deep_agent"
    ) as create:
        harness._create_agent(
            role="coach", cwd=tmp_path, resolved_model="m", allowed_tools=allowed
        )
    kwargs = create.call_args.kwargs
    assert [tool.name for tool in kwargs["tools"]] == list(TOOL_NAMES)
    (middleware,) = kwargs["middleware"]
    assert isinstance(middleware, _AllowedToolsMiddleware)
    assert not isinstance(middleware, TodoListMiddleware)
    assert middleware.allowed == allowed
    assert "code_search" in kwargs["system_prompt"]

    # Read alone gives no code search tools.
    with patch(
        "guardkitfactory.harness.code_search_tools.code_search_tools",
        return_value=(fake_tools, ""),
    ) as search, patch(
        "guardkitfactory.harness.langgraph_harness.create_deep_agent"
    ) as create:
        harness._create_agent(
            role="coach",
            cwd=tmp_path,
            resolved_model="m",
            allowed_tools=read_only_allowlist(["Read"], "coach"),
        )
    assert create.call_args.kwargs["tools"] == []
    search.assert_not_called()
    assert "code_search" not in create.call_args.kwargs["system_prompt"]


# ---------------------------------------------------------------------------
# 29 October 2026: code_references for the builder, how it is told to use the
# code tools, and its servers stopped when each invocation ends
# (the builder tools design of 29 October 2026).
# ---------------------------------------------------------------------------

_PINNED = [{"command": ["gopls"], "files": ["**/*.go"]}]


def test_player_context_names_the_look_up_order_only_when_tools_are_offered(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "dcode-profile"
    profile.mkdir()
    config = build_player_config(cwd=tmp_path, dcode_home=profile)

    assert "Code look-up tools" not in _player_context_prompt(config)
    every = _player_context_prompt(
        config, (), ["code_search", "code_outline", "code_pattern", "code_references"]
    )
    assert "### Code look-up tools" in every
    assert "You have code_search, code_outline, code_pattern, code_references." in every
    assert "1. Before changing a function, type, field, setting or route" in every
    assert "code_references with the name and a file that defines it" in every
    assert "Change the callers and tests it finds in this task" in every
    assert "2. Before creating a file, check it does not exist" in every
    assert "3. After a rename, a move or a signature change" in every
    assert "declared test command" in every
    assert "4. code_pattern finding nothing is not evidence of no uses" in every
    assert "Do not repeat a look-up unless you have changed files since" in every
    without = _player_context_prompt(config, (), ["code_search", "code_outline", "code_pattern"])
    assert "### Code look-up tools" in without
    assert "code_references" not in without
    assert "code_search in literal mode with the name" in without


@pytest.mark.parametrize("fails", [False, True])
def test_the_players_code_tools_get_the_declaration_and_close_when_invoke_ends(
    tmp_path: Path, fails: bool
) -> None:
    from types import SimpleNamespace

    from langchain_core.tools import StructuredTool

    tools = [
        StructuredTool.from_function(func=lambda: "{}", name=name, description=name)
        for name in ("code_search", "code_outline", "code_pattern", "code_references")
    ]
    graph = _make_fake_agent()
    graph.guardkit_code_search_tools = tools
    if fails:
        graph.ainvoke = AsyncMock(side_effect=RuntimeError("model went away"))
    profile = tmp_path / "dcode-profile"
    profile.mkdir()
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    harness = LangGraphHarness(
        model="ignored",
        backend=SimpleNamespace(cwd=worktree),
        player_config=build_player_config(cwd=worktree, dcode_home=profile),
        language_servers=_PINNED,
    )

    async def _collect() -> None:
        async for _event in harness.invoke(
            prompt="Do the task.", role="player", tools=[], cwd=worktree, timeout_seconds=30
        ):
            pass

    with patch(
        "guardkitfactory.harness.dcode_harness.create_dcode_player", return_value=graph
    ) as create, patch(
        "guardkitfactory.harness.langgraph_harness.close_code_search_tools"
    ) as close, patch.object(
        LangGraphHarness, "_resolve_model_for_invoke", return_value="ignored"
    ):
        if fails:
            with pytest.raises(LangGraphHarnessError):
                asyncio.run(_collect())
        else:
            asyncio.run(_collect())
    assert create.call_args.kwargs["language_servers"] is _PINNED
    sent = graph.ainvoke.call_args.args[0]["messages"][0]["content"]
    assert "### Code look-up tools" in sent and "code_references" in sent
    assert sent.endswith("## Assigned task\n\nDo the task.")
    close.assert_called_once_with(tools)
