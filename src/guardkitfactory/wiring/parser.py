"""Parser cache: tree-sitter language loading + standalone Parser.

Uses ``tree_sitter_language_pack.get_language(name)`` + a standalone
``tree_sitter.Parser`` — **NOT** the pack's ``get_parser()``.

The pack's ``get_parser()`` returns vendored bindings where
``Tree.root_node`` is a *method* and ``Node`` has no ``.type``,
incompatible with the standalone Query/Node API this design assumes
(AC-019; scope doc §3.1).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language, Parser, Tree

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

_lang_cache: dict[str, Language] = {}
_parser_cache: dict[str, Parser] = {}


def _load_language(name: str) -> Language:
    """Load (and cache) a tree-sitter grammar from the language pack.

    Parameters
    ----------
    name:
        Canonical language key for the language pack
        (``"python"``, ``"javascript"``, ``"typescript"``, ``"csharp"``).

    Raises
    ------
    ImportError
        If ``tree_sitter_language_pack`` is not installed.
    LookupError
        If the language name is not found in the pack.
    """
    if name in _lang_cache:
        return _lang_cache[name]

    try:
        from tree_sitter_language_pack import get_language
    except ImportError as exc:
        raise ImportError(
            "tree_sitter_language_pack is required for wiring analysis. "
            "Install it with: pip install tree-sitter-language-pack"
        ) from exc

    try:
        lang = get_language(name)
    except Exception as exc:
        raise LookupError(
            f"Language '{name}' not found in tree-sitter-language-pack. "
            f"Available languages depend on the installed pack version."
        ) from exc

    _lang_cache[name] = lang
    return lang


def get_parser(language_name: str) -> Parser:
    """Get (or create) a standalone tree-sitter Parser for *language_name*."""
    if language_name not in _parser_cache:
        from tree_sitter import Parser

        _parser_cache[language_name] = Parser(_load_language(language_name))
    return _parser_cache[language_name]


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def parse_bytes(source: bytes, language_name: str) -> Tree | None:
    """Parse *source* bytes into a tree-sitter ``Tree``.

    Returns ``None`` when the parser itself fails.  Note tree-sitter is
    LENIENT: syntactically broken source usually still yields a tree whose
    ``root_node.has_error`` is True — callers deciding parse-degradation
    must check ``has_error``, not just ``None``.
    """
    try:
        return get_parser(language_name).parse(source)
    except Exception as exc:
        logger.warning("Parse failed for language '%s': %s", language_name, exc)
        return None


def parse_file(path: str, language_name: str) -> Tree | None:
    """Parse a source file into a tree-sitter ``Tree``.

    Returns ``None`` if the file cannot be read or parsed.
    """
    try:
        with open(path, "rb") as f:
            source = f.read()
    except OSError as exc:
        logger.warning("Cannot read file '%s': %s", path, exc)
        return None
    return parse_bytes(source, language_name)
