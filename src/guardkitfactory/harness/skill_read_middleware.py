"""Pre-execution proof that every required project document was consumed.

The required set is the selected skill bodies plus the mandatory supporting
documents the project declared. One gate enforces both; there is no second
gate and nothing here parses Markdown links.
"""

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

_SAFE_BEFORE_SKILL_READS = {"read_file", "ls", "glob", "grep", "write_todos"}


class SelectedSkillReadError(RuntimeError):
    """Raised when a Player attempts work before required documents are read."""


def _label(item: Mapping[str, Any]) -> str:
    """Name one required entry the way a person reads it."""

    return (
        "declared document"
        if str(item.get("kind", "skill")) == "declared_document"
        else "selected skill"
    )


def _sdk_text_body(raw: bytes, path: Path) -> str:
    """Return the body emitted by the SDK's complete text read renderer."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SelectedSkillReadError(
            f"required document is not valid UTF-8: {path}"
        ) from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text[:-1] if text.endswith("\n") else text


class SelectedSkillReadMiddleware(AgentMiddleware):
    """Block coding tools until every required full-body read finishes."""

    name = "guardkitfactory-selected-skill-reads"

    def __init__(
        self,
        *,
        cwd: Path,
        required: tuple[dict[str, Any], ...],
    ) -> None:
        self._cwd = cwd.resolve(strict=True)
        self._required = tuple(dict(item) for item in required)
        self._expected: dict[Path, dict[str, Any]] = {}
        for item in self._required:
            path = Path(item["path"]).resolve(strict=True)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != item["sha256"]:
                raise SelectedSkillReadError(
                    f"required {_label(item)} changed before graph construction: {path}"
                )
            body = _sdk_text_body(raw, path)
            line_count = len(body.split("\n"))
            if line_count != item["line_count"]:
                raise SelectedSkillReadError(
                    f"required {_label(item)} line metadata changed before graph "
                    f"construction: {path}"
                )
            self._expected[path] = {
                **item,
                "rendered": f"@@ lines 1-{line_count} of {line_count} @@\n{body}",
            }
        self._observed: dict[Path, dict[str, str]] = {}
        self._lock = threading.RLock()

    def _missing(self) -> list[Path]:
        return sorted(set(self._expected) - set(self._observed))

    def check_before(self, tool_name: str) -> None:
        """Refuse a guarded handler while any selected read is incomplete."""

        if tool_name in _SAFE_BEFORE_SKILL_READS:
            return
        with self._lock:
            missing = self._missing()
        if missing:
            raise SelectedSkillReadError(
                "selected skill bodies and project-declared documents "
                "must be read successfully before "
                f"{tool_name!r}; missing: {[str(path) for path in missing]}"
            )

    def _selected_path(self, args: Mapping[str, Any]) -> Path | None:
        raw_path = args.get("file_path", args.get("path"))
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        candidate = Path(raw_path)
        candidate = candidate if candidate.is_absolute() else self._cwd / candidate
        lexical = Path(os.path.abspath(candidate))
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        accepted_roots = (self._cwd / "skills", self._cwd / ".agents" / "skills")
        accepted_path = lexical == canonical or any(
            lexical.is_relative_to(root) for root in accepted_roots
        )
        if not accepted_path or canonical not in self._expected:
            return None
        return canonical

    def record_completed_read(
        self,
        tool_call: Mapping[str, Any],
        result: ToolMessage | Command[Any],
    ) -> None:
        """Record one read only after its real handler returned the exact body."""

        if str(tool_call.get("name", "")) != "read_file":
            return
        args = tool_call.get("args", {}) or {}
        if not isinstance(args, Mapping):
            return
        canonical = self._selected_path(args)
        if canonical is None or not isinstance(result, ToolMessage):
            return
        call_id = str(tool_call.get("id", "") or "")
        if not call_id or result.tool_call_id != call_id:
            return
        if str(getattr(result, "status", "") or "").casefold() == "error":
            return
        offset = args.get("offset", 0)
        limit = args.get("limit", 100)
        expected = self._expected[canonical]
        if (
            not isinstance(offset, int)
            or isinstance(offset, bool)
            or offset != 0
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < expected["line_count"]
            or not isinstance(result.content, str)
            or result.content != expected["rendered"]
        ):
            return
        try:
            digest = hashlib.sha256(canonical.read_bytes()).hexdigest()
        except OSError as exc:
            raise SelectedSkillReadError(
                f"required document cannot be revalidated after read: {canonical}"
            ) from exc
        if digest != expected["sha256"]:
            raise SelectedSkillReadError(
                f"required {_label(expected)} changed while it was read: {canonical}"
            )
        with self._lock:
            self._observed.setdefault(
                canonical,
                {
                    "path": str(canonical),
                    "relative_path": expected["relative_path"],
                    "sha256": digest,
                    "kind": str(expected.get("kind", "skill")),
                    "tool_call_id": call_id,
                },
            )

    def evidence(self) -> dict[str, Any]:
        """Return immutable-style telemetry for completed reads in chronology."""

        with self._lock:
            missing = self._missing()
            observed = [dict(item) for item in self._observed.values()]
        if missing:
            raise SelectedSkillReadError(
                "selected skill bodies and project-declared documents "
                "were not read successfully: "
                f"{[str(path) for path in missing]}"
            )
        return {
            "status": "passed",
            "required": [dict(item) for item in self._required],
            "observed": observed,
        }

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """Guard and observe synchronous tool execution."""

        self.check_before(request.tool_call["name"])
        result = handler(request)
        self.record_completed_read(request.tool_call, result)
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[
            [ToolCallRequest], Awaitable[ToolMessage | Command[Any]]
        ],
    ) -> ToolMessage | Command[Any]:
        """Guard and observe asynchronous tool execution."""

        self.check_before(request.tool_call["name"])
        result = await handler(request)
        self.record_completed_read(request.tool_call, result)
        return result
