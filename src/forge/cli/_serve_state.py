"""Shared subscription state for the ``forge serve`` daemon (TASK-F009-001).

The daemon (writer) and the healthz HTTP server (reader) need to agree on
a single boolean — *is the JetStream subscription currently live?* — to
implement the readiness probe mandated by Integration Contract B
(``HEALTHZ_PORT = 8080``).

This module defines the boundary type: a small ``SubscriptionState``
dataclass with a single ``live: bool`` field defaulted to ``False`` and a
guarded mutator/accessor pair that protects writes with an ``asyncio.Lock``.
Reads return the cached boolean without taking the lock — Python's GIL
guarantees attribute reads are atomic, and a stale-by-one-tick read is
acceptable for a readiness probe (TASK-F009-001 AC-006).

Wave-2 tasks T3 (daemon) and T4 (healthz) import :class:`SubscriptionState`
and share a single instance built by ``serve_cmd`` so the producer and
consumer cannot drift.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class SubscriptionState:
    """Mutable readiness flag shared between daemon and healthz server.

    Attributes:
        live: ``True`` once the JetStream subscription is established and
            messages can be processed; ``False`` while the daemon is
            still bootstrapping (or has just lost its connection). The
            healthz HTTP server reads this attribute to answer
            ``GET /healthz`` with ``200`` (live) or ``503`` (not live).
    """

    live: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def set_live(self, value: bool) -> None:
        """Atomically update :attr:`live` under the internal lock.

        Use this from the daemon side (writer) — the lock guarantees that
        a concurrent writer never tears the boolean across a coroutine
        switch. The reader side may use plain attribute access.

        Args:
            value: New value for :attr:`live`.
        """
        async with self._lock:
            self.live = value

    def is_live(self) -> bool:
        """Return the current :attr:`live` value without taking the lock.

        Reads are safe without the lock because Python attribute reads
        are atomic under the GIL and the readiness semantics tolerate a
        single-tick staleness window.
        """
        return self.live


__all__ = ["SubscriptionState"]
