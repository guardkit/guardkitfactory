"""HTTP resources owned by one factory invocation, never by a process cache.

Only local string models constructed inside ``with_invocation_clients`` use
this owner. Prebuilt models (including their implicit clients) belong to the
caller: the harness neither reconstructs them nor closes their transports.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, aclosing
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar

_owner: ContextVar[AsyncExitStack | None] = ContextVar("factory_http_owner", default=None)
_P = ParamSpec("_P")
_T = TypeVar("_T")

FEATURE_ROUTING_ID_ENV = "GUARDKIT_FEATURE_ROUTING_ID"
FEATURE_ROUTING_REQUIRED_ENV = "GUARDKIT_FEATURE_ROUTING_REQUIRED"
FEATURE_ROUTING_HEADER = "x-feature-id"
_FEATURE_ROUTING_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
logger = logging.getLogger(__name__)


def resolve_feature_routing_headers(
    headers: Mapping[str, str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy headers and add the per-child routing value when it is usable.

    The source mappings are never mutated. Header names are compared without
    regard to case. Routing is bookkeeping (26 October 2026, step 2): a
    required flag other than '0' or '1', a routing id that is not 1 to 256
    ASCII letters, digits, '_' or '-', a missing id, and duplicate or
    conflicting caller headers are logged, never a refusal. An unusable id
    adds no header; the environment's usable id replaces any caller copy.
    """
    source: Mapping[str, str] = os.environ if environ is None else environ
    result = dict(headers or {})

    required_raw = source.get(FEATURE_ROUTING_REQUIRED_ENV)
    if required_raw not in (None, "0", "1"):
        logger.warning(
            "%s is %r, not '0' or '1'; treated as not required",
            FEATURE_ROUTING_REQUIRED_ENV,
            required_raw,
        )
    required = required_raw == "1"

    routing_id = source.get(FEATURE_ROUTING_ID_ENV)
    if routing_id is not None and (
        not isinstance(routing_id, str) or _FEATURE_ROUTING_ID_RE.fullmatch(routing_id) is None
    ):
        logger.warning(
            "%s is not 1 to 256 ASCII letters, digits, '_' or '-'; no routing header is sent",
            FEATURE_ROUTING_ID_ENV,
        )
        routing_id = None
    if routing_id is None and required:
        logger.warning(
            "%s=1 but no usable %s; requests go without a routing header",
            FEATURE_ROUTING_REQUIRED_ENV,
            FEATURE_ROUTING_ID_ENV,
        )

    reserved = [name for name in result if name.lower() == FEATURE_ROUTING_HEADER]
    if len(reserved) > 1 or (
        reserved and (routing_id is None or result[reserved[0]] != routing_id)
    ):
        logger.warning(
            "caller-supplied %s header(s) %s differ from the child's routing; %s",
            FEATURE_ROUTING_HEADER,
            reserved,
            "replaced" if routing_id is not None else "kept",
        )
    if routing_id is not None:
        for name in reserved:
            del result[name]
        result[FEATURE_ROUTING_HEADER] = routing_id
    return result


def feature_routing_is_configured(*, environ: Mapping[str, str] | None = None) -> bool:
    """Validate routing and report whether this child expects tagged HTTP."""
    return bool(resolve_feature_routing_headers(environ=environ))


def is_supported_routed_model(model: object) -> bool:
    """Whether model resolution is guaranteed to use ``create_chat_openai``."""
    if not isinstance(model, str):
        return False
    provider, separator, bare = model.partition(":")
    return provider == "openai" and bool(separator) and bool(bare)


async def _close_owned_clients(stack: AsyncExitStack) -> None:
    """Finish closing on this loop even if cancellation arrives during cleanup."""
    cleanup = asyncio.create_task(stack.aclose())
    cancelled = False
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
    await cleanup
    if cancelled:
        raise asyncio.CancelledError


def with_invocation_clients(
    invoke: Callable[_P, AsyncIterator[_T]],
) -> Callable[_P, AsyncIterator[_T]]:
    """Settle graph work and its clients before delivering buffered events.

    These harness generators already await the complete graph/model result
    before emitting events. Drain their existing finalizers inside the owner,
    then deliver the same events. A consumer that breaks at ResultMessageEvent
    (or closes at the first event) therefore cannot leave HTTP cleanup pending.
    ContextVar isolation also covers nested tasks without sharing clients with
    invocations on other loops or worker threads.
    """
    @wraps(invoke)
    async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> AsyncIterator[_T]:
        stack = AsyncExitStack()
        token = _owner.set(stack)
        try:
            async with aclosing(invoke(*args, **kwargs)) as stream:
                events = [event async for event in stream]
        finally:
            _owner.reset(token)
            await _close_owned_clients(stack)
        for event in events:
            yield event

    return wrapped


def create_chat_openai(*, replay_reasoning: bool = False, **kwargs: Any) -> Any:
    """Build a local model with uncached clients when an invocation owns it.

    ``replay_reasoning=True`` builds
    :class:`~guardkitfactory.harness.reasoning_replay.ReasoningReplayChatOpenAI`,
    which keeps each reply's thinking and sends it back on later requests.
    Only the Player asks for it; every other caller keeps plain ``ChatOpenAI``.

    Use the resolved langchain-openai provider's *uncached* builders. They
    select the HTTP implementation appropriate for the OpenAI SDK and retain
    its timeout, pool and socket defaults. In particular, this factory's
    omitted request timeout is None, not httpx's 5s or OpenAI's 600s default.
    Keep the provider's proxy decision from the original, client-free kwargs:
    injecting a client first would change its env-proxy/socket-option branch.
    """
    resolved_headers = resolve_feature_routing_headers(kwargs.get("default_headers"))
    if resolved_headers or "default_headers" in kwargs:
        kwargs["default_headers"] = resolved_headers or None

    if replay_reasoning:
        from guardkitfactory.harness.reasoning_replay import (
            ReasoningReplayChatOpenAI as ChatOpenAI,
        )
    else:
        from langchain_openai import ChatOpenAI

    stack = _owner.get()
    if stack is None:
        # Helpers may also be used to create a model for an external caller.
        # Its eventual invocation and client lifetime are then caller-owned.
        return ChatOpenAI(**kwargs)

    from langchain_openai.chat_models import _client_utils as provider
    from langchain_openai.chat_models.base import global_ssl_context

    base_url = kwargs.get("base_url", os.environ.get("OPENAI_BASE_URL"))
    timeout = kwargs.get("timeout", kwargs.get("request_timeout"))
    proxy = kwargs.get("openai_proxy", os.environ.get("OPENAI_PROXY"))
    socket_options = kwargs.get("http_socket_options")
    if provider._should_bypass_socket_options_for_proxy_env(
        http_socket_options=socket_options,
        http_client=None,
        http_async_client=None,
        openai_proxy=proxy,
    ):
        resolved_options = ()
    else:
        resolved_options = provider._resolve_socket_options(socket_options)

    if proxy:
        async_client = provider._build_proxied_async_httpx_client(
            proxy, global_ssl_context, resolved_options
        )
        stack.push_async_callback(async_client.aclose)
        sync_client = provider._build_proxied_sync_httpx_client(
            proxy, global_ssl_context, resolved_options
        )
        # The proxy is already applied to both owned transports. Avoid asking
        # ChatOpenAI to apply it again (it rejects proxy + explicit clients).
        kwargs["openai_proxy"] = None
    else:
        async_client = provider._build_async_httpx_client(base_url, timeout, resolved_options)
        stack.push_async_callback(async_client.aclose)
        sync_client = provider._build_sync_httpx_client(base_url, timeout, resolved_options)
    stack.callback(sync_client.close)

    return ChatOpenAI(
        **{
            **kwargs,
            "http_client": sync_client,
            "http_async_client": async_client,
            "http_socket_options": resolved_options,
        }
    )
