"""Unit tests for ``guardkitfactory.harness.model_config``.

Covers TASK-HMIG-002R-MODEL-PROFILE (2026-06-04):

* String spec → resolved BaseChatModel with profile attached for known models
* String spec → no profile attached for unknown models (SDK fallback preserved)
* BaseChatModel passthrough preserves identity and attaches profile when known
* Existing profile is never overridden (operator policy is a fallback, not a hint)

The string-spec tests patch deepagents' ``resolve_model`` at the model_config
import site so the tests do not depend on ``langchain-openai`` being installed
in the dev environment (production deployment installs it via
``.[providers]``; the dev venv may not). The patched stub mimics
``resolve_model``'s contract — return a ``BaseChatModel`` for a given string —
and the tests verify the profile-injection layer wrapping it.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI

from guardkitfactory.harness.model_config import (
    MODEL_CONTEXT_WINDOWS,
    resolve_autobuild_model,
)

# ---------------------------------------------------------------------------
# String spec resolution
# ---------------------------------------------------------------------------


def _fake_resolve(*_args, **_kwargs) -> FakeListChatModel:
    """Stand-in for deepagents' ``resolve_model`` — no real provider deps."""
    return FakeListChatModel(responses=["ok"])


def test_string_spec_for_known_model_attaches_profile() -> None:
    """qwen36-workhorse is registered with 131,072 tokens. Profile must land.

    Without the profile, deepagents' summarisation middleware would fall
    back to the 170 k-token trigger and the model would overflow context
    before summarisation fires. See ``autobuild-FEAT-AOF-run-2.md`` line 350.
    """
    with patch(
        "langchain_openai.ChatOpenAI",
        side_effect=_fake_resolve,
    ):
        resolved = resolve_autobuild_model("openai:qwen36-workhorse")

    assert resolved.profile is not None
    assert resolved.profile["max_input_tokens"] == 131_072


def test_string_spec_for_unknown_model_leaves_profile_untouched() -> None:
    """Unknown models pass through. The SDK no-profile fallback applies.

    Operator policy adds models to ``MODEL_CONTEXT_WINDOWS`` explicitly —
    we never guess. Surfacing "no profile" cleanly preserves the existing
    behaviour for any model not yet registered.
    """
    with patch(
        "langchain_openai.ChatOpenAI",
        side_effect=_fake_resolve,
    ):
        resolved = resolve_autobuild_model("openai:not-in-registry-model")

    assert resolved.profile is None


# ---------------------------------------------------------------------------
# BaseChatModel passthrough
# ---------------------------------------------------------------------------


def test_basechatmodel_passthrough_preserves_identity() -> None:
    """Pre-built BaseChatModel instances must not be re-resolved.

    The caller may have constructed the model with bespoke kwargs we should
    not silently drop (custom headers, retry policy, model_name override).
    """
    fake = FakeListChatModel(responses=["hello"])
    resolved = resolve_autobuild_model(fake)
    assert resolved is fake


def test_basechatmodel_with_existing_profile_is_not_overridden() -> None:
    """Operator policy is a fallback, not an override.

    If a partner package already populated ``profile`` (e.g.
    ``langchain-openai`` for genuine OpenAI models), keep theirs.
    """
    fake = FakeListChatModel(responses=["hello"])
    fake.profile = {"max_input_tokens": 999_999}
    resolved = resolve_autobuild_model(fake)
    assert resolved.profile == {"max_input_tokens": 999_999}


def test_prebuilt_local_chatopenai_is_normalized_without_losing_configuration() -> None:
    """A Responses-enabled local model keeps its identity and request policy."""
    transport = httpx.MockTransport(lambda _request: httpx.Response(200))
    sync_client = httpx.Client(transport=transport)
    async_client = httpx.AsyncClient(transport=transport)
    model = ChatOpenAI(
        model="local-adapter",
        api_key="test",
        base_url="http://model.test/v1",
        use_responses_api=True,
        temperature=0.37,
        max_tokens=321,
        profile={"max_input_tokens": 65_536},
        http_client=sync_client,
        http_async_client=async_client,
        http_socket_options=(),
    )

    resolved = resolve_autobuild_model(model)

    assert resolved is model
    assert resolved.use_responses_api is False
    assert resolved.model_name == "local-adapter"
    assert resolved.openai_api_base == "http://model.test/v1"
    assert resolved.http_client is sync_client
    assert resolved.http_async_client is async_client
    assert resolved.profile == {"max_input_tokens": 65_536}
    assert resolved.temperature == 0.37
    assert resolved.max_tokens == 321


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


def test_registry_contains_qwen36_workhorse() -> None:
    """Regression — keep qwen36-workhorse in the registry until llama-swap drops it.

    Removing the entry without removing the deployment would silently re-
    expose the F11 overflow. If a future task retires qwen36, both this test
    and the deployment should be updated together.

    TASK-FIX-COACHBUDG01 (2026-06-06): shape changed from ``int`` to dict.
    """
    assert "qwen36-workhorse" in MODEL_CONTEXT_WINDOWS
    entry = MODEL_CONTEXT_WINDOWS["qwen36-workhorse"]
    assert isinstance(entry, dict), f"expected dict entry, got {type(entry)}"
    assert entry["ctx_size"] == 131_072
    assert entry["reasoning_mode"] == "off", "qwen36-workhorse needs --reasoning off per §3.2"


def test_registry_contains_gemma4_26b() -> None:
    """TASK-FIX-COACHBUDG01: gemma4:26b entry pins the Coach-swap (HMIG-013).

    Entry carries the larger max_tokens_coach budget (16384) that lets the
    model reason + emit structured output under --reasoning auto. Without
    this budget, hybrid-reasoning models squeeze reasoning_content +
    content and produce empty Coach turns — exactly the F17 failure mode
    the parser fallback was meant to close.
    """
    assert "gemma4:26b" in MODEL_CONTEXT_WINDOWS
    entry = MODEL_CONTEXT_WINDOWS["gemma4:26b"]
    assert isinstance(entry, dict)
    assert entry["ctx_size"] == 65_536
    assert entry["max_tokens_coach"] == 16_384, (
        "Coach budget must accommodate reasoning + structured output for "
        "hybrid-reasoning models — see §9.13 of AUTOBUILD-ON-LLAMA-SWAP findings."
    )
    assert entry["reasoning_mode"] == "auto", (
        "gemma4:26b runs with --reasoning auto in production once the parser "
        "fallback to reasoning_content lands (TASK-FIX-COACHBUDG01 AC-009)."
    )


def test_registry_entries_are_well_formed() -> None:
    """Every registry entry MUST be normalisable.

    A misconfigured zero or negative ctx_size would break
    ``compute_summarization_defaults``; a missing reasoning_mode default
    would surface as a registry lookup failure in operator tooling.
    """
    from guardkitfactory.harness.model_config import _normalize_entry

    for name, entry_raw in MODEL_CONTEXT_WINDOWS.items():
        entry = _normalize_entry(entry_raw)
        assert isinstance(entry["ctx_size"], int), f"{name}: ctx_size not int"
        assert entry["ctx_size"] > 0, f"{name}: ctx_size must be positive, got {entry['ctx_size']}"
        assert entry["reasoning_mode"] in ("off", "auto", "on"), (
            f"{name}: reasoning_mode must be off/auto/on, got {entry['reasoning_mode']!r}"
        )


def test_normalize_entry_accepts_legacy_int_shape() -> None:
    """Backwards compatibility: a callers writing legacy ``int`` entries still work.

    The pre-COACHBUDG01 shape was ``MODEL_CONTEXT_WINDOWS[name] = int``. The
    normalize helper bridges that to the new dict shape so downstream code
    doesn't need to branch on type.
    """
    from guardkitfactory.harness.model_config import _normalize_entry

    normalized = _normalize_entry(131_072)
    assert normalized["ctx_size"] == 131_072
    assert normalized["reasoning_mode"] == "auto", "legacy entries default to auto"
    assert normalized["max_tokens_coach"] is None, "legacy entries have no role budget"
    assert normalized["max_tokens_player"] is None


def test_get_reasoning_mode_returns_registry_policy() -> None:
    """``get_reasoning_mode`` consults the registry's policy field."""
    from guardkitfactory.harness.model_config import get_reasoning_mode

    assert get_reasoning_mode("qwen36-workhorse") == "off"
    assert get_reasoning_mode("gemma4:26b") == "auto"
    # Provider-prefixed spec is normalised.
    assert get_reasoning_mode("openai:gemma4:26b") == "auto"
    # Unknown model defaults to "auto" — the safest default.
    assert get_reasoning_mode("some-future-model") == "auto"


@pytest.mark.parametrize("role", ["coach", "specialist", None])
def test_openai_string_uses_chat_completions_and_preserves_alias(
    monkeypatch: pytest.MonkeyPatch, role: str | None
) -> None:
    """Local aliases must keep the factory's Chat Completions HTTP contract.

    Every role except the Player still builds plain ``ChatOpenAI``.
    """
    fake = FakeListChatModel(responses=["ok"])
    monkeypatch.setenv("OPENAI_BASE_URL", "http://model.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")

    with patch("langchain_openai.ChatOpenAI", return_value=fake) as constructor:
        resolved = resolve_autobuild_model("openai:flash-next-t06", role=role)

    assert resolved is fake
    constructor.assert_called_once_with(
        model="flash-next-t06",
        use_responses_api=False,
        base_url="http://model.test/v1",
        api_key="local-test-key",
    )


# ---------------------------------------------------------------------------
# Player reasoning replay (coding speed fix A, 3 October 2026)
#
# These tests run langchain-openai's real request building and reply parsing
# through an in-memory HTTP transport. Nothing that the replay overrides is
# mocked, so a library change that stops calling an override fails here.
# ---------------------------------------------------------------------------


def _reply(
    *,
    content: str | None = "done",
    tool_call: bool = False,
    reasoning: dict[str, str] | None = None,
) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_call:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path": "a.txt"}'},
                }
            ],
        }
    message.update(reasoning or {})
    return {
        "id": "chat-1",
        "object": "chat.completion",
        "created": 1,
        "model": "flash-next-t06",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_call else "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class _Server:
    """Records each request body and answers with the queued replies."""

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json

        self.bodies.append(json.loads(request.content))
        return httpx.Response(200, json=self.replies.pop(0))


def _local_model(cls: type, server: _Server, **extra) -> tuple:
    transport = httpx.MockTransport(server)
    sync_client = httpx.Client(transport=transport)
    async_client = httpx.AsyncClient(transport=transport)
    model = cls(
        model="flash-next-t06",
        api_key="synthetic-test",
        base_url="http://model.test/v1",
        use_responses_api=False,
        max_retries=0,
        http_client=sync_client,
        http_async_client=async_client,
        http_socket_options=(),
        **extra,
    )
    return model, sync_client, async_client


def _call(model, messages, mode: str):
    import asyncio

    if mode == "async":
        return asyncio.run(model.ainvoke(messages))
    return model.invoke(messages)


def _close(sync_client: httpx.Client, async_client: httpx.AsyncClient) -> None:
    import asyncio

    asyncio.run(async_client.aclose())
    sync_client.close()


def test_player_string_builds_reasoning_replay_model_and_others_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    monkeypatch.setenv("OPENAI_BASE_URL", "http://model.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")

    player = resolve_autobuild_model("openai:flash-next-t06", role="player")
    assert isinstance(player, ReasoningReplayChatOpenAI)
    assert player.model_name == "flash-next-t06"
    assert player.use_responses_api is False
    assert player.openai_api_base == "http://model.test/v1"
    for role in ("coach", "specialist", None):
        other = resolve_autobuild_model("openai:flash-next-t06", role=role)
        assert type(other) is ChatOpenAI


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
def test_player_keeps_reply_thinking_and_sends_it_back(mode: str, field: str) -> None:
    """LiteLLM's ``reasoning_content`` and vLLM's ``reasoning`` are kept and replayed."""
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    server = _Server(
        _reply(tool_call=True, reasoning={field: "R1 earlier thinking"}),
        _reply(content="finished"),
    )
    model, sync_client, async_client = _local_model(ReasoningReplayChatOpenAI, server)
    try:
        history = [SystemMessage("system"), HumanMessage("read a.txt")]
        first = _call(model, history, mode)
        assert first.additional_kwargs["reasoning_content"] == "R1 earlier thinking"
        assert first.tool_calls[0]["id"] == "call-1"

        history += [first, ToolMessage("contents", tool_call_id="call-1")]
        second = _call(model, history, mode)
        assert "reasoning_content" not in second.additional_kwargs
    finally:
        _close(sync_client, async_client)

    sent = server.bodies[1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "tool"]
    assert sent[2]["reasoning_content"] == "R1 earlier thinking"
    assert sent[2]["tool_calls"][0]["id"] == "call-1"
    assert all("reasoning_content" not in m for i, m in enumerate(sent) if i != 2)
    assert all("reasoning" not in m for m in sent)


def test_player_payload_without_thinking_is_unchanged() -> None:
    """With no thinking anywhere, the Player sends exactly what ChatOpenAI sends."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    history = [
        SystemMessage("system"),
        HumanMessage("question"),
        AIMessage("earlier answer"),
        HumanMessage("say done"),
    ]
    bodies = []
    for cls in (ChatOpenAI, ReasoningReplayChatOpenAI):
        server = _Server(_reply(content="done"))
        model, sync_client, async_client = _local_model(cls, server, temperature=0)
        try:
            reply = model.invoke(history)
        finally:
            _close(sync_client, async_client)
        assert "reasoning_content" not in reply.additional_kwargs
        bodies.append(server.bodies[0])
    assert bodies[0] == bodies[1]


def test_player_ignores_empty_or_non_text_thinking() -> None:
    from langchain_core.messages import HumanMessage

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    server = _Server(
        _reply(reasoning={"reasoning_content": ""}),
        _reply(reasoning={"reasoning": {"summary": "not text"}}),
    )
    model, sync_client, async_client = _local_model(ReasoningReplayChatOpenAI, server)
    try:
        for _ in range(2):
            assert "reasoning_content" not in model.invoke([HumanMessage("q")]).additional_kwargs
    finally:
        _close(sync_client, async_client)


def test_plain_chatopenai_neither_keeps_nor_sends_thinking() -> None:
    """The coach's plain model is untouched: why the Player needs its own class."""
    from langchain_core.messages import AIMessage, HumanMessage

    server = _Server(
        _reply(reasoning={"reasoning_content": "R1"}),
        _reply(content="done"),
    )
    model, sync_client, async_client = _local_model(ChatOpenAI, server)
    try:
        first = model.invoke([HumanMessage("q")])
        assert "reasoning_content" not in first.additional_kwargs
        carried = AIMessage("answer", additional_kwargs={"reasoning_content": "R1"})
        model.invoke([HumanMessage("q"), carried, HumanMessage("say done")])
    finally:
        _close(sync_client, async_client)
    assert all("reasoning_content" not in m for m in server.bodies[1]["messages"])


def test_player_streaming_keeps_thinking() -> None:
    """Streamed thinking pieces add up to the whole text on the merged message."""
    import asyncio
    import json

    from langchain_core.messages import HumanMessage

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    def chunk(delta: dict, finish: str | None = None) -> str:
        body = {
            "id": "chat-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "flash-next-t06",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(body)}\n\n"

    stream = "".join(
        [
            chunk({"role": "assistant", "content": ""}),
            chunk({"reasoning_content": "think "}),
            chunk({"reasoning_content": "harder"}),
            chunk({"content": "answer"}),
            chunk({}, "stop"),
            "data: [DONE]\n\n",
        ]
    )

    def serve(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=stream.encode(), headers={"content-type": "text/event-stream"}
        )

    transport = httpx.MockTransport(serve)
    async_client = httpx.AsyncClient(transport=transport)
    sync_client = httpx.Client(transport=transport)
    model = ReasoningReplayChatOpenAI(
        model="flash-next-t06",
        api_key="synthetic-test",
        base_url="http://model.test/v1",
        use_responses_api=False,
        max_retries=0,
        http_client=sync_client,
        http_async_client=async_client,
        http_socket_options=(),
    )

    async def merged():
        total = None
        async for piece in model.astream([HumanMessage("q")]):
            total = piece if total is None else total + piece
        return total

    try:
        message = asyncio.run(merged())
    finally:
        _close(sync_client, async_client)
    assert message.content == "answer"
    assert message.additional_kwargs["reasoning_content"] == "think harder"


def test_reasoning_replay_refuses_a_changed_parent_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """A langchain-openai upgrade that reshapes a wrapped method fails loudly."""
    from guardkitfactory.harness import reasoning_replay

    reasoning_replay._check_parent_shapes()  # the installed version matches

    class Reshaped:
        def _create_chat_result(self, response, generation_info=None, extra=None): ...

        def _get_request_payload(self, input_, *, stop=None, **kwargs): ...

        def _convert_chunk_to_generation_chunk(
            self, chunk, default_chunk_class, base_generation_info
        ): ...

    monkeypatch.setattr(reasoning_replay, "ChatOpenAI", Reshaped)
    with pytest.raises(reasoning_replay.ReasoningReplayShapeError, match="_create_chat_result"):
        reasoning_replay._check_parent_shapes()

    del Reshaped._get_request_payload
    Reshaped._create_chat_result = lambda self, response, generation_info=None: None
    with pytest.raises(reasoning_replay.ReasoningReplayShapeError, match="missing"):
        reasoning_replay._check_parent_shapes()
