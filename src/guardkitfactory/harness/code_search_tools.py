"""Read-only code search tools for the coding Player and the Coach's evidence pass.

Three tools, each bound when the graph is built to one worktree root, so two
builds' worktrees never see each other's files. They run the pinned programs
through :mod:`guardkitfactory.code_search`; a ``path`` that leads outside the
root is refused. They only read, so the Player's skill-read gate treats them
like ``grep`` and ``glob``. When the pinned programs are not installed no tool
is offered and the reason is returned for the launch evidence; the built-in
``read_file``, ``grep`` and ``glob`` stay as the text fallback either way.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from guardkitfactory import code_search

TOOL_NAMES = ("code_search", "code_outline", "code_pattern")

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


def _render(answer: dict[str, Any]) -> str:
    return json.dumps(answer, ensure_ascii=False)


def code_search_tools(
    root: Path, *, max_chars: int = code_search.DEFAULT_MAX_CHARS
) -> tuple[list[BaseTool], str]:
    """The three tools bound to ``root``, or ``([], reason)`` when the pinned
    programs are not installed exactly."""

    ok, reason = code_search.available()
    if not ok:
        return [], reason
    bound = Path(root).resolve(strict=True)

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
            handle_validation_error=True,
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
            handle_validation_error=True,
        ),
        StructuredTool.from_function(
            func=pattern,
            coroutine=apattern,
            name="code_pattern",
            description=(
                "Find code by its syntax shape (ast-grep), for example every call of a "
                "function or every access of an attribute. Matches are syntax, not proof "
                "of behaviour or of every caller. " + _STATUS_HELP
            ),
            args_schema=_PatternArgs,
            handle_validation_error=True,
        ),
    ]
    return tools, ""
