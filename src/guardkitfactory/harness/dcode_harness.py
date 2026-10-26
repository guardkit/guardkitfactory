"""Required dcode Player construction; invocation remains owned by the factory.

Only this module imports dcode, after validating its launch-time profile. Artifact
aliases are filesystem-tool paths, not shell paths; they lead to the factory
backend's private folder outside the worktree. The supplied factory backend
continues to own ordinary file access and command execution.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import stat
import sys
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

from guardkitfactory.harness.player_config import PlayerConfig

logger = logging.getLogger(__name__)

# Read directly from os (not through getattr) so the launch guard sees os used
# only through its attributes; 0 where the platform has no such flag.
try:
    _O_CLOEXEC = os.O_CLOEXEC
except AttributeError:  # pragma: no cover - not on every platform
    _O_CLOEXEC = 0
_AGENT = "guardkit-player"
_INSTALL = "install guardkitfactory with Python >=3.12,<4; no fallback engine was started"


def _refuse(message: str) -> NoReturn:
    # Lazy import avoids a circular dependency at the construction seam.
    from guardkitfactory.harness.langgraph_harness import LangGraphHarnessError

    raise LangGraphHarnessError(f"dcode Player: {message}")


def _advise(message: str, advice: list[str] | None = None) -> None:
    """Record a launch finding that does not stop the Player.

    26 October 2026 (step 2): what the launch finds about the project's
    skills, memory and the run profile is logged, and listed in the
    construction evidence's ``warnings`` when ``advice`` is given; the Player
    starts all the same.
    """
    logger.warning("dcode Player launch advice: %s", message)
    if advice is not None:
        advice.append(message)


def _read(path: Path) -> bytes:
    return path.resolve(strict=True).read_bytes()


def _tree(path: Path, advice: list[str] | None = None) -> dict[str, str]:
    """Inventory every file below ``path`` by SHA-256.

    A link inside is not followed, and an unreadable folder or file is left
    out; each is advice, not a refusal (26 October 2026, step 2).
    """
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    try:
        root = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _advise(f"discovery source cannot be resolved ({type(exc).__name__}): {path}", advice)
        return {}
    if not root.is_dir():
        _advise(f"discovery source is not a directory: {path}", advice)
        return {}
    result: dict[str, str] = {}

    def walk(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir())
        except OSError:
            _advise(f"unreadable discovery directory left out: {directory}", advice)
            return
        for child in children:
            if child.is_symlink():
                _advise(f"symlink inside discovery source not followed: {child}", advice)
                continue
            if child.is_dir():
                walk(child)
                continue
            try:
                body = _read(child)
            except OSError:
                _advise(f"unreadable discovery file left out: {child}", advice)
                continue
            result[str(child.relative_to(root))] = hashlib.sha256(body).hexdigest()

    walk(root)
    return result


def _required_entry(canonical: Path, *, config: PlayerConfig, kind: str) -> dict[str, Any]:
    """Describe one document the Player must read in full before it works."""

    body = _read(canonical)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        label = "selected skill" if kind == "skill" else "declared document"
        _advise(f"{label} is not valid UTF-8: {canonical}")
        text = body.decode("utf-8", errors="replace")
    return {
        "path": str(canonical),
        "relative_path": str(canonical.relative_to(config.cwd)),
        "sha256": hashlib.sha256(body).hexdigest(),
        "line_count": len(text.splitlines()),
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
                _advise(f"selected skill document left out (escaping or not a file): {path}")
                continue
            try:
                skill_reads.append(_required_entry(canonical, config=config, kind="skill"))
            except OSError as exc:
                _advise(f"selected skill document left out ({type(exc).__name__}): {path}")
    if config.skills and not skill_reads:
        _advise("selected skills contain no SKILL.md documents")

    declared_reads: list[dict[str, Any]] = []
    for document in config.required_documents:
        try:
            declared_reads.append(
                _required_entry(
                    document.resolve(strict=True), config=config, kind="declared_document"
                )
            )
        except OSError as exc:
            _advise(f"declared document left out ({type(exc).__name__}): {document}")
    return tuple(skill_reads) + tuple(declared_reads)


_CLEAN_PROFILE = {f"{_AGENT}/AGENTS.md": hashlib.sha256(b"").hexdigest()}


# Bounds on the diagnostic profile inventory. It only describes the profile;
# it must never hold up a launch decision or an invocation's return.
_INVENTORY_MAX_ENTRIES = 1000
_INVENTORY_MAX_FILE_BYTES = 16 * 1024 * 1024
_INVENTORY_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_INVENTORY_SECONDS = 2.0
# How long a caller waits for the inventory, which runs on a daemon thread
# because a read can block whatever the in-walk budget says: the launch's
# advice about the profile waits briefly, an invocation's finalisation a
# little longer.
_ADVICE_INVENTORY_SECONDS = 3.0
_POST_INVOCATION_INVENTORY_SECONDS = 5.0
_NOT_REGULAR = "not a regular file when opened"
_TOO_LARGE = "not recorded: too large"
_TIMED_OUT = "not recorded: timed out"
_CHANGED = "not recorded: changed while reading"
_TOO_MANY = "not recorded: too many entries"


class _Budget:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + _INVENTORY_SECONDS
        self.bytes_left = _INVENTORY_MAX_TOTAL_BYTES

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline


def _hash_regular_file(path: Path, entry: dict[str, Any], budget: _Budget) -> None:
    """Hash a file without following a link or blocking on a swapped-in FIFO."""

    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | _O_CLOEXEC
    descriptor = os.open(path, flags)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            entry["error"] = _NOT_REGULAR
            return
        size = status.st_size
        entry["size"] = size
        if size > _INVENTORY_MAX_FILE_BYTES or size > budget.bytes_left:
            entry["error"] = _TOO_LARGE
            return
        digest = hashlib.sha256()
        remaining = size
        while remaining > 0:
            if budget.expired():
                entry["error"] = _TIMED_OUT
                return
            chunk = os.read(descriptor, min(1 << 16, remaining))
            if not chunk:
                entry["error"] = _CHANGED
                return
            digest.update(chunk)
            remaining -= len(chunk)
            budget.bytes_left -= len(chunk)
        # A file still growing has more than fstat reported: its hash would
        # describe a prefix, so it is not recorded.
        if os.read(descriptor, 1):
            entry["error"] = _CHANGED
            return
        entry["sha256"] = digest.hexdigest()
    finally:
        os.close(descriptor)


def _walk_profile(profile: Path, entries: list[dict[str, Any]], current: list[str]) -> None:
    """Fill ``entries`` in walk order; ``current`` names the entry in progress."""

    budget = _Budget()

    def record(path: Path) -> bool:
        """Record ``path`` (and below); return False once a bound stops the walk."""
        current[0] = str(path.relative_to(profile)) if path != profile else "."
        if len(entries) >= _INVENTORY_MAX_ENTRIES or budget.expired():
            entries.append(
                {
                    "path": str(path.relative_to(profile)) if path != profile else ".",
                    "type": "other",
                    "size": None,
                    "sha256": None,
                    "error": _TOO_MANY if len(entries) >= _INVENTORY_MAX_ENTRIES else _TIMED_OUT,
                }
            )
            return False
        relative = str(path.relative_to(profile)) if path != profile else "."
        entry: dict[str, Any] = {"path": relative, "type": "other", "size": None, "sha256": None}
        try:
            status = path.lstat()
        except OSError as exc:
            entry["error"] = type(exc).__name__
            entries.append(entry)
            return True
        mode = status.st_mode
        if stat.S_ISLNK(mode):
            entry.update(type="symlink", size=status.st_size)
        elif stat.S_ISDIR(mode):
            entry["type"] = "directory"
        elif stat.S_ISREG(mode):
            entry.update(type="file", size=status.st_size)
            try:
                _hash_regular_file(path, entry, budget)
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
                return True
            for child in children:
                if not record(child):
                    return False
        elif path == profile:
            entries.append(entry)
        return True

    try:
        profile.lstat()
    except FileNotFoundError:
        return
    record(profile)


def _bounded_inventory(profile: Path, seconds: float) -> tuple[list[dict[str, Any]], bool]:
    """Take the inventory on a daemon thread, waiting at most ``seconds``.

    Returns the entries and whether the walk finished. On expiry the entries
    gathered so far are kept and the entry in progress is marked
    "not recorded: timed out"; the thread is abandoned.
    """

    entries: list[dict[str, Any]] = []
    current = ["."]
    finished = threading.Event()

    def take() -> None:
        try:
            _walk_profile(profile, entries, current)
        except Exception as exc:  # noqa: BLE001 - diagnostics never raise
            entries.append(
                {
                    "path": current[0],
                    "type": "other",
                    "size": None,
                    "sha256": None,
                    "error": type(exc).__name__,
                }
            )
        finally:
            finished.set()

    threading.Thread(target=take, name="dcode-profile-inventory", daemon=True).start()
    done = finished.wait(seconds)
    snapshot = [dict(entry) for entry in list(entries)]
    if not done:
        snapshot.append(
            {
                "path": current[0],
                "type": "other",
                "size": None,
                "sha256": None,
                "error": _TIMED_OUT,
            }
        )
    return snapshot, done


def profile_inventory(
    profile: Path, *, seconds: float | None = None
) -> list[dict[str, Any]]:
    """Describe every entry in a run profile without exposing its contents.

    Each entry gives the path relative to the profile, its file type, its size
    and, for regular files, its SHA-256. Links are recorded, never followed, and
    an unreadable entry is recorded with the error's type rather than refused,
    so the inventory itself never fails a launch. Entries, bytes hashed and time
    are bounded, and the caller waits at most ``seconds`` (the launch advice's
    bound by default) however a read behaves; what a bound cut short is marked
    "not recorded" and every entry gathered before it is kept.
    """

    wait = _ADVICE_INVENTORY_SECONDS if seconds is None else seconds
    return _bounded_inventory(profile, wait)[0]


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


def log_profile_inventory(profile: Path, *, cwd: Path) -> list[dict[str, Any]]:
    """Log the profile as one invocation left it, so a later refusal can be traced.

    Runs in the invocation's finalisation, so the inventory is taken on a
    daemon thread and waited for only briefly: diagnostics never stop a
    completed or cancelled invocation from returning.
    """

    entries, finished = _bounded_inventory(profile, _POST_INVOCATION_INVENTORY_SECONDS)
    if not finished:
        logger.warning(
            "dcode Player post-invocation profile inventory not recorded: timed out; "
            "cwd=%s profile=%s partial entries=%s",
            cwd,
            profile,
            entries,
        )
        return entries
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
    # retried as if it were an implementation failure. The interpreter is
    # the install rule's (pyproject ``requires-python``), not checked again.
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
    # dcode itself makes only empty directories and an empty memory file. A
    # profile holding anything else (26 October 2026, step 2: census GKF-035)
    # is logged with its entries, by path, type, size and hash, never their
    # contents, and the launch goes on.
    findings: list[str] = []
    files = _tree(profile, findings)
    if findings or (files and files != _CLEAN_PROFILE):
        unexpected = _unexpected_profile_entries(profile_inventory(profile))
        _advise(
            "run profile holds more than dcode's own empty files; launching anyway: "
            f"profile={profile}; unexpected profile entries: {_describe_entries(unexpected)}"
        )
    return profile


_SKILLS = "skills"
_MEMORY = "AGENTS.md"


def _lock_profile(profile: Path, identity: tuple[int, int]) -> None:
    """Make a clean, owner-selected run profile read-only before the model runs.

    18 October 2026 (build FEAT-05EE, and FEAT-B463 on 11 October): the owner
    reuses one profile for every Player turn in its process, and a stray file
    a model's command wrote there refused every later turn. Read-only, such a
    write fails inside the command instead.

    The clean shape is fixed, so no tree is walked. The root is opened once
    without following a link and must be this user's directory with the
    ``identity`` (device, inode) its owner recorded when it made the profile;
    otherwise nothing is made or changed, a WARNING is logged and the launch
    goes on as today. Every other
    entry (``guardkit-player``, its ``skills`` folder and its empty
    ``AGENTS.md``) is opened by name relative to its parent's descriptor,
    without following a link, and loses its write bits through that
    descriptor (dcode's 0775/0664 become 0555/0444, the owner-only root 0500).
    Anything else in the root or in ``guardkit-player``, a nonempty or
    non-regular ``AGENTS.md``, or a nonempty ``skills`` leaves it unlocked.
    Only the complete skeleton is locked. dcode makes ``guardkit-player`` at
    its first launch; without it the profile is left writable, as today, with
    a WARNING. A missing ``skills`` folder or empty ``AGENTS.md`` is made here
    through ``guardkit-player``'s descriptor (never by path), so a later task
    with memory or skills on still finds them; if that fails the profile is
    left writable with a WARNING. Anything else that keeps the profile from
    being locked (26 October 2026, step 2: census GKF-036) is a WARNING too:
    the profile is left writable and the launch goes on.
    """

    class _NotLocked(Exception):
        pass

    def refuse(reason: str) -> NoReturn:
        not_owned(reason)
        raise _NotLocked

    def not_owned(reason: str) -> None:
        logger.warning("dcode Player run profile not locked: %s; profile=%s", reason, profile)


    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | _O_CLOEXEC
    opened: list[int] = []

    def open_at(name: str, parent: int, flags: int) -> int:
        try:
            descriptor = os.open(name, flags, dir_fd=parent)
        except OSError as exc:
            refuse(
                f"{name} could not be opened without following a link "
                f"({type(exc).__name__})"
            )
        opened.append(descriptor)
        return descriptor

    def read_only(descriptor: int) -> None:
        mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
        os.fchmod(descriptor, mode & ~0o222)

    try:
        # The root must be, by its own descriptor, the directory the owner
        # recorded when it made the profile. Otherwise it is not the owner's
        # to lock: nothing is made or changed, and the launch goes on as today.
        try:
            root = os.open(profile, directory_flags)
        except OSError as exc:
            not_owned(f"it could not be opened without following a link ({type(exc).__name__})")
            return
        opened.append(root)
        status = os.fstat(root)
        if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.geteuid():
            not_owned("it is not a directory owned by this user")
            return
        if (status.st_dev, status.st_ino) != identity:
            not_owned("it is not the directory its owner made")
            return
        names = set(os.listdir(root))
        if names - {_AGENT}:
            refuse(f"unexpected entries {sorted(names - {_AGENT})}")
        if _AGENT not in names:
            logger.warning(
                "dcode Player run profile left writable: dcode has not made %s yet; profile=%s",
                _AGENT,
                profile,
            )
            return
        agent = open_at(_AGENT, root, directory_flags)
        agent_names = set(os.listdir(agent))
        if agent_names - {_SKILLS, _MEMORY}:
            refuse(f"unexpected entries {sorted(agent_names - {_SKILLS, _MEMORY})}")
        # Only the complete skeleton is locked. dcode makes AGENTS.md only for
        # a task with memory or skills on (the live FEAT-05EE project has
        # neither), so the missing clean entries are made here, through
        # guardkit-player's descriptor, before locking: then a later task with
        # memory or skills on finds them. Another launch making one at the
        # same moment (EEXIST) counts as present; the reopen below checks it.
        try:
            if _SKILLS not in agent_names:
                with suppress(FileExistsError):
                    os.mkdir(_SKILLS, 0o755, dir_fd=agent)
            if _MEMORY not in agent_names:
                create = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | _O_CLOEXEC
                with suppress(FileExistsError):
                    os.close(os.open(_MEMORY, create, 0o644, dir_fd=agent))
        except OSError as exc:
            logger.warning(
                "dcode Player run profile left writable: could not make its clean "
                "entries (%s); profile=%s",
                type(exc).__name__,
                profile,
            )
            return
        agent_names = set(os.listdir(agent))
        if agent_names != {_SKILLS, _MEMORY}:
            refuse(f"unexpected entries {sorted(agent_names)}")
        skills = open_at(_SKILLS, agent, directory_flags)
        if os.listdir(skills):
            refuse(f"{_AGENT}/{_SKILLS} is not empty")
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | _O_CLOEXEC
        memory = open_at(_MEMORY, agent, file_flags)
        memory_status = os.fstat(memory)
        if not stat.S_ISREG(memory_status.st_mode) or memory_status.st_size != 0:
            refuse(f"{_AGENT}/{_MEMORY} is not an empty regular file")
        for descriptor in (memory, skills, agent, root):
            read_only(descriptor)
    except _NotLocked:
        return
    except OSError as exc:
        not_owned(f"{type(exc).__name__} while locking")
    finally:
        for descriptor in opened:
            os.close(descriptor)


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
    if not model.model_name:
        _advise("the model has no explicit alias; the server's default model answers")
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
    """Collect the skill loader's warnings for one discovery call.

    The loader's logger is shared by the whole process, and parallel tasks
    run Player launches in threads, so only warnings from the thread that
    installed this handler are this discovery's (18 October 2026: another
    task's missing skill folders refused a launch running beside it).
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []
        self._thread = threading.get_ident()

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread == self._thread:
            self.messages.append(record.getMessage())


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
    # 26 October 2026 (step 2): every finding below is advice, listed in the
    # evidence's ``warnings``; the Player starts with what dcode discovers.
    warnings: list[str] = []
    selected = (cwd / "skills").resolve()
    if config.skills and config.skills != (selected,):
        _advise("only the root skills/ folder is discovered; other selected skills are not", warnings)
    if config.skills:
        link = cwd / ".agents" / "skills"
        if not link.is_symlink() or os.readlink(link) != "../skills":
            _advise("selected skills are discovered through .agents/skills -> ../skills, which is missing", warnings)
    plugins = discover_plugins()
    if plugins.plugins or plugins.warnings:
        _advise(f"plugins or discovery warnings: {plugins.warnings!r}", warnings)
    agents = [get_user_agents_dir(_AGENT), context.project_agents_dir()]
    definitions = {str(p): _tree(p, warnings) for p in agents if p is not None}
    if any(definitions.values()) or list_subagents(
        user_agents_dir=agents[0], project_agents_dir=agents[1]
    ):
        _advise("custom subagent definitions are present", warnings)
    builtins = get_built_in_skills_dir().resolve(strict=True)
    sources = []
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    for raw, label in get_skill_sources(assistant_id=_AGENT, project_context=context):
        path = Path(raw)
        canonical = path.resolve()
        allowed = canonical == builtins or (bool(config.skills) and canonical == selected)
        files = _tree(path, warnings)
        if files and not allowed:
            _advise(
                f"unexpected skill discovery source: {path} (its skills are offered "
                "to the Player too)",
                warnings,
            )
        if files and canonical in seen_paths:
            _advise(f"duplicate skill discovery source: {path}", warnings)
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
                _advise(f"skill discovery warnings for {path}: {error or handler.messages}", warnings)
            expected = {
                (canonical / relative).resolve()
                for relative in files
                if Path(relative).name == "SKILL.md"
            }
            if {Path(skill["path"]).resolve() for skill in loaded} != expected:
                _advise(f"skill discovery skipped selected files: {path}", warnings)
            for skill in loaded:
                name = skill["name"]
                if name in seen_names:
                    _advise(f"duplicate discovered skill name: {name}", warnings)
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
        _advise("selected skills were not discovered", warnings)
    # Inspect selected instruction sources directly so an optional memory
    # middleware cannot be the only route by which repository guidance reaches
    # the Player. Their contents are also supplied in the invocation prompt.
    instructions = {
        str(path): hashlib.sha256(_read(path)).hexdigest()
        for path in config.repository_instructions
    }
    discovered = tuple(p.resolve() for p in context.project_agent_md_paths())
    if config.memory and discovered != config.memory:
        _advise("project memory discovery does not match the selected sources", warnings)
    memory = {str(path): hashlib.sha256(_read(path)).hexdigest() for path in config.memory}
    user_memory = get_user_agent_md_path(_AGENT)
    if user_memory.exists() or user_memory.is_symlink():
        if _read(user_memory) != b"":
            _advise("profile AGENTS.md is not empty", warnings)
    return {
        "skills": sources,
        "memory": memory,
        "repository_instructions": instructions,
        "declared_commands": dict(config.declared_commands),
        "protected_paths": [str(path) for path in config.protected_paths],
        "agents": definitions,
        "plugins": [],
        "warnings": warnings,
        "subagents": ["general-purpose"],
    }


def _private_artifacts_root(backend: Any, cwd: Path) -> Path:
    """The factory backend's private folder for model artifacts, checked.

    14 October 2026. dcode's conversation summaries and large tool results
    go to the folder ``build_autobuild_backend`` chose
    (``backend_config.model_artifacts_root``), never into the worktree,
    where a checkpoint commit would take them into the build's branch. A
    missing, symlinked, unresolvable or in-project folder is refused. One
    that is another user's or cannot be made owner-only (mode 0700) is
    logged (26 October 2026).
    """
    raw = getattr(backend, "artifacts_root", None)
    if not isinstance(raw, (str, Path)) or not str(raw).strip():
        _refuse("the backend names no private folder for model artifacts")
    root = Path(raw)
    if root.is_symlink():
        _refuse(f"artifact directory must not be a symlink: {root}")
    try:
        resolved = root.resolve(strict=True)
    except (OSError, RuntimeError):
        _refuse(f"invalid artifact directory: {root}")
    if resolved != root or not resolved.is_dir():
        _refuse(f"invalid artifact directory: {root}")
    project = cwd.resolve()
    if resolved.is_relative_to(project) and not resolved.is_relative_to(project / ".git"):
        _refuse(f"artifact directory is inside the worktree: {root}")
    _owner_only(resolved)
    return resolved


def _owner_only(directory: Path) -> None:
    from guardkitfactory.harness.backend_config import ensure_owner_only_directory

    try:
        ensure_owner_only_directory(directory, "artifact directory")
    except ValueError as exc:
        _refuse(str(exc))


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
        if target.is_symlink():
            _refuse(f"artifact directory must not be a symlink: {target}")
        target.mkdir(mode=0o700, exist_ok=True)
        if target.resolve(strict=True) != target or not target.is_dir():
            _refuse(f"invalid artifact directory: {target}")
        _owner_only(target)
        inside: list[str] = []
        _tree(target, inside)
        if inside:
            _refuse(f"invalid artifact directory contents: {'; '.join(inside)}")
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
    settings = _validate_model(model, config)
    from deepagents_code._env_vars import EXPERIMENTAL
    from deepagents_code._paths import PATHS
    from deepagents_code.agent import create_cli_agent
    from deepagents_code.config import MODEL_RETRIES_ATTR
    from deepagents_code.extensions.registry import (
        ExtensionRegistry,
        SourceInfo,
        SourceScope,
    )
    from deepagents_code.project_utils import ProjectContext

    from guardkitfactory.harness.code_search_tools import code_search_tools
    from guardkitfactory.harness.skill_read_middleware import (
        SelectedSkillReadMiddleware,
    )

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
    before = _inventory(config, context)
    artifacts = _private_artifacts_root(backend, cwd)
    adapted = _artifact_backend(backend, cwd, artifacts)
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
        extension_registry=registry,
        environ=dcode_environment,
    )
    if config.lock_profile_identity is not None:
        _lock_profile(profile, config.lock_profile_identity)
    tools = sorted(graph.nodes["tools"].bound.tools_by_name)
    evidence = {
        "discovery": before,
        "required_skill_reads": [dict(item) for item in required],
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
    graph.guardkit_skill_read_gate = skill_gate
    logger.info("dcode Player construction inventory: %s", evidence)
    return graph
