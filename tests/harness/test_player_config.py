"""Validation tests for the single required local Player configuration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from guardkitfactory.harness.player_config import (
    PlayerConfig,
    PlayerConfigError,
    build_player_config,
    revalidate_player_config,
)


def _worktree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "skills" / "planning").mkdir(parents=True)
    (root / "skills" / "planning" / "SKILL.md").write_text(
        "---\nname: planning\ndescription: Plan changes.\n---\n"
    )
    (root / "docs").mkdir()
    (root / "docs" / "CONTRIBUTING.md").write_text("# Instructions\n")
    (root / "evidence").mkdir()
    profile = tmp_path / "profile"
    profile.mkdir()
    return root, profile


def test_project_inputs_are_canonical_and_immutable(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        skills=["skills"],
        repository_instructions=["docs/CONTRIBUTING.md"],
        declared_commands=[("test", "./qa/run-suite.sh --exact")],
        protected_paths=["evidence"],
    )

    assert config == PlayerConfig(
        skills=((root / "skills").resolve(),),
        memory=(),
        repository_instructions=((root / "docs/CONTRIBUTING.md").resolve(),),
        declared_commands=(("test", "./qa/run-suite.sh --exact"),),
        protected_paths=((root / "evidence").resolve(),),
        cwd=root.resolve(),
        dcode_home=profile.resolve(),
    )
    with pytest.raises(FrozenInstanceError):
        config.cwd = profile  # type: ignore[misc]
    assert revalidate_player_config(config, cwd=root) is config


def test_empty_project_declarations_add_no_stack_defaults(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    config = build_player_config(cwd=root, dcode_home=profile)

    assert config.skills == ()
    assert config.memory == ()
    assert config.repository_instructions == ()
    assert config.declared_commands == ()
    assert config.protected_paths == ()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("skills", ["missing"], "does not exist"),
        ("skills", ["docs/CONTRIBUTING.md"], "directory"),
        ("repository_instructions", ["skills"], "regular file"),
        ("protected_paths", ["missing"], "does not exist"),
    ],
)
def test_invalid_declared_paths_fail_visibly(
    tmp_path: Path, field: str, value: list[str], match: str
) -> None:
    root, profile = _worktree(tmp_path)
    kwargs = {field: value}
    with pytest.raises(PlayerConfigError, match=match):
        build_player_config(cwd=root, dcode_home=profile, **kwargs)


def test_sources_and_protection_cannot_escape_worktree(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "instructions.md").write_text("outside")
    (root / "outside-link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PlayerConfigError, match="outside the task worktree"):
        build_player_config(cwd=root, dcode_home=profile, skills=["outside-link"])
    with pytest.raises(PlayerConfigError, match="outside the task worktree"):
        build_player_config(
            cwd=root,
            dcode_home=profile,
            protected_paths=["../outside"],
        )


def test_dcode_profile_must_be_absolute_external_and_writable(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    assert build_player_config(cwd=root, dcode_home=profile).dcode_home == profile.resolve()

    with pytest.raises(PlayerConfigError, match="absolute"):
        build_player_config(cwd=root, dcode_home="profile")
    inside = root / "profile"
    inside.mkdir()
    with pytest.raises(PlayerConfigError, match="outside"):
        build_player_config(cwd=root, dcode_home=inside)


def test_revalidation_refuses_changed_source_and_worktree(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        repository_instructions=["docs/CONTRIBUTING.md"],
    )
    other = tmp_path / "other"
    other.mkdir()

    with pytest.raises(PlayerConfigError, match="outside the task worktree"):
        revalidate_player_config(config, cwd=other)
    (root / "docs" / "CONTRIBUTING.md").unlink()
    with pytest.raises(PlayerConfigError, match="does not exist"):
        revalidate_player_config(config, cwd=root)
