"""WiringDialect: frozen dataclass + registry for declarative per-language descriptors.

A dialect is a frozen dataclass ``WiringDialect``, one record per language,
registered in a per-language module under ``wiring/dialects/``.  Every field
is DATA — tree-sitter S-expression query strings and pattern lists, no
executable plugin code.

The registry maps a language name (e.g. ``"python"``) to its dialect
descriptor.  Dialects are registered at import time by their respective
``wiring.dialects.<lang>`` modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, WiringDialect] = {}


def register_dialect(dialect: WiringDialect) -> WiringDialect:
    """Register a wiring dialect in the global registry.

    Returns *dialect* for use as a decorator / return-value.
    """
    _registry[dialect.language] = dialect
    return dialect


def get_dialect(language: str) -> WiringDialect | None:
    """Look up a dialect by language name.

    Returns ``None`` when no dialect is registered for *language*.
    """
    return _registry.get(language)


def iter_dialects() -> Iterator[WiringDialect]:
    """Iterate over all registered dialects (insertion order)."""
    yield from _registry.values()


# ---------------------------------------------------------------------------
# WiringDialect
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WiringDialect:
    """Declarative descriptor for one language's wiring-analysis queries.

    Parameters
    ----------
    language:
        Human-readable language name used in findings (``"python"``,
        ``"javascript"``, ``"typescript"``, ``"c_sharp"``).
    ts_language_name:
        Canonical key passed to ``tree_sitter_language_pack.get_language()``
        (``"python"``, ``"javascript"``, ``"typescript"``, ``"csharp"`` —
        note ``"csharp"``, NOT ``"c_sharp"``, for the pack key).
    file_globs:
        Glob patterns for source files of this language.
    public_symbols_query:
        tree-sitter S-expression that captures public top-level
        function/class/export declarations plus their ``@name`` capture.
        May also capture ``@visibility`` (e.g. C# modifiers); the analyzer
        pairs ``@visibility`` with ``@name`` per match and applies
        ``public_visibilities``.
    references_query:
        tree-sitter S-expression that captures identifier / member-access
        nodes used for reference detection.
    registration_queries:
        One or more S-expressions that match composition-root binding
        patterns (e.g. ``cli.add_command(X)``, ``AddScoped<X>()``).  The
        registered symbol must be captured as ``@target``.
    mock_call_query:
        S-expression that captures mock/patch primitive calls plus their
        target argument as ``@target``.  Use tree-sitter predicates
        (``#any-of?``/``#eq?``) to restrict to actual mock primitives —
        an unrestricted call query floods MOCKED_SEAM with false targets.
    test_path_markers:
        Path substrings that identify test files (excluded from wiring
        analysis targets and from the reference map).
    acceptance_path_markers:
        Path substrings that identify acceptance/integration test files
        (scanned for MOCKED_SEAM).
    external_mock_allowlist:
        Module names whose mocking is acceptable (e.g. ``"httpx"``,
        ``"requests"``).
    external_mock_path_roots:
        Path substrings indicating external-adapter code whose mocking
        is acceptable.
    script_manifest_files:
        Filenames (or globs, e.g. ``"*.csproj"``) of package manifests
        used for registration detection.
    private_name_prefixes:
        Name prefixes that mark a symbol as private (``("_",)`` for
        Python).  Private symbols are never UNWIRED candidates.
    public_visibilities:
        When the ``public_symbols_query`` captures ``@visibility``, only
        matches whose visibility text is in this tuple count as public
        (``("public", "internal")`` for C#).  Empty tuple = no visibility
        gating (every ``@name`` match is a candidate).
    smoke_snippet:
        A canonical source snippet for :meth:`smoke_test` (AC-019): the
        snippet is parsed with the live grammar and the
        ``public_symbols_query`` must capture ``smoke_expected_symbol``.
    smoke_expected_symbol:
        The symbol name :meth:`smoke_test` expects to capture from
        ``smoke_snippet``.
    composition_root_markers:
        Path substrings identifying the composition root(s) — the
        ``main.py`` / app-factory / DI-wiring files where first-party
        services are constructed (e.g. ``("/main.py", "__main__.py",
        "/app.py", "container", "/wiring")``).  The CTOR_ARITY probe only
        scans constructor calls inside these files.  Empty ⇒ the probe is a
        no-op for this dialect (absent-signal, never a pass — AC#5).
    constructor_signature_query:
        S-expression capturing a class declaration's name as ``@class`` and
        its constructor parameter list as ``@params`` (Python: a
        ``class_definition`` whose body defines ``__init__``).  Empty ⇒
        ctor-arity does not run for this dialect.
    constructor_call_query:
        S-expression capturing a constructor call's callee identifier as
        ``@class`` and its argument list as ``@args``.  Empty ⇒ ctor-arity
        does not run.
    param_self_names:
        Parameter names excluded from the required-arg count (``("self",
        "cls")`` for Python).
    param_default_node_types:
        Parameter node types that carry a default value (Python:
        ``default_parameter``, ``typed_default_parameter``) — NOT required.
    param_splat_node_types:
        Parameter node types making the signature's arity unknowable
        (Python: ``list_splat_pattern``, ``dictionary_splat_pattern``).  Any
        present ⇒ the signature is treated as variadic and never flagged
        (bias OK).
    param_required_node_types:
        Parameter node types that count as a required positional-or-keyword
        parameter (Python: ``identifier``, ``typed_parameter``).
    arg_keyword_node_types:
        Call-argument node types that are keyword/named arguments (Python:
        ``keyword_argument``) — they satisfy a required param by name.
    arg_splat_node_types:
        Call-argument node types that splat an unknown number of arguments
        (Python: ``list_splat``, ``dictionary_splat``).  Any present ⇒ the
        call's arity is unknowable and the call is never flagged (bias OK).
    """

    language: str
    ts_language_name: str
    file_globs: tuple[str, ...]
    public_symbols_query: str
    references_query: str
    registration_queries: tuple[str, ...]
    mock_call_query: str
    test_path_markers: tuple[str, ...]
    acceptance_path_markers: tuple[str, ...]
    external_mock_allowlist: tuple[str, ...]
    external_mock_path_roots: tuple[str, ...]
    script_manifest_files: tuple[str, ...]
    private_name_prefixes: tuple[str, ...] = ()
    public_visibilities: tuple[str, ...] = ()
    smoke_snippet: str = ""
    smoke_expected_symbol: str = ""
    # CTOR_ARITY probe (composition-root constructor-arity). All defaulted
    # so existing dialect records (js/ts/c#) stay valid and the probe is a
    # no-op for any dialect that does not populate them (absent-signal).
    composition_root_markers: tuple[str, ...] = ()
    constructor_signature_query: str = ""
    constructor_call_query: str = ""
    param_self_names: tuple[str, ...] = ()
    param_default_node_types: tuple[str, ...] = ()
    param_splat_node_types: tuple[str, ...] = ()
    param_required_node_types: tuple[str, ...] = ()
    arg_keyword_node_types: tuple[str, ...] = ()
    arg_splat_node_types: tuple[str, ...] = ()

    def smoke_test(self) -> bool:
        """Compile all queries against the live grammar and match the snippet.

        Per AC-019 this both compiles every query (a malformed S-expr fails
        here, in Wave 0, instead of masquerading as ``unsupported_stack``
        later) AND runs ``public_symbols_query`` against
        ``smoke_snippet``, requiring ``smoke_expected_symbol`` among the
        ``@name`` captures (catching tree-sitter API drift).

        Returns ``True`` on success, ``False`` otherwise (failures are
        logged, never raised).
        """
        try:
            from tree_sitter import Parser, Query, QueryCursor
            from tree_sitter_language_pack import get_language
        except ImportError as exc:
            logger.warning("smoke_test: tree-sitter stack not available: %s", exc)
            return False

        try:
            lang = get_language(self.ts_language_name)
        except Exception as exc:
            logger.warning(
                "smoke_test: could not load language '%s': %s",
                self.ts_language_name, exc,
            )
            return False

        queries = [
            ("public_symbols_query", self.public_symbols_query),
            ("references_query", self.references_query),
            ("mock_call_query", self.mock_call_query),
        ] + [
            (f"registration_queries[{i}]", q)
            for i, q in enumerate(self.registration_queries)
        ] + [
            # CTOR_ARITY queries are optional per dialect; compile them only
            # when populated so a malformed S-expr fails here (Wave 0) rather
            # than masquerading as a silent skip later.
            (qname, qtext)
            for qname, qtext in (
                ("constructor_signature_query", self.constructor_signature_query),
                ("constructor_call_query", self.constructor_call_query),
            )
            if qtext
        ]

        compiled: dict[str, Query] = {}
        for qname, qtext in queries:
            try:
                compiled[qname] = Query(lang, qtext)
            except Exception as exc:
                logger.warning(
                    "smoke_test: %s failed to compile for '%s': %s",
                    qname, self.language, exc,
                )
                return False

        # Canonical-snippet match (AC-019).
        if self.smoke_snippet and self.smoke_expected_symbol:
            try:
                parser = Parser(lang)
                tree = parser.parse(self.smoke_snippet.encode("utf-8"))
                cursor = QueryCursor(compiled["public_symbols_query"])
                captures = cursor.captures(tree.root_node)
                names = {
                    self.smoke_snippet.encode("utf-8")[n.start_byte:n.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    for n in captures.get("name", [])
                }
                if self.smoke_expected_symbol not in names:
                    logger.warning(
                        "smoke_test: public_symbols_query did not capture '%s' "
                        "from canonical snippet for '%s' (got %s)",
                        self.smoke_expected_symbol, self.language, sorted(names),
                    )
                    return False
            except Exception as exc:
                logger.warning(
                    "smoke_test: canonical-snippet match failed for '%s': %s",
                    self.language, exc,
                )
                return False

        return True


# Language aliases → canonical registry keys.  Extensions of source
# languages WITHOUT a dialect map to their canonical name so the analyzer
# can report unsupported_stack (absent-signal) instead of None.
_ALIASES: dict[str, str] = {
    "c_sharp": "c_sharp",
    "csharp": "c_sharp",
    "cs": "c_sharp",
    "dotnet": "c_sharp",
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "typescript",
}


def _find_language(language: str) -> str | None:
    """Resolve a language name to its canonical registry key.

    Handles aliases like ``"csharp"``/``"dotnet"`` → ``"c_sharp"``.
    Returns ``None`` for unknown names (the caller treats the original
    name as an unsupported stack).
    """
    return _ALIASES.get(language.lower())
