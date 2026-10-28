"""Find references: the LSP client, the project's declaration and the
``references`` operation, against a small fake language server
(``fake_lsp_server.py``, standard library only) and, when installed, the real
servers.

The client, declaration and merge tests need nothing installed and run on
GitHub. The operation tests need the pinned ripgrep (it lists the server's
files and finds the text-only matches) and are skipped without it, like
``test_code_search.py``; the real-server tests also need gopls, pyright or
typescript-language-server in ``/opt/language-servers/bin``.
"""

from __future__ import annotations

import gc
import json
import shutil
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from guardkitfactory import code_search
from guardkitfactory.lsp_client import (
    LspCancelled,
    LspClient,
    LspError,
    LspTimeout,
    path_uri,
    utf16_column,
)

_FAKE = Path(__file__).with_name("fake_lsp_server.py")
_RIPGREP = code_search.toolkit()["tools"]["ripgrep"]["ok"]
needs_ripgrep = pytest.mark.skipif(
    not _RIPGREP, reason="the pinned ripgrep is not installed (it lists files and finds text)"
)


def _gone(pid: int) -> bool:
    """Dead: no such process, or only a zombie no one has reaped yet."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state in ("Z", "X")


def _wait_gone(pid: int, seconds: float = 5.0) -> bool:
    stop = time.monotonic() + seconds
    while time.monotonic() < stop:
        if _gone(pid):
            return True
        time.sleep(0.05)
    return _gone(pid)


@pytest.fixture()
def fake_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A folder holding the fake server as ``fake-lsp``, the tests' extra
    server folder; the image folders are pointed at empty ones."""
    folder = tmp_path / "servers"
    folder.mkdir()
    program = folder / "fake-lsp"
    shutil.copy(_FAKE, program)
    program.chmod(program.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    empty = tmp_path / "no-servers"
    empty.mkdir()
    monkeypatch.setattr(code_search, "LANGUAGE_SERVER_DIRS", (str(empty),))
    monkeypatch.setenv(code_search.LANGUAGE_SERVER_DIR_ENV, str(folder))
    return folder


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pkg" / "store.py").write_text(
        "# store_total adds up the store\n"
        "def store_total(rows):\n"
        "    return sum(rows)\n"
    )
    (root / "pkg" / "report.py").write_text(
        "from pkg.store import store_total\n"
        "\n"
        "def report(rows):\n"
        "    return 'store_total: ' + str(store_total(rows))\n"
    )
    (root / "tests" / "test_store.py").write_text(
        "from pkg.store import store_total\n\ndef test_total():\n"
        "    assert store_total([1, 2]) == 3\n"
    )
    (root / "README.md").write_text("Call store_total for the sum.\n")
    (root / "notes.txt").write_text("nothing here\n")
    return root


def _declare(root: Path, entries: list[dict[str, Any]]) -> None:
    (root / ".guardkit").mkdir(exist_ok=True)
    (root / ".guardkit" / "config.yaml").write_text(
        json.dumps({"toolchain": {"test": "true", "language_servers": entries}})
    )


def _fake_entry(log: Path | None = None, mode: str = "normal", **extra: Any) -> dict[str, Any]:
    env = {"FAKE_LSP_MODE": mode, **extra.pop("env", {})}
    if log is not None:
        env["FAKE_LSP_LOG"] = str(log)
    return {"command": ["fake-lsp"], "files": ["**/*.py"], "env": env, **extra}


def _log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def _client(fake_dir: Path, root: Path, **env: str) -> LspClient:
    return LspClient([str(fake_dir / "fake-lsp")], cwd=root, workspace=root,
                     env={"PATH": "/usr/local/bin:/usr/bin:/bin", **env})


# -- the client --------------------------------------------------------------


def test_client_answers_the_servers_requests_and_reads_split_frames(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    log = tmp_path / "log.jsonl"
    client = _client(fake_dir, project, FAKE_LSP_LOG=str(log))
    try:
        client.initialize(initialization_options={"x": 1},
                          deadline=time.monotonic() + 10)
        assert client.server_info == {"name": "fake-lsp", "version": "1.2.3"}
        answers = {e["answer"]: e["result"] for e in _log(log) if "answer" in e}
        # One null per configuration item; null for the capability registration.
        assert answers == {"cfg-1": [None, None], 7: None}
        sent = next(e for e in _log(log) if e.get("method") == "initialize")
        assert sent["params"]["initializationOptions"] == {"x": 1}
        assert sent["params"]["rootUri"] == path_uri(project)
        store = project / "pkg" / "store.py"
        found = client.references(path_uri(store), 1, 4, deadline=time.monotonic() + 10)
        lines = sorted((Path(f["uri"][7:]).name, f["range"]["start"]["line"]) for f in found)
        assert lines == [("report.py", 0), ("report.py", 3), ("store.py", 1),
                         ("test_store.py", 0), ("test_store.py", 3)]
    finally:
        client.close(grace_s=1)
    assert not client.alive


def test_a_slow_answer_times_out_and_the_server_keeps_going(
    fake_dir: Path, project: Path
) -> None:
    client = _client(fake_dir, project, FAKE_LSP_MODE="hang_references")
    try:
        client.initialize(initialization_options=None, deadline=time.monotonic() + 10)
        started = time.monotonic()
        with pytest.raises(LspTimeout):
            client.references(path_uri(project / "pkg" / "store.py"), 1, 4,
                              deadline=time.monotonic() + 0.5)
        assert time.monotonic() - started < 3
        assert client.alive
        cancel = threading.Event()
        threading.Timer(0.3, cancel.set).start()
        with pytest.raises(LspCancelled):
            client.references(path_uri(project / "pkg" / "store.py"), 1, 4,
                              deadline=time.monotonic() + 30, cancel=cancel)
    finally:
        client.close(grace_s=1)


def test_a_server_that_cannot_start_is_an_error_with_its_words(
    fake_dir: Path, project: Path
) -> None:
    client = _client(fake_dir, project, FAKE_LSP_MODE="crash")
    try:
        with pytest.raises(LspError) as raised:
            client.initialize(initialization_options=None, deadline=time.monotonic() + 10)
        assert not isinstance(raised.value, LspTimeout)
        stop = time.monotonic() + 5
        while "cannot start" not in client.stderr_tail() and time.monotonic() < stop:
            time.sleep(0.05)
        assert "cannot start" in client.stderr_tail()
    finally:
        client.close(grace_s=1)


def test_a_broken_frame_is_an_error_not_a_hang(fake_dir: Path, project: Path) -> None:
    client = _client(fake_dir, project, FAKE_LSP_MODE="garbage")
    try:
        with pytest.raises(LspError) as raised:
            client.initialize(initialization_options=None, deadline=time.monotonic() + 10)
        assert not isinstance(raised.value, LspTimeout)
    finally:
        client.close(grace_s=1)


def test_close_stops_the_whole_process_group(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    child_file = tmp_path / "child.pid"
    client = _client(fake_dir, project, FAKE_LSP_MODE="child", FAKE_LSP_CHILD=str(child_file))
    client.initialize(initialization_options=None, deadline=time.monotonic() + 10)
    child = int(child_file.read_text())
    assert not _gone(child)
    client.close(grace_s=1)
    assert _wait_gone(client.process.pid)
    assert _wait_gone(child), "the server's child outlived it"


def test_a_server_that_ignores_shutdown_and_sigterm_is_killed(
    fake_dir: Path, project: Path
) -> None:
    client = _client(fake_dir, project, FAKE_LSP_MODE="stubborn")
    client.initialize(initialization_options=None, deadline=time.monotonic() + 10)
    started = time.monotonic()
    client.close(grace_s=0.3)
    assert time.monotonic() - started < 5
    assert _wait_gone(client.process.pid)
    client.close(grace_s=0.3)  # a second close is harmless


def test_utf16_columns() -> None:
    assert utf16_column("abc", 2) == 2
    assert utf16_column("é𝄞x", 2) == 3  # the clef takes two UTF-16 code units


# -- the project's declaration --------------------------------------------------


def test_no_declaration_and_good_and_bad_declarations(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    assert code_search.declared_servers(root) is None
    (root / ".guardkit").mkdir()
    (root / ".guardkit" / "config.yaml").write_text("toolchain:\n  test: pytest\n")
    assert code_search.declared_servers(root) is None
    _declare(root, [{"command": ["gopls"], "files": ["**/*.go"], "root": "./packages/agent/",
                     "env": {"GOFLAGS": "-tags=live"},
                     "initialization_options": {"b": 1}}])
    (entry,) = code_search.declared_servers(root)  # type: ignore[misc]
    assert entry.command == ("gopls",) and entry.root == "packages/agent"
    assert entry.env == (("GOFLAGS", "-tags=live"),) and json.loads(entry.options) == {"b": 1}
    for bad, words in (
        ({"command": ["/usr/bin/gopls"], "files": ["*.go"]}, "program name"),
        ({"command": [], "files": ["*.go"]}, "command"),
        ({"command": ["gopls"]}, "files"),
        ({"command": ["gopls"], "files": ["*.go"], "root": "../elsewhere"}, "inside"),
        ({"command": ["gopls"], "files": ["*.go"], "env": {"PATH": "/tmp"}}, "PATH"),
        ({"command": ["gopls"], "files": ["*.go"], "flags": 1}, "unknown key"),
    ):
        _declare(root, [bad])
        problem = code_search.declared_servers(root)
        assert isinstance(problem, str) and words in problem, (bad, problem)
    (root / ".guardkit" / "config.yaml").write_text("toolchain: [unclosed\n")
    assert "YAML" in str(code_search.declared_servers(root))


def test_globs_match_paths_from_the_project_root() -> None:
    match = code_search._glob_matches
    assert match("**/*.go", "main.go") and match("**/*.go", "a/b/c.go")
    assert match("*.ts", "src/deep/x.ts")  # no '/': the file name at any depth
    assert match("src/**/*.ts", "src/x.ts") and not match("src/**/*.ts", "lib/x.ts")
    assert not match("**/*.go", "main.gox")


def test_positions_use_the_given_line_or_the_first_occurrences() -> None:
    text = "# total is here\ntotal = 1\nsubtotal = total\n"
    assert code_search._positions(text, "total", 3) == [(2, 11)]
    assert code_search._positions(text, "total", 1) == [(0, 2)]
    assert code_search._positions(text, "total", 9) == []
    assert code_search._positions(text, "total", None) == [(0, 2), (1, 0), (2, 11)]


def test_programs_are_found_only_in_the_fixed_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second, extra = (tmp_path / n for n in ("first", "second", "extra"))
    for folder in (first, second, extra):
        folder.mkdir()
    for folder in (second, extra):
        program = folder / "srv"
        program.write_text("#!/bin/sh\n")
        program.chmod(0o755)
    monkeypatch.setattr(code_search, "LANGUAGE_SERVER_DIRS", (str(first), str(second)))
    monkeypatch.setenv(code_search.LANGUAGE_SERVER_DIR_ENV, str(extra))
    monkeypatch.setenv("PATH", str(extra))
    assert code_search.server_program("srv") == second / "srv"
    (second / "srv").unlink()
    assert code_search.server_program("srv") == extra / "srv"
    monkeypatch.delenv(code_search.LANGUAGE_SERVER_DIR_ENV)
    assert code_search.server_program("srv") is None  # never the caller's PATH


def test_the_toolchain_folder_is_not_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    """``/usr/local/go/bin/go`` would run any code a declaration named."""
    monkeypatch.delenv(code_search.LANGUAGE_SERVER_DIR_ENV, raising=False)
    assert code_search.LANGUAGE_SERVER_DIRS == ("/opt/language-servers/bin",)
    assert code_search.server_program("go") is None
    assert code_search.server_program("gofmt") is None
    # The server's own PATH still has the toolchains it runs.
    assert "/usr/local/go/bin" in code_search.SERVER_PATH_DIRS


def _git(root: Path, *args: str) -> str:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def _repo_with_declaration(root: Path, entry: dict[str, Any]) -> str:
    """A repository on ``main`` declaring ``entry``, then a build branch;
    returns the base commit."""
    root.mkdir(parents=True, exist_ok=True)
    _declare(root, [entry])
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "checkout", "-q", "-b", "autobuild/feature")
    return _git(root, "rev-parse", "HEAD")


def test_the_declaration_is_pinned_at_the_base_commit(tmp_path: Path) -> None:
    root = (tmp_path / "repo").resolve()
    base = _repo_with_declaration(root, {"command": ["first-server"], "files": ["**/*.py"]})
    _declare(root, [{"command": ["second-server"], "files": ["**/*.py"]}])
    _git(root, "commit", "-qam", "the builder changes the server")
    _declare(root, [{"command": ["third-server"], "files": ["**/*.py"]}])
    pinned = code_search.pin_declaration(root, base)
    assert isinstance(pinned.servers, list)
    assert [e.command for e in pinned.servers] == [("first-server",)]
    assert pinned.source.startswith(f"commit {base[:12]}")
    # A commit the worktree does not descend from is refused, not read.
    other = _git(root, "commit-tree", "-m", "x", f"{base}^{{tree}}")
    refused = code_search.pin_declaration(root, other)
    assert isinstance(refused.servers, str) and "not an ancestor" in refused.servers
    assert isinstance(code_search.pin_declaration(root, "HEAD; rm").servers, str)
    # No declaration at the base commit: none, whatever the worktree says now.
    bare = (tmp_path / "bare").resolve()
    bare.mkdir()
    (bare / "a.py").write_text("x = 1\n")
    _git(bare, "init", "-q", "-b", "main")
    _git(bare, "add", "-A")
    _git(bare, "commit", "-qm", "base")
    _declare(bare, [{"command": ["planted"], "files": ["**/*.py"]}])
    assert code_search.pin_declaration(bare, _git(bare, "rev-parse", "HEAD")).servers is None
    # Without a base commit the file is read once, now.
    now = code_search.pin_declaration(root, None)
    assert [e.command for e in now.servers] == [("third-server",)]  # type: ignore[union-attr]
    assert "when the tools were bound" in now.source


def test_install_state_is_said_never_guessed() -> None:
    state = code_search._install_state
    assert state("installed", False, True) == "installed"
    assert state(None, True, False) == "not_installed"  # a commit snapshot
    assert state(None, False, True) == "unknown"


def test_merge_puts_server_references_first_and_marks_the_rest() -> None:
    facts = code_search._new_facts(True)
    text = [{"path": "a.py", "first_line": 1, "text": "x"},
            {"path": "doc.md", "first_line": 4, "text": "x in prose"}]
    code_search._merge_references(Path("/nonexistent"), [("a.py", 1), ("b.py", 2)], text, 20,
                                  "installed", facts)
    assert [(r["path"], r.get("text_only", False)) for r in facts.results] == [
        ("a.py", False), ("b.py", False), ("doc.md", True)]
    assert facts.coverage["server_references"] == 2
    assert facts.coverage["text_only_matches"] == 1
    assert code_search._decide(facts)[0] == "ok"
    assert any("check them by hand" in n for n in facts.notes)

    only_text = code_search._new_facts(True)
    code_search._merge_references(Path("/x"), [], text, 20, "installed", only_text)
    assert code_search._decide(only_text)[0] == "ok"  # text matches alone are still uses

    nothing = code_search._new_facts(True)
    code_search._merge_references(Path("/x"), [], [], 20, "unknown", nothing)
    assert code_search._decide(nothing)[0] == "no_matches"
    assert any("unknown" in n for n in nothing.notes)

    capped = code_search._new_facts(True)
    code_search._merge_references(Path("/x"), [("a.py", n) for n in range(1, 6)], text, 3,
                                  "installed", capped)
    assert len(capped.results) == 3 and capped.limits
    assert code_search._decide(capped)[0] == "partial"


def test_a_session_tells_the_server_about_changed_new_and_deleted_files(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    log = tmp_path / "log.jsonl"
    entry = code_search._server_entry(_fake_entry(log))
    assert isinstance(entry, code_search.ServerEntry)
    root = project.resolve()
    session = code_search._ServerSession(root, entry, fake_dir / "fake-lsp")

    def files() -> dict[str, tuple[int, int]]:
        out = {}
        for path in root.rglob("*.py"):
            st = path.stat()
            out[path.relative_to(root).as_posix()] = (st.st_mtime_ns, st.st_size)
        return out

    try:
        session.known = files()
        session.start(time.monotonic() + 10, None)
        assert session.sync(files(), "pkg/store.py") == (1, 0)  # only the asked file opens
        (root / "pkg" / "new_use.py").write_text("from pkg.store import store_total\n")
        (root / "pkg" / "report.py").write_text("store_total = None\n")
        (root / "tests" / "test_store.py").unlink()
        assert session.sync(files(), "pkg/store.py") == (2, 0)
        assert session.client is not None
        # A request answered means every notice sent before it was read.
        found = session.client.references(path_uri(root / "pkg" / "store.py"), 1, 4,
                                          deadline=time.monotonic() + 10)
        methods = [(e.get("method"), e.get("params")) for e in _log(log) if "method" in e]
        opened = [p["textDocument"]["uri"].rsplit("/", 1)[1]
                  for m, p in methods if m == "textDocument/didOpen"]
        assert opened[0] == "store.py"
        assert sorted(opened[1:]) == ["new_use.py", "report.py"]
        watched = next(p for m, p in methods if m == "workspace/didChangeWatchedFiles")
        kinds = {c["uri"].rsplit("/", 1)[1]: c["type"] for c in watched["changes"]}
        assert kinds == {"new_use.py": 1, "report.py": 2, "test_store.py": 3}
        names = sorted({f["uri"].rsplit("/", 1)[1] for f in found})
        assert names == ["new_use.py", "report.py", "store.py"]
        (root / "pkg" / "report.py").unlink()  # an open file deleted is closed
        session.sync(files(), "pkg/store.py")
        session.client.references(path_uri(root / "pkg" / "store.py"), 1, 4,
                                  deadline=time.monotonic() + 10)
        closes = [e for e in _log(log) if e.get("method") == "textDocument/didClose"]
        assert closes and closes[-1]["params"]["textDocument"]["uri"].endswith("report.py")
    finally:
        session.close()


def test_closing_a_binding_or_dropping_it_stops_its_servers(
    fake_dir: Path, project: Path
) -> None:
    entry = code_search._server_entry(_fake_entry())
    assert isinstance(entry, code_search.ServerEntry)
    root = project.resolve()
    servers = code_search.ReferenceServers()
    session = servers.session(root, entry, fake_dir / "fake-lsp")
    assert servers.session(root, entry, fake_dir / "fake-lsp") is session
    session.start(time.monotonic() + 10, None)
    assert session.client is not None
    pid = session.client.process.pid
    servers.close()
    assert _wait_gone(pid)
    # A closed binding can be used again, and is stopped when collected.
    again = servers.session(root, entry, fake_dir / "fake-lsp")
    assert again is not session
    again.start(time.monotonic() + 10, None)
    assert again.client is not None
    pid = again.client.process.pid
    del servers, again, session
    gc.collect()
    assert _wait_gone(pid)


# -- the operation (needs the pinned ripgrep) ----------------------------------------


@needs_ripgrep
def test_references_merge_server_answers_with_text_only_matches(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    _declare(project, [_fake_entry(tmp_path / "log.jsonl")])
    answer = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             line=2, timeout_s=30)
    assert answer["status"] == "ok", answer
    resolved = [(r["path"], r["first_line"]) for r in answer["results"] if not r.get("text_only")]
    assert resolved == [("pkg/report.py", 1), ("pkg/report.py", 4), ("pkg/store.py", 2),
                        ("tests/test_store.py", 1), ("tests/test_store.py", 4)]
    text_only = [(r["path"], r["first_line"]) for r in answer["results"] if r.get("text_only")]
    # The comment and the README: lines the server did not return.
    assert text_only == [("README.md", 1), ("pkg/store.py", 1)]
    assert all(set(r) <= {"path", "first_line", "text", "text_only"} for r in answer["results"])
    assert answer["results"][0]["text"] == "from pkg.store import store_total"
    coverage = answer["coverage"]
    assert coverage["server"]["name"] == "fake-lsp" and coverage["server"]["version"] == "1.2.3"
    assert coverage["server"]["command"] == ["fake-lsp"]
    assert coverage["install_state"] == "unknown"
    assert coverage["server_references"] == 5 and coverage["text_only_matches"] == 2
    assert "check them by hand" in answer["note"] and "literal" in answer["note"]
    assert answer["tool"] is None and answer["query"]["name"] == "store_total"


@needs_ripgrep
def test_without_a_line_the_first_resolvable_occurrence_is_used(
    fake_dir: Path, project: Path
) -> None:
    _declare(project, [_fake_entry()])
    # The first occurrence is in a comment, where the server finds nothing.
    answer = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             timeout_s=30, install_state="installed")
    assert answer["status"] == "ok"
    assert answer["coverage"]["position"] == {"line": 2, "column": 5, "tried": 2}
    assert "dependencies" not in answer["note"]


@needs_ripgrep
def test_no_matches_only_when_the_server_and_the_text_search_find_nothing(
    fake_dir: Path, project: Path
) -> None:
    _declare(project, [_fake_entry(mode="null_refs")])
    # A server answer of nothing is not "no uses" while the text says otherwise.
    seen = code_search.run("references", project, name="store_total", path="pkg/store.py",
                           line=2, timeout_s=30)
    assert seen["status"] == "ok"
    assert seen["results"] and all(r["text_only"] for r in seen["results"])
    # A hidden file: ripgrep skips it, so nothing anywhere names it.
    (project / ".hidden").mkdir()
    (project / ".hidden" / "lonely.py").write_text("lonely_name = 1\n")
    none = code_search.run("references", project, name="lonely_name",
                           path=".hidden/lonely.py", line=1, timeout_s=30)
    assert none["status"] == "no_matches", none
    assert none["results"] == []


@needs_ripgrep
def test_unsupported_names_what_is_missing(fake_dir: Path, project: Path) -> None:
    undeclared = code_search.run("references", project, name="store_total", path="pkg/store.py")
    assert undeclared["status"] == "unsupported"
    assert "language_servers" in undeclared["note"] and "literal" in undeclared["note"]
    _declare(project, [{**_fake_entry(), "files": ["**/*.go"]}])
    other = code_search.run("references", project, name="store_total", path="pkg/store.py")
    assert other["status"] == "unsupported" and "pkg/store.py" in other["note"]
    _declare(project, [{**_fake_entry(), "command": ["no-such-server", "--stdio"]}])
    missing = code_search.run("references", project, name="store_total", path="pkg/store.py")
    assert missing["status"] == "unsupported" and "'no-such-server'" in missing["note"]
    assert missing["results"] == []


@needs_ripgrep
@pytest.mark.parametrize("mode, words", [("hang_references", "did not answer"),
                                          ("hang_initialize", "did not finish starting"),
                                          ("crash", "could not be started")])
def test_a_server_that_fails_is_a_tool_error_never_no_uses(
    fake_dir: Path, project: Path, mode: str, words: str
) -> None:
    _declare(project, [_fake_entry(mode=mode)])
    started = time.monotonic()
    answer = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             line=2, timeout_s=2)
    assert answer["status"] == "tool_error", answer
    assert words in answer["note"] and "literal" in answer["note"]
    assert answer["results"] == []
    assert time.monotonic() - started < 10


@needs_ripgrep
def test_a_command_outside_the_server_folder_is_unsupported(
    fake_dir: Path, project: Path
) -> None:
    for command in (["go", "run", "./pwn"], ["sh", "-c", "touch /tmp/pwned"]):
        _declare(project, [{**_fake_entry(), "command": command}])
        answer = code_search.run("references", project, name="store_total",
                                 path="pkg/store.py", line=2)
        assert answer["status"] == "unsupported", answer
        assert f"{command[0]!r} is not installed in" in answer["note"]
        assert "/usr/local/go/bin" not in answer["note"].split("installed in", 1)[1]


@needs_ripgrep
def test_bad_arguments_are_input_errors(fake_dir: Path, project: Path) -> None:
    _declare(project, [_fake_entry()])
    for kwargs, words in (
        ({"name": "", "path": "pkg/store.py"}, "name"),
        ({"name": "two words", "path": "pkg/store.py"}, "name"),
        ({"name": "store_total", "path": "pkg/store.py", "line": 0}, "line"),
        ({"name": "store_total", "path": "pkg/store.py", "line": 3}, "line 3"),
        ({"name": "store_total", "path": "pkg"}, "file"),
        ({"name": "store_total", "path": "../outside.py"}, "outside"),
        ({"name": "nowhere_at_all", "path": "pkg/store.py"}, "anywhere"),
    ):
        answer = code_search.run("references", project, **kwargs)  # type: ignore[arg-type]
        assert answer["status"] == "input_error", (kwargs, answer)
        assert words in answer["note"], (kwargs, answer["note"])


@needs_ripgrep
def test_a_binding_keeps_its_server_and_sees_changed_files(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    pid_file = tmp_path / "server.pid"
    _declare(project, [_fake_entry(env={"FAKE_LSP_PID": str(pid_file)})])
    servers = code_search.ReferenceServers()
    first = code_search.run("references", project, name="store_total", path="pkg/store.py",
                            line=2, timeout_s=30, servers=servers)
    pid = int(pid_file.read_text())
    assert first["coverage"]["server_references"] == 5
    (project / "pkg" / "later.py").write_text("from pkg.store import store_total\n")
    second = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             line=2, timeout_s=30, servers=servers)
    assert int(pid_file.read_text()) == pid  # the same server answered
    assert ("pkg/later.py", 1) in {(r["path"], r["first_line"]) for r in second["results"]
                                   if not r.get("text_only")}
    assert servers.running() == 1
    servers.close()
    assert _wait_gone(pid)


@needs_ripgrep
def test_a_call_without_a_binding_stops_its_server(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    pid_file = tmp_path / "server.pid"
    _declare(project, [_fake_entry(env={"FAKE_LSP_PID": str(pid_file)})])
    answer = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             line=2, timeout_s=30)
    assert answer["status"] == "ok"
    assert _wait_gone(int(pid_file.read_text()))


@needs_ripgrep
def test_a_snapshot_reports_dependencies_not_installed(fake_dir: Path, project: Path) -> None:
    _declare(project, [_fake_entry()])
    answer = code_search.run("references", project, name="store_total", path="pkg/store.py",
                             line=2, timeout_s=30, source={"kind": "commit", "root": "snap"},
                             respect_ignore=False)
    assert answer["coverage"]["install_state"] == "not_installed"
    assert "not installed" in answer["note"]


@needs_ripgrep
def test_the_tool_offers_references_and_closes_its_servers(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    if not code_search.available()[0]:
        pytest.skip("the tools are offered only with every pinned program installed")
    from guardkitfactory.harness.code_search_tools import (
        TOOL_NAMES,
        close_code_search_tools,
        code_search_tools,
    )

    pid_file = tmp_path / "server.pid"
    _declare(project, [_fake_entry(env={"FAKE_LSP_PID": str(pid_file)})])
    tools, reason = code_search_tools(project, install_state="installed")
    assert reason == "" and [t.name for t in tools] == list(TOOL_NAMES)
    tool = next(t for t in tools if t.name == "code_references")
    assert "text_only" in tool.description and "by hand" in tool.description
    answer = json.loads(tool.invoke({"name": "store_total", "path": "pkg/store.py", "line": 2}))
    assert answer["status"] == "ok" and answer["coverage"]["install_state"] == "installed"
    bad = json.loads(tool.invoke({"name": "store_total", "path": "pkg/store.py", "line": 0}))
    assert bad["status"] == "input_error"
    pid = int(pid_file.read_text())
    assert not _gone(pid)  # kept for the binding
    close_code_search_tools(tools)
    assert _wait_gone(pid)


@needs_ripgrep
def test_editing_the_declaration_after_binding_changes_nothing(
    fake_dir: Path, project: Path, tmp_path: Path
) -> None:
    if not code_search.available()[0]:
        pytest.skip("the tools are offered only with every pinned program installed")
    from guardkitfactory.harness.code_search_tools import (
        close_code_search_tools,
        code_search_tools,
    )

    pinned_pid, edited_pid = tmp_path / "pinned.pid", tmp_path / "edited.pid"
    _repo_with_declaration(project, _fake_entry(env={"FAKE_LSP_PID": str(pinned_pid)}))
    tools, _ = code_search_tools(project)
    tool = next(t for t in tools if t.name == "code_references")
    edited = _fake_entry(env={"FAKE_LSP_PID": str(edited_pid)})
    try:
        # An edit in the worktree after the tools were bound.
        _declare(project, [edited])
        answer = json.loads(tool.invoke({"name": "store_total", "path": "pkg/store.py",
                                         "line": 2}))
        assert answer["status"] == "ok", answer
        assert answer["coverage"]["declaration"].startswith("commit ")
        assert pinned_pid.exists() and not edited_pid.exists()
    finally:
        close_code_search_tools(tools)
    # Committed on the build branch: the next binding still uses the base's.
    _git(project, "commit", "-qam", "the builder changes the server")
    tools, _ = code_search_tools(project)
    try:
        tool = next(t for t in tools if t.name == "code_references")
        answer = json.loads(tool.invoke({"name": "store_total", "path": "pkg/store.py",
                                         "line": 2}))
        assert answer["status"] == "ok" and not edited_pid.exists()
    finally:
        close_code_search_tools(tools)


# -- real language servers (skipped unless installed) ---------------------------------


def _real(name: str) -> Path | None:
    return code_search.server_program(name) if _RIPGREP else None


def _git_init(root: Path) -> None:
    for args in (("init", "-q"), ("add", "-A")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


_REAL_PROJECTS: dict[str, dict[str, Any]] = {
    "gopls": {
        "entry": {"command": ["gopls"], "files": ["**/*.go"], "root": "mod",
                  "env": {"GOFLAGS": "-tags=live", "GOTOOLCHAIN": "local", "GOPROXY": "off"}},
        "files": {
            "mod/go.mod": "module example.com/m\n\ngo 1.22\n",
            "mod/store/store.go": "package store\n\n// Total adds rows.\n"
                                  "func Total(rows []int) int {\n\treturn len(rows)\n}\n",
            "mod/report/report.go": "package report\n\nimport \"example.com/m/store\"\n\n"
                                    "func Report() int { return store.Total(nil) }\n",
            "mod/store/store_live_test.go": "//go:build live\n\npackage store\n\n"
                                            "import \"testing\"\n\nfunc TestTotal(t *testing.T) "
                                            "{ _ = Total(nil) }\n",
            "README.md": "Total is the sum.\n",
        },
        "ask": ("Total", "mod/store/store.go", 4),
        "resolved": {("mod/store/store.go", 4), ("mod/report/report.go", 5),
                     ("mod/store/store_live_test.go", 7)},
        "added": ("mod/report/zz_added.go", "package report\n\nimport \"example.com/m/store\"\n"
                  "\nvar Added = store.Total(nil)\n", 5),
    },
    "pyright-langserver": {
        "entry": {"command": ["pyright-langserver", "--stdio"], "files": ["**/*.py"]},
        "files": {
            "pkg/__init__.py": "",
            "pkg/store.py": "def total(rows):\n    \"\"\"total adds rows.\"\"\"\n"
                            "    return len(rows)\n",
            "pkg/report.py": "from pkg.store import total\n\n\ndef report():\n"
                             "    return total([])\n",
            "tests/test_store.py": "from pkg.store import total\n\n\ndef test_total():\n"
                                   "    assert total([]) == 0\n",
            "README.md": "total is the sum.\n",
        },
        "ask": ("total", "pkg/store.py", 1),
        "resolved": {("pkg/store.py", 1), ("pkg/report.py", 1), ("pkg/report.py", 5),
                     ("tests/test_store.py", 1), ("tests/test_store.py", 5)},
        "added": ("pkg/zz_added.py", "from pkg.store import total\n\nADDED = total([])\n", 3),
    },
    "typescript-language-server": {
        "entry": {"command": ["typescript-language-server", "--stdio"],
                  "files": ["**/*.ts"]},
        "files": {
            "tsconfig.json": json.dumps({"compilerOptions": {"strict": True, "noEmit": True,
                                                             "module": "nodenext"},
                                         "include": ["src", "tests"]}),
            "package.json": json.dumps({"name": "m", "type": "module"}),
            "src/store.ts": "// total adds rows.\nexport function total(rows: number[]): number "
                            "{\n  return rows.length;\n}\n",
            "src/report.ts": "import { total } from './store.js';\n\n"
                             "export const report = (): number => total([]);\n",
            "tests/store.test.ts": "import { total } from '../src/store.js';\n\n"
                                   "export const checked = total([]) === 0;\n",
            "README.md": "total is the sum.\n",
        },
        "ask": ("total", "src/store.ts", 2),
        "resolved": {("src/store.ts", 2), ("src/report.ts", 1), ("src/report.ts", 3),
                     ("tests/store.test.ts", 1), ("tests/store.test.ts", 3)},
        "added": ("src/zz_added.ts", "import { total } from './store.js';\n\n"
                  "export const added = total([]);\n", 3),
    },
}


@pytest.mark.parametrize("server", sorted(_REAL_PROJECTS))
def test_a_real_server_resolves_references(server: str, tmp_path: Path) -> None:
    if _real(server) is None:
        pytest.skip(f"{server} or the pinned ripgrep is not installed")
    spec = _REAL_PROJECTS[server]
    root = tmp_path / "real"
    for rel, text in spec["files"].items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _declare(root, [spec["entry"]])
    _git_init(root)
    name, path, line = spec["ask"]
    servers = code_search.ReferenceServers()
    try:
        answer = code_search.run("references", root, name=name, path=path, line=line,
                                 timeout_s=90, servers=servers)
        assert answer["status"] == "ok", answer
        resolved = {(r["path"], r["first_line"]) for r in answer["results"]
                    if not r.get("text_only")}
        assert resolved == spec["resolved"], answer
        text_only = {r["path"] for r in answer["results"] if r.get("text_only")}
        assert "README.md" in text_only
        assert answer["coverage"]["server"]["command"] == spec["entry"]["command"]
        # A file added after the server started is seen on the next question.
        added, text, added_line = spec["added"]
        (root / added).write_text(text)
        again = code_search.run("references", root, name=name, path=path, line=line,
                                timeout_s=90, servers=servers)
        assert (added, added_line) in {(r["path"], r["first_line"]) for r in again["results"]
                                       if not r.get("text_only")}, again
    finally:
        servers.close()
