#!/usr/bin/env python3
"""A tiny language server for the find-references tests (standard library only).

It answers ``textDocument/references`` with every whole-word occurrence of the
word at the position, in files with the queried file's extension, leaving out
occurrences after ``#`` or ``//`` or inside quotes: so comments, strings and
other languages are left for the text-only part, as with a real server. Like
pyright, it knows the files that existed at ``initialize`` plus those it is
told about (``didOpen``, ``didChangeWatchedFiles``); open files are read from
what the client sent.

``FAKE_LSP_MODE``: ``normal``; ``crash`` (exit 3 at once); ``hang_initialize``;
``hang_references``; ``null_refs``; ``child`` (starts ``sleep 300`` in its
process group, pid in ``FAKE_LSP_CHILD``); ``stubborn`` (ignores SIGTERM and
``exit``); ``garbage`` (answers ``initialize`` with a broken header).
``FAKE_LSP_LOG`` gets one JSON line per message received; ``FAKE_LSP_PID``
gets this server's pid.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

MODE = os.environ.get("FAKE_LSP_MODE", "normal")
LOG = os.environ.get("FAKE_LSP_LOG")
STDIN = sys.stdin.buffer
STDOUT = sys.stdout.buffer


def log(entry: dict[str, Any]) -> None:
    if LOG:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


def send(message: dict[str, Any], split: bool = False) -> None:
    body = json.dumps(message).encode("utf-8")
    data = (b"Content-Length: %d\r\nContent-Type: application/vscode-jsonrpc; "
            b"charset=utf-8\r\n\r\n" % len(body)) + body
    pieces = [data[i:i + 7] for i in range(0, len(data), 7)] if split else [data]
    for piece in pieces:
        STDOUT.write(piece)
        STDOUT.flush()


def read() -> dict[str, Any] | None:
    length = None
    while True:
        line = STDIN.readline()
        if not line:
            return None
        text = line.decode("ascii").strip()
        if not text:
            break
        name, _, value = text.partition(":")
        if name.lower() == "content-length":
            length = int(value)
    assert length is not None
    return json.loads(STDIN.read(length))


def to_path(uri: str) -> Path:
    return Path(unquote(urlparse(uri).path))


known: set[Path] = set()
docs: dict[Path, str] = {}
root: Path | None = None


def text_of(path: Path) -> str:
    if path in docs:
        return docs[path]
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def counted(prefix: str) -> bool:
    return ("#" in prefix or "//" in prefix or prefix.count('"') % 2 == 1
            or prefix.count("'") % 2 == 1)


def references(params: dict[str, Any]) -> list[dict[str, Any]]:
    where = to_path(params["textDocument"]["uri"])
    position = params["position"]
    line = text_of(where).split("\n")[position["line"]]
    match = None
    for found in re.finditer(r"\w+", line):
        if found.start() <= position["character"] < found.end():
            match = found
    if match is None or counted(line[: match.start()]):
        return []
    word = re.compile(rf"(?<!\w){re.escape(match.group())}(?!\w)")
    out = []
    for path in sorted(known | set(docs)):
        if path.suffix != where.suffix:
            continue
        for number, text in enumerate(text_of(path).split("\n")):
            for hit in word.finditer(text):
                if not counted(text[: hit.start()]):
                    out.append({"uri": path.as_uri(), "range": {
                        "start": {"line": number, "character": hit.start()},
                        "end": {"line": number, "character": hit.end()}}})
    return out


def initialize(message: dict[str, Any]) -> None:
    global root
    root = to_path(message["params"]["rootUri"])
    for folder, dirs, names in os.walk(root):  # links are not followed
        dirs[:] = [d for d in dirs if d != ".git"]
        known.update(Path(folder) / name for name in names)
    # Ask the client two things, as real servers do, and wait for both answers.
    send({"jsonrpc": "2.0", "id": "cfg-1", "method": "workspace/configuration",
          "params": {"items": [{"section": "a"}, {"section": "b"}]}})
    send({"jsonrpc": "2.0", "id": 7, "method": "client/registerCapability",
          "params": {"registrations": []}})
    send({"jsonrpc": "2.0", "method": "window/logMessage",
          "params": {"type": 3, "message": "indexing"}})
    waiting = {"cfg-1", 7}
    while waiting:
        answer = read()
        if answer is None:
            sys.exit(0)
        log({"answer": answer.get("id"), "result": answer.get("result")})
        waiting.discard(answer.get("id"))
    if MODE == "garbage":
        STDOUT.write(b"Content-Length: lots\r\n\r\n{}")
        STDOUT.flush()
        return
    send({"jsonrpc": "2.0", "id": message["id"], "result": {
        "capabilities": {"referencesProvider": True, "textDocumentSync": 1},
        "serverInfo": {"name": "fake-lsp", "version": "1.2.3"}}}, split=True)


def main() -> None:
    if os.environ.get("FAKE_LSP_PID"):
        Path(os.environ["FAKE_LSP_PID"]).write_text(str(os.getpid()))
    if MODE == "crash":
        sys.stderr.write("fake-lsp: cannot start\n")
        sys.exit(3)
    if MODE == "child":
        child = subprocess.Popen(["sleep", "300"])
        Path(os.environ["FAKE_LSP_CHILD"]).write_text(str(child.pid))
    if MODE == "stubborn":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        message = read()
        if message is None:
            return
        method = message.get("method")
        log({"method": method, "params": message.get("params")})
        if method == "initialize" and MODE != "hang_initialize":
            initialize(message)
        elif method in ("textDocument/didOpen", "textDocument/didChange"):
            document = message["params"]["textDocument"]
            text = (document["text"] if method.endswith("didOpen")
                    else message["params"]["contentChanges"][-1]["text"])
            docs[to_path(document["uri"])] = text
        elif method == "textDocument/didClose":
            docs.pop(to_path(message["params"]["textDocument"]["uri"]), None)
        elif method == "workspace/didChangeWatchedFiles":
            for change in message["params"]["changes"]:
                path = to_path(change["uri"])
                if change["type"] == 3:
                    known.discard(path)
                else:
                    known.add(path)
        elif method == "textDocument/references" and MODE != "hang_references":
            result = None if MODE == "null_refs" else references(message["params"])
            send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        elif method == "shutdown":
            send({"jsonrpc": "2.0", "id": message["id"], "result": None})
        elif method == "exit" and MODE != "stubborn":
            sys.exit(0)


if __name__ == "__main__":
    main()
