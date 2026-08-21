"""CALLSITE_DRIFT — deterministic call-site / signature-drift scan (WS3-S3 2b).

The ctor-arity mechanic generalized from ``__init__`` to every first-party
callable (module-level functions AND ``ClassName(...)`` constructors), plus
keyword-*name* binding (not just arity counts).  This check requires **no test
honesty at all** — it binds production call sites against production signatures
statically, which is why it, not the signature-binding-fake scan (2a), is the
primary DD4F / SMP3-06 killer.

Two apertures (S2 design §3.2, the load-bearing R2a-4 / R2b-1 correction):

* **Aperture A — changed-signature × stale-site.**  Callables whose signature
  changed this turn/wave (vs the feature-base baseline), bound against their
  existing call sites repo-wide.  The SMP3-06 shape (a signature loses a param;
  a stale call site keeps passing the retired kwarg → ``unknown_kwarg``).
  Requires ``baseline_sources`` (the feature-base file contents), which guardkit
  supplies — the analyzer stays git-free and stack-agnostic.

* **Aperture B — authored-site × current-signature.**  Call sites authored or
  modified this turn/wave, bound against the *current* (possibly unchanged)
  signature of their resolved callee.  The literal DD4F shape (a NEW wrong call
  against an UNCHANGED signature).  Needs no baseline.

Signature model is the **named ``(name, kind, has_default)`` tuple** (R2b-3),
NOT the shipped counts summary — a same-arity kwarg rename preserves counts and
must still be caught.

Design-boundary note (dated 2026-07-09, WS3-S3): the S2 spec §3.2.6 folds
keyword-name binding "into the shipped CTOR_ARITY probe".  This implementation
lands it in CALLSITE_DRIFT's own result key instead, covering functions AND
``ClassName(...)`` ctors through one shared signature model, so the shipped
counts-based ``CtorArityResult`` and its tests are left untouched (they keep
catching the pure count cases; CALLSITE_DRIFT adds the *name* cases).  One
mechanic, one place — the §3.2.6 intent — realized as an additive sibling
rather than a mutation of the shipped probe.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
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
    splat_kind,
)
from guardkitfactory.wiring.dialect import (
    WiringDialect,
    get_dialect,
    iter_dialects,
)

logger = logging.getLogger(__name__)

_ANALYZED_TASK_TYPES = {"FEATURE", "REFACTOR", "INTEGRATION"}


# ---------------------------------------------------------------------------
# Signature model — the named (name, kind, has_default) tuple (R2b-3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ParamSpec:
    """One parameter: name, binding kind, and default-presence."""

    name: str
    kind: str  # "pos_only" | "pos_or_kw" | "kw_only"
    has_default: bool


@dataclass
class _Signature:
    """A callable's bind-relevant signature (functions and ctors alike)."""

    name: str
    params: tuple[_ParamSpec, ...]
    has_var_positional: bool  # *args
    has_var_keyword: bool  # **kwargs
    lineno: int = 0
    file: str = ""
    is_ctor: bool = False

    def bind_tuple(self) -> tuple:
        """The value used for 'signature differs' comparison (aperture A).

        Excludes annotations and default *values* by construction (they are
        not captured) — only param name/kind/has_default + variadic flags.
        """
        return (
            tuple((p.name, p.kind, p.has_default) for p in self.params),
            self.has_var_positional,
            self.has_var_keyword,
        )

    @property
    def param_names(self) -> set[str]:
        return {p.name for p in self.params}

    @property
    def max_positional(self) -> int:
        return sum(1 for p in self.params if p.kind in ("pos_only", "pos_or_kw"))

    def required_unsatisfied(self, positional: int, kw_names: set[str]) -> list[str]:
        """Required params not satisfied by the observed positional/keyword args."""
        missing: list[str] = []
        pos_index = 0
        for p in self.params:
            if p.has_default:
                continue
            if p.kind in ("pos_only", "pos_or_kw"):
                if pos_index < positional:
                    pos_index += 1
                    continue
                if p.name in kw_names:
                    continue
                missing.append(p.name)
            else:  # kw_only, required
                if p.name not in kw_names:
                    missing.append(p.name)
        return missing


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class _DriftFinding:
    file: str
    lineno: int
    callee: str
    form: str  # unknown_kwarg | excess_positional | missing_required
    aperture: str  # A | B
    why: str
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "lineno": self.lineno,
            "symbol": self.callee,
            "kind": "CALLSITE_DRIFT",
            "pattern": "CALLSITE_DRIFT",
            "form": self.form,
            "aperture": self.aperture,
            "why": self.why,
            "severity": self.severity,
            "authored_this_turn": True,
        }


@dataclass
class CallsiteDriftResult:
    """Result of a CALLSITE_DRIFT run (nested under ``callsite_drift``).

    ``ran=False`` (no targets, no dialect, unsupported stack) is an **absent**
    signal — never a pass, never a block (absence-of-failure).  ``status`` is
    always serialized so absence survives every reconciliation layer.
    """

    status: str = "skipped_no_targets"
    ran: bool = False
    skip_reason: str | None = "no authored source targets"
    dialect: str | None = None
    language: str = ""
    apertures_run: tuple[str, ...] = ()
    findings: list[_DriftFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ran": self.ran,
            "skip_reason": self.skip_reason,
            "dialect": self.dialect,
            "language": self.language,
            "apertures_run": list(self.apertures_run),
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------


def _summarise_signature(
    params_node: Any,
    source: bytes,
    dialect: WiringDialect,
    *,
    drop_receiver: bool = False,
) -> tuple[tuple[_ParamSpec, ...], bool, bool]:
    """Build ordered ``_ParamSpec`` tuple + (var_positional, var_keyword).

    Handles Python's ``*``/``/`` separators (``keyword_separator`` /
    ``positional_separator``) so kw-only and pos-only params carry the right
    kind (pinned against the live grammar).

    ``drop_receiver`` removes the implicit first argument a METHOD gets for
    free (``self`` / ``cls``), which the caller never writes.  It is off by
    default: a plain module-level ``def validate_markdown_file(cls, path)`` has
    an ordinary parameter that merely happens to be spelled ``cls``, and
    deleting it made the scan believe the function took one value, not two.
    """
    specs: list[_ParamSpec] = []
    kw_only = False
    pos_only_upto: int | None = None
    var_positional = False
    var_keyword = False
    seen_a_param = False
    for child in params_node.named_children:
        ctype = child.type
        if ctype in dialect.trivia_node_types:  # a comment is not a parameter
            continue
        if ctype == "keyword_separator":  # bare `*`
            kw_only = True
            continue
        if ctype == "positional_separator":  # `/`
            pos_only_upto = len(specs)
            continue
        splat = splat_kind(child, dialect)
        if splat:
            # An annotated catch-all (`*args: int`, `**kw: Any`) parses as a
            # wrapper around the pattern; unwrap so both spellings read alike.
            pattern = child if ctype == splat else child.named_children[0]
            # *args has an identifier child; a bare `*` is keyword_separator
            # (handled above), so a splat-pattern here is a real variadic.
            has_name = any(c.type == "identifier" for c in pattern.named_children)
            if splat == "list_splat_pattern":
                if has_name:
                    var_positional = True
                    seen_a_param = True
                else:
                    kw_only = True  # defensive: bare `*` as splat pattern
            else:  # dictionary_splat_pattern
                var_keyword = True
                seen_a_param = True
            continue
        # regular param node (identifier / typed_parameter / *default*)
        name = _first_identifier(child, source)
        if not name:
            continue
        if drop_receiver and not seen_a_param and name in dialect.param_self_names:
            seen_a_param = True
            continue
        seen_a_param = True
        has_default = ctype in dialect.param_default_node_types
        specs.append(_ParamSpec(
            name=name, kind="kw_only" if kw_only else "pos_or_kw", has_default=has_default,
        ))
    if pos_only_upto is not None:
        specs = [
            (_ParamSpec(p.name, "pos_only", p.has_default) if i < pos_only_upto else p)
            for i, p in enumerate(specs)
        ]
    return tuple(specs), var_positional, var_keyword


def _first_identifier(node: Any, source: bytes) -> str:
    if node.type == "identifier":
        return _node_text(node, source)
    for child in node.children:
        if child.type == "identifier":
            return _node_text(child, source)
    return ""


def _decorator_names(name_node: Any, source: bytes) -> list[str]:
    """Bare names of the decorators sitting above a definition.

    ``@click.option("--x")`` yields ``"option"``; ``@functools.cache`` yields
    ``"cache"``.  Returns an empty list for an undecorated definition.
    """
    fn = name_node.parent
    holder = fn.parent if fn is not None else None
    if holder is None or "decorated" not in holder.type:
        return []
    out: list[str] = []
    for child in holder.named_children:
        if child.type != "decorator":
            continue
        text = _node_text(child, source).lstrip("@").split("(")[0].strip()
        if text:
            out.append(text.split(".")[-1])
    return out


def _signature_survives_its_decorators(
    name_node: Any, source: bytes, dialect: WiringDialect
) -> bool:
    """True when the ``def`` line still describes how the name is called.

    A decorator may replace the function entirely: ``@click.group()`` swaps it
    for a command object called with ``obj=`` / ``standalone_mode=``, names the
    ``def`` line never mentions.  Reading the ``def`` line in that case is
    guesswork, so unless every decorator is on the known signature-preserving
    list the signature is withheld and the scan stays silent.

    Dialects that declare no list keep the previous behaviour (no gating).
    """
    if not dialect.signature_preserving_decorators:
        return True
    return all(
        d in dialect.signature_preserving_decorators
        for d in _decorator_names(name_node, source)
    )


def _dotted(parts: tuple[str, ...]) -> str:
    """Join path segments into a dotted module name (``__init__`` = its package)."""
    if not parts:
        return ""
    stem = parts[-1].rsplit(".", 1)[0]
    pkg = parts[:-1] if stem == "__init__" else parts[:-1] + (stem,)
    return ".".join(pkg)


def module_aliases(rel_path: str, dialect: WiringDialect) -> tuple[str, ...]:
    """Every dotted module name this file can legitimately be imported as.

    A repository whose code lives under ``src/`` can be laid out two ways, and
    the file path alone does not say which:

    * ``src/`` is a packaging wrapper that is NOT part of the import path —
      forge installs ``src/forge/cli/serve.py`` as ``forge.cli.serve``; or
    * ``src/`` is itself the top package — api_test's own modules import
      ``from src.core.config import settings``, so ``src/core/config.py`` is
      the module ``src.core.config``.

    Stripping ``src/`` unconditionally was right for the first layout and wrong
    for the second, and being wrong there meant the checker could not match a
    single internal import in that repository and went completely silent —
    including on api_test, the surface the build pipeline actually works in.

    So BOTH readings are published and an import resolves under whichever name
    it actually writes.  A repository uses one convention throughout, so the
    unused alias is simply never named.
    """
    parts = tuple(rel_path.replace(os.sep, "/").strip("/").split("/"))
    if not parts:
        return ()
    names: list[str] = []
    full = _dotted(parts)
    if full:
        names.append(full)
    if parts[0] in dialect.source_root_dirs:
        stripped = _dotted(parts[1:])
        if stripped and stripped not in names:
            names.append(stripped)
    return tuple(names)


def module_dotted_names(rel_path: str, dialect: WiringDialect) -> set[str]:
    """Dotted module names a source file provides, plus its parent packages.

    ``src/forge/cli/serve.py`` provides ``forge.cli.serve`` (and, under the
    other layout this path allows, ``src.forge.cli.serve``) and implies the
    packages ``forge`` / ``forge.cli`` / ``src`` / ``src.forge`` ...  Used to
    decide whether an imported name comes from THIS repository.
    """
    out: set[str] = set()
    for alias in module_aliases(rel_path, dialect):
        segs = alias.split(".")
        out |= {".".join(segs[:i]) for i in range(1, len(segs) + 1)}
    return out


def absolute_module(origin: str, importing_package: str) -> str:
    """Turn an import's module reference into an absolute dotted module name.

    ``from .helpers import x`` written in any file of package ``app`` refers to
    ``app.helpers``; ``from ..core import y`` in package ``a.b.c`` refers to
    ``a.b.core``.  An already-absolute reference is returned unchanged.

    The anchor is the importing file's PACKAGE, not its module — that is what
    Python uses, and it is the difference between a package's own ``__init__``
    re-export pointing inward (correct) and pointing at its parent (wrong).
    """
    if not origin.startswith("."):
        return origin
    dots = len(origin) - len(origin.lstrip("."))
    remainder = origin[dots:]
    base = importing_package.split(".") if importing_package else []
    # One dot = the importing file's own package; each extra dot climbs one.
    base = base[: len(base) - (dots - 1)] if dots > 1 else base
    parts = [q for q in (*base, *remainder.split(".")) if q]
    return ".".join(parts)


def own_package(rel_path: str, dialect: WiringDialect) -> str:
    """The dotted package a source file lives in — the anchor for ``from .x``."""
    parts = tuple(rel_path.replace(os.sep, "/").strip("/").split("/"))
    if parts and parts[0] in dialect.source_root_dirs:
        parts = parts[1:]
    return ".".join(parts[:-1])


def _is_first_party_module(origin: str, first_party_modules: set[str]) -> bool:
    """Is ``origin`` a module that lives in this repository?

    A relative import (``from .helpers import build``) is first-party by
    construction.  Anything else must match a module the repository actually
    provides — otherwise the scan cannot tell whose function it is and, per the
    bias-to-silence posture, says nothing.
    """
    if not origin:
        return False
    if origin.startswith("."):
        return True
    return origin in first_party_modules


def _extract_signatures(
    source: bytes, tree: Any, dialect: WiringDialect, rel_path: str
) -> dict[str, _Signature]:
    """Extract ``{callable_name: _Signature}`` for module functions + ctors.

    Duplicate same-name defs in one module (``@overload`` + impl,
    version-conditional) are dropped from the map (``skipped_ambiguous_defs``
    posture — never a false bind).
    """
    sigs: dict[str, _Signature] = {}
    ambiguous: set[str] = set()

    def _add(name: str, sig: _Signature) -> None:
        if name in sigs or name in ambiguous:
            ambiguous.add(name)
            sigs.pop(name, None)
            return
        sigs[name] = sig

    # Module-level functions.
    if dialect.function_signature_query:
        try:
            for captures in _run_query_matches(
                dialect.function_signature_query, tree, dialect.ts_language_name
            ):
                names = captures.get("name", [])
                params = captures.get("params", [])
                if not names or not params:
                    continue
                fname = _node_text(names[0], source)
                if not _signature_survives_its_decorators(names[0], source, dialect):
                    continue  # decorator rewrites the call shape → stay silent
                specs, vp, vk = _summarise_signature(params[0], source, dialect)
                _add(fname, _Signature(
                    name=fname, params=specs, has_var_positional=vp,
                    has_var_keyword=vk, lineno=names[0].start_point[0] + 1,
                    file=rel_path, is_ctor=False,
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("function_signature_query failed for %s: %s", rel_path, exc)

    # Class constructors (reuse the shipped ctor-signature query).
    if dialect.constructor_signature_query:
        try:
            for captures in _run_query_matches(
                dialect.constructor_signature_query, tree, dialect.ts_language_name
            ):
                classes = captures.get("class", [])
                params = captures.get("params", [])
                if not classes or not params:
                    continue
                cname = _node_text(classes[0], source)
                # A constructor's leading `self` is supplied by Python, never
                # written by the caller.
                specs, vp, vk = _summarise_signature(
                    params[0], source, dialect, drop_receiver=True
                )
                _add(cname, _Signature(
                    name=cname, params=specs, has_var_positional=vp,
                    has_var_keyword=vk, lineno=classes[0].start_point[0] + 1,
                    file=rel_path, is_ctor=True,
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("constructor_signature_query failed for %s: %s", rel_path, exc)

    return sigs


# ---------------------------------------------------------------------------
# Import map
# ---------------------------------------------------------------------------


def _build_import_map(
    source: bytes, tree: Any, dialect: WiringDialect
) -> dict[str, tuple[str, str]]:
    """Per-file ``local_name -> (origin_module, original_name)``.

    Aliases resolve by construction (``from x import fn as f`` → ``f``;
    ``import a.b as m`` → ``m``).  Only ``from module import name`` forms carry
    an original-name mapping used for callee resolution; plain ``import mod``
    maps the module local name to ``(mod, "")``.
    """
    imap: dict[str, tuple[str, str]] = {}
    if not dialect.imports_query:
        return imap
    try:
        matches = _run_query_matches(dialect.imports_query, tree, dialect.ts_language_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("imports_query failed: %s", exc)
        return imap
    for captures in matches:
        for node in captures.get("imp", []):
            _parse_import_node(node, source, imap)
    return imap


def _parse_import_node(node: Any, source: bytes, imap: dict[str, tuple[str, str]]) -> None:
    """Populate the import map from one import node (Python)."""
    if node.type == "import_from_statement":
        # module_name child = the from-module; the rest are imported names,
        # each possibly `aliased_import`.
        module_name = ""
        name_nodes: list[Any] = []
        for child in node.named_children:
            if child.type in ("dotted_name", "relative_import") and not module_name:
                module_name = _node_text(child, source)
            elif child.type == "dotted_name":
                name_nodes.append(child)
            elif child.type == "aliased_import":
                name_nodes.append(child)
            elif child.type == "wildcard_import":
                pass
        # The grammar makes the first dotted_name the module; subsequent ones
        # (and aliased_import) are imported names.
        first = True
        module = ""
        for child in node.named_children:
            if child.type in ("dotted_name", "relative_import") and first:
                module = _node_text(child, source)
                first = False
                continue
            if child.type == "dotted_name":
                orig = _node_text(child, source)
                imap[orig] = (module, orig)
            elif child.type == "aliased_import":
                # `name as alias`
                names = [c for c in child.named_children if c.type == "dotted_name"]
                alias = [c for c in child.named_children if c.type == "identifier"]
                if names:
                    orig = _node_text(names[0], source)
                    local = _node_text(alias[0], source) if alias else orig
                    imap[local] = (module, orig)
    elif node.type == "import_statement":
        # `import a.b` / `import a.b as m`
        for child in node.named_children:
            if child.type == "dotted_name":
                mod = _node_text(child, source)
                local = mod.split(".")[-1]
                imap[local] = (mod, "")
            elif child.type == "aliased_import":
                names = [c for c in child.named_children if c.type == "dotted_name"]
                alias = [c for c in child.named_children if c.type == "identifier"]
                if names:
                    mod = _node_text(names[0], source)
                    local = _node_text(alias[0], source) if alias else mod.split(".")[-1]
                    imap[local] = (mod, "")


# ---------------------------------------------------------------------------
# Call-site extraction + bind check
# ---------------------------------------------------------------------------


def _extract_call_sites(
    source: bytes, tree: Any, dialect: WiringDialect
) -> list[tuple[str, Any, int]]:
    """Return ``(callee_name, args_node, lineno)`` for bare-identifier calls."""
    out: list[tuple[str, Any, int]] = []
    if not dialect.call_site_query:
        return out
    try:
        matches = _run_query_matches(dialect.call_site_query, tree, dialect.ts_language_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("call_site_query failed: %s", exc)
        return out
    for captures in matches:
        callee = captures.get("callee", [])
        args = captures.get("args", [])
        if not callee or not args:
            continue
        # Only bare-identifier callees whose parent `call.function` IS the
        # identifier (attribute callees are captured too but resolved only for
        # module bases — deferred, accepted FN R2b-8/R2b-11).
        cnode = callee[0]
        parent = cnode.parent
        if parent is None or parent.type != "call":
            continue  # attribute callee → base is not a module here; skip (FN)
        out.append((_node_text(cnode, source), args[0], cnode.start_point[0] + 1))
    return out


def _summarise_call(
    args_node: Any, source: bytes, dialect: WiringDialect
) -> tuple[int, set[str], bool]:
    """Return ``(positional_count, keyword_names, splat_present)``."""
    positional = 0
    kw_names: set[str] = set()
    splat = False
    for child in args_node.named_children:
        ctype = child.type
        if ctype in dialect.trivia_node_types:
            continue  # a `# type: ignore` note inside the brackets is not a value
        if ctype in dialect.arg_splat_node_types:
            splat = True
        elif ctype in dialect.arg_keyword_node_types:
            name = _first_identifier(child, source)
            if name:
                kw_names.add(name)
        else:
            positional += 1
    return positional, kw_names, splat


def _bind_check(
    sig: _Signature,
    positional: int,
    kw_names: set[str],
    call_splat: bool,
    callee: str,
    rel_path: str,
    lineno: int,
    aperture: str,
) -> _DriftFinding | None:
    """Bind observed args against ``sig``; return a finding or None (bias-to-no-finding)."""
    if call_splat:
        return None  # splat at call site → arity/names unknowable (bias OK)
    # unknown_kwarg: a keyword name not in params, with no **kwargs.
    if not sig.has_var_keyword:
        unknown = sorted(k for k in kw_names if k not in sig.param_names)
        if unknown:
            return _DriftFinding(
                file=rel_path, lineno=lineno, callee=callee, form="unknown_kwarg",
                aperture=aperture,
                why=(
                    f"call to '{callee}' passes keyword arg(s) {unknown} that its "
                    f"signature ({sig.file}:{sig.lineno}) does not accept and it has "
                    f"no **kwargs — a TypeError at runtime"
                ),
            )
    # excess_positional
    if not sig.has_var_positional and positional > sig.max_positional:
        return _DriftFinding(
            file=rel_path, lineno=lineno, callee=callee, form="excess_positional",
            aperture=aperture,
            why=(
                f"call to '{callee}' passes {positional} positional arg(s) but its "
                f"signature accepts at most {sig.max_positional}"
            ),
        )
    # missing_required
    missing = sig.required_unsatisfied(positional, kw_names)
    if missing:
        return _DriftFinding(
            file=rel_path, lineno=lineno, callee=callee, form="missing_required",
            aperture=aperture,
            why=(
                f"call to '{callee}' does not satisfy required param(s) {missing} "
                f"(signature {sig.file}:{sig.lineno})"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_callsite_drift(
    authored_files: list[str],
    worktree_path: str | Path,
    task_type: str,
    *,
    baseline_sources: dict[str, bytes] | None = None,
    stack: Any = None,
) -> dict[str, Any] | None:
    """Run CALLSITE_DRIFT (both apertures) over the authored set.

    Parameters
    ----------
    authored_files:
        Worktree-relative paths authored this turn/wave.
    worktree_path:
        Worktree root.
    task_type:
        Only FEATURE / REFACTOR / INTEGRATION run (case-insensitive).
    baseline_sources:
        Optional ``{rel_path: bytes}`` feature-base file contents.  When
        provided, aperture A (changed-signature × stale-site) runs; when
        absent, only aperture B (authored-site × current-signature).
    stack:
        Optional object with a ``language`` attribute (dialect hint).

    Returns
    -------
    dict | None
        The ``callsite_drift`` sub-result dict, or ``None`` when task-type
        gated / zero source targets.  Fail-open to absent on any error.
    """
    try:
        return _impl(
            authored_files, Path(worktree_path), task_type, baseline_sources or {}, stack
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract
        logger.warning("analyze_callsite_drift failed unexpectedly: %s", exc, exc_info=True)
        return CallsiteDriftResult(
            status="error", ran=False, skip_reason="analyzer error"
        ).to_dict()


def _dialect_for(stack: Any) -> WiringDialect | None:
    if stack is not None and getattr(stack, "language", None):
        d = get_dialect(str(stack.language))
        if d is not None:
            return d
    return None


def _impl(
    authored_files: list[str],
    worktree: Path,
    task_type: str,
    baseline_sources: dict[str, bytes],
    stack: Any,
) -> dict[str, Any] | None:
    if (task_type or "").upper() not in _ANALYZED_TASK_TYPES:
        return None

    # Pick the Python-family dialect(s) with ≥1 authored non-test source target.
    candidates: list[tuple[WiringDialect, list[str]]] = []
    for dialect in iter_dialects():
        if not dialect.call_site_query or not dialect.function_signature_query:
            continue  # probe is a no-op for this dialect (absent-signal)
        targets = [
            f for f in authored_files
            if _matches_glob(f, dialect.file_globs)
            and not _is_test_file(f, dialect)
            and (worktree / f).is_file()
        ]
        if targets:
            candidates.append((dialect, targets))
    if not candidates:
        return None  # zero authored source targets → probe didn't run

    all_findings: list[_DriftFinding] = []
    apertures: set[str] = set()
    primary = candidates[0][0]

    for dialect, targets in candidates:
        findings, ap = _run_dialect(dialect, targets, worktree, baseline_sources)
        all_findings.extend(findings)
        apertures |= ap

    result = CallsiteDriftResult(
        status="ran",
        ran=True,
        skip_reason=None,
        dialect=primary.language,
        language=primary.language,
        apertures_run=tuple(sorted(apertures)),
        findings=all_findings,
    )
    return result.to_dict()


def _run_dialect(
    dialect: WiringDialect,
    authored_targets: list[str],
    worktree: Path,
    baseline_sources: dict[str, bytes],
) -> tuple[list[_DriftFinding], set[str]]:
    findings: list[_DriftFinding] = []
    apertures: set[str] = set()

    # --- Current worktree signatures (all non-test source, repo-wide) --------
    current_sigs: dict[str, _Signature] = {}
    sigs_by_module: dict[tuple[str, str], _Signature] = {}
    # module -> (its import map, its package) so a re-export can be followed
    # back to the module that actually defines the name.
    import_maps: dict[str, tuple[dict[str, tuple[str, str]], str]] = {}
    # Every dotted module name this repository provides, so an imported callee
    # can be told apart from a same-named third-party one.
    first_party_modules: set[str] = set()
    # A dotted module name claimed by two different files (a repo holding both
    # `src/app.py` and `app.py`) cannot be resolved — it is dropped below so
    # the scan stays silent rather than binding against whichever came first.
    alias_owner: dict[str, str] = {}
    contested_modules: set[str] = set()
    for rel in _collect_source_files(worktree, dialect):
        if _is_test_file(rel, dialect):
            continue
        aliases = module_aliases(rel, dialect)
        for alias in aliases:
            if alias_owner.setdefault(alias, rel) != rel:
                contested_modules.add(alias)
        first_party_modules |= module_dotted_names(rel, dialect)
        src = _read_bytes(worktree / rel)
        if src is None:
            continue
        tree = _parse_or_none(src, dialect)
        if tree is None:
            continue
        if aliases:
            imap_here = _build_import_map(src, tree, dialect)
            package_here = own_package(rel, dialect)
            for alias in aliases:
                import_maps.setdefault(alias, (imap_here, package_here))
        for name, sig in _extract_signatures(src, tree, dialect, rel).items():
            # `current_sigs` (bare name, first wins) is used ONLY to decide
            # which signatures changed this turn (aperture A).  Binding a call
            # always goes through `sigs_by_module`, which cannot confuse two
            # same-named functions in different modules.
            current_sigs.setdefault(name, sig)
            for alias in aliases:
                sigs_by_module.setdefault((alias, name), sig)
    for contested in contested_modules:
        import_maps.pop(contested, None)
        for key in [k for k in sigs_by_module if k[0] == contested]:
            del sigs_by_module[key]

    authored_set = {os.path.normpath(f) for f in authored_targets}

    # --- Aperture B: authored call sites × current signature -----------------
    for rel in authored_targets:
        src = _read_bytes(worktree / rel)
        if src is None:
            continue
        tree = _parse_or_none(src, dialect)
        if tree is None:
            continue
        apertures.add("B")
        imap = _build_import_map(src, tree, dialect)
        local_sigs = _extract_signatures(src, tree, dialect, rel)
        for callee, args_node, lineno in _extract_call_sites(src, tree, dialect):
            sig = _resolve_callee(
                callee, local_sigs, imap, sigs_by_module, import_maps,
                first_party_modules, own_package(rel, dialect),
            )
            if sig is None:
                continue
            positional, kw_names, splat = _summarise_call(args_node, src, dialect)
            f = _bind_check(sig, positional, kw_names, splat, callee, rel, lineno, "B")
            if f is not None:
                findings.append(f)

    # --- Aperture A: changed signatures × stale call sites repo-wide ---------
    if baseline_sources:
        baseline_sigs: dict[str, _Signature] = {}
        for rel, src in baseline_sources.items():
            if _is_test_file(rel, dialect) or not _matches_glob(rel, dialect.file_globs):
                continue
            tree = _parse_or_none(src, dialect)
            if tree is None:
                continue
            for name, sig in _extract_signatures(src, tree, dialect, rel).items():
                baseline_sigs.setdefault(name, sig)
        changed = {
            name
            for name, cur in current_sigs.items()
            if name in baseline_sigs and baseline_sigs[name].bind_tuple() != cur.bind_tuple()
        }
        if changed:
            apertures.add("A")
            for rel in _collect_source_files(worktree, dialect):
                if _is_test_file(rel, dialect):
                    continue
                # Aperture B already covered authored files; A targets the STALE
                # (unchanged-this-turn) sites — skip authored files here.
                if os.path.normpath(rel) in authored_set:
                    continue
                src = _read_bytes(worktree / rel)
                if src is None:
                    continue
                tree = _parse_or_none(src, dialect)
                if tree is None:
                    continue
                imap = _build_import_map(src, tree, dialect)
                local_sigs = _extract_signatures(src, tree, dialect, rel)
                for callee, args_node, lineno in _extract_call_sites(src, tree, dialect):
                    if callee not in changed:
                        continue
                    sig = _resolve_callee(
                        callee, local_sigs, imap, sigs_by_module, import_maps,
                        first_party_modules, own_package(rel, dialect),
                    )
                    if sig is None or sig.name not in changed:
                        continue
                    positional, kw_names, splat = _summarise_call(args_node, src, dialect)
                    f = _bind_check(sig, positional, kw_names, splat, callee, rel, lineno, "A")
                    if f is not None:
                        findings.append(f)

    return findings, apertures


def _resolve_callee(
    callee: str,
    local_sigs: dict[str, _Signature],
    imap: dict[str, tuple[str, str]],
    sigs_by_module: dict[tuple[str, str], _Signature],
    import_maps: dict[str, tuple[dict[str, tuple[str, str]], str]],
    first_party_modules: set[str],
    importing_package: str,
) -> _Signature | None:
    """Resolve a bare-identifier callee to the signature it will actually call.

    Same-file definitions resolve trivially.  An IMPORTED name resolves only
    when BOTH of these hold:

    * the module it was imported FROM belongs to this repository — otherwise
      the scan would check, say, SQLAlchemy's ``create_async_engine`` against an
      unrelated local function of the same name; and
    * that exact module really defines that exact name.  Looking the name up
      across the whole repository and taking the first hit is what made
      ``from forge.adapters.guardkit.run import run`` land on an unrelated
      ``run`` in ``scripts/`` and report a TypeError that cannot happen.

    Where origin cannot be established the scan says nothing.  That is the
    posture of this probe throughout: a silent check beats one that cries wolf.
    A plain ``import some.module`` binds a MODULE name, not a callable, so it
    never resolves either.
    """
    if callee in local_sigs:
        return local_sigs[callee]
    entry = imap.get(callee)
    if entry is None:
        return None
    origin, original = entry
    if not original:
        return None  # `import mod` — the local name is a module, not a function
    absolute = absolute_module(origin, importing_package)
    return _follow_to_definition(
        absolute, original, sigs_by_module, import_maps, first_party_modules
    )


_MAX_REEXPORT_HOPS = 4


def _follow_to_definition(
    module: str,
    name: str,
    sigs_by_module: dict[tuple[str, str], _Signature],
    import_maps: dict[str, tuple[dict[str, tuple[str, str]], str]],
    first_party_modules: set[str],
    _hops: int = 0,
) -> _Signature | None:
    """Find where ``module.name`` is really DEFINED, hopping through re-exports.

    Packages routinely publish a name from a private module through their
    ``__init__``: ``guardkit.orchestrator.harness`` exposes ``select_harness``,
    which is written in ``guardkit.orchestrator.harness.selector``.  Without
    following that hop the scan cannot see the signature at all and goes quiet,
    losing real detections.  Bounded to a few hops so an import cycle cannot
    spin.
    """
    if not _is_first_party_module(module, first_party_modules):
        return None  # third-party (or unknown) origin → stay silent
    sig = sigs_by_module.get((module, name))
    if sig is not None:
        return sig
    if _hops >= _MAX_REEXPORT_HOPS:
        return None
    entry = import_maps.get(module)
    if entry is None:
        return None
    imap, package = entry
    hop = imap.get(name)
    if hop is None:
        return None
    origin, original = hop
    if not original:
        return None
    return _follow_to_definition(
        absolute_module(origin, package), original,
        sigs_by_module, import_maps, first_party_modules, _hops + 1,
    )
