"""SYS_MODULES_TAMPER — product-file ``sys.modules`` mutation scan (ENVTAMPER-b).

Half (b) of the ENVTAMPER01 environment-integrity contract (S2 spec §5.2): a
Player runtime-substitutes a module in **product code** to defeat environment
skip-guards and corrupt the test oracle — the ABL-001 run-2 move (a 56-line
``nats_core`` stub assigned into ``guardkit/__init__.py`` via
``sys.modules["nats_core"] = stub``).

Scope: **authored-this-turn, non-test files** (test-tier ``sys.modules`` use —
fixtures, monkeypatching — is legitimate and never flagged, AC-009).

Covered forms (Python v1, §5.2 table): subscript assignment / ``setdefault`` /
``update`` / ``del`` on ``sys.modules``, including a module-alias receiver
(``import sys as _s; _s.modules[...]``) and a from-import receiver
(``from sys import modules; modules[...]``) resolved via the per-file import map
(RENV-2, the DATA/analyzer split).  ``getattr``/``eval`` obfuscation and
import-machinery hooks are accepted FNs (the resolution-origin check in
ENVTAMPER-a catches the *effect*).

FP posture (RENV-6): ``sys.modules[__name__] = ...`` self-replacement, and
alias shims whose RHS is itself a ``sys.modules[...]`` entry, are NOT findings.

Disposition (AC-006): **advisory-first, never turn-rejecting on first landing,
never terminating**.  Promotion via the §8 protocol after a clean cohort.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from guardkitfactory.wiring.analyzer import (
    _is_test_file,
    _matches_glob,
    _node_text,
    _parse_or_none,
    _read_bytes,
    _run_query_matches,
)
from guardkitfactory.wiring.callsite_drift import _build_import_map
from guardkitfactory.wiring.dialect import WiringDialect, iter_dialects

logger = logging.getLogger(__name__)

_ANALYZED_TASK_TYPES = {"FEATURE", "REFACTOR", "INTEGRATION"}
_CALL_METHODS = {"setdefault", "update"}


def analyze_env_tamper(
    authored_files: list[str],
    worktree_path: str | Path,
    task_type: str,
    stack: Any = None,
) -> dict[str, Any] | None:
    """Scan authored non-test product files for ``sys.modules`` tampering.

    Returns the ``env_tamper`` sub-result dict, or ``None`` when task-type
    gated / no authored non-test source targets.  Fail-open to absent on error.
    """
    try:
        return _impl(authored_files, Path(worktree_path), task_type, stack)
    except Exception as exc:  # noqa: BLE001 — fail-open by contract
        logger.warning("analyze_env_tamper failed unexpectedly: %s", exc, exc_info=True)
        return {
            "status": "error", "ran": False, "skip_reason": "analyzer error",
            "dialect": None, "language": "", "findings": [],
        }


def _absent(reason: str) -> dict[str, Any]:
    return {
        "status": reason, "ran": False,
        "skip_reason": reason.replace("_", " "),
        "dialect": None, "language": "", "findings": [],
    }


def _impl(
    authored_files: list[str], worktree: Path, task_type: str, stack: Any
) -> dict[str, Any] | None:
    if (task_type or "").upper() not in _ANALYZED_TASK_TYPES:
        return None
    candidates: list[tuple[WiringDialect, list[str]]] = []
    for dialect in iter_dialects():
        if not dialect.env_tamper_query:
            continue  # no-op for this dialect (absent-signal)
        targets = [
            f for f in authored_files
            if _matches_glob(f, dialect.file_globs)
            and not _is_test_file(f, dialect)  # non-test product files only
            and (worktree / f).is_file()
        ]
        if targets:
            candidates.append((dialect, targets))
    if not candidates:
        return None

    findings: list[dict[str, Any]] = []
    primary = candidates[0][0]
    for dialect, targets in candidates:
        for rel in targets:
            src = _read_bytes(worktree / rel)
            if src is None:
                continue
            tree = _parse_or_none(src, dialect)
            if tree is None:
                continue
            imap = _build_import_map(src, tree, dialect)
            findings.extend(_scan_file(src, tree, dialect, rel, imap))

    return {
        "status": "ran",
        "ran": True,
        "skip_reason": None,
        "dialect": primary.language,
        "language": primary.language,
        "findings": findings,
    }


def _sys_aliases(imap: dict[str, tuple[str, str]]) -> set[str]:
    """Local names that bind the ``sys`` module (direct + ``import sys as X``)."""
    aliases = {"sys"}
    for local, (origin, _orig) in imap.items():
        if origin == "sys":
            aliases.add(local)
    return aliases


def _modules_local_names(imap: dict[str, tuple[str, str]]) -> set[str]:
    """Local names bound to ``sys.modules`` via ``from sys import modules [as X]``."""
    names: set[str] = set()
    for local, (origin, orig) in imap.items():
        if origin == "sys" and orig == "modules":
            names.add(local)
    return names


def _recv_is_sys_modules(
    recv_node: Any, source: bytes, sys_aliases: set[str]
) -> bool:
    """Is ``@recv`` (an ``attribute``) a ``<sys-alias>.modules`` receiver?"""
    if recv_node.type != "attribute":
        return False
    obj = recv_node.child_by_field_name("object")
    attr = recv_node.child_by_field_name("attribute")
    if obj is None or attr is None:
        return False
    return (
        _node_text(attr, source) == "modules"
        and obj.type == "identifier"
        and _node_text(obj, source) in sys_aliases
    )


def _literal_key(subscript_node: Any, source: bytes) -> str | None:
    """The literal string key of ``sys.modules["x"]`` (None when non-literal).

    Only the INDEX child is inspected — the subscript's ``value`` (the
    ``sys.modules`` receiver, which is itself an identifier for the
    from-import form) is skipped.
    """
    value = subscript_node.child_by_field_name("value")
    value_span = (value.start_byte, value.end_byte) if value is not None else None
    for child in subscript_node.named_children:
        if value_span is not None and (child.start_byte, child.end_byte) == value_span:
            continue
        if child.type == "string":
            for gc in child.named_children:
                if gc.type == "string_content":
                    return _node_text(gc, source)
            return _node_text(child, source).strip("\"'")
        # index is an identifier / __name__ / expression → non-literal
        return None
    return None


def _finding(rel: str, node: Any, form: str, key: str | None) -> dict[str, Any]:
    return {
        "file": rel,
        "lineno": node.start_point[0] + 1,
        "symbol": f'sys.modules[{key!r}]' if key else "sys.modules",
        "kind": "SYS_MODULES_TAMPER",
        "pattern": "SYS_MODULES_TAMPER",
        "form": form,
        "module_key": key,
        "why": (
            f"sys.modules{('[' + repr(key) + ']') if key else ''} mutated in a "
            f"non-test product file (authored this turn). Runtime module "
            f"substitution defeats environment skip-guards and corrupts the test "
            f"oracle; declare the missing extra instead of stubbing."
        ),
        "severity": "warning",
        "authored_this_turn": True,
    }


def _scan_file(
    source: bytes,
    tree: Any,
    dialect: WiringDialect,
    rel: str,
    imap: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sys_aliases = _sys_aliases(imap)
    modules_locals = _modules_local_names(imap)
    try:
        matches = _run_query_matches(dialect.env_tamper_query, tree, dialect.ts_language_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("env_tamper_query failed for %s: %s", rel, exc)
        return findings

    seen: set[tuple[int, int]] = set()
    for captures in matches:
        recv = captures.get("recv", [])
        recv_id = captures.get("recv_id", [])
        # Determine whether this match targets sys.modules.
        is_target = False
        if recv and _recv_is_sys_modules(recv[0], source, sys_aliases):
            is_target = True
        elif recv_id and _node_text(recv_id[0], source) in modules_locals:
            is_target = True
        if not is_target:
            continue

        if "assign" in captures:
            node = captures["assign"][0]
            subscript = _find_subscript(node)
            key = _literal_key(subscript, source) if subscript else None
            # Require a LITERAL string key (§5.2 covered forms). Non-literal
            # keys — `sys.modules[__name__]` self-replacement, a variable key,
            # dynamic registration — bias to no-finding (RENV-6 / obfuscation FN).
            if key is None:
                continue
            if _rhs_is_sys_modules_alias(node, source, sys_aliases):
                continue  # compat alias shim (RENV-6)
            _emit(findings, seen, _finding(rel, node, "subscript", key))
        elif "del" in captures:
            node = captures["del"][0]
            subscript = _find_subscript(node)
            key = _literal_key(subscript, source) if subscript else None
            if key is None:
                continue  # non-literal del (reload/cache-bust bias, RENV-6)
            _emit(findings, seen, _finding(rel, node, "del", key))
        elif "call" in captures:
            method_nodes = captures.get("method", [])
            if not method_nodes:
                continue
            method = _node_text(method_nodes[0], source)
            if method not in _CALL_METHODS:
                continue
            node = captures["call"][0]
            cargs = captures.get("cargs", [])
            key = _first_literal_arg(cargs[0], source) if cargs else None
            _emit(findings, seen, _finding(rel, node, method, key))

    return findings


def _emit(findings: list, seen: set, finding: dict) -> None:
    fp = (finding["lineno"], hash(finding["form"] + str(finding["module_key"])))
    if fp in seen:
        return
    seen.add(fp)
    findings.append(finding)


def _find_subscript(node: Any) -> Any | None:
    """Find the ``subscript`` descendant of an assignment/delete node."""
    for child in node.named_children:
        if child.type == "subscript":
            return child
        found = _find_subscript(child)
        if found is not None:
            return found
    return None


def _first_literal_arg(args_node: Any, source: bytes) -> str | None:
    for child in args_node.named_children:
        if child.type == "string":
            for gc in child.named_children:
                if gc.type == "string_content":
                    return _node_text(gc, source)
            return _node_text(child, source).strip("\"'")
        return None
    return None


def _rhs_is_sys_modules_alias(assign_node: Any, source: bytes, sys_aliases: set[str]) -> bool:
    """Is the RHS of an assignment itself a ``sys.modules[...]`` read (alias shim)?"""
    right = assign_node.child_by_field_name("right")
    if right is None or right.type != "subscript":
        return False
    value = right.child_by_field_name("value")
    return value is not None and _recv_is_sys_modules(value, source, sys_aliases)
