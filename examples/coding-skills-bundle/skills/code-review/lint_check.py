#!/usr/bin/env python3
"""Check the syntax of explicitly named Python files inside a root directory.

Adapted from ``examples/deploy-coding-agent/skills/code-review/lint_check.py``
at ``langchain-ai/deepagents@1d3232c0852c47af09119edea10eeec887e4f0da``.
"""

from __future__ import annotations

import argparse
import ast
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    """One resolved, in-root Python file ready for checking."""

    path: Path
    display: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "check syntax for one or more Python files contained by an "
            "explicit root"
        )
    )
    parser.add_argument(
        "--root",
        required=True,
        help="existing directory that must contain every resolved file",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python file paths, absolute or relative to --root",
    )
    return parser


def _resolve_root(raw_root: str) -> tuple[Path | None, str | None]:
    try:
        root = Path(raw_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"ERROR root {raw_root}: cannot resolve ({exc})"
    if not root.is_dir():
        return None, f"ERROR root {raw_root}: not a directory"
    return root, None


def _resolve_candidate(
    root: Path,
    raw_path: str,
) -> tuple[Candidate | None, str | None]:
    supplied = Path(raw_path)
    unresolved = supplied if supplied.is_absolute() else root / supplied

    try:
        resolved = unresolved.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"ERROR {raw_path}: cannot resolve ({exc})"

    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None, f"ERROR {raw_path}: resolved path escapes root"

    if resolved.suffix != ".py":
        return None, f"ERROR {raw_path}: not a .py file"
    if not resolved.is_file():
        return None, f"ERROR {raw_path}: not a regular file"

    return Candidate(resolved, relative.as_posix()), None


def _check(candidate: Candidate) -> str | None:
    try:
        with tokenize.open(candidate.path) as source_file:
            source = source_file.read()
    except (OSError, UnicodeError, SyntaxError) as exc:
        return f"ERROR {candidate.display}: cannot read Python source ({exc})"

    try:
        ast.parse(source, filename=candidate.display)
    except (SyntaxError, ValueError) as exc:
        if isinstance(exc, SyntaxError):
            location = f":{exc.lineno}" if exc.lineno is not None else ""
            return f"ERROR {candidate.display}{location}: syntax error: {exc.msg}"
        return f"ERROR {candidate.display}: syntax error: {exc}"
    return None


def main(argv: list[str] | None = None) -> int:
    """Validate every requested input and report each successfully checked file."""
    args = _parser().parse_args(argv)
    root, root_error = _resolve_root(args.root)
    if root_error is not None:
        print(root_error, file=sys.stderr)
        return 2
    assert root is not None

    candidates: list[Candidate] = []
    errors: list[str] = []
    for raw_path in args.files:
        candidate, error = _resolve_candidate(root, raw_path)
        if error is not None:
            errors.append(error)
        else:
            assert candidate is not None
            candidates.append(candidate)

    checked = 0
    ordered_candidates = sorted(
        candidates,
        key=lambda item: (item.display, str(item.path)),
    )
    for candidate in ordered_candidates:
        error = _check(candidate)
        if error is not None:
            errors.append(error)
        else:
            print(f"CHECKED {candidate.display}")
            checked += 1

    for error in errors:
        print(error, file=sys.stderr)
    if checked == 0:
        print("ERROR no Python files passed syntax checking", file=sys.stderr)

    return 1 if errors or checked == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
