"""Validated configuration for the single local dcode Player."""

from __future__ import annotations

import logging
import os
import stat
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "PlayerConfig",
    "PlayerConfigError",
    "build_player_config",
    "revalidate_player_config",
]


class PlayerConfigError(ValueError):
    """Raised when required Player context is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class PlayerConfig:
    """Canonical, immutable inputs for the normal dcode Player."""

    skills: tuple[Path, ...]
    memory: tuple[Path, ...]
    repository_instructions: tuple[Path, ...]
    declared_commands: tuple[tuple[str, str], ...]
    protected_paths: tuple[Path, ...]
    cwd: Path
    dcode_home: Path
    required_documents: tuple[Path, ...] = ()
    # Set by the profile's owner (GuardKit, for the profile it made itself) to
    # the (st_dev, st_ino) it recorded when it made it: after a launch passes
    # its check that same directory is made read-only, so a stray write into
    # it fails instead of refusing every later turn.
    lock_profile_identity: tuple[int, int] | None = None


_MAX_REQUIRED_DOCUMENTS = 32
# One binding document may be as large as the whole project-documents budget
# that GuardKit's Coach and Forge's planning writers accept (128 KiB), so a
# document those accept is never refused here.
_MAX_REQUIRED_DOCUMENT_BYTES = 131_072

_READ_BITS = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _canonical_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PlayerConfigError(f"{label} does not exist or cannot be resolved: {path}") from exc
    if not resolved.is_dir():
        raise PlayerConfigError(f"{label} must be a directory: {path}")
    mode = resolved.stat().st_mode
    if not mode & _READ_BITS or not mode & _EXEC_BITS or not os.access(resolved, os.R_OK | os.X_OK):
        raise PlayerConfigError(f"{label} is not readable/searchable: {resolved}")
    return resolved


def _inside(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _skipped(label: str, index: int, value: object, reason: str) -> None:
    logger.warning("Player %s[%d] %r skipped: %s", label, index, value, reason)


def _canonical_sources(
    values: Iterable[str | Path],
    *,
    label: str,
    cwd: Path,
    directories: bool,
) -> tuple[Path, ...]:
    """Resolve each path, inside the task worktree, readable, no duplicates.

    26 October 2026 (step 2): an entry that cannot be used is logged and
    skipped, never a refusal of the Player. That is an empty entry, one that
    does not exist, one that resolves outside the task worktree (it is not
    read), the wrong kind or an unreadable one. Two entries that resolve to
    the same file are one, kept at its first position: many projects keep
    ``AGENTS.md`` as the source and make ``CLAUDE.md`` a symbolic link to it.
    """
    resolved_sources: list[Path] = []
    seen: set[Path] = set()
    for index, value in enumerate(values):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            _skipped(label, index, value, "not a path")
            continue
        selected = Path(value)
        candidate = selected if selected.is_absolute() else cwd / selected
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            _skipped(label, index, value, "does not exist")
            continue
        if not _inside(resolved, cwd):
            _skipped(label, index, value, "resolves outside the task worktree")
            continue
        if resolved in seen:
            continue
        mode = resolved.stat().st_mode
        if directories:
            if not resolved.is_dir():
                _skipped(label, index, value, "is not a directory")
                continue
            usable = bool(
                mode & _READ_BITS
                and mode & _EXEC_BITS
                and os.access(resolved, os.R_OK | os.X_OK)
            )
        else:
            if not resolved.is_file():
                _skipped(label, index, value, "is not a regular file")
                continue
            usable = bool(mode & _READ_BITS and os.access(resolved, os.R_OK))
        if not usable:
            _skipped(label, index, value, "is not readable")
            continue
        seen.add(resolved)
        resolved_sources.append(resolved)
    return tuple(resolved_sources)


def _canonical_protected_paths(
    values: Iterable[str | Path], *, cwd: Path
) -> tuple[Path, ...]:
    """The declared protected paths that exist inside the worktree.

    26 October 2026 (step 2): a declared path that does not exist protects
    nothing and is noted, not refused; so is one outside the worktree or one
    that is neither a file nor a folder. A repeat is kept once.
    """
    resolved: list[Path] = []
    seen: set[Path] = set()
    for index, value in enumerate(values):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            _skipped("protected_paths", index, value, "not a path")
            continue
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else cwd / candidate
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            logger.info(
                "Player protected_paths[%d] %r does not exist; it protects nothing",
                index,
                value,
            )
            continue
        if not _inside(canonical, cwd):
            _skipped("protected_paths", index, value, "resolves outside the task worktree")
            continue
        if canonical in seen:
            continue
        if not (canonical.is_file() or canonical.is_dir()):
            _skipped("protected_paths", index, value, "is not a file or directory")
            continue
        seen.add(canonical)
        resolved.append(canonical)
    return tuple(resolved)


def _canonical_required_documents(
    values: Iterable[str | Path], *, cwd: Path
) -> tuple[Path, ...]:
    """Canonicalise project-declared mandatory supporting documents.

    Same discipline as ``_canonical_sources(..., directories=False)``. The
    count and size are guides (26 October 2026, step 2): more than 32
    documents, a document over 128 KiB, or one that is not UTF-8 text is
    logged and kept.
    """

    selected = list(values)
    if len(selected) > _MAX_REQUIRED_DOCUMENTS:
        logger.warning(
            "required_documents declares %d entries, more than the guide of %d; "
            "all are kept",
            len(selected),
            _MAX_REQUIRED_DOCUMENTS,
        )
    resolved = _canonical_sources(
        selected, label="required_documents", cwd=cwd, directories=False
    )
    for path in resolved:
        size = path.stat().st_size
        if size > _MAX_REQUIRED_DOCUMENT_BYTES:
            logger.warning(
                "required document %s is %d bytes, more than the guide of %d; kept",
                path,
                size,
                _MAX_REQUIRED_DOCUMENT_BYTES,
            )
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("required document %s is not valid UTF-8; kept", path)
    return resolved


def _canonical_commands(values: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """The declared commands; a blank one or a repeated name is logged and skipped."""
    commands: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, command in values:
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(command, str)
            or not command.strip()
        ):
            logger.warning("declared command %r skipped: blank name or value", name)
            continue
        if name in seen:
            logger.warning("declared command %r skipped: the name is used twice", name)
            continue
        seen.add(name)
        commands.append((name, command))
    return tuple(commands)


def _canonical_dcode_home(value: str | Path, *, cwd: Path) -> Path:
    """The coding agent's profile folder, outside the task worktree.

    Inside the worktree its files would be committed with the build, so that
    stays refused. A relative path or a folder that is not writable is logged
    (26 October 2026, step 2): the owner locks a clean profile read-only.
    """
    selected = Path(value)
    if not selected.is_absolute():
        logger.warning("dcode_home %s is not an absolute path", value)
    resolved = _canonical_directory(selected, label="dcode_home")
    if _inside(resolved, cwd):
        raise PlayerConfigError("dcode_home must be outside the task worktree")
    mode = resolved.stat().st_mode
    if not mode & _WRITE_BITS or not os.access(resolved, os.W_OK):
        logger.info("dcode_home %s is not writable", resolved)
    return resolved


def build_player_config(
    *,
    cwd: Path,
    dcode_home: str | Path,
    skills: Iterable[str | Path] = (),
    memory: Iterable[str | Path] = (),
    repository_instructions: Iterable[str | Path] = (),
    declared_commands: Sequence[tuple[str, str]] = (),
    protected_paths: Iterable[str | Path] = (),
    required_documents: Iterable[str | Path] = (),
    lock_profile_identity: tuple[int, int] | None = None,
) -> PlayerConfig:
    """Validate the project-supplied inputs for one normal Player.

    ``lock_profile_identity`` is for the owner of ``dcode_home`` only (GuardKit,
    for the profile it made itself): the (st_dev, st_ino) it recorded when it
    made the profile. A profile supplied from outside never sets it.
    """

    if lock_profile_identity is not None and (
        not isinstance(lock_profile_identity, tuple)
        or len(lock_profile_identity) != 2
        or not all(
            isinstance(part, int) and not isinstance(part, bool)
            for part in lock_profile_identity
        )
    ):
        logger.warning(
            "lock_profile_identity %r is not a (st_dev, st_ino) pair of integers; "
            "the profile will not be locked",
            lock_profile_identity,
        )
        lock_profile_identity = None

    actual_cwd = _canonical_directory(Path(cwd), label="Player cwd")
    return PlayerConfig(
        skills=_canonical_sources(skills, label="skills", cwd=actual_cwd, directories=True),
        memory=_canonical_sources(memory, label="memory", cwd=actual_cwd, directories=False),
        repository_instructions=_canonical_sources(
            repository_instructions,
            label="repository_instructions",
            cwd=actual_cwd,
            directories=False,
        ),
        declared_commands=_canonical_commands(declared_commands),
        protected_paths=_canonical_protected_paths(protected_paths, cwd=actual_cwd),
        cwd=actual_cwd,
        dcode_home=_canonical_dcode_home(dcode_home, cwd=actual_cwd),
        required_documents=_canonical_required_documents(
            required_documents, cwd=actual_cwd
        ),
        lock_profile_identity=lock_profile_identity,
    )


def revalidate_player_config(config: PlayerConfig, *, cwd: Path) -> PlayerConfig:
    """Rebuild every local source immediately before graph construction.

    A source that changed, went or left the worktree since the config was
    built is not an error: the rebuilt config describes what is on disk now
    (a source that cannot be used is logged and left out), and it is the one
    to use.
    """

    if not isinstance(config, PlayerConfig):
        raise PlayerConfigError("player_config has an unsupported value type")
    rebuilt = build_player_config(
        cwd=cwd,
        dcode_home=config.dcode_home,
        skills=config.skills,
        memory=config.memory,
        repository_instructions=config.repository_instructions,
        declared_commands=config.declared_commands,
        protected_paths=config.protected_paths,
        required_documents=config.required_documents,
        lock_profile_identity=config.lock_profile_identity,
    )
    if rebuilt != config:
        logger.info(
            "Player configuration changed since it was built; using the rebuilt one"
        )
        return rebuilt
    return config
