"""LangGraph harness subpackage.

Hosts :class:`LangGraphHarness` (TASK-HMIG-001B), the concrete
``HarnessAdapter`` implementation imported from
``guardkit.orchestrator.harness`` (TASK-HMIG-001A) and constructed on top
of :func:`deepagents.create_deep_agent`. Backend / permissions plumbing
(TASK-HMIG-002R) and Player/Coach role-prompt wiring (TASK-HMIG-007)
compose with this class but live elsewhere.
"""

from __future__ import annotations

from guardkitfactory.harness.langgraph_harness import (
    LangGraphHarness,
    LangGraphHarnessError,
)

__all__ = ["LangGraphHarness", "LangGraphHarnessError"]
