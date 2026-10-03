"""Give the Player model its own earlier thinking back on every step.

``langchain_openai.ChatOpenAI`` on Chat Completions drops the thinking text an
OpenAI-compatible server returns beside each reply (``reasoning_content`` from
LiteLLM, ``reasoning`` from vLLM reached directly). Every earlier assistant
turn therefore reaches the model with its thinking removed, and the model
thinks the whole problem through again at each step.

:class:`ReasoningReplayChatOpenAI` keeps that text on the reply's
``AIMessage.additional_kwargs["reasoning_content"]`` and sends it back on the
same assistant message in later requests. The local model's chat template then
writes it back inside the earlier turn's thinking block.

Only the Player uses this class. The coach and the other roles keep plain
``ChatOpenAI``: the coach's verdict parser falls back to reasoning text, so
giving it reasoning would change its behaviour.

The overrides wrap three private ``ChatOpenAI`` methods. Their names and
parameters are checked when this module is imported, and the request/response
behaviour is covered by tests that run the real library code, so a
langchain-openai upgrade that changes either shape fails loudly instead of
silently dropping the replay.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from typing import Any

import openai
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai.chat_models.base import ChatOpenAI

REASONING_KEY = "reasoning_content"
# LiteLLM returns ``reasoning_content``; vLLM reached directly returns ``reasoning``.
_RESPONSE_KEYS = ("reasoning_content", "reasoning")

# The private parent methods this module wraps, with the parameters it relies on.
_EXPECTED_PARENT_SHAPES: dict[str, tuple[str, ...]] = {
    "_create_chat_result": ("self", "response", "generation_info"),
    "_get_request_payload": ("self", "input_", "stop", "kwargs"),
    "_convert_chunk_to_generation_chunk": (
        "self",
        "chunk",
        "default_chunk_class",
        "base_generation_info",
    ),
}


class ReasoningReplayShapeError(RuntimeError):
    """The installed langchain-openai no longer matches what the replay wraps."""


def _check_parent_shapes() -> None:
    for name, expected in _EXPECTED_PARENT_SHAPES.items():
        method = getattr(ChatOpenAI, name, None)
        if method is None or not callable(method):
            raise ReasoningReplayShapeError(
                f"langchain_openai ChatOpenAI.{name} is missing; the Player's "
                "reasoning replay must be updated for this library version"
            )
        actual = tuple(inspect.signature(method).parameters)
        if actual != expected:
            raise ReasoningReplayShapeError(
                f"langchain_openai ChatOpenAI.{name} parameters changed from "
                f"{expected} to {actual}; the Player's reasoning replay must be "
                "updated for this library version"
            )


_check_parent_shapes()


def _reasoning_text(source: Any) -> str | None:
    """Return the non-empty thinking text carried by a reply or a delta."""
    if not isinstance(source, Mapping):
        return None
    for key in _RESPONSE_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _response_messages(response: Any) -> list[Any]:
    """Each choice's raw message, as a mapping, in choice order."""
    if isinstance(response, Mapping):
        choices = response.get("choices") or []
        return [c.get("message") if isinstance(c, Mapping) else None for c in choices]
    messages = []
    for choice in getattr(response, "choices", None) or []:
        message = getattr(choice, "message", None)
        if isinstance(message, openai.BaseModel):
            # Servers' extra fields (``reasoning_content``) are kept by the
            # SDK's permissive models and appear in the dump.
            message = message.model_dump(exclude={"parsed"}, warnings=False)
        messages.append(message)
    return messages


class ReasoningReplayChatOpenAI(ChatOpenAI):  # type: ignore[override]
    """``ChatOpenAI`` that keeps each reply's thinking and sends it back later."""

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        raw_messages = _response_messages(response)
        if len(raw_messages) != len(result.generations):
            raise ReasoningReplayShapeError(
                f"reply has {len(raw_messages)} choices but langchain-openai "
                f"built {len(result.generations)} generations"
            )
        for generation, raw in zip(result.generations, raw_messages, strict=True):
            text = _reasoning_text(raw)
            if text is not None and isinstance(generation.message, AIMessage):
                generation.message.additional_kwargs[REASONING_KEY] = text
        return result

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        entries = payload.get("messages")
        if not isinstance(entries, list):
            # Responses API payloads use ``input``; this class is only built
            # for Chat Completions, so there is nothing to replay into.
            return payload
        messages: Sequence[BaseMessage] = self._convert_input(input_).to_messages()
        if len(entries) != len(messages):
            raise ReasoningReplayShapeError(
                f"langchain-openai built {len(entries)} request messages from "
                f"{len(messages)} input messages; cannot pair earlier thinking"
            )
        for entry, message in zip(entries, messages, strict=True):
            if not isinstance(message, AIMessage) or entry.get("role") != "assistant":
                continue
            text = message.additional_kwargs.get(REASONING_KEY)
            if isinstance(text, str) and text and REASONING_KEY not in entry:
                entry[REASONING_KEY] = text
        return payload

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if generation_chunk is None:
            return None
        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if choices:
            text = _reasoning_text(choices[0].get("delta"))
            if text is not None:
                # Chunk merging concatenates string values, so the streamed
                # pieces add up to the whole thinking text.
                generation_chunk.message.additional_kwargs[REASONING_KEY] = text
        return generation_chunk
