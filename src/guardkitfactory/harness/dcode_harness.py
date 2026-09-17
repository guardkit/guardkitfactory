"""Required dcode Player construction; invocation remains owned by the factory.

Only this module imports dcode, after validating its launch-time profile. Artifact
aliases are filesystem-tool paths, not shell paths. The supplied factory backend
continues to own ordinary file access and command execution.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from guardkitfactory.harness.player_config import PlayerConfig

logger = logging.getLogger(__name__)
_AGENT = "guardkit-player"
_INSTALL = "install guardkitfactory with Python >=3.12,<4; no fallback engine was started"


def _refuse(message: str) -> None:
    # Lazy import avoids a circular dependency at the construction seam.
    from guardkitfactory.harness.langgraph_harness import LangGraphHarnessError

    raise LangGraphHarnessError(f"dcode Player: {message}")


def _read(path: Path, root: Path) -> bytes:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        _refuse(f"escaping or invalid discovery file: {path}")
    if not resolved.stat().st_mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH):
        _refuse(f"unreadable discovery file: {path}")
    return resolved.read_bytes()


def _tree(path: Path) -> dict[str, str]:
    """Inventory every file, rejecting hidden escapes and unreadable directories."""
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    root = path.resolve(strict=True)
    if not root.is_dir():
        _refuse(f"discovery source is not a directory: {path}")
    result: dict[str, str] = {}

    def walk(directory: Path) -> None:
        mode = directory.stat().st_mode
        if not mode & 0o444 or not mode & 0o111:
            _refuse(f"unreadable discovery directory: {directory}")
        for child in sorted(directory.iterdir()):
            # A selected top-level seed link is supported; nested links make the
            # effective skill contents ambiguous and are deliberately refused.
            if child.is_symlink():
                _refuse(f"symlink inside discovery source: {child}")
            if child.is_dir():
                walk(child)
            else:
                result[str(child.relative_to(root))] = hashlib.sha256(
                    _read(child, root)
                ).hexdigest()

    walk(root)
    return result


def _validate_launch(config: PlayerConfig) -> Path:
    if not (3, 12) <= sys.version_info[:2] < (4, 0):
        _refuse(f"unsupported interpreter; {_INSTALL}")
    if importlib.util.find_spec("deepagents_code") is None:
        _refuse(f"required dependency is not installed; {_INSTALL}")
    profile = config.dcode_home
    configured = os.environ.get("DEEPAGENTS_HOME", "")
    if profile is None or not Path(configured).is_absolute():
        _refuse("set absolute DEEPAGENTS_HOME to the selected fresh run profile before import")
    if Path(configured).resolve(strict=True) != profile:
        _refuse("DEEPAGENTS_HOME does not match the selected Player profile")
    if profile == Path.home().resolve() or profile == Path("/"):
        _refuse("dcode_home must be a dedicated run profile")
    if os.environ.get("DEEPAGENTS_CODE_OFFLINE") != "1":
        _refuse("DEEPAGENTS_CODE_OFFLINE=1 is required")
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        if os.environ.get(name, "false").lower() not in {"false", "0", ""}:
            _refuse(f"{name} must be disabled for the Player run")
    # Permit only the empty directories/files dcode itself creates. This blocks
    # config, dotenv, hooks, plugins, credentials and another agent's profile.
    files = _tree(profile)
    if files and files != {f"{_AGENT}/AGENTS.md": hashlib.sha256(b"").hexdigest()}:
        _refuse("run profile contains unexpected configuration or nonempty memory")
    return profile


def _validate_model(model: Any) -> dict[str, Any]:
    from langchain_openai.chat_models.base import ChatOpenAI

    expected = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if not isinstance(model, ChatOpenAI) or model.use_responses_api is not False:
        _refuse("requires a resolved local ChatOpenAI using ChatCompletions; no model fallback")
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
        _refuse("model endpoint does not match the accepted local OPENAI_BASE_URL")
    if not model.model_name or ":" in model.model_name:
        _refuse("requires an explicit local model alias")
    return {
        "alias": model.model_name,
        "endpoint": actual,
        "transport": "chat/completions",
        "temperature": model.temperature,
        "max_tokens": model.max_tokens,
        "profile": model.profile,
        "provider_retries": model.max_retries,
        "model_retries": 0,
        "cli_max_retries": 0,
    }


class _DiscoveryWarnings(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _inventory(config: PlayerConfig, context: Any) -> dict[str, Any]:
    from deepagents_code._paths import (
        get_built_in_skills_dir,
        get_user_agent_md_path,
        get_user_agents_dir,
    )
    from deepagents_code.agent import get_skill_sources
    from deepagents_code.plugins import discover_plugins
    from deepagents_code.subagents import list_subagents

    cwd = config.cwd
    selected = (cwd / "skills").resolve()
    if config.skills and config.skills != (selected,):
        _refuse("only selected root skills/ is supported")
    if config.skills:
        link = cwd / ".agents" / "skills"
        if not link.is_symlink() or os.readlink(link) != "../skills":
            _refuse("selected skills require .agents/skills -> ../skills")
        if not selected.is_relative_to(cwd):
            _refuse("selected skills escape the task worktree")
    plugins = discover_plugins()
    if plugins.plugins or plugins.warnings:
        _refuse(f"unexpected plugins or discovery warnings: {plugins.warnings!r}")
    agents = [get_user_agents_dir(_AGENT), context.project_agents_dir()]
    definitions = {str(p): _tree(p) for p in agents if p is not None}
    if any(definitions.values()) or list_subagents(
        user_agents_dir=agents[0], project_agents_dir=agents[1]
    ):
        _refuse("custom subagents are not supported; retain built-in general-purpose only")
    builtins = get_built_in_skills_dir().resolve(strict=True)
    sources = []
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    for raw, label in get_skill_sources(assistant_id=_AGENT, project_context=context):
        path = Path(raw)
        files = _tree(path)
        canonical = path.resolve()
        allowed = canonical == builtins or (bool(config.skills) and canonical == selected)
        if files and not allowed:
            _refuse(f"unexpected skill discovery source: {path}")
        if files and canonical in seen_paths:
            _refuse(f"duplicate skill discovery source: {path}")
        if files:
            seen_paths.add(canonical)
        if files:
            from deepagents.backends.filesystem import FilesystemBackend
            from deepagents.middleware import skills as sdk_skills

            handler = _DiscoveryWarnings()
            sdk_logger = logging.getLogger(sdk_skills.__name__)
            sdk_logger.addHandler(handler)
            try:
                loaded, error = sdk_skills._list_skills_with_errors(
                    FilesystemBackend(virtual_mode=False), str(canonical)
                )
            finally:
                sdk_logger.removeHandler(handler)
            if error or handler.messages:
                _refuse(f"skill discovery warnings for {path}: {error or handler.messages}")
            expected = {
                (canonical / relative).resolve()
                for relative in files
                if Path(relative).name == "SKILL.md"
            }
            if {Path(skill["path"]).resolve() for skill in loaded} != expected:
                _refuse(f"skill discovery skipped selected files: {path}")
            for skill in loaded:
                name = skill["name"]
                if name in seen_names:
                    _refuse(f"duplicate discovered skill name: {name}")
                seen_names.add(name)
        sources.append(
            {
                "path": str(canonical),
                "label": label,
                "state": "present" if path.exists() else "absent",
                "files": files,
            }
        )
    if config.skills and selected not in seen_paths:
        _refuse("selected skills were not discovered")
    # Inspect selected instruction sources directly so an optional memory
    # middleware cannot be the only route by which repository guidance reaches
    # the Player. Their contents are also supplied in the invocation prompt.
    instructions = {
        str(path): hashlib.sha256(_read(path, cwd)).hexdigest()
        for path in config.repository_instructions
    }
    discovered = tuple(p.resolve() for p in context.project_agent_md_paths())
    if config.memory and discovered != config.memory:
        _refuse("project memory discovery does not match the selected sources")
    memory = {str(path): hashlib.sha256(_read(path, cwd)).hexdigest() for path in config.memory}
    user_memory = get_user_agent_md_path(_AGENT)
    if user_memory.exists() or user_memory.is_symlink():
        if _read(user_memory, config.dcode_home) != b"":
            _refuse("profile AGENTS.md must remain empty")
    return {
        "skills": sources,
        "memory": memory,
        "repository_instructions": instructions,
        "declared_commands": dict(config.declared_commands),
        "protected_paths": [str(path) for path in config.protected_paths],
        "agents": definitions,
        "plugins": [],
        "warnings": [],
        "subagents": ["general-purpose"],
    }


def _artifact_backend(backend: Any, cwd: Path) -> Any:
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
        target = cwd / name
        if target.is_symlink():
            _refuse(f"artifact directory must not be a symlink: {target}")
        target.mkdir(exist_ok=True)
        if target.resolve(strict=True) != target or not target.is_dir():
            _refuse(f"invalid artifact directory: {target}")
        _tree(target)
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
    """Construct dcode lazily after the harness's shared worktree checks."""
    profile = _validate_launch(config)
    settings = _validate_model(model)
    from deepagents_code._paths import PATHS
    from deepagents_code.agent import create_cli_agent
    from deepagents_code.config import MODEL_RETRIES_ATTR
    from deepagents_code.project_utils import ProjectContext

    if PATHS.profile.root != profile:
        _refuse("already-imported dcode profile differs; start a new process for this run")
    # dcode's auxiliary summarizer otherwise defaults to five extra retries for
    # prebuilt models. A shallow copy preserves the factory-owned clients and
    # every generation setting without changing the caller's model instance.
    model = model.model_copy()
    object.__setattr__(model, MODEL_RETRIES_ATTR, 0)
    context = ProjectContext(user_cwd=cwd, project_root=cwd)
    before = _inventory(config, context)
    adapted = _artifact_backend(backend, cwd)
    graph, effective = create_cli_agent(
        model=model,
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
        environ=dict(os.environ),
    )
    after = _inventory(config, context)
    _validate_launch(config)
    if before != after:
        _refuse("discovery sources changed during graph construction")
    tools = sorted(graph.nodes["tools"].bound.tools_by_name)
    evidence = {
        "discovery": after,
        "model": settings,
        "tools": tools,
        "artifacts": {
            f"/{name}/": str(cwd / name) for name in ("conversation_history", "large_tool_results")
        },
    }
    # Diagnostics stay on the graph; the factory retains its shared invoke and
    # cancellation ownership, with no wrapper graph or additional task.
    graph.guardkit_dcode_evidence = evidence
    graph.guardkit_dcode_backend = effective
    logger.info("dcode Player construction inventory: %s", evidence)
    return graph
