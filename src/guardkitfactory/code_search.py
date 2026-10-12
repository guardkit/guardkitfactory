"""Read-only code search over one root, through three pinned programs.

ripgrep (exact and regex text), Probe (ranked code blocks) and ast-grep
(symbol outlines and structural patterns) are run directly, by absolute path,
with typed arguments only: a caller never supplies a shell string or a program
flag. Every answer has the same shape, and an empty answer is ``no_matches``
only when the path was checked first, the program finished normally, its
output parsed and it reported no error. The programs were seen (12 October
2026) to answer a missing path, an invalid pattern and a malformed Probe query
with exit 0 and an empty list, so neither exit 0 nor valid JSON is trusted on
its own.

The Forge sandbox helper runs this over an immutable snapshot of a commit; the
coding Player and Coach run it over their own worktree. Nothing here keeps an
index, starts a daemon, downloads anything or writes inside the searched root.

The module itself uses only the standard library; the Forge helper imports it
from the same image, which installs GuardKitFactory. ``python -m
guardkitfactory.code_search self-check`` verifies the installed programs inside
an image.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where the image installs the programs. Deliberately not on any ``PATH``:
#: the agents' shell has ``PATH=/usr/bin:/bin``, where ``sg`` is ``newgrp``,
#: and Deep Agents' built-in ``grep`` would start using an ``rg`` it found.
DEFAULT_TOOL_DIR = "/opt/code-search/bin"
TOOL_DIR_ENV = "GUARDKITFACTORY_CODE_SEARCH_DIR"


@dataclass(frozen=True)
class PinnedTool:
    name: str
    executable: str
    version: str
    sha256: str
    version_line: str


#: The exact executables this contract was written against (official Linux
#: ARM64 releases; archive hashes are pinned in the Forge Dockerfile).
PINNED_TOOLS: dict[str, PinnedTool] = {
    "ripgrep": PinnedTool(
        "ripgrep",
        "rg",
        "15.2.0",
        "c14cdb389f34e504d69e386cfc67d5c5d9a730a990de03ca6910b2a15e30386a",
        "ripgrep 15.2.0 (rev e89fff89ac)",
    ),
    "ast-grep": PinnedTool(
        "ast-grep",
        "ast-grep",
        "0.50.0",
        "e453bdbe419cb21e2c2ae1e9586e09111fcbe70f98213276f5ad728849503d6b",
        "ast-grep 0.50.0",
    ),
    "probe": PinnedTool(
        "probe",
        "probe",
        "0.6.0-rc341",
        "25890db00250a181dea656537641e1f2f51fd4bc472f5344d0c28793a493a420",
        "probe-code 0.6.0",
    ),
}

DEFAULT_TIMEOUT_S = 20.0
DEFAULT_MAX_RESULTS = 20
MAX_RESULTS_LIMIT = 50
DEFAULT_MAX_CHARS = 12_000
#: No answer is cut below this: room for its status, source and reasons.
MIN_ANSWER_CHARS = 2_000
#: How much of a caller's argument an answer repeats back.
ECHO_CHARS = 200
#: Raw program output read before the program is stopped.
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_LINE_CHARS = 300
MAX_BLOCK_LINES = 60
MAX_QUERY_CHARS = 1000
MAX_DIAGNOSTICS = 8
THREADS = "2"

#: ast-grep's outline extracted symbols for these languages on 12 October
#: 2026 (0.50.0). It parses others (Dart, Scala, Bash, YAML ...) but returns no
#: symbols for them, which would read as "nothing defined here".
OUTLINE_EXTENSIONS: dict[str, str] = {
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".kt": "kotlin", ".kts": "kotlin",
    ".php": "php",
    ".py": "python", ".pyi": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".swift": "swift",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".tsx": "tsx",
}

#: Languages ast-grep 0.50.0 accepts for structural patterns.
PATTERN_LANGUAGES = frozenset(
    {
        "bash", "c", "cpp", "csharp", "css", "dart", "elixir", "go", "haskell", "hcl",
        "html", "java", "javascript", "json", "kotlin", "lua", "nix", "php", "python",
        "ruby", "rust", "scala", "solidity", "swift", "tsx", "typescript", "yaml",
    }
)

#: Languages whose code Probe splits into blocks (from ``probe search --help``);
#: other text files are searched and returned as plain lines.
RANKED_BLOCK_LANGUAGES = frozenset(
    {
        "bash", "c", "cpp", "crystal", "csharp", "go", "haskell", "java", "javascript",
        "php", "python", "qml", "ruby", "rust", "solidity", "swift", "tsx", "typescript",
        "yaml",
    }
)

OPERATIONS = ("search", "outline", "pattern")
SEARCH_MODES = ("ranked", "literal", "regex")


def capabilities() -> dict[str, Any]:
    """Which operation works for which language, said plainly."""

    return {
        "search": {
            "literal": "every text file (ripgrep)",
            "regex": "every text file (ripgrep, Rust regex syntax)",
            "ranked": (
                "every text file (Probe, BM25 over the query's words); code blocks for "
                + ", ".join(sorted(RANKED_BLOCK_LANGUAGES))
                + "; plain lines otherwise"
            ),
        },
        "outline": sorted(set(OUTLINE_EXTENSIONS.values())),
        "pattern": sorted(PATTERN_LANGUAGES),
        "not_diagnosed": (
            "syntax errors: tree-sitter parses what it can, so results from a malformed "
            "file may be incomplete without any error being reported"
        ),
        "tests": "always included",
        "hidden": "files and folders whose names start with '.' are skipped unless named",
    }


# --------------------------------------------------------------------------
# The installed programs


def tool_dir() -> Path:
    return Path(os.environ.get(TOOL_DIR_ENV) or DEFAULT_TOOL_DIR)


_verified: dict[tuple[Any, ...], dict[str, Any]] = {}
_verified_lock = threading.Lock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def toolkit() -> dict[str, Any]:
    """Each pinned program's path and whether it is exactly the pinned one.

    Hashes and ``--version`` are checked once per file identity per process.
    """

    folder = tool_dir()
    identity: list[Any] = [str(folder)]
    for tool in PINNED_TOOLS.values():
        path = folder / tool.executable
        try:
            st = path.stat()
            identity.append((tool.executable, st.st_size, st.st_mtime_ns, st.st_ino))
        except OSError:
            identity.append((tool.executable, None))
    key = tuple(identity)
    with _verified_lock:
        cached = _verified.get(key)
    if cached is not None:
        return cached
    tools: dict[str, Any] = {}
    problems: list[str] = []
    for name, tool in PINNED_TOOLS.items():
        path = folder / tool.executable
        entry: dict[str, Any] = {"path": str(path), "version": tool.version}
        problem = None
        if not path.is_file():
            problem = f"{tool.executable} is not installed at {path}"
        elif not os.access(path, os.X_OK):
            problem = f"{path} is not executable"
        else:
            actual = _sha256(path)
            if actual != tool.sha256:
                problem = f"{path} is not the pinned {name} {tool.version} (sha256 {actual})"
            else:
                try:
                    shown = subprocess.run(  # noqa: S603 - fixed argv, no shell
                        [str(path), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        env={**_git_environment(), "NO_COLOR": "1"},
                        stdin=subprocess.DEVNULL,
                        check=False,
                    )
                    first = (shown.stdout or "").strip().splitlines()[:1]
                    if shown.returncode != 0 or not first or first[0] != tool.version_line:
                        problem = (
                            f"{path} --version answered {first[0] if first else 'nothing'!r}, "
                            f"expected {tool.version_line!r}"
                        )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    problem = f"{path} could not run: {type(exc).__name__}: {exc}"
        entry["ok"] = problem is None
        if problem:
            entry["problem"] = problem
            problems.append(problem)
        tools[name] = entry
    result = {"dir": str(folder), "ok": not problems, "tools": tools, "problems": problems}
    with _verified_lock:
        _verified[key] = result
    return result


def available() -> tuple[bool, str]:
    """``(True, "")`` when all three pinned programs verify, else the reason."""

    state = toolkit()
    return state["ok"], "; ".join(state["problems"])


# --------------------------------------------------------------------------
# Running one program


@dataclass
class _Run:
    returncode: int | None
    stdout: bytes
    stderr: str
    output_capped: bool
    timed_out: bool
    cancelled: bool
    elapsed_ms: int


def _base_environment(private: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(private),
        "XDG_CACHE_HOME": str(private / "cache"),
        "XDG_CONFIG_HOME": str(private / "config"),
        "XDG_DATA_HOME": str(private / "data"),
        "TMPDIR": str(private / "tmp"),
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }


def _git_environment() -> dict[str, str]:
    """git with no user, system or shared-folder configuration: nothing a
    planted ``.gitconfig`` says (an fsmonitor command, say) can run."""

    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C.UTF-8",
    }


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        process.kill()


def _execute(
    argv: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_s: float,
    cancel: threading.Event | None,
    max_bytes: int | None = None,
) -> _Run:
    """Run one program in its own process group, bounded in time and output.

    The whole group is stopped on a timeout, a cancellation or too much
    output; the answer says which happened.
    """

    if max_bytes is None:
        max_bytes = MAX_OUTPUT_BYTES
    started = time.monotonic()
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        argv,
        cwd=str(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    out = bytearray()
    err = bytearray()
    capped = threading.Event()

    def pump_stdout() -> None:
        assert process.stdout is not None
        for chunk in iter(lambda: process.stdout.read(65536), b""):
            room = max_bytes - len(out)
            if room <= 0:
                capped.set()
                _kill_group(process)
                break
            out.extend(chunk[:room])
            if len(chunk) > room:
                capped.set()
                _kill_group(process)
                break

    def pump_stderr() -> None:
        assert process.stderr is not None
        for chunk in iter(lambda: process.stderr.read(8192), b""):
            room = MAX_STDERR_BYTES - len(err)
            if room > 0:
                err.extend(chunk[:room])

    readers = [threading.Thread(target=pump_stdout, daemon=True),
               threading.Thread(target=pump_stderr, daemon=True)]
    for reader in readers:
        reader.start()
    timed_out = cancelled = False
    deadline = started + timeout_s
    try:
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                cancelled = True
                _kill_group(process)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _kill_group(process)
                break
            if capped.is_set():
                break
            time.sleep(0.02)
    finally:
        stopped_early = process.poll() is None or timed_out or cancelled or capped.is_set()
        if stopped_early:
            # The whole group, so a child that kept a pipe open stops too.
            _kill_group(process)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
        for stream in (process.stdout, process.stderr):
            with contextlib.suppress(Exception):
                if stream is not None:
                    stream.close()
    return _Run(
        returncode=process.returncode,
        stdout=bytes(out),
        stderr=err.decode("utf-8", errors="replace"),
        output_capped=capped.is_set(),
        timed_out=timed_out,
        cancelled=cancelled,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


# --------------------------------------------------------------------------
# Inputs


class _InputError(ValueError):
    pass


def _resolve_root(root: str | os.PathLike[str]) -> Path:
    try:
        resolved = Path(root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _InputError(f"the search root {root} cannot be read: {exc}") from exc
    if not resolved.is_dir():
        raise _InputError(f"the search root {resolved} is not a folder")
    return resolved


def _resolve_target(root: Path, path: str | None) -> tuple[Path, str]:
    """The checked target inside ``root`` and its root-relative spelling."""

    raw = "." if path is None or str(path).strip() == "" else str(path).strip()
    if "\0" in raw:
        raise _InputError("the path contains a NUL character")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.normpath(candidate))
    if lexical != root and root not in lexical.parents:
        raise _InputError(f"{raw!r} is outside the searched folder")
    if not os.path.lexists(lexical):
        raise _InputError(f"{raw!r} does not exist in the searched folder")
    try:
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _InputError(f"{raw!r} cannot be resolved: {exc}") from exc
    if resolved != root and root not in resolved.parents:
        raise _InputError(f"{raw!r} leads outside the searched folder through a link")
    wanted = os.R_OK | (os.X_OK if resolved.is_dir() else 0)
    if not os.access(resolved, wanted):
        raise _InputError(f"{raw!r} cannot be read")
    if not (resolved.is_dir() or resolved.is_file()):
        raise _InputError(f"{raw!r} is neither a file nor a folder")
    relative = "." if resolved == root else resolved.relative_to(root).as_posix()
    return resolved, relative


def _limit(value: Any, default: int, ceiling: int) -> int:
    try:
        number = int(value) if value is not None else default
    except (TypeError, ValueError):
        number = default
    return max(1, min(ceiling, number))


#: Probe's query operators. Dropped in any case: they rank nothing, and as
#: words they could still be read as syntax.
_PROBE_OPERATORS = frozenset({"and", "or", "not"})


def query_words(text: str) -> list[str]:
    """The query reduced to plain lower-case words, so no Probe syntax
    (``AND``/``OR``/``NOT``, quotes, brackets, ``+``/``-`` prefixes, ``ext:``
    hints) can reach it. An empty list means there is nothing to rank by."""

    seen: list[str] = []
    for word in re.findall(r"[A-Za-z0-9_]+", text or ""):
        lowered = word.lower()
        if lowered in _PROBE_OPERATORS or lowered in seen:
            continue
        seen.append(lowered)
    return seen[:32]



# --------------------------------------------------------------------------
# Identity of what was searched

#: Changed and untracked file contents hashed into a worktree fingerprint.
FINGERPRINT_CONTENT_BYTES = 32 * 1024 * 1024


def _left(deadline: float | None, ceiling: float) -> float:
    """Seconds left before ``deadline``, at most ``ceiling``."""
    if deadline is None:
        return ceiling
    return min(ceiling, deadline - time.monotonic())


def _stop(deadline: float | None, cancel: threading.Event | None) -> bool:
    return (cancel is not None and cancel.is_set()) or (
        deadline is not None and time.monotonic() >= deadline
    )


def worktree_source(
    root: Path,
    timeout_s: float = 10.0,
    *,
    deadline: float | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """What the worktree holds at query time: where it is, its commit and its
    changes.

    The fingerprint is a SHA-256 over ``git status`` and the content of every
    changed or untracked regular file, so two worktrees at the same commit
    with the same changed paths but different edits differ, and so does a
    second edit to an already-changed file. Past
    :data:`FINGERPRINT_CONTENT_BYTES` of content, later files contribute their
    size and modification time and ``fingerprint_complete`` is false. git runs
    through the same bounded, cancellable runner as the search programs; when
    the call's ``deadline`` passes or it is cancelled before the identity is
    complete, ``fingerprint`` is ``None`` and ``note`` says why.
    """

    def unknown(note: str) -> dict[str, Any]:
        return {"kind": "worktree", "root": str(root), "fingerprint": None,
                "fingerprint_complete": False, "note": note}

    env = _git_environment()
    base = ["git", "-c", "safe.directory=*", "-c", "core.fsmonitor=false", "-C", str(root)]
    answers = []
    for args in (("rev-parse", "--verify", "--quiet", "HEAD"),
                 ("status", "--porcelain=v1", "-z", "--untracked-files=all")):
        left = _left(deadline, timeout_s)
        if left <= 0 or _stop(None, cancel):
            return unknown("not described: the call's time ran out or it was cancelled")
        try:
            answer = _execute([*base, *args], cwd=root, env=env, timeout_s=left, cancel=cancel)
        except OSError as exc:
            return {"kind": "folder", "root": str(root), "note": f"git could not run: {exc}"}
        if answer.cancelled or answer.timed_out or answer.output_capped:
            return unknown("not described: git did not finish within the call's time or limits")
        answers.append(answer)
    head, status = answers
    if status.returncode != 0:
        detail = status.stderr.strip().splitlines()[:1]
        return {
            "kind": "folder",
            "root": str(root),
            "note": f"not a git worktree ({detail[0] if detail else 'git status failed'})",
        }
    digest = hashlib.sha256(status.stdout)
    changed = untracked = deleted = 0
    budget = FINGERPRINT_CONTENT_BYTES
    complete = True
    records = status.stdout.split(b"\0")
    index = 0
    while index < len(records):
        if _stop(deadline, cancel):
            return unknown("not described: the call's time ran out or it was cancelled")
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        code, name = record[:2], record[3:].decode("utf-8", errors="replace")
        if code[:1] in (b"R", b"C"):
            index += 1  # the original name follows a rename or copy
        if code == b"??":
            untracked += 1
        elif b"D" in code:
            deleted += 1
            continue
        else:
            changed += 1
        path = root / name
        try:
            st = path.lstat()
        except OSError:
            continue
        digest.update(f"\0{name}\0{st.st_size}".encode())
        if not path.is_file() or path.is_symlink():
            continue
        if st.st_size > budget:
            complete = False
            digest.update(f"\0{st.st_mtime_ns}".encode())
            continue
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
                    if _stop(deadline, cancel):
                        return unknown(
                            "not described: the call's time ran out or it was cancelled"
                        )
            budget -= st.st_size
        except OSError:
            complete = False
            digest.update(f"\0unreadable\0{st.st_mtime_ns}".encode())
    return {
        "kind": "worktree",
        "root": str(root),
        "head": head.stdout.decode("utf-8", errors="replace").strip() or None,
        "changed": changed,
        "untracked": untracked,
        "deleted": deleted,
        "fingerprint": digest.hexdigest(),
        "fingerprint_complete": complete,
    }


# --------------------------------------------------------------------------
# Answers


@dataclass
class _Facts:
    """What one program run established; :func:`_decide` turns it into a status."""

    results: list[dict[str, Any]]
    coverage: dict[str, Any]
    limits: list[str]
    program_errors: list[str]
    diagnostics: list[str]
    input_problem: str | None = None
    unsupported: str | None = None
    fatal: str | None = None
    cancelled: bool = False
    elapsed_ms: int = 0
    #: Results whose text is shown only in part (long lines or blocks).
    shown_in_part: int = 0


def _new_facts(respect_ignore: bool) -> _Facts:
    return _Facts(
        results=[],
        coverage={"hidden": "skipped unless named", "ignore_files": respect_ignore},
        limits=[],
        program_errors=[],
        diagnostics=[],
    )


def _decide(facts: _Facts) -> tuple[str, str]:
    """When several apply, the first wins: input_error, cancelled, tool_error,
    unsupported, partial, then ok or no_matches (tool_unavailable is decided
    before any program runs)."""
    if facts.input_problem:
        return "input_error", facts.input_problem
    if facts.cancelled:
        return "cancelled", "the search was cancelled and its program stopped"
    if facts.fatal:
        return "tool_error", facts.fatal
    if facts.unsupported:
        return "unsupported", facts.unsupported
    if facts.limits or facts.program_errors:
        note = "the search did not cover everything; see truncation"
        if facts.program_errors:
            note = "the program reported errors, so some files may not have been searched"
        return "partial", note
    return ("ok", "") if facts.results else ("no_matches", "")


def _answer(
    *,
    operation: str,
    status: str,
    source: Mapping[str, Any] | None,
    query: Mapping[str, Any],
    tool: str | None = None,
    facts: _Facts | None = None,
    note: str = "",
    elapsed_ms: int = 0,
) -> dict[str, Any]:
    tool_info = None
    if tool is not None:
        pinned = PINNED_TOOLS[tool]
        tool_info = {"name": pinned.name, "version": pinned.version}
    keep = facts is not None and status in ("ok", "partial", "no_matches")
    truncation = list(facts.limits) if facts else []
    if facts and facts.program_errors:
        truncation.append("the program reported errors part-way")
    return {
        "operation": operation,
        "status": status,
        "source": dict(source) if source else None,
        "query": dict(query),
        "tool": tool_info,
        "results": list(facts.results) if keep and facts else [],
        "coverage": dict(facts.coverage) if facts else {},
        "truncated": bool(truncation),
        "truncation": truncation,
        "diagnostics": (facts.diagnostics if facts else [])[:MAX_DIAGNOSTICS],
        "note": note,
        "elapsed_ms": facts.elapsed_ms if facts else elapsed_ms,
    }


def _echo(value: str, limit: int = ECHO_CHARS) -> str:
    """At most ``limit`` characters of a caller's argument, said when cut."""
    return value if len(value) <= limit else value[:limit] + f"…[{len(value)} characters]"


def _cut(text: str) -> str:
    return text if len(text) <= MAX_LINE_CHARS else text[:MAX_LINE_CHARS] + " …[line cut]"


def _cut_block(text: str) -> tuple[str, bool]:
    """The text, at most :data:`MAX_BLOCK_LINES` lines each cut to
    :data:`MAX_LINE_CHARS`; ``True`` when anything was cut."""
    lines = text.split("\n")
    cut = len(lines) > MAX_BLOCK_LINES or any(
        len(line) > MAX_LINE_CHARS for line in lines[:MAX_BLOCK_LINES]
    )
    shown = [_cut(line) for line in lines[:MAX_BLOCK_LINES]]
    if len(lines) > MAX_BLOCK_LINES:
        shown.append(f"…[{len(lines) - MAX_BLOCK_LINES} more lines not shown]")
    return "\n".join(shown), cut


_INFO_LINES = (
    "Using BM25 ranking",
    "Using TF-IDF ranking",
    "Using hybrid ranking",
    "sg: summary|",
    "sg: entity|",
)
#: ast-grep's advice lines that follow a warning; not errors themselves.
_ADVICE_LINES = ("Help:", "See also:")


def _diagnostic_lines(stderr: str) -> list[str]:
    lines = []
    for line in stderr.splitlines():
        text = line.strip()
        if not text or text.startswith(_INFO_LINES):
            continue
        lines.append(_cut(text))
    return lines


def _relative_result_path(root: Path, reported: str) -> str | None:
    candidate = Path(reported)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.normpath(candidate))
    if lexical != root and root not in lexical.parents:
        return None
    return lexical.relative_to(root).as_posix() if lexical != root else "."


def _fit_to_chars(answer: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Drop trailing results until the whole answer, including the sentence
    saying so, fits ``max_chars``."""

    def size() -> int:
        return len(json.dumps(answer, ensure_ascii=False))

    if size() > max_chars and not answer["results"]:
        _shrink_metadata(answer)
        return answer
    if size() <= max_chars:
        return answer
    answer["truncated"] = True
    answer["truncation"].append("")
    if answer["status"] == "ok":
        answer["status"] = "partial"
        answer["note"] = "the search did not cover everything; see truncation"
    dropped = 0
    while answer["results"]:
        answer["results"].pop()
        dropped += 1
        answer["truncation"][-1] = (
            f"{dropped} more result(s) left out to fit {max_chars} characters"
        )
        if size() <= max_chars:
            break
    if size() > max_chars:
        _shrink_metadata(answer)
    return answer


def _shrink_metadata(answer: dict[str, Any]) -> None:
    """Cut an answer's descriptive fields to fixed sizes. If that is still
    not small enough, keep only the identity fields, each cut short, so the
    answer always fits :data:`MIN_ANSWER_CHARS`."""
    _cut_metadata(answer)
    if len(json.dumps(answer, ensure_ascii=False)) > MIN_ANSWER_CHARS:
        _minimal_metadata(answer)


_IDENTITY_FIELDS = ("kind", "root", "commit", "head", "fingerprint", "fingerprint_complete",
                    "files", "omitted_count", "changed", "untracked", "deleted")


def _minimal_metadata(answer: dict[str, Any]) -> None:
    source = answer.get("source") if isinstance(answer.get("source"), dict) else {}
    answer["source"] = {
        key: (_echo(value, 60) if isinstance(value, str) else value)
        for key, value in source.items()
        if key in _IDENTITY_FIELDS
    }
    answer["query"] = {key: (_echo(value, 40) if isinstance(value, str) else None)
                       for key, value in (answer.get("query") or {}).items()
                       if key in ("path", "mode", "text", "pattern", "language", "items")}
    answer["coverage"] = {}
    answer["diagnostics"] = []
    answer["truncation"] = [_echo(t, 100) for t in (answer.get("truncation") or [])[:2]]
    answer["note"] = _echo(answer.get("note") or "", 150) + " (details abbreviated to fit)"
    answer["operation"] = _echo(str(answer.get("operation") or ""), 40)
    answer["results"] = []


def _cut_metadata(answer: dict[str, Any]) -> None:
    answer["note"] = _echo(answer.get("note") or "", 300)
    answer["diagnostics"] = [_echo(d, 200) for d in (answer.get("diagnostics") or [])[:2]]
    answer["truncation"] = [_echo(t, 200) for t in (answer.get("truncation") or [])[:4]]
    answer["query"] = {k: (_echo(v, 100) if isinstance(v, str) else v)
                       for k, v in (answer.get("query") or {}).items()}
    if isinstance(answer.get("query", {}).get("words"), list):
        answer["query"]["words"] = answer["query"]["words"][:8]
    source = answer.get("source")
    if isinstance(source, dict):
        if isinstance(source.get("omitted"), list):
            source["omitted"] = [
                {k: _echo(str(v), 120) for k, v in item.items()} if isinstance(item, dict)
                else _echo(str(item), 120)
                for item in source["omitted"][:3]
            ]
        source.pop("after", None)
        for key, value in list(source.items()):
            if isinstance(value, str):
                source[key] = _echo(value, 200)


def _stopped(run: _Run, facts: _Facts, timeout_s: float) -> bool:
    """Record why a program was stopped; True when its output is cut short."""

    facts.elapsed_ms = run.elapsed_ms
    facts.diagnostics = _diagnostic_lines(run.stderr)
    if run.cancelled:
        facts.cancelled = True
        return True
    if run.timed_out:
        facts.limits.append(f"stopped after {timeout_s:g} seconds")
        return True
    if run.output_capped:
        facts.limits.append(f"program output cut at {MAX_OUTPUT_BYTES} bytes")
        return True
    return False


# --------------------------------------------------------------------------
# Operations


def _private_folder(root: Path) -> Path:
    base = Path(tempfile.gettempdir()).resolve()
    if base == root or root in base.parents:
        base = Path("/tmp")
    private = Path(tempfile.mkdtemp(prefix="code-search-", dir=str(base)))
    for name in ("cache", "config", "data", "tmp"):
        (private / name).mkdir()
    # ast-grep would otherwise read an sgconfig.yml from the searched tree.
    (private / "sgconfig.yml").write_text("ruleDirs: []\n", encoding="utf-8")
    return private


@dataclass
class _Call:
    root: Path
    target_path: Path
    target: str
    max_results: int
    respect_ignore: bool
    exe: str
    env: Mapping[str, str]
    private: Path
    timeout_s: float
    cancel: threading.Event | None
    deadline: float | None = None

    @property
    def operand(self) -> str:
        """The target as the programs get it: relative to the root they run
        in, always starting ``./`` so a name like ``--rewrite`` stays a path."""
        return "." if self.target == "." else f"./{self.target}"

    def execute(self, argv: list[str]) -> _Run:
        """Run the program with whatever is left of the call's time, measured
        now, not when the call began; with none left it does not start."""
        left = self.timeout_s if self.deadline is None else self.deadline - time.monotonic()
        if left <= 0:
            return _Run(None, b"", "", False, True, False, 0)
        return _execute(argv, cwd=self.root, env=self.env, timeout_s=left, cancel=self.cancel)


def _search_rg(call: _Call, query: str, mode: str, facts: _Facts) -> None:
    argv = [call.exe, "--json", "--no-config", "--threads", THREADS, "--max-columns", "2000"]
    if mode == "literal":
        argv.append("--fixed-strings")
    if not call.respect_ignore:
        argv.append("--no-ignore")
    argv += ["--regexp", query, "--", call.operand]
    run = call.execute(argv)
    cut_short = _stopped(run, facts, call.timeout_s)
    stats: dict[str, Any] | None = None
    unparsed = 0
    found: list[dict[str, Any]] = []
    for raw in run.stdout.splitlines():
        try:
            event = json.loads(raw)
        except ValueError:
            unparsed += 1
            continue
        kind = event.get("type")
        data = event.get("data") or {}
        if kind == "match":
            path = _relative_result_path(call.root, str((data.get("path") or {}).get("text")))
            if path is None:
                continue
            text = (data.get("lines") or {}).get("text")
            number = data.get("line_number")
            if text is not None and len(text.rstrip("\n")) > MAX_LINE_CHARS:
                facts.shown_in_part += 1
            found.append(
                {
                    "path": path,
                    "first_line": number,
                    "last_line": number,
                    "text": _cut((text if text is not None else "[not UTF-8]").rstrip("\n")),
                }
            )
        elif kind == "summary":
            stats = data.get("stats") or {}
    # ripgrep's threads finish files in any order: sort, so the same search
    # always keeps the same results.
    found.sort(key=lambda r: (r["path"], r["first_line"] or 0))
    total = len(found)
    facts.results.extend(found[: call.max_results])
    facts.coverage.update(
        {
            "files_searched": (stats or {}).get("searches"),
            "files_with_matches": (stats or {}).get("searches_with_match"),
            "matches_found": total,
            "tests_included": True,
        }
    )
    if total > len(facts.results):
        facts.limits.append(f"showing {len(facts.results)} of {total} matching lines")
    if cut_short:
        return
    if run.returncode == 2 and any("regex parse error" in d for d in facts.diagnostics):
        facts.input_problem = "the regular expression is not valid ripgrep syntax"
    elif run.returncode not in (0, 1, 2) or stats is None:
        facts.fatal = f"ripgrep ended with status {run.returncode} and no summary"
    elif run.returncode == 2 or unparsed or facts.diagnostics:
        # ripgrep carries on past a file it cannot read and exits 2.
        facts.program_errors = facts.diagnostics or ["ripgrep output could not be read"]


def _search_probe(call: _Call, words: list[str], facts: _Facts) -> None:
    argv = [
        call.exe, "search", " ".join(words), call.operand,
        "--format", "json",
        "--allow-tests",
        "--max-results", str(call.max_results),
        "--max-bytes", str(MAX_OUTPUT_BYTES // 4),
        "--timeout", str(max(1, int(call.timeout_s))),
    ]
    if not call.respect_ignore:
        argv.append("--no-gitignore")
    run = call.execute(argv)
    cut_short = _stopped(run, facts, call.timeout_s)
    facts.coverage.update(
        {
            "files_searched": None,
            "files_searched_note": "Probe does not report how many files it read",
            "tests_included": True,
        }
    )
    if cut_short:
        return
    try:
        parsed = json.loads(run.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        facts.fatal = f"Probe's output was not JSON (exit {run.returncode})"
        return
    if run.returncode != 0 or not isinstance(parsed, dict) or not isinstance(
        parsed.get("results"), list
    ):
        facts.fatal = f"Probe ended with status {run.returncode}"
        return
    for item in parsed["results"]:
        if not isinstance(item, dict):
            continue
        path = _relative_result_path(call.root, str(item.get("file") or ""))
        lines = item.get("lines")
        if path is None or not isinstance(lines, list) or len(lines) != 2:
            continue
        text, cut = _cut_block(str(item.get("code") or ""))
        entry: dict[str, Any] = {
            "path": path,
            "first_line": lines[0],
            "last_line": lines[1],
            "text": text,
            "score": round(float(item.get("bm25_score") or item.get("score") or 0.0), 4),
            "kind": item.get("node_type"),
            "language": item.get("language"),
            "matched": item.get("matched_keywords") or [],
        }
        if cut:
            entry["text_cut"] = True
            facts.shown_in_part += 1
        facts.results.append(entry)
    if facts.diagnostics:
        # Probe reports an unreadable path only on stderr, with exit 0.
        facts.program_errors = list(facts.diagnostics)
    if len(facts.results) >= call.max_results:
        facts.limits.append(f"result limit {call.max_results} reached; more may exist")
    limits = parsed.get("limits") or {}
    max_bytes = limits.get("max_bytes")
    if isinstance(max_bytes, int) and (limits.get("total_bytes") or 0) >= max_bytes:
        facts.limits.append(f"Probe's byte limit {max_bytes} reached")


def _sg_counts(stderr: str) -> dict[str, int]:
    found = re.search(r"scannedFileCount=(\d+),skippedFileCount=(\d+)", stderr)
    if not found:
        return {}
    return {"files_scanned": int(found.group(1)), "files_skipped": int(found.group(2))}


def _sg_ignore_flags(respect_ignore: bool) -> list[str]:
    if respect_ignore:
        return []
    return ["--no-ignore", "vcs", "--no-ignore", "dot", "--no-ignore", "exclude",
            "--no-ignore", "global", "--no-ignore", "parent"]


def _sg_errors(diagnostics: list[str]) -> list[str]:
    return [line for line in diagnostics if not line.startswith(_ADVICE_LINES)]


def _has_outline_files(
    folder: Path, deadline: float | None = None, cancel: threading.Event | None = None
) -> bool | None:
    """Whether any file under ``folder`` has outline support; ``None`` when
    the walk was stopped by the call's time limit or a cancellation."""
    for _current, dirs, names in os.walk(folder):
        if _stop(deadline, cancel):
            return None
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if any(
            Path(n).suffix.lower() in OUTLINE_EXTENSIONS for n in names if not n.startswith(".")
        ):
            return True
    return False


def _range(rng: Any) -> tuple[int, int] | None:
    """An ast-grep range as 1-based ``(first, last)`` lines, or ``None`` when
    it is not a well-formed range."""
    if not isinstance(rng, dict):
        return None
    first, last = _line(rng.get("start")), _line(rng.get("end"))
    if first is None or last is None or first < 1 or last < first:
        return None
    return first, last


#: The most members listed under one symbol; more are counted as cut.
MAX_MEMBERS = 40


def _line(position: Any) -> int | None:
    """ast-grep counts lines from 0."""

    if isinstance(position, dict) and isinstance(position.get("line"), int):
        return position["line"] + 1
    return None


def _outline(call: _Call, items: str, facts: _Facts) -> None:
    if call.target_path.is_file() and call.target_path.suffix.lower() not in OUTLINE_EXTENSIONS:
        facts.unsupported = (
            f"symbol outlines are not available for {call.target_path.suffix or 'this'} files; "
            "use code_search instead"
        )
        return
    if call.target_path.is_dir():
        found = _has_outline_files(call.target_path, call.deadline, call.cancel)
        if found is None:
            if call.cancel is not None and call.cancel.is_set():
                facts.cancelled = True
            else:
                facts.limits.append("the time limit ran out while finding files to outline")
            return
        if found is False:
            facts.unsupported = (
                "no file here is in a language with symbol outlines; use code_search instead"
            )
            return
    argv = [call.exe, "outline", "--items", items, "--json=stream", "--color", "never",
            "--threads", THREADS, *_sg_ignore_flags(call.respect_ignore), call.operand]
    run = call.execute(argv)
    cut_short = _stopped(run, facts, call.timeout_s)
    total = files = without_support = bad = 0
    for raw in run.stdout.splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            bad += 1
            continue
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not entry["path"]
            or not isinstance(entry.get("items"), list)
        ):
            bad += 1
            continue
        path = _relative_result_path(call.root, entry["path"])
        if path is None or path == ".":
            bad += 1
            continue
        if Path(path).suffix.lower() not in OUTLINE_EXTENSIONS:
            without_support += 1
            continue
        files += 1
        for item in entry["items"]:
            lines = _range(item.get("range")) if isinstance(item, dict) else None
            if lines is None or not isinstance(item.get("members", []), list):
                bad += 1
                continue
            total += 1
            if len(facts.results) >= call.max_results:
                continue
            record: dict[str, Any] = {
                "path": path,
                "first_line": lines[0],
                "last_line": lines[1],
                "kind": item.get("symbolType"),
                "name": item.get("name"),
                "import": bool(item.get("isImport")),
                "exported": bool(item.get("isExported")),
            }
            if item.get("signature"):
                signature = str(item["signature"])
                if len(signature) > MAX_LINE_CHARS:
                    facts.shown_in_part += 1
                record["text"] = _cut(signature)
            members = []
            for member in item.get("members") or []:
                member_lines = (
                    _range(member.get("range")) if isinstance(member, dict) else None
                )
                if member_lines is None:
                    bad += 1
                    continue
                members.append({"name": member.get("name"), "kind": member.get("symbolType"),
                                "first_line": member_lines[0], "last_line": member_lines[1]})
            if len(members) > MAX_MEMBERS:
                record["members_not_shown"] = len(members) - MAX_MEMBERS
                members = members[:MAX_MEMBERS]
                facts.shown_in_part += 1
            if members:
                record["members"] = members
            facts.results.append(record)
    facts.coverage.update(
        {
            "files_with_symbols": files,
            "symbols_found": total,
            "outline_languages": sorted(set(OUTLINE_EXTENSIONS.values())),
            "files_without_outline_support": without_support,
            "tests_included": True,
        }
    )
    if total > len(facts.results):
        facts.limits.append(f"showing {len(facts.results)} of {total} symbols")
    if cut_short:
        return
    errors = _sg_errors(facts.diagnostics)
    if bad and not facts.results:
        facts.fatal = f"ast-grep's output could not be read ({bad} unreadable record(s))"
    elif run.returncode != 0 and not run.stdout:
        facts.fatal = f"ast-grep ended with status {run.returncode}"
    elif run.returncode != 0 or errors or bad:
        # ast-grep outline answers an unreadable path with exit 0 and an error line.
        facts.program_errors = errors or [
            f"ast-grep ended with status {run.returncode}" if run.returncode
            else f"{bad} unreadable output record(s)"
        ]


def _pattern(call: _Call, pattern: str, language: str, facts: _Facts) -> None:
    argv = [call.exe, "run", "--config", str(call.private / "sgconfig.yml"),
            "--pattern", pattern, "--lang", language, "--json=stream", "--color", "never",
            "--inspect", "summary", "--threads", THREADS,
            *_sg_ignore_flags(call.respect_ignore), call.operand]
    run = call.execute(argv)
    cut_short = _stopped(run, facts, call.timeout_s)
    total = bad = 0
    for raw in run.stdout.splitlines():
        try:
            match = json.loads(raw)
        except ValueError:
            bad += 1
            continue
        lines = _range(match.get("range")) if isinstance(match, dict) else None
        if lines is None or not isinstance(match.get("file"), str) or not match["file"]:
            bad += 1
            continue
        path = _relative_result_path(call.root, match["file"])
        if path is None or path == ".":
            bad += 1
            continue
        total += 1
        if len(facts.results) >= call.max_results:
            continue
        text, cut = _cut_block(str(match.get("lines") or match.get("text") or ""))
        record: dict[str, Any] = {
            "path": path,
            "first_line": lines[0],
            "last_line": lines[1],
            "text": text,
        }
        if cut:
            record["text_cut"] = True
            facts.shown_in_part += 1
        facts.results.append(record)
    counts = _sg_counts(run.stderr)
    facts.coverage.update(counts)
    facts.coverage.update({"matches_found": total, "tests_included": True})
    if total > len(facts.results):
        facts.limits.append(f"showing {len(facts.results)} of {total} matches")
    if cut_short:
        return
    if any("Pattern contains an ERROR node" in line for line in facts.diagnostics):
        facts.input_problem = f"the pattern is not valid {language} code"
        return
    errors = _sg_errors(facts.diagnostics)
    if bad and not facts.results:
        facts.fatal = f"ast-grep's output could not be read ({bad} unreadable record(s))"
    elif run.returncode != 0 and not run.stdout:
        facts.fatal = f"ast-grep ended with status {run.returncode}: {' '.join(errors)[:200]}"
    elif run.returncode != 0 or errors or bad:
        facts.program_errors = errors or [
            f"ast-grep ended with status {run.returncode}" if run.returncode
            else f"{bad} unreadable output record(s)"
        ]
    elif not counts:
        facts.fatal = "ast-grep did not report what it scanned"
    elif counts.get("files_scanned") == 0:
        facts.unsupported = f"no {language} file was searched here"


def _snapshot_omissions(omitted: Sequence[Mapping[str, Any]], target: str) -> list[str]:
    """Files a commit snapshot left out inside the searched path."""

    inside = [
        item for item in omitted
        if isinstance(item, dict)
        and (target == "." or str(item.get("path", "")) == target
             or str(item.get("path", "")).startswith(target.rstrip("/") + "/"))
    ]
    if not inside:
        return []
    reasons = sorted({str(item.get("reason", "left out")) for item in inside})
    return [
        f"{len(inside)} file(s) in the searched path were left out of the commit snapshot "
        f"({', '.join(reasons)})"
    ]


def run(
    operation: str,
    root: str | os.PathLike[str],
    *,
    query: str = "",
    mode: str = "ranked",
    path: str | None = None,
    pattern: str = "",
    language: str = "",
    items: str = "all",
    max_results: int | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    source: Mapping[str, Any] | None = None,
    omitted: Sequence[Mapping[str, Any]] = (),
    respect_ignore: bool = True,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """One bounded, read-only operation over ``root``.

    ``source`` describes what ``root`` holds (a commit snapshot, from the
    Forge helper); ``omitted`` lists the files that snapshot left out, each
    ``{path, reason}``, and is used, not copied into the answer. Without
    ``source`` the worktree is described before and after the program runs.
    ``respect_ignore`` is false for a snapshot, which holds exactly the
    tracked files.
    """

    limit = _limit(max_results, DEFAULT_MAX_RESULTS, MAX_RESULTS_LIMIT)
    max_chars = max(MIN_ANSWER_CHARS, int(max_chars))
    shown_query: dict[str, Any] = {"path": _echo(path or ".")}
    if operation == "search":
        shown_query.update({"text": _echo(query), "mode": _echo(mode)})
    elif operation == "outline":
        shown_query["items"] = _echo(items)
    elif operation == "pattern":
        shown_query.update({"pattern": _echo(pattern), "language": _echo(language)})
    else:
        operation = _echo(str(operation))
    started = time.monotonic()
    # One deadline for the whole call: describing the worktree, finding
    # files, the program, and checking the worktree again afterwards. The
    # program stops early enough to leave the last check its share.
    deadline = started + timeout_s
    after_reserve = min(2.0, timeout_s * 0.2)

    def refused(status: str, note: str, tool: str | None = None) -> dict[str, Any]:
        return _fit_to_chars(
            _answer(
                operation=operation, status=status, source=source, query=shown_query,
                tool=tool, note=note, elapsed_ms=int((time.monotonic() - started) * 1000),
            ),
            max_chars,
        )

    if operation not in OPERATIONS:
        return refused("input_error", f"unknown operation {operation!r}")
    try:
        root_path = _resolve_root(root)
    except _InputError as exc:
        return refused("input_error", str(exc))
    described_here = source is None
    if described_here:
        source = worktree_source(root_path, deadline=deadline - after_reserve, cancel=cancel)
    try:
        target_path, target = _resolve_target(root_path, path)
    except _InputError as exc:
        return refused("input_error", str(exc))
    shown_query["path"] = _echo(target)

    words: list[str] = []
    if operation == "search":
        if mode not in SEARCH_MODES:
            return refused("input_error", f"mode must be one of {', '.join(SEARCH_MODES)}")
        if not query or len(query) > MAX_QUERY_CHARS:
            return refused("input_error", f"the query must be 1 to {MAX_QUERY_CHARS} characters")
        if mode != "ranked" and any(ch in query for ch in "\n\r\0"):
            return refused("input_error", "literal and regex searches match one line at a time; "
                           "the query must not contain a line break")
        tool = "probe" if mode == "ranked" else "ripgrep"
        if mode == "ranked":
            words = query_words(query)
            if not words:
                return refused("input_error", "the query has no words to rank by", tool)
            shown_query["words"] = words
    elif operation == "outline":
        tool = "ast-grep"
        if items not in ("all", "exports", "structure", "imports"):
            return refused("input_error", "items must be all, exports, structure or imports", tool)
    else:
        tool = "ast-grep"
        language = (language or "").strip().lower()
        shown_query["language"] = language
        if not pattern or len(pattern) > MAX_QUERY_CHARS:
            return refused(
                "input_error", f"the pattern must be 1 to {MAX_QUERY_CHARS} characters", tool
            )
        if language not in PATTERN_LANGUAGES:
            return refused(
                "unsupported",
                f"structural patterns are not available for {language or 'an unnamed language'};"
                " use code_search instead",
                tool,
            )

    entry = toolkit()["tools"][tool]
    if not entry["ok"]:
        return refused("tool_unavailable", entry.get("problem", "not installed"), tool)
    if cancel is not None and cancel.is_set():
        return refused("cancelled", "the search was cancelled before it started", tool)

    facts = _new_facts(respect_ignore)
    facts.limits.extend(_snapshot_omissions(omitted, target))
    program_time = deadline - after_reserve - time.monotonic()
    private = _private_folder(root_path)
    try:
        call = _Call(root_path, target_path, target, limit, respect_ignore, entry["path"],
                     _base_environment(private), private, max(0.0, program_time), cancel,
                     deadline - after_reserve)
        if program_time <= 0:
            facts.limits.append(f"the {timeout_s:g}-second limit ran out before {tool} could run")
        elif operation == "search" and mode == "ranked":
            _search_probe(call, words, facts)
        elif operation == "search":
            _search_rg(call, query, mode, facts)
        elif operation == "outline":
            _outline(call, items, facts)
        else:
            _pattern(call, pattern, language, facts)
    except OSError as exc:
        facts.fatal = f"{tool} could not be started: {type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(private, ignore_errors=True)
    if cancel is not None and cancel.is_set():
        facts.cancelled = True
    if described_here and source is not None and source.get("kind") == "worktree":
        if source.get("fingerprint") is None:
            facts.limits.append("the worktree's state could not be recorded before the search")
        else:
            after = worktree_source(root_path, deadline=deadline, cancel=cancel)
            if after.get("fingerprint") is None:
                facts.limits.append("the worktree could not be checked again after the search")
            elif after.get("fingerprint") != source.get("fingerprint") or after.get(
                "head"
            ) != source.get("head"):
                facts.limits.append("the worktree changed while it was searched")
                source = {**source, "after": after}
    if facts.shown_in_part:
        facts.limits.append(
            f"{facts.shown_in_part} result(s) shown only in part (lines cut at "
            f"{MAX_LINE_CHARS} characters, blocks at {MAX_BLOCK_LINES} lines)"
        )
    status, note = _decide(facts)
    answer = _answer(
        operation=operation, status=status, source=source, query=shown_query, tool=tool,
        facts=facts, note=note,
    )
    return _fit_to_chars(answer, max_chars)


async def run_async(operation: str, root: str | os.PathLike[str], **kwargs: Any) -> dict[str, Any]:
    """:func:`run` in a worker thread; cancelling the task stops the program."""

    cancel = threading.Event()
    task = asyncio.ensure_future(asyncio.to_thread(run, operation, root, cancel=cancel, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        cancel.set()
        await asyncio.wait({task})
        raise


# --------------------------------------------------------------------------
# Self-check inside an image


def self_check(out: Callable[[str], None] = print) -> int:
    """Run every operation on a fresh neutral fixture; 0 when all behave."""

    state = toolkit()
    report: dict[str, Any] = {"toolkit": state, "checks": []}
    if not state["ok"]:
        report["ok"] = False
        out(json.dumps(report, indent=2))
        return 1
    failures = 0
    with tempfile.TemporaryDirectory(prefix="code-search-self-check-") as folder:
        root = Path(folder)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "accounts.py").write_text(
            "class Ledger:\n    def balance(self):\n        return 0\n", encoding="utf-8"
        )
        (root / "tests" / "test_accounts.py").write_text(
            "from src.accounts import Ledger\n\ndef test_balance():\n"
            "    assert Ledger().balance() == 0\n",
            encoding="utf-8",
        )
        (root / "notes.dart").write_text("int ledgerBalance() => 0;\n", encoding="utf-8")
        snapshot = {"kind": "folder", "root": "self-check"}
        checks: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], bool]]] = [
            ("literal", {"operation": "search", "query": "balance", "mode": "literal"},
             lambda a: a["status"] == "ok" and len(a["results"]) >= 2),
            ("regex", {"operation": "search", "query": "def +balance", "mode": "regex"},
             lambda a: a["status"] == "ok"),
            ("ranked includes tests", {"operation": "search", "query": "ledger balance"},
             lambda a: a["status"] == "ok"
             and any(r["path"].startswith("tests/") for r in a["results"])),
            ("no matches", {"operation": "search", "query": "zzqqnothinghere", "mode": "literal"},
             lambda a: a["status"] == "no_matches"),
            ("missing path", {"operation": "search", "query": "x", "path": "absent"},
             lambda a: a["status"] == "input_error"),
            ("outline", {"operation": "outline", "path": "src/accounts.py"},
             lambda a: a["status"] == "ok" and a["results"][0]["name"] == "Ledger"),
            ("outline unsupported", {"operation": "outline", "path": "notes.dart"},
             lambda a: a["status"] == "unsupported"),
            ("pattern", {"operation": "pattern", "pattern": "return $X", "language": "python"},
             lambda a: a["status"] == "ok"),
            ("invalid pattern",
             {"operation": "pattern", "pattern": "def $F(", "language": "python"},
             lambda a: a["status"] == "input_error"),
            ("snapshot omission is partial",
             {"operation": "search", "query": "zzqqnothinghere", "mode": "literal",
              "omitted": [{"path": "big.bin", "reason": "too large"}]},
             lambda a: a["status"] == "partial" and not a["results"]),
            ("snapshot mode ranked",
             {"operation": "search", "query": "ledger balance", "respect_ignore": False},
             lambda a: a["status"] == "ok"
             and any(r["path"].startswith("tests/") for r in a["results"])),
            ("snapshot mode literal",
             {"operation": "search", "query": "balance", "mode": "literal",
              "respect_ignore": False},
             lambda a: a["status"] == "ok"),
            ("snapshot mode pattern",
             {"operation": "pattern", "pattern": "return $X", "language": "python",
              "respect_ignore": False},
             lambda a: a["status"] == "ok"),
            ("snapshot mode outline",
             {"operation": "outline", "path": "src", "respect_ignore": False},
             lambda a: a["status"] == "ok"),
        ]
        for name, call, accept in checks:
            kwargs = dict(call)
            operation = kwargs.pop("operation")
            kwargs.setdefault("source", snapshot)
            answer = run(operation, root, **kwargs)
            passed = bool(accept(answer))
            failures += 0 if passed else 1
            report["checks"].append({"check": name, "passed": passed, "status": answer["status"],
                                     "note": answer["note"], "diagnostics": answer["diagnostics"]})
    report["ok"] = failures == 0
    out(json.dumps(report, indent=2))
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["self-check"]:
        return self_check()
    if args == ["capabilities"]:
        print(json.dumps(capabilities(), indent=2))
        return 0
    print("usage: python -m guardkitfactory.code_search self-check | capabilities",
          file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
