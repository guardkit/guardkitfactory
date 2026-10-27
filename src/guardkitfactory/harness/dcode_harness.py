"""Required dcode Player construction; invocation remains owned by the factory.

Only this module imports dcode, after checking the launch settings that keep
the Player local and on its own run profile. Artifact aliases are
filesystem-tool paths, not shell paths; they lead to the factory backend's
private folder outside the worktree. The supplied factory backend continues to
own ordinary file access and command execution.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

from guardkitfactory.harness.player_config import PlayerConfig

logger = logging.getLogger(__name__)

_AGENT = "guardkit-player"
_INSTALL = "install guardkitfactory with Python >=3.12,<4; no fallback engine was started"


def _refuse(message: str) -> NoReturn:
    # Lazy import avoids a circular dependency at the construction seam.
    from guardkitfactory.harness.langgraph_harness import LangGraphHarnessError

    raise LangGraphHarnessError(f"dcode Player: {message}")


def required_skill_reads(config: PlayerConfig) -> tuple[dict[str, Any], ...]:
    """Every document the Player is asked to read: skills, then declarations.

    The selected ``SKILL.md`` bodies come first and carry ``kind="skill"``; the
    project-declared supporting documents follow and carry
    ``kind="declared_document"``. They are named in the Player's prompt; since
    27 October 2026 nothing checks that they were read.
    """

    reads: list[dict[str, Any]] = []
    for source in config.skills:
        for path in sorted(source.rglob("SKILL.md")):
            if path.is_file():
                reads.append(_read_entry(path.resolve(), config=config, kind="skill"))
    for document in config.required_documents:
        reads.append(_read_entry(document, config=config, kind="declared_document"))
    return tuple(reads)


def _read_entry(path: Path, *, config: PlayerConfig, kind: str) -> dict[str, Any]:
    relative = path.relative_to(config.cwd) if path.is_relative_to(config.cwd) else path
    return {"path": str(path), "relative_path": str(relative), "kind": kind}


def _refuse_launch(message: str, profile: Path | None) -> NoReturn:
    """Refuse a launch that would be refused the same way on every later turn.

    Used for the process-wide launch conditions that remain: the dependency,
    the profile selection (never the owner's own settings) and the offline,
    tracing and local-model settings.
    """
    from guardkitfactory.harness.langgraph_harness import PlayerLaunchRefused

    logger.error("dcode Player launch refused: %s; profile=%s", message, profile)
    raise PlayerLaunchRefused(
        f"dcode Player: {message}", profile="" if profile is None else str(profile)
    )


def _validate_launch(config: PlayerConfig) -> Path:
    # Every refusal here is fixed for this process and never reaches the
    # model, so each is raised as PlayerLaunchRefused rather than left to be
    # retried as if it were an implementation failure. They keep the Player
    # offline, untraced and on its own run profile, never the owner's own
    # settings and credentials. The interpreter is the install rule's
    # (pyproject ``requires-python``), not checked again.
    profile = config.dcode_home
    if importlib.util.find_spec("deepagents_code") is None:
        _refuse_launch(f"required dependency is not installed; {_INSTALL}", profile)
    configured = os.environ.get("DEEPAGENTS_HOME", "")
    if profile is None or not Path(configured).is_absolute():
        _refuse_launch(
            "set absolute DEEPAGENTS_HOME to the selected fresh run profile before import",
            profile,
        )
    if Path(configured).resolve(strict=True) != profile:
        _refuse_launch("DEEPAGENTS_HOME does not match the selected Player profile", profile)
    if profile == Path.home().resolve() or profile == Path("/"):
        _refuse_launch("dcode_home must be a dedicated run profile", profile)
    if os.environ.get("DEEPAGENTS_CODE_OFFLINE") != "1":
        _refuse_launch("DEEPAGENTS_CODE_OFFLINE=1 is required", profile)
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        if os.environ.get(name, "false").lower() not in {"false", "0", ""}:
            _refuse_launch(f"{name} must be disabled for the Player run", profile)
    return profile


def _validate_model(model: Any, config: PlayerConfig) -> dict[str, Any]:
    # The model and OPENAI_BASE_URL are fixed for the process, so a mismatch
    # would be refused on every turn: these refusals are typed launch refusals.
    from langchain_openai.chat_models.base import ChatOpenAI

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    expected = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if not isinstance(model, ChatOpenAI) or model.use_responses_api is not False:
        _refuse_launch(
            "requires a resolved local ChatOpenAI using ChatCompletions; no model fallback",
            config.dcode_home,
        )
    actual = str(model.openai_api_base or "").rstrip("/")
    parsed = urlsplit(actual)
    if (
        not expected
        or actual != expected
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.hostname.endswith("openai.com")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        _refuse_launch(
            "model endpoint does not match the accepted local OPENAI_BASE_URL",
            config.dcode_home,
        )
    return {
        "alias": model.model_name,
        "endpoint": actual,
        "transport": "chat/completions",
        # True when each step's earlier thinking is sent back to the model.
        "reasoning_replay": isinstance(model, ReasoningReplayChatOpenAI),
        "temperature": model.temperature,
        "max_tokens": model.max_tokens,
        "profile": model.profile,
        "provider_retries": model.max_retries,
        "model_retries": 0,
        "cli_max_retries": 0,
    }


_SUMMARY_NOTICE_LOGGER = "deepagents_code.goal_state_notice"
_SUMMARY_DISCARD = "Discarding malformed `_summarization_event` (cutoff_index=%s, "
_SUMMARY_LINE_INTERVAL = 60.0
_SUMMARY_FILTER_LOCK = threading.Lock()
# The only upstream caller where the record is the false alarm: it sees the
# request after the summariser has shortened it. The same record from
# `GoalToolsMiddleware._notice_update` (before_model) reads the full saved
# history, so there a cutoff past the end means the summary really is dropped.
_SUMMARY_FALSE_ALARM_CALLER = "GoalToolsMiddleware._request_with_goal_notice"
_SUMMARY_CALLER_DEPTH = 12


def _from_model_request() -> bool:
    """Whether the record being filtered was logged from the shortened request.

    Walks at most a dozen frames (filter, logging internals, the upstream log
    helper, its caller) and never raises; anything unexpected means "no", so
    the record keeps its upstream wording.
    """
    try:
        frame = sys._getframe(1)
        for _ in range(_SUMMARY_CALLER_DEPTH):
            if frame is None:
                return False
            code = frame.f_code
            if getattr(code, "co_qualname", code.co_name) == _SUMMARY_FALSE_ALARM_CALLER:
                return True
            frame = frame.f_back
    except Exception:  # noqa: BLE001 - a log filter must never break logging
        return False
    return False


class _SummaryFalseAlarm(logging.Filter):
    """Reword dcode's false "summary dropped" warning, at most once a minute.

    In the pinned deepagents-code (0.1.69 on deepagents 0.7.14) the goal-state
    middleware sits inside the summariser, so after every summary it compares
    the full-history cutoff with the already-shortened request, calls a valid
    cutoff out of range and warns that the full history is re-sent. It is not:
    the model receives the summary plus recent messages (pinned in
    tests/harness/test_dcode_summary_window.py). On 19 October 2026 the line
    misled an investigation and repeated 842 times in one build.

    Only that exact record with a whole-number cutoff above the message count
    (the false-alarm shape), logged from the request path
    (`_request_with_goal_notice`), is reworded, at INFO; one line is kept per
    minute per process, with the count of those not shown, so a genuinely
    broken checkpoint seen there still leaves a trace. The same record from
    `_notice_update` (before_model), where the summary really is dropped, and
    every other record from the logger, including a non-numeric or negative
    cutoff, pass unchanged as upstream wrote them and do not count against the
    minute.
    """

    def __init__(
        self,
        version: str | None = None,
        clock: Any = time.monotonic,
        caller: Any = _from_model_request,
    ) -> None:
        super().__init__()
        self._caller = caller
        self._version = version  # looked up on first use, so installing stays cheap
        self._clock = clock
        self._lock = threading.Lock()
        self._last: float | None = None
        self._hidden = 0

    @staticmethod
    def _numbers(record: logging.LogRecord) -> tuple[int, int] | None:
        if not isinstance(record.msg, str) or not record.msg.startswith(_SUMMARY_DISCARD):
            return None
        args = record.args
        if not isinstance(args, tuple) or len(args) != 2:
            return None
        detail, count = args
        if not isinstance(detail, str) or type(count) is not int:
            return None
        try:
            cutoff = int(detail)
        except ValueError:
            return None
        if str(cutoff) != detail or cutoff <= count:
            return None
        return cutoff, count

    def filter(self, record: logging.LogRecord) -> bool:
        numbers = self._numbers(record)
        if numbers is None or not self._caller():
            return True
        with self._lock:
            now = self._clock()
            if self._last is not None and now - self._last < _SUMMARY_LINE_INTERVAL:
                self._hidden += 1
                return False
            self._last = now
            hidden, self._hidden = self._hidden, 0
            if self._version is None:
                self._version = _installed_dcode_version()
        cutoff, count = numbers
        record.msg = (
            "Known false alarm from deepagents-code %s, not a dropped summary: its "
            "goal-state check saw an already-shortened request (cutoff_index=%d, "
            'messages=%d) and logged "Discarding malformed `_summarization_event`". '
            "The model still received the summary and the recent messages; nothing "
            "was re-sent. Shown at most once a minute; %d more since the last line."
        )
        record.args = (self._version, cutoff, count, hidden)
        record.levelno = logging.INFO
        record.levelname = logging.getLevelName(logging.INFO)
        return True


def _installed_dcode_version() -> str:
    try:
        from importlib.metadata import version

        return version("deepagents-code")
    except Exception:  # noqa: BLE001 - wording only; never break logging
        return "(version unknown)"


def install_summary_warning_filter() -> logging.Filter:
    """Install the reworded summary warning once per process; return the filter."""
    target = logging.getLogger(_SUMMARY_NOTICE_LOGGER)
    with _SUMMARY_FILTER_LOCK:
        for existing in target.filters:
            if isinstance(existing, _SummaryFalseAlarm):
                return existing
        added = _SummaryFalseAlarm()
        target.addFilter(added)
        return added


def _refuse_custom_subagents(context: Any) -> None:
    """Refuse a custom subagent: dcode runs each one on the model its own
    definition names, which could be a hosted model. Only the built-in
    general-purpose subagent, which uses the checked local model, runs."""
    from deepagents_code._paths import get_user_agents_dir
    from deepagents_code.subagents import list_subagents

    if list_subagents(
        user_agents_dir=get_user_agents_dir(_AGENT),
        project_agents_dir=context.project_agents_dir(),
    ):
        _refuse("custom subagents are not supported; retain built-in general-purpose only")


def _artifact_backend(backend: Any, cwd: Path, artifacts: Path) -> Any:
    from deepagents.backends.composite import CompositeBackend
    from deepagents.backends.filesystem import FilesystemBackend
    from deepagents.backends.protocol import SandboxBackendProtocol

    class ArtifactRoutes(CompositeBackend, SandboxBackendProtocol):
        # dcode adds another CompositeBackend. The SDK checks its immediate
        # default's nominal execution protocol, so preserve that capability
        # explicitly while forwarding commands to the unchanged factory backend.
        @property
        def id(self) -> str:
            return f"guardkit-player:{cwd}"

        def execute(self, command: str, *, timeout: int | None = None) -> Any:
            return self.default.execute(command, timeout=timeout)

        async def aexecute(self, command: str, *, timeout: int | None = None) -> Any:
            return await self.default.aexecute(command, timeout=timeout)

    routes = {}
    for name in ("conversation_history", "large_tool_results"):
        target = artifacts / name
        target.mkdir(mode=0o700, exist_ok=True)
        routes[f"/{name}/"] = FilesystemBackend(root_dir=target, virtual_mode=True)
    return ArtifactRoutes(default=backend, routes=routes)


def create_dcode_player(
    *,
    model: Any,
    backend: Any,
    cwd: Path,
    config: PlayerConfig,
    recursion_limit: int | None,
) -> Any:
    """Construct dcode lazily after the harness's launch settings are checked."""
    profile = _validate_launch(config)
    settings = _validate_model(model, config)
    from deepagents_code._env_vars import EXPERIMENTAL
    from deepagents_code._paths import PATHS
    from deepagents_code.agent import create_cli_agent
    from deepagents_code.config import MODEL_RETRIES_ATTR
    from deepagents_code.project_utils import ProjectContext

    from guardkitfactory.harness.code_search_tools import code_search_tools

    if PATHS.profile.root != profile:
        _refuse_launch(
            "already-imported dcode profile differs; start a new process for this run",
            profile,
        )
    # dcode's auxiliary summarizer otherwise defaults to five extra retries for
    # prebuilt models. A shallow copy preserves the factory-owned clients and
    # every generation setting without changing the caller's model instance.
    model = model.model_copy()
    object.__setattr__(model, MODEL_RETRIES_ATTR, 0)
    install_summary_warning_filter()
    context = ProjectContext(user_cwd=cwd, project_root=cwd)
    _refuse_custom_subagents(context)
    # The factory backend's private folder for the model's own working files
    # (``backend_config.model_artifacts_root``), outside the worktree.
    artifacts = Path(backend.artifacts_root)
    adapted = _artifact_backend(backend, cwd, artifacts)
    dcode_environment = dict(os.environ)
    dcode_environment[EXPERIMENTAL] = "1"
    # Read-only code search over this worktree; none when the pinned programs
    # are not installed, and the reason goes into the launch evidence.
    search_tools, search_unavailable = code_search_tools(cwd)
    graph, effective = create_cli_agent(
        model=model,
        tools=search_tools,
        assistant_id=_AGENT,
        sandbox=adapted,
        interactive=False,
        auto_approve=True,
        auto_mode_enabled=False,
        enable_ask_user=False,
        enable_memory=bool(config.memory),
        memory_auto_save=False,
        enable_skills=bool(config.skills),
        enable_shell=True,
        enable_interpreter=False,
        cwd=cwd,
        project_context=context,
        recursion_limit=recursion_limit,
        model_retries=0,
        cli_max_retries=0,
        environ=dcode_environment,
    )
    tools = sorted(graph.nodes["tools"].bound.tools_by_name)
    evidence = {
        "model": settings,
        "tools": tools,
        "code_search": {
            "tools": [tool.name for tool in search_tools],
            "unavailable": search_unavailable,
        },
        "artifacts": {
            f"/{name}/": str(artifacts / name)
            for name in ("conversation_history", "large_tool_results")
        },
    }
    # Diagnostics stay on the graph; the factory retains its shared invoke and
    # cancellation ownership, with no wrapper graph or additional task.
    graph.guardkit_dcode_evidence = evidence
    graph.guardkit_dcode_backend = effective
    logger.info("dcode Player construction inventory: %s", evidence)
    return graph
