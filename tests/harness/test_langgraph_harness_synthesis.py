"""TASK-ARCH-COACHSPLIT (D-3) — LangGraphHarness.invoke_synthesis tests.

The toolless verdict-synthesis path is the substrate-level half of the Coach
split. These tests pin the two properties the architecture rests on:

* **Toolless (AC-1/AC-2).** ``invoke_synthesis`` MUST NOT call
  ``create_deep_agent`` — the path that always binds DeepAgents' built-in
  tool surface and makes every request tool-bound. A tool-bound request is
  what triggers the run-13 grammar no-op and the run-18 tool-parse HTTP 500
  (and, on the current llama.cpp build, the HTTP 400 "Cannot use custom
  grammar constraints with tools").
* **Grammar-carrying (AC-1/AC-3).** The synthesis model carries the GBNF
  grammar as a top-level request-body field (``extra_body={"grammar": ...}``)
  on the **chat-completions** transport — exactly the shape the 2026-06-09
  GB10 probe validated. The deepagents default resolver routes through the
  Responses API where the grammar is unvalidated, so the synthesis path
  forces ``use_responses_api=False``.

Async tests use ``asyncio.run`` to avoid a pytest-asyncio dependency (the
existing harness suite's convention).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    ResultMessageEvent,
)
from guardkitfactory import LangGraphHarness


def _drain_synthesis(
    harness: LangGraphHarness, *, grammar: str | None = "GBNF", prompt: str = "synthesise"
) -> list[Any]:
    async def _collect() -> list[Any]:
        events: list[Any] = []
        async for ev in harness.invoke_synthesis(
            prompt=prompt,
            role="coach",
            grammar=grammar,
            cwd=Path.cwd(),
            timeout_seconds=30,
        ):
            events.append(ev)
        return events

    return asyncio.run(_collect())


def _fake_chat_model(content: str = "```json\n{}\n```") -> MagicMock:
    """A MagicMock that passes ``isinstance(_, BaseChatModel)`` (so the
    injected-model branch of _build_synthesis_model is taken) and whose
    ainvoke returns a single AIMessage."""
    fake = MagicMock(spec=BaseChatModel)
    fake.bind.return_value = fake  # the "bound" model is itself, for simplicity
    fake.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return fake


# ---------------------------------------------------------------------------
# AC-1/AC-2 — invoke_synthesis is TOOLLESS (no create_deep_agent)
# ---------------------------------------------------------------------------


class TestInvokeSynthesisToolless:
    def test_does_not_call_create_deep_agent(self) -> None:
        harness = LangGraphHarness(model=_fake_chat_model("verdict-text"))

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        ) as create_mock:
            events = _drain_synthesis(harness)

        # The whole point: the toolless path never constructs a tool-bound
        # DeepAgent.
        create_mock.assert_not_called()

        # Event taxonomy mirrors invoke(): one assistant + one terminal.
        assert len(events) == 2
        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].text == "verdict-text"
        assert isinstance(events[1], ResultMessageEvent)
        assert events[1].session_id is None
        assert events[1].stop_reason == "end_turn"

    def test_binds_grammar_onto_injected_model(self) -> None:
        fake = _fake_chat_model()
        harness = LangGraphHarness(model=fake)

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        ):
            _drain_synthesis(harness, grammar="MY-GBNF")

        # The grammar rides as extra_body (top-level body field) — the shape
        # the GB10 probe validated. No tools are bound.
        fake.bind.assert_called_once_with(extra_body={"grammar": "MY-GBNF"})
        fake.ainvoke.assert_awaited_once()

    def test_no_grammar_means_no_bind(self) -> None:
        fake = _fake_chat_model()
        harness = LangGraphHarness(model=fake)

        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        ):
            _drain_synthesis(harness, grammar=None)

        # grammar=None → unconstrained, no extra_body, no bind.
        fake.bind.assert_not_called()
        fake.ainvoke.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC-1/AC-3 — _build_synthesis_model builds a chat-completions ChatOpenAI
# ---------------------------------------------------------------------------


class TestBuildSynthesisModel:
    def test_string_alias_builds_chat_completions_with_grammar(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", "http://gb10:9000/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.delenv("GUARDKIT_COACH_SYNTHESIS_MAX_TOKENS", raising=False)
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar="GBNF", role="coach")

        chatopenai.assert_called_once()
        kwargs = chatopenai.call_args.kwargs
        # bare model name (provider prefix stripped on the FIRST colon)
        assert kwargs["model"] == "gemma4:31b"
        # grammar as a top-level body field (probe-faithful)
        assert kwargs["extra_body"] == {"grammar": "GBNF"}
        # chat-completions transport, NOT the Responses API
        assert kwargs["use_responses_api"] is False
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 16384
        # connection threaded from env
        assert kwargs["base_url"] == "http://gb10:9000/v1"
        assert kwargs["api_key"] == "k"

    def test_max_tokens_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("GUARDKIT_COACH_SYNTHESIS_MAX_TOKENS", "20000")
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar=None, role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert kwargs["max_tokens"] == 20000
        # grammar=None → no extra_body key
        assert "extra_body" not in kwargs

    def test_injected_model_grammar_none_returns_model_unbound(self) -> None:
        fake = _fake_chat_model()
        harness = LangGraphHarness(model=fake)
        result = harness._build_synthesis_model(grammar=None, role="coach")
        assert result is fake
        fake.bind.assert_not_called()


# ---------------------------------------------------------------------------
# TASK-PERF-COACHTURNBUDGET (Lever 2) — default-off per-request reasoning_budget
# curtailment for the toolless synthesis. The knob caps the reasoning_content
# phase WITHOUT touching max_tokens (which would truncate the verdict — AC-3).
# ---------------------------------------------------------------------------


class TestSynthesisReasoningBudget:
    _ENV = "GUARDKIT_COACH_SYNTHESIS_REASONING_BUDGET"

    def test_unset_omits_field_default_off(self, monkeypatch) -> None:
        """Default-off: no env → no reasoning_budget in the request body."""
        monkeypatch.delenv(self._ENV, raising=False)
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar=None, role="coach")

        kwargs = chatopenai.call_args.kwargs
        # No grammar AND no reasoning budget → extra_body collapses to None and
        # is omitted entirely (behaviour identical to pre-COACHTURNBUDGET).
        assert "extra_body" not in kwargs

    def test_set_injects_reasoning_budget_string_path(self, monkeypatch) -> None:
        monkeypatch.setenv(self._ENV, "0")  # 0 = disable thinking (llama.cpp)
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar=None, role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert kwargs["extra_body"] == {"reasoning_budget": 0}

    def test_merges_with_grammar_string_path(self, monkeypatch) -> None:
        """grammar + reasoning_budget ride together as top-level body fields."""
        monkeypatch.setenv(self._ENV, "512")
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar="GBNF", role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert kwargs["extra_body"] == {"grammar": "GBNF", "reasoning_budget": 512}

    def test_does_not_lower_max_tokens(self, monkeypatch) -> None:
        """AC-3 tension: curtailing reasoning must NOT touch max_tokens."""
        monkeypatch.setenv(self._ENV, "0")
        monkeypatch.delenv("GUARDKIT_COACH_SYNTHESIS_MAX_TOKENS", raising=False)
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar="GBNF", role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert kwargs["max_tokens"] == 16384  # full verdict budget preserved

    def test_negative_one_unlimited_is_honoured(self, monkeypatch) -> None:
        """-1 (unlimited) is a valid int budget, distinct from unset."""
        monkeypatch.setenv(self._ENV, "-1")
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar=None, role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert kwargs["extra_body"] == {"reasoning_budget": -1}

    def test_non_int_falls_back_to_unset(self, monkeypatch) -> None:
        monkeypatch.setenv(self._ENV, "low")
        harness = LangGraphHarness(model="openai:gemma4:31b")

        with patch("langchain_openai.ChatOpenAI") as chatopenai:
            harness._build_synthesis_model(grammar=None, role="coach")

        kwargs = chatopenai.call_args.kwargs
        assert "extra_body" not in kwargs

    def test_injected_model_binds_reasoning_budget(self, monkeypatch) -> None:
        """Injected-model path binds the merged extra_body via .bind()."""
        monkeypatch.setenv(self._ENV, "0")
        fake = _fake_chat_model()
        harness = LangGraphHarness(model=fake)

        harness._build_synthesis_model(grammar="GBNF", role="coach")

        fake.bind.assert_called_once_with(
            extra_body={"grammar": "GBNF", "reasoning_budget": 0}
        )

    def test_helper_returns_none_when_unset(self, monkeypatch) -> None:
        monkeypatch.delenv(self._ENV, raising=False)
        harness = LangGraphHarness(model="openai:gemma4:31b")
        assert harness._synthesis_reasoning_budget() is None
