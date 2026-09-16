"""Strict configuration for opt-in Player implementation experiments.

The configuration is intentionally small and worktree-scoped. Callers parse
it against the task worktree once, then the harness revalidates the immutable
value against the directory used for the actual invocation.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "PlayerExperimentConfig",
    "PlayerExperimentConfigError",
    "parse_player_experiment",
    "revalidate_player_experiment",
]


class PlayerExperimentConfigError(ValueError):
    """Raised when a requested Player experiment is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class PlayerExperimentConfig:
    """Canonical, immutable Player experiment configuration."""

    engine: Literal["native", "dcode"]
    skills: tuple[Path, ...]
    memory: tuple[Path, ...]
    cwd: Path
    dcode_home: Path | None = None


_ALLOWED_FIELDS = frozenset({"engine", "skills", "memory", "dcode_home"})
_READ_BITS = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlayerExperimentConfigError(
                f"GUARDKIT_PLAYER_EXPERIMENT contains duplicate field {key!r}"
            )
        result[key] = value
    return result


def _canonical_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PlayerExperimentConfigError(
            f"{label} does not exist or cannot be resolved: {path}"
        ) from exc
    if not resolved.is_dir():
        raise PlayerExperimentConfigError(f"{label} must be a directory: {path}")
    mode = resolved.stat().st_mode
    if not (mode & _READ_BITS) or not (mode & _EXEC_BITS):
        raise PlayerExperimentConfigError(f"{label} is not readable/searchable: {resolved}")
    if not os.access(resolved, os.R_OK | os.X_OK):
        raise PlayerExperimentConfigError(f"{label} is not readable/searchable: {resolved}")
    return resolved


def _inside(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _canonical_sources(
    value: Any,
    *,
    field: Literal["skills", "memory"],
    cwd: Path,
) -> tuple[Path, ...]:
    if not isinstance(value, list):
        raise PlayerExperimentConfigError(f"{field!r} must be a JSON array of paths")

    resolved_sources: list[Path] = []
    seen: set[Path] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PlayerExperimentConfigError(
                f"{field}[{index}] must be a non-empty path string"
            )
        selected = Path(item)
        candidate = selected if selected.is_absolute() else cwd / selected
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PlayerExperimentConfigError(
                f"{field}[{index}] does not exist or cannot be resolved: {item}"
            ) from exc
        if not _inside(resolved, cwd):
            raise PlayerExperimentConfigError(
                f"{field}[{index}] resolves outside the task worktree: {item} -> {resolved}"
            )
        if resolved in seen:
            raise PlayerExperimentConfigError(
                f"{field!r} contains duplicate resolved path: {resolved}"
            )

        mode = resolved.stat().st_mode
        if field == "skills":
            if not resolved.is_dir():
                raise PlayerExperimentConfigError(
                    f"skills[{index}] must resolve to a directory: {resolved}"
                )
            if not (mode & _READ_BITS) or not (mode & _EXEC_BITS):
                raise PlayerExperimentConfigError(
                    f"skills[{index}] is not readable/searchable: {resolved}"
                )
            access_mode = os.R_OK | os.X_OK
        else:
            if not resolved.is_file():
                raise PlayerExperimentConfigError(
                    f"memory[{index}] must resolve to a regular file: {resolved}"
                )
            if not mode & _READ_BITS:
                raise PlayerExperimentConfigError(
                    f"memory[{index}] is not readable: {resolved}"
                )
            access_mode = os.R_OK
        if not os.access(resolved, access_mode):
            raise PlayerExperimentConfigError(f"{field}[{index}] is not readable: {resolved}")

        seen.add(resolved)
        resolved_sources.append(resolved)
    return tuple(resolved_sources)


def _canonical_dcode_home(value: Any, *, cwd: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PlayerExperimentConfigError(
            "'dcode_home' is required for engine 'dcode' and must be a non-empty path string"
        )
    selected = Path(value)
    if not selected.is_absolute():
        raise PlayerExperimentConfigError("'dcode_home' must be an absolute path")
    resolved = _canonical_directory(selected, label="dcode_home")
    if _inside(resolved, cwd):
        raise PlayerExperimentConfigError("'dcode_home' must be outside the task worktree")
    mode = resolved.stat().st_mode
    if not mode & _WRITE_BITS or not os.access(resolved, os.W_OK):
        raise PlayerExperimentConfigError(f"dcode_home is not writable: {resolved}")
    return resolved


def parse_player_experiment(raw: str, *, cwd: Path) -> PlayerExperimentConfig:
    """Parse and validate one GUARDKIT_PLAYER_EXPERIMENT JSON value."""

    if not isinstance(raw, str) or not raw.strip():
        raise PlayerExperimentConfigError(
            "GUARDKIT_PLAYER_EXPERIMENT must be a non-empty JSON object"
        )
    actual_cwd = _canonical_directory(Path(cwd), label="Player experiment cwd")
    try:
        parsed = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
    except PlayerExperimentConfigError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PlayerExperimentConfigError(
            f"GUARDKIT_PLAYER_EXPERIMENT is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise PlayerExperimentConfigError("GUARDKIT_PLAYER_EXPERIMENT must be a JSON object")

    unknown = sorted(set(parsed) - _ALLOWED_FIELDS)
    if unknown:
        raise PlayerExperimentConfigError(
            f"GUARDKIT_PLAYER_EXPERIMENT contains unknown field(s): {', '.join(unknown)}"
        )
    engine = parsed.get("engine")
    if not isinstance(engine, str) or engine not in {"native", "dcode"}:
        raise PlayerExperimentConfigError("'engine' is required and must be 'native' or 'dcode'")

    skills = _canonical_sources(parsed.get("skills", []), field="skills", cwd=actual_cwd)
    memory = _canonical_sources(parsed.get("memory", []), field="memory", cwd=actual_cwd)

    if engine == "native":
        if "dcode_home" in parsed:
            raise PlayerExperimentConfigError("'dcode_home' is only valid for engine 'dcode'")
        dcode_home = None
    else:
        dcode_home = _canonical_dcode_home(parsed.get("dcode_home"), cwd=actual_cwd)

    return PlayerExperimentConfig(
        engine=engine,
        skills=skills,
        memory=memory,
        cwd=actual_cwd,
        dcode_home=dcode_home,
    )


def revalidate_player_experiment(
    experiment: PlayerExperimentConfig,
    *,
    cwd: Path,
) -> PlayerExperimentConfig:
    """Revalidate canonical sources immediately before graph construction."""

    if not isinstance(experiment, PlayerExperimentConfig):
        raise PlayerExperimentConfigError("player_experiment has an unsupported value type")
    actual_cwd = _canonical_directory(Path(cwd), label="Player invocation cwd")
    if actual_cwd != experiment.cwd:
        raise PlayerExperimentConfigError(
            "Player experiment was configured for a different worktree: "
            f"configured={experiment.cwd} invocation={actual_cwd}"
        )

    for field, sources in (("skills", experiment.skills), ("memory", experiment.memory)):
        _canonical_sources(
            [str(path) for path in sources],
            field=field,
            cwd=actual_cwd,
        )
    if experiment.engine == "dcode":
        if experiment.dcode_home is None:
            raise PlayerExperimentConfigError("engine 'dcode' requires dcode_home")
        _canonical_dcode_home(str(experiment.dcode_home), cwd=actual_cwd)
    elif experiment.engine != "native":
        raise PlayerExperimentConfigError(
            f"unsupported Player experiment engine: {experiment.engine!r}"
        )
    return experiment
