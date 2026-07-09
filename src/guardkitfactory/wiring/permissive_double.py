"""PERMISSIVE_DOUBLE — signature-binding-fake scan (WS3-S3 2a, §2).

A test double standing in for a production callable that accepts
``(*args, **kwargs)`` binds to anything; a caller drifting off the real
signature stays green and detonates in production (DD4F, POC-006).  The house
cure is ``SignatureBindingFake`` (``inspect.signature(real).bind(...)`` on every
call).  2a makes the *cheap* permissive forms loud.

Tier-1 signals (this module, §2.4):

* **patched** (high confidence): a permissive double installed over a
  first-party production target via a mock primitive — ``patch("first.mod.fn")``
  with an implicit MagicMock or a star-args replacement, ``patch.object`` /
  ``monkeypatch.setattr`` likewise.  Classified against the ladder (§2.1) via
  the §2.2 decision table; ``wraps=`` / ``autospec`` / ``create_autospec`` bind
  the signature → NO finding.
* **name_matched** (medium confidence): a test-file class/function whose name is
  a ``double_name_affixes`` affix of a first-party symbol reachable through the
  per-file import map, with a star-args accepting surface (§2.2.1).

First-party is the POSITIVE worktree-resolution predicate (R2a-5) — NOT
allowlist-negation — so ``patch("time.sleep")`` / ``patch("subprocess.run")``
never fire.  ``spec=`` mock elevation (POC-006's exact form) is **tier-2**
(needs the F6 manifest) and is recorded here as an ``info`` sub-signal, never a
tier-1 advisory.  Advisory (``should_fix``) disposition at both consumers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from guardkitfactory.wiring.analyzer import (
    _collect_source_files,
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


def analyze_permissive_double(
    authored_files: list[str],
    worktree_path: str | Path,
    task_type: str,
    stack: Any = None,
) -> dict[str, Any] | None:
    """Scan authored test files for permissive doubles over first-party seams."""
    try:
        return _impl(authored_files, Path(worktree_path), task_type)
    except Exception as exc:  # noqa: BLE001 — fail-open by contract
        logger.warning("analyze_permissive_double failed: %s", exc, exc_info=True)
        return {"status": "error", "ran": False, "skip_reason": "analyzer error",
                "dialect": None, "language": "", "findings": []}


def _impl(authored_files: list[str], worktree: Path, task_type: str) -> dict[str, Any] | None:
    if (task_type or "").upper() not in _ANALYZED_TASK_TYPES:
        return None
    candidates: list[tuple[WiringDialect, list[str]]] = []
    for dialect in iter_dialects():
        if not dialect.double_def_query:
            continue
        # 2a scope: authored TEST files (the loop gates what the Player writes).
        targets = [
            f for f in authored_files
            if _matches_glob(f, dialect.file_globs)
            and _is_test_file(f, dialect)
            and (worktree / f).is_file()
        ]
        if targets:
            candidates.append((dialect, targets))
    if not candidates:
        return None

    # First-party symbol set: names defined in non-test worktree source.
    primary = candidates[0][0]
    firstparty = _first_party_symbols(worktree, primary)

    findings: list[dict[str, Any]] = []
    for dialect, targets in candidates:
        for rel in targets:
            src = _read_bytes(worktree / rel)
            if src is None:
                continue
            tree = _parse_or_none(src, dialect)
            if tree is None:
                continue
            imap = _build_import_map(src, tree, dialect)
            findings.extend(_scan_patched(src, tree, dialect, rel, firstparty))
            findings.extend(_scan_name_matched(src, tree, dialect, rel, imap, firstparty))

    return {
        "status": "ran", "ran": True, "skip_reason": None,
        "dialect": primary.language, "language": primary.language, "findings": findings,
    }


def _first_party_symbols(worktree: Path, dialect: WiringDialect) -> set[str]:
    """Names defined at module level in non-test worktree source (positive R2a-5)."""
    names: set[str] = set()
    for rel in _collect_source_files(worktree, dialect):
        if _is_test_file(rel, dialect):
            continue
        src = _read_bytes(worktree / rel)
        if src is None:
            continue
        tree = _parse_or_none(src, dialect)
        if tree is None:
            continue
        try:
            for captures in _run_query_matches(
                dialect.public_symbols_query, tree, dialect.ts_language_name
            ):
                for n in captures.get("name", []):
                    names.add(_node_text(n, src))
        except Exception:  # noqa: BLE001
            continue
    return names


def _string_content(node: Any, source: bytes) -> str:
    for gc in node.named_children:
        if gc.type == "string_content":
            return _node_text(gc, source)
    return _node_text(node, source).strip("\"'")


def _has_binding_marker(call_node: Any, source: bytes, dialect: WiringDialect) -> bool:
    """Does this patch/mock call confer signature binding (wraps/autospec)?"""
    text = _node_text(call_node, source)
    for kw in dialect.binding_kwarg_names:
        if f"{kw}=" in text:
            return True
    for ctor in dialect.binding_ctor_names:
        if ctor in text:
            return True
    return False


def _scan_patched(
    source: bytes, tree: Any, dialect: WiringDialect, rel: str, firstparty: set[str]
) -> list[dict[str, Any]]:
    """patch(...)/setattr(...) installing a permissive double over a first-party target."""
    findings: list[dict[str, Any]] = []
    if not dialect.mock_call_query:
        return findings
    try:
        matches = _run_query_matches(dialect.mock_call_query, tree, dialect.ts_language_name)
    except Exception:  # noqa: BLE001
        return findings
    for captures in matches:
        targets = captures.get("target", [])
        if not targets:
            continue
        tnode = targets[0]
        target_text = (
            _string_content(tnode, source) if tnode.type == "string"
            else _node_text(tnode, source)
        )
        # First-party positive check: the target's leaf symbol is a first-party
        # name (R2a-5). stdlib patches (time.sleep, subprocess.run) miss this.
        leaf = target_text.split(".")[-1]
        if leaf not in firstparty and target_text.split(".")[0] not in firstparty:
            continue
        # Find the enclosing call node to check binding markers / spec.
        call_node = _enclosing_call(tnode)
        if call_node is None:
            continue
        if _has_binding_marker(call_node, source, dialect):
            continue  # wraps/autospec/create_autospec → binds → no finding
        call_text = _node_text(call_node, source)
        # spec=/spec_set= → permissive but TIER-2 (info only here, §2.4).
        form = "spec_mock" if ("spec=" in call_text or "spec_set=" in call_text) else None
        severity = "info" if form else "warning"
        if form is None:
            has_splat = "*args" in call_text or "**kwargs" in call_text
            form = "star_args_fake" if has_splat else "unspecced_mock"
        reason = (
            "spec= is tier-2 (needs seam manifest)" if severity == "info"
            else "binds nothing — signature drift is invisible"
        )
        findings.append({
            "file": rel, "lineno": call_node.start_point[0] + 1,
            "symbol": target_text, "kind": "PERMISSIVE_DOUBLE", "pattern": "PERMISSIVE_DOUBLE",
            "form": form, "target_evidence": "patched", "severity": severity,
            "why": (
                f"permissive double installed over first-party '{target_text}' "
                f"({reason}). Use a SignatureBindingFake "
                f"(tests/support/signature_binding.py) or autospec."
            ),
            "authored_this_turn": True,
        })
    return findings


def _enclosing_call(node: Any) -> Any:
    cur = node.parent
    while cur is not None:
        if cur.type == "call":
            return cur
        cur = cur.parent
    return None


def _scan_name_matched(
    source: bytes, tree: Any, dialect: WiringDialect, rel: str,
    imap: dict[str, tuple[str, str]], firstparty: set[str],
) -> list[dict[str, Any]]:
    """A test-file double whose affixed name matches a first-party symbol (§2.2)."""
    findings: list[dict[str, Any]] = []
    if not dialect.double_def_query:
        return findings
    # Names reachable through the import map (original names) ∪ first-party set.
    reachable = set(firstparty)
    for _local, (_origin, orig) in imap.items():
        if orig:
            reachable.add(orig)
    try:
        matches = _run_query_matches(dialect.double_def_query, tree, dialect.ts_language_name)
    except Exception:  # noqa: BLE001
        return findings
    for captures in matches:
        cls = captures.get("cname", [])
        fn = captures.get("name", [])
        if cls:
            name = _node_text(cls[0], source)
            node = cls[0]
            body = captures.get("cbody", [None])[0]
            permissive = _class_is_permissive(body, source, dialect) if body else False
        elif fn:
            name = _node_text(fn[0], source)
            node = fn[0]
            params = captures.get("params", [None])[0]
            permissive = _params_have_splat(params, source, dialect) if params else False
        else:
            continue
        if not permissive:
            continue
        target = _affix_target(name, dialect, reachable)
        if target is None:
            continue
        body_text = _node_text(node.parent or node, source)
        if any(esc in body_text for esc in dialect.bind_escape_patterns):
            continue  # the cure's own star-args surface — do not flag
        findings.append({
            "file": rel, "lineno": node.start_point[0] + 1,
            "symbol": name, "kind": "PERMISSIVE_DOUBLE", "pattern": "PERMISSIVE_DOUBLE",
            "form": "star_args_fake", "target_evidence": "name_matched", "target": target,
            "severity": "warning",
            "why": (
                f"'{name}' is a permissive (star-args) double named after first-party "
                f"'{target}' — a caller drifting off the real signature stays green. "
                f"Use a SignatureBindingFake."
            ),
            "authored_this_turn": True,
        })
    return findings


def _params_have_splat(params_node: Any, source: bytes, dialect: WiringDialect) -> bool:
    for child in params_node.named_children:
        if child.type in dialect.param_splat_node_types:
            if child.type == "list_splat_pattern" and any(
                c.type == "identifier" for c in child.named_children
            ):
                return True
            if child.type == "dictionary_splat_pattern":
                return True
    return False


def _class_is_permissive(body_node: Any, source: bytes, dialect: WiringDialect) -> bool:
    """A class double is permissive if a surface method has *args/**kwargs, or it
    defines __getattr__/__getattribute__ (§2.2.1)."""
    for child in body_node.named_children:
        fn = child
        if child.type == "decorated_definition":
            fn = child.child_by_field_name("definition") or child
        if fn.type != "function_definition":
            continue
        name_node = fn.child_by_field_name("name")
        params = fn.child_by_field_name("parameters")
        if name_node is None:
            continue
        mname = _node_text(name_node, source)
        if mname in ("__getattr__", "__getattribute__"):
            return True  # getattr_fake — star-args-equivalent
        if mname == "__init__" or (mname.startswith("_") and mname != "__call__"):
            continue  # __init__ is CTOR_ARITY's job; privates excluded
        if params is not None and _params_have_splat(params, source, dialect):
            return True
    return False


def _affix_target(name: str, dialect: WiringDialect, reachable: set[str]) -> str | None:
    """If ``name`` is an affix form of a reachable first-party symbol, return it."""
    norm = name.replace("_", "").lower()
    for affix in dialect.double_name_affixes:
        a = affix.lower()
        remainder = None
        if norm.startswith(a):
            remainder = name_after_prefix(name, affix)
        elif norm.endswith(a):
            remainder = name_before_suffix(name, affix)
        if remainder:
            for sym in reachable:
                if sym.replace("_", "").lower() == remainder.replace("_", "").lower():
                    return sym
    return None


def name_after_prefix(name: str, affix: str) -> str:
    lowered = name.lower().replace("_", "")
    a = affix.lower()
    if lowered.startswith(a):
        # rebuild remainder from the original by stripping affix chars
        stripped = name.lstrip("_")
        if stripped[: len(affix)].lower() == a:
            return stripped[len(affix):].lstrip("_")
    return ""


def name_before_suffix(name: str, affix: str) -> str:
    stripped = name.rstrip("_")
    if stripped[-len(affix):].lower() == affix.lower():
        return stripped[: -len(affix)].rstrip("_")
    return ""
