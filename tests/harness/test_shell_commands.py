"""A shell command leaves nothing running, and tools know no one is watching.

19 October 2026. A factory build: the build's 4 GiB sandbox ran out of memory
while the builder was adding a test-coverage script. At the kill it held
dozens of test-runner processes under a command of the shape
``timeout N <test command> | tail``, and the kernel stopped GuardKit, the
biggest single process, so the build was lost. DeepAgents' shell kills only
the shell itself when a command times out, and nothing at all when it
returns, so whatever a command starts in the background keeps running.

These tests show, with harmless ``sleep`` processes standing in for a
forgotten watcher, server or test run:

* every role's shell has ``CI=true`` unless the project declares ``CI`` itself;
* a process a command leaves running is stopped when the command returns,
  also when it moved to its own process group (as ``timeout`` does) or to a
  session of its own (as ``setsid`` does), and the log and the output say so;
* a background process that keeps the output open does not hold the agent
  until the time limit;
* on a timeout the command and everything it started are stopped;
* processes the command did not start are never touched;
* output, exit codes and the timeout message are DeepAgents' own.

No network, no model and no ``claude``. Every process started here is
stopped by the test's own clean-up if the code under test fails to.
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from deepagents.backends.local_shell import LocalShellBackend

from guardkitfactory import build_autobuild_backend
from guardkitfactory.harness import shell_commands
from guardkitfactory.harness.backend_config import SHELL_ROLES
from guardkitfactory.harness.shell_commands import (
    COMMAND_MARKER_NAME,
    CommandSessionShellBackend,
)

linux_only = pytest.mark.skipif(
    not Path("/proc/self/stat").exists() or sys.platform != "linux",
    reason="the process checks read /proc",
)

_ENV = {"PATH": "/usr/bin:/bin"}


def _worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "host" / ".guardkit" / "worktrees" / "FEAT-X"
    worktree.mkdir(parents=True)
    return worktree


def _alive(pid: int) -> bool:
    try:
        data = Path(f"/proc/{pid}/stat").read_bytes()
    except OSError:
        return False
    state = data[data.rindex(b")") + 2 :].split()[0]
    return state not in (b"Z", b"X")


def _pid(folder: Path, name: str) -> int:
    return int((folder / name).read_text().strip())


@pytest.fixture
def started(tmp_path: Path) -> Iterator[list[int]]:
    """Pids the test started; any still running at the end are killed."""
    pids: list[int] = []
    yield pids
    for name in ("bg.pid", "inner.pid", "fg.pid"):
        file = tmp_path / name
        if file.exists():
            try:
                pids.append(int(file.read_text().strip()))
            except ValueError:
                pass
    for pid in pids:
        if _alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def _shell(folder: Path, timeout: int = 60) -> CommandSessionShellBackend:
    return CommandSessionShellBackend(
        root_dir=folder, virtual_mode=False, env=dict(_ENV), timeout=timeout
    )


# A line that waits until the background process has written its pid.
_WAIT_FOR = "while [ ! -s {name} ]; do sleep 0.05; done"


# ---------------------------------------------------------------------------
# The environment
# ---------------------------------------------------------------------------


class TestCiIsSet:
    @pytest.mark.parametrize("role", [None, *SHELL_ROLES])
    def test_every_role_shell_has_ci_true(
        self, tmp_path: Path, role: str | None
    ) -> None:
        worktree = _worktree(tmp_path)
        backend = build_autobuild_backend(worktree, shell_role=role)

        assert backend.default._env["CI"] == "true"
        result = backend.execute('printf "%s" "$CI"')
        assert result.output == "true"

    def test_a_project_that_declares_ci_keeps_its_own_value(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        worktree = _worktree(tmp_path)
        monkeypatch.setenv("CI", "0")

        with caplog.at_level(logging.WARNING):
            backend = build_autobuild_backend(
                worktree, launch_environment={"settings": ["CI"]}
            )

        assert backend.default._env["CI"] == "0"
        assert backend.execute('printf "%s" "$CI"').output == "0"
        assert "set by the backend itself" not in caplog.text

    def test_a_declared_ci_not_set_here_falls_back_to_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = _worktree(tmp_path)
        monkeypatch.delenv("CI", raising=False)

        backend = build_autobuild_backend(
            worktree, launch_environment={"settings": ["CI"]}
        )

        assert backend.default._env["CI"] == "true"

    def test_the_factory_process_ci_is_not_copied_unless_declared(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = _worktree(tmp_path)
        monkeypatch.setenv("CI", "0")

        backend = build_autobuild_backend(worktree)

        assert backend.default._env["CI"] == "true"

    def test_each_command_has_its_own_marker_and_the_shell_env_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        worktree = _worktree(tmp_path)
        backend = build_autobuild_backend(worktree)
        before = dict(backend.default._env)

        first = backend.execute(f'printf "%s" "${COMMAND_MARKER_NAME}"').output
        second = backend.execute(f'printf "%s" "${COMMAND_MARKER_NAME}"').output

        assert len(first) == 32 and len(second) == 32
        assert first != second
        assert backend.default._env == before
        assert COMMAND_MARKER_NAME not in before


# ---------------------------------------------------------------------------
# What a command leaves behind
# ---------------------------------------------------------------------------


@linux_only
class TestLeftoversAreStopped:
    def test_the_factory_backend_runs_commands_this_way(
        self, tmp_path: Path, started: list[int], caplog: pytest.LogCaptureFixture
    ) -> None:
        worktree = _worktree(tmp_path)
        backend = build_autobuild_backend(worktree)
        pidfile = tmp_path / "bg.pid"

        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = backend.execute(
                f"sleep 300 >/dev/null 2>&1 & echo $! > {pidfile}; echo started"
            )

        assert isinstance(backend.default._inner, CommandSessionShellBackend)
        assert result.exit_code == 0
        assert result.output.startswith("started\n")
        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert "left 1 process running; it was stopped" in caplog.text
        assert "sleep 300" in caplog.text

    def test_a_background_process_is_stopped_when_the_command_returns(
        self, tmp_path: Path, started: list[int], caplog: pytest.LogCaptureFixture
    ) -> None:
        shell = _shell(tmp_path)

        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = shell.execute(
                "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; echo started"
            )

        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert result.output == (
            "started\n\n\nNote: this command finished but left 1 process "
            "running; it was stopped. Start and use a server or watcher "
            "within one command."
        )
        assert result.exit_code == 0
        assert caplog.records[-1].getMessage() == (
            "A shell command finished but left 1 process running; it was "
            "stopped. The command: sleep 300 >/dev/null 2>&1 & echo $! > "
            "bg.pid; echo started"
        )

    def test_a_process_in_its_own_group_is_stopped(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        # The incident's shape: ``timeout`` moves itself and what it runs into
        # a process group of its own, so signalling the shell's group alone
        # would miss them.
        if shutil.which("timeout", path=_ENV["PATH"]) is None:
            pytest.skip("no timeout program")
        shell = _shell(tmp_path)

        result = shell.execute(
            "timeout 120 sh -c 'echo $$ > inner.pid; exec sleep 300' "
            ">/dev/null 2>&1 & echo $! > bg.pid; "
            + _WAIT_FOR.format(name="inner.pid")
        )

        assert result.exit_code == 0
        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert not _alive(_pid(tmp_path, "inner.pid"))
        assert "left 2 processes running" in result.output

    def test_a_process_in_a_session_of_its_own_is_stopped(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")
        shell = _shell(tmp_path)

        shell.execute(
            "setsid sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="bg.pid")
        )

        assert not _alive(_pid(tmp_path, "bg.pid"))

    def test_a_process_without_the_marker_is_stopped_by_its_session(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        # Out of the shell's group (``timeout``) and without the marker:
        # only the session finds them.
        if shutil.which("timeout", path=_ENV["PATH"]) is None:
            pytest.skip("no timeout program")
        shell = _shell(tmp_path)

        result = shell.execute(
            f"env -u {COMMAND_MARKER_NAME} timeout 120 sh -c 'echo $$ > bg.pid; "
            "exec sleep 300' >/dev/null 2>&1 & " + _WAIT_FOR.format(name="bg.pid")
        )

        assert "left 2 processes running" in result.output
        assert not _alive(_pid(tmp_path, "bg.pid"))

    def test_a_process_that_ignores_sigterm_is_killed(
        self, tmp_path: Path, started: list[int], caplog: pytest.LogCaptureFixture
    ) -> None:
        shell = _shell(tmp_path)

        began = time.monotonic()
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = shell.execute(
                "sh -c 'trap \"\" TERM; echo $$ > bg.pid; exec sleep 300' "
                ">/dev/null 2>&1 & " + _WAIT_FOR.format(name="bg.pid")
            )
        took = time.monotonic() - began

        assert not _alive(_pid(tmp_path, "bg.pid"))
        # It outlived SIGTERM's grace, so SIGKILL ended it.
        assert took >= shell_commands._GRACE_SECONDS
        assert "left 1 process running; it was stopped" in result.output
        assert "still running" not in caplog.text

    def test_a_refused_pidfd_still_stops_the_process(
        self,
        tmp_path: Path,
        started: list[int],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A security filter may refuse pidfd_open (EPERM); the process is
        # then checked and signalled the ordinary way.
        def refused(_pid: int) -> int:
            raise PermissionError(errno.EPERM, "refused by a filter")

        monkeypatch.setattr(shell_commands.os, "pidfd_open", refused)
        result = _shell(tmp_path).execute(
            "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; echo started"
        )

        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert "left 1 process running; it was stopped" in result.output

    def test_without_a_pidfd_a_process_outside_the_group_is_never_signalled(
        self,
        tmp_path: Path,
        started: list[int],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # No pidfd: the command's own group is still stopped (by the number
        # the uncollected shell pins), but a process that left the group is
        # not signalled by number, and the result says so plainly.
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")

        def refused(_pid: int) -> int:
            raise PermissionError(errno.EPERM, "refused by a filter")

        def no_kill(pid: int, sig: int) -> None:
            raise AssertionError(f"signalled {pid} by number")

        monkeypatch.setattr(shell_commands.os, "pidfd_open", refused)
        monkeypatch.setattr(shell_commands.os, "kill", no_kill)
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute(
                "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; "
                "setsid sh -c 'echo $$ > inner.pid; exec sleep 300' >/dev/null 2>&1 & "
                + _WAIT_FOR.format(name="inner.pid")
            )

        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert _alive(_pid(tmp_path, "inner.pid"))
        assert (
            "left 2 processes running; 1 was stopped. 1 process outside the "
            "command's process group could not be stopped safely on this system "
            "(it does not allow signalling one process through a pidfd), so it is "
            "still running."
        ) in result.output
        assert "could not be stopped safely" in caplog.text

    def test_a_refused_signal_through_a_pidfd_is_reported_not_counted(
        self,
        tmp_path: Path,
        started: list[int],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The pidfd opens but the signal is refused (EPERM): the process was
        # not signalled, so it is reported as not stopped, never as "gone".
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")

        def refused(_handle: int, _sig: int) -> None:
            raise PermissionError(errno.EPERM, "refused by a filter")

        monkeypatch.setattr(shell_commands.signal, "pidfd_send_signal", refused)
        result = _shell(tmp_path).execute(
            "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; "
            "setsid sh -c 'echo $$ > inner.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="inner.pid")
        )
        monkeypatch.undo()

        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert _alive(_pid(tmp_path, "inner.pid"))
        assert "left 2 processes running; 1 was stopped. 1 process outside" in result.output

    def test_a_process_that_no_longer_belongs_after_pinning_is_not_signalled(
        self, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The re-check after pinning: a process listed as the command's but no
        # longer its own once pinned (its number was handed on before the
        # pidfd was opened) is not signalled.
        stranger = subprocess.Popen(["sleep", "300"], start_new_session=True)
        started.append(stranger.pid)
        command = shell_commands._Command(os.getpid() + 1, "0" * 32, since=None)
        monkeypatch.setattr(command, "owns", lambda pid: None)
        monkeypatch.setattr(
            shell_commands, "pidfd_send_signal",
            lambda handle, sig: pytest.fail("signalled a process that is not the command's"),
        )
        try:
            assert command.signal_outside({stranger.pid}, signal.SIGKILL) == set()
            time.sleep(0.2)
            assert _alive(stranger.pid)
        finally:
            monkeypatch.undo()
            stranger.kill()
            stranger.wait()

    def test_a_number_reused_after_pinning_is_never_signalled(
        self, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulated at the check/signal boundary: the pidfd was opened for
        # the process that held the number, which then ended; the number now
        # names another process, which even passes the ownership check. The
        # signal goes to the ended process, so the other one is untouched.
        gone = subprocess.Popen(["true"])
        stale = os.pidfd_open(gone.pid)
        gone.wait()
        victim = subprocess.Popen(["sleep", "300"], start_new_session=True)
        started.append(victim.pid)
        command = shell_commands._Command(os.getpid() + 1, "0" * 32, since=None)
        fields = ("S", victim.pid, victim.pid, 0)  # outside the command's group
        monkeypatch.setattr(command, "owns", lambda pid: fields)
        monkeypatch.setattr(shell_commands.os, "pidfd_open", lambda pid: os.dup(stale))
        monkeypatch.setattr(
            shell_commands.os, "kill",
            lambda pid, sig: pytest.fail(f"signalled {pid} by number"),
        )
        try:
            refused = command.signal_outside({victim.pid}, signal.SIGKILL)
            time.sleep(0.2)
            assert refused == set()
            assert _alive(victim.pid)
        finally:
            monkeypatch.undo()
            os.close(stale)
            victim.kill()
            victim.wait()

    def test_the_shell_is_not_collected_until_the_stop_has_finished(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The shell exits at once, a background process holds the output
        # open, and the time limit comes before the grace for held output.
        # While the stop runs, the shell is an uncollected zombie, so its
        # number (the session's and the group's) cannot be handed to anyone
        # else.
        monkeypatch.setattr(shell_commands, "_PIPE_GRACE_SECONDS", 30.0)
        real_stop = shell_commands.stop_command_processes
        seen: list[tuple[str, str]] = []

        def watched(process, marker, **kwargs):
            stat = Path(f"/proc/{process.pid}/stat").read_bytes()
            state = stat[stat.rindex(b")") + 2 :].split()[0].decode()
            seen.append((shell_commands._shell_state(process), state))
            return real_stop(process, marker, **kwargs)

        monkeypatch.setattr(shell_commands, "stop_command_processes", watched)
        result = _shell(tmp_path).execute("sleep 300 & echo $! > bg.pid", timeout=1)

        assert result.exit_code == 124
        assert seen == [(shell_commands._EXITED, "Z")]
        assert not _alive(_pid(tmp_path, "bg.pid"))

    def test_a_process_holding_the_output_does_not_hold_the_agent(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        # Upstream waits for the output to close, so this held the agent for
        # the whole time limit and then left the process running.
        shell = _shell(tmp_path, timeout=40)

        began = time.monotonic()
        result = shell.execute("sleep 300 & echo $! > bg.pid; echo done")
        took = time.monotonic() - began

        assert took < 20
        assert result.exit_code == 0
        assert result.output.startswith("done\n")
        assert "left 1 process running" in result.output
        assert not _alive(_pid(tmp_path, "bg.pid"))

    def test_a_timeout_stops_the_command_and_everything_it_started(
        self, tmp_path: Path, started: list[int], caplog: pytest.LogCaptureFixture
    ) -> None:
        shell = _shell(tmp_path)

        began = time.monotonic()
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = shell.execute(
                "sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
                + _WAIT_FOR.format(name="bg.pid")
                + "; echo $$ > fg.pid; sleep 300",
                timeout=2,
            )
        took = time.monotonic() - began

        assert took < 20
        assert result.exit_code == 124
        assert result.output.startswith(
            "Error: Command timed out after 2 seconds (custom timeout). The "
            "command may be stuck or require more time.\n\nIt was stopped "
            "along with everything it started ("
        )
        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert not _alive(_pid(tmp_path, "fg.pid"))
        assert "ran past its time limit" in caplog.text

    def test_processes_the_command_did_not_start_are_left_alone(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        # One stranger started before the command, with no marker; one
        # started while the command runs, carrying another command's marker.
        before = subprocess.Popen(
            ["sleep", "300"], start_new_session=True, env=dict(_ENV)
        )
        started.append(before.pid)
        strangers = [before]
        stranger_env = {**_ENV, COMMAND_MARKER_NAME: "f" * 32}

        def start_during() -> None:
            during = subprocess.Popen(
                ["sleep", "300"], start_new_session=True, env=stranger_env
            )
            started.append(during.pid)
            strangers.append(during)

        timer = threading.Timer(0.3, start_during)
        timer.start()
        try:
            result = _shell(tmp_path).execute(
                "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; sleep 1.5"
            )
            timer.join()

            assert len(strangers) == 2
            assert "left 1 process running" in result.output
            assert not _alive(_pid(tmp_path, "bg.pid"))
            assert all(_alive(process.pid) for process in strangers)
        finally:
            timer.cancel()
            timer.join()
            for process in strangers:
                process.kill()
                process.wait()


@linux_only
class TestCommandsGoFirstWhenMemoryRunsOut:
    def test_the_command_and_what_it_starts_are_first_in_line(
        self, tmp_path: Path
    ) -> None:
        own = Path("/proc/self/oom_score_adj").read_text().strip()
        backend = build_autobuild_backend(_worktree(tmp_path))

        shell = backend.execute("cat /proc/$$/oom_score_adj")
        child = backend.execute("cat /proc/self/oom_score_adj")
        grandchild = backend.execute("sh -c 'sh -c \"cat /proc/self/oom_score_adj\"'")

        assert shell.output == "1000\n"
        assert child.output == "1000\n"
        assert grandchild.output == "1000\n"
        # GuardKit's own process is unchanged.
        assert Path("/proc/self/oom_score_adj").read_text().strip() == own

    def test_the_command_still_runs_as_the_session_leader(
        self, tmp_path: Path
    ) -> None:
        # ``exec`` keeps the shell's process: it leads the command's session.
        result = _shell(tmp_path).execute(
            "awk '{print $6}' /proc/$$/stat; echo $$"
        )
        session, shell = result.output.split()
        assert session == shell

    def test_arguments_reach_the_command_as_written(self, tmp_path: Path) -> None:
        command = "set -- a 'b c'; printf '[%s]' \"$0\" \"$#\" \"$@\" '$1'"
        ours = _shell(tmp_path).execute(command)
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV)
        ).execute(command)

        assert ours == theirs
        assert ours.output == "[/bin/sh][2][a][b c][$1]"


class TestCleanupCapability:
    """Where a command's leftovers cannot all be stopped safely (no pidfd, no
    ``os.waitid``, no ``/proc``), a factory launch's self-test fails. Since
    26 October 2026 (step 2, census GKF-026, 081, 133) that is logged once and
    the commands run with the reduced clean-up, as a person's own run does."""

    _MISSING = (
        "pidfd_open is refused here by the kernel or a security filter "
        "(Operation not permitted)"
    )

    _ADVICE = (
        "Run the factory where /proc can be read and waitid, pidfd_open and "
        "pidfd_send_signal are allowed (Linux 5.3 or later)."
    )

    @pytest.fixture
    def missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A factory launch: the self-test fails; a person's run: the check
        # finds the same thing missing.
        monkeypatch.setattr(shell_commands, "_self_test", lambda: self._MISSING)
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [self._MISSING])
        monkeypatch.setattr(shell_commands, "_WARNED", [])

    @linux_only
    def test_this_system_has_everything_needed(self) -> None:
        assert shell_commands._missing_capability() is None

    @linux_only
    def test_the_self_test_passes_here_and_leaves_nothing(self) -> None:
        before_fds = len(os.listdir("/proc/self/fd"))
        before = _self_test_processes()  # earlier tests' refused ones
        assert shell_commands._self_test() is None
        assert len(os.listdir("/proc/self/fd")) == before_fds
        assert _self_test_processes() - before == set()

    def test_a_refused_pidfd_is_named(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refused(_pid: int) -> int:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        if not Path("/proc/self/stat").exists():
            pytest.skip("needs /proc")
        monkeypatch.setattr(shell_commands.os, "pidfd_open", refused)
        assert shell_commands._missing_capability() == self._MISSING

    @linux_only
    def test_a_refused_signal_through_a_pidfd_is_named_and_a_factory_command_still_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # A filter may allow opening a pidfd and refuse signalling through it.
        def refused(_handle: int, _sig: int) -> None:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(shell_commands.signal, "pidfd_send_signal", refused)
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [])
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        expected = (
            "pidfd_send_signal is refused here by the kernel or a security filter "
            "(Operation not permitted)"
        )

        assert shell_commands._missing_capability() == expected
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")
        assert result.exit_code == 0
        assert (tmp_path / "ran").exists()
        assert "reduced clean-up" in caplog.text

    @linux_only
    def test_a_python_without_the_pidfd_wrappers_uses_the_system_calls(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Some standalone Python builds (uv-managed ones) lack os.pidfd_open
        # and signal.pidfd_send_signal although the kernel has the calls.
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")
        monkeypatch.delattr(os, "pidfd_open")
        monkeypatch.delattr(signal, "pidfd_send_signal")
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [])
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")

        assert shell_commands._missing_capability() is None
        result = _shell(tmp_path).execute(
            "setsid sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="bg.pid")
        )
        monkeypatch.undo()

        assert "left 1 process running; it was stopped" in result.output
        assert not _alive(_pid(tmp_path, "bg.pid"))

    @linux_only
    def test_without_wrappers_or_system_calls_the_python_build_is_named(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def refused(_number: int, *_args: object) -> int:
            raise OSError(errno.EPERM, "Operation not permitted")

        monkeypatch.delattr(os, "pidfd_open")
        monkeypatch.setattr(shell_commands, "_raw_syscall", refused)
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [])
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        expected = (
            "this Python build lacks pidfd_open, and the system call itself is "
            "refused by the kernel or a security filter (Operation not permitted)"
        )

        assert shell_commands._missing_capability() == expected
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")
        assert result.exit_code == 0
        assert (tmp_path / "ran").exists()
        assert "reduced clean-up" in caplog.text

    def test_without_wrappers_off_linux_the_platform_is_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if not Path("/proc/self/stat").exists():
            pytest.skip("needs /proc")
        monkeypatch.delattr(os, "pidfd_open", raising=False)
        monkeypatch.setattr(shell_commands.sys, "platform", "darwin")
        assert shell_commands._missing_capability() == (
            "this Python build lacks pidfd_open, and this system is not Linux"
        )

    @linux_only
    @pytest.mark.parametrize("send", ["works", "refused"])
    def test_the_probe_closes_its_pidfd(
        self, monkeypatch: pytest.MonkeyPatch, send: str
    ) -> None:
        if send == "refused":
            def refused(_handle: int, _sig: int) -> None:
                raise PermissionError(errno.EPERM, "Operation not permitted")

            monkeypatch.setattr(signal, "pidfd_send_signal", refused)
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(20):
            shell_commands._missing_capability()
        assert len(os.listdir("/proc/self/fd")) == before

    @linux_only
    def test_a_refused_waitid_is_named_and_a_factory_launch_still_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # os.waitid exists but a filter refuses it: the probe makes the call.
        def refused(*_args: object) -> None:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(shell_commands.os, "waitid", refused)
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [])
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setattr(shell_commands, "_WARNED", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        expected = (
            "waitid is refused here by the kernel or a security filter "
            "(Operation not permitted)"
        )

        assert shell_commands._missing_capability() == expected
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")
        build_autobuild_backend(_worktree(tmp_path / "w"))
        monkeypatch.undo()
        assert result.exit_code == 0
        assert (tmp_path / "ran").exists()
        assert expected in caplog.text and "reduced clean-up" in caplog.text

    @linux_only
    def test_a_refused_waitid_on_a_persons_run_falls_back_and_never_hangs(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refused(*_args: object) -> None:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(shell_commands.os, "waitid", refused)
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [])
        monkeypatch.setattr(shell_commands, "_WARNED", [])
        monkeypatch.delenv(shell_commands.FACTORY_LAUNCH_ENV, raising=False)
        assert _shell(tmp_path).execute("echo ok").output == "ok\n"
        result = _shell(tmp_path).execute("echo $$ > fg.pid; exec sleep 300", timeout=1)
        monkeypatch.undo()
        assert result.exit_code == 124
        assert not _alive(_pid(tmp_path, "fg.pid"))

    def test_collecting_the_shell_never_waits_without_bound(
        self, started: list[int], monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Even where the shell cannot be ended (its group refuses the
        # signal), collecting it gives up after a bounded wait and says so.
        shell = subprocess.Popen(["sleep", "300"], start_new_session=True)
        started.append(shell.pid)
        monkeypatch.setattr(shell_commands, "_KILL_WAIT_SECONDS", 0.2)
        monkeypatch.setattr(shell_commands, "_DRAIN_SECONDS", 0.2)
        monkeypatch.setattr(shell_commands.os, "killpg", lambda _pgid, _sig: None)
        began = time.monotonic()
        try:
            with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
                shell_commands._collect(shell)
            assert time.monotonic() - began < 5
            assert "could not be collected" in caplog.text
        finally:
            monkeypatch.undo()
            shell.kill()
            shell.wait()

    @linux_only
    def test_waitid_refused_while_a_command_runs_never_hangs(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The probe passes (this process is no child of its own), then
        # watching the shell is refused once the command is under way: the
        # command is ended and collected within bounds, and the answer says
        # why (execute never raises).
        real_waitid = os.waitid
        own = os.getpid()

        def flaky(idtype: int, ident: int, options: int):
            if ident == own or not (tmp_path / "fg.pid").exists():
                return real_waitid(idtype, ident, options)
            raise PermissionError(errno.EPERM, "Operation not permitted")

        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")
        monkeypatch.setattr(shell_commands.os, "waitid", flaky)
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [None])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        began = time.monotonic()
        # A process in a session of its own, one in another group of the same
        # session (timeout), then the shell itself.
        result = _shell(tmp_path).execute(
            "setsid sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
            "timeout 120 sh -c 'echo $$ > inner.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="bg.pid") + "; " + _WAIT_FOR.format(name="inner.pid")
            + "; echo $$ > fg.pid; exec sleep 300"
        )
        monkeypatch.undo()

        assert time.monotonic() - began < 30
        assert result.exit_code == 1
        assert result.output.startswith(
            "Error executing command (CleanupUnavailableError): "
        )
        assert "A shell command was ended because waitid is refused here" in result.output
        assert not _alive(_pid(tmp_path, "fg.pid"))
        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert not _alive(_pid(tmp_path, "inner.pid"))

    def test_a_factory_launch_runs_its_commands_with_one_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        missing: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            first = _shell(tmp_path).execute("touch ran; echo ok")
            second = _shell(tmp_path).execute("echo ok")

        assert first.output == second.output == "ok\n"
        assert (tmp_path / "ran").exists()
        warnings = [r for r in caplog.records if "reduced clean-up" in r.getMessage()]
        assert len(warnings) == 1
        assert warnings[0].getMessage() == (
            f"Shell commands run with the reduced clean-up: {self._MISSING}, so what "
            f"a command leaves running may not all be stopped. {self._ADVICE}"
        )

    def test_a_factory_launch_builds_its_shell(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: None
    ) -> None:
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "1")
        backend = build_autobuild_backend(_worktree(tmp_path))
        assert backend.execute("echo ok").output == "ok\n"

    def test_a_persons_own_run_goes_on_with_a_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        missing: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv(shell_commands.FACTORY_LAUNCH_ENV, raising=False)
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            first = _shell(tmp_path).execute("touch ran; echo ok")
            second = _shell(tmp_path).execute("echo ok")

        assert first.output == second.output == "ok\n"
        assert (tmp_path / "ran").exists()
        warnings = [r for r in caplog.records if "may be left running" in r.getMessage()]
        assert len(warnings) == 1

    def test_an_empty_factory_signal_is_not_a_factory_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "")
        assert not shell_commands.is_factory_launch()
        monkeypatch.delenv(shell_commands.FACTORY_LAUNCH_ENV)
        assert not shell_commands.is_factory_launch()

    @pytest.mark.parametrize("value", ["   ", "0", "false"])
    def test_any_other_factory_signal_is_a_factory_launch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: None, value: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Whitespace or "0" still counts as a factory launch: the self-test runs.
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, value)
        assert shell_commands.is_factory_launch()
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")
        assert result.exit_code == 0
        assert "reduced clean-up" in caplog.text


def _self_test_processes() -> set[int]:
    marker_name = COMMAND_MARKER_NAME.encode()
    found = set()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            environ = Path(f"/proc/{name}/environ").read_bytes()
            cmdline = Path(f"/proc/{name}/cmdline").read_bytes()
        except OSError:
            continue
        if marker_name in environ and b"os.setsid()" in cmdline and _alive(int(name)):
            found.add(int(name))
    return found


class _DeniedProc(type(Path("/proc"))):  # type: ignore[misc]
    """``/proc`` whose listing is refused while ``when()`` is true, and whose
    environment records are refused for the pids ``deny_environ`` names."""

    when = staticmethod(lambda: True)
    deny_environ = staticmethod(lambda pid: False)

    def iterdir(self):  # type: ignore[override]
        if str(self) == "/proc" and _DeniedProc.when():
            raise PermissionError(errno.EACCES, "Permission denied")
        return super().iterdir()

    def read_bytes(self):  # type: ignore[override]
        if (
            self.name == "environ"
            and self.parent.name.isdigit()
            and _DeniedProc.deny_environ(int(self.parent.name))
        ):
            raise PermissionError(errno.EACCES, "Permission denied")
        return super().read_bytes()


@linux_only
class TestTheRuleOnAFactoryLaunch:
    """Codex review, 20 October 2026: the probe proved less than the clean-up
    needs, so a factory launch runs an end-to-end self-test first. Since
    27 October 2026 (step 2 review) a failure of the clean-up later, after a
    passed self-test, never refuses or ends the command: it is logged or
    reported in the command's output, and the command runs, as on a
    person's own run."""

    @staticmethod
    def _deny_proc_listing(monkeypatch: pytest.MonkeyPatch, when=lambda: True) -> None:
        monkeypatch.setattr(_DeniedProc, "when", staticmethod(when))
        monkeypatch.setattr(shell_commands, "_PROC", _DeniedProc("/proc"))

    @staticmethod
    def _deny_environ(monkeypatch: pytest.MonkeyPatch, which) -> None:
        monkeypatch.setattr(_DeniedProc, "when", staticmethod(lambda: False))
        monkeypatch.setattr(_DeniedProc, "deny_environ", staticmethod(which))
        monkeypatch.setattr(shell_commands, "_PROC", _DeniedProc("/proc"))

    def test_a_denied_proc_listing_fails_the_self_test(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        self._deny_proc_listing(monkeypatch)
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")
        build_autobuild_backend(_worktree(tmp_path / "w"))

        assert result.exit_code == 0
        assert (tmp_path / "ran").exists()
        assert "Shell commands run with the reduced clean-up" in caplog.text
        assert "/proc could not be listed (Permission denied)" in caplog.text

    def test_a_listing_denied_mid_run_is_said_and_a_factory_command_runs(
        self,
        tmp_path: Path,
        started: list[int],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [None])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        self._deny_proc_listing(monkeypatch, when=lambda: (tmp_path / "fg.pid").exists())
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute(
                "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; echo $$ > fg.pid; echo ok"
            )
        monkeypatch.undo()

        assert result.exit_code == 0
        assert result.output == "ok\n"
        assert "/proc could not be listed (Permission denied)" in caplog.text

    def test_a_listing_denied_on_a_persons_run_is_said(
        self,
        tmp_path: Path,
        started: list[int],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv(shell_commands.FACTORY_LAUNCH_ENV, raising=False)
        monkeypatch.setattr(shell_commands, "_CAPABILITY", [None])
        self._deny_proc_listing(monkeypatch)
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute(
                "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; echo ok"
            )
        assert result.output == "ok\n"
        assert "/proc could not be listed" in caplog.text

    def test_a_cached_success_then_a_refused_waitid_runs_the_command_reduced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # The fresh waitid check before every command now chooses the reduced
        # clean-up, logged once; the command runs.
        def refused(*_args: object) -> None:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [None])
        monkeypatch.setattr(shell_commands, "_WARNED", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        monkeypatch.setattr(shell_commands.os, "waitid", refused)
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran; echo ok")
        monkeypatch.undo()

        assert result.exit_code == 0
        assert result.output == "ok\n"
        assert (tmp_path / "ran").exists()
        assert (
            "Here waitid is refused here by the kernel or a security filter "
            "(Operation not permitted), so a process a shell command moves out of "
            "its process group may be left running"
        ) in caplog.text

    def test_a_denied_environment_read_fails_the_self_test(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        own = os.getpid()
        self._deny_environ(monkeypatch, lambda pid: pid != own)
        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("touch ran")

        assert result.exit_code == 0
        assert (tmp_path / "ran").exists()
        assert (
            "the clean-up self-test's process environment could not be read "
            "(Permission denied)"
        ) in caplog.text

    def test_a_denied_environment_read_mid_run_leaves_that_process_out(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")

        def escapee(pid: int) -> bool:
            file = tmp_path / "bg.pid"
            return file.exists() and file.read_text().strip() == str(pid)

        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [None])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        self._deny_environ(monkeypatch, escapee)
        result = _shell(tmp_path).execute(
            "setsid sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="bg.pid") + "; echo ok"
        )
        monkeypatch.undo()

        # The command runs and answers as usual; the process whose environment
        # could not be read is not found, so it is not stopped (the fixture
        # ends it).
        assert result.exit_code == 0
        assert result.output == "ok\n"

    def test_the_self_test_checks_its_own_process_not_only_the_scan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A scan that misses marked processes would leave the self-test's
        # process running; the pinned pidfd shows it, so the test fails.
        monkeypatch.setattr(shell_commands, "_carries_marker", lambda _pid, _entry: False)
        assert shell_commands._self_test() == (
            "the clean-up self-test's left-behind process was still running after the stop"
        )

    def test_the_emergency_kill_checks_ownership_after_pinning(
        self, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A number listed as the self-test's but handed on before it was
        # pinned: the process it names now does not carry the marker, so it
        # is not signalled.
        stranger = subprocess.Popen(["sleep", "300"], start_new_session=True)
        started.append(stranger.pid)
        monkeypatch.setattr(
            shell_commands, "pidfd_send_signal",
            lambda handle, sig: pytest.fail("signalled a process that is not the self-test's"),
        )
        try:
            shell_commands._end_self_test_leftovers(
                {stranger.pid}, f"\0{COMMAND_MARKER_NAME}={'f' * 32}\0".encode(), None
            )
            time.sleep(0.2)
            assert _alive(stranger.pid)
        finally:
            monkeypatch.undo()
            stranger.kill()
            stranger.wait()

    def test_a_refused_pidfd_mid_run_is_reported_and_a_factory_command_runs(
        self, tmp_path: Path, started: list[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if shutil.which("setsid", path=_ENV["PATH"]) is None:
            pytest.skip("no setsid program")

        def refused(_handle: int, _sig: int) -> None:
            raise PermissionError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(shell_commands, "_SELF_TEST_OUTCOME", [None])
        monkeypatch.setenv(shell_commands.FACTORY_LAUNCH_ENV, "build-x")
        monkeypatch.setattr(shell_commands.signal, "pidfd_send_signal", refused)
        result = _shell(tmp_path).execute(
            "setsid sh -c 'echo $$ > bg.pid; exec sleep 300' >/dev/null 2>&1 & "
            + _WAIT_FOR.format(name="bg.pid") + "; echo ok"
        )
        monkeypatch.undo()

        assert result.exit_code == 0
        assert result.output.startswith("ok\n")
        assert "could not be stopped safely on this system" in result.output


class TestWithoutWaitid:
    """macOS before Python 3.13 has no ``os.waitid``: the command still runs,
    as upstream, and a timeout still stops the command's own process group."""

    @pytest.fixture(autouse=True)
    def _no_waitid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delattr(os, "waitid")

    @pytest.mark.parametrize(
        "command",
        ["echo hi; echo err >&2; exit 3", "true", "printf 'bad \\377'"],
    )
    def test_the_same_result_as_upstream(self, tmp_path: Path, command: str) -> None:
        ours = _shell(tmp_path).execute(command)
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV)
        ).execute(command)
        assert ours == theirs

    @linux_only
    def test_a_timeout_stops_the_process_group(
        self, tmp_path: Path, started: list[int]
    ) -> None:
        result = _shell(tmp_path).execute(
            "sleep 300 >/dev/null 2>&1 & echo $! > bg.pid; echo $$ > fg.pid; exec sleep 300",
            timeout=1,
        )
        assert result.exit_code == 124
        assert result.output.endswith(
            "It was stopped along with everything it started (how many is not known)."
        )
        assert not _alive(_pid(tmp_path, "bg.pid"))
        assert not _alive(_pid(tmp_path, "fg.pid"))


# ---------------------------------------------------------------------------
# Unchanged: DeepAgents' own output
# ---------------------------------------------------------------------------


class TestUpstreamOutputIsKept:
    @pytest.mark.parametrize(
        "command",
        [
            "echo hi; echo err >&2; exit 3",
            "true",
            "printf 'a\\nb'",
            "echo one; echo two >&2; echo three >&2",
            "exit 7",
        ],
    )
    def test_the_same_output_and_exit_code(
        self, tmp_path: Path, command: str
    ) -> None:
        ours = _shell(tmp_path).execute(command)
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV)
        ).execute(command)

        assert ours == theirs

    @pytest.mark.parametrize(
        "command",
        [
            "printf 'ok \\377 bad'",
            "printf 'bad \\377' >&2",
            "printf 'out \\377'; printf 'err \\376' >&2; exit 2",
            "printf 'fine'; printf '\\377' >&2",
        ],
        ids=["stdout", "stderr", "both", "stderr-only-bad"],
    )
    def test_output_that_cannot_be_decoded_is_answered_as_upstream(
        self, tmp_path: Path, command: str
    ) -> None:
        ours = _shell(tmp_path).execute(command)
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV)
        ).execute(command)

        assert ours == theirs
        assert ours.exit_code == 1
        assert ours.output.startswith("Error executing command (UnicodeDecodeError): ")

    def test_truncation_is_the_same(self, tmp_path: Path) -> None:
        command = "head -c 5000 /dev/zero | tr '\\0' x"
        ours = CommandSessionShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV),
            max_output_bytes=100,
        ).execute(command)
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV),
            max_output_bytes=100,
        ).execute(command)

        assert ours == theirs
        assert ours.truncated

    def test_the_default_timeout_message_is_the_same(self, tmp_path: Path) -> None:
        ours = _shell(tmp_path, timeout=1).execute("exec sleep 30")
        theirs = LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False, env=dict(_ENV), timeout=1
        ).execute("exec sleep 30")

        assert theirs.exit_code == ours.exit_code == 124
        assert ours.output.startswith(theirs.output + "\n\nIt was stopped")

    def test_a_quick_command_says_nothing_extra(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger=shell_commands.__name__):
            result = _shell(tmp_path).execute("echo hi")

        assert result.output == "hi\n"
        assert caplog.records == []

    def test_an_empty_command_is_refused_as_upstream(self, tmp_path: Path) -> None:
        assert _shell(tmp_path).execute("") == LocalShellBackend(
            root_dir=tmp_path, virtual_mode=False
        ).execute("")
