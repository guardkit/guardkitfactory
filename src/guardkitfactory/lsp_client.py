"""A small Language Server Protocol client over stdio, for "find references".

Written for this package (28 October 2026) rather than taken from
``serena-agent``, which is GPL-3.0-or-later as a whole. It speaks only what
:mod:`guardkitfactory.code_search` needs: ``initialize``/``initialized``,
``textDocument/didOpen``, ``didChange`` (full text), ``didClose``,
``workspace/didChangeWatchedFiles``, ``textDocument/references`` (declaration
included), ``shutdown`` and ``exit``.

Messages are JSON-RPC 2.0 framed by a ``Content-Length`` header. One reader
thread reads the server's output: answers go to the request waiting for them
(late answers to abandoned requests are dropped), notifications are ignored,
and the server's own requests are answered with empty results so it never
waits on us (``workspace/configuration`` gets one ``null`` per item). Work the
server reports through ``$/progress`` is tracked, so a caller can wait until
it is idle (:meth:`LspClient.wait_until_idle`). Every
wait is bounded by the caller's deadline and cancellation. The server runs
in its own process group; :meth:`LspClient.close` asks it to stop
(``shutdown``, ``exit``), then terminates and kills the whole group after a
grace period, so nothing it started outlives it.

Uses only the standard library.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

#: The largest message accepted from a server; more is a broken stream.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
MAX_HEADER_BYTES = 8 * 1024
#: How much of the server's standard error is kept (the end of it).
MAX_STDERR_BYTES = 16 * 1024
#: Seconds a stopping server gets after ``exit``, and again after SIGTERM.
CLOSE_GRACE_S = 2.0
_POLL_S = 0.05


class LspError(Exception):
    """The server could not answer: it died, broke the protocol or refused."""


class LspTimeout(LspError):
    """The deadline passed before the server answered."""


class LspCancelled(LspError):
    """The caller cancelled while waiting."""


def path_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_path(uri: str) -> Path | None:
    """The local path a ``file:`` URI names, else ``None``."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def utf16_column(text: str, index: int) -> int:
    """LSP counts a line's characters in UTF-16 code units by default."""
    return len(text[:index].encode("utf-16-le")) // 2


class _Waiter:
    __slots__ = ("done", "result", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Any = None
        self.error: str | None = None


class LspClient:
    """One language server process and the JSON-RPC conversation with it."""

    def __init__(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                 workspace: Path) -> None:
        self.argv = list(argv)
        self.workspace = workspace
        self.server_info: dict[str, Any] = {}
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._pending: dict[int, _Waiter] = {}
        self._next_id = 0
        self._stderr = bytearray()
        self._dead: str | None = None
        self._progress: set[str] = set()
        self._progress_changed = time.monotonic()
        self.process = subprocess.Popen(  # noqa: S603 - argv from fixed folders, no shell
            self.argv,
            cwd=str(cwd),
            env=dict(env),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self._threads = [threading.Thread(target=self._read_messages, daemon=True),
                         threading.Thread(target=self._read_stderr, daemon=True)]
        for thread in self._threads:
            thread.start()

    # -- state -----------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._dead is None and self.process.poll() is None

    def stderr_tail(self, limit: int = 300) -> str:
        text = bytes(self._stderr).decode("utf-8", errors="replace").strip()
        return text[-limit:]

    def _fail(self, reason: str) -> None:
        with self._state_lock:
            if self._dead is None:
                self._dead = reason
            waiters = list(self._pending.values())
            self._pending.clear()
        for waiter in waiters:
            waiter.error = reason
            waiter.done.set()

    # -- reading ---------------------------------------------------------

    def _read_stderr(self) -> None:
        stream = self.process.stderr
        assert stream is not None
        for chunk in iter(lambda: stream.read(4096), b""):
            self._stderr.extend(chunk)
            if len(self._stderr) > MAX_STDERR_BYTES:
                del self._stderr[: len(self._stderr) - MAX_STDERR_BYTES]

    def _read_frame(self, stream: Any) -> dict[str, Any] | None:
        length = None
        header = 0
        while True:
            line = stream.readline(MAX_HEADER_BYTES)
            if not line:
                return None
            header += len(line)
            if header > MAX_HEADER_BYTES:
                raise LspError("the server sent a header that is too long")
            text = line.decode("ascii", errors="replace").strip()
            if not text:
                break
            name, _, value = text.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    length = int(value.strip())
                except ValueError as exc:
                    raise LspError(f"the server sent a bad Content-Length {value!r}") from exc
        if length is None or length < 0 or length > MAX_MESSAGE_BYTES:
            raise LspError(f"the server sent a message without a usable length ({length})")
        body = stream.read(length)
        if len(body) != length:
            return None
        message = json.loads(body.decode("utf-8"))
        if not isinstance(message, dict):
            raise LspError("the server sent a message that is not a JSON object")
        return message

    def _read_messages(self) -> None:
        stream = self.process.stdout
        assert stream is not None
        try:
            while True:
                message = self._read_frame(stream)
                if message is None:
                    break
                self._dispatch(message)
        except (LspError, ValueError, OSError) as exc:
            self._fail(f"the server's output could not be read: {exc}")
            return
        self._fail("the server stopped")

    def _dispatch(self, message: dict[str, Any]) -> None:
        if "method" in message:
            if "id" in message:
                self._answer_server_request(message)
            elif message["method"] == "$/progress":
                self._note_progress(message.get("params"))
            return  # other notifications (diagnostics, logs) are not needed
        ident = message.get("id")
        with self._state_lock:
            waiter = self._pending.pop(ident, None) if isinstance(ident, int) else None
        if waiter is None:
            return  # an answer to a request already given up on
        error = message.get("error")
        if error is not None:
            text = error.get("message") if isinstance(error, dict) else error
            waiter.error = f"the server answered with an error: {str(text)[:300]}"
        else:
            waiter.result = message.get("result")
        waiter.done.set()

    def _note_progress(self, params: Any) -> None:
        token = params.get("token") if isinstance(params, dict) else None
        value = params.get("value") if isinstance(params, dict) else None
        kind = value.get("kind") if isinstance(value, dict) else None
        if token is None or kind not in ("begin", "end"):
            return
        with self._state_lock:
            if kind == "begin":
                self._progress.add(str(token))
            else:
                self._progress.discard(str(token))
            self._progress_changed = time.monotonic()

    def wait_until_idle(self, *, deadline: float, cancel: threading.Event | None = None,
                        quiet_s: float = 0.3) -> bool:
        """Wait until no work the server reported (``$/progress``) is running
        and none began or ended for ``quiet_s``; ``False`` if the deadline came
        first. A server that reports nothing is idle after ``quiet_s``."""
        while True:
            with self._state_lock:
                busy = bool(self._progress)
                quiet_since = self._progress_changed
            now = time.monotonic()
            if not busy and now - quiet_since >= quiet_s:
                return True
            if self._dead is not None or now >= deadline:
                return False
            if cancel is not None and cancel.is_set():
                raise LspCancelled("cancelled while the server was busy")
            time.sleep(_POLL_S)

    def _answer_server_request(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params")
        result: Any = None
        if method == "workspace/configuration":
            items = params.get("items") if isinstance(params, dict) else None
            result = [None] * (len(items) if isinstance(items, list) else 0)
        elif method == "workspace/workspaceFolders":
            result = [{"uri": path_uri(self.workspace), "name": self.workspace.name}]
        with contextlib.suppress(LspError):
            self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    # -- writing ---------------------------------------------------------

    def _send(self, message: dict[str, Any]) -> None:
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        frame = b"Content-Length: %d\r\n\r\n" % len(body) + body
        stdin = self.process.stdin
        try:
            with self._write_lock:
                assert stdin is not None
                stdin.write(frame)
                stdin.flush()
        except (OSError, ValueError) as exc:
            self._fail("the server stopped reading its input")
            raise LspError("the server stopped reading its input") from exc

    def notify(self, method: str, params: Any) -> None:
        if self._dead is not None:
            raise LspError(self._dead)
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: Any, *, deadline: float,
                cancel: threading.Event | None = None) -> Any:
        """Send one request and wait for its answer until ``deadline``
        (``time.monotonic()``); a request given up on is cancelled with the
        server (``$/cancelRequest``) and its late answer dropped."""
        waiter = _Waiter()
        with self._state_lock:
            if self._dead is not None:
                raise LspError(self._dead)
            self._next_id += 1
            ident = self._next_id
            self._pending[ident] = waiter
        self._send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        while not waiter.done.wait(_POLL_S):
            stopped = cancel is not None and cancel.is_set()
            if stopped or time.monotonic() >= deadline:
                with self._state_lock:
                    self._pending.pop(ident, None)
                with contextlib.suppress(LspError):
                    self.notify("$/cancelRequest", {"id": ident})
                if stopped:
                    raise LspCancelled(f"{method} was cancelled")
                raise LspTimeout(f"the server did not answer {method} in time")
        if waiter.error is not None:
            raise LspError(waiter.error)
        return waiter.result

    # -- the conversation ------------------------------------------------

    def initialize(self, *, initialization_options: Any, deadline: float,
                   cancel: threading.Event | None = None) -> dict[str, Any]:
        result = self.request("initialize", {
            "processId": os.getpid(),
            "clientInfo": {"name": "guardkitfactory"},
            "rootUri": path_uri(self.workspace),
            "rootPath": str(self.workspace),
            "workspaceFolders": [{"uri": path_uri(self.workspace),
                                  "name": self.workspace.name}],
            "initializationOptions": initialization_options,
            "capabilities": {
                "general": {"positionEncodings": ["utf-16"]},
                "window": {"workDoneProgress": True},
                "workspace": {"configuration": True, "workspaceFolders": True,
                              "didChangeWatchedFiles": {"dynamicRegistration": False}},
                "textDocument": {
                    "synchronization": {"didSave": False, "dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                },
            },
        }, deadline=deadline, cancel=cancel)
        info = result.get("serverInfo") if isinstance(result, dict) else None
        if isinstance(info, dict):
            self.server_info = {k: str(info[k])[:100] for k in ("name", "version") if k in info}
        self.notify("initialized", {})
        return result if isinstance(result, dict) else {}

    def references(self, uri: str, line: int, character: int, *, deadline: float,
                   cancel: threading.Event | None = None) -> list[dict[str, Any]]:
        """Locations referring to the symbol at a 0-based position,
        declaration included; ``[]`` when the server returned ``null``."""
        result = self.request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True},
        }, deadline=deadline, cancel=cancel)
        if result is None:
            return []
        if not isinstance(result, list):
            raise LspError("the server's references answer is not a list")
        return [item for item in result if isinstance(item, dict)]

    # -- stopping --------------------------------------------------------

    def _group_alive(self) -> bool:
        """Whether anything in the server's process group still runs. On
        Linux, zombies (dead, waiting for a parent to collect them) do not
        count, so a container whose first process collects nothing does not
        hold up the close."""
        group = self.process.pid
        proc = Path("/proc")
        if proc.is_dir():
            for entry in proc.iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                except (OSError, IndexError):
                    continue
                if len(fields) > 2 and fields[2] == str(group) and fields[0] not in "ZX":
                    return True
            return False
        try:
            os.killpg(group, 0)
        except OSError:
            return False
        return True

    def close(self, grace_s: float = CLOSE_GRACE_S) -> None:
        """``shutdown`` and ``exit``, then SIGTERM and SIGKILL to the whole
        process group, each after ``grace_s``. Safe to call more than once."""
        if self.alive:
            with contextlib.suppress(LspError):
                self.request("shutdown", None, deadline=time.monotonic() + grace_s)
                self.notify("exit", None)
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.process.wait(timeout=grace_s)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if not self._group_alive():
                break
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(self.process.pid, sig)
            stop = time.monotonic() + grace_s
            while time.monotonic() < stop and self._group_alive():
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self.process.wait(timeout=_POLL_S)
        with contextlib.suppress(Exception):
            self.process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.process.wait(timeout=grace_s)
        self._fail("the server was stopped")
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            with contextlib.suppress(Exception):
                if stream is not None:
                    stream.close()
