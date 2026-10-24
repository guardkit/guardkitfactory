"""Reminder to read every required project document before running commands.

The required set is the selected skill bodies plus the mandatory supporting
documents the project declared. One gate covers both; there is no second
gate and nothing here parses Markdown links. The gate nudges and records. It
never ends a turn: a document that was not read is written down as such in
the evidence, and the work goes on.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from guardkitfactory.harness.code_search_tools import TOOL_NAMES as _CODE_SEARCH_TOOLS

logger = logging.getLogger(__name__)

# The code search tools only read, like grep and glob (12 October 2026).
_SAFE_BEFORE_SKILL_READS = {"read_file", "ls", "glob", "grep", "write_todos", *_CODE_SEARCH_TOOLS}

# Early guarded calls answered with an error result in one turn. After that
# the call runs, so a model that will not read is not held up for the rest of
# the turn; the evidence still says what was not read.
MAX_EARLY_REFUSALS = 3


def refusal_prefix(tool_name: str) -> str:
    """The opening words of the error result for a call made too early."""

    return (
        f"{tool_name!r} was not run. Read these required documents in full "
        "before running commands: "
    )


class SelectedSkillReadMiddleware(AgentMiddleware):
    """Answer coding tools with an error until the required reads are done."""

    name = "guardkitfactory-selected-skill-reads"

    def __init__(
        self,
        *,
        cwd: Path,
        required: tuple[dict[str, Any], ...],
    ) -> None:
        self._cwd = cwd.resolve(strict=True)
        self._required = tuple(dict(item) for item in required)
        self._expected: dict[Path, dict[str, Any]] = {
            Path(item["path"]).resolve(): dict(item) for item in self._required
        }
        self._observed: dict[Path, dict[str, Any]] = {}
        self._refusals = 0
        self._lock = threading.RLock()

    def _missing(self) -> list[Path]:
        return sorted(set(self._expected) - set(self._observed))

    def _missing_before(self, tool_name: str) -> list[Path]:
        """Return the unread documents that hold ``tool_name`` back now."""

        if tool_name in _SAFE_BEFORE_SKILL_READS:
            return []
        with self._lock:
            return self._missing()

    def refuse_early_call(self, tool_call: Mapping[str, Any]) -> ToolMessage | None:
        """Answer a guarded call made too early with an error tool result.

        The call is not run. The model reads the error, reads the documents
        and retries in the same turn. After ``MAX_EARLY_REFUSALS`` such
        answers in one turn the call runs, and ``evidence()`` records what was
        still unread.
        """

        name = str(tool_call.get("name", "") or "")
        with self._lock:
            missing = self._missing_before(name)
            if not missing:
                return None
            self._refusals += 1
            refusals = self._refusals
        if refusals > MAX_EARLY_REFUSALS:
            logger.warning(
                "required documents still unread (%d); running tool %r "
                "(early call %d in this turn)",
                len(missing),
                name,
                refusals,
            )
            return None
        logger.info(
            "required documents unread; refused tool %r (%d unread, refusal %d of %d)",
            name,
            len(missing),
            refusals,
            MAX_EARLY_REFUSALS,
        )
        return ToolMessage(
            content=(
                refusal_prefix(name)
                + f"{', '.join(str(path) for path in missing)}. Then retry."
            ),
            tool_call_id=str(tool_call.get("id", "") or ""),
            name=name,
            status="error",
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
        """Record a read of a required document that returned without error.

        The offset and limit the model used are kept so a partial read can be
        seen in the evidence; it still counts as a read.
        """

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
        expected = self._expected[canonical]
        with self._lock:
            self._observed.setdefault(
                canonical,
                {
                    "path": str(canonical),
                    "relative_path": expected.get("relative_path"),
                    "sha256": expected.get("sha256"),
                    "kind": str(expected.get("kind", "skill")),
                    "tool_call_id": call_id,
                    "offset": args.get("offset", 0),
                    "limit": args.get("limit", 100),
                },
            )

    def evidence(self) -> dict[str, Any]:
        """Return telemetry for the reads seen, saying so when some are missing."""

        with self._lock:
            missing = self._missing()
            observed = [dict(item) for item in self._observed.values()]
        if missing:
            logger.warning(
                "required documents not read: %s", [str(path) for path in missing]
            )
        return {
            "status": "incomplete" if missing else "passed",
            "required": [dict(item) for item in self._required],
            "observed": observed,
            "missing": [str(path) for path in missing],
        }

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """Guard and observe synchronous tool execution."""

        refusal = self.refuse_early_call(request.tool_call)
        if refusal is not None:
            return refusal
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

        refusal = self.refuse_early_call(request.tool_call)
        if refusal is not None:
            return refusal
        result = await handler(request)
        self.record_completed_read(request.tool_call, result)
        return result
