"""Vendored helpers for the guardkitfactory harness.

Subset of the langchain-deepagents template's lib/ tree, narrowed to the
modules the LangGraph harness needs (TASK-HMIG-000R; the tool-allowlist and
system-message guards in ``factory_guards`` were removed on 27 October 2026):

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

from .json_extractor import JsonExtractionError, JsonExtractor
from .retry_context import build_context_manifest, build_retry_input
from .session_logging import configure_logging, write_session_log

normalise_think_closing_tags = JsonExtractor.normalise_think_closing_tags

__all__ = [
    "JsonExtractionError",
    "JsonExtractor",
    "build_context_manifest",
    "build_retry_input",
    "configure_logging",
    "normalise_think_closing_tags",
    "write_session_log",
]
