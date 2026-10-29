"""Read-only code search tools for the coding Player and the Coach's evidence pass.

Three tools (four when a language server declaration is available), each
bound when the graph is built to one root, so two builds' worktrees never see
each other's files. They run the pinned programs
through :mod:`guardkitfactory.code_search`; a ``path`` that leads outside the
root is refused. They only read, like ``grep`` and ``glob``. When the
pinned programs are not installed no tool
is offered and the reason is returned for the launch evidence; the built-in
``read_file``, ``grep`` and ``glob`` stay as the text fallback either way.

``code_references`` (28 October 2026) asks the language server the project
declares. Over a commit snapshot (``snapshot=``: the planner's plain copy of
the start commit) the declaration is the project's own committed one. Over a
worktree (the builder's) it is offered only when the
caller passes the declaration's entries (``language_servers=``: GuardKit pins
them in memory before the builder's first turn), and those entries are used,
never a file in the worktree, which the builder can write (29 October 2026;
ai-transition docs/designs/builder-tools-and-instructions-2026-10-29.md). Its
servers are kept for the binding and stopped by
:func:`close_code_search_tools`, which the binding's owner calls when it ends
(if it never does, they stop when the binding is collected or at exit).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, PrivateAttr

from guardkitfactory import code_search

TOOL_NAMES = ("code_search", "code_outline", "code_pattern", "code_references")
#: Offered only with a declaration: over a commit snapshot, or over a
#: worktree when the caller passes ``language_servers``.
DECLARATION_TOOL_NAMES = ("code_references",)

_STATUS_HELP = (
    "The answer is JSON. 'status' is ok, no_matches (the whole scope was searched), partial "
    "(not everything was covered: read 'truncation'), input_error, unsupported, "
    "tool_unavailable, tool_error or cancelled. Paths are relative to the worktree; "
    "line numbers start at 1. Test files are always included."
)


class _SearchArgs(BaseModel):
    query: str = Field(description="What to look for: words for ranked, text for literal, "
                       "a ripgrep regular expression for regex.")
    mode: Literal["ranked", "literal", "regex"] = Field(
        default="ranked",
        description="ranked: code blocks ranked by the query's words (good for finding "
        "existing behaviour). literal: exact text lines. regex: regular-expression lines.",
    )
    path: str = Field(default=".", description="File or folder inside the worktree.")
    max_results: int = Field(default=code_search.DEFAULT_MAX_RESULTS, ge=1,
                             le=code_search.MAX_RESULTS_LIMIT)


class _OutlineArgs(BaseModel):
    path: str = Field(default=".", description="File or folder inside the worktree.")
    items: Literal["all", "exports"] = Field(
        default="all",
        description="all: every top-level symbol, including internal ones. exports: only "
        "what the file exports.",
    )
    max_results: int = Field(default=code_search.DEFAULT_MAX_RESULTS, ge=1,
                             le=code_search.MAX_RESULTS_LIMIT)


class _PatternArgs(BaseModel):
    pattern: str = Field(description="An ast-grep code pattern, for example 'def $NAME($$$)' "
                         "or '$OBJ.active'. $X matches one node, $$$ any number.")
    language: str = Field(description="The pattern's language, for example python, "
                          "typescript, go, rust, java.")
    path: str = Field(default=".", description="File or folder inside the worktree.")
    max_results: int = Field(default=code_search.DEFAULT_MAX_RESULTS, ge=1,
                             le=code_search.MAX_RESULTS_LIMIT)


class _ReferencesArgs(BaseModel):
    name: str = Field(description="The symbol's name as written in the code, for example "
                      "'run_health', 'HealthResult' or 'Message' (a field). One name, no "
                      "package or class prefix.")
    path: str = Field(description="A file inside the worktree that defines or uses the name.")
    line: int | None = Field(default=None, ge=1, description="The line in that file where "
                             "the name is, if known; otherwise its first occurrence is used.")
    max_results: int = Field(default=code_search.DEFAULT_MAX_RESULTS, ge=1,
                             le=code_search.MAX_RESULTS_LIMIT)


class _ReferencesTool(StructuredTool):
    """``code_references``, holding the language servers of its binding."""

    _servers: code_search.ReferenceServers | None = PrivateAttr(default=None)


def close_code_search_tools(tools: Iterable[Any]) -> None:
    """Stop the language servers the tools' binding started. Safe to call
    more than once, and with any tools or none."""
    for tool in tools:
        servers = tool._servers if isinstance(tool, _ReferencesTool) else None
        if servers is not None:
            servers.close()


def _render(answer: dict[str, Any]) -> str:
    return json.dumps(answer, ensure_ascii=False)


def _bad_arguments(error: Exception) -> str:
    """Tell the model which argument was wrong, in the tools' own answer shape
    (LangChain's default is a fixed sentence that names nothing)."""
    return _render({"status": "input_error", "note": f"invalid arguments: {error}",
                    "results": []})


def code_search_tools(
    root: Path, *, max_chars: int = code_search.DEFAULT_MAX_CHARS,
    snapshot: Mapping[str, Any] | None = None,
    language_servers: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[BaseTool], str]:
    """The tools bound to ``root``, or ``([], reason)`` when the pinned
    programs are not installed exactly.

    A worktree (the default) gets ``code_search``, ``code_outline`` and
    ``code_pattern``, and ``code_references`` when ``language_servers`` (the
    task's pinned ``toolchain.language_servers`` entries) is a non-empty list;
    the tool then uses a copy of those entries and never reads the worktree's
    own declaration. ``snapshot`` says ``root`` is a plain copy of a commit
    and describes it (``{"kind": "commit", ...}``, as the Forge helper's
    ``source``); every answer then carries it, ignore files are not applied
    (the copy holds exactly the tracked files), and ``code_references`` is
    offered too, reading the copy's own declaration and reporting
    ``install_state: not_installed``."""

    ok, reason = code_search.available()
    if not ok:
        return [], reason
    bound = Path(root).resolve(strict=True)
    common: dict[str, Any] = {"max_chars": max_chars}
    if snapshot is not None:
        common.update({"source": dict(snapshot), "respect_ignore": False})

    def search(query: str, mode: str = "ranked", path: str = ".",
               max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("search", bound, query=query, mode=mode, path=path,
                                       max_results=max_results, **common))

    async def asearch(query: str, mode: str = "ranked", path: str = ".",
                      max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "search", bound, query=query, mode=mode, path=path, max_results=max_results,
            **common))

    def outline(path: str = ".", items: str = "all",
                max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("outline", bound, path=path, items=items,
                                       max_results=max_results, **common))

    async def aoutline(path: str = ".", items: str = "all",
                       max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "outline", bound, path=path, items=items, max_results=max_results,
            **common))

    def pattern(pattern: str, language: str, path: str = ".",
                max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("pattern", bound, pattern=pattern, language=language,
                                       path=path, max_results=max_results, **common))

    async def apattern(pattern: str, language: str, path: str = ".",
                       max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "pattern", bound, pattern=pattern, language=language, path=path,
            max_results=max_results, **common))

    outline_languages = ", ".join(sorted(set(code_search.OUTLINE_EXTENSIONS.values())))
    tools: list[BaseTool] = [
        StructuredTool.from_function(
            func=search,
            coroutine=asearch,
            name="code_search",
            description=(
                "Search this worktree's current files, including uncommitted ones, without "
                "changing anything. Use it to find what already exists before writing new "
                "code. " + _STATUS_HELP
            ),
            args_schema=_SearchArgs,
            handle_validation_error=_bad_arguments,
        ),
        StructuredTool.from_function(
            func=outline,
            coroutine=aoutline,
            name="code_outline",
            description=(
                "List the classes, functions, methods and imports in a file or folder, with "
                f"line ranges. Available for {outline_languages}; other files answer "
                "'unsupported'. " + _STATUS_HELP
            ),
            args_schema=_OutlineArgs,
            handle_validation_error=_bad_arguments,
        ),
        StructuredTool.from_function(
            func=pattern,
            coroutine=apattern,
            name="code_pattern",
            description=(
                "Find code by its syntax shape (ast-grep), for example every call of a "
                "function or every access of an attribute. Matches are syntax, not proof "
                "of behaviour or of every caller. No matches is not evidence of no uses: "
                "a short pattern can be read as a different kind of code (in Go, '$X.Name' "
                "alone is a type, and 'f($$$A)' a conversion), so read the note and confirm "
                "with code_search in literal mode. " + _STATUS_HELP
            ),
            args_schema=_PatternArgs,
            handle_validation_error=_bad_arguments,
        ),
    ]
    if language_servers:
        pinned = copy.deepcopy([dict(entry) for entry in language_servers])
        tools.append(_references_tool(bound, {**common, "language_servers": pinned},
                                      snapshot is not None))
    elif snapshot is not None:
        tools.append(_references_tool(bound, common, True))
    return tools, ""


def _references_tool(bound: Path, common: dict[str, Any], plain_copy: bool) -> BaseTool:
    """``code_references`` with its own servers: over a commit snapshot
    (``plain_copy``) or over a worktree with the passed declaration."""
    servers = code_search.ReferenceServers()
    where = (
        "This is a plain copy of the start commit: the project's dependencies are not "
        "installed (coverage.install_state), so confirm uses that pass through them with "
        "code_search. "
        if plain_copy else
        "It reads your worktree as it is now, including changes not yet committed. "
    )

    def references(name: str, path: str, line: int | None = None,
                   max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run(
            "references", bound, name=name, path=path, line=line, max_results=max_results,
            timeout_s=code_search.REFERENCES_TIMEOUT_S, servers=servers, **common))

    async def areferences(name: str, path: str, line: int | None = None,
                          max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "references", bound, name=name, path=path, line=line, max_results=max_results,
            timeout_s=code_search.REFERENCES_TIMEOUT_S, servers=servers, **common))

    references_tool = _ReferencesTool.from_function(
        func=references,
        coroutine=areferences,
        name="code_references",
        description=(
            "Find every place that refers to a function, type, method, field or setting, "
            "as the project's language server resolves it (the compiler's own view, tests "
            "included), plus the whole-word text matches it did not resolve. Use it before "
            "changing a signature, renaming or moving code: who uses this, and what stops "
            "compiling. Give the name and a file that defines or uses it (and the line if you "
            "know it). Entries marked text_only were not checked by the server (strings, docs, "
            "tests that read source, other languages): check them by hand. 'unsupported' "
            "means the project declares no language server for that file: use code_search in "
            "literal mode. 'tool_error' means the server did not answer: it is not evidence "
            "of no uses. " + where + _STATUS_HELP
        ),
        args_schema=_ReferencesArgs,
        handle_validation_error=_bad_arguments,
    )
    references_tool._servers = servers
    return references_tool
