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
import locale
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


# Runs only the wiring analysis, as GuardKit's Coach does once per turn.
_RUN_WIRING_ONLY = textwrap.dedent(
    """
    import json, logging, sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from guardkitfactory.wiring import analyze_wiring

    out = analyze_wiring(json.loads(sys.argv[2]), sys.argv[1], "feature")
    print(json.dumps(out, sort_keys=True, default=str))
    """
)

# The two BDD plugin reads: the pytest-bdd preflight (conftest.py files) and
# cucumber-js discovery (package.json).
_RUN_BDD_READS = textwrap.dedent(
    """
    import json, logging, sys
    from pathlib import Path
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from guardkitfactory.bdd.plugin import StackProfile
    from guardkitfactory.bdd.plugins.cucumber_js_plugin import CucumberJSPlugin
    from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin

    worktree = Path(sys.argv[1])
    stack = StackProfile("typescript", "cucumber", "npm", worktree)
    out = {
        "pytest_bdd_preflight": PytestBDDPlugin().preflight("TASK-PIPE-1", worktree),
        "cucumber_discovered": CucumberJSPlugin.discover(stack, worktree) is not None,
    }
    print(json.dumps(out, sort_keys=True))
    """
)


# A pytest-bdd run whose "pytest" (GUARDKIT_BDD_VENV_PYTHON=/bin/true) exits
# at once without writing a report, so the plugin reads whatever is already
# at the report path: the case where a named pipe was left there.
_RUN_BDD_REPORT = textwrap.dedent(
    """
    import dataclasses, json, logging, sys
    from pathlib import Path
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin

    result = PytestBDDPlugin().run([], "TASK-PIPE-1", Path(sys.argv[1]), timeout_seconds=30)
    print(json.dumps(dataclasses.asdict(result), default=str))
    """
)


def _run_child(code: str, *args: str) -> tuple[object, str]:
    """Run ``code`` in a child process; fail if it does not finish."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    env["GUARDKIT_BDD_VENV_PYTHON"] = "/bin/true"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, *args],
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


def _run_checkers(
    worktree: Path, authored: list[str], parse: list[str] = ()
) -> tuple[dict, str]:
    """Run every checker in a child process; fail if it does not finish."""
    return _run_child(
        _RUN_CHECKERS, str(worktree), json.dumps(authored), json.dumps(list(parse))
    )


def _info_lines(log: str) -> list[str]:
    return [line for line in log.splitlines() if line.startswith("INFO:guardkitfactory")]


def _write(worktree: Path, rel: str, content: str) -> None:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_AUTHORED = ["app/service.py", "app/main.py", "app/pipe.py", "src/Widget.cs"]


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
    # A C# file too, so the C# manifest search (the pattern *.csproj) runs.
    _write(
        worktree,
        "src/Widget.cs",
        "namespace Shop\n{\n    public class WidgetBuilder\n    {\n"
        "        public int Build() { return 1; }\n    }\n}\n",
    )


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
    # the text search reads, a manifest by name and one found by pattern
    # (*.csproj), and a test helper.
    for rel in (
        "app/pipe.py",
        "docs/notes.md",
        "pyproject.toml",
        "Shop.csproj",
        "tests/conftest.py",
    ):
        (with_pipes / rel).parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(with_pipes / rel)

    before, _ = _run_checkers(plain, _AUTHORED)
    after, log = _run_checkers(with_pipes, _AUTHORED, parse=["app/pipe.py"])

    # The regular files were really analysed ...
    assert "orphan_helper" in _unwired_symbols(before)
    assert set(before["wiring"]["languages"]) >= {"python", "c_sharp"}, before["wiring"]
    assert before["stub_scan"]["findings"], before["stub_scan"]
    # ... and the pipes change nothing.
    before.pop("parse_file")
    after_parse = after.pop("parse_file")
    assert after == before
    assert after_parse == {"app/pipe.py": False}
    # One line per checker call. The wiring analysis does not read test
    # files, so the pipe at tests/conftest.py is the skip-guard scan's.
    assert "Wiring analysis skipped 4 entries that are not regular files" in log
    assert "; and 1 more." in log
    assert "Skip guard scan skipped 1 entry that is not a regular file" in log
    assert "tests/conftest.py (named pipe)" in log
    # parse_file is a single read outside a checker call: its own note.
    assert "it is a named pipe, not a regular file" in log


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
    assert "orphan_helper" in _unwired_symbols(result)
    assert result["parse_file"] == {"app/s.py": False, "app/device.py": False}
    assert "app/s.py (socket)" in log
    assert "app/device.py (character device)" in log
    assert "it is a socket, not a regular file" in log
    assert "it is a character device, not a regular file" in log


def test_many_skipped_entries_give_one_log_line_per_call(tmp_path: Path) -> None:
    """Thousands of sockets must not flood the run log: one INFO line for
    the whole wiring analysis, with the count and a few examples."""
    worktree = tmp_path / "wt"
    _regular_project(worktree)
    folder = worktree / "s"
    folder.mkdir()
    if len(os.fsencode(folder / "s0000.py")) > 100:
        pytest.skip("temporary folder path too long for a socket")
    count = 1000
    for n in range(count):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(folder / f"s{n:04d}.py"))  # the file stays after close
    result, log = _run_child(
        _RUN_WIRING_ONLY, str(worktree), json.dumps(["app/service.py", "app/main.py"])
    )
    assert "orphan_helper" in {
        f["symbol"] for f in result["findings"] if f["pattern"] == "UNWIRED_PATH"
    }
    lines = _info_lines(log)
    assert len(lines) == 1, lines[:5]
    assert f"Wiring analysis skipped {count} entries that are not regular files" in lines[0]
    assert f"; and {count - 3} more." in lines[0]


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


# --- the two BDD plugin reads ----------------------------------------------


def test_bdd_plugin_reads_skip_pipes(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    _write(worktree, "features/shop/test_shop__TASK_PIPE_1.py", "# glue\n")
    # Neither conftest.py names the task variable, so the preflight has to
    # read both: the regular one, and the pipe, which it must skip.
    _write(worktree, "features/conftest.py", "import os\n")
    os.mkfifo(worktree / "features" / "shop" / "conftest.py")
    os.mkfifo(worktree / "package.json")
    result, log = _run_child(_RUN_BDD_READS, str(worktree))
    assert result == {"pytest_bdd_preflight": False, "cucumber_discovered": False}
    assert "pytest-bdd preflight skipped 1 entry that is not a regular file" in log
    assert "package.json: it is a named pipe, not a regular file" in log


_REPORT = ".guardkit/autobuild/TASK-PIPE-1/bdd_TASK-PIPE-1.xml"


def _git_worktree(tmp_path: Path) -> Path:
    """A git checkout: project commands get their private HOME and TMPDIR
    inside its git folder, and will not run without one."""
    worktree = tmp_path / "wt"
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    return worktree


@pytest.mark.skipif(not os.access("/bin/true", os.X_OK), reason="needs /bin/true")
def test_bdd_report_that_is_a_pipe_gives_an_errored_result(tmp_path: Path) -> None:
    worktree = _git_worktree(tmp_path)
    (worktree / _REPORT).parent.mkdir(parents=True)
    os.mkfifo(worktree / _REPORT)
    result, _ = _run_child(_RUN_BDD_REPORT, str(worktree))
    assert result["scenarios_errored"] == 1
    assert result["scenarios_attempted"] == 0
    assert result["errors"] == [
        f"junit report is not a regular file, so it was not read: {worktree / _REPORT}"
    ]


@pytest.mark.skipif(not os.access("/bin/true", os.X_OK), reason="needs /bin/true")
def test_bdd_report_that_is_regular_xml_is_read_as_before(tmp_path: Path) -> None:
    worktree = _git_worktree(tmp_path)
    _write(
        worktree,
        _REPORT,
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite tests="5" '
        'failures="1" errors="1" skipped="1" time="2.5"/></testsuites>',
    )
    result, _ = _run_child(_RUN_BDD_REPORT, str(worktree))
    assert {k: result[k] for k in (
        "scenarios_attempted", "scenarios_passed", "scenarios_failed",
        "scenarios_skipped", "scenarios_errored", "duration_seconds", "errors",
    )} == {
        "scenarios_attempted": 5, "scenarios_passed": 2, "scenarios_failed": 1,
        "scenarios_skipped": 1, "scenarios_errored": 1, "duration_seconds": 2.5,
        "errors": [],
    }


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


def test_helper_decodes_like_open_for_text_that_is_not_utf8(tmp_path: Path) -> None:
    """Bytes that are not UTF-8 decode exactly as open() decodes them, with
    the same error handling, so dropping ``errors`` or changing the default
    encoding is caught."""
    latin = tmp_path / "latin.txt"
    latin.write_bytes(b"caf\xe9 au lait\r\n")
    with open(latin, errors="replace") as handle:
        expected = handle.read()
    assert read_regular_text(latin, errors="replace") == expected
    assert read_regular_text(latin, encoding="utf-8", errors="replace") == "caf\ufffd au lait\n"
    if locale.getpreferredencoding(False).lower().replace("-", "") == "utf8":
        assert expected == "caf\ufffd au lait\n"
        with pytest.raises(UnicodeDecodeError):
            read_regular_text(latin)


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
