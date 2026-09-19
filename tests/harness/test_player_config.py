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
    (root / "references").mkdir()
    (root / "references" / "project-conventions.md").write_text(
        "# Conventions\nName the delivered surface.\n"
    )
    profile = tmp_path / "profile"
    profile.mkdir()
    return root, profile


def _makefile_project(tmp_path: Path) -> tuple[Path, Path]:
    """A deliberately non-Python project: a Makefile and a plain-text document."""

    root = tmp_path / "make-repo"
    (root / "skills" / "release").mkdir(parents=True)
    (root / "skills" / "release" / "SKILL.md").write_text(
        "---\nname: release\ndescription: Cut a release.\n---\n"
    )
    (root / "Makefile").write_text("check:\n\t./qa/run-suite.sh\n")
    (root / "docs").mkdir()
    (root / "docs" / "conventions.txt").write_text("Use the declared make targets.\n")
    profile = tmp_path / "make-profile"
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
        required_documents=["references/project-conventions.md"],
    )

    assert config == PlayerConfig(
        skills=((root / "skills").resolve(),),
        memory=(),
        repository_instructions=((root / "docs/CONTRIBUTING.md").resolve(),),
        declared_commands=(("test", "./qa/run-suite.sh --exact"),),
        protected_paths=((root / "evidence").resolve(),),
        cwd=root.resolve(),
        dcode_home=profile.resolve(),
        required_documents=(
            (root / "references/project-conventions.md").resolve(),
        ),
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
    assert config.required_documents == ()


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


def test_declared_documents_are_canonical_and_revalidated(tmp_path: Path) -> None:
    """The positive control: a declared document is accepted and revalidated."""

    root, profile = _worktree(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        skills=["skills"],
        required_documents=["references/project-conventions.md"],
    )

    assert config.required_documents == (
        (root / "references" / "project-conventions.md").resolve(),
    )
    assert revalidate_player_config(config, cwd=root) is config
    (root / "references" / "project-conventions.md").unlink()
    with pytest.raises(PlayerConfigError, match="required_documents"):
        revalidate_player_config(config, cwd=root)


def test_declared_documents_work_for_a_non_python_project(tmp_path: Path) -> None:
    """A Makefile project declaring a plain-text document needs no Python."""

    root, profile = _makefile_project(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        skills=["skills"],
        declared_commands=[("test", "make check")],
        required_documents=["docs/conventions.txt"],
    )

    assert config.required_documents == ((root / "docs" / "conventions.txt").resolve(),)
    assert config.declared_commands == (("test", "make check"),)


def test_declared_document_refusals_name_the_path(tmp_path: Path) -> None:
    """Every named failure mode is refused at configuration time, by name."""

    root, profile = _worktree(tmp_path)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "conventions.md").write_text("outside the worktree\n")
    (root / "references" / "outside-link.md").symlink_to(outside / "conventions.md")
    (root / "references" / "oversized.md").write_bytes(b"x" * 65_537)
    (root / "references" / "binary.md").write_bytes(b"# title\n\xff\xfe")

    cases: list[tuple[list[str], str]] = [
        (["references/missing.md"], "does not exist"),
        (["../outside/conventions.md"], "outside the task worktree"),
        (["references/outside-link.md"], "outside the task worktree"),
        (["references/oversized.md"], "65536 are accepted"),
        (["references/binary.md"], "not valid UTF-8"),
        (
            [
                "references/project-conventions.md",
                "references/project-conventions.md",
            ],
            "duplicate resolved path",
        ),
        (["references"], "must resolve to a regular file"),
    ]
    for value, match in cases:
        with pytest.raises(PlayerConfigError, match=match):
            build_player_config(
                cwd=root, dcode_home=profile, required_documents=value
            )
        # The refusal names the declared path so a person can fix the declaration.
        with pytest.raises(PlayerConfigError, match="required_documents"):
            build_player_config(
                cwd=root, dcode_home=profile, required_documents=value
            )


def test_declared_documents_are_bounded_in_count(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    declared: list[str] = []
    for index in range(33):
        name = f"references/doc-{index:02d}.md"
        (root / name).write_text(f"# document {index}\n")
        declared.append(name)

    assert (
        len(
            build_player_config(
                cwd=root, dcode_home=profile, required_documents=declared[:32]
            ).required_documents
        )
        == 32
    )
    with pytest.raises(PlayerConfigError, match="at most 32 are accepted"):
        build_player_config(cwd=root, dcode_home=profile, required_documents=declared)
