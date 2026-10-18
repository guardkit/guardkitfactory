"""Restoring a run profile its owner made to the clean launch state.

18 October 2026 (build FEAT-05EE, and FEAT-B463 on 11 October): GuardKit reuses
one run profile for every Player turn in a process, and one stray file left
there refused every later launch. ``reset_run_profile`` lets the owner remove
what the clean profile lacks; the launch check afterwards is unchanged.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import threading
from pathlib import Path

import pytest

from guardkitfactory.harness import PlayerLaunchRefused, build_player_config, reset_run_profile
from guardkitfactory.harness.dcode_harness import (
    _validate_launch,
    player_profile_in_use,
)

_needs_dcode = pytest.mark.skipif(
    importlib.util.find_spec("deepagents_code") is None,
    reason="the launch check needs the required dcode dependency",
)


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """A profile as dcode leaves it after a clean turn."""

    root = (tmp_path / "guardkit-dcode-1234-abc").resolve()
    (root / "guardkit-player" / "skills").mkdir(parents=True)
    return root


@pytest.fixture
def launch_env(monkeypatch: pytest.MonkeyPatch, profile: Path) -> None:
    monkeypatch.setenv("DEEPAGENTS_HOME", str(profile))
    monkeypatch.setenv("DEEPAGENTS_CODE_OFFLINE", "1")
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        monkeypatch.setenv(name, "false")


def _launch_check(tmp_path: Path, profile: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir(exist_ok=True)
    _validate_launch(build_player_config(cwd=worktree, dcode_home=profile))


def _contents(profile: Path) -> list[str]:
    return sorted(str(path.relative_to(profile)) for path in profile.rglob("*"))


def test_clean_profile_is_left_alone_and_logs_nothing(
    profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (profile / "guardkit-player" / "AGENTS.md").write_bytes(b"")
    with caplog.at_level(logging.WARNING):
        assert reset_run_profile(profile) == []
    assert _contents(profile) == [
        "guardkit-player",
        "guardkit-player/AGENTS.md",
        "guardkit-player/skills",
    ]
    assert not caplog.records


@_needs_dcode
def test_stray_entries_are_removed_and_described_without_contents(
    tmp_path: Path, profile: Path, launch_env: None, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "check.sh output: do not log me"
    (profile / "full.log").write_text(secret)
    (profile / "cache" / "nested").mkdir(parents=True)
    (profile / "cache" / "nested" / "blob.bin").write_bytes(b"\x00" * 10)
    (profile / ".env").write_text("TOKEN=x")
    (profile / "guardkit-player" / "AGENTS.md").write_text("remembered")
    (profile / "guardkit-player" / "skills" / "evil").mkdir()
    (profile / "guardkit-player" / "skills" / "evil" / "SKILL.md").write_text("x")
    os.mkfifo(profile / "pipe")

    # Today's refusal, before the reset.
    with pytest.raises(PlayerLaunchRefused):
        _launch_check(tmp_path, profile)

    with caplog.at_level(logging.WARNING, logger="guardkitfactory.harness.dcode_harness"):
        removed = reset_run_profile(profile)

    assert removed is not None
    assert _contents(profile) == ["guardkit-player", "guardkit-player/skills"]
    paths = {entry["path"] for entry in removed}
    assert {
        "full.log",
        "cache",
        "cache/nested",
        "cache/nested/blob.bin",
        ".env",
        "pipe",
        "guardkit-player/AGENTS.md",
        "guardkit-player/skills/evil",
        "guardkit-player/skills/evil/SKILL.md",
    } == paths
    full_log = next(entry for entry in removed if entry["path"] == "full.log")
    assert full_log == {
        "path": "full.log",
        "type": "file",
        "size": len(secret),
        "sha256": hashlib.sha256(secret.encode()).hexdigest(),
    }
    (message,) = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "reset before launch" in message and "full.log" in message
    assert secret not in message and "TOKEN=x" not in message and "remembered" not in message
    _launch_check(tmp_path, profile)


@_needs_dcode
def test_links_are_removed_as_links_and_never_followed(
    tmp_path: Path, profile: Path, launch_env: None
) -> None:
    outside = tmp_path / "outside"
    (outside / "inner").mkdir(parents=True)
    (outside / "inner" / "keep.txt").write_text("not the profile's")
    (profile / "to-dir").symlink_to(outside, target_is_directory=True)
    (profile / "to-file").symlink_to(outside / "inner" / "keep.txt")
    (profile / "dangling").symlink_to(tmp_path / "missing")
    # A link in place of dcode's own directory, and in place of the memory file.
    skills = profile / "guardkit-player" / "skills"
    skills.rmdir()
    skills.symlink_to(outside / "inner", target_is_directory=True)
    (profile / "guardkit-player" / "AGENTS.md").symlink_to(outside / "inner" / "keep.txt")

    removed = reset_run_profile(profile)

    assert removed is not None
    assert _contents(profile) == ["guardkit-player"]
    assert {entry["type"] for entry in removed} == {"symlink"}
    assert (outside / "inner" / "keep.txt").read_text() == "not the profile's"
    assert sorted(p.name for p in outside.rglob("*")) == ["inner", "keep.txt"]
    _launch_check(tmp_path, profile)


def test_a_linked_profile_root_is_not_reset(tmp_path: Path, profile: Path) -> None:
    (profile / "full.log").write_text("stray")
    link = tmp_path / "profile-link"
    link.symlink_to(profile, target_is_directory=True)

    assert reset_run_profile(link) is None
    assert reset_run_profile(Path("relative/profile")) is None
    assert (profile / "full.log").exists()


@_needs_dcode
@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_what_cannot_be_removed_keeps_todays_refusal(
    tmp_path: Path, profile: Path, launch_env: None, caplog: pytest.LogCaptureFixture
) -> None:
    locked = profile / "locked"
    locked.mkdir()
    (locked / "inside.txt").write_text("stuck")
    locked.chmod(0o500)
    try:
        with caplog.at_level(logging.WARNING, logger="guardkitfactory.harness.dcode_harness"):
            assert reset_run_profile(profile) is None
        assert any("reset stopped" in r.getMessage() for r in caplog.records)
        with pytest.raises(
            PlayerLaunchRefused,
            match="run profile contains unexpected configuration or nonempty memory",
        ):
            _launch_check(tmp_path, profile)
    finally:
        locked.chmod(0o700)


def test_no_reset_while_a_player_invocation_uses_the_profile(
    profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (profile / "full.log").write_text("being written by a running Player")
    with player_profile_in_use(profile):
        with caplog.at_level(logging.WARNING, logger="guardkitfactory.harness.dcode_harness"):
            assert reset_run_profile(profile) is None
        assert (profile / "full.log").exists()
        assert any("not reset: 1 Player invocation(s)" in r.getMessage() for r in caplog.records)
        # Nested use (two tasks at once) is counted, not overwritten.
        with player_profile_in_use(profile):
            pass
        assert reset_run_profile(profile) is None
    removed = reset_run_profile(profile)
    assert removed is not None and [entry["path"] for entry in removed] == ["full.log"]


def test_a_claim_waits_for_a_reset_in_progress(
    profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Player cannot start using the profile half-way through a reset."""

    from guardkitfactory.harness import dcode_harness

    (profile / "a.log").write_text("1")
    (profile / "b.log").write_text("2")
    started = threading.Event()
    release = threading.Event()
    real_unlink = os.unlink
    observed: list[list[str]] = []

    def slow_unlink(name: str, *, dir_fd: int | None = None) -> None:
        if not started.is_set():
            started.set()
            assert release.wait(10)
        real_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(dcode_harness.os, "unlink", slow_unlink)
    resetting = threading.Thread(target=reset_run_profile, args=(profile,))
    resetting.start()
    assert started.wait(10)

    def claim() -> None:
        with player_profile_in_use(profile):
            observed.append(sorted(p.name for p in profile.iterdir()))

    claimant = threading.Thread(target=claim)
    claimant.start()
    claimant.join(0.3)
    assert claimant.is_alive() and not observed
    release.set()
    resetting.join(10)
    claimant.join(10)
    assert observed == [["guardkit-player"]]
