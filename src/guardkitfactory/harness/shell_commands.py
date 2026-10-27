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

On a factory launch the real clean-up first runs an END-TO-END SELF-TEST in
this process (:func:`_self_test`, once, remembered): a tiny command leaves a
process in a session of its own, is stopped exactly as any command is, and the
process must be gone. That proves the ``/proc`` listing and record reads,
``waitid`` and the pidfd calls together. When it fails (26 October 2026, step
2) the reason is logged once and the commands run with the reduced clean-up a
person's own run has: a missing system capability is advice, not a reason to
run no command. Since 27 October 2026 (step 2 review) the same holds when one
of them fails later, after a passed self-test: a record or listing that cannot
be read is left out (a listing that cannot be made is logged), a process that
cannot be signalled through a pidfd is reported in the command's output as
not stopped, and a ``waitid`` refused before a command gives that command the
reduced clean-up. None of these refuses or ends a command. (Codex review,
20 October 2026.)

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
collecting it (``os.waitid`` missing, as on macOS before Python 3.13, or
refused by a filter), the command is waited for as upstream does, and only a
timeout stops its process group. No wait for the shell is ever unbounded.

Nothing here names a language, tool or test runner.
"""

from __future__ import annotations

import errno
import logging
import os
import select
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
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
    "full_cleanup",
    "is_factory_launch",
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
    except (FileNotFoundError, ProcessLookupError):
        return None  # gone, or never there
    except OSError:
        # A record that cannot be read is left out, as on a person's own run
        # (27 October 2026, step 2 review: it no longer ends the command).
        return None
    # The program name (field 2) may hold spaces and brackets; the fields
    # after the last ")" start at field 3.
    try:
        rest = data[data.rindex(b")") + 2 :].split()
        return rest[0].decode(), int(rest[2]), int(rest[3]), int(rest[19])
    except (ValueError, IndexError):
        return None


def _carries_marker(pid: int, marker: bytes) -> bool:
    """Whether ``pid``'s environment holds ``marker``.

    A process that has gone does not, and nor does one whose environment
    cannot be read (27 October 2026, step 2 review: that no longer ends the
    command; the process is left out, as on a person's own run).
    """
    try:
        environ = (_PROC / str(pid) / "environ").read_bytes()
    except OSError:
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


#: The system call numbers of pidfd_open and pidfd_send_signal: the same on
#: every Linux architecture (they come from the unified syscall table).
_SYS_PIDFD_OPEN = 434
_SYS_PIDFD_SEND_SIGNAL = 424
_LIBC: list[Any] = []


def _raw_syscall(number: int, *args: Any) -> int:
    """``syscall(2)`` through ctypes, for a Python built without the pidfd
    wrappers (some standalone builds, such as uv-managed ones). Raises
    ``OSError`` with the call's own error."""
    import ctypes

    if not _LIBC:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.syscall.restype = ctypes.c_long
        _LIBC.append(libc)
    result = _LIBC[0].syscall(ctypes.c_long(number), *args)
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    return int(result)


def _has_wrapper(module: str) -> bool:
    try:
        if module == "os":
            os.pidfd_open  # noqa: B018 - the attribute's presence is the question
        else:
            signal.pidfd_send_signal  # noqa: B018
    except AttributeError:
        return False
    return True


def pidfd_open(pid: int) -> int:
    """``os.pidfd_open``, or the system call itself where this Python build
    lacks the wrapper (Linux only)."""
    if _has_wrapper("os"):
        return os.pidfd_open(pid)
    if sys.platform != "linux":
        raise OSError(errno.ENOSYS, "pidfd_open is a Linux system call")
    return _raw_syscall(_SYS_PIDFD_OPEN, _c_int(pid), _c_int(0))


def pidfd_send_signal(handle: int, sig: int) -> None:
    """``signal.pidfd_send_signal``, or the system call itself where this
    Python build lacks the wrapper (Linux only)."""
    if _has_wrapper("signal"):
        signal.pidfd_send_signal(handle, sig)
        return
    if sys.platform != "linux":
        raise OSError(errno.ENOSYS, "pidfd_send_signal is a Linux system call")
    _raw_syscall(
        _SYS_PIDFD_SEND_SIGNAL, _c_int(handle), _c_int(int(sig)), None, _c_int(0)
    )


def _c_int(value: int) -> Any:
    import ctypes

    return ctypes.c_int(value)


def _refused(call: str, wrapper: bool, exc: OSError) -> str:
    """The plain clause naming why ``call`` cannot be used here."""
    reason = exc.strerror or str(exc)
    if wrapper:
        return f"{call} is refused here by the kernel or a security filter ({reason})"
    if sys.platform != "linux":
        return f"this Python build lacks {call}, and this system is not Linux"
    return (
        f"this Python build lacks {call}, and the system call itself is "
        f"refused by the kernel or a security filter ({reason})"
    )


def _missing_capability() -> str | None:
    """Why this system cannot stop everything a command leaves, as a plain
    clause, or ``None`` when nothing is missing.

    Stopping a process that left the command's process group needs ``/proc``
    (to find it), ``os.waitid`` (to keep the shell uncollected meanwhile) and a
    pidfd that can be opened and signalled through (to signal that one
    process and no other). Both are tried on this process itself, through
    the Python wrappers or, where this Python build lacks them, the system
    calls themselves.
    """
    if not (_PROC / "self" / "stat").exists():
        return "/proc is missing (it is needed to find a command's processes)"
    waitid_problem = _waitid_problem()
    if waitid_problem is not None:
        return waitid_problem
    try:
        handle = pidfd_open(os.getpid())
    except OSError as exc:
        return _refused("pidfd_open", _has_wrapper("os"), exc)
    try:
        # Signal 0 checks that signalling through a pidfd is allowed too (a
        # filter may allow opening one and refuse sending).
        pidfd_send_signal(handle, 0)
    except OSError as exc:
        return _refused("pidfd_send_signal", _has_wrapper("signal"), exc)
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
    """This system cannot stop everything a shell command leaves (``errno``
    ENOSYS and the plain sentence as ``strerror``, so a caller reporting
    ``strerror`` says why). ``reason`` is the clause alone."""

    reason: str = ""


_ADVICE = (
    "Run the factory where /proc can be read and waitid, pidfd_open and "
    "pidfd_send_signal are allowed (Linux 5.3 or later)."
)


def _cleanup_failure(reason: str) -> CleanupUnavailableError:
    text = (
        f"A shell command was ended because {reason}, so what it left running "
        f"could not all be stopped safely. {_ADVICE}"
    )
    error = CleanupUnavailableError(errno.ENOSYS, text)
    error.reason = reason
    return error


#: The self-test's outcome, once per process: ``None`` when it passed, else
#: the reason it failed.
_SELF_TEST_OUTCOME: list[str | None] = []
_SELF_TEST_LOCK = threading.Lock()
_IN_SELF_TEST = threading.local()

#: The self-test's command (argument 1: a private folder). It starts one
#: process that moves into a session of its own (carrying the command's
#: marker, as every process of a command does), lets go of the output and
#: writes its pid; the command then waits for the self-test's "go", prints
#: that pid and the marker, and returns, leaving the process running.
_SELF_TEST_CODE = (
    "import os, sys, time\n"
    "folder = sys.argv[1]\n"
    "pid = os.fork()\n"
    "if pid == 0:\n"
    "    os.setsid()\n"
    "    null = os.open(os.devnull, os.O_RDWR)\n"
    "    for fd in (0, 1, 2):\n"
    "        os.dup2(null, fd)\n"
    "    with open(os.path.join(folder, 'child.tmp'), 'w') as fh:\n"
    "        fh.write(str(os.getpid()))\n"
    "    os.rename(os.path.join(folder, 'child.tmp'), os.path.join(folder, 'child'))\n"
    "    time.sleep(30)\n"
    "    os._exit(0)\n"
    "deadline = time.monotonic() + 20\n"
    "while not os.path.exists(os.path.join(folder, 'go')) and time.monotonic() < deadline:\n"
    "    time.sleep(0.01)\n"
    f"print(pid, os.environ.get({COMMAND_MARKER_NAME!r}, ''), flush=True)\n"
)
_SELF_TEST_WAIT_SECONDS = 20.0


def _self_test_child_check(
    pid: int, handle: int, since: int | None
) -> tuple[str | None, bytes]:
    """Check, through the pinned pidfd ``handle``, that ``pid`` is the
    self-test's own process: alive, the leader of a session of its own,
    started after the self-test, with a readable environment carrying a
    command marker. Returns ``(problem, marker entry)``."""
    try:
        pidfd_send_signal(handle, 0)  # still the pinned process, still alive
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return "the clean-up self-test's process ended before it could be checked", b""
        return _refused("pidfd_send_signal", _has_wrapper("signal"), exc), b""
    stat = _stat(pid)
    if stat is None or stat[0] in ("Z", "X"):
        return "the clean-up self-test's process ended before it could be checked", b""
    _state, _group, session, started = stat
    if session != pid or (since is not None and started < since):
        return "the clean-up self-test's process is not the one it started", b""
    try:
        environ = (_PROC / str(pid) / "environ").read_bytes()
    except OSError as exc:
        return (
            "the clean-up self-test's process environment could not be read "
            f"({exc.strerror or exc})"
        ), b""
    prefix = f"{COMMAND_MARKER_NAME}=".encode()
    for item in environ.split(b"\0"):
        if item.startswith(prefix) and len(item) > len(prefix):
            return None, b"\0" + item + b"\0"
    return "the clean-up self-test's process does not carry the command's marker", b""


def _has_ended(handle: int, seconds: float) -> bool:
    """Whether the pinned process has ended, waiting at most ``seconds``
    (a pidfd becomes readable when its process exits)."""
    poller = select.poll()
    poller.register(handle, select.POLLIN)
    return bool(poller.poll(int(seconds * 1000)))


def _end_self_test_leftovers(pids: set[int], entry: bytes, since: int | None) -> None:
    """Kill what the self-test left, through pidfds, each checked again after
    pinning (alive, started after the self-test, carrying its marker), so a
    number handed on in between is never signalled."""
    for pid in pids:
        try:
            handle = pidfd_open(pid)
        except OSError:
            continue
        try:
            stat = _stat(pid)
            if (
                stat is not None
                and stat[0] not in ("Z", "X")
                and (since is None or stat[3] >= since)
                and _carries_marker(pid, entry)
            ):
                pidfd_send_signal(handle, signal.SIGKILL)
        except OSError:
            pass
        finally:
            os.close(handle)


def _self_test_command(folder: str, outcome: dict[str, Any]) -> None:
    """The self-test's command, run like any shell command (in its own
    thread, so the self-test can pin the process it leaves meanwhile)."""
    _IN_SELF_TEST.active = True
    try:
        shell = CommandSessionShellBackend(
            root_dir="/", virtual_mode=False, env={"PATH": os.defpath}, timeout=60
        )
        command = (
            f"{shlex.quote(sys.executable)} -I -c {shlex.quote(_SELF_TEST_CODE)} "
            f"{shlex.quote(folder)}"
        )
        outcome["response"], outcome["failure"] = shell._run(command, 60, None)
    except BaseException as exc:  # noqa: BLE001 - reported by the self-test
        outcome["failure"] = exc


def _self_test() -> str | None:
    """Run the real clean-up end to end once; ``None`` when it worked, else
    the plain reason.

    A tiny command, run through the real shell like any command, leaves a
    process in a session of its own. While the command waits, that process
    is pinned (a pidfd) and checked to be the one it started, carrying the
    command's marker; then the command returns and the real stop runs.
    Afterwards the pinned process must have ended (its pidfd readable), and
    nothing carrying the marker may be left in ``/proc``. That proves, on
    this system, the ``/proc`` listing and record reads, ``waitid`` and the
    pidfd calls the clean-up needs, without relying on the marker scan to
    see its own process.
    """
    folder = tempfile.mkdtemp(prefix="guardkitfactory-cleanup-self-test-")
    outcome: dict[str, Any] = {}
    since = _now_ticks()
    if since is not None:
        since -= 1
    worker = threading.Thread(
        target=_self_test_command, args=(folder, outcome), name="clean-up self-test",
        daemon=True,
    )
    handle: int | None = None
    entry = b""
    problem: str | None = None
    try:
        worker.start()
        child_file = Path(folder) / "child"
        deadline = time.monotonic() + _SELF_TEST_WAIT_SECONDS
        while not child_file.exists() and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not child_file.exists():
            (Path(folder) / "go").write_text("go", encoding="ascii")
            worker.join(_SELF_TEST_WAIT_SECONDS + 60)
            failure = outcome.get("failure")
            if isinstance(failure, CleanupUnavailableError):
                return failure.reason or str(failure)
            return "the clean-up self-test's process did not start"
        pid = int(child_file.read_text(encoding="ascii"))
        try:
            handle = pidfd_open(pid)
        except OSError as exc:
            problem = _refused("pidfd_open", _has_wrapper("os"), exc)
        else:
            problem, entry = _self_test_child_check(pid, handle, since)
        (Path(folder) / "go").write_text("go", encoding="ascii")
        worker.join(_SELF_TEST_WAIT_SECONDS + 60)
        if worker.is_alive():
            return problem or "the clean-up self-test's command did not finish"
        if problem is not None:
            return problem
        failure = outcome.get("failure")
        if isinstance(failure, CleanupUnavailableError):
            return failure.reason or str(failure)
        if failure is not None:
            return f"the clean-up self-test failed ({type(failure).__name__}: {failure})"
        response = outcome["response"]
        words = response.output.split("\n", 1)[0].split()
        printed = f"\0{COMMAND_MARKER_NAME}={words[1]}\0".encode() if len(words) == 2 else b""
        if response.exit_code != 0 or handle is None or entry != printed:
            return (
                "the clean-up self-test's command did not run as expected "
                f"(exit {response.exit_code})"
            )
        # Independent of the marker scan: the pinned process itself.
        if not _has_ended(handle, _GRACE_SECONDS):
            try:
                pidfd_send_signal(handle, signal.SIGKILL)
            except OSError:
                pass
            return "the clean-up self-test's left-behind process was still running after the stop"
        # And nothing else carrying the marker.
        left: set[int] = set()
        try:
            for path in _PROC.iterdir():
                if not path.name.isdigit():
                    continue
                stat = _stat(int(path.name))
                if (
                    stat is not None
                    and stat[0] not in ("Z", "X")
                    # Only what started after the self-test can be its own.
                    and (since is None or stat[3] >= since)
                    and _carries_marker(int(path.name), entry)
                ):
                    left.add(int(path.name))
        except OSError as exc:
            return f"/proc could not be listed ({exc.strerror or exc})"
        if left:
            _end_self_test_leftovers(left, entry, since)
            return "the clean-up self-test left a process running after the stop"
        return None
    finally:
        if handle is not None:
            os.close(handle)
        shutil.rmtree(folder, ignore_errors=True)


def full_cleanup() -> bool:
    """Whether this process's commands get the full clean-up.

    True on a factory launch whose clean-up passed its end-to-end self-test in
    this process (run on first need, once, remembered), and inside the
    self-test itself. A person's own run, and a factory launch whose
    self-test failed, get the reduced clean-up instead. The failure is logged
    once, in plain words (26 October 2026, step 2: it was a refusal of every
    command).
    """
    if getattr(_IN_SELF_TEST, "active", False):
        return True
    if not is_factory_launch():
        return False
    if not _SELF_TEST_OUTCOME:
        with _SELF_TEST_LOCK:
            if not _SELF_TEST_OUTCOME:
                _IN_SELF_TEST.active = True
                try:
                    reason = _self_test()
                finally:
                    _IN_SELF_TEST.active = False
                _SELF_TEST_OUTCOME.append(reason)
                if reason is not None:
                    logger.warning(
                        "Shell commands run with the reduced clean-up: %s, so what a "
                        "command leaves running may not all be stopped. %s",
                        reason,
                        _ADVICE,
                    )
    return _SELF_TEST_OUTCOME[0] is None


_WARNED: list[bool] = []


def _warn_reduced_cleanup_once(missing: str) -> None:
    if _WARNED:
        return
    _WARNED.append(True)
    logger.warning(
        "Here %s, so a process a shell command moves out of its process "
        "group may be left running after the command.",
        missing,
    )


def _waitid_problem() -> str | None:
    """Why the shell's exit cannot be read without collecting it, as a plain
    clause, or ``None`` when it can.

    ``os.waitid`` must exist (macOS has it only from Python 3.13) and the
    call must work: it is tried on this process itself, which is never its
    own child, so a working call answers "no such child" (ECHILD) and a
    refusal by the kernel or a filter answers otherwise. Nothing is
    collected.
    """
    try:
        os.waitid  # noqa: B018 - the attribute's presence is the question
    except AttributeError:
        return "os.waitid is missing (macOS has it from Python 3.13)"
    try:
        os.waitid(os.P_PID, os.getpid(), os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return None
    except OSError as exc:
        return _refused("waitid", True, exc)
    return None


def _collect(process: subprocess.Popen[Any]) -> None:
    """Collect the ended shell, never waiting without bound: after
    ``_KILL_WAIT_SECONDS`` its group is sent SIGKILL (by the number the
    uncollected shell pins) and given ``_DRAIN_SECONDS`` more; then it is
    left, said plainly."""
    try:
        process.wait(timeout=_KILL_WAIT_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        process.wait(timeout=_DRAIN_SECONDS)
    except subprocess.TimeoutExpired:
        logger.warning(
            "A shell command's shell (%s) could not be collected; it is left as it is.",
            process.pid,
        )


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
    except OSError as exc:
        # waitid refused (a filter): the shell's state cannot be read, so the
        # command cannot be watched safely. Never read as "running", which
        # could wait for ever.
        raise _cleanup_failure(_refused("waitid", True, exc)) from exc
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
        except OSError as exc:
            # A listing that cannot be made is said, and the command goes on
            # (27 October 2026, step 2 review: it no longer ends the command).
            logger.warning(
                "/proc could not be listed (%s), so what a shell command left "
                "running cannot be found or stopped.",
                exc.strerror or exc,
            )
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
                handle = pidfd_open(pid)
            except OSError as exc:
                if exc.errno != errno.ESRCH:  # ESRCH: it has gone
                    refused.add(pid)
                continue
            try:
                stat = self.owns(pid)
                if stat is not None and stat[1] != self.leader:
                    pidfd_send_signal(handle, sig)
            except OSError as exc:
                # Only ESRCH means it ended after it was pinned; anything else
                # (a refusal) means it was not signalled, which the command's
                # output reports (27 October 2026, step 2 review: it no longer
                # ends the command).
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
            self.pidfd = pidfd_open(process.pid)
        except OSError:
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

        if not full_cleanup():
            missing = cleanup_capability_missing()
            if missing is not None:
                _warn_reduced_cleanup_once(missing)
        response, _failure = self._run(command, effective_timeout, timeout)
        return response

    def _run(
        self, command: str, effective_timeout: int, timeout: int | None
    ) -> tuple[ExecuteResponse, Exception | None]:
        """Run ``command`` and stop what it leaves; return the answer and the
        failure, if any, that ended it (the self-test reads the failure)."""
        # Fresh before every command, even after a cached self-test success:
        # one cheap call on this process itself. Where the shell's exit cannot
        # be read without collecting it, the command runs with the reduced
        # clean-up and that is logged once (27 October 2026, step 2 review:
        # on a factory launch it was refused before it started).
        waitid_problem = _waitid_problem()
        reduced = waitid_problem is not None
        if reduced:
            _warn_reduced_cleanup_once(waitid_problem)
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
            return _error(e), None
        if reduced:
            return (
                self._finish_without_waitid(process, command, timeout, effective_timeout),
                None,
            )
        output: _Output | None = None
        result = Stopped()
        timed_out = False
        failure: Exception | None = None
        try:
            output = _Output(process)
            timed_out = output.wait(effective_timeout)
            result = stop_command_processes(
                process, marker, since=since, include_shell=timed_out
            )
            output.drain(_DRAIN_SECONDS)
        except Exception as e:  # noqa: BLE001 - e.g. waitid refused while watching
            _end_everything(process, marker, since)
            failure = e
        except BaseException:
            _end_everything(process, marker, since)
            raise
        finally:
            if output is not None:
                output.close()
            _collect(process)
        if failure is not None:
            return _error(failure), failure  # upstream's contract: never raise

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
            return ExecuteResponse(output=msg + note, exit_code=124, truncated=False), None
        try:
            stdout, stderr = output.text()
        except Exception as e:  # noqa: BLE001 - upstream returns this, e.g. bad UTF-8
            response = _error(e)
            response.output += note
            return response, None

        return self._response(stdout, stderr, process.returncode, note), None

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
            _collect(process)
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
                _collect(process)
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


def _end_everything(process: subprocess.Popen[Any], marker: str, since: int | None) -> None:
    """End the command and all it started after a failure while watching it.

    First the normal stop. Where even that fails (for example waitid is
    refused), the shell is still uncollected (nothing here collects it before
    this), so its number is still the group's and the session's: the group
    is sent SIGKILL by that number, and each process of the command outside
    the group is sent SIGKILL through a pidfd, checked after pinning, without
    waitid. A few looks, bounded; failures here are swallowed (the caller
    reports the original one)."""
    try:
        stop_command_processes(process, marker, since=since, include_shell=True)
        return
    except Exception:  # noqa: BLE001
        pass
    command = _Command(process.pid, marker, since)
    command.signal_group(signal.SIGKILL)
    deadline = time.monotonic() + _GRACE_SECONDS
    while time.monotonic() < deadline:
        try:
            outside = command.outside_group(command.processes())
            if not outside:
                return
            if command.signal_outside(outside, signal.SIGKILL):
                return  # refused: nothing more can be done safely
        except Exception:  # noqa: BLE001
            return
        time.sleep(_LOOK_SECONDS)


def _error(e: Exception) -> ExecuteResponse:
    """Upstream's response when the command cannot be run or read."""
    return ExecuteResponse(
        output=f"Error executing command ({type(e).__name__}): {e}",
        exit_code=1,
        truncated=False,
    )
