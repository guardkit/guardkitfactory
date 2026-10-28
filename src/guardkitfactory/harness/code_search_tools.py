"""Read-only code search tools for the coding Player and the Coach's evidence pass.

Four tools, each bound when the graph is built to one worktree root, so two
builds' worktrees never see each other's files. They run the pinned programs
through :mod:`guardkitfactory.code_search`; a ``path`` that leads outside the
root is refused. They only read, like ``grep`` and ``glob``. When the
pinned programs are not installed no tool
is offered and the reason is returned for the launch evidence; the built-in
``read_file``, ``grep`` and ``glob`` stay as the text fallback either way.

``code_references`` (28 October 2026) asks the language server the project
declares. Its servers are kept for the binding and stopped by
:func:`close_code_search_tools`, which the binding's owner calls when the turn
ends (if it never does, they stop when the binding is collected or at exit).

Which servers run, and with what settings, is pinned when the tools are bound:
read with ``git show`` from the worktree's base commit, the commit the build
started from, found by GuardKit's own ``resolve_feature_base`` (the record
GuardKit makes when it creates the worktree, else ``git merge-base HEAD main``).
So an edit to ``.guardkit/config.yaml`` in the worktree, committed or not,
cannot change the program the tools start. GuardKit's per-task toolchain pin
cannot carry the declaration: the harness is not given the task, and that pin's
schema refuses unknown keys. Without a base commit (not a git worktree) the
file is read once, when the tools are bound.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, PrivateAttr

from guardkitfactory import code_search

TOOL_NAMES = ("code_search", "code_outline", "code_pattern", "code_references")

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


def _base_commit(root: Path) -> str | None:
    """The commit the worktree was made from, by GuardKit's own rule
    (``guardkit.orchestrator.seam_checks.resolve_feature_base``); ``None``
    when there is none to find."""
    try:
        from guardkit.orchestrator.seam_checks import resolve_feature_base

        found = resolve_feature_base(root)
    except Exception:  # noqa: BLE001 - no base commit: the file is read once instead
        return None
    return found if isinstance(found, str) and found else None


def _render(answer: dict[str, Any]) -> str:
    return json.dumps(answer, ensure_ascii=False)


def _bad_arguments(error: Exception) -> str:
    """Tell the model which argument was wrong, in the tools' own answer shape
    (LangChain's default is a fixed sentence that names nothing)."""
    return _render({"status": "input_error", "note": f"invalid arguments: {error}",
                    "results": []})


def code_search_tools(
    root: Path, *, max_chars: int = code_search.DEFAULT_MAX_CHARS,
    install_state: str | None = None,
) -> tuple[list[BaseTool], str]:
    """The four tools bound to ``root``, or ``([], reason)`` when the pinned
    programs are not installed exactly. ``install_state`` says whether the
    project's install step ran on ``root`` (``installed``, ``not_installed``
    or ``unknown``, the default); ``code_references`` reports it."""

    ok, reason = code_search.available()
    if not ok:
        return [], reason
    bound = Path(root).resolve(strict=True)
    servers = code_search.ReferenceServers(
        pinned=code_search.pin_declaration(bound, _base_commit(bound)))

    def search(query: str, mode: str = "ranked", path: str = ".",
               max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("search", bound, query=query, mode=mode, path=path,
                                       max_results=max_results, max_chars=max_chars))

    async def asearch(query: str, mode: str = "ranked", path: str = ".",
                      max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "search", bound, query=query, mode=mode, path=path, max_results=max_results,
            max_chars=max_chars))

    def outline(path: str = ".", items: str = "all",
                max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("outline", bound, path=path, items=items,
                                       max_results=max_results, max_chars=max_chars))

    async def aoutline(path: str = ".", items: str = "all",
                       max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "outline", bound, path=path, items=items, max_results=max_results,
            max_chars=max_chars))

    def pattern(pattern: str, language: str, path: str = ".",
                max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run("pattern", bound, pattern=pattern, language=language,
                                       path=path, max_results=max_results,
                                       max_chars=max_chars))

    async def apattern(pattern: str, language: str, path: str = ".",
                       max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "pattern", bound, pattern=pattern, language=language, path=path,
            max_results=max_results, max_chars=max_chars))

    def references(name: str, path: str, line: int | None = None,
                   max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(code_search.run(
            "references", bound, name=name, path=path, line=line, max_results=max_results,
            max_chars=max_chars, timeout_s=code_search.REFERENCES_TIMEOUT_S,
            install_state=install_state, servers=servers))

    async def areferences(name: str, path: str, line: int | None = None,
                          max_results: int = code_search.DEFAULT_MAX_RESULTS) -> str:
        return _render(await code_search.run_async(
            "references", bound, name=name, path=path, line=line, max_results=max_results,
            max_chars=max_chars, timeout_s=code_search.REFERENCES_TIMEOUT_S,
            install_state=install_state, servers=servers))

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
            "of no uses. coverage.install_state says whether the project's dependencies were "
            "installed. " + _STATUS_HELP
        ),
        args_schema=_ReferencesArgs,
        handle_validation_error=_bad_arguments,
    )
    references_tool._servers = servers

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
        references_tool,
    ]
    return tools, ""
