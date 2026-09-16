"""Strict parser and invocation-boundary tests for Player experiments."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from guardkitfactory.harness.player_experiment import (
    PlayerExperimentConfig,
    PlayerExperimentConfigError,
    parse_player_experiment,
    revalidate_player_experiment,
)


def _worktree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "skills" / "planning").mkdir(parents=True)
    (root / "skills" / "planning" / "SKILL.md").write_text(
        "---\nname: planning\ndescription: Plan changes.\n---\n"
    )
    (root / "AGENTS.md").write_text("# Instructions\n")
    return root


def _parse(root: Path, value: object) -> PlayerExperimentConfig:
    return parse_player_experiment(json.dumps(value), cwd=root)


def test_native_defaults_are_canonical_and_immutable(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    config = _parse(root, {"engine": "native"})

    assert config == PlayerExperimentConfig(
        engine="native",
        skills=(),
        memory=(),
        cwd=root.resolve(),
        dcode_home=None,
    )
    with pytest.raises(FrozenInstanceError):
        config.engine = "dcode"  # type: ignore[misc]


def test_native_sources_resolve_relative_to_actual_cwd(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    config = _parse(
        root,
        {"engine": "native", "skills": ["skills"], "memory": ["AGENTS.md"]},
    )

    assert config.skills == ((root / "skills").resolve(),)
    assert config.memory == ((root / "AGENTS.md").resolve(),)
    assert revalidate_player_experiment(config, cwd=root) is config


def test_native_sources_accept_in_worktree_skill_symlinks(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    bundled = root / "examples" / "coding-skills-bundle" / "skills"
    bundled.mkdir(parents=True)
    (root / "skills" / "planning").rename(bundled / "planning")
    (root / "skills").rmdir()
    (root / "skills").symlink_to(
        "examples/coding-skills-bundle/skills",
        target_is_directory=True,
    )
    (root / ".agents").mkdir()
    (root / ".agents" / "skills").symlink_to("../skills", target_is_directory=True)

    root_link = _parse(root, {"engine": "native", "skills": ["skills"]})
    agents_link = _parse(root, {"engine": "native", "skills": [".agents/skills"]})

    assert root_link.skills == (bundled.resolve(),)
    assert agents_link.skills == root_link.skills


@pytest.mark.parametrize(
    "raw,match",
    [
        ("", "non-empty JSON object"),
        ("{", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ('{"engine":"native","extra":true}', "unknown field"),
        ('{"skills":[]}', "engine"),
        ('{"engine":"other"}', "native.*dcode"),
        ('{"engine":"native","skills":"skills"}', "JSON array"),
        ('{"engine":"native","memory":[1]}', "non-empty path string"),
        ('{"engine":"native","skills":[""]}', "non-empty path string"),
        ('{"engine":"native","engine":"dcode"}', "duplicate field"),
    ],
)
def test_rejects_malformed_schema(tmp_path: Path, raw: str, match: str) -> None:
    root = _worktree(tmp_path)
    with pytest.raises(PlayerExperimentConfigError, match=match):
        parse_player_experiment(raw, cwd=root)


def test_rejects_missing_sources_and_wrong_file_types(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    with pytest.raises(PlayerExperimentConfigError, match="does not exist"):
        _parse(root, {"engine": "native", "skills": ["missing"]})
    with pytest.raises(PlayerExperimentConfigError, match="must resolve to a directory"):
        _parse(root, {"engine": "native", "skills": ["AGENTS.md"]})
    with pytest.raises(PlayerExperimentConfigError, match="must resolve to a regular file"):
        _parse(root, {"engine": "native", "memory": ["skills"]})


def test_rejects_unreadable_sources(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    memory = root / "AGENTS.md"
    memory.chmod(0)
    try:
        with pytest.raises(PlayerExperimentConfigError, match="not readable"):
            _parse(root, {"engine": "native", "memory": ["AGENTS.md"]})
    finally:
        memory.chmod(0o644)


def test_rejects_duplicate_canonical_sources(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    (root / "skills-alias").symlink_to("skills", target_is_directory=True)
    with pytest.raises(PlayerExperimentConfigError, match="duplicate resolved path"):
        _parse(
            root,
            {"engine": "native", "skills": ["skills", "skills-alias"]},
        )


def test_rejects_parent_and_symlink_escapes(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "AGENTS.md").write_text("# outside\n")
    (root / "outside-link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PlayerExperimentConfigError, match="outside the task worktree"):
        _parse(root, {"engine": "native", "memory": ["../outside/AGENTS.md"]})
    with pytest.raises(PlayerExperimentConfigError, match="outside the task worktree"):
        _parse(root, {"engine": "native", "skills": ["outside-link"]})


def test_native_rejects_dcode_home(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    profile = tmp_path / "profile"
    profile.mkdir()
    with pytest.raises(PlayerExperimentConfigError, match="only valid"):
        _parse(
            root,
            {"engine": "native", "dcode_home": str(profile)},
        )


def test_dcode_requires_absolute_external_profile(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    profile = tmp_path / "profile"
    profile.mkdir()
    config = _parse(
        root,
        {"engine": "dcode", "dcode_home": str(profile)},
    )
    assert config.dcode_home == profile.resolve()

    with pytest.raises(PlayerExperimentConfigError, match="required"):
        _parse(root, {"engine": "dcode"})
    with pytest.raises(PlayerExperimentConfigError, match="absolute"):
        _parse(root, {"engine": "dcode", "dcode_home": "profile"})
    inside = root / "profile"
    inside.mkdir()
    with pytest.raises(PlayerExperimentConfigError, match="outside"):
        _parse(root, {"engine": "dcode", "dcode_home": str(inside)})


def test_revalidation_refuses_other_worktree_and_changed_source(tmp_path: Path) -> None:
    root = _worktree(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    config = _parse(root, {"engine": "native", "memory": ["AGENTS.md"]})

    with pytest.raises(PlayerExperimentConfigError, match="different worktree"):
        revalidate_player_experiment(config, cwd=other)
    (root / "AGENTS.md").unlink()
    with pytest.raises(PlayerExperimentConfigError, match="does not exist"):
        revalidate_player_experiment(config, cwd=root)
