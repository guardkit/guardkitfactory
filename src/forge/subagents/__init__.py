"""Forge subagents package.

Long-running ``AsyncSubAgent`` modules dispatched by the FEAT-FORGE-010
supervisor through DeepAgents ``start_async_task`` (per ADR-ARCH-031).

Currently exports:

- :mod:`forge.subagents.autobuild_runner` — the autobuild AsyncSubAgent
  that owns the DDR-006 lifecycle progression and the DDR-007 inline
  ``PipelineLifecycleEmitter`` wiring.

The package is intentionally thin — each subagent is a self-contained
module that exports a compiled DeepAgents ``graph`` for ``langgraph.json``
to address.
"""

from __future__ import annotations

__all__: list[str] = []
