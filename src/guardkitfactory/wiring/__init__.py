"""guardkitfactory.wiring: stack-agnostic wiring-analysis engine.

A single analyzer over tree-sitter Concrete Syntax Trees, parameterized by
declarative per-language ``WiringDialect`` records (DATA).  Detects
UNWIRED_PATH and MOCKED_SEAM evidence for guardkit's Coach evidence path.

Public API
----------
- ``analyze_wiring(authored_files, worktree_path, task_type, stack)`` —
  main entry point; returns the scope-§5.1 dict (wiring shape with the
  ``mocked_seam`` result nested) or ``None`` when the probe legitimately
  did not run.  See :mod:`guardkitfactory.wiring.analyzer` for the shape.
- ``WiringResult``, ``MockSeamResult``, ``Finding``, ``WiringStatus`` —
  result types.
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
    WiringResult,
    WiringStatus,
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
    "WiringDialect",
    "WiringResult",
    "WiringStatus",
    "analyze_wiring",
    "get_dialect",
    "get_parser",
    "iter_dialects",
    "parse_bytes",
    "parse_file",
    "register_dialect",
]
