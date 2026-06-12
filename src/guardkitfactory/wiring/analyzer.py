"""WiringAnalyzer: stack-agnostic wiring-analysis engine.

Operates over tree-sitter Concrete Syntax Trees.  The only stack-specific
input is a declarative ``WiringDialect`` descriptor (DATA).  Adding a
language is **a descriptor entry, not a code plugin change**.

Fidelity caveat
---------------
tree-sitter yields a **Concrete Syntax Tree, NOT full semantic
resolution**.  Reachability is a **syntactic identifier-match heuristic
across files** — the same fidelity as the prior python-ast plan, now
multi-language.  It cannot resolve aliased imports, dynamic dispatch,
string-keyed registries, reflection-based DI, or entry-points outside
the worktree.  The FP/FN posture deliberately **biases toward WIRED**
(substrings count as referenced; ``__all__`` / manifest names count as
wired; parse-degraded files are skipped, never flagged) so the heuristic
produces accepted false-negatives, never false-red false-positives.

Result shape (consumed by guardkit's Coach evidence path)
----------------------------------------------------------
``analyze_wiring`` returns ``None`` when the probe legitimately did not
run (task-type gate; zero authored non-test source targets), otherwise a
dict in the ``bundle.wiring`` shape of the scope doc §5.1, with the
MOCKED_SEAM result nested under the ``"mocked_seam"`` key (its own §5.1
shape) so a single CST pass serves both probes::

    {
      "status": "complete" | "parse_degraded" | "unsupported_stack" | "error",
      "dialect": "<primary>", "language": "<primary>",
      "dialects": [...], "languages": [...],          # polyglot (AC-021)
      "targets_scanned": int, "symbols_examined": int,
      "findings": [ {UNWIRED_PATH finding} ],
      "degraded_files": [...],
      "mocked_seam": {
        "status": "ran" | "skipped_no_acceptance_files",
        "ran": bool, "skip_reason": str | None,
        "dialect": ..., "language": ...,
        "findings": [ {MOCKED_SEAM finding, severity warning|info} ],
        "external_mocks_ignored": [...],
      },
    }

No status value ever maps to "pass": the only positive verdict is
``complete`` **with** ``findings: []`` (scope §5.6).
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardkitfactory.wiring.dialect import (
    WiringDialect,
    _find_language,
    get_dialect,
    iter_dialects,
)
from guardkitfactory.wiring.parser import _load_language, parse_bytes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status discriminator
# ---------------------------------------------------------------------------

WiringStatus = str  # literal type: see status table below

# Status values (no value maps to "pass" — see scope doc §5.6):
#   complete                    — analyzer ran, classification authoritative
#                                 (empty findings = real positive verdict)
#   unsupported_stack           — no dialect for the detected language
#   parse_degraded              — ≥1 target skipped on CST parse error
#                                 (biased WIRED, recorded in degraded_files)
#   error                       — unexpected exception, caught fail-open
# MOCKED_SEAM sub-result additionally uses:
#   ran / skipped_no_acceptance_files

_ANALYZED_TASK_TYPES = frozenset({"FEATURE", "REFACTOR", "INTEGRATION"})

# Source extensions that are real languages we know about but have no
# registered dialect — used to report unsupported_stack (absent-signal)
# instead of None when a stack profile is not supplied.
_KNOWN_UNDIALECTED_EXTENSIONS = {
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".php": "php",
    ".scala": "scala",
    ".ex": "elixir",
    ".erl": "erlang",
}

# ---------------------------------------------------------------------------
# Finding / result types
# ---------------------------------------------------------------------------

FindingKind = str  # "UNWIRED_PATH" | "MOCKED_SEAM"


@dataclass
class Finding:
    """A single wiring evidence finding."""

    file: str
    symbol: str
    kind: FindingKind
    module: str = ""
    lineno: int = 0
    severity: str = "warning"
    pattern: str = ""
    why: str = ""
    registration_found: bool = False
    searched_refs: int = 0
    mock_kind: str = ""
    authored_this_turn: bool | None = None
    dialect: str = ""
    language: str = ""


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    """Convert a Finding to a plain JSON-serializable dict."""
    return {
        "file": f.file,
        "symbol": f.symbol,
        "kind": f.kind,
        "module": f.module,
        "lineno": f.lineno,
        "severity": f.severity,
        "pattern": f.pattern,
        "why": f.why,
        "registration_found": f.registration_found,
        "searched_refs": f.searched_refs,
        "mock_kind": f.mock_kind,
        "authored_this_turn": f.authored_this_turn,
        "dialect": f.dialect,
        "language": f.language,
    }


@dataclass
class WiringResult:
    """Result of an UNWIRED_PATH analysis run."""

    status: WiringStatus
    dialect: str | None = None
    language: str = ""
    dialects: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    targets_scanned: int = 0
    symbols_examined: int = 0
    findings: list[Finding] = field(default_factory=list)
    degraded_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dict (scope §5.1 ``bundle.wiring`` shape)."""
        return {
            "status": self.status,
            "dialect": self.dialect,
            "language": self.language,
            "dialects": self.dialects,
            "languages": self.languages,
            "targets_scanned": self.targets_scanned,
            "symbols_examined": self.symbols_examined,
            "findings": [_finding_to_dict(f) for f in self.findings],
            "degraded_files": self.degraded_files,
        }


@dataclass
class MockSeamResult:
    """Result of a MOCKED_SEAM analysis run."""

    status: WiringStatus = "skipped_no_acceptance_files"
    ran: bool = False
    skip_reason: str | None = "no acceptance files found"
    dialect: str | None = None
    language: str = ""
    findings: list[Finding] = field(default_factory=list)
    external_mocks_ignored: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dict (scope §5.1 ``bundle.mocked_seam`` shape)."""
        return {
            "status": self.status,
            "ran": self.ran,
            "skip_reason": self.skip_reason,
            "dialect": self.dialect,
            "language": self.language,
            "findings": [_finding_to_dict(f) for f in self.findings],
            "external_mocks_ignored": [
                _finding_to_dict(f) for f in self.external_mocks_ignored
            ],
        }


# ---------------------------------------------------------------------------
# File-walking helpers
# ---------------------------------------------------------------------------

_EXCLUSION_DIRS = frozenset({
    "__pycache__",
    "node_modules",
    "bin",
    "obj",
    ".git",
    ".guardkit",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
})


def _norm_path(path: str) -> str:
    """Normalize a relative path for marker matching: forward slashes and a
    leading "/" so markers like ``"/test_"`` anchor at path-segment starts
    (avoids ``"test_"`` matching ``contest_utils.py``)."""
    return "/" + path.replace(os.sep, "/")


def _is_test_file(path: str, dialect: WiringDialect) -> bool:
    """Check if a path matches the dialect's test-file markers."""
    p = _norm_path(path)
    return any(marker in p for marker in dialect.test_path_markers)


def _is_acceptance_file(path: str, dialect: WiringDialect) -> bool:
    """Check if a path matches the dialect's acceptance/integration markers."""
    p = _norm_path(path)
    return any(marker in p for marker in dialect.acceptance_path_markers)


def _matches_glob(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if a path matches any of the glob patterns."""
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _collect_source_files(worktree: Path, dialect: WiringDialect) -> list[str]:
    """Collect worktree-relative source files matching the dialect's globs."""
    files: list[str] = []
    for root, dirs, filenames in os.walk(worktree):
        dirs[:] = [d for d in dirs if d not in _EXCLUSION_DIRS]
        for fname in filenames:
            rel_path = os.path.relpath(os.path.join(root, fname), worktree)
            if _matches_glob(rel_path, dialect.file_globs):
                files.append(rel_path)
    return sorted(files)


def _read_bytes(path: Path) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _node_text(node: Any, source: bytes) -> str:
    """Extract text from a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _run_query_matches(
    query_text: str, tree: Any, language_name: str
) -> list[dict[str, list[Any]]]:
    """Run a query and return per-match capture dicts.

    Per-match grouping (``matches`` not ``captures``) is required to pair
    ``@visibility`` with its ``@name`` in the same declaration, and to
    apply ``#any-of?``/``#eq?``/``#match?`` predicates reliably.
    """
    from tree_sitter import Query, QueryCursor

    lang = _load_language(language_name)
    query = Query(lang, query_text)
    cursor = QueryCursor(query)
    return [captures for _pattern_idx, captures in cursor.matches(tree.root_node)]


def _run_query_captures(
    query_text: str, tree: Any, language_name: str
) -> dict[str, list[Any]]:
    """Run a query and return the flat capture-name → nodes dict."""
    from tree_sitter import Query, QueryCursor

    lang = _load_language(language_name)
    query = Query(lang, query_text)
    cursor = QueryCursor(query)
    return cursor.captures(tree.root_node)


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


def _extract_public_symbols(
    source: bytes, tree: Any, dialect: WiringDialect
) -> list[dict[str, Any]]:
    """Extract public symbols, applying the dialect's is-public predicates.

    Privacy is DATA-driven: ``private_name_prefixes`` (e.g. ``"_"`` for
    Python) and ``public_visibilities`` (e.g. ``("public", "internal")``
    for C#, paired with the query's ``@visibility`` captures per match).
    """
    try:
        matches = _run_query_matches(
            dialect.public_symbols_query, tree, dialect.ts_language_name
        )
    except Exception as exc:
        logger.warning(
            "public_symbols_query failed for '%s': %s", dialect.language, exc
        )
        return []

    symbols: list[dict[str, Any]] = []
    for captures in matches:
        name_nodes = captures.get("name", [])
        if not name_nodes:
            continue
        if dialect.public_visibilities:
            vis = {
                _node_text(v, source) for v in captures.get("visibility", [])
            }
            if not (vis & set(dialect.public_visibilities)):
                continue
        for node in name_nodes:
            name = _node_text(node, source)
            if not name:
                continue
            if any(name.startswith(p) for p in dialect.private_name_prefixes):
                continue
            symbols.append({
                "name": name,
                "lineno": node.start_point[0] + 1,
                "kind": _symbol_kind(node),
            })
    return symbols


_KIND_BY_DECLARATION = {
    "function_definition": "function",
    "function_declaration": "function",
    "method_declaration": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "interface_declaration": "interface",
    "variable_declarator": "const",
}


def _symbol_kind(name_node: Any) -> str:
    """Map a captured name node to its declaration kind (AC-001:
    ``kind:"function"``/``"class"``/...), via the enclosing declaration."""
    parent = getattr(name_node, "parent", None)
    if parent is not None:
        return _KIND_BY_DECLARATION.get(parent.type, "symbol")
    return "symbol"


_DUNDER_ALL_RE = re.compile(r"__all__\s*=\s*[\[\(]([^\]\)]*)[\]\)]", re.DOTALL)
_QUOTED_NAME_RE = re.compile(r"""["']([^"']+)["']""")


def _dunder_all_names(source: bytes) -> set[str]:
    """Names listed in a Python ``__all__`` literal (count as wired)."""
    text = source.decode("utf-8", errors="replace")
    names: set[str] = set()
    for m in _DUNDER_ALL_RE.finditer(text):
        names.update(_QUOTED_NAME_RE.findall(m.group(1)))
    return names


def _extract_references(
    source: bytes, tree: Any, dialect: WiringDialect
) -> set[str]:
    """Extract identifier references from a parsed file."""
    try:
        captures = _run_query_captures(
            dialect.references_query, tree, dialect.ts_language_name
        )
    except Exception as exc:
        logger.warning(
            "references_query failed for '%s': %s", dialect.language, exc
        )
        return set()
    return {
        _node_text(n, source)
        for n in captures.get("name", [])
        if n is not None
    }


def _extract_registrations(
    source: bytes, tree: Any, dialect: WiringDialect
) -> set[str]:
    """Extract registered symbol names (``@target`` captures) from a file."""
    registered: set[str] = set()
    for reg_query in dialect.registration_queries:
        try:
            captures = _run_query_captures(
                reg_query, tree, dialect.ts_language_name
            )
        except Exception as exc:
            logger.warning(
                "registration query failed for '%s': %s", dialect.language, exc
            )
            continue
        registered.update(
            _node_text(n, source) for n in captures.get("target", [])
        )
    return registered


def _manifest_text(worktree: Path, dialect: WiringDialect) -> str:
    """Concatenated text of all script-manifest files (glob-aware)."""
    chunks: list[str] = []
    for pattern in dialect.script_manifest_files:
        if any(ch in pattern for ch in "*?["):
            paths = list(worktree.glob(pattern))
        else:
            p = worktree / pattern
            paths = [p] if p.is_file() else []
        for path in paths:
            try:
                chunks.append(path.read_text(errors="replace"))
            except OSError:
                continue
    return "\n".join(chunks)


def _build_text_corpus(
    worktree: Path, dialect: WiringDialect
) -> list[tuple[str, str]]:
    """Raw text of every non-test file under the worktree, read once.

    Powers the biased-WIRED substring fallback: deliberately BROADER than
    scope §4.1 step 5's parse-failed-only grep — a raw-text hit anywhere
    (configs, docs, .feature files) counts as referenced.  This widens
    accepted false-negatives and can never produce a false UNWIRED.
    """
    corpus: list[tuple[str, str]] = []
    for root, dirs, filenames in os.walk(worktree):
        dirs[:] = [d for d in dirs if d not in _EXCLUSION_DIRS]
        for fname in filenames:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, worktree)
            if _is_test_file(rel_path, dialect):
                continue
            try:
                with open(full_path, errors="replace") as f:
                    corpus.append((rel_path, f.read()))
            except OSError:
                continue
    return corpus


def _substring_fallback(
    symbol: str, corpus: list[tuple[str, str]], exclude_file: str
) -> bool:
    """Biased-WIRED fallback: symbol appears as a substring in any
    non-test, non-self file's raw text."""
    return any(
        symbol in text for rel_path, text in corpus if rel_path != exclude_file
    )


# ---------------------------------------------------------------------------
# Per-dialect analysis
# ---------------------------------------------------------------------------


@dataclass
class _DialectAnalysis:
    """Internal per-dialect analysis output."""

    dialect: WiringDialect
    targets_scanned: int = 0
    symbols_examined: int = 0
    unwired: list[Finding] = field(default_factory=list)
    degraded_files: list[str] = field(default_factory=list)
    mocked: list[Finding] = field(default_factory=list)
    mocks_ignored: list[Finding] = field(default_factory=list)
    acceptance_files_scanned: int = 0


def _parse_or_none(source: bytes, dialect: WiringDialect) -> Any | None:
    """Parse source; ``None`` when the CST is unusable (parse degraded).

    tree-sitter is lenient: syntax errors produce a tree with ERROR nodes
    rather than raising, so ``root_node.has_error`` is the real signal.
    """
    tree = parse_bytes(source, dialect.ts_language_name)
    if tree is None:
        return None
    if tree.root_node.has_error:
        return None
    return tree


def _analyze_dialect(
    targets: list[str],
    worktree: Path,
    dialect: WiringDialect,
) -> _DialectAnalysis:
    """Run UNWIRED_PATH + MOCKED_SEAM for one dialect over authored targets."""
    out = _DialectAnalysis(dialect=dialect)

    # --- Parse authored targets, extract public symbols -------------------
    # symbol → (defining file, symbol info)
    candidates: list[tuple[str, dict[str, Any]]] = []
    wired_by_dunder_all: set[str] = set()
    authored_seams: set[str] = set()

    for rel_path in targets:
        source = _read_bytes(worktree / rel_path)
        if source is None:
            continue
        out.targets_scanned += 1
        tree = _parse_or_none(source, dialect)
        if tree is None:
            # Parse degraded: skip the target — bias WIRED, never a false
            # UNWIRED (scope §4.1 step 3 / AC-010).
            out.degraded_files.append(rel_path)
            continue
        wired_by_dunder_all |= _dunder_all_names(source)
        symbols = _extract_public_symbols(source, tree, dialect)
        out.symbols_examined += len(symbols)
        for sym in symbols:
            candidates.append((rel_path, sym))
            authored_seams.add(sym["name"])

    # --- Build reference + registration maps over the worktree ------------
    # Reference map is per-file so a symbol's own defining file and test
    # files never count as references (the core "referenced only by its
    # own tests" detection — scope §4.1 step 5).
    refs_by_file: dict[str, set[str]] = {}
    registrations: set[str] = set()

    if candidates:
        for rel_path in _collect_source_files(worktree, dialect):
            if _is_test_file(rel_path, dialect):
                continue
            source = _read_bytes(worktree / rel_path)
            if source is None:
                continue
            tree = _parse_or_none(source, dialect)
            if tree is None:
                continue
            refs_by_file[rel_path] = _extract_references(source, tree, dialect)
            registrations |= _extract_registrations(source, tree, dialect)

    manifest = _manifest_text(worktree, dialect)
    corpus = _build_text_corpus(worktree, dialect) if candidates else []

    # --- Classify ----------------------------------------------------------
    for defining_file, sym in candidates:
        name = sym["name"]
        if name in wired_by_dunder_all:
            continue  # exported via __all__ — counts as wired
        if name in registrations:
            continue  # registered into a composition root
        if manifest and name in manifest:
            continue  # named in a script/package manifest
        if any(
            name in refs
            for f, refs in refs_by_file.items()
            if f != defining_file
        ):
            continue  # referenced by a non-test, non-self module
        if _substring_fallback(name, corpus, defining_file):
            continue  # biased WIRED on raw-text hit
        searched_refs = sum(1 for f in refs_by_file if f != defining_file)
        out.unwired.append(Finding(
            file=defining_file,
            symbol=name,
            kind=sym.get("kind", "symbol"),
            module=os.path.basename(defining_file),
            lineno=sym["lineno"],
            severity="warning",
            pattern="UNWIRED_PATH",
            why=(
                f"Public symbol '{name}' has no non-test reference, no "
                f"registration, and no manifest entry"
            ),
            registration_found=False,
            searched_refs=searched_refs,
            dialect=dialect.language,
            language=dialect.language,
        ))

    # --- MOCKED_SEAM over acceptance files ---------------------------------
    # Scans ALL acceptance files in the worktree (not just authored ones):
    # a pre-existing acceptance test that mocks the authored seam hides the
    # missing wiring just the same.  The SEAM SET stays authored-only, so
    # attribution precision is preserved.
    acceptance_files = [
        f
        for f in _collect_source_files(worktree, dialect)
        if _is_acceptance_file(f, dialect)
    ]
    for rel_path in acceptance_files:
        source = _read_bytes(worktree / rel_path)
        if source is None:
            continue
        tree = _parse_or_none(source, dialect)
        if tree is None:
            continue
        out.acceptance_files_scanned += 1
        try:
            captures = _run_query_captures(
                dialect.mock_call_query, tree, dialect.ts_language_name
            )
        except Exception as exc:
            logger.warning(
                "mock_call_query failed for '%s': %s", dialect.language, exc
            )
            continue
        for node in captures.get("target", []):
            raw = _node_text(node, source)
            target = raw.strip("\"'")
            if not target:
                continue
            lineno = node.start_point[0] + 1
            base = dict(
                file=rel_path,
                kind="MOCKED_SEAM",
                lineno=lineno,
                pattern="MOCKED_SEAM",
                mock_kind="mock",
                dialect=dialect.language,
                language=dialect.language,
            )
            # Authored-seam attribution runs BEFORE the allowlist: an
            # authored seam whose name merely embeds an allow-listed string
            # (e.g. my_requests_handler ⊃ "requests") must still warn —
            # allowlist-first would be a false-green channel.
            if target in authored_seams or any(
                seam in target for seam in authored_seams
            ):
                out.mocked.append(Finding(
                    symbol=target,
                    severity="warning",
                    why=f"Acceptance test mocks authored seam: {target}",
                    authored_this_turn=True,
                    **base,
                ))
            elif any(ext in target for ext in dialect.external_mock_allowlist):
                out.mocks_ignored.append(Finding(
                    symbol=target,
                    severity="info",
                    why=f"External mock (allow-listed): {target}",
                    authored_this_turn=False,
                    **base,
                ))
            else:
                # Third-party, not authored, not allow-listed: surfaced as
                # info, never dropped (scope §4.2).
                out.mocked.append(Finding(
                    symbol=target,
                    severity="info",
                    why=f"Mock of non-authored target: {target}",
                    authored_this_turn=False,
                    **base,
                ))

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_wiring(
    authored_files: list[str],
    worktree_path: str | Path,
    task_type: str,
    stack: Any = None,
) -> dict[str, Any] | None:
    """Analyze wiring for the files authored this turn.

    Parameters
    ----------
    authored_files:
        Worktree-relative paths authored this turn (the authored set per
        scope §4: ``files_authored`` else ``files_created ∪ files_modified``).
    worktree_path:
        Path to the worktree root.
    task_type:
        Only ``FEATURE`` / ``REFACTOR`` / ``INTEGRATION`` are analyzed
        (case-insensitive); other task types legitimately produce
        un-wired stubs and return ``None``.
    stack:
        Optional object with a ``language`` attribute (e.g. a factory
        ``StackProfile``); used for dialect dispatch and
        unsupported-stack detection.  When absent, languages are inferred
        from authored file extensions — ALL matching dialects run
        (polyglot, AC-021).

    Returns
    -------
    dict | None
        The §5.1 result dict (see module docstring), or ``None`` when the
        probe legitimately did not run (task-type gate; zero authored
        non-test source targets).  Unexpected exceptions are caught and
        reported as ``status: "error"`` — fail-open to absent-signal,
        never a crash at the Coach seam.
    """
    try:
        return _analyze_wiring_impl(
            authored_files, Path(worktree_path), task_type, stack
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract
        logger.warning("analyze_wiring failed unexpectedly: %s", exc, exc_info=True)
        return {
            "status": "error",
            "error": str(exc),
            "dialect": None,
            "language": "",
            "dialects": [],
            "languages": [],
            "targets_scanned": 0,
            "symbols_examined": 0,
            "findings": [],
            "degraded_files": [],
            "mocked_seam": MockSeamResult(
                status="error", ran=False, skip_reason="analyzer error"
            ).to_dict(),
        }


def _unsupported_stack_dict(language: str) -> dict[str, Any]:
    """The unsupported-stack absent-signal result (never a pass — AC-009)."""
    return {
        "status": "unsupported_stack",
        "dialect": None,
        "language": language,
        "dialects": [],
        "languages": [language] if language else [],
        "targets_scanned": 0,
        "symbols_examined": 0,
        "findings": [],
        "degraded_files": [],
        "mocked_seam": MockSeamResult(
            status="unsupported_stack",
            ran=False,
            skip_reason=f"no dialect for language '{language}'",
        ).to_dict(),
    }


def _analyze_wiring_impl(
    authored_files: list[str],
    worktree: Path,
    task_type: str,
    stack: Any,
) -> dict[str, Any] | None:
    # --- Task-type gate (AC-008) -------------------------------------------
    if (task_type or "").upper() not in _ANALYZED_TASK_TYPES:
        return None

    stack_language: str | None = None
    if stack is not None and getattr(stack, "language", None):
        stack_language = str(stack.language)

    # --- Select candidate dialects: every registered dialect with ≥1
    # authored, non-test target (polyglot — AC-021) -------------------------
    candidates: list[tuple[WiringDialect, list[str]]] = []
    for dialect in iter_dialects():
        targets = [
            f
            for f in authored_files
            if _matches_glob(f, dialect.file_globs)
            and not _is_test_file(f, dialect)
            and (worktree / f).is_file()
        ]
        if targets:
            candidates.append((dialect, targets))

    if not candidates:
        # Stack explicitly names a language we have no dialect for →
        # absent-signal, never a silent pass (AC-009).
        if stack_language is not None:
            resolved = _find_language(stack_language)
            if resolved is None or get_dialect(resolved) is None:
                return _unsupported_stack_dict(stack_language)
            return None  # dialect exists; zero authored targets → probe didn't run
        # No stack: a known-but-undialected source extension is still an
        # absent-signal, not a silent None.
        for f in authored_files:
            ext = os.path.splitext(f)[1].lower()
            if ext in _KNOWN_UNDIALECTED_EXTENSIONS:
                return _unsupported_stack_dict(_KNOWN_UNDIALECTED_EXTENSIONS[ext])
        return None  # zero authored source targets → probe didn't run

    # --- Run every matching dialect ----------------------------------------
    analyses = [
        _analyze_dialect(targets, worktree, dialect)
        for dialect, targets in candidates
    ]

    # --- Merge --------------------------------------------------------------
    languages = [a.dialect.language for a in analyses]
    primary = languages[0]
    if stack_language is not None:
        resolved = _find_language(stack_language)
        if resolved in languages:
            primary = resolved

    degraded = [f for a in analyses for f in a.degraded_files]
    status: WiringStatus = "parse_degraded" if degraded else "complete"

    wiring = WiringResult(
        status=status,
        dialect=primary,
        language=primary,
        dialects=languages,
        languages=languages,
        targets_scanned=sum(a.targets_scanned for a in analyses),
        symbols_examined=sum(a.symbols_examined for a in analyses),
        findings=[f for a in analyses for f in a.unwired],
        degraded_files=degraded,
    )

    acceptance_scanned = sum(a.acceptance_files_scanned for a in analyses)
    mocked = MockSeamResult(
        status="ran" if acceptance_scanned else "skipped_no_acceptance_files",
        ran=bool(acceptance_scanned),
        skip_reason=None if acceptance_scanned else "no acceptance files found",
        dialect=primary,
        language=primary,
        findings=[f for a in analyses for f in a.mocked],
        external_mocks_ignored=[f for a in analyses for f in a.mocks_ignored],
    )

    result = wiring.to_dict()
    result["mocked_seam"] = mocked.to_dict()
    return result
