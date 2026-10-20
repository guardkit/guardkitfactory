"""The checkers never open a named pipe, socket or device (20 October 2026).

A model can leave a named pipe (``mkfifo``) among the files it wrote. A plain
``open()`` on it waits forever for a writer, which hung the Coach turn in
GuardKit's direct mode. The checkers now open only regular files.

Every run that could block is done in a child process with a time limit, so
a regression fails the test (the child is killed) instead of hanging the
whole test run.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from guardkitfactory.regular_file import (
    open_regular,
    read_regular_bytes,
    read_regular_text,
    special_kind,
)

pytestmark = pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="named pipes need a POSIX system"
)

_TIME_LIMIT_SECONDS = 60

# Runs every checker the Coach and the feature orchestrator call, on the
# worktree given as the first argument, and prints the results as JSON.
_RUN_CHECKERS = textwrap.dedent(
    """
    import json, logging, sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from guardkitfactory.wiring import analyze_stub_scan, analyze_wiring, parse_file
    from guardkitfactory.wiring.skip_guards import extract_skip_guard_modules

    worktree = sys.argv[1]
    authored = json.loads(sys.argv[2])
    extra = json.loads(sys.argv[3])
    out = {
        "wiring": analyze_wiring(authored, worktree, "feature"),
        "stub_scan": analyze_stub_scan(authored, worktree, "feature"),
        "skip_guards": extract_skip_guard_modules(worktree),
        "parse_file": {
            rel: parse_file(worktree + "/" + rel, "python") is not None for rel in extra
        },
    }
    print(json.dumps(out, sort_keys=True, default=str))
    """
)


def _run_checkers(
    worktree: Path, authored: list[str], parse: list[str] = ()
) -> tuple[dict, str]:
    """Run the checkers in a child process; fail if it does not finish."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                _RUN_CHECKERS,
                str(worktree),
                json.dumps(authored),
                json.dumps(list(parse)),
            ],
            capture_output=True,
            text=True,
            timeout=_TIME_LIMIT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"the checkers did not finish within {_TIME_LIMIT_SECONDS} seconds: "
            "they blocked opening a special file and were killed"
        )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1]), proc.stderr


def _write(worktree: Path, rel: str, content: str) -> None:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_AUTHORED = ["app/service.py", "app/main.py", "app/pipe.py"]


def _regular_project(worktree: Path) -> None:
    """One wired function, one unwired function, one stub body."""
    _write(
        worktree,
        "app/service.py",
        "def used_helper():\n    return 1\n\n\n"
        "def orphan_helper():\n    return 2\n\n\n"
        "def stub_helper():\n    raise NotImplementedError\n",
    )
    _write(
        worktree,
        "app/main.py",
        "from app.service import used_helper, stub_helper\n\n"
        "used_helper()\nstub_helper()\n",
    )
    _write(worktree, "app/__init__.py", "")


def _unwired_symbols(result: dict) -> set[str]:
    return {f["symbol"] for f in result["wiring"]["findings"] if f["pattern"] == "UNWIRED_PATH"}


def test_named_pipes_do_not_hang_and_regular_files_are_analysed_as_before(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    with_pipes = tmp_path / "with_pipes"
    _regular_project(plain)
    _regular_project(with_pipes)
    # Pipes where every checker looks: an authored source file, a file only
    # the text search reads, the project manifest, and a test helper.
    for rel in ("app/pipe.py", "docs/notes.md", "pyproject.toml", "tests/conftest.py"):
        (with_pipes / rel).parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(with_pipes / rel)

    before, _ = _run_checkers(plain, _AUTHORED)
    after, log = _run_checkers(with_pipes, _AUTHORED, parse=["app/pipe.py"])

    # The regular files were really analysed ...
    assert _unwired_symbols(before) == {"orphan_helper"}
    assert before["stub_scan"]["findings"], before["stub_scan"]
    # ... and the pipes change nothing.
    before.pop("parse_file")
    after_parse = after.pop("parse_file")
    assert after == before
    assert after_parse == {"app/pipe.py": False}
    assert "Skipped" in log and "it is a named pipe, not a regular file" in log


def test_socket_and_device_are_skipped(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    _regular_project(worktree)
    sock_path = worktree / "app" / "s.py"
    if len(os.fsencode(sock_path)) > 100:
        pytest.skip("temporary folder path too long for a socket")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
        # A link inside the worktree to a character device.
        os.symlink("/dev/null", worktree / "app" / "device.py")
        result, log = _run_checkers(
            worktree,
            ["app/service.py", "app/main.py", "app/s.py", "app/device.py"],
            parse=["app/s.py", "app/device.py"],
        )
    finally:
        server.close()
    assert _unwired_symbols(result) == {"orphan_helper"}
    assert result["parse_file"] == {"app/s.py": False, "app/device.py": False}
    assert "it is a socket, not a regular file" in log
    assert "it is a character device, not a regular file" in log


def test_link_to_a_regular_file_is_still_followed_and_read(tmp_path: Path) -> None:
    """Today's behaviour, kept: a link to a regular file is read through.

    The target sits in a folder the walk skips, so the only way the text
    search can see the name is through the link.
    """
    worktree = tmp_path / "wt"
    _regular_project(worktree)
    _write(worktree, "node_modules/real.txt", "orphan_helper is called by the runner\n")
    (worktree / "docs").mkdir()
    os.symlink("../node_modules/real.txt", worktree / "docs" / "mention.md")
    result, _ = _run_checkers(worktree, ["app/service.py", "app/main.py"])
    assert _unwired_symbols(result) == set()


# --- the helper itself -------------------------------------------------------


def test_helper_reads_regular_files_and_links_to_them(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"one\r\ntwo\n")
    link = tmp_path / "link.txt"
    os.symlink(target, link)
    assert read_regular_bytes(target) == b"one\r\ntwo\n"
    assert read_regular_bytes(link) == b"one\r\ntwo\n"
    # Same decoding and newline handling as open(path, errors="replace").
    with open(target, errors="replace") as handle:
        assert read_regular_text(target, errors="replace") == handle.read()
    assert read_regular_bytes(tmp_path / "missing") is None
    with pytest.raises(OSError):
        open_regular(tmp_path / "missing")


def test_helper_rechecks_the_type_once_open(tmp_path: Path, monkeypatch, caplog) -> None:
    """A regular file swapped for a pipe between the look-up and the open is
    caught on the open file, and the non-blocking open cannot wait."""
    import guardkitfactory.regular_file as regular_file

    pipe = tmp_path / "swapped.py"
    os.mkfifo(pipe)
    real_stat = os.stat

    class _LooksRegular:
        st_mode = stat.S_IFREG | 0o644

    def stat_before_swap(path, *args, **kwargs):
        if Path(path) == pipe:
            return _LooksRegular()
        return real_stat(path, *args, **kwargs)

    released = []

    def release_a_blocked_reader() -> None:
        # Only reached if the open blocked: give it a writer so the test
        # fails instead of hanging.
        try:
            os.close(os.open(pipe, os.O_WRONLY | os.O_NONBLOCK))
            released.append(True)
        except OSError:
            pass

    guard = threading.Timer(10, release_a_blocked_reader)
    guard.start()
    monkeypatch.setattr(regular_file.os, "stat", stat_before_swap)
    try:
        with caplog.at_level("INFO", logger="guardkitfactory.regular_file"):
            assert read_regular_bytes(pipe) is None
    finally:
        guard.cancel()
    assert not released, "the open blocked on the pipe"
    assert "it is a named pipe, not a regular file" in caplog.text


def test_special_kind_names() -> None:
    assert special_kind(stat.S_IFREG) == ""
    assert special_kind(stat.S_IFIFO) == "named pipe"
    assert special_kind(stat.S_IFSOCK) == "socket"
    assert special_kind(stat.S_IFCHR) == "character device"
    assert special_kind(stat.S_IFBLK) == "block device"
    assert special_kind(stat.S_IFDIR) == "folder"
