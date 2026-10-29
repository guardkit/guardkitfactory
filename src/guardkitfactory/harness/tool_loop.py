"""A tool-using model turn is bounded: a model cannot call tools forever.

Moved here on 29 October 2026 so both reviewers use one copy (the build reviewer
design of 29 October 2026): it is specialist-agent's
``ToolLoopGuardMiddleware`` (``agents/tool_loop.py``, the plan reviewer's
limit), unchanged in behaviour. GuardKit's build reviewer gets it on its
read-only graph (``LangGraphHarness``). specialist-agent still has its own copy;
switching its import to this one is a later, coordinated step.

WHY IT EXISTS. On 7 October 2026 the architect seat's planner made over 400
model calls in one invocation, calling one memory search with the same
arguments every other turn, until the prompt reached the model's context limit.
Nothing bounded the loop: LangGraph's own step limit (about 10,000 steps) is far
beyond any context window. The build reviewer's earlier bound was a graph step
ceiling of 12 steps (about six tool calls) that threw away everything it had
found when it tripped; this one ends with an answer instead.

WHAT IT DOES. Per invocation, counted from the invocation's own messages so it
needs no stored state:

* **Identical calls.** A tool call with the same name and the same arguments
  as :data:`MAX_IDENTICAL_CALLS_PER_RUN` earlier calls in this invocation that
  were answered (did not fail) is not run. It is answered with an error
  message saying the result is already above, and the next model call is the
  final one (below). Failed calls are not counted here: a failure may be
  retried.
* **Tool turns.** After :data:`MAX_TOOL_TURNS_PER_RUN` model turns that asked
  for tools, the next model call is the final one. A turn may ask for more
  than one tool.
* **Every tool failing.** When every tool offered has failed
  :data:`MAX_TOOL_FAILURES_PER_RUN` times, the next model call is the final
  one.

THE FINAL CALL. The model is asked once more, with NO tools offered, for its
complete answer from what it already has. Because some providers reject a
request that carries tool-call history but defines no tools (the Anthropic API
does), that one request is sent with the history written out as ordinary
text: each tool request becomes a line of the model's own turn, and each tool
result becomes a user message. The agent's real message history is not
changed. If the reply still asks for a tool, its text is kept as the answer
and the tool calls are dropped, so the run ends; if it wrote no text at all,
the run fails with :class:`ToolUseEnded`, which names the reason in plain
words.

Nothing here depends on the model, the provider, the role or the tools: the
bounds are counts of the invocation's own messages.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)


MAX_TOOL_FAILURES_PER_RUN = 3
"""Failed calls one tool may make in one invocation before it counts as gone.

The same number as specialist-agent's failure cap (``agents/tool_errors.py``),
whose counting this module repeats below so it stands alone.
"""


def _messages(state: Any) -> list[Any]:
    if isinstance(state, dict):
        msgs = state.get("messages")
    else:
        msgs = getattr(state, "messages", None)
    return list(msgs) if isinstance(msgs, (list, tuple)) else []


def failures_by_tool(state: Any) -> dict[str, int]:
    """Count this run's failed tool results (``status == "error"``) per tool."""
    counts: dict[str, int] = {}
    for msg in _messages(state):
        if isinstance(msg, ToolMessage) and msg.status == "error" and msg.name:
            counts[msg.name] = counts.get(msg.name, 0) + 1
    return counts


def _withdrawn(state: Any) -> set[str]:
    return {
        name
        for name, n in failures_by_tool(state).items()
        if n >= MAX_TOOL_FAILURES_PER_RUN
    }


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, dict):
        name = tool.get("name") or (tool.get("function") or {}).get("name")
        return name if isinstance(name, str) else None
    name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None

MAX_TOOL_TURNS_PER_RUN = 40
"""Model turns that may ask for tools in one invocation.

Traces on this machine up to 7 October 2026: architect rounds used at most
five tool calls, but product-owner greenfield rounds that scored GOOD used 18
different memory searches (trace -fe349e42, 18 August) and 37 calls, 35 of
them different (trace -d922111f, 5 October). Forty turns leaves room for that
kind of exploration; a loop on one call is caught much earlier by the
identical-call bound below, and forty turns still ends any loop long before a
context window fills.
"""

MAX_IDENTICAL_CALLS_PER_RUN = 2
"""Times one call (same tool, same arguments) is run in one invocation.

Only calls that were answered count (a failed call may be retried). A third
identical call after two answers is not run, and ends tool use for the
invocation.
"""


class ToolUseEnded(RuntimeError):
    """The model was asked for its answer without tools and wrote none."""


# --- counting ----------------------------------------------------------------


def call_signature(call: Any) -> tuple[str, str]:
    """``(tool name, arguments as canonical JSON)`` for one tool call."""
    if isinstance(call, dict):
        name, args = call.get("name"), call.get("args")
    else:
        name, args = getattr(call, "name", None), getattr(call, "args", None)
    try:
        canonical = json.dumps(args or {}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canonical = repr(args)
    return str(name or ""), canonical


def _tool_turns(state: Any) -> list[AIMessage]:
    return [
        m for m in _messages(state) if isinstance(m, AIMessage) and m.tool_calls
    ]


def _ordered_calls(state: Any) -> list[tuple[str, tuple[str, str]]]:
    """Every tool call of this invocation, in order: ``(call id, signature)``."""
    return [
        (str(call.get("id") or ""), call_signature(call))
        for turn in _tool_turns(state)
        for call in turn.tool_calls
    ]


def _answered_call_ids(state: Any) -> set[str]:
    """Ids of this invocation's calls whose result came back without error."""
    return {
        m.tool_call_id
        for m in _messages(state)
        if isinstance(m, ToolMessage) and m.status != "error"
    }


def _answered_identical_calls(state: Any, call: dict[str, Any]) -> int:
    """Calls before ``call`` in this invocation with its signature whose
    result came back without error.

    A failed call may be retried; repeated failures end tool use through the
    "every tool failing" rule. Calls made
    together in one turn have no results yet when they run, so they do not
    count against each other (the overrun is at most that one turn).
    """
    signature = call_signature(call)
    call_id = str(call.get("id") or "")
    ordered = _ordered_calls(state)
    position = next(
        (i for i, (cid, _) in enumerate(ordered) if call_id and cid == call_id),
        len(ordered),
    )
    answered = _answered_call_ids(state)
    return sum(
        1 for cid, sig in ordered[:position] if sig == signature and cid in answered
    )


def stop_reason(state: Any, offered: list[Any]) -> str | None:
    """Why tool use must end before the next model call, or ``None``.

    ``offered`` is the request's tool list before any is taken away.
    """
    answered_ids = _answered_call_ids(state)
    answered: dict[tuple[str, str], int] = {}
    for call_id, signature in _ordered_calls(state):
        if answered.get(signature, 0) >= MAX_IDENTICAL_CALLS_PER_RUN:
            return (
                f"the writer called {signature[0]} again with the same "
                f"arguments after {MAX_IDENTICAL_CALLS_PER_RUN} answers that "
                "would not change"
            )
        if call_id in answered_ids:
            answered[signature] = answered.get(signature, 0) + 1
    turns = len(_tool_turns(state))
    if turns >= MAX_TOOL_TURNS_PER_RUN:
        return (
            f"the writer has asked for tools in {turns} turns, the most "
            "allowed for one answer"
        )
    names = {n for n in (_tool_name(t) for t in offered) if n}
    if names and names <= _withdrawn(state):
        return (
            f"every tool offered has failed {MAX_TOOL_FAILURES_PER_RUN} times "
            "and been withdrawn"
        )
    return None


# --- the final call, without tools --------------------------------------------


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts)


def final_answer_note(reason: str) -> str:
    """The instruction the model receives for its final call."""
    return (
        f"Tool use has ended for this answer: {reason}. No tools are available "
        "now, so do not ask for one. Write your complete answer now, in the "
        "form your instructions ask for, using what is already in this "
        "conversation."
    )


def _merge(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Join consecutive user turns and consecutive model turns into one each.

    Some chat templates require user and model turns to alternate.
    """
    merged: list[BaseMessage] = []
    for message in messages:
        if (
            merged
            and type(merged[-1]) is type(message)
            and isinstance(message, (HumanMessage, AIMessage))
        ):
            joined = "\n\n".join(
                t for t in (_text(merged[-1]), _text(message)) if t
            )
            merged[-1] = type(message)(content=joined)
        else:
            merged.append(message)
    return merged


def written_out(messages: list[BaseMessage], note: str) -> list[BaseMessage]:
    """``messages`` with tool calls and results as plain text, ``note`` last."""
    out: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, AIMessage):
            lines = [_text(message)] if _text(message).strip() else []
            for call in message.tool_calls or []:
                name, args = call_signature(call)
                lines.append(f"(I asked for the tool {name} with {args}.)")
            out.append(AIMessage(content="\n".join(lines)))
        elif isinstance(message, ToolMessage):
            out.append(
                HumanMessage(
                    content=f"Result of the tool {message.name or 'tool'}:\n"
                    f"{_text(message)}"
                )
            )
        else:
            out.append(message)
    out.append(HumanMessage(content=note))
    return _merge(out)


def _without_tool_calls(message: AIMessage) -> AIMessage:
    kwargs = dict(message.additional_kwargs or {})
    kwargs.pop("tool_calls", None)
    kwargs.pop("function_call", None)
    return message.model_copy(
        update={
            "tool_calls": [],
            "invalid_tool_calls": [],
            "additional_kwargs": kwargs,
        }
    )


def _checked_final(response: Any, reason: str) -> Any:
    """Drop any tool calls from the final reply; fail if it wrote nothing."""

    def check(message: AIMessage) -> AIMessage:
        if not _text(message).strip():
            raise ToolUseEnded(
                f"The writer was stopped from using tools ({reason}) and asked "
                "for its answer without them, but wrote no answer"
                + (
                    " and asked for a tool again."
                    if message.tool_calls or message.invalid_tool_calls
                    else "."
                )
            )
        if message.tool_calls or message.invalid_tool_calls:
            logger.warning(
                "Final answer without tools still asked for %d tool call(s); "
                "the calls are dropped and its text kept",
                len(message.tool_calls) + len(message.invalid_tool_calls),
            )
            return _without_tool_calls(message)
        return message

    if isinstance(response, AIMessage):
        return check(response)
    inner = getattr(response, "model_response", None)  # ExtendedModelResponse
    holder = inner if inner is not None else response
    result = getattr(holder, "result", None)
    if isinstance(result, list):
        ai_seen = False
        for i, message in enumerate(result):
            if isinstance(message, AIMessage):
                ai_seen = True
                result[i] = check(message)
        if not ai_seen:
            raise ToolUseEnded(
                f"The writer was stopped from using tools ({reason}) and asked "
                "for its answer without them, but returned no reply."
            )
    return response


class ToolLoopGuardMiddleware(AgentMiddleware):
    """Bound a model's tool use per invocation; see the module docstring."""

    # --- tool calls ---------------------------------------------------------

    def _repeat_refused(self, request: Any) -> ToolMessage | None:
        call = request.tool_call
        name = str(call.get("name") or "tool")
        if name in _withdrawn(request.state):
            # A tool past its failures is left to the caller's own failure
            # handling (specialist-agent's cap answers it without running it).
            return None
        earlier = _answered_identical_calls(request.state, call)
        if earlier < MAX_IDENTICAL_CALLS_PER_RUN:
            return None
        logger.warning(
            "Tool %s called again with identical arguments (%d earlier "
            "answered identical calls in this run); not run, tool use ends "
            "(args=%r)",
            name,
            earlier,
            call.get("args"),
        )
        return ToolMessage(
            content=(
                f"{name} was already called with exactly these arguments "
                f"{earlier} times in this run; its result is above and would "
                "not change, so the call was not run. Tool use ends now: "
                "write your answer from what you have."
            ),
            name=name,
            tool_call_id=str(call.get("id") or ""),
            status="error",
        )

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        refused = self._repeat_refused(request)
        return refused if refused is not None else handler(request)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        refused = self._repeat_refused(request)
        return refused if refused is not None else await handler(request)

    # --- model calls --------------------------------------------------------

    @staticmethod
    def _final_request(request: ModelRequest, reason: str) -> ModelRequest:
        logger.warning(
            "Tool use ended for this call (%s); asking for the final "
            "answer without tools",
            reason,
        )
        return request.override(
            messages=cast(Any, written_out(list(request.messages), final_answer_note(reason))),
            tools=[],
            tool_choice=None,
        )

    def wrap_model_call(self, request: ModelRequest, handler: Any) -> Any:
        reason = stop_reason(request.state, list(request.tools))
        if reason is None:
            return handler(request)
        return _checked_final(handler(self._final_request(request, reason)), reason)

    async def awrap_model_call(self, request: ModelRequest, handler: Any) -> Any:
        reason = stop_reason(request.state, list(request.tools))
        if reason is None:
            return await handler(request)
        return _checked_final(
            await handler(self._final_request(request, reason)), reason
        )
