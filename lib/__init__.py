"""Vendored helpers for the guardkitfactory harness.

Subset of the langchain-deepagents template's lib/ tree, narrowed to the
four modules the LangGraph harness needs (TASK-HMIG-000R):

- :mod:`factory_guards` — tool allowlisting + ``ainvoke()`` system-message
  guard (TASK-REV-R2A1).
- :mod:`json_extractor` — 5-strategy JSON extraction cascade for parsing
  Coach LLM output.
- :mod:`retry_context` — retry-input construction + structural context
  manifest (Category C fix).
- :mod:`session_logging` — per-run diagnostic JSON + root-logger bootstrap
  (Category A fix).

The broader template lib (``domain_validator``, ``content_pipeline``,
``observability``, ``preflight``, ``checkpoint_hooks``, ``sprint_contract``)
is intentionally not vendored at this stage. Later harness tasks can add
modules here as they need them; keeping the vendored surface minimal makes
upstream-drift diffs cheaper to read.
"""

from __future__ import annotations

from .factory_guards import (
    ToolLeakageError,
    assert_no_system_messages,
    assert_tool_inventory,
    create_restricted_agent,
)
from .json_extractor import JsonExtractionError, JsonExtractor
from .retry_context import build_context_manifest, build_retry_input
from .session_logging import configure_logging, write_session_log

normalise_think_closing_tags = JsonExtractor.normalise_think_closing_tags

__all__ = [
    "JsonExtractionError",
    "JsonExtractor",
    "ToolLeakageError",
    "assert_no_system_messages",
    "assert_tool_inventory",
    "build_context_manifest",
    "build_retry_input",
    "configure_logging",
    "create_restricted_agent",
    "normalise_think_closing_tags",
    "write_session_log",
]
