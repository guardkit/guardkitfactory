"""Shell commands run by the builder, checker and specialists, and what they leave.

19 October 2026 (a factory build). The build's sandbox ran out of memory while
the builder was adding a test-coverage script: at the kill it held dozens of
test-runner processes, and the kernel stopped GuardKit, the biggest single
process, so the whole build was lost.

DeepAgents' ``LocalShellBackend.execute`` runs each command with
``subprocess.run(..., shell=True, start_new_session=True)``. The command gets
its own session, but nothing ever looks at that session again:

* when the command returns, any process it started in the background (a
  watcher, a server, a test run left behind with ``&``) keeps running, and the
  next command adds more;
* when the command times out, ``subprocess.run`` kills only the shell. Every
  process below it keeps running.

:class:`CommandSessionShellBackend` keeps DeepAgents' backend and its output
format, and changes only that. Each command still runs in a new session. When
it returns or times out, every process still in that session is stopped
(``SIGTERM``, a short grace, then ``SIGKILL``), and so is any process that
carries the command's own marker (:data:`COMMAND_MARKER_NAME` in its
environment, a fresh value per command), which catches a process that moved
itself into a session of its own. A process is never stopped for any other
reason: GuardKit, the runner, other roles' commands and anything else on the
machine are left alone. When something is stopped, the log says so in plain
words, naming the command and how many processes, and the command's own
output says so too, so the agent knows that a server or watcher must be
started and used within one command.

Two rules keep the stop safe (Codex review, 19 October 2026), the same as
GuardKit's runner for project commands (``guardkit.orchestrator.process_group``):

* THE SHELL IS NOT COLLECTED UNTIL THE STOP HAS FINISHED. The output is read
  here rather than by ``communicate()`` (which collects the shell), and the
  shell's exit is read without collecting it. While the shell is uncollected
  its number, which is also the number of its process group and its session,
  cannot be handed to any other process.
* NO PROCESS IS SIGNALLED BY NUMBER ALONE. The command's own process group is
  signalled as a group (``killpg``, one step, by the pinned number). Any other
  process of the command (one that moved into a group or session of its own)
  is signalled only through a pidfd opened first and then checked. Where a
  pidfd cannot be had, such a process is not signalled at all, and the log
  and the output say plainly that it could not be stopped safely.

Finding the session's processes reads ``/proc`` (Linux, where the factory's
sandboxes run). Elsewhere only the command's own process group is signalled,
and nothing is counted. Where the shell's exit cannot be read without
collecting it (``os.waitid`` is missing: macOS before Python 3.13), the command
is waited for as upstream does, and only a timeout stops its process group.

Nothing here names a language, tool or test runner.
"""

from __future__ import annotations

import errno
import logging
import os
import selectors
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents.backends.local_shell import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse

logger = logging.getLogger(__name__)

__all__ = [
    "COMMAND_MARKER_NAME",
    "CleanupUnavailableError",
    "cleanup_capability_missing",
    "is_factory_launch",
    "refusal_for_factory_launch",
    "CommandSessionShellBackend",
    "stop_command_processes",
]

#: Set in each command's environment to a value used by that command alone.
#: The reserved ``GUARDKIT_`` prefix means no project can declare it.
COMMAND_MARKER_NAME = "GUARDKIT_SHELL_COMMAND"

#: How long the processes get to stop after ``SIGTERM``.
_GRACE_SECONDS = 2.0
#: How long ``SIGKILL`` is repeated until nothing of the command is left.
_KILL_WAIT_SECONDS = 10.0
#: How often the stop looks again.
_LOOK_SECONDS = 0.05
#: How long to wait for the output pipes once the command's processes are stopped.
_DRAIN_SECONDS = 5.0
#: How long one wait for output lasts before the shell is looked at again.
_POLL_SECONDS = 0.5
#: How long the output pipes may stay open after the shell has finished.
_PIPE_GRACE_SECONDS = 1.0
#: How much of a command the log line quotes.
_QUOTED_COMMAND_CHARS = 200

_PROC = Path("/proc")

#: 19 October 2026 (a factory build). When memory runs out, the kernel stops
#: the process it scores highest, mostly by size. Dozens of small test
#: processes lost to GuardKit, the biggest single process, and the build was
#: lost with it. Each command's shell raises its own ``oom_score_adj`` to the
#: maximum before running the command (raising needs no privilege, and every
#: process the command starts inherits it), so the command's processes are
#: stopped first and GuardKit carries on: the command fails and the agent
#: sees it. Where ``/proc`` is missing or refuses, nothing changes. Then
#: ``exec`` runs the command exactly as ``shell=True`` would, in the same
#: process, so the session is still the shell's.
_FIRST_TO_GO = (
    '{ echo 1000 > /proc/self/oom_score_adj; } 2>/dev/null; exec /bin/sh -c "$1"'
)


def _now_ticks() -> int | None:
    """Clock ticks since boot (the unit of ``/proc/<pid>/stat`` start times)."""
    try:
        uptime = float((_PROC / "uptime").read_text().split()[0])
        return int(uptime * os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError):
        return None


def _stat(pid: int) -> tuple[str, int, int, int] | None:
    """``(state, group, session, start time)`` for ``pid``, or ``None`` if gone."""
    try:
        data = (_PROC / str(pid) / "stat").read_bytes()
    except OSError:
        return None
    # The program name (field 2) may hold spaces and brackets; the fields
    # after the last ")" start at field 3.
    try:
        rest = data[data.rindex(b")") + 2 :].split()
        return rest[0].decode(), int(rest[2]), int(rest[3]), int(rest[19])
    except (ValueError, IndexError):
        return None


def _carries_marker(pid: int, marker: bytes) -> bool:
    try:
        environ = (_PROC / str(pid) / "environ").read_bytes()
    except OSError:  # gone, or another user's process
        return False
    return marker in b"\0" + environ


#: Set when the factory launched this GuardKit (GuardKit's
#: ``FACTORY_LAUNCH_ENV``).
FACTORY_LAUNCH_ENV = "GUARDKIT_FACTORY_LAUNCH"


def is_factory_launch() -> bool:
    """Whether the factory launched this process.

    GuardKit's one predicate (``m0_fence.is_factory_launch``) when it has
    it, else the same rule: any value at all is a factory launch,
    whitespace and ``0``/``false`` included; only unset or exactly empty is
    a person's own run. A value nobody can read as "on" must never switch
    the refusal off.
    """
    try:
        from guardkit.orchestrator.m0_fence import (  # type: ignore[attr-defined]
            is_factory_launch as guardkits,
        )
    except ImportError:
        value = os.environ.get(FACTORY_LAUNCH_ENV)
        return value is not None and value != ""
    return bool(guardkits())


def _missing_capability() -> str | None:
    """What this system lacks to stop everything a command leaves, in plain
    words, or ``None`` when nothing is missing.

    Stopping a process that left the command's process group needs ``/proc``
    (to find it), ``os.waitid`` (to keep the shell uncollected meanwhile) and a
    pidfd that can be opened and signalled through (to signal that one
    process and no other). Both are tried on this process itself.
    """
    if not (_PROC / "self" / "stat").exists():
        return "/proc (to find a command's processes)"
    if not _can_wait_without_collecting():
        return "os.waitid (Python 3.13 or later on macOS)"
    try:
        handle = os.pidfd_open(os.getpid())
    except AttributeError:
        return "pidfd support in this Python"
    except OSError as exc:
        return f"pidfd_open (refused here: {exc.strerror or exc})"
    try:
        # Signal 0 checks that signalling through a pidfd is allowed too (a
        # filter may allow opening one and refuse sending).
        signal.pidfd_send_signal(handle, 0)
    except OSError as exc:
        return f"pidfd_send_signal (refused here: {exc.strerror or exc})"
    finally:
        os.close(handle)
    return None


_CAPABILITY: list[str | None] = []


def cleanup_capability_missing() -> str | None:
    """:func:`_missing_capability`, worked out once per process."""
    if not _CAPABILITY:
        _CAPABILITY.append(_missing_capability())
    return _CAPABILITY[0]


class CleanupUnavailableError(OSError):
    """A factory build's shell cannot stop everything its commands leave."""


def refusal_for_factory_launch() -> str | None:
    """The plain sentence refusing a factory launch's commands, or ``None``.

    A factory build must leave nothing running (19 October 2026), so where
    a command's leftovers cannot all be stopped safely its commands are not
    run. On a person's own run the reduced clean-up goes on, with a warning.
    """
    missing = cleanup_capability_missing()
    if missing is None or not is_factory_launch():
        return None
    return (
        "The factory does not run commands here: this system lacks "
        f"{missing}, so what a command leaves running could not all be "
        "stopped safely. Run the factory on a current Linux kernel "
        "(5.3 or later) where pidfd_open is allowed."
    )


_WARNED: list[bool] = []


def _warn_reduced_cleanup_once(missing: str) -> None:
    if _WARNED:
        return
    _WARNED.append(True)
    logger.warning(
        "This system lacks %s, so a process a shell command moves out of its "
        "process group may be left running after the command.",
        missing,
    )


def _can_wait_without_collecting() -> bool:
    """Whether ``os.waitid`` exists. macOS has it only from Python 3.13."""
    try:
        os.waitid  # noqa: B018 - the attribute's presence is the question
    except AttributeError:
        return False
    return True


_RUNNING = "running"  # the shell has not exited
_EXITED = "exited"  # it has exited and is still uncollected
_COLLECTED = "collected"  # it has been collected; its number is not ours


def _shell_state(process: subprocess.Popen[Any]) -> str:
    """Whether the shell runs, has exited (uncollected) or was collected.

    Read with ``WNOWAIT``, so the shell is never collected here.
    """
    if process.returncode is not None:
        return _COLLECTED
    try:
        info = os.waitid(
            os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT
        )
    except ChildProcessError:
        return _COLLECTED
    return _RUNNING if info is None else _EXITED


class _Command:
    """The processes of one command whose shell (``leader``) is uncollected."""

    def __init__(self, leader: int, marker: str, since: int | None) -> None:
        self.leader = leader
        self.entry = f"\0{COMMAND_MARKER_NAME}={marker}\0".encode()
        self.since = since

    def owns(self, pid: int) -> tuple[str, int, int, int] | None:
        """``pid``'s stat fields when it is a live process of the command
        other than its shell; ``None`` otherwise.

        The group and session tests are sound because the shell, whose
        number both of them carry, is not collected while the stop runs.
        """
        if pid == os.getpid() or pid == self.leader:
            return None
        stat = _stat(pid)
        if stat is None or stat[0] in ("Z", "X"):
            return None
        _state, group, session, started = stat
        if group == self.leader or session == self.leader:
            return stat
        # A process the command started cannot be older than the command.
        if self.since is not None and started < self.since:
            return None
        return stat if _carries_marker(pid, self.entry) else None

    def processes(self) -> set[int]:
        """The live processes of the command, its shell apart: those in its
        session or process group, and those carrying its marker."""
        try:
            names = [entry.name for entry in _PROC.iterdir()]
        except OSError:
            return set()
        return {
            int(name)
            for name in names
            if name.isdigit() and self.owns(int(name)) is not None
        }

    def signal_group(self, sig: int) -> None:
        """Signal the command's own process group, in one step, by the number
        the uncollected shell pins."""
        try:
            os.killpg(self.leader, sig)
        except OSError:
            pass

    def signal_outside(self, pids: set[int], sig: int) -> set[int]:
        """Signal each process of the command outside its own group, through
        a pidfd opened first and then checked; return those that could not be
        pinned or whose signal was refused (and so were not signalled).

        A pidfd names one process, not a number: if the process ends and its
        number is handed to another one after the pidfd is opened, the
        signal finds the ended process and goes nowhere. No process is ever
        signalled by number alone.
        """
        refused: set[int] = set()
        for pid in pids:
            try:
                handle = os.pidfd_open(pid)
            except AttributeError:  # pragma: no cover - no pidfds in this Python
                refused.add(pid)
                continue
            except OSError as exc:
                if exc.errno != errno.ESRCH:  # ESRCH: it has gone
                    refused.add(pid)
                continue
            try:
                stat = self.owns(pid)
                if stat is not None and stat[1] != self.leader:
                    signal.pidfd_send_signal(handle, sig)
            except OSError as exc:
                # Only ESRCH means it ended after it was pinned; anything else
                # (a refusal) means it was not signalled.
                if exc.errno != errno.ESRCH:
                    refused.add(pid)
            finally:
                os.close(handle)
        return refused

    def outside_group(self, pids: set[int]) -> set[int]:
        found = set()
        for pid in pids:
            stat = self.owns(pid)
            if stat is not None and stat[1] != self.leader:
                found.add(pid)
        return found


@dataclass(frozen=True)
class Stopped:
    """What the stop did. ``stopped`` is ``None`` when nothing could be
    counted (no ``/proc``); ``not_safe`` processes outside the command's
    group were left running because no pidfd could be had or signalled
    through for them;
    ``still_running`` were sent ``SIGKILL`` but not seen to end in time."""

    stopped: int | None = 0
    not_safe: int = 0
    still_running: int = 0

    @property
    def anything(self) -> bool:
        return self.stopped is None or bool(
            self.stopped or self.not_safe or self.still_running
        )


def stop_command_processes(
    process: subprocess.Popen[Any],
    marker: str,
    *,
    since: int | None = None,
    include_shell: bool = False,
) -> Stopped:
    """Stop every process of one command, its shell still uncollected.

    ``process`` is the command's shell (it leads the command's session and
    process group), ``marker`` the command's own :data:`COMMAND_MARKER_NAME`
    value and ``since`` the clock-tick time just before it started. With
    ``include_shell`` (a timeout) the shell itself is stopped too.
    ``SIGTERM`` first and ``_GRACE_SECONDS`` to stop; then ``SIGKILL``,
    looking again each time for anything still there or started meanwhile,
    until nothing is left or ``_KILL_WAIT_SECONDS`` have passed. A collected
    shell's number may belong to someone else, so then nothing is signalled.
    """
    if _shell_state(process) == _COLLECTED:
        logger.warning(
            "A shell command's processes were not stopped: its shell had "
            "already been collected, so its number may belong to another process."
        )
        return Stopped()
    command = _Command(process.pid, marker, since)
    if not (_PROC / "self" / "stat").exists():
        if include_shell:
            command.signal_group(signal.SIGTERM)
            time.sleep(_LOOK_SECONDS)
        command.signal_group(signal.SIGKILL)
        return Stopped(stopped=None if include_shell else 0)
    seen = command.processes()
    if not seen and not include_shell:
        return Stopped()

    def finished(left: set[int]) -> bool:
        return not left and (not include_shell or _shell_state(process) != _RUNNING)

    refused: set[int] = set()
    command.signal_group(signal.SIGTERM)
    refused |= command.signal_outside(command.outside_group(seen), signal.SIGTERM)
    deadline = time.monotonic() + _GRACE_SECONDS
    while time.monotonic() < deadline:
        time.sleep(_LOOK_SECONDS)
        left = command.processes()
        seen |= left
        if finished(left - refused):
            break
    else:
        deadline = time.monotonic() + _KILL_WAIT_SECONDS
        while True:
            left = command.processes()
            seen |= left
            pending = left - refused
            if finished(pending) or time.monotonic() >= deadline:
                break
            command.signal_group(signal.SIGKILL)
            refused |= command.signal_outside(
                command.outside_group(pending), signal.SIGKILL
            )
            time.sleep(_LOOK_SECONDS)
    left = command.processes()
    not_safe = left & refused
    still = left - refused
    if still:
        logger.warning(
            "%s from a shell command still running %.0f seconds after being killed.",
            _processes(len(still)).capitalize(),
            _KILL_WAIT_SECONDS,
        )
    return Stopped(
        stopped=len(seen - left), not_safe=len(not_safe), still_running=len(still)
    )


class _Output:
    """The command's output, read here so the shell is never collected by the
    reading (``communicate()`` collects it). Bytes are read from the pipes as
    ``communicate()`` reads them and decoded the same way at the end."""

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        self.process = process
        self.selector = selectors.DefaultSelector()
        self.chunks: dict[Any, list[bytes]] = {}
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                self.chunks[stream] = []
                self.selector.register(stream, selectors.EVENT_READ)
        self.pidfd: int | None
        try:  # wakes the wait when the shell exits
            self.pidfd = os.pidfd_open(process.pid)
        except (AttributeError, OSError):
            self.pidfd = None
        if self.pidfd is not None:
            self.selector.register(self.pidfd, selectors.EVENT_READ)

    def open(self) -> bool:
        return any(
            key.fileobj is not self.pidfd for key in self.selector.get_map().values()
        )

    def pump(self, timeout: float) -> None:
        if not self.selector.get_map():
            time.sleep(min(timeout, _LOOK_SECONDS))
            return
        if self.pidfd is None:
            timeout = min(timeout, _LOOK_SECONDS)
        for key, _events in self.selector.select(max(timeout, 0.0)):
            if key.fileobj is self.pidfd:
                # The shell has exited; its pidfd stays readable from now on.
                self.selector.unregister(self.pidfd)
                os.close(self.pidfd)
                self.pidfd = None
                continue
            data = os.read(key.fd, 32768)
            if data:
                self.chunks[key.fileobj].append(data)
            else:
                self.selector.unregister(key.fileobj)
                key.fileobj.close()

    def wait(self, limit: float) -> bool:
        """Read until the shell has exited (left uncollected) and the output
        has closed, or ``_PIPE_GRACE_SECONDS`` after the exit if something
        still holds it open. True when ``limit`` passed first."""
        deadline = time.monotonic() + limit
        exited_at: float | None = None
        while True:
            now = time.monotonic()
            if _shell_state(self.process) != _RUNNING:
                if not self.open():
                    return False
                if exited_at is None:
                    exited_at = now
                if now - exited_at >= _PIPE_GRACE_SECONDS:
                    return False
            if now >= deadline:
                return True
            wait = min(_POLL_SECONDS, deadline - now)
            if exited_at is not None:
                wait = min(wait, _PIPE_GRACE_SECONDS - (now - exited_at))
            self.pump(wait)

    def drain(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while self.open() and time.monotonic() < deadline:
            self.pump(min(0.1, max(deadline - time.monotonic(), 0.0)))

    def close(self) -> None:
        for key in list(self.selector.get_map().values()):
            self.selector.unregister(key.fileobj)
            if key.fileobj is not self.pidfd:
                key.fileobj.close()
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None
        self.selector.close()

    def text(self) -> tuple[str, str]:
        """stdout and stderr decoded as ``communicate()`` decodes them, stdout
        first; a ``UnicodeDecodeError`` propagates as it does upstream."""

        def decoded(stream: Any) -> str:
            data = b"".join(self.chunks.get(stream, []))
            value = data.decode(stream.encoding, stream.errors)
            return value.replace("\r\n", "\n").replace("\r", "\n")

        return decoded(self.process.stdout), decoded(self.process.stderr)


def _quoted(command: str) -> str:
    one_line = " ".join(command.split())
    if len(one_line) > _QUOTED_COMMAND_CHARS:
        one_line = one_line[: _QUOTED_COMMAND_CHARS - 3] + "..."
    return one_line


def _processes(count: int) -> str:
    return "1 process" if count == 1 else f"{count} processes"


def _were(count: int) -> str:
    return "was" if count == 1 else "were"


def _not_stopped(result: Stopped) -> str:
    """The plain sentences for processes that were not stopped."""
    parts = []
    if result.not_safe:
        parts.append(
            f" {_processes(result.not_safe).capitalize()} outside the command's "
            f"process group could not be stopped safely on this system (it "
            f"does not allow signalling one process through a pidfd), so "
            f"{'it is' if result.not_safe == 1 else 'they are'} still running."
        )
    if result.still_running:
        parts.append(
            f" {_processes(result.still_running).capitalize()} "
            f"{_were(result.still_running)} killed but still running "
            f"{_KILL_WAIT_SECONDS:.0f} seconds later."
        )
    return "".join(parts)


class CommandSessionShellBackend(LocalShellBackend):
    """``LocalShellBackend`` whose commands leave no processes behind.

    Output, exit codes, truncation, the timeout message and the response to
    output that cannot be decoded are DeepAgents' own. See the module
    docstring for what changes.
    """

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )
        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            msg = f"timeout must be positive, got {effective_timeout}"
            raise ValueError(msg)

        refusal = refusal_for_factory_launch()
        if refusal is not None:
            return ExecuteResponse(output=f"Error: {refusal}", exit_code=1, truncated=False)
        missing = cleanup_capability_missing()
        if missing is not None:
            _warn_reduced_cleanup_once(missing)

        marker = uuid.uuid4().hex
        env = dict(self._env)
        env[COMMAND_MARKER_NAME] = marker
        since = _now_ticks()
        if since is not None:
            since -= 1  # the clock's own rounding
        try:
            process = subprocess.Popen(
                # ``shell=True`` runs ``/bin/sh -c command``; this runs the
                # same, after marking the shell first in line for the
                # out-of-memory killer (see _FIRST_TO_GO).
                ["/bin/sh", "-c", _FIRST_TO_GO, "/bin/sh", command],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(self.cwd),
                start_new_session=True,
            )
        except Exception as e:  # noqa: BLE001 - upstream's contract: never raise
            return _error(e)
        if not _can_wait_without_collecting():
            return self._finish_without_waitid(process, command, timeout, effective_timeout)
        output: _Output | None = None
        result = Stopped()
        timed_out = False
        try:
            output = _Output(process)
            timed_out = output.wait(effective_timeout)
            result = stop_command_processes(
                process, marker, since=since, include_shell=timed_out
            )
            output.drain(_DRAIN_SECONDS)
        except BaseException:
            stop_command_processes(process, marker, since=since, include_shell=True)
            raise
        finally:
            if output is not None:
                output.close()
            if process.returncode is None and _shell_state(process) == _RUNNING:
                process.kill()  # not reached while the stop works; never left behind
            process.wait()

        note = self._report_stopped(command, result, timed_out)
        if timed_out:
            if timeout is not None:
                msg = (
                    f"Error: Command timed out after {effective_timeout} seconds "
                    "(custom timeout). The command may be stuck or require more time."
                )
            else:
                msg = (
                    f"Error: Command timed out after {effective_timeout} seconds. "
                    "For long-running commands, re-run using the timeout parameter."
                )
            return ExecuteResponse(output=msg + note, exit_code=124, truncated=False)
        try:
            stdout, stderr = output.text()
        except Exception as e:  # noqa: BLE001 - upstream returns this, e.g. bad UTF-8
            response = _error(e)
            response.output += note
            return response

        return self._response(stdout, stderr, process.returncode, note)

    def _finish_without_waitid(
        self,
        process: subprocess.Popen[str],
        command: str,
        timeout: int | None,
        effective_timeout: int,
    ) -> ExecuteResponse:
        """Where the shell's exit cannot be read without collecting it (macOS
        before Python 3.13): wait as upstream does, and on a timeout stop the
        command's own process group, by the number the still uncollected
        shell pins. Nothing that left the group can be found or stopped
        safely there, and nothing is counted."""
        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            # A timed-out communicate() has not collected the shell.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(process.pid, sig)
                except OSError:
                    break
                if sig == signal.SIGTERM:
                    time.sleep(_GRACE_SECONDS)
            try:
                process.communicate(timeout=_DRAIN_SECONDS)
            except (subprocess.TimeoutExpired, ValueError):
                process.kill()
            process.wait()
            note = self._report_stopped(command, Stopped(stopped=None), True)
            if timeout is not None:
                msg = (
                    f"Error: Command timed out after {effective_timeout} seconds "
                    "(custom timeout). The command may be stuck or require more time."
                )
            else:
                msg = (
                    f"Error: Command timed out after {effective_timeout} seconds. "
                    "For long-running commands, re-run using the timeout parameter."
                )
            return ExecuteResponse(output=msg + note, exit_code=124, truncated=False)
        except Exception as e:  # noqa: BLE001 - upstream's contract, e.g. bad UTF-8
            if process.returncode is None:
                process.kill()
                process.wait()
            return _error(e)
        return self._response(stdout, stderr, process.returncode, "")

    def _response(
        self, stdout: str, stderr: str, returncode: int, note: str
    ) -> ExecuteResponse:
        """Upstream's output format, with ``note`` added."""
        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            stderr_lines = stderr.strip().split("\n")
            output_parts.extend(f"[stderr] {line}" for line in stderr_lines)
        text = "\n".join(output_parts) if output_parts else "<no output>"
        truncated = False
        if len(text) > self._max_output_bytes:
            text = text[: self._max_output_bytes]
            text += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
            truncated = True
        if returncode != 0:
            text = f"{text.rstrip()}\n\nExit code: {returncode}"
        return ExecuteResponse(output=text + note, exit_code=returncode, truncated=truncated)

    @staticmethod
    def _report_stopped(command: str, result: Stopped, timed_out: bool) -> str:
        """Log what was stopped; return the sentence added to the output."""
        quoted = _quoted(command)
        if timed_out:
            if result.stopped is None:
                done = "It was stopped along with everything it started (how many is not known)."
            elif result.stopped:
                done = (
                    "It was stopped along with everything it started "
                    f"({_processes(result.stopped)} in all)."
                )
            else:
                done = "It was stopped."
            done += _not_stopped(result)
            logger.warning(
                "A shell command ran past its time limit. %s The command: %s", done, quoted
            )
            return f"\n\n{done}"
        if not result.anything:
            return ""
        left = (result.stopped or 0) + result.not_safe + result.still_running
        if result.not_safe or result.still_running:
            done = (
                f"left {_processes(left)} running; {result.stopped or 0} "
                f"{_were(result.stopped or 0)} stopped.{_not_stopped(result)}"
            )
        else:
            were = "it was" if left == 1 else "they were"
            done = f"left {_processes(left)} running; {were} stopped."
        logger.warning("A shell command finished but %s The command: %s", done, quoted)
        return (
            f"\n\nNote: this command finished but {done} "
            "Start and use a server or watcher within one command."
        )


def _error(e: Exception) -> ExecuteResponse:
    """Upstream's response when the command cannot be run or read."""
    return ExecuteResponse(
        output=f"Error executing command ({type(e).__name__}): {e}",
        exit_code=1,
        truncated=False,
    )
