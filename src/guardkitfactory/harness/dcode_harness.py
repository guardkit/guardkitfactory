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
from collections.abc import Mapping
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


def _required_entry(canonical: Path, *, config: PlayerConfig, kind: str) -> dict[str, Any]:
    """Describe one document the Player must read in full before it works."""

    body = _read(canonical, config.cwd)
    try:
        line_count = len(body.decode("utf-8").splitlines())
    except UnicodeDecodeError:
        label = "selected skill" if kind == "skill" else "declared document"
        _refuse(f"{label} is not valid UTF-8: {canonical}")
    return {
        "path": str(canonical),
        "relative_path": str(canonical.relative_to(config.cwd)),
        "sha256": hashlib.sha256(body).hexdigest(),
        "line_count": line_count,
        "kind": kind,
    }


def required_skill_reads(config: PlayerConfig) -> tuple[dict[str, Any], ...]:
    """Return every document the Player must read: skills, then declarations.

    The selected ``SKILL.md`` bodies come first and carry ``kind="skill"``; the
    project-declared mandatory supporting documents follow and carry
    ``kind="declared_document"``. Nothing parses Markdown, so an optional link
    inside a skill body stays optional — only what the project declared is
    required.
    """

    skill_reads: list[dict[str, Any]] = []
    for source in config.skills:
        source_root = source.resolve(strict=True)
        for path in sorted(source_root.rglob("SKILL.md")):
            canonical = path.resolve(strict=True)
            if not canonical.is_relative_to(source_root) or not canonical.is_file():
                _refuse(f"escaping or invalid selected skill document: {path}")
            skill_reads.append(_required_entry(canonical, config=config, kind="skill"))
    if config.skills and not skill_reads:
        _refuse("selected skills contain no SKILL.md documents")

    declared_reads: list[dict[str, Any]] = []
    for document in config.required_documents:
        canonical = document.resolve(strict=True)
        if not canonical.is_relative_to(config.cwd) or not canonical.is_file():
            _refuse(f"escaping or invalid declared document: {document}")
        declared_reads.append(
            _required_entry(canonical, config=config, kind="declared_document")
        )
    return tuple(skill_reads) + tuple(declared_reads)


def validate_skill_reads(
    result: Any,
    *,
    config: PlayerConfig,
    required: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Audit a completed transcript without counting future tool results."""

    if not required:
        return {"status": "not_required", "required": [], "observed": []}
    if not isinstance(result, Mapping):
        _refuse("selected skill reads cannot be proved from a non-mapping result")

    from langchain_core.messages import ToolMessage

    from guardkitfactory.harness.skill_read_middleware import (
        SelectedSkillReadError,
        SelectedSkillReadMiddleware,
    )

    gate = SelectedSkillReadMiddleware(cwd=config.cwd, required=required)
    pending: dict[str, Mapping[str, Any]] = {}
    try:
        for message in result.get("messages", []) or []:
            if isinstance(message, ToolMessage):
                call = pending.pop(str(message.tool_call_id or ""), None)
                if call is not None:
                    gate.record_completed_read(call, message)
                continue
            for call in getattr(message, "tool_calls", None) or []:
                if not isinstance(call, Mapping):
                    continue
                name = str(call.get("name", "") or "")
                gate.check_before(name)
                call_id = str(call.get("id", "") or "")
                if name == "read_file" and call_id:
                    pending[call_id] = call
        telemetry = gate.evidence()
    except SelectedSkillReadError as exc:
        _refuse(str(exc))
    logger.info("dcode Player selected-skill transcript audit: %s", telemetry)
    return telemetry


_CLEAN_PROFILE = {f"{_AGENT}/AGENTS.md": hashlib.sha256(b"").hexdigest()}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profile_inventory(profile: Path) -> list[dict[str, Any]]:
    """Describe every entry in a run profile without exposing its contents.

    Each entry gives the path relative to the profile, its file type, its size
    and, for regular files, its SHA-256. Links are recorded, never followed, and
    an unreadable entry is recorded with the error's type rather than refused,
    so the inventory itself never fails a launch.
    """

    entries: list[dict[str, Any]] = []

    def record(path: Path) -> None:
        relative = str(path.relative_to(profile)) if path != profile else "."
        entry: dict[str, Any] = {"path": relative, "type": "other", "size": None, "sha256": None}
        try:
            status = path.lstat()
        except OSError as exc:
            entry["error"] = type(exc).__name__
            entries.append(entry)
            return
        mode = status.st_mode
        if stat.S_ISLNK(mode):
            entry.update(type="symlink", size=status.st_size)
        elif stat.S_ISDIR(mode):
            entry["type"] = "directory"
        elif stat.S_ISREG(mode):
            entry.update(type="file", size=status.st_size)
            try:
                entry["sha256"] = _sha256_file(path)
            except OSError as exc:
                entry["error"] = type(exc).__name__
        if path != profile:
            entries.append(entry)
        if entry["type"] == "directory":
            try:
                children = sorted(path.iterdir())
            except OSError as exc:
                entry["error"] = type(exc).__name__
                if path == profile:
                    entries.append(entry)
                return
            for child in children:
                record(child)
        elif path == profile:
            entries.append(entry)

    try:
        profile.lstat()
    except FileNotFoundError:
        return entries
    record(profile)
    return entries


def _unexpected_profile_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Entries the launch check does not permit: anything but the empty memory file."""

    def permitted(entry: dict[str, Any]) -> bool:
        if "error" in entry:
            return False
        if entry["type"] == "directory":
            return True
        return entry["type"] == "file" and _CLEAN_PROFILE.get(entry["path"]) == entry["sha256"]

    return [entry for entry in entries if not permitted(entry)]


def _describe_entries(entries: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{entry['path']} ({entry['type']}, size={entry['size']}, "
        f"sha256={entry['sha256']}"
        + (f", error={entry['error']}" if "error" in entry else "")
        + ")"
        for entry in entries
    )


def _refuse_launch(
    message: str, profile: Path | None, entries: list[dict[str, Any]]
) -> NoReturn:
    """Refuse a launch that would be refused the same way on every later turn.

    Used for the process-wide launch conditions (interpreter, dependency,
    profile selection, offline and tracing settings) and for the profile's own
    contents; ``entries`` is empty unless the profile's contents are at fault.
    """
    from guardkitfactory.harness.langgraph_harness import PlayerLaunchRefused

    unexpected = _unexpected_profile_entries(entries)
    logger.error(
        "dcode Player launch refused: %s; profile=%s unexpected entries=%s",
        message,
        profile,
        unexpected,
    )
    detail = (
        f"; unexpected profile entries: {_describe_entries(unexpected)}" if unexpected else ""
    )
    raise PlayerLaunchRefused(
        f"dcode Player: {message}{detail}",
        profile="" if profile is None else str(profile),
        entries=unexpected,
    )


def log_profile_inventory(profile: Path, *, cwd: Path) -> list[dict[str, Any]]:
    """Log the profile as one invocation left it, so a later refusal can be traced."""

    entries = profile_inventory(profile)
    logger.info(
        "dcode Player post-invocation profile inventory: cwd=%s profile=%s "
        "unexpected=%s entries=%s",
        cwd,
        profile,
        _unexpected_profile_entries(entries),
        entries,
    )
    return entries


def _validate_launch(config: PlayerConfig) -> Path:
    # Every refusal here is fixed for this process and never reaches the
    # model, so each is raised as PlayerLaunchRefused rather than left to be
    # retried as if it were an implementation failure.
    profile = config.dcode_home
    if not (3, 12) <= sys.version_info[:2] < (4, 0):
        _refuse_launch(f"unsupported interpreter; {_INSTALL}", profile, [])
    if importlib.util.find_spec("deepagents_code") is None:
        _refuse_launch(f"required dependency is not installed; {_INSTALL}", profile, [])
    configured = os.environ.get("DEEPAGENTS_HOME", "")
    if profile is None or not Path(configured).is_absolute():
        _refuse_launch(
            "set absolute DEEPAGENTS_HOME to the selected fresh run profile before import",
            profile,
            [],
        )
    if Path(configured).resolve(strict=True) != profile:
        _refuse_launch("DEEPAGENTS_HOME does not match the selected Player profile", profile, [])
    if profile == Path.home().resolve() or profile == Path("/"):
        _refuse_launch("dcode_home must be a dedicated run profile", profile, [])
    if os.environ.get("DEEPAGENTS_CODE_OFFLINE") != "1":
        _refuse_launch("DEEPAGENTS_CODE_OFFLINE=1 is required", profile, [])
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        if os.environ.get(name, "false").lower() not in {"false", "0", ""}:
            _refuse_launch(f"{name} must be disabled for the Player run", profile, [])
    # Permit only the empty directories/files dcode itself creates. This blocks
    # config, dotenv, hooks, plugins, credentials and another agent's profile.
    # The offending entries are described in the refusal.
    from guardkitfactory.harness.langgraph_harness import LangGraphHarnessError

    try:
        files = _tree(profile)
    except LangGraphHarnessError as exc:
        _refuse_launch(
            str(exc).removeprefix("dcode Player: "), profile, profile_inventory(profile)
        )
    if files and files != _CLEAN_PROFILE:
        _refuse_launch(
            "run profile contains unexpected configuration or nonempty memory",
            profile,
            profile_inventory(profile),
        )
    return profile


def _validate_model(model: Any) -> dict[str, Any]:
    from langchain_openai.chat_models.base import ChatOpenAI

    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

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
        # True when each step's earlier thinking is sent back to the model.
        "reasoning_replay": isinstance(model, ReasoningReplayChatOpenAI),
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
            _refuse_launch(
                "profile AGENTS.md must remain empty",
                config.dcode_home,
                profile_inventory(config.dcode_home),
            )
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
    from deepagents_code._env_vars import EXPERIMENTAL
    from deepagents_code.agent import create_cli_agent
    from deepagents_code.config import MODEL_RETRIES_ATTR
    from deepagents_code.extensions.registry import (
        ExtensionRegistry,
        SourceInfo,
        SourceScope,
    )
    from deepagents_code.project_utils import ProjectContext

    from guardkitfactory.harness.skill_read_middleware import (
        SelectedSkillReadMiddleware,
    )

    if PATHS.profile.root != profile:
        _refuse_launch(
            "already-imported dcode profile differs; start a new process for this run",
            profile,
            [],
        )
    # dcode's auxiliary summarizer otherwise defaults to five extra retries for
    # prebuilt models. A shallow copy preserves the factory-owned clients and
    # every generation setting without changing the caller's model instance.
    model = model.model_copy()
    object.__setattr__(model, MODEL_RETRIES_ATTR, 0)
    context = ProjectContext(user_cwd=cwd, project_root=cwd)
    before = _inventory(config, context)
    adapted = _artifact_backend(backend, cwd)
    required = required_skill_reads(config)
    skill_gate = SelectedSkillReadMiddleware(cwd=config.cwd, required=required)
    registry = ExtensionRegistry()
    registry.add_middleware(
        skill_gate,
        SourceInfo(
            path=Path(__file__),
            source_id="guardkitfactory-selected-skill-reads",
            scope=SourceScope.TEMPORARY,
        ),
    )
    dcode_environment = dict(os.environ)
    dcode_environment[EXPERIMENTAL] = "1"
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
        extension_registry=registry,
        environ=dcode_environment,
    )
    after = _inventory(config, context)
    _validate_launch(config)
    if before != after:
        _refuse("discovery sources changed during graph construction")
    tools = sorted(graph.nodes["tools"].bound.tools_by_name)
    evidence = {
        "discovery": after,
        "required_skill_reads": [dict(item) for item in required],
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
    graph.guardkit_skill_read_gate = skill_gate
    logger.info("dcode Player construction inventory: %s", evidence)
    return graph
