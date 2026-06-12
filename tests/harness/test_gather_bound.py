"""Unit tests for the TASK-PERF-COACHSYNTH gather-bound levers.

The B-full Coach gather is the load-bearing F20 surface: its tool-using
agentic loop appends tool-result tokens every round-trip and, on the
gemma4:31b substrate (98,304-token window), a long investigation overflowed
the window (run-22 TP05: 108,094 > 98,304). This module pins the three
guardkitfactory-side levers that bound it:

* **Profile registration** — ``gemma4:31b`` is in ``MODEL_CONTEXT_WINDOWS``
  so ``resolve_autobuild_model`` injects ``profile["max_input_tokens"]`` and
  deepagents' summarisation middleware fires at a fraction of the real window
  instead of its 170 k fixed fallback (which is *larger* than 98 k → never
  fired → the root cause of F20).
* **recursion_limit** — ``LangGraphHarness`` forwards a per-invoke super-step
  ceiling to ``agent.ainvoke(config=...)``; ``None`` preserves the historic
  single-arg call shape (LangGraph default 25).
* **TruncatingBackend** — caps each ``read``/``grep``/``execute`` result so a
  single tool cycle cannot blow the window; opt-in via
  ``build_autobuild_backend(max_tool_result_chars=...)``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepagents.backends.composite import CompositeBackend
from deepagents.backends.protocol import (
    ExecuteResponse,
    GrepResult,
    ReadResult,
)

from guardkitfactory.harness.backend_config import (
    TruncatingBackend,
    build_autobuild_backend,
)
from guardkitfactory.harness.langgraph_harness import LangGraphHarness
from guardkitfactory.harness.model_config import (
    MODEL_CONTEXT_WINDOWS,
    resolve_autobuild_model,
)


# ---------------------------------------------------------------------------
# Lever 1 — gemma4:31b profile registration (AC-1 root cause)
# ---------------------------------------------------------------------------
class TestGemma31bProfile:
    def test_registered_with_98k_window(self) -> None:
        entry = MODEL_CONTEXT_WINDOWS.get("gemma4:31b")
        assert entry is not None, "gemma4:31b must be registered so summarisation fires"
        # The whole point: the trigger is keyed on the REAL serving window,
        # which is smaller than deepagents' 170k fixed fallback.
        assert entry["ctx_size"] == 98_304
        assert entry["ctx_size"] < 170_000

    def test_profile_injected_for_31b(self) -> None:
        """A BaseChatModel resolved for gemma4:31b carries max_input_tokens."""

        class _FakeModel:
            profile = None

        fake = _FakeModel()
        with patch(
            "guardkitfactory.harness.model_config.resolve_model",
            return_value=fake,
        ):
            resolved = resolve_autobuild_model("openai:gemma4:31b", role="coach")
        assert resolved.profile == {"max_input_tokens": 98_304}


# ---------------------------------------------------------------------------
# Lever 2 — LangGraphHarness recursion_limit (AC-1 hard ceiling)
# ---------------------------------------------------------------------------
def _fake_agent(text: str = "findings") -> MagicMock:
    from langchain_core.messages import AIMessage

    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content=text)]})
    return fake


async def _drain(harness: LangGraphHarness, prompt: str = "investigate") -> list:
    events = []
    async for event in harness.invoke(
        prompt=prompt, role="coach", tools=[], cwd=Path("/tmp"), timeout_seconds=60
    ):
        events.append(event)
    return events


class TestRecursionLimitForwarding:
    def test_limit_forwarded_to_ainvoke_config(self) -> None:
        fake = _fake_agent()
        harness = LangGraphHarness(model="ignored", recursion_limit=5)
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake,
        ):
            asyncio.run(_drain(harness))
        fake.ainvoke.assert_awaited_once_with(
            {"messages": [{"role": "user", "content": "investigate"}]},
            config={"recursion_limit": 5},
        )

    def test_none_limit_preserves_single_arg_shape(self) -> None:
        """Default (None) must NOT pass config — preserves LangGraph default 25."""
        fake = _fake_agent()
        harness = LangGraphHarness(model="ignored")  # recursion_limit defaults None
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake,
        ):
            asyncio.run(_drain(harness))
        fake.ainvoke.assert_awaited_once_with(
            {"messages": [{"role": "user", "content": "investigate"}]}
        )

    def test_recursion_error_wraps_to_harness_error(self) -> None:
        """A GraphRecursionError surfaces as LangGraphHarnessError so the

        orchestrator's gather degrades to B-min (AC-2) rather than crashing.
        """
        from langgraph.errors import GraphRecursionError

        from guardkitfactory.harness.langgraph_harness import LangGraphHarnessError

        fake = MagicMock()
        fake.ainvoke = AsyncMock(side_effect=GraphRecursionError("limit hit"))
        harness = LangGraphHarness(model="ignored", recursion_limit=2)
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake,
        ):
            with pytest.raises(LangGraphHarnessError):
                asyncio.run(_drain(harness))


# ---------------------------------------------------------------------------
# Lever 3 — TruncatingBackend (AC-1 per-tool-result cap)
# ---------------------------------------------------------------------------
class TestTruncatingBackend:
    def test_read_over_limit_is_capped_and_marked(self) -> None:
        big = "x" * 5000
        inner = MagicMock()
        inner.read = MagicMock(
            return_value=ReadResult(
                error=None, file_data={"content": big, "encoding": "utf-8"}
            )
        )
        wrapped = TruncatingBackend(inner, max_chars=1000)
        result = wrapped.read("foo.py")
        content = result.file_data["content"]
        assert len(content) < len(big)
        assert content.startswith("x" * 1000)
        assert "truncated" in content  # the marker is load-bearing, not silent

    def test_read_under_limit_passes_through_unchanged(self) -> None:
        small = ReadResult(error=None, file_data={"content": "tiny", "encoding": "utf-8"})
        inner = MagicMock()
        inner.read = MagicMock(return_value=small)
        wrapped = TruncatingBackend(inner, max_chars=1000)
        result = wrapped.read("foo.py")
        assert result is small  # identity: no copy when nothing to cut

    def test_execute_output_capped_and_flagged_truncated(self) -> None:
        inner = MagicMock()
        inner.execute = MagicMock(
            return_value=ExecuteResponse(
                output="y" * 5000, exit_code=0, truncated=False
            )
        )
        wrapped = TruncatingBackend(inner, max_chars=500)
        result = wrapped.execute("pytest -q")
        assert len(result.output) < 5000
        assert result.truncated is True

    def test_grep_matches_capped_with_marker(self) -> None:
        matches = [
            {"path": "a.py", "line": i, "text": "z" * 100} for i in range(50)
        ]
        inner = MagicMock()
        inner.grep = MagicMock(return_value=GrepResult(error=None, matches=matches))
        wrapped = TruncatingBackend(inner, max_chars=300)
        result = wrapped.grep("pattern")
        assert len(result.matches) < len(matches)
        # final synthetic match carries the truncation notice
        assert "truncated" in result.matches[-1]["text"]

    def test_non_capped_methods_delegate(self) -> None:
        inner = MagicMock()
        inner.write = MagicMock(return_value="written")
        inner.cwd = Path("/wt")
        wrapped = TruncatingBackend(inner, max_chars=10)
        assert wrapped.write("f", "data") == "written"
        assert wrapped.cwd == Path("/wt")

    def test_aread_capped(self) -> None:
        big = "q" * 4000
        inner = MagicMock()
        inner.aread = AsyncMock(
            return_value=ReadResult(
                error=None, file_data={"content": big, "encoding": "utf-8"}
            )
        )
        wrapped = TruncatingBackend(inner, max_chars=800)
        result = asyncio.run(wrapped.aread("foo.py"))
        assert len(result.file_data["content"]) < len(big)


# ---------------------------------------------------------------------------
# build_autobuild_backend wiring (opt-in; Player path unchanged)
# ---------------------------------------------------------------------------
class TestBuildBackendWiring:
    def test_default_is_unwrapped(self, tmp_path: Path) -> None:
        backend = build_autobuild_backend(tmp_path)
        assert isinstance(backend, CompositeBackend)
        assert not isinstance(backend.default, TruncatingBackend)

    def test_limit_wraps_default(self, tmp_path: Path) -> None:
        backend = build_autobuild_backend(tmp_path, max_tool_result_chars=4096)
        assert isinstance(backend, CompositeBackend)
        assert isinstance(backend.default, TruncatingBackend)
        # artifacts_root must still re-root summarisation under the worktree
        assert str(tmp_path) in str(backend.artifacts_root)

    def test_wrapped_default_still_passes_composite_execute_gate(
        self, tmp_path: Path
    ) -> None:
        """TASK-FIX-WTESCAPE01 regression — wrappers satisfy the ABC gate.

        ``CompositeBackend.execute`` gates on
        ``isinstance(default, SandboxBackendProtocol)`` (an ABC, so
        ``__getattr__`` delegation alone does not satisfy it). Before the
        ``SandboxBackendProtocol.register(...)`` calls in backend_config,
        a TruncatingBackend default raised ``NotImplementedError`` on the
        Coach gather's first ``execute`` — latent since
        TASK-PERF-COACHSYNTH.
        """
        for kwargs in ({}, {"max_tool_result_chars": 4096}):
            backend = build_autobuild_backend(tmp_path, **kwargs)
            result = backend.execute("echo gate-open")
            assert "gate-open" in result.output
