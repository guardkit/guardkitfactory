"""Skip-guard extraction (WS3-S3 ENVTAMPER-a §5.1.1) — dialect DATA driven.

Extracts the module names guarded by ``pytest.importorskip("X")`` and
``find_spec("X")`` skipif conditions across the worktree test tree.  The guardkit
bootstrap parity probe consumes this list to detect an env gap (skip-guarded
module missing from the venv) BEFORE the Player is tempted to stub it.

Accepted FNs (documented): ``HAS_X = try-import`` indirection, computed module
names.  Non-Python dialects with an empty ``skip_guard_query`` are absent —
the advisory never fires, never a pass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from guardkitfactory.wiring.analyzer import (
    _collect_source_files,
    _is_test_file,
    _node_text,
    _parse_or_none,
    _read_bytes,
    _run_query_matches,
)
from guardkitfactory.wiring.dialect import iter_dialects

logger = logging.getLogger(__name__)


def _string_content(node: Any, source: bytes) -> str:
    for gc in node.named_children:
        if gc.type == "string_content":
            return _node_text(gc, source)
    return _node_text(node, source).strip("\"'")


def extract_skip_guard_modules(worktree_path: str | Path) -> dict[str, list[str]]:
    """Return ``{module_name: [test_file, ...]}`` for skip-guarded modules.

    Scans TEST-tier files only (skip-guards live in tests).  Returns an empty
    map when no dialect populates ``skip_guard_query`` (absent-signal).
    """
    worktree = Path(worktree_path)
    result: dict[str, list[str]] = {}
    for dialect in iter_dialects():
        if not dialect.skip_guard_query:
            continue
        for rel in _collect_source_files(worktree, dialect):
            if not _is_test_file(rel, dialect):
                continue
            src = _read_bytes(worktree / rel)
            if src is None:
                continue
            tree = _parse_or_none(src, dialect)
            if tree is None:
                continue
            try:
                matches = _run_query_matches(
                    dialect.skip_guard_query, tree, dialect.ts_language_name
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("skip_guard_query failed for %s: %s", rel, exc)
                continue
            for captures in matches:
                for arg in captures.get("modarg", []):
                    mod = _string_content(arg, src)
                    if mod:
                        result.setdefault(mod, [])
                        if rel not in result[mod]:
                            result[mod].append(rel)
    return result
