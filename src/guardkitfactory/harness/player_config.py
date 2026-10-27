"""Configuration for the single local dcode Player."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PlayerConfig",
    "PlayerConfigError",
    "build_player_config",
    "revalidate_player_config",
]


class PlayerConfigError(ValueError):
    """Raised when the Player's worktree or run profile is not there to use."""


@dataclass(frozen=True, slots=True)
class PlayerConfig:
    """Resolved, immutable inputs for the normal dcode Player."""

    skills: tuple[Path, ...]
    memory: tuple[Path, ...]
    repository_instructions: tuple[Path, ...]
    declared_commands: tuple[tuple[str, str], ...]
    protected_paths: tuple[Path, ...]
    cwd: Path
    dcode_home: Path
    required_documents: tuple[Path, ...] = ()


_READ_BITS = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _canonical_directory(path: Path, *, label: str) -> Path:
    """The Player's worktree or run profile: there is nothing to work from
    without it."""
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


def _canonical_sources(
    values: Iterable[str | Path],
    *,
    cwd: Path,
    directories: bool,
) -> tuple[Path, ...]:
    """The declared sources that are there, resolved, each once.

    An entry that does not exist, lies outside the task worktree (it is not
    read) or is the wrong kind is left out. Two entries that resolve to the
    same file are one, kept at its first position: many projects keep
    ``AGENTS.md`` as the source and make ``CLAUDE.md`` a symbolic link to it.
    """
    resolved_sources: list[Path] = []
    for value in values:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            continue
        candidate = Path(value) if Path(value).is_absolute() else cwd / value
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        usable = resolved.is_dir() if directories else resolved.is_file()
        if usable and resolved.is_relative_to(cwd) and resolved not in resolved_sources:
            resolved_sources.append(resolved)
    return tuple(resolved_sources)


def _canonical_protected_paths(
    values: Iterable[str | Path], *, cwd: Path
) -> tuple[Path, ...]:
    """The declared protected paths that exist inside the worktree, each once."""
    resolved: list[Path] = []
    for value in values:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            continue
        candidate = Path(value) if Path(value).is_absolute() else cwd / value
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if canonical.is_relative_to(cwd) and canonical not in resolved:
            resolved.append(canonical)
    return tuple(resolved)


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
) -> PlayerConfig:
    """Resolve the project-supplied inputs for one normal Player."""

    actual_cwd = _canonical_directory(Path(cwd), label="Player cwd")
    return PlayerConfig(
        skills=_canonical_sources(skills, cwd=actual_cwd, directories=True),
        memory=_canonical_sources(memory, cwd=actual_cwd, directories=False),
        repository_instructions=_canonical_sources(
            repository_instructions, cwd=actual_cwd, directories=False
        ),
        declared_commands=tuple((name, command) for name, command in declared_commands),
        protected_paths=_canonical_protected_paths(protected_paths, cwd=actual_cwd),
        cwd=actual_cwd,
        dcode_home=_canonical_directory(Path(dcode_home), label="dcode_home"),
        required_documents=_canonical_sources(
            required_documents, cwd=actual_cwd, directories=False
        ),
    )


def revalidate_player_config(config: PlayerConfig, *, cwd: Path) -> PlayerConfig:
    """Resolve every local source again immediately before graph construction.

    The rebuilt config describes what is on disk now (a source that went is
    left out), and it is the one to use.
    """

    return build_player_config(
        cwd=cwd,
        dcode_home=config.dcode_home,
        skills=config.skills,
        memory=config.memory,
        repository_instructions=config.repository_instructions,
        declared_commands=config.declared_commands,
        protected_paths=config.protected_paths,
        required_documents=config.required_documents,
    )
