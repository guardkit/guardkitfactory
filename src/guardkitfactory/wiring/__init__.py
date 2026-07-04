"""guardkitfactory.wiring: stack-agnostic wiring-analysis engine.

A single analyzer over tree-sitter Concrete Syntax Trees, parameterized by
declarative per-language ``WiringDialect`` records (DATA).  Detects
UNWIRED_PATH, MOCKED_SEAM, and STUB_BODY evidence for guardkit's Coach
evidence path.

Public API
----------
- ``analyze_wiring(authored_files, worktree_path, task_type, stack)`` —
  main entry point; returns the scope-§5.1 dict (wiring shape with the
  ``mocked_seam`` result nested) or ``None`` when the probe legitimately
  did not run.  See :mod:`guardkitfactory.wiring.analyzer` for the shape.
- ``analyze_stub_scan(authored_files, worktree_path, task_type, stack)`` —
  anti-stub body scan; returns a ``StubScanResult`` dict or ``None``.
- ``WiringResult``, ``MockSeamResult``, ``StubScanResult``, ``Finding``,
  ``WiringStatus`` — result types.
- ``WiringDialect`` — frozen descriptor dataclass (+ registry helpers).

Side-effect import registers all built-in dialects (python, javascript,
typescript, c_sharp).
"""

from __future__ import annotations

# Side-effect import: registers all built-in dialects.
import guardkitfactory.wiring.dialects  # noqa: F401
from guardkitfactory.wiring.analyzer import (
    CtorArityResult,
    Finding,
    MockSeamResult,
    StubScanResult,
    WiringResult,
    WiringStatus,
    analyze_stub_scan,
    analyze_wiring,
)
from guardkitfactory.wiring.dialect import (
    WiringDialect,
    get_dialect,
    iter_dialects,
    register_dialect,
)
from guardkitfactory.wiring.parser import get_parser, parse_bytes, parse_file

__all__ = [
    "CtorArityResult",
    "Finding",
    "MockSeamResult",
    "StubScanResult",
    "WiringDialect",
    "WiringResult",
    "WiringStatus",
    "analyze_stub_scan",
    "analyze_wiring",
    "get_dialect",
    "get_parser",
    "iter_dialects",
    "parse_bytes",
    "parse_file",
    "register_dialect",
]
