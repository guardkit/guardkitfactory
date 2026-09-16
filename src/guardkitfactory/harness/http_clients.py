"""HTTP resources owned by one factory invocation, never by a process cache.

Only local string models constructed inside ``with_invocation_clients`` use
this owner. Prebuilt models (including their implicit clients) belong to the
caller: the harness neither reconstructs them nor closes their transports.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, aclosing
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar

_owner: ContextVar[AsyncExitStack | None] = ContextVar("factory_http_owner", default=None)
_P = ParamSpec("_P")
_T = TypeVar("_T")


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


def create_chat_openai(**kwargs: Any) -> Any:
    """Build a local model with uncached clients when an invocation owns it.

    Use the resolved langchain-openai provider's *uncached* builders. They
    select the HTTP implementation appropriate for the OpenAI SDK and retain
    its timeout, pool and socket defaults. In particular, this factory's
    omitted request timeout is None, not httpx's 5s or OpenAI's 600s default.
    Keep the provider's proxy decision from the original, client-free kwargs:
    injecting a client first would change its env-proxy/socket-option branch.
    """
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
