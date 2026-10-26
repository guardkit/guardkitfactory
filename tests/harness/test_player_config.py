"""Validation tests for the single required local Player configuration."""

from __future__ import annotations

import logging
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
    ("field", "value", "logged"),
    [
        ("skills", ["missing"], "does not exist"),
        ("skills", ["docs/CONTRIBUTING.md"], "is not a directory"),
        ("repository_instructions", ["skills"], "is not a regular file"),
        ("protected_paths", ["missing"], "it protects nothing"),
    ],
)
def test_unusable_declared_paths_are_logged_and_skipped(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    field: str,
    value: list[str],
    logged: str,
) -> None:
    # 26 October 2026 (step 2): a declaration slip is a note, not a refusal
    # of the Player (census GKF-071 and GKF-072).
    root, profile = _worktree(tmp_path)
    with caplog.at_level(logging.INFO):
        config = build_player_config(cwd=root, dcode_home=profile, **{field: value})
    assert getattr(config, field) == ()
    assert logged in caplog.text


def test_sources_and_protection_outside_the_worktree_are_not_used(
    tmp_path: Path,
) -> None:
    root, profile = _worktree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "instructions.md").write_text("outside")
    (root / "outside-link").symlink_to(outside, target_is_directory=True)

    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        skills=["outside-link", "skills"],
        protected_paths=["../outside", "evidence"],
    )
    assert config.skills == ((root / "skills").resolve(),)
    assert config.protected_paths == ((root / "evidence").resolve(),)


def test_dcode_profile_must_be_outside_the_worktree(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    assert build_player_config(cwd=root, dcode_home=profile).dcode_home == profile.resolve()

    inside = root / "profile"
    inside.mkdir()
    with pytest.raises(PlayerConfigError, match="outside"):
        build_player_config(cwd=root, dcode_home=inside)


def test_a_bad_lock_identity_is_logged_and_dropped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root, profile = _worktree(tmp_path)
    with caplog.at_level(logging.WARNING):
        config = build_player_config(
            cwd=root, dcode_home=profile, lock_profile_identity=(1, "2")  # type: ignore[arg-type]
        )
    assert config.lock_profile_identity is None
    assert "will not be locked" in caplog.text


def test_blank_or_repeated_commands_are_skipped(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        declared_commands=[("test", "make check"), ("", "x"), ("test", "make other")],
    )
    assert config.declared_commands == (("test", "make check"),)


def test_revalidation_leaves_out_a_source_that_went(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        repository_instructions=["docs/CONTRIBUTING.md"],
    )
    other = tmp_path / "other"
    other.mkdir()

    assert revalidate_player_config(config, cwd=other).repository_instructions == ()
    (root / "docs" / "CONTRIBUTING.md").unlink()
    assert revalidate_player_config(config, cwd=root).repository_instructions == ()


def test_revalidation_returns_the_rebuilt_config_when_a_source_moved(
    tmp_path: Path,
) -> None:
    root, profile = _worktree(tmp_path)
    docs = root / "docs"
    (docs / "a.md").write_text("first\n")
    (docs / "b.md").write_text("second\n")
    config = build_player_config(
        cwd=root, dcode_home=profile, required_documents=["docs/a.md"]
    )
    (docs / "a.md").unlink()
    (docs / "a.md").symlink_to("b.md")

    rebuilt = revalidate_player_config(config, cwd=root)

    assert rebuilt != config
    assert rebuilt.required_documents == ((docs / "b.md").resolve(),)


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
    assert revalidate_player_config(config, cwd=root).required_documents == ()


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


def test_declared_document_slips_are_logged_by_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing, escaping or non-file document is skipped; a large or
    non-UTF-8 one is kept. Each is logged by path (26 October 2026)."""

    root, profile = _worktree(tmp_path)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "conventions.md").write_text("outside the worktree\n")
    (root / "references" / "outside-link.md").symlink_to(outside / "conventions.md")
    (root / "references" / "oversized.md").write_bytes(b"x" * 131_073)
    (root / "references" / "binary.md").write_bytes(b"# title\n\xff\xfe")

    cases: list[tuple[list[str], str, int]] = [
        (["references/missing.md"], "does not exist", 0),
        (["../outside/conventions.md"], "outside the task worktree", 0),
        (["references/outside-link.md"], "outside the task worktree", 0),
        (["references/oversized.md"], "more than the guide of 131072", 1),
        (["references/binary.md"], "not valid UTF-8", 1),
        (["references"], "is not a regular file", 0),
    ]
    for value, logged, kept in cases:
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            config = build_player_config(
                cwd=root, dcode_home=profile, required_documents=value
            )
        assert len(config.required_documents) == kept, value
        assert logged in caplog.text, value


def test_more_than_32_declared_documents_are_kept_with_a_note(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root, profile = _worktree(tmp_path)
    declared: list[str] = []
    for index in range(33):
        name = f"references/doc-{index:02d}.md"
        (root / name).write_text(f"# document {index}\n")
        declared.append(name)

    with caplog.at_level(logging.WARNING):
        config = build_player_config(
            cwd=root, dcode_home=profile, required_documents=declared
        )
    assert len(config.required_documents) == 33
    assert "more than the guide of 32" in caplog.text


# Repository instructions: CLAUDE.md that links to AGENTS.md (7 October 2026).
# GuardKit adds both conventional names when both are files, so a project
# whose CLAUDE.md is a symbolic link to AGENTS.md used to be refused for a
# "duplicate resolved path".


def test_claude_md_linked_to_agents_md_is_one_document_read_once(
    tmp_path: Path,
) -> None:
    from guardkitfactory.harness.langgraph_harness import _player_context_prompt

    root, profile = _worktree(tmp_path)
    (root / "AGENTS.md").write_text("# Agent guidance\nRun the declared check.\n")
    (root / "CLAUDE.md").symlink_to("AGENTS.md")

    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        repository_instructions=["AGENTS.md", "CLAUDE.md"],
    )

    assert config.repository_instructions == ((root / "AGENTS.md").resolve(),)
    assert revalidate_player_config(config, cwd=root) is config
    prompt = _player_context_prompt(config)
    assert prompt.count("Run the declared check.") == 1


def test_claude_md_and_agents_md_as_separate_files_are_both_kept(
    tmp_path: Path,
) -> None:
    root, profile = _worktree(tmp_path)
    (root / "AGENTS.md").write_text("# Agent guidance\n")
    # A one-line pointer is its own file, so both are read.
    (root / "CLAUDE.md").write_text("See AGENTS.md.\n")

    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        repository_instructions=["AGENTS.md", "CLAUDE.md"],
    )

    assert config.repository_instructions == (
        (root / "AGENTS.md").resolve(),
        (root / "CLAUDE.md").resolve(),
    )


def test_claude_md_linked_outside_the_project_is_not_read(
    tmp_path: Path,
) -> None:
    root, profile = _worktree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "AGENTS.md").write_text("outside the worktree\n")
    (root / "AGENTS.md").write_text("# Agent guidance\n")
    (root / "CLAUDE.md").symlink_to(outside / "AGENTS.md")

    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        repository_instructions=["AGENTS.md", "CLAUDE.md"],
    )
    assert config.repository_instructions == ((root / "AGENTS.md").resolve(),)


def test_a_repeated_declared_document_is_kept_once(tmp_path: Path) -> None:
    root, profile = _worktree(tmp_path)
    (root / "references" / "alias.md").symlink_to("project-conventions.md")

    config = build_player_config(
        cwd=root,
        dcode_home=profile,
        required_documents=[
            "references/project-conventions.md",
            "references/alias.md",
        ],
    )
    assert config.required_documents == (
        (root / "references" / "project-conventions.md").resolve(),
    )
