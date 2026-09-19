"""Validated configuration for the single local dcode Player."""

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


_MAX_REQUIRED_DOCUMENTS = 32
_MAX_REQUIRED_DOCUMENT_BYTES = 65_536

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


def _canonical_sources(
    values: Iterable[str | Path],
    *,
    label: str,
    cwd: Path,
    directories: bool,
) -> tuple[Path, ...]:
    resolved_sources: list[Path] = []
    seen: set[Path] = set()
    for index, value in enumerate(values):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise PlayerConfigError(f"{label}[{index}] must be a non-empty path")
        selected = Path(value)
        candidate = selected if selected.is_absolute() else cwd / selected
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PlayerConfigError(f"{label}[{index}] does not exist: {value}") from exc
        if not _inside(resolved, cwd):
            raise PlayerConfigError(f"{label}[{index}] resolves outside the task worktree: {value}")
        if resolved in seen:
            raise PlayerConfigError(f"{label} contains duplicate resolved path: {resolved}")
        mode = resolved.stat().st_mode
        if directories:
            if not resolved.is_dir():
                raise PlayerConfigError(f"{label}[{index}] must resolve to a directory: {resolved}")
            usable = bool(
                mode & _READ_BITS
                and mode & _EXEC_BITS
                and os.access(resolved, os.R_OK | os.X_OK)
            )
        else:
            if not resolved.is_file():
                raise PlayerConfigError(
                    f"{label}[{index}] must resolve to a regular file: {resolved}"
                )
            usable = bool(mode & _READ_BITS and os.access(resolved, os.R_OK))
        if not usable:
            raise PlayerConfigError(f"{label}[{index}] is not readable: {resolved}")
        seen.add(resolved)
        resolved_sources.append(resolved)
    return tuple(resolved_sources)


def _canonical_protected_paths(
    values: Iterable[str | Path], *, cwd: Path
) -> tuple[Path, ...]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for index, value in enumerate(values):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise PlayerConfigError(f"protected_paths[{index}] must be a non-empty path")
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else cwd / candidate
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PlayerConfigError(f"protected_paths[{index}] does not exist: {value}") from exc
        if not _inside(canonical, cwd):
            raise PlayerConfigError(
                f"protected_paths[{index}] resolves outside the task worktree: {value}"
            )
        if canonical in seen:
            raise PlayerConfigError(
                f"protected_paths contains duplicate resolved path: {canonical}"
            )
        if not (canonical.is_file() or canonical.is_dir()):
            raise PlayerConfigError(
                f"protected_paths[{index}] is not a file or directory: {canonical}"
            )
        seen.add(canonical)
        resolved.append(canonical)
    return tuple(resolved)


def _canonical_required_documents(
    values: Iterable[str | Path], *, cwd: Path
) -> tuple[Path, ...]:
    """Canonicalise project-declared mandatory supporting documents.

    Same discipline as ``_canonical_sources(..., directories=False)`` — the
    declaration is a finite list of repository-relative regular files that stay
    inside the task worktree after canonical resolution, with no duplicates —
    plus the two extra limits the documents themselves must respect: a readable
    UTF-8 body and a bounded size, so the required read the Player must perform
    is always renderable and always finite.
    """

    selected = list(values)
    if len(selected) > _MAX_REQUIRED_DOCUMENTS:
        raise PlayerConfigError(
            f"required_documents declares {len(selected)} entries; at most "
            f"{_MAX_REQUIRED_DOCUMENTS} are accepted "
            f"(first refused entry: {selected[_MAX_REQUIRED_DOCUMENTS]})"
        )
    resolved = _canonical_sources(
        selected, label="required_documents", cwd=cwd, directories=False
    )
    for index, path in enumerate(resolved):
        size = path.stat().st_size
        if size > _MAX_REQUIRED_DOCUMENT_BYTES:
            raise PlayerConfigError(
                f"required_documents[{index}] is {size} bytes; at most "
                f"{_MAX_REQUIRED_DOCUMENT_BYTES} are accepted: {path}"
            )
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PlayerConfigError(
                f"required_documents[{index}] is not valid UTF-8: {path}"
            ) from exc
    return resolved


def _canonical_commands(values: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    commands: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, command in values:
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(command, str)
            or not command.strip()
        ):
            raise PlayerConfigError("declared command names and values must be non-empty strings")
        if name in seen:
            raise PlayerConfigError(f"duplicate declared command name: {name}")
        seen.add(name)
        commands.append((name, command))
    return tuple(commands)


def _canonical_dcode_home(value: str | Path, *, cwd: Path) -> Path:
    selected = Path(value)
    if not selected.is_absolute():
        raise PlayerConfigError("dcode_home must be an absolute path")
    resolved = _canonical_directory(selected, label="dcode_home")
    if _inside(resolved, cwd):
        raise PlayerConfigError("dcode_home must be outside the task worktree")
    mode = resolved.stat().st_mode
    if not mode & _WRITE_BITS or not os.access(resolved, os.W_OK):
        raise PlayerConfigError(f"dcode_home is not writable: {resolved}")
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
) -> PlayerConfig:
    """Validate the project-supplied inputs for one normal Player."""

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
    )


def revalidate_player_config(config: PlayerConfig, *, cwd: Path) -> PlayerConfig:
    """Revalidate every local source immediately before graph construction."""

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
    )
    if rebuilt != config:
        raise PlayerConfigError("Player configuration changed before invocation")
    return config
